"""Domain data models for GeoAccuRate.

All models are frozen dataclasses (immutable once created).
This module has ZERO imports from qgis.* or PyQt5.*.
Only depends on: numpy, typing, dataclasses.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Sampling models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SampleDesign:
    """Configuration for a sample generation run."""
    scheme: str                       # "stratified_random"
    total_n: int
    allocation: str                   # "proportional" | "equal"
    n_per_class: Dict[int, int]       # class_value -> sample count
    min_distance_m: float
    confidence_level: float           # e.g. 0.95
    expected_accuracy: float          # e.g. 0.85
    margin_of_error: float            # e.g. 0.05
    random_seed: int


@dataclass(frozen=True)
class SamplePoint:
    """A single sample location."""
    id: int
    x: float
    y: float
    stratum_class: int


@dataclass(frozen=True)
class SampleSet:
    """Result of a sample generation run."""
    design: SampleDesign
    points: Tuple[SamplePoint, ...]
    strata_info: Dict[int, dict]      # class -> {name, pixel_count, n_generated}
    warnings: Tuple[str, ...]         # e.g. "Only 18/25 for Water"


# ---------------------------------------------------------------------------
# Area-weighted accuracy (Olofsson et al. 2014)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AreaWeightedResult:
    """Olofsson et al. (2014) area-weighted accuracy estimates."""
    weight_per_class: Dict[int, float]
    estimated_area_ha: Dict[int, float]
    estimated_area_ci_ha: Dict[int, Tuple[float, float]]
    overall_accuracy_weighted: float
    overall_accuracy_weighted_ci: Tuple[float, float]
    producers_accuracy_weighted: Dict[int, float]
    users_accuracy_weighted: Dict[int, float]
    mapped_area_ha: Dict[int, float]


# ---------------------------------------------------------------------------
# Confusion matrix and categorical accuracy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfusionMatrixResult:
    """Complete categorical accuracy assessment result."""
    matrix: np.ndarray                # (k x k), reference=rows, classified=columns
    class_labels: Tuple[int, ...]
    class_names: Dict[int, str]
    n_samples: int
    n_excluded_nodata: int

    # Global metrics
    overall_accuracy: float
    overall_accuracy_ci: Tuple[float, float]

    # Per-class metrics
    producers_accuracy: Dict[int, float]
    users_accuracy: Dict[int, float]
    producers_accuracy_ci: Dict[int, Tuple[float, float]]
    users_accuracy_ci: Dict[int, Tuple[float, float]]
    f1_per_class: Dict[int, float]
    precision_per_class: Dict[int, float]       # = UA
    recall_per_class: Dict[int, float]          # = PA

    # Pontius metrics
    quantity_disagreement: float
    allocation_disagreement: float

    # Optional metrics
    kappa: Optional[float] = None
    kappa_ci: Optional[Tuple[float, float]] = None
    area_weighted: Optional[AreaWeightedResult] = None


# ---------------------------------------------------------------------------
# Provenance (lightweight, no database)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunMetadata:
    """Lightweight provenance record. Serialized to JSON alongside reports."""
    plugin_version: str
    qgis_version: str
    timestamp: str                    # ISO 8601
    classified_layer_path: str
    classified_layer_name: str
    reference_layer_path: str
    reference_layer_name: str
    reference_field: str
    crs_epsg: int
    random_seed: Optional[int]
    class_mapping: Dict[int, int]
    parameters: Dict[str, Any]


# ---------------------------------------------------------------------------
# Report content
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportContent:
    """Everything needed to generate a PDF report."""
    metadata: RunMetadata
    result: ConfusionMatrixResult
    title: str
    author: str
    validation_warnings: Tuple[str, ...] = ()
    project_name: str = ""
