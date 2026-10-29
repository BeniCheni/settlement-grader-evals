"""Compare every plain-code check with the human labels.

The result is in sample: two checks were fixed while reading these same traces.
"""
import argparse
import json
import os
import sys

from scorer.checks import CHECKS
from scorer.stats import (
    MIN_AGREEMENT,
    MIN_KAPPA,
    agreement,
    canonical_json,
    cohen_kappa,
    confusion,
    false_pass_rate,
    meets_bar,
)
from scorer.traces import load_run


PROVENANCE = (
    "In sample. Two checks were fixed while reading these 32 traces. "
    "This shows the checks reproduce the labels they were built from, "
    "not that they generalise."
)


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def bar_words():
    """The two numbers meets_bar tests, as every report prints them."""
    return "%d%% and %s" % (round(MIN_AGREEMENT * 100), MIN_KAPPA)


def not_bar_words():
    return "not %d%% or %s" % (round(MIN_AGREEMENT * 100), MIN_KAPPA)


def false_passes_read(row):
    """How many false passes have a non-empty reading, over how many there are.

    The second number is the length of false_passes. A reading counts when its
    text is a non-empty string.
    """
    readings = row["readings"]
    read = 0
    for case_id in row["false_passes"]:
        text = readings.get(case_id)
        if isinstance(text, str) and text:
            read += 1
    return "%s of %s" % (read, len(row["false_passes"]))


def load_cases(path):
    return {case["case_id"]: case for case in _load(path)}


def _round4(value):
    if value is None:
        return None
    return round(value, 4)


def calibrate(run_dir, cases_path="data/gold.json", codes_path="data/codes_v1.json",
              readings_path="data/calibration_readings_v1.json"):
    """Return run, cases, and one row per plain-code check."""
    records = load_run(run_dir)
    cases = load_cases(cases_path)
    readings = _load(readings_path)
    rows = []
    for code_obj in _load(codes_path):
        code = code_obj["code"]
        if code not in CHECKS:
            continue
        check = CHECKS[code]
        human = set(code_obj.get("traces") or [])
        predicted = []
        truth = []
        evidence = {}
        for record in records:
            found = check(record, cases[record["case_id"]])
            predicted.append(found is not None)
            truth.append(record["case_id"] in human)
            if found is not None:
                evidence[record["case_id"]] = found
        counts = confusion(predicted, truth)
        false_passes = {}
        false_fails = {}
        for record, pred, actual in zip(records, predicted, truth):
            case_id = record["case_id"]
            if actual and not pred:
                false_passes[case_id] = "human label; the check did not flag"
            elif pred and not actual:
                false_fails[case_id] = evidence[case_id]
        rows.append({
            "code": code,
            "n": len(records),
            "tp": counts["tp"],
            "fp": counts["fp"],
            "fn": counts["fn"],
            "tn": counts["tn"],
            "agreement": _round4(agreement(counts)),
            "kappa": _round4(cohen_kappa(counts)),
            "false_pass_rate": _round4(false_pass_rate(counts)),
            "meets_bar": meets_bar(counts),
            "human_near_miss": list(code_obj.get("near_miss") or []),
            "false_passes": false_passes,
            "false_fails": false_fails,
            "readings": dict(readings.get(code) or {}),
        })
    return {"run": run_dir, "cases": len(records), "codes": rows}


def _meta(run_dir):
    path = os.path.join(run_dir, "run_meta.json")
    if not os.path.isfile(path):
        return {}
    meta = _load(path)
    return meta if isinstance(meta, dict) else {}


def document(run_dir, **paths):
    """The calibration plus the in-sample limit, for the page and the JSON report."""
    doc = calibrate(run_dir, **paths)
    meta = _meta(run_dir)
    model = meta.get("model")
    run_label = meta.get("run_id")
    doc["model"] = model if isinstance(model, str) and model.strip() else None
    doc["run_label"] = run_label if isinstance(run_label, str) and run_label.strip() else run_dir
    doc["in_sample"] = True
    doc["provenance"] = PROVENANCE
    return doc


def _fmt(value):
    if value is None:
        return "none"
    return "%.4f" % value


def render_markdown(doc):
    rows = doc["codes"]
    meeting = sum(1 for row in rows if row["meets_bar"])
    false_passes = sum(len(row["false_passes"]) for row in rows)
    lacks = sum(len(row["false_fails"]) for row in rows)
    lines = [
        "# Calibration of the plain-code checks",
        "",
        doc.get("provenance") or PROVENANCE,
        "",
        "Run: %s. Model: %s. Tickets: %s. Checks at %s: %s of %s. False passes: %s. Flags the labels lack: %s." % (
            doc["run"],
            doc.get("model") or "unknown",
            doc["cases"],
            bar_words(),
            meeting,
            len(rows),
            false_passes,
            lacks,
        ),
        "",
        "Command: `python3 -m scorer.calibrate %s --json reports/calibration-v1.json --md reports/calibration-v1.md`" % doc["run"],
        "",
        "| Code | Caught | Agreement | Kappa | False passes | False fails | %s | False passes read |" % bar_words(),
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append("| %s | %s of %s | %s | %s | %s | %s | %s | %s |" % (
            row["code"],
            row["tp"],
            row["tp"] + row["fn"],
            _fmt(row["agreement"]),
            _fmt(row["kappa"]),
            len(row["false_passes"]),
            len(row["false_fails"]),
            "yes" if row["meets_bar"] else "no",
            false_passes_read(row),
        ))
    lines.extend(["", "## Disagreements", ""])
    notes = 0
    for row in rows:
        readings = row["readings"]
        for kind, bucket in (("flag the labels lack", row["false_fails"]), ("false pass", row["false_passes"])):
            for case_id in sorted(bucket):
                notes += 1
                lines.append("### %s · %s" % (row["code"], case_id))
                lines.append("")
                lines.append("This is a %s." % kind)
                lines.append("")
                lines.append(readings.get(case_id) or "No reading recorded.")
                lines.append("")
    if notes == 0:
        lines.extend(["No disagreements on this run.", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_text(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Calibrate the plain-code checks. The result is in sample.")
    parser.add_argument("run_dir")
    parser.add_argument("--json", dest="json_out")
    parser.add_argument("--md", dest="md_out")
    args = parser.parse_args(argv)
    doc = document(args.run_dir)
    text = render_markdown(doc)
    sys.stdout.write(text)
    if args.json_out:
        write_text(args.json_out, canonical_json(doc))
    if args.md_out:
        write_text(args.md_out, text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
