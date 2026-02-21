"""Confidence interval methods for GeoAccuRate.

Implements Wilson score intervals for proportions.
No QGIS or Qt imports. Only depends on: math.
"""

import math
from typing import Tuple

# z-scores for common confidence levels
Z_SCORES = {
    0.80: 1.2816,
    0.85: 1.4395,
    0.90: 1.6449,
    0.95: 1.9600,
    0.99: 2.5758,
}


def z_score_for_confidence(confidence_level: float) -> float:
    """Get z-score for a given confidence level.

    Args:
        confidence_level: Confidence level in [0, 1], e.g. 0.95.

    Returns:
        Corresponding z-score.
    """
    if confidence_level in Z_SCORES:
        return Z_SCORES[confidence_level]
    # Fall back to approximation via inverse normal CDF (Abramowitz & Stegun)
    # For arbitrary confidence levels
    p = (1 + confidence_level) / 2
    return _probit(p)


def wilson_ci(p: float, n: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score confidence interval for a proportion.

    Superior to the Wald (normal approximation) interval because:
    - Never produces intervals outside [0, 1]
    - More accurate for p near 0 or 1
    - More accurate for small n
    Recommended by Agresti & Coull (1998).

    Args:
        p: Observed proportion (e.g., overall accuracy).
        n: Sample size.
        z: Z-score for desired confidence level (1.96 for 95%).

    Returns:
        (lower, upper) confidence interval bounds.
    """
    if n == 0:
        return (0.0, 1.0)

    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    spread = z * math.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n))) / denom

    lower = max(0.0, center - spread)
    upper = min(1.0, center + spread)
    return (lower, upper)


def kappa_ci(kappa: float, p_o: float, p_e: float, n: int,
             z: float = 1.96) -> Tuple[float, float]:
    """Large-sample confidence interval for Cohen's Kappa.

    Uses the simplified variance approximation from
    Congalton & Green (2019), Appendix.

    Args:
        kappa: Computed Kappa value.
        p_o: Observed agreement proportion.
        p_e: Expected agreement proportion.
        n: Total sample count.
        z: Z-score for desired confidence level.

    Returns:
        (lower, upper) confidence interval bounds.
    """
    if n == 0 or p_e == 1.0:
        return (0.0, 0.0)

    var_k = (p_o * (1.0 - p_o)) / (n * (1.0 - p_e) ** 2)
    se_k = math.sqrt(var_k)
    return (kappa - z * se_k, kappa + z * se_k)


def _probit(p: float) -> float:
    """Approximate inverse of the standard normal CDF.

    Uses the rational approximation from Abramowitz & Stegun (1964),
    formula 26.2.23. Accurate to ~4.5e-4.

    Args:
        p: Probability in (0, 1).

    Returns:
        z-score such that Phi(z) = p.
    """
    if p <= 0.0 or p >= 1.0:
        raise ValueError(f"p must be in (0, 1), got {p}")

    if p < 0.5:
        return -_probit(1.0 - p)

    # Rational approximation constants
    t = math.sqrt(-2.0 * math.log(1.0 - p))
    c0 = 2.515517
    c1 = 0.802853
    c2 = 0.010328
    d1 = 1.432788
    d2 = 0.189269
    d3 = 0.001308

    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)
