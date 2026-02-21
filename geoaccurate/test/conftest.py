"""Test configuration for GeoAccuRate.

Domain-layer tests (test_confusion_matrix, test_pontius, etc.) run with
plain pytest — no QGIS needed. Integration tests require pytest-qgis.
"""

import json
import os
import sys

import numpy as np
import pytest

# Add plugin root to path so domain imports work
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


@pytest.fixture
def olofsson_golden():
    """Load Olofsson et al. 2014 Table 4 golden test data."""
    path = os.path.join(GOLDEN_DIR, "olofsson_table4.json")
    with open(path) as f:
        data = json.load(f)
    data["matrix"] = np.array(data["matrix"], dtype=np.int64)
    data["class_labels"] = tuple(data["class_labels"])
    # Convert string keys to int for mapped_area_ha
    data["mapped_area_ha"] = {
        int(k): v for k, v in data["mapped_area_ha"].items()
    }
    return data


@pytest.fixture
def pontius_golden():
    """Load Pontius & Millones 2011 golden test data."""
    path = os.path.join(GOLDEN_DIR, "pontius_example.json")
    with open(path) as f:
        data = json.load(f)
    for case in data["test_cases"]:
        case["matrix"] = np.array(case["matrix"], dtype=np.int64)
    return data


@pytest.fixture
def simple_2class_matrix():
    """Simple 2-class confusion matrix for basic tests."""
    # 80% overall accuracy
    # Reference=rows, Classified=cols
    #          Classified
    #            C0   C1
    # Ref  R0 [ 40,  10 ]
    #      R1 [ 10,  40 ]
    return np.array([[40, 10], [10, 40]], dtype=np.int64)


@pytest.fixture
def perfect_matrix():
    """Perfect 3-class confusion matrix (100% accuracy)."""
    return np.array([[50, 0, 0], [0, 30, 0], [0, 0, 20]], dtype=np.int64)


@pytest.fixture
def asymmetric_5class_matrix():
    """Realistic 5-class matrix with varied accuracy."""
    return np.array([
        [45,  3,  1,  0,  1],   # Forest: PA = 90%
        [ 2, 28,  4,  1,  0],   # Urban: PA = 80%
        [ 1,  2, 15,  1,  1],   # Water: PA = 75%
        [ 3,  1,  2, 38,  1],   # Crop: PA = 84%
        [ 0,  1,  0,  2, 12],   # Bare: PA = 80%
    ], dtype=np.int64)
