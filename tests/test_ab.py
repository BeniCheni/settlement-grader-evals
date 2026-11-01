"""The A/B: a prompt variant, two judged runs, a paired interval, and the report."""
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

import run_eval
from grader.agent import SYSTEM_PROMPT
from run_eval import main


def _body(payload):
    class Body:
        def read(self):
            if isinstance(payload, bytes):
                return payload
            return payload.encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return Body()


def _setup_opener(seen=None):
    version = b'{"version":"0.6.2"}'
    tags = b'{"models":[{"name":"qwen3:8b","digest":"sha256:abc"}]}'

    def opener(request, timeout=None):
        if seen is not None:
            seen.append(request.full_url)
        if request.full_url.endswith("/api/version"):
            return _body(version)
        if request.full_url.endswith("/api/tags"):
            return _body(tags)
        raise AssertionError("unexpected url")

    return opener


def _no_network(*_args, **_kwargs):
    raise AssertionError("network")


def _quiet(argv, opener, chat):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout):
        with redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _no_network):
                with mock.patch("grader.agent._chat", chat):
                    status = main(argv, opener=opener)
    return status, stdout.getvalue(), stderr.getvalue()


class PromptFileTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        patcher = mock.patch.object(run_eval, "__file__", os.path.join(scratch.name, "run_eval.py"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.traces = os.path.join(scratch.name, "traces")
        self.work = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(self.work.cleanup)
        # 3.14 returns an absolute path even when dir is "."; the prompt file must be relative.
        self.work_rel = os.path.relpath(self.work.name)
        self.cases = os.path.join(self.work_rel, "cases.json")
        with open(self.cases, "w", encoding="utf-8") as handle:
            json.dump([{
                "case_id": "P1",
                "book": "book",
                "bet_type": "single",
                "stake": 1,
                "legs": [],
                "expected": {"ticket_result": "WIN", "net": 0},
            }], handle)

    def _chat(self, seen):
        def chat(payload, timeout):
            seen.append(payload)
            return {
                "message": {"role": "assistant", "content": '{"ticket_result":"WIN","net":0}'},
                "done_reason": "stop",
                "prompt_eval_count": 1,
                "eval_count": 1,
            }
        return chat

    def test_help_and_checks_import_do_not_need_the_judge(self):
        import subprocess
        import sys
        help_run = subprocess.run([sys.executable, "run_eval.py", "--help"], capture_output=True, text=True)
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--prompt-file", help_run.stdout)
        imported = subprocess.run([sys.executable, "-c", "import scorer.checks"], capture_output=True, text=True)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertEqual(imported.stdout, "")

    def test_without_the_flag_the_system_message_is_the_default_prompt(self):
        seen = []
        opener_seen = []
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-default"],
            _setup_opener(opener_seen),
            self._chat(seen),
        )
        self.assertEqual(status, 0, stderr)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertEqual(seen[0]["messages"][0]["role"], "system")
        with open(os.path.join(self.traces, "prompt-default", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["system_prompt"], SYSTEM_PROMPT)

    def test_the_file_bytes_are_the_system_message_and_are_not_stripped(self):
        path = os.path.join(self.work_rel, "prompt.txt")
        text = "Grade it.\nSecond line.\n"
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        bare = []
        flagged = []
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-bare"],
            _setup_opener(),
            self._chat(bare),
        )
        self.assertEqual(status, 0, stderr)
        status, _stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-file", "--prompt-file", path],
            _setup_opener(),
            self._chat(flagged),
        )
        self.assertEqual(status, 0, stderr)
        self.assertEqual(flagged[0]["messages"][0]["content"], text)
        self.assertTrue(flagged[0]["messages"][0]["content"].endswith("\n"))
        bare_payload = json.loads(json.dumps(bare[0]))
        flagged_payload = json.loads(json.dumps(flagged[0]))
        bare_payload["messages"][0]["content"] = None
        flagged_payload["messages"][0]["content"] = None
        self.assertEqual(bare_payload, flagged_payload)
        with open(os.path.join(self.traces, "prompt-file", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["system_prompt"], text)
        self.assertEqual(set(meta), {
            "run_id", "cases_file", "model", "ollama_version", "model_digest", "think",
            "budgets", "system_prompt", "n_cases", "outcome_matches",
        })

    def _refused(self, argument, fragment):
        seen = []
        opener_seen = []

        def chat(payload, timeout):
            raise AssertionError("graded")

        self.assertFalse(os.path.exists(self.traces))
        status, stdout, stderr = _quiet(
            [self.cases, "--run-id", "prompt-refused", "--prompt-file", argument],
            _setup_opener(opener_seen),
            chat,
        )
        self.assertEqual(status, 2, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, fragment)
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(opener_seen, [])
        self.assertEqual(seen, [])
        self.assertFalse(os.path.exists(self.traces))

    def test_a_bad_prompt_file_exits_before_setup_and_writes_nothing(self):
        missing = os.path.join(self.work_rel, "missing.txt")
        self._refused(missing, "prompt file is unreadable\n")
        empty = os.path.join(self.work_rel, "empty.txt")
        with open(empty, "w", encoding="utf-8", newline="") as handle:
            handle.write(" \n\t")
        self._refused(empty, "prompt file is empty\n")
        binary = os.path.join(self.work_rel, "binary.txt")
        with open(binary, "wb") as handle:
            handle.write(b"\xff")
        self._refused(binary, "prompt file is unreadable\n")
        self._refused("/tmp/prompt.txt", "prompt file must be a relative path, not an absolute path\n")
        self._refused("~/prompt.txt", "prompt file must be a relative path, not an absolute path\n")
        self._refused("../prompt.txt", "prompt file must be a relative path inside this directory\n")


class VariantTests(unittest.TestCase):
    def test_compare_first_differs_by_one_line(self):
        with open("variants/compare-first.txt", encoding="utf-8", newline="") as handle:
            variant = handle.read()
        self.assertFalse(variant.endswith("\n"))
        self.assertFalse(SYSTEM_PROMPT.endswith("\n"))
        base = SYSTEM_PROMPT.split("\n")
        other = variant.split("\n")
        self.assertEqual(len(base), len(other))
        changed = [(left, right) for left, right in zip(base, other) if left != right]
        removed = (
            "3. Grade each leg: W (won), L (lost), P (push), VOID, MOOT "
            "(not needed: another leg already lost), OPEN (match not final) or "
            "NEEDS_HUMAN (a fact you need is missing or a rule says so)."
        )
        added = (
            "3. Grade each leg by comparing it with the facts. In the same message as your "
            "settle_ticket call, first write one line per leg: the selection, the score or stat "
            "from get_match_facts with home and away named, and what that means for the selection. "
            "Then give its result: W (won), L (lost), P (push), VOID, MOOT (not needed: another leg "
            "already lost), OPEN (match not final) or NEEDS_HUMAN (a fact you need is missing or a "
            "rule says so)."
        )
        self.assertEqual(changed, [(removed, added)])
        self.assertEqual(len(removed), 184)
        self.assertEqual(len(added), 434)
