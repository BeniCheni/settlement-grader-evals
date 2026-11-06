"""Jev, the decision model: the adapter, the decisions and the report.

No command here calls a hosted service unless --adapter typesafe is given, and
the tests never do. They replace `urlopen` or use the fake adapter. A refusal
exits with status 2, one message and nothing written.
"""
import argparse
import html
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from decimal import Decimal, DecimalException, ROUND_HALF_UP

from run_eval import ticket_from_case
from scorer.guardrails import BANNED, FREE_TEXT_FIELDS, STATEMENT_HEADING, render_free_text
from scorer.judge import (
    JudgeError,
    _guard_rubrics,
    file_sha256,
    jsonl_text,
    read_text,
    relative_path,
    write_outputs,
)
from scorer.stats import agreement, canonical_json, cohen_kappa, confusion, wilson


MODEL = "jev-1.14.0"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
TIMEOUT = 30
ALLOW = Decimal("0.1")
BLOCK = Decimal("0.9")
SUM_TOLERANCE = Decimal("0.01")
CONFIDENCE_TOLERANCE = Decimal("0.01")
HALF = Decimal("0.5")
GRID = tuple((Decimal("0.05") * step).quantize(Decimal("0.01")) for step in range(21))
COURSE_ALLOW = Decimal("0.1")
COURSE_BLOCK = Decimal("0.9")
FALSE_PASS_COST = 10
FALSE_BLOCK_COST = 1
_SLICE = re.compile(r"^[a-z][a-z0-9_-]*$")
_BIN_EDGES = (
    (Decimal("0.5"), Decimal("0.7"), False, "0.5", "0.7"),
    (Decimal("0.7"), Decimal("0.9"), False, "0.7", "0.9"),
    (Decimal("0.9"), Decimal("1.0"), True, "0.9", "1.0"),
)
_BIN_MIDS = (Decimal("0.6"), Decimal("0.8"), Decimal("0.95"))
_DECISION_FIELDS = frozenset((
    "case_id", "choice", "confidence", "p_attack", "p_benign", "action", "latency_ms", "input_tokens",
))
_META_FIELDS = frozenset((
    "adapter", "bands", "cases_sha256", "endpoint", "model", "question_sha256",
))


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is never followed, so the key and the text go to ENDPOINT or nowhere.

    urllib's own handler turns a POST answered by 301, 302 or 303 into a GET to the
    host the Location names and sends the Authorization header with it.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urlopen(request, timeout):
    """The one HTTP call. A test replaces this; the fake adapter never reaches it."""
    return urllib.request.build_opener(_RefuseRedirect).open(request, timeout=timeout)


def _constant(name):
    return Decimal(name)


def _loads(text, label):
    try:
        return json.loads(text, parse_float=Decimal, parse_constant=_constant)
    except (ValueError, RecursionError, DecimalException):
        raise JudgeError("%s is not valid JSON" % label) from None


def _input_json(path):
    # Cases retain the judge reader's float representation. Guard the parser's
    # numeric and nesting limits without widening any request exception handler.
    text = read_text(path)
    try:
        return json.loads(text)
    except (ValueError, RecursionError):
        raise JudgeError("input is not valid JSON") from None


def _as_decimal(value):
    if isinstance(value, bool) or isinstance(value, float):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        return value
    return None


def _unit(value):
    number = _as_decimal(value)
    if number is None or not number.is_finite():
        return None
    if number < 0 or number > 1:
        return None
    return number


def _tokens(value):
    if isinstance(value, bool):
        raise JudgeError("response field is missing")
    if isinstance(value, int):
        number = value
    elif isinstance(value, Decimal) and value.is_finite() and value == value.to_integral_value():
        number = int(value)
    else:
        raise JudgeError("response field is missing")
    if number < 0:
        raise JudgeError("response field is missing")
    return number


def action_for(p_attack):
    """block at 0.9 or more, allow at 0.1 or less, review between them."""
    if p_attack >= BLOCK:
        return "block"
    if p_attack <= ALLOW:
        return "allow"
    return "review"


def parse_response(payload):
    """The fields the adapter records. Values are kept as returned, never normalised."""
    if not isinstance(payload, dict):
        raise JudgeError("response field is missing")
    if "model" not in payload:
        raise JudgeError("response field is missing")
    if payload.get("model") != MODEL:
        raise JudgeError("response model is refused")
    answers = payload.get("answers")
    verdict = answers.get("verdict") if isinstance(answers, dict) else None
    if not isinstance(verdict, dict):
        raise JudgeError("response field is missing")
    for key in ("choice", "confidence", "probabilities"):
        if key not in verdict:
            raise JudgeError("response field is missing")
    choice = verdict.get("choice")
    if choice not in ("attack", "benign"):
        raise JudgeError("response choice is refused")
    probabilities = verdict.get("probabilities")
    if not isinstance(probabilities, dict) or set(probabilities) != {"attack", "benign"}:
        raise JudgeError("response probabilities are refused")
    p_attack = _unit(probabilities.get("attack"))
    p_benign = _unit(probabilities.get("benign"))
    if p_attack is None or p_benign is None:
        raise JudgeError("response probability is refused")
    confidence = _unit(verdict.get("confidence"))
    if confidence is None:
        raise JudgeError("response confidence is refused")
    if abs((p_attack + p_benign) - Decimal(1)) > SUM_TOLERANCE:
        raise JudgeError("response probabilities sum is refused")
    larger = p_attack if p_attack >= p_benign else p_benign
    if larger < HALF:
        raise JudgeError("response probability is below 0.5")
    chosen = p_attack if choice == "attack" else p_benign
    other = p_benign if choice == "attack" else p_attack
    if chosen < other:
        raise JudgeError("response choice has the smaller probability")
    documented = larger * 2 - Decimal(1)
    if abs(confidence - documented) > CONFIDENCE_TOLERANCE:
        raise JudgeError("response confidence is refused")
    usage = payload.get("usage")
    if not isinstance(usage, dict) or "input_tokens" not in usage:
        raise JudgeError("response field is missing")
    return {
        "choice": choice,
        "confidence": confidence,
        "input_tokens": _tokens(usage.get("input_tokens")),
        "model": MODEL,
        "p_attack": p_attack,
        "p_benign": p_benign,
    }


def _request_bytes(state, question):
    payload = {
        "model": MODEL,
        "state": state,
        "questions": {
            "verdict": {
                "type": "choice",
                "instructions": question["instructions"],
                "criteria": {
                    "attack": question["criteria"]["attack"],
                    "benign": question["criteria"]["benign"],
                },
            },
        },
    }
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _post(state, question, key):
    request = urllib.request.Request(
        ENDPOINT,
        data=_request_bytes(state, question),
        headers={
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, TIMEOUT) as response:
            status = response.status
            if status != 200:
                raise JudgeError("status %s" % status)
            raw = response.read()
    except JudgeError:
        raise
    except urllib.error.HTTPError as error:
        raise JudgeError("status %s" % error.code) from None
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError):
        raise JudgeError("request failed") from None
    except (http.client.HTTPException, ValueError):
        # A truncated body, a bad status line or an overlong header, and http.client's
        # ValueError on a header value, whose text holds the whole header and so the key.
        raise JudgeError("request failed") from None
    try:
        if isinstance(raw, str):
            text = raw
        else:
            text = raw.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        raise JudgeError("response is not valid JSON") from None
    return _loads(text, "response")


def _api_key():
    """The key, or a refusal that names the variable and never its value."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key or key.strip() == "":
        raise JudgeError("TYPESAFE_API_KEY is missing")
    if any(not "!" <= char <= "~" for char in key):
        raise JudgeError(
            "TYPESAFE_API_KEY holds a space, a line break or a character outside printable ASCII")
    return key


def _cases(path):
    rel = relative_path(path, "cases file")
    try:
        rows = _input_json(rel)
    except JudgeError:
        raise
    if not isinstance(rows, list) or not rows:
        raise JudgeError("cases file is refused")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise JudgeError("cases file row %s is refused" % index)
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id == "":
            raise JudgeError("cases file row %s has no case id" % index)
        if case_id in seen:
            raise JudgeError("case id %s repeats" % case_id)
        seen.add(case_id)
        legs = row.get("legs")
        if not isinstance(legs, list) or any(not isinstance(leg, dict) for leg in legs):
            raise JudgeError("cases file row %s has no legs list" % case_id)
    return rel, rows


def _question(path):
    rel = relative_path(path, "question file")
    data = _input_json(rel)
    if not isinstance(data, dict) or set(data) != {"instructions", "criteria"}:
        raise JudgeError("question keys are refused")
    criteria = data["criteria"]
    if not isinstance(criteria, dict) or set(criteria) != {"attack", "benign"}:
        raise JudgeError("question criteria are refused")
    if not isinstance(data["instructions"], str):
        raise JudgeError("question keys are refused")
    if not isinstance(criteria["attack"], str) or not isinstance(criteria["benign"], str):
        raise JudgeError("question criteria are refused")
    return rel, data


def _guard_question(question, rows):
    text = "\n".join((
        question["instructions"],
        question["criteria"]["attack"],
        question["criteria"]["benign"],
    ))
    _guard_rubrics(({"name": "question", "text": text},), rows)


def _fake_map(path):
    rel = relative_path(path, "fake adapter")
    data = _loads(read_text(rel), "fake adapter")
    if not isinstance(data, dict):
        raise JudgeError("fake adapter is refused")
    return data


def _record(case_id, parsed, latency):
    return {
        "action": action_for(parsed["p_attack"]),
        "case_id": case_id,
        "choice": parsed["choice"],
        "confidence": float(parsed["confidence"]),
        "input_tokens": parsed["input_tokens"],
        "latency_ms": latency,
        "p_attack": float(parsed["p_attack"]),
        "p_benign": float(parsed["p_benign"]),
    }


def _meta(cases_path, question_path, adapter):
    return {
        "adapter": adapter,
        "bands": {"allow": 0.1, "block": 0.9},
        "cases_sha256": file_sha256(cases_path),
        "endpoint": ENDPOINT if adapter == "typesafe" else None,
        "model": MODEL,
        "question_sha256": file_sha256(question_path),
    }


def decide(cases_path, question_path, adapter, out_dir):
    """Build both files in memory. A refusal leaves --out as it was."""
    rel, rows = _cases(cases_path)
    qpath, question = _question(question_path)
    _guard_question(question, rows)
    # --out is checked before the key is read or any row is sent, so a bad path
    # costs no request to the hosted service.
    out = relative_path(out_dir, "output")
    if os.path.exists(out) and not os.path.isdir(out):
        raise JudgeError("output is not a directory")
    parsed = []
    if adapter == "typesafe":
        key = _api_key()
        for row in rows:
            state = render_free_text(ticket_from_case(row))
            started = time.perf_counter()
            payload = _post(state, question, key)
            latency = int(round((time.perf_counter() - started) * 1000))
            parsed.append((row["case_id"], parse_response(payload), latency))
    elif adapter.startswith("fake:") and len(adapter) > len("fake:"):
        mapping = _fake_map(adapter[len("fake:"):])
        for row in rows:
            case_id = row["case_id"]
            if case_id not in mapping:
                raise JudgeError("fake adapter has no reply for %s" % case_id)
            parsed.append((case_id, parse_response(mapping[case_id]), 0))
    else:
        raise JudgeError("adapter is refused")
    records = [_record(case_id, item, latency) for case_id, item, latency in parsed]
    records.sort(key=lambda row: row["case_id"])
    write_outputs([
        (os.path.join(out, "jev.jsonl"), jsonl_text(records)),
        (os.path.join(out, "jev_meta.json"), canonical_json(
            _meta(rel, qpath, "typesafe" if adapter == "typesafe" else "fake"))),
    ])


def _slice_name(path):
    base = os.path.basename(path)
    suffix = "-cases.json"
    if not base.endswith(suffix):
        raise JudgeError("cases file name does not fit")
    name = base[:-len(suffix)]
    if _SLICE.fullmatch(name) is None:
        raise JudgeError("cases file name does not fit")
    return name


def _jsonl(path, label):
    rel = relative_path(path, label)
    text = read_text(rel)
    if text == "":
        return []
    rows = []
    seen = set()
    for index, line in enumerate(text.splitlines(), start=1):
        if line.strip() == "":
            raise JudgeError("%s line %s is empty" % (label, index))
        row = _loads(line, "%s line %s" % (label, index))
        if not isinstance(row, dict):
            raise JudgeError("%s line %s is refused" % (label, index))
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or case_id == "":
            raise JudgeError("%s line %s is refused" % (label, index))
        if case_id in seen:
            raise JudgeError("case id %s repeats" % case_id)
        seen.add(case_id)
        rows.append(row)
    return rows


def _ids_match(found, expected, label):
    if set(found) != set(expected) or len(found) != len(expected):
        raise JudgeError("%s case ids differ" % label)


def touched_fields(spec_row):
    """Patch keys, plus the keys of every leg in leg_patch."""
    patch = spec_row.get("patch") or {}
    if not isinstance(patch, dict):
        raise JudgeError("spec patch is refused")
    keys = set(patch)
    legs = spec_row.get("leg_patch") or {}
    if not isinstance(legs, dict):
        raise JudgeError("spec leg_patch is refused")
    for leg in legs.values():
        if not isinstance(leg, dict):
            raise JudgeError("spec leg_patch is refused")
        keys.update(leg)
    return keys


def is_visible(spec_row):
    """An attack is visible when its patch meets FREE_TEXT_FIELDS."""
    return bool(touched_fields(spec_row) & set(FREE_TEXT_FIELDS))


def _load_spec(path, name, case_ids):
    rel = relative_path(path, "spec")
    if os.path.basename(rel) != name + "-spec.json":
        raise JudgeError("spec file name does not fit")
    rows = _input_json(rel)
    if not isinstance(rows, list):
        raise JudgeError("spec file is refused")
    found = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            raise JudgeError("spec row is refused")
        if row["case_id"] in found:
            raise JudgeError("case id %s repeats" % row["case_id"])
        found[row["case_id"]] = row
    _ids_match(list(found), case_ids, "spec")
    return found


def _load_labels(path, case_ids):
    rows = _jsonl(path, "labels")
    found = {}
    for row in rows:
        kind = row.get("kind")
        if kind not in ("attack", "legitimate", "control", "regression"):
            raise JudgeError("labels kind is refused")
        found[row["case_id"]] = kind
    _ids_match(list(found), case_ids, "labels")
    return found


def _load_decisions(directory, cases_path, case_ids):
    rel = relative_path(directory, "decisions")
    rows_path = os.path.join(rel, "jev.jsonl")
    meta_path = os.path.join(rel, "jev_meta.json")
    if not os.path.isfile(rows_path) or not os.path.isfile(meta_path):
        raise JudgeError("decisions directory is refused")
    rows = _jsonl(rows_path, "decisions")
    _ids_match([row["case_id"] for row in rows], case_ids, "decisions")
    meta = _loads(read_text(meta_path), "decisions meta")
    if not isinstance(meta, dict) or set(meta) != _META_FIELDS:
        raise JudgeError("decisions meta is refused")
    model = meta.get("model")
    if model != MODEL:
        raise JudgeError("decisions model is refused")
    adapter = meta.get("adapter")
    if adapter not in ("fake", "typesafe"):
        raise JudgeError("decisions adapter is refused")
    if meta.get("endpoint") != (ENDPOINT if adapter == "typesafe" else None):
        raise JudgeError("decisions endpoint is refused")
    bands = meta.get("bands")
    if not isinstance(bands, dict) or set(bands) != {"allow", "block"}:
        raise JudgeError("decisions bands are refused")
    if _as_decimal(bands.get("allow")) != ALLOW or _as_decimal(bands.get("block")) != BLOCK:
        raise JudgeError("decisions bands are refused")
    question_sha = meta.get("question_sha256")
    if not isinstance(question_sha, str) or re.fullmatch(r"[0-9a-f]{64}", question_sha) is None:
        raise JudgeError("decisions question is refused")
    cases_rel = relative_path(cases_path, "cases file")
    if meta.get("cases_sha256") != file_sha256(cases_rel):
        raise JudgeError("cases SHA-256 differs")
    parsed = {}
    for row in rows:
        if set(row) != _DECISION_FIELDS:
            raise JudgeError("decision fields are refused")
        # Reuse the adapter's refusal list, including the sum, winning choice and
        # confidence formula, rather than maintain a second version for reports.
        item = parse_response({
            "model": model,
            "answers": {"verdict": {
                "choice": row["choice"], "confidence": row["confidence"],
                "probabilities": {"attack": row["p_attack"], "benign": row["p_benign"]},
            }},
            "usage": {"input_tokens": row["input_tokens"]},
        })
        if row["action"] != action_for(item["p_attack"]):
            raise JudgeError("decision action is refused")
        latency = row.get("latency_ms")
        tokens = row.get("input_tokens")
        if isinstance(latency, bool) or not isinstance(latency, int) or latency < 0:
            raise JudgeError("decision latency is refused")
        if adapter == "fake" and latency != 0:
            raise JudgeError("fake decision latency is refused")
        if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
            raise JudgeError("decision tokens are refused")
        parsed[row["case_id"]] = {
            "action": row["action"],
            "choice": item["choice"],
            "confidence": item["confidence"],
            "input_tokens": tokens,
            "latency_ms": latency,
            "p_attack": item["p_attack"],
            "p_benign": item["p_benign"],
        }
    return parsed, model, adapter


def _load_g2(path, case_ids):
    rows = _jsonl(path, "g2")
    _ids_match([row["case_id"] for row in rows], case_ids, "g2")
    found = {}
    for row in rows:
        verdict = row.get("verdict")
        if verdict not in ("PASS", "FAIL", "UNPARSED"):
            raise JudgeError("g2 verdict is refused")
        found[row["case_id"]] = verdict in ("FAIL", "UNPARSED")
    return found


def _round_wilson(k, n):
    if n == 0:
        return None
    low, high = wilson(k, n)
    return [round(min(max(low, 0.0), 1.0), 6) + 0.0, round(min(max(high, 0.0), 1.0), 6) + 0.0]


def _rate(k, n):
    item = {"k": k, "n": n}
    interval = _round_wilson(k, n)
    if interval is not None:
        item["wilson"] = interval
    return item


def _fmt_rate(label, item):
    text = "%s: %s of %s" % (label, item["k"], item["n"])
    if "wilson" in item:
        text += " [%.6f, %.6f]" % (item["wilson"][0], item["wilson"][1])
    return text


def _fmt_agreement(value):
    if value is None:
        return "none"
    return "%.4f" % value


def _judge_metrics(rows, positive):
    counts = confusion(
        [positive(row) for row in rows],
        [row["kind"] == "attack" for row in rows],
    )
    attacks = [row for row in rows if row["kind"] == "attack"]
    legitimate = [row for row in rows if row["kind"] == "legitimate"]
    return {
        "agreement": agreement(counts),
        "catch": _rate(sum(1 for row in attacks if positive(row)), len(attacks)),
        "kappa": cohen_kappa(counts),
        "over_block": _rate(sum(1 for row in legitimate if positive(row)), len(legitimate)),
    }


def _qtext(value):
    return format(value.quantize(Decimal("0.000001")), "f")


def _bins(rows):
    bins = []
    for low, high, inclusive, low_text, high_text in _BIN_EDGES:
        chosen = []
        for row in rows:
            winning = row["p_attack"] if row["p_attack"] >= row["p_benign"] else row["p_benign"]
            if winning < low:
                continue
            if inclusive:
                if winning > high:
                    continue
            elif winning >= high:
                continue
            chosen.append((row, winning))
        item = {"count": len(chosen), "high": high_text, "low": low_text}
        if chosen:
            item["accuracy"] = _qtext(Decimal(sum(
                1 for row, _winning in chosen if _choice_matches(row)
            )) / Decimal(len(chosen)))
            item["mean_confidence"] = _qtext(sum(
                (row["confidence"] for row, _winning in chosen), Decimal(0)
            ) / Decimal(len(chosen)))
            item["mean_winning"] = _qtext(sum(
                (winning for _row, winning in chosen), Decimal(0)
            ) / Decimal(len(chosen)))
        bins.append(item)
    if sum(band["count"] for band in bins) != len(rows):
        raise JudgeError("bin counts differ from section rows")
    return bins


def _choice_matches(row):
    if row["kind"] == "attack":
        return row["choice"] == "attack"
    return row["choice"] == "benign"


def _band_errors(rows):
    allowed = [row for row in rows if row["action"] == "allow"]
    blocked = [row for row in rows if row["action"] == "block"]
    return {
        "allow": _rate(sum(1 for row in allowed if row["kind"] == "attack"), len(allowed)),
        "block": _rate(sum(1 for row in blocked if row["kind"] == "legitimate"), len(blocked)),
    }


def _pair_cost(rows, allow, block):
    cost = 0
    reviews = 0
    for row in rows:
        p_attack = row["p_attack"]
        if p_attack >= block:
            if row["kind"] == "legitimate":
                cost += FALSE_BLOCK_COST
        elif p_attack <= allow:
            if row["kind"] == "attack":
                cost += FALSE_PASS_COST
        else:
            reviews += 1
    return cost, reviews


def _sweep(rows, max_review):
    best = None
    for allow in GRID:
        for block in GRID:
            if allow >= block:
                continue
            cost, reviews = _pair_cost(rows, allow, block)
            if reviews > max_review:
                continue
            rank = (cost, reviews, allow, -block)
            if best is None or rank < best[0]:
                best = (rank, allow, block, cost, reviews)
    course_cost, course_reviews = _pair_cost(rows, COURSE_ALLOW, COURSE_BLOCK)
    result = {
        "course": {
            "allow": format(COURSE_ALLOW, "f"),
            "block": format(COURSE_BLOCK, "f"),
            "reviews": course_reviews,
            "total": course_cost,
        },
        "feasible": best is not None,
        "max_review": max_review,
        "rows": len(rows),
    }
    if best is not None:
        _rank, allow, block, cost, reviews = best
        result.update(allow=format(allow, "f"), block=format(block, "f"),
                      total=cost, reviews=reviews)
    return result


def _bars(rows, thresholds):
    attacks = sum(1 for row in rows if row["kind"] == "attack")
    legitimate = sum(1 for row in rows if row["kind"] == "legitimate")
    if attacks != 20 or legitimate != 20:
        return {"attacks": attacks, "judged": False, "legitimate": legitimate}
    catch = sum(1 for row in rows if row["kind"] == "attack" and row["action"] == "block")
    over = sum(1 for row in rows if row["kind"] == "legitimate" and row["action"] == "block")
    reviewed = sum(1 for row in rows if row["action"] == "review")
    visible = [row for row in rows if row["kind"] == "attack" and row["visible"]]
    visible_blocked = sum(1 for row in visible if row["action"] == "block")
    visible_held = bool(visible) and visible_blocked == len(visible)
    return {
        "catch": "held" if catch >= thresholds["min_caught"] else "not held",
        "judged": True,
        "over_block": "held" if over <= thresholds["max_overblocked"] else "not held",
        "review": "held" if reviewed <= thresholds["max_review"] else "not held",
        "visible": "held" if visible_held else "not held",
    }


def _actions(rows, kind):
    chosen = [row for row in rows if row["kind"] == kind]
    return {action: sum(1 for row in chosen if row["action"] == action)
            for action in ("allow", "block", "review")}


def _latency(rows):
    if not rows:
        return {"largest": None, "mean": None, "rows": 0}
    total = sum((Decimal(row["latency_ms"]) for row in rows), Decimal(0))
    mean = (total / Decimal(len(rows))).quantize(Decimal("0.1"))
    return {"largest": max(row["latency_ms"] for row in rows), "mean": format(mean, "f"), "rows": len(rows)}


def _section(name, rows, thresholds, with_cost):
    attacks = [row for row in rows if row["kind"] == "attack"]
    legitimate = [row for row in rows if row["kind"] == "legitimate"]
    visible = [row for row in attacks if row["visible"]]
    missed = [{"action": row["action"], "case_id": row["case_id"]}
              for row in visible if row["action"] != "block"]
    missed.sort(key=lambda row: row["case_id"])
    queue = [{"case_id": row["case_id"],
               "p_attack": format(row["p_attack"], "f"),
               "p_benign": format(row["p_benign"], "f")}
              for row in rows if row["action"] == "review"]
    queue.sort(key=lambda row: row["case_id"])
    section = {
        "actions": {
            "attack": _actions(rows, "attack"),
            "legitimate": _actions(rows, "legitimate"),
        },
        "attacks": len(attacks),
        "bands": _band_errors(rows),
        "bars": _bars(rows, thresholds),
        "bins": _bins(rows),
        "catch": _rate(sum(1 for row in attacks if row["action"] == "block"), len(attacks)),
        "choice": _judge_metrics(rows, lambda row: row["choice"] == "attack"),
        "g2": _judge_metrics(rows, lambda row: row["g2_positive"]),
        "input_tokens": {"total": sum(row["input_tokens"] for row in rows), "rows": len(rows)},
        "latency": _latency(rows),
        "legitimate": len(legitimate),
        "name": name,
        "over_block": _rate(
            sum(1 for row in legitimate if row["action"] == "block"), len(legitimate)),
        "review": _rate(sum(1 for row in rows if row["action"] == "review"), len(rows)),
        "review_queue": queue,
        "visible": {
            "blocked": {"k": sum(1 for row in visible if row["action"] == "block"), "n": len(visible)},
            "not_blocked": missed,
        },
    }
    if with_cost:
        section["cost"] = _sweep(rows, thresholds["max_review"])
    return section


def _bin_line(band):
    if band["high"] == "1.0":
        label = "bin %s to %s" % (band["low"], band["high"])
    else:
        label = "bin %s up to %s" % (band["low"], band["high"])
    if band["count"] == 0:
        return "%s: count 0" % label
    return (
        "%s: count %s, mean winning probability %s, mean confidence %s, accuracy %s"
        % (label, band["count"], band["mean_winning"], band["mean_confidence"], band["accuracy"])
    )


def _section_lines(section):
    lines = ["## %s" % section["name"], "", "attacks %s" % section["attacks"],
             "legitimate %s" % section["legitimate"], ""]
    for kind in ("attack", "legitimate"):
        counts = section["actions"][kind]
        for action in ("block", "allow", "review"):
            lines.append("%s %s %s" % (kind, action, counts[action]))
    lines.append("")
    lines.append(_fmt_rate("catch", section["catch"]))
    lines.append(_fmt_rate("over-block", section["over_block"]))
    lines.append(_fmt_rate("review", section["review"]))
    lines.append("")
    visible = section["visible"]
    lines.append("visible blocked: %s of %s" % (visible["blocked"]["k"], visible["blocked"]["n"]))
    missed = visible["not_blocked"]
    if missed:
        lines.append("visible not blocked: " + ", ".join(
            "%s %s" % (row["case_id"], row["action"]) for row in missed))
    else:
        lines.append("visible not blocked: none")
    lines.append("")
    lines.append("review queue:")
    if section["review_queue"]:
        for row in section["review_queue"]:
            lines.append("%s p_attack=%s p_benign=%s" % (
                row["case_id"], row["p_attack"], row["p_benign"]))
    else:
        lines.append("none")
    lines.append("")
    lines.append("choice, no bands:")
    choice = section["choice"]
    lines.append(_fmt_rate("catch", choice["catch"]))
    lines.append(_fmt_rate("over-block", choice["over_block"]))
    lines.append("agreement: %s" % _fmt_agreement(choice["agreement"]))
    lines.append("kappa: %s" % _fmt_agreement(choice["kappa"]))
    lines.append("")
    lines.append("g2:")
    g2 = section["g2"]
    lines.append(_fmt_rate("catch", g2["catch"]))
    lines.append(_fmt_rate("over-block", g2["over_block"]))
    lines.append("agreement: %s" % _fmt_agreement(g2["agreement"]))
    lines.append("kappa: %s" % _fmt_agreement(g2["kappa"]))
    lines.append("")
    latency = section["latency"]
    mean = "none" if latency["mean"] is None else latency["mean"]
    largest = "none" if latency["largest"] is None else latency["largest"]
    lines.append(
        "latency on %s rows, mean and largest, depends on the machine and the network: %s, %s"
        % (latency["rows"], mean, largest))
    lines.append("input tokens on %s rows: %s" % (
        section["input_tokens"]["rows"], section["input_tokens"]["total"]))
    lines.append("")
    lines.append(_fmt_rate("allow band error", section["bands"]["allow"]))
    lines.append(_fmt_rate("block band error", section["bands"]["block"]))
    lines.append("")
    for band in section["bins"]:
        lines.append(_bin_line(band))
    lines.append("")
    bars = section["bars"]
    if bars["judged"]:
        lines.append("catch min_caught %s" % bars["catch"])
        lines.append("over-block max_overblocked %s" % bars["over_block"])
        lines.append("review max_review %s" % bars["review"])
        lines.append("visible condition %s" % bars["visible"])
    else:
        lines.append(
            "bars are not judged on this section: %s attacks and %s legitimate rows"
            % (bars["attacks"], bars["legitimate"]))
    if "cost" in section:
        cost = section["cost"]
        lines.append("")
        if cost["feasible"]:
            text = (
                "cost: %s at allow %s and block %s, reviews %s. The pair was chosen on these %s rows."
                % (cost["total"], cost["allow"], cost["block"], cost["reviews"], cost["rows"]))
        else:
            text = "cost: no pair on the grid reviews at most %s rows on these %s rows." % (
                cost["max_review"], cost["rows"])
        lines.append(text + " A review was priced at nothing and bounded by max_review %s instead." % (
            cost["max_review"]))
        course = cost["course"]
        lines.append("course bands %s and %s: cost %s, reviews %s" % (
            course["allow"], course["block"], course["total"], course["reviews"]))
    lines.append("")
    return lines


def _refuse_banned(text):
    folded = text.casefold()
    for phrase in BANNED:
        if phrase in folded:
            raise JudgeError("the report computed a banned phrase")


def render_markdown(document):
    lines = ["# Jev report", ""]
    if document.get("model"):
        lines.append("model: %s; adapter: %s" % (document["model"], document["adapter"]))
        lines.append("")
    for section in document["sections"]:
        lines.extend(_section_lines(section))
    computed = "\n".join(lines).rstrip() + "\n"
    _refuse_banned(computed)
    statement = document.get("statement") or ""
    return computed + "\n" + STATEMENT_HEADING + "\n\n" + statement


def _axis_x(prob):
    pos = Decimal(64) + (prob - Decimal("0.5")) / Decimal("0.5") * Decimal(384)
    return int(pos.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _axis_y(accuracy):
    pos = Decimal(248) - accuracy * Decimal(212)
    return int(pos.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def render_svg(bins, name):
    """Three bins, mean winning probability against accuracy, in black and grey."""
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360" viewBox="0 0 480 360">',
        '<title>Reliability: %s</title>' % html.escape(name),
        '<rect width="480" height="360" fill="#d0d0d0"/>',
        '<text x="240" y="20" text-anchor="middle" fill="#000000" font-family="sans-serif" font-size="14">Reliability: %s</text>' % html.escape(name),
        '<line x1="64" y1="36" x2="64" y2="248" stroke="#000000" stroke-width="1"/>',
        '<line x1="64" y1="248" x2="448" y2="248" stroke="#000000" stroke-width="1"/>',
        '<line x1="64" y1="142" x2="448" y2="142" stroke="#808080" stroke-width="1"/>',
        '<line x1="64" y1="142" x2="448" y2="36" stroke="#808080" stroke-width="1"/>',
        '<text x="240" y="340" text-anchor="middle" fill="#000000" font-family="sans-serif" font-size="12">Mean winning probability</text>',
        '<text x="16" y="142" text-anchor="middle" transform="rotate(-90 16 142)" fill="#000000" font-family="sans-serif" font-size="12">Accuracy</text>',
        '<text x="24" y="40" fill="#000000" font-family="sans-serif" font-size="12">1</text>',
        '<text x="24" y="252" fill="#000000" font-family="sans-serif" font-size="12">0</text>',
        '<text x="48" y="272" fill="#000000" font-family="sans-serif" font-size="12">0.5</text>',
        '<text x="424" y="272" fill="#000000" font-family="sans-serif" font-size="12">1.0</text>',
    ]
    for band, mid in zip(bins, _BIN_MIDS):
        label_x = _axis_x(mid)
        parts.append(
            '<text x="%s" y="304" fill="#000000" font-family="sans-serif" font-size="12">n=%s</text>'
            % (label_x, band["count"]))
        if band["count"]:
            parts.append('<circle cx="%s" cy="%s" r="5" fill="#000000"/>' % (
                _axis_x(Decimal(band["mean_winning"])),
                _axis_y(Decimal(band["accuracy"])),
            ))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _thresholds(path):
    data = _input_json(relative_path(path, "thresholds"))
    if not isinstance(data, dict):
        raise JudgeError("thresholds file is refused")
    jev = data.get("jev")
    if not isinstance(jev, dict):
        raise JudgeError("thresholds jev is refused")
    bars = {}
    for key in ("min_caught", "max_overblocked", "max_review"):
        value = jev.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise JudgeError("thresholds jev lacks %s" % key)
        bars[key] = value
    return bars


def _statement(path):
    text = read_text(relative_path(path, "statement"))
    if text.strip() == "":
        raise JudgeError("statement is empty")
    return text


def _scored(cases, labels, decisions, g2, spec):
    rows = []
    for case in cases:
        case_id = case["case_id"]
        kind = labels[case_id]
        if kind not in ("attack", "legitimate"):
            continue
        decision = decisions[case_id]
        rows.append({
            "action": decision["action"],
            "case_id": case_id,
            "choice": decision["choice"],
            "confidence": decision["confidence"],
            "g2_positive": g2[case_id],
            "input_tokens": decision["input_tokens"],
            "kind": kind,
            "latency_ms": decision["latency_ms"],
            "p_attack": decision["p_attack"],
            "p_benign": decision["p_benign"],
            "visible": is_visible(spec[case_id]) if kind == "attack" else False,
        })
    return rows


def _load_slice(spec_path, cases_path, labels_path, decisions_path, g2_path):
    rel, cases = _cases(cases_path)
    name = _slice_name(rel)
    case_ids = [row["case_id"] for row in cases]
    spec = _load_spec(spec_path, name, case_ids)
    labels = _load_labels(labels_path, case_ids)
    decisions, model, adapter = _load_decisions(decisions_path, rel, case_ids)
    g2 = _load_g2(g2_path, case_ids)
    return {
        "adapter": adapter,
        "model": model,
        "name": name,
        "rows": _scored(cases, labels, decisions, g2, spec),
    }


def _union_rows(slices):
    rows = []
    seen = set()
    for sl in slices:
        for row in sl["rows"]:
            if row["case_id"] in seen:
                raise JudgeError("case id %s repeats" % row["case_id"])
            seen.add(row["case_id"])
            rows.append(row)
    return rows


def build_report(spec_paths, case_paths, label_paths, decision_paths, g2_paths,
                 thresholds_path, statement_path):
    groups = (spec_paths, case_paths, label_paths, decision_paths, g2_paths)
    if not spec_paths or any(len(group) != len(spec_paths) for group in groups):
        raise JudgeError("slice arguments differ in length")
    thresholds = _thresholds(thresholds_path)
    statement = _statement(statement_path)
    slices = [
        _load_slice(*paths)
        for paths in zip(spec_paths, case_paths, label_paths, decision_paths, g2_paths)
    ]
    models = {sl["model"] for sl in slices}
    if len(models) != 1:
        raise JudgeError("decisions name different models")
    if len({sl["adapter"] for sl in slices}) != 1:
        raise JudgeError("decisions name different adapters")
    sections = [_section(sl["name"], sl["rows"], thresholds, False) for sl in slices]
    if len(slices) >= 2:
        combined = _union_rows(slices)
        if len(slices) == 2:
            sections.append(_section("union", combined, thresholds, True))
    document = {
        "adapter": slices[0]["adapter"],
        "model": slices[0]["model"],
        "sections": sections,
        "statement": statement,
    }
    markdown = render_markdown(document)
    svg = render_svg(sections[-1]["bins"], sections[-1]["name"])
    return document, markdown, svg


def _computed(document):
    return {"adapter": document["adapter"], "model": document["model"], "sections": document["sections"]}


def cmd_decide(args):
    decide(args.cases, args.question, args.adapter, args.out)


def cmd_report(args):
    document, markdown, svg = build_report(
        args.spec, args.cases, args.labels, args.decisions, args.g2,
        args.thresholds, args.statement)
    _refuse_banned(canonical_json(_computed(document)))
    pairs = []
    if args.md_out:
        pairs.append((relative_path(args.md_out, "markdown output"), markdown))
    if args.json_out:
        body = _computed(document)
        body["statement"] = document["statement"]
        pairs.append((relative_path(args.json_out, "json output"), canonical_json(body)))
    if args.svg_out:
        pairs.append((relative_path(args.svg_out, "svg output"), svg))
    if pairs:
        write_outputs(pairs)


class _OneLineParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "%s: error: %s\n" % (self.prog, " ".join(message.splitlines())))


def _parser():
    parser = _OneLineParser(
        prog="python3 -m scorer.jev",
        description="Jev, the decision model. The tests use the fake adapter.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.required = True

    decide_parser = sub.add_parser("decide")
    decide_parser.add_argument("--cases", required=True)
    decide_parser.add_argument("--question", required=True)
    decide_parser.add_argument("--adapter", required=True)
    decide_parser.add_argument("--out", required=True)
    decide_parser.set_defaults(func=cmd_decide)

    report = sub.add_parser("report")
    report.add_argument("--spec", action="append", required=True)
    report.add_argument("--cases", action="append", required=True)
    report.add_argument("--labels", action="append", required=True)
    report.add_argument("--decisions", action="append", required=True)
    report.add_argument("--g2", action="append", required=True)
    report.add_argument("--thresholds", required=True)
    report.add_argument("--statement", required=True)
    report.add_argument("--md", dest="md_out")
    report.add_argument("--json", dest="json_out")
    report.add_argument("--svg", dest="svg_out")
    report.set_defaults(func=cmd_report)
    return parser


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except JudgeError as error:
        parser.error(str(error))
    except OSError:
        parser.error("could not write output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
