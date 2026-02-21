"""Tests for confidence interval methods."""

import math

import pytest

from geoaccurate.domain.confidence import (
    kappa_ci,
    wilson_ci,
    z_score_for_confidence,
)


class TestWilsonCI:
    """Test Wilson score confidence interval."""

    def test_known_50_percent(self):
        """p=0.5, n=100: well-known interval."""
        lo, hi = wilson_ci(0.5, 100, z=1.96)
        # Expected ~(0.402, 0.598)
        assert 0.39 < lo < 0.42
        assert 0.58 < hi < 0.61

    def test_always_within_0_1(self):
        """Wilson CI must always be in [0, 1]."""
        test_cases = [
            (0.0, 100),
            (1.0, 100),
            (0.01, 10),
            (0.99, 10),
            (0.5, 1),
            (0.0, 1),
            (1.0, 1),
        ]
        for p, n in test_cases:
            lo, hi = wilson_ci(p, n)
            assert 0.0 <= lo <= hi <= 1.0, (
                f"Wilson CI out of bounds for p={p}, n={n}: [{lo}, {hi}]"
            )

    def test_zero_samples_returns_full_range(self):
        lo, hi = wilson_ci(0.5, 0)
        assert lo == 0.0
        assert hi == 1.0

    def test_p_zero(self):
        lo, hi = wilson_ci(0.0, 100)
        assert lo == 0.0
        assert hi > 0.0
        assert hi < 0.1  # should be small

    def test_p_one(self):
        lo, hi = wilson_ci(1.0, 100)
        assert lo > 0.9
        assert abs(hi - 1.0) < 1e-10

    def test_wider_ci_for_smaller_n(self):
        """Smaller sample → wider CI."""
        lo_big, hi_big = wilson_ci(0.8, 1000)
        lo_small, hi_small = wilson_ci(0.8, 20)
        width_big = hi_big - lo_big
        width_small = hi_small - lo_small
        assert width_small > width_big

    def test_higher_confidence_wider_ci(self):
        """Higher confidence level → wider CI."""
        lo_95, hi_95 = wilson_ci(0.8, 100, z=1.96)
        lo_99, hi_99 = wilson_ci(0.8, 100, z=2.576)
        assert (hi_99 - lo_99) > (hi_95 - lo_95)

    def test_symmetry_near_50(self):
        """At p=0.5, CI should be roughly symmetric."""
        lo, hi = wilson_ci(0.5, 200)
        center = (lo + hi) / 2
        assert abs(center - 0.5) < 0.01


class TestKappaCI:
    """Test Kappa confidence interval."""

    def test_positive_kappa(self):
        lo, hi = kappa_ci(0.7, 0.8, 0.5, 200)
        assert lo < 0.7 < hi

    def test_zero_n_returns_zero(self):
        lo, hi = kappa_ci(0.5, 0.6, 0.3, 0)
        assert lo == 0.0
        assert hi == 0.0

    def test_pe_one_returns_zero(self):
        lo, hi = kappa_ci(0.0, 1.0, 1.0, 100)
        assert lo == 0.0
        assert hi == 0.0


class TestZScore:
    """Test z-score lookup."""

    def test_95_percent(self):
        assert abs(z_score_for_confidence(0.95) - 1.96) < 0.001

    def test_99_percent(self):
        assert abs(z_score_for_confidence(0.99) - 2.5758) < 0.001

    def test_90_percent(self):
        assert abs(z_score_for_confidence(0.90) - 1.6449) < 0.001

    def test_arbitrary_level(self):
        """Non-standard confidence level should return reasonable z."""
        z = z_score_for_confidence(0.975)
        assert 2.0 < z < 2.5  # between 95% and 99%
