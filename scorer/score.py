"""Score one run: which failure codes each ticket shows.

Comparing two runs is a later slice. Anything this prints is in sample.
"""
import argparse
import sys

from scorer.calibrate import PROVENANCE, load_cases, write_text
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
        case = cases[record["case_id"]]
        flags = []
        for code, check in CHECKS.items():
            evidence = check(record, case)
            if evidence is None:
                continue
            counts[code] += 1
            flags.append({"code": code, "evidence": evidence})
        tickets.append({"case_id": record["case_id"], "flags": flags})
    return {
        "run": run_dir,
        "in_sample": True,
        "provenance": PROVENANCE,
        "counts": counts,
        "tickets": tickets,
    }


def format_counts(scored):
    lines = ["%s %s" % (code, scored["counts"][code]) for code in CHECKS]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Score one run with the plain-code checks. The result is in sample.")
    parser.add_argument("run_dir")
    parser.add_argument("--json", dest="json_out")
    args = parser.parse_args(argv)
    scored = score_run(args.run_dir)
    sys.stdout.write(format_counts(scored))
    if args.json_out:
        write_text(args.json_out, canonical_json(scored))
    return 0


if __name__ == "__main__":
    sys.exit(main())
