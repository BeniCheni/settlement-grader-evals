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
from scorer.stats import paired_difference
from scorer.rag import (
    DEFAULT_CONFIG,
    VERDICT_NO_SHIP,
    VERDICT_SHIP,
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


def _world_of(root, cases, no_final_in_b=()):
    """A root with v1, the statement, both runs and a config, from one tuple per case.

    Each case is (case_id, a_retrieves, b_retrieves, a_matches, b_matches). A
    variant that retrieves calls lookup_rule for the needed topic; one that does
    not match answers WIN against the row's LOSS. A case named in no_final_in_b
    has no final and no settle_ticket in variant b, so its faithfulness is None.
    """
    rows = []
    records = {"a": [], "b": []}
    for case_id, a_retrieves, b_retrieves, a_matches, b_matches in cases:
        ticket = _ticket(case_id)
        rows.append(_row(case_id, ticket))
        for variant, retrieves, matches in (("a", a_retrieves, a_matches), ("b", b_retrieves, b_matches)):
            record = _record(case_id, ticket, retrieved=retrieves, tool_calls=2)
            if not matches:
                record["final"]["ticket_result"] = "WIN"
                record["tools"][-1]["result"]["ticket_result"] = "WIN"
            if variant == "b" and case_id in no_final_in_b:
                record["final"] = None
                record["tools"] = [tool for tool in record["tools"] if tool["name"] != "settle_ticket"]
            records[variant].append(record)
    v1 = os.path.join(root, "data", "golden", "v1.jsonl")
    os.makedirs(os.path.dirname(v1))
    text = "".join(
        json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n"
        for row in sorted(rows, key=lambda row: row["case_id"]))
    with open(v1, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    statement = os.path.join(root, "reports", "rag-statement.md")
    os.makedirs(os.path.dirname(statement))
    shutil.copyfile(_STATEMENT, statement)
    _write_run(os.path.join(root, "traces", "w4-a"), "w4-a", "exact", records["a"])
    _write_run(os.path.join(root, "traces", "w4-b"), "w4-b", "alias", records["b"])
    config_path = os.path.join(root, DEFAULT_CONFIG)
    _dump(config_path, _config(dataset_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()))
    return config_path


def _report_of(test, root, config_path):
    status, _out, err = _run(["report", "--config", config_path, "--root", root])
    test.assertEqual(status, 0, err)
    with open(os.path.join(root, "reports", "rag.json"), encoding="utf-8") as handle:
        document = json.load(handle)
    with open(os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md"), encoding="utf-8") as handle:
        text = handle.read()
    return document, text


def _config_hash_holds(root):
    """True while dataset_sha256 is null, or when it equals data/golden/v1.sha256 and v1's bytes."""
    config = load_config(os.path.join(root, DEFAULT_CONFIG))
    if config["dataset_sha256"] is None:
        return True
    sha_path = os.path.join(root, "data", "golden", "v1.sha256")
    v1_path = os.path.join(root, config["dataset"])
    if not os.path.isfile(sha_path) or not os.path.isfile(v1_path):
        return False
    with open(sha_path, encoding="utf-8") as handle:
        recorded = handle.read().split()[0]
    with open(v1_path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return config["dataset_sha256"] == recorded == digest


class ConfigTests(unittest.TestCase):
    def test_the_committed_config_matches_the_contract_in_every_lifecycle_state(self):
        config = load_config(os.path.join(ROOT, DEFAULT_CONFIG))
        self.assertEqual(config["dataset"], "data/golden/v1.jsonl")
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
        self.assertEqual(config["statement"], "reports/rag-statement.md")
        self.assertEqual(config["report"], "packages/rag-eval/assignment-2/report.md")
        self.assertEqual(config["json"], "reports/rag.json")
        # dataset_sha256 is null until the PM writes v1's hash after the freeze; from
        # then on it equals data/golden/v1.sha256 and the sha256 of v1's bytes.
        self.assertTrue(_config_hash_holds(ROOT))
        # The two ids are null until the owner fills them. load_config has already
        # refused any other shape, so a filled value holds exactly its written keys.
        if config["langsmith_version"] is not None:
            self.assertEqual(set(config["langsmith_version"]), {"as_of", "dataset_id"})
        if config["braintrust_experiments"] is not None:
            self.assertEqual(set(config["braintrust_experiments"]), {"a", "b"})

    def test_the_hash_check_can_fail(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            sha_path = os.path.join(root, "data", "golden", "v1.sha256")
            # The hash is written but v1.sha256 is not.
            self.assertFalse(_config_hash_holds(root))
            with open(sha_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("%s  data/golden/v1.jsonl\n" % world.digest)
            self.assertTrue(_config_hash_holds(root))
            with open(sha_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("%s  data/golden/v1.jsonl\n" % ("0" * 64))
            self.assertFalse(_config_hash_holds(root))
            with open(sha_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("%s  data/golden/v1.jsonl\n" % world.digest)
            # v1's bytes moved under the hash.
            with open(os.path.join(root, "data", "golden", "v1.jsonl"), "ab") as handle:
                handle.write(b" ")
            self.assertFalse(_config_hash_holds(root))
            _dump(world.config_path, _config(dataset_sha256=None))
            self.assertTrue(_config_hash_holds(root))

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
            filled["langsmith_version"] = {"as_of": "", "dataset_id": "d"}
            _dump(path, filled)
            with self.assertRaises(rag.ConfigError):
                load_config(path)
            filled = _config()
            filled["braintrust_experiments"] = {"a": "one", "b": 2}
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
    def test_the_committed_config_reports_only_once_both_runs_exist(self):
        config = load_config(os.path.join(ROOT, DEFAULT_CONFIG))
        report_path = os.path.join(ROOT, config["report"])
        json_path = os.path.join(ROOT, config["json"])
        runs_present = all(
            os.path.isdir(os.path.join(ROOT, "traces", config["runs"][variant]))
            for variant in ("a", "b"))
        if config["dataset_sha256"] is None:
            # Before the freeze: the command refuses before it reads a run, and writes nothing.
            status, out, err = _run(["report"])
            self.assertEqual(status, 2)
            self.assertEqual(out, "")
            self.assertEqual(err, "dataset_sha256 is null\n")
        elif not runs_present:
            # After the hash and before step 9's runs: the refusal names the missing run.
            # prepare_report writes nothing, where the command would write into this tree
            # once both runs exist.
            with self.assertRaises(rag.ReportError) as caught:
                rag.prepare_report(config, ROOT, os.path.join(ROOT, DEFAULT_CONFIG))
            self.assertRegex(str(caught.exception), r"^variant [ab] run is missing$")
        if config["dataset_sha256"] is None or not runs_present:
            self.assertFalse(os.path.exists(report_path))
            self.assertFalse(os.path.exists(json_path))
        # In every state the committed files match the runs: absent while a run is, and
        # equal to report's output once both runs, the statement and the report are in.
        self.assertTrue(report_files_hold(ROOT))

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
            self.assertIn("supported 2 of 2 claims legs left 0", decoded)
            # The header holds "mean", "scored" and "interval" too, so the rows are pinned
            # whole: S002 retrieved the one needed rule and S001 retrieved nothing.
            self.assertIn("| context_recall | 0.500 | 2 | 0 | [0.000, 1.000] | found 1 of 2 needed |\n", decoded)
            self.assertIn("| context_precision | 0.500 | 2 | 0 | [0.000, 1.000] | relevant 1 of 1 retrieved |\n", decoded)
            self.assertIn("| faithfulness | 1.000 | 2 | 0 | [1.000, 1.000] | supported 2 of 2 claims legs left 0 |\n", decoded)
            self.assertIn("| answer_relevancy | 1.000 | 2 | 0 | [1.000, 1.000] | held 8 of 8 tests |\n", decoded)

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

            def differ_think(_current):
                _meta("b", think=True)

            def differ_prompt(_current):
                _meta("b", system_prompt="another prompt")

            def extra_drop(_current):
                _meta("a", drop_fields=["slip_text"])

            def extra_guard(_current):
                _meta("b", guard_output=["o1"])

            def differ_budgets(_current):
                _meta("a", budgets={"max_turns": 1})

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
                ("run_meta think differs\n", differ_think),
                ("run_meta system_prompt differs\n", differ_prompt),
                ("run_meta drop_fields differs\n", extra_drop),
                ("run_meta guard_output differs\n", extra_guard),
                ("run_meta budgets differs\n", differ_budgets),
                ("statement is blank\n", blank_statement),
                ("statement is missing\n", missing_statement),
            )
            for message, mutate in pairs:
                with self.subTest(message=message.strip()):
                    refuse(message, mutate)

    def test_retrieval_and_generation_print_as_separate_tables(self):
        # Ruling 39. Each variant prints two tables, one row per scorer. The
        # A/B, the candidates and the runs stay lines.
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            status, _out, err = _run(world.report_argv())
            self.assertEqual(status, 0, err)
            report_path = os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md")
            with open(report_path, encoding="utf-8") as handle:
                text = handle.read()
        header = "| scorer | mean | scored | none | interval | k of n |"
        rule = "| --- | --- | --- | --- | --- | --- |"
        self.assertEqual(text.count(header), 4)
        self.assertEqual(text.count(rule), 4)
        self.assertNotIn("\ncontext_recall mean ", text)
        self.assertNotIn("\nfaithfulness mean ", text)
        for variant in ("a", "b"):
            section = text.split("## Variant %s\n" % variant, 1)[1].split("\n## ", 1)[0]
            retrieval, generation = section.split("### Generation\n", 1)
            self.assertIn("### Retrieval\n", retrieval)
            self.assertIn("| context_recall |", retrieval)
            self.assertIn("| context_precision |", retrieval)
            self.assertNotIn("| faithfulness |", retrieval)
            self.assertIn("| faithfulness |", generation)
            self.assertIn("legs left ", generation)
            self.assertIn("| answer_relevancy |", generation)
            self.assertNotIn("| context_recall |", generation)
        ab = text.split("## A/B\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("\ncontext_recall delta ", ab)
        self.assertNotIn(header, ab)
        candidates = text.split("## Groundedness candidates\n", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(header, candidates)
        runs = text.split("## Runs\n", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn(header, runs)

    def test_every_table_cell_prints_its_column_for_each_variant(self):
        # Ruling 39's rows. A table that prints the wrong number under the right
        # header must turn this red, so every cell of every row is pinned for a
        # world where the two variants differ on every scorer: A retrieves the
        # needed rule on S001 and S002 only, B on all four, and B's S003 has no
        # final. Means and k of n are hand-derived; an interval that is not a point
        # is read from the JSON and must bracket its mean.
        ids = ["S001", "S002", "S003", "S004"]
        header = "| scorer | mean | scored | none | interval | k of n |"
        rule = "| --- | --- | --- | --- | --- | --- |"
        with tempfile.TemporaryDirectory() as root:
            cases = [(case_id, case_id in ("S001", "S002"), True, True, True) for case_id in ids]
            document, text = _report_of(self, root, _world_of(root, cases, no_final_in_b=("S003",)))
            a_recall = document["variants"]["a"]["retrieval"]["context_recall"]
            a_precision = document["variants"]["a"]["retrieval"]["context_precision"]
            b_relevancy = document["variants"]["b"]["generation"]["answer_relevancy"]
            for block, mean in ((a_recall, 0.5), (a_precision, 0.5), (b_relevancy, 0.75)):
                self.assertEqual(block["mean"], mean)
                self.assertLess(block["lo"], mean)
                self.assertGreater(block["hi"], mean)
            spread = {
                "a_recall": "[%.3f, %.3f]" % (a_recall["lo"], a_recall["hi"]),
                "a_precision": "[%.3f, %.3f]" % (a_precision["lo"], a_precision["hi"]),
                "b_relevancy": "[%.3f, %.3f]" % (b_relevancy["lo"], b_relevancy["hi"]),
            }
            expected = {
                "a": (
                    "| context_recall | 0.500 | 4 | 0 | %s | found 2 of 4 needed |" % spread["a_recall"],
                    "| context_precision | 0.500 | 4 | 0 | %s | relevant 2 of 2 retrieved |" % spread["a_precision"],
                    "| faithfulness | 1.000 | 4 | 0 | [1.000, 1.000] | supported 4 of 4 claims legs left 0 |",
                    "| answer_relevancy | 1.000 | 4 | 0 | [1.000, 1.000] | held 16 of 16 tests |",
                ),
                "b": (
                    "| context_recall | 1.000 | 4 | 0 | [1.000, 1.000] | found 4 of 4 needed |",
                    "| context_precision | 1.000 | 4 | 0 | [1.000, 1.000] | relevant 4 of 4 retrieved |",
                    "| faithfulness | 1.000 | 3 | 1 | [1.000, 1.000] | supported 3 of 3 claims legs left 0 |",
                    "| answer_relevancy | 0.750 | 4 | 0 | %s | held 12 of 16 tests |" % spread["b_relevancy"],
                ),
            }
            for variant in ("a", "b"):
                section = text.split("## Variant %s\n" % variant, 1)[1].split("\n## ", 1)[0]
                recall, precision, faith, relevancy = expected[variant]
                self.assertEqual(
                    section,
                    "\n### Retrieval\n\n%s\n%s\n%s\n%s\n\n### Generation\n\n%s\n%s\n%s\n%s\n" % (
                        header, rule, recall, precision, header, rule, faith, relevancy))
        # A scorer with no scored case prints none for its mean and its interval, and
        # the table stays six cells wide on every line.
        with tempfile.TemporaryDirectory() as root:
            cases = [(case_id, True, True, True, True) for case_id in ids]
            document, text = _report_of(self, root, _world_of(root, cases, no_final_in_b=tuple(ids)))
            section = text.split("## Variant b\n", 1)[1].split("\n## ", 1)[0]
            self.assertIn(
                "\n### Generation\n\n%s\n%s\n"
                "| faithfulness | none | 0 | 4 | none | supported 0 of 0 claims legs left 0 |\n"
                "| answer_relevancy | 0.000 | 4 | 0 | [0.000, 0.000] | held 0 of 16 tests |\n" % (header, rule),
                section)
            table_lines = [line for line in text.split("\n") if line.startswith("|")]
            self.assertEqual(len(table_lines), 16)
            for line in table_lines:
                self.assertEqual(len(line.split(" | ")), 6, line)
                self.assertTrue(line.startswith("| ") and line.endswith(" |"), line)

    def test_the_bars_read_their_bounds_and_the_verdict_needs_all_three(self):
        ids = ["S%03d" % index for index in range(1, 81)]
        with tempfile.TemporaryDirectory() as root:
            # B retrieves the needed rule on every case and A never. Every outcome
            # matches in both runs but S001, which only B gets.
            cases = [(case_id, False, True, case_id != "S001", True) for case_id in ids]
            document, text = _report_of(self, root, _world_of(root, cases))
            ab = document["ab"]
            self.assertEqual(ab["context_recall"]["bar"], {"holds": True, "threshold": 0.0, "value": 1.0})
            self.assertEqual(ab["faithfulness"]["bar"], {"holds": True, "threshold": -0.05, "value": 0.0})
            outcome = ab["outcome"]
            self.assertEqual((outcome["a"], outcome["b"], outcome["c"], outcome["d"]), (79, 0, 1, 0))
            fall, lower, upper = paired_difference(79, 0, 1, 0)
            self.assertEqual((outcome["fall"], outcome["lo"], outcome["hi"]), (fall, lower, upper))
            self.assertLess(upper, 0.05)
            self.assertEqual(outcome["bar"], {"holds": True, "threshold": 0.05, "value": upper})
            self.assertEqual(document["verdict"], VERDICT_SHIP)
            self.assertIn("outcome: upper bound %.3f at most 0.050: yes" % upper, text)
            self.assertIn("verdict: ship", text)
            # The candidates are read from A, where the outcome matched and recall is 0,
            # so S001 is not one; read from B, whose recall is 1, there would be none.
            self.assertEqual([row["case_id"] for row in document["groundedness"]], ids[1:])
            self.assertEqual(document["groundedness"][0]["context_recall"], 0.0)
            self.assertEqual(document["groundedness"][0]["tool_calls"], 2)
            # The weaker half is read per variant: A's retrieval averages 0 against a
            # generation of 1, and B's two halves tie.
            self.assertEqual(document["weaker_half"]["a"]["name"], "retrieval")
            self.assertIsNone(document["weaker_half"]["b"]["name"])
            self.assertIn("variant a: retrieval is the weaker half", text)
            self.assertIn("variant b: neither half: the two averages tie", text)
        with tempfile.TemporaryDirectory() as root:
            # B misses six outcomes A got. The fall is 6 of 80; the upper bound of its
            # interval, 0.154, decides and fails, where the lower bound, 0.014, would pass.
            cases = [(case_id, False, True, True, index >= 6) for index, case_id in enumerate(ids)]
            document, text = _report_of(self, root, _world_of(root, cases))
            outcome = document["ab"]["outcome"]
            self.assertEqual((outcome["a"], outcome["b"], outcome["c"], outcome["d"]), (74, 6, 0, 0))
            self.assertLessEqual(outcome["lo"], 0.05)
            self.assertGreater(outcome["hi"], 0.05)
            self.assertFalse(outcome["bar"]["holds"])
            self.assertTrue(document["ab"]["context_recall"]["bar"]["holds"])
            self.assertTrue(document["ab"]["faithfulness"]["bar"]["holds"])
            self.assertEqual(document["verdict"], VERDICT_NO_SHIP)
            self.assertIn("outcome fall 0.075 interval [0.014, 0.154] paired 80 left 0 a 74 b 6 c 0 d 0", text)
            self.assertIn("outcome: upper bound 0.154 at most 0.050: no", text)
            self.assertIn("verdict: no-ship", text)

    def test_a_none_in_either_variant_leaves_the_pair_and_is_counted(self):
        ids = ["S%03d" % index for index in range(1, 6)]
        with tempfile.TemporaryDirectory() as root:
            cases = [(case_id, True, True, True, True) for case_id in ids]
            document, text = _report_of(self, root, _world_of(root, cases, no_final_in_b=("S003",)))
            faith = document["ab"]["faithfulness"]
            self.assertEqual((faith["paired"], faith["left"]), (4, 1))
            self.assertEqual((faith["mean_delta"], faith["lo"], faith["hi"]), (0.0, 0.0, 0.0))
            # Without a final, relevancy is 0, not None, so that pair stays.
            relevancy = document["ab"]["answer_relevancy"]
            self.assertEqual((relevancy["paired"], relevancy["left"]), (5, 0))
            self.assertEqual(relevancy["mean_delta"], -0.2)
            block = document["variants"]["b"]["generation"]["faithfulness"]
            self.assertEqual((block["scored"], block["none"]), (4, 1))
            self.assertIn("faithfulness delta 0.000 interval [0.000, 0.000] paired 4 left 1", text)

    def test_the_stale_check_fails_on_a_refused_config(self):
        with tempfile.TemporaryDirectory() as root:
            config = _config(dataset_sha256=None)
            config["top_k"] = 1
            _dump(os.path.join(root, DEFAULT_CONFIG), config)
            self.assertFalse(report_files_hold(root))

    def test_the_statement_is_verbatim(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            statement = " Leading space, trailing blank line.\n\n"
            with open(os.path.join(root, "reports", "rag-statement.md"), "w", encoding="utf-8", newline="\n") as handle:
                handle.write(statement)
            status, _out, err = _run(world.report_argv())
            self.assertEqual(status, 0, err)
            with open(os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md"), "rb") as handle:
                text = handle.read().decode("utf-8")
            self.assertTrue(text.startswith(statement + "\n# RAG report\n"))

    def test_load_pair_returns_what_report_and_the_uploader_read(self):
        with tempfile.TemporaryDirectory() as root:
            world = _World(root)
            config = load_config(world.config_path)
            rows, metas, records = rag.load_pair(config, root)
            self.assertEqual([row["case_id"] for row in rows], ["S001", "S002"])
            self.assertEqual(sorted(metas), ["a", "b"])
            self.assertEqual(metas["b"]["rule_match"], "alias")
            self.assertEqual(sorted(records["a"]), ["S001", "S002"])
            self.assertEqual(records["b"]["S001"]["ticket"], json.loads(rows[0]["question"]))
            with open(os.path.join(root, "traces", "w4-b", "run_meta.json"), encoding="utf-8") as handle:
                meta = json.load(handle)
            meta["think"] = True
            with open(os.path.join(root, "traces", "w4-b", "run_meta.json"), "w", encoding="utf-8") as handle:
                json.dump(meta, handle)
            with self.assertRaises(rag.ReportError) as caught:
                rag.load_pair(config, root)
            self.assertEqual(str(caught.exception), "run_meta think differs")

    def test_report_refuses_a_config_outside_the_root_and_names_the_one_it_used(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as elsewhere:
            world = _World(root)
            report_path = os.path.join(root, "packages", "rag-eval", "assignment-2", "report.md")
            json_path = os.path.join(root, "reports", "rag.json")
            outside = os.path.join(elsewhere, "config.yaml")
            shutil.copyfile(world.config_path, outside)
            status, out, err = _run(["report", "--config", outside, "--root", root])
            self.assertEqual(status, 2)
            self.assertEqual(err, "config is outside the root\n")
            self.assertEqual(out, "")
            self.assertFalse(os.path.exists(report_path))
            self.assertFalse(os.path.exists(json_path))
            # Inside the root, the printed commands name the file that was used.
            inside = os.path.join(root, "other.json")
            shutil.copyfile(world.config_path, inside)
            status, _out, err = _run(["report", "--config", inside, "--root", root])
            self.assertEqual(status, 0, err)
            with open(report_path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertIn("python3 -m scorer.rag report --config other.json\n", text)
            self.assertNotIn(DEFAULT_CONFIG, text)
            document = json.load(open(json_path, encoding="utf-8"))
            self.assertEqual(document["commands"][2], "python3 -m scorer.rag report --config other.json")

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
