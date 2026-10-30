"""Report what differs between two grader runs.

The command names differences. It does not label them noise, drift, or a verdict.
"""
import argparse
import json
import os
import sys
import tempfile

from scorer.calibrate import MissingCaseError, load_cases, provenance_for, write_text
from scorer.checks import CHECKS
from scorer.score import score_run
from scorer.stats import canonical_json
from scorer.traces import load_run


EXCLUDED_META = frozenset(("run_id", "n_cases", "outcome_matches"))
SETUP_KEYS = ("ollama_version", "model_digest")


class CompareError(ValueError):
    """A run pair cannot be compared. The command exits with status 2."""


def normalise_run(path):
    """Name a resolved run inside the working directory, without a machine path."""
    root = os.path.realpath(os.getcwd())
    resolved = os.path.realpath(path)
    if os.path.commonpath((root, resolved)) != root:
        raise CompareError("run outside working directory")
    return os.path.relpath(resolved, root)


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _final_token(final):
    if final is None:
        return None
    return _canon(final)


def _load_records(run_dir, name):
    normalise_run(os.path.join(run_dir, "settlement-traces.json"))
    try:
        records = load_run(run_dir)
    except (FileNotFoundError, NotADirectoryError):
        raise CompareError("missing run %s" % name) from None
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        raise CompareError("unreadable settlement-traces.json for %s" % name) from None
    if not records:
        raise CompareError("empty run %s" % name)
    seen = set()
    for record in records:
        case_id = record.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise CompareError("invalid case_id in %s" % name)
        if case_id in seen:
            raise CompareError("duplicate case_id %s in %s" % (case_id, name))
        seen.add(case_id)
    return records


def _load_meta(run_dir, name):
    path = os.path.join(run_dir, "run_meta.json")
    normalise_run(path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        raise CompareError("unreadable run_meta.json for %s" % name) from None
    if not isinstance(payload, dict):
        raise CompareError("unreadable run_meta.json for %s" % name)
    return payload


def _check_cases(cases_path):
    """Check that load_cases can read the cases file before scoring."""
    try:
        load_cases(cases_path)
    except FileNotFoundError:
        raise
    except (OSError, ValueError, TypeError, AttributeError, KeyError):
        raise CompareError("unreadable cases file %s" % cases_path) from None


def _recorded(meta):
    if not isinstance(meta, dict):
        return False
    for key in SETUP_KEYS:
        if key not in meta:
            return False
        value = meta[key]
        if not isinstance(value, str) or not value.strip():
            return False
    return True


def _side(meta, key):
    if not isinstance(meta, dict) or key not in meta:
        return {"absent": True}
    return {"absent": False, "value": meta[key]}


def _same_side(left, right):
    if left["absent"] or right["absent"]:
        return left["absent"] and right["absent"]
    return _canon(left["value"]) == _canon(right["value"])


def _differing(meta_a, meta_b):
    keys = set()
    if isinstance(meta_a, dict):
        keys.update(meta_a)
    if isinstance(meta_b, dict):
        keys.update(meta_b)
    keys.difference_update(EXCLUDED_META)
    found = []
    for key in sorted(keys):
        side_a = _side(meta_a, key)
        side_b = _side(meta_b, key)
        if _same_side(side_a, side_b):
            continue
        found.append({"a": side_a, "b": side_b, "key": key})
    return found


def _flag_sets(scored):
    found = {}
    for ticket in scored["tickets"]:
        found[ticket["case_id"]] = {flag["code"] for flag in ticket["flags"]}
    return found


def _show(side):
    if side["absent"]:
        return "absent"
    return json.dumps(side["value"], sort_keys=True, ensure_ascii=False)


def compare_runs(run_a, run_b, cases_path="data/gold.json"):
    """Facts that differ between two runs. Paths in the result are normalised."""
    name_a = normalise_run(run_a)
    name_b = normalise_run(run_b)
    records_a = _load_records(run_a, name_a)
    records_b = _load_records(run_b, name_b)
    meta_a = _load_meta(run_a, name_a)
    meta_b = _load_meta(run_b, name_b)
    _check_cases(cases_path)
    scored_a = score_run(run_a, cases_path=cases_path)
    scored_b = score_run(run_b, cases_path=cases_path)
    by_a = {record["case_id"]: record for record in records_a}
    by_b = {record["case_id"]: record for record in records_b}
    shared = sorted(set(by_a) & set(by_b))
    finals = [
        case_id for case_id in shared
        if _final_token(by_a[case_id]["final"]) != _final_token(by_b[case_id]["final"])
    ]
    flags_a = _flag_sets(scored_a)
    flags_b = _flag_sets(scored_b)
    codes = []
    for code in CHECKS:
        count_a = scored_a["counts"][code]
        count_b = scored_b["counts"][code]
        codes.append({
            "a": count_a,
            "b": count_b,
            "b_minus_a": count_b - count_a,
            "code": code,
        })
    a_recorded = _recorded(meta_a)
    b_recorded = _recorded(meta_b)
    setup = {
        "a_recorded": a_recorded,
        "b_recorded": b_recorded,
        "cannot_trace": not (a_recorded and b_recorded),
        "differ": _differing(meta_a, meta_b),
    }
    if a_recorded and b_recorded:
        setup["matches"] = not setup["differ"]
    return {
        "a": name_a,
        "b": name_b,
        "tickets": {
            "a": len(by_a),
            "b": len(by_b),
            "only_a": sorted(set(by_a) - set(by_b)),
            "only_b": sorted(set(by_b) - set(by_a)),
            "shared": len(shared),
        },
        "final_answers": {"case_ids": finals, "differ": len(finals)},
        "codes": codes,
        "codes_differ": [
            case_id for case_id in shared if flags_a[case_id] != flags_b[case_id]
        ],
        "setup": setup,
        "provenance": {
            "a": provenance_for(records_a)[1],
            "b": provenance_for(records_b)[1],
        },
    }


def format_report(report):
    """Text form of compare_runs. One trailing newline, no timestamp."""
    lines = [
        "A %s" % report["a"],
        "B %s" % report["b"],
        "",
        "tickets",
        "A %s" % report["tickets"]["a"],
        "B %s" % report["tickets"]["b"],
        "shared %s" % report["tickets"]["shared"],
        "only A",
    ]
    lines.extend(report["tickets"]["only_a"])
    lines.append("only B")
    lines.extend(report["tickets"]["only_b"])
    lines.extend(["", "final answers", "differ %s" % report["final_answers"]["differ"]])
    lines.extend(report["final_answers"]["case_ids"])
    lines.extend(["", "codes"])
    for row in report["codes"]:
        lines.append("%s %s %s %s" % (row["code"], row["a"], row["b"], row["b_minus_a"]))
    lines.append("codes differ %s" % len(report["codes_differ"]))
    lines.extend(report["codes_differ"])
    lines.extend(["", "setup", "differ"])
    for item in report["setup"]["differ"]:
        lines.append(item["key"])
        lines.append("A %s" % _show(item["a"]))
        lines.append("B %s" % _show(item["b"]))
    recorded = report["setup"]
    lines.append("A records setup %s" % ("yes" if recorded["a_recorded"] else "no"))
    lines.append("B records setup %s" % ("yes" if recorded["b_recorded"] else "no"))
    if recorded.get("matches") is True:
        lines.append("recorded setup matches")
    if recorded["cannot_trace"]:
        lines.append("a difference between the runs cannot be traced to its setup")
    lines.extend(["", "provenance", "A", report["provenance"]["a"], "B", report["provenance"]["b"]])
    return "\n".join(lines) + "\n"


def _write_json(path, text):
    """Publish a complete report, or leave the previous output untouched."""
    parent = os.path.dirname(os.path.abspath(path))
    missing = []
    directory = parent
    while not os.path.exists(directory):
        missing.append(directory)
        directory = os.path.dirname(directory)
    staged = None
    try:
        os.makedirs(parent, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=parent, delete=False) as handle:
            staged = handle.name
        write_text(staged, text)
        os.replace(staged, path)
        staged = None
    finally:
        if staged is not None:
            os.unlink(staged)
        for directory in missing:
            try:
                os.rmdir(directory)
            except OSError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report what differs between two grader runs.")
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--cases", dest="cases_path", default="data/gold.json",
                        help="the cases file the runs were graded from (default data/gold.json)")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args(argv)
    try:
        report = compare_runs(args.run_a, args.run_b, cases_path=args.cases_path)
    except (CompareError, MissingCaseError, FileNotFoundError) as error:
        parser.error(str(error))
    text = format_report(report)
    if args.json_out:
        try:
            _write_json(args.json_out, canonical_json(report))
        except OSError:
            parser.error("cannot write %s" % args.json_out)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
