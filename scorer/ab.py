"""Judge two runs that have no human labels, and report each metric on its own row.

The statement file is the only sentence here about in sample or held out.
This module does not call a model except through the adapter run-ab is given.
"""
import difflib
import json
import math
import os
import shlex
import sys
from decimal import Decimal, ROUND_HALF_UP

from scorer.checks import CHECKS
from scorer.compare import CompareError, _canon, _check_cases, _load_meta, _load_records
from scorer.judge import (
    PROVENANCE_HEADING,
    FakeAdapter,
    JudgeError,
    _source,
    agreement_percent,
    build_adapter,
    collect_verdicts,
    jsonl_text,
    load_json,
    load_rubrics,
    read_text,
    relative_path,
    run_name,
    write_outputs,
    _load_verdicts,
)
from scorer.report import FONT_LINKS, _css_text, esc
from scorer.score import score_run
from scorer.stats import canonical_json, paired_difference
from scorer.calibrate import MissingCaseError


_ALLOWED_META = frozenset(("run_id", "outcome_matches", "system_prompt"))
_TOP_KEYS = frozenset(("code", "interval", "judge", "weakest_judge"))
_INTERVAL_KEYS = frozenset(("method", "z"))
_METHOD = "newcombe-1998-method-10"
_CODE_KEYS = {
    "must_fall": frozenset(("code", "interval_excludes_zero", "kind", "min_net_fall")),
    "max_rise": frozenset(("code", "kind", "max_rise")),
}
_JUDGE_KEYS = {
    "max_pass_fall": frozenset(("kind", "max_pass_fall", "rubric")),
    "report_only": frozenset(("kind", "rubric")),
}
_CELLS = ("JP_HP", "JP_HF", "JF_HP", "JF_HF")


def signed_points(numerator, denominator):
    """Percentage points to one decimal, with a sign. An exact half rounds away from zero."""
    sign = "-" if numerator < 0 else "+"
    scaled = abs(numerator) * 1000
    quot, rem = divmod(scaled, denominator)
    if rem * 2 >= denominator:
        quot += 1
    return "%s%d.%d" % (sign, quot // 10, quot % 10)


def signed_tickets(numerator):
    return "%+d" % numerator


def format_limit(proportion):
    """One decimal point from the float. -0.0 prints as 0.0. A half rounds away from zero."""
    if proportion == 0.0:
        return "0.0"
    points = (Decimal(str(proportion)) * Decimal(100)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    if points == 0:
        return "0.0"
    return format(points, "f")


def _same_value(left, right, key):
    if (key in left) != (key in right):
        return False
    if key not in left:
        return True
    return _canon(left[key]) == _canon(right[key])


def _need_setup(meta, name):
    if not isinstance(meta, dict):
        raise JudgeError("%s run_meta.json is missing" % name)
    for key in ("ollama_version", "model_digest"):
        value = meta.get(key)
        if not isinstance(value, str) or value.strip() == "":
            raise JudgeError("%s run_meta.json lacks %s" % (name, key))


def _prompt(meta, name):
    if "system_prompt" not in meta or not isinstance(meta.get("system_prompt"), str):
        raise JudgeError("%s run_meta.json lacks system_prompt" % name)
    return meta["system_prompt"]


def _records(name):
    try:
        return _load_records(name, name)
    except CompareError as error:
        raise JudgeError(str(error)) from None


def _meta(name):
    try:
        meta = _load_meta(name, name)
    except CompareError as error:
        raise JudgeError(str(error)) from None
    if meta is None:
        raise JudgeError("%s run_meta.json is missing" % name)
    return meta


def check_runs(path_a, path_b):
    """The refusals run-ab and ab share. Nothing here calls a model."""
    name_a = run_name(path_a)
    name_b = run_name(path_b)
    records_a = _records(name_a)
    records_b = _records(name_b)
    ids_a = [record["case_id"] for record in records_a]
    ids_b = [record["case_id"] for record in records_b]
    if set(ids_a) != set(ids_b):
        raise JudgeError("the runs do not hold the same case ids")
    meta_a = _meta(name_a)
    meta_b = _meta(name_b)
    _need_setup(meta_a, name_a)
    _need_setup(meta_b, name_b)
    differed = []
    for key in sorted((set(meta_a) | set(meta_b)) - _ALLOWED_META):
        if not _same_value(meta_a, meta_b, key):
            differed.append(key)
    if differed:
        raise JudgeError("run_meta.json differs in %s" % ", ".join(differed))
    prompt_a = _prompt(meta_a, name_a)
    prompt_b = _prompt(meta_b, name_b)
    if prompt_a == prompt_b:
        raise JudgeError("system_prompt values are equal")
    return {
        "a": name_a,
        "b": name_b,
        "records_a": records_a,
        "records_b": records_b,
        "meta_a": meta_a,
        "meta_b": meta_b,
        "prompt_a": prompt_a,
        "prompt_b": prompt_b,
        "case_ids": sorted(set(ids_a)),
    }


def _frozen(path, rubrics):
    path = relative_path(path, "--frozen-rubrics")
    data = load_json(path)
    recorded = data.get("rubrics") if isinstance(data, dict) else None
    if not isinstance(recorded, dict):
        raise JudgeError("frozen rubrics are not a rubric map")
    for rubric in rubrics:
        if recorded.get(rubric["name"]) != rubric["sha256"]:
            raise JudgeError("rubric %s is not the frozen text" % rubric["name"])


def _adapter_name(adapter):
    """As run records it: fake, or what _source says answered."""
    return "fake" if isinstance(adapter, FakeAdapter) else _source(adapter.client)


def run_ab(args):
    pair = check_runs(args.a, args.b)
    rubrics = load_rubrics(relative_path(args.rubrics, "--rubrics"))
    _frozen(args.frozen_rubrics, rubrics)
    adapter = build_adapter(args.adapter, args.http_fixture)
    rows = []
    for name, records in ((pair["a"], pair["records_a"]), (pair["b"], pair["records_b"])):
        for record in records:
            rows.append({
                "run": name,
                "case_id": record["case_id"],
                "trace_id": record["trace_id"],
            })
    verdicts = []
    cache = {}
    for row in rows:
        verdicts.extend(collect_verdicts(row, rubrics, adapter, cache))
    verdicts.sort(key=lambda item: (item["run"], item["case_id"], item["rubric"]))
    meta = {
        "adapter": _adapter_name(adapter),
        "digest": adapter.digest,
        "model": adapter.model,
        "options": adapter.options,
        "rubrics": {rubric["name"]: rubric["sha256"] for rubric in rubrics},
        "runs": [pair["a"], pair["b"]],
        "server_version": adapter.server_version,
    }
    write_outputs([
        (os.path.join(args.out, "verdicts.jsonl"), jsonl_text(verdicts)),
        (os.path.join(args.out, "judge_meta.json"), canonical_json(meta)),
    ])
    sys.stdout.write("verdicts %s\n" % len(verdicts))


def _integer(value, label, least=0):
    """A count. A negative limit, or a must_fall of nothing, reads as a rule and decides nothing."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise JudgeError("%s is not an integer" % label)
    if value < least:
        raise JudgeError("%s is below %s" % (label, least))
    return value


def _thresholds(path, codes, rubrics):
    path = relative_path(path, "--thresholds")
    data = load_json(path)
    if not isinstance(data, dict) or set(data) != _TOP_KEYS:
        raise JudgeError("thresholds.json has the wrong keys")
    interval = data["interval"]
    if not isinstance(interval, dict) or set(interval) != _INTERVAL_KEYS:
        raise JudgeError("thresholds.json interval has the wrong keys")
    if interval.get("method") != _METHOD:
        raise JudgeError("interval.method is not newcombe-1998-method-10")
    z = interval.get("z")
    if isinstance(z, bool) or not isinstance(z, (int, float)):
        raise JudgeError("interval.z is not a number")
    # NaN, zero and a negative z each collapse or mirror the interval, so any positive fall
    # would satisfy interval_excludes_zero. JSON accepts NaN; the method needs z above zero.
    if not math.isfinite(z) or z <= 0:
        raise JudgeError("interval.z is not a finite number above zero")
    if not isinstance(data["code"], list) or not isinstance(data["judge"], list):
        raise JudgeError("thresholds.json has the wrong keys")
    rows = []
    seen_codes = set()
    for raw in data["code"]:
        if not isinstance(raw, dict):
            raise JudgeError("thresholds.json row has the wrong keys")
        kind = raw.get("kind")
        if kind not in _CODE_KEYS or set(raw) != _CODE_KEYS[kind]:
            raise JudgeError("thresholds.json row has the wrong keys")
        code = raw.get("code")
        if not isinstance(code, str) or code not in codes:
            raise JudgeError("thresholds.json names %s which the data lacks" % code)
        if code in seen_codes:
            raise JudgeError("thresholds.json repeats %s" % code)
        seen_codes.add(code)
        row = {"name": code, "kind": kind, "source": "code"}
        if kind == "must_fall":
            row["min_net_fall"] = _integer(raw.get("min_net_fall"), "min_net_fall", least=1)
            flag = raw.get("interval_excludes_zero")
            if not isinstance(flag, bool):
                raise JudgeError("interval_excludes_zero is not a boolean")
            row["interval_excludes_zero"] = flag
        else:
            row["max_rise"] = _integer(raw.get("max_rise"), "max_rise")
        rows.append(row)
    if not any(row["kind"] == "must_fall" for row in rows):
        raise JudgeError("thresholds.json has no must_fall code")
    seen_rubrics = set()
    judge_rows = []
    for raw in data["judge"]:
        if not isinstance(raw, dict):
            raise JudgeError("thresholds.json row has the wrong keys")
        kind = raw.get("kind")
        if kind not in _JUDGE_KEYS or set(raw) != _JUDGE_KEYS[kind]:
            raise JudgeError("thresholds.json row has the wrong keys")
        rubric = raw.get("rubric")
        if not isinstance(rubric, str) or rubric not in rubrics:
            raise JudgeError("thresholds.json names %s which the data lacks" % rubric)
        if rubric in seen_rubrics:
            raise JudgeError("thresholds.json repeats %s" % rubric)
        seen_rubrics.add(rubric)
        row = {"name": rubric, "kind": kind, "source": "judge"}
        if kind == "max_pass_fall":
            row["max_pass_fall"] = _integer(raw.get("max_pass_fall"), "max_pass_fall")
        judge_rows.append(row)
    weakest = data.get("weakest_judge")
    if not isinstance(weakest, str) or weakest not in rubrics:
        raise JudgeError("thresholds.json names %s which the data lacks" % weakest)
    return rows + judge_rows, float(z), weakest


def _false_pass_text(items):
    if not items:
        return "no false passes"
    read = 0
    for item in items:
        if not isinstance(item, dict):
            raise JudgeError("a false pass is not an object")
        reading = item.get("reading")
        if reading is True or (isinstance(reading, str) and reading.strip() != ""):
            read += 1
    return "%s of %s" % (read, len(items))


def _exact(value):
    if value is None:
        return "none"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JudgeError("set 1 report has a figure that is not a number")
    return "%.4f" % value


def _set1(path, names):
    path = relative_path(path, "--set1")
    data = load_json(path)
    rubrics = data.get("rubrics") if isinstance(data, dict) else None
    if not isinstance(rubrics, list):
        raise JudgeError("set 1 report is not a report")
    found = {}
    for item in rubrics:
        if isinstance(item, dict) and isinstance(item.get("rubric"), str):
            found[item["rubric"]] = item
    sides = []
    for name in names:
        item = found.get(name)
        final = item.get("final") if isinstance(item, dict) else None
        if not isinstance(final, dict):
            raise JudgeError("set 1 report lacks final labels for %s" % name)
        if not isinstance(final.get("meets_bar"), bool):
            raise JudgeError("set 1 report lacks meets_bar for %s" % name)
        cells = {}
        for cell in _CELLS:
            cells[cell] = _integer(final.get(cell), cell)
        passes = final.get("false_passes")
        if not isinstance(passes, list):
            raise JudgeError("set 1 report lacks false passes for %s" % name)
        if "agreement" not in final or "kappa" not in final:
            raise JudgeError("set 1 report lacks a figure for %s" % name)
        agree = cells["JP_HP"] + cells["JF_HF"]
        total = agree + cells["JP_HF"] + cells["JF_HP"]
        sides.append({
            "rubric": name,
            "meets_bar": final["meets_bar"],
            "agreement": agreement_percent(agree, total),
            "agreement_exact": _exact(final.get("agreement")),
            "kappa": _exact(final.get("kappa")),
            "false_passes_read": _false_pass_text(passes),
        })
    return sides


def _statement(path):
    path = relative_path(path, "--statement")
    if not os.path.isfile(path):
        raise JudgeError("statement file is missing or unreadable")
    text = read_text(path)
    if text.strip() == "":
        raise JudgeError("statement file is empty")
    return text


def _show(value):
    if isinstance(value, str) and value.strip() != "":
        return value
    return "none"


def _result(record):
    final = record.get("final")
    if not isinstance(final, dict):
        return None
    value = final.get("ticket_result")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _flags(scored):
    order = list(CHECKS)
    found = {}
    for ticket in scored["tickets"]:
        have = {flag["code"] for flag in ticket["flags"]}
        found[ticket["case_id"]] = [code for code in order if code in have]
    return found


def _cells(case_ids, left, right):
    both = only_a = only_b = neither = 0
    for case_id in case_ids:
        a_on = case_id in left
        b_on = case_id in right
        if a_on and b_on:
            both += 1
        elif a_on:
            only_a += 1
        elif b_on:
            only_b += 1
        else:
            neither += 1
    return both, only_a, only_b, neither


def _metric(name, source, case_ids, left, right, z, extra):
    both, only_a, only_b, neither = _cells(case_ids, left, right)
    n = len(case_ids)
    fall, lower, upper = paired_difference(both, only_a, only_b, neither, z=z)
    if not all(math.isfinite(value) for value in (fall, lower, upper)):
        # A z large enough to overflow z squared leaves NaN limits, which would print as a point.
        raise JudgeError("the interval for %s is not finite" % name)
    count_a = both + only_a
    count_b = both + only_b
    row = {
        "name": name,
        "source": source,
        "n": n,
        "count_a": count_a,
        "count_b": count_b,
        "both": both,
        "only_a": only_a,
        "only_b": only_b,
        "neither": neither,
        "delta_tickets": signed_tickets(count_a - count_b),
        "delta_points": signed_points(count_a - count_b, n),
        "lower_points": format_limit(lower),
        "upper_points": format_limit(upper),
    }
    row.update(extra)
    row["_lower"] = lower
    return row


def _score(name, cases):
    """The checks' flags for one run. A cases file that cannot be read is a refusal, never a traceback."""
    try:
        _check_cases(cases)
        return score_run(name, cases_path=cases)
    except (MissingCaseError, CompareError) as error:
        raise JudgeError(str(error)) from None
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        raise JudgeError("unreadable cases file %s" % cases) from None


def _verdict_map(rows, pair, recorded):
    by_case_a = {record["case_id"]: record for record in pair["records_a"]}
    by_case_b = {record["case_id"]: record for record in pair["records_b"]}
    names = sorted(recorded)
    expected = {}
    for case_id in pair["case_ids"]:
        for rubric in names:
            expected[(pair["a"], case_id, rubric)] = by_case_a[case_id]["trace_id"]
            expected[(pair["b"], case_id, rubric)] = by_case_b[case_id]["trace_id"]
    found = {}
    for row in rows:
        key = (row["run"], row["case_id"], row["rubric"])
        if key in found:
            raise JudgeError("duplicate verdict for %s %s %s" % key)
        found[key] = row
    extra = set(found) - set(expected)
    if extra:
        raise JudgeError("extra verdict")
    missing = set(expected) - set(found)
    if missing:
        raise JudgeError("missing verdict")
    for key, trace_id in expected.items():
        row = found[key]
        if row["trace_id"] != trace_id:
            raise JudgeError("verdict trace_id does not match")
        if row["rubric_sha256"] != recorded.get(row["rubric"]):
            raise JudgeError("rubric %s does not match judge_meta.json" % row["rubric"])
    return found, names


def _holds(row, metric):
    if row["kind"] == "report_only":
        return None
    if row["kind"] == "must_fall":
        if metric["count_a"] < row["min_net_fall"]:
            return False
        if (metric["count_a"] - metric["count_b"]) < row["min_net_fall"]:
            return False
        if row["interval_excludes_zero"] and not (metric["_lower"] > 0):
            return False
        return True
    if row["kind"] == "max_rise":
        return (metric["count_b"] - metric["count_a"]) <= row["max_rise"]
    return (metric["pass_a"] - metric["pass_b"]) <= row["max_pass_fall"]


def _public(row):
    return {key: value for key, value in row.items() if not key.startswith("_")}


def ab_command(paths):
    """The command the colophon prints. The html path is fixed, and there is no md or json."""
    ordered = (
        ("--a", paths["a"]),
        ("--b", paths["b"]),
        ("--verdicts", paths["verdicts"]),
        ("--thresholds", paths["thresholds"]),
        ("--statement", paths["statement"]),
        ("--set1", paths["set1"]),
        ("--cases", paths["cases"]),
    )
    quoted = []
    for flag, value in ordered:
        quoted.append(flag)
        quoted.append(shlex.quote(value))
    quoted.extend(["--html", "reports/ab.html"])
    return " ".join(["python3 -m scorer.judge ab"] + quoted)


def threshold_text(row):
    """One threshold row: its rule and whether it held, its limits, and the observed value."""
    if row["report_only"]:
        head = "%s report_only. Not counted" % row["name"]
    else:
        head = "%s %s. %s" % (row["name"], row["kind"], "Held" if row["held"] else "Not held")
    limits = []
    for key in ("min_net_fall", "max_rise", "max_pass_fall"):
        if key in row:
            limits.append("%s %s" % (key, row[key]))
    if "interval_excludes_zero" in row:
        limits.append("interval_excludes_zero %s" % ("yes" if row["interval_excludes_zero"] else "no"))
    observed = []
    if "fall" in row:
        observed.append("fall %+d tickets" % row["fall"])
        if row.get("interval_excludes_zero"):
            observed.append("lower limit %s points" % row["lower_points"])
    if "rise" in row:
        observed.append("rise %+d tickets" % row["rise"])
    if "pass_fall" in row:
        observed.append("PASS fall %+d tickets" % row["pass_fall"])
    parts = [head]
    if limits:
        parts.append(", ".join(limits))
    if observed:
        parts.append("Observed " + ", ".join(observed))
    return ". ".join(parts) + "."


def _marked(kind, text):
    return "<!-- input:%s -->\n%s\n<!-- /input:%s -->" % (kind, text, kind)


def render_markdown(document):
    primary = document["primary"]
    lines = [
        "# Did the change work?",
        "",
        "Command: `%s`" % document["command"],
        "",
        "## %s" % primary["code"],
        "",
        "A %s. B %s." % (primary["count_a"], primary["count_b"]),
        "Delta %s tickets, %s points." % (primary["delta_tickets"], primary["delta_points"]),
        "Interval %s to %s points." % (primary["lower_points"], primary["upper_points"]),
        document["cover_note"],
        "",
        "%s thresholds held." % document["thresholds_held"],
        "",
        "## %s" % PROVENANCE_HEADING,
        "",
        _marked("statement", document["statement"]),
        "",
        "## Setup",
        "",
    ]
    setup = document["setup"]
    lines.extend([
        "Ollama %s." % setup["ollama_version"],
        "Grader model %s. Digest %s." % (setup["grader_model"], setup["grader_digest"]),
        "Judge model %s. Digest %s. Adapter %s." % (setup["judge_model"], setup["judge_digest"], setup["judge_adapter"]),
        "Interval method %s, z %s." % (setup["interval_method"], setup["z"]),
        "A %s." % setup["a"],
        "B %s." % setup["b"],
        "",
        "## Prompt",
        "",
        _marked("diff", "\n".join(document["prompt_diff"])),
        "",
        "## Set 1",
        "",
        document["weakest_sentence"],
        "",
    ])
    for side in document["set1"]:
        lines.extend([
            "### %s" % side["rubric"],
            "",
            "meets_bar: %s. Agreement %s (%s). Kappa %s. False passes read: %s." % (
                "yes" if side["meets_bar"] else "no",
                side["agreement"],
                side["agreement_exact"],
                side["kappa"],
                side["false_passes_read"],
            ),
            "",
        ])
    # Agreement and kappa are calibration numbers, and AGENTS.md wants the hand-written
    # statement beside every one of them, not three sections away on the cover.
    lines.extend(["### %s" % PROVENANCE_HEADING, "", _marked("statement", document["statement"]), ""])
    lines.extend(["## Metrics", "", document["sign_note"], ""])
    for row in document["metrics"]:
        lines.append("### %s" % row["name"])
        lines.append("")
        if row["source"] == "judge":
            lines.append("PASS share A %s. PASS share B %s." % (row["pass_share_a"], row["pass_share_b"]))
            lines.append("UNPARSED A %s. UNPARSED B %s." % (row["unparsed_a"], row["unparsed_b"]))
            lines.append("FAIL to PASS %s. PASS to FAIL %s." % (row["fail_to_pass"], row["pass_to_fail"]))
        lines.append("%sA %s. B %s. Delta %s tickets, %s points." % (
            "FAIL " if row["source"] == "judge" else "",
            row["count_a"], row["count_b"], row["delta_tickets"], row["delta_points"],
        ))
        lines.append("Interval %s to %s points." % (row["lower_points"], row["upper_points"]))
        lines.append("Only A %s. Only B %s." % (row["only_a"], row["only_b"]))
        lines.append("")
    lines.extend(["## Thresholds", ""])
    for row in document["threshold_rows"]:
        lines.append(threshold_text(row))
    lines.extend(["", "%s thresholds held." % document["thresholds_held"], "", "## Tickets", ""])
    for ticket in document["tickets"]:
        lines.append("### %s" % ticket["case_id"])
        lines.append("")
        lines.append("A final %s. B final %s." % (
            "none" if ticket["final_a"] is None else ticket["final_a"],
            "none" if ticket["final_b"] is None else ticket["final_b"],
        ))
        lines.append("A codes %s." % (", ".join(ticket["codes_a"]) or "none"))
        lines.append("B codes %s." % (", ".join(ticket["codes_b"]) or "none"))
        for verdict in ticket["verdicts"]:
            lines.append("%s A %s. B %s." % (verdict["rubric"], verdict["a"], verdict["b"]))
            if verdict["differs"]:
                lines.append(_marked("reason", "A: %s\nB: %s" % (_show(verdict["reason_a"]), _show(verdict["reason_b"]))))
        lines.append("")
    text = "\n".join(lines)
    if not text.endswith("\n"):
        text += "\n"
    return text


def _span(text, short=False, marker=None):
    classes = "mono" if short else "break"
    extra = ' data-short="1"' if short else ""
    if marker:
        extra += ' data-input="%s"' % marker
    return '<span class="%s"%s>%s</span>' % (classes, extra, esc(text))


def _td(label, inner, short=False):
    flag = ' data-short="1"' if short else ""
    return '<td data-label="%s"%s>%s</td>' % (esc(label), flag, inner)


def _ticket_row(ticket):
    reasons = []
    for verdict in ticket["verdicts"]:
        if verdict["differs"]:
            text = "%s A: %s B: %s" % (verdict["rubric"], _show(verdict["reason_a"]), _show(verdict["reason_b"]))
            reasons.append(_span(text, marker="reason"))
    cells = [
        _td("Case", _span(ticket["case_id"], short=True), short=True),
        _td("A final", _span("none" if ticket["final_a"] is None else ticket["final_a"], short=True), short=True),
        _td("B final", _span("none" if ticket["final_b"] is None else ticket["final_b"], short=True), short=True),
        _td("A codes", _span(", ".join(ticket["codes_a"]) or "none")),
        _td("B codes", _span(", ".join(ticket["codes_b"]) or "none")),
    ]
    for verdict in ticket["verdicts"]:
        cells.append(_td("A " + verdict["rubric"], _span(verdict["a"], short=True), short=True))
        cells.append(_td("B " + verdict["rubric"], _span(verdict["b"], short=True), short=True))
    cells.append(_td("Reasons", "".join(reasons)))
    return '<tr class="row" data-case="%s">%s</tr>' % (esc(ticket["case_id"]), "".join(cells))


def render_ab_html(document, css):
    primary = document["primary"]
    setup = document["setup"]
    lines = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<link rel="icon" href="data:,">',
        "<title>Did the change work?</title>",
    ]
    lines.extend(FONT_LINKS)
    lines.extend([
        "<style>",
        css.rstrip("\n"),
        "</style>",
        "</head>",
        "<body>",
        '<div class="wrap break ab-page">',
        '<header class="cover panel">',
        '<p class="issue"><span>A/B</span><span class="as-recorded break" data-input="path">%s</span>'
        '<span class="as-recorded break" data-input="path">%s</span></p>' % (
            esc(setup["a"]), esc(setup["b"]),
        ),
        '<h1 class="mast"><small>Settlement grader</small>Did the change work?</h1>',
        '<div class="cover-main">',
        '<div class="cover-tiles">',
        '<p class="ab-primary" data-primary="%s">%s</p>' % (esc(primary["code"]), esc(primary["code"])),
        "<p>A <span class=\"mono\">%s</span>. B <span class=\"mono\">%s</span>.</p>" % (
            esc(primary["count_a"]), esc(primary["count_b"]),
        ),
        "<p>Delta <span class=\"mono\">%s</span> tickets, <span class=\"mono\">%s</span> points.</p>" % (
            esc(primary["delta_tickets"]), esc(primary["delta_points"]),
        ),
        "<p>Interval <span class=\"mono\">%s</span> to <span class=\"mono\">%s</span> points.</p>" % (
            esc(primary["lower_points"]), esc(primary["upper_points"]),
        ),
        '<p class="ab-legend">%s</p>' % esc(document["cover_note"]),
        '<p class="ab-held">%s thresholds held.</p>' % esc(document["thresholds_held"]),
        "</div>",
        '<div class="prov">',
        "<h2>%s</h2>" % esc(PROVENANCE_HEADING),
        '<p class="cover-statement" data-input="statement">%s</p>' % esc(document["statement"]),
        "</div>",
        "</div>",
        "</header>",
        '<section class="sec panel">',
        "<h2>Setup</h2>",
        "<p>Ollama <span class=\"mono\">%s</span>. Grader <span class=\"mono\">%s</span> "
        "<span class=\"mono break\">%s</span>.</p>" % (
            esc(setup["ollama_version"]), esc(setup["grader_model"]), esc(setup["grader_digest"]),
        ),
        "<p>Judge <span class=\"mono\">%s</span> <span class=\"mono break\">%s</span>. "
        "Adapter <span class=\"mono\">%s</span>. "
        "Interval method <span class=\"mono\">%s</span>, z <span class=\"mono\">%s</span>.</p>" % (
            esc(setup["judge_model"]), esc(setup["judge_digest"]), esc(setup["judge_adapter"]),
            esc(setup["interval_method"]), esc(setup["z"]),
        ),
        '<details class="prompt-fold" open><summary>Prompt</summary>',
        '<pre class="prompt-diff" data-input="diff">%s</pre>' % esc("\n".join(document["prompt_diff"])),
        "</details>",
        "</section>",
        '<section class="sec panel">',
        "<h2>Set 1</h2>",
        "<p>%s</p>" % esc(document["weakest_sentence"]),
    ])
    for side in document["set1"]:
        klass = "ab-judge"
        if not side["meets_bar"]:
            klass += " ab-fail"
        lines.append(
            '<p class="%s" data-set1="%s">%s. meets_bar: %s. Agreement %s (%s). Kappa %s. '
            "False passes read: %s.</p>" % (
                klass,
                esc(side["rubric"]),
                esc(side["rubric"]),
                esc("yes" if side["meets_bar"] else "no"),
                esc(side["agreement"]),
                esc(side["agreement_exact"]),
                esc(side["kappa"]),
                esc(side["false_passes_read"]),
            )
        )
    lines.extend([
        '<div class="prov">',
        "<h3>%s</h3>" % esc(PROVENANCE_HEADING),
        '<p class="set1-statement" data-input="statement">%s</p>' % esc(document["statement"]),
        "</div>",
    ])
    lines.extend(["</section>", '<section class="sec panel">', "<h2>Metrics</h2>", "<p>%s</p>" % esc(document["sign_note"])])
    for row in document["metrics"]:
        lines.append('<article class="metric" data-metric="%s" data-source="%s">' % (esc(row["name"]), esc(row["source"])))
        lines.append("<h3>%s</h3>" % esc(row["name"]))
        if row["source"] == "judge":
            lines.append("<p>PASS share A %s. PASS share B %s. Delta %s points.</p>" % (
                esc(row["pass_share_a"]), esc(row["pass_share_b"]), esc(row["delta_points"]),
            ))
            lines.append("<p>FAIL to PASS %s. PASS to FAIL %s. UNPARSED A %s. UNPARSED B %s.</p>" % (
                esc(row["fail_to_pass"]), esc(row["pass_to_fail"]), esc(row["unparsed_a"]), esc(row["unparsed_b"]),
            ))
        lines.append("<p>%sA %s. B %s. Delta %s tickets, %s points. Interval %s to %s points.</p>" % (
            "FAIL " if row["source"] == "judge" else "",
            esc(row["count_a"]), esc(row["count_b"]), esc(row["delta_tickets"]), esc(row["delta_points"]),
            esc(row["lower_points"]), esc(row["upper_points"]),
        ))
        lines.append("<p>Only A %s. Only B %s.</p>" % (esc(row["only_a"]), esc(row["only_b"])))
        lines.append("</article>")
    lines.extend(["</section>", '<section class="sec panel">', "<h2>Thresholds</h2>"])
    for row in document["threshold_rows"]:
        if row["report_only"]:
            klass = "ab-threshold"
            held = "report"
        elif row["held"]:
            klass = "ab-threshold"
            held = "yes"
        else:
            klass = "ab-threshold ab-fail"
            held = "no"
        lines.append('<p class="%s" data-threshold="%s" data-held="%s">%s</p>' % (
            klass, esc(row["name"]), held, esc(threshold_text(row)),
        ))
    lines.append('<p class="ab-held">%s thresholds held.</p>' % esc(document["thresholds_held"]))
    lines.extend([
        "</section>",
        '<section class="sec panel">',
        "<h2>Tickets</h2>",
        '<table class="ledger ab-rows">',
        "<thead><tr>%s</tr></thead>" % "".join("<th>%s</th>" % esc(name) for name in document["ticket_columns"]),
        "<tbody>",
    ])
    for ticket in document["tickets"]:
        lines.append(_ticket_row(ticket))
    lines.extend([
        "</tbody>",
        "</table>",
        "</section>",
        '<p class="colophon">Regenerated by <code class="mono" data-input="command">%s</code>. '
        "Fonts load from Google Fonts.</p>" % esc(document["command"]),
        "</div>",
        "</body>",
        "</html>",
        "",
    ])
    return "\n".join(lines)


def report_ab(args):
    pair = check_runs(args.a, args.b)
    verdict_rows, meta = _load_verdicts(relative_path(args.verdicts, "--verdicts"))
    if not isinstance(meta, dict):
        raise JudgeError("judge_meta.json is not an object")
    recorded = meta.get("rubrics")
    names = sorted(recorded) if isinstance(recorded, dict) else []
    # Paths are normalised once so the colophon and the checks see the same strings.
    paths = {
        "a": pair["a"],
        "b": pair["b"],
        "verdicts": relative_path(args.verdicts, "--verdicts"),
        "thresholds": relative_path(args.thresholds, "--thresholds"),
        "statement": relative_path(args.statement, "--statement"),
        "set1": relative_path(args.set1, "--set1"),
        "cases": relative_path(args.cases, "--cases"),
    }
    statement = _statement(paths["statement"])
    set1 = _set1(paths["set1"], names) if names else None
    command = ab_command(paths)
    document = _assemble(pair, verdict_rows, meta, paths, statement, set1, command)
    markdown = render_markdown(document)
    pairs = []
    if args.md_out:
        pairs.append((args.md_out, markdown))
    if args.json_out:
        pairs.append((args.json_out, canonical_json(_json_document(document))))
    if args.html_out:
        pairs.append((args.html_out, render_ab_html(document, _css_text())))
    write_outputs(pairs)
    sys.stdout.write(markdown)


def _json_document(document):
    """The written JSON. Private interval floats stay out of it."""
    copied = dict(document)
    copied["metrics"] = [_public(row) if "_lower" in row else row for row in document["metrics"]]
    return copied


def _assemble(pair, verdict_rows, meta, paths, statement, set1, command):
    """Build the document. set1 is loaded once the rubric names are known."""
    recorded = meta.get("rubrics")
    if not isinstance(recorded, dict) or not recorded:
        raise JudgeError("judge_meta.json lacks rubrics")
    for name, digest in recorded.items():
        if not isinstance(name, str) or not isinstance(digest, str) or digest.strip() == "":
            raise JudgeError("judge_meta.json lacks rubrics")
    if meta.get("runs") != [pair["a"], pair["b"]]:
        raise JudgeError("judge_meta.json runs do not match")
    found, rubric_names = _verdict_map(verdict_rows, pair, recorded)
    if set1 is None:
        set1 = _set1(paths["set1"], rubric_names)
    threshold_rows, z, weakest = _thresholds(paths["thresholds"], set(CHECKS), set(rubric_names))
    cases_path = paths["cases"]
    flags_a = _flags(_score(pair["a"], cases_path))
    flags_b = _flags(_score(pair["b"], cases_path))

    def failing_ids(name, rubric):
        return {
            case_id for case_id in pair["case_ids"]
            if found[(name, case_id, rubric)]["verdict"] != "PASS"
        }

    metrics = []
    n = len(pair["case_ids"])
    for rubric in rubric_names:
        pass_a = sum(found[(pair["a"], case_id, rubric)]["verdict"] == "PASS" for case_id in pair["case_ids"])
        pass_b = sum(found[(pair["b"], case_id, rubric)]["verdict"] == "PASS" for case_id in pair["case_ids"])
        extra = {
            "pass_a": pass_a,
            "pass_b": pass_b,
            "pass_share_a": agreement_percent(pass_a, n),
            "pass_share_b": agreement_percent(pass_b, n),
            "unparsed_a": sum(found[(pair["a"], case_id, rubric)]["verdict"] == "UNPARSED" for case_id in pair["case_ids"]),
            "unparsed_b": sum(found[(pair["b"], case_id, rubric)]["verdict"] == "UNPARSED" for case_id in pair["case_ids"]),
        }
        row = _metric(rubric, "judge", pair["case_ids"], failing_ids(pair["a"], rubric), failing_ids(pair["b"], rubric), z, extra)
        row["fail_to_pass"] = row["only_a"]
        row["pass_to_fail"] = row["only_b"]
        metrics.append(row)
    for code in CHECKS:
        left = {case_id for case_id, codes in flags_a.items() if code in codes}
        right = {case_id for case_id, codes in flags_b.items() if code in codes}
        metrics.append(_metric(code, "code", pair["case_ids"], left, right, z, {}))
    by_name = {row["name"]: row for row in metrics}
    applied = []
    for raw in threshold_rows:
        held = _holds(raw, by_name[raw["name"]])
        item = {
            "name": raw["name"],
            "kind": raw["kind"],
            "source": raw["source"],
            "held": held,
            "report_only": raw["kind"] == "report_only",
        }
        for key in ("min_net_fall", "interval_excludes_zero", "max_rise", "max_pass_fall"):
            if key in raw:
                item[key] = raw[key]
        # The observed value beside the limit, so "Held" can be checked on the row itself.
        metric = by_name[raw["name"]]
        if raw["kind"] == "must_fall":
            item["fall"] = metric["count_a"] - metric["count_b"]
            item["lower_points"] = metric["lower_points"]
        elif raw["kind"] == "max_rise":
            item["rise"] = metric["count_b"] - metric["count_a"]
        elif raw["kind"] == "max_pass_fall":
            item["pass_fall"] = metric["pass_a"] - metric["pass_b"]
        applied.append(item)
    counted = [item for item in applied if not item["report_only"]]
    holding = sum(1 for item in counted if item["held"])
    primary = next(row for row in metrics if row["name"] == next(item["name"] for item in applied if item["kind"] == "must_fall"))
    by_a = {record["case_id"]: record for record in pair["records_a"]}
    by_b = {record["case_id"]: record for record in pair["records_b"]}
    tickets = []
    for case_id in pair["case_ids"]:
        verdicts = []
        for rubric in rubric_names:
            left = found[(pair["a"], case_id, rubric)]
            right = found[(pair["b"], case_id, rubric)]
            verdicts.append({
                "rubric": rubric,
                "a": left["verdict"],
                "b": right["verdict"],
                "reason_a": left["reason"],
                "reason_b": right["reason"],
                "differs": left["verdict"] != right["verdict"],
            })
        tickets.append({
            "case_id": case_id,
            "final_a": _result(by_a[case_id]),
            "final_b": _result(by_b[case_id]),
            "codes_a": list(flags_a[case_id]),
            "codes_b": list(flags_b[case_id]),
            "verdicts": verdicts,
        })
    z_text = "%g" % z
    return {
        "command": command,
        "statement": statement,
        # Computed sentences that say what a sign means; without them "+1 tickets" on a
        # code row reads as a rise, and the same plus on a judge row means more PASS.
        "sign_note": (
            "Delta is A minus B. For a code, a plus means fewer tickets with the code in B. "
            "For a judge, the tickets counted are FAIL and UNPARSED, so a plus means more PASS in B. "
            "Each interval is the paired interval on that delta, z %s." % z_text
        ),
        "cover_note": (
            "Delta is A minus B: a plus means fewer tickets with the code in B. "
            "The interval is the paired interval on that delta, z %s." % z_text
        ),
        "ticket_columns": (
            ["Case", "A final", "B final", "A codes", "B codes"]
            + [side + " " + rubric for rubric in rubric_names for side in ("A", "B")]
            + ["Reasons"]
        ),
        "primary": {
            "code": primary["name"],
            "count_a": primary["count_a"],
            "count_b": primary["count_b"],
            "delta_tickets": primary["delta_tickets"],
            "delta_points": primary["delta_points"],
            "lower_points": primary["lower_points"],
            "upper_points": primary["upper_points"],
        },
        "thresholds_held": "%s of %s" % (holding, len(counted)),
        "setup": {
            "ollama_version": _show(pair["meta_a"].get("ollama_version")),
            "grader_model": _show(pair["meta_a"].get("model")),
            "grader_digest": _show(pair["meta_a"].get("model_digest")),
            "judge_model": _show(meta.get("model")),
            "judge_digest": _show(meta.get("digest")),
            "interval_method": _METHOD,
            "z": z_text,
            "judge_adapter": _show(meta.get("adapter")),
            "a": pair["a"],
            "b": pair["b"],
        },
        "prompt_diff": list(difflib.unified_diff(
            pair["prompt_a"].splitlines(),
            pair["prompt_b"].splitlines(),
            fromfile="A",
            tofile="B",
            lineterm="",
            n=1,
        )),
        "set1": set1,
        "weakest_judge": weakest,
        "weakest_sentence": "%s is the delta to read with most care." % weakest,
        "metrics": [_public(row) for row in metrics],
        "threshold_rows": applied,
        "tickets": tickets,
    }
