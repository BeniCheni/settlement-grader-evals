"""The committed page is the regeneration. A stale file fails. Dynamic text is escaped."""
import os
from html import escape
import re
import unittest
from unittest import mock

import scorer.calibrate
import scorer.stats
from scorer.calibrate import bar_words, document, render_markdown
from scorer.report import render_html
from scorer.stats import canonical_json


class ReportTests(unittest.TestCase):
    def test_dynamic_text_is_escaped(self):
        doc = document("traces/v1")
        doc["model"] = "<script>alert(1)</script>"
        doc["run"] = "traces/<v1>"
        doc["codes"][0]["false_fails"] = {"ZZ": "evidence"}
        doc["codes"][0]["readings"] = {"ZZ": "<img src=x onerror=alert(1)>"}
        html = render_html(doc, "body{color:red}")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertIn("traces/&lt;v1&gt;", html)

    def test_every_dynamic_text_field_is_escaped_including_derived_words(self):
        doc = document("traces/v1")
        values = {name: name + "<tag>&\"'" for name in
                  ("model", "run", "run_label", "cases", "cases_path", "provenance", "code", "case_id", "reading", "bar", "not_bar", "read_count")}
        for field in ("model", "run", "run_label", "cases", "cases_path", "provenance"):
            doc[field] = values[field]
        row = doc["codes"][0]
        row["code"] = values["code"]
        row["false_passes"] = {values["case_id"]: "missed"}
        row["readings"] = {values["case_id"]: values["reading"]}
        doc["codes"][1]["meets_bar"] = False
        with mock.patch("scorer.report.bar_words", return_value=values["bar"]), mock.patch("scorer.report.not_bar_words", return_value=values["not_bar"]), mock.patch("scorer.report.false_passes_read", return_value=values["read_count"]):
            html = render_html(doc, "x")
        for field, value in values.items():
            with self.subTest(field=field):
                self.assertNotIn(value, html)
                self.assertIn(escape(value, quote=True), html)
        # Disagreement mapping insertion order must not affect note order.
        row["false_passes"] = {"Z": "z", "A": "a"}
        row["readings"] = {"Z": "last", "A": "first"}
        first = render_html(doc, "x")
        row["false_passes"] = {"A": "a", "Z": "z"}
        self.assertEqual(render_html(doc, "x"), first)
        markdown = render_markdown(doc)
        row["false_passes"] = {"Z": "z", "A": "a"}
        self.assertEqual(render_markdown(doc), markdown)

    def test_page_says_in_sample_and_names_the_command(self):
        doc = document("traces/v1")
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        html = render_html(doc, css)
        self.assertIn("in sample", html.lower())
        self.assertIn("not that they generalise", html)
        self.assertIn("Fonts load from Google Fonts.", html)
        self.assertIn("python3 -m scorer.report traces/v1", html)
        self.assertNotIn("/Users/", html)
        self.assertNotIn(os.path.expanduser("~"), html)
        self.assertIn("--slime:#56c083", html)

    def test_pill_and_tile_name_the_two_numbers(self):
        doc = document("traces/v1")
        html = render_html(doc, "x")
        self.assertIn("<span>checks at 85% and 0.6</span>", html)
        self.assertIn("Beside the pill, false passes read are n of n", html)
        self.assertNotIn("meeting the bar", html)
        self.assertNotIn("trusted", html.lower())
        self.assertNotIn(">met<", html)
        self.assertNotIn(">Bar<", html)
        self.assertIsNone(re.search(r'<span class="pill[^"]*">[^<]*\d+ of \d+', html))
        self.assertEqual(
            html.count('<span class="pill ok">85% and 0.6</span>'),
            11,
        )
        self.assertNotIn("not 85% or 0.6", html)
        self.assertNotIn("0 of 0", html)

    def test_false_passes_read_counts_non_empty_readings_beside_the_pill(self):
        doc = document("traces/v1")
        doc["codes"][0]["meets_bar"] = False
        doc["codes"][0]["false_passes"] = {
            "READ": "human label; the check did not flag",
            "SPACE": "human label; the check did not flag",
            "BLANK": "human label; the check did not flag",
            "MISSING": "human label; the check did not flag",
        }
        doc["codes"][0]["readings"] = {
            "READ": "a reading",
            "SPACE": " ",
            "BLANK": "",
            "OTHER": "not a false pass",
        }
        html = render_html(doc, "x")
        self.assertIn('<span class="pill alarm">not 85% or 0.6</span> <span class="mono">1 of 4</span>', html)
        self.assertNotIn('<span class="pill alarm">not 85% or 0.6 1 of 4</span>', html)
        self.assertEqual(html.count(">1 of 4<"), 1)

    def test_disagreement_badges_require_a_trimmed_reading(self):
        doc = document("traces/v1")
        for row in doc["codes"]:
            row["false_fails"] = {}
        row = doc["codes"][0]
        row["false_passes"] = {key: "x" for key in ("READ", "SPACE", "EMPTY", "MISSING")}
        row["readings"] = {"READ": " a reading ", "SPACE": " \t\n", "EMPTY": ""}
        html = render_html(doc, "x")
        self.assertEqual(html.count('<span class="pill read">read</span>'), 1)
        self.assertEqual(html.count('<span class="pill alarm">unread</span>'), 3)
        self.assertEqual(html.count("No reading recorded."), 3)
        self.assertEqual(render_markdown(doc).count("No reading recorded."), 3)

    def test_markdown_says_what_the_page_says(self):
        doc = document("traces/v1")
        md = render_markdown(doc)
        self.assertNotIn("meeting the bar", md)
        self.assertNotIn("| Bar |", md)
        self.assertNotIn("| met |", md)
        self.assertNotIn("trusted", md.lower())
        self.assertIn("Checks at 85% and 0.6: 11 of 11.", md)
        self.assertIn("| 85% and 0.6 | False passes read |", md)
        self.assertEqual(md.count("| yes |  |"), 11)
        doc["codes"][0]["meets_bar"] = False
        doc["codes"][0]["false_passes"] = {"READ": "x", "SPACE": "x", "BLANK": "x", "MISSING": "x"}
        doc["codes"][0]["readings"] = {"READ": "a reading", "SPACE": " ", "BLANK": ""}
        md = render_markdown(doc)
        self.assertIn("Checks at 85% and 0.6: 10 of 11.", md)
        self.assertEqual(md.count("| no | 1 of 4 |"), 1)
        self.assertEqual(md.count("| yes |  |"), 10)

    def test_tile_is_alarm_when_a_check_misses_the_numbers(self):
        doc = document("traces/v1")
        self.assertIn('<div class="stat good"><b>11</b><span>checks at 85% and 0.6</span></div>', render_html(doc, "x"))
        doc["codes"][0]["meets_bar"] = False
        self.assertIn('<div class="stat alarm"><b>10</b><span>checks at 85% and 0.6</span></div>', render_html(doc, "x"))

    def test_page_words_and_decisions_follow_non_default_bar_constants(self):
        self.assertEqual(bar_words(), "85% and 0.6")
        for agreement, kappa, words, meeting in ((0.855, 0.9, "85.5% and 0.9", 10), (0.9, 0.95, "90% and 0.95", 9)):
            with self.subTest(words=words), mock.patch.object(scorer.stats, "MIN_AGREEMENT", agreement), mock.patch.object(scorer.stats, "MIN_KAPPA", kappa):
                doc = document("traces/v1")
                self.assertEqual(sum(row["meets_bar"] for row in doc["codes"]), meeting)
                for row in doc["codes"]:
                    counts = {key: row[key] for key in ("tp", "fp", "fn", "tn")}
                    self.assertEqual(row["meets_bar"], scorer.stats.meets_bar(counts))
                html = render_html(doc, "x")
                md = render_markdown(doc)
                self.assertIn('<div class="stat alarm"><b>%s</b><span>checks at %s</span>' % (meeting, words), html)
                self.assertIn("<th>%s</th>" % words, html)
                self.assertEqual(html.count('<span class="pill ok">%s</span>' % words), meeting)
                self.assertIn("| %s | False passes read |" % words, md)
                self.assertEqual(sum("| yes |" in line for line in md.splitlines()), meeting)
                self.assertNotIn("85% and 0.6", html + md)

    def test_committed_reports_match_regeneration(self):
        doc = document("traces/v1")
        with open("ui/ledger.css", encoding="utf-8") as handle:
            css = handle.read()
        expected = {
            "reports/calibration-v1.html": render_html(doc, css),
            "reports/calibration-v1.json": canonical_json(doc),
            "reports/calibration-v1.md": render_markdown(doc),
        }
        for path, text in expected.items():
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text, path)
        again = document("traces/v1")
        self.assertEqual(render_html(again, css), expected["reports/calibration-v1.html"])


if __name__ == "__main__":
    unittest.main()
