"""Cohen's Kappa coefficient.

Available but NOT enabled by default in GeoAccuRate.
Pontius metrics are preferred for interpretability.

Kappa is included because journal reviewers still request it.

No QGIS or Qt imports. Only depends on: numpy, confidence module.
"""

from typing import Tuple

import numpy as np

from .confidence import kappa_ci as _kappa_ci


def compute(matrix: np.ndarray) -> Tuple[float, Tuple[float, float]]:
    """Compute Cohen's Kappa and its confidence interval.

    Args:
        matrix: k x k confusion matrix (reference=rows, classified=cols).

    Returns:
        (kappa_value, (ci_lower, ci_upper))

    Raises:
        ValueError: If matrix is empty.
    """
    N = int(matrix.sum())
    if N == 0:
        raise ValueError("Cannot compute Kappa on empty matrix")

    row_totals = matrix.sum(axis=1).astype(float)
    col_totals = matrix.sum(axis=0).astype(float)
    diagonal = np.diag(matrix).astype(float)

    p_o = diagonal.sum() / N
    p_e = float((row_totals * col_totals).sum()) / (N * N)

    if abs(1.0 - p_e) < 1e-15:
        # Degenerate case: expected agreement = 1
        # Kappa is undefined; return 0 by convention
        return (0.0, (0.0, 0.0))

    kappa = (p_o - p_e) / (1.0 - p_e)
    ci = _kappa_ci(kappa, p_o, p_e, N)

    return (float(kappa), ci)
