"""run_eval records the Ollama version and the model digest before it writes a run."""
import json
import os
import shutil
import urllib.error
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import unittest
from unittest import mock

from run_eval import SetupReadError, read_ollama_setup, main


VERSION_URL = "http://127.0.0.1:11434/api/version"
TAGS_URL = "http://127.0.0.1:11434/api/tags"


class _Body:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        if isinstance(self.payload, bytes):
            return self.payload
        return self.payload.encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _stand_in(version=b'{"version":"0.6.2"}', tags=None, fail=None, seen=None):
    if tags is None:
        tags = (
            b'{"models":['
            b'{"name":"other:1","digest":"sha256:other"},'
            b'{"name":"qwen3:8b","digest":"sha256:abc"}]}'
        )

    def opener(request, timeout=None):
        if seen is not None:
            seen.append((request.get_method(), request.full_url, timeout))
        if fail == "version" and request.full_url.endswith("/api/version"):
            raise urllib.error.URLError("down")
        if fail == "tags" and request.full_url.endswith("/api/tags"):
            raise urllib.error.URLError("down")
        if request.full_url.endswith("/api/version"):
            return _Body(version)
        if request.full_url.endswith("/api/tags"):
            return _Body(tags)
        raise AssertionError("unexpected url")

    return opener


def _network(*args, **kwargs):
    raise AssertionError("network")


def _graded(*args, **kwargs):
    raise AssertionError("graded")


def _quiet_main(argv, opener, grade=_graded):
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout):
        with redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _network):
                with mock.patch("run_eval.grade_ticket", grade):
                    status = main(argv, opener=opener)
    return status, stdout.getvalue(), stderr.getvalue()


class RunSetupTests(unittest.TestCase):
    def test_stand_in_reads_version_and_exact_model_digest(self):
        seen = []
        version, digest = read_ollama_setup("qwen3:8b", _stand_in(seen=seen))
        self.assertEqual(version, "0.6.2")
        self.assertEqual(digest, "sha256:abc")
        self.assertEqual(
            [(method, url) for method, url, _timeout in seen],
            [("GET", VERSION_URL), ("GET", TAGS_URL)],
        )
        self.assertTrue(all(timeout == 30 for _method, _url, timeout in seen))

    def test_near_name_is_missing_and_a_blank_digest_is_not_recorded(self):
        near = b'{"models":[{"name":"qwen3:8b-extra","digest":"sha256:nope"}]}'
        with self.assertRaises(SetupReadError) as missing:
            read_ollama_setup("qwen3:8b", _stand_in(tags=near))
        self.assertIn("qwen3:8b", str(missing.exception))
        self.assertNotIn("null", str(missing.exception))
        blank = b'{"models":[{"name":"qwen3:8b","digest":"  "}]}'
        with self.assertRaises(SetupReadError) as no_digest:
            read_ollama_setup("qwen3:8b", _stand_in(tags=blank))
        self.assertEqual(str(no_digest.exception), "could not read the model digest")
        with self.assertRaises(SetupReadError) as null_version:
            read_ollama_setup("qwen3:8b", _stand_in(version=b'{"version":null}'))
        self.assertEqual(str(null_version.exception), "could not read the Ollama version")

    def _stop(self, run_id, opener, message):
        out = os.path.join("traces", run_id)
        shutil.rmtree(out, ignore_errors=True)
        calls = []

        def grade(*args, **kwargs):
            calls.append(1)
            raise AssertionError("graded")

        try:
            self.assertFalse(os.path.exists(out))
            status, _stdout, stderr = _quiet_main(
                ["data/gold.json", "--only", "A01", "--run-id", run_id], opener, grade=grade)
            self.assertEqual(status, 1)
            self.assertEqual(stderr, message)
            self.assertEqual(calls, [])
            self.assertFalse(os.path.exists(out))
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_failed_version_stops_before_a_file_or_a_ticket(self):
        seen = []
        self._stop(
            "floor-setup-fail-version",
            _stand_in(fail="version", seen=seen),
            "could not read the Ollama version\n",
        )
        self.assertEqual([url for _method, url, _timeout in seen], [VERSION_URL])

    def test_failed_tags_stops_before_a_file_or_a_ticket(self):
        self._stop(
            "floor-setup-fail-tags",
            _stand_in(fail="tags"),
            "could not read the model digest\n",
        )

    def test_missing_model_stops_before_a_file_or_a_ticket(self):
        tags = b'{"models":[{"name":"qwen3:8b-extra","digest":"sha256:nope"}]}'
        self._stop(
            "floor-setup-fail-model",
            _stand_in(tags=tags),
            "model qwen3:8b is not in the Ollama tags\n",
        )

    def test_stand_in_records_both_keys_and_leaves_no_run_behind(self):
        run_id = "floor-setup-recorded"
        out = os.path.join("traces", run_id)
        shutil.rmtree(out, ignore_errors=True)
        calls = []

        def grade(*args, **kwargs):
            calls.append(kwargs.get("model"))
            return {
                "final": {"ticket_result": "WIN", "net": 0},
                "trace_id": "floor-setup",
                "status": "complete",
                "reason_code": None,
                "turns": 1,
                "tool_calls": 1,
                "wall_clock_s": 0,
                "input_tokens": 1,
                "output_tokens": 1,
            }

        try:
            status, _stdout, stderr = _quiet_main(
                ["data/gold.json", "--only", "A01", "--run-id", run_id, "--model", "qwen3:8b"],
                _stand_in(),
                grade=grade,
            )
            self.assertEqual(status, 0, stderr)
            self.assertEqual(calls, ["qwen3:8b"])
            with open(os.path.join(out, "run_meta.json"), encoding="utf-8") as handle:
                meta = json.load(handle)
            self.assertEqual(meta["ollama_version"], "0.6.2")
            self.assertEqual(meta["model_digest"], "sha256:abc")
            self.assertEqual(meta["model"], "qwen3:8b")
            self.assertEqual(meta["run_id"], run_id)
            self.assertEqual(
                set(meta),
                {
                    "run_id", "cases_file", "model", "ollama_version", "model_digest",
                    "think", "budgets", "system_prompt", "n_cases", "outcome_matches",
                },
            )
            self.assertIsInstance(meta["ollama_version"], str)
            self.assertIsInstance(meta["model_digest"], str)
        finally:
            shutil.rmtree(out, ignore_errors=True)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
