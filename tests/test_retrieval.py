"""The retrieval seam: alias matching, the exact runner, and the empty rule."""
import hashlib
import os
import unittest

from grader.retrieval import (
    ALIASES, disabled_rule_runner, normalise, resolve_topic, rule_runner, words_of,
)
from grader.rules import RULES, lookup_rule
from grader.tools import call_tool


FROZEN = os.path.join("data", "espn_frozen.json")

# The six misses the alias table was written from.
MISSES = {
    "match_result": "moneyline_3way",
    "anytime_goalscorer": "goalscorer",
    "total_goals": "totals",
    "both_teams_to_score": "btts",
    "goals": "totals",
    "combo": "parlay_moot",
}


def _frozen_sha256():
    digest = hashlib.sha256()
    with open(FROZEN, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


class AliasTests(unittest.TestCase):
    def test_every_alias_reaches_its_topic(self):
        runner = rule_runner("alias")
        for key, topic in ALIASES.items():
            self.assertEqual(resolve_topic(key), topic)
            hit = runner("lookup_rule", {"topic": key})
            direct = lookup_rule(topic)
            self.assertEqual(set(hit), set(direct))
            self.assertEqual(hit, direct)

    def test_the_six_recorded_misses_reach_their_topics(self):
        runner = rule_runner("alias")
        for key, topic in MISSES.items():
            self.assertEqual(ALIASES[key], topic)
            self.assertEqual(runner("lookup_rule", {"topic": key}), lookup_rule(topic))
        self.assertEqual(resolve_topic("Match-Result"), "moneyline_3way")

    def test_every_rules_key_equals_lookup_rule(self):
        runner = rule_runner("alias")
        for key in RULES:
            self.assertEqual(runner("lookup_rule", {"topic": key}), lookup_rule(key))

    def test_a_tie_or_no_shared_word_is_unknown_byte_for_byte(self):
        runner = rule_runner("alias")
        for key in ("chance", "zzz_qqq", "the_bet_market", None, "", "   "):
            got = runner("lookup_rule", {"topic": key})
            self.assertEqual(got, lookup_rule(key))
            self.assertEqual(got["error"], "UNKNOWN_TOPIC")
            self.assertEqual(set(got), {"error", "available_topics"})

    def test_a_unique_shared_word_resolves(self):
        self.assertEqual(resolve_topic("profit_only"), "profit_boost")
        self.assertEqual(resolve_topic("team"), "team_total")
        self.assertEqual(words_of("the_bet_market"), set())

    def test_normalise_matches_lookup_rule(self):
        self.assertEqual(normalise(None), "")
        self.assertEqual(normalise("  Match-Result "), "match_result")


class RunnerTests(unittest.TestCase):
    def test_exact_results_equal_call_tool_for_every_tool(self):
        runner = rule_runner("exact")
        calls = (
            ("find_match", {"team": "Portugal", "opponent": "Denmark", "date_et": "2026-10-01"}),
            ("get_match_facts", {"event_id": "401861096"}),
            ("lookup_rule", {"topic": "moneyline_3way"}),
            ("settle_ticket", {"leg_results": ["L"], "stake": 5, "stake_kind": "cash"}),
            ("not_a_tool", {}),
            ("lookup_rule", {"topic": None}),
        )
        for name, args in calls:
            self.assertEqual(runner(name, args), call_tool(name, args))

    def test_any_other_mode_raises(self):
        with self.assertRaises(ValueError):
            rule_runner("close")
        with self.assertRaises(ValueError):
            rule_runner("")

    def test_other_tools_are_not_remapped(self):
        runner = rule_runner("alias")
        args = {"event_id": "401861096"}
        self.assertEqual(runner("get_match_facts", args), call_tool("get_match_facts", args))
        self.assertEqual(runner("not_a_tool", {}), call_tool("not_a_tool", {}))

    def test_disabled_lookup_rule_is_an_empty_rule_and_the_file_is_unchanged(self):
        before = _frozen_sha256()
        runner = disabled_rule_runner()
        for topic in (None, "", "Match-Result", "moneyline_3way", "not_a_topic"):
            self.assertEqual(runner("lookup_rule", {"topic": topic}), {
                "topic": normalise(topic),
                "rule": "",
            })
        args = {"event_id": "401861096"}
        self.assertEqual(runner("get_match_facts", args), call_tool("get_match_facts", args))
        self.assertEqual(runner("not_a_tool", {}), call_tool("not_a_tool", {}))
        self.assertEqual(runner("lookup_rule", None), {"topic": "", "rule": ""})
        self.assertEqual(_frozen_sha256(), before)


if __name__ == "__main__":
    unittest.main()
