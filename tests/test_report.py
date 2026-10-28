"""The committed page is the regeneration. A stale file fails. Dynamic text is escaped."""
import os
import unittest

from scorer.calibrate import document, render_markdown
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
