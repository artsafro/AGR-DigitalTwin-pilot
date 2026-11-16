"""#1609 KPP1 quad master corners: pure planning kernel (posts as separate clean elements, wall strip grid)."""
import importlib.util
import itertools
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('corner_plan', ROOT / 'jobs/KPP1/quad-1372/corner_plan.py')
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def box_tris(x0, x1, y0, y1, z0, z1, diag=0):
    c = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    idx = lambda i, j, k: c[i * 4 + j * 2 + k]  # noqa: E731
    quads = [[idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)], [idx(1, 0, 0), idx(1, 1, 0), idx(1, 1, 1), idx(1, 0, 1)],
             [idx(0, 0, 0), idx(1, 0, 0), idx(1, 0, 1), idx(0, 0, 1)], [idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1), idx(0, 1, 1)],
             [idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)], [idx(0, 0, 1), idx(1, 0, 1), idx(1, 1, 1), idx(0, 1, 1)]]
    out = []
    for q in quads:
        q = q[diag:] + q[:diag]
        out += [(q[0], q[1], q[2]), (q[0], q[2], q[3])]
    return out


def test_snap_prefers_body_plane_and_merges_sub_mm_planes():
    reps, m = cp.snap_values([-15.0753, -15.075, -14.985, -14.9853, -14.975], prefer=[-14.985])
    assert reps == [-15.0752, -14.985, -14.975] or reps[1:] == [-14.985, -14.975]
    assert m[-14.9853] == -14.985 and m[-14.975] == -14.975


@pytest.mark.parametrize('bad', [[math.nan], [math.inf, 1.0]])
def test_snap_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        cp.snap_values(bad)


def test_snap_rejects_two_preferred_in_one_cluster():
    with pytest.raises(ValueError):
        cp.snap_values([0.0, 0.0002], prefer=[0.0, 0.0002])


def test_post_cells_two_stacked_boxes_one_clean_element():
    tris = box_tris(0, 0.09, 0, 0.2, 1, 2) + box_tris(-0.1, 0.1, 0.05, 0.12, 2, 3, diag=1)  # coincident contact layer
    xs, ys, zs = [-0.1, 0, 0.09, 0.1], [0, 0.05, 0.12, 0.2], [1, 2, 3]
    cells = cp.post_cells(tris, xs, ys, zs)
    assert len(cells) == 3 + 3          # lower box 1x3 cells, upper 3x1
    faces = cp.post_faces(cells, xs, ys, zs)
    # closed, conforming: every edge used exactly twice
    edges = {}
    for corners, _ in faces:
        for a, b in zip(corners, corners[1:] + corners[:1]):
            edges[frozenset((a, b))] = edges.get(frozenset((a, b)), 0) + 1
    assert set(edges.values()) == {2}
    # no coincident internal face at z = 2 under the upper box footprint
    assert not any(all(c[2] == 2 for c in q) and 0 <= sum(c[0] for c in q) / 4 <= 0.09
                   and 0.05 <= sum(c[1] for c in q) / 4 <= 0.12 for q, _ in faces)


def test_post_faces_outward_normals():
    tris = box_tris(0, 1, 0, 1, 0, 1)
    cells = cp.post_cells(tris, [0, 1], [0, 1], [0, 1])
    for corners, n in cp.post_faces(cells, [0, 1], [0, 1], [0, 1]):
        a, b, c = corners[0], corners[1], corners[2]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - a[k] for k in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        assert sum(cross[k] * n[k] for k in range(3)) > 0


def test_post_faces_hidden_contact_dropped():
    tris = box_tris(0, 1, 0, 1, 0, 1)
    cells = cp.post_cells(tris, [0, 1], [0, 1], [0, 1])
    faces = cp.post_faces(cells, [0, 1], [0, 1], [0, 1], hidden=lambda c, n: n == (1, 0, 0))
    assert len(faces) == 5


def test_post_cells_open_box_parity_disagreement_is_error():
    tris = [t for t in box_tris(0, 1, 0, 1, 0, 1) if not all(p[2] == 1 for p in t)]  # top missing
    with pytest.raises(ValueError, match='parity'):
        cp.post_cells(tris, [0, 1], [0, 1], [0, 1])


def wall(rects, tile=(2, 0)):
    return [([(s0, z0), (s1, z0), (s1, z1), (s0, z1)], tile) for s0, s1, z0, z1 in rects]


def test_wall_strip_picks_clean_rectangle_and_avoids_crossing_and_openings():
    faces = wall([(0, 0.3, 3.9, 5), (0.3, 0.6, 3.9, 5), (0, 0.6, 5, 7.1), (0.6, 2.0, 3.9, 7.1),   # crosses s = 0.6? no
                  (0, 0.45, 7.1, 8.65), (0.45, 1.5, 7.1, 8.65)])
    r = cp.wall_strip(faces, 0.3, 0.8)
    assert (r['S'], r['z0'], r['z1']) == (0.6, 3.9, 7.1)
    assert sorted(r['faces']) == [0, 1, 2]


def test_wall_strip_opening_inside_is_rejected():
    faces = wall([(0, 0.6, 3.9, 5), (0, 0.6, 6, 7)])           # hole 5..6
    r = cp.wall_strip(faces, 0.3, 0.8)
    assert r['z1'] - r['z0'] == pytest.approx(1.1)


@pytest.mark.parametrize('faces', [[], [([(0, 0), (1, 0), (math.nan, 1)], (0, 0))], [([(-0.01, 0), (1, 0), (1, 1)], (0, 0))]])
def test_wall_strip_fail_closed(faces):
    with pytest.raises(ValueError):
        cp.wall_strip(faces, 0.3, 0.8)


def test_wall_strip_brute_force_never_returns_crossed_rectangle():
    rng = random.Random(1609)
    for _ in range(60):
        # random guillotine partition of [0, 2] x [0, 4]
        rects = [(0, 2, 0, 4)]
        for _ in range(rng.randint(2, 9)):
            i = rng.randrange(len(rects))
            s0, s1, z0, z1 = rects.pop(i)
            if rng.random() < 0.5 and s1 - s0 > 0.2:
                c = round(rng.uniform(s0 + 0.1, s1 - 0.1), 3)
                rects += [(s0, c, z0, z1), (c, s1, z0, z1)]
            elif z1 - z0 > 0.2:
                c = round(rng.uniform(z0 + 0.1, z1 - 0.1), 3)
                rects += [(s0, s1, z0, c), (s0, s1, c, z1)]
            else:
                rects.append((s0, s1, z0, z1))
        drop = rng.randrange(len(rects)) if rng.random() < 0.3 else None
        faces = wall([r for k, r in enumerate(rects) if k != drop])
        try:
            r = cp.wall_strip(faces, 0.3, 1.5)
        except ValueError:
            continue
        for poly, _ in faces:
            ss, zs = [p[0] for p in poly], [p[1] for p in poly]
            inter = min(max(ss), r['S']) - max(min(ss), 0) > 1e-9 and min(max(zs), r['z1']) - max(min(zs), r['z0']) > 1e-9
            if inter:
                assert max(ss) <= r['S'] + 1e-9 and min(zs) >= r['z0'] - 1e-9 and max(zs) <= r['z1'] + 1e-9


def test_grid_lines_even_and_required():
    g = cp.grid_lines(3.9, 8.65, required=[7.1], step=0.6)
    assert g[0] == 3.9 and g[-1] == 8.65 and 7.1 in g
    assert max(b - a for a, b in zip(g, g[1:])) <= 0.6 + 1e-9


@pytest.mark.parametrize('args', [(1, 1), (0, math.nan), (0, 1, [0.5, 0.52])])
def test_grid_lines_fail_closed(args):
    with pytest.raises(ValueError):
        cp.grid_lines(*args)


def test_affine_uv_exact_and_seam_rejected():
    pts = [(0, 0), (1, 0), (1, 2), (0, 2)]
    f = cp.affine_uv(pts, [(0.1, 0.2), (0.6, 0.2), (0.6, 1.2), (0.1, 1.2)])
    assert f(0.5, 1) == pytest.approx((0.35, 0.7))
    with pytest.raises(ValueError, match='not affine'):
        cp.affine_uv(pts, [(0.1, 0.2), (0.6, 0.2), (0.6, 1.2), (0.3, 1.2)])
    with pytest.raises(ValueError, match='degenerate'):
        cp.affine_uv([(0, 0), (1, 0), (2, 0)], [(0, 0)] * 3)


def test_module_docstring_marks_new_case():
    assert 'new-case' in (cp.__doc__ or '')


def test_post_cells_skip_body_voxels_then_contact_faces_hidden():
    # post 0..1 penetrating 0.1 into the body at x >= 1 (open there in the source: no x = 1.1 face)
    tris = [t for t in box_tris(0, 1.1, 0, 1, 0, 1) if not all(p[0] == 1.1 for p in t)]
    xs = [0, 1, 1.1]
    assert cp.post_cells(tris, xs, [0, 1], [0, 1]) == {(0, 0, 0), (1, 0, 0)}
    cells = cp.post_cells(tris, xs, [0, 1], [0, 1], skip=lambda c: c[0] > 1)
    assert cells == {(0, 0, 0)}
    faces = cp.post_faces(cells, xs, [0, 1], [0, 1], hidden=lambda c, n: n == (1, 0, 0) and c[0] == 1)
    assert len(faces) == 5


def test_clip_area():
    assert cp.clip_area([(0, 0), (2, 0), (2, 2), (0, 2)], 1, 3, 0, 1) == pytest.approx(1.0)
    assert cp.clip_area([(0, 0), (2, 0), (0, 2)], 0, 1, 0, 1) == pytest.approx(1.0)
    assert cp.clip_area([(5, 5), (6, 5), (6, 6)], 0, 1, 0, 1) == 0.0


@pytest.mark.parametrize('poly,S,kind', [
    ([(0, 0), (1, 0), (1, 1), (0, 1)], 0.5, 'clean'),
    ([(0, 0), (1, 0), (1, 1), (0, 1)], 1.0, 'left'),
    ([(0, 0), (1, 0), (1, 1), (0.6, 1)], 0.5, 'bad'),        # adjacent edges -> triangle + pentagon
    ([(0, 0), (1, 0), (1, 1), (0.5, 1)], 0.5, 'bad'),        # through a corner
    ([(0, 0), (1, 0), (0.5, 1)], 0.3, 'bad'),
])
def test_cut_kind(poly, S, kind):
    assert cp.cut_kind(poly, S) == kind


def test_strip_cut_prefers_existing_line_then_clean_cut_and_rejects_openings():
    faces = [[(0, 0), (0.62, 0), (0.62, 1), (0, 1)], [(0.62, 0), (2, 0), (2, 1), (0.62, 1)],
             [(0, 1), (0.9, 1), (0.9, 2), (0, 2)], [(0.9, 1), (2, 1), (2, 2), (0.9, 2)],
             [(0, 2), (0.62, 2), (0.62, 3), (0, 3)], [(0.62, 2), (2, 2), (2, 3), (0.62, 3)]]
    r = cp.strip_cut(faces, 0, 3, 0.3, 0.8, 0.6)
    assert r['cut'] == [2] and r['inside'] == [0, 4] and r['S'] == pytest.approx(0.62)
    faces2 = faces + [[(0, 3), (0.6, 3), (0.6, 4), (0, 4)]]          # z1 = 4 but the right faces stop at 3: an opening above
    with pytest.raises(ValueError, match='covered'):
        cp.strip_cut(faces2, 0, 4, 0.7, 0.8, 0.75)      # S >= 0.7 reaches past the 0.6 m top face
    with pytest.raises(ValueError, match='straddles'):
        cp.strip_cut(faces, 0.5, 3, 0.3, 0.8, 0.6)
    with pytest.raises(ValueError):
        cp.strip_cut(faces, 0, math.nan, 0.3, 0.8, 0.6)
    with pytest.raises(ValueError):
        cp.strip_cut([], 0, 3, 0.3, 0.8, 0.6)


def test_strip_cut_never_cuts_a_border_edge():
    # one tall face 0..1 x 0..2 whose top/bottom edges are the strip borders: cutting it splits its neighbours
    faces = [[(0, 0), (1, 0), (1, 2), (0, 2)]]
    with pytest.raises(ValueError, match='badly'):
        cp.strip_cut(faces, 0, 2, 0.3, 0.8, 0.6)


def test_lone_corner_is_the_vertex_to_snap():
    assert cp.lone_corner([(0, 0), (1, 0), (1, 1), (0.6, 1)], 0.5) == 0     # (0, 0) alone left of the line
    assert cp.lone_corner([(0, 0), (1, 0), (1, 1), (0, 1)], 0.5) is None     # clean 2 + 2


def test_strip_cut_allow_bad_reports_count():
    faces = [[(0, 0), (1, 0), (1, 1), (0.55, 1)], [(0, 0), (0.55, 1), (0, 1)][:3] + [(0, 0.5)]]
    r = cp.strip_cut(faces, 0, 1, 0.5, 0.52, 0.5, allow_bad=True)
    assert r['bad'] >= 1
    with pytest.raises(ValueError, match='badly'):
        cp.strip_cut(faces, 0, 1, 0.5, 0.52, 0.5)


def test_grid_lines_merges_rounded_copies_of_one_line():
    g = cp.grid_lines(0.0, 0.699999, [0.7, 0.35, 0.35004], step=0.6)
    assert g == [0.0, 0.35, 0.699999]
