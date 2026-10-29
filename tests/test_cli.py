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


if __name__ == "__main__":
    unittest.main()
