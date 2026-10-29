"""The provenance sentences name the sample and do not name a count of fixes."""
import os
import unittest

from scorer.calibrate import provenance_for
from scorer.traces import load_run


# Literals, not the module's constants: a drift on either side fails this file.
EXACT = (
    (
        "traces/v1",
        True,
        "In sample. The labels were made on these 32 traces and the checks were built against them. "
        "This shows the checks reproduce the labels they were built from, not that they generalise.",
    ),
    (
        "traces/v1-adv",
        True,
        "In sample. This is a subset of traces/v1, the run the checks were built against. "
        "It is not independent evidence that they generalise.",
    ),
    (
        "traces/smoke-1",
        None,
        "Run-specific calibration is not established. "
        "The labels in data/codes_v1.json were made on traces/v1, not on this run. "
        "The supplied labels have not been established as labels for this run; "
        "these numbers do not establish held-out agreement or generalisation.",
    ),
)

PHRASES = (
    "fixed while reading",
    "checks were fixed",
    "were tuned on",
    "tuned on traces",
)


def guarded_paths():
    """scorer/*.py, files directly in reports/, and the slice-1 oracle. Not this file."""
    paths = []
    for name in sorted(os.listdir("scorer")):
        if name.endswith(".py"):
            paths.append(os.path.join("scorer", name))
    for name in sorted(os.listdir("reports")):
        path = os.path.join("reports", name)
        if os.path.isfile(path):
            paths.append(path)
    paths.append(os.path.join("data", "oracle_slice1.json"))
    return paths


class ProvenanceWordsTests(unittest.TestCase):
    def test_the_three_sentences_are_pinned(self):
        for run, in_sample, sentence in EXACT:
            with self.subTest(run=run):
                self.assertEqual(provenance_for(load_run(run)), (in_sample, sentence))

    def test_retired_phrases_are_absent(self):
        paths = guarded_paths()
        self.assertNotIn(os.path.abspath(__file__), [os.path.abspath(path) for path in paths])
        hits = []
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                text = handle.read().lower()
            for phrase in PHRASES:
                if phrase in text:
                    hits.append("%s: %s" % (path, phrase))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
