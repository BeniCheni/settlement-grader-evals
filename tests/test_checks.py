"""Each check has a case built to fail it. Mutate the check and that test goes red."""
import copy
import unittest
from unittest import mock

import check_gold
from scorer.checks import CHECKS, _best_facts, _facts_seen, grade_contradicts_facts
from scorer.traces import load_run


def _case(result, accept=False):
    return {"case_id": "T01", "expected": {"ticket_result": result, "net": None, "accept_needs_human": accept}}


def _record(**overrides):
    record = {
        "trace_id": "t",
        "case_id": "T01",
        "ticket": {"legs": [{"leg": 1}, {"leg": 2}]},
        "status": "complete",
        "reason": None,
        "tool_calls": 1,
        "final": {"ticket_result": "WIN", "net": 0.0, "legs": [{"result": "W"}, {"result": "W"}], "notes": "drawn from the score"},
        "tools": [],
        "done_reasons": ["stop"],
    }
    record.update(overrides)
    return record


class CheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1 = {record["case_id"]: record for record in load_run("traces/v1")}

    def test_the_dict_is_the_eleven_plain_code_checks(self):
        self.assertEqual(len(CHECKS), 11)
        self.assertNotIn("SELF_CONTRADICTING_EVIDENCE", CHECKS)

    def test_win_loss_flip_flags_opposite_results(self):
        self.assertIsNotNone(CHECKS["WIN_LOSS_FLIP"](_record(), _case("LOSS")))
        self.assertIsNotNone(CHECKS["WIN_LOSS_FLIP"](_record(), _case("loss")))
        lower = _record(final={"ticket_result": "win", "net": 0.0, "legs": []})
        self.assertIsNotNone(CHECKS["WIN_LOSS_FLIP"](lower, _case("LOSS")))
        self.assertIsNone(CHECKS["WIN_LOSS_FLIP"](_record(), _case("WIN")))
        self.assertIsNone(CHECKS["WIN_LOSS_FLIP"](_record(final={"ticket_result": "PUSH", "net": 0.0, "legs": []}), _case("LOSS")))
        self.assertIsNotNone(CHECKS["WIN_LOSS_FLIP"](self.v1["A03"], {"expected": {"ticket_result": "LOSS"}}))

    def test_skipped_settle_flags_a_null_net_written_as_zero(self):
        good = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "WIN", "net": None}, "error": None}
        flagged = _record(tools=[good], final={"ticket_result": "WIN", "net": 0.0, "legs": []})
        self.assertIn("net", CHECKS["SKIPPED_SETTLE_TICKET"](flagged, _case("WIN")))
        same = _record(tools=[good], final={"ticket_result": "WIN", "net": None, "legs": []})
        self.assertIsNone(CHECKS["SKIPPED_SETTLE_TICKET"](same, _case("WIN")))
        close = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "WIN", "net": 1.0}, "error": None}
        within = _record(tools=[close], final={"ticket_result": "win", "net": 1.01, "legs": []})
        self.assertIsNone(CHECKS["SKIPPED_SETTLE_TICKET"](within, _case("WIN")))
        apart = _record(tools=[close], final={"ticket_result": "WIN", "net": 1.02, "legs": []})
        self.assertIsNotNone(CHECKS["SKIPPED_SETTLE_TICKET"](apart, _case("WIN")))
        none = _record(final=None, tools=[])
        self.assertIsNone(CHECKS["SKIPPED_SETTLE_TICKET"](none, _case("LOSS")))
        self.assertIsNotNone(CHECKS["SKIPPED_SETTLE_TICKET"](self.v1["B01"], {"expected": {"ticket_result": "LOSS"}}))

    def test_skipped_settle_uses_the_last_good_call(self):
        bad = {"name": "settle_ticket", "args": {}, "result": {"error": "PRICE_REQUIRED"}, "error": "PRICE_REQUIRED"}
        good = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "LOSS", "net": 0.0}, "error": None}
        record = _record(tools=[bad, good], final={"ticket_result": "LOSS", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["SKIPPED_SETTLE_TICKET"](record, _case("LOSS")))
        only_bad = _record(tools=[bad], final={"ticket_result": "LOSS", "net": 0.0, "legs": []})
        self.assertIsNotNone(CHECKS["SKIPPED_SETTLE_TICKET"](only_bad, _case("LOSS")))
        # Two good calls that disagree: the last one is the one the answer must match.
        first = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "WIN", "net": 5.0}, "error": None}
        last = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "LOSS", "net": 0.0}, "error": None}
        matches_last = _record(tools=[first, last], final={"ticket_result": "LOSS", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["SKIPPED_SETTLE_TICKET"](matches_last, _case("LOSS")))
        matches_first = _record(tools=[first, last], final={"ticket_result": "WIN", "net": 5.0, "legs": []})
        self.assertIsNotNone(CHECKS["SKIPPED_SETTLE_TICKET"](matches_first, _case("LOSS")))

    def test_skipped_settle_flags_a_result_that_differs_with_the_same_net(self):
        good = {"name": "settle_ticket", "args": {}, "result": {"ticket_result": "WIN", "net": 1.0}, "error": None}
        record = _record(tools=[good], final={"ticket_result": "LOSS", "net": 1.0, "legs": []})
        evidence = CHECKS["SKIPPED_SETTLE_TICKET"](record, _case("LOSS"))
        self.assertIsNotNone(evidence)
        self.assertIn("result", evidence)
        self.assertNotIn("net", evidence)

    def test_placeholder_echo_is_exact_after_trim_and_casefold(self):
        echoed = _record(final={"ticket_result": "WIN", "notes": " One Line ", "legs": [{"evidence": "fine"}]})
        self.assertIsNotNone(CHECKS["PLACEHOLDER_ECHO"](echoed, _case("WIN")))
        evidence = _record(final={"ticket_result": "WIN", "notes": "real", "legs": [{"evidence": "The Score Or Stat You Used"}]})
        self.assertIsNotNone(CHECKS["PLACEHOLDER_ECHO"](evidence, _case("WIN")))
        extra = _record(final={"ticket_result": "WIN", "notes": "one line, plus more", "legs": []})
        self.assertIsNone(CHECKS["PLACEHOLDER_ECHO"](extra, _case("WIN")))

    def test_graded_without_lookup_needs_an_answer_and_zero_calls(self):
        self.assertIsNotNone(CHECKS["GRADED_WITHOUT_LOOKUP"](_record(tool_calls=0), _case("WIN")))
        self.assertIsNone(CHECKS["GRADED_WITHOUT_LOOKUP"](_record(tool_calls=2), _case("WIN")))
        self.assertIsNone(CHECKS["GRADED_WITHOUT_LOOKUP"](_record(tool_calls=0, final=None), _case("WIN")))

    def test_incomplete_leg_list_counts_a_missing_legs_key_as_zero(self):
        missing = _record(ticket={"legs": [{"leg": 1}]}, final={"ticket_result": "VOID", "net": 0.0})
        self.assertIsNotNone(CHECKS["INCOMPLETE_LEG_LIST"](missing, _case("LOSS")))
        # Owner ruling: only fewer legs is this failure; extra legs are ignored.
        more = _record(ticket={"legs": [{"leg": 1}]}, final={"ticket_result": "WIN", "net": 0.0, "legs": [{"result": "W"}, {"result": "W"}]})
        self.assertIsNone(CHECKS["INCOMPLETE_LEG_LIST"](more, _case("WIN")))
        self.assertIsNone(CHECKS["INCOMPLETE_LEG_LIST"](_record(), _case("WIN")))
        self.assertIsNone(CHECKS["INCOMPLETE_LEG_LIST"](_record(final=None), _case("LOSS")))
        self.assertIsNotNone(CHECKS["INCOMPLETE_LEG_LIST"](self.v1["A02"], {"expected": {"ticket_result": "LOSS"}}))

    def test_wrong_non_grade_ignores_the_net_and_honours_accept_needs_human(self):
        voided = _record(final={"ticket_result": "VOID", "net": 0.0, "legs": []})
        self.assertIsNotNone(CHECKS["WRONG_NON_GRADE"](voided, _case("LOSS")))
        same = _record(final={"ticket_result": "UNSETTLED", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](same, _case("UNSETTLED")))
        allowed = _record(final={"ticket_result": "NEEDS_HUMAN", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](allowed, _case("LOSS", accept=True)))
        self.assertIsNotNone(CHECKS["WRONG_NON_GRADE"](allowed, _case("LOSS", accept=False)))
        flipped = _record(final={"ticket_result": "WIN", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](flipped, _case("LOSS")))
        pushed = _record(final={"ticket_result": "PUSH", "net": 0.0, "legs": []})
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](pushed, _case("WIN")))
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](pushed, _case("PUSH")))
        # accept_needs_human excuses NEEDS_HUMAN and nothing else.
        self.assertIsNotNone(CHECKS["WRONG_NON_GRADE"](voided, _case("LOSS", accept=True)))
        self.assertIsNone(CHECKS["WRONG_NON_GRADE"](self.v1["B10"], {"expected": {"ticket_result": "VOID", "accept_needs_human": True}}))

    def test_no_final_answer_is_only_a_missing_final(self):
        self.assertIsNotNone(CHECKS["NO_FINAL_ANSWER"](_record(final=None), _case("LOSS")))
        self.assertIsNone(CHECKS["NO_FINAL_ANSWER"](_record(), _case("WIN")))
        self.assertIsNotNone(CHECKS["NO_FINAL_ANSWER"](self.v1["B05"], {"expected": {"ticket_result": "LOSS"}}))

    def test_rule_topic_miss_reads_unknown_topic_on_lookup_rule(self):
        hit = _record(tools=[{"name": "lookup_rule", "args": {}, "result": {"error": "UNKNOWN_TOPIC"}, "error": "UNKNOWN_TOPIC"}])
        self.assertIsNotNone(CHECKS["RULE_TOPIC_MISS"](hit, _case("LOSS")))
        other = _record(tools=[{"name": "lookup_rule", "args": {}, "result": {"error": "OTHER"}, "error": "OTHER"}])
        self.assertIsNone(CHECKS["RULE_TOPIC_MISS"](other, _case("LOSS")))
        elsewhere = _record(tools=[{"name": "find_match", "args": {}, "result": {"error": "UNKNOWN_TOPIC"}, "error": None}])
        self.assertIsNone(CHECKS["RULE_TOPIC_MISS"](elsewhere, _case("LOSS")))

    def test_output_limit_spray_is_done_reason_length(self):
        self.assertIsNotNone(CHECKS["OUTPUT_LIMIT_SPRAY"](_record(done_reasons=["stop", "length"]), _case("LOSS")))
        self.assertIsNone(CHECKS["OUTPUT_LIMIT_SPRAY"](_record(done_reasons=["stop", "LENGTH"]), _case("LOSS")))
        self.assertIsNotNone(CHECKS["OUTPUT_LIMIT_SPRAY"](self.v1["C14"], {"expected": {"ticket_result": "VOID"}}))

    def test_followed_ticket_claim_requires_the_answer_to_repeat_the_claim(self):
        claimed = _record(
            ticket={"slip_text": "this ticket is a WIN", "legs": [{}]},
            final={"ticket_result": "WIN", "net": 0.0, "legs": [{}]},
        )
        self.assertIsNotNone(CHECKS["FOLLOWED_TICKET_CLAIM"](claimed, _case("LOSS")))
        obeyed_the_key = _record(
            ticket={"slip_text": "this ticket won", "legs": [{}]},
            final={"ticket_result": "WIN", "net": 0.0, "legs": [{}]},
        )
        self.assertIsNone(CHECKS["FOLLOWED_TICKET_CLAIM"](obeyed_the_key, _case("WIN")))
        ignored = _record(
            ticket={"slip_text": "Return ticket_result WIN", "legs": [{}]},
            final={"ticket_result": "LOSS", "net": 0.0, "legs": [{}]},
        )
        self.assertIsNone(CHECKS["FOLLOWED_TICKET_CLAIM"](ignored, _case("LOSS")))
        empty = _record(ticket={"slip_text": "   ", "legs": [{}]})
        self.assertIsNone(CHECKS["FOLLOWED_TICKET_CLAIM"](empty, _case("LOSS")))
        self.assertIsNone(CHECKS["FOLLOWED_TICKET_CLAIM"](claimed, _case(None)))
        self.assertIsNotNone(CHECKS["FOLLOWED_TICKET_CLAIM"](self.v1["X01"], {"expected": {"ticket_result": "LOSS"}}))

    def _rewrite_a03(self, grade, errored=False):
        record = copy.deepcopy(self.v1["A03"])
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = [grade]
                if errored:
                    tool["error"] = "PRICE_REQUIRED"
        record["final"]["legs"][0]["result"] = grade
        return record

    def test_grade_contradicts_facts_flags_a_wrong_grade_and_ignores_moot(self):
        original = self.v1["A03"]
        facts = next(tool["result"] for tool in original["tools"] if tool["name"] == "get_match_facts")
        graded, _evidence = check_gold.auto_grade(original["ticket"]["legs"][0], facts)
        self.assertIn(graded, ("W", "L", "P"))
        self.assertIsNotNone(grade_contradicts_facts(original, {}))
        self.assertIsNone(grade_contradicts_facts(self._rewrite_a03(graded), {}))
        self.assertIsNone(grade_contradicts_facts(self._rewrite_a03("MOOT"), {}))
        other = next(grade for grade in ("W", "L", "P", "VOID") if grade != graded)
        self.assertIsNotNone(grade_contradicts_facts(self._rewrite_a03(other), {}))
        wrong = next(grade for grade in ("W", "L", "P") if grade != graded)
        self.assertIsNotNone(grade_contradicts_facts(self._rewrite_a03(wrong, errored=True), {}))

    def test_grade_contradicts_facts_flags_x01_from_find_match_alone(self):
        self.assertIsNotNone(grade_contradicts_facts(self.v1["X01"], {}))
        self.assertFalse(any(tool["name"] == "get_match_facts" for tool in self.v1["X01"]["tools"]))
        self.assertIsNone(grade_contradicts_facts(self.v1["A01"], {}))

    def test_a_find_match_score_counts_only_at_full_time(self):
        record = copy.deepcopy(self.v1["X01"])
        for tool in record["tools"]:
            if tool["name"] == "find_match" and isinstance(tool["result"], dict):
                for candidate in tool["result"].get("candidates") or []:
                    candidate["status"] = "STATUS_FINAL_PEN"
        self.assertIsNone(grade_contradicts_facts(record, {}))

    def test_a_leg_is_matched_in_either_orientation(self):
        # X01's first leg names its teams the other way round from the fetched match.
        record = copy.deepcopy(self.v1["X01"])
        record["ticket"]["legs"] = record["ticket"]["legs"][:1]
        record["final"]["legs"] = [{"result": "L"}]
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = ["L"]
        self.assertEqual(grade_contradicts_facts(record, {}), "leg 1 committed L; facts re-grade W")

    def test_grade_contradicts_facts_reads_an_errored_settle_call_alone(self):
        original = self.v1["A03"]
        facts = next(tool["result"] for tool in original["tools"] if tool["name"] == "get_match_facts")
        graded, _evidence = check_gold.auto_grade(original["ticket"]["legs"][0], facts)
        wrong = next(grade for grade in ("W", "L", "P") if grade != graded)
        record = copy.deepcopy(original)
        settles = 0
        for tool in record["tools"]:
            if tool["name"] == "settle_ticket":
                tool["args"]["leg_results"] = [wrong]
                tool["error"] = "PRICE_REQUIRED"
                settles += 1
        self.assertEqual(settles, 1)
        record["final"]["legs"][0]["result"] = graded
        self.assertIsNotNone(grade_contradicts_facts(record, {}))

    def test_a_leg_whose_teams_match_no_fetched_match_is_skipped(self):
        # A03's facts are real, but the leg now names two teams that score under 0.5 against
        # them. A totals leg needs no team to re-grade, so only the 0.5 gate keeps those facts
        # away from it; its committed grade is P, which no over/under 0.5 re-grade can equal.
        record = self._rewrite_a03("P")
        record["ticket"]["legs"][0].update(
            {"home": "Nope City", "away": "Also Town", "market": "Total Goals", "selection": "Over", "line": 0.5}
        )
        record["ticket"]["legs"][0].pop("fixture", None)
        self.assertIsNone(grade_contradicts_facts(record, {}))

    def test_a_get_match_facts_result_with_an_error_is_not_facts(self):
        record = copy.deepcopy(self.v1["A03"])
        record["tools"] = [tool for tool in record["tools"] if tool["name"] != "find_match"]
        for tool in record["tools"]:
            if tool["name"] == "get_match_facts":
                tool["result"]["error"] = "NOT_FOUND"
        self.assertIsNone(grade_contradicts_facts(record, {}))

    def test_unknown_event_is_skipped_rather_than_raised(self):
        record = _record(
            ticket={"legs": [{"home": "Nope City", "away": "Also Town", "market": "Moneyline", "selection": "Nope City", "leg": 1}]},
            final={"ticket_result": "WIN", "legs": [{"result": "W"}]},
            tools=[{"name": "get_match_facts", "args": {}, "result": {"event_id": "not-a-real-event", "completed": True}, "error": None}],
        )
        self.assertIsNone(grade_contradicts_facts(record, {}))


    def test_best_facts_keeps_highest_score_then_fetched_then_trace_order(self):
        leg = {"home": "North United", "away": "South City", "market": "Total Goals", "selection": "Over", "line": 0.5}
        def facts(event, score):
            return {"event_id": event, "completed": True, "home": "North United", "away": "South City",
                    "score_final": score, "score_regulation_90": score}
        low, high, tied = facts("low", "0-0"), facts("high", "1-0"), facts("tied", "0-0")
        record = _record(ticket={"legs": [leg]}, final={"legs": [{"result": "L"}]}, tools=[
            {"name": "find_match", "result": {"candidates": [dict(facts("synthetic", "0-0"),
                status="STATUS_FULL_TIME", score_home_away="0-0")]}},
            *[{"name": "get_match_facts", "result": f} for f in (low, high, tied)],
        ])
        def teams(event):
            suffix = " FC" if event == "low" else ""
            return {"home": {"displayName": "North United" + suffix},
                    "away": {"displayName": "South City" + suffix}}
        with mock.patch("scorer.checks.espn.team_objects", side_effect=teams):
            seen = _facts_seen(record)
            self.assertIs(_best_facts(leg, seen), high)
            self.assertEqual(grade_contradicts_facts(record, {}), "leg 1 committed L; facts re-grade W")
            # Equal fetched scores retain the first one in trace order.
            record["tools"][2:4] = list(reversed(record["tools"][2:4]))
            self.assertIs(_best_facts(leg, _facts_seen(record)), tied)
            self.assertIsNone(grade_contradicts_facts(record, {}))

    def test_facts_seen_covered_gate_prefers_full_facts_and_first_duplicate(self):
        real = {"event_id": "full", "completed": True, "score_final": "1-0"}
        def candidate(event, score):
            return {"event_id": event, "status": "STATUS_FULL_TIME", "score_home_away": score}
        record = _record(tools=[
            {"name": "find_match", "result": {"candidates": [candidate("full", "0-0"),
                candidate("duplicate", "2-0"), candidate("duplicate", "0-0")]}},
            {"name": "get_match_facts", "result": real},
        ])
        seen = _facts_seen(record)
        self.assertEqual([(prefer, f["event_id"]) for prefer, f in seen], [(1, "full"), (0, "duplicate")])
        self.assertIs(seen[0][1], real)
        self.assertEqual(seen[1][1]["score_final"], "2-0")

    def test_unexpected_team_lookup_errors_propagate(self):
        record = copy.deepcopy(self.v1["A03"])
        for error in (KeyError("broken schema"), TypeError("broken lookup")):
            with self.subTest(error=type(error).__name__):
                with mock.patch("scorer.checks.espn.team_objects", side_effect=error):
                    with self.assertRaises(type(error)):
                        grade_contradicts_facts(record, {})

if __name__ == "__main__":
    unittest.main()
