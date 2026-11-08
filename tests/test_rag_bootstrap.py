"""paired_bootstrap and bootstrap_mean. One Random, the observed mean, pinned bytes."""
import unittest

from scorer.stats import bootstrap_mean, canonical_json, paired_bootstrap


class BootstrapTests(unittest.TestCase):
    def test_constant_differences_have_a_zero_width_interval(self):
        mean, lo, hi = paired_bootstrap([1, 1, 1], [4, 4, 4], n_boot=30, seed=3)
        self.assertEqual((mean, lo, hi), (3.0, 3.0, 3.0))

    def test_the_same_seed_gives_the_same_bytes(self):
        left = paired_bootstrap([0.0, 1.0, 0.5], [1.0, 0.0, 0.5], n_boot=80, seed=7)
        right = paired_bootstrap([0.0, 1.0, 0.5], [1.0, 0.0, 0.5], n_boot=80, seed=7)
        self.assertEqual(canonical_json(list(left)), canonical_json(list(right)))
        self.assertLessEqual(left[1], left[0])
        self.assertLessEqual(left[0], left[2])

    def test_a_small_bootstrap_is_pinned(self):
        # Differences are 1 then 0. seed 0, four resamples, two draws each:
        # (0, 0), (1, 0), (0, 0), (0, 0). Means 0, 0.5, 0, 0.
        # lo is index int(0.025 * 4) = 0 and hi is index int(0.975 * 4) = 3.
        pinned = paired_bootstrap([0.0, 1.0], [1.0, 1.0], n_boot=4, seed=0)
        self.assertEqual(pinned, (0.5, 0.0, 0.5))
        # A wider sample. lo is an average, so one reused index cannot produce it.
        wider = paired_bootstrap(
            [0.0, 1.0, 0.0, 1.0], [0.0, 0.0, 1.0, 1.0], n_boot=40, seed=7)
        self.assertEqual(wider, (0.0, -0.5, 0.75))
        self.assertLessEqual(wider[1], wider[0])
        self.assertLessEqual(wider[0], wider[2])

    def test_the_pinned_bounds_sit_at_their_indices(self):
        # Differences 1, 0.5, 0. seed 0, four resamples of three draws by index:
        # (1, 1, 0), (1, 2, 1), (1, 1, 1), (1, 2, 0); means 2/3, 1/3, 1/2, 1/2;
        # sorted 1/3, 1/2, 1/2, 2/3. lo is index 0 and hi index 3, and each has a
        # different neighbour, so an index moved by one moves a bound.
        pinned = paired_bootstrap([0.0, 0.0, 0.0], [1.0, 0.5, 0.0], n_boot=4, seed=0)
        self.assertEqual(pinned, (0.5, 1.0 / 3.0, 2.0 / 3.0))

    def test_empty_or_unequal_inputs_raise(self):
        with self.assertRaises(ValueError):
            paired_bootstrap([], [], n_boot=4, seed=1)
        with self.assertRaises(ValueError):
            paired_bootstrap([1.0], [1.0, 2.0], n_boot=4, seed=1)

    def test_bootstrap_mean_is_the_paired_interval_against_zeros(self):
        sample = [0.25, 0.75, 0.5]
        self.assertEqual(
            bootstrap_mean(sample, 25, 4),
            paired_bootstrap([0.0, 0.0, 0.0], sample, n_boot=25, seed=4),
        )


if __name__ == "__main__":
    unittest.main()
