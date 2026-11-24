"""#1609 KPP1 package step: plan of the non-post outside elements (frames, portals, annex) and the glass depth cap.

Artem 2026-11-24: posts accepted; the package rebuilds window framings and portals by the same voxel/lattice method
as separate elements [D336]. Kernel: jobs/KPP1/lattice-1609/posts_plan.py (stdlib).
"""
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'jobs' / 'KPP1' / 'lattice-1609'))
import posts_plan as pp  # noqa: E402

RECT = (-14.985, -5.685, 12.675, 5.975)


def test_window_frame_on_south_is_voxel_frame_with_outward_ray():
    p = pp.element_plan([-7.055, -5.885, 4.775], [-2.98, -5.685, 6.725], 9.98, 0.0, RECT)
    assert p == {'side': 'S', 'kind': 'Frame', 'method': 'voxel', 'rays': ((1, -1),), 'why': 'axis-aligned solid'}


def test_open_strip_without_closing_planes_is_kept():
    # S strip x 6.6-6.675 (v003 component 11): only y faces, no x end caps, no z caps -> cannot be voxelised
    p = pp.element_plan([6.6, -5.729, 1.2], [6.675, -5.636, 3.0], 0.14, 0.0, RECT, planes=(0, 3, 0))
    assert (p['method'], p['why']) == ('keep', 'open surface: < 2 own planes on axis x')
    closed = pp.element_plan([6.6, -5.729, 1.2], [6.675, -5.636, 3.0], 0.14, 0.0, RECT, planes=(2, 1, 2))
    assert closed['method'] == 'voxel'


def test_each_side_gets_its_outward_ray():
    got = {pp.element_plan(lo, hi, 1.0, 0.0, RECT)['side']: pp.element_plan(lo, hi, 1.0, 0.0, RECT)['rays'][0]
           for lo, hi in (([-15.185, 0.02, 4.775], [-14.985, 4.05, 6.725]),    # W
                          ([0.54, 5.939, 1.2], [1.87, 6.175, 6.725]),          # N
                          ([-1.77, -5.885, 1.125], [-0.44, -5.675, 6.725]),    # S
                          ([12.66, -2.955, 1.0], [16.676, 3.225, 3.9]))}       # E
    assert got == {'W': (0, -1), 'N': (1, 1), 'S': (1, -1), 'E': (0, 1)}


def test_ground_standing_axis_element_is_annex_and_slanted_one_is_kept_portal():
    annex = pp.element_plan([12.66, -2.955, 0.0], [16.676, 3.225, 3.9], 46.3, 0.0, RECT)
    portal = pp.element_plan([-4.013, -6.385, 0.0], [-2.817, -5.525, 3.3], 6.99, 4.32, RECT)
    assert (annex['kind'], annex['method']) == ('Annex', 'voxel')
    assert (portal['kind'], portal['method']) == ('Portal', 'keep')


def test_flat_element_is_kept_not_voxelised():
    p = pp.element_plan([-15.029, 3.975, 1.2], [-15.029, 4.05, 3.0], 0.135, 0.0, RECT)
    assert (p['side'], p['method']) == ('W', 'keep')


@pytest.mark.parametrize('lo,hi,area,na', [
    ([0, 0, 0], [1, 1, 1], 1.0, 0.0),                       # inside the ring: no side
    ([-16, -7, 0], [-15.5, -6, 1], 1.0, 0.0),               # beyond two sides (corner): post territory
    ([-7, -5.9, 4], [-3, -5.7, 6], 0.0, 0.0),               # zero area
    ([-7, -5.9, 4], [-3, -5.7, 6], 1.0, 2.0),               # non-axis area larger than area
    ([-7, -5.9, math.nan], [-3, -5.7, 6], 1.0, 0.0),        # NaN
    ([-7, -5.9, 4], [-3, -5.7, math.inf], 1.0, 0.0),        # inf
    ([-7, -5.9, 4], [-8, -5.7, 6], 1.0, 0.0),               # lo > hi
])
def test_element_plan_fails_closed(lo, hi, area, na):
    with pytest.raises(ValueError):
        pp.element_plan(lo, hi, area, na, RECT)


def test_glass_shift_caps_depth_and_keeps_shallow_glass():
    assert pp.glass_shift([0.21, 0.23], 0.24) == 0.0
    assert pp.glass_shift([0.32, 0.35], 0.24) == pytest.approx(0.11)
    assert pp.glass_shift([0.24], 0.24) == 0.0                 # exactly at the cap: stays


@pytest.mark.parametrize('depths', [[], [math.nan], [0.3, math.inf], [-0.01]])
def test_glass_shift_fails_closed(depths):
    with pytest.raises(ValueError):
        pp.glass_shift(depths, 0.24)


def test_glass_shift_probe_never_leaves_glass_behind_the_cap():
    rng = random.Random(1609)
    for _ in range(500):
        ds = [rng.uniform(0.0, 0.6) for _ in range(rng.randint(1, 6))]
        s = pp.glass_shift(ds, 0.24)
        assert s >= 0 and max(ds) - s <= 0.24 + 1e-12
        assert s == 0 or max(ds) - s == pytest.approx(0.24)


def test_element_plan_probe_side_matches_offset_box():
    rng = random.Random(16090)
    x0, y0, x1, y1 = RECT
    for _ in range(300):
        side = rng.choice('WSNE')
        a, b = sorted(rng.uniform(-4, 4) for _ in range(2))
        d = rng.uniform(0.01, 0.5)
        lo, hi = {'W': ([x0 - d, a, 1], [x0, b + 0.1, 2]), 'E': ([x1, a, 1], [x1 + d, b + 0.1, 2]),
                  'S': ([a, y0 - d, 1], [b + 0.1, y0, 2]), 'N': ([a, y1, 1], [b + 0.1, y1 + d, 2])}[side]
        assert pp.element_plan(lo, hi, 1.0, 0.0, RECT)['side'] == side


def test_majority_finish_door_wins_over_band():
    hits = ['Door_RAL7004'] * 15 + ['Frame_RAL9016'] * 5 + [None] * 5
    assert pp.majority_finish(hits, 'Cassette_RAL5015') == ('Door_RAL7004', 0.6)


def test_majority_finish_keeps_band_when_nothing_or_too_little_is_seen():
    assert pp.majority_finish([None] * 25, 'Cassette_RAL5015') == ('Cassette_RAL5015', 0.0)
    assert pp.majority_finish(['Door_RAL7004'] * 12 + [None] * 13, 'Cassette_RAL5015') == ('Cassette_RAL5015', 0.48)


def test_majority_finish_exactly_at_threshold_and_tie_is_deterministic():
    assert pp.majority_finish(['A'] * 5 + [None] * 5, 'band') == ('A', 0.5)
    assert pp.majority_finish(['B'] * 3 + ['A'] * 3, 'band', 0.5) == ('A', 0.5)


@pytest.mark.parametrize('hits,fallback,share', [([], 'band', 0.5), (['A'], '', 0.5), (['A'], 'band', 0.0),
                                                 (['A'], 'band', 1.5), (['A'], 'band', math.nan)])
def test_majority_finish_fails_closed(hits, fallback, share):
    with pytest.raises(ValueError):
        pp.majority_finish(hits, fallback, share)


def test_majority_finish_probe():
    rng = random.Random(16091)
    for _ in range(400):
        hits = [rng.choice(['A', 'B', 'C', None]) for _ in range(rng.randint(1, 30))]
        fin, share = pp.majority_finish(hits, 'band')
        assert 0 <= share <= 1
        if fin != 'band':
            assert hits.count(fin) / len(hits) == share >= 0.5
            assert all(hits.count(fin) >= hits.count(o) for o in 'ABC')


def test_outside_ring_keeps_ring_plane_faces_inside():
    x0, y0, x1, y1 = RECT
    assert not pp.outside_ring((x0, 0.0), RECT, tol=0.002)          # the N screen / wall face on the ring plane
    assert not pp.outside_ring((x0 - 0.002, 0.0), RECT, tol=0.002)  # exactly at the threshold: not outside
    assert pp.outside_ring((x0 - 0.0021, 0.0), RECT, tol=0.002)
    assert pp.outside_ring((0.0, y1 + 0.2), RECT)
    with pytest.raises(ValueError):
        pp.outside_ring((math.nan, 0.0), RECT)


def test_glass_target_modes():
    assert pp.glass_target([0.33, 0.35], [0.25] * 5, 0.24, 0.01) == (pytest.approx(0.11), 'reveal')
    shift, how = pp.glass_target([0.23, 0.24], [0.11] * 5, 0.24, 0.01)      # niche at 0.11 in front of the pane
    assert how == 'surface' and 0.24 - shift == pytest.approx(0.10)
    shift, how = pp.glass_target([0.335, 0.345], [0.0] * 4 + [0.4], 0.24, 0.01)   # solid wall: onto the wall
    assert how == 'onto_wall' and 0.335 - shift == pytest.approx(-0.02) and 0.345 - shift == pytest.approx(-0.01)
    assert pp.glass_target([0.3], [0.0, 0.4], 0.24, 0.01)[1] == 'reveal'        # exactly half with room: in place
    assert pp.glass_target([0.3], [], 0.24, 0.01) == (pytest.approx(0.06), 'reveal')   # nothing behind: reveal cap


@pytest.mark.parametrize('depths,behind,cap,gap', [([], [0.2], 0.24, 0.01), ([0.3], [math.nan], 0.24, 0.01),
                                                   ([0.3], [0.2], 0.24, 0.0), ([0.3], [0.2], 0.01, 0.01)])
def test_glass_target_fails_closed(depths, behind, cap, gap):
    with pytest.raises(ValueError):
        pp.glass_target(depths, behind, cap, gap)


def test_glass_target_probe_pane_never_behind_a_body_surface_with_room():
    rng = random.Random(16092)
    for _ in range(500):
        depths = sorted(rng.uniform(0.0, 0.5) for _ in range(2))
        behind = [rng.choice([0.0, rng.uniform(0.0, 0.6)]) for _ in range(rng.randint(0, 6))]
        shift, how = pp.glass_target(depths, behind, 0.24, 0.01)
        deepest = depths[1] - shift
        assert shift >= 0
        if how == 'onto_wall':
            assert deepest == pytest.approx(-0.01)
        else:
            assert deepest <= 0.24 + 1e-12
            assert all(deepest <= d - 0.01 + 1e-12 for d in behind if d >= 0.02)


def test_roof_face_selects_inside_ring_above_level_only():
    x0, y0, x1, y1 = RECT
    assert pp.roof_face((0.0, 0.0, 7.91), RECT, 7.85)                 # roof slab
    assert pp.roof_face((x0 + 0.15, 0.0, 8.28), RECT, 7.85)           # parapet inner face
    assert pp.roof_face((0.0, 0.0, 7.85), RECT, 7.85)                 # exactly at the level: roof
    assert not pp.roof_face((x0, 0.0, 8.3), RECT, 7.85)               # facade face on the ring plane
    assert not pp.roof_face((x0 + 0.001, 0.0, 8.3), RECT, 7.85)       # within tol of the ring plane
    assert not pp.roof_face((0.0, 0.0, 7.84), RECT, 7.85)
    assert not pp.roof_face((0.0, y1 + 0.3, 8.0), RECT, 7.85)         # outside elements are not roof
    with pytest.raises(ValueError):
        pp.roof_face((0.0, 0.0, math.nan), RECT, 7.85)


def test_clamp_outside_moves_points_in_front_of_the_ring_plane():
    x0, y0, x1, y1 = RECT
    pts = [(0.0, y0 - 0.5, 1.0), (0.0, y0 + 0.16, 1.0), (0.0, y0 - 0.006, 1.0), (0.0, y0 - 0.005, 1.0)]
    out, moved = pp.clamp_outside(pts, 'S', RECT, 0.006)
    assert moved == 2                                   # inside the ring and 5 mm out; exactly at the gap stays
    assert out[0] == pts[0] and out[2] == pts[2]
    assert out[1][1] == pytest.approx(y0 - 0.006) and out[3][1] == pytest.approx(y0 - 0.006)
    assert pp.clamp_outside([(x1 + 0.001, 0, 0)], 'E', RECT, 0.006)[0][0][0] == pytest.approx(x1 + 0.006)


@pytest.mark.parametrize('pts,side,gap', [([(0, 0, 0)], 'X', 0.006), ([(0, 0, 0)], 'S', 0.0),
                                          ([(math.nan, 0, 0)], 'S', 0.006), ([(0, 0, 0)], 'S', math.inf)])
def test_clamp_outside_fails_closed(pts, side, gap):
    with pytest.raises(ValueError):
        pp.clamp_outside(pts, side, RECT, gap)


def test_clamp_outside_probe_every_point_at_least_gap_outside():
    rng = random.Random(16093)
    planes = {'W': (0, -1, RECT[0]), 'E': (0, 1, RECT[2]), 'S': (1, -1, RECT[1]), 'N': (1, 1, RECT[3])}
    for _ in range(300):
        side = rng.choice('WESN')
        ax, sg, plane = planes[side]
        pts = [tuple(rng.uniform(-20, 20) for _ in range(3)) for _ in range(rng.randint(1, 8))]
        out, moved = pp.clamp_outside(pts, side, RECT, 0.006)
        assert all((q[ax] - plane) * sg >= 0.006 - 1e-12 for q in out)
        assert moved == sum(1 for p, q in zip(pts, out) if p != q)
