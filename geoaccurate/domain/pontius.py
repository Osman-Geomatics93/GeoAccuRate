"""Pontius & Millones (2011) Quantity and Allocation Disagreement.

Decomposes total disagreement into two interpretable components:
  - Quantity Disagreement (QD): difference in class proportions
  - Allocation Disagreement (AD): misallocation given correct proportions

Identity: QD + AD = 1 - OA (total disagreement). This is asserted.

Preferred over Kappa for interpretability.

No QGIS or Qt imports. Only depends on: numpy.
"""

from typing import Tuple

import numpy as np


def compute(matrix: np.ndarray) -> Tuple[float, float]:
    """Compute Quantity and Allocation Disagreement.

    Args:
        matrix: k x k confusion matrix (reference=rows, classified=cols).

    Returns:
        (quantity_disagreement, allocation_disagreement)

    Raises:
        ValueError: If matrix is empty or identity QD + AD = 1-OA fails.
    """
    N = matrix.sum()
    if N == 0:
        raise ValueError("Cannot compute Pontius metrics on empty matrix")

    k = matrix.shape[0]

    row_props = matrix.sum(axis=1) / N    # reference proportions
    col_props = matrix.sum(axis=0) / N    # classified proportions
    diag_props = np.diag(matrix) / N      # agreement proportions

    qd = 0.0
    ad = 0.0

    for i in range(k):
        # Quantity difference for class i
        q_i = abs(float(col_props[i]) - float(row_props[i]))

        # Allocation difference for class i
        commission_i = float(col_props[i]) - float(diag_props[i])
        omission_i = float(row_props[i]) - float(diag_props[i])
        a_i = 2.0 * min(commission_i, omission_i)

        qd += q_i
        ad += a_i

    qd /= 2.0
    ad /= 2.0

    # Validate the identity: QD + AD = 1 - OA
    oa = float(diag_props.sum())
    total_disagreement = 1.0 - oa
    residual = abs(qd + ad - total_disagreement)
    if residual > 1e-9:
        raise ValueError(
            f"Pontius identity violated: QD({qd:.10f}) + AD({ad:.10f}) = "
            f"{qd + ad:.10f} != 1 - OA = {total_disagreement:.10f} "
            f"(residual={residual:.2e})"
        )

    return (qd, ad)
