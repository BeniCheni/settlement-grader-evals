"""Step 6's additions to the seams: follow-ups sent, the raw text, the poison mark."""
import json
import os
import tempfile
import unittest
from unittest import mock

from grader.agent import grade_ticket
from grader.redteam_target import main as target_main
from grader.tracer import Tracer
from scorer.traces import load_run, records_from_otlp


FINAL_A = '{"legs":[{"leg":1,"result":"L","evidence":"a"}],"ticket_result":"LOSS","net":-1,"notes":"a"}'


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


def _unparsed():
    return {"message": {"role": "assistant", "content": "not json at all"}, "done_reason": "stop"}


def _run(replies, followups=(), budgets=None):
    seen = []

    def chat(payload, timeout):
        seen.append(1)
        if len(seen) <= len(replies):
            return replies[len(seen) - 1]
        return {"message": {"role": "assistant", "content": ""}, "done_reason": "length"}

    tracer = Tracer("settlement-grader")
    kwargs = {}
    if budgets is not None:
        kwargs["budgets"] = budgets
    if followups:
        kwargs["followups"] = followups
    with mock.patch("grader.agent._chat", chat):
        result = grade_ticket({"legs": [{"leg": 1}]}, tracer, **kwargs)
    root = next(span for span in tracer.spans if "parentSpanId" not in span)
    return result, root, tracer


class SeamTests(unittest.TestCase):
    def test_no_followups_omits_the_count_and_keeps_final_text(self):
        result, root, tracer = _run((_settle(), _final(FINAL_A)))
        self.assertNotIn("run.followups_sent", root["_attrs"])
        self.assertNotIn("input.followups", root["_attrs"])
        record = records_from_otlp(tracer.to_otlp())[0]
        self.assertNotIn("followups_sent", record)
        self.assertNotIn("followups_total", record)
        self.assertEqual(record["final_text"], FINAL_A)
        self.assertIsNone(result["reason_code"])

    def test_a_null_final_text_is_none_and_does_not_raise(self):
        result, _root, tracer = _run((_settle(), _final("")))
        # An empty completion is EMPTY_FINAL and passes no text.
        self.assertEqual(result["status"], "incomplete")
        record = records_from_otlp(tracer.to_otlp())[0]
        self.assertIsNone(record["final_text"])
        self.assertIsNone(record["final"])

    def test_followups_sent_is_the_number_appended_not_the_lengths(self):
        # One follow-up goes out, and the next turn does not parse. The finals
        # list gains nothing for that turn, so its length is not the count sent.
        result, root, tracer = _run(
            (_settle(), _final(FINAL_A), _unparsed()),
            followups=("again", "later"),
            budgets={"max_turns": 6},
        )
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(root["_attrs"]["run.followups_sent"], 1)
        finals = json.loads(root["_attrs"]["output.final_by_turn"])
        self.assertEqual(len(finals), 1)
        self.assertEqual(len(json.loads(root["_attrs"]["input.followups"])), 2)
        record = records_from_otlp(tracer.to_otlp())[0]
        self.assertEqual(record["followups_sent"], 1)
        self.assertEqual(record["followups_total"], 2)
        self.assertEqual(record["final_text"], "not json at all")

    def test_none_sent_is_zero_and_all_sent_is_the_total(self):
        _result, root, _tracer = _run(
            (_unparsed(),),
            followups=("never",),
            budgets={"max_turns": 4},
        )
        self.assertEqual(root["_attrs"]["run.followups_sent"], 0)
        self.assertEqual(json.loads(root["_attrs"]["output.final_by_turn"]), [])

        _result, root, _tracer = _run(
            (_settle(), _final(FINAL_A), _final(FINAL_A)),
            followups=("once",),
            budgets={"max_turns": 6},
        )
        self.assertEqual(root["_attrs"]["run.followups_sent"], 1)
        self.assertEqual(len(json.loads(root["_attrs"]["output.final_by_turn"])), 2)

    def test_loader_reads_a_recorded_count_from_a_directory(self):
        _result, _root, tracer = _run(
            (_settle(), _final(FINAL_A), _final(FINAL_A)),
            followups=("once",),
            budgets={"max_turns": 6},
        )
        directory = tempfile.mkdtemp()
        path = os.path.join(directory, "settlement-traces.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(tracer.to_otlp(), handle)
        record = load_run(directory)[0]
        self.assertEqual(record["followups_sent"], 1)
        self.assertEqual(record["followups_total"], 1)
        self.assertIn("final_text", record)


class TargetLineTests(unittest.TestCase):
    def test_the_line_marks_only_a_poisoned_call_and_counts_followups(self):
        cases = [{
            "case_id": "S1",
            "source": "synthetic",
            "legs": [{"leg": 1, "selection": "Home"}],
            "expected": {"ticket_result": "LOSS", "net": -1},
            "poison": [{"tool": "lookup_rule", "match": {}, "append_text": " POISON"}],
            "followups": ["why"],
        }]
        replies = [
            _call("lookup_rule", {"topic": "general"}),
            _call("settle_ticket", {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"}),
            _final(FINAL_A),
            _final(FINAL_A),
        ]
        directory = tempfile.mkdtemp()
        cases_path = os.path.join(directory, "cases.json")
        replies_path = os.path.join(directory, "replies.json")
        with open(cases_path, "w", encoding="utf-8") as handle:
            json.dump(cases, handle)
        with open(replies_path, "w", encoding="utf-8") as handle:
            json.dump(replies, handle)
        # Point the target's root at a scratch tree so it does not write this checkout.
        import grader.redteam_target as target
        previous = target.__file__
        target.__file__ = os.path.join(directory, "grader", "redteam_target.py")
        os.makedirs(os.path.join(directory, "grader"))
        os.environ["REDTEAM_RUN_ID"] = "seam-line"
        try:
            from io import StringIO
            from contextlib import redirect_stdout, redirect_stderr
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = target_main(
                    ["--cases", cases_path, "--fixture", replies_path, "S1"])
            self.assertEqual(status, 0, stderr.getvalue())
            line = json.loads(stdout.getvalue())
        finally:
            target.__file__ = previous
            os.environ.pop("REDTEAM_RUN_ID", None)
        self.assertEqual(line["followups_sent"], 1)
        self.assertEqual(line["tools"][0].get("poisoned"), True)
        self.assertNotIn("poisoned", line["tools"][1])
        self.assertEqual([tool["name"] for tool in line["tools"]], ["lookup_rule", "settle_ticket"])


if __name__ == "__main__":
    unittest.main()
