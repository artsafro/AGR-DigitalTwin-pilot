import numpy as np

import run as trial


def test_raster_edges_are_on_dark_side_without_crop_boundary():
    luma = np.ones((5, 10))
    luma[:, 2:8] = 0.5
    luma[:, 5] = 0.55
    edges = trial.raster_edges(luma)
    assert list(np.flatnonzero(edges[2])) == [2, 7]
    assert not edges[:, 3:7].any()
    assert np.array_equal(edges[:, ::-1], trial.raster_edges(luma[:, ::-1]))


def test_class_edges_retain_silhouette_even_without_windows():
    hit = np.zeros((7, 9), np.int8)
    hit[1:6, 2:7] = 1
    boundary = trial.model_edges(hit, trial.upstream_edges())
    assert boundary[1, 4] and boundary[3, 2]
    assert not boundary[3, 4] and not boundary[3, 1]
    hit[3, 4:6] = 2
    with_window = trial.model_edges(hit, trial.upstream_edges())
    assert with_window[3, 4] and with_window[3, 6]
