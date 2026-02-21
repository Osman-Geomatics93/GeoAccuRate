"""Chart rendering for GeoAccuRate reports.

Generates publication-quality matplotlib figures for embedding
in PDF reports and the QGIS dock widget.

Depends on: matplotlib, numpy.
"""

import io
import math
from typing import Optional, Tuple

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend for thread safety
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    from matplotlib.colors import Normalize
    from matplotlib.patches import Rectangle
    from matplotlib.cm import ScalarMappable
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
            result.class_names.get(lbl, str(lbl)) for lbl in result.class_labels
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
        names = [result.class_names.get(lbl, str(lbl)) for lbl in labels_ordered]
        x = np.arange(len(labels_ordered))
        width = 0.35

        pa_vals = [result.producers_accuracy.get(lbl, 0) * 100 for lbl in labels_ordered]
        ua_vals = [result.users_accuracy.get(lbl, 0) * 100 for lbl in labels_ordered]

        # Error bars from CIs
        pa_lo = [result.producers_accuracy_ci.get(lbl, (0, 0))[0] * 100 for lbl in labels_ordered]
        pa_hi = [result.producers_accuracy_ci.get(lbl, (0, 0))[1] * 100 for lbl in labels_ordered]
        ua_lo = [result.users_accuracy_ci.get(lbl, (0, 0))[0] * 100 for lbl in labels_ordered]
        ua_hi = [result.users_accuracy_ci.get(lbl, (0, 0))[1] * 100 for lbl in labels_ordered]

        pa_err = [[v - lo for v, lo in zip(pa_vals, pa_lo)],
                   [hi - v for v, hi in zip(pa_vals, pa_hi)]]
        ua_err = [[v - lo for v, lo in zip(ua_vals, ua_lo)],
                   [hi - v for v, hi in zip(ua_vals, ua_hi)]]

        ax.bar(x - width / 2, pa_vals, width, label="Producer's Acc.",
                        yerr=pa_err, capsize=3, color="#4C72B0", edgecolor="black",
                        linewidth=0.5)
        ax.bar(x + width / 2, ua_vals, width, label="User's Acc.",
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


def draw_extended_heatmap(ax, result: ConfusionMatrixResult, cmap: str = "YlOrRd"):
    """Draw an extended confusion matrix heatmap onto *ax*.

    The extended layout includes:
    - k x k core confusion matrix (colored)
    - Total row and column (gray)
    - Producer's Accuracy row (gray, %)
    - User's Accuracy column (gray, %)
    - Overall Accuracy in the PA/UA intersection cell
    - Kappa in its own column (if available)

    Returns the colorbar-mappable so the caller can add a colorbar.
    """
    matrix = result.matrix
    k = matrix.shape[0]
    labels = [result.class_names.get(lbl, str(lbl)) for lbl in result.class_labels]

    # --- Build the extended numeric grid ---
    # Columns: k classes + Total + UA  (+ Kappa if available)
    has_kappa = result.kappa is not None
    n_extra_cols = 3 if has_kappa else 2  # Total, UA, (Kappa)
    n_extra_rows = 2  # Total, PA
    n_rows = k + n_extra_rows
    n_cols = k + n_extra_cols

    # Compute marginals
    row_totals = matrix.sum(axis=1)  # (k,)
    col_totals = matrix.sum(axis=0)  # (k,)
    grand_total = matrix.sum()

    pa_values = []
    for idx, lbl in enumerate(result.class_labels):
        pa = result.producers_accuracy.get(lbl, float("nan"))
        pa_values.append(pa * 100 if not math.isnan(pa) else float("nan"))

    ua_values = []
    for idx, lbl in enumerate(result.class_labels):
        ua = result.users_accuracy.get(lbl, float("nan"))
        ua_values.append(ua * 100 if not math.isnan(ua) else float("nan"))

    oa_pct = result.overall_accuracy * 100

    # --- Draw core cells as colored patches ---
    cmap_obj = plt.get_cmap(cmap)
    vmin, vmax = 0, matrix.max() if matrix.max() > 0 else 1
    norm = Normalize(vmin=vmin, vmax=vmax)

    for i in range(k):
        for j in range(k):
            val = matrix[i, j]
            color = cmap_obj(norm(val))
            ax.add_patch(Rectangle((j, i), 1, 1, facecolor=color, edgecolor="gray", linewidth=0.5))
            # Smart text color
            luminance = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
            txt_color = "white" if luminance < 0.5 else "black"
            ax.text(j + 0.5, i + 0.5, str(int(val)), ha="center", va="center",
                    color=txt_color, fontsize=9, fontweight="bold")

    gray = "#E0E0E0"

    # --- Total column (col index = k) ---
    for i in range(k):
        ax.add_patch(Rectangle((k, i), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
        ax.text(k + 0.5, i + 0.5, str(int(row_totals[i])), ha="center", va="center", fontsize=9)

    # --- Total row (row index = k) ---
    for j in range(k):
        ax.add_patch(Rectangle((j, k), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
        ax.text(j + 0.5, k + 0.5, str(int(col_totals[j])), ha="center", va="center", fontsize=9)

    # Grand total cell
    ax.add_patch(Rectangle((k, k), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
    ax.text(k + 0.5, k + 0.5, str(int(grand_total)), ha="center", va="center",
            fontsize=9, fontweight="bold")

    # --- UA column (col index = k+1) ---
    ua_col = k + 1
    for i in range(k):
        ax.add_patch(Rectangle((ua_col, i), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
        txt = f"{ua_values[i]:.1f}%" if not math.isnan(ua_values[i]) else "\u2014"
        ax.text(ua_col + 0.5, i + 0.5, txt, ha="center", va="center", fontsize=8)

    # UA header in total row
    ax.add_patch(Rectangle((ua_col, k), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
    ax.text(ua_col + 0.5, k + 0.5, "", ha="center", va="center", fontsize=8)

    # --- PA row (row index = k+1) ---
    pa_row = k + 1
    for j in range(k):
        ax.add_patch(Rectangle((j, pa_row), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
        txt = f"{pa_values[j]:.1f}%" if not math.isnan(pa_values[j]) else "\u2014"
        ax.text(j + 0.5, pa_row + 0.5, txt, ha="center", va="center", fontsize=8)

    # PA/Total intersection → empty
    ax.add_patch(Rectangle((k, pa_row), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
    ax.text(k + 0.5, pa_row + 0.5, "", ha="center", va="center", fontsize=8)

    # PA/UA intersection → OA
    ax.add_patch(Rectangle((ua_col, pa_row), 1, 1, facecolor="#B0D0FF", edgecolor="gray", linewidth=0.5))
    ax.text(ua_col + 0.5, pa_row + 0.5, f"OA\n{oa_pct:.1f}%", ha="center", va="center",
            fontsize=8, fontweight="bold")

    # --- Kappa column (col index = k+2) if available ---
    if has_kappa:
        kappa_col = k + 2
        for i in range(k):
            ax.add_patch(Rectangle((kappa_col, i), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
            ax.text(kappa_col + 0.5, i + 0.5, "", ha="center", va="center", fontsize=8)
        # Total row
        ax.add_patch(Rectangle((kappa_col, k), 1, 1, facecolor=gray, edgecolor="gray", linewidth=0.5))
        ax.text(kappa_col + 0.5, k + 0.5, "", ha="center", va="center", fontsize=8)
        # PA row → Kappa value
        ax.add_patch(Rectangle((kappa_col, pa_row), 1, 1, facecolor="#FFD0B0", edgecolor="gray", linewidth=0.5))
        ax.text(kappa_col + 0.5, pa_row + 0.5, f"\u03BA\n{result.kappa:.3f}",
                ha="center", va="center", fontsize=8, fontweight="bold")

    # --- Thick separator lines ---
    lw = 2
    # Vertical line after core columns
    ax.plot([k, k], [0, n_rows], color="black", linewidth=lw, clip_on=False)
    # Horizontal line after core rows
    ax.plot([0, n_cols], [k, k], color="black", linewidth=lw, clip_on=False)
    # Vertical line after Total column
    ax.plot([k + 1, k + 1], [0, n_rows], color="black", linewidth=lw * 0.7, clip_on=False)
    # Horizontal line after Total row
    ax.plot([0, n_cols], [k + 1, k + 1], color="black", linewidth=lw * 0.7, clip_on=False)

    # --- Axis config ---
    ax.set_xlim(0, n_cols)
    ax.set_ylim(n_rows, 0)  # invert y so row 0 is on top
    ax.set_aspect("equal")

    # X-axis labels on top
    col_labels = labels + ["Total", "UA"] + (["\u03BA"] if has_kappa else [])
    ax.set_xticks([i + 0.5 for i in range(n_cols)])
    ax.set_xticklabels(col_labels, rotation=45, ha="left", fontsize=9)
    ax.xaxis.set_ticks_position("top")
    ax.xaxis.set_label_position("top")

    # Y-axis labels
    row_labels = labels + ["Total", "PA"]
    ax.set_yticks([i + 0.5 for i in range(n_rows)])
    ax.set_yticklabels(row_labels, fontsize=9)

    ax.tick_params(length=0)  # hide tick marks

    # Outer border
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.5)

    ax.set_xlabel("Classified", fontsize=11, labelpad=8)
    ax.set_ylabel("Reference", fontsize=11, labelpad=8)
    ax.set_title("Confusion Matrix", fontsize=13, fontweight="bold", pad=40)

    # Return the ScalarMappable for colorbar
    sm = ScalarMappable(cmap=cmap_obj, norm=norm)
    sm.set_array([])
    return sm


def create_extended_heatmap_figure(
    result: ConfusionMatrixResult,
    cmap: str = "YlOrRd",
    figsize: Tuple[float, float] = (10, 8),
    dpi: int = 150,
) -> "Figure":
    """Create a standalone Figure with the extended heatmap.

    Uses ``Figure()`` directly (not ``plt.subplots()``) to avoid
    backend conflicts when embedding in a Qt canvas.
    """
    fig = Figure(figsize=figsize, dpi=dpi)
    ax = fig.add_subplot(111)
    sm = draw_extended_heatmap(ax, result, cmap)
    fig.colorbar(sm, ax=ax, label="Count", shrink=0.6, pad=0.02)
    fig.tight_layout()
    return fig


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
        names = [result.class_names.get(lbl, str(lbl)) for lbl in labels_ordered]
        x = np.arange(len(labels_ordered))
        width = 0.35

        mapped = [aw.mapped_area_ha.get(lbl, 0) for lbl in labels_ordered]
        estimated = [aw.estimated_area_ha.get(lbl, 0) for lbl in labels_ordered]

        # Clamp CI lower bounds to 0 (area can't be negative)
        est_lo = [max(0, aw.estimated_area_ci_ha.get(lbl, (0, 0))[0]) for lbl in labels_ordered]
        est_hi = [aw.estimated_area_ci_ha.get(lbl, (0, 0))[1] for lbl in labels_ordered]
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
