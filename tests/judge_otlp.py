"""Minimal OTLP runs for the judge tests. Not a second harness entry point."""
import json
import os


def _attr(key, value):
    if isinstance(value, str):
        wrapped = {"stringValue": value}
    elif isinstance(value, int) and not isinstance(value, bool):
        wrapped = {"intValue": str(value)}
    else:
        raise TypeError(key)
    return {"key": key, "value": wrapped}


def settlement_document(records):
    spans = []
    for index, record in enumerate(records):
        trace_id = record["trace_id"]
        root_id = "root%s" % index
        attributes = [
            _attr("case.id", record["case_id"]),
            _attr("input.ticket", json.dumps(record["ticket"], sort_keys=True)),
            _attr("run.status", record["status"]),
            _attr("run.tool_calls", len(record.get("tools") or [])),
        ]
        if record.get("reason") is not None:
            attributes.append(_attr("run.reason_code", record["reason"]))
        if record.get("final") is not None:
            attributes.append(_attr("output.final", json.dumps(record["final"], sort_keys=True)))
        spans.append({
            "attributes": attributes,
            "endTimeUnixNano": "20",
            "name": "grade_ticket",
            "spanId": root_id,
            "startTimeUnixNano": "1",
            "traceId": trace_id,
        })
        for tool_index, tool in enumerate(record.get("tools") or []):
            span = {
                "attributes": [
                    _attr("tool.name", tool["name"]),
                    _attr("tool.call.args", json.dumps(tool.get("args"), sort_keys=True)),
                    _attr("tool.call.result", json.dumps(tool.get("result"), sort_keys=True)),
                ],
                "endTimeUnixNano": "19",
                "name": "tool.%s" % tool["name"],
                "parentSpanId": root_id,
                "spanId": "tool%s%s" % (index, tool_index),
                "startTimeUnixNano": str(2 + tool_index),
                "traceId": trace_id,
            }
            if tool.get("error") is None:
                span["status"] = {"code": 0}
            else:
                span["status"] = {"code": 2, "message": tool["error"]}
            spans.append(span)
    return {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}


def canonical_document(records):
    return json.dumps(settlement_document(records), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


BASE_RECORDS = [
    {
        "case_id": "C1",
        "final": {"mark": "win"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "result"},
        "tools": [{"name": "find_match", "args": {"q": "c1"}, "result": {"ok": True}, "error": None}],
        "trace_id": "tb-c1",
    },
    {
        "case_id": "C2",
        "final": {"mark": "loss"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "total"},
        "tools": [],
        "trace_id": "tb-c2",
    },
    {
        "case_id": "C3",
        "final": {"mark": "win"},
        "reason": "EMPTY_FINAL",
        "status": "incomplete",
        "ticket": {"leg": "score"},
        "tools": [{
            "name": "lookup_rule",
            "args": {"topic": "btts"},
            "result": {"text": "rule"},
            "error": "missing",
        }],
        "trace_id": "tb-c3",
    },
]

# fresh1 contributes C3 (different final). C2 matches the base. C9 is not in the base.
FRESH1_RECORDS = [
    {
        "case_id": "C2",
        "final": {"mark": "loss"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "total"},
        "tools": [],
        "trace_id": "t1-c2",
    },
    {
        "case_id": "C3",
        "final": {"mark": "loss"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "score"},
        "tools": [],
        "trace_id": "t1-c3",
    },
    {
        "case_id": "C9",
        "final": {"mark": "other"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "other"},
        "tools": [],
        "trace_id": "t1-c9",
    },
]

# Named after fresh1, so a differing C1 stays after fresh1's C3 in the plan.
FRESH2_RECORDS = [
    {
        "case_id": "C1",
        "final": {"mark": "loss"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "result"},
        "tools": [],
        "trace_id": "t2-c1",
    },
]

# Named after fresh2. Its C1 differs from the base too, but fresh2 took C1 first, so only C2 is new.
FRESH3_RECORDS = [
    {
        "case_id": "C1",
        "final": {"mark": "void"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "result"},
        "tools": [],
        "trace_id": "t3-c1",
    },
    {
        "case_id": "C2",
        "final": {"mark": "win"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "total"},
        "tools": [],
        "trace_id": "t3-c2",
    },
]

DUPLICATE_RECORDS = [
    {
        "case_id": "C1",
        "final": {"mark": "win"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "result"},
        "tools": [],
        "trace_id": "td-1",
    },
    {
        "case_id": "C1",
        "final": {"mark": "loss"},
        "reason": None,
        "status": "complete",
        "ticket": {"leg": "result"},
        "tools": [],
        "trace_id": "td-2",
    },
]


def write_run(directory, records):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, "settlement-traces.json")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(canonical_document(records))
    return path
