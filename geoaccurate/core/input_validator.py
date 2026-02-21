"""Input validation for GeoAccuRate.

Validates layers, CRS, fields, and class mappings before analysis.
Returns structured validation results (never silently proceeds).

Depends on: core.raster_reader.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .raster_reader import get_raster_info


@dataclass
class ValidationIssue:
    """A single validation finding."""
    severity: str     # 'FATAL' | 'ERROR' | 'WARNING'
    message: str
    suggestion: str = ""


@dataclass
class ValidationResult:
    """Aggregated validation result."""
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "FATAL" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "WARNING" for i in self.issues)

    @property
    def fatal_issues(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "FATAL"]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]


def validate_accuracy_inputs(
    classified_raster_path: str,
    reference_classes: Set[int],
    classified_classes: Set[int],
    n_reference_samples: int,
    n_excluded_nodata: int,
    area_weighted: bool = True,
    min_samples_per_class: int = 25,
    class_sample_counts: Optional[Dict[int, int]] = None,
) -> ValidationResult:
    """Validate inputs for categorical accuracy assessment.

    Args:
        classified_raster_path: Path to classified raster.
        reference_classes: Set of class values in reference data.
        classified_classes: Set of class values in classified data (at sample points).
        n_reference_samples: Total number of valid reference samples.
        n_excluded_nodata: Number of samples excluded due to nodata.
        area_weighted: Whether area-weighted analysis is requested.
        min_samples_per_class: Minimum recommended samples per class.
        class_sample_counts: {class_value: sample_count} for per-class checking.

    Returns:
        ValidationResult with issues.
    """
    result = ValidationResult()

    # Check raster exists and is readable
    try:
        info = get_raster_info(classified_raster_path)
    except FileNotFoundError:
        result.issues.append(ValidationIssue(
            severity="FATAL",
            message=f"Cannot open classified raster: {classified_raster_path}",
        ))
        return result

    # CRS check for area-weighted analysis
    if area_weighted and info["crs_is_geographic"]:
        result.issues.append(ValidationIssue(
            severity="FATAL",
            message=(
                f"Area-weighted analysis requires projected CRS. "
                f"Raster CRS is EPSG:{info['crs_epsg']} (geographic/degrees)."
            ),
            suggestion=(
                "Reproject the raster to a projected CRS (e.g., UTM), "
                "or disable area-weighted analysis."
            ),
        ))

    # Sample count check
    if n_reference_samples == 0:
        result.issues.append(ValidationIssue(
            severity="FATAL",
            message="No valid reference samples after nodata exclusion.",
        ))
        return result

    # Nodata exclusion notice
    if n_excluded_nodata > 0:
        pct = n_excluded_nodata / (n_reference_samples + n_excluded_nodata) * 100
        result.issues.append(ValidationIssue(
            severity="WARNING",
            message=(
                f"{n_excluded_nodata} of {n_reference_samples + n_excluded_nodata} "
                f"samples excluded (nodata) ({pct:.1f}%)."
            ),
        ))

    # Class mismatch check
    ref_only = reference_classes - classified_classes
    cls_only = classified_classes - reference_classes
    if ref_only:
        result.issues.append(ValidationIssue(
            severity="WARNING",
            message=(
                f"Reference classes {ref_only} not found in classified data "
                f"at sample locations."
            ),
            suggestion="These classes will have 0 user's accuracy.",
        ))
    if cls_only:
        result.issues.append(ValidationIssue(
            severity="WARNING",
            message=(
                f"Classified classes {cls_only} not found in reference data."
            ),
            suggestion="These classes will have 0 producer's accuracy.",
        ))

    # Per-class sample count warnings
    if class_sample_counts:
        for cls_val, count in class_sample_counts.items():
            if count < min_samples_per_class:
                result.issues.append(ValidationIssue(
                    severity="WARNING",
                    message=(
                        f"Class {cls_val} has only {count} reference samples. "
                        f"Minimum recommended: {min_samples_per_class}."
                    ),
                    suggestion=(
                        "Per-class metrics may be unreliable. Consider "
                        "collecting more reference data for this class."
                    ),
                ))

    return result
