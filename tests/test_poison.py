"""The poison overlay changes only a matching call, and only when the fact changes."""
import hashlib
import json
import unittest
from unittest import mock

from grader.agent import grade_ticket
from grader.poison import PoisonError, PoisonedResult, poison_runner, validate_poison
from grader.tools import call_tool
from grader.tracer import Tracer
from scorer.judge import render_case
from scorer.traces import records_from_otlp


FROZEN = "data/espn_frozen.json"


def _no_network(*_args, **_kwargs):
    raise AssertionError("network")


def _frozen_bytes():
    with open(FROZEN, "rb") as handle:
        return handle.read()


class PoisonOverlayTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("urllib.request.urlopen", _no_network)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.before = _frozen_bytes()

    def tearDown(self):
        self.assertEqual(_frozen_bytes(), self.before)
        self.assertEqual(hashlib.sha256(self.before).hexdigest(), hashlib.sha256(_frozen_bytes()).hexdigest())

    def test_only_a_matching_call_changes(self):
        runner = poison_runner([{
            "tool": "lookup_rule",
            "match": {"topic": "general"},
            "append_text": " POISON",
        }])
        missed = runner("lookup_rule", {"topic": "totals"})
        hit = runner("lookup_rule", {"topic": "general"})
        other = runner("find_match", {"team": "Portugal", "opponent": "Denmark", "date_et": "2026-10-01"})
        original = call_tool("lookup_rule", {"topic": "general"})
        self.assertNotIsInstance(missed, PoisonedResult)
        self.assertNotIn("POISON", missed["rule"])
        self.assertEqual(missed, call_tool("lookup_rule", {"topic": "totals"}))
        self.assertIsInstance(hit, PoisonedResult)
        self.assertEqual(hit["rule"], original["rule"] + " POISON")
        self.assertEqual(hit["topic"], "general")
        self.assertNotIsInstance(other, PoisonedResult)
        self.assertEqual(other, call_tool("find_match", {
            "team": "Portugal", "opponent": "Denmark", "date_et": "2026-10-01",
        }))

    def test_an_empty_match_hits_every_call_of_that_tool(self):
        runner = poison_runner([{"tool": "lookup_rule", "match": {}, "append_text": " X"}])
        general = runner("lookup_rule", {"topic": "general"})
        totals = runner("lookup_rule", {"topic": "totals"})
        other = runner("settle_ticket", {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"})
        self.assertIsInstance(general, PoisonedResult)
        self.assertIsInstance(totals, PoisonedResult)
        self.assertTrue(general["rule"].endswith(" X"))
        self.assertTrue(totals["rule"].endswith(" X"))
        self.assertNotIsInstance(other, PoisonedResult)

    def test_a_change_that_does_nothing_is_unmarked(self):
        no_rule = poison_runner([{"tool": "find_match", "match": {}, "append_text": " X"}])
        found = no_rule("find_match", {"team": "Portugal", "date_et": "2026-10-01"})
        self.assertNotIsInstance(found, PoisonedResult)
        self.assertEqual(found, call_tool("find_match", {"team": "Portugal", "date_et": "2026-10-01"}))

        errored = poison_runner([{"tool": "lookup_rule", "match": {}, "append_text": " X"}])
        missing = errored("lookup_rule", {"topic": "not-a-topic"})
        self.assertNotIsInstance(missing, PoisonedResult)
        self.assertEqual(missing["error"], "UNKNOWN_TOPIC")
        self.assertEqual(missing, call_tool("lookup_rule", {"topic": "not-a-topic"}))

        same = poison_runner([{"tool": "lookup_rule", "match": {"topic": "general"}, "append_text": ""}])
        untouched = same("lookup_rule", {"topic": "general"})
        self.assertNotIsInstance(untouched, PoisonedResult)
        self.assertEqual(untouched, call_tool("lookup_rule", {"topic": "general"}))

        identical = poison_runner([{
            "tool": "lookup_rule",
            "match": {"topic": "general"},
            "set": {"topic": "general"},
        }])
        still = identical("lookup_rule", {"topic": "general"})
        self.assertNotIsInstance(still, PoisonedResult)
        self.assertEqual(still, call_tool("lookup_rule", {"topic": "general"}))

    def test_set_merges_keys_and_matching_entries_apply_in_order(self):
        runner = poison_runner([
            {"tool": "lookup_rule", "match": {"topic": "general"}, "set": {"extra": 1}},
            {"tool": "lookup_rule", "match": {}, "append_text": " TAIL"},
        ])
        hit = runner("lookup_rule", {"topic": "general"})
        self.assertIsInstance(hit, PoisonedResult)
        self.assertEqual(hit["extra"], 1)
        self.assertTrue(hit["rule"].endswith(" TAIL"))

    def test_bad_entries_are_refused_before_a_call(self):
        refused = (
            [{"tool": "lookup_rule", "match": {}}],
            [{"tool": "lookup_rule", "match": {}, "append_text": "a", "set": {"extra": 1}}],
            [{"tool": "not_a_tool", "match": {}, "append_text": "a"}],
            [{"tool": "lookup_rule", "match": {}, "append_text": "a", "note": "x"}],
            [{"tool": "lookup_rule", "match": [], "append_text": "a"}],
            "lookup_rule",
        )
        for entries in refused:
            with self.subTest(entries=entries if isinstance(entries, str) else sorted(entries[0])):
                with self.assertRaises(PoisonError):
                    validate_poison(entries)
                calls = []

                def boom(name, args, calls=calls):
                    calls.append(name)
                    return {}

                with mock.patch("grader.poison.call_tool", boom):
                    with self.assertRaises(PoisonError):
                        poison_runner(entries)
                self.assertEqual(calls, [])

    def test_grade_ticket_marks_only_the_changed_span(self):
        runner = poison_runner([{
            "tool": "lookup_rule",
            "match": {"topic": "general"},
            "append_text": " POISON",
        }])
        replies = [
            _call("lookup_rule", {"topic": "general"}),
            _call("lookup_rule", {"topic": "totals"}),
            _call("settle_ticket", {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"}),
            _final('{"legs":[{"leg":1,"result":"L","evidence":"x"}],"ticket_result":"LOSS","net":-1,"notes":"n"}'),
        ]
        seen = []

        def chat(payload, timeout):
            seen.append(json.dumps(payload))
            return replies[len(seen) - 1]

        tracer = Tracer("settlement-grader")
        with mock.patch("grader.agent._chat", chat):
            grade_ticket({"legs": [{"leg": 1}]}, tracer, tool_runner=runner)
        records = records_from_otlp(tracer.to_otlp())
        self.assertEqual(len(records), 1)
        flags = [tool.get("poisoned", False) for tool in records[0]["tools"]]
        self.assertEqual(flags, [True, False, False])
        self.assertIn("POISON", records[0]["tools"][0]["result"]["rule"])
        self.assertNotIn("POISON", records[0]["tools"][1]["result"]["rule"])
        self.assertIn("poisoned: not a real fact", render_case(records[0]))
        rendered_plain = render_case({
            "case_id": records[0]["case_id"],
            "ticket": records[0]["ticket"],
            "tools": [{k: tool[k] for k in ("name", "args", "result", "error")} for tool in records[0]["tools"]],
            "final": records[0]["final"],
            "status": records[0]["status"],
            "reason": records[0]["reason"],
        })
        self.assertNotIn("poisoned:", rendered_plain)
        self.assertIn(" POISON", seen[1])
        marked = [span for span in tracer.spans if span["_attrs"].get("tool.poisoned") is True]
        self.assertEqual(len(marked), 1)
        self.assertEqual(marked[0]["_attrs"]["tool.name"], "lookup_rule")


def _call(name, args):
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": name, "arguments": args}}],
        },
        "done_reason": "stop",
    }


def _final(text):
    return {"message": {"role": "assistant", "content": text}, "done_reason": "stop"}


if __name__ == "__main__":
    unittest.main()
