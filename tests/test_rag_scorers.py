"""The four scorers on the recorded runs, and the cases that have to be able to fail."""
import copy
import json
import os
import unittest

import check_gold
import scorer.rag as rag
from scorer.checks import _best_facts, _committed, _facts_seen
from scorer.golden import enrich_real, event_index, key_for_leg, load_gold, real_rows
from scorer.rag import needed_items, retrieved_items, score_case
from scorer.traces import load_run


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RUNS = ("v1", "aa-1", "aa-2", "aa-3", "ab-a", "ab-b")
_FOUR = (("v1", "A01"), ("aa-1", "C09"), ("v1", "C09"), ("v1", "C13"))


def _output(row, record):
    return {
        "answer": record.get("final"),
        "retrieved_contexts": [list(item) for item in retrieved_items(record)],
        "record": record,
    }


def _metadata(row):
    return {
        "question": row.get("question"),
        "ground_truth_contexts": row.get("contexts"),
        "row": row,
    }


def _load():
    if getattr(_load, "rows", None) is None:
        gold = load_gold(os.path.join(ROOT, "data", "gold.json"))
        events = event_index(os.path.join(ROOT, "data", "gold_check.json"))
        _load.rows = {row["case_id"]: enrich_real(row, events) for row in real_rows(gold)}
        _load.runs = {}
        for name in _RUNS:
            records = load_run(os.path.join(ROOT, "traces", name))
            _load.runs[name] = {record["case_id"]: record for record in records}
    return _load.rows, _load.runs


class RecordedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.runs = _load()

    def _score(self, run, case_id):
        return score_case(self.rows[case_id], self.runs[run][case_id])

    def test_v1_a01_is_the_worked_example(self):
        scored = self._score("v1", "A01")
        self.assertEqual(scored["context_recall"]["value"], 2.0 / 3.0)
        self.assertEqual(scored["context_recall"]["reason"], "2 of 3")
        self.assertEqual(scored["context_precision"]["value"], 1.0)
        self.assertEqual(scored["faithfulness"]["supported"], 2)
        self.assertEqual(scored["faithfulness"]["claims"], 2)
        self.assertEqual(scored["answer_relevancy"]["value"], 1.0)

    def test_aa1_c09_has_no_tools_and_four_unsupported_grades(self):
        scored = self._score("aa-1", "C09")
        self.assertEqual(scored["context_recall"]["value"], 0.0)
        self.assertEqual(scored["context_precision"]["value"], 0.0)
        self.assertEqual(scored["faithfulness"]["supported"], 0)
        self.assertEqual(scored["faithfulness"]["claims"], 4)
        self.assertEqual(scored["answer_relevancy"]["value"], 0.75)

    def test_v1_c09_leg_4_committed_p_against_a_key_of_l(self):
        row = self.rows["C09"]
        record = self.runs["v1"]["C09"]
        seen = _facts_seen(record)
        facts = _best_facts(record["ticket"]["legs"][3], seen)
        grade, _evidence = key_for_leg(row["legs"][3], facts)
        self.assertEqual(grade, "L")
        self.assertIn("P", _committed(record, 3))
        scored = score_case(row, record)
        self.assertEqual(scored["faithfulness"]["supported"], 7)
        self.assertEqual(scored["faithfulness"]["claims"], 8)

    def test_v1_c13_lists_one_final_leg_of_three(self):
        scored = self._score("v1", "C13")
        self.assertEqual(scored["faithfulness"]["supported"], 1)
        self.assertEqual(scored["faithfulness"]["claims"], 4)
        self.assertEqual(scored["answer_relevancy"]["value"], 0.75)
        final_legs = self.runs["v1"]["C13"]["final"]["legs"]
        self.assertEqual(len(final_legs), 1)
        self.assertEqual(final_legs[0]["leg"], 1)
        self.assertEqual(len(self.rows["C13"]["legs"]), 3)

    def test_aa1_b05_leg_4_is_an_l_made_with_no_usable_facts(self):
        row = self.rows["B05"]
        record = self.runs["aa-1"]["B05"]
        facts = _best_facts(record["ticket"]["legs"][3], _facts_seen(record))
        with self.assertRaises(KeyError):
            key_for_leg(row["legs"][3], facts)
        self.assertIn("L", _committed(record, 3))
        scored = score_case(row, record)
        self.assertEqual(scored["faithfulness"]["supported"], 2)
        self.assertEqual(scored["faithfulness"]["claims"], 5)
        self.assertEqual(scored["faithfulness"]["legs_left"], 0)

    def test_v1_b05_has_no_final_and_no_claim(self):
        record = self.runs["v1"]["B05"]
        self.assertIsNone(record["final"])
        scored = score_case(self.rows["B05"], record)
        self.assertEqual(scored["answer_relevancy"]["value"], 0.0)
        self.assertIsNone(scored["faithfulness"]["value"])
        self.assertEqual(scored["faithfulness"]["claims"], 0)
        self.assertEqual(scored["faithfulness"]["legs_left"], 0)

    def test_auto_grade_in_place_of_the_key_changes_none_of_the_four(self):
        before = [self._score(run, case_id) for run, case_id in _FOUR]
        original = rag.key_for_leg

        def via_auto(leg, facts):
            return check_gold.auto_grade(leg, facts)

        rag.key_for_leg = via_auto
        try:
            after = [self._score(run, case_id) for run, case_id in _FOUR]
        finally:
            rag.key_for_leg = original
        for left, right in zip(before, after):
            for name in left:
                self.assertEqual(left[name]["value"], right[name]["value"])

    def test_the_recorded_real_rows_match_their_questions_and_do_not_raise(self):
        seen = 0
        legs_left = 0
        for name in _RUNS:
            records = self.runs[name]
            for case_id, row in self.rows.items():
                record = records[case_id]
                self.assertEqual(record["ticket"], json.loads(row["question"]))
                scored = score_case(row, record)
                legs_left += scored["faithfulness"]["legs_left"]
                seen += 1
        self.assertEqual(seen, 180)
        self.assertEqual(legs_left, 0)

    def test_the_public_scorers_return_the_score_case_value(self):
        row = self.rows["A01"]
        record = self.runs["v1"]["A01"]
        calls = []
        real = rag.score_case

        def wrapped(got_row, got_record):
            calls.append(got_row["case_id"])
            return real(got_row, got_record)

        rag.score_case = wrapped
        try:
            output = _output(row, record)
            metadata = _metadata(row)
            values = [
                rag.context_recall(output, row["ground_truth"], metadata),
                rag.context_precision(output, row["ground_truth"], metadata),
                rag.faithfulness(output, row["ground_truth"], metadata),
                rag.answer_relevancy(output, row["ground_truth"], metadata),
            ]
        finally:
            rag.score_case = real
        self.assertEqual(calls, ["A01", "A01", "A01", "A01"])
        for value in values:
            self.assertIsInstance(value, float)
            self.assertNotIsInstance(value, bool)
        missing = self.runs["v1"]["B05"]
        none_value = rag.faithfulness(_output(self.rows["B05"], missing), "", _metadata(self.rows["B05"]))
        self.assertIsNone(none_value)


class ScorerRuleTests(unittest.TestCase):
    def test_the_hand_example(self):
        row = {"contexts": [
            {"leg": 1, "kind": "event", "event_id": "E1"},
            {"leg": 1, "kind": "rule", "topic": "moneyline_3way"},
        ], "legs": []}
        record = {"tools": [
            {"name": "lookup_rule", "args": {"topic": "match_result"},
             "result": {"error": "UNKNOWN_TOPIC"}},
            {"name": "get_match_facts", "result": {"event_id": "E1"}},
            {"name": "lookup_rule", "args": {"topic": "other"},
             "result": {"topic": "moneyline_3way", "rule": "text"}},
        ], "ticket": {"legs": []}, "final": None}
        scored = score_case(row, record)
        self.assertEqual(scored["context_recall"]["value"], 1.0)
        self.assertEqual(
            scored["context_precision"]["value"], (1.0 / 2.0 + 2.0 / 3.0) / 2.0)
        self.assertEqual("%.3f" % scored["context_precision"]["value"], "0.583")

    def test_a_record_with_no_tools_scores_recall_zero(self):
        row = {"contexts": [
            {"leg": 1, "kind": "event", "event_id": "E1"},
            {"leg": 1, "kind": "rule", "topic": "moneyline_3way"},
        ], "legs": [{"leg": 1}]}
        record = {"tools": [], "ticket": {"legs": [{"leg": 1}]}, "final": None}
        self.assertEqual(score_case(row, record)["context_recall"]["value"], 0.0)
        self.assertEqual(retrieved_items(record), [])

    def test_two_legs_on_one_match_need_its_event_once(self):
        row = {"contexts": [
            {"leg": 1, "kind": "event", "event_id": "E1"},
            {"leg": 2, "kind": "event", "event_id": "E1"},
            {"leg": 1, "kind": "rule", "topic": "totals"},
        ]}
        self.assertEqual(
            needed_items(row), [("event", "E1"), ("rule", "totals")])

    def test_a_repeated_pair_is_dropped_and_find_match_is_not_an_item(self):
        record = {"tools": [
            {"name": "find_match", "result": {"candidates": [{"event_id": "E1"}]}},
            {"name": "get_match_facts", "result": {"event_id": "E1"}},
            {"name": "get_match_facts", "result": {"event_id": "E1"}},
            {"name": "settle_ticket", "result": {"ticket_result": "LOSS"}},
        ]}
        self.assertEqual(retrieved_items(record), [("event", "E1")])
        row = {"contexts": [{"leg": 1, "kind": "event", "event_id": "E1"}], "legs": []}
        self.assertEqual(score_case(row, record)["context_recall"]["value"], 1.0)
        # The candidate is the only retrieval. Counting it would make recall 1.
        only_find = {"tools": [
            {"name": "find_match", "result": {"candidates": [{"event_id": "E1"}]}},
        ]}
        self.assertEqual(retrieved_items(only_find), [])
        self.assertEqual(score_case(row, only_find)["context_recall"]["value"], 0.0)

    def test_a_rule_item_uses_the_resolved_topic(self):
        row = {"contexts": [{"leg": None, "kind": "rule", "topic": "moneyline_3way"}], "legs": []}
        record = {"tools": [{
            "name": "lookup_rule",
            "args": {"topic": "match_result"},
            "result": {"topic": "moneyline_3way", "rule": "text"},
        }], "ticket": {"legs": []}, "final": None}
        self.assertEqual(retrieved_items(record), [("rule", "moneyline_3way")])
        self.assertEqual(score_case(row, record)["context_recall"]["value"], 1.0)

    def test_a_rule_error_is_not_relevant(self):
        # The error asked for the needed topic. It is still not relevant.
        row = {"contexts": [{"leg": 1, "kind": "rule", "topic": "moneyline_3way"}], "legs": []}
        record = {"tools": [
            {"name": "lookup_rule", "args": {"topic": "moneyline_3way"},
             "result": {"error": "UNKNOWN_TOPIC"}},
            {"name": "lookup_rule", "args": {"topic": "moneyline_3way"},
             "result": {"topic": "moneyline_3way", "rule": "text"}},
        ], "ticket": {"legs": []}, "final": None}
        self.assertEqual(
            retrieved_items(record),
            [("rule_error", "moneyline_3way"), ("rule", "moneyline_3way")])
        self.assertEqual(score_case(row, record)["context_precision"]["value"], 0.5)
        self.assertEqual(score_case(row, record)["context_recall"]["value"], 1.0)

    def test_a_non_string_rule_error_topic_is_retrieved_and_not_relevant(self):
        # Ruling 40. A topic that is not a string is still a retrieved item, and
        # it is not relevant. The id is json.dumps of the topic, keys sorted, or
        # of null when the topic is missing, so the pair is hashable and stable.
        row = {"contexts": [{"leg": 1, "kind": "rule", "topic": "moneyline_3way"}], "legs": []}
        topic = {"b": 1, "a": 2}
        record = {"tools": [
            {"name": "lookup_rule", "args": {"topic": topic}, "result": {"error": "bad"}},
            {"name": "lookup_rule", "args": {}, "result": {"error": "bad"}},
            {"name": "lookup_rule", "args": {"topic": 3}, "result": {"error": "bad"}},
            {"name": "lookup_rule", "args": {"topic": "moneyline_3way"},
             "result": {"topic": "moneyline_3way", "rule": "text"}},
        ], "ticket": {"legs": []}, "final": None}
        dumped = json.dumps(topic, sort_keys=True)
        self.assertEqual(retrieved_items(record), [
            ("rule_error", dumped),
            ("rule_error", "null"),
            ("rule_error", "3"),
            ("rule", "moneyline_3way"),
        ])
        scored = score_case(row, record)
        self.assertEqual(scored["context_precision"]["value"], 0.25)
        self.assertEqual(scored["context_recall"]["value"], 1.0)
        record["tools"][0]["args"]["topic"] = {"a": 2, "b": 1}
        self.assertEqual(retrieved_items(record)[0], ("rule_error", dumped))

    def test_a_facts_result_with_an_error_or_no_event_gives_no_item(self):
        record = {"tools": [
            {"name": "get_match_facts", "result": {"error": "RuntimeError", "event_id": "E1"}},
            {"name": "get_match_facts", "result": {"home": "A"}},
        ]}
        self.assertEqual(retrieved_items(record), [])

    def test_a_grade_made_with_no_facts_is_unsupported_unless_it_is_needs_human(self):
        row = {"legs": [{"leg": 1, "market": "Moneyline", "selection": "Home"}], "contexts": [
            {"leg": 1, "kind": "rule", "topic": "moneyline_3way"},
        ]}
        bare = {
            "tools": [],
            "ticket": {"legs": [{"leg": 1, "market": "Moneyline", "home": "A", "away": "B"}]},
            "final": {"legs": [{"leg": 1, "result": "W", "evidence": "guessed"}],
                      "ticket_result": "WIN"},
        }
        scored = score_case(row, bare)
        self.assertEqual(scored["faithfulness"]["value"], 0.0)
        self.assertEqual(scored["faithfulness"]["claims"], 1)
        bare["final"]["legs"][0]["result"] = "NEEDS_HUMAN"
        scored = score_case(row, bare)
        self.assertEqual(scored["faithfulness"]["value"], 1.0)

    def test_a_moot_grade_needs_another_committed_l(self):
        rows, runs = _load()
        base = rows["A01"]
        record = copy.deepcopy(runs["v1"]["A01"])
        record["final"]["legs"] = [{"leg": 1, "result": "MOOT", "evidence": "no score cited"}]
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = ["MOOT"]
        alone = score_case(base, record)
        self.assertEqual(alone["faithfulness"]["supported"], 0)
        self.assertEqual(alone["faithfulness"]["claims"], 1)
        row = copy.deepcopy(base)
        second = copy.deepcopy(row["legs"][0])
        second["leg"] = 2
        row["legs"].append(second)
        ticket_leg = copy.deepcopy(record["ticket"]["legs"][0])
        ticket_leg["leg"] = 2
        record["ticket"]["legs"].append(ticket_leg)
        record["final"]["legs"] = [
            {"leg": 1, "result": "MOOT", "evidence": "no score cited"},
            {"leg": 2, "result": "L", "evidence": "no score cited"},
        ]
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = ["MOOT", "L"]
        paired = score_case(row, record)
        self.assertEqual(paired["faithfulness"]["supported"], 1)
        self.assertEqual(paired["faithfulness"]["claims"], 2)

    def test_a_none_key_leaves_the_rate_and_is_counted(self):
        rows, runs = _load()
        row = copy.deepcopy(rows["A01"])
        row["legs"][0]["market"] = "Second Half Total Goals"
        record = runs["v1"]["A01"]
        grade, reason = key_for_leg(row["legs"][0], _best_facts(
            record["ticket"]["legs"][0], _facts_seen(record)))
        self.assertIsNone(grade)
        self.assertEqual(reason, "no branch for this half market")
        scored = score_case(row, record)
        self.assertIsNone(scored["faithfulness"]["value"])
        self.assertEqual(scored["faithfulness"]["claims"], 0)
        self.assertEqual(scored["faithfulness"]["legs_left"], 1)

    def test_a_score_inside_a_date_is_not_a_claim(self):
        rows, runs = _load()
        row = rows["A01"]
        record = copy.deepcopy(runs["v1"]["A01"])
        record["final"]["legs"][0]["evidence"] = "played on 2026-10-14"
        record["final"]["legs"][0]["result"] = "W"
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = ["W"]
        dated = score_case(row, record)
        self.assertEqual(dated["faithfulness"]["claims"], 1)
        self.assertEqual(dated["faithfulness"]["value"], 1.0)
        record["final"]["legs"][0]["evidence"] = "score 2-4 on 2026-10-14"
        cited = score_case(row, record)
        self.assertEqual(cited["faithfulness"]["claims"], 2)
        self.assertEqual(cited["faithfulness"]["supported"], 2)

    def test_an_empty_final_passes_numbering_and_fails_the_leg_count(self):
        row = {"legs": [{"leg": 1, "market": "Moneyline"}], "contexts": []}
        record = {
            "tools": [{"name": "settle_ticket", "result": {"ticket_result": "WIN"}}],
            "ticket": {"legs": [{"leg": 1}]},
            "final": {"legs": [], "ticket_result": "WIN"},
        }
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 0.75)
        record["final"]["legs"] = "not a list"
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 0.75)

    def test_relevancy_reads_the_last_settle_ticket_call(self):
        rows, runs = _load()
        row = rows["A01"]
        record = copy.deepcopy(runs["v1"]["A01"])
        record["tools"].insert(0, {
            "name": "settle_ticket",
            "args": {"leg_results": ["L"]},
            "result": {"ticket_result": "LOSS"},
        })
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 1.0)
        record["tools"].append({
            "name": "settle_ticket",
            "args": {"leg_results": ["L"]},
            "result": {"error": "INVALID_LEG_RESULT"},
        })
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 1.0)

    def test_a_ticket_result_in_another_case_is_not_one_of_the_six(self):
        row = {"legs": [{"leg": 1, "market": "Moneyline"}], "contexts": []}
        record = {
            "tools": [{"name": "settle_ticket", "result": {"ticket_result": "WIN"}}],
            "ticket": {"legs": [{"leg": 1}]},
            "final": {"legs": [{"leg": 1, "result": "W", "evidence": ""}], "ticket_result": "win"},
        }
        # One leg each and numbered hold; the name and the settle_ticket match do not.
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 0.5)
        record["final"]["ticket_result"] = "WIN"
        self.assertEqual(score_case(row, record)["answer_relevancy"]["value"], 1.0)

    def test_a_score_claim_matches_either_way_round(self):
        rows, runs = _load()
        row = rows["A01"]
        record = copy.deepcopy(runs["v1"]["A01"])
        # The facts hold 2-4. The final cites it the other way round.
        record["final"]["legs"][0]["evidence"] = "won 4-2"
        scored = score_case(row, record)
        self.assertEqual((scored["faithfulness"]["claims"], scored["faithfulness"]["supported"]), (2, 2))
        record["final"]["legs"][0]["evidence"] = "won 3-2"
        scored = score_case(row, record)
        self.assertEqual((scored["faithfulness"]["claims"], scored["faithfulness"]["supported"]), (2, 1))

    def test_another_exception_from_key_for_leg_propagates(self):
        rows, runs = _load()
        original = rag.key_for_leg

        def broken(leg, facts):
            raise RuntimeError("not a facts error")

        rag.key_for_leg = broken
        try:
            with self.assertRaises(RuntimeError):
                score_case(rows["A01"], runs["v1"]["A01"])
        finally:
            rag.key_for_leg = original

    def test_recall_and_precision_are_none_when_nothing_is_needed(self):
        scored = score_case({"contexts": [], "legs": []}, {"tools": [], "ticket": {"legs": []}, "final": None})
        self.assertIsNone(scored["context_recall"]["value"])
        self.assertIsNone(scored["context_precision"]["value"])


if __name__ == "__main__":
    unittest.main()
