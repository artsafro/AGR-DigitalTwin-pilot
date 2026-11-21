"""#1609 KPP1 v004 variant A (Artem 2026-11-20 «принимаю рекомендации»): walls are one body with the reveals - every
rebuilt plane's grid shares the nodes on each edge it has with a neighbour plane (`wall_plan.conform`)."""
import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('wall_plan', ROOT / 'jobs/KPP1/quad-1372/wall_plan.py')
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)


def rect(h0, h1, z0, z1, fin=0):
    return ([(h0, z0), (h1, z0), (h1, z1), (h0, z1)], fin)


def test_forced_line_is_kept_exactly():
    p = wp.plan([rect(0, 1, 0, 1)], 5.0, 1e-3, forced=({0.3}, {0.7}))
    assert p['H'] == [0, 0.3, 1] and p['Z'] == [0, 0.7, 1]
    assert len(p['cells']) == 4


def test_forced_value_snaps_its_cluster_and_smallest_forced_wins():
    p = wp.plan([rect(0, 1.0004, 0, 1)], 5.0, 1e-3, forced=({1.0002, 1.0001}, set()))
    assert p['H'] == [0, 1.0001]


def test_forced_outside_extent_is_ignored():
    p = wp.plan([rect(0, 1, 0, 1)], 5.0, 1e-3, forced=({-2.0, 7.0}, {3.0}))
    assert p['H'] == [0, 1] and p['Z'] == [0, 1]


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_forced_non_finite_fails(bad):
    with pytest.raises(ValueError, match='forced'):
        wp.plan([rect(0, 1, 0, 1)], 5.0, 1e-3, forced=({bad}, set()))


def l_pair(rng):
    """Wall P (normal x at x=0, coords (y, z)) and reveal Q (normal y at y=0, coords (x, z)), sharing the edge
    x=0, y=0 along z in 0..3. P has random finish borders in z, Q random tessellation in z."""
    zb = sorted({round(rng.uniform(0.2, 2.8), 2) for _ in range(rng.randint(1, 4))})
    zs = [0.0] + zb + [3.0]
    P = [rect(0, 2, a, b, fin=i % 2) for i, (a, b) in enumerate(zip(zs, zs[1:]))]
    zq = sorted({0.0, 3.0} | {round(rng.uniform(0.1, 2.9), 3) for _ in range(5)})
    Q = [rect(-0.3, 0, a, b) for a, b in zip(zq, zq[1:])]
    planes = {'P': {'faces': P, 'axes': (1, 2), 'ax': 0, 'pos': 0.0},
              'Q': {'faces': Q, 'axes': (0, 2), 'ax': 1, 'pos': 0.0}}
    return planes, {('P', 'Q'): [(2, 0.0, 3.0)]}, zb


def test_conform_l_corner_brute_force():
    rng = random.Random(1609)
    for _ in range(200):
        planes, adj, zb = l_pair(rng)
        plans, info = wp.conform(planes, adj, 2.048, 1e-3)
        assert info['mismatched_spans'] == 0
        zp, zq = plans['P']['Z'], plans['Q']['Z']
        assert zp == zq, (zp, zq)
        assert all(min(abs(z - w) for w in zq) <= 1e-3 for z in zb)   # wall lines continue along the reveal
        assert 0.0 in plans['P']['H'] and 0.0 in plans['Q']['H']   # the shared edge is a line in both


def test_conform_chain_propagates_and_converges():
    # P - Q - R in a chain: R's border reaches P through Q
    planes = {'P': {'faces': [rect(0, 1, 0, 3)], 'axes': (1, 2), 'ax': 0, 'pos': 0.0},
              'Q': {'faces': [rect(-1, 0, 0, 3)], 'axes': (0, 2), 'ax': 1, 'pos': 0.0},
              'R': {'faces': [rect(0, 1, 0, 1.5, 0), rect(0, 1, 1.5, 3, 1)], 'axes': (1, 2), 'ax': 0, 'pos': -1.0}}
    adj = {('P', 'Q'): [(2, 0.0, 3.0)], ('Q', 'R'): [(2, 0.0, 3.0)]}
    plans, rounds = wp.conform(planes, adj, 5.0, 1e-3)
    assert 1.5 in plans['P']['Z'] and 1.5 in plans['Q']['Z']
    assert plans['P']['Z'] == plans['Q']['Z'] == plans['R']['Z']


def test_conform_span_limits_propagation():
    planes = {'P': {'faces': [rect(0, 1, 0, 1, 0), rect(0, 1, 1, 3, 1)], 'axes': (1, 2), 'ax': 0, 'pos': 0.0},
              'Q': {'faces': [rect(-1, 0, 1.5, 3)], 'axes': (0, 2), 'ax': 1, 'pos': 0.0}}
    plans, _ = wp.conform(planes, {('P', 'Q'): [(2, 1.5, 3.0)]}, 5.0, 1e-3)
    assert 1.0 not in plans['Q']['Z']     # P's border at z=1 is below the shared edge
    assert 1.5 in plans['P']['Z']         # Q's outline end is on the shared edge


def test_conform_lattice_splits_converge_brute_force():
    # long planes with different extents: even splits would differ per plane and cascade; lattice splits agree
    rng = random.Random(57)
    for _ in range(100):
        z1, z2, z3 = (round(rng.uniform(2.5, 9.0), 2) for _ in range(3))
        planes = {'P': {'faces': [rect(0, 1, 0, z1)], 'axes': (1, 2), 'ax': 0, 'pos': 0.0},
                  'Q': {'faces': [rect(-1, 0, 0, z2)], 'axes': (0, 2), 'ax': 1, 'pos': 0.0},
                  'R': {'faces': [rect(0, 1, 0, z3)], 'axes': (1, 2), 'ax': 0, 'pos': -1.0}}
        adj = {('P', 'Q'): [(2, 0.0, min(z1, z2))], ('Q', 'R'): [(2, 0.0, min(z2, z3))]}
        plans, info = wp.conform(planes, adj, 2.048, 1e-3)
        assert info['mismatched_spans'] == 0
        for p, q, hi in (('P', 'Q', min(z1, z2)), ('Q', 'R', min(z2, z3))):
            a = [z for z in plans[p]['Z'] if z <= hi + 1e-3]
            b = [z for z in plans[q]['Z'] if z <= hi + 1e-3]
            assert a == b, (p, q, a, b)
        for pl in plans.values():
            assert max(b - a for a, b in zip(pl['Z'], pl['Z'][1:])) <= 2.048 + 1e-9


def test_conform_fails_closed():
    with pytest.raises(ValueError, match='no planes'):
        wp.conform({}, {}, 1.0, 1e-3)
    planes = {'P': {'faces': [rect(0, 1, 0, 1)], 'axes': (1, 2), 'ax': 0, 'pos': 0.0}}
    with pytest.raises(ValueError, match='unknown plane'):
        wp.conform(planes, {('P', 'X'): [(2, 0, 1)]}, 1.0, 1e-3)
    planes['Q'] = {'faces': [rect(0, 1, 0, 1)], 'axes': (1, 2), 'ax': 0, 'pos': 1.0}
    with pytest.raises(ValueError, match='parallel'):
        wp.conform(planes, {('P', 'Q'): [(2, 0, 1)]}, 1.0, 1e-3)
    with pytest.raises(ValueError, match='axis'):
        planes['Q']['axes'], planes['Q']['ax'] = (0, 2), 1
        wp.conform(planes, {('P', 'Q'): [(0, 0, 1)]}, 1.0, 1e-3)
    assert math.isfinite(1.0)


# w12g: 1201 pierce pairs - rebuilt sills/heads whose outline runs along a sloped flashing (slanted outline edge) were
# rasterised to whole axis cells that poke past the slanted edge into the v003 flashing. Such a plane stays v003.
def test_slanted_outline_counts_only_non_axis_boundary_edges():
    sq = [rect(0, 1, 0, 1), rect(1, 2, 0, 1)]
    assert wp.slanted_outline(sq) == 0
    tri = [([(0, 0), (1, 0), (0, 1)], 0)]          # hypotenuse is a slanted outline edge
    assert wp.slanted_outline(tri) == 1
    # an internal diagonal (two triangles of one square) is shared, not outline
    two = [([(0, 0), (1, 0), (1, 1)], 0), ([(0, 0), (1, 1), (0, 1)], 0)]
    assert wp.slanted_outline(two) == 0


def test_slanted_outline_ignores_wildcard_contact_faces_and_tiny_tilts():
    assert wp.slanted_outline([([(0, 0), (1, 0), (0, 1)], None)]) == 0
    # a 0.5 mm wobble over 1 m (r1 float noise) is not a slant at tol 1 mm
    assert wp.slanted_outline([([(0, 0), (1, 0.0005), (1, 1), (0, 1)], 0)], tol=1e-3) == 0
    assert wp.slanted_outline([([(0, 0), (1, 0.0015), (1, 1), (0, 1)], 0)], tol=1e-3) == 1


@pytest.mark.parametrize('faces', [[], [([(0, 0), (1, float('nan')), (0, 1)], 0)]])
def test_slanted_outline_fails_closed(faces):
    with pytest.raises(ValueError):
        wp.slanted_outline(faces)


def test_slanted_outline_random_rectilinear_unions_are_zero():
    rnd = random.Random(1609)
    for _ in range(200):
        n = rnd.randint(1, 6)
        cells = {(rnd.randint(0, 4), rnd.randint(0, 4)) for _ in range(n)}
        faces = [rect(i * 0.5, i * 0.5 + 0.5, j * 0.3, j * 0.3 + 0.3) for i, j in cells]
        assert wp.slanted_outline(faces) == 0


# w13: weld_body (2.1 mm) twisted one 4 mm v003 sliver quad into a bow-tie; `dt qa xview` refuses such a polygon.
def test_quad_twisted_detects_bowtie_order_only():
    assert not wp.quad_twisted([(0, 0), (1, 0), (1, 1), (0, 1)])
    assert wp.quad_twisted([(0, 0), (1, 1), (1, 0), (0, 1)])
    assert wp.quad_twisted([(0, 0), (1, 0), (0, 1), (1, 1)])


def test_quad_twisted_random_convex_never_and_swapped_always():
    rnd = random.Random(16092)
    for _ in range(300):
        cx, cy, r = rnd.uniform(-5, 5), rnd.uniform(-5, 5), rnd.uniform(0.01, 3)
        angs = sorted(rnd.uniform(0, 2 * math.pi) for _ in range(4))
        if min(b - a for a, b in zip(angs, angs[1:] + [angs[0] + 2 * math.pi])) < 0.05:
            continue
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angs]
        assert not wp.quad_twisted(pts)
        assert wp.quad_twisted([pts[0], pts[2], pts[1], pts[3]])


@pytest.mark.parametrize('pts', [[(0, 0), (1, 0), (1, 1)], [(0, 0), (1, float('nan')), (1, 1), (0, 1)]])
def test_quad_twisted_fails_closed(pts):
    with pytest.raises(ValueError):
        wp.quad_twisted(pts)
