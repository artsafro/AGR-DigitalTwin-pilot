"""Ring-stack sliding walls and upper-ring snapping (src/dt_ai/geometry/ring_stack.py)."""

import math

import pytest

from dt_ai.geometry.ring_stack import (
    COLLAPSE_M, LINE_M, _intersect, sliding_walls, snap_upper_cols)


def ring(points):
    """Closed ring from its corner points: edge i runs points[i] -> points[i + 1]."""
    n = len(points)
    edges = []
    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        edges.append({"a": a, "b": b, "length": math.dist(a, b)})
    return {"edges": edges}


SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
CHAINS = [{"edges": [0, 1, 2, 3]}]


def test_defaults_match_job_constants():
    assert (LINE_M, COLLAPSE_M) == (0.01, 0.005)


def test_end_moved_along_wall_line_is_sliding():
    upper = ring([(0.0, 0.0), (10.5, 0.0), (10.0, 10.0), (0.0, 10.0)])
    assert sliding_walls([ring(SQUARE), upper], CHAINS) == {0: {0}}


def test_end_moved_perpendicular_is_not_sliding():
    upper = ring([(0.0, 0.0), (10.0, 0.5), (10.0, 10.0), (0.0, 10.0)])
    walls = sliding_walls([ring(SQUARE), upper], CHAINS)
    assert 0 not in walls[0]        # edge 0's end left its line by 0.5 m
    assert walls == {0: {1}}        # the same move runs along edge 1's line x=10


def test_collapsed_edge_is_skipped():
    lower = ring([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.003)])
    upper = ring([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.002)])
    chains = [{"edges": [0, 1, 2, 3, 4]}]
    assert lower["edges"][4]["length"] < COLLAPSE_M
    # edge 4 slides along x=0 but is shorter than COLLAPSE_M; edge 3 slides too and is long
    assert sliding_walls([lower, upper], chains) == {0: {3}}


def test_unchanged_ends_are_not_sliding():
    upper = ring([(0.0, 0.0), (10.0 + 5e-5, 0.0), (10.0, 10.0), (0.0, 10.0)])
    assert sliding_walls([ring(SQUARE), ring(SQUARE)], CHAINS) == {0: set()}
    assert sliding_walls([ring(SQUARE), upper], CHAINS) == {0: set()}


def test_custom_thresholds_are_keyword_args():
    upper = ring([(0.0, 0.0), (10.5, 0.0), (10.0, 10.0), (0.0, 10.0)])
    assert sliding_walls([ring(SQUARE), upper], CHAINS, line_m=1.0) == {0: {0, 1}}
    assert sliding_walls([ring(SQUARE), upper], CHAINS, collapse_m=20.0) == {0: set()}


def test_snap_projects_upper_points_back_onto_lower_line():
    cols = [(0.0, 0.001, 0, False), (5.0, 0.001, 0, True), (10.0, 0.001, 1, False),
            (10.0, 10.0, 2, False), (0.0, 10.0, 3, False)]
    out, worst = snap_upper_cols(cols, ring(SQUARE), {0})
    assert out[:3] == [(0.0, 0.0, 0, False), (5.0, 0.0, 0, True), (10.0, 0.0, 1, False)]
    assert out[3:] == cols[3:]
    assert abs(worst - 0.001) < 1e-9


def test_snap_corner_of_two_sliding_walls_goes_to_intersection():
    cols = [(0.0, 0.0, 0, False), (10.2, 0.3, 1, False), (10.0, 10.0, 2, False), (0.0, 10.0, 3, False)]
    out, worst = snap_upper_cols(cols, ring(SQUARE), {0, 1})
    assert out[1][:2] == pytest.approx((10.0, 0.0), abs=1e-12)
    assert worst == pytest.approx(math.hypot(0.2, 0.3), abs=1e-12)


def test_parallel_lines_have_no_intersection_and_point_stays():
    assert _intersect((0.0, 0.0), (5.0, 0.0), (5.0, 0.0), (10.0, 0.0)) is None
    lower = ring([(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    cols = [(0.0, 0.0, 0, False), (5.0, 0.0, 1, False), (10.0, 0.0, 2, False),
            (10.0, 10.0, 3, False), (0.0, 10.0, 4, False)]
    out, worst = snap_upper_cols(cols, lower, {0, 1})
    assert out[1] == (5.0, 0.0, 1, False)
    assert worst == 0.0


def test_empty_input():
    assert sliding_walls([], CHAINS) == {}
    assert sliding_walls([ring(SQUARE)], CHAINS) == {}
    assert snap_upper_cols([], ring(SQUARE), {0}) == ([], 0.0)


@pytest.mark.parametrize("bad", [math.nan, math.inf])
def test_non_finite_coordinates_raise(bad):
    upper = ring([(0.0, 0.0), (bad, 0.0), (10.0, 10.0), (0.0, 10.0)])
    with pytest.raises(ValueError, match="non-finite"):
        sliding_walls([ring(SQUARE), upper], CHAINS, collapse_m=-1.0)


def test_zero_length_lower_line_raises():
    lower = {"edges": [{"a": (1.0, 1.0), "b": (1.0, 1.0), "length": 0.0}]}
    with pytest.raises(ValueError, match="zero-length"):
        snap_upper_cols([(0.0, 0.0, 0, False)], lower, {0})


def test_exactly_at_line_threshold_is_not_sliding():
    # perpendicular offset of the moved end equals LINE_M exactly: strict '<' keeps the job's semantics
    upper = ring([(0.0, 0.0), (10.5, 0.0), (10.0, 10.0), (0.0, 10.0)])
    upper["edges"][0]["b"] = (10.5, 0.01)
    assert 0 not in sliding_walls([ring(SQUARE), upper], CHAINS, line_m=0.01)[0]


def test_unknown_wall_edge_raises():
    with pytest.raises(ValueError, match=r"\[7\]"):
        snap_upper_cols([(0.0, 0.0, 7, False)], ring(SQUARE), {7})
