"""--rule-match and --disable-tool, including the idle golden through main."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

import run_eval
from grader.tools import call_tool
from run_eval import _load_cases, main


def _idle():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_idle_requests.py")
    spec = importlib.util.spec_from_file_location("idle_requests_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _body(payload):
    class Body:
        def read(self):
            return payload if isinstance(payload, bytes) else payload.encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return Body()


def _opener(request, timeout=None):
    if request.full_url.endswith("/api/version"):
        return _body(b'{"version":"0.6.2"}')
    if request.full_url.endswith("/api/tags"):
        return _body(b'{"models":[{"name":"qwen3:8b","digest":"sha256:abc"}]}')
    raise AssertionError("unexpected url")


def _case(case_id, **extra):
    row = {
        "case_id": case_id,
        "source": "synthetic",
        "book": "book",
        "bet_type": "single",
        "stake": 1,
        "legs": [{
            "leg": 1,
            "selection": "Home",
            "market": "Moneyline",
            "market_wording_on_slip": "Moneyline",
        }],
        "expected": {"ticket_result": "LOSS", "net": -1},
    }
    row.update(extra)
    return row


def _result():
    return {
        "final": {"ticket_result": "LOSS", "net": -1},
        "trace_id": "t",
        "status": "complete",
        "reason_code": None,
        "turns": 1,
        "tool_calls": 0,
        "wall_clock_s": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }


class RuleMatchTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        patcher = mock.patch.object(run_eval, "__file__", os.path.join(scratch.name, "run_eval.py"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.traces = os.path.join(scratch.name, "traces")
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.work = work.name

    def _write(self, cases, name="cases.json"):
        path = os.path.join(self.work, name)
        if name.endswith(".jsonl"):
            with open(path, "w", encoding="utf-8") as handle:
                for case in cases:
                    if case is None:
                        handle.write("\n")
                    else:
                        handle.write(json.dumps(case) + "\n")
        else:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(cases, handle)
        return path

    def _run(self, argv, chat=None, grade=None, opener=_opener):
        stdout = StringIO()
        stderr = StringIO()
        chat_patch = mock.patch("grader.agent._chat", chat) if chat is not None else nullcontext()
        grade_patch = mock.patch("run_eval.grade_ticket", grade) if grade is not None else nullcontext()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", opener):
                with chat_patch, grade_patch:
                    status = main(argv, opener=opener)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_metadata_keys_appear_only_with_their_flag(self):
        path = self._write([_case("A")])
        seen = []

        def spy(ticket, tracer, **kwargs):
            seen.append(kwargs)
            return _result()

        status, _out, err = self._run(
            [path, "--run-id", "meta-exact", "--rule-match", "exact"], grade=spy,
        )
        self.assertEqual(status, 0, err)
        with open(os.path.join(self.traces, "meta-exact", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["rule_match"], "exact")
        self.assertNotIn("disabled_tools", meta)
        self.assertFalse(os.path.isabs(meta["cases_file"]))
        self.assertNotIn("~", meta["cases_file"])
        self.assertIs(seen[0]["tool_runner"], call_tool)

        seen.clear()
        status, _out, err = self._run(
            [path, "--run-id", "meta-off", "--disable-tool", "lookup_rule"], grade=spy,
        )
        self.assertEqual(status, 0, err)
        with open(os.path.join(self.traces, "meta-off", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["disabled_tools"], ["lookup_rule"])
        self.assertNotIn("rule_match", meta)
        self.assertTrue(callable(seen[0]["tool_runner"]))

        seen.clear()
        status, _out, err = self._run([path, "--run-id", "meta-plain"], grade=spy)
        self.assertEqual(status, 0, err)
        with open(os.path.join(self.traces, "meta-plain", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertNotIn("rule_match", meta)
        self.assertNotIn("disabled_tools", meta)
        self.assertNotIn("tool_runner", seen[0])

    def test_the_two_flags_and_a_guard_are_refused_before_a_directory(self):
        missing = os.path.join(self.work, "missing.json")
        opened = []

        def opener(request, timeout=None):
            opened.append(1)
            return _opener(request, timeout)

        pairs = (
            ([missing, "--rule-match", "exact", "--disable-tool", "lookup_rule"],
             "--rule-match and --disable-tool exclude each other\n"),
            ([missing, "--rule-match", "fuzzy"], "unknown rule-match\n"),
            ([missing, "--disable-tool", "settle_ticket"], "unknown tool\n"),
            ([missing, "--rule-match", "exact", "--guard-input", "g1"],
             "a retrieval flag cannot be combined with a guard\n"),
            ([missing, "--disable-tool", "lookup_rule", "--guard-output", "g4"],
             "a retrieval flag cannot be combined with a guard\n"),
        )
        for argv, message in pairs:
            opened.clear()
            status, _out, err = self._run(argv, opener=opener)
            self.assertEqual(status, 2)
            self.assertEqual(err, message)
            self.assertEqual(opened, [])
            self.assertFalse(os.path.isdir(self.traces))

    def test_poison_is_refused_before_only_and_before_a_directory(self):
        path = self._write([
            _case("POISONED", poison=[{
                "tool": "lookup_rule", "match": {}, "append_text": "hidden",
            }]),
            _case("CLEAN"),
        ])
        opened = []

        def opener(request, timeout=None):
            opened.append(1)
            return _opener(request, timeout)

        status, _out, err = self._run(
            [path, "--only", "CLEAN", "--rule-match", "alias"], opener=opener,
        )
        self.assertEqual(status, 2)
        self.assertEqual(err, "POISONED: poison is refused\n")
        self.assertEqual(opened, [])
        self.assertFalse(os.path.isdir(self.traces))

    def test_jsonl_reads_the_same_cases_as_the_json_it_came_from(self):
        cases = [_case("A"), _case("B")]
        json_path = self._write(cases, "cases.json")
        jsonl_path = self._write([None, cases[0], None, cases[1], None], "cases.jsonl")
        self.assertEqual(_load_cases(json_path), _load_cases(jsonl_path))
        seen = []

        def spy(ticket, tracer, **kwargs):
            seen.append(ticket["legs"][0]["selection"])
            return _result()

        status, _out, err = self._run([jsonl_path, "--run-id", "jsonl"], grade=spy)
        self.assertEqual(status, 0, err)
        self.assertEqual(seen, ["Home", "Home"])
        with open(os.path.join(self.traces, "jsonl", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertTrue(meta["cases_file"].endswith("cases.jsonl"))
        self.assertFalse(os.path.isabs(meta["cases_file"]))

    def test_a_non_object_jsonl_line_is_unreadable_and_writes_nothing(self):
        path = os.path.join(self.work, "bad.jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"case_id": "A"}\n')
            handle.write("1\n")
        status, _out, err = self._run([path, "--run-id", "bad-jsonl"])
        self.assertEqual(status, 2)
        self.assertEqual(err, "cases file is unreadable\n")
        self.assertFalse(os.path.isdir(self.traces))

    def test_rule_match_exact_matches_the_idle_golden(self):
        idle = _idle()
        golden = idle.load_golden()
        path = self._write([golden["case"]])
        seen = []

        def chat(payload, timeout):
            seen.append(json.dumps(payload))
            return idle.scripted_reply(len(seen) - 1)

        status, _out, err = self._run(
            [path, "--run-id", "idle-exact", "--rule-match", "exact"], chat=chat,
        )
        self.assertEqual(status, 0, err)
        self.assertEqual(seen, golden["requests"])


class ImportTests(unittest.TestCase):
    def test_help_and_checks_import_without_a_cycle(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        runs = (
            [sys.executable, "run_eval.py", "--help"],
            [sys.executable, "-c", "import scorer.checks"],
            [sys.executable, "-c",
             "import run_eval, sys; "
             "raise SystemExit(1 if any(n == 'scorer' or n.startswith('scorer.') for n in sys.modules) else 0)"],
            [sys.executable, "-c",
             "import grader.retrieval, sys; "
             "bad = [n for n in sys.modules if n == 'scorer' or n.startswith('scorer.') or n in ('run_eval', 'check_gold')]; "
             "raise SystemExit(1 if bad else 0)"],
            [sys.executable, "-c",
             "import scorer.checks, sys; raise SystemExit(1 if 'scorer.golden' in sys.modules else 0)"],
        )
        for argv in runs:
            result = subprocess.run(argv, cwd=root, capture_output=True)
            self.assertEqual(result.returncode, 0, argv)


if __name__ == "__main__":
    unittest.main()
