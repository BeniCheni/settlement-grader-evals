"""The four RAG scorers, and the commands that run and report the A/B.

Retrieved items come from a record's tool calls. Needed items come from the
row's contexts. A scorer never treats the row's contexts as what the run
retrieved. No function here calls a model. `run` is the only command that
reaches `run_eval.main`, and only after the config, the hash and the run
directory have been accepted. `load_pair` applies every refusal of the two
runs; `report` and the Braintrust uploader both read the pair through it.

The report's verdict words are `ship` and `no-ship`.
"""
import argparse
import hashlib
import json
import os
import re
import sys

import run_eval
from scorer.checks import _best_facts, _committed, _facts_seen
from scorer.golden import key_for_leg
from scorer.stats import bootstrap_mean, canonical_json, paired_bootstrap, paired_difference
from scorer.traces import load_run


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join("packages", "rag-eval", "assignment-2", "config.yaml")

VERDICT_SHIP = "ship"
VERDICT_NO_SHIP = "no-ship"
WEAKER_TIE = "neither half: the two averages tie"
WEAKER_RETRIEVAL_EMPTY = "neither half: retrieval has no scored case"
WEAKER_GENERATION_EMPTY = "neither half: generation has no scored case"
WEAKER_BOTH_EMPTY = "neither half: neither half has a scored case"
WEAKER_RETRIEVAL = "retrieval is the weaker half"
WEAKER_GENERATION = "generation is the weaker half"

_TICKET_RESULTS = ("WIN", "LOSS", "PUSH", "VOID", "UNSETTLED", "NEEDS_HUMAN")
_SCORE_FIELDS = ("score_regulation_90", "score_halftime", "score_final")
_SCORE_CLAIM = re.compile(
    r"(?<![0-9\-\u2013])([0-9]{1,2})\s*[-\u2013]\s*([0-9]{1,2})(?![0-9\-\u2013])"
)
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_TOP_KEYS = (
    "bars", "bootstrap", "braintrust_experiments", "dataset", "dataset_sha256",
    "json", "langsmith_version", "model", "report", "runs", "statement", "variants",
)
_BAR_KEYS = ("faithfulness_lo_at_least", "outcome_fall_hi_at_most", "recall_lo_above")
_BOOT_KEYS = ("n_boot", "seed")
_VARIANT_KEYS = ("a", "b")
_FLAG_KEYS = (
    "disabled_tools", "drop_fields", "guard_input", "guard_model", "guard_output",
    "rule_match", "think",
)
_COMMANDS = (
    "python3 -m scorer.rag run --config %s --variant a",
    "python3 -m scorer.rag run --config %s --variant b",
    "python3 -m scorer.rag report --config %s",
)


class ConfigError(Exception):
    """The config breaks the contract. The command writes nothing."""


class ReportError(Exception):
    """The report cannot be written. Nothing has been written."""


def _result_has_error(result):
    if not isinstance(result, dict):
        return True
    return result.get("error") is not None


def retrieved_items(record):
    """(kind, id) pairs from the record's tools, in call order, first kept.

    A lookup_rule item's id is the topic its result resolved. A rule_error
    item's id is the topic the call asked for when that topic is a string.
    Otherwise it is json.dumps of the topic with sort_keys=True, or of null
    when the topic is missing, so the pair stays hashable and byte-stable and
    counts as retrieved and not relevant. A get_match_facts item's id is the
    string of the result's event_id. An errored facts result, or a facts
    result with no event_id, gives no item. find_match and settle_ticket give
    none.
    """
    items = []
    seen = set()
    tools = record.get("tools") if isinstance(record, dict) else None
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        name = tool.get("name")
        result = tool.get("result")
        args = tool.get("args") if isinstance(tool.get("args"), dict) else {}
        if name == "get_match_facts":
            if _result_has_error(result) or result.get("event_id") is None:
                continue
            item = ("event", str(result.get("event_id")))
        elif name == "lookup_rule":
            if _result_has_error(result):
                topic = args.get("topic")
                if isinstance(topic, str):
                    item = ("rule_error", topic)
                else:
                    item = ("rule_error", json.dumps(topic, sort_keys=True))
            else:
                topic = result.get("topic")
                if not isinstance(topic, str):
                    continue
                item = ("rule", topic)
        else:
            continue
        if item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def needed_items(row):
    """Distinct (kind, id) pairs in the row's context order, first kept."""
    items = []
    seen = set()
    contexts = row.get("contexts") if isinstance(row, dict) else None
    for ctx in contexts or []:
        if not isinstance(ctx, dict):
            continue
        kind = ctx.get("kind")
        if kind == "event":
            event_id = ctx.get("event_id")
            if event_id is None:
                continue
            item = ("event", str(event_id))
        elif kind == "rule":
            topic = ctx.get("topic")
            if not isinstance(topic, str):
                continue
            item = ("rule", topic)
        else:
            continue
        if item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _recall(needed, retrieved):
    if not needed:
        return None, "nothing needed", 0, 0
    found = sum(1 for item in needed if item in retrieved)
    return float(found) / float(len(needed)), "%d of %d" % (found, len(needed)), found, len(needed)


def _precision(needed, retrieved):
    if not needed:
        return None, "nothing needed", 0, 0
    if not retrieved:
        return 0.0, "0 of 0", 0, 0
    needed_set = set(needed)
    flags = [item in needed_set for item in retrieved]
    positions = [index for index, flag in enumerate(flags, start=1) if flag]
    if not positions:
        return 0.0, "0 of %d" % len(retrieved), 0, len(retrieved)
    total = 0.0
    for k in positions:
        total += float(sum(flags[:k])) / float(k)
    value = total / float(len(positions))
    return value, "%d of %d" % (len(positions), len(retrieved)), len(positions), len(retrieved)


def _scores_in(text):
    if not isinstance(text, str):
        return []
    found = []
    seen = set()
    for match in _SCORE_CLAIM.finditer(text):
        token = "%s-%s" % (match.group(1), match.group(2))
        if token in seen:
            continue
        seen.add(token)
        found.append(token)
    return found


def _orientations(token):
    left, right = token.split("-", 1)
    return set(((left, right), (right, left)))


def _score_supported(token, facts):
    """True when the claim matches a fetched score, either way round.

    facts may be unusable. With no facts the claim is unsupported.
    """
    if not isinstance(facts, dict):
        return False
    wanted = _orientations(token)
    for field in _SCORE_FIELDS:
        value = facts.get(field)
        if not isinstance(value, str):
            continue
        for other in _scores_in(value):
            if wanted & _orientations(other):
                return True
    return False


def _score_claims(final_legs, leg_number):
    tokens = []
    seen = set()
    for leg in final_legs:
        if not isinstance(leg, dict) or leg.get("leg") != leg_number:
            continue
        for token in _scores_in(leg.get("evidence")):
            if token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _grade_supported(grade, usable, key, other_has_l):
    """Whether one committed grade is supported.

    No usable facts: only NEEDS_HUMAN. A MOOT grade is supported when another
    leg has a committed L. Any other grade is supported when it equals the key.
    """
    if not usable:
        return grade == "NEEDS_HUMAN"
    if grade == "MOOT":
        return other_has_l
    return grade == key


def _usable_key(row_leg, facts):
    """(usable, key). A KeyError, TypeError or ValueError means no usable facts.

    Any other exception propagates. Usable facts with a key of None stay usable.
    """
    if not facts or not isinstance(row_leg, dict):
        return False, None
    try:
        grade, _evidence = key_for_leg(row_leg, facts)
    except (KeyError, TypeError, ValueError):
        return False, None
    return True, grade


def _faithfulness(row, record):
    row_legs = row.get("legs") if isinstance(row.get("legs"), list) else []
    ticket = record.get("ticket") if isinstance(record.get("ticket"), dict) else {}
    ticket_legs = ticket.get("legs") if isinstance(ticket.get("legs"), list) else []
    final = record.get("final") if isinstance(record.get("final"), dict) else {}
    final_legs = final.get("legs") if isinstance(final.get("legs"), list) else []
    seen = _facts_seen(record)
    committed = []
    usable = []
    keys = []
    facts_list = []
    for index, row_leg in enumerate(row_legs):
        if isinstance(row_leg, dict):
            committed.append(_committed(record, index))
        else:
            committed.append([])
        ticket_leg = ticket_legs[index] if index < len(ticket_legs) else None
        facts = _best_facts(ticket_leg, seen) if isinstance(ticket_leg, dict) else None
        facts_list.append(facts)
        is_usable, key = _usable_key(row_leg, facts)
        usable.append(is_usable)
        keys.append(key)
    claims = 0
    supported_n = 0
    legs_left = 0
    for index, row_leg in enumerate(row_legs):
        if not isinstance(row_leg, dict):
            continue
        if usable[index] and keys[index] is None:
            legs_left += 1
            continue
        other_has_l = any(
            "L" in grades for other, grades in enumerate(committed) if other != index
        )
        if committed[index]:
            claims += 1
            if all(_grade_supported(grade, usable[index], keys[index], other_has_l)
                   for grade in committed[index]):
                supported_n += 1
        for token in _score_claims(final_legs, row_leg.get("leg")):
            claims += 1
            if _score_supported(token, facts_list[index]):
                supported_n += 1
    if claims == 0:
        return None, "no claim", 0, 0, legs_left
    value = float(supported_n) / float(claims)
    return value, "%d of %d" % (supported_n, claims), claims, supported_n, legs_left


def _last_settle_ticket_result(record):
    """(saw a result with no error, that result's ticket_result)."""
    saw = False
    found = None
    for tool in record.get("tools") or []:
        if not isinstance(tool, dict) or tool.get("name") != "settle_ticket":
            continue
        result = tool.get("result")
        if _result_has_error(result):
            continue
        saw = True
        found = result.get("ticket_result")
    return saw, found


def _relevancy(row, record):
    final = record.get("final")
    if not isinstance(final, dict):
        return 0.0, "no final", 0, 4
    legs = final.get("legs")
    if not isinstance(legs, list):
        legs = []
    ticket_legs = row.get("legs") if isinstance(row.get("legs"), list) else []
    one_each = len(legs) == len(ticket_legs)
    numbered = True
    for index, leg in enumerate(legs, start=1):
        if not isinstance(leg, dict) or leg.get("leg") != index:
            numbered = False
            break
    result = final.get("ticket_result")
    in_enum = result in _TICKET_RESULTS
    saw, settled = _last_settle_ticket_result(record)
    matches = saw and result == settled
    held = sum(1 for flag in (one_each, numbered, in_enum, matches) if flag)
    return float(held) / 4.0, "%d of 4" % held, held, 4


def _pack(value, reason, k, n):
    return {"value": value, "reason": reason, "k": k, "n": n}


def score_case(row, record):
    """Each scorer's value and reason, plus faithfulness's claim counts.

    The public scorers call this and return only the value.
    """
    if not isinstance(row, dict) or not isinstance(record, dict):
        raise ValueError("score_case needs a row and a record")
    needed = needed_items(row)
    retrieved = retrieved_items(record)
    recall = _recall(needed, retrieved)
    precision = _precision(needed, retrieved)
    faith = _faithfulness(row, record)
    relevancy = _relevancy(row, record)
    return {
        "context_recall": _pack(*recall),
        "context_precision": _pack(*precision),
        "faithfulness": {
            "value": faith[0],
            "reason": faith[1],
            "claims": faith[2],
            "supported": faith[3],
            "legs_left": faith[4],
        },
        "answer_relevancy": _pack(*relevancy),
    }


def _inputs(output, metadata):
    if not isinstance(output, dict) or not isinstance(metadata, dict):
        raise ValueError("scorer inputs are refused")
    row = metadata.get("row")
    record = output.get("record")
    if not isinstance(row, dict) or not isinstance(record, dict):
        raise ValueError("scorer inputs are refused")
    return row, record


def context_recall(output, expected, metadata=None, **kwargs):
    row, record = _inputs(output, metadata)
    return score_case(row, record)["context_recall"]["value"]


def context_precision(output, expected, metadata=None, **kwargs):
    row, record = _inputs(output, metadata)
    return score_case(row, record)["context_precision"]["value"]


def faithfulness(output, expected, metadata=None, **kwargs):
    row, record = _inputs(output, metadata)
    return score_case(row, record)["faithfulness"]["value"]


def answer_relevancy(output, expected, metadata=None, **kwargs):
    row, record = _inputs(output, metadata)
    return score_case(row, record)["answer_relevancy"]["value"]


def _expect_object(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ConfigError("%s is refused" % label)
    return value


def _path(value):
    if not isinstance(value, str) or value == "" or os.path.isabs(value) or value.startswith("~"):
        raise ConfigError("path is refused")
    if ".." in value.split("/"):
        raise ConfigError("path is refused")
    return value


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError("%s is refused" % label)
    return value


def _optional_object(value, keys, label):
    if value is None:
        return None
    obj = _expect_object(value, keys, label)
    for key in keys:
        if not isinstance(obj[key], str) or obj[key] == "":
            raise ConfigError("%s is refused" % label)
    return obj


def load_config(path):
    """The config object, or ConfigError when the contract refuses it."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ConfigError("config is unreadable")
    _expect_object(data, _TOP_KEYS, "config")
    _path(data["dataset"])
    if data["dataset_sha256"] is not None and not isinstance(data["dataset_sha256"], str):
        raise ConfigError("dataset_sha256 is refused")
    if not isinstance(data["model"], str) or data["model"] == "":
        raise ConfigError("model is refused")
    variants = _expect_object(data["variants"], _VARIANT_KEYS, "variants")
    for name in _VARIANT_KEYS:
        inner = _expect_object(variants[name], ("rule_match",), "variants.%s" % name)
        if inner["rule_match"] not in ("exact", "alias"):
            raise ConfigError("rule_match is refused")
    runs = _expect_object(data["runs"], _VARIANT_KEYS, "runs")
    for name in _VARIANT_KEYS:
        if not isinstance(runs[name], str) or _RUN_ID.fullmatch(runs[name]) is None:
            raise ConfigError("run id is refused")
    boot = _expect_object(data["bootstrap"], _BOOT_KEYS, "bootstrap")
    if isinstance(boot["n_boot"], bool) or not isinstance(boot["n_boot"], int) or boot["n_boot"] <= 0:
        raise ConfigError("n_boot is refused")
    if isinstance(boot["seed"], bool) or not isinstance(boot["seed"], int):
        raise ConfigError("seed is refused")
    bars = _expect_object(data["bars"], _BAR_KEYS, "bars")
    for key in _BAR_KEYS:
        _number(bars[key], "bar")
    _path(data["statement"])
    _path(data["report"])
    _path(data["json"])
    _optional_object(data["langsmith_version"], ("as_of", "dataset_id"), "langsmith_version")
    _optional_object(data["braintrust_experiments"], _VARIANT_KEYS, "braintrust_experiments")
    return data


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


def _dataset_digest(root, config):
    path = os.path.join(root, config["dataset"])
    if not os.path.isfile(path):
        return None
    return hashlib.sha256(_read_bytes(path)).hexdigest()


def _refuse_dataset(root, config):
    """None when v1's bytes match dataset_sha256, else the one-line reason."""
    if config["dataset_sha256"] is None:
        return "dataset_sha256 is null"
    digest = _dataset_digest(root, config)
    if digest is None:
        return "v1 is missing"
    if digest != config["dataset_sha256"]:
        return "v1 bytes do not match dataset_sha256"
    return None


def _load_v1(root, config):
    path = os.path.join(root, config["dataset"])
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip() == "":
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ReportError("v1 is unreadable")
                rows.append(item)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ReportError("v1 is unreadable")
    ids = [row.get("case_id") for row in rows]
    if any(not isinstance(case_id, str) or case_id == "" for case_id in ids):
        raise ReportError("v1 is unreadable")
    if len(ids) != len(set(ids)):
        raise ReportError("v1 is unreadable")
    rows.sort(key=lambda row: row["case_id"])
    return rows


def _load_meta(path, variant):
    if not os.path.isfile(path):
        raise ReportError("variant %s run_meta.json is missing" % variant)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ReportError("variant %s run_meta.json is unreadable" % variant)
    if not isinstance(meta, dict):
        raise ReportError("variant %s run_meta.json is unreadable" % variant)
    return meta


def _nonempty(value):
    return isinstance(value, str) and value != ""


def _check_meta(meta, config, variant):
    if not _nonempty(meta.get("model_digest")):
        raise ReportError("variant %s model_digest is missing" % variant)
    if not _nonempty(meta.get("ollama_version")):
        raise ReportError("variant %s ollama_version is missing" % variant)
    if meta.get("model") != config["model"]:
        raise ReportError("model differs from the config")
    if meta.get("cases_file") != config["dataset"]:
        raise ReportError("cases_file differs from the dataset")
    if meta.get("rule_match") != config["variants"][variant]["rule_match"]:
        raise ReportError("rule_match differs from the variant")


def _load_records(run_dir, variant, case_ids):
    path = os.path.join(run_dir, "settlement-traces.json")
    if not os.path.isfile(path):
        raise ReportError("variant %s settlement-traces.json is missing" % variant)
    try:
        records = load_run(run_dir)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise ReportError("variant %s settlement-traces.json is unreadable" % variant)
    found = {}
    allowed = set(case_ids)
    for record in records:
        case_id = record.get("case_id")
        if case_id not in allowed:
            raise ReportError("a record for a case v1 does not hold")
        if case_id in found:
            raise ReportError("two records for one case")
        found[case_id] = record
    for case_id in case_ids:
        if case_id not in found:
            raise ReportError("a v1 case has no record")
    return found


def _tickets_match(rows, records):
    for row in rows:
        question = row.get("question")
        try:
            ticket = json.loads(question)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ReportError("a record ticket differs from its question")
        if ticket != records[row["case_id"]].get("ticket"):
            raise ReportError("a record ticket differs from its question")


def _read_statement(path):
    if not os.path.isfile(path):
        raise ReportError("statement is missing")
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except (OSError, UnicodeError):
        raise ReportError("statement is missing")
    if text.strip() == "":
        raise ReportError("statement is blank")
    return text


def recall_bar_holds(lower, paired, threshold):
    """True when the interval's lower bound is greater than the bar."""
    if paired == 0 or lower is None:
        return False
    return lower > threshold


def faithfulness_bar_holds(lower, paired, threshold):
    """True when the interval's lower bound is at least the bar."""
    if paired == 0 or lower is None:
        return False
    return lower >= threshold


def outcome_bar_holds(a, b, c, d, threshold):
    """(holds, paired_difference or None). A missing difference does not hold."""
    diff = paired_difference(a, b, c, d)
    if diff is None:
        return False, None
    return diff[2] <= threshold, diff


def _fmt(value):
    if value is None:
        return "none"
    return "%.3f" % value


def _count(value):
    return "%d" % value


def _block(per_case, n_boot, seed, legs_left=None):
    scored = [item["value"] for item in per_case if item["value"] is not None]
    if scored:
        mean, lo, hi = bootstrap_mean(scored, n_boot, seed)
    else:
        mean = lo = hi = None
    block = {
        "hi": hi,
        "k": sum(item["k"] for item in per_case),
        "lo": lo,
        "mean": mean,
        "n": sum(item["n"] for item in per_case),
        "none": len(per_case) - len(scored),
        "scored": len(scored),
    }
    if legs_left is not None:
        block["legs_left"] = legs_left
    return block


def _paired_block(left_values, right_values, n_boot, seed):
    paired_a = []
    paired_b = []
    left = 0
    for left_value, right_value in zip(left_values, right_values):
        if left_value is None or right_value is None:
            left += 1
            continue
        paired_a.append(left_value)
        paired_b.append(right_value)
    if not paired_a:
        return {"hi": None, "left": left, "lo": None, "mean_delta": None, "paired": 0}
    mean, lo, hi = paired_bootstrap(paired_a, paired_b, n_boot=n_boot, seed=seed)
    return {
        "hi": hi,
        "left": left,
        "lo": lo,
        "mean_delta": mean,
        "paired": len(paired_a),
    }


def _values(scores, name):
    return [item[name]["value"] for item in scores]


def _weaker(retrieval, generation):
    if retrieval is None and generation is None:
        return {"name": None, "reason": WEAKER_BOTH_EMPTY}
    if retrieval is None:
        return {"name": None, "reason": WEAKER_RETRIEVAL_EMPTY}
    if generation is None:
        return {"name": None, "reason": WEAKER_GENERATION_EMPTY}
    if retrieval == generation:
        return {"name": None, "reason": WEAKER_TIE}
    if retrieval < generation:
        return {"name": "retrieval", "reason": WEAKER_RETRIEVAL}
    return {"name": "generation", "reason": WEAKER_GENERATION}


def _half_average(left, right):
    if left is None or right is None:
        return None
    return (left + right) / 2.0


def _below_one(value):
    return isinstance(value, float) and not isinstance(value, bool) and value < 1.0


def _outcome_matches(row, record):
    expected_result, expected_net = run_eval.expected_of(row)
    accept = (row.get("expected") or {}).get("accept_needs_human", False)
    return run_eval.outcome_match(record.get("final"), expected_result, expected_net, accept)


def _command_label(config_path, root):
    """The config's path under the root, as the report's commands print it.

    A config outside the root is refused: the commands must name the file
    that was used, and a path outside the repository cannot be printed in a
    byte-stable report.
    """
    if not config_path:
        return DEFAULT_CONFIG
    absolute = os.path.realpath(config_path)
    prefix = os.path.realpath(root) + os.sep
    if not absolute.startswith(prefix):
        raise ReportError("config is outside the root")
    return absolute[len(prefix):].replace(os.sep, "/")


def _variant_flags(meta, run_id):
    flags = {"run_id": run_id}
    for key in _FLAG_KEYS:
        if key in meta:
            flags[key] = meta[key]
    return flags


# run_meta keys that may differ between the two runs of one A/B.
_PAIR_FREE_KEYS = ("outcome_matches", "rule_match", "run_id")


def _check_pair(metas):
    """The two runs are one session and one condition, apart from rule_match.

    The digest and the Ollama version are the spec's two checks. Every other
    run_meta key but run_id, rule_match and outcome_matches must agree too: a
    pair whose system_prompt, think, drop_fields, budgets or guards differ is
    not the A/B. run passes none of those flags, so a pair it made never
    differs there.
    """
    left = metas["a"]
    right = metas["b"]
    if left["model_digest"] != right["model_digest"]:
        raise ReportError("model_digest differs")
    if left["ollama_version"] != right["ollama_version"]:
        raise ReportError("ollama_version differs")
    for key in sorted(set(left) | set(right)):
        if key in _PAIR_FREE_KEYS:
            continue
        if key not in left or key not in right or left[key] != right[key]:
            raise ReportError("run_meta %s differs" % key)


def load_pair(config, root):
    """(rows, metas, records) once every refusal has passed; ReportError otherwise.

    rows are v1 in case_id order; metas and records are keyed by variant, and
    records[variant] by case_id. report and uploaders/braintrust_eval.py both
    read the pair through this, so the uploader cannot accept a pair that
    report refuses.
    """
    reason = _refuse_dataset(root, config)
    if reason:
        raise ReportError(reason)
    rows = _load_v1(root, config)
    case_ids = [row["case_id"] for row in rows]
    metas = {}
    records = {}
    for variant in _VARIANT_KEYS:
        run_dir = os.path.join(root, "traces", config["runs"][variant])
        if not os.path.isdir(run_dir):
            raise ReportError("variant %s run is missing" % variant)
        meta = _load_meta(os.path.join(run_dir, "run_meta.json"), variant)
        _check_meta(meta, config, variant)
        found = _load_records(run_dir, variant, case_ids)
        _tickets_match(rows, found)
        metas[variant] = meta
        records[variant] = found
    _check_pair(metas)
    return rows, metas, records


def prepare_report(config, root, config_path=None):
    """(markdown, canonical json). ReportError before either string exists."""
    label = _command_label(config_path, root)
    rows, metas, records = load_pair(config, root)
    statement = _read_statement(os.path.join(root, config["statement"]))
    scored = {}
    for variant in _VARIANT_KEYS:
        scored[variant] = [score_case(row, records[variant][row["case_id"]]) for row in rows]
    n_boot = config["bootstrap"]["n_boot"]
    seed = config["bootstrap"]["seed"]
    variants = {}
    for variant in _VARIANT_KEYS:
        cases = scored[variant]
        legs_left = sum(item["faithfulness"]["legs_left"] for item in cases)
        variants[variant] = {
            "generation": {
                "answer_relevancy": _block(
                    [_pack(item["answer_relevancy"]["value"], "", item["answer_relevancy"]["k"], item["answer_relevancy"]["n"]) for item in cases],
                    n_boot, seed),
                "faithfulness": _block(
                    [_pack(item["faithfulness"]["value"], "", item["faithfulness"]["supported"], item["faithfulness"]["claims"]) for item in cases],
                    n_boot, seed, legs_left=legs_left),
            },
            "retrieval": {
                "context_precision": _block(
                    [_pack(item["context_precision"]["value"], "", item["context_precision"]["k"], item["context_precision"]["n"]) for item in cases],
                    n_boot, seed),
                "context_recall": _block(
                    [_pack(item["context_recall"]["value"], "", item["context_recall"]["k"], item["context_recall"]["n"]) for item in cases],
                    n_boot, seed),
            },
        }
    names = ("context_recall", "context_precision", "faithfulness", "answer_relevancy")
    ab = {}
    for name in names:
        ab[name] = _paired_block(_values(scored["a"], name), _values(scored["b"], name), n_boot, seed)
    bars = config["bars"]
    recall = ab["context_recall"]
    faith = ab["faithfulness"]
    recall_holds = recall_bar_holds(recall["lo"], recall["paired"], bars["recall_lo_above"])
    faith_holds = faithfulness_bar_holds(faith["lo"], faith["paired"], bars["faithfulness_lo_at_least"])
    both = only_a = only_b = neither = 0
    for row in rows:
        match_a = _outcome_matches(row, records["a"][row["case_id"]])
        match_b = _outcome_matches(row, records["b"][row["case_id"]])
        if match_a and match_b:
            both += 1
        elif match_a:
            only_a += 1
        elif match_b:
            only_b += 1
        else:
            neither += 1
    outcome_holds, diff = outcome_bar_holds(
        both, only_a, only_b, neither, bars["outcome_fall_hi_at_most"])
    if diff is None:
        outcome = {
            "a": both, "b": only_a, "c": only_b, "d": neither,
            "fall": None, "hi": None, "lo": None, "paired": 0, "left": len(rows),
        }
    else:
        outcome = {
            "a": both, "b": only_a, "c": only_b, "d": neither,
            "fall": diff[0], "hi": diff[2], "lo": diff[1],
            "paired": both + only_a + only_b + neither, "left": 0,
        }
    ab["context_recall"]["bar"] = {
        "holds": recall_holds, "threshold": bars["recall_lo_above"], "value": recall["lo"],
    }
    ab["faithfulness"]["bar"] = {
        "holds": faith_holds, "threshold": bars["faithfulness_lo_at_least"], "value": faith["lo"],
    }
    ab["outcome"] = outcome
    ab["outcome"]["bar"] = {
        "holds": outcome_holds,
        "threshold": bars["outcome_fall_hi_at_most"],
        "value": None if diff is None else diff[2],
    }
    verdict = VERDICT_SHIP if recall_holds and faith_holds and outcome_holds else VERDICT_NO_SHIP
    groundedness = []
    for index, row in enumerate(rows):
        case = scored["a"][index]
        if not _outcome_matches(row, records["a"][row["case_id"]]):
            continue
        if not (_below_one(case["context_recall"]["value"]) or _below_one(case["faithfulness"]["value"])):
            continue
        tool_calls = records["a"][row["case_id"]].get("tool_calls")
        if isinstance(tool_calls, bool) or not isinstance(tool_calls, int):
            tool_calls = 0
        groundedness.append({
            "answer_relevancy": case["answer_relevancy"]["value"],
            "case_id": row["case_id"],
            "context_precision": case["context_precision"]["value"],
            "context_recall": case["context_recall"]["value"],
            "faithfulness": case["faithfulness"]["value"],
            "tool_calls": tool_calls,
        })
    langsmith = config["langsmith_version"]
    experiments = config["braintrust_experiments"]
    document = {
        "ab": ab,
        "braintrust_experiments": experiments,
        "commands": [line % label for line in _COMMANDS],
        "dataset": {
            "n": len(rows),
            "sha256": config["dataset_sha256"],
        },
        "groundedness": groundedness,
        "langsmith_version": langsmith,
        "runs": {
            "model": config["model"],
            "model_digest": metas["a"]["model_digest"],
            "ollama_version": metas["a"]["ollama_version"],
            "variants": {
                "a": _variant_flags(metas["a"], config["runs"]["a"]),
                "b": _variant_flags(metas["b"], config["runs"]["b"]),
            },
        },
        "variants": variants,
        "verdict": verdict,
        "weaker_half": {
            variant: _weaker(
                _half_average(
                    variants[variant]["retrieval"]["context_recall"]["mean"],
                    variants[variant]["retrieval"]["context_precision"]["mean"],
                ),
                _half_average(
                    variants[variant]["generation"]["faithfulness"]["mean"],
                    variants[variant]["generation"]["answer_relevancy"]["mean"],
                ),
            )
            for variant in _VARIANT_KEYS
        },
    }
    return _markdown(statement, document), canonical_json(document)


_TABLE_HEADER = "| scorer | mean | scored | none | interval | k of n |"
_TABLE_RULE = "| --- | --- | --- | --- | --- | --- |"


def _table_row(name, block):
    """One scorer row. Faithfulness keeps the legs-left count on the same row."""
    interval = "none"
    if block["lo"] is not None:
        interval = "[%s, %s]" % (_fmt(block["lo"]), _fmt(block["hi"]))
    left, right = {
        "context_recall": ("found", "needed"),
        "context_precision": ("relevant", "retrieved"),
        "faithfulness": ("supported", "claims"),
        "answer_relevancy": ("held", "tests"),
    }[name]
    detail = "%s %s of %s %s" % (left, _count(block["k"]), _count(block["n"]), right)
    if "legs_left" in block:
        detail += " legs left %s" % _count(block["legs_left"])
    return "| %s | %s | %s | %s | %s | %s |" % (
        name, _fmt(block["mean"]), _count(block["scored"]), _count(block["none"]),
        interval, detail,
    )


def _bar_phrase(kind, bar):
    if bar["value"] is None:
        if kind == "outcome":
            return "paired difference is none: no"
        return "no pairs: no"
    word = "yes" if bar["holds"] else "no"
    if kind == "recall":
        return "lower bound %s above %s: %s" % (_fmt(bar["value"]), _fmt(bar["threshold"]), word)
    if kind == "faithfulness":
        return "lower bound %s at least %s: %s" % (_fmt(bar["value"]), _fmt(bar["threshold"]), word)
    return "upper bound %s at most %s: %s" % (_fmt(bar["value"]), _fmt(bar["threshold"]), word)


def _markdown(statement, document):
    lines = ["# RAG report", ""]
    data = document["dataset"]
    lines.append("## Dataset")
    lines.append("")
    lines.append("n: %s" % _count(data["n"]))
    lines.append("sha256: %s" % data["sha256"])
    langsmith = document["langsmith_version"]
    if langsmith is None:
        lines.append("langsmith: not pinned yet")
    else:
        lines.append("langsmith dataset_id %s as_of %s" % (langsmith["dataset_id"], langsmith["as_of"]))
    lines.append("")
    for variant in _VARIANT_KEYS:
        lines.append("## Variant %s" % variant)
        lines.append("")
        lines.append("### Retrieval")
        lines.append("")
        lines.append(_TABLE_HEADER)
        lines.append(_TABLE_RULE)
        retrieval = document["variants"][variant]["retrieval"]
        lines.append(_table_row("context_recall", retrieval["context_recall"]))
        lines.append(_table_row("context_precision", retrieval["context_precision"]))
        lines.append("")
        lines.append("### Generation")
        lines.append("")
        lines.append(_TABLE_HEADER)
        lines.append(_TABLE_RULE)
        generation = document["variants"][variant]["generation"]
        lines.append(_table_row("faithfulness", generation["faithfulness"]))
        lines.append(_table_row("answer_relevancy", generation["answer_relevancy"]))
        lines.append("")
    lines.append("## Weaker half")
    lines.append("")
    for variant in _VARIANT_KEYS:
        lines.append("variant %s: %s" % (variant, document["weaker_half"][variant]["reason"]))
    lines.append("")
    lines.append("## A/B")
    lines.append("")
    for name in ("context_recall", "context_precision", "faithfulness", "answer_relevancy"):
        block = document["ab"][name]
        if block["lo"] is None:
            interval = "none"
        else:
            interval = "[%s, %s]" % (_fmt(block["lo"]), _fmt(block["hi"]))
        lines.append("%s delta %s interval %s paired %s left %s" % (
            name, _fmt(block["mean_delta"]), interval,
            _count(block["paired"]), _count(block["left"]),
        ))
    outcome = document["ab"]["outcome"]
    lines.append("outcome fall %s interval [%s, %s] paired %s left %s a %s b %s c %s d %s" % (
        _fmt(outcome["fall"]), _fmt(outcome["lo"]), _fmt(outcome["hi"]),
        _count(outcome["paired"]), _count(outcome["left"]),
        _count(outcome["a"]), _count(outcome["b"]), _count(outcome["c"]), _count(outcome["d"]),
    ))
    lines.append("recall: %s" % _bar_phrase("recall", document["ab"]["context_recall"]["bar"]))
    lines.append("faithfulness: %s" % _bar_phrase("faithfulness", document["ab"]["faithfulness"]["bar"]))
    lines.append("outcome: %s" % _bar_phrase("outcome", outcome["bar"]))
    lines.append("verdict: %s" % document["verdict"])
    lines.append("")
    lines.append("## Groundedness candidates")
    lines.append("")
    if not document["groundedness"]:
        lines.append("none")
    for row in document["groundedness"]:
        lines.append("%s recall %s precision %s faithfulness %s relevancy %s tool_calls %s" % (
            row["case_id"], _fmt(row["context_recall"]), _fmt(row["context_precision"]),
            _fmt(row["faithfulness"]), _fmt(row["answer_relevancy"]), _count(row["tool_calls"]),
        ))
    lines.append("")
    lines.append("## Runs")
    lines.append("")
    runs = document["runs"]
    lines.append("model: %s" % runs["model"])
    lines.append("model_digest: %s" % runs["model_digest"])
    lines.append("ollama_version: %s" % runs["ollama_version"])
    for variant in _VARIANT_KEYS:
        flags = runs["variants"][variant]
        parts = ["variant %s" % variant]
        for key in sorted(flags):
            parts.append("%s %s" % (key, flags[key]))
        lines.append(" ".join(parts))
    experiments = document["braintrust_experiments"]
    if experiments is None:
        lines.append("braintrust: not pinned yet")
    else:
        lines.append("braintrust a %s b %s" % (experiments["a"], experiments["b"]))
    lines.append("")
    lines.append("## Commands")
    lines.append("")
    for command in document["commands"]:
        lines.append(command)
    lines.append("")
    body = "\n".join(lines)
    if statement.endswith("\n"):
        return statement + "\n" + body
    return statement + "\n\n" + body


def _emit(path, text):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass


def report_files_hold(root=None):
    """True when a missing run has no report, and a present pair matches this command.

    While either variant's run directory is absent, the config's report and json
    must be absent. Once both are present, those files must equal this report.
    """
    base = ROOT if root is None else root
    config_path = os.path.join(base, DEFAULT_CONFIG)
    try:
        config = load_config(config_path)
    except ConfigError:
        return False
    report_path = os.path.join(base, config["report"])
    json_path = os.path.join(base, config["json"])
    run_a = os.path.join(base, "traces", config["runs"]["a"])
    run_b = os.path.join(base, "traces", config["runs"]["b"])
    if not (os.path.isdir(run_a) and os.path.isdir(run_b)):
        return not os.path.exists(report_path) and not os.path.exists(json_path)
    try:
        text, body = prepare_report(config, base, config_path)
    except ReportError:
        return False
    if not os.path.isfile(report_path) or not os.path.isfile(json_path):
        return False
    return _read_bytes(report_path) == text.encode("utf-8") and _read_bytes(json_path) == body.encode("utf-8")


def _config_path(args):
    if args.config:
        return args.config
    return os.path.join(args.root, DEFAULT_CONFIG)


def cmd_run(args):
    try:
        config = load_config(_config_path(args))
    except ConfigError as error:
        sys.stderr.write("%s\n" % error)
        return 2
    if args.variant not in _VARIANT_KEYS:
        sys.stderr.write("variant must be a or b\n")
        return 2
    reason = _refuse_dataset(args.root, config)
    if reason:
        sys.stderr.write("%s\n" % reason)
        return 2
    run_dir = os.path.join(args.root, "traces", config["runs"][args.variant])
    if os.path.exists(run_dir):
        sys.stderr.write("run already exists\n")
        return 2
    # run_eval opens its cases path from the working directory, so it gets the
    # path of the file whose bytes were just checked, not a path relative to
    # wherever this command was started. From the repository root run_eval
    # still records cases_file as data/golden/v1.jsonl, which report compares.
    argv = [
        os.path.join(args.root, config["dataset"]),
        "--run-id", config["runs"][args.variant],
        "--model", config["model"],
        "--rule-match", config["variants"][args.variant]["rule_match"],
    ]
    return run_eval.main(argv)


def cmd_report(args):
    config_path = _config_path(args)
    try:
        config = load_config(config_path)
        text, body = prepare_report(config, args.root, config_path)
    except (ConfigError, ReportError) as error:
        sys.stderr.write("%s\n" % error)
        return 2
    _emit(os.path.join(args.root, config["report"]), text)
    _emit(os.path.join(args.root, config["json"]), body)
    return 0


def _build_parser():
    parser = argparse.ArgumentParser(prog="scorer.rag")
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run")
    run.add_argument("--config", default=None)
    run.add_argument("--variant", default=None)
    run.add_argument("--root", default=ROOT)
    report = sub.add_parser("report")
    report.add_argument("--config", default=None)
    report.add_argument("--root", default=ROOT)
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return 2
    if args.command == "run":
        return cmd_run(args)
    return cmd_report(args)


if __name__ == "__main__":
    sys.exit(main())
