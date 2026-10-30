"""The judge harness: rubrics, sheets, a local judge, and agreement with labels."""
import contextlib
import csv
import hashlib
import io
import json
import os
import subprocess
import sys
import textwrap
import unittest
import urllib.error
from unittest import mock

from scorer.judge import (
    CASE_CHAR_LIMIT,
    OLLAMA_ORIGIN,
    UNSURE_LINE,
    FixtureClient,
    JudgeError,
    OllamaAdapter,
    OllamaClient,
    build_report,
    case_sections,
    export_files,
    parse_reply,
    render_case,
    run_judge,
    run_name,
)
from scorer.stats import canonical_json, cohen_kappa, confusion, meets_bar
from scorer.traces import load_run

from tests.judge_otlp import (
    BASE_RECORDS,
    DUPLICATE_RECORDS,
    FRESH1_RECORDS,
    FRESH2_RECORDS,
    canonical_document,
)


ROOT = "tests/fixtures/judge"
RUBRICS = ROOT + "/rubrics"
BASE = ROOT + "/runs/base"
FRESH1 = ROOT + "/runs/fresh1"
FRESH2 = ROOT + "/runs/fresh2"
DUPLICATE = ROOT + "/runs/duplicate"
NAMES = ["needs_human_correctness", "rule_adherence", "tool_call_accuracy"]
META_KEYS = {"adapter", "digest", "labels_sha256", "model", "options", "rubrics", "server_version"}
CHOICE_KEYS = {"adapter", "candidates", "choice", "grader_family", "grader_model", "not_run", "smoke_run"}


def cli(args):
    return subprocess.run(
        [sys.executable, "-m", "scorer.judge", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def offline(args):
    """Run a command in this process with urlopen and socket connect patched; a subprocess would not see the patch.

    Returns the exit status, stdout, stderr, and whether either network call was made.
    """
    from scorer import judge
    out = io.StringIO()
    err = io.StringIO()
    status = 0
    with mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")) as opened:
        with mock.patch("socket.socket.connect", side_effect=AssertionError("network")) as connected:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    judge.main(args)
                except SystemExit as stop:
                    status = stop.code
    return status, out.getvalue(), err.getvalue(), opened.called or connected.called


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write_text(path, text):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def rubric_file(directory, name, body=None):
    os.makedirs(directory, exist_ok=True)
    if body is None:
        body = "Reply PASS or FAIL on the first line.\nReason: one short line.\n"
    path = os.path.join(directory, name + ".md")
    write_text(path, body)
    return path


class ParseReplyTests(unittest.TestCase):
    def test_parse_reply_table(self):
        table = (
            ("PASS", "PASS", ""),
            ("FAIL", "FAIL", ""),
            ("PASS\nReason: fine", "PASS", "fine"),
            ("FAIL\nReason: first\nReason: second", "FAIL", "first"),
            ("<think>secret</think>\nPASS\nReason: ok", "PASS", "ok"),
            ("<think>\nPASS\n</think>\nFAIL", "FAIL", ""),
            ("Pass", "UNPARSED", ""),
            ("**PASS**", "UNPARSED", ""),
            ("PASS.", "UNPARSED", ""),
            ("PASS Reason: no", "UNPARSED", ""),
            ("PASS\nreason: lower", "PASS", ""),
            ("\n\nFAIL\n\nReason: later", "FAIL", "later"),
            ("  PASS  \nReason:  spaced  ", "PASS", "spaced"),
            ("PASS\r\nReason: win\r\n", "PASS", "win"),
            ("", "UNPARSED", ""),
            ("FAIL\nReason:", "FAIL", ""),
        )
        for text, verdict, reason in table:
            with self.subTest(text=text):
                self.assertEqual(parse_reply(text), (verdict, reason))


class RenderCaseTests(unittest.TestCase):
    def test_render_case_format(self):
        record = {
            "case_id": "C1",
            "ticket": {"b": 1, "a": 2},
            "tools": [
                {"name": "find_match", "args": {"z": 1, "y": 2}, "result": {"ok": True}, "error": None},
                {"name": "lookup_rule", "args": {}, "result": None, "error": "missing"},
            ],
            "final": {"ticket_result": "WIN"},
            "status": "complete",
            "reason": None,
        }
        self.assertEqual(render_case(record), textwrap.dedent("""\
            TICKET
            {
              "a": 2,
              "b": 1
            }

            TOOL CALLS
            1. find_match
               args: {"y": 2, "z": 1}
               result: {"ok": true}
               error: none
            2. lookup_rule
               args: {}
               result: null
               error: missing

            FINAL ANSWER
            {
              "ticket_result": "WIN"
            }

            RUN STATUS
            complete, reason none
            """))
        bare = {
            "case_id": "C2",
            "ticket": {},
            "tools": [],
            "final": None,
            "status": "incomplete",
            "reason": "EMPTY_FINAL",
        }
        text = render_case(bare)
        self.assertIn("TOOL CALLS\nnone\n", text)
        self.assertIn("FINAL ANSWER\nnone\n", text)
        self.assertTrue(text.endswith("incomplete, reason EMPTY_FINAL\n"))

    def test_golden_a01_and_real_none_forms(self):
        records = {row["case_id"]: row for row in load_run("traces/v1")}
        with open(ROOT + "/case-A01.txt", encoding="utf-8") as handle:
            golden = handle.read()
        self.assertEqual(render_case(records["A01"]), golden)
        self.assertLessEqual(len(golden), CASE_CHAR_LIMIT)
        for case_id, tools_none, final_none in (
            ("B06", True, False),
            ("B05", False, True),
            ("C14", True, True),
        ):
            text = render_case(records[case_id])
            if tools_none:
                self.assertIn("TOOL CALLS\nnone\n", text)
            else:
                self.assertNotIn("TOOL CALLS\nnone\n", text)
            if final_none:
                self.assertIn("FINAL ANSWER\nnone\n", text)
            else:
                self.assertNotIn("FINAL ANSWER\nnone\n", text)

    def test_size_limit_names_the_case_and_counts_characters(self):
        record = {
            "case_id": "BIG",
            "ticket": {"pad": ""},
            "tools": [],
            "final": None,
            "status": "complete",
            "reason": None,
        }
        base = len(render_case(record))
        record["ticket"]["pad"] = "x" * (CASE_CHAR_LIMIT - base)
        self.assertEqual(len(render_case(record)), CASE_CHAR_LIMIT)
        record["ticket"]["pad"] = "é" * (CASE_CHAR_LIMIT - base)
        text = render_case(record)
        self.assertEqual(len(text), CASE_CHAR_LIMIT)
        self.assertGreater(len(text.encode("utf-8")), CASE_CHAR_LIMIT)
        record["ticket"]["pad"] = "x" * (CASE_CHAR_LIMIT - base + 1)
        with self.assertRaises(JudgeError) as caught:
            render_case(record)
        self.assertIn("BIG", str(caught.exception))


class RunNameTests(unittest.TestCase):
    def test_normalise(self):
        self.assertEqual(run_name("./traces/v1/"), "traces/v1")
        self.assertEqual(run_name("traces/v1"), "traces/v1")
        self.assertEqual(run_name("traces/v1/"), "traces/v1")
        self.assertEqual(run_name("traces//v1"), "traces/v1")
        self.assertEqual(run_name("traces/../traces/v1"), "traces/v1")
        samples = (
            os.path.abspath(os.sep + "no-such-run"),
            "~" + "/traces",
            "C:" + "/traces",
            # Outside the repository: the climb would carry the clone's location into a plan or label file.
            "..",
            "../traces/v1",
            "traces/../../x",
        )
        for raw in samples:
            with self.subTest(raw=raw):
                with self.assertRaises(JudgeError):
                    run_name(raw)


class CommandTests(unittest.TestCase):
    def assert_status_2(self, done, fragment, absent):
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertNotIn("Traceback", done.stderr)
        self.assertEqual(done.stdout, "")
        self.assertIn(fragment, done.stderr)
        for path in absent:
            self.assertFalse(os.path.exists(path), path)

    def test_fixture_runs_match_the_builder(self):
        pairs = (
            (BASE, BASE_RECORDS),
            (FRESH1, FRESH1_RECORDS),
            (FRESH2, FRESH2_RECORDS),
            (DUPLICATE, DUPLICATE_RECORDS),
        )
        for directory, records in pairs:
            with self.subTest(directory=directory):
                with open(os.path.join(directory, "settlement-traces.json"), encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), canonical_document(records))

    def test_select_rule_order_skips_and_errors(self):
        with self.temporary() as directory:
            out = os.path.join(directory, "plan.json")
            done = cli(["select", "--base", BASE, "--fresh", FRESH1, "--fresh", FRESH2, "--n-fresh", "2", "--out", out])
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("skipped 1\n", done.stdout)
            rows = json.loads(open(out, encoding="utf-8").read())
            self.assertEqual(
                [(row["run"], row["case_id"], row["trace_id"]) for row in rows],
                [
                    (BASE, "C1", "tb-c1"),
                    (BASE, "C2", "tb-c2"),
                    (BASE, "C3", "tb-c3"),
                    (FRESH1, "C3", "t1-c3"),
                    (FRESH2, "C1", "t2-c1"),
                ],
            )
            again = os.path.join(directory, "again.json")
            dotted = "./" + BASE + "/"
            second = cli(["select", "--base", dotted, "--fresh", FRESH1, "--fresh", FRESH2, "--n-fresh", "2", "--out", again])
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(open(out, "rb").read(), open(again, "rb").read())
            few = os.path.join(directory, "few.json")
            refused = cli(["select", "--base", BASE, "--fresh", FRESH1, "--fresh", FRESH2, "--n-fresh", "3", "--out", few])
            self.assert_status_2(refused, "only 2 fresh records qualify", [few])
            duplicate = os.path.join(directory, "dup.json")
            refused = cli(["select", "--base", DUPLICATE, "--n-fresh", "0", "--out", duplicate])
            self.assert_status_2(refused, "case_id C1", [duplicate])
            self.assertIn(DUPLICATE, refused.stderr)
            absolute = os.path.join(directory, "abs.json")
            refused = cli(["select", "--base", os.path.abspath(os.sep + "no-such-run"), "--n-fresh", "0", "--out", absolute])
            self.assert_status_2(refused, "absolute", [absolute])
            tilde = os.path.join(directory, "tilde.json")
            refused = cli(["select", "--base", "~" + "/traces", "--n-fresh", "0", "--out", tilde])
            self.assert_status_2(refused, "absolute", [tilde])
            broken = ROOT + "/_tmp_broken"
            os.makedirs(broken, exist_ok=True)
            try:
                write_text(os.path.join(broken, "settlement-traces.json"), "{")
                bad = os.path.join(directory, "bad.json")
                refused = cli(["select", "--base", broken, "--n-fresh", "0", "--out", bad])
                self.assert_status_2(refused, "not valid JSON", [bad])
                # Valid JSON of the wrong shape is a message too, never a traceback.
                for shape in ("[]", '{"resourceSpans": 5}', '{"resourceSpans": [{"scopeSpans": [{"spans": [5]}]}]}'):
                    with self.subTest(shape=shape):
                        write_text(os.path.join(broken, "settlement-traces.json"), shape)
                        refused = cli(["select", "--base", broken, "--n-fresh", "0", "--out", bad])
                        self.assert_status_2(refused, "is not a trace export", [bad])
            finally:
                import shutil
                shutil.rmtree(broken, ignore_errors=True)

    def test_sheet_import_and_check_final(self):
        with self.temporary() as directory:
            plan = os.path.join(directory, "plan.json")
            made = cli(["select", "--base", BASE, "--n-fresh", "0", "--out", plan])
            self.assertEqual(made.returncode, 0, made.stderr)
            sheet_dir = os.path.join(directory, "sheet")
            made = cli(["sheet", "--plan", plan, "--rubrics", RUBRICS, "--out", sheet_dir])
            self.assertEqual(made.returncode, 0, made.stderr)
            case_files = open(os.path.join(sheet_dir, "case-files.md"), encoding="utf-8").read()
            self.assertEqual(case_files.splitlines()[0], UNSURE_LINE)
            self.assertIn("# 1. %s C1" % BASE, case_files)
            with open(os.path.join(sheet_dir, "labels.csv"), encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                sheet_rows = list(reader)
                header = list(reader.fieldnames)
            self.assertEqual(header, ["n", "run", "case_id", "trace_id"] + NAMES + ["unsure", "note"])
            for row in sheet_rows:
                for name in NAMES + ["unsure", "note"]:
                    self.assertEqual(row[name], "")
            filled = os.path.join(directory, "filled.csv")
            self.write_filled(sheet_rows, header, filled)
            labels = os.path.join(directory, "set.jsonl")
            meta = os.path.join(directory, "set-meta.json")
            made = cli([
                "import-labels", "--plan", plan, "--sheet", filled, "--rubrics", RUBRICS,
                "--labels", labels, "--meta", meta,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertIn("rows 3\n", made.stdout)
            self.assertIn("needs_human_correctness FAIL 2\n", made.stdout)
            self.assertIn("rule_adherence FAIL 1\n", made.stdout)
            self.assertIn("tool_call_accuracy FAIL 1\n", made.stdout)
            imported = [json.loads(line) for line in open(labels, encoding="utf-8") if line.strip()]
            self.assertEqual(imported[1]["unsure"], ["needs_human_correctness"])
            self.assertEqual(imported[2]["unsure"], ["rule_adherence", "tool_call_accuracy"])
            self.assertEqual(imported[1]["note"], "look, again")
            self.assertEqual(imported[0]["human"]["needs_human_correctness"], "FAIL")
            meta_doc = json.loads(open(meta, encoding="utf-8").read())
            self.assertEqual(meta_doc["plan_sha256"], sha256(plan))
            for name in NAMES:
                self.assertEqual(meta_doc["rubrics"][name], sha256(os.path.join(RUBRICS, name + ".md")))
            bom = os.path.join(directory, "bom.csv")
            raw = open(filled, "rb").read().replace(b"\n", b"\r\n")
            with open(bom, "wb") as handle:
                handle.write(b"\xef\xbb\xbf" + raw)
            labels_bom = os.path.join(directory, "bom.jsonl")
            meta_bom = os.path.join(directory, "bom-meta.json")
            made = cli([
                "import-labels", "--plan", plan, "--sheet", bom, "--rubrics", RUBRICS,
                "--labels", labels_bom, "--meta", meta_bom,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(open(labels, "rb").read(), open(labels_bom, "rb").read())
            reversed_path = os.path.join(directory, "reversed.csv")
            with open(filled, encoding="utf-8", newline="") as handle:
                filled_reader = csv.DictReader(handle)
                filled_rows = list(filled_reader)
                filled_header = list(filled_reader.fieldnames)
            self.write_csv(list(reversed(filled_header)), filled_rows, reversed_path, None)
            labels_rev = os.path.join(directory, "rev.jsonl")
            meta_rev = os.path.join(directory, "rev-meta.json")
            made = cli([
                "import-labels", "--plan", plan, "--sheet", reversed_path, "--rubrics", RUBRICS,
                "--labels", labels_rev, "--meta", meta_rev,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(open(labels, "rb").read(), open(labels_rev, "rb").read())
            # report reads <labels>-meta.json beside the labels; a meta written anywhere else would leave
            # report reading a stale one, or none.
            loose = os.path.join(directory, "loose.jsonl")
            elsewhere = os.path.join(directory, "elsewhere-meta.json")
            refused = cli([
                "import-labels", "--plan", plan, "--sheet", filled, "--rubrics", RUBRICS,
                "--labels", loose, "--meta", elsewhere,
            ])
            self.assert_status_2(refused, "--meta must be", [loose, elsewhere])
            self.import_refusals(directory, plan, header, sheet_rows, labels)
            final = os.path.join(directory, "final.jsonl")
            self.write_final(imported, final, valid=True)
            made = cli(["check-final", "--labels", labels, "--final", final])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(made.stdout, "changes 1\n")
            self.final_refusals(directory, labels, imported)

    def test_sheet_refusals(self):
        with self.temporary() as directory:
            plan = os.path.join(directory, "plan.json")
            made = cli(["select", "--base", BASE, "--n-fresh", "0", "--out", plan])
            self.assertEqual(made.returncode, 0, made.stderr)
            bad_rubrics = os.path.join(directory, "bad-rubrics")
            rubric_file(bad_rubrics, "rule_adherence", "PASS FAIL Reason: see C1\n")
            out = os.path.join(directory, "out")
            refused = cli(["sheet", "--plan", plan, "--rubrics", bad_rubrics, "--out", out])
            self.assert_status_2(refused, "C1", [os.path.join(out, "case-files.md")])
            rows = json.loads(open(plan, encoding="utf-8").read())
            rows[0]["trace_id"] = "other-trace"
            changed = os.path.join(directory, "changed.json")
            write_text(changed, canonical_json(rows))
            out2 = os.path.join(directory, "out2")
            refused = cli(["sheet", "--plan", changed, "--rubrics", RUBRICS, "--out", out2])
            self.assert_status_2(refused, "run changed after labelling", [os.path.join(out2, "labels.csv")])
            empty = os.path.join(directory, "empty-rubrics")
            rubric_file(empty, "rule_adherence", "")
            refused = cli(["sheet", "--plan", plan, "--rubrics", empty, "--out", os.path.join(directory, "out3")])
            self.assert_status_2(refused, "empty", [])
            crlf = os.path.join(directory, "crlf-rubrics")
            rubric_file(crlf, "rule_adherence", "PASS\r\nFAIL\r\nReason: x\r\n")
            refused = cli(["sheet", "--plan", plan, "--rubrics", crlf, "--out", os.path.join(directory, "out4")])
            self.assert_status_2(refused, "LF", [])
            for word, body in (
                ("PASS", "Reply FAIL.\nReason: x\n"),
                ("FAIL", "Reply PASS.\nReason: x\n"),
                ("Reason:", "Reply PASS or FAIL.\n"),
            ):
                with self.subTest(missing=word):
                    lacking = os.path.join(directory, "lacking-" + word.rstrip(":"))
                    rubric_file(lacking, "rule_adherence", body)
                    out6 = os.path.join(directory, "out6-" + word.rstrip(":"))
                    refused = cli(["sheet", "--plan", plan, "--rubrics", lacking, "--out", out6])
                    self.assert_status_2(refused, "must contain PASS, FAIL and Reason:", [out6])
            long_dir = os.path.join(directory, "long-rubrics")
            rubric_file(long_dir, "rule_adherence", "PASS FAIL Reason: " + ("x" * 6000) + "\n")
            refused = cli(["sheet", "--plan", plan, "--rubrics", long_dir, "--out", os.path.join(directory, "out5")])
            self.assert_status_2(refused, "6000", [])

    def import_refusals(self, directory, plan, header, sheet_rows, good_labels):
        cases = []
        missing = [dict(row) for row in sheet_rows[:-1]]
        cases.append((missing, header, "does not match the plan"))
        extra = [dict(row) for row in sheet_rows]
        extra.append(dict(sheet_rows[0], n="4"))
        cases.append((extra, header, "does not match the plan"))
        duplicate = [dict(sheet_rows[0]), dict(sheet_rows[0]), dict(sheet_rows[1])]
        cases.append((duplicate, header, "duplicate sheet row"))
        bad_cell = [dict(row) for row in sheet_rows]
        bad_cell[0]["rule_adherence"] = "Pass"
        cases.append((bad_cell, header, "not exactly PASS or FAIL"))
        spaced = [dict(row) for row in sheet_rows]
        spaced[0]["rule_adherence"] = " FAIL"
        cases.append((spaced, header, "not exactly PASS or FAIL"))
        unsure = [dict(row) for row in sheet_rows]
        unsure[0]["unsure"] = "not_a_rubric"
        cases.append((unsure, header, "not a rubric"))
        dup_unsure = [dict(row) for row in sheet_rows]
        dup_unsure[0]["unsure"] = "rule_adherence; rule_adherence"
        cases.append((dup_unsure, header, "duplicate unsure"))
        trace = [dict(row) for row in sheet_rows]
        trace[0]["trace_id"] = "other-trace"
        cases.append((trace, header, "does not match the plan"))
        short_header = [name for name in header if name != "rule_adherence"]
        cases.append((sheet_rows, short_header, "missing"))
        extra_header = header + ["hint"]
        cases.append((sheet_rows, extra_header, "unexpected column"))
        for index, (rows, fields, fragment) in enumerate(cases):
            path = os.path.join(directory, "bad-%s.csv" % index)
            labels = os.path.join(directory, "bad-%s.jsonl" % index)
            meta = os.path.join(directory, "bad-%s-meta.json" % index)
            self.write_csv(fields, rows, path, None if fields != header and "hint" in fields else self.assignments())
            if "hint" in fields:
                self.write_csv(fields, rows, path, self.assignments(), extras={"hint": "no"})
            refused = cli([
                "import-labels", "--plan", plan, "--sheet", path, "--rubrics", RUBRICS,
                "--labels", labels, "--meta", meta,
            ])
            self.assert_status_2(refused, fragment, [labels, meta])
        self.assertTrue(os.path.isfile(good_labels))

    def final_refusals(self, directory, labels, imported):
        mutations = (
            ("from", "change from does not match"),
            ("to", "change to does not match"),
            ("same", "does not change the label"),
            ("blank-reason", "reason is empty"),
            ("space-reason", "reason is empty"),
            ("no-record", "no change record"),
            ("note", "differs in note"),
            ("unsure", "differs in unsure"),
            ("trace", "differs in trace_id"),
            ("extra-key", "wrong keys"),
            ("unsure-mixed", "unsure entry is not a rubric"),
            ("unsure-order", "not in sorted order"),
            ("order", "differs in"),
            ("drop", "row count"),
        )
        for name, fragment in mutations:
            path = os.path.join(directory, "final-%s.jsonl" % name)
            self.write_final(imported, path, valid=False, mutation=name)
            refused = cli(["check-final", "--labels", labels, "--final", path])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertEqual(refused.stdout, "")
            self.assertIn(fragment, refused.stderr)

    def assignments(self):
        return {
            ("C1", "needs_human_correctness"): "FAIL",
            ("C1", "rule_adherence"): "PASS",
            ("C1", "tool_call_accuracy"): "PASS",
            ("C2", "needs_human_correctness"): "FAIL",
            ("C2", "rule_adherence"): "FAIL",
            ("C2", "tool_call_accuracy"): "PASS",
            ("C3", "needs_human_correctness"): "PASS",
            ("C3", "rule_adherence"): "PASS",
            ("C3", "tool_call_accuracy"): "FAIL",
        }

    def write_filled(self, rows, header, path):
        unsure = {"C1": "", "C2": "needs_human_correctness", "C3": "tool_call_accuracy; rule_adherence"}
        notes = {"C1": "", "C2": "look, again", "C3": ""}
        filled = []
        for row in rows:
            item = dict(row)
            for name in NAMES:
                item[name] = self.assignments()[(row["case_id"], name)]
            item["unsure"] = unsure[row["case_id"]]
            item["note"] = notes[row["case_id"]]
            filled.append(item)
        self.write_csv(header, filled, path, None)

    def write_csv(self, fields, rows, path, assignments, extras=None):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                item = {key: row.get(key, "") for key in fields}
                if assignments is not None:
                    for name in NAMES:
                        if name in item and item[name] == "" and (row["case_id"], name) in assignments:
                            item[name] = assignments[(row["case_id"], name)]
                if extras:
                    item.update(extras)
                writer.writerow({key: item.get(key, "") for key in fields})

    def write_final(self, imported, path, valid, mutation=None):
        rows = []
        for index, source in enumerate(imported):
            row = {
                "case_id": source["case_id"],
                "changes": [],
                "human": dict(source["human"]),
                "note": source["note"],
                "run": source["run"],
                "trace_id": source["trace_id"],
                "unsure": list(source["unsure"]),
            }
            rows.append(row)
        if valid:
            rows[0]["human"]["needs_human_correctness"] = "PASS"
            rows[0]["changes"] = [{
                "from": "FAIL",
                "reason": "read again",
                "rubric": "needs_human_correctness",
                "to": "PASS",
            }]
        elif mutation == "from":
            rows[0]["changes"] = [{"from": "PASS", "reason": "read again", "rubric": "needs_human_correctness", "to": "FAIL"}]
        elif mutation == "to":
            rows[0]["human"]["needs_human_correctness"] = "FAIL"
            rows[0]["changes"] = [{"from": "FAIL", "reason": "read again", "rubric": "needs_human_correctness", "to": "PASS"}]
        elif mutation == "same":
            rows[0]["changes"] = [{"from": "FAIL", "reason": "read again", "rubric": "needs_human_correctness", "to": "FAIL"}]
        elif mutation == "blank-reason":
            rows[0]["human"]["needs_human_correctness"] = "PASS"
            rows[0]["changes"] = [{"from": "FAIL", "reason": "", "rubric": "needs_human_correctness", "to": "PASS"}]
        elif mutation == "space-reason":
            rows[0]["human"]["needs_human_correctness"] = "PASS"
            rows[0]["changes"] = [{"from": "FAIL", "reason": "   ", "rubric": "needs_human_correctness", "to": "PASS"}]
        elif mutation == "no-record":
            rows[0]["human"]["needs_human_correctness"] = "PASS"
        elif mutation == "note":
            rows[0]["note"] = "edited"
        elif mutation == "unsure":
            rows[0]["unsure"] = ["rule_adherence"]
        elif mutation == "trace":
            rows[0]["trace_id"] = "other-trace"
        elif mutation == "extra-key":
            rows[0]["extra"] = "no"
        elif mutation == "unsure-mixed":
            rows[0]["unsure"] = [1, "rule_adherence"]
        elif mutation == "unsure-order":
            rows[2]["unsure"] = ["tool_call_accuracy", "rule_adherence"]
        elif mutation == "order":
            rows = list(reversed(rows))
        elif mutation == "drop":
            rows = rows[:-1]
        else:
            raise AssertionError(mutation)
        lines = [json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows]
        write_text(path, "\n".join(lines) + "\n")

    def test_run_fake_adapter_and_failures(self):
        with self.temporary() as directory:
            labels, meta = self.base_labels(directory)
            replies = {}
            records = {row["case_id"]: row for row in load_run(BASE)}
            for case_id in ("C1", "C2", "C3"):
                for name in NAMES:
                    replies["%s|%s|%s" % (BASE, case_id, name)] = "PASS\nReason: ok"
            replies["%s|C2|tool_call_accuracy" % BASE] = "maybe\nReason: no"
            reply_path = os.path.join(directory, "replies.json")
            write_text(reply_path, json.dumps(replies, sort_keys=True))
            out = os.path.join(directory, "judgments")
            status, _stdout, stderr, networked = offline([
                "run", "--labels", labels, "--rubrics", RUBRICS,
                "--adapter", "fake:" + reply_path, "--out", out,
            ])
            self.assertEqual(status, 0, stderr)
            self.assertFalse(networked, "the fake adapter opened a network connection")
            verdicts = [json.loads(line) for line in open(os.path.join(out, "verdicts.jsonl"), encoding="utf-8")]
            self.assertEqual(len(verdicts), 9)
            self.assertEqual(
                [(row["run"], row["case_id"], row["rubric"]) for row in verdicts],
                sorted((row["run"], row["case_id"], row["rubric"]) for row in verdicts),
            )
            for row in verdicts:
                self.assertNotIn("human", row)
                self.assertEqual(set(row.keys()), {
                    "case_id", "reason", "reply", "rubric", "rubric_sha256", "run", "trace_id", "verdict",
                })
            odd = [row for row in verdicts if row["case_id"] == "C2" and row["rubric"] == "tool_call_accuracy"][0]
            self.assertEqual(odd["verdict"], "UNPARSED")
            self.assertEqual(odd["reply"], "maybe\nReason: no")
            judge_meta = json.loads(open(os.path.join(out, "judge_meta.json"), encoding="utf-8").read())
            # The spec: no timestamp and no machine path. Any key beyond these fails.
            self.assertEqual(set(judge_meta.keys()), META_KEYS)
            self.assertEqual(judge_meta["adapter"], "fake")
            self.assertEqual(judge_meta["labels_sha256"], sha256(labels))
            self.assertEqual(judge_meta["rubrics"]["rule_adherence"], sha256(os.path.join(RUBRICS, "rule_adherence.md")))
            self.assertIsNone(judge_meta["model"])
            self.assertIsNone(judge_meta["digest"])
            missing = dict(replies)
            del missing["%s|C3|rule_adherence" % BASE]
            missing_path = os.path.join(directory, "missing.json")
            write_text(missing_path, json.dumps(missing))
            missing_out = os.path.join(directory, "missing-out")
            refused = cli([
                "run", "--labels", labels, "--rubrics", RUBRICS,
                "--adapter", "fake:" + missing_path, "--out", missing_out,
            ])
            self.assert_status_2(refused, "no reply", [os.path.join(missing_out, "verdicts.jsonl"), os.path.join(missing_out, "judge_meta.json")])
            changed = os.path.join(directory, "changed.jsonl")
            rows = [json.loads(line) for line in open(labels, encoding="utf-8")]
            rows[0]["trace_id"] = "other-trace"
            write_text(changed, "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            changed_out = os.path.join(directory, "changed-out")
            refused = cli([
                "run", "--labels", changed, "--rubrics", RUBRICS,
                "--adapter", "fake:" + reply_path, "--out", changed_out,
            ])
            self.assert_status_2(refused, "run changed after labelling", [os.path.join(changed_out, "verdicts.jsonl")])
            one = os.path.join(directory, "one-rubric")
            rubric_file(one, "rule_adherence")
            two = [row for row in rows if False]
            kept = []
            for case_id in ("C1", "C2"):
                record = records[case_id]
                kept.append({
                    "case_id": case_id,
                    "human": {"rule_adherence": "PASS"},
                    "note": "HUMAN_SENTINEL",
                    "run": BASE,
                    "trace_id": record["trace_id"],
                    "unsure": [],
                })
            two_path = os.path.join(directory, "two.jsonl")
            write_text(two_path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in kept))
            http = {
                "fail_chat_at": 2,
                "replies": {
                    "judge:1|%s|C1|rule_adherence" % BASE: "PASS\nReason: ok",
                    "judge:1|%s|C2|rule_adherence" % BASE: "PASS\nReason: ok",
                },
                "show": {"judge:1": "llama"},
                "tags": {"judge:1": "digest-1"},
                "version": "0.1.0",
            }
            http_path = os.path.join(directory, "http.json")
            write_text(http_path, json.dumps(http))
            http_out = os.path.join(directory, "http-out")
            refused = cli([
                "run", "--labels", two_path, "--rubrics", one,
                "--adapter", "ollama:judge:1", "--http-fixture", http_path, "--out", http_out,
            ])
            self.assert_status_2(refused, "Ollama connection failed", [
                os.path.join(http_out, "verdicts.jsonl"),
                os.path.join(http_out, "judge_meta.json"),
            ])
            ok_http = dict(http)
            del ok_http["fail_chat_at"]
            ok_http["replies"] = {"judge:1|%s|C1|rule_adherence" % BASE: "PASS\nReason: ok"}
            ok_path = os.path.join(directory, "http-ok.json")
            write_text(ok_path, json.dumps(ok_http))
            one_label = os.path.join(directory, "one.jsonl")
            write_text(one_label, json.dumps(kept[0], sort_keys=True) + "\n")
            ok_out = os.path.join(directory, "http-ok-out")
            made = cli([
                "run", "--labels", one_label, "--rubrics", one,
                "--adapter", "ollama:judge:1", "--http-fixture", ok_path, "--out", ok_out,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            ok_meta = json.loads(open(os.path.join(ok_out, "judge_meta.json"), encoding="utf-8").read())
            self.assertEqual(set(ok_meta.keys()), META_KEYS)
            # Canned replies are not an Ollama run: a judgments directory made this way must say so.
            self.assertEqual(ok_meta["adapter"], "http-fixture")
            self.assertEqual(ok_meta["model"], "judge:1")
            self.assertEqual(ok_meta["digest"], "digest-1")
            self.assertEqual(ok_meta["server_version"], "0.1.0")
            self.assertEqual(ok_meta["options"], {"num_ctx": 16384, "num_predict": 256, "seed": 0, "temperature": 0})
            self.assertFalse(os.path.exists(os.path.join(http_out, "verdicts.jsonl")))

    def test_a_failed_write_leaves_each_path_as_it_was(self):
        with self.temporary() as directory:
            labels, _meta = self.base_labels(directory)
            replies = "fake:" + ROOT + "/replies.json"
            # A directory where judge_meta.json goes makes the second write fail.
            again = os.path.join(directory, "again")
            os.makedirs(os.path.join(again, "judge_meta.json"))
            write_text(os.path.join(again, "verdicts.jsonl"), "OLD\n")
            refused = cli(["run", "--labels", labels, "--rubrics", RUBRICS, "--adapter", replies, "--out", again])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertIn("could not write output", refused.stderr)
            with open(os.path.join(again, "verdicts.jsonl"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "OLD\n")
            fresh = os.path.join(directory, "fresh")
            os.makedirs(os.path.join(fresh, "judge_meta.json"))
            refused = cli(["run", "--labels", labels, "--rubrics", RUBRICS, "--adapter", replies, "--out", fresh])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertFalse(os.path.exists(os.path.join(fresh, "verdicts.jsonl")))

    def test_human_label_is_not_sent_to_the_adapter(self):
        records = {row["case_id"]: row for row in load_run(BASE)}
        record = records["C1"]
        label = {
            "case_id": "C1",
            "human": {"rule_adherence": "FAIL"},
            "note": "HUMAN_SENTINEL",
            "run": BASE,
            "trace_id": record["trace_id"],
            "unsure": [],
        }

        class Recording(object):
            def __init__(self):
                self.calls = []
                self.model = None
                self.digest = None
                self.server_version = None
                self.options = None
                self.key = None

            def __call__(self, system, user):
                self.calls.append((system, user))
                return "PASS\nReason: ok"

        adapter = Recording()
        rubric = {"name": "rule_adherence", "text": "PASS FAIL Reason: x\n", "sha256": "abc"}
        from scorer.judge import judge_rows
        verdicts = judge_rows([label], [rubric], adapter, {})
        self.assertEqual(len(adapter.calls), 1)
        system, user = adapter.calls[0]
        self.assertNotIn("HUMAN_SENTINEL", system)
        self.assertNotIn("HUMAN_SENTINEL", user)
        self.assertEqual(user, render_case(record))
        self.assertNotIn("human", verdicts[0])

    def test_ollama_client_posts_the_grader_shape(self):
        captured = []

        def opener(request, timeout=None):
            captured.append((request.full_url, request.data, timeout))
            if request.full_url.endswith("/api/version"):
                raw = b'{"version":"0.9.0"}'
            elif request.full_url.endswith("/api/tags"):
                raw = b'{"models":[{"name":"judge:1","digest":"abc123"}]}'
            elif request.full_url.endswith("/api/show"):
                raw = b'{"details":{"family":"llama"}}'
            else:
                raw = b'{"message":{"content":"PASS\\nReason: ok"}}'
            return _Body(raw)

        client = OllamaClient(opener=opener)
        adapter = OllamaAdapter("judge:1", client)
        reply = run_judge("RUBRIC", "CASE", adapter)
        self.assertEqual(reply, "PASS\nReason: ok")
        self.assertEqual(adapter.digest, "abc123")
        self.assertEqual(adapter.server_version, "0.9.0")
        chat = [item for item in captured if item[0].endswith("/api/chat")]
        self.assertEqual(len(chat), 1)
        url, data, timeout = chat[0]
        self.assertEqual(url, OLLAMA_ORIGIN + "/api/chat")
        self.assertEqual(url, "http://127.0.0.1:11434/api/chat")
        with open("grader/agent.py", encoding="utf-8") as handle:
            self.assertIn('OLLAMA_URL = "http://127.0.0.1:11434/api/chat"', handle.read())
        payload = json.loads(data.decode("utf-8"))
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["think"], False)
        self.assertEqual(payload["options"], {"temperature": 0, "seed": 0, "num_ctx": 16384, "num_predict": 256})
        self.assertEqual(payload["messages"], [
            {"role": "system", "content": "RUBRIC"},
            {"role": "user", "content": "CASE"},
        ])
        self.assertEqual(timeout, 180)

        def down(_request, timeout=None):
            raise urllib.error.URLError("down")

        with self.assertRaises(JudgeError) as caught:
            OllamaClient(opener=down).version()
        self.assertIn("connection failed", str(caught.exception))
        with self.assertRaises(JudgeError) as caught:
            FixtureClient({"tags": {}, "version": "0"}).digest("missing")
        self.assertIn("lacks the model", str(caught.exception))

    def test_pick_model(self):
        grader = ROOT + "/_tmp_grader"
        no_model = ROOT + "/_tmp_no_model"
        try:
            os.makedirs(grader, exist_ok=True)
            write_text(os.path.join(grader, "run_meta.json"), json.dumps({"model": "qwen3:8b"}) + "\n")
            os.makedirs(no_model, exist_ok=True)
            write_text(os.path.join(no_model, "run_meta.json"), "{}\n")
            self.pick_model_body(grader, no_model)
        finally:
            import shutil
            shutil.rmtree(grader, ignore_errors=True)
            shutil.rmtree(no_model, ignore_errors=True)

    def pick_model_body(self, grader, no_model):
        with self.temporary() as directory:
            plan = os.path.join(directory, "plan.json")
            write_text(plan, canonical_json([{"run": "traces/v1", "case_id": "C1", "trace_id": "t-1"}]))
            rubrics = os.path.join(directory, "rubrics")
            rubric_file(rubrics, "rule_adherence")
            smoke = "traces/smoke-1"
            cases = [row["case_id"] for row in load_run(smoke)]
            self.assertEqual(cases, ["SMOKE1", "SMOKE2", "SMOKE3"])

            def replies_for(model, texts):
                found = {}
                for case_id, text in zip(cases, texts):
                    found["%s|%s|%s|rule_adherence" % (model, smoke, case_id)] = text
                return found

            http = {
                "replies": {},
                "show": {"qwen3:8b": "qwen3", "model-a": "llama", "model-b": "gemma", "model-c": "mistral"},
                "tags": {"model-a": "digest-a", "model-b": "digest-b", "model-c": "digest-c", "qwen3:8b": "digest-q"},
                "version": "0.5.0",
            }
            http["replies"].update(replies_for("model-a", ["PASS\nReason: a", "PASS\nReason: a", "Pass\nReason: a"]))
            http["replies"].update(replies_for("model-b", ["PASS\nReason: b", "FAIL\nReason: b", "PASS\nReason: b"]))
            path = os.path.join(directory, "http.json")
            write_text(path, json.dumps(http))
            out = os.path.join(directory, "choice.json")
            status, _stdout, stderr, networked = offline([
                "pick-model", "--candidates", "model-a,model-b,model-c",
                "--grader-run", grader, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", path, "--out", out,
            ])
            self.assertEqual(status, 0, stderr)
            self.assertFalse(networked, "pick-model with --http-fixture opened a network connection")
            choice = json.loads(open(out, encoding="utf-8").read())
            # No timestamp and no machine path in model-choice.json either.
            self.assertEqual(set(choice.keys()), CHOICE_KEYS)
            self.assertEqual(choice["adapter"], "http-fixture")
            for candidate in choice["candidates"]:
                self.assertEqual(set(candidate.keys()), {"digest", "family", "model", "parsed", "ran", "replies"})
            self.assertEqual(choice["choice"], "model-b")
            self.assertEqual(choice["not_run"], ["model-c"])
            self.assertEqual([row["model"] for row in choice["candidates"]], ["model-a", "model-b", "model-c"])
            self.assertEqual(choice["candidates"][0]["parsed"], 2)
            self.assertEqual(choice["candidates"][0]["replies"], 3)
            self.assertEqual(choice["candidates"][1]["parsed"], 3)
            self.assertEqual(choice["candidates"][1]["family"], "gemma")
            self.assertEqual(choice["candidates"][1]["digest"], "digest-b")
            self.assertFalse(choice["candidates"][2]["ran"])
            self.assertIsNone(choice["candidates"][2]["family"])
            first = os.path.join(directory, "first.json")
            http_first = json.loads(json.dumps(http))
            http_first["replies"] = replies_for("model-a", ["PASS\nReason: a", "PASS\nReason: a", "PASS\nReason: a"])
            first_http = os.path.join(directory, "http-first.json")
            write_text(first_http, json.dumps(http_first))
            made = cli([
                "pick-model", "--candidates", "model-a,model-b",
                "--grader-run", grader, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", first_http, "--out", first,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(json.loads(open(first, encoding="utf-8").read())["choice"], "model-a")
            self.assertEqual(json.loads(open(first, encoding="utf-8").read())["not_run"], ["model-b"])
            same = os.path.join(directory, "same.json")
            http_same = json.loads(json.dumps(http))
            http_same["show"]["model-a"] = "qwen3"
            http_same["replies"] = replies_for("model-a", ["PASS\nReason: a", "PASS\nReason: a", "PASS\nReason: a"])
            same_http = os.path.join(directory, "http-same.json")
            write_text(same_http, json.dumps(http_same))
            refused = cli([
                "pick-model", "--candidates", "model-a,model-b",
                "--grader-run", grader, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", same_http, "--out", same,
            ])
            self.assert_status_2(refused, "equals the grader family", [same])
            missing_family = os.path.join(directory, "missing-family.json")
            http_missing = json.loads(json.dumps(http_same))
            http_missing["show"]["model-a"] = ""
            http_missing["replies"] = replies_for("model-a", ["PASS\nReason: a", "PASS\nReason: a", "PASS\nReason: a"])
            missing_http = os.path.join(directory, "http-missing.json")
            write_text(missing_http, json.dumps(http_missing))
            refused = cli([
                "pick-model", "--candidates", "model-a",
                "--grader-run", grader, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", missing_http, "--out", missing_family,
            ])
            self.assert_status_2(refused, "lacks details.family", [missing_family])
            overlap = os.path.join(directory, "overlap.json")
            overlap_plan = os.path.join(directory, "overlap-plan.json")
            write_text(overlap_plan, canonical_json([{"run": "traces/v1", "case_id": "SMOKE2", "trace_id": "t"}]))
            overlap_http = os.path.join(directory, "http-overlap.json")
            write_text(overlap_http, json.dumps({"fail": "connect", "show": {"qwen3:8b": "qwen3"}, "version": "0"}))
            refused = cli([
                "pick-model", "--candidates", "model-a",
                "--grader-run", grader, "--plan", overlap_plan, "--rubrics", rubrics,
                "--http-fixture", overlap_http, "--out", overlap,
            ])
            self.assert_status_2(refused, "smoke case SMOKE2 is in the plan", [overlap])
            self.assertNotIn("connection", refused.stderr)
            no_model_out = os.path.join(directory, "no-model.json")
            refused = cli([
                "pick-model", "--candidates", "model-a",
                "--grader-run", no_model, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", overlap_http, "--out", no_model_out,
            ])
            self.assert_status_2(refused, "lacks the model", [no_model_out])
            self.assertNotIn("connection", refused.stderr)
            no_digest = os.path.join(directory, "no-digest.json")
            http_digest = json.loads(json.dumps(http))
            del http_digest["tags"]["model-a"]
            http_digest["replies"] = replies_for("model-a", ["PASS\nReason: a", "PASS\nReason: a", "PASS\nReason: a"])
            digest_http = os.path.join(directory, "http-digest.json")
            write_text(digest_http, json.dumps(http_digest))
            refused = cli([
                "pick-model", "--candidates", "model-a",
                "--grader-run", grader, "--plan", plan, "--rubrics", rubrics,
                "--http-fixture", digest_http, "--out", no_digest,
            ])
            self.assert_status_2(refused, "/api/tags lacks the model", [no_digest])

    def base_labels(self, directory):
        plan = os.path.join(directory, "plan.json")
        made = cli(["select", "--base", BASE, "--n-fresh", "0", "--out", plan])
        self.assertEqual(made.returncode, 0, made.stderr)
        sheet_dir = os.path.join(directory, "sheet")
        made = cli(["sheet", "--plan", plan, "--rubrics", RUBRICS, "--out", sheet_dir])
        self.assertEqual(made.returncode, 0, made.stderr)
        with open(os.path.join(sheet_dir, "labels.csv"), encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            header = list(reader.fieldnames)
        filled = os.path.join(directory, "filled.csv")
        self.write_filled(rows, header, filled)
        labels = os.path.join(directory, "labels.jsonl")
        meta = os.path.join(directory, "labels-meta.json")
        made = cli([
            "import-labels", "--plan", plan, "--sheet", filled, "--rubrics", RUBRICS,
            "--labels", labels, "--meta", meta,
        ])
        self.assertEqual(made.returncode, 0, made.stderr)
        return labels, meta

    def temporary(self):
        import tempfile
        return tempfile.TemporaryDirectory()


class _Body(object):
    def __init__(self, raw):
        self.raw = raw

    def read(self):
        return self.raw

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class ReportTests(unittest.TestCase):
    def world(self, directory, rows, verdicts, meta_rubrics, labels_meta_rubrics, provenance, readings=None, final=None):
        labels = os.path.join(directory, "labels.jsonl")
        write_text(labels, "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows))
        write_text(os.path.join(directory, "labels-meta.json"), canonical_json({
            "plan_sha256": "abc",
            "rubrics": labels_meta_rubrics,
        }))
        verdict_dir = os.path.join(directory, "verdicts")
        write_text(os.path.join(verdict_dir, "verdicts.jsonl"), "".join(
            json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in verdicts
        ))
        write_text(os.path.join(verdict_dir, "judge_meta.json"), canonical_json({
            "digest": "digest-1",
            "labels_sha256": sha256(labels),
            "model": "judge:1",
            "options": {"num_ctx": 16384, "num_predict": 256, "seed": 0, "temperature": 0},
            "rubrics": meta_rubrics,
            "server_version": "0.1.0",
        }))
        provenance_path = os.path.join(directory, "provenance.txt")
        write_text(provenance_path, provenance)
        readings_path = None
        if readings is not None:
            readings_path = os.path.join(directory, "readings.json")
            write_text(readings_path, canonical_json(readings))
        final_path = None
        if final is not None:
            final_path = os.path.join(directory, "final.jsonl")
            write_text(final_path, "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in final))
        return labels, final_path, readings_path, provenance_path, verdict_dir

    def row(self, case_id, human, trace="t"):
        return {
            "case_id": case_id,
            "human": human,
            "note": "",
            "run": "fixture/run",
            "trace_id": trace,
            "unsure": [],
        }

    def verdict(self, case_id, rubric, verdict, reason, sha, trace="t"):
        return {
            "case_id": case_id,
            "reason": reason,
            "reply": verdict + "\nReason: " + reason,
            "rubric": rubric,
            "rubric_sha256": sha,
            "run": "fixture/run",
            "trace_id": trace,
            "verdict": verdict,
        }

    def test_disagreement_cells_unparsed_and_kappa(self):
        # judge, human for alpha: PASS/PASS, PASS/FAIL, FAIL/PASS, FAIL/FAIL, UNPARSED/PASS
        alpha = "alpha"
        beta = "beta"
        sha = {"alpha": "a" * 64, "beta": "b" * 64}
        cases = ["R1", "R2", "R3", "R4", "R5"]
        alpha_pairs = (
            ("PASS", "PASS"),
            ("PASS", "FAIL"),
            ("FAIL", "PASS"),
            ("FAIL", "FAIL"),
            ("UNPARSED", "PASS"),
        )
        rows = []
        verdicts = []
        for case_id, (judge, human) in zip(cases, alpha_pairs):
            rows.append(self.row(case_id, {alpha: human, beta: "PASS"}))
            verdicts.append(self.verdict(case_id, alpha, judge, "because", sha[alpha]))
            verdicts.append(self.verdict(case_id, beta, "PASS", "because", sha[beta]))
        with tempfile_dir() as directory:
            labels, _final, readings, provenance, verdict_dir = self.world(
                directory, rows, verdicts, sha, sha,
                "Hand written. These numbers are not held out.\n",
                readings={"alpha": {"fixture/run|R2": "  ", "fixture/run|R1": "seen"}},
            )
            markdown, document = build_report(labels, None, readings, provenance, verdict_dir)
            alpha_doc = [item for item in document["rubrics"] if item["rubric"] == "alpha"][0]
            side = alpha_doc["first_pass"]
            self.assertEqual(side["JP_HP"], 1)
            self.assertEqual(side["tn"], 1)
            self.assertEqual(side["JP_HF"], 1)
            self.assertEqual(side["fn"], 1)
            self.assertEqual(side["JF_HP"], 2)
            self.assertEqual(side["fp"], 2)
            self.assertEqual(side["JF_HF"], 1)
            self.assertEqual(side["tp"], 1)
            self.assertEqual(alpha_doc["unparsed"], 1)
            predicted = [judge != "PASS" for judge, _human in alpha_pairs]
            truth = [human == "FAIL" for _judge, human in alpha_pairs]
            counts = confusion(predicted, truth)
            self.assertEqual(side["kappa"], None if cohen_kappa(counts) is None else round(cohen_kappa(counts), 4))
            self.assertEqual(side["meets_bar"], meets_bar(counts))
            self.assertIn("JP_HF (fn): 1", markdown)
            self.assertIn("JF_HP (fp): 2", markdown)
            passes = side["false_passes"]
            fails = side["false_fails"]
            self.assertEqual([(item["case_id"], item["reading"]) for item in passes], [("R2", False)])
            self.assertEqual(sorted(item["case_id"] for item in fails), ["R3", "R5"])
            self.assertEqual(side["false_passes_read"], "0 of 1")
            self.assertIn("meets_bar (%s)" % side["bar"], markdown)
            self.assertIn("False passes read: 0 of 1", markdown)
            self.assertNotIn("trust", markdown.split("## Written by hand, not computed")[0])
            beta_doc = [item for item in document["rubrics"] if item["rubric"] == "beta"][0]
            self.assertIsNone(beta_doc["first_pass"]["kappa"])
            self.assertEqual(document["worst"]["rubrics"], ["beta"])
            self.assertFalse(document["worst"]["tied"])
            self.assertEqual(document["worst"]["labels"], "first-pass")
            self.assertIn("Worst judge on the first-pass labels: beta.", markdown)

    def test_worst_tie_rules_and_which_labels(self):
        # Same rounded kappa, different false-pass counts. The larger count is worse.
        # zzz has the false pass, so a name sort would not pick it on its own.
        sha = {"aaa": "a" * 64, "zzz": "b" * 64}
        cases = ["R1", "R2", "R3", "R4"]
        # aaa: tn, tn, tp, fp -> fn 0
        # zzz: tn, tn, tp, fn -> fn 1
        patterns = {
            "aaa": (("PASS", "PASS"), ("PASS", "PASS"), ("FAIL", "FAIL"), ("FAIL", "PASS")),
            "zzz": (("PASS", "PASS"), ("PASS", "PASS"), ("FAIL", "FAIL"), ("PASS", "FAIL")),
        }
        rows = []
        verdicts = []
        for index, case_id in enumerate(cases):
            human = {name: patterns[name][index][1] for name in ("aaa", "zzz")}
            rows.append(self.row(case_id, human))
            for name in ("aaa", "zzz"):
                verdicts.append(self.verdict(case_id, name, patterns[name][index][0], "because", sha[name]))
        with tempfile_dir() as directory:
            labels, _final, _readings, provenance, verdict_dir = self.world(
                directory, rows, verdicts, sha, sha, "Hand written.\n",
            )
            _markdown, document = build_report(labels, None, None, provenance, verdict_dir)
            by_name = {item["rubric"]: item for item in document["rubrics"]}
            self.assertEqual(by_name["aaa"]["first_pass"]["kappa"], by_name["zzz"]["first_pass"]["kappa"])
            self.assertEqual(len(by_name["zzz"]["first_pass"]["false_passes"]), 1)
            self.assertEqual(len(by_name["aaa"]["first_pass"]["false_passes"]), 0)
            self.assertEqual(document["worst"]["rubrics"], ["zzz"])
            self.assertFalse(document["worst"]["tied"])
        tied_rows = []
        tied_verdicts = []
        for case_id, (judge, human) in zip(cases, patterns["aaa"]):
            tied_rows.append(self.row(case_id, {"aaa": human, "zzz": human}))
            tied_verdicts.append(self.verdict(case_id, "aaa", judge, "because", sha["aaa"]))
            tied_verdicts.append(self.verdict(case_id, "zzz", judge, "because", sha["zzz"]))
        with tempfile_dir() as directory:
            labels, _final, _readings, provenance, verdict_dir = self.world(
                directory, tied_rows, tied_verdicts, sha, sha, "Hand written.\n",
            )
            markdown, document = build_report(labels, None, None, provenance, verdict_dir)
            self.assertTrue(document["worst"]["tied"])
            self.assertEqual(document["worst"]["rubrics"], ["aaa", "zzz"])
            self.assertIn("Worst judges on the first-pass labels tied: aaa, zzz.", markdown)
        self.which_labels()

    def which_labels(self):
        sha = {"alpha": "a" * 64, "beta": "b" * 64}
        cases = ["R1", "R2", "R3", "R4"]
        rows = []
        finals = []
        verdicts = []
        for index, case_id in enumerate(cases):
            # alpha verdicts are all PASS. First-pass humans are all PASS (kappa is undefined).
            # beta verdicts are all FAIL. First-pass humans are mixed.
            alpha_human = "PASS"
            beta_human = "FAIL" if index < 2 else "PASS"
            rows.append(self.row(case_id, {"alpha": alpha_human, "beta": beta_human}))
            verdicts.append(self.verdict(case_id, "alpha", "PASS", "because", sha["alpha"]))
            verdicts.append(self.verdict(case_id, "beta", "FAIL", "because", sha["beta"]))
            final = {
                "case_id": case_id,
                "changes": [],
                "human": {"alpha": "PASS" if index < 2 else "FAIL", "beta": "FAIL"},
                "note": "",
                "run": "fixture/run",
                "trace_id": "t",
                "unsure": [],
            }
            if index >= 2:
                final["changes"].append({
                    "from": "PASS", "reason": "read again", "rubric": "alpha", "to": "FAIL",
                })
            if index >= 2:
                final["changes"].append({
                    "from": "PASS", "reason": "read again", "rubric": "beta", "to": "FAIL",
                })
            finals.append(final)
        with tempfile_dir() as directory:
            labels, final, _readings, provenance, verdict_dir = self.world(
                directory, rows, verdicts, sha, sha, "Hand written.\n", final=finals,
            )
            without, without_doc = build_report(labels, None, None, provenance, verdict_dir)
            with_final, with_doc = build_report(labels, final, None, provenance, verdict_dir)
            self.assertEqual(without_doc["worst"]["labels"], "first-pass")
            self.assertEqual(without_doc["worst"]["rubrics"], ["alpha"])
            self.assertIn("first-pass labels: alpha.", without)
            self.assertEqual(with_doc["worst"]["labels"], "final")
            self.assertEqual(with_doc["worst"]["rubrics"], ["beta"])
            self.assertIn("final labels: beta.", with_final)
            self.assertIsNotNone(with_doc["rubrics"][0]["final"])

    def test_text_state_provenance_and_refusals(self):
        sha_judge = {"alpha": "a" * 64}
        sha_labels = {"alpha": "c" * 64}
        rows = [self.row("R1", {"alpha": "PASS"})]
        verdicts = [self.verdict("R1", "alpha", "PASS", "because", sha_judge["alpha"])]
        provenance = "Hand written for this fixture. The result is not held out.\n"
        with tempfile_dir() as directory:
            labels, _final, _readings, provenance_path, verdict_dir = self.world(
                directory, rows, verdicts, sha_judge, sha_labels, provenance,
            )
            markdown, document = build_report(labels, None, None, provenance_path, verdict_dir)
            self.assertEqual(document["rubrics"][0]["text"], "changed since the labels were made: in sample")
            self.assertIn("changed since the labels were made: in sample", markdown)
            marker = "\n## Written by hand, not computed\n\n"
            head, found, tail = markdown.partition(marker)
            self.assertTrue(found)
            self.assertNotIn("held out", head)
            self.assertEqual(tail, provenance)
            self.assertIn("not held out", markdown)
            copy = dict(document)
            copy.pop("provenance")
            self.assertNotIn("held out", canonical_json(copy))
            self.assertEqual(document["provenance"], provenance)
            same = os.path.join(directory, "labels-meta.json")
            write_text(same, canonical_json({"plan_sha256": "abc", "rubrics": sha_judge}))
            markdown, document = build_report(labels, None, None, provenance_path, verdict_dir)
            self.assertEqual(document["rubrics"][0]["text"], "same text as when the labels were made")
            self.assertIn("same text as when the labels were made", markdown)
            # Verdicts that were not made from these labels, or with these rubrics, are refused.
            mismatches = (
                ("trace", "verdict trace_id does not match the label row"),
                ("hash", "verdict rubric hash does not match judge_meta"),
                ("labels", "verdicts were not made from this labels file"),
            )
            for kind, fragment in mismatches:
                with self.subTest(mismatch=kind):
                    other = os.path.join(directory, "mismatch-" + kind)
                    bad_verdicts = [dict(verdicts[0])]
                    if kind == "trace":
                        bad_verdicts[0]["trace_id"] = "other-trace"
                    if kind == "hash":
                        bad_verdicts[0]["rubric_sha256"] = "d" * 64
                    paths = self.world(other, rows, bad_verdicts, sha_judge, sha_judge, provenance)
                    if kind == "labels":
                        write_text(paths[0], open(paths[0], encoding="utf-8").read().replace('"note": ""', '"note": "edited"'))
                    with self.assertRaises(JudgeError) as caught:
                        build_report(paths[0], None, None, paths[3], paths[4])
                    self.assertIn(fragment, str(caught.exception))
            missing = os.path.join(directory, "missing-provenance.txt")
            out = os.path.join(directory, "out.md")
            refused = cli([
                "report", "--labels", labels, "--provenance", missing, "--verdicts", verdict_dir, "--md", out,
            ])
            self.assertEqual(refused.returncode, 2)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertEqual(refused.stdout, "")
            self.assertFalse(os.path.exists(out))
            empty = os.path.join(directory, "empty.txt")
            write_text(empty, " \n")
            refused = cli([
                "report", "--labels", labels, "--provenance", empty, "--verdicts", verdict_dir, "--md", out,
            ])
            self.assertEqual(refused.returncode, 2)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse(os.path.exists(out))
            bad_json = os.path.join(directory, "bad.jsonl")
            write_text(bad_json, "{")
            refused = cli([
                "report", "--labels", bad_json, "--provenance", provenance_path, "--verdicts", verdict_dir, "--md", out,
            ])
            self.assertEqual(refused.returncode, 2)
            self.assertIn("not valid JSON", refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse(os.path.exists(out))
            # The command line is copied into results.md, which is committed: it shows each path
            # relative and normalised, and refuses one it cannot show that way.
            markdown, document = build_report("./" + labels, None, None, provenance_path, verdict_dir + "/")
            self.assertIn("--labels %s --provenance %s --verdicts %s`" % (labels, provenance_path, verdict_dir), markdown)
            self.assertEqual(document["command"].split("--labels ")[1].split(" ")[0], labels)
            for flag, value in (
                ("--labels", os.path.abspath(labels)),
                ("--provenance", "~" + "/" + "provenance.txt"),
                ("--verdicts", "../" + verdict_dir),
            ):
                with self.subTest(flag=flag):
                    args = {"--labels": labels, "--provenance": provenance_path, "--verdicts": verdict_dir}
                    args[flag] = value
                    refused = cli([
                        "report", "--labels", args["--labels"], "--provenance", args["--provenance"],
                        "--verdicts", args["--verdicts"], "--md", out,
                    ])
                    self.assertEqual(refused.returncode, 2, refused.stderr)
                    self.assertNotIn("Traceback", refused.stderr)
                    self.assertEqual(refused.stdout, "")
                    self.assertIn("%s must be a relative path" % flag, refused.stderr)
                    self.assertFalse(os.path.exists(out))

    def test_export_course_shape_fence_and_results(self):
        records = {row["case_id"]: row for row in load_run(BASE)}
        rubric_sha = sha256(os.path.join(RUBRICS, "rule_adherence.md"))
        # The committed rubric directory has three rubrics. Export uses a one-rubric directory
        # except for the fence case, which is its own directory.
        with tempfile_dir() as directory:
            one = os.path.join(directory, "rubrics")
            body = open(os.path.join(RUBRICS, "rule_adherence.md"), encoding="utf-8").read()
            rubric_file(one, "rule_adherence", body)
            row = self.row("C1", {"rule_adherence": "FAIL"}, trace=records["C1"]["trace_id"])
            row["run"] = BASE
            verdict = self.verdict("C1", "rule_adherence", "PASS", "because", rubric_sha, trace=records["C1"]["trace_id"])
            verdict["run"] = BASE
            final = {
                "case_id": "C1",
                "changes": [{"from": "FAIL", "reason": "read again", "rubric": "rule_adherence", "to": "PASS"}],
                "human": {"rule_adherence": "PASS"},
                "note": "",
                "run": BASE,
                "trace_id": records["C1"]["trace_id"],
                "unsure": [],
            }
            labels, final_path, _readings, provenance, verdict_dir = self.world(
                directory, [row], [verdict],
                {"rule_adherence": rubric_sha},
                {"rule_adherence": rubric_sha},
                "Hand written.\n",
                final=[final],
            )
            out = os.path.join(directory, "course")
            made = cli([
                "export-course", "--labels", labels, "--rubrics", one, "--provenance", provenance,
                "--verdicts", verdict_dir, "--out", out,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(set(os.listdir(out)), {"labels.jsonl", "results.md", "rubrics.md"})
            course = json.loads(open(os.path.join(out, "labels.jsonl"), encoding="utf-8").read())
            self.assertEqual(set(course.keys()), {"human", "input", "output"})
            case_text = render_case(records["C1"])
            ticket, output = case_sections(case_text)
            self.assertEqual(course["input"], ticket)
            self.assertEqual(course["output"], output)
            self.assertEqual(ticket + "\n\n" + output, case_text)
            self.assertEqual(course["human"], {"rule_adherence": "FAIL"})
            report_out = os.path.join(directory, "report.md")
            made = cli([
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir, "--md", report_out,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            self.assertEqual(open(os.path.join(out, "results.md"), "rb").read(), open(report_out, "rb").read())
            out_final = os.path.join(directory, "course-final")
            made = cli([
                "export-course", "--labels", labels, "--final", final_path, "--rubrics", one,
                "--provenance", provenance, "--verdicts", verdict_dir, "--out", out_final,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            course_final = json.loads(open(os.path.join(out_final, "labels.jsonl"), encoding="utf-8").read())
            self.assertEqual(course_final["human"], {"rule_adherence": "PASS"})
            self.assertEqual(course_final["input"], course["input"])
            report_final = os.path.join(directory, "report-final.md")
            made = cli([
                "report", "--labels", labels, "--final", final_path, "--provenance", provenance,
                "--verdicts", verdict_dir, "--md", report_final,
            ])
            self.assertEqual(open(os.path.join(out_final, "results.md"), "rb").read(), open(report_final, "rb").read())
            self.assertNotEqual(open(report_out, "rb").read(), open(report_final, "rb").read())
            rubrics_text = open(os.path.join(out, "rubrics.md"), encoding="utf-8").read()
            self.assertIn(body, rubrics_text)
            self.assertIn(rubric_sha, rubrics_text)
            fence_dir = os.path.join(directory, "fence")
            fenced = "before ```` inside\nPASS\nFAIL\nReason: x\n"
            rubric_file(fence_dir, "rule_adherence", fenced)
            fence_sha = sha256(os.path.join(fence_dir, "rule_adherence.md"))
            labels2, _f, _r, provenance2, verdicts2 = self.world(
                os.path.join(directory, "fence-world"),
                [row],
                [dict(verdict, rubric_sha256=fence_sha)],
                {"rule_adherence": fence_sha},
                {"rule_adherence": fence_sha},
                "Hand written.\n",
            )
            files = export_files(labels2, None, None, provenance2, verdicts2, fence_dir, {})
            text = files["rubrics.md"]
            self.assertIn("\n`````\n", text)
            self.assertNotIn("\n````\n", text.split("`````", 2)[1])
            self.assertIn(fenced, text)
            plain = os.path.join(directory, "plain")
            rubric_file(plain, "rule_adherence", "PASS\nFAIL\nReason: x\n")
            plain_sha = sha256(os.path.join(plain, "rule_adherence.md"))
            labels3, _f, _r, provenance3, verdicts3 = self.world(
                os.path.join(directory, "plain-world"),
                [row],
                [dict(verdict, rubric_sha256=plain_sha)],
                {"rule_adherence": plain_sha},
                {"rule_adherence": plain_sha},
                "Hand written.\n",
            )
            plain_text = export_files(labels3, None, None, provenance3, verdicts3, plain, {})["rubrics.md"]
            self.assertIn("\n```\n", plain_text)
            bad_row = dict(row, trace_id="other-trace")
            bad_verdict = dict(verdict, trace_id="other-trace")
            bad_dir = os.path.join(directory, "bad-world")
            bad_labels, _bad_final, _bad_readings, bad_provenance, bad_verdicts = self.world(
                bad_dir, [bad_row], [bad_verdict],
                {"rule_adherence": rubric_sha},
                {"rule_adherence": rubric_sha},
                "Hand written.\n",
            )
            bad_out = os.path.join(directory, "bad-out")
            refused = cli([
                "export-course", "--labels", bad_labels, "--rubrics", one, "--provenance", bad_provenance,
                "--verdicts", bad_verdicts, "--out", bad_out,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertIn("run changed after labelling", refused.stderr)
            self.assertFalse(os.path.exists(os.path.join(bad_out, "labels.jsonl")))
            # A rubric edited after the judge ran is not the text behind results.md.
            edited = os.path.join(directory, "edited")
            rubric_file(edited, "rule_adherence", body + "Edited after the run.\n")
            edited_out = os.path.join(directory, "edited-out")
            refused = cli([
                "export-course", "--labels", labels, "--rubrics", edited, "--provenance", provenance,
                "--verdicts", verdict_dir, "--out", edited_out,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertIn("rubric rule_adherence is not the text the judge ran", refused.stderr)
            self.assertFalse(os.path.exists(edited_out))

    def test_sheet_size_limit_names_the_case(self):
        run = ROOT + "/_tmp_size"
        try:
            from tests.judge_otlp import write_run
            write_run(run, [{
                "case_id": "BIG",
                "final": None,
                "reason": None,
                "status": "complete",
                "ticket": {"pad": "x" * 30000},
                "tools": [],
                "trace_id": "tb-big",
            }])
            with tempfile_dir() as directory:
                plan = os.path.join(directory, "plan.json")
                write_text(plan, canonical_json([{"run": run, "case_id": "BIG", "trace_id": "tb-big"}]))
                rubrics = os.path.join(directory, "rubrics")
                rubric_file(rubrics, "rule_adherence")
                out = os.path.join(directory, "sheet")
                refused = cli(["sheet", "--plan", plan, "--rubrics", rubrics, "--out", out])
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertNotIn("Traceback", refused.stderr)
                self.assertIn("BIG", refused.stderr)
                self.assertFalse(os.path.exists(os.path.join(out, "case-files.md")))
        finally:
            import shutil
            shutil.rmtree(run, ignore_errors=True)

    def test_committed_fixture_report_regenerates(self):
        labels = ROOT + "/labels.jsonl"
        final = ROOT + "/labels-final.jsonl"
        readings = ROOT + "/readings.json"
        provenance = ROOT + "/provenance.txt"
        verdicts = ROOT + "/verdicts"
        markdown, document = build_report(labels, final, readings, provenance, verdicts)
        with open(ROOT + "/report.md", encoding="utf-8") as handle:
            committed_md = handle.read()
        with open(ROOT + "/report.json", encoding="utf-8") as handle:
            committed_json = handle.read()
        self.assertEqual(markdown, committed_md)
        self.assertEqual(canonical_json(document), committed_json)
        marker = "\n## Written by hand, not computed\n\n"
        head, found, tail = markdown.partition(marker)
        self.assertTrue(found)
        self.assertNotIn("held out", head)
        self.assertIn("not held out", tail)
        self.assertIn("UNPARSED: 1.", markdown)
        self.assertIn("Worst judges on the final labels tied:", markdown)
        self.assertIn("False passes read: 1 of 1.", markdown)

    def test_repo_root_label_dirs_stay_absent_and_sheets_are_ignored(self):
        for name in ("rubrics", "labels", "judgments", "sheets"):
            self.assertFalse(os.path.isdir(name), name)
        with open(".gitignore", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertIn("sheets/", lines)
        self.assertEqual(lines.count("sheets/"), 1)
        # The tests' scratch runs under ROOT/_tmp*; a run cut short must not leave files git would add.
        self.assertIn(ROOT + "/_tmp*/", lines)


@contextlib.contextmanager
def tempfile_dir():
    """A scratch directory named relative to the repository, as a report's command line requires."""
    import tempfile
    scratch = ROOT + "/_tmp"
    os.makedirs(scratch, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            yield os.path.relpath(directory).replace(os.sep, "/")
    finally:
        try:
            os.rmdir(scratch)
        except OSError:
            pass


if __name__ == "__main__":
    unittest.main()
