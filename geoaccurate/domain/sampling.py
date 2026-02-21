"""Stratified random sampling point generation.

Generates sample points within raster strata (class regions).
Uses minimum distance constraints with optional k-d tree acceleration.

No QGIS or Qt imports. Only depends on: numpy, typing.
scipy.spatial.cKDTree used if available, with brute-force fallback.
"""

from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from .models import SamplePoint

# Try to import scipy for fast distance checking
try:
    from scipy.spatial import cKDTree

    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


def generate_stratified_random(
    candidates_per_class: Dict[int, np.ndarray],
    n_per_class: Dict[int, int],
    min_distance: float = 0.0,
    seed: int = 42,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> Tuple[List[SamplePoint], List[str]]:
    """Generate stratified random sample points from candidate coordinates.

    Args:
        candidates_per_class: {class_value: Nx2 array of (x, y) coordinates}
            These are pixel center coordinates belonging to each class.
        n_per_class: {class_value: desired sample count}.
        min_distance: Minimum distance between any two selected points (map units).
        seed: Random seed for reproducibility.
        progress_callback: Optional (current, total) progress reporter.

    Returns:
        (list of SamplePoints, list of warning messages)
    """
    rng = np.random.RandomState(seed)
    all_selected_coords: List[np.ndarray] = []
    all_points: List[SamplePoint] = []
    warnings: List[str] = []
    point_id = 1

    classes = sorted(n_per_class.keys())
    total_classes = len(classes)

    for cls_idx, class_val in enumerate(classes):
        if class_val not in candidates_per_class:
            warnings.append(
                f"Class {class_val}: no candidate pixels found. "
                f"0 of {n_per_class[class_val]} samples generated."
            )
            if progress_callback:
                progress_callback(cls_idx + 1, total_classes)
            continue

        coords = candidates_per_class[class_val].copy()
        n_desired = n_per_class[class_val]

        if len(coords) == 0:
            warnings.append(
                f"Class {class_val}: no candidate pixels. "
                f"0 of {n_desired} samples generated."
            )
            if progress_callback:
                progress_callback(cls_idx + 1, total_classes)
            continue

        # Shuffle candidates
        indices = rng.permutation(len(coords))
        coords = coords[indices]

        selected = []

        if min_distance > 0:
            selected = _select_with_distance(
                coords, n_desired, min_distance, all_selected_coords
            )
        else:
            selected = coords[:n_desired].tolist()

        if len(selected) < n_desired:
            warnings.append(
                f"Class {class_val}: only {len(selected)} of {n_desired} "
                f"samples generated (insufficient candidates or "
                f"distance constraint too strict)."
            )

        for xy in selected:
            coord = np.array(xy)
            all_selected_coords.append(coord)
            all_points.append(SamplePoint(
                id=point_id,
                x=float(coord[0]),
                y=float(coord[1]),
                stratum_class=class_val,
            ))
            point_id += 1

        if progress_callback:
            progress_callback(cls_idx + 1, total_classes)

    return all_points, warnings


def _select_with_distance(
    candidates: np.ndarray,
    n_desired: int,
    min_distance: float,
    existing_points: List[np.ndarray],
) -> List[list]:
    """Select points with minimum distance constraint.

    Uses scipy cKDTree if available for O(n log n) queries,
    falls back to brute-force O(n*m) otherwise.
    """
    selected: List[np.ndarray] = []

    if _HAS_SCIPY and existing_points:
        # Build tree from existing points for fast distance queries
        existing_arr = np.array(existing_points)
        tree = cKDTree(existing_arr)
    else:
        tree = None

    for i in range(len(candidates)):
        coord = candidates[i]

        if len(selected) >= n_desired:
            break

        # Check distance against previously selected (within this class)
        ok = True
        for prev in selected:
            dist = np.sqrt((coord[0] - prev[0]) ** 2 + (coord[1] - prev[1]) ** 2)
            if dist < min_distance:
                ok = False
                break

        if not ok:
            continue

        # Check against globally selected (other classes)
        if tree is not None:
            dist_to_existing, _ = tree.query(coord)
            if dist_to_existing < min_distance:
                continue
        elif existing_points:
            # Brute-force fallback
            for prev in existing_points:
                dist = np.sqrt(
                    (coord[0] - prev[0]) ** 2 + (coord[1] - prev[1]) ** 2
                )
                if dist < min_distance:
                    ok = False
                    break
            if not ok:
                continue

        selected.append(coord)

    return [s.tolist() for s in selected]
