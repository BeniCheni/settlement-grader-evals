"""The oracle is the acceptance test. A disagreement without a reading fails the suite."""
import json
import os
import unittest

from scorer.calibrate import PROVENANCE, calibrate, document
from scorer.checks import CHECKS
from scorer.score import score_run
from scorer.traces import load_run


def require_readings(rows):
    missing = []
    for row in rows:
        readings = row["readings"]
        case_ids = list(row["false_passes"]) + list(row["false_fails"])
        for case_id in case_ids:
            text = readings.get(case_id)
            if not isinstance(text, str) or not text.strip():
                missing.append("%s %s" % (row["code"], case_id))
    if missing:
        raise AssertionError("disagreement lacks a reading: %s" % ", ".join(missing))


class OracleTests(unittest.TestCase):
    def test_v1_matches_the_oracle_on_every_pinned_field(self):
        with open("data/oracle_slice1.json", encoding="utf-8") as handle:
            oracle = json.load(handle)
        doc = calibrate("traces/v1")
        self.assertEqual(doc["run"], oracle["run"])
        self.assertEqual(doc["cases"], oracle["tickets"])
        self.assertEqual(sum(1 for row in doc["codes"] if row["meets_bar"]), oracle["checks_meeting_the_bar"])
        self.assertEqual([row["code"] for row in doc["codes"]], list(oracle["codes"]))
        records = load_run("traces/v1")
        with open("data/gold.json", encoding="utf-8") as handle:
            cases = {case["case_id"]: case for case in json.load(handle)}
        by_code = {row["code"]: row for row in doc["codes"]}
        for code, expected in oracle["codes"].items():
            row = by_code[code]
            flagged = [record["case_id"] for record in records if CHECKS[code](record, cases[record["case_id"]])]
            self.assertEqual(flagged, expected["flagged"], code)
            for key in ("tp", "fp", "fn", "tn", "meets_bar"):
                self.assertEqual(row[key], expected[key], "%s %s" % (code, key))
            self.assertEqual(round(row["agreement"], 4), expected["agreement"], code)
            self.assertEqual(round(row["kappa"], 4), expected["kappa"], code)
            self.assertEqual(sorted(row["false_passes"]), expected["false_passes"], code)
            self.assertEqual(sorted(row["false_fails"]), expected["false_fails"], code)
        require_readings(doc["codes"])

    def test_a_disagreement_without_a_reading_fails(self):
        bare = {"code": "SKIPPED_SETTLE_TICKET", "false_passes": {}, "false_fails": {"B01": "net"}, "readings": {}}
        with self.assertRaises(AssertionError):
            require_readings([bare])
        filled = dict(bare)
        filled["readings"] = {"B01": "a reading"}
        require_readings([filled])

    def test_the_report_says_the_result_is_in_sample(self):
        doc = document("traces/v1")
        self.assertTrue(doc["in_sample"])
        self.assertIn("in sample", doc["provenance"].lower())
        self.assertIn("not that they generalise", doc["provenance"])
        self.assertEqual(doc["provenance"], PROVENANCE)
        self.assertNotIn("/Users/", json.dumps(doc))
        self.assertNotIn(os.path.expanduser("~"), json.dumps(doc))

    def test_score_counts_match_the_oracle_flags(self):
        with open("data/oracle_slice1.json", encoding="utf-8") as handle:
            oracle = json.load(handle)
        scored = score_run("traces/v1")
        self.assertTrue(scored["in_sample"])
        for code, expected in oracle["codes"].items():
            self.assertEqual(scored["counts"][code], len(expected["flagged"]), code)


if __name__ == "__main__":
    unittest.main()
