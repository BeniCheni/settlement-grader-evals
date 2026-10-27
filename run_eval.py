#!/usr/bin/env python3
"""Run the settlement grader over a case file.

Writes, under traces/<run_id>/:
  settlement-traces.json  OTLP JSON — upload to the Trace Viewer (viewer/index.html)
  results.csv             one row per case: grader output vs expected (a code check, not a verdict)
  annotations.csv         blank pass_fail / note sheet for the human pass
  run_meta.json           model, options, budgets, git-free provenance

Usage:
  python3 run_eval.py data/gold.json [--only A01,C03] [--show-expected] [--think] [--model qwen3:8b]
"""
import argparse
import csv
import json
import os
from datetime import datetime

from grader.agent import DEFAULT_BUDGETS, SYSTEM_PROMPT, grade_ticket
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases")
    ap.add_argument("--only", default="")
    ap.add_argument("--model", default="qwen3:8b")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--show-expected", action="store_true",
                    help="put the expected result on each root span (annotators see it)")
    ap.add_argument("--run-id", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    args = ap.parse_args()

    with open(args.cases) as f:
        cases = json.load(f)
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
        r = grade_ticket(ticket_from_case(c), tracer, model=args.model, think=args.think, root_attrs=root_attrs)
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
        json.dump({"run_id": args.run_id, "cases_file": os.path.relpath(os.path.abspath(args.cases), os.path.dirname(os.path.abspath(__file__))), "model": args.model,
                   "think": args.think, "budgets": DEFAULT_BUDGETS, "system_prompt": SYSTEM_PROMPT,
                   "n_cases": len(rows), "outcome_matches": sum(r["outcome_match"] for r in rows)}, f, indent=1)
    print(f"\n{sum(r['outcome_match'] for r in rows)}/{len(rows)} outcome matches · traces → {out_dir}")


if __name__ == "__main__":
    main()
