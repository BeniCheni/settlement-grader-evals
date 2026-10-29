"""The committed page is the regeneration. A stale file fails. Dynamic text is escaped."""
import os
import re
import unittest
from unittest import mock

import scorer.calibrate
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
            html.count('<span class="pill ok">85% and 0.6</span> <span class="mono">0 of 0</span>'),
            11,
        )
        self.assertNotIn("not 85% or 0.6", html)

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
        self.assertIn('<span class="pill alarm">not 85% or 0.6</span> <span class="mono">2 of 4</span>', html)
        self.assertNotIn('<span class="pill alarm">not 85% or 0.6 2 of 4</span>', html)
        self.assertEqual(html.count(">2 of 4<"), 1)

    def test_markdown_says_what_the_page_says(self):
        doc = document("traces/v1")
        md = render_markdown(doc)
        self.assertNotIn("meeting the bar", md)
        self.assertNotIn("| Bar |", md)
        self.assertNotIn("| met |", md)
        self.assertNotIn("trusted", md.lower())
        self.assertIn("Checks at 85% and 0.6: 11 of 11.", md)
        self.assertIn("| 85% and 0.6 | False passes read |", md)
        self.assertEqual(md.count("| yes | 0 of 0 |"), 11)
        doc["codes"][0]["meets_bar"] = False
        doc["codes"][0]["false_passes"] = {"READ": "x", "SPACE": "x", "BLANK": "x", "MISSING": "x"}
        doc["codes"][0]["readings"] = {"READ": "a reading", "SPACE": " ", "BLANK": ""}
        md = render_markdown(doc)
        self.assertIn("Checks at 85% and 0.6: 10 of 11.", md)
        self.assertEqual(md.count("| no | 2 of 4 |"), 1)
        self.assertEqual(md.count("| yes | 0 of 0 |"), 10)

    def test_tile_is_alarm_when_a_check_misses_the_numbers(self):
        doc = document("traces/v1")
        self.assertIn('<div class="stat good"><b>11</b><span>checks at 85% and 0.6</span></div>', render_html(doc, "x"))
        doc["codes"][0]["meets_bar"] = False
        self.assertIn('<div class="stat alarm"><b>10</b><span>checks at 85% and 0.6</span></div>', render_html(doc, "x"))

    def test_page_words_follow_the_bar_constants(self):
        self.assertEqual(bar_words(), "85% and 0.6")
        doc = document("traces/v1")
        with mock.patch.object(scorer.calibrate, "MIN_AGREEMENT", 0.9), mock.patch.object(scorer.calibrate, "MIN_KAPPA", 0.7):
            html = render_html(doc, "x")
            md = render_markdown(doc)
        self.assertIn("<span>checks at 90% and 0.7</span>", html)
        self.assertIn("<th>90% and 0.7</th>", html)
        self.assertEqual(html.count('<span class="pill ok">90% and 0.7</span>'), 11)
        self.assertNotIn("85% and 0.6", html)
        self.assertIn("| 90% and 0.7 | False passes read |", md)
        self.assertNotIn("85% and 0.6", md)

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
