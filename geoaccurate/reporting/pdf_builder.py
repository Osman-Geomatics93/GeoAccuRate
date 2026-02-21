"""PDF report generation for GeoAccuRate.

Generates publication-ready PDF reports with tables, charts,
methods text, and provenance metadata.

Depends on: reportlab (optional — graceful fallback if missing).
"""

import io
import json
import math
import os
from typing import List, Optional, Tuple

import numpy as np

from ..domain.confusion_matrix import normalize_confusion_matrix
from ..domain.models import ConfusionMatrixResult, ReportContent, RunMetadata
from .chart_renderer import (
    render_area_comparison_chart,
    render_confusion_matrix_heatmap,
    render_pa_ua_bar_chart,
)
from .methods_text import generate_methods_text, generate_references

# Try to import ReportLab
_REPORTLAB_AVAILABLE = False
try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    _REPORTLAB_AVAILABLE = True
except ImportError:
    pass


def is_pdf_available() -> bool:
    """Check if PDF generation is available."""
    return _REPORTLAB_AVAILABLE


def generate_pdf(content: ReportContent, output_path: str) -> str:
    """Generate a PDF accuracy assessment report.

    Args:
        content: Report content (metadata + results).
        output_path: Path for the output PDF file.

    Returns:
        Path to the generated PDF file.

    Raises:
        ImportError: If ReportLab is not installed.
    """
    if not _REPORTLAB_AVAILABLE:
        raise ImportError(
            "PDF generation requires ReportLab. Install it via: "
            "pip install reportlab"
        )

    result = content.result
    metadata = content.metadata

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    body_small = ParagraphStyle("BodySmall", parent=body, fontSize=8)

    elements = []

    # ── Title ──
    elements.append(Paragraph("GeoAccuRate \u2014 Accuracy Assessment Report", title_style))
    elements.append(Spacer(1, 6 * mm))

    author_display = content.author if content.author else "Not specified"
    meta_lines = [
        f"<b>Title:</b> {content.title}",
        f"<b>Author:</b> {author_display}",
        f"<b>Date:</b> {metadata.timestamp[:10]}",
        f"<b>Plugin:</b> GeoAccuRate v{metadata.plugin_version}",
    ]
    if metadata.qgis_version:
        meta_lines.append(f"<b>QGIS:</b> {metadata.qgis_version}")
    if content.project_name:
        meta_lines.append(f"<b>Project:</b> {content.project_name}")
    for line in meta_lines:
        elements.append(Paragraph(line, body))
    elements.append(Spacer(1, 8 * mm))

    # ── 1. Input Summary ──
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("1. Input Summary", h1))
    # Show layer names (not raw URIs which can be unreadable for memory layers)
    classified_display = metadata.classified_layer_name or metadata.classified_layer_path
    reference_display = metadata.reference_layer_name or metadata.reference_layer_path

    input_lines = [
        f"<b>Classified raster:</b> {classified_display}",
        f"<b>Reference data:</b> {reference_display}",
        f"<b>Reference field:</b> {metadata.reference_field}",
        f"<b>CRS:</b> EPSG:{metadata.crs_epsg}",
        f"<b>Classes:</b> {len(result.class_labels)}",
        f"<b>Total samples:</b> {result.n_samples} ({result.n_excluded_nodata} excluded: nodata)",
    ]
    for line in input_lines:
        elements.append(Paragraph(line, body))
    elements.append(Spacer(1, 6 * mm))

    # ── 2. Confusion Matrix ──
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("2. Confusion Matrix", h1))
    elements.append(_build_confusion_table(result, styles))
    elements.append(Spacer(1, 6 * mm))

    # ── Table B: Row-Normalized Confusion Matrix ──
    elements.append(Paragraph("Table B: Row-Normalized Confusion Matrix (%)", h2))
    elements.append(Paragraph(
        "Each cell shows the percentage of reference samples in that row "
        "classified into each column class.", body_small))
    elements.append(Spacer(1, 2 * mm))
    elements.append(_build_normalized_confusion_table(result, styles))
    elements.append(Spacer(1, 6 * mm))

    # ── 3. Accuracy Metrics ──
    elements.append(Paragraph("3. Accuracy Metrics", h1))
    elements.append(_build_summary_table(result, styles))
    footnote = ParagraphStyle("Footnote", parent=body_small, fontSize=7,
                              textColor=colors.Color(0.4, 0.4, 0.4))
    elements.append(Paragraph(
        "Confidence intervals constrained to logical bounds.", footnote))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("3.1 Per-Class Metrics", h2))
    elements.append(_build_per_class_table(result, styles))
    elements.append(Spacer(1, 6 * mm))

    # ── Interpretation Notes (conditional) ──
    interp_notes = _build_interpretation_notes(content, styles)
    elements.extend(interp_notes)

    # ── 4. Area-Weighted Results ──
    if result.area_weighted is not None:
        elements.append(Paragraph("4. Area-Weighted Results (Olofsson et al. 2014)", h1))
        elements.append(_build_area_table(result, styles))
        elements.append(Spacer(1, 6 * mm))

    # ── 5. Figures ──
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("5. Figures", h1))

    heatmap = render_confusion_matrix_heatmap(result)
    if heatmap:
        elements.append(Paragraph("Figure 1: Confusion Matrix Heatmap", body))
        elements.append(Image(io.BytesIO(heatmap), width=14 * cm, height=10 * cm))
        elements.append(Spacer(1, 4 * mm))

    bar_chart = render_pa_ua_bar_chart(result)
    if bar_chart:
        elements.append(Paragraph("Figure 2: Producer's and User's Accuracy by Class", body))
        elements.append(Image(io.BytesIO(bar_chart), width=14 * cm, height=7 * cm))
        elements.append(Spacer(1, 4 * mm))

    area_chart = render_area_comparison_chart(result)
    if area_chart:
        elements.append(Paragraph("Figure 3: Mapped vs Estimated Area", body))
        elements.append(Image(io.BytesIO(area_chart), width=14 * cm, height=7 * cm))
        elements.append(Spacer(1, 4 * mm))

    # ── 6. Methods ──
    elements.append(PageBreak())
    elements.append(Paragraph("6. Methods", h1))
    methods = generate_methods_text(result, metadata)
    for para in methods.split("\n\n"):
        elements.append(Paragraph(para, body))
        elements.append(Spacer(1, 2 * mm))

    # ── 7. References ──
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("7. References", h1))
    refs = generate_references()
    for ref in refs.split("\n\n"):
        elements.append(Paragraph(ref, body_small))
        elements.append(Spacer(1, 2 * mm))

    # ── 8. ISO 19157 Quality Element Mapping ──
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("8. ISO 19157 Quality Element Mapping", h1))
    elements.append(_build_iso19157_table(styles))
    iso_disclaimer = ParagraphStyle("ISODisclaimer", parent=body_small, fontSize=7,
                                    textColor=colors.Color(0.4, 0.4, 0.4),
                                    fontName="Helvetica-Oblique")
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "This mapping is informational and does not constitute "
        "formal ISO certification.", iso_disclaimer))
    elements.append(Spacer(1, 4 * mm))

    # ── 9. Provenance ──
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("9. Provenance", h1))
    prov_lines = [
        f"<b>Timestamp:</b> {metadata.timestamp}",
        f"<b>Plugin version:</b> {metadata.plugin_version}",
        f"<b>Parameters:</b> {json.dumps(metadata.parameters, indent=2)}",
    ]
    for line in prov_lines:
        elements.append(Paragraph(line, body_small))

    # Build PDF
    doc.build(elements)

    # Also save provenance JSON
    json_path = output_path.rsplit(".", 1)[0] + "_provenance.json"
    _save_provenance_json(metadata, result, json_path)

    return output_path


def _build_confusion_table(result: ConfusionMatrixResult, styles) -> Table:
    """Build confusion matrix as a ReportLab Table."""
    labels = [result.class_names.get(l, str(l)) for l in result.class_labels]
    k = len(labels)
    matrix = result.matrix

    # Header row
    header = ["Ref \\ Cls"] + labels + ["Row Total"]
    data = [header]

    for i in range(k):
        row = [labels[i]]
        for j in range(k):
            row.append(str(int(matrix[i, j])))
        row.append(str(int(matrix[i, :].sum())))
        data.append(row)

    # Column totals row
    col_totals = ["Col Total"]
    for j in range(k):
        col_totals.append(str(int(matrix[:, j].sum())))
    col_totals.append(str(int(matrix.sum())))
    data.append(col_totals)

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.9, 0.9, 0.9)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]))

    # Highlight diagonal
    for i in range(k):
        table.setStyle(TableStyle([
            ("BACKGROUND", (i + 1, i + 1), (i + 1, i + 1),
             colors.Color(0.85, 0.95, 0.85)),
        ]))

    return table


def _build_summary_table(result: ConfusionMatrixResult, styles) -> Table:
    """Build summary metrics table."""
    data = [["Metric", "Value", "95% CI"]]

    oa = result.overall_accuracy
    oa_lo, oa_hi = result.overall_accuracy_ci
    oa_lo, oa_hi = max(0.0, oa_lo), min(1.0, oa_hi)
    data.append(["Overall Accuracy", f"{oa:.1%}", f"{oa_lo:.1%} \u2013 {oa_hi:.1%}"])

    data.append(["Quantity Disagreement", f"{result.quantity_disagreement:.4f}", "\u2014"])
    data.append(["Allocation Disagreement", f"{result.allocation_disagreement:.4f}", "\u2014"])

    td = result.quantity_disagreement + result.allocation_disagreement
    data.append(["Total Disagreement", f"{td:.4f}", "\u2014"])

    if result.kappa is not None:
        k_lo, k_hi = result.kappa_ci or (0, 0)
        data.append(["Kappa", f"{result.kappa:.4f}", f"{k_lo:.4f} \u2013 {k_hi:.4f}"])

    if result.area_weighted is not None:
        aw = result.area_weighted
        aw_lo, aw_hi = aw.overall_accuracy_weighted_ci
        # Clamp to [0%, 100%] — small samples can produce CIs outside range
        aw_lo = max(0.0, aw_lo)
        aw_hi = min(1.0, aw_hi)
        data.append([
            "Area-Weighted OA",
            f"{aw.overall_accuracy_weighted:.1%}",
            f"{aw_lo:.1%} \u2013 {aw_hi:.1%}",
        ])

    table = Table(data, colWidths=[5 * cm, 3 * cm, 4 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    return table


def _build_per_class_table(result: ConfusionMatrixResult, styles) -> Table:
    """Build per-class metrics table."""
    data = [["Class", "PA", "PA CI", "UA", "UA CI", "F1"]]

    for label in result.class_labels:
        name = result.class_names.get(label, str(label))
        pa = result.producers_accuracy.get(label, float("nan"))
        ua = result.users_accuracy.get(label, float("nan"))
        f1 = result.f1_per_class.get(label, float("nan"))
        pa_ci = result.producers_accuracy_ci.get(label, (0, 0))
        ua_ci = result.users_accuracy_ci.get(label, (0, 0))

        def fmt(v):
            return f"{v:.1%}" if not math.isnan(v) else "\u2014"

        def fmt_ci(ci):
            lo, hi = ci
            if math.isnan(lo):
                return "\u2014"
            lo, hi = max(0.0, lo), min(1.0, hi)
            return f"{lo:.1%}\u2013{hi:.1%}"

        data.append([name, fmt(pa), fmt_ci(pa_ci), fmt(ua), fmt_ci(ua_ci), fmt(f1)])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    return table


def _build_area_table(result: ConfusionMatrixResult, styles) -> Table:
    """Build area-weighted results table."""
    aw = result.area_weighted
    if aw is None:
        return Table([["Area-weighted analysis not available"]])

    total_mapped = sum(aw.mapped_area_ha.get(l, 0) for l in result.class_labels)

    data = [["Class", "Mapped (ha)", "Estimated (ha)", "Est. CI (ha)", "PA (weighted)", "UA (weighted)"]]

    for label in result.class_labels:
        name = result.class_names.get(label, str(label))
        mapped = aw.mapped_area_ha.get(label, 0)
        est = aw.estimated_area_ha.get(label, 0)
        ci = aw.estimated_area_ci_ha.get(label, (0, 0))
        pa_w = aw.producers_accuracy_weighted.get(label, float("nan"))
        ua_w = aw.users_accuracy_weighted.get(label, float("nan"))

        def fmt_pct(v):
            if math.isnan(v):
                return "\u2014"
            v = max(0.0, min(1.0, v))
            return f"{v:.1%}"

        # Clamp area CI to logical bounds [0, total_mapped]
        ci_lo = max(0, ci[0])
        ci_hi = min(total_mapped, ci[1]) if total_mapped > 0 else ci[1]
        data.append([
            name,
            f"{mapped:,.0f}",
            f"{est:,.0f}",
            f"{ci_lo:,.0f}\u2013{ci_hi:,.0f}",
            fmt_pct(pa_w),
            fmt_pct(ua_w),
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    return table


def _build_normalized_confusion_table(
    result: ConfusionMatrixResult, styles
) -> Table:
    """Build row-normalized confusion matrix as a ReportLab Table (%)."""
    labels = [result.class_names.get(l, str(l)) for l in result.class_labels]
    k = len(labels)
    norm = normalize_confusion_matrix(result.matrix, axis=1)

    header = ["Ref \\ Cls"] + labels + ["Row Total"]
    data = [header]

    for i in range(k):
        row = [labels[i]]
        for j in range(k):
            row.append(f"{norm[i, j]:.1f}%")
        row.append("100%")
        data.append(row)

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.9, 0.9, 0.9)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
    ]))

    # Highlight diagonal
    for i in range(k):
        table.setStyle(TableStyle([
            ("BACKGROUND", (i + 1, i + 1), (i + 1, i + 1),
             colors.Color(0.85, 0.95, 0.85)),
        ]))

    return table


def _build_interpretation_notes(content: ReportContent, styles) -> list:
    """Build conditional interpretation warning notes.

    Deduplicates per-class warnings from the validator and replaces raw
    class values with human-readable names where available.

    Returns a list of Flowable elements (empty if no warnings apply).
    """
    import re

    result = content.result
    warnings = []
    seen = set()

    # Total sample size (unique to PDF builder, not in validator)
    if result.n_samples < 50:
        warnings.append(
            f"Small total sample size (n={result.n_samples}). "
            f"Results may be unreliable with fewer than 50 samples."
        )

    # Forward validator warnings, deduplicating and enriching class names
    _per_class_re = re.compile(
        r"^Class (\d+) has only (\d+) reference samples"
    )
    for w in content.validation_warnings:
        m = _per_class_re.match(w)
        if m:
            cls_val = int(m.group(1))
            count = m.group(2)
            name = result.class_names.get(cls_val, str(cls_val))
            canonical = (
                f"Class '{name}' has only {count} reference samples "
                f"(minimum recommended: 25)."
            )
            if canonical not in seen:
                seen.add(canonical)
                warnings.append(canonical)
        else:
            if w not in seen:
                seen.add(w)
                warnings.append(w)

    if not warnings:
        return []

    heading_style = ParagraphStyle(
        "InterpHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-BoldOblique",
    )
    warn_style = ParagraphStyle(
        "InterpWarning",
        parent=styles["BodyText"],
        fontSize=9,
        textColor=colors.Color(0.4, 0.25, 0.0),
        backColor=colors.Color(0.96, 0.96, 0.96),
        borderPadding=4,
        spaceBefore=2,
        spaceAfter=2,
    )

    elements = [Spacer(1, 6 * mm)]
    elements.append(Paragraph("Interpretation Notes", heading_style))
    elements.append(Spacer(1, 2 * mm))
    for w in warnings:
        elements.append(Paragraph(f"\u2022 {w}", warn_style))
    elements.append(Spacer(1, 6 * mm))

    return elements


def _build_iso19157_table(styles) -> Table:
    """Build ISO 19157 quality element mapping table."""
    data = [
        ["GeoAccuRate Metric", "ISO 19157 Quality Element", "Measure"],
        ["Overall Accuracy (OA)", "Thematic classification correctness",
         "Misclassification rate"],
        ["Producer's Accuracy (PA)", "Thematic classification correctness",
         "Correctly classified reference samples"],
        ["User's Accuracy (UA)", "Thematic classification correctness",
         "Correctly classified map samples"],
        ["Commission Error (1\u2212UA)", "Thematic classification correctness",
         "Commission error rate"],
        ["Omission Error (1\u2212PA)", "Thematic classification correctness",
         "Omission error rate"],
        ["Quantity Disagreement (QD)", "Thematic classification correctness",
         "Quantity disagreement"],
        ["Allocation Disagreement (AD)", "Thematic classification correctness",
         "Allocation disagreement"],
        ["Confidence Interval (CI)", "Thematic classification correctness",
         "Confidence interval (Wilson)"],
        ["Nodata exclusion", "Completeness \u2014 omission",
         "Missing item"],
    ]

    table = Table(data, colWidths=[5 * cm, 6 * cm, 5 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.8, 0.8, 0.8)),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _save_provenance_json(
    metadata: RunMetadata,
    result: ConfusionMatrixResult,
    output_path: str,
):
    """Save provenance JSON alongside the PDF report."""
    from dataclasses import asdict

    prov = {
        "geoaccurate_version": metadata.plugin_version,
        "qgis_version": metadata.qgis_version,
        "timestamp": metadata.timestamp,
        "classified_layer": {
            "path": metadata.classified_layer_path,
            "name": metadata.classified_layer_name,
            "crs": f"EPSG:{metadata.crs_epsg}",
        },
        "reference_layer": {
            "path": metadata.reference_layer_path,
            "name": metadata.reference_layer_name,
            "field": metadata.reference_field,
        },
        "parameters": metadata.parameters,
        "class_mapping": {str(k): v for k, v in metadata.class_mapping.items()},
        "n_samples": result.n_samples,
        "n_excluded_nodata": result.n_excluded_nodata,
        "results": {
            "overall_accuracy": result.overall_accuracy,
            "overall_accuracy_ci": list(result.overall_accuracy_ci),
            "quantity_disagreement": result.quantity_disagreement,
            "allocation_disagreement": result.allocation_disagreement,
        },
    }

    if result.kappa is not None:
        prov["results"]["kappa"] = result.kappa

    with open(output_path, "w") as f:
        json.dump(prov, f, indent=2)
