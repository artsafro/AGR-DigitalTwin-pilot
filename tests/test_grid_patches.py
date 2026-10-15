"""Synthetic contracts shared by grid producers and geometry consumers."""
import importlib
from pathlib import Path

import numpy as np
import pytest

from dt_ai.geometry import grid_patches


@pytest.fixture(params=["dt_ai.geometry.grid_patches", "dt_ai.geometry.exterior",
                        "build_exterior_surface"])
def clusterer(request, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))
    return importlib.import_module(request.param).clustered


def test_coordinate_clusters_use_full_span_not_transitive_neighbours():
    # Binary-exact values make the inclusive tolerance boundary unambiguous.
    values = np.array([0.375, 0.125, 0.0, 0.25, 0.125])
    before = values.copy()
    assert grid_patches.clustered(values, span=0.125) == {
        0.0: 0.0625, 0.125: 0.0625, 0.25: 0.3125, 0.375: 0.3125,
    }
    np.testing.assert_array_equal(values, before)


@pytest.mark.parametrize("values, span, expected", [
    ([], 0.001, {}),
    ([2, 2, -1], 0, {-1.0: -1.0, 2.0: 2.0}),
    ([-0.125, 0, 0.125], 0.125, {-0.125: -0.0625, 0.0: -0.0625, 0.125: 0.125}),
    ([0, 0.001, 0.002], 0.001, {0.0: 0.0005, 0.001: 0.0005, 0.002: 0.002}),
])
def test_coordinate_cluster_boundaries(clusterer, values, span, expected):
    assert clusterer(iter(values), span=span) == expected


@pytest.fixture(params=["dt_ai.geometry.grid_patches", "compact_floor_body",
                        "build_exterior_surface"])
def rectangle_extractor(request, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))
    return importlib.import_module(request.param).rectangles


def test_rectangles_keep_labels_holes_order_and_input(rectangle_extractor):
    mask = np.array([[7, 7, 0, 9], [7, 0, 0, 9], [7, 7, 9, 9]], dtype=np.int32)
    before = mask.copy()
    assert list(rectangle_extractor(mask)) == [
        (0, 1, 0, 2, 7), (0, 3, 3, 4, 9), (1, 3, 0, 1, 7),
        (2, 3, 1, 2, 7), (2, 3, 2, 3, 9),
    ]
    np.testing.assert_array_equal(mask, before)


@pytest.mark.parametrize("shape", [(0, 0), (0, 3), (3, 0), (2, 3)])
def test_empty_grid_has_no_rectangles(rectangle_extractor, shape):
    assert list(rectangle_extractor(np.zeros(shape, dtype=np.int32))) == []


def test_boolean_grid_coalesces_touching_cells(rectangle_extractor):
    mask = np.array([[True, True], [True, True]])
    assert list(rectangle_extractor(mask)) == [(0, 2, 0, 2, 1)]
    assert mask.all()
