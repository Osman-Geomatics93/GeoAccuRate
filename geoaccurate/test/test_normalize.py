"""Tests for normalize_confusion_matrix()."""

import numpy as np
import pytest

from domain.confusion_matrix import normalize_confusion_matrix


class TestNormalizeConfusionMatrix:
    """Tests for row/column normalization of confusion matrices."""

    def test_simple_2class_row_normalize(self, simple_2class_matrix):
        """Row-normalized 2-class matrix should have rows summing to 100."""
        norm = normalize_confusion_matrix(simple_2class_matrix, axis=1)
        assert norm.shape == (2, 2)
        np.testing.assert_allclose(norm.sum(axis=1), [100.0, 100.0])
        # Row 0: 40/(40+10)=80%, 10/(40+10)=20%
        np.testing.assert_allclose(norm[0], [80.0, 20.0])
        np.testing.assert_allclose(norm[1], [20.0, 80.0])

    def test_perfect_matrix_row_normalize(self, perfect_matrix):
        """Perfect diagonal matrix: each diagonal cell should be 100%."""
        norm = normalize_confusion_matrix(perfect_matrix, axis=1)
        assert norm.shape == (3, 3)
        np.testing.assert_allclose(norm.sum(axis=1), [100.0, 100.0, 100.0])
        np.testing.assert_allclose(np.diag(norm), [100.0, 100.0, 100.0])
        # Off-diagonal should be 0
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert norm[i, j] == pytest.approx(0.0)

    def test_asymmetric_5class_row_normalize(self, asymmetric_5class_matrix):
        """5-class matrix rows should each sum to 100."""
        norm = normalize_confusion_matrix(asymmetric_5class_matrix, axis=1)
        assert norm.shape == (5, 5)
        np.testing.assert_allclose(norm.sum(axis=1), np.full(5, 100.0), atol=1e-10)
        # Spot check: row 0 total = 45+3+1+0+1 = 50, so cell[0,0] = 90%
        assert norm[0, 0] == pytest.approx(90.0)

    def test_zero_row_produces_zeros(self):
        """A row with all zeros should normalize to all zeros (no NaN/Inf)."""
        matrix = np.array([[10, 5], [0, 0]], dtype=np.int64)
        norm = normalize_confusion_matrix(matrix, axis=1)
        np.testing.assert_allclose(norm[0], [100.0 * 10 / 15, 100.0 * 5 / 15])
        np.testing.assert_allclose(norm[1], [0.0, 0.0])
        assert not np.any(np.isnan(norm))
        assert not np.any(np.isinf(norm))

    def test_column_normalize(self, simple_2class_matrix):
        """Column normalization (axis=0) should have columns summing to 100."""
        norm = normalize_confusion_matrix(simple_2class_matrix, axis=0)
        assert norm.shape == (2, 2)
        np.testing.assert_allclose(norm.sum(axis=0), [100.0, 100.0])
        # Col 0: 40/(40+10)=80%, 10/(40+10)=20%
        np.testing.assert_allclose(norm[:, 0], [80.0, 20.0])

    def test_all_zero_matrix(self):
        """Entirely zero matrix should produce all zeros."""
        matrix = np.zeros((3, 3), dtype=np.int64)
        norm = normalize_confusion_matrix(matrix, axis=1)
        np.testing.assert_allclose(norm, np.zeros((3, 3)))
        assert not np.any(np.isnan(norm))
        assert not np.any(np.isinf(norm))
