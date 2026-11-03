"""Idle requests for one gold ticket stay byte for byte the committed golden.

The fake chat calls each of the four tools and then finishes complete, so the
later payloads carry tool-result messages. Nothing here passes a new argument.
"""
import hashlib
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

import run_eval
from grader.agent import SYSTEM_PROMPT, grade_ticket
from grader.tracer import Tracer
from run_eval import main, ticket_from_case


GOLDEN_PATH = "tests/fixtures/redteam/idle-requests.json"
SYSTEM_PROMPT_SHA256 = "26938a29ebb319367ae33765016038485cba1e5b39e5205f0420f9e1962cc831"

CALLS = (
    ("find_match", {"team": "Portugal", "opponent": "Denmark", "date_et": "2026-10-01"}),
    ("get_match_facts", {"event_id": "401861096"}),
    ("lookup_rule", {"topic": "moneyline_3way"}),
    ("settle_ticket", {
        "leg_results": ["W"],
        "stake": 10.0,
        "stake_kind": "cash",
        "ticket_price_american": "+115",
        "printed_payout": 21.5,
    }),
)
FINAL_TEXT = (
    '{"legs":[{"leg":1,"result":"W","evidence":"score_regulation_90"}],'
    '"ticket_result":"WIN","net":11.5,"notes":"graded"}'
)


def scripted_reply(index):
    """The reply for request index, counting from zero."""
    if index < len(CALLS):
        name, args = CALLS[index]
        return {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": name, "arguments": args}}],
            },
            "done_reason": "stop",
            "prompt_eval_count": index + 1,
            "eval_count": 1,
        }
    return {
        "message": {"role": "assistant", "content": FINAL_TEXT},
        "done_reason": "stop",
        "prompt_eval_count": len(CALLS) + 1,
        "eval_count": 2,
    }


def load_golden():
    with open(GOLDEN_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def capture_requests(case):
    """json.dumps of each payload _chat receives, and grade_ticket's return."""
    seen = []

    def chat(payload, timeout):
        seen.append(json.dumps(payload))
        return scripted_reply(len(seen) - 1)

    with mock.patch("grader.agent._chat", chat):
        result = grade_ticket(ticket_from_case(case), Tracer("settlement-grader"))
    return seen, result


class IdleRequestTests(unittest.TestCase):
    def test_system_prompt_sha256(self):
        digest = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
        self.assertEqual(digest, SYSTEM_PROMPT_SHA256)
        self.assertEqual(load_golden()["system_prompt_sha256"], SYSTEM_PROMPT_SHA256)

    def test_one_gold_ticket_matches_the_golden_requests(self):
        golden = load_golden()
        with open("data/gold.json", encoding="utf-8") as handle:
            a01 = next(row for row in json.load(handle) if row["case_id"] == "A01")
        self.assertEqual(golden["case"], a01)
        seen, result = capture_requests(a01)
        self.assertEqual(result["status"], "complete")
        self.assertIsNone(result["reason_code"])
        self.assertEqual(result["tool_calls"], 4)
        self.assertEqual(result["turns"], 5)
        self.assertEqual(seen, golden["requests"])
        for raw in seen:
            self.assertEqual(json.loads(raw)["messages"][0]["content"], SYSTEM_PROMPT)
        last = json.loads(seen[-1])
        tool_names = [message["tool_name"] for message in last["messages"] if message["role"] == "tool"]
        self.assertEqual(tool_names, [name for name, _args in CALLS])
        for raw in seen[1:]:
            roles = [message["role"] for message in json.loads(raw)["messages"]]
            self.assertIn("tool", roles)

    def test_run_meta_keeps_its_keys_without_new_flags(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        work = tempfile.TemporaryDirectory(dir=".")
        self.addCleanup(work.cleanup)
        cases_path = os.path.join(os.path.relpath(work.name), "cases.json")
        with open(cases_path, "w", encoding="utf-8") as handle:
            json.dump([load_golden()["case"]], handle)

        def chat(payload, timeout):
            return {
                "message": {"role": "assistant", "content": '{"ticket_result":"WIN","net":0}'},
                "done_reason": "stop",
            }

        def opener(request, timeout=None):
            class Body:
                def __init__(self, data):
                    self.data = data

                def read(self):
                    return self.data

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

            if request.full_url.endswith("/api/version"):
                return Body(b'{"version":"0.6.2"}')
            if request.full_url.endswith("/api/tags"):
                return Body(b'{"models":[{"name":"qwen3:8b","digest":"sha256:abc"}]}')
            raise AssertionError("unexpected url")

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            with mock.patch("urllib.request.urlopen", opener):
                with mock.patch("grader.agent._chat", chat):
                    with mock.patch.object(run_eval, "__file__", os.path.join(scratch.name, "run_eval.py")):
                        status = main([cases_path, "--run-id", "idle-meta"])
        self.assertEqual(status, 0, stderr.getvalue())
        meta_path = os.path.join(scratch.name, "traces", "idle-meta", "run_meta.json")
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        self.assertEqual(set(meta), {
            "run_id", "cases_file", "model", "ollama_version", "model_digest", "think",
            "budgets", "system_prompt", "n_cases", "outcome_matches",
        })
        self.assertEqual(meta["system_prompt"], SYSTEM_PROMPT)
        self.assertNotIn("drop_fields", meta)


if __name__ == "__main__":
    unittest.main()
