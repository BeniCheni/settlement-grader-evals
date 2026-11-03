"""Follow-up turns share the budgets and record every final given so far."""
import json
import unittest
from unittest import mock

from grader.agent import grade_ticket
from grader.tracer import Tracer


FINAL_A = '{"legs":[{"leg":1,"result":"L","evidence":"a"}],"ticket_result":"LOSS","net":-1,"notes":"a"}'
FINAL_B = '{"legs":[{"leg":1,"result":"W","evidence":"b"}],"ticket_result":"WIN","net":1,"notes":"b"}'


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


def _settle():
    return _call("settle_ticket", {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"})


def _run(replies, followups=(), budgets=None, pass_followups=True):
    seen = []

    def chat(payload, timeout):
        # grade_ticket keeps mutating the same messages list, so snapshot now.
        seen.append(json.loads(json.dumps(payload)))
        if len(seen) <= len(replies):
            return replies[len(seen) - 1]
        return {"message": {"role": "assistant", "content": ""}, "done_reason": "length"}

    tracer = Tracer("settlement-grader")
    kwargs = {"budgets": budgets}
    if pass_followups:
        kwargs["followups"] = followups
    with mock.patch("grader.agent._chat", chat):
        result = grade_ticket({"legs": [{"leg": 1}]}, tracer, **kwargs)
    root = next(span for span in tracer.spans if "parentSpanId" not in span)
    return seen, result, root["_attrs"]


class FollowupTests(unittest.TestCase):
    def test_empty_followups_add_no_keys_and_match_the_default(self):
        replies = (_settle(), _final(FINAL_A))
        default_seen, default_result, default_attrs = _run(replies, pass_followups=False)
        empty_seen, empty_result, empty_attrs = _run(replies, followups=())
        self.assertEqual([json.dumps(payload) for payload in empty_seen],
                         [json.dumps(payload) for payload in default_seen])
        self.assertNotIn("input.followups", default_attrs)
        self.assertNotIn("output.final_by_turn", default_attrs)
        self.assertNotIn("input.followups", empty_attrs)
        self.assertNotIn("output.final_by_turn", empty_attrs)
        self.assertEqual(default_result["final"]["ticket_result"], "LOSS")
        self.assertEqual(empty_result["status"], "complete")

    def test_message_order_and_the_last_final(self):
        seen, result, attrs = _run(
            (_settle(), _final(FINAL_A), _final(FINAL_B)),
            followups=("why that grade?",),
            budgets={"max_turns": 4},
        )
        self.assertEqual(len(seen), 3)
        messages = seen[2]["messages"]
        self.assertEqual(messages[-2]["role"], "assistant")
        self.assertEqual(messages[-2]["content"], FINAL_A)
        self.assertEqual(messages[-1], {"role": "user", "content": "why that grade?"})
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["final"]["notes"], "b")
        self.assertEqual(json.loads(attrs["output.final"])["notes"], "b")
        self.assertEqual(
            [item["notes"] for item in json.loads(attrs["output.final_by_turn"])],
            ["a", "b"],
        )
        self.assertEqual(json.loads(attrs["input.followups"]), ["why that grade?"])
        self.assertEqual(result["tool_calls"], 1)

    def test_a_followup_is_not_sent_after_a_budget_runs_out(self):
        seen, result, attrs = _run(
            (_call("lookup_rule", {"topic": "general"}),),
            followups=("still there",),
            budgets={"max_tool_calls": 0},
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["reason_code"], "TOOL_CALL_LIMIT")
        self.assertIsNone(result["final"])
        self.assertEqual(json.loads(attrs["output.final_by_turn"]), [])
        self.assertNotIn("output.final", attrs)
        blob = json.dumps(seen)
        self.assertNotIn("still there", blob)

    def test_a_non_complete_followup_turn_keeps_the_finals_so_far(self):
        seen, result, attrs = _run(
            (_settle(), _final(FINAL_A), {
                "message": {"role": "assistant", "content": "cut off"},
                "done_reason": "length",
            }),
            followups=("again",),
            budgets={"max_turns": 4},
        )
        self.assertEqual(len(seen), 3)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["reason_code"], "NON_NORMAL_DONE_REASON")
        self.assertEqual(result["final"]["notes"], "a")
        self.assertEqual(json.loads(attrs["output.final"])["notes"], "a")
        self.assertEqual(attrs["run.status"], "incomplete")
        self.assertEqual(attrs["run.reason_code"], "NON_NORMAL_DONE_REASON")
        self.assertEqual(len(json.loads(attrs["output.final_by_turn"])), 1)

    def test_completion_on_the_last_turn_does_not_send_the_next_string(self):
        seen, result, attrs = _run(
            (_settle(), _final(FINAL_A)),
            followups=("not sent", "also not"),
            budgets={"max_turns": 2},
        )
        self.assertEqual(len(seen), 2)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["reason_code"], None)
        self.assertEqual(result["turns"], 2)
        self.assertEqual(result["final"]["notes"], "a")
        blob = json.dumps(seen)
        self.assertNotIn("not sent", blob)
        self.assertEqual(json.loads(attrs["input.followups"]), ["not sent", "also not"])
        self.assertEqual(len(json.loads(attrs["output.final_by_turn"])), 1)

    def test_any_other_ending_does_not_send_a_followup(self):
        seen, result, attrs = _run(
            (_final(FINAL_A),),
            followups=("later",),
            budgets={"max_turns": 4},
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["reason_code"], "PREMATURE_FINAL")
        self.assertEqual(result["final"]["notes"], "a")
        self.assertNotIn("later", json.dumps(seen))
        self.assertEqual(len(json.loads(attrs["output.final_by_turn"])), 1)

    def test_turns_and_tool_calls_are_not_reset(self):
        seen, result, attrs = _run(
            (_settle(), _final(FINAL_A), _final(FINAL_B)),
            followups=("one", "two"),
            budgets={"max_turns": 3},
        )
        self.assertEqual(result["turns"], 3)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(attrs["run.turns"], 3)
        self.assertEqual(attrs["run.tool_calls"], 1)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["final"]["notes"], "b")
        self.assertNotIn("two", json.dumps(seen))
        self.assertIn("one", json.dumps(seen[2]))


if __name__ == "__main__":
    unittest.main()
