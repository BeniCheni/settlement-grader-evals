"""Exec target for Promptfoo.

python3 -m grader.redteam_target --cases FILE <case_id> [ignored...]

The case id is the first positional argument. Anything after it is ignored.
Stdout is one JSON line. Every other message goes to stderr. The run directory
is traces/<REDTEAM_RUN_ID>/ beside this file's repository, never the working
directory. Writes take an exclusive lock and replace the trace file atomically.
"""
import argparse
import fcntl
import json
import os
import re
import sys
import tempfile

import grader.agent as agent
from grader.agent import DEFAULT_BUDGETS, SYSTEM_PROMPT, grade_ticket
from grader.poison import poison_runner
from grader.tracer import Tracer
from run_eval import (
    SetupReadError,
    expected_of,
    outcome_match,
    read_ollama_setup,
    seam_refusal,
    summary,
    ticket_from_case,
)
from scorer.traces import records_from_otlp


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MODEL = "qwen3:8b"
_FIXTURE = "fixture"


def repo_root():
    """The repository root, from this file's location."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None, opener=None):
    parser = argparse.ArgumentParser(prog="python3 -m grader.redteam_target")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--fixture", default=None)
    parser.add_argument("case_id")
    parser.add_argument("ignored", nargs="*")
    args = parser.parse_args(argv)

    run_id = os.environ.get("REDTEAM_RUN_ID")
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        return _refuse("REDTEAM_RUN_ID is refused")

    try:
        with open(args.cases, encoding="utf-8") as handle:
            cases = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _refuse("cases file is unreadable")
    case = _find_case(cases, args.case_id)
    if case is None:
        return _refuse("case is not in the file")
    message = seam_refusal(case)
    if message:
        return _refuse(message)
    legs = case.get("legs")
    if not isinstance(legs, list) or not all(isinstance(leg, dict) for leg in legs):
        return _refuse("case is unusable")

    replies = None
    if args.fixture is not None:
        replies = _read_fixture(args.fixture)
        if isinstance(replies, str):
            return _refuse(replies)
        setup = (_FIXTURE, _FIXTURE)
    else:
        if opener is None:
            import urllib.request
            opener = urllib.request.urlopen
        try:
            setup = read_ollama_setup(_MODEL, opener)
        except SetupReadError as error:
            return _refuse(str(error))

    tracer = Tracer("settlement-grader", resource={
        "deployment.environment": "eval",
        "eval.run_id": run_id,
        "gen_ai.request.model": _MODEL,
    })
    root_attrs = {
        "case.id": case["case_id"],
        "case.category": case.get("category"),
        "ticket.summary": summary(case),
    }
    ticket_kwargs = {"model": _MODEL, "think": False, "root_attrs": root_attrs}
    poison = case.get("poison") or []
    followups = case.get("followups") or []
    if poison:
        ticket_kwargs["tool_runner"] = poison_runner(poison)
    if followups:
        ticket_kwargs["followups"] = tuple(followups)

    previous = agent._chat
    if replies is not None:
        agent._chat = _fixture_chat(replies)
    try:
        result = grade_ticket(ticket_from_case(case), tracer, **ticket_kwargs)
    finally:
        agent._chat = previous

    exp_result, exp_net = expected_of(case)
    expected = case.get("expected") if isinstance(case.get("expected"), dict) else {}
    matched = outcome_match(
        result["final"], exp_result, exp_net, expected.get("accept_needs_human", False))
    root = repo_root()
    error = commit_call(
        root, run_id, args.cases, setup, tracer.to_otlp(), matched)
    if error:
        return _refuse(error)

    record = None
    for row in records_from_otlp(tracer.to_otlp()):
        if row["trace_id"] == result["trace_id"]:
            record = row
            break
    if record is None:
        return _refuse("trace was not recorded")
    tools = []
    for tool in record["tools"]:
        entry = {"name": tool.get("name"), "args": tool.get("args")}
        if tool.get("poisoned") is True:
            entry["poisoned"] = True
        tools.append(entry)
    line = {
        "status": result["status"],
        "reason_code": result["reason_code"],
        "final": result["final"],
        "final_text": result["final_text"],
        "tools": tools,
    }
    if followups:
        line["followups_sent"] = record.get("followups_sent")
    sys.stdout.write(json.dumps(line, ensure_ascii=False) + "\n")
    return 0


def _refuse(message):
    sys.stderr.write("%s\n" % message)
    return 2


def _find_case(cases, case_id):
    if not isinstance(cases, list):
        return None
    for case in cases:
        if isinstance(case, dict) and case.get("case_id") == case_id:
            return case
    return None


def _read_fixture(path):
    try:
        with open(path, encoding="utf-8") as handle:
            replies = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "fixture is unreadable"
    if not isinstance(replies, list):
        return "fixture is unreadable"
    return replies


def _fixture_chat(replies):
    index = {"n": 0}

    def chat(payload, timeout):
        n = index["n"]
        index["n"] += 1
        if n >= len(replies) or not isinstance(replies[n], dict):
            return {"message": {"role": "assistant", "content": ""}, "done_reason": "fixture_exhausted"}
        return replies[n]

    return chat


def _lock_path(root, run_id):
    traces = os.path.join(root, "traces")
    os.makedirs(traces, exist_ok=True)
    return os.path.join(traces, run_id + ".lock")


class _Lock(object):
    def __init__(self, path):
        self.handle = open(path, "a+")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)

    def close(self):
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()


def _atomic(directory, name, payload, indent):
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + name + ".", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if indent is None:
                json.dump(payload, handle, ensure_ascii=False)
            else:
                json.dump(payload, handle, indent=indent, ensure_ascii=False)
        os.replace(tmp, os.path.join(directory, name))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _cases_relpath(root, cases_path):
    return os.path.relpath(os.path.abspath(cases_path), root)


def _fresh_meta(root, run_id, cases_path, setup, matched):
    return {
        "run_id": run_id,
        "cases_file": _cases_relpath(root, cases_path),
        "model": _MODEL,
        "ollama_version": setup[0],
        "model_digest": setup[1],
        "think": False,
        "budgets": DEFAULT_BUDGETS,
        "system_prompt": SYSTEM_PROMPT,
        "n_cases": 1,
        "outcome_matches": 1 if matched else 0,
    }


def commit_call(root, run_id, cases_path, setup, document, matched):
    """Append this call's spans. A different setup writes nothing.

    An exclusive lock covers the read and the replace. The replace is atomic.
    A directory that holds one of the two files without the other, a traces
    file that is not an OTLP document, or a call naming a different cases
    file is refused and left as it is. Returns an error string, or None.
    """
    run_dir = os.path.join(root, "traces", run_id)
    lock = _Lock(_lock_path(root, run_id))
    try:
        meta_path = os.path.join(run_dir, "run_meta.json")
        traces_path = os.path.join(run_dir, "settlement-traces.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as handle:
                    meta = json.load(handle)
            except (OSError, UnicodeError, json.JSONDecodeError):
                return "run metadata is unreadable"
            if not isinstance(meta, dict):
                return "run metadata is unreadable"
            if (meta.get("ollama_version") != setup[0]
                    or meta.get("model_digest") != setup[1]
                    or meta.get("model") != _MODEL):
                return "setup differs from the run"
            if meta.get("cases_file") != _cases_relpath(root, cases_path):
                return "cases file differs from the run"
            try:
                n_cases = int(meta.get("n_cases") or 0)
                matches = int(meta.get("outcome_matches") or 0)
            except (TypeError, ValueError):
                return "run metadata is unreadable"
            meta["n_cases"] = n_cases + 1
            meta["outcome_matches"] = matches + (1 if matched else 0)
            if not os.path.isfile(traces_path):
                return "traces are missing"
            try:
                with open(traces_path, encoding="utf-8") as handle:
                    existing = json.load(handle)
            except (OSError, UnicodeError, json.JSONDecodeError):
                return "traces are unreadable"
            if not isinstance(existing, dict) or not isinstance(existing.get("resourceSpans"), list):
                return "traces are unreadable"
            existing["resourceSpans"].extend(document.get("resourceSpans") or [])
            _atomic(run_dir, "settlement-traces.json", existing, None)
            _atomic(run_dir, "run_meta.json", meta, 1)
            return None
        if os.path.isfile(traces_path):
            return "run metadata is missing"
        meta = _fresh_meta(root, run_id, cases_path, setup, matched)
        _atomic(run_dir, "settlement-traces.json", document, None)
        _atomic(run_dir, "run_meta.json", meta, 1)
        return None
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
