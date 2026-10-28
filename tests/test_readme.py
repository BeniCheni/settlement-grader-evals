"""The README names the calibration as in sample and lists the scorer commands."""
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


if __name__ == "__main__":
    unittest.main()
