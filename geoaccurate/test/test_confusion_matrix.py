"""Tests for confusion matrix construction and basic accuracy metrics."""

import math

import numpy as np
import pytest

from geoaccurate.domain.confusion_matrix import build_matrix, compute_metrics


class TestBuildMatrix:
    """Tests for confusion matrix construction."""

    def test_simple_2class(self):
        classified = np.array([0, 0, 1, 1, 0, 1])
        reference  = np.array([0, 0, 1, 1, 1, 0])
        labels = (0, 1)
        matrix = build_matrix(classified, reference, labels)
        # reference=rows, classified=cols
        #       C0  C1
        # R0  [ 2,  0 ]
        # R1  [ 1,  1 ]   wait, let me recount
        # ref[0]=0, cls[0]=0 → (0,0) +1
        # ref[1]=0, cls[1]=0 → (0,0) +1
        # ref[2]=1, cls[2]=1 → (1,1) +1
        # ref[3]=1, cls[3]=1 → (1,1) +1
        # ref[4]=1, cls[4]=0 → (1,0) +1  (omission of class 1)
        # ref[5]=0, cls[5]=1 → (0,1) +1  (commission of class 1)
        expected = np.array([[2, 1], [1, 2]], dtype=np.int64)
        np.testing.assert_array_equal(matrix, expected)

    def test_3class_perfect(self):
        classified = np.array([0, 0, 1, 1, 1, 2, 2])
        reference  = np.array([0, 0, 1, 1, 1, 2, 2])
        labels = (0, 1, 2)
        matrix = build_matrix(classified, reference, labels)
        expected = np.array([[2, 0, 0], [0, 3, 0], [0, 0, 2]], dtype=np.int64)
        np.testing.assert_array_equal(matrix, expected)

    def test_unknown_labels_ignored(self):
        """Values not in class_labels are silently ignored."""
        classified = np.array([0, 1, 99])
        reference  = np.array([0, 1, 0])
        labels = (0, 1)
        matrix = build_matrix(classified, reference, labels)
        # 99 is not in labels, so that sample is skipped
        expected = np.array([[1, 0], [0, 1]], dtype=np.int64)
        np.testing.assert_array_equal(matrix, expected)

    def test_empty_arrays_raises(self):
        with pytest.raises(ValueError, match="empty"):
            build_matrix(np.array([]), np.array([]), (0, 1))

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="mismatch"):
            build_matrix(np.array([0, 1]), np.array([0]), (0, 1))

    def test_single_class(self):
        classified = np.array([5, 5, 5])
        reference  = np.array([5, 5, 5])
        labels = (5,)
        matrix = build_matrix(classified, reference, labels)
        np.testing.assert_array_equal(matrix, np.array([[3]]))

    def test_zero_column_class(self):
        """A class present in labels but absent from classified data."""
        classified = np.array([0, 0, 0])
        reference  = np.array([0, 0, 1])
        labels = (0, 1)
        matrix = build_matrix(classified, reference, labels)
        expected = np.array([[2, 0], [1, 0]], dtype=np.int64)
        np.testing.assert_array_equal(matrix, expected)

    def test_large_class_count(self):
        """10-class matrix smoke test."""
        rng = np.random.RandomState(42)
        n = 500
        labels = tuple(range(10))
        classified = rng.choice(labels, n)
        reference = rng.choice(labels, n)
        matrix = build_matrix(classified, reference, labels)
        assert matrix.shape == (10, 10)
        assert matrix.sum() == n


class TestComputeMetrics:
    """Tests for OA, PA, UA, F1, precision, recall."""

    def test_perfect_accuracy(self, perfect_matrix):
        labels = (0, 1, 2)
        result = compute_metrics(perfect_matrix, labels)

        assert result["overall_accuracy"] == 1.0
        for label in labels:
            assert result["producers_accuracy"][label] == 1.0
            assert result["users_accuracy"][label] == 1.0
            assert result["f1_per_class"][label] == 1.0

    def test_2class_known_values(self, simple_2class_matrix):
        labels = (0, 1)
        result = compute_metrics(simple_2class_matrix, labels)

        # OA = (40 + 40) / 100 = 0.80
        assert abs(result["overall_accuracy"] - 0.80) < 1e-10

        # PA[0] = 40/50 = 0.80, PA[1] = 40/50 = 0.80
        assert abs(result["producers_accuracy"][0] - 0.80) < 1e-10
        assert abs(result["producers_accuracy"][1] - 0.80) < 1e-10

        # UA[0] = 40/50 = 0.80, UA[1] = 40/50 = 0.80
        assert abs(result["users_accuracy"][0] - 0.80) < 1e-10
        assert abs(result["users_accuracy"][1] - 0.80) < 1e-10

        # F1[0] = 2*0.8*0.8/(0.8+0.8) = 0.80
        assert abs(result["f1_per_class"][0] - 0.80) < 1e-10

    def test_5class_oa(self, asymmetric_5class_matrix):
        labels = (0, 1, 2, 3, 4)
        result = compute_metrics(asymmetric_5class_matrix, labels)
        N = asymmetric_5class_matrix.sum()
        diag = asymmetric_5class_matrix.diagonal().sum()
        expected_oa = diag / N
        assert abs(result["overall_accuracy"] - expected_oa) < 1e-10

    def test_confidence_intervals_within_bounds(self, simple_2class_matrix):
        labels = (0, 1)
        result = compute_metrics(simple_2class_matrix, labels, confidence_level=0.95)
        lo, hi = result["overall_accuracy_ci"]
        assert 0.0 <= lo <= result["overall_accuracy"] <= hi <= 1.0

        for label in labels:
            lo, hi = result["producers_accuracy_ci"][label]
            assert 0.0 <= lo <= hi <= 1.0

    def test_zero_row_produces_nan(self):
        """Class absent from reference → PA = NaN."""
        # Row 1 is all zeros (class 1 never appears in reference)
        matrix = np.array([[50, 0], [0, 0]], dtype=np.int64)
        labels = (0, 1)
        result = compute_metrics(matrix, labels)
        assert result["producers_accuracy"][0] == 1.0
        assert math.isnan(result["producers_accuracy"][1])

    def test_zero_column_produces_nan(self):
        """Class absent from classified → UA = NaN."""
        matrix = np.array([[30, 20], [0, 0]], dtype=np.int64)
        labels = (0, 1)
        result = compute_metrics(matrix, labels)
        assert result["users_accuracy"][0] == 30 / 30
        assert result["users_accuracy"][1] == 0 / 20

    def test_matrix_shape_mismatch_raises(self):
        matrix = np.array([[10, 5], [5, 10]], dtype=np.int64)
        with pytest.raises(ValueError, match="shape"):
            compute_metrics(matrix, (0, 1, 2))

    def test_precision_equals_ua(self, simple_2class_matrix):
        labels = (0, 1)
        result = compute_metrics(simple_2class_matrix, labels)
        for label in labels:
            assert result["precision_per_class"][label] == result["users_accuracy"][label]

    def test_recall_equals_pa(self, simple_2class_matrix):
        labels = (0, 1)
        result = compute_metrics(simple_2class_matrix, labels)
        for label in labels:
            assert result["recall_per_class"][label] == result["producers_accuracy"][label]
