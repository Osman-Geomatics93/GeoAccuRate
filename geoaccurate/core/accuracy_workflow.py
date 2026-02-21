"""Accuracy assessment workflow orchestrator.

Coordinates the full pipeline: validate -> extract -> compute -> package.
This is the bridge between core I/O and domain math.

Depends on: core.*, domain.*.
"""

import datetime
from typing import Dict, Optional, Tuple

import numpy as np

from ..domain import confusion_matrix, kappa, olofsson, pontius
from ..domain.confidence import z_score_for_confidence
from ..domain.models import (
    AreaWeightedResult,
    ConfusionMatrixResult,
    RunMetadata,
)
from .area_calculator import GeographicCRSError, compute_class_areas_ha
from .input_validator import ValidationResult, validate_accuracy_inputs
from .raster_reader import extract_values_at_points, get_raster_info


def run_accuracy_assessment(
    classified_raster_path: str,
    reference_points_xy: np.ndarray,
    reference_class_values: np.ndarray,
    class_labels: Tuple[int, ...],
    class_names: Dict[int, str],
    class_mapping: Optional[Dict[int, int]] = None,
    compute_kappa: bool = False,
    compute_area_weighted: bool = True,
    confidence_level: float = 0.95,
    plugin_version: str = "1.0.0",
    qgis_version: str = "",
    reference_layer_path: str = "",
    reference_layer_name: str = "",
    reference_field: str = "",
) -> Tuple[ConfusionMatrixResult, ValidationResult, RunMetadata]:
    """Execute the full accuracy assessment workflow.

    Args:
        classified_raster_path: Path to classified raster.
        reference_points_xy: Nx2 array of reference point coordinates.
        reference_class_values: 1D array of reference class values.
        class_labels: Ordered tuple of class values.
        class_names: {class_value: display_name}.
        class_mapping: Optional {classified_value: reference_value} remapping.
        compute_kappa: Whether to compute Kappa coefficient.
        compute_area_weighted: Whether to compute Olofsson estimates.
        confidence_level: CI confidence level (e.g. 0.95).
        plugin_version: Plugin version string.
        qgis_version: QGIS version string.
        reference_layer_path: Reference file path (for provenance).
        reference_layer_name: Reference layer name (for provenance).
        reference_field: Reference class field name (for provenance).

    Returns:
        (result, validation, metadata)
    """
    # --- Step 1: Extract classified values at reference points ---
    classified_values, valid_mask = extract_values_at_points(
        classified_raster_path, reference_points_xy
    )

    # Combine with reference validity
    ref_valid = np.isfinite(reference_class_values.astype(float))
    combined_valid = valid_mask & ref_valid

    n_excluded = int((~combined_valid).sum())
    n_valid = int(combined_valid.sum())

    # Filter to valid samples only
    cls_valid = classified_values[combined_valid].astype(np.int64)
    ref_valid_vals = reference_class_values[combined_valid].astype(np.int64)

    # Apply class mapping if provided
    if class_mapping:
        cls_valid = np.array([
            class_mapping.get(int(v), int(v)) for v in cls_valid
        ], dtype=np.int64)

    # --- Step 2: Validate ---
    classified_classes = set(cls_valid.tolist())
    reference_classes = set(ref_valid_vals.tolist())

    # Per-class sample counts (reference-based)
    class_sample_counts = {}
    for label in class_labels:
        class_sample_counts[label] = int((ref_valid_vals == label).sum())

    validation = validate_accuracy_inputs(
        classified_raster_path=classified_raster_path,
        reference_classes=reference_classes,
        classified_classes=classified_classes,
        n_reference_samples=n_valid,
        n_excluded_nodata=n_excluded,
        area_weighted=compute_area_weighted,
        class_sample_counts=class_sample_counts,
    )

    if not validation.is_valid:
        # Return partial result with validation errors
        raise ValueError(
            "Validation failed:\n" +
            "\n".join(f"  [{i.severity}] {i.message}" for i in validation.fatal_issues)
        )

    # --- Step 3: Build confusion matrix ---
    matrix = confusion_matrix.build_matrix(cls_valid, ref_valid_vals, class_labels)

    # --- Step 4: Compute metrics ---
    metrics = confusion_matrix.compute_metrics(matrix, class_labels, confidence_level)

    # --- Step 5: Pontius metrics ---
    qd, ad = pontius.compute(matrix)

    # --- Step 6: Kappa (optional) ---
    kappa_val = None
    kappa_ci = None
    if compute_kappa:
        kappa_val, kappa_ci = kappa.compute(matrix)

    # --- Step 7: Olofsson area-weighted (optional) ---
    area_weighted_result: Optional[AreaWeightedResult] = None
    if compute_area_weighted:
        try:
            area_ha, _ = compute_class_areas_ha(
                classified_raster_path, list(class_labels)
            )
            z = z_score_for_confidence(confidence_level)
            area_weighted_result = olofsson.compute(
                matrix, area_ha, class_labels, z
            )
        except GeographicCRSError:
            # This should have been caught by validation, but be safe
            validation.issues.append(type(validation.issues[0])(
                severity="WARNING",
                message="Area-weighted analysis skipped: geographic CRS.",
            ) if validation.issues else None)
            area_weighted_result = None

    # --- Step 8: Package result ---
    result = ConfusionMatrixResult(
        matrix=matrix,
        class_labels=class_labels,
        class_names=class_names,
        n_samples=n_valid,
        n_excluded_nodata=n_excluded,
        overall_accuracy=metrics["overall_accuracy"],
        overall_accuracy_ci=metrics["overall_accuracy_ci"],
        producers_accuracy=metrics["producers_accuracy"],
        users_accuracy=metrics["users_accuracy"],
        producers_accuracy_ci=metrics["producers_accuracy_ci"],
        users_accuracy_ci=metrics["users_accuracy_ci"],
        f1_per_class=metrics["f1_per_class"],
        precision_per_class=metrics["precision_per_class"],
        recall_per_class=metrics["recall_per_class"],
        quantity_disagreement=qd,
        allocation_disagreement=ad,
        kappa=kappa_val,
        kappa_ci=kappa_ci,
        area_weighted=area_weighted_result,
    )

    # --- Step 9: Build provenance ---
    raster_info = get_raster_info(classified_raster_path)
    metadata = RunMetadata(
        plugin_version=plugin_version,
        qgis_version=qgis_version,
        timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        classified_layer_path=classified_raster_path,
        classified_layer_name=raster_info.get("name", classified_raster_path),
        reference_layer_path=reference_layer_path,
        reference_layer_name=reference_layer_name,
        reference_field=reference_field,
        crs_epsg=raster_info["crs_epsg"],
        random_seed=None,
        class_mapping=class_mapping or {},
        parameters={
            "compute_kappa": compute_kappa,
            "compute_area_weighted": compute_area_weighted,
            "confidence_level": confidence_level,
            "n_classes": len(class_labels),
        },
    )

    return result, validation, metadata
