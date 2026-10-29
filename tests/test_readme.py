"""The README names the calibration as in sample and lists the scorer commands."""
import os
import subprocess
import sys
import tempfile
import unittest


class ReadmeTests(unittest.TestCase):
    def test_where_we_are_says_in_sample_and_try_it_lists_the_commands(self):
        with open("README.md", encoding="utf-8") as handle:
            text = handle.read()
        where_at = text.index("## 📍 Where we are")
        where = text[where_at:text.index("## ", where_at + 5)]
        self.assertIn("in sample", where.lower())
        try_at = text.index("## 🥅 Try it")
        commands = text[try_at:text.index("## ", try_at + 5)]
        self.assertIn("python3 -m scorer.calibrate traces/v1", commands)
        self.assertIn("python3 -m scorer.score traces/v1", commands)
        self.assertIn(
            "python3 -m scorer.report traces/v1 --out reports/calibration-v1.html --json reports/calibration-v1.json",
            commands,
        )

    def test_the_three_commands_run_from_the_repo_root(self):
        for command, first_line in (
            ("python3 -m scorer.calibrate traces/v1", "# Calibration of the plain-code checks"),
            ("python3 -m scorer.score traces/v1", "GRADE_CONTRADICTS_FACTS 14"),
        ):
            done = subprocess.run([sys.executable] + command.split()[1:], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, command)
            self.assertEqual(done.stdout.splitlines()[0], first_line, command)
        out = tempfile.mkdtemp()
        done = subprocess.run(
            [sys.executable, "-m", "scorer.report", "traces/v1", "--out", os.path.join(out, "calibration-v1.html"),
             "--json", os.path.join(out, "calibration-v1.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        for name in ("calibration-v1.html", "calibration-v1.json"):
            with open(os.path.join("reports", name), encoding="utf-8") as handle:
                committed = handle.read()
            with open(os.path.join(out, name), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), committed, name)


if __name__ == "__main__":
    unittest.main()
