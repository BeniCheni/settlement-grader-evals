"""The poison mark on a tool span, and the one OTLP reader both callers use."""
import json
import os
import tempfile
import unittest

from scorer.judge import render_case
from scorer.traces import load_run, records_from_otlp


def _attr(key, value):
    if isinstance(value, bool):
        raw = {"boolValue": value}
    elif isinstance(value, int):
        raw = {"intValue": str(value)}
    elif isinstance(value, float):
        raw = {"doubleValue": value}
    else:
        raw = {"stringValue": value}
    return {"key": key, "value": raw}


def _span(name, span_id, attrs, parent=None, trace_id="abc", status=0, message="", start=1):
    span = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": str(start),
        "attributes": [_attr(key, value) for key, value in attrs.items()],
        "status": {"code": status, "message": message},
    }
    if parent:
        span["parentSpanId"] = parent
    return span


def _document(spans):
    return {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}


def _write(spans):
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "settlement-traces.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(_document(spans), handle)
    return directory


class PoisonMarkTests(unittest.TestCase):
    def _pair(self, marked):
        attrs = {
            "tool.name": "lookup_rule",
            "tool.call.args": '{"topic":"general"}',
            "tool.call.result": '{"topic":"general","rule":"text"}',
        }
        if marked:
            attrs["tool.poisoned"] = True
        root = _span("grade_ticket", "root", {
            "case.id": "T1",
            "input.ticket": "{}",
            "run.status": "complete",
            "run.tool_calls": 1,
        })
        tool = _span("tool.lookup_rule", "tool", attrs, parent="root", start=2)
        return [root, tool]

    def test_records_from_otlp_matches_load_run_on_the_same_spans(self):
        first = _span("grade_ticket", "r1", {"case.id": "B", "input.ticket": "{}"}, trace_id="t-b")
        second_root = _span("grade_ticket", "r2", {"case.id": "A", "input.ticket": "{}"}, trace_id="t-a")
        marked = _span(
            "tool.lookup_rule", "tool",
            {
                "tool.name": "lookup_rule",
                "tool.call.args": "{}",
                "tool.call.result": '{"rule":"changed"}',
                "tool.poisoned": True,
            },
            parent="r2", trace_id="t-a", start=2,
        )
        spans = [first, marked, second_root]
        document = _document(spans)
        from_file = load_run(_write(spans))
        direct = records_from_otlp(document)
        self.assertEqual(sorted(direct, key=lambda row: row["case_id"]), from_file)
        self.assertEqual([row["case_id"] for row in from_file], ["A", "B"])
        self.assertEqual(from_file[0]["tools"][0]["poisoned"], True)
        self.assertEqual(direct[0]["tools"], [])

    def test_only_a_boolean_mark_adds_the_key(self):
        marked = load_run(_write(self._pair(True)))
        self.assertEqual(marked[0]["tools"][0]["poisoned"], True)
        plain = load_run(_write(self._pair(False)))
        self.assertNotIn("poisoned", plain[0]["tools"][0])
        self.assertEqual(set(plain[0]["tools"][0]), {"name", "args", "result", "error"})

        root = self._pair(False)[0]
        tool = self._pair(False)[1]
        tool["attributes"].append(_attr("tool.poisoned", "true"))
        stringy = load_run(_write([root, tool]))
        self.assertNotIn("poisoned", stringy[0]["tools"][0])

    def test_render_names_a_poisoned_fact_and_leaves_an_unmarked_record(self):
        record = {
            "case_id": "C1",
            "ticket": {"a": 1},
            "tools": [
                {"name": "lookup_rule", "args": {}, "result": {"rule": "text"}, "error": None},
            ],
            "final": None,
            "status": "complete",
            "reason": None,
        }
        unmarked = render_case(record)
        self.assertNotIn("poisoned:", unmarked)
        marked = dict(record)
        marked["tools"] = [dict(record["tools"][0], poisoned=True)]
        text = render_case(marked)
        self.assertIn("poisoned: not a real fact", text)
        self.assertIn("result:", text)
        without = dict(marked["tools"][0])
        del without["poisoned"]
        again = dict(record)
        again["tools"] = [without]
        self.assertEqual(render_case(again), unmarked)


if __name__ == "__main__":
    unittest.main()
