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
    observed = (tp + tn) / total
    chance = ((tp + fp) * (tp + fn) + (fn + tn) * (fp + tn)) / (total * total)
    if abs(1.0 - chance) <= 1e-12:
        return None
    return (observed - chance) / (1.0 - chance)


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes in n trials. (0.0, 1.0) when n is 0."""
    if n == 0:
        return (0.0, 1.0)
    proportion = k / n
    denominator = 1.0 + z * z / n
    centre = (proportion + z * z / (2.0 * n)) / denominator
    margin = z * math.sqrt(proportion * (1.0 - proportion) / n + z * z / (4.0 * n * n)) / denominator
    return (centre - margin, centre + margin)


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
