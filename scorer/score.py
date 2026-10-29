"""Score one run: which failure codes each ticket shows.

Comparing two runs is a later slice. The output identifies the tuning sample and its limits.
"""
import argparse
import sys

from scorer.calibrate import MissingCaseError, case_for, load_cases, provenance_for, write_text
from scorer.checks import CHECKS
from scorer.stats import canonical_json
from scorer.traces import load_run


def score_run(run_dir, cases_path="data/gold.json"):
    records = load_run(run_dir)
    cases = load_cases(cases_path)
    counts = {}
    tickets = []
    for code in CHECKS:
        counts[code] = 0
    for record in records:
        case = case_for(cases, record["case_id"], cases_path)
        flags = []
        for code, check in CHECKS.items():
            evidence = check(record, case)
            if evidence is None:
                continue
            counts[code] += 1
            flags.append({"code": code, "evidence": evidence})
        tickets.append({"case_id": record["case_id"], "flags": flags})
    in_sample, provenance = provenance_for(records)
    output = {
        "run": run_dir,
        "in_sample": in_sample,
        "provenance": provenance,
        "counts": counts,
        "tickets": tickets,
    }
    if cases_path != "data/gold.json":
        output["cases_path"] = cases_path
    return output


def format_counts(scored):
    lines = ["%s %s" % (code, scored["counts"][code]) for code in CHECKS]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score one run with the plain-code checks. The result is in sample.")
    parser.add_argument("run_dir")
    parser.add_argument("--cases", dest="cases_path", default="data/gold.json",
                        help="the cases file the run was graded from (default data/gold.json)")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args(argv)
    try:
        scored = score_run(args.run_dir, cases_path=args.cases_path)
    except (MissingCaseError, FileNotFoundError) as error:
        parser.error(str(error))
    sys.stdout.write(format_counts(scored))
    if args.json_out:
        write_text(args.json_out, canonical_json(scored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
