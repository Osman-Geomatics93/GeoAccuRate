"""Auto-generated methods text for publication.

Generates a parameterized paragraph suitable for the Methods section
of a journal article. Includes proper citations.

No QGIS or Qt imports. Only depends on: domain models.
"""

from ..domain.models import ConfusionMatrixResult, RunMetadata


def generate_methods_text(
    result: ConfusionMatrixResult,
    metadata: RunMetadata,
    sampling_info: str = "",
) -> str:
    """Generate a methods paragraph for the accuracy assessment.

    Args:
        result: The accuracy assessment result.
        metadata: Run provenance metadata.
        sampling_info: Optional sentence about sampling design.

    Returns:
        Multi-paragraph methods text with citations.
    """
    n_classes = len(result.class_labels)
    oa = result.overall_accuracy
    oa_lo, oa_hi = result.overall_accuracy_ci
    qd = result.quantity_disagreement
    ad = result.allocation_disagreement

    paragraphs = []

    # Paragraph 1: Sampling and matrix construction
    p1 = (
        f"Accuracy assessment was conducted using {result.n_samples} "
        f"reference samples across {n_classes} land cover classes"
    )
    if sampling_info:
        p1 += f", {sampling_info}"
    p1 += (
        ". A confusion matrix was constructed following the convention "
        "of Congalton and Green (2019), with reference data in rows "
        "and classified data in columns."
    )
    if result.n_excluded_nodata > 0:
        p1 += (
            f" {result.n_excluded_nodata} sample(s) were excluded "
            f"due to nodata values in the classified raster."
        )
    paragraphs.append(p1)

    # Paragraph 2: Overall accuracy and disagreement
    p2 = (
        f"Overall accuracy was {oa:.1%} "
        f"(95% Wilson CI: {oa_lo:.1%}\u2013{oa_hi:.1%}). "
        f"Disagreement was decomposed into quantity disagreement "
        f"({qd:.4f}) and allocation disagreement ({ad:.4f}) "
        f"following Pontius and Millones (2011), which provides a "
        f"more interpretable decomposition of error than the "
        f"traditional Kappa coefficient."
    )
    if result.kappa is not None:
        p2 += f" Cohen\u2019s Kappa was {result.kappa:.4f}."
    paragraphs.append(p2)

    # Paragraph 3: Area-weighted (conditional)
    if result.area_weighted is not None:
        aw = result.area_weighted
        aw_oa = aw.overall_accuracy_weighted
        aw_lo, aw_hi = aw.overall_accuracy_weighted_ci
        # Clamp to [0%, 100%] for display
        aw_lo = max(0.0, aw_lo)
        aw_hi = min(1.0, aw_hi)
        p3 = (
            f"Area-weighted accuracy estimation followed the good "
            f"practices recommended by Olofsson et al. (2014). "
            f"Mapped area proportions were used as inclusion weights "
            f"(W_i = A_i / A_total). Area-weighted overall accuracy "
            f"was {aw_oa:.1%} (95% CI: {aw_lo:.1%}\u2013{aw_hi:.1%}). "
            f"Estimated class areas with 95% confidence intervals "
            f"are reported in the accompanying table."
        )
        paragraphs.append(p3)

    # Paragraph 4: Per-class note
    p4 = (
        "Per-class producer\u2019s and user\u2019s accuracies with "
        "95% Wilson confidence intervals are reported in the "
        "per-class metrics table."
    )
    paragraphs.append(p4)

    # Paragraph 5: Tool attribution
    p5 = (
        f"All accuracy metrics were computed using the GeoAccuRate "
        f"plugin (v{metadata.plugin_version}) for QGIS"
    )
    if metadata.qgis_version:
        p5 += f" {metadata.qgis_version}"
    p5 += "."
    paragraphs.append(p5)

    return "\n\n".join(paragraphs)


def generate_references() -> str:
    """Generate the references section for the report."""
    return (
        "Congalton, R.G. and Green, K. (2019). Assessing the Accuracy "
        "of Remotely Sensed Data: Principles and Practices, 3rd ed. "
        "CRC Press.\n\n"
        "Olofsson, P., Foody, G.M., Herold, M., Stehman, S.V., "
        "Woodcock, C.E. and Wulder, M.A. (2014). Good practices for "
        "estimating area and assessing accuracy of land use change. "
        "Remote Sensing of Environment, 148, 42-57. "
        "https://doi.org/10.1016/j.rse.2014.02.015\n\n"
        "Pontius, R.G. Jr. and Millones, M. (2011). Death to Kappa: "
        "birth of quantity disagreement and allocation disagreement "
        "for accuracy assessment. International Journal of Remote "
        "Sensing, 32(15), 4407-4429. "
        "https://doi.org/10.1080/01431161.2011.552923\n\n"
        "ISO (2013). ISO 19157:2013 Geographic information \u2014 "
        "Data quality. International Organization for Standardization."
    )
