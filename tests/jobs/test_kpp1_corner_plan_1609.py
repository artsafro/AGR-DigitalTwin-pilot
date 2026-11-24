"""#1609 KPP1 quad master corners: pure planning kernel (posts as separate clean elements, conforming wall rectangle).

Pattern: n/a | new-case: tests of jobs/KPP1/lattice-1609/hooks/kpp1_elements.py (post voxels, was quad-1372/corner_plan.py).
"""
import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('corner_plan', ROOT / 'jobs/KPP1/lattice-1609/hooks/kpp1_elements.py')
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


# ---- conform_rect: the corner wall rectangle re-mesh plan (#1609 v004 rework, BM-04/BM-05/BM-09) ----

def mesh(polys, extra_items=(), extra_edges=()):
    """faces/items/edges of a wall mesh from {fid: poly}; extra = another element's vertices/edges in the plane."""
    faces = {f: [tuple(p) for p in poly] for f, poly in polys.items()}
    vf, ef = {}, {}
    for f, poly in faces.items():
        for i, p in enumerate(poly):
            vf.setdefault(p, set()).add(f)
            q = poly[(i + 1) % len(poly)]
            ef.setdefault(frozenset((p, q)), set()).add(f)
    items = [(p[0], p[1], frozenset(fs)) for p, fs in vf.items()] + list(extra_items)
    edges = [(*sorted(k), frozenset(fs)) for k, fs in ef.items()] + list(extra_edges)
    return faces, items, edges


def grid_polys(cols, rows, skip=lambda i, j: False, start=0):
    out, k = {}, start
    for i in range(len(cols) - 1):
        for j in range(len(rows) - 1):
            if not skip(i, j):
                out[k] = [(cols[i], rows[j]), (cols[i + 1], rows[j]), (cols[i + 1], rows[j + 1]), (cols[i], rows[j + 1])]
                k += 1
    return out


def fan(s0, s1, z0, z1, start):
    c = ((s0 + s1) / 2 + 0.07, (z0 + z1) / 2 - 0.05)
    ring = [(s0, z0), (s1, z0), (s1, z1), (s0, z1)]
    return {start + k: [ring[k], ring[(k + 1) % 4], c] for k in range(4)}


def test_conform_rect_replaces_fan_with_the_outer_grid_lines():
    polys = grid_polys([0, 0.5, 1, 1.5, 2], [0, 1, 2, 3], skip=lambda i, j: i < 2 and j == 1)
    polys.update(fan(0, 1, 1, 2, 100))
    r = cp.conform_rect(*mesh(polys), 0.4, 1.0, 0, 3)
    assert (r['S'], r['z0'], r['z1']) == (1.0, 0, 3)
    assert r['rows'] == [0, 1, 2, 3]            # every kept vertex on s = 1
    assert r['cols'] == [0.0, 1.0]              # bottom / top borders are free
    assert set(r['faces']) == {k for k, p in polys.items() if max(q[0] for q in p) <= 1}


def test_conform_rect_line_inside_a_kept_edge_is_rejected():
    polys = grid_polys([0, 1], [0, 1, 2, 3])
    polys[50] = [(1, 0), (2, 0), (2, 3), (1, 3)]               # one tall kept face beyond s = 1
    seams = [((0, 1.5), (1, 1.5))]                              # horizontal UV seam needs a row at 1.5
    with pytest.raises(ValueError, match='lines'):
        cp.conform_rect(*mesh(polys), 1.0, 1.0, 0, 3, seams=seams)


def test_conform_rect_min_gap_rejects_sliver_rows():
    polys = grid_polys([0, 1], [0, 1, 2, 3])
    polys.update(grid_polys([1, 2], [0, 1, 1.02, 3], start=50))   # kept neighbour with a 2 cm row
    r = cp.conform_rect(*mesh(polys), 1.0, 1.0, 0, 3)          # falls back to a smaller band, never the sliver
    assert r['area'] < 3 and all(b - a >= 0.03 for a, b in zip(r['rows'], r['rows'][1:]))
    r = cp.conform_rect(*mesh(polys), 1.0, 1.0, 0, 3, min_gap=0.01)
    assert r['area'] == 3 and r['rows'] == [0, 1, 1.02, 3]


def test_conform_rect_attached_element_inside_is_rejected():
    polys = grid_polys([0, 1, 2], [0, 1, 2])
    attached = [(0.5, 1.0, frozenset({'cornice'}))]            # another element welded to the wall inside
    with pytest.raises(ValueError, match='attached'):           # inside, or on a border inside a kept edge
        cp.conform_rect(*mesh(polys, extra_items=attached), 0.5, 2, 0, 2)
    r = cp.conform_rect(*mesh(polys), 0.5, 2, 0, 2)                 # the same wall without it: whole wall
    assert (r['S'], r['z0'], r['z1']) == (2, 0, 2)


def test_conform_rect_opening_rejected_dontcare_fills_post_strip():
    polys = grid_polys([0.01, 1, 2], [0, 1, 2])                 # post contact strip 0..0.01 has no wall face
    with pytest.raises(ValueError, match='coverage'):
        cp.conform_rect(*mesh(polys), 1, 1, 0, 2)
    r = cp.conform_rect(*mesh(polys), 1, 1, 0, 2, dontcare=[(0, 0.01, 0, 2)])
    assert (r['S'], r['z0'], r['z1'], r['cols']) == (1, 0, 2, [0.0, 1])


def test_conform_rect_slanted_seam_rejected():
    polys = grid_polys([0, 1], [0, 2])
    with pytest.raises(ValueError, match='slanted'):
        cp.conform_rect(*mesh(polys), 1, 1, 0, 2, seams=[((0, 0), (1, 2))])


@pytest.mark.parametrize('kw', [dict(s_lo=math.nan), dict(s_lo=0), dict(z_hi=-1), dict(min_gap=0), dict(z_lo=math.inf)])
def test_conform_rect_fail_closed_args(kw):
    args = dict(s_lo=0.5, s_hi=1, z_lo=0, z_hi=2)
    args.update(kw)
    with pytest.raises(ValueError):
        cp.conform_rect(*mesh(grid_polys([0, 1], [0, 2])), **args)


def test_conform_rect_fail_closed_inputs():
    with pytest.raises(ValueError, match='no wall faces'):
        cp.conform_rect({}, [], [], 0.5, 1, 0, 1)
    with pytest.raises(ValueError, match='bad wall face'):
        cp.conform_rect({1: [(0, 0), (1, math.nan), (1, 1)]}, [], [], 0.5, 1, 0, 1)
    with pytest.raises(ValueError, match='beyond the corner'):
        cp.conform_rect({1: [(-0.1, 0), (1, 0), (1, 1)]}, [], [], 0.5, 1, 0, 1)


def _verify_plan(r, faces, items, edges, min_gap, tol=cp.CORNER_TOL):
    """Independent check of a plan: whole faces, every kept border vertex a line, no line inside a kept edge."""
    S, z0, z1, cols, rows = r['S'], r['z0'], r['z1'], r['cols'], r['rows']
    inside = set(r['faces'])
    for f, poly in faces.items():
        inn = [(-tol <= s <= S + tol and z0 - tol <= z <= z1 + tol) for s, z in poly]
        cen = (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
        if 0 < cen[0] < S and z0 < cen[1] < z1:
            assert f in inside and all(inn)
        else:
            assert f not in inside
    assert all(b - a >= min_gap - tol for a, b in zip(cols, cols[1:]))
    assert all(b - a >= min_gap - tol for a, b in zip(rows, rows[1:]))
    nodes = {(c, z) for c in cols for z in (z0, z1)} | {(s, z) for s in (0, S) for z in rows}
    for s, z, fids in items:
        if set(fids) - inside and -tol <= s <= S + tol and z0 - tol <= z <= z1 + tol:
            assert any(abs(s - a) <= tol and abs(z - b) <= tol for a, b in nodes), (s, z)
    for p, q, fids in edges:
        if not set(fids) - inside:
            continue
        for a, b in nodes:
            on_seg = (abs((q[0] - p[0]) * (b - p[1]) - (q[1] - p[1]) * (a - p[0])) <= 1e-9
                      and min(p[0], q[0]) - tol <= a <= max(p[0], q[0]) + tol
                      and min(p[1], q[1]) - tol <= b <= max(p[1], q[1]) + tol)
            at_end = any(abs(a - v[0]) <= tol and abs(b - v[1]) <= tol for v in (p, q))
            assert not (on_seg and not at_end), ('T-junction', (a, b), p, q)


def test_conform_rect_random_walls_never_plan_a_t_junction():
    rng = random.Random(1609)
    planned = 0
    for _ in range(120):
        cols = sorted({0.0} | {round(rng.uniform(0.05, 3.0), 3) for _ in range(rng.randint(2, 6))})
        rows = sorted({round(rng.uniform(0, 4), 3) for _ in range(rng.randint(3, 7))})
        if len(rows) < 2 or len(cols) < 2:
            continue
        merged = set()
        polys, k = {}, 0
        for i in range(len(cols) - 1):
            for j in range(len(rows) - 1):
                if (i, j) in merged:
                    continue
                if j + 2 < len(rows) and rng.random() < 0.25:      # a tall kept face (long edge on a border)
                    merged.add((i, j + 1))
                    polys[k] = [(cols[i], rows[j]), (cols[i + 1], rows[j]), (cols[i + 1], rows[j + 2]), (cols[i], rows[j + 2])]
                elif rng.random() < 0.2:
                    polys.update(fan(cols[i], cols[i + 1], rows[j], rows[j + 1], 1000 + 10 * k))
                else:
                    polys[k] = [(cols[i], rows[j]), (cols[i + 1], rows[j]), (cols[i + 1], rows[j + 1]), (cols[i], rows[j + 1])]
                k += 1
        faces, items, edges = mesh(polys)
        try:
            r = cp.conform_rect(faces, items, edges, 0.05, 3.0, rows[0], rows[-1], min_gap=0.03)
        except ValueError:
            continue
        _verify_plan(r, faces, items, edges, 0.03)
        planned += 1
    assert planned >= 60
