"""The trace loader. A wrong status-code or a non-object final fails these, not a later check."""
import json
import os
import tempfile
import unittest

from scorer.traces import load_run


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


def _span(name, span_id, attrs, parent=None, status=0, message="", start=1):
    span = {
        "traceId": "abc",
        "spanId": span_id,
        "name": name,
        "startTimeUnixNano": str(start),
        "attributes": [_attr(key, value) for key, value in attrs.items()],
        "status": {"code": status, "message": message},
    }
    if parent:
        span["parentSpanId"] = parent
    return span


def _write(spans):
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, "settlement-traces.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}, handle)
    return directory


class TraceLoaderTests(unittest.TestCase):
    def test_v1_loads_thirtytwo_tickets_in_case_order(self):
        records = load_run("traces/v1")
        self.assertEqual(len(records), 32)
        case_ids = [record["case_id"] for record in records]
        self.assertEqual(case_ids, sorted(case_ids))
        self.assertEqual(case_ids[0], "A01")
        self.assertEqual(case_ids[-1], "X02")

    def test_tool_calls_intvalue_is_an_int_and_final_none_stays_none(self):
        records = {record["case_id"]: record for record in load_run("traces/v1")}
        self.assertIsInstance(records["B06"]["tool_calls"], int)
        self.assertEqual(records["B06"]["tool_calls"], 0)
        self.assertIsNone(records["B05"]["final"])
        self.assertIn("length", records["B05"]["done_reasons"])

    def test_settle_error_is_the_status_message(self):
        records = {record["case_id"]: record for record in load_run("traces/v1")}
        settles = [tool for tool in records["C06"]["tools"] if tool["name"] == "settle_ticket"]
        self.assertEqual(len(settles), 1)
        self.assertEqual(settles[0]["error"], "PRICE_REQUIRED")

    def test_invalid_or_non_object_final_is_none(self):
        root = _span("grade_ticket", "root", {
            "case.id": "T01",
            "input.ticket": "{}",
            "run.tool_calls": 3,
            "output.final": "[1, 2]",
        })
        records = load_run(_write([root]))
        self.assertIsNone(records[0]["final"])
        self.assertEqual(records[0]["tool_calls"], 3)
        self.assertIsInstance(records[0]["tool_calls"], int)

        root["attributes"] = [item for item in root["attributes"] if item["key"] != "output.final"]
        root["attributes"].append(_attr("output.final", "not json"))
        records = load_run(_write([root]))
        self.assertIsNone(records[0]["final"])

        root["attributes"] = [item for item in root["attributes"] if item["key"] != "run.tool_calls"]
        records = load_run(_write([root]))
        self.assertEqual(records[0]["tool_calls"], 0)

    def test_tool_error_follows_status_code_not_the_result_body(self):
        root = _span("grade_ticket", "root", {"case.id": "T02", "input.ticket": "{}", "run.status": "complete"})
        clean = _span(
            "tool.lookup_rule", "tool1",
            {"tool.name": "lookup_rule", "tool.call.args": "{}", "tool.call.result": '{"error": "UNKNOWN_TOPIC"}'},
            parent="root", status=0, message="", start=2,
        )
        failed = _span(
            "tool.settle_ticket", "tool2",
            {"tool.name": "settle_ticket", "tool.call.args": "{}", "tool.call.result": '{"ticket_result": "WIN"}'},
            parent="root", status=2, message="PRICE_REQUIRED", start=3,
        )
        records = load_run(_write([failed, root, clean]))
        tools = records[0]["tools"]
        self.assertEqual([tool["name"] for tool in tools], ["lookup_rule", "settle_ticket"])
        self.assertIsNone(tools[0]["error"])
        self.assertEqual(tools[0]["result"]["error"], "UNKNOWN_TOPIC")
        self.assertEqual(tools[1]["error"], "PRICE_REQUIRED")

    def test_records_are_sorted_by_case_id(self):
        second = _span("grade_ticket", "r2", {"case.id": "T02", "input.ticket": "{}"})
        second["traceId"] = "t2"
        first = _span("grade_ticket", "r1", {"case.id": "T01", "input.ticket": "{}"})
        first["traceId"] = "t1"
        records = load_run(_write([second, first]))
        self.assertEqual([record["case_id"] for record in records], ["T01", "T02"])

    def test_equal_start_times_use_span_ids_and_null_results_stay_none(self):
        root = _span("grade_ticket", "root", {"case.id": "T03", "input.ticket": "{}"})
        last = _span("tool.lookup_rule", "z", {"tool.name": "lookup_rule", "tool.call.result": "null"}, parent="root", start=2)
        first = _span("tool.find_match", "a", {"tool.name": "find_match"}, parent="root", start=2)
        tools = load_run(_write([root, last, first]))[0]["tools"]
        self.assertEqual([t["name"] for t in tools], ["find_match", "lookup_rule"])
        self.assertEqual([t["result"] for t in tools], [None, None])
        self.assertEqual([t["error"] for t in tools], [None, None])

    def test_other_runs_use_the_same_shape(self):
        self.assertEqual(len(load_run("traces/v1-adv")), 2)
        self.assertEqual(len(load_run("traces/smoke-1")), 3)


if __name__ == "__main__":
    unittest.main()
