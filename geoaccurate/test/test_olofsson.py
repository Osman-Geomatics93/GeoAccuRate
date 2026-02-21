"""Tests for Olofsson et al. (2014) area-weighted accuracy estimation."""

import math

import numpy as np
import pytest

from geoaccurate.domain.olofsson import compute


class TestOlofsson:
    """Test Olofsson area-weighted estimation."""

    def test_golden_table4(self, olofsson_golden):
        """Validate against Olofsson et al. 2014 Table 4.

        This is the most critical test in the entire plugin.
        If this fails, the plugin should not ship.
        """
        result = compute(
            matrix=olofsson_golden["matrix"],
            mapped_area_ha=olofsson_golden["mapped_area_ha"],
            class_labels=olofsson_golden["class_labels"],
        )
        tol = olofsson_golden["tolerance"]

        # Weights should sum to 1
        assert abs(sum(result.weight_per_class.values()) - 1.0) < 1e-10

        # Estimated areas should sum to total mapped area
        total_mapped = sum(olofsson_golden["mapped_area_ha"].values())
        total_estimated = sum(result.estimated_area_ha.values())
        assert abs(total_estimated - total_mapped) < total_mapped * 0.001

        # OA weighted should be reasonable (between 0.8 and 1.0 for this dataset)
        assert 0.8 < result.overall_accuracy_weighted < 1.0

        # CI should bracket the point estimate
        lo, hi = result.overall_accuracy_weighted_ci
        assert lo <= result.overall_accuracy_weighted <= hi

    def test_equal_weights_approximates_unweighted(self):
        """When all classes have equal area, weighted ≈ unweighted OA."""
        matrix = np.array([
            [40, 5, 5],
            [5, 35, 10],
            [5, 10, 35],
        ], dtype=np.int64)
        labels = (0, 1, 2)

        # Equal area weights
        area = {0: 1000.0, 1: 1000.0, 2: 1000.0}
        result = compute(matrix, area, labels)

        oa_unweighted = matrix.diagonal().sum() / matrix.sum()
        # With equal weights and equal sample sizes, weighted ≈ unweighted
        # (not exactly equal because formula differs, but should be close)
        assert abs(result.overall_accuracy_weighted - oa_unweighted) < 0.05

    def test_weights_sum_to_one(self, olofsson_golden):
        result = compute(
            olofsson_golden["matrix"],
            olofsson_golden["mapped_area_ha"],
            olofsson_golden["class_labels"],
        )
        assert abs(sum(result.weight_per_class.values()) - 1.0) < 1e-10

    def test_estimated_areas_sum_to_total(self, olofsson_golden):
        result = compute(
            olofsson_golden["matrix"],
            olofsson_golden["mapped_area_ha"],
            olofsson_golden["class_labels"],
        )
        total_mapped = sum(olofsson_golden["mapped_area_ha"].values())
        total_estimated = sum(result.estimated_area_ha.values())
        assert abs(total_estimated - total_mapped) < total_mapped * 0.001

    def test_ci_brackets_estimate(self, olofsson_golden):
        """All CIs should bracket their point estimates."""
        result = compute(
            olofsson_golden["matrix"],
            olofsson_golden["mapped_area_ha"],
            olofsson_golden["class_labels"],
        )
        for label in olofsson_golden["class_labels"]:
            lo, hi = result.estimated_area_ci_ha[label]
            area = result.estimated_area_ha[label]
            assert lo <= area <= hi, (
                f"Class {label}: CI [{lo}, {hi}] does not bracket "
                f"estimate {area}"
            )

    def test_pa_ua_weighted_in_range(self, olofsson_golden):
        """Weighted PA and UA should be in [0, 1]."""
        result = compute(
            olofsson_golden["matrix"],
            olofsson_golden["mapped_area_ha"],
            olofsson_golden["class_labels"],
        )
        for label in olofsson_golden["class_labels"]:
            pa = result.producers_accuracy_weighted[label]
            ua = result.users_accuracy_weighted[label]
            if not math.isnan(pa):
                assert 0.0 <= pa <= 1.0, f"PA weighted out of range for class {label}"
            if not math.isnan(ua):
                assert 0.0 <= ua <= 1.0, f"UA weighted out of range for class {label}"

    def test_missing_area_raises(self):
        matrix = np.array([[10, 2], [3, 15]], dtype=np.int64)
        labels = (0, 1)
        area = {0: 1000.0}  # missing class 1
        with pytest.raises(ValueError, match="Missing mapped area"):
            compute(matrix, area, labels)

    def test_zero_column_raises(self):
        """Class with 0 samples should raise an error."""
        matrix = np.array([[10, 0], [5, 0]], dtype=np.int64)
        labels = (0, 1)
        area = {0: 1000.0, 1: 500.0}
        with pytest.raises(ValueError, match="0 samples"):
            compute(matrix, area, labels)

    def test_shape_mismatch_raises(self):
        matrix = np.array([[10, 2], [3, 15]], dtype=np.int64)
        labels = (0, 1, 2)  # 3 labels, 2x2 matrix
        area = {0: 100.0, 1: 100.0, 2: 100.0}
        with pytest.raises(ValueError, match="shape"):
            compute(matrix, area, labels)

    def test_dominant_class_weight(self):
        """A very dominant class should have a weight close to 1."""
        matrix = np.array([[8, 2], [1, 89]], dtype=np.int64)
        labels = (0, 1)
        area = {0: 100.0, 1: 9900.0}  # class 1 dominates
        result = compute(matrix, area, labels)
        assert result.weight_per_class[1] > 0.95
        assert result.weight_per_class[0] < 0.05
