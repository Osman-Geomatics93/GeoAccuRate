"""Tests for Pontius & Millones (2011) Quantity/Allocation Disagreement."""

import numpy as np
import pytest

from geoaccurate.domain.pontius import compute


class TestPontiusMetrics:
    """Test Pontius Quantity and Allocation Disagreement."""

    def test_perfect_agreement(self, perfect_matrix):
        """Perfect agreement → QD=0, AD=0."""
        qd, ad = compute(perfect_matrix)
        assert abs(qd) < 1e-10
        assert abs(ad) < 1e-10

    def test_identity_2class(self, simple_2class_matrix):
        """QD + AD must equal 1 - OA."""
        qd, ad = compute(simple_2class_matrix)
        N = simple_2class_matrix.sum()
        oa = simple_2class_matrix.diagonal().sum() / N
        assert abs(qd + ad - (1.0 - oa)) < 1e-10

    def test_identity_5class(self, asymmetric_5class_matrix):
        """QD + AD must equal 1 - OA for 5-class matrix."""
        qd, ad = compute(asymmetric_5class_matrix)
        N = asymmetric_5class_matrix.sum()
        oa = asymmetric_5class_matrix.diagonal().sum() / N
        assert abs(qd + ad - (1.0 - oa)) < 1e-10

    def test_symmetric_errors_no_quantity(self):
        """Symmetric off-diagonal errors → QD = 0, only AD."""
        # Each class has same row total and column total
        matrix = np.array([
            [40, 5, 5],
            [5, 40, 5],
            [5, 5, 40],
        ], dtype=np.int64)
        qd, ad = compute(matrix)
        # Row totals = col totals = [50, 50, 50] → no quantity difference
        assert abs(qd) < 1e-10
        assert ad > 0  # allocation errors exist

    def test_golden_3class(self, pontius_golden):
        """Verify against golden test data."""
        case = pontius_golden["test_cases"][2]  # three_class_example
        matrix = case["matrix"]
        qd, ad = compute(matrix)

        oa = matrix.diagonal().sum() / matrix.sum()
        expected_oa = case["expected_oa"]
        assert abs(oa - expected_oa) < pontius_golden["tolerance"]

        # QD + AD must equal 1 - OA
        assert abs(qd + ad - (1.0 - oa)) < 1e-10

    def test_golden_perfect(self, pontius_golden):
        """Perfect agreement golden case."""
        case = pontius_golden["test_cases"][0]  # perfect_agreement
        matrix = case["matrix"]
        qd, ad = compute(matrix)
        assert abs(qd - case["expected_qd"]) < 1e-10
        assert abs(ad - case["expected_ad"]) < 1e-10

    def test_qd_and_ad_non_negative(self):
        """QD and AD must always be >= 0."""
        rng = np.random.RandomState(123)
        for _ in range(50):
            k = rng.randint(2, 8)
            matrix = rng.randint(0, 50, size=(k, k)).astype(np.int64)
            if matrix.sum() == 0:
                continue
            qd, ad = compute(matrix)
            assert qd >= -1e-10, f"QD negative: {qd}"
            assert ad >= -1e-10, f"AD negative: {ad}"

    def test_identity_holds_random_matrices(self):
        """Identity QD + AD = 1 - OA must hold for random matrices."""
        rng = np.random.RandomState(456)
        for _ in range(100):
            k = rng.randint(2, 10)
            matrix = rng.randint(0, 100, size=(k, k)).astype(np.int64)
            if matrix.sum() == 0:
                continue
            qd, ad = compute(matrix)
            oa = matrix.diagonal().sum() / matrix.sum()
            assert abs(qd + ad - (1.0 - oa)) < 1e-9

    def test_empty_matrix_raises(self):
        matrix = np.zeros((3, 3), dtype=np.int64)
        with pytest.raises(ValueError, match="empty"):
            compute(matrix)

    def test_single_class(self):
        """Single class → QD=0, AD=0."""
        matrix = np.array([[100]], dtype=np.int64)
        qd, ad = compute(matrix)
        assert abs(qd) < 1e-10
        assert abs(ad) < 1e-10
