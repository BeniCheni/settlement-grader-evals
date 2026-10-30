"""Hand-worked confusion tables. Mutate a count and the matching assertion goes red."""
import unittest
from fractions import Fraction
from unittest import mock

from scorer import stats

from scorer.stats import (
    MIN_AGREEMENT,
    MIN_KAPPA,
    agreement,
    cohen_kappa,
    confusion,
    false_pass_rate,
    meets_bar,
    wilson,
)


class ConfusionTests(unittest.TestCase):
    def test_exact_kappa_bar_and_nearby_tables(self):
        boundary = {"tp": 9, "fp": 6, "fn": 1, "tn": 24}
        self.assertEqual(cohen_kappa(boundary), 0.6)
        self.assertTrue(meets_bar(boundary, min_agreement=0.8))
        self.assertFalse(meets_bar(boundary))  # Agreement is 33/40, below 85%.
        below = {"tp": 66, "fp": 77, "fn": 0, "tn": 1000}
        self.assertLess(cohen_kappa(below), 0.6)
        self.assertEqual(round(cohen_kappa(below), 4), 0.6)
        self.assertFalse(meets_bar(below))
        self.assertTrue(meets_bar(dict(below, fp=76)))

    def test_every_exact_three_fifths_table_through_sixty(self):
        exact = legacy_under = 0
        for n in range(1, 61):
            for tp in range(n + 1):
                for fp in range(n - tp + 1):
                    for fn in range(n - tp - fp + 1):
                        tn = n - tp - fp - fn
                        # Independent count form: 2(ad-bc) / ((a+b)(b+d)+(a+c)(c+d)).
                        denominator = (tp + fp) * (fp + tn) + (tp + fn) * (fn + tn)
                        if not denominator or Fraction(2 * (tp * tn - fp * fn), denominator) != Fraction(3, 5):
                            continue
                        exact += 1
                        counts = {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
                        with self.subTest(counts=counts):
                            self.assertEqual(cohen_kappa(counts), 0.6)
                            self.assertTrue(meets_bar(counts, min_agreement=0))
                            self.assertEqual(meets_bar(counts), Fraction(tp + tn, n) >= Fraction(17, 20))
                        chance = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (n * n)
                        old_kappa = ((tp + tn) / n - chance) / (1 - chance)
                        legacy_under += old_kappa < 0.6
        self.assertEqual(exact, 220)
        self.assertEqual(legacy_under, 32)

    def test_counts_tp_fp_fn_tn_in_that_meaning(self):
        # fp and fn differ on purpose: a swap of the two inside confusion must fail here.
        predicted = [True, True, True, False, False, True]
        truth = [True, False, False, True, False, True]
        self.assertEqual(confusion(predicted, truth), {"tp": 2, "fp": 2, "fn": 1, "tn": 1})

    def test_unequal_lengths_raise(self):
        with self.assertRaises(ValueError):
            confusion([True], [True, False])

    def test_hand_worked_eight_seven_four_thirtyone(self):
        counts = {"tp": 8, "fn": 7, "fp": 4, "tn": 31}
        self.assertEqual(agreement(counts), 0.78)
        self.assertAlmostEqual(cohen_kappa(counts), 0.444, places=3)
        self.assertEqual(false_pass_rate(counts), 7 / 15)
        self.assertFalse(meets_bar(counts))
        self.assertTrue(meets_bar(counts, min_agreement=0.78, min_kappa=0.44))
        self.assertFalse(meets_bar(counts, min_agreement=0.78, min_kappa=0.45))

    def test_hand_worked_one_six_zero_ninetythree(self):
        counts = {"tp": 1, "fn": 6, "fp": 0, "tn": 93}
        self.assertEqual(agreement(counts), 0.94)
        self.assertAlmostEqual(cohen_kappa(counts), 0.237, places=3)
        self.assertFalse(meets_bar(counts))

    def test_always_pass_judge_has_kappa_zero(self):
        counts = {"tp": 0, "fn": 7, "fp": 0, "tn": 93}
        self.assertEqual(agreement(counts), 0.93)
        self.assertEqual(cohen_kappa(counts), 0.0)
        self.assertFalse(meets_bar(counts))

    def test_wilson_eleven_of_thirtytwo_and_empty(self):
        low, high = wilson(11, 32)
        self.assertGreater(low, 0.20)
        self.assertLess(low, 0.21)
        self.assertGreater(high, 0.51)
        self.assertLess(high, 0.52)
        self.assertEqual(wilson(0, 0), (0.0, 1.0))

    def test_kappa_is_none_when_chance_agreement_is_one(self):
        counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 10}
        self.assertEqual(agreement(counts), 1.0)
        self.assertIsNone(cohen_kappa(counts))
        self.assertIsNone(false_pass_rate(counts))
        self.assertFalse(meets_bar(counts))

    def test_one_class_only_has_no_kappa(self):
        counts = {"tp": 5, "fp": 0, "fn": 0, "tn": 0}
        self.assertEqual(agreement(counts), 1.0)
        self.assertIsNone(cohen_kappa(counts))
        self.assertEqual(false_pass_rate(counts), 0.0)
        self.assertFalse(meets_bar(counts))

    def test_the_bar_constants_are_the_live_meets_bar_defaults(self):
        self.assertEqual((MIN_AGREEMENT, MIN_KAPPA), (0.85, 0.6))
        counts = {"tp": 3, "fp": 0, "fn": 2, "tn": 27}
        self.assertTrue(meets_bar(counts))
        for name, value in (("MIN_AGREEMENT", 0.95), ("MIN_KAPPA", 0.85)):
            with self.subTest(name=name), mock.patch.object(stats, name, value):
                self.assertFalse(meets_bar(counts))
                self.assertTrue(meets_bar(counts, min_agreement=0.85, min_kappa=0.6))

    def test_empty_counts_do_not_divide_by_zero(self):
        counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        self.assertIsNone(agreement(counts))
        self.assertIsNone(cohen_kappa(counts))
        self.assertIsNone(false_pass_rate(counts))
        self.assertFalse(meets_bar(counts))


if __name__ == "__main__":
    unittest.main()
