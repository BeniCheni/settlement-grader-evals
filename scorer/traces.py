"""One record per ticket from an OTLP run directory.

Attribute values are typed. An intValue arrives as a string. The final answer is
None when it is absent, invalid JSON, or not a JSON object.
"""
import json
import os


def _value(raw):
    if not isinstance(raw, dict):
        return None
    if "stringValue" in raw:
        return raw["stringValue"]
    if "intValue" in raw:
        return int(raw["intValue"])
    if "doubleValue" in raw:
        return raw["doubleValue"]
    if "boolValue" in raw:
        return raw["boolValue"]
    return None


def _attrs(span):
    found = {}
    for item in span.get("attributes") or []:
        found[item.get("key")] = _value(item.get("value"))
    return found


def _parse_json(text):
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _start_key(span):
    raw = span.get("startTimeUnixNano") or "0"
    try:
        start = int(raw)
    except (TypeError, ValueError):
        start = 0
    return (start, span.get("spanId") or "")


def _status_error(span):
    """The tool error is status code 2, not a key inside the result."""
    status = span.get("status") or {}
    code = status.get("code")
    try:
        errored = int(code) == 2
    except (TypeError, ValueError):
        errored = False
    if not errored:
        return None
    message = status.get("message")
    return "" if message is None else message


def _spans(document):
    found = []
    for resource in document.get("resourceSpans") or []:
        for scope in resource.get("scopeSpans") or []:
            found.extend(scope.get("spans") or [])
    return found


def _record(trace_id, group):
    roots = [span for span in group if not span.get("parentSpanId")]
    if len(roots) != 1:
        raise ValueError("trace %s has %s root spans" % (trace_id, len(roots)))
    root_attrs = _attrs(roots[0])
    ordered = sorted(group, key=_start_key)
    tools = []
    done_reasons = []
    for span in ordered:
        name = span.get("name") or ""
        attrs = _attrs(span)
        if name.startswith("tool."):
            tools.append({
                "name": attrs.get("tool.name"),
                "args": _parse_json(attrs.get("tool.call.args")),
                "result": _parse_json(attrs.get("tool.call.result")),
                "error": _status_error(span),
            })
        elif name == "llm.generate":
            done_reasons.append(attrs.get("ollama.done_reason"))
    final = _parse_json(root_attrs.get("output.final"))
    ticket = _parse_json(root_attrs.get("input.ticket"))
    tool_calls = root_attrs.get("run.tool_calls")
    return {
        "trace_id": trace_id,
        "case_id": root_attrs.get("case.id"),
        "ticket": ticket if isinstance(ticket, dict) else {},
        "status": root_attrs.get("run.status"),
        "reason": root_attrs.get("run.reason_code"),
        "tool_calls": 0 if tool_calls is None else int(tool_calls),
        "final": final if isinstance(final, dict) else None,
        "tools": tools,
        "done_reasons": done_reasons,
    }


def load_run(run_dir):
    """Records for one run, sorted by case_id."""
    path = os.path.join(run_dir, "settlement-traces.json")
    with open(path, encoding="utf-8") as handle:
        document = json.load(handle)
    grouped = {}
    for span in _spans(document):
        grouped.setdefault(span.get("traceId"), []).append(span)
    records = [_record(trace_id, group) for trace_id, group in grouped.items()]
    records.sort(key=lambda record: record.get("case_id") or "")
    return records
