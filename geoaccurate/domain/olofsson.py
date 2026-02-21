"""Olofsson et al. (2014) area-weighted accuracy estimation.

Implements "Good practices for estimating area and assessing accuracy
of land use change" (Remote Sensing of Environment, 148, 42-57).

Corrects for sampling bias when sample allocation differs from class
proportions by using mapped area as inclusion weights.

No QGIS or Qt imports. Only depends on: numpy, typing.
"""

from typing import Dict, Tuple

import numpy as np

from .models import AreaWeightedResult


def compute(
    matrix: np.ndarray,
    mapped_area_ha: Dict[int, float],
    class_labels: Tuple[int, ...],
    z: float = 1.96,
) -> AreaWeightedResult:
    """Compute area-weighted accuracy and area estimates.

    Args:
        matrix: k x k confusion matrix (reference=rows, classified=cols).
        mapped_area_ha: Mapped area per class in hectares,
                        keyed by class label.
        class_labels: Ordered class labels matching matrix dimensions.
        z: Z-score for confidence intervals (1.96 for 95%).

    Returns:
        AreaWeightedResult with all estimates and CIs.

    Raises:
        ValueError: If inputs are inconsistent.
    """
    k = len(class_labels)
    if matrix.shape != (k, k):
        raise ValueError(
            f"Matrix shape {matrix.shape} doesn't match {k} class labels"
        )

    for label in class_labels:
        if label not in mapped_area_ha:
            raise ValueError(
                f"Missing mapped area for class {label}"
            )

    A_total = sum(mapped_area_ha.values())
    if A_total <= 0:
        raise ValueError("Total mapped area must be positive")

    # Area weights: W_j = mapped area of class j / total area
    W = {label: mapped_area_ha[label] / A_total for label in class_labels}

    # Sample counts per mapped class (column totals)
    n_j = matrix.sum(axis=0).astype(float)

    # Check for zero-sample columns
    for j, label in enumerate(class_labels):
        if n_j[j] == 0:
            raise ValueError(
                f"Class {label} has 0 samples in classified map. "
                f"Cannot compute area-weighted estimates."
            )

    # -- Estimated area proportions --
    # p_hat[i,j] = W[j] * (n_ij / n_j)
    p_hat = np.zeros((k, k), dtype=float)
    for i in range(k):
        for j in range(k):
            p_hat[i, j] = W[class_labels[j]] * (matrix[i, j] / n_j[j])

    # -- Estimated area per reference class --
    A_hat = {}
    for i, label in enumerate(class_labels):
        A_hat[label] = float(A_total * p_hat[i, :].sum())

    # -- Overall accuracy (area-weighted) --
    OA_w = float(sum(p_hat[i, i] for i in range(k)))

    # -- User's accuracy (area-weighted) --
    UA_w = {}
    for j, label in enumerate(class_labels):
        col_sum = float(p_hat[:, j].sum())
        if col_sum > 0:
            UA_w[label] = float(p_hat[j, j] / col_sum)
        else:
            UA_w[label] = float("nan")

    # -- Producer's accuracy (area-weighted) --
    PA_w = {}
    for i, label in enumerate(class_labels):
        row_sum = float(p_hat[i, :].sum())
        if row_sum > 0:
            PA_w[label] = float(p_hat[i, i] / row_sum)
        else:
            PA_w[label] = float("nan")

    # -- Variance and CI for estimated area --
    A_hat_ci = {}
    for i, label_i in enumerate(class_labels):
        var_sum = 0.0
        for j, label_j in enumerate(class_labels):
            if n_j[j] > 1:
                p_ij = matrix[i, j] / n_j[j]
                w_j = W[label_j]
                var_sum += w_j ** 2 * p_ij * (1.0 - p_ij) / (n_j[j] - 1)
        se = A_total * np.sqrt(var_sum)
        A_hat_ci[label_i] = (
            float(A_hat[label_i] - z * se),
            float(A_hat[label_i] + z * se),
        )

    # -- Variance and CI for overall accuracy --
    var_oa = 0.0
    for j, label in enumerate(class_labels):
        if n_j[j] > 1:
            w_j = W[label]
            ua_j = UA_w[label]
            if not np.isnan(ua_j):
                var_oa += w_j ** 2 * ua_j * (1.0 - ua_j) / (n_j[j] - 1)
    se_oa = np.sqrt(var_oa)
    OA_w_ci = (float(OA_w - z * se_oa), float(OA_w + z * se_oa))

    return AreaWeightedResult(
        weight_per_class=dict(W),
        estimated_area_ha=A_hat,
        estimated_area_ci_ha=A_hat_ci,
        overall_accuracy_weighted=OA_w,
        overall_accuracy_weighted_ci=OA_w_ci,
        producers_accuracy_weighted=PA_w,
        users_accuracy_weighted=UA_w,
        mapped_area_ha=dict(mapped_area_ha),
    )
