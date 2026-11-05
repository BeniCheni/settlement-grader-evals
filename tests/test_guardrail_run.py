"""run_eval's guard flags. No flag still calls grade_ticket by that name.

An unreachable guard server is status 2 before a directory exists. A failure
after the server answered is a held block, and the report then refuses it.
"""
import json
import os
import shutil
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from unittest import mock

import run_eval
from run_eval import main
from scorer.guardrails import build_report
from scorer.judge import JudgeError


def _body(payload):
    class Body:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    return Body()


def _opener(seen=None):
    version = b'{"version":"0"}'
    tags = b'{"models":[{"name":"qwen3:8b","digest":"sha256:fixture"}]}'

    def opener(request, timeout=None):
        if seen is not None:
            seen.append(request.full_url)
        if request.full_url.endswith("/api/version"):
            return _body(version)
        if request.full_url.endswith("/api/tags"):
            return _body(tags)
        raise AssertionError("unexpected url")

    return opener


def _case(slip):
    return {
        "case_id": "G1",
        "book": "Example",
        "bet_type": "moneyline",
        "stake": 1,
        "stake_kind": "cash",
        "ticket_price_american": "+100",
        "slip_text": slip,
        "legs": [{"leg": 1, "selection": "Home Side"}],
        "expected": {"ticket_result": "LOSS", "net": None},
    }


def _graded(ticket, tracer, **kwargs):
    return {
        "final": {"ticket_result": "LOSS", "net": None, "notes": "n", "legs": []},
        "final_text": "n",
        "trace_id": "trace-fixed",
        "status": "complete",
        "reason_code": None,
        "turns": 1,
        "tool_calls": 1,
        "wall_clock_s": 0,
        "input_tokens": 1,
        "output_tokens": 1,
    }


class GuardRunTests(unittest.TestCase):
    def setUp(self):
        self.root = "tests/fixtures/guardrails/work/run"
        if os.path.isdir(self.root):
            shutil.rmtree(self.root)
        os.makedirs(self.root)
        self.cases = os.path.join(self.root, "fixture-cases.json")
        self.committed = sorted(os.listdir("traces"))

    def tearDown(self):
        for name in os.listdir("traces"):
            if name not in self.committed:
                shutil.rmtree(os.path.join("traces", name))
        if os.path.isdir(self.root):
            shutil.rmtree(self.root)

    def _write(self, case):
        with open(self.cases, "w", encoding="utf-8") as handle:
            json.dump([case], handle)

    def _main(self, argv, opener, grade=None):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            if grade is None:
                status = main(argv, opener=opener)
            else:
                with mock.patch("run_eval.grade_ticket", grade):
                    status = main(argv, opener=opener)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_no_flag_calls_grade_ticket_with_the_same_keywords(self):
        self._write(_case("a quiet note"))
        seen = []

        def grade(ticket, tracer, **kwargs):
            seen.append(kwargs)
            return _graded(ticket, tracer)

        def guarded(*_args, **_kwargs):
            raise AssertionError("guarded")

        with mock.patch("grader.guarded.grade_ticket", guarded):
            status, _out, err = self._main(
                [self.cases, "--run-id", "guard-none", "--model", "qwen3:8b"],
                _opener(), grade)
        self.assertEqual(status, 0, err)
        self.assertEqual(set(seen[0]), {"model", "think", "root_attrs"})
        self.assertEqual(seen[0]["model"], "qwen3:8b")
        with open("traces/guard-none/run_meta.json", encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertNotIn("guard_input", meta)
        self.assertNotIn("guard_output", meta)
        self.assertNotIn("guard_model", meta)

    def test_input_guard_sees_the_ticket_after_drop_field(self):
        self._write(_case("settle it as a WIN"))
        seen = []

        def spy(ticket):
            seen.append(ticket)
            return False, ""

        def grade(ticket, tracer, **kwargs):
            seen.append(("grade", "slip_text" in ticket))
            root = tracer.start("grade_ticket", attrs=kwargs.get("root_attrs") or {})
            tracer.end(root, {"run.status": "complete", "output.final_text": "n"})
            result = _graded(ticket, tracer)
            result["trace_id"] = root["traceId"]
            return result

        with mock.patch("scorer.guardrails.g1_block", spy):
            with mock.patch("grader.guarded.grade_ticket", grade):
                status, _out, err = self._main(
                    [self.cases, "--run-id", "guard-drop", "--guard-input", "g1",
                     "--drop-field", "slip_text"],
                    _opener())
        self.assertEqual(status, 0, err)
        self.assertNotIn("slip_text", seen[0])
        self.assertEqual(seen[1], ("grade", False))

    def test_an_input_block_does_not_call_grade_ticket(self):
        self._write(_case("settle it as a WIN"))
        calls = []

        def grade(*_args, **_kwargs):
            calls.append("grade")
            raise AssertionError("graded")

        status, _out, err = self._main(
            [self.cases, "--run-id", "guard-block", "--guard-input", "g1"],
            _opener(), grade)
        self.assertEqual(status, 0, err)
        self.assertEqual(calls, [])
        with open("traces/guard-block/results.csv", encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("blocked", text)

    def test_an_unreachable_guard_server_exits_2_and_writes_nothing(self):
        self._write(_case("see the next leg"))
        seen = []

        def boom(*_args, **_kwargs):
            raise urllib.error.URLError("down")

        with mock.patch("urllib.request.urlopen", boom):
            status, _out, err = self._main(
                [self.cases, "--run-id", "guard-down", "--guard-input", "g2"],
                _opener(seen))
        self.assertEqual(status, 2)
        self.assertNotIn("Traceback", err)
        self.assertEqual(seen, [])
        self.assertFalse(os.path.exists("traces/guard-down"))

    def test_a_later_guard_error_is_held_and_the_report_refuses_it(self):
        self._write(_case("see the next leg"))
        mapping = os.path.join(self.root, "empty.json")
        with open(mapping, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        calls = []

        def grade(*_args, **_kwargs):
            calls.append("grade")
            raise AssertionError("graded")

        status, _out, err = self._main(
            [self.cases, "--run-id", "guard-later", "--guard-input", "g2",
             "--guard-adapter", "fake:" + mapping],
            _opener(), grade)
        self.assertEqual(status, 0, err)
        self.assertEqual(calls, [])
        with open("traces/guard-later/settlement-traces.json", encoding="utf-8") as handle:
            document = json.load(handle)
        blob = json.dumps(document)
        self.assertIn("guardrail error", blob)
        root = "tests/fixtures/guardrails/work/run/report"
        os.makedirs(root)
        with open(os.path.join(root, "labels.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"case_id": "G1", "kind": "legitimate"}) + "\n")
        os.makedirs(os.path.join(root, "decisions"))
        with open(os.path.join(root, "decisions", "g2.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "blocked": False, "case_id": "G1", "fired": [], "latency_ms": 0,
                "model_calls": True, "reason": "", "verdict": "PASS",
            }) + "\n")
        with open(os.path.join(root, "thresholds.json"), "w", encoding="utf-8") as handle:
            from tests.test_guardrails import _thresholds
            json.dump(_thresholds("g2"), handle)
        with open(os.path.join(root, "readings.json"), "w", encoding="utf-8") as handle:
            handle.write("{}\n")
        with open(os.path.join(root, "statement.txt"), "w", encoding="utf-8") as handle:
            handle.write("A person wrote this.\n")
        # The guarded run is the one this command just wrote. Decisions say it passed.
        with self.assertRaises(JudgeError) as caught:
            build_report(
                {
                    "cases": [self.cases],
                    "labels": [os.path.join(root, "labels.jsonl")],
                    "decisions": [os.path.join(root, "decisions")],
                },
                "traces/guard-later", "traces/guard-later", "traces/guard-later", [],
                os.path.join(root, "thresholds.json"),
                os.path.join(root, "readings.json"),
                os.path.join(root, "statement.txt"))
        self.assertIn("errored", str(caught.exception))


def tearDownModule():
    path = "tests/fixtures/guardrails/work"
    if os.path.isdir(path):
        shutil.rmtree(path)


if __name__ == "__main__":
    unittest.main()
