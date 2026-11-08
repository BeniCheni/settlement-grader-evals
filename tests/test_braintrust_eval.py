"""The Braintrust uploader is source-checked only. The tests do not import it or run it."""
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BraintrustEvalSourceTests(unittest.TestCase):
    def test_the_refusals_precede_the_import_and_tests_do_not_name_it(self):
        path = os.path.join(ROOT, "uploaders", "braintrust_eval.py")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        needle = "import " + "braintrust"
        self.assertEqual(text.count(needle), 1)
        import_at = text.index(needle)
        # The pair is read through scorer.rag.load_pair, so every refusal
        # report applies comes before the package is imported.
        for marker in (
            "load_config(",
            "load_pair(",
            "except ReportError",
            "BRAINTRUST_" + "API_KEY",
        ):
            self.assertLess(text.index(marker), import_at)
        # The SDK records a raising scorer in the case's metadata and completes,
        # so the script checks for it before it prints an id.
        self.assertIn("scorer_errors", text)
        self.assertIn("results", text)
        self.assertIn("settlement-grader-rag", text)
        self.assertIn("experiment_name", text)
        self.assertIn("experiment_id", text)
        for name in ("context_recall", "context_precision", "faithfulness", "answer_relevancy"):
            self.assertIn(name, text)
        self.assertNotIn("grade_ticket", text)
        self.assertNotIn("ollama", text)
        for line in text.splitlines():
            if "stdout" in line or line.strip().startswith("print("):
                self.assertNotIn("API_KEY", line)
                self.assertNotIn("api_key", line)
            if line.startswith("import ") or line.startswith("from "):
                self.assertNotIn("brain" + "trust", line)
        key_name = "BRAINTRUST_" + "API_KEY"
        for folder in ("tests", "scorer"):
            base = os.path.join(ROOT, folder)
            for dirpath, _dirs, names in os.walk(base):
                for name in names:
                    if not name.endswith(".py"):
                        continue
                    with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                        body = handle.read()
                    self.assertNotIn(needle, body)
                    self.assertNotIn(key_name, body)
                    self.assertNotIn("uploaders." + "braintrust_eval", body)


if __name__ == "__main__":
    unittest.main()
