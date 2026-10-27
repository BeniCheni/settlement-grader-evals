"""A minimal OpenTelemetry span recorder that writes OTLP JSON — the format the
course Trace Viewer (docs/trace-viewer) uploads. No SDK, no exporter, no network."""
import json
import os
import time


def _attr(k, v):
    if isinstance(v, bool):
        val = {"boolValue": v}
    elif isinstance(v, int):
        val = {"intValue": str(v)}
    elif isinstance(v, float):
        val = {"doubleValue": v}
    elif isinstance(v, str):
        val = {"stringValue": v}
    else:
        val = {"stringValue": json.dumps(v, ensure_ascii=False)}
    return {"key": k, "value": val}


class Tracer:
    def __init__(self, service_name, scope="settlement.grader", resource=None):
        self.service_name = service_name
        self.scope = scope
        self.resource = resource or {}
        self.spans = []

    def start(self, name, trace_id=None, parent=None, attrs=None):
        span = {
            "traceId": trace_id or (parent["traceId"] if parent else os.urandom(16).hex()),
            "spanId": os.urandom(8).hex(),
            "name": name,
            "kind": 1,
            "startTimeUnixNano": str(time.time_ns()),
            "_attrs": dict(attrs or {}),
            "status": {"code": 0, "message": ""},
        }
        if parent:
            span["parentSpanId"] = parent["spanId"]
        self.spans.append(span)
        return span

    def end(self, span, attrs=None, error=None):
        span["endTimeUnixNano"] = str(time.time_ns())
        span["_attrs"].update(attrs or {})
        if error:
            span["status"] = {"code": 2, "message": str(error)}

    def to_otlp(self):
        spans = []
        for s in self.spans:
            out = {k: v for k, v in s.items() if not k.startswith("_")}
            out["attributes"] = [_attr(k, v) for k, v in s["_attrs"].items() if v is not None]
            spans.append(out)
        res = {"service.name": self.service_name, **self.resource}
        return {"resourceSpans": [{
            "resource": {"attributes": [_attr(k, v) for k, v in res.items()]},
            "scopeSpans": [{"scope": {"name": self.scope}, "spans": spans}],
        }]}
