"""python3 -m scorer.compare reports what differs between two runs."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from unittest import mock

import scorer.compare as compare

from scorer.calibrate import provenance_for
from scorer.checks import CHECKS
from scorer.compare import compare_runs, format_report
from scorer.score import score_run
from scorer.stats import canonical_json
from scorer.traces import load_run


CASES = "tests/fixtures/compare/cases.json"
RUNS = "tests/fixtures/compare/runs"
V1_AA1_CODES = [
    "GRADE_CONTRADICTS_FACTS 14 15 1",
    "WIN_LOSS_FLIP 14 15 1",
    "SKIPPED_SETTLE_TICKET 9 8 -1",
    "PLACEHOLDER_ECHO 5 5 0",
    "GRADED_WITHOUT_LOOKUP 5 5 0",
    "INCOMPLETE_LEG_LIST 6 7 1",
    "WRONG_NON_GRADE 3 2 -1",
    "NO_FINAL_ANSWER 3 1 -2",
    "RULE_TOPIC_MISS 3 5 2",
    "OUTPUT_LIMIT_SPRAY 2 0 -2",
    "FOLLOWED_TICKET_CLAIM 2 2 0",
]


def _scratch():
    return tempfile.TemporaryDirectory(prefix="_tmp", dir="tests/fixtures/compare")


def _cli(args, json_out=None):
    command = [sys.executable, "-m", "scorer.compare", *args]
    if json_out is not None:
        command.extend(["--json", json_out])
    return subprocess.run(command, capture_output=True, text=True)


def _finals(run_dir):
    found = {}
    for record in load_run(run_dir):
        final = record["final"]
        if final is None:
            found[record["case_id"]] = None
        else:
            found[record["case_id"]] = json.dumps(final, sort_keys=True, ensure_ascii=False)
    return found


def _code_sets(run_dir):
    scored = score_run(run_dir)
    return {ticket["case_id"]: {flag["code"] for flag in ticket["flags"]} for ticket in scored["tickets"]}


class CompareFloorTests(unittest.TestCase):
    def test_aa_pairs_share_32_tickets_and_record_no_setup(self):
        for pair in (("traces/aa-1", "traces/aa-2"), ("traces/aa-2", "traces/aa-3")):
            with self.subTest(pair=pair):
                report = compare_runs(*pair)
                text = format_report(report)
                self.assertEqual(report["tickets"], {
                    "a": 32, "b": 32, "only_a": [], "only_b": [], "shared": 32,
                })
                self.assertEqual(report["final_answers"], {"case_ids": [], "differ": 0})
                self.assertEqual(_finals(pair[0]), _finals(pair[1]))
                self.assertEqual([row["b_minus_a"] for row in report["codes"]], [0] * len(CHECKS))
                self.assertEqual(report["codes_differ"], [])
                self.assertEqual(_code_sets(pair[0]), _code_sets(pair[1]))
                self.assertFalse(report["setup"]["a_recorded"])
                self.assertFalse(report["setup"]["b_recorded"])
                self.assertTrue(report["setup"]["cannot_trace"])
                self.assertNotIn("matches", report["setup"])
                self.assertNotIn("recorded setup matches", text)
                self.assertIn("A records setup no\n", text)
                self.assertIn("B records setup no\n", text)
                self.assertIn("a difference between the runs cannot be traced to its setup\n", text)
                for banned in ("drift", "noise", "verdict", "threshold"):
                    self.assertNotIn(banned, text.lower())

    def test_v1_against_aa1_matches_score_run(self):
        report = compare_runs("traces/v1", "traces/aa-1")
        text = format_report(report)
        lines = text.splitlines()
        start = lines.index("codes") + 1
        self.assertEqual(lines[start:start + len(CHECKS)], V1_AA1_CODES)
        self.assertEqual([row["code"] for row in report["codes"]], list(CHECKS))
        for run, side in (("traces/v1", "a"), ("traces/aa-1", "b")):
            scored = score_run(run)
            for row in report["codes"]:
                self.assertEqual(row[side], scored["counts"][row["code"]])
        finals_a = _finals("traces/v1")
        finals_b = _finals("traces/aa-1")
        expected_finals = sorted(
            case_id for case_id in finals_a if finals_a[case_id] != finals_b[case_id])
        self.assertEqual(report["final_answers"]["case_ids"], expected_finals)
        self.assertEqual(report["final_answers"]["differ"], 21)
        self.assertEqual(len(expected_finals), 21)
        sets_a = _code_sets("traces/v1")
        sets_b = _code_sets("traces/aa-1")
        expected_codes = sorted(
            case_id for case_id in sets_a if sets_a[case_id] != sets_b[case_id])
        self.assertEqual(report["codes_differ"], expected_codes)
        self.assertEqual(len(expected_codes), 9)
        begin = lines.index("codes differ 9") + 1
        self.assertEqual(lines[begin:begin + len(expected_codes)], expected_codes)
        v1_sentence = provenance_for(load_run("traces/v1"))[1]
        aa_sentence = provenance_for(load_run("traces/aa-1"))[1]
        self.assertEqual(report["provenance"]["a"], v1_sentence)
        self.assertEqual(report["provenance"]["b"], aa_sentence)
        self.assertNotEqual(v1_sentence, aa_sentence)
        self.assertIn(v1_sentence, text)
        self.assertIn(aa_sentence, text)
        self.assertNotIn("recorded setup matches", text)
        self.assertTrue(report["setup"]["cannot_trace"])

    def test_path_spellings_and_json_are_the_same_bytes(self):
        with _scratch() as directory:
            left_json = os.path.join(directory, "left.json")
            right_json = os.path.join(directory, "right.json")
            abs_json = os.path.join(directory, "abs.json")
            left = _cli(["./traces/aa-1/", "traces/aa-2"], left_json)
            right = _cli(["traces/aa-1", "./traces/aa-2/"], right_json)
            absolute = os.path.abspath("traces/aa-1")
            via_abs = _cli([absolute, "traces/aa-2"], abs_json)
            self.assertEqual(left.returncode, 0, left.stderr)
            self.assertEqual(left.stdout, right.stdout)
            self.assertEqual(left.stdout, via_abs.stdout)
            with open(left_json, encoding="utf-8") as handle:
                left_body = handle.read()
            with open(right_json, encoding="utf-8") as handle:
                right_body = handle.read()
            with open(abs_json, encoding="utf-8") as handle:
                abs_body = handle.read()
            self.assertEqual(left_body, right_body)
            self.assertEqual(left_body, abs_body)
            self.assertNotIn(absolute, via_abs.stdout)
            self.assertNotIn(absolute, via_abs.stderr)
            self.assertNotIn(absolute, left_body)
        self.assertIn("A traces/aa-1\n", left.stdout)
        self.assertIn("B traces/aa-2\n", left.stdout)

    def test_committed_output_matches_the_command(self):
        pairs = (
            ("traces/v1", "traces/aa-1", "v1-aa-1"),
            ("traces/aa-1", "traces/aa-2", "aa-1-aa-2"),
            ("traces/aa-2", "traces/aa-3", "aa-2-aa-3"),
        )
        for run_a, run_b, name in pairs:
            with self.subTest(name=name):
                with _scratch() as directory:
                    out = os.path.join(directory, "out.json")
                    done = _cli([run_a, run_b], out)
                    self.assertEqual(done.returncode, 0, done.stderr)
                    text_path = os.path.join("tests/fixtures/compare/output", name + ".txt")
                    json_path = os.path.join("tests/fixtures/compare/output", name + ".json")
                    with open(text_path, encoding="utf-8") as handle:
                        self.assertEqual(done.stdout, handle.read(), name)
                    with open(json_path, encoding="utf-8") as handle:
                        committed = handle.read()
                    with open(out, encoding="utf-8") as handle:
                        self.assertEqual(handle.read(), committed, name)
                    self.assertEqual(committed, canonical_json(json.loads(committed)))


class CompareFixtureTests(unittest.TestCase):
    def _pair(self, left, right):
        return compare_runs(os.path.join(RUNS, left), os.path.join(RUNS, right), cases_path=CASES)

    def test_case_only_in_one_run_counts_toward_that_run(self):
        report = self._pair("only-a", "only-b")
        self.assertEqual(report["tickets"]["shared"], 1)
        self.assertEqual(report["tickets"]["only_a"], ["F2"])
        self.assertEqual(report["tickets"]["only_b"], ["F3"])
        self.assertEqual(report["final_answers"]["case_ids"], [])
        row = next(item for item in report["codes"] if item["code"] == "NO_FINAL_ANSWER")
        self.assertEqual((row["a"], row["b"], row["b_minus_a"]), (1, 0, -1))
        self.assertEqual(report["codes_differ"], [])

    def test_only_in_one_lists_are_in_case_id_order_whatever_the_hash_seed(self):
        with open(os.path.join(RUNS, "order-a", "settlement-traces.json"), encoding="utf-8") as handle:
            template = json.load(handle)
        ids = ["F%s" % number for number in range(2, 10)]
        with _scratch() as directory:
            run = os.path.join(directory, "many")
            os.makedirs(run)
            document = json.loads(json.dumps(template))
            spans = document["resourceSpans"][0]["scopeSpans"][0]["spans"]
            for case_id in ids:
                for span in json.loads(json.dumps(template))["resourceSpans"][0]["scopeSpans"][0]["spans"]:
                    span["traceId"] = "t-" + case_id
                    for item in span.get("attributes") or []:
                        if item["key"] == "case.id":
                            item["value"] = {"stringValue": case_id}
                    spans.append(span)
            with open(os.path.join(run, "settlement-traces.json"), "w", encoding="utf-8") as handle:
                json.dump(document, handle)
            cases = os.path.join(directory, "cases.json")
            with open(CASES, encoding="utf-8") as handle:
                rows = json.load(handle)
            known = {row["case_id"] for row in rows}
            rows.extend(dict(rows[0], case_id=case_id) for case_id in ids if case_id not in known)
            with open(cases, "w", encoding="utf-8") as handle:
                json.dump(rows, handle)
            for seed in ("0", "1", "2", "3"):
                for left, right, side in ((run, os.path.join(RUNS, "order-b"), "only_a"),
                                          (os.path.join(RUNS, "order-b"), run, "only_b")):
                    with self.subTest(seed=seed, side=side):
                        out = os.path.join(directory, "out.json")
                        done = subprocess.run(
                            [sys.executable, "-m", "scorer.compare", left, right, "--cases", cases, "--json", out],
                            capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=seed))
                        self.assertEqual(done.returncode, 0, done.stderr)
                        with open(out, encoding="utf-8") as handle:
                            self.assertEqual(json.load(handle)["tickets"][side], ids)
                        lines = done.stdout.splitlines()
                        start = lines.index("only A" if side == "only_a" else "only B") + 1
                        self.assertEqual(lines[start:start + len(ids)], ids)

    def test_reordered_final_keys_do_not_differ_and_null_does(self):
        same = self._pair("order-a", "order-b")
        self.assertEqual(same["final_answers"], {"case_ids": [], "differ": 0})
        differed = self._pair("order-a", "null-b")
        self.assertEqual(differed["final_answers"], {"case_ids": ["F1"], "differ": 1})
        self.assertEqual(differed["codes_differ"], ["F1"])

    def test_recorded_setup_difference_equality_and_a_missing_key(self):
        same = self._pair("recorded-a", "recorded-same")
        text = format_report(same)
        self.assertEqual(same["setup"]["differ"], [])
        self.assertTrue(same["setup"]["matches"])
        self.assertFalse(same["setup"]["cannot_trace"])
        self.assertIn("recorded setup matches\n", text)
        self.assertNotIn("cannot be traced to its setup", text)

        changed = self._pair("recorded-a", "recorded-b")
        changed_text = format_report(changed)
        self.assertEqual(
            [item["key"] for item in changed["setup"]["differ"]],
            ["budgets", "model_digest", "ollama_version", "system_prompt"],
        )
        self.assertFalse(changed["setup"]["matches"])
        self.assertNotIn("recorded setup matches", changed_text)
        self.assertNotIn("cannot be traced to its setup", changed_text)
        self.assertIn('"max_turns": 12', changed_text)
        self.assertIn('"max_turns": 4', changed_text)

        floated = self._pair("recorded-a", "recorded-float")
        self.assertEqual([item["key"] for item in floated["setup"]["differ"]], ["budgets"])
        self.assertIn("12.0", format_report(floated))

        missing = self._pair("legacy-a", "legacy-b")
        missing_text = format_report(missing)
        self.assertEqual(missing["setup"]["differ"], [])
        self.assertNotIn("matches", missing["setup"])
        self.assertTrue(missing["setup"]["cannot_trace"])
        self.assertNotIn("recorded setup matches", missing_text)
        self.assertIn("A records setup no\n", missing_text)
        self.assertIn("B records setup no\n", missing_text)
        self.assertIn("cannot be traced to its setup", missing_text)

        one_side = self._pair("recorded-a", "legacy-a")
        one_text = format_report(one_side)
        self.assertEqual(
            [item["key"] for item in one_side["setup"]["differ"]],
            ["model_digest", "ollama_version"],
        )
        self.assertTrue(one_side["setup"]["a_recorded"])
        self.assertFalse(one_side["setup"]["b_recorded"])
        self.assertNotIn("matches", one_side["setup"])
        self.assertNotIn("recorded setup matches", one_text)
        self.assertIn("B absent\n", one_text)
        self.assertIn("cannot be traced to its setup", one_text)

        absent_file = self._pair("recorded-a", "no-meta")
        self.assertFalse(absent_file["setup"]["b_recorded"])
        self.assertNotIn("recorded setup matches", format_report(absent_file))
        sentence = provenance_for(load_run(os.path.join(RUNS, "recorded-a")))[1]
        self.assertIn(sentence, format_report(absent_file))

    def test_setup_keys_are_sorted_whatever_the_hash_seed(self):
        expected = ["budgets", "model_digest", "ollama_version", "system_prompt"]
        with _scratch() as directory:
            out = os.path.join(directory, "out.json")
            for seed in ("0", "1", "2", "3", "4", "5", "6", "7"):
                with self.subTest(seed=seed):
                    done = subprocess.run(
                        [sys.executable, "-m", "scorer.compare", os.path.join(RUNS, "recorded-a"),
                         os.path.join(RUNS, "recorded-b"), "--cases", CASES, "--json", out],
                        capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=seed))
                    self.assertEqual(done.returncode, 0, done.stderr)
                    with open(out, encoding="utf-8") as handle:
                        keys = [item["key"] for item in json.load(handle)["setup"]["differ"]]
                    self.assertEqual(keys, expected)
                    lines = done.stdout.splitlines()
                    self.assertEqual([line for line in lines if line in expected], expected)

    def test_one_setup_key_is_not_recorded(self):
        with _scratch() as directory:
            run = os.path.join(directory, "one-key")
            shutil.copytree(os.path.join(RUNS, "recorded-a"), run)
            meta_path = os.path.join(run, "run_meta.json")
            with open(meta_path, encoding="utf-8") as handle:
                meta = json.load(handle)
            for broken in (
                {key: value for key, value in meta.items() if key != "model_digest"},
                dict(meta, model_digest=None),
                dict(meta, ollama_version="  "),
            ):
                with open(meta_path, "w", encoding="utf-8") as handle:
                    json.dump(broken, handle)
                report = compare_runs(os.path.join(RUNS, "recorded-a"), run, cases_path=CASES)
                self.assertFalse(report["setup"]["b_recorded"])
                self.assertNotIn("matches", report["setup"])
                self.assertNotIn("recorded setup matches", format_report(report))


class CompareCommandTests(unittest.TestCase):
    def _assert_error_keeps_output(self, args, needle, directory):
        for existing in (False, True):
            out = os.path.join(directory, "kept.json" if existing else "new.json")
            if existing:
                with open(out, "wb") as handle:
                    handle.write(b"kept\n")
            done = _cli(args, out)
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertEqual(done.stdout, "")
            self.assertNotIn("Traceback", done.stderr)
            self.assertEqual(done.stderr.count("error:"), 1, done.stderr)
            self.assertIn(needle, done.stderr)
            if existing:
                with open(out, "rb") as handle:
                    self.assertEqual(handle.read(), b"kept\n")
            else:
                self.assertFalse(os.path.exists(out))
            yield done

    def test_failed_json_write_preserves_output_and_removes_new_directories(self):
        with _scratch() as directory:
            for existing in (False, True):
                with self.subTest(existing=existing):
                    out = os.path.join(directory, "kept.json" if existing else "new", "out.json")
                    if existing:
                        os.makedirs(os.path.dirname(out))
                        with open(out, "wb") as handle:
                            handle.write(b"kept\n")
                    before = sorted(os.listdir(directory))

                    def failed_write(path, text):
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path, "w", encoding="utf-8") as handle:
                            handle.write(text[:10])
                        raise OSError("write failed")

                    stdout, stderr = StringIO(), StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        with mock.patch.object(compare, "write_text", failed_write):
                            with self.assertRaises(SystemExit) as stopped:
                                compare.main([os.path.join(RUNS, "order-a"), os.path.join(RUNS, "order-b"),
                                              "--cases", CASES, "--json", out])
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertEqual(stdout.getvalue(), "")
                    self.assertEqual(stderr.getvalue().count("error:"), 1)
                    self.assertNotIn("Traceback", stderr.getvalue())
                    self.assertEqual(sorted(os.listdir(directory)), before)
                    if existing:
                        with open(out, "rb") as handle:
                            self.assertEqual(handle.read(), b"kept\n")
                    else:
                        self.assertFalse(os.path.exists(out))

    def test_empty_runs_exit_2_without_creating_or_clobbering_output(self):
        with _scratch() as directory:
            run = os.path.join(directory, "empty")
            os.makedirs(run)
            for document in ({}, {"resourceSpans": []},
                             {"resourceSpans": [{"scopeSpans": [{"spans": []}]}]}):
                with open(os.path.join(run, "settlement-traces.json"), "w", encoding="utf-8") as handle:
                    json.dump(document, handle)
                for left, right in ((run, os.path.join(RUNS, "order-b")),
                                    (os.path.join(RUNS, "order-b"), run)):
                    with self.subTest(document=document, side=left == run):
                        list(self._assert_error_keeps_output(
                            [left, right, "--cases", CASES], "empty run", directory))

    def test_outside_runs_and_symlinks_are_refused_before_reading(self):
        with _scratch() as directory:
            with tempfile.TemporaryDirectory() as outside:
                run = os.path.join(outside, "run")
                shutil.copytree(os.path.join(RUNS, "order-a"), run)
                link = os.path.join(directory, "escape")
                os.symlink(outside, link)
                paths = (run, os.path.relpath(run), os.path.join(link, "run"))
                for path in paths:
                    for left, right in ((path, os.path.join(RUNS, "order-b")),
                                        (os.path.join(RUNS, "order-b"), path)):
                        with self.subTest(path=paths.index(path), side=left == path):
                            args = [left, right, "--cases", CASES]
                            for done in self._assert_error_keeps_output(args, "outside working directory", directory):
                                self.assertNotIn(outside, done.stderr)
                                self.assertNotIn(os.path.relpath(outside), done.stderr)
                # Even invalid content is never parsed through an escaping link.
                with open(os.path.join(run, "settlement-traces.json"), "w", encoding="utf-8") as handle:
                    handle.write("not json")
                list(self._assert_error_keeps_output(
                    [os.path.join(link, "run"), os.path.join(RUNS, "order-b"), "--cases", CASES],
                    "outside working directory", directory))

    def test_inside_run_spellings_resolve_to_the_same_report(self):
        run = os.path.join(RUNS, "order-a")
        expected = _cli([run, os.path.join(RUNS, "order-b"), "--cases", CASES])
        with _scratch() as directory:
            link = os.path.join(directory, "inside")
            os.symlink(os.path.abspath(run), link)
            paths = ("./" + run + "/", os.path.join(RUNS, "..", "runs", "order-a"),
                     os.path.abspath(run), link)
            for path in paths:
                with self.subTest(spelling=paths.index(path)):
                    done = _cli([path, os.path.join(RUNS, "order-b"), "--cases", CASES])
                    self.assertEqual(done.returncode, 0, done.stderr)
                    self.assertEqual(done.stdout, expected.stdout)

    def test_duplicate_unreadable_missing_and_unknown_case_exit_2_and_write_nothing(self):
        with _scratch() as directory:
            cases = (
                ([os.path.join(RUNS, "dup"), os.path.join(RUNS, "order-a"), "--cases", CASES], "duplicate case_id F1"),
                ([os.path.join(RUNS, "unreadable"), os.path.join(RUNS, "order-a"), "--cases", CASES], "unreadable run_meta.json"),
                (["tests/fixtures/compare/runs/not-a-run", "traces/v1"], "missing run tests/fixtures/compare/runs/not-a-run"),
                ([os.path.join(RUNS, "unknown"), os.path.join(RUNS, "order-a"), "--cases", CASES], "NOPE"),
                (["traces/v1", "traces/aa-1", "--cases", "tests/fixtures/compare/no-such.json"], "no-such.json"),
            )
            for args, needle in cases:
                with self.subTest(needle=needle):
                    out = os.path.join(directory, "out.json")
                    done = _cli(args, out)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertEqual(done.stdout, "")
                    self.assertNotIn("Traceback", done.stderr)
                    self.assertIn(needle, done.stderr)
                    self.assertFalse(os.path.exists(out))
                    kept = os.path.join(directory, "kept.json")
                    with open(kept, "w", encoding="utf-8") as handle:
                        handle.write("kept\n")
                    again = _cli(args, kept)
                    self.assertEqual(again.returncode, 2, again.stderr)
                    with open(kept, encoding="utf-8") as handle:
                        self.assertEqual(handle.read(), "kept\n")

    def test_unreadable_traces_meta_and_cases_exit_2_and_write_nothing(self):
        traces = os.path.join(RUNS, "order-a", "settlement-traces.json")
        two_roots = (b'{"resourceSpans":[{"scopeSpans":[{"spans":['
                     b'{"traceId":"t","spanId":"a"},{"traceId":"t","spanId":"b"}]}]}]}')
        with _scratch() as directory:
            def run_with(name, body=None, meta=None):
                run = os.path.join(directory, name)
                os.makedirs(run)
                if body is None:
                    shutil.copy(traces, run)
                else:
                    with open(os.path.join(run, "settlement-traces.json"), "wb") as handle:
                        handle.write(body)
                if meta is not None:
                    with open(os.path.join(run, "run_meta.json"), "wb") as handle:
                        handle.write(meta)
                return run

            def cases_file(name, body):
                path = os.path.join(directory, name)
                with open(path, "wb") as handle:
                    handle.write(body)
                return path

            folder_run = run_with("traces-folder", body=b"")
            os.remove(os.path.join(folder_run, "settlement-traces.json"))
            os.makedirs(os.path.join(folder_run, "settlement-traces.json"))
            cases_folder = os.path.join(directory, "cases-folder")
            os.makedirs(cases_folder)
            good = os.path.join(RUNS, "order-b")
            unreadable_traces = "unreadable settlement-traces.json"
            unreadable_cases = "unreadable cases file"
            cases = (
                ([run_with("not-json", b"{not json"), good, "--cases", CASES], unreadable_traces),
                ([run_with("array", b"[]"), good, "--cases", CASES], unreadable_traces),
                ([run_with("bare-spans", b'{"resourceSpans":[{"scopeSpans":[{"spans":[1]}]}]}'), good,
                  "--cases", CASES], unreadable_traces),
                ([run_with("two-roots", two_roots), good, "--cases", CASES], unreadable_traces),
                ([run_with("not-utf8", b"\xff\xfe"), good, "--cases", CASES], unreadable_traces),
                ([folder_run, good, "--cases", CASES], unreadable_traces),
                ([CASES, good, "--cases", CASES], "missing run"),
                ([run_with("meta-not-utf8", meta=b"\xff\xfe"), good, "--cases", CASES], "unreadable run_meta.json"),
                ([os.path.join(RUNS, "order-a"), good, "--cases", cases_file("not-json.json", b"nope")],
                 unreadable_cases),
                ([os.path.join(RUNS, "order-a"), good, "--cases", cases_file("object.json", b'{"x":1}')],
                 unreadable_cases),
                ([os.path.join(RUNS, "order-a"), good, "--cases", cases_file("numbers.json", b"[1,2]")],
                 unreadable_cases),
                ([os.path.join(RUNS, "order-a"), good, "--cases", cases_file("no-id.json", b'[{"id":"F1"}]')],
                 unreadable_cases),
                ([os.path.join(RUNS, "order-a"), good, "--cases", cases_folder], unreadable_cases),
            )
            for args, needle in cases:
                with self.subTest(run=os.path.basename(args[0]), cases=os.path.basename(args[3])):
                    out = os.path.join(directory, "out.json")
                    done = _cli(args, out)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertEqual(done.stdout, "")
                    self.assertNotIn("Traceback", done.stderr)
                    self.assertEqual(done.stderr.count("error:"), 1, done.stderr)
                    self.assertIn(needle, done.stderr)
                    self.assertFalse(os.path.exists(out))

    def test_unwritable_json_path_exits_2_before_printing(self):
        with _scratch() as directory:
            blocker = os.path.join(directory, "blocker")
            with open(blocker, "w", encoding="utf-8") as handle:
                handle.write("kept\n")
            for out in (directory, os.path.join(blocker, "out.json")):
                with self.subTest(out=os.path.relpath(out, directory)):
                    done = _cli([os.path.join(RUNS, "order-a"), os.path.join(RUNS, "order-b"),
                                 "--cases", CASES], out)
                    self.assertEqual(done.returncode, 2, done.stderr)
                    self.assertEqual(done.stdout, "")
                    self.assertNotIn("Traceback", done.stderr)
                    self.assertEqual(done.stderr.count("error:"), 1, done.stderr)
                    self.assertIn("cannot write", done.stderr)
            self.assertEqual(sorted(os.listdir(directory)), ["blocker"])
            with open(blocker, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "kept\n")

    def test_json_array_meta_is_unreadable_and_stdout_matches_the_report(self):
        with _scratch() as directory:
            run = os.path.join(directory, "array-meta")
            shutil.copytree(os.path.join(RUNS, "order-a"), run)
            with open(os.path.join(run, "run_meta.json"), "w", encoding="utf-8") as handle:
                handle.write("[]\n")
            out = os.path.join(directory, "out.json")
            done = _cli([run, os.path.join(RUNS, "order-b"), "--cases", CASES], out)
            self.assertEqual(done.returncode, 2)
            self.assertNotIn("Traceback", done.stderr)
            self.assertFalse(os.path.exists(out))
            good = os.path.join(directory, "good.json")
            compared = _cli(
                [os.path.join(RUNS, "order-a"), os.path.join(RUNS, "null-b"), "--cases", CASES], good)
            self.assertEqual(compared.returncode, 0, compared.stderr)
            report = compare_runs(os.path.join(RUNS, "order-a"), os.path.join(RUNS, "null-b"), cases_path=CASES)
            self.assertEqual(compared.stdout, format_report(report))
            with open(good, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), canonical_json(report))


if __name__ == "__main__":
    unittest.main()
