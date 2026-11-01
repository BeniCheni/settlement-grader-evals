"""The judge comparison page. Agreement percents come from the integer counts."""
import json
import os
import shutil
import subprocess
import tempfile
import shlex
import unittest
from html import unescape
from html.parser import HTMLParser

from scorer.calibrate import has_reading
from scorer.judge import agreement_percent, build_report, render_comparison
from scorer.report import esc
from scorer.stats import confusion

from tests.test_judge import ROOT, ReportTests, cli, tempfile_dir, write_text


BANNED = ("held out", "held-out", "trusted", "generalise", "generalize")
_HELPER = ReportTests("test_committed_fixture_report_regenerates")


class AgreementPercentTests(unittest.TestCase):
    def test_one_decimal_from_the_counts(self):
        # Set 1's final and first-pass agreements, as the report prints them.
        self.assertEqual(agreement_percent(32, 40), "80.0%")
        self.assertEqual(agreement_percent(37, 40), "92.5%")
        self.assertEqual(agreement_percent(23, 40), "57.5%")
        self.assertEqual(agreement_percent(26, 40), "65.0%")
        self.assertEqual(agreement_percent(1, 1), "100.0%")
        self.assertEqual(agreement_percent(0, 1), "0.0%")
        self.assertEqual(agreement_percent(0, 0), "none")

    def test_an_exact_half_rounds_away_from_zero(self):
        # 1/16 is 6.25%, halfway between 6.2% and 6.3%. Half away from zero is 6.3%.
        # 5/16 is 31.25%, halfway between 31.2% and 31.3%, and prints 31.3%.
        self.assertEqual(agreement_percent(1, 16), "6.3%")
        self.assertEqual(agreement_percent(5, 16), "31.3%")
        self.assertEqual((1 * 1000) % 16, 8)
        self.assertEqual(16 // 2, 8)


def _agree(verdict, human):
    return (verdict == "PASS") == (human == "PASS")


def _jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _verdicts(directory):
    found = {}
    for row in _jsonl(os.path.join(directory, "verdicts.jsonl")):
        found[(row["run"], row["case_id"], row["rubric"])] = row
    return found


def _readings(path):
    if path is None:
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _expected(labels, final, readings, verdicts):
    """What the page must show, counted from the inputs rather than the renderer."""
    rows = _jsonl(labels)
    names = sorted(rows[0]["human"].keys())
    final_rows = _jsonl(final) if final else None
    verdict_rows = _verdicts(verdicts)
    reading_map = _readings(readings)
    rubrics = []
    for name in names:
        bucket = reading_map.get(name) or {}
        page_rows = []
        changed = 0 if final_rows is not None else None
        first_pairs = []
        final_pairs = []
        for index, row in enumerate(rows):
            verdict = verdict_rows[(row["run"], row["case_id"], name)]
            first = row["human"][name]
            final_label = None
            change_reason = None
            if final_rows is not None:
                final_label = final_rows[index]["human"][name]
                if final_label != first:
                    changed += 1
                    for change in final_rows[index]["changes"]:
                        if change["rubric"] == name:
                            change_reason = change["reason"]
            cover = final_label if final_label is not None else first
            show = (not _agree(verdict["verdict"], first)) or (
                final_label is not None and not _agree(verdict["verdict"], final_label)
            )
            text = bucket.get("%s|%s" % (row["run"], row["case_id"]))
            page_rows.append({
                "agree": _agree(verdict["verdict"], cover),
                "case_id": row["case_id"],
                "change": change_reason,
                "reading": text if show and has_reading(text) else None,
                "run": row["run"],
                "show": show,
                "unread": show and not has_reading(text),
                "verdict": verdict["verdict"],
            })
            first_pairs.append((verdict["verdict"], first))
            if final_label is not None:
                final_pairs.append((verdict["verdict"], final_label))
        rubrics.append({
            "changed": changed,
            "final": _confusion(final_pairs) if final_pairs else None,
            "first": _confusion(first_pairs),
            "name": name,
            "rows": page_rows,
        })
    return rubrics


def _confusion(pairs):
    predicted = [verdict != "PASS" for verdict, _human in pairs]
    truth = [human == "FAIL" for _verdict, human in pairs]
    counts = confusion(predicted, truth)
    return {"JP_HF": counts["fn"], "JF_HP": counts["fp"], "JP_HP": counts["tn"], "JF_HF": counts["tp"], "n": len(pairs)}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.sections = []
        self._sec = None
        self._matrix = None
        self._targets = []

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = attr.get("class", "").split()
        if tag == "section" and "rubric" in classes:
            self._sec = {"name": attr.get("data-rubric"), "rows": [], "matrices": [], "sides": {}, "changed": []}
            self.sections.append(self._sec)
        elif tag == "table" and "matrix" in classes and self._sec is not None:
            self._matrix = []
            self._sec["matrices"].append(self._matrix)
        elif tag == "tr" and "row" in classes and self._sec is not None:
            self._sec["rows"].append({
                "badges": [],
                "case": attr.get("data-case"),
                "change": None,
                "mark": attr.get("data-mark"),
                "reading": None,
                "run": attr.get("data-run"),
            })
        elif tag == "article" and "side" in classes:
            self._targets.append((tag, "side:" + attr.get("data-labels", ""), []))
        elif tag == "td" and self._matrix is not None:
            self._targets.append((tag, "cell", []))
        elif tag == "p" and "rubric-statement" in classes:
            self._targets.append((tag, "statement", []))
        elif tag == "p" and "changed" in classes:
            self._targets.append((tag, "changed", []))
        elif tag == "p" and "reading" in classes and self._sec and self._sec["rows"]:
            self._targets.append((tag, "reading", []))
        elif tag == "span" and "change" in classes and self._sec and self._sec["rows"]:
            self._targets.append((tag, "change", []))
        elif tag == "span" and "pill" in classes and self._sec and self._sec["rows"]:
            self._targets.append((tag, "pill", []))

    def handle_endtag(self, tag):
        if self._targets and self._targets[-1][0] == tag:
            _tag, kind, buf = self._targets.pop()
            text = "".join(buf)
            if kind.startswith("side:") and self._sec is not None:
                self._sec["sides"][kind.split(":", 1)[1]] = text
            elif kind == "cell" and self._matrix is not None:
                self._matrix.append(text)
            elif kind == "statement" and self._sec is not None:
                self._sec["statement"] = text
            elif kind == "changed" and self._sec is not None:
                self._sec["changed"].append(text)
            elif kind == "reading":
                self._sec["rows"][-1]["reading"] = text
            elif kind == "change":
                self._sec["rows"][-1]["change"] = text
            elif kind == "pill":
                self._sec["rows"][-1]["badges"].append(text.strip())
        if tag == "table":
            self._matrix = None

    def handle_data(self, data):
        if self._targets:
            self._targets[-1][2].append(data)


def _parse(html):
    parser = _Page()
    parser.feed(html)
    return parser.sections


def _strip_inputs(html, strings):
    cleaned = html
    for text in sorted((esc(value) for value in strings if isinstance(value, str) and value), key=len, reverse=True):
        cleaned = cleaned.replace(text, "")
    return cleaned


def _banned_left(html, strings):
    left = _strip_inputs(html, strings).lower()
    return [word for word in BANNED if word in left]


def _input_strings(labels, final, readings, provenance, verdicts, rubric_provenance, extra=()):
    strings = [open(provenance, encoding="utf-8").read()]
    with open(rubric_provenance, encoding="utf-8") as handle:
        statements = json.load(handle)
    strings.extend(statements.values())
    if readings:
        for bucket in _readings(readings).values():
            if isinstance(bucket, dict):
                strings.extend(text for text in bucket.values() if isinstance(text, str))
    for row in _jsonl(os.path.join(verdicts, "verdicts.jsonl")):
        strings.append(row["reason"])
    if final:
        for row in _jsonl(final):
            for change in row["changes"]:
                strings.append(change["reason"])
    strings.extend([labels, final or "", readings or "", provenance, verdicts, rubric_provenance])
    strings.extend(extra)
    return strings


def _cell_count(text):
    return int(text.split()[0])


def _check_page(test, html, labels, final, readings, verdicts, statements):
    expected = _expected(labels, final, readings, verdicts)
    sections = _parse(html)
    test.assertEqual([item["name"] for item in sections], [item["name"] for item in expected])
    for section, want in zip(sections, expected):
        test.assertEqual(section.get("statement"), statements[want["name"]])
        test.assertEqual(html.count(esc(statements[want["name"]])), 1)
        test.assertEqual(len(section["rows"]), len(want["rows"]))
        for got, row in zip(section["rows"], want["rows"]):
            test.assertEqual(got["run"], row["run"])
            test.assertEqual(got["case"], row["case_id"])
            test.assertEqual(got["mark"], "agree" if row["agree"] else "disagree")
            if row["show"]:
                if row["unread"]:
                    test.assertIn("unread", got["badges"])
                    test.assertNotIn("read", got["badges"])
                    test.assertIsNone(got["reading"])
                else:
                    test.assertEqual(got["badges"], ["read"])
                    test.assertEqual(got["reading"], row["reading"])
            else:
                test.assertEqual(got["badges"], [])
                test.assertIsNone(got["reading"])
            test.assertEqual(got["change"], row["change"])
        matrices = [want["first"]]
        if want["final"] is not None:
            matrices.append(want["final"])
            test.assertEqual(len(section["changed"]), 1)
            test.assertIn(str(want["changed"]), section["changed"][0])
        else:
            test.assertEqual(section["changed"], [])
        test.assertEqual(len(section["matrices"]), len(matrices))
        for matrix, counts in zip(section["matrices"], matrices):
            test.assertEqual(len(matrix), 4)
            test.assertEqual(_cell_count(matrix[0]), counts["JP_HP"])
            test.assertIn("JP_HP", matrix[0])
            test.assertIn("tn", matrix[0])
            test.assertEqual(_cell_count(matrix[1]), counts["JP_HF"])
            test.assertIn("JP_HF", matrix[1])
            test.assertIn("fn", matrix[1])
            test.assertIn("a false pass: the judge passed a real failure", matrix[1])
            test.assertNotIn("a false fail", matrix[1])
            test.assertEqual(_cell_count(matrix[2]), counts["JF_HP"])
            test.assertIn("JF_HP", matrix[2])
            test.assertIn("fp", matrix[2])
            test.assertIn("a false fail: the judge failed a row the human passed", matrix[2])
            test.assertNotIn("a false pass", matrix[2])
            test.assertEqual(_cell_count(matrix[3]), counts["JF_HF"])
            test.assertIn("JF_HF", matrix[3])
            agree_count = counts["JP_HP"] + counts["JF_HF"]
            side_key = "first-pass" if counts is want["first"] else "final"
            test.assertIn(agreement_percent(agree_count, counts["n"]), section["sides"][side_key])
    test.assertNotIn("<script", html.lower())
    test.assertNotIn("0 of 0", html)


class PageTests(unittest.TestCase):
    def test_markup_is_escaped_and_rows_follow_the_inputs(self):
        reason = 'because <b>&"quoted"'
        reading = "read <script>alert(1)</script>"
        change = "changed <i>reason</i>"
        provenance = "Hand <em>written</em>. Held Out, held-out, trusted, generalise."
        statement = 'Statement <img src=x> for alpha. Do not generalize.'
        hidden = "HIDDEN-READING-TOKEN"
        sha = "a" * 64
        with tempfile_dir() as directory:
            marked = os.path.join(directory, "mark<up>")
            os.makedirs(marked)
            final = {
                "case_id": "A1",
                "changes": [{"from": "FAIL", "reason": change, "rubric": "alpha", "to": "PASS"}],
                "human": {"alpha": "PASS"},
                "note": "",
                "run": "fixture/run",
                "trace_id": "t",
                "unsure": [],
            }
            rows = [
                _HELPER.row("A1", {"alpha": "FAIL"}),
                _HELPER.row("A2", {"alpha": "PASS"}),
                _HELPER.row("A3", {"alpha": "PASS"}),
                _HELPER.row("A4", {"alpha": "PASS"}),
            ]
            verdicts = [
                _HELPER.verdict("A1", "alpha", "PASS", reason, sha),
                _HELPER.verdict("A2", "alpha", "PASS", "plain", sha),
                _HELPER.verdict("A3", "alpha", "FAIL", "missed", sha),
                _HELPER.verdict("A4", "alpha", "UNPARSED", "no reply", sha),
            ]
            readings = {"alpha": {"fixture/run|A1": reading, "fixture/run|A2": hidden, "fixture/run|A4": "   "}}
            labels, final_path, readings_path, provenance_path, verdict_dir = _HELPER.world(
                marked, rows, verdicts, {"alpha": sha}, {"alpha": sha}, provenance,
                readings=readings, final=[final, dict(rows[1], changes=[]), dict(rows[2], changes=[]), dict(rows[3], changes=[])],
            )
            # world() writes the final rows I pass only when final= is the list. The first row needs the change.
            rubric_path = os.path.join(marked, "rubric.json")
            write_text(rubric_path, json.dumps({"alpha": statement}))
            out = os.path.join(directory, "not-comparison.html")
            made = cli([
                "report", "--labels", labels, "--final", final_path, "--readings", readings_path,
                "--provenance", provenance_path, "--verdicts", verdict_dir,
                "--md", os.path.join(directory, "out.md"), "--json", os.path.join(directory, "out.json"),
                "--html", out, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            html = open(out, encoding="utf-8").read()
            self.assertNotIn("not-comparison.html", html)
            self.assertIn("--html comparison.html", html)
            self.assertNotIn(reason, html)
            self.assertIn(esc(reason), html)
            self.assertNotIn("<script", html.lower())
            self.assertIn(esc(reading), html)
            self.assertNotIn(change, html)
            self.assertIn(esc(change), html)
            self.assertNotIn(provenance, html)
            self.assertIn(esc(provenance), html)
            self.assertNotIn("<img", html.lower())
            self.assertIn(esc(statement), html)
            self.assertNotIn("mark<up>", html)
            self.assertIn("mark&lt;up&gt;", html)
            self.assertNotIn(hidden, html)
            _check_page(self, html, labels, final_path, readings_path, verdict_dir, {"alpha": statement})
            self.assertIn("These tiles count the final labels.", html)
            self.assertEqual(_banned_left(html, _input_strings(
                labels, final_path, readings_path, provenance_path, verdict_dir, rubric_path,
            )), [])
            plain = os.path.join(directory, "first.html")
            made = cli([
                "report", "--labels", labels, "--readings", readings_path, "--provenance", provenance_path,
                "--verdicts", verdict_dir, "--html", plain, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            first_html = open(plain, encoding="utf-8").read()
            self.assertIn("These tiles count the first-pass labels.", first_html)
            self.assertNotIn("Labels the owner changed:", first_html)
            self.assertNotIn('data-label="Final"', first_html)
            _check_page(self, first_html, labels, None, readings_path, verdict_dir, {"alpha": statement})

    def test_committed_page_rows_statements_and_banned_words(self):
        labels = "labels/set1.jsonl"
        final = "labels/set1-final.jsonl"
        readings = "labels/set1-readings.json"
        provenance = "labels/set1-provenance.txt"
        verdicts = "judgments/set1-llama3.1-8b"
        rubric_path = "labels/set1-rubric-provenance.json"
        html = open("reports/judge-set1.html", encoding="utf-8").read()
        with open(rubric_path, encoding="utf-8") as handle:
            statements = json.load(handle)
        _check_page(self, html, labels, final, readings, verdicts, statements)
        self.assertEqual(_banned_left(html, _input_strings(
            labels, final, readings, provenance, verdicts, rubric_path,
        )), [])
        _markdown, document = build_report(labels, final, readings, provenance, verdicts)
        self.assertIn(document["command"], html)
        for rubric in document["rubrics"]:
            side = rubric["final"]
            percent = agreement_percent(side["JP_HP"] + side["JF_HF"], side["JP_HP"] + side["JP_HF"] + side["JF_HP"] + side["JF_HF"])
            four = "none" if side["agreement"] is None else "%.4f" % side["agreement"]
            self.assertIn("%s (%s)" % (percent, four), html)
        self.assertIn("These tiles count the final labels.", html)
        self.assertIn("Worst judge on the final labels: rule_adherence.", html)
        self.assertNotIn(">trusted<", html.lower())

    def test_fixture_page_and_export_match_report(self):
        rubric_path = ROOT + "/rubric-provenance.json"
        with open(rubric_path, encoding="utf-8") as handle:
            statements = json.load(handle)
        with tempfile_dir() as directory:
            page = os.path.join(directory, "page.html")
            made = cli([
                "report", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--html", page, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            html = open(page, encoding="utf-8").read()
            _check_page(
                self, html, ROOT + "/labels.jsonl", ROOT + "/labels-final.jsonl",
                ROOT + "/readings.json", ROOT + "/verdicts", statements,
            )
            self.assertIn("none · none", html)
            out = os.path.join(directory, "course")
            exported = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", out,
                "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertIn("files 4\n", exported.stdout)
            self.assertEqual(open(os.path.join(out, "comparison.html"), "rb").read(), open(page, "rb").read())
            bare = os.path.join(directory, "bare")
            bare_run = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--final", ROOT + "/labels-final.jsonl",
                "--readings", ROOT + "/readings.json", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", bare,
            ])
            self.assertEqual(bare_run.returncode, 0, bare_run.stderr)
            self.assertEqual(set(os.listdir(bare)), {"labels.jsonl", "results.md", "rubrics.md"})
            self.assertIn("files 3\n", bare_run.stdout)
            for name in ("labels.jsonl", "results.md", "rubrics.md"):
                self.assertEqual(open(os.path.join(out, name), "rb").read(), open(os.path.join(bare, name), "rb").read())
            first_page = os.path.join(directory, "first.html")
            first_out = os.path.join(directory, "course-first")
            made = cli([
                "report", "--labels", ROOT + "/labels.jsonl", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--html", first_page, "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            exported = cli([
                "export-course", "--labels", ROOT + "/labels.jsonl", "--provenance", ROOT + "/provenance.txt",
                "--verdicts", ROOT + "/verdicts", "--rubrics", ROOT + "/rubrics", "--out", first_out,
                "--rubric-provenance", rubric_path,
            ])
            self.assertEqual(exported.returncode, 0, exported.stderr)
            self.assertEqual(
                open(os.path.join(first_out, "comparison.html"), "rb").read(),
                open(first_page, "rb").read(),
            )
            self.assertIn("These tiles count the first-pass labels.", open(first_page, encoding="utf-8").read())

    def test_colophon_command_reproduces_the_committed_page(self):
        html = open("reports/judge-set1.html", encoding="utf-8").read()
        start = html.find('<code class="mono">')
        end = html.find("</code>", start)
        command = unescape(html[start + len('<code class="mono">'):end])
        self.assertTrue(command.endswith("--html comparison.html"))
        self.assertNotIn("reports/judge-set1.html", command)
        with tempfile.TemporaryDirectory() as scratch:
            copy = os.path.join(scratch, "repo")
            shutil.copytree(".", copy, ignore=shutil.ignore_patterns(".git", "__pycache__", "_tmp*"))
            done = subprocess.run(shlex.split(command), cwd=copy, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(os.path.join(copy, "comparison.html"), "rb") as handle:
                got = handle.read()
            with open("reports/judge-set1.html", "rb") as handle:
                self.assertEqual(got, handle.read())

    def test_refusals_write_nothing(self):
        sha = "b" * 64
        with tempfile_dir() as directory:
            labels, _final, readings, provenance, verdict_dir = _HELPER.world(
                directory, [_HELPER.row("A1", {"alpha": "PASS"})],
                [_HELPER.verdict("A1", "alpha", "PASS", "because", sha)],
                {"alpha": sha}, {"alpha": sha}, "Hand written.\n",
            )
            good = os.path.join(directory, "rubric.json")
            write_text(good, json.dumps({"alpha": "A statement."}))
            out = os.path.join(directory, "page.html")
            md = os.path.join(directory, "out.md")
            js = os.path.join(directory, "out.json")
            base = [
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ]

            def refuse(args, fragment):
                write_text(out, "OLD-HTML")
                write_text(md, "OLD-MD")
                write_text(js, "OLD-JSON")
                refused = cli(args)
                self.assertEqual(refused.returncode, 2, refused.stderr)
                self.assertNotIn("Traceback", refused.stderr)
                self.assertEqual(refused.stderr.count("error:"), 1)
                self.assertIn(fragment, refused.stderr)
                self.assertEqual(open(out, encoding="utf-8").read(), "OLD-HTML")
                self.assertEqual(open(md, encoding="utf-8").read(), "OLD-MD")
                self.assertEqual(open(js, encoding="utf-8").read(), "OLD-JSON")

            refuse(base[:-2], "must be given together")
            refuse(base[:-4] + ["--rubric-provenance", good], "must be given together")
            missing = os.path.join(directory, "missing.txt")
            refuse(base[:4] + [missing] + base[5:], "missing or unreadable")
            empty = os.path.join(directory, "empty.txt")
            write_text(empty, " \n")
            refuse(base[:4] + [empty] + base[5:], "empty")
            bad_labels = os.path.join(directory, "bad.jsonl")
            write_text(bad_labels, "{")
            refuse(["report", "--labels", bad_labels, "--provenance", provenance, "--verdicts", verdict_dir,
                    "--md", md, "--json", js, "--html", out, "--rubric-provenance", good], "not valid JSON")
            refuse(["report", "--labels", os.path.abspath(labels), "--provenance", provenance, "--verdicts", verdict_dir,
                    "--md", md, "--json", js, "--html", out, "--rubric-provenance", good], "relative path")
            refuse(base[:6] + ["../" + "verdicts"] + base[7:], "relative path")
            empty_labels = os.path.join(directory, "empty-human.jsonl")
            write_text(empty_labels, json.dumps({
                "case_id": "A1", "human": {}, "note": "", "run": "fixture/run", "trace_id": "t", "unsure": [],
            }) + "\n")
            refuse([
                "report", "--labels", empty_labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ], "no rubric")
            refuse(base[:4] + ["~" + "/provenance.txt"] + base[5:], "relative path")
            bad_readings = os.path.join(directory, "bad-readings.json")
            write_text(bad_readings, "[1]")
            refuse([
                "report", "--labels", labels, "--readings", bad_readings, "--provenance", provenance,
                "--verdicts", verdict_dir, "--md", md, "--json", js, "--html", out, "--rubric-provenance", good,
            ], "not an object")
            absent = os.path.join(directory, "no-rubric.json")
            refuse(base[:-1] + [absent], "missing or unreadable")
            write_text(os.path.join(directory, "array.json"), "[1]")
            refuse(base[:-1] + [os.path.join(directory, "array.json")], "not an object")
            write_text(os.path.join(directory, "empty-object.json"), "{}")
            refuse(base[:-1] + [os.path.join(directory, "empty-object.json")], "lacks a rubric")
            write_text(os.path.join(directory, "extra.json"), json.dumps({"alpha": "Yes.", "beta": "No."}))
            refuse(base[:-1] + [os.path.join(directory, "extra.json")], "names a rubric the labels do not have")
            write_text(os.path.join(directory, "blank.json"), json.dumps({"alpha": "  "}))
            refuse(base[:-1] + [os.path.join(directory, "blank.json")], "empty")
            write_text(os.path.join(directory, "number.json"), json.dumps({"alpha": 1}))
            refuse(base[:-1] + [os.path.join(directory, "number.json")], "not text")
            refuse(base[:-1] + [os.path.abspath(good)], "relative path")
            refuse(base[:-2] + ["--html", md, "--rubric-provenance", good], "distinct")
            refuse(base[:-2] + ["--html", js, "--rubric-provenance", good], "distinct")
            blocked = os.path.join(directory, "blocked")
            os.mkdir(blocked)
            fresh_md = os.path.join(directory, "fresh.md")
            fresh_js = os.path.join(directory, "fresh.json")
            refused = cli([
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", fresh_md, "--json", fresh_js, "--html", blocked, "--rubric-provenance", good,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertIn("could not write output", refused.stderr)
            self.assertFalse(os.path.exists(fresh_md))
            self.assertFalse(os.path.exists(fresh_js))
            self.assertTrue(os.path.isdir(blocked))
            write_text(md, "OLD-MD")
            write_text(js, "OLD-JSON")
            refused = cli([
                "report", "--labels", labels, "--provenance", provenance, "--verdicts", verdict_dir,
                "--md", md, "--json", js, "--html", blocked, "--rubric-provenance", good,
            ])
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertEqual(open(md, encoding="utf-8").read(), "OLD-MD")
            self.assertEqual(open(js, encoding="utf-8").read(), "OLD-JSON")

    def test_set1_export_fourth_file_matches_the_page(self):
        with tempfile_dir() as directory:
            out = os.path.join(directory, "course")
            made = cli([
                "export-course", "--labels", "labels/set1.jsonl", "--final", "labels/set1-final.jsonl",
                "--readings", "labels/set1-readings.json", "--provenance", "labels/set1-provenance.txt",
                "--verdicts", "judgments/set1-llama3.1-8b", "--rubrics", "rubrics", "--out", out,
                "--rubric-provenance", "labels/set1-rubric-provenance.json",
            ])
            self.assertEqual(made.returncode, 0, made.stderr)
            with open(os.path.join(out, "comparison.html"), "rb") as handle:
                got = handle.read()
            with open("reports/judge-set1.html", "rb") as handle:
                self.assertEqual(got, handle.read())
