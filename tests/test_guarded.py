"""grade_ticket_guarded: idle identity, blocks, and a held final that names nothing."""
import json
import os
import tempfile
import unittest
from unittest import mock

from grader.agent import grade_ticket
from grader.guarded import grade_ticket_guarded
from grader.tracer import Tracer
from run_eval import ticket_from_case
from scorer.traces import load_run, records_from_otlp
from tests.test_idle_requests import load_golden, scripted_reply


FINAL = '{"legs":[{"leg":1,"result":"L","evidence":"grader"}],"ticket_result":"LOSS","net":-1,"notes":"grader-note"}'
NEEDLE = "pattern_slip_text_BLOCKER"
REASON = "blocked because slip_text"


def _final(text=FINAL):
    return {"message": {"role": "assistant", "content": text}, "done_reason": "stop"}


def _settle():
    return {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {
                "name": "settle_ticket",
                "arguments": {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"},
            }}],
        },
        "done_reason": "stop",
    }


def _ticket():
    return {"slip_text": "original", "legs": [{"leg": 1, "selection": "original"}]}


def _drive(replies, fn):
    seen = []

    def chat(payload, timeout):
        seen.append(json.loads(json.dumps(payload)))
        if len(seen) <= len(replies):
            return replies[len(seen) - 1]
        return {"message": {"role": "assistant", "content": ""}, "done_reason": "length"}

    tracer = Tracer("settlement-grader")
    with mock.patch("grader.agent._chat", chat):
        result = fn(tracer)
    return seen, result, tracer


def _roots(tracer):
    return [span for span in tracer.spans if "parentSpanId" not in span]


def _names_in(text):
    return NEEDLE in text or REASON in text or "Traceback" in text


class GuardedTests(unittest.TestCase):
    def test_both_empty_matches_grade_ticket_and_the_golden(self):
        case = load_golden()["case"]
        ticket = ticket_from_case(case)

        def run(caller):
            seen = []

            def chat(payload, timeout):
                seen.append(json.dumps(payload))
                return scripted_reply(len(seen) - 1)

            tracer = Tracer("settlement-grader")
            with mock.patch("grader.agent._chat", chat):
                result = caller(ticket, tracer)
            root = _roots(tracer)[0]
            return seen, result, root

        plain_seen, plain, plain_root = run(grade_ticket)
        guarded_seen, guarded, guarded_root = run(
            lambda ticket, tracer: grade_ticket_guarded(ticket, tracer))
        self.assertEqual(plain_seen, load_golden()["requests"])
        self.assertEqual(guarded_seen, plain_seen)
        self.assertEqual(set(plain), set(guarded))
        for key in plain:
            if key in ("trace_id", "wall_clock_s"):
                continue
            self.assertEqual(plain[key], guarded[key], key)
        self.assertNotIn("guardrail.decisions", plain_root["_attrs"])
        self.assertNotIn("guardrail.decisions", guarded_root["_attrs"])

    def test_an_input_block_does_not_call_the_model(self):
        calls = []

        def first(ticket):
            calls.append("first")
            return True, REASON

        def second(ticket):
            calls.append("second")
            return False, "later"

        def chat(payload, timeout):
            raise AssertionError("model")

        ticket = _ticket()
        root_attrs = {"case.id": "G1", "ticket.summary": "one leg", "case.category": "test"}
        tracer = Tracer("settlement-grader")
        with mock.patch("grader.agent._chat", chat):
            result = grade_ticket_guarded(
                ticket, tracer,
                input_guardrails=((NEEDLE, first), ("second", second)),
                output_guardrails=(("output", lambda record: calls.append("output") or (False, "no")),),
                root_attrs=root_attrs, model="qwen3:8b", think=False, options={"temperature": 0},
            )
        self.assertEqual(calls, ["first"])
        self.assertEqual([span["name"] for span in tracer.spans if span["name"] == "llm.generate"], [])
        self.assertEqual(len(_roots(tracer)), 1)
        root = _roots(tracer)[0]
        self.assertEqual(root["name"], "grade_ticket · one leg")
        self.assertEqual(root["status"], {"code": 0, "message": ""})
        self.assertEqual(root["_attrs"]["run.status"], "blocked")
        self.assertEqual(root["_attrs"]["run.reason_code"], "GUARDRAIL_INPUT")
        self.assertEqual(root["_attrs"]["run.tool_calls"], 0)
        self.assertEqual(root["_attrs"]["input.ticket"], json.dumps(ticket, ensure_ascii=False))
        self.assertEqual(root["_attrs"]["gen_ai.request.model"], "qwen3:8b")
        self.assertEqual(root["_attrs"]["gen_ai.request.temperature"], 0)
        self.assertEqual(root["_attrs"]["ollama.think"], False)
        self.assertEqual(root["_attrs"]["case.id"], "G1")
        self._held(result, root, legs=1)
        decisions = json.loads(root["_attrs"]["guardrail.decisions"])
        self.assertEqual([(row["guardrail"], row["side"], row["blocked"]) for row in decisions],
                         [(NEEDLE, "input", True)])
        self.assertEqual(decisions[0]["reason"], REASON)
        self.assertIsInstance(decisions[0]["latency_ms"], int)
        directory = tempfile.mkdtemp()
        with open(os.path.join(directory, "settlement-traces.json"), "w", encoding="utf-8") as handle:
            json.dump(tracer.to_otlp(), handle)
        loaded = load_run(directory)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["status"], "blocked")
        self.assertEqual(loaded[0]["reason"], "GUARDRAIL_INPUT")
        self.assertEqual(loaded[0]["tool_calls"], 0)
        self.assertEqual(loaded[0]["final"]["ticket_result"], "NEEDS_HUMAN")
        self.assertIsNone(loaded[0]["final"]["net"])

    def test_a_mutating_input_guardrail_does_not_change_the_ticket_the_model_sees(self):
        original = _ticket()
        handed = []

        def mutate(ticket):
            handed.append(ticket["slip_text"])
            ticket["slip_text"] = "MUTATED"
            ticket["legs"][0]["selection"] = "MUTATED"
            return False, "pass"

        seen, result, tracer = _drive((_settle(), _final()), lambda tracer: grade_ticket_guarded(
            original, tracer, input_guardrails=(("copy", mutate),)))
        self.assertEqual(original["slip_text"], "original")
        self.assertEqual(original["legs"][0]["selection"], "original")
        self.assertEqual(handed, ["original"])
        user = seen[0]["messages"][1]["content"]
        self.assertIn("original", user)
        self.assertNotIn("MUTATED", user)
        self.assertEqual(result["status"], "complete")

    def test_an_output_block_holds_the_final_and_keeps_the_grader_answer_withheld(self):
        seen_record = {}

        def output(record):
            seen_record["record"] = record
            return True, REASON

        def later(record):
            seen_record["later"] = True
            return False, "no"

        seen, result, tracer = _drive((_settle(), _final()), lambda tracer: grade_ticket_guarded(
            _ticket(), tracer, output_guardrails=((NEEDLE, output), ("later", later))))
        self.assertEqual(len(seen), 2)
        self.assertNotIn("later", seen_record)
        self.assertEqual(seen_record["record"]["final"]["notes"], "grader-note")
        self.assertEqual(seen_record["record"]["status"], "complete")
        again = records_from_otlp(tracer.to_otlp())
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["final"]["notes"], "held for human review")
        self.assertEqual(again[0]["status"], "blocked")
        root = _roots(tracer)[0]
        self.assertEqual(len(_roots(tracer)), 1)
        self.assertEqual(root["status"]["code"], 0)
        withheld = json.loads(root["_attrs"]["output.final_withheld"])
        self.assertEqual(withheld["notes"], "grader-note")
        self.assertEqual(root["_attrs"]["output.final_text"], result["final_text"])
        self.assertNotIn("grader-note", result["final_text"])
        self.assertNotIn("output.final_by_turn", root["_attrs"])
        self.assertNotIn("output.final_by_turn_withheld", root["_attrs"])
        self.assertNotIn("grader", result["final"]["legs"][0]["evidence"])
        self._held(result, root, legs=1)
        self.assertEqual(result["tool_calls"], 1)

    def test_an_output_block_withholds_every_followup_final(self):
        replies = (_settle(), _final(), _final(FINAL.replace("grader-note", "second-note")))
        seen, result, tracer = _drive(replies, lambda tracer: grade_ticket_guarded(
            _ticket(), tracer, followups=("again",),
            output_guardrails=(("hold", lambda record: (True, REASON)),)))
        attrs = _roots(tracer)[0]["_attrs"]
        self.assertEqual(json.loads(attrs["input.followups"]), ["again"])
        self.assertEqual(json.loads(attrs["output.final_by_turn"]), [result["final"]])
        self.assertEqual(json.loads(attrs["output.final"]),
                         json.loads(attrs["output.final_by_turn"])[-1])
        self.assertEqual([item["notes"] for item in
                          json.loads(attrs["output.final_by_turn_withheld"])],
                         ["grader-note", "second-note"])
        self.assertEqual(json.loads(attrs["output.final_withheld"])["notes"], "second-note")
        completions = [span["_attrs"]["gen_ai.completion"] for span in tracer.spans
                       if span["name"] == "llm.generate"]
        self.assertEqual(completions[1:], [FINAL, FINAL.replace("grader-note", "second-note")])
        self.assertEqual(records_from_otlp(tracer.to_otlp())[0]["final"], result["final"])

    def test_followup_keys_are_absent_on_an_input_block(self):
        tracer = Tracer("settlement-grader")
        with mock.patch("grader.agent._chat", side_effect=AssertionError("model")):
            result = grade_ticket_guarded(_ticket(), tracer, followups=("not sent",),
                                         input_guardrails=(("hold", lambda ticket: (True, REASON)),))
        self.assertEqual(result["status"], "blocked")
        attrs = _roots(tracer)[0]["_attrs"]
        for key in ("input.followups", "output.final_by_turn", "output.final_by_turn_withheld"):
            self.assertNotIn(key, attrs)

    def test_an_output_block_on_an_incomplete_run_is_not_an_error_span(self):
        seen, result, tracer = _drive((
            {"message": {"role": "assistant", "content": "cut off"}, "done_reason": "length"},
        ), lambda tracer: grade_ticket_guarded(
            _ticket(), tracer, output_guardrails=(("out", lambda record: (True, REASON)),)))
        root = _roots(tracer)[0]
        self.assertEqual(root["status"], {"code": 0, "message": ""})
        self.assertEqual(root["_attrs"]["run.status"], "blocked")
        self.assertEqual(root["_attrs"]["run.reason_code"], "GUARDRAIL_OUTPUT")
        self.assertNotIn("cut off", result["final_text"])
        self.assertNotIn("cut off", root["_attrs"]["output.final_text"])
        self.assertEqual(json.loads(root["_attrs"]["output.final_withheld"]), None)
        self.assertTrue(any(span["name"] == "llm.generate" for span in tracer.spans))
        self._held(result, root, legs=1)

    def test_the_output_record_is_what_records_from_otlp_returns(self):
        captured = {}
        real = records_from_otlp

        def wrapped(document):
            rows = real(document)
            captured["rows"] = rows
            return rows

        def output(record):
            captured["record"] = record
            return False, "pass"

        with mock.patch("grader.guarded.records_from_otlp", wrapped):
            _drive((_settle(), _final()), lambda tracer: grade_ticket_guarded(
                _ticket(), tracer, output_guardrails=(("see", output),)))
        self.assertEqual(captured["record"]["final"], captured["rows"][0]["final"])
        self.assertEqual(captured["record"]["tools"], captured["rows"][0]["tools"])
        self.assertEqual(captured["record"]["status"], captured["rows"][0]["status"])

    def test_a_raising_guardrail_is_held_closed_and_names_nothing(self):
        def boom(ticket):
            raise RuntimeError("SECRET_TRACEBACK_NEEDLE")

        def later(ticket):
            raise AssertionError("should not run")

        tracer = Tracer("settlement-grader")
        with mock.patch("grader.agent._chat", lambda payload, timeout: (_ for _ in ()).throw(AssertionError("model"))):
            result = grade_ticket_guarded(
                _ticket(), tracer, input_guardrails=(("boom", boom), ("later", later)))
        root = _roots(tracer)[0]
        decisions = json.loads(root["_attrs"]["guardrail.decisions"])
        self.assertEqual(decisions[0]["guardrail"], "boom")
        self.assertEqual(decisions[0]["reason"], "guardrail error")
        self.assertTrue(decisions[0]["blocked"])
        self.assertEqual(len(decisions), 1)
        self._held(result, root, legs=1)
        self.assertNotIn("SECRET_TRACEBACK_NEEDLE", result["final_text"])
        self.assertNotIn("SECRET_TRACEBACK_NEEDLE", root["_attrs"]["guardrail.decisions"])

    def test_a_passed_input_still_runs_the_output_guardrail_second(self):
        order = []

        def allow(ticket):
            order.append("input")
            return False, "fine"

        def block(record):
            order.append("output")
            return True, REASON

        _drive((_settle(), _final()), lambda tracer: grade_ticket_guarded(
            _ticket(), tracer,
            input_guardrails=(("in", allow),),
            output_guardrails=((NEEDLE, block),)))
        self.assertEqual(order, ["input", "output"])

    def test_a_passed_run_still_records_every_decision(self):
        seen, result, tracer = _drive((_settle(), _final()), lambda tracer: grade_ticket_guarded(
            _ticket(), tracer,
            input_guardrails=(("in", lambda ticket: (False, "fine")),),
            output_guardrails=(("out", lambda record: (False, "also fine")),)))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["final"]["notes"], "grader-note")
        root = _roots(tracer)[0]
        decisions = json.loads(root["_attrs"]["guardrail.decisions"])
        self.assertEqual([(row["guardrail"], row["side"], row["blocked"], row["reason"]) for row in decisions],
                         [("in", "input", False, "fine"), ("out", "output", False, "also fine")])
        for row in decisions:
            self.assertEqual(sorted(row), ["blocked", "guardrail", "latency_ms", "reason", "side"])
            self.assertIsInstance(row["latency_ms"], int)
        self.assertEqual(root["_attrs"]["run.status"], "complete")
        self.assertNotIn("output.final_withheld", root["_attrs"])
        self.assertEqual(records_from_otlp(tracer.to_otlp())[0]["status"], "complete")

    def test_a_guardrail_that_returns_the_wrong_shape_is_held_closed(self):
        outcomes = ((None, "x"), (0, "x"), ("", "x"), (False, None), [False, "x"], (False,), "no", None)
        for outcome in outcomes:
            with self.subTest(outcome=outcome):
                def guard(ticket, outcome=outcome):
                    return outcome

                def chat(payload, timeout):
                    raise AssertionError("model")

                tracer = Tracer("settlement-grader")
                with mock.patch("grader.agent._chat", chat):
                    result = grade_ticket_guarded(_ticket(), tracer, input_guardrails=(("shape", guard),))
                root = _roots(tracer)[0]
                decisions = json.loads(root["_attrs"]["guardrail.decisions"])
                self.assertEqual([(row["blocked"], row["reason"]) for row in decisions], [(True, "guardrail error")])
                self._held(result, root, legs=1)

    def _held(self, result, root, legs):
        self.assertEqual(result["status"], "blocked")
        final = result["final"]
        self.assertEqual(final["ticket_result"], "NEEDS_HUMAN")
        self.assertIsNone(final["net"])
        self.assertEqual(final["notes"], "held for human review")
        self.assertEqual(len(final["legs"]), legs)
        for leg in final["legs"]:
            self.assertEqual(leg["result"], "NEEDS_HUMAN")
            self.assertEqual(leg["evidence"], "held for human review")
        self.assertFalse(_names_in(result["final_text"]))
        self.assertFalse(_names_in(json.dumps(final)))
        self.assertFalse(_names_in(root["_attrs"]["output.final"]))
        self.assertFalse(_names_in(root["_attrs"]["output.final_text"]))
        self.assertEqual(root["_attrs"]["output.ticket_result"], "NEEDS_HUMAN")
        self.assertIsNone(root["_attrs"]["output.net"])


if __name__ == "__main__":
    unittest.main()
