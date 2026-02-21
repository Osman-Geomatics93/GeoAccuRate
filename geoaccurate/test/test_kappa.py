"""Tests for Cohen's Kappa coefficient."""

import numpy as np
import pytest

from geoaccurate.domain.kappa import compute


class TestKappa:
    """Test Cohen's Kappa computation."""

    def test_perfect_agreement(self, perfect_matrix):
        """Perfect agreement → Kappa = 1."""
        kappa, ci = compute(perfect_matrix)
        assert abs(kappa - 1.0) < 1e-10

    def test_known_2class(self, simple_2class_matrix):
        """Known 2-class matrix: hand-calculated Kappa."""
        # OA = 0.80
        # p_e = (50*50 + 50*50) / 10000 = 5000/10000 = 0.50
        # Kappa = (0.80 - 0.50) / (1 - 0.50) = 0.60
        kappa, ci = compute(simple_2class_matrix)
        assert abs(kappa - 0.60) < 1e-10

    def test_kappa_range(self, asymmetric_5class_matrix):
        """Kappa should be in [-1, 1] for typical matrices."""
        kappa, ci = compute(asymmetric_5class_matrix)
        assert -1.0 <= kappa <= 1.0

    def test_ci_brackets_kappa(self, asymmetric_5class_matrix):
        kappa, (lo, hi) = compute(asymmetric_5class_matrix)
        assert lo <= kappa <= hi

    def test_random_agreement_kappa_near_zero(self):
        """Random predictions → Kappa near 0."""
        rng = np.random.RandomState(42)
        matrix = rng.randint(10, 50, size=(3, 3)).astype(np.int64)
        # Force equal row/col totals roughly
        kappa, ci = compute(matrix)
        # Random agreement → Kappa should be small (positive or negative)
        assert abs(kappa) < 0.5

    def test_empty_matrix_raises(self):
        matrix = np.zeros((2, 2), dtype=np.int64)
        with pytest.raises(ValueError, match="empty"):
            compute(matrix)

    def test_single_class(self):
        """Single class → degenerate. p_e = 1, Kappa = 0."""
        matrix = np.array([[100]], dtype=np.int64)
        kappa, ci = compute(matrix)
        assert kappa == 0.0

    def test_complete_disagreement(self):
        """All off-diagonal → Kappa < 0."""
        matrix = np.array([[0, 50], [50, 0]], dtype=np.int64)
        kappa, ci = compute(matrix)
        assert kappa < 0
