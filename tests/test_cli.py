"""All three entry points share the cases-file default and clean usage errors."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CasesCommandTests(unittest.TestCase):
    def test_cases_default_override_and_errors_on_all_three_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            for module in ("calibrate", "score", "report"):
                for run, options, expected_cases in (
                    ("traces/v1", [], 32),
                    ("traces/smoke-1", ["--cases", "data/smoke.json"], 3),
                    ("traces/smoke-1", [], None),
                    ("traces/v1", ["--cases", "missing-cases.json"], None),
                ):
                    with self.subTest(module=module, run=run, options=options):
                        output = Path(directory) / "out.json"
                        command = [sys.executable, "-m", "scorer." + module, run, *options, "--json", str(output)]
                        if module == "report":
                            command += ["--out", str(Path(directory) / "out.html")]
                        output.unlink(missing_ok=True)
                        done = subprocess.run(command, capture_output=True, text=True)
                        if expected_cases is None:
                            self.assertEqual(done.returncode, 2)
                            self.assertNotIn("Traceback", done.stderr)
                            self.assertEqual(done.stdout, "")
                            self.assertFalse(output.exists())
                            if options:
                                self.assertIn("missing-cases.json", done.stderr)
                            else:
                                self.assertIn("case SMOKE1 is not in data/gold.json", done.stderr)
                                self.assertIn("--cases", done.stderr)
                        else:
                            self.assertEqual(done.returncode, 0, done.stderr)
                            data = json.loads(output.read_text())
                            self.assertEqual(len(data["tickets"]) if module == "score" else data["cases"], expected_cases)

    def test_smoke_outputs_do_not_claim_the_v1_calibration_and_keep_the_cases_command(self):
        from scorer.calibrate import document, render_markdown
        from scorer.report import render_html
        from scorer.score import score_run
        doc = document("traces/smoke-1", cases_path="data/smoke.json")
        scored = score_run("traces/smoke-1", cases_path="data/smoke.json")
        for output in (doc, scored):
            self.assertIsNone(output["in_sample"])
            self.assertIn("not established", output["provenance"])
            self.assertNotIn("these 32 traces", output["provenance"])

    def test_alternate_cases_file_is_retained_in_report_commands(self):
        from scorer.calibrate import document, render_markdown
        from scorer.report import render_html
        from scorer.score import score_run
        doc = document("traces/smoke-1", cases_path="data/smoke.json")
        scored = score_run("traces/smoke-1", cases_path="data/smoke.json")
        for name, output in (("document", doc), ("score", scored)):
            with self.subTest(name=name):
                self.assertEqual(output.get("cases_path"), "data/smoke.json")
        for name, text in (("markdown", render_markdown(doc)), ("html", render_html(doc, "x"))):
            with self.subTest(name=name):
                self.assertIn("--cases data/smoke.json", text)

    def test_v1_subsets_are_named_as_in_sample_subsets(self):
        from scorer.calibrate import document
        subset = document("traces/v1-adv")
        self.assertTrue(subset["in_sample"])
        self.assertIn("subset", subset["provenance"])


if __name__ == "__main__":
    unittest.main()
