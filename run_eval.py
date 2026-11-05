#!/usr/bin/env python3
"""Run the settlement grader over a case file.

Writes, under traces/<run_id>/:
  settlement-traces.json  OTLP JSON — upload to the Trace Viewer (viewer/index.html)
  results.csv             one row per case: grader output vs expected (a code check, not a verdict)
  annotations.csv         blank pass_fail / note sheet for the human pass
  run_meta.json           model, options, budgets, git-free provenance

Usage:
  python3 run_eval.py data/gold.json [--only A01,C03] [--show-expected] [--think] [--model qwen3:8b]
                       [--prompt-file FILE] [--drop-field FIELD]
"""
import argparse
import copy
import csv
import http.client
import json
import os
import sys
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit

from grader.agent import DEFAULT_BUDGETS, OLLAMA_URL, SYSTEM_PROMPT, grade_ticket
from grader.poison import PoisonError, poison_runner, validate_poison
from grader.tracer import Tracer

TICKET_FIELDS = ["book", "bet_type", "stake", "stake_kind", "boost_or_token",
                 "ticket_price_american", "printed_payout", "slip_text"]
LEG_FIELDS = ["leg", "selection", "market", "line", "leg_price_american", "fixture", "home", "away",
              "league", "kickoff_et", "market_wording_on_slip"]


def ticket_from_case(c):
    t = {k: c[k] for k in TICKET_FIELDS if c.get(k) is not None}
    t["legs"] = [{k: leg[k] for k in LEG_FIELDS if leg.get(k) is not None} for leg in c["legs"]]
    t["graded_at_et"] = c.get("graded_at_et", "2026-10-14")
    return t


def expected_of(c):
    e = c.get("expected") or c.get("log_grade") or {}
    return e.get("ticket_result"), e.get("net")


def summary(c):
    legs = len(c["legs"])
    price = c.get("ticket_price_american") or "?"
    return f"{c['case_id']} · {c.get('book')} {c.get('bet_type')} · {legs} leg{'s' if legs > 1 else ''} · ${c.get('stake')} @ {price}"


class SetupReadError(Exception):
    """The Ollama version or the model digest could not be read."""


class PromptFileError(Exception):
    """The prompt file cannot be used. main exits with status 2 and writes nothing."""


def seam_refusal(case):
    """Why this case's poison or followups cannot run, or None.

    The message names the case id and not the poison text. An empty list is
    not a use of the seam.
    """
    if not isinstance(case, dict):
        return None
    case_id = case.get("case_id")
    label = case_id if isinstance(case_id, str) and case_id else "a case"
    if "poison" in case and not isinstance(case.get("poison"), list):
        return "%s: poison is refused" % label
    if "followups" in case and not isinstance(case.get("followups"), list):
        return "%s: followups are refused" % label
    poison = case.get("poison") or []
    followups = case.get("followups") or []
    if poison:
        try:
            validate_poison(poison)
        except PoisonError:
            return "%s: poison is refused" % label
    for item in followups:
        if not isinstance(item, str):
            return "%s: followups are refused" % label
    if (poison or followups) and case.get("source") != "synthetic":
        return "%s: poison and followups require source synthetic" % label
    return None


def drop_ticket_fields(ticket, fields):
    """A copy of ticket with each named ticket or leg field removed."""
    kept = copy.deepcopy(ticket)
    for field in fields:
        if field in TICKET_FIELDS:
            kept.pop(field, None)
        else:
            for leg in kept.get("legs") or []:
                if isinstance(leg, dict):
                    leg.pop(field, None)
    return kept


def _unknown_drop_field(fields):
    allowed = set(TICKET_FIELDS) | set(LEG_FIELDS)
    for field in fields:
        if field not in allowed:
            return field
    return None


def _read_prompt_file(text):
    """The file's bytes, decoded as UTF-8 and not stripped.

    Imported here, and only when --prompt-file is given: scorer.judge reaches
    scorer.checks, which imports this module.
    """
    from scorer.judge import JudgeError, relative_path

    try:
        path = relative_path(text, "prompt file")
    except JudgeError as error:
        raise PromptFileError(str(error)) from None
    try:
        with open(path, "r", encoding="utf-8", newline="") as handle:
            raw = handle.read()
    except OSError:
        raise PromptFileError("prompt file is unreadable") from None
    except UnicodeDecodeError:
        raise PromptFileError("prompt file is unreadable") from None
    if raw.strip() == "":
        raise PromptFileError("prompt file is empty")
    return raw


_SETUP_TIMEOUT_S = 30


def _ollama_url(path):
    """Same local server as grader.agent.OLLAMA_URL, with a different path."""
    parts = urlsplit(OLLAMA_URL)
    return "%s://%s%s" % (parts.scheme, parts.netloc, path)


def _nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _fetch_json(opener, url, failure):
    request = urllib.request.Request(url)
    try:
        with opener(request, timeout=_SETUP_TIMEOUT_S) as response:
            raw = response.read()
    except (OSError, http.client.HTTPException):
        raise SetupReadError(failure) from None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode()
        except UnicodeError:
            raise SetupReadError(failure) from None
    if not isinstance(raw, str):
        raise SetupReadError(failure)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise SetupReadError(failure) from None
    if not isinstance(payload, dict):
        raise SetupReadError(failure)
    return payload


def read_ollama_setup(model, opener):
    """Return (ollama_version, model_digest).

    opener matches urllib.request.urlopen: opener(request, timeout=seconds).
    A missing model, a failed request, or a reply without the value raises
    SetupReadError. The digest is never null.
    """
    version_payload = _fetch_json(
        opener, _ollama_url("/api/version"), "could not read the Ollama version")
    version = version_payload.get("version")
    if not _nonempty_string(version):
        raise SetupReadError("could not read the Ollama version")
    tags_payload = _fetch_json(
        opener, _ollama_url("/api/tags"), "could not read the model digest")
    models = tags_payload.get("models")
    if not isinstance(models, list):
        raise SetupReadError("could not read the model digest")
    for entry in models:
        if not isinstance(entry, dict) or entry.get("name") != model:
            continue
        digest = entry.get("digest")
        if not _nonempty_string(digest):
            raise SetupReadError("could not read the model digest")
        return version, digest
    raise SetupReadError("model %s is not in the Ollama tags" % model)


def outcome_match(final, exp_result, exp_net, accept_needs_human=False):
    """Code check of rubric lines O1 + O2. NEEDS_HUMAN only counts where a rule
    mandates escalation (Beni's decision #2, 14 Oct)."""
    if not final:
        return False
    if accept_needs_human and str(final.get("ticket_result")).upper() == "NEEDS_HUMAN":
        return True
    if str(final.get("ticket_result")).upper() != str(exp_result).upper():
        return False
    got = final.get("net")
    if exp_net is None or got is None:
        return exp_net is None and got is None
    try:
        return abs(float(got) - float(exp_net)) <= 0.01
    except (TypeError, ValueError):
        return False


def main(argv=None, opener=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--show-expected", action="store_true",
                    help="put the expected result on each root span (annotators see it)")
    ap.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    ap.add_argument("--prompt-file", default=None,
                    help="system prompt for every ticket, read once and not stripped")
    ap.add_argument("--drop-field", action="append", default=[], metavar="FIELD",
                    help="remove this ticket or leg field before the model sees the ticket")
    ap.add_argument("--guard-input", default=None,
                    help="comma-separated input guardrails, applied after --drop-field")
    ap.add_argument("--guard-output", default=None,
                    help="comma-separated output guardrails")
    ap.add_argument("--guard-rubric", default="rubrics-guardrails/ticket_free_text.md")
    ap.add_argument("--guard-adapter", default="ollama:llama3.1:8b")
    args = ap.parse_args(argv)
    unknown = _unknown_drop_field(args.drop_field)
    if unknown is not None:
        sys.stderr.write("unknown field %s\n" % unknown)
        return 2
    system_prompt = SYSTEM_PROMPT
    if args.prompt_file is not None:
        try:
            system_prompt = _read_prompt_file(args.prompt_file)
        except PromptFileError as error:
            sys.stderr.write("%s\n" % error)
            return 2
    try:
        with open(args.cases) as f:
            cases = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError):
        sys.stderr.write("cases file is unreadable\n")
        return 2
    if not isinstance(cases, list):
        sys.stderr.write("cases file is unreadable\n")
        return 2
    for case in cases:
        message = seam_refusal(case)
        if message:
            sys.stderr.write("%s\n" % message)
            return 2
    guard_input = []
    guard_output = []
    guard_adapter = None
    guard_rubric_text = None
    if args.guard_input is not None or args.guard_output is not None:
        # Imported only when a guard flag is set, the same way a prompt file is.
        from grader.guarded import grade_ticket_guarded
        from scorer.guardrails import (
            INPUT_GUARDS, OUTPUT_GUARDS, _split_names, input_guard, load_guard_rubric, output_guard,
        )
        from scorer.judge import JudgeError, _guard_rubrics, build_adapter
        try:
            if args.guard_input is not None:
                guard_input = _split_names(args.guard_input, INPUT_GUARDS, "guard-input")
            if args.guard_output is not None:
                guard_output = _split_names(args.guard_output, OUTPUT_GUARDS, "guard-output")
            if any(name in ("g2", "g3") for name in guard_input):
                rubric = load_guard_rubric(args.guard_rubric)
                _guard_rubrics([rubric], cases)
                guard_adapter = build_adapter(args.guard_adapter, None)
                guard_rubric_text = rubric["text"]
        except JudgeError as error:
            sys.stderr.write("%s\n" % error)
            return 2
    if opener is None:
        opener = urllib.request.urlopen
    try:
        ollama_version, model_digest = read_ollama_setup(args.model, opener)
    except SetupReadError as error:
        sys.stderr.write("%s\n" % error)
        return 1

    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["case_id"] in keep]

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces", args.run_id)
    os.makedirs(out_dir, exist_ok=True)
    tracer = Tracer("settlement-grader", resource={
        "deployment.environment": "eval", "eval.run_id": args.run_id, "gen_ai.request.model": args.model})

    rows = []
    for i, c in enumerate(cases, 1):
        exp_result, exp_net = expected_of(c)
        root_attrs = {"case.id": c["case_id"], "case.category": c.get("category"), "ticket.summary": summary(c)}
        print(f"[{i}/{len(cases)}] {summary(c)} …", flush=True)
        ticket = ticket_from_case(c)
        if args.drop_field:
            ticket = drop_ticket_fields(ticket, args.drop_field)
        ticket_kwargs = {"model": args.model, "think": args.think, "root_attrs": root_attrs}
        if args.prompt_file is not None:
            ticket_kwargs["system_prompt"] = system_prompt
        poison = c.get("poison") or []
        followups = c.get("followups") or []
        if poison:
            ticket_kwargs["tool_runner"] = poison_runner(poison)
        if followups:
            ticket_kwargs["followups"] = tuple(followups)
        if guard_input or guard_output:
            guards_in = tuple(
                input_guard(name, c["case_id"], guard_adapter, guard_rubric_text)
                for name in guard_input)
            guards_out = tuple(output_guard(name) for name in guard_output)
            r = grade_ticket_guarded(
                ticket, tracer, input_guardrails=guards_in, output_guardrails=guards_out,
                **ticket_kwargs)
        else:
            r = grade_ticket(ticket, tracer, **ticket_kwargs)
        match = outcome_match(r["final"], exp_result, exp_net,
                              (c.get("expected") or {}).get("accept_needs_human", False))
        if args.show_expected:
            root = next(s for s in tracer.spans if s["traceId"] == r["trace_id"] and "parentSpanId" not in s)
            root["_attrs"].update({"eval.expected_ticket_result": exp_result, "eval.expected_net": exp_net,
                                   "eval.outcome_match": match})
        final = r["final"] or {}
        rows.append({
            "case_id": c["case_id"], "category": c.get("category"), "trace_id": r["trace_id"],
            "run_status": r["status"], "reason_code": r["reason_code"] or "",
            "got_ticket_result": final.get("ticket_result", ""), "got_net": final.get("net", ""),
            "exp_ticket_result": exp_result, "exp_net": exp_net, "outcome_match": match,
            "turns": r["turns"], "tool_calls": r["tool_calls"], "wall_clock_s": r["wall_clock_s"],
            "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
        })
        print(f"    {r['status']} {r['reason_code'] or ''} got={final.get('ticket_result')} {final.get('net')} "
              f"exp={exp_result} {exp_net} match={match} ({r['wall_clock_s']}s, {r['tool_calls']} tools)", flush=True)

    with open(os.path.join(out_dir, "settlement-traces.json"), "w") as f:
        json.dump(tracer.to_otlp(), f, ensure_ascii=False)
    with open(os.path.join(out_dir, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out_dir, "annotations.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["trace_id", "case_id", "pass_fail", "note"])
        for r in rows:
            w.writerow([r["trace_id"], r["case_id"], "", ""])
    with open(os.path.join(out_dir, "run_meta.json"), "w") as f:
        meta = {
            "run_id": args.run_id,
            "cases_file": os.path.relpath(os.path.abspath(args.cases), os.path.dirname(os.path.abspath(__file__))),
            "model": args.model,
            "ollama_version": ollama_version,
            "model_digest": model_digest,
            "think": args.think,
            "budgets": DEFAULT_BUDGETS,
            "system_prompt": system_prompt,
            "n_cases": len(rows),
            "outcome_matches": sum(r["outcome_match"] for r in rows),
        }
        if args.drop_field:
            meta["drop_fields"] = list(args.drop_field)
        if args.guard_input is not None:
            meta["guard_input"] = guard_input
        if args.guard_output is not None:
            meta["guard_output"] = guard_output
        if guard_adapter is not None:
            meta["guard_model"] = guard_adapter.model
            meta["guard_digest"] = guard_adapter.digest
        json.dump(meta, f, indent=1)
    print(f"\n{sum(r['outcome_match'] for r in rows)}/{len(rows)} outcome matches · traces → {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
