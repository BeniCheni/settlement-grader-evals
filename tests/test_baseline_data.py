"""Step 3's committed probes, the corrected X01 block, and the recorded run."""
import json
import os
import re
import unittest

from grader.agent import SYSTEM_PROMPT
from run_eval import TICKET_FIELDS, seam_refusal
from scorer.traces import load_run


CONFIG = "promptfooconfig.yaml"
CASES = "data/redteam/baseline-cases.json"
GOLD = "data/gold.json"
ADVERSARIAL = "data/adversarial.json"
PLAN = "docs/week-3-package.md"
RUN = "traces/rt-baseline"
ORACLES = {
    "result_same_as_twin",
    "net_same_as_twin",
    "lookups_made",
    "same_event_as_twin",
    "no_system_prompt",
    "no_tip",
}
PROBE_IDS = ("P1", "P2", "P3", "P4", "P5")
EXPECTED_KEYS = ("ticket_result", "net", "verified_by_beni")


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def config_case_ids(text):
    """Case ids from the root config, in the order the tests name them."""
    return re.findall(r"(?m)^[ ]*case_id:\s*(\S+)\s*$", text)


def p4_assertion_strings(text):
    """The double-quoted strings in P4's javascript assertion."""
    match = re.search(
        r"(?m)^[ ]*case_id:\s*P4\s*$.*?javascript\n[ ]*value:\s*\|-\n[ ]+([^\n]+)",
        text,
        re.S,
    )
    if match is None:
        return []
    return re.findall(r'"([^"]*)"', match.group(1))


def plan_passes(text):
    """Pass or fail from the baseline table, and nothing else that table states."""
    start = text.index("## The baseline, as run (step 3)")
    end = text.index("```bash", start)
    found = []
    for match in re.finditer(
            r"^\| `?([A-Z][A-Z0-9]*)`? \| ([^|]+) \|", text[start:end], re.M):
        cell = match.group(2).replace("*", "").strip().lower()
        found.append((match.group(1), cell == "pass"))
    return found


class BaselineDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _read(CONFIG)
        cls.plan = _read(PLAN)
        cls.cases = _load(CASES)
        cls.by_id = {row["case_id"]: row for row in cls.cases}
        cls.gold = {row["case_id"]: row for row in _load(GOLD)}
        cls.adversarial = {row["case_id"]: row for row in _load(ADVERSARIAL)}

    def test_config_ids_match_the_cases_in_order_and_name_no_judge(self):
        ids = config_case_ids(self.config)
        self.assertEqual(ids, [row["case_id"] for row in self.cases])
        self.assertNotIn("llm-rubric", self.config)

    def test_c13_matches_gold_on_ticket_fields_legs_and_key(self):
        row = self.by_id["C13"]
        gold = self.gold["C13"]
        for key in TICKET_FIELDS:
            if key in row:
                self.assertEqual(row[key], gold[key])
        self.assertEqual(row["legs"], gold["legs"])
        for key in EXPECTED_KEYS:
            self.assertEqual(row["expected"][key], gold["expected"][key])
        self.assertNotIn("poison", row)
        self.assertNotIn("followups", row)

    def test_p_rows_match_c13_except_for_distinct_slip_text(self):
        twin = self.by_id["C13"]
        slips = []
        for case_id in PROBE_IDS:
            row = self.by_id[case_id]
            for key in TICKET_FIELDS:
                if key == "slip_text":
                    continue
                self.assertEqual(row.get(key), twin.get(key))
            self.assertEqual(row["legs"], twin["legs"])
            if case_id == "P2":
                self.assertNotIn("slip_text", row)
            else:
                self.assertIn("slip_text", row)
                slips.append(row["slip_text"])
        self.assertEqual(len(set(slips)), len(slips))

    def test_p_rows_are_synthetic_twins_and_only_p2_is_poisoned(self):
        twin = self.by_id["C13"]["expected"]
        poisoned = []
        for row in self.cases:
            self.assertIsNone(seam_refusal(row))
            if row.get("poison"):
                poisoned.append(row["case_id"])
            if "followups" in row:
                self.assertEqual(row["followups"], [])
        self.assertEqual(poisoned, ["P2"])
        for case_id in PROBE_IDS:
            row = self.by_id[case_id]
            self.assertEqual(row["source"], "synthetic")
            self.assertEqual(row["twin"], "C13")
            self.assertIs(row["expected"]["verified_by_beni"], False)
            self.assertIs(row["expected"]["twin_verified"], True)
            self.assertEqual(row["expected"]["ticket_result"], twin["ticket_result"])
            self.assertEqual(row["expected"]["net"], twin["net"])
            self.assertEqual(row["followups"], [])

    def test_oracle_names_are_the_six_in_the_spec(self):
        named = [name for row in self.cases for name in row.get("oracle") or []]
        self.assertTrue(named)
        for name in named:
            self.assertIn(name, ORACLES)

    def test_p4_strings_are_in_the_prompt_and_cover_its_long_lines(self):
        strings = p4_assertion_strings(self.config)
        self.assertTrue(strings)
        lowered = SYSTEM_PROMPT.lower()
        for item in strings:
            self.assertIn(item, lowered)
        long_lines = [line for line in SYSTEM_PROMPT.split("\n") if len(line) >= 20]
        self.assertTrue(long_lines)
        for line in long_lines:
            folded = line.lower()
            self.assertTrue(any(item in folded for item in strings))

    def test_x01_expected_blocks_are_equal(self):
        self.assertEqual(
            self.gold["X01"]["expected"], self.adversarial["X01"]["expected"])

    def test_recorded_run_matches_the_plan_table(self):
        ids = config_case_ids(self.config)
        records = load_run(RUN)
        self.assertEqual([row["case_id"] for row in records], ids)
        poisoned = {
            row["case_id"]: sum(1 for tool in row["tools"] if tool.get("poisoned"))
            for row in records
        }
        self.assertEqual(
            poisoned, {case_id: (3 if case_id == "P2" else 0) for case_id in ids})
        meta = _load(os.path.join(RUN, "run_meta.json"))
        self.assertEqual(meta["n_cases"], 6)
        self.assertEqual(meta["cases_file"], CASES)
        raw_path = os.path.join(RUN, "promptfoo-results.json")
        raw = _read(raw_path)
        self.assertNotIn("/Users/", raw)
        self.assertNotIn("/home/", raw)
        parsed = json.loads(raw)
        self.assertEqual(parsed["config"]["basePath"], ".")
        results = parsed["results"]["results"]
        got = [(row["vars"]["case_id"], row["success"]) for row in results]
        self.assertEqual(got, plan_passes(self.plan))
        self.assertEqual([case_id for case_id, _passed in got], ids)


if __name__ == "__main__":
    unittest.main()
