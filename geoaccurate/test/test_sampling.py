"""Tests for sample size calculation, allocation, and point generation."""

import numpy as np
import pytest

from geoaccurate.domain.sample_size import (
    allocate_equal,
    allocate_proportional,
    calculate_sample_size,
)
from geoaccurate.domain.sampling import generate_stratified_random


class TestSampleSize:
    """Test sample size calculator."""

    def test_known_values(self):
        """p=0.85, E=0.05, 95% CI → n=196 (standard textbook result)."""
        n = calculate_sample_size(
            confidence_level=0.95,
            expected_accuracy=0.85,
            margin_of_error=0.05,
        )
        assert n == 196

    def test_p50_is_maximum(self):
        """p=0.5 gives maximum sample size for given E and CI."""
        n_50 = calculate_sample_size(0.95, 0.50, 0.05)
        n_85 = calculate_sample_size(0.95, 0.85, 0.05)
        n_95 = calculate_sample_size(0.95, 0.95, 0.05)
        assert n_50 > n_85
        assert n_50 > n_95

    def test_higher_confidence_larger_n(self):
        n_95 = calculate_sample_size(0.95, 0.85, 0.05)
        n_99 = calculate_sample_size(0.99, 0.85, 0.05)
        assert n_99 > n_95

    def test_smaller_margin_larger_n(self):
        n_5 = calculate_sample_size(0.95, 0.85, 0.05)
        n_3 = calculate_sample_size(0.95, 0.85, 0.03)
        assert n_3 > n_5

    def test_finite_population_reduces_n(self):
        n_inf = calculate_sample_size(0.95, 0.85, 0.05, population_size=0)
        n_fin = calculate_sample_size(0.95, 0.85, 0.05, population_size=1000)
        assert n_fin < n_inf

    def test_invalid_accuracy_raises(self):
        with pytest.raises(ValueError):
            calculate_sample_size(0.95, 0.0, 0.05)
        with pytest.raises(ValueError):
            calculate_sample_size(0.95, 1.0, 0.05)

    def test_invalid_margin_raises(self):
        with pytest.raises(ValueError):
            calculate_sample_size(0.95, 0.85, 0.0)


class TestAllocation:
    """Test proportional and equal allocation."""

    def test_proportional_basic(self):
        counts = {1: 4000, 2: 3000, 3: 2000, 4: 1000}
        alloc, warnings = allocate_proportional(200, counts)
        # All classes should get some samples
        for label in counts:
            assert alloc[label] > 0

    def test_proportional_min_per_class_warning(self):
        """Small class should trigger minimum-per-class adjustment."""
        counts = {1: 9000, 2: 900, 3: 100}
        alloc, warnings = allocate_proportional(100, counts, min_per_class=25)
        # Class 3 has only 1% of pixels → proportional would give ~1 sample
        # Should be bumped to 25 (or max available if fewer pixels)
        assert alloc[3] >= min(25, counts[3])
        assert len(warnings) > 0

    def test_equal_basic(self):
        labels = [1, 2, 3, 4]
        alloc, warnings = allocate_equal(200, labels)
        assert alloc[1] == 50
        assert alloc[2] == 50
        assert alloc[3] == 50
        assert alloc[4] == 50

    def test_equal_remainder(self):
        labels = [1, 2, 3]
        alloc, warnings = allocate_equal(100, labels)
        assert sum(alloc.values()) == 100

    def test_equal_low_n_warning(self):
        labels = [1, 2, 3, 4]
        alloc, warnings = allocate_equal(80, labels)
        assert len(warnings) > 0  # 20 < 25 minimum

    def test_proportional_empty_raises(self):
        with pytest.raises(ValueError):
            allocate_proportional(100, {})


class TestStratifiedRandomSampling:
    """Test stratified random point generation."""

    def test_correct_count(self):
        """Generates correct number of points per class."""
        candidates = {
            1: np.array([[i, 0] for i in range(100)], dtype=float),
            2: np.array([[i, 100] for i in range(100)], dtype=float),
        }
        n_per_class = {1: 20, 2: 30}
        points, warnings = generate_stratified_random(
            candidates, n_per_class, seed=42
        )
        class_counts = {}
        for p in points:
            class_counts[p.stratum_class] = class_counts.get(p.stratum_class, 0) + 1
        assert class_counts[1] == 20
        assert class_counts[2] == 30

    def test_reproducibility(self):
        """Same seed → same points."""
        candidates = {
            1: np.array([[i, j] for i in range(50) for j in range(50)], dtype=float),
        }
        n_per_class = {1: 25}

        points_a, _ = generate_stratified_random(candidates, n_per_class, seed=42)
        points_b, _ = generate_stratified_random(candidates, n_per_class, seed=42)

        for a, b in zip(points_a, points_b):
            assert a.x == b.x
            assert a.y == b.y

    def test_different_seed_different_points(self):
        candidates = {
            1: np.array([[i, j] for i in range(50) for j in range(50)], dtype=float),
        }
        n_per_class = {1: 25}

        points_a, _ = generate_stratified_random(candidates, n_per_class, seed=42)
        points_b, _ = generate_stratified_random(candidates, n_per_class, seed=99)

        coords_a = {(p.x, p.y) for p in points_a}
        coords_b = {(p.x, p.y) for p in points_b}
        assert coords_a != coords_b

    def test_min_distance_respected(self):
        """All points must be at least min_distance apart."""
        candidates = {
            1: np.array(
                [[i * 10, j * 10] for i in range(100) for j in range(100)],
                dtype=float,
            ),
        }
        n_per_class = {1: 50}
        min_dist = 15.0

        points, _ = generate_stratified_random(
            candidates, n_per_class, min_distance=min_dist, seed=42
        )

        # Check all pairwise distances
        coords = np.array([[p.x, p.y] for p in points])
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                dist = np.sqrt(np.sum((coords[i] - coords[j]) ** 2))
                assert dist >= min_dist - 1e-6, (
                    f"Points {i} and {j} are {dist:.2f} apart "
                    f"(min_distance={min_dist})"
                )

    def test_insufficient_candidates_warning(self):
        """Warning when fewer candidates than requested samples."""
        candidates = {1: np.array([[0, 0], [10, 10]], dtype=float)}
        n_per_class = {1: 50}
        points, warnings = generate_stratified_random(
            candidates, n_per_class, seed=42
        )
        assert len(points) == 2  # only 2 candidates available
        assert len(warnings) > 0
        assert "only 2 of 50" in warnings[0].lower()

    def test_missing_class_warning(self):
        """Warning when a class has no candidates."""
        candidates = {1: np.array([[0, 0]], dtype=float)}
        n_per_class = {1: 1, 2: 5}  # class 2 has no candidates
        points, warnings = generate_stratified_random(
            candidates, n_per_class, seed=42
        )
        assert len(warnings) > 0

    def test_point_ids_sequential(self):
        candidates = {
            1: np.array([[i, 0] for i in range(50)], dtype=float),
            2: np.array([[i, 50] for i in range(50)], dtype=float),
        }
        n_per_class = {1: 10, 2: 10}
        points, _ = generate_stratified_random(candidates, n_per_class, seed=42)
        ids = [p.id for p in points]
        assert ids == list(range(1, 21))
