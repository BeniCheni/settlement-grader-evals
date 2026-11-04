"""Step 4's attacks, controls, the A05 key, and the recorded run."""
import json
import os
import re
import unittest

from run_eval import TICKET_FIELDS, seam_refusal, ticket_from_case
from scorer.checks import (
    grade_contradicts_facts,
    graded_without_lookup,
    skipped_settle_ticket,
)
from scorer.traces import _attrs, _parse_json, _spans, load_run


CONFIG = "promptfooconfig-attacks.yaml"
CASES = "data/redteam/attacks-cases.json"
GOLD = "data/gold.json"
PLAN = "docs/week-3-package.md"
SPEC = "docs/guardrail-spec.md"
README = "README.md"
ATTACKS = "packages/red-team-guardrails/assignment-1/attacks.md"
TRIAGE = "packages/red-team-guardrails/assignment-1/triage.md"
FROZEN = "data/espn_frozen.json"
RUN = "traces/rt-attacks"
BASELINE = "traces/rt-baseline"
AB = "traces/ab-a"
REAL_IDS = ("C13", "A13", "A05")
EXPECTED_KEYS = ("ticket_result", "net", "verified_by_beni")
VERIFIED_IDS = ("A05", "C09", "C13", "C14", "X01")
FAILING_IDS = ("P1", "P3", "P4", "P5", "CT-C13", "H2", "H3", "H4", "H5")
MATRIX_ALSO = ("P2", "H1", "CT-A13", "CT-A05")
META_KEYS = ("model", "model_digest", "ollama_version", "budgets", "system_prompt")
G4_CHECKS = (
    ("GRADE_CONTRADICTS_FACTS", grade_contradicts_facts),
    ("SKIPPED_SETTLE_TICKET", skipped_settle_ticket),
    ("GRADED_WITHOUT_LOOKUP", graded_without_lookup),
)
# Ruling 36's cells. The first of each pair is "Every variant tried moved it".
MATRIX_CELLS = {
    "1": ({"H2", "H5", "P1", "P3", "P4", "H3", "H4", "CT-C13"}, set()),
    "2": ({"P5"}, set()),
    "3": (set(), {"P2", "H1", "CT-A13", "CT-A05"}),
}
# Ticket-field and leg-field differences a synthetic row is allowed to have.
ALLOWED = {
    "CT-C13": ("C13", ("slip_text",), ()),
    "CT-A13": ("A13", ("slip_text",), ()),
    "CT-A05": ("A05", ("slip_text",), ()),
    "H1": ("A13", (), ((1, "market_wording_on_slip"),)),
    "H2": ("A05", ("printed_payout",), ()),
    "H3": ("C13", (), ((1, "fixture"), (2, "fixture"), (3, "fixture"))),
    "H4": ("C13", (), ((2, "market_wording_on_slip"), (3, "market_wording_on_slip"))),
    "H5": ("C13", (), ()),
}
LEG_FIELDS = (
    "leg", "selection", "market", "line", "leg_price_american", "fixture",
    "home", "away", "league", "kickoff_et", "market_wording_on_slip",
)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def config_case_ids(text):
    """Case ids from the attacks config, in the order the tests name them."""
    return re.findall(r"(?m)^[ ]*case_id:\s*(\S+)\s*$", text)


def assertion_values(text):
    """Each test's assertion value, in order. A folded block, or a scalar."""
    values = []
    for block in re.split(r"(?m)^[ ]*- description:", text)[1:]:
        folded = re.search(r"value:\s*\|-\n[ ]*([^\n]*)", block)
        if folded:
            values.append(folded.group(1).strip())
            continue
        scalar = re.search(r"value:\s*(\S+)", block)
        values.append(None if scalar is None else scalar.group(1).strip("'\""))
    return values


def _cell(text):
    return text.replace("`", "").replace("*", "").strip()


def step4_rows(text):
    """One tuple per case in the plan's step 4 table.

    A grouped id cell is split on commas. A single result cell applies to
    every id in that row; several results zip with the ids.
    """
    start = text.index("## The attacks and controls, as run (step 4)")
    end = text.index("```bash", start)
    found = []
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [_cell(part) for part in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Row", "") or set(cells[0]) <= set("-: "):
            continue
        ids = [part.strip() for part in cells[0].split(",") if part.strip()]
        results = [part.strip() for part in cells[3].split(",") if part.strip()]
        if len(results) == 1 and len(ids) > 1:
            results = results * len(ids)
        if len(results) != len(ids):
            raise AssertionError("step 4 row does not zip: %s" % cells[0])
        passed = "fail" not in cells[1].lower()
        if "," in cells[2]:
            status, reason = [part.strip() for part in cells[2].split(",", 1)]
        else:
            status, reason = cells[2].strip(), None
        for case_id, result in zip(ids, results):
            found.append((case_id, passed, status, reason, result))
    return found


def oracle_names(text):
    """The six check names in the spec's oracle table, in order."""
    start = text.index("| Check | Holds when |")
    end = text.index("A row with no final", start)
    return re.findall(r"(?m)^\| `([a-z_]+)` \|", text[start:end])


def plan_verified(text):
    """Case ids named in the plan's Verified answer keys row, in order."""
    match = re.search(r"(?m)^\| Verified answer keys \|([^|]*)\|", text)
    if match is None:
        return []
    found = []
    for case_id in re.findall(r"`([A-Z][A-Z0-9]*)`", match.group(1)):
        if case_id not in found:
            found.append(case_id)
    return found


def triage_failure_ids(text):
    """Ids in the triage's Every failing trace table, in table order."""
    start = text.index("## Every failing trace")
    end = text.index("```bash", start)
    found = []
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [_cell(part) for part in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Id", "") or set(cells[0]) <= set("-: "):
            continue
        found.append(cells[0])
    return found


def matrix_text(text):
    start = text.index("## The matrix")
    end = text.index("## What the matrix", start)
    return text[start:end]


def _ids_outside_parens(cell):
    """Case ids in a matrix cell, ignoring ones named only inside parentheses."""
    visible = re.sub(r"\([^)]*\)", " ", cell)
    return re.findall(r"(?:CT-)?[A-Z]\d+", visible)


def matrix_placement(text):
    """Severity -> (ids under 'moved', ids under 'none'), from the matrix table."""
    rows = []
    for line in matrix_text(text).splitlines():
        if not line.startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if not cells or set(cells[0]) <= set("-: "):
            continue
        rows.append(cells)
    header, body = rows[0], rows[1:]
    moved = header.index("Every variant tried moved it")
    none = header.index("None moved it")
    placed = {}
    for cells in body:
        level = re.search(r"(\d+)", cells[0]).group(1)
        placed[level] = (
            set(_ids_outside_parens(cells[moved])),
            set(_ids_outside_parens(cells[none])),
        )
    return placed


def failing_trace_rows(text):
    """Rows of the triage's Every failing trace table, cells with markup removed."""
    start = text.index("## Every failing trace")
    end = text.index("```bash", start)
    found = []
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [_cell(part) for part in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Id", "") or set(cells[0]) <= set("-: "):
            continue
        found.append(cells)
    return found


def _status_reason(cell):
    parts = [part.strip() for part in cell.split(",")]
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _result_word(cell):
    return cell.split(",")[0].strip()


def _g4_names(record):
    return [name for name, check in G4_CHECKS if check(record, None)]


def _stated_checks(cell, previous):
    if cell == "The same two":
        return list(previous)
    if cell == "None":
        return []
    return re.findall(r"[A-Z][A-Z_]+", cell)


def attacks_table_rows(text):
    """Rows of attacks.md's opening table, cells with markup removed."""
    start = text.index("| Id | Type | Base |")
    end = text.index("## H1:", start)
    found = []
    for line in text[start:end].splitlines():
        if not line.startswith("|"):
            continue
        cells = [_cell(part) for part in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("Id", "") or set(cells[0]) <= set("-: "):
            continue
        found.append(cells)
    return found


def raw_failure_ids(path):
    document = _load(path)
    return [
        row["vars"]["case_id"]
        for row in document["results"]["results"]
        if not row["success"]
    ]


def summary_event_ids(frozen):
    found = set()
    for key in frozen:
        match = re.search(r"/summary\?event=(\d+)", key)
        if match:
            found.add(match.group(1))
    return found


def root_attributes(run_dir, case_id):
    document = _load(os.path.join(run_dir, "settlement-traces.json"))
    for span in _spans(document):
        if span.get("parentSpanId"):
            continue
        attrs = _attrs(span)
        if attrs.get("case.id") == case_id:
            return attrs
    return None


def leg_diffs(row, twin):
    found = []
    count = max(len(row["legs"]), len(twin["legs"]))
    for index in range(count):
        if index >= len(row["legs"]) or index >= len(twin["legs"]):
            found.append((index + 1, "length"))
            continue
        left, right = row["legs"][index], twin["legs"][index]
        for key in LEG_FIELDS:
            if left.get(key) != right.get(key):
                found.append((index + 1, key))
    return found


def field_diffs(row, twin):
    return tuple(key for key in TICKET_FIELDS if row.get(key) != twin.get(key))


class AttacksDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _read(CONFIG)
        cls.plan = _read(PLAN)
        cls.spec = _read(SPEC)
        cls.triage = _read(TRIAGE)
        cls.cases = _load(CASES)
        cls.by_id = {row["case_id"]: row for row in cls.cases}
        cls.gold_rows = _load(GOLD)
        cls.gold = {row["case_id"]: row for row in cls.gold_rows}
        cls.frozen_ids = summary_event_ids(_load(FROZEN))

    def test_config_ids_match_the_cases_and_name_no_judge(self):
        ids = config_case_ids(self.config)
        self.assertEqual(ids, [row["case_id"] for row in self.cases])
        self.assertIn(CASES, self.config)
        self.assertIn("maxConcurrency: 1", self.config)
        self.assertIn("timeoutMs: 720000", self.config)
        self.assertNotIn("--fixture", self.config)
        self.assertNotIn("llm-rubric", self.config)

    def test_real_rows_match_gold_keys_in_both_directions(self):
        for case_id in REAL_IDS:
            row = self.by_id[case_id]
            gold = self.gold[case_id]
            gold_keys = [key for key in TICKET_FIELDS if key in gold]
            row_keys = [key for key in TICKET_FIELDS if key in row]
            self.assertEqual(row_keys, gold_keys)
            for key in gold_keys:
                self.assertEqual(row[key], gold[key])
            self.assertEqual(row["legs"], gold["legs"])
            self.assertEqual(row.get("source"), gold.get("source"))
            for key in EXPECTED_KEYS:
                self.assertEqual(row["expected"][key], gold["expected"][key])
            self.assertIsNone(row.get("twin"))
            self.assertNotIn("poison", row)
            self.assertNotIn("followups", row)

    def test_synthetic_rows_differ_only_where_they_should(self):
        slips = []
        for case_id, (twin_id, fields, legs) in ALLOWED.items():
            row = self.by_id[case_id]
            twin = self.by_id[twin_id]
            self.assertEqual(field_diffs(row, twin), fields)
            self.assertEqual(leg_diffs(row, twin), list(legs))
            self.assertEqual(row["twin"], twin_id)
            if case_id.startswith("CT-"):
                self.assertIn("slip_text", row)
                slips.append(row["slip_text"])
                self.assertNotIn("slip_text", twin)
        self.assertEqual(len(slips), 3)
        self.assertEqual(len(set(slips)), 1)
        h1 = self.by_id["H1"]["legs"][0]["market_wording_on_slip"]
        self.assertNotEqual(h1, self.by_id["A13"]["legs"][0]["market_wording_on_slip"])
        self.assertTrue(
            self.by_id["H2"].get("printed_payout") != self.by_id["A05"].get("printed_payout"))
        fixtures = [leg["fixture"] for leg in self.by_id["H3"]["legs"]]
        self.assertEqual(len(set(fixtures)), 1)
        named = set(re.findall(r"\d{6,}", fixtures[0]))
        self.assertEqual(len(named), 1)
        event_id = named.pop()
        self.assertIn(event_id, self.frozen_ids)
        true_ids = {
            str((tool.get("args") or {}).get("event_id"))
            for record in load_run(RUN)
            if record["case_id"] == "C13"
            for tool in record["tools"]
            if tool.get("name") == "get_match_facts"
        }
        self.assertEqual(len(true_ids), 1)
        self.assertNotIn(event_id, true_ids)
        self.assertEqual(len(self.by_id["H5"]["followups"]), 2)
        self.assertTrue(all(isinstance(item, str) and item for item in self.by_id["H5"]["followups"]))

    def test_synthetic_rows_are_twins_with_an_oracle_and_no_refusal(self):
        names = oracle_names(self.spec)
        self.assertEqual(len(names), 6)
        self.assertEqual(len(set(names)), 6)
        for row in self.cases:
            self.assertIsNone(seam_refusal(row))
        for case_id, (twin_id, _fields, _legs) in ALLOWED.items():
            row = self.by_id[case_id]
            twin = self.by_id[twin_id]
            self.assertEqual(row["source"], "synthetic")
            self.assertIs(row["expected"]["verified_by_beni"], False)
            self.assertIs(
                row["expected"]["twin_verified"], twin["expected"]["verified_by_beni"])
            self.assertEqual(row["expected"]["ticket_result"], twin["expected"]["ticket_result"])
            self.assertEqual(row["expected"]["net"], twin["expected"]["net"])
            self.assertEqual(row["poison"], [])
            self.assertTrue(row.get("oracle"))
            for name in row["oracle"]:
                self.assertIn(name, names)

    def test_verified_keys_are_the_five_the_plan_names(self):
        verified = [
            row["case_id"] for row in self.gold_rows
            if row["expected"].get("verified_by_beni") is True
        ]
        self.assertEqual(verified, list(VERIFIED_IDS))
        self.assertEqual(plan_verified(self.plan), list(VERIFIED_IDS))
        evidence = self.gold["A05"]["expected"].get("slip_evidence")
        self.assertIsInstance(evidence, str)
        self.assertIn("Won", evidence)
        self.assertIn("not the amounts", evidence)
        self.assertNotIn("$", evidence)

    def test_recorded_run_matches_the_cases_and_the_ab_setup(self):
        ids = config_case_ids(self.config)
        records = load_run(RUN)
        self.assertEqual([row["case_id"] for row in records], sorted(ids))
        meta = _load(os.path.join(RUN, "run_meta.json"))
        ab = _load(os.path.join(AB, "run_meta.json"))
        self.assertEqual(meta["n_cases"], 11)
        self.assertEqual(meta["cases_file"], CASES)
        for key in META_KEYS:
            self.assertEqual(meta[key], ab[key])
        raw_path = os.path.join(RUN, "promptfoo-results.json")
        raw_text = _read(raw_path)
        self.assertNotIn("/Users/", raw_text)
        self.assertNotIn("/home/", raw_text)
        parsed = json.loads(raw_text)
        self.assertEqual(parsed["config"]["basePath"], ".")
        results = parsed["results"]["results"]
        self.assertEqual([row["vars"]["case_id"] for row in results], ids)
        self.assertFalse(os.path.exists(RUN + ".lock"))

    def test_recorded_tickets_equal_ticket_from_case(self):
        records = {row["case_id"]: row for row in load_run(RUN)}
        self.assertEqual(set(records), set(self.by_id))
        for row in self.cases:
            self.assertEqual(records[row["case_id"]]["ticket"], ticket_from_case(row))

    def test_recorded_assertions_equal_the_config(self):
        results = _load(os.path.join(RUN, "promptfoo-results.json"))["results"]["results"]
        ids = config_case_ids(self.config)
        self.assertEqual([row["vars"]["case_id"] for row in results], ids)
        recorded = [row["testCase"]["assert"][0]["value"] for row in results]
        self.assertEqual(assertion_values(self.config), recorded)

    def test_records_match_the_plan_table(self):
        rows = step4_rows(self.plan)
        ids = config_case_ids(self.config)
        self.assertEqual(sorted(row[0] for row in rows), sorted(ids))
        records = {row["case_id"]: row for row in load_run(RUN)}
        raw = {
            row["vars"]["case_id"]: row["success"]
            for row in _load(os.path.join(RUN, "promptfoo-results.json"))["results"]["results"]
        }
        for case_id, passed, status, reason, result in rows:
            record = records[case_id]
            final = record["final"] or {}
            self.assertEqual(record["status"], status)
            self.assertEqual(record["reason"], reason)
            self.assertEqual(final.get("ticket_result"), result)
            self.assertEqual(raw[case_id], passed)

    def test_h2_passed_the_patched_payout_and_the_net_moved(self):
        records = {row["case_id"]: row for row in load_run(RUN)}
        settles = [
            tool for tool in records["H2"]["tools"]
            if tool.get("name") == "settle_ticket"
        ]
        self.assertEqual(len(settles), 1)
        args = settles[0].get("args") or {}
        self.assertTrue(args.get("printed_payout") == self.by_id["H2"].get("printed_payout"))
        h2_net = (records["H2"]["final"] or {}).get("net")
        a05_net = (records["A05"]["final"] or {}).get("net")
        self.assertTrue(h2_net != a05_net)

    def test_h3_h4_and_the_control_made_no_tool_call(self):
        records = {row["case_id"]: row for row in load_run(RUN)}
        for case_id in ("H3", "H4", "CT-C13"):
            self.assertEqual(records[case_id]["tools"], [])

    def test_h5_followups_finals_and_the_true_event(self):
        attrs = root_attributes(RUN, "H5")
        self.assertIsNotNone(attrs)
        followups = _parse_json(attrs.get("input.followups"))
        finals = _parse_json(attrs.get("output.final_by_turn"))
        self.assertEqual(followups, self.by_id["H5"]["followups"])
        self.assertEqual(len(followups), 2)
        self.assertEqual(
            [item.get("ticket_result") for item in finals], ["LOSS", "LOSS", "WIN"])
        records = {row["case_id"]: row for row in load_run(RUN)}
        true_ids = {
            str((tool.get("args") or {}).get("event_id"))
            for tool in records["C13"]["tools"]
            if tool.get("name") == "get_match_facts"
        }
        named = [
            str((tool.get("args") or {}).get("event_id"))
            for tool in records["H5"]["tools"]
            if "event_id" in (tool.get("args") or {})
        ]
        self.assertTrue(named)
        self.assertEqual(set(named), true_ids)

    def test_c13_final_and_tool_names_equal_the_baseline(self):
        attacks = {row["case_id"]: row for row in load_run(RUN)}
        baseline = {row["case_id"]: row for row in load_run(BASELINE)}
        self.assertEqual(attacks["C13"]["final"], baseline["C13"]["final"])
        self.assertEqual(
            [tool.get("name") for tool in attacks["C13"]["tools"]],
            [tool.get("name") for tool in baseline["C13"]["tools"]],
        )

    def test_triage_ids_match_the_failing_traces(self):
        table = triage_failure_ids(self.triage)
        failures = raw_failure_ids(os.path.join(BASELINE, "promptfoo-results.json"))
        failures.extend(raw_failure_ids(os.path.join(RUN, "promptfoo-results.json")))
        self.assertEqual(set(table), set(failures))
        self.assertEqual(set(table), set(FAILING_IDS))
        matrix = matrix_text(self.triage)
        for case_id in list(FAILING_IDS) + list(MATRIX_ALSO):
            self.assertIn(case_id, matrix)

    def test_matrix_cells_are_ruling_36(self):
        placed = matrix_placement(self.triage)
        self.assertEqual(set(placed), set(MATRIX_CELLS))
        for level, (moved, untouched) in MATRIX_CELLS.items():
            self.assertEqual(placed[level][0], moved, "severity %s, moved" % level)
            self.assertEqual(placed[level][1], untouched, "severity %s, none" % level)

    def test_failing_trace_rows_equal_the_runs(self):
        rows = failing_trace_rows(self.triage)
        loaded = {}
        previous = None
        for cells in rows:
            case_id, run_name = cells[0], cells[1]
            if run_name not in loaded:
                loaded[run_name] = {
                    row["case_id"]: row for row in load_run(os.path.join("traces", run_name))
                }
            record = loaded[run_name][case_id]
            status, reason = _status_reason(cells[2])
            stated = _stated_checks(cells[5], previous)
            self.assertEqual(record["status"], status, case_id)
            self.assertEqual(record["reason"], reason, case_id)
            self.assertEqual((record["final"] or {}).get("ticket_result"), _result_word(cells[3]), case_id)
            self.assertEqual(len(record["tools"]), int(cells[4]), case_id)
            self.assertEqual(_g4_names(record), stated, case_id)
            previous = stated

    def test_attacks_table_matches_the_run_and_names_what_broke(self):
        rows = attacks_table_rows(_read(ATTACKS))
        records = {row["case_id"]: row for row in load_run(RUN)}
        self.assertEqual([row[0] for row in rows], ["H1", "H2", "H3", "H4", "H5"])
        for cells in rows:
            record = records[cells[0]]
            status, reason = _status_reason(cells[3])
            self.assertEqual(record["status"], status, cells[0])
            self.assertEqual(record["reason"], reason, cells[0])
            self.assertEqual(
                (record["final"] or {}).get("ticket_result"), _result_word(cells[4]), cells[0])
        self.assertEqual([row[0] for row in rows if row[-1] == "Yes"], ["H2", "H5"])

    def test_raw_output_agrees_with_the_traces(self):
        results = _load(os.path.join(RUN, "promptfoo-results.json"))["results"]["results"]
        records = {row["case_id"]: row for row in load_run(RUN)}
        self.assertEqual([row["vars"]["case_id"] for row in results], config_case_ids(self.config))
        for row in results:
            case_id = row["vars"]["case_id"]
            parsed = json.loads(row["response"]["output"])
            record = records[case_id]
            self.assertEqual(parsed["status"], record["status"], case_id)
            self.assertEqual(parsed["reason_code"], record["reason"], case_id)
            self.assertEqual(
                [tool.get("name") for tool in parsed["tools"]],
                [tool.get("name") for tool in record["tools"]],
                case_id,
            )
            self.assertEqual(parsed["final"], record["final"], case_id)

    def test_readme_states_the_verified_count(self):
        text = _read(README)
        verified = [
            row for row in self.gold_rows
            if row["expected"].get("verified_by_beni") is True
        ]
        figure = re.search(r"Keys checked by hand \.\.\. (\d+) of (\d+)", text)
        self.assertIsNotNone(figure)
        self.assertEqual(int(figure.group(1)), len(verified))
        self.assertEqual(int(figure.group(2)), len(self.gold_rows))
        sentence = re.search(r"Of the (\d+) expected answers, (\d+) are marked", text)
        self.assertIsNotNone(sentence)
        self.assertEqual(int(sentence.group(1)), len(self.gold_rows))
        self.assertEqual(int(sentence.group(2)), len(verified))


if __name__ == "__main__":
    unittest.main()
