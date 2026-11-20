"""#1609 KPP1 v004 [D357]: whole-wall grid kernel `wall_plan` - lines only at outline/finish borders, embed shifts."""
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


def tessellated_wall_with_hole(rng):
    """A 6 x 3 m wall, one finish, hole 2..3 x 1..2, cut into random sub-rectangles (tessellation noise)."""
    faces = []
    hs = sorted({0.0, 2.0, 3.0, 6.0} | {round(rng.uniform(0.1, 5.9), 3) for _ in range(5)})
    zs = sorted({0.0, 1.0, 2.0, 3.0} | {round(rng.uniform(0.1, 2.9), 3) for _ in range(3)})
    for a, b in zip(hs, hs[1:]):
        for c, d in zip(zs, zs[1:]):
            if not (2.0 <= a and b <= 3.0 and 1.0 <= c and d <= 2.0):
                faces.append(rect(a, b, c, d))
    return faces


def test_tessellation_vertices_leave_no_line():
    for seed in range(50):
        p = wp.plan(tessellated_wall_with_hole(random.Random(seed)), max_cell=10.0)
        assert p['H'] == [0.0, 2.0, 3.0, 6.0] and p['Z'] == [0.0, 1.0, 2.0, 3.0], seed
        assert len(p['cells']) == 8 and (1, 1) not in p['cells']
        assert all(abs(v) < 1e-9 for v in p['area_error_m2'].values())


def test_finish_border_is_a_line_and_long_cells_split():
    p = wp.plan([rect(0, 1.5, 0, 1, 0), rect(1.5, 5, 0, 1, 1)], max_cell=2.0)
    assert 1.5 in p['H'] and max(b - a for a, b in zip(p['H'], p['H'][1:])) <= 2.0
    assert {f for f in p['cells'].values()} == {0, 1}


def test_wildcard_takes_row_neighbour():
    p = wp.plan([rect(0, 1, 0, 1, 3), rect(1, 1.2, 0, 1, None), rect(1.2, 2, 0, 1, 3)], max_cell=5.0)
    assert set(p['cells'].values()) == {3} and p['H'] == [0, 2]


@pytest.mark.parametrize('faces', [[], [([(0, 0), (1, 0)], 0)], [([(0, 0), (1, math.nan), (1, 1)], 0)],
                                   [([(0, 0), (1, math.inf), (1, 1)], 0)], [([(0, 0), (1, 0), (1, 1)], -1)]])
def test_plan_fails_closed(faces):
    with pytest.raises(ValueError):
        wp.plan(faces, max_cell=1.0)


def test_wildcard_alone_in_row_fails():
    with pytest.raises(ValueError, match='wildcard'):
        wp.plan([rect(0, 1, 0, 1, None)], max_cell=1.0)


def test_embed_moves_outline_out_and_keeps_interior():
    H, Z = [0.0, 1.0, 2.0, 3.0], [0.0, 1.0, 2.0, 3.0]
    cells = {(a, b): 0 for a in range(3) for b in range(3) if (a, b) != (1, 1)}   # hole in the middle
    sh, stuck, clamped = wp.embed_shifts(cells, H, Z, 0.003)
    assert not stuck and not clamped
    assert sh[(0, 0)] == (-0.003, -0.003) and sh[(3, 3)] == (0.003, 0.003)       # outer corners go out
    assert sh[(1, 1)] == (0.003, 0.003) and sh[(2, 2)] == (-0.003, -0.003)       # hole corners go into the hole
    assert sh[(0, 1)] == (-0.003, 0)                                              # straight outer edge


def test_embed_brute_force_no_flip_and_off_outline():
    """Random cell sets on random uneven grids: every moved node leaves its outline position, no quad flips
    (each cell keeps positive width and height after the shifts)."""
    for seed in range(200):
        rng = random.Random(seed)
        H = sorted({0.0} | {round(rng.uniform(0.001, 1.0), 4) for _ in range(5)})
        Z = sorted({0.0} | {round(rng.uniform(0.001, 1.0), 4) for _ in range(5)})
        cells = {(a, b): 0 for a in range(len(H) - 1) for b in range(len(Z) - 1) if rng.random() < 0.7}
        sh, stuck, clamped = wp.embed_shifts(cells, H, Z, 0.003)
        for (a, b) in cells:
            def at(i, j):
                d = sh.get((i, j), (0, 0))
                return H[i] + d[0], Z[j] + d[1]
            p00, p10, p11, p01 = at(a, b), at(a + 1, b), at(a + 1, b + 1), at(a, b + 1)
            assert p10[0] > p00[0] and p11[0] > p01[0] and p01[1] > p00[1] and p11[1] > p10[1], (seed, a, b)
        for k in stuck:
            assert k not in sh


@pytest.mark.parametrize('emb', [0, -0.003, math.nan, math.inf])
def test_embed_fails_closed(emb):
    with pytest.raises(ValueError):
        wp.embed_shifts({(0, 0): 0}, [0, 1], [0, 1], emb)


def test_uv_segments_bound_and_fail_on_long_interval():
    assert wp.uv_segments([0, 1, 2, 3, 4.5], 2.048) == [0, 0, 2, 3]   # 2..4.5 > S: new segment at 3
    with pytest.raises(ValueError):
        wp.uv_segments([0, 3], 2.048)
