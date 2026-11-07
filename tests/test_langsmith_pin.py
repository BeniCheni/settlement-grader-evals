"""The pin script is source-checked only. The tests do not import it or run it."""
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class LangSmithPinSourceTests(unittest.TestCase):
    def test_the_hash_check_precedes_the_import_and_tests_do_not_name_it(self):
        path = os.path.join(ROOT, "uploaders", "langsmith_pin.py")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        needle = "import " + "langsmith"
        self.assertLess(text.index("v1_hash_matches"), text.index(needle))
        for line in text.splitlines():
            if line.startswith("import ") or line.startswith("from "):
                self.assertNotIn("lang" + "smith", line)
        key_name = "LANGSMITH_" + "API_KEY"
        self.assertNotIn(key_name, text)
        tests = os.path.join(ROOT, "tests")
        for dirpath, _dirs, names in os.walk(tests):
            for name in names:
                if not name.endswith(".py"):
                    continue
                with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                    body = handle.read()
                self.assertNotIn(needle, body)
                self.assertNotIn(key_name, body)
                self.assertNotIn("uploaders." + "langsmith_pin", body)


if __name__ == "__main__":
    unittest.main()
