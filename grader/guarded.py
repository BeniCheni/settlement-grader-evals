"""Wrap grade_ticket with input and output guardrails.

With both lists empty this is grade_ticket. A block replaces the answer with a
held final that names nothing. The trace keeps the decisions. An output block
also keeps the grader's own final under output.final_withheld, and the root
span is not an error span.
"""
import copy
import json
import time

from grader.agent import grade_ticket
from scorer.traces import records_from_otlp


_HELD_NOTE = "held for human review"


def grade_ticket_guarded(ticket, tracer, input_guardrails=(), output_guardrails=(), **grade_kwargs):
    """Same keys as grade_ticket. The first blocking guardrail stops the rest."""
    if not input_guardrails and not output_guardrails:
        return grade_ticket(ticket, tracer, **grade_kwargs)
    decisions = []
    if _blocked(input_guardrails, "input", ticket, decisions):
        return _input_block(ticket, tracer, grade_kwargs, decisions)
    result = grade_ticket(ticket, tracer, **grade_kwargs)
    root = _root(tracer, result["trace_id"])
    record = _record_for(tracer, result["trace_id"])
    output_hit = _blocked(output_guardrails, "output", record, decisions)
    if decisions:
        root["_attrs"]["guardrail.decisions"] = json.dumps(decisions, ensure_ascii=False)
    if not output_hit:
        return result
    return _apply_output_block(ticket, result, root)


def _blocked(guardrails, side, payload, decisions):
    """True when a guardrail on this side blocks. Each call gets its own copy."""
    for name, fn in guardrails:
        started = time.perf_counter()
        try:
            outcome = fn(copy.deepcopy(payload))
            if (not isinstance(outcome, tuple) or len(outcome) != 2
                    or type(outcome[0]) is not bool or not isinstance(outcome[1], str)):
                raise TypeError("bad guardrail result")
            blocked, reason = outcome
        except Exception:
            blocked, reason = True, "guardrail error"
        latency_ms = int(round((time.perf_counter() - started) * 1000))
        decisions.append({
            "guardrail": name,
            "side": side,
            "blocked": blocked,
            "reason": reason,
            "latency_ms": latency_ms,
        })
        if blocked:
            return True
    return False


def _model_view(grade_kwargs):
    options = {"temperature": 0, "num_ctx": 8192, "num_predict": 1024, **(grade_kwargs.get("options") or {})}
    model = grade_kwargs.get("model", "qwen3:8b")
    think = bool(grade_kwargs.get("think", False))
    return model, options, think


def _root_name(root_attrs):
    title = (root_attrs or {}).get("ticket.summary")
    if title:
        return "grade_ticket · %s" % title
    return "grade_ticket"


def _held_final(ticket):
    legs = ticket.get("legs") if isinstance(ticket, dict) else None
    if not isinstance(legs, list):
        legs = []
    held_legs = []
    for index, leg in enumerate(legs, start=1):
        number = index
        if isinstance(leg, dict) and type(leg.get("leg")) is int:
            number = leg["leg"]
        held_legs.append({"leg": number, "result": "NEEDS_HUMAN", "evidence": _HELD_NOTE})
    return {
        "legs": held_legs,
        "ticket_result": "NEEDS_HUMAN",
        "net": None,
        "notes": _HELD_NOTE,
    }


def _held_attrs(held):
    text = json.dumps(held, ensure_ascii=False)
    return text, {
        "output.final_text": text,
        "output.final": text,
        "output.ticket_result": "NEEDS_HUMAN",
        "output.net": None,
        "output.leg_results": [leg.get("result") for leg in held["legs"] if isinstance(leg, dict)],
    }


def _root(tracer, trace_id):
    for span in tracer.spans:
        if span["traceId"] == trace_id and "parentSpanId" not in span:
            return span
    raise RuntimeError("missing root")


def _record_for(tracer, trace_id):
    for record in records_from_otlp(tracer.to_otlp()):
        if record["trace_id"] == trace_id:
            return record
    raise RuntimeError("missing trace")


def _input_block(ticket, tracer, grade_kwargs, decisions):
    model, options, think = _model_view(grade_kwargs)
    root_attrs = grade_kwargs.get("root_attrs")
    started = time.time()
    root = tracer.start(_root_name(root_attrs), attrs={
        **(root_attrs or {}),
        "input.ticket": json.dumps(ticket, ensure_ascii=False),
        "gen_ai.request.model": model,
        "gen_ai.request.temperature": options["temperature"],
        "ollama.think": think,
    })
    held = _held_final(ticket)
    text, outputs = _held_attrs(held)
    wall = round(time.time() - started, 2)
    tracer.end(root, {
        "run.status": "blocked",
        "run.reason_code": "GUARDRAIL_INPUT",
        "run.turns": 0,
        "run.tool_calls": 0,
        "run.retries": 0,
        "run.tool_call_counts": {},
        "run.wall_clock_s": wall,
        "gen_ai.usage.input_tokens": 0,
        "gen_ai.usage.output_tokens": 0,
        "guardrail.decisions": json.dumps(decisions, ensure_ascii=False),
        **outputs,
    }, error=None)
    return {
        "status": "blocked",
        "reason_code": "GUARDRAIL_INPUT",
        "final": held,
        "final_text": text,
        "trace_id": root["traceId"],
        "turns": 0,
        "tool_calls": 0,
        "retries": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "wall_clock_s": wall,
    }


def _apply_output_block(ticket, result, root):
    held = _held_final(ticket)
    text, outputs = _held_attrs(held)
    root["_attrs"].update({
        "run.status": "blocked",
        "run.reason_code": "GUARDRAIL_OUTPUT",
        "output.final_withheld": json.dumps(result.get("final"), ensure_ascii=False),
    })
    root["_attrs"].update(outputs)
    root["status"] = {"code": 0, "message": ""}
    updated = dict(result)
    updated["status"] = "blocked"
    updated["reason_code"] = "GUARDRAIL_OUTPUT"
    updated["final"] = held
    updated["final_text"] = text
    return updated
