"""The exec target: one stdout line, a required run id, and a locked trace file."""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

import grader.redteam_target as target
from grader.redteam_target import main
from scorer.traces import load_run


CASES = "tests/fixtures/redteam/proof-cases.json"
REPLIES = "tests/fixtures/redteam/proof-replies.json"
ROOT_CONFIG = "promptfooconfig.yaml"
PROOF_CONFIG = "tests/fixtures/redteam/promptfooconfig.yaml"


def _body(payload):
    class Body:
        def read(self):
            return payload if isinstance(payload, bytes) else payload.encode()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    return Body()


def _opener(version="0.6.2", digest="sha256:abc"):
    def opener(request, timeout=None):
        if request.full_url.endswith("/api/version"):
            return _body(json.dumps({"version": version}).encode())
        if request.full_url.endswith("/api/tags"):
            return _body(json.dumps({"models": [{"name": "qwen3:8b", "digest": digest}]}).encode())
        raise AssertionError("unexpected url")

    return opener


def _raise_open(*_args, **_kwargs):
    raise AssertionError("socket")


class RedteamTargetTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        os.makedirs(os.path.join(self.root, "grader"))
        self._file = target.__file__
        target.__file__ = os.path.join(self.root, "grader", "redteam_target.py")
        self.addCleanup(self._restore_file)
        self._env = os.environ.get("REDTEAM_RUN_ID")
        self.addCleanup(self._restore_env)

    def _restore_file(self):
        target.__file__ = self._file

    def _restore_env(self):
        if self._env is None:
            os.environ.pop("REDTEAM_RUN_ID", None)
        else:
            os.environ["REDTEAM_RUN_ID"] = self._env

    def _run(self, argv, run_id="rt-unit", opener=None, fixture=True):
        if run_id is None:
            os.environ.pop("REDTEAM_RUN_ID", None)
        else:
            os.environ["REDTEAM_RUN_ID"] = run_id
        stdout = StringIO()
        stderr = StringIO()
        args = list(argv)
        if fixture and "--fixture" not in args:
            args = ["--cases", CASES, "--fixture", REPLIES] + args
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(args, opener=opener)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_help_import_and_no_arguments(self):
        help_run = subprocess.run([sys.executable, "run_eval.py", "--help"], capture_output=True, text=True)
        self.assertEqual(help_run.returncode, 0, help_run.stderr)
        self.assertIn("--drop-field", help_run.stdout)
        imported = subprocess.run([sys.executable, "-c", "import scorer.checks"], capture_output=True, text=True)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertEqual(imported.stdout, "")
        bare = subprocess.run([sys.executable, "-m", "grader.redteam_target"], capture_output=True, text=True)
        self.assertEqual(bare.returncode, 2)
        self.assertEqual(bare.stdout, "")
        self.assertTrue(bare.stderr)

    def test_the_run_id_is_required_and_stdout_stays_empty(self):
        status, stdout, stderr = self._run(["P0"], run_id=None)
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("REDTEAM_RUN_ID", stderr)
        self.assertFalse(os.path.exists(os.path.join(self.root, "traces")))
        for run_id in ("", "-bad", ".hidden", "a/b", "../out"):
            with self.subTest(run_id=run_id):
                status, stdout, stderr = self._run(["P0"], run_id=run_id)
                self.assertEqual(status, 2)
                self.assertEqual(stdout, "")
                self.assertFalse(os.path.isdir(os.path.join(self.root, "traces", run_id)))

    def test_fixture_writes_no_socket_and_one_line(self):
        status, stdout, stderr = self._run(["P0", "{\"ignored\":true}", "[1]"], opener=_raise_open)
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout.count("\n"), 1)
        row = json.loads(stdout)
        self.assertEqual(sorted(row), ["final", "final_text", "reason_code", "status", "tools"])
        self.assertEqual(row["status"], "complete")
        self.assertIsNone(row["reason_code"])
        self.assertEqual(row["final"]["ticket_result"], "LOSS")
        self.assertIn("\n", row["final"]["notes"])
        self.assertEqual([tool["name"] for tool in row["tools"]], ["settle_ticket"])
        self.assertNotIn("\n", stdout.strip())
        meta_path = os.path.join(self.root, "traces", "rt-unit", "run_meta.json")
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["ollama_version"], "fixture")
        self.assertEqual(meta["model_digest"], "fixture")
        self.assertEqual(meta["n_cases"], 1)
        self.assertEqual(meta["outcome_matches"], 1)
        self.assertEqual(set(meta), {
            "run_id", "cases_file", "model", "ollama_version", "model_digest", "think",
            "budgets", "system_prompt", "n_cases", "outcome_matches",
        })
        self.assertFalse(os.path.isabs(meta["cases_file"]))

    def test_two_calls_then_a_different_setup_writes_nothing(self):
        status, stdout, _stderr = self._run(["P0"], run_id="rt-two")
        self.assertEqual(status, 0)
        self.assertEqual(len(load_run(os.path.join(self.root, "traces", "rt-two"))), 1)
        status, stdout, _stderr = self._run(["P1"], run_id="rt-two")
        self.assertEqual(status, 0, stdout)
        self.assertEqual(stdout.count("\n"), 1)
        records = load_run(os.path.join(self.root, "traces", "rt-two"))
        self.assertEqual(sorted(row["case_id"] for row in records), ["P0", "P1"])
        with open(os.path.join(self.root, "traces", "rt-two", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["n_cases"], 2)
        self.assertEqual(meta["outcome_matches"], 2)
        with open(os.path.join(self.root, "traces", "rt-two", "settlement-traces.json"), "rb") as handle:
            before = handle.read()
        with open(os.path.join(self.root, "traces", "rt-two", "run_meta.json"), "rb") as handle:
            meta_before = handle.read()
        status, stdout, stderr = self._run(
            ["--cases", CASES, "P0"], run_id="rt-two", opener=_opener(), fixture=False)
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("setup differs", stderr)
        with open(os.path.join(self.root, "traces", "rt-two", "settlement-traces.json"), "rb") as handle:
            after = handle.read()
        with open(os.path.join(self.root, "traces", "rt-two", "run_meta.json"), "rb") as handle:
            meta_after = handle.read()
        self.assertEqual(before, after)
        self.assertEqual(meta_before, meta_after)

    def test_without_a_fixture_the_setup_is_read(self):
        from unittest import mock
        with open(REPLIES, encoding="utf-8") as handle:
            replies = json.load(handle)
        index = {"n": 0}

        def chat(payload, timeout):
            reply = replies[index["n"]]
            index["n"] += 1
            return reply

        with mock.patch("grader.agent._chat", chat):
            status, stdout, stderr = self._run(
                ["--cases", CASES, "P0"], run_id="rt-live", opener=_opener(), fixture=False)
        self.assertEqual(status, 0, stderr)
        self.assertEqual(json.loads(stdout)["status"], "complete")
        with open(os.path.join(self.root, "traces", "rt-live", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["ollama_version"], "0.6.2")
        self.assertEqual(meta["model_digest"], "sha256:abc")

    def test_a_fixture_that_runs_out_does_not_open_a_socket(self):
        replies = os.path.join(self.root, "empty-replies.json")
        with open(replies, "w", encoding="utf-8") as handle:
            json.dump([], handle)
        status, stdout, stderr = self._run(
            ["--cases", CASES, "--fixture", replies, "P0"], run_id="rt-empty", opener=_raise_open)
        self.assertEqual(status, 0, stderr)
        row = json.loads(stdout)
        self.assertEqual(row["status"], "incomplete")
        self.assertEqual(row["reason_code"], "NON_NORMAL_DONE_REASON")
        self.assertEqual(stdout.count("\n"), 1)

    def test_a_newline_in_final_text_stays_on_one_stdout_line(self):
        work = os.path.join(self.root, "newline.json")
        replies = os.path.join(self.root, "replies.json")
        with open(work, "w", encoding="utf-8") as handle:
            json.dump([{
                "case_id": "N1",
                "source": "synthetic",
                "book": "book",
                "bet_type": "single",
                "stake": 1,
                "legs": [{"leg": 1}],
            }], handle)
        with open(replies, "w", encoding="utf-8") as handle:
            json.dump([{
                "message": {"role": "assistant", "content": "line1\nline2"},
                "done_reason": "stop",
            }], handle)
        status, stdout, stderr = self._run(
            ["--cases", work, "--fixture", replies, "N1"], run_id="rt-nl")
        self.assertEqual(status, 0, stderr)
        self.assertEqual(stdout.count("\n"), 1)
        row = json.loads(stdout)
        self.assertEqual(row["final_text"], "line1\nline2")
        self.assertIn("\\n", stdout)

    def test_a_non_synthetic_case_is_refused_before_the_directory(self):
        path = os.path.join(self.root, "bad.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump([{
                "case_id": "BAD",
                "source": "real ticket from the author's private betting log",
                "legs": [{"leg": 1}],
                "poison": [{"tool": "lookup_rule", "match": {}, "append_text": "hidden"}],
            }], handle)
        status, stdout, stderr = self._run(
            ["--cases", path, "--fixture", REPLIES, "BAD"], run_id="rt-bad")
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("synthetic", stderr)
        self.assertNotIn("hidden", stderr)
        self.assertFalse(os.path.isdir(os.path.join(self.root, "traces", "rt-bad")))

    def test_configs_name_the_target_and_leave_out_the_judge_assertion(self):
        with open(ROOT_CONFIG, encoding="utf-8") as handle:
            root = handle.read()
        with open(PROOF_CONFIG, encoding="utf-8") as handle:
            proof = handle.read()
        self.assertIn("data/redteam/baseline-cases.json", root)
        self.assertNotIn("--fixture", root)
        self.assertIn("{{case_id}}", root)
        self.assertIn("maxConcurrency: 1", root)
        self.assertIn("timeoutMs: 360000", root)
        self.assertIn("--fixture", proof)
        self.assertIn("invoke.py", proof)
        self.assertIn("proof-cases.json", proof)
        self.assertIn("javascript", proof)
        self.assertIn("not-contains", proof)
        for text in (root, proof):
            self.assertNotIn("llm-rubric", text)
        self.assertFalse(os.path.exists("data/redteam/baseline-cases.json"))

    def test_two_overlapping_processes_keep_both_records(self):
        self._restore_file()
        run_id = "rt-unit-overlap"
        root = target.repo_root()
        run_dir = os.path.join(root, "traces", run_id)
        lock_path = os.path.join(root, "traces", run_id + ".lock")
        procs = []

        def cleanup():
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            shutil.rmtree(run_dir, ignore_errors=True)
            try:
                os.remove(lock_path)
            except OSError:
                pass

        self.addCleanup(cleanup)
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        held = open(lock_path, "a+")
        self.addCleanup(held.close)
        fcntl.flock(held.fileno(), fcntl.LOCK_EX)
        env = os.environ.copy()
        env["REDTEAM_RUN_ID"] = run_id
        for case_id in ("P0", "P1"):
            procs.append(subprocess.Popen(
                [sys.executable, "-m", "grader.redteam_target",
                 "--cases", CASES, "--fixture", REPLIES, case_id, "{\"ignored\":1}", "[2]"],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            ))
        deadline = time.time() + 5
        while time.time() < deadline and any(proc.poll() is not None for proc in procs):
            time.sleep(0.05)
        time.sleep(0.3)
        self.assertTrue(all(proc.poll() is None for proc in procs), "a process finished while the lock was held")
        self.assertFalse(os.path.exists(os.path.join(run_dir, "settlement-traces.json")))
        fcntl.flock(held.fileno(), fcntl.LOCK_UN)
        rows = []
        for proc in procs:
            stdout, stderr = proc.communicate(timeout=30)
            self.assertEqual(proc.returncode, 0, stderr)
            self.assertEqual(stdout.count("\n"), 1, stdout)
            rows.append(json.loads(stdout))
        records = load_run(run_dir)
        self.assertEqual(sorted(row["case_id"] for row in records), ["P0", "P1"])
        self.assertEqual(sorted(row["status"] for row in rows), ["complete", "complete"])
        with open(os.path.join(run_dir, "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["n_cases"], 2)


if __name__ == "__main__":
    unittest.main()
