"""Config, run, report and the stale check. run_eval.main is replaced, never called."""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import run_eval
import scorer.rag as rag
from scorer.rag import (
    DEFAULT_CONFIG,
    VERDICT_NO_SHIP,
    faithfulness_bar_holds,
    load_config,
    outcome_bar_holds,
    recall_bar_holds,
    report_files_hold,
)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATEMENT = os.path.join(ROOT, "tests", "fixtures", "rag", "statement.md")


def _run(argv):
    err = io.StringIO()
    out = io.StringIO()
    with redirect_stderr(err), redirect_stdout(out):
        status = rag.main(argv)
    return status, out.getvalue(), err.getvalue()


def _dump(path, obj):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def _config(**updates):
    config = {
        "bars": {
            "faithfulness_lo_at_least": -0.05,
            "outcome_fall_hi_at_most": 0.05,
            "recall_lo_above": 0.0,
        },
        "bootstrap": {"n_boot": 40, "seed": 7},
        "braintrust_experiments": None,
        "dataset": "data/golden/v1.jsonl",
        "dataset_sha256": "pending",
        "json": "reports/rag.json",
        "langsmith_version": None,
        "model": "qwen3:8b",
        "report": "packages/rag-eval/assignment-2/report.md",
        "runs": {"a": "w4-a", "b": "w4-b"},
        "statement": "reports/rag-statement.md",
        "variants": {
            "a": {"rule_match": "exact"},
            "b": {"rule_match": "alias"},
        },
    }
    config.update(updates)
    return config


def _attr(key, value):
    if isinstance(value, int) and not isinstance(value, bool):
        return {"key": key, "value": {"intValue": str(value)}}
    return {"key": key, "value": {"stringValue": value}}


def _otlp(records):
    spans = []
    for index, record in enumerate(records):
        trace_id = "t%d" % index
        root_id = "r%d" % index
        attrs = [
            _attr("case.id", record["case_id"]),
            _attr("input.ticket", json.dumps(record["ticket"])),
            _attr("run.tool_calls", record.get("tool_calls", 0)),
            _attr("run.status", "ok"),
        ]
        if record.get("final") is not None:
            attrs.append(_attr("output.final", json.dumps(record["final"])))
        spans.append({
            "traceId": trace_id,
            "spanId": root_id,
            "name": "grader",
            "startTimeUnixNano": "1",
            "attributes": attrs,
        })
        for tindex, tool in enumerate(record.get("tools") or []):
            span = {
                "traceId": trace_id,
                "spanId": "s%d-%d" % (index, tindex),
                "parentSpanId": root_id,
                "name": "tool.%s" % tool["name"],
                "startTimeUnixNano": str(2 + tindex),
                "attributes": [
                    _attr("tool.name", tool["name"]),
                    _attr("tool.call.args", json.dumps(tool.get("args") or {})),
                    _attr("tool.call.result", json.dumps(tool.get("result") if tool.get("result") is not None else {})),
                ],
            }
            spans.append(span)
    return {"resourceSpans": [{"scopeSpans": [{"spans": spans}]}]}


def _ticket(case_id):
    return {
        "graded_at_et": "2026-10-14",
        "legs": [{
            "away": "Away",
            "home": "Home",
            "leg": 1,
            "market": "Moneyline",
            "selection": "Home",
        }],
    }


def _row(case_id, ticket):
    return {
        "case_id": case_id,
        "contexts": [{"kind": "rule", "leg": 1, "topic": "moneyline_3way"}],
        "expected": {"accept_needs_human": False, "net": None, "ticket_result": "LOSS"},
        "ground_truth": "Ticket must be LOSS.",
        "legs": ticket["legs"],
        "question": json.dumps(ticket, indent=1, ensure_ascii=False),
    }


def _record(case_id, ticket, retrieved=False, tool_calls=0):
    tools = []
    if retrieved:
        tools.append({
            "name": "lookup_rule",
            "args": {"topic": "moneyline_3way"},
            "result": {"topic": "moneyline_3way", "rule": "text"},
        })
    tools.append({
        "name": "settle_ticket",
        "args": {"leg_results": ["NEEDS_HUMAN"]},
        "result": {"ticket_result": "LOSS"},
    })
    return {
        "case_id": case_id,
        "final": {
            "legs": [{"evidence": "no score cited", "leg": 1, "result": "NEEDS_HUMAN"}],
            "ticket_result": "LOSS",
        },
        "ticket": ticket,
        "tool_calls": tool_calls,
        "tools": tools,
    }


def _write_run(directory, run_id, rule_match, records, **meta):
    os.makedirs(directory, exist_ok=True)
    body = {
        "cases_file": "data/golden/v1.jsonl",
        "model": "qwen3:8b",
        "model_digest": "digest-same",
        "ollama_version": "0.0.test",
        "rule_match": rule_match,
        "run_id": run_id,
        "think": False,
    }
    body.update(meta)
    with open(os.path.join(directory, "run_meta.json"), "w", encoding="utf-8") as handle:
        json.dump(body, handle)
    with open(os.path.join(directory, "settlement-traces.json"), "w", encoding="utf-8") as handle:
        json.dump(_otlp(records), handle)


class _World:
    def __init__(self, root):
        self.root = root
        self.rows = []
        tickets = {}
        for case_id in ("S002", "S001"):
            ticket = _ticket(case_id)
            tickets[case_id] = ticket
            self.rows.append(_row(case_id, ticket))
        v1 = os.path.join(root, "data", "golden", "v1.jsonl")
        os.makedirs(os.path.dirname(v1))
        text = "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
            for row in sorted(self.rows, key=lambda row: row["case_id"])
        )
        with open(v1, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        self.digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        statement = os.path.join(root, "reports", "rag-statement.md")
        os.makedirs(os.path.dirname(statement))
        with open(_STATEMENT, "r", encoding="utf-8") as handle:
            body = handle.read()
        with open(statement, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        self.records = {
            "S001": _record("S001", tickets["S001"], retrieved=False, tool_calls=2),
            "S002": _record("S002", tickets["S002"], retrieved=True, tool_calls=3),
        }
        _write_run(
            os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
            [self.records["S002"], self.records["S001"]])
        _write_run(
            os.path.join(root, "traces", "w4-b"), "w4-b", "alias",
            [self.records["S001"], self.records["S002"]])
        self.config_path = os.path.join(root, DEFAULT_CONFIG)
        _dump(self.config_path, _config(dataset_sha256=self.digest))

    def report_argv(self):
        return ["report", "--config", self.config_path, "--root", self.root]


class ConfigTests(unittest.TestCase):
    def test_the_committed_config_matches_the_contract_and_a_null_hash_holds(self):
        config = load_config(os.path.join(ROOT, DEFAULT_CONFIG))
        self.assertEqual(config["dataset"], "data/golden/v1.jsonl")
        self.assertIsNone(config["dataset_sha256"])
        self.assertEqual(config["model"], "qwen3:8b")
        self.assertEqual(config["variants"]["a"], {"rule_match": "exact"})
        self.assertEqual(config["variants"]["b"], {"rule_match": "alias"})
        self.assertEqual(config["runs"], {"a": "w4-a", "b": "w4-b"})
        self.assertEqual(config["bootstrap"], {"n_boot": 10000, "seed": 7})
        self.assertEqual(config["bars"], {
            "faithfulness_lo_at_least": -0.05,
            "outcome_fall_hi_at_most": 0.05,
            "recall_lo_above": 0.0,
        })
        self.assertIsNone(config["langsmith_version"])
        self.assertIsNone(config["braintrust_experiments"])
        sha_path = os.path.join(ROOT, "data", "golden", "v1.sha256")
        if config["dataset_sha256"] is None:
            return
        with open(sha_path, encoding="utf-8") as handle:
            digest = handle.read().split()[0]
        self.assertEqual(config["dataset_sha256"], digest)

    def test_unknown_and_missing_keys_are_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            extra = _config()
            extra["top_k"] = 1
            _dump(path, extra)
            with self.assertRaises(rag.ConfigError):
                load_config(path)
            missing = _config()
            del missing["bars"]["recall_lo_above"]
            _dump(path, missing)
            with self.assertRaises(rag.ConfigError):
                load_config(path)

    def test_extra_keys_inside_variant_and_filled_version_objects_are_refused(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "config.json")
            extra = _config()
            extra["variants"]["a"]["top_k"] = 4
            _dump(path, extra)
            with self.assertRaises(rag.ConfigError):
                load_config(path)
            filled = _config()
            filled["langsmith_version"] = {"as_of": "t", "dataset_id": "d", "extra": "no"}
            _dump(path, filled)
            with self.assertRaises(rag.ConfigError):
                load_config(path)
            filled = _config()
            filled["braintrust_experiments"] = {"a": "one", "b": "two", "c": "three"}
            _dump(path, filled)
            with self.assertRaises(rag.ConfigError):
                load_config(path)
            filled = _config()
            filled["langsmith_version"] = {"as_of": "t", "dataset_id": "d"}
            filled["braintrust_experiments"] = {"a": "one", "b": "two"}
            _dump(path, filled)
            self.assertEqual(load_config(path)["langsmith_version"]["dataset_id"], "d")

    def test_wrong_types_are_refused(self):
        samples = []
        rule = _config()
        rule["variants"]["b"]["rule_match"] = "fuzzy"
        samples.append(rule)
        run_id = _config()
        run_id["runs"]["a"] = "-bad"
        samples.append(run_id)
        boot = _config()
        boot["bootstrap"]["n_boot"] = True
        samples.append(boot)
        boot = _config()
        boot["bootstrap"]["n_boot"] = 0
        samples.append(boot)
        boot = _config()
        boot["bootstrap"]["seed"] = False
        samples.append(boot)
        bar = _config()
        bar["bars"]["recall_lo_above"] = True
        samples.append(bar)
        path = _config()
        path["dataset"] = 1
        samples.append(path)
        path = _config()
        path["statement"] = "/tmp/statement.md"
        samples.append(path)
        digest = _config()
        digest["dataset_sha256"] = 1
        samples.append(digest)
        with tempfile.TemporaryDirectory() as root:
            file_path = os.path.join(root, "config.json")
            for sample in samples:
                _dump(file_path, sample)
                with self.assertRaises(rag.ConfigError):
                    load_config(file_path)


class RunTests(unittest.TestCase):
    def test_run_passes_the_variant_list_and_the_real_main_is_not_called(self):
        called = {}

        def fake(argv=None, opener=None):
            called["argv"] = list(argv)
            called["opener"] = opener
            return 0

        original = run_eval.main
        run_eval.main = fake
        try:
            with tempfile.TemporaryDirectory() as root:
                world = _World(root)
                for variant, rule_match, run_id in (
                    ("a", "exact", "w4-a"),
                    ("b", "alias", "w4-b"),
                ):
                    shutil.rmtree(os.path.join(root, "traces", run_id))
                    called.clear()
                    status, _out, err = _run([
                        "run", "--config", world.config_path, "--root", root,
                        "--variant", variant,
                    ])
                    self.assertEqual(status, 0, err)
                    self.assertEqual(err, "")
                    self.assertEqual(called["argv"], [
                        os.path.join(root, "data", "golden", "v1.jsonl"),
                        "--run-id", run_id,
                        "--model", "qwen3:8b",
                        "--rule-match", rule_match,
                    ])
                    self.assertIsNone(called["opener"])
        finally:
            run_eval.main = original

    def test_run_hands_run_eval_the_file_it_hashed_from_any_directory(self):
        # run_eval opens the cases path from the working directory. A relative
        # path would make run check one file and grade another, or none, when
        # the command is not started from the root.
        seen = {}

        def fake(argv=None, opener=None):
            seen["path"] = argv[0]
            if os.path.isfile(argv[0]):
                with open(argv[0], "rb") as handle:
                    seen["digest"] = hashlib.sha256(handle.read()).hexdigest()
            else:
                seen["digest"] = None
            return 0

        original = run_eval.main
        run_eval.main = fake
        here = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as elsewhere:
                world = _World(root)
                shutil.rmtree(os.path.join(root, "traces", "w4-a"))
                os.chdir(elsewhere)
                try:
                    status, _out, err = _run([
                        "run", "--config", world.config_path, "--root", root, "--variant", "a",
                    ])
                finally:
                    os.chdir(here)
                self.assertEqual(status, 0, err)
                self.assertEqual(seen["digest"], world.digest)
                self.assertEqual(
                    os.path.relpath(seen["path"], root), os.path.join("data", "golden", "v1.jsonl"))
        finally:
            os.chdir(here)
            run_eval.main = original

    def test_run_refusals_do_not_call_main_or_write(self):
        called = []

        def fake(argv=None, opener=None):
            called.append(argv)
            return 0

        original = run_eval.main
        run_eval.main = fake
        try:
            with tempfile.TemporaryDirectory() as root:
                world = _World(root)
                cases = [
                    (["run", "--config", world.config_path, "--root", root, "--variant", "c"],
                     "variant must be a or b\n"),
                ]
                broken = os.path.join(root, "broken.json")
                bad = _config(dataset_sha256=world.digest)
                bad["variants"]["a"]["window_days"] = 7
                _dump(broken, bad)
                cases.append((
                    ["run", "--config", broken, "--root", root, "--variant", "a"],
                    "variants.a is refused\n",
                ))
                null_hash = os.path.join(root, "null.json")
                _dump(null_hash, _config(dataset_sha256=None))
                cases.append((
                    ["run", "--config", null_hash, "--root", root, "--variant", "a"],
                    "dataset_sha256 is null\n",
                ))
                v1_path = os.path.join(root, "data", "golden", "v1.jsonl")
                original_v1 = open(v1_path, "rb").read()
                os.remove(v1_path)
                called[:] = []
                status, _out, err = _run([
                    "run", "--config", world.config_path, "--root", root, "--variant", "a",
                ])
                self.assertEqual(status, 2)
                self.assertEqual(err, "v1 is missing\n")
                self.assertEqual(called, [])
                with open(v1_path, "wb") as handle:
                    handle.write(b"{}\n")
                called[:] = []
                status, _out, err = _run([
                    "run", "--config", world.config_path, "--root", root, "--variant", "a",
                ])
                self.assertEqual(status, 2)
                self.assertEqual(err, "v1 bytes do not match dataset_sha256\n")
                self.assertEqual(called, [])
                with open(v1_path, "wb") as handle:
                    handle.write(original_v1)
                for argv, message in cases:
                    called[:] = []
                    status, _out, err = _run(argv)
                    self.assertEqual(status, 2)
                    self.assertEqual(err, message)
                    self.assertEqual(called, [])
                called[:] = []
                status, _out, err = _run([
                    "run", "--config", world.config_path, "--root", root, "--variant", "a",
                ])
                self.assertEqual(status, 2)
                self.assertEqual(err, "run already exists\n")
                self.assertEqual(called, [])
        finally:
            run_eval.main = original


class ReportTests(unittest.TestCase):
    def test_report_on_the_committed_config_refuses(self):
        status, _out, err = _run(["report"])
        self.assertEqual(status, 2)
        self.assertEqual(err, "dataset_sha256 is null\n")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "reports", "rag.json")))
        self.assertFalse(os.path.exists(os.path.join(
            ROOT, "packages", "rag-eval", "assignment-2", "report.md")))

    def test_a_fixture_report_is_byte_stable_and_prints_no_amount(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            status, _out, err = _run(world.report_argv())
            self.assertEqual(status, 0, err)
            report_path = os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md")
            json_path = os.path.join(root, "reports", "rag.json")
            text = open(report_path, "rb").read()
            body = open(json_path, "rb").read()
            status, _out, err = _run(world.report_argv())
            self.assertEqual(status, 0, err)
            self.assertEqual(open(report_path, "rb").read(), text)
            self.assertEqual(open(json_path, "rb").read(), body)
            self.assertEqual(body, rag.canonical_json(json.loads(body.decode("utf-8"))).encode("utf-8"))
            decoded = text.decode("utf-8")
            self.assertNotIn(root, decoded)
            self.assertNotIn("stake", decoded)
            self.assertNotIn("payout", decoded)
            self.assertNotIn("price", decoded)
            statement = open(_STATEMENT, encoding="utf-8").read()
            self.assertTrue(decoded.startswith(statement))
            document = json.loads(body.decode("utf-8"))
            self.assertEqual(document["dataset"]["n"], 2)
            self.assertEqual(document["dataset"]["sha256"], world.digest)
            self.assertEqual(document["verdict"], VERDICT_NO_SHIP)
            self.assertFalse(document["ab"]["context_recall"]["bar"]["holds"])
            self.assertEqual(document["ab"]["context_recall"]["bar"]["value"], 0.0)
            self.assertEqual(document["ab"]["context_recall"]["lo"], 0.0)
            self.assertEqual([row["case_id"] for row in document["groundedness"]], ["S001"])
            self.assertEqual(document["groundedness"][0]["tool_calls"], 2)
            self.assertIn("S001 recall 0.000", decoded)
            self.assertIn("tool_calls 2", decoded)
            self.assertNotIn("S002 recall", decoded)
            self.assertIn("verdict: no-ship", decoded)
            self.assertIn("recall: lower bound 0.000 above 0.000: no", decoded)
            for word in ("mean ", "interval ", "scored ", "paired ", "left "):
                self.assertIn(word, decoded)

    def test_recall_does_not_hold_at_exactly_zero_and_an_empty_difference_does_not(self):
        self.assertFalse(recall_bar_holds(0.0, 1, 0.0))
        self.assertTrue(recall_bar_holds(0.001, 1, 0.0))
        self.assertFalse(recall_bar_holds(None, 0, 0.0))
        self.assertTrue(faithfulness_bar_holds(-0.05, 2, -0.05))
        self.assertFalse(faithfulness_bar_holds(-0.051, 2, -0.05))
        holds, diff = outcome_bar_holds(0, 0, 0, 0, 0.05)
        self.assertFalse(holds)
        self.assertIsNone(diff)

    def test_report_refusals_write_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            report_path = os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md")
            json_path = os.path.join(root, "reports", "rag.json")

            holder = {"world": world}

            def refuse(message, mutate):
                current = holder["world"]
                if os.path.exists(report_path):
                    os.remove(report_path)
                if os.path.exists(json_path):
                    os.remove(json_path)
                try:
                    mutate(current)
                    status, _out, err = _run(current.report_argv())
                    self.assertEqual(status, 2, message)
                    self.assertEqual(err, message)
                    self.assertFalse(os.path.exists(report_path))
                    self.assertFalse(os.path.exists(json_path))
                finally:
                    for name in os.listdir(root):
                        path = os.path.join(root, name)
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    holder["world"] = _World(root)

            def _meta(variant, **updates):
                path = os.path.join(root, "traces", "w4-" + variant, "run_meta.json")
                with open(path, encoding="utf-8") as handle:
                    meta = json.load(handle)
                meta.update(updates)
                for key in updates:
                    if updates[key] is None:
                        del meta[key]
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(meta, handle)

            def null_hash(_current):
                _dump(_current.config_path, _config(dataset_sha256=None))

            def mismatch(_current):
                with open(os.path.join(root, "data", "golden", "v1.jsonl"), "a", encoding="utf-8") as handle:
                    handle.write(" ")

            def drop_run(_current):
                shutil.rmtree(os.path.join(root, "traces", "w4-b"))

            def drop_meta(_current):
                os.remove(os.path.join(root, "traces", "w4-a", "run_meta.json"))

            def drop_traces(_current):
                os.remove(os.path.join(root, "traces", "w4-a", "settlement-traces.json"))

            def drop_digest(_current):
                _meta("a", model_digest=None)

            def drop_version(_current):
                _meta("b", ollama_version=None)

            def differ_digest(_current):
                _meta("b", model_digest="digest-other")

            def differ_version(_current):
                _meta("b", ollama_version="9.9.test")

            def differ_model(_current):
                _meta("a", model="other:8b")

            def differ_cases(_current):
                _meta("a", cases_file="data/gold.json")

            def differ_rule(_current):
                _meta("a", rule_match="alias")

            def duplicate(current):
                _write_run(
                    os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
                    [current.records["S001"], current.records["S001"]])

            def unknown(current):
                extra = dict(current.records["S001"])
                extra["case_id"] = "Z99"
                _write_run(
                    os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
                    [current.records["S001"], current.records["S002"], extra])

            def missing_case(current):
                _write_run(
                    os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
                    [current.records["S001"]])

            def wrong_ticket(current):
                changed = dict(current.records["S001"])
                changed["ticket"] = {"legs": []}
                _write_run(
                    os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
                    [changed, current.records["S002"]])

            def blank_statement(_current):
                path = os.path.join(root, "reports", "rag-statement.md")
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(" \n")

            def missing_statement(_current):
                os.remove(os.path.join(root, "reports", "rag-statement.md"))

            pairs = (
                ("dataset_sha256 is null\n", null_hash),
                ("v1 bytes do not match dataset_sha256\n", mismatch),
                ("variant b run is missing\n", drop_run),
                ("variant a run_meta.json is missing\n", drop_meta),
                ("variant a settlement-traces.json is missing\n", drop_traces),
                ("variant a model_digest is missing\n", drop_digest),
                ("variant b ollama_version is missing\n", drop_version),
                ("model_digest differs\n", differ_digest),
                ("ollama_version differs\n", differ_version),
                ("model differs from the config\n", differ_model),
                ("cases_file differs from the dataset\n", differ_cases),
                ("rule_match differs from the variant\n", differ_rule),
                ("two records for one case\n", duplicate),
                ("a record for a case v1 does not hold\n", unknown),
                ("a v1 case has no record\n", missing_case),
                ("a record ticket differs from its question\n", wrong_ticket),
                ("statement is blank\n", blank_statement),
                ("statement is missing\n", missing_statement),
            )
            for message, mutate in pairs:
                with self.subTest(message=message.strip()):
                    refuse(message, mutate)

    def test_the_committed_report_is_absent_while_its_runs_are(self):
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "traces", "w4-a")))
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "traces", "w4-b")))
        self.assertTrue(report_files_hold(ROOT))

    def test_the_stale_check_fails_when_the_report_exists_without_its_runs(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            shutil.rmtree(os.path.join(root, "traces", "w4-a"))
            self.assertTrue(report_files_hold(root))
            report_path = os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md")
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as handle:
                handle.write("stale\n")
            self.assertFalse(report_files_hold(root))
            os.remove(report_path)
            self.assertTrue(report_files_hold(root))
            _write_run(
                os.path.join(root, "traces", "w4-a"), "w4-a", "exact",
                [world.records["S001"], world.records["S002"]])
            self.assertFalse(report_files_hold(root))
            status, _out, err = _run(world.report_argv())
            self.assertEqual(status, 0, err)
            self.assertTrue(report_files_hold(root))
            with open(report_path, "ab") as handle:
                handle.write(b" ")
            self.assertFalse(report_files_hold(root))

    def test_help_imports_without_a_model(self):
        env = os.environ.copy()
        env.pop("ESPN_LIVE", None)
        for command in (
            [sys.executable, "-m", "scorer.rag", "--help"],
            [sys.executable, "run_eval.py", "--help"],
        ):
            done = subprocess.run(
                command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(done.returncode, 0)
        done = subprocess.run(
            [sys.executable, "-c", "import scorer.checks"],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
