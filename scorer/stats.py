"""Agreement, Cohen's kappa, Wilson intervals, and the bar a check has to clear.

A positive is a failure. `fn` is a real failure the check missed (a false pass).
`fp` is a flag the human labels lack (a false fail).
"""
import json
import math


# The two numbers meets_bar tests. The third part of the trust bar, every false
# pass read, is a human act reported beside them and never folded in.
MIN_AGREEMENT = 0.85
MIN_KAPPA = 0.6


def confusion(predicted, truth):
    """Count tp, fp, fn, tn from two equal-length lists of booleans."""
    if len(predicted) != len(truth):
        raise ValueError("predicted and truth must have the same length")
    tp = fp = fn = tn = 0
    for pred, actual in zip(predicted, truth):
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif actual and not pred:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def _parts(counts):
    return counts["tp"], counts["fp"], counts["fn"], counts["tn"]


def _total(counts):
    tp, fp, fn, tn = _parts(counts)
    return tp + fp + fn + tn


def agreement(counts):
    """Share of tickets the check and the labels put in the same class. None if n is 0."""
    total = _total(counts)
    if total == 0:
        return None
    tp, _fp, _fn, tn = _parts(counts)
    return (tp + tn) / total


def cohen_kappa(counts):
    """Cohen's kappa. None when n is 0 or chance agreement is 1."""
    total = _total(counts)
    if total == 0:
        return None
    tp, fp, fn, tn = _parts(counts)
    # Keep the numerator and denominator exact until the final division, so an
    # exact boundary such as 3/5 has the same float as the 0.6 bar.
    chance_numerator = (tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)
    denominator = total * total - chance_numerator
    if denominator == 0:
        return None
    return (total * (tp + tn) - chance_numerator) / denominator


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes in n trials. (0.0, 1.0) when n is 0."""
    if n == 0:
        return (0.0, 1.0)
    proportion = k / n
    denominator = 1.0 + z * z / n
    centre = (proportion + z * z / (2.0 * n)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / n + z * z / (4.0 * n * n)) / denominator
    return (centre - margin, centre + margin)


def paired_difference(a, b, c, d, z=1.96):
    """Newcombe's 1998 method 10, the hybrid score interval for a paired proportion.

    a is the tickets both runs count, b those only A counts, c those only B counts
    and d neither. The fall is (b - c) / n, positive when B counts fewer tickets.
    Returns (fall, lower, upper), or None when n is 0. Built on wilson.
    """
    n = a + b + c + d
    if n == 0:
        return None
    p1 = (a + b) / n
    p2 = (a + c) / n
    l1, u1 = wilson(a + b, n, z)
    l2, u2 = wilson(a + c, n, z)
    disc = a * d - b * c
    if disc > 0:
        adj = max(disc - n / 2.0, 0.0)
    else:
        adj = float(disc)
    product = (a + b) * (c + d) * (a + c) * (b + d)
    if product == 0:
        phi = 0.0
    else:
        phi = adj / math.sqrt(product)
    diff = p1 - p2
    lower_inside = (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2
    upper_inside = (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2
    # A radicand a rounding error pushes below zero is clamped; NaN is not, so a z that
    # overflows the Wilson limits gives NaN limits for the caller to refuse, not a point.
    lower = diff - math.sqrt(0.0 if lower_inside < 0.0 else lower_inside)
    upper = diff + math.sqrt(0.0 if upper_inside < 0.0 else upper_inside)
    return (diff, lower, upper)


def false_pass_rate(counts):
    """Missed real failures over all real failures. None when there are no real failures."""
    tp, _fp, fn, _tn = _parts(counts)
    real = tp + fn
    if real == 0:
        return None
    return fn / real


def meets_bar(counts, min_agreement=None, min_kappa=None):
    """True only when agreement and kappa are both defined and both clear the bar."""
    if min_agreement is None:
        min_agreement = MIN_AGREEMENT
    if min_kappa is None:
        min_kappa = MIN_KAPPA
    observed = agreement(counts)
    kappa = cohen_kappa(counts)
    if observed is None or kappa is None:
        return False
    return observed >= min_agreement and kappa >= min_kappa


def canonical_json(obj):
    """Byte-stable JSON: sorted keys, no ASCII escaping, trailing newline, no timestamps."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def paired_bootstrap(a, b, n_boot=10000, seed=7):
    """(mean of b - a, lower, upper) from one Random(seed).

    Each resample draws n times with rng.choice over the paired differences.
    The resample means are sorted. lo is index int(0.025 * n_boot) and hi is
    index int(0.975 * n_boot). mean_delta is the observed mean, not the
    bootstrap's mean. Unequal or empty inputs raise ValueError.
    """
    if len(a) != len(b) or len(a) == 0:
        raise ValueError("paired_bootstrap needs equal, non-empty inputs")
    import random
    differences = [b[i] - a[i] for i in range(len(a))]
    observed = sum(differences) / float(len(differences))
    rng = random.Random(seed)
    means = []
    width = len(differences)
    for _sample in range(n_boot):
        total = 0.0
        for _draw in range(width):
            total += rng.choice(differences)
        means.append(total / float(width))
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot)]
    return (observed, lo, hi)


def bootstrap_mean(xs, n_boot, seed):
    """paired_bootstrap of xs against zeros."""
    zeros = [0.0] * len(xs)
    return paired_bootstrap(zeros, list(xs), n_boot=n_boot, seed=seed)
