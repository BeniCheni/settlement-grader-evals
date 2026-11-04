"""--drop-field and a case that carries poison or followups."""
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

import run_eval
from run_eval import main
from scorer.traces import load_run


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


def _no_network(*_args, **_kwargs):
    raise AssertionError("network")


def _case(case_id, source="synthetic", **extra):
    row = {
        "case_id": case_id,
        "source": source,
        "book": "book",
        "bet_type": "single",
        "stake": 1,
        "slip_text": "keep me",
        "legs": [{
            "leg": 1,
            "selection": "Home",
            "market_wording_on_slip": "wording",
        }],
        "expected": {"ticket_result": "LOSS", "net": -1},
    }
    row.update(extra)
    return row


def _final_chat(seen):
    def chat(payload, timeout):
        seen.append(json.loads(json.dumps(payload)))
        return {
            "message": {"role": "assistant", "content": '{"ticket_result":"LOSS","net":-1}'},
            "done_reason": "stop",
        }
    return chat


class DropFieldTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        patcher = mock.patch.object(run_eval, "__file__", os.path.join(scratch.name, "run_eval.py"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.traces = os.path.join(scratch.name, "traces")
        work = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(work.cleanup)
        self.work = os.path.relpath(work.name)

    def _write(self, cases):
        path = os.path.join(self.work, "cases.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cases, handle)
        return path

    def _run(self, argv, chat, opener=_opener):
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _no_network):
                with mock.patch("grader.agent._chat", chat):
                    status = main(argv, opener=opener)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_an_unknown_field_is_refused_before_a_directory_or_a_read(self):
        opened = []

        def opener(request, timeout=None):
            opened.append(request.full_url)
            return _opener(request, timeout)

        status, stdout, stderr = self._run(
            [os.path.join(self.work, "missing.json"), "--drop-field", "not-a-field", "--run-id", "drop-bad"],
            _final_chat([]),
            opener=opener,
        )
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unknown field not-a-field", stderr)
        self.assertEqual(opened, [])
        self.assertFalse(os.path.exists(self.traces))
        self.assertFalse(os.path.exists(os.path.join(self.work, "missing.json")))

    def test_an_unreadable_cases_file_is_refused_with_one_message(self):
        opened = []

        def opener(request, timeout=None):
            opened.append(request.full_url)
            return _opener(request, timeout)

        files = {
            "missing.json": None,
            "empty.json": b"",
            "latin.json": b"[\xff]",
            "object.json": b'{"case_id": "X"}',
            "truncated.json": b"[{",
        }
        for name, data in files.items():
            path = os.path.join(self.work, name)
            if data is not None:
                with open(path, "wb") as handle:
                    handle.write(data)
            with self.subTest(file=name):
                status, stdout, stderr = self._run([path, "--run-id", "cases-bad"], _final_chat([]), opener=opener)
                self.assertEqual(status, 2)
                self.assertEqual(stdout, "")
                self.assertEqual(stderr, "cases file is unreadable\n")
        self.assertEqual(opened, [])
        self.assertFalse(os.path.exists(self.traces))

    def test_the_field_is_gone_from_the_request_and_named_in_the_metadata(self):
        path = self._write([_case("D1")])
        seen = []
        status, _stdout, stderr = self._run(
            [path, "--run-id", "drop-ok", "--drop-field", "slip_text", "--drop-field", "market_wording_on_slip"],
            _final_chat(seen),
        )
        self.assertEqual(status, 0, stderr)
        ticket = json.loads(seen[0]["messages"][1]["content"].split("\n", 1)[1])
        self.assertNotIn("slip_text", ticket)
        self.assertNotIn("market_wording_on_slip", ticket["legs"][0])
        self.assertEqual(ticket["legs"][0]["selection"], "Home")
        with open(os.path.join(self.traces, "drop-ok", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(meta["drop_fields"], ["slip_text", "market_wording_on_slip"])
        self.assertIn("system_prompt", meta)
        self.assertIn("n_cases", meta)

    def test_without_the_flag_the_field_stays_and_the_metadata_key_does_not(self):
        path = self._write([_case("D2")])
        seen = []
        status, _stdout, stderr = self._run([path, "--run-id", "drop-off"], _final_chat(seen))
        self.assertEqual(status, 0, stderr)
        ticket = json.loads(seen[0]["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(ticket["slip_text"], "keep me")
        self.assertEqual(ticket["legs"][0]["market_wording_on_slip"], "wording")
        with open(os.path.join(self.traces, "drop-off", "run_meta.json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertNotIn("drop_fields", meta)
        self.assertEqual(set(meta), {
            "run_id", "cases_file", "model", "ollama_version", "model_digest", "think",
            "budgets", "system_prompt", "n_cases", "outcome_matches",
        })

    def test_a_non_synthetic_case_is_refused_before_only_filters_it(self):
        path = self._write([
            _case("BAD", source="real ticket from the author's private betting log", poison=[{
                "tool": "lookup_rule", "match": {}, "append_text": "hidden",
            }]),
            _case("GOOD"),
        ])
        calls = []

        def chat(payload, timeout):
            calls.append(1)
            return {"message": {"role": "assistant", "content": "{}"}, "done_reason": "stop"}

        opened = []

        def opener(request, timeout=None):
            opened.append(1)
            return _opener(request, timeout)

        status, stdout, stderr = self._run(
            [path, "--only", "GOOD", "--run-id", "seam-bad"],
            chat,
            opener=opener,
        )
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("BAD", stderr)
        self.assertIn("synthetic", stderr)
        self.assertNotIn("hidden", stderr)
        self.assertEqual(calls, [])
        self.assertEqual(opened, [])
        self.assertFalse(os.path.exists(self.traces))

    def test_a_bad_poison_entry_is_refused_before_anything_is_written(self):
        path = self._write([_case("BADP", poison=[{
            "tool": "lookup_rule", "match": {}, "append_text": "a", "set": {"extra": 1},
        }])])
        status, stdout, stderr = self._run([path, "--run-id", "seam-shape"], _final_chat([]))
        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("poison is refused", stderr)
        self.assertFalse(os.path.exists(self.traces))

    def test_synthetic_poison_and_followups_reach_the_grader(self):
        path = self._write([_case("SYN", poison=[{
            "tool": "lookup_rule", "match": {"topic": "general"}, "append_text": " POISON",
        }], followups=["why"])])
        replies = [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "lookup_rule", "arguments": {"topic": "general"}}}],
                },
                "done_reason": "stop",
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {
                        "name": "settle_ticket",
                        "arguments": {"leg_results": ["L"], "stake": 1, "stake_kind": "cash"},
                    }}],
                },
                "done_reason": "stop",
            },
            {"message": {"role": "assistant", "content": '{"ticket_result":"LOSS","net":-1,"notes":"a"}'},
             "done_reason": "stop"},
            {"message": {"role": "assistant", "content": '{"ticket_result":"LOSS","net":-1,"notes":"b"}'},
             "done_reason": "stop"},
        ]
        seen = []

        def chat(payload, timeout):
            seen.append(json.loads(json.dumps(payload)))
            return replies[len(seen) - 1]

        kwargs_seen = []
        real = run_eval.grade_ticket

        def grade(*args, **kwargs):
            kwargs_seen.append(sorted(kwargs))
            return real(*args, **kwargs)

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _no_network):
                with mock.patch("run_eval.grade_ticket", grade):
                    with mock.patch("grader.agent._chat", chat):
                        status = main([path, "--run-id", "seam-ok"], opener=_opener)
        self.assertEqual(status, 0, stderr.getvalue())
        self.assertIn("tool_runner", kwargs_seen[0])
        self.assertIn("followups", kwargs_seen[0])
        self.assertIn(" POISON", json.dumps(seen[1]))
        self.assertEqual(seen[-1]["messages"][-1], {"role": "user", "content": "why"})
        records = load_run(os.path.join(self.traces, "seam-ok"))
        self.assertEqual(records[0]["tools"][0]["poisoned"], True)
        self.assertNotIn("poisoned", records[0]["tools"][1])

    def test_an_empty_poison_list_does_not_pass_the_new_arguments(self):
        path = self._write([_case(
            "EMPTY",
            source="real ticket from the author's private betting log",
            poison=[],
            followups=[],
        )])
        kwargs_seen = []

        def grade(*args, **kwargs):
            kwargs_seen.append(kwargs)
            return {
                "final": {"ticket_result": "LOSS", "net": -1},
                "trace_id": "empty",
                "status": "complete",
                "reason_code": None,
                "turns": 1,
                "tool_calls": 0,
                "wall_clock_s": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            }

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", _no_network):
                with mock.patch("run_eval.grade_ticket", grade):
                    status = main([path, "--run-id", "seam-empty"], opener=_opener)
        self.assertEqual(status, 0, stderr.getvalue())
        self.assertNotIn("tool_runner", kwargs_seen[0])
        self.assertNotIn("followups", kwargs_seen[0])


if __name__ == "__main__":
    unittest.main()
