"""Sample size calculation and allocation strategies.

Implements the multinomial sampling formula (Cochran 1977) and
allocation strategies (proportional, equal) with minimum-per-class
enforcement.

No QGIS or Qt imports. Only depends on: math, typing.
"""

import math
from typing import Dict, List, Tuple

from .confidence import z_score_for_confidence


def calculate_sample_size(
    confidence_level: float = 0.95,
    expected_accuracy: float = 0.85,
    margin_of_error: float = 0.05,
    population_size: int = 0,
) -> int:
    """Calculate total sample size using Cochran's formula.

    n = (z^2 * p * (1-p)) / E^2

    Optionally applies finite population correction.

    Args:
        confidence_level: e.g. 0.95 for 95% confidence.
        expected_accuracy: Expected overall accuracy, e.g. 0.85.
        margin_of_error: Desired margin of error, e.g. 0.05.
        population_size: Total pixels (0 = infinite population).

    Returns:
        Required sample size (integer, rounded up).
    """
    if not 0 < expected_accuracy < 1:
        raise ValueError(
            f"expected_accuracy must be in (0, 1), got {expected_accuracy}"
        )
    if not 0 < margin_of_error < 1:
        raise ValueError(
            f"margin_of_error must be in (0, 1), got {margin_of_error}"
        )
    if not 0 < confidence_level < 1:
        raise ValueError(
            f"confidence_level must be in (0, 1), got {confidence_level}"
        )

    z = z_score_for_confidence(confidence_level)
    p = expected_accuracy
    E = margin_of_error

    n = (z ** 2 * p * (1 - p)) / (E ** 2)

    # Finite population correction
    if population_size > 0:
        n = n / (1 + n / population_size)

    return math.ceil(n)


def allocate_proportional(
    total_n: int,
    class_pixel_counts: Dict[int, int],
    min_per_class: int = 25,
) -> Tuple[Dict[int, int], List[str]]:
    """Allocate samples proportionally to class area.

    Enforces minimum samples per class. If proportional allocation
    gives a class fewer than min_per_class, that class is bumped up
    and others are adjusted proportionally.

    Args:
        total_n: Total number of samples.
        class_pixel_counts: {class_value: pixel_count}.
        min_per_class: Minimum samples per class (default 25,
                       per Olofsson et al. 2014 recommendation).

    Returns:
        ({class_value: n_samples}, [warning_messages])
    """
    if not class_pixel_counts:
        raise ValueError("No classes provided")

    warnings = []
    total_pixels = sum(class_pixel_counts.values())
    if total_pixels == 0:
        raise ValueError("Total pixel count is zero")

    k = len(class_pixel_counts)
    labels = sorted(class_pixel_counts.keys())

    # Initial proportional allocation
    allocation = {}
    for label in labels:
        prop = class_pixel_counts[label] / total_pixels
        allocation[label] = max(1, round(total_n * prop))

    # Enforce minimum per class
    bumped_classes = []
    for label in labels:
        if allocation[label] < min_per_class:
            if class_pixel_counts[label] >= min_per_class:
                bumped_classes.append(label)
                allocation[label] = min_per_class
            else:
                # Not enough pixels for min_per_class
                allocation[label] = class_pixel_counts[label]
                warnings.append(
                    f"Class {label}: only {class_pixel_counts[label]} pixels "
                    f"available (< {min_per_class} minimum). "
                    f"Allocating all available pixels."
                )

    if bumped_classes:
        warnings.append(
            f"Classes {bumped_classes} bumped to minimum {min_per_class} "
            f"samples (proportional allocation was lower)."
        )

    # Adjust total: ensure sum matches total_n (redistribute excess/deficit)
    current_total = sum(allocation.values())
    if current_total != total_n and current_total > 0:
        # Only adjust non-bumped classes
        adjustable = [
            l for l in labels
            if l not in bumped_classes
            and allocation[l] > min_per_class
        ]
        diff = total_n - current_total
        if adjustable and diff != 0:
            adjustable_total = sum(allocation[l] for l in adjustable)
            if adjustable_total > 0:
                for label in adjustable:
                    share = allocation[label] / adjustable_total
                    allocation[label] += round(diff * share)
                    allocation[label] = max(1, allocation[label])

    return allocation, warnings


def allocate_equal(
    total_n: int,
    class_labels: List[int],
) -> Tuple[Dict[int, int], List[str]]:
    """Allocate samples equally across classes.

    Args:
        total_n: Total number of samples.
        class_labels: List of class values.

    Returns:
        ({class_value: n_samples}, [warning_messages])
    """
    if not class_labels:
        raise ValueError("No classes provided")

    warnings = []
    k = len(class_labels)
    base = total_n // k
    remainder = total_n % k

    allocation = {}
    for i, label in enumerate(sorted(class_labels)):
        allocation[label] = base + (1 if i < remainder else 0)

    if base < 25:
        warnings.append(
            f"Equal allocation gives {base} samples per class. "
            f"Minimum recommended is 25 (Olofsson et al. 2014)."
        )

    return allocation, warnings
