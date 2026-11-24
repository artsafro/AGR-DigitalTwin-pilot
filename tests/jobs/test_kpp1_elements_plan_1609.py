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
    assert p == {'side': 'S', 'kind': 'Frame', 'method': 'voxel', 'rays': ((1, -1), (0, 1))}


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
