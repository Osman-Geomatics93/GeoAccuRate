"""Sampling workflow orchestrator.

Coordinates: class detection -> sample size calculation -> allocation ->
point generation -> packaging.

Depends on: core.*, domain.*.
"""

from typing import Callable, Dict, List, Optional, Tuple

from ..domain.models import SampleDesign, SampleSet
from ..domain.sample_size import (
    allocate_equal,
    allocate_proportional,
    calculate_sample_size,
)
from ..domain.sampling import generate_stratified_random
from .area_calculator import compute_class_areas_ha
from .raster_reader import count_pixels_per_class, extract_candidate_pixels


def run_sample_generation(
    raster_path: str,
    confidence_level: float = 0.95,
    expected_accuracy: float = 0.85,
    margin_of_error: float = 0.05,
    allocation_method: str = "proportional",
    min_distance_m: float = 0.0,
    seed: int = 42,
    min_per_class: int = 25,
    class_names: Optional[Dict[int, str]] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    total_n_override: Optional[int] = None,
    allocation_override: Optional[Dict[int, int]] = None,
) -> SampleSet:
    """Execute the full sampling workflow.

    Args:
        raster_path: Path to classified raster.
        confidence_level: For sample size calculation (e.g. 0.95).
        expected_accuracy: Expected OA (e.g. 0.85).
        margin_of_error: Desired margin of error (e.g. 0.05).
        allocation_method: "proportional" or "equal".
        min_distance_m: Minimum distance between samples (map units).
        seed: Random seed for reproducibility.
        min_per_class: Minimum samples per class.
        class_names: Optional {class_value: name}.
        progress_callback: Optional (step, total) progress reporter.

    Returns:
        SampleSet with generated points and metadata.
    """
    all_warnings: List[str] = []

    # Step 1: Count pixels per class
    pixel_counts = count_pixels_per_class(raster_path)
    if not pixel_counts:
        raise ValueError("No valid pixels found in classified raster")

    class_labels = sorted(pixel_counts.keys())
    total_pixels = sum(pixel_counts.values())

    # Step 2: Calculate sample size (or use override)
    if total_n_override is not None and total_n_override > 0:
        total_n = total_n_override
    else:
        total_n = calculate_sample_size(
            confidence_level=confidence_level,
            expected_accuracy=expected_accuracy,
            margin_of_error=margin_of_error,
            population_size=total_pixels,
        )

    # Step 3: Allocate samples (use override if user edited per-class counts)
    if allocation_override:
        n_per_class = {cls: allocation_override[cls] for cls in class_labels
                       if cls in allocation_override}
        total_n = sum(n_per_class.values())
    elif allocation_method == "proportional":
        n_per_class, alloc_warnings = allocate_proportional(
            total_n, pixel_counts, min_per_class=min_per_class
        )
        all_warnings.extend(alloc_warnings)
    elif allocation_method == "equal":
        n_per_class, alloc_warnings = allocate_equal(total_n, class_labels)
        all_warnings.extend(alloc_warnings)
    else:
        raise ValueError(f"Unknown allocation method: {allocation_method}")

    # Step 4: Extract candidate pixels per class
    # Use subsample rate for large rasters (>10M pixels per class)
    candidates_per_class = {}
    total_steps = len(class_labels)
    for i, cls in enumerate(class_labels):
        n_pixels = pixel_counts[cls]
        # Subsample if >10M candidates to keep memory under control
        rate = min(1.0, max(0.01, n_per_class.get(cls, 50) * 10 / n_pixels))
        candidates = extract_candidate_pixels(
            raster_path, cls, subsample_rate=rate, seed=seed
        )
        candidates_per_class[cls] = candidates

        if progress_callback:
            progress_callback(i + 1, total_steps * 2)  # first half: extraction

    # Step 5: Generate stratified random points
    points, gen_warnings = generate_stratified_random(
        candidates_per_class=candidates_per_class,
        n_per_class=n_per_class,
        min_distance=min_distance_m,
        seed=seed,
        progress_callback=(
            lambda step, total: progress_callback(total_steps + step, total_steps * 2)
            if progress_callback else None
        ),
    )
    all_warnings.extend(gen_warnings)

    # Step 6: Build strata info
    strata_info = {}
    for cls in class_labels:
        n_gen = sum(1 for p in points if p.stratum_class == cls)
        strata_info[cls] = {
            "name": class_names.get(cls, str(cls)) if class_names else str(cls),
            "pixel_count": pixel_counts[cls],
            "n_requested": n_per_class.get(cls, 0),
            "n_generated": n_gen,
        }

    design = SampleDesign(
        scheme="stratified_random",
        total_n=total_n,
        allocation=allocation_method,
        n_per_class=n_per_class,
        min_distance_m=min_distance_m,
        confidence_level=confidence_level,
        expected_accuracy=expected_accuracy,
        margin_of_error=margin_of_error,
        random_seed=seed,
    )

    return SampleSet(
        design=design,
        points=tuple(points),
        strata_info=strata_info,
        warnings=tuple(all_warnings),
    )
