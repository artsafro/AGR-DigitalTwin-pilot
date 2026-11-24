"""Synthetic regression: a dense distractor row must not outvote two panel rows."""
import numpy as np
import pytest

from replay import P72, R72, candidate, load_source


def runs_owner():
    legacy = load_source(R72, P72)
    return load_source(legacy["BASE"], legacy["JOINT"])["runs"]


def test_dense_distractor_row_has_one_vote():
    tile = np.full((4, 100, 3), 220, np.uint8)
    tile[1::2, 10::20] = 20
    tile[2, 2::4] = 20
    assert candidate()(tile, runs_owner()) == (20.0, [5, 25, 5])


def test_row_without_complete_runs_is_not_measured():
    tile = np.full((4, 100, 3), 220, np.uint8)
    tile[1::2, 10::20] = 20
    with pytest.raises(ValueError, match="pitch not measured"):
        candidate()(tile, runs_owner())
