"""Confusion matrix construction and basic accuracy metrics.

Convention: rows = reference (true), columns = classified (predicted).
This follows Congalton & Green (2019).

No QGIS or Qt imports. Only depends on: numpy.
"""

from typing import Dict, Tuple

import numpy as np

from .confidence import wilson_ci, z_score_for_confidence


def build_matrix(
    classified: np.ndarray,
    reference: np.ndarray,
    class_labels: Tuple[int, ...],
) -> np.ndarray:
    """Build a confusion matrix from paired classified/reference values.

    Args:
        classified: 1D array of classified (predicted) values.
        reference: 1D array of reference (true) values.
        class_labels: Ordered tuple of all class values.

    Returns:
        k x k numpy integer array where:
          matrix[i, j] = count of samples with reference=class_labels[i]
                         and classified=class_labels[j].
    """
    if len(classified) != len(reference):
        raise ValueError(
            f"Array length mismatch: classified={len(classified)}, "
            f"reference={len(reference)}"
        )
    if len(classified) == 0:
        raise ValueError("Cannot build confusion matrix from empty arrays")

    k = len(class_labels)
    label_to_idx = {label: i for i, label in enumerate(class_labels)}

    matrix = np.zeros((k, k), dtype=np.int64)
    for c_val, r_val in zip(classified, reference):
        r_idx = label_to_idx.get(r_val)
        c_idx = label_to_idx.get(c_val)
        if r_idx is not None and c_idx is not None:
            matrix[r_idx, c_idx] += 1

    return matrix


def compute_metrics(
    matrix: np.ndarray,
    class_labels: Tuple[int, ...],
    confidence_level: float = 0.95,
) -> dict:
    """Compute all basic accuracy metrics from a confusion matrix.

    Args:
        matrix: k x k confusion matrix (reference=rows, classified=cols).
        class_labels: Ordered class labels matching matrix dimensions.
        confidence_level: For Wilson CIs (default 0.95).

    Returns:
        Dictionary with keys:
          overall_accuracy, overall_accuracy_ci,
          producers_accuracy, users_accuracy,
          producers_accuracy_ci, users_accuracy_ci,
          f1_per_class, precision_per_class, recall_per_class
    """
    k = len(class_labels)
    if matrix.shape != (k, k):
        raise ValueError(
            f"Matrix shape {matrix.shape} does not match "
            f"{k} class labels"
        )

    N = int(matrix.sum())
    if N == 0:
        raise ValueError("Confusion matrix has zero total samples")

    z = z_score_for_confidence(confidence_level)

    row_totals = matrix.sum(axis=1)    # reference totals
    col_totals = matrix.sum(axis=0)    # classified totals
    diagonal = matrix.diagonal()

    # Overall accuracy
    oa = float(diagonal.sum()) / N
    oa_ci = wilson_ci(oa, N, z)

    pa: Dict[int, float] = {}
    ua: Dict[int, float] = {}
    pa_ci: Dict[int, Tuple[float, float]] = {}
    ua_ci: Dict[int, Tuple[float, float]] = {}
    f1: Dict[int, float] = {}
    precision: Dict[int, float] = {}
    recall: Dict[int, float] = {}

    for i, label in enumerate(class_labels):
        # Producer's accuracy (recall)
        if row_totals[i] > 0:
            pa_val = float(diagonal[i]) / float(row_totals[i])
            pa[label] = pa_val
            pa_ci[label] = wilson_ci(pa_val, int(row_totals[i]), z)
        else:
            pa[label] = float("nan")
            pa_ci[label] = (float("nan"), float("nan"))

        # User's accuracy (precision)
        if col_totals[i] > 0:
            ua_val = float(diagonal[i]) / float(col_totals[i])
            ua[label] = ua_val
            ua_ci[label] = wilson_ci(ua_val, int(col_totals[i]), z)
        else:
            ua[label] = float("nan")
            ua_ci[label] = (float("nan"), float("nan"))

        # F1 score
        pa_v = pa[label]
        ua_v = ua[label]
        if (
            not (np.isnan(pa_v) or np.isnan(ua_v))
            and (pa_v + ua_v) > 0
        ):
            f1[label] = 2.0 * pa_v * ua_v / (pa_v + ua_v)
        else:
            f1[label] = float("nan")

        precision[label] = ua[label]  # precision = user's accuracy
        recall[label] = pa[label]     # recall = producer's accuracy

    return {
        "overall_accuracy": oa,
        "overall_accuracy_ci": oa_ci,
        "producers_accuracy": pa,
        "users_accuracy": ua,
        "producers_accuracy_ci": pa_ci,
        "users_accuracy_ci": ua_ci,
        "f1_per_class": f1,
        "precision_per_class": precision,
        "recall_per_class": recall,
    }


def normalize_confusion_matrix(matrix: np.ndarray, axis: int = 1) -> np.ndarray:
    """Normalize a confusion matrix to percentages along an axis.

    Args:
        matrix: k x k confusion matrix (integer or float).
        axis: Normalization axis. 1 = row-normalize (default),
              0 = column-normalize.

    Returns:
        k x k float array where values sum to 100.0 along the given axis.
        Zero-sum rows/columns produce all zeros (no NaN/Inf).
    """
    m = matrix.astype(np.float64)
    totals = m.sum(axis=axis, keepdims=True)
    safe_totals = np.where(totals == 0, 1.0, totals)
    return np.where(totals == 0, 0.0, m / safe_totals * 100.0)
