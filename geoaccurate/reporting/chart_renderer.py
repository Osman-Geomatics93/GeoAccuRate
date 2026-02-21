"""Chart rendering for GeoAccuRate reports.

Generates publication-quality matplotlib figures for embedding
in PDF reports and the QGIS dock widget.

Depends on: matplotlib, numpy.
"""

import io
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for thread safety
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from ..domain.models import ConfusionMatrixResult


# Publication-quality style
STYLE = {
    "font.family": "serif",
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
}


def is_available() -> bool:
    return HAS_MATPLOTLIB


def render_confusion_matrix_heatmap(
    result: ConfusionMatrixResult,
    figsize: Tuple[float, float] = (8, 6),
) -> Optional[bytes]:
    """Render confusion matrix as a heatmap.

    Returns:
        PNG image bytes, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=figsize)

        matrix = result.matrix
        k = matrix.shape[0]
        labels = [
            result.class_names.get(l, str(l)) for l in result.class_labels
        ]

        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

        # Annotate cells with counts
        for i in range(k):
            for j in range(k):
                val = int(matrix[i, j])
                color = "white" if val > matrix.max() * 0.6 else "black"
                ax.text(j, i, str(val), ha="center", va="center",
                        color=color, fontsize=9)

        ax.set_xticks(range(k))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(k))
        ax.set_yticklabels(labels)
        ax.set_xlabel("Classified")
        ax.set_ylabel("Reference")
        ax.set_title("Confusion Matrix")

        fig.colorbar(im, ax=ax, label="Count", shrink=0.8)
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300)
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def render_pa_ua_bar_chart(
    result: ConfusionMatrixResult,
    figsize: Tuple[float, float] = (10, 5),
) -> Optional[bytes]:
    """Render Producer's and User's Accuracy per class as a grouped bar chart.

    Returns:
        PNG image bytes, or None if matplotlib unavailable.
    """
    if not HAS_MATPLOTLIB:
        return None

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=figsize)

        labels_ordered = list(result.class_labels)
        names = [result.class_names.get(l, str(l)) for l in labels_ordered]
        x = np.arange(len(labels_ordered))
        width = 0.35

        pa_vals = [result.producers_accuracy.get(l, 0) * 100 for l in labels_ordered]
        ua_vals = [result.users_accuracy.get(l, 0) * 100 for l in labels_ordered]

        # Error bars from CIs
        pa_lo = [result.producers_accuracy_ci.get(l, (0, 0))[0] * 100 for l in labels_ordered]
        pa_hi = [result.producers_accuracy_ci.get(l, (0, 0))[1] * 100 for l in labels_ordered]
        ua_lo = [result.users_accuracy_ci.get(l, (0, 0))[0] * 100 for l in labels_ordered]
        ua_hi = [result.users_accuracy_ci.get(l, (0, 0))[1] * 100 for l in labels_ordered]

        pa_err = [[v - lo for v, lo in zip(pa_vals, pa_lo)],
                   [hi - v for v, hi in zip(pa_vals, pa_hi)]]
        ua_err = [[v - lo for v, lo in zip(ua_vals, ua_lo)],
                   [hi - v for v, hi in zip(ua_vals, ua_hi)]]

        bars1 = ax.bar(x - width / 2, pa_vals, width, label="Producer's Acc.",
                        yerr=pa_err, capsize=3, color="#4C72B0", edgecolor="black",
                        linewidth=0.5)
        bars2 = ax.bar(x + width / 2, ua_vals, width, label="User's Acc.",
                        yerr=ua_err, capsize=3, color="#DD8452", edgecolor="black",
                        linewidth=0.5)

        # OA reference line
        oa_pct = result.overall_accuracy * 100
        ax.axhline(y=oa_pct, color="gray", linestyle="--", linewidth=1,
                    label=f"OA = {oa_pct:.1f}%")

        ax.set_xlabel("Class")
        ax.set_ylabel("Accuracy (%)")
        ax.set_title("Producer's and User's Accuracy by Class")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.set_ylim(0, 105)
        ax.legend(loc="lower left")
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300)
        plt.close(fig)
        buf.seek(0)
        return buf.read()


def render_area_comparison_chart(
    result: ConfusionMatrixResult,
    figsize: Tuple[float, float] = (10, 5),
) -> Optional[bytes]:
    """Render mapped vs estimated area bar chart (Olofsson).

    Returns:
        PNG image bytes, or None if matplotlib unavailable or no area data.
    """
    if not HAS_MATPLOTLIB or result.area_weighted is None:
        return None

    aw = result.area_weighted

    with plt.rc_context(STYLE):
        fig, ax = plt.subplots(figsize=figsize)

        labels_ordered = list(result.class_labels)
        names = [result.class_names.get(l, str(l)) for l in labels_ordered]
        x = np.arange(len(labels_ordered))
        width = 0.35

        mapped = [aw.mapped_area_ha.get(l, 0) for l in labels_ordered]
        estimated = [aw.estimated_area_ha.get(l, 0) for l in labels_ordered]

        # Clamp CI lower bounds to 0 (area can't be negative)
        est_lo = [max(0, aw.estimated_area_ci_ha.get(l, (0, 0))[0]) for l in labels_ordered]
        est_hi = [aw.estimated_area_ci_ha.get(l, (0, 0))[1] for l in labels_ordered]
        est_err = [[max(0, e - lo) for e, lo in zip(estimated, est_lo)],
                    [max(0, hi - e) for e, hi in zip(estimated, est_hi)]]

        ax.bar(x - width / 2, mapped, width, label="Mapped Area",
               color="#AEC7E8", edgecolor="black", linewidth=0.5)
        ax.bar(x + width / 2, estimated, width, label="Estimated Area",
               yerr=est_err, capsize=3, color="#FF9896", edgecolor="black",
               linewidth=0.5)

        ax.set_xlabel("Class")
        ax.set_ylabel("Area (ha)")
        ax.set_title("Mapped vs Estimated Area (Olofsson et al. 2014)")
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right")
        ax.legend()
        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=300)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
