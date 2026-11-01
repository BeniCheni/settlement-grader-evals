"""The judge comparison page. Agreement percents come from the integer counts."""
import unittest

from scorer.judge import agreement_percent


class AgreementPercentTests(unittest.TestCase):
    def test_one_decimal_from_the_counts(self):
        # Set 1's final and first-pass agreements, as the report prints them.
        self.assertEqual(agreement_percent(32, 40), "80.0%")
        self.assertEqual(agreement_percent(37, 40), "92.5%")
        self.assertEqual(agreement_percent(23, 40), "57.5%")
        self.assertEqual(agreement_percent(26, 40), "65.0%")
        self.assertEqual(agreement_percent(1, 1), "100.0%")
        self.assertEqual(agreement_percent(0, 1), "0.0%")
        self.assertEqual(agreement_percent(0, 0), "none")

    def test_an_exact_half_rounds_away_from_zero(self):
        # 1/16 is 6.25%, halfway between 6.2% and 6.3%. Half away from zero is 6.3%.
        # 5/16 is 31.25%, halfway between 31.2% and 31.3%, and prints 31.3%.
        self.assertEqual(agreement_percent(1, 16), "6.3%")
        self.assertEqual(agreement_percent(5, 16), "31.3%")
        self.assertEqual((1 * 1000) % 16, 8)
        self.assertEqual(16 // 2, 8)
