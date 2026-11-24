"""KPP1 lattice step 3 kernel: corner posts as separate elements + body finish bands (#1609, D336).

Pattern: n/a | new-case: tests of jobs/KPP1/lattice-1609/hooks/kpp1_elements.py (posts, finish bands; was posts_plan.py).
"""
import importlib.util
import json
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'jobs/KPP1/lattice-1609'


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_1609s3', D / 'hooks' / (name + '.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pp = _load('kpp1_elements')
RECT = (-14.985, -5.685, 12.675, 5.975)
BANDS = json.loads((D / 'finish_bands.json').read_text(encoding='utf-8'))['bands']


def box(x0, y0, z0, x1, y1, z1, base=0):
    v = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    f = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]]
    return v, [[k + base for k in q] for q in f]


def mesh(*boxes):
    V, F = [], []
    for b in boxes:
        v, f = box(*b, base=len(V))
        V += v
        F += f
    return V, F


def test_corner_post_found_and_other_reported():
    V, F = mesh((-15.185, 5.965, 1.1, -14.975, 6.175, 8.5),      # NW post (crosses the ring a little)
                (-7.0, -5.885, 4.7, -3.0, -5.685, 6.7),          # S window surround: not a post
                (-10, -5, 0, 10, 5, 8))                           # body inside the ring
    r = pp.outside_components(V, F, RECT)
    assert set(r['posts']) == {'NW'}
    assert len(r['other']) == 1
    # every outside face ends in a post or in `other` (nothing dropped)
    assert len(r['posts']['NW']) + sum(map(len, r['other'])) == r['outside_faces']


def test_random_boxes_every_outside_face_accounted():
    rng = random.Random(1609)
    for _ in range(200):
        bs = []
        for _ in range(rng.randint(1, 6)):
            x = rng.uniform(-16, 14)
            y = rng.uniform(-7, 7)
            bs.append((x, y, 0, x + rng.uniform(0.05, 0.3), y + rng.uniform(0.05, 0.3), rng.uniform(1, 8)))
        V, F = mesh(*bs)
        try:
            r = pp.outside_components(V, F, RECT, near_m=0.4)
        except ValueError as e:
            assert 'near corners' in str(e)
            continue
        assert sum(map(len, r['posts'].values())) + sum(map(len, r['other'])) == r['outside_faces']


@pytest.mark.parametrize('bad', [([], [[0, 1, 2]]), ([(0, 0, 0)], []),
                                 ([(0, 0, 0), (1, 0, 0), (float('nan'), 1, 0)], [[0, 1, 2]]),
                                 ([(0, 0, 0), (1, 0, 0), (1, 1, 0)], [[0, 1]])])
def test_outside_components_fail_closed(bad):
    with pytest.raises(ValueError):
        pp.outside_components(*bad, RECT)


@pytest.mark.parametrize('rect', [(0, 0, 0, 1), (0, 0, 1), (0, 0, math.inf, 1), (1, 0, 0, 1)])
def test_rect_fail_closed(rect):
    with pytest.raises(ValueError):
        pp.check_rect(rect)


def test_near_m_fail_closed():
    V, F = mesh((-15.185, 5.965, 1.1, -14.975, 6.175, 8.5))
    for n in (0, -1, float('nan'), math.inf):
        with pytest.raises(ValueError):
            pp.outside_components(V, F, RECT, near_m=n)


def test_component_near_two_corners_is_error():
    V, F = mesh((-15.2, -5.9, 0, -15.0, 6.2, 8))     # runs along the whole W facade outside the ring
    with pytest.raises(ValueError, match='near corners'):
        pp.outside_components(V, F, RECT)


def test_ring_contact_only_inward_on_boundary():
    assert pp.ring_contact((-14.985, 6.0, 3), (1, 0, 0), RECT) is False      # y outside the ring span
    assert pp.ring_contact((-14.985, 5.9, 3), (1, 0, 0), RECT) is True
    assert pp.ring_contact((-14.985, 5.9, 3), (-1, 0, 0), RECT) is False     # faces out: visible
    assert pp.ring_contact((-15.0, 5.9, 3), (1, 0, 0), RECT) is False        # not on the boundary
    assert pp.ring_contact((12.0, 5.975, 3), (0, -1, 0), RECT) is True
    assert pp.ring_contact((12.675, -5.0, 3), (-1, 0, 0), RECT) is True


def test_inside_ring():
    assert pp.inside_ring((0, 0, 0), RECT)
    assert not pp.inside_ring((-14.985, 0, 0), RECT)                         # exactly on the boundary
    assert not pp.inside_ring((-15.1, 6.1, 0), RECT)


def test_finish_bands_walls_sills_heads():
    def f(lo, hi, nz):
        return pp.finish_of_face(lo, hi, nz, BANDS)
    assert f(0.0, 0.9, 0) == 'Plinth_RAL7004'
    assert f(0.9, 1.125, 0) == 'Cassette_RAL7047'
    assert f(2.7, 3.075, 0) == 'Cassette_RAL5015'
    assert f(7.1, 8.65, 0) == 'Cassette_RAL5015_Top'
    assert f(0.9, 0.9, 1) == 'Plinth_RAL7004'          # plinth top (up) closes the plinth
    assert f(0.9, 0.9, -1) == 'Cassette_RAL7047'       # head (down) at the border belongs to the band above
    assert f(2.7, 2.7, 1) == 'Cassette_RAL7047'
    assert f(7.1, 7.1, -1) == 'Cassette_RAL5015_Top'
    assert f(8.65, 8.65, 1) == 'Cassette_RAL5015_Top'


def test_finish_exactly_at_band_borders_brute():
    for b in BANDS:
        for z in (b['z0'], b['z1']):
            if -1.0 < z < 9.0:
                up, dn = pp.finish_of_face(z, z, 1, BANDS), pp.finish_of_face(z, z, -1, BANDS)
                assert up != dn or z in (-1.0, 9.0)


@pytest.mark.parametrize('args', [(9.5, 9.6, 0), (-2, -1.5, 0), (3.0, 3.0, 0), (float('nan'), 1, 0),
                                  (1, math.inf, 0)])
def test_finish_fail_closed(args):
    with pytest.raises(ValueError):
        pp.finish_of_face(*args, BANDS)


def test_bands_gap_is_error():
    bad = [dict(BANDS[0]), dict(BANDS[1], z0=BANDS[1]['z0'] + 0.1)]
    with pytest.raises(ValueError, match='gap'):
        pp.finish_of_face(1.0, 1.1, 0, bad)
    with pytest.raises(ValueError):
        pp.check_bands([])
