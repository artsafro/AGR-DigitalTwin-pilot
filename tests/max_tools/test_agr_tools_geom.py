"""new-case: AGR Tools 0.8 branch A (#908): model.triangulate, ucx.triangulate, export.pivot_place (geom_core.py).

Plain pytest, no pymxs. Every defect named in docs/experiments/<id>.md gets a regression test that is RED on a
behaviour model of the measured source (lab L01/L02, no GeoAGR code, #853) and GREEN on geom_core.py.
The `source_*` helpers below model only what the lab measured; they are not GeoAGR code.
"""
import ast
import importlib.util
import math
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


g = _load(PKG / 'geom_core.py', 'agr_tools_geom_core_t')
ucx = _load(PKG / 'ucx_core.py', 'agr_tools_ucx_core')
ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_geom_t')


# ---- shapes -------------------------------------------------------------------------------------------
def ngon(r, n=8, c=(0.0, 0.0, 0.0), z=None):
    return [(c[0] + r * math.cos(2 * math.pi * i / n), c[1] + r * math.sin(2 * math.pi * i / n),
             c[2] if z is None else z) for i in range(n)]


def u_shape(s):
    pts = [(0, 0), (6, 0), (6, 6), (4, 6), (4, 2), (2, 2), (2, 6), (0, 6)]
    return [(x * s / 6, y * s / 6, 0.0) for x, y in pts]


def comb12():
    pts = [(0, 0), (10, 0), (10, 4), (8, 4), (8, 1), (6, 1), (6, 4), (4, 4), (4, 1), (2, 1), (2, 4), (0, 4)]
    return [(float(x), float(y), 0.0) for x, y in pts]


def nonplanar_hex():
    return [(p[0], p[1], 0.15 * (-1) ** i) for i, p in enumerate(ngon(1.0, 6))]


def area2d(pts):
    flat, _, _ = g.project(pts)
    return 0.5 * abs(sum(flat[i][0] * flat[(i + 1) % len(flat)][1] - flat[(i + 1) % len(flat)][0] * flat[i][1]
                         for i in range(len(flat)))), flat


def assert_valid(pts, t):
    """n-3 diagonals, n-2 triangles that tile the projected outline exactly (no overlap, nothing outside)."""
    n = len(pts)
    assert len(t['diagonals']) == n - 3 and len(t['triangles']) == n - 2
    assert not g.diagonals_cross(pts, t['diagonals'])
    area, flat = area2d(pts)
    tri_area = 0.0
    for a, b, c in t['triangles']:
        signed = g._orient2(flat[a], flat[b], flat[c])
        assert signed > 0, 'flipped or zero-area triangle'
        tri_area += 0.5 * signed
    assert math.isclose(tri_area, area, rel_tol=1e-9)


# ---- source behaviour models (lab L01 / L02 measurements) ---------------------------------------------
def source_triangulate_pairs(pts):
    """Lab L01: the DLL uses absolute 1e-6 thresholds in scene units and returns every visible pair
    (octagon 20 pairs for 5 needed). Below the threshold it returns nothing: the face stays an n-gon."""
    n = len(pts)
    nrm = g.newell_normal(pts)
    if g._length(nrm) / 2.0 < 1e-6:  # area in scene units (m^2) against an absolute threshold
        return []
    return [(i, j) for i in range(n) for j in range(i + 2, n) if not (i == 0 and j == n - 1)]


def source_ucx_triangles(poly):
    """Lab L01 ucx.triangulate: Max Connect on all vertices; on a quad the diagonal ignores convexity."""
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def source_ucx_processed(base_class, modifiers):
    """Lab L01: only Editable Poly without modifiers is touched; the rest is skipped silently (no list)."""
    return base_class == 'Editable_Poly' and modifiers == 0


def source_text(x):
    return '%g' % x  # Get Pivot: ~6 significant digits, exponent at 1e6 (lab L02)


def source_rotation_z(angle_ui):
    return -angle_ui  # lab L02: field shows -30 for a model turned +30 in the UI


def source_empty_field(text):
    return float(text) if text.strip() else 0.0  # lab L02: empty field read as 0, object moved


# ---- model.triangulate ------------------------------------------------------------------------------------
@pytest.mark.parametrize('r', [1000.0, 1.0, 1e-3, 5e-4, 3e-4, 1e-4])
def test_defect1_small_octagons_stay_ngons_in_source_and_triangulate_here(r):
    pts = ngon(r, 8, c=(12345.678, -6789.012, 150.0))
    small = r < 1e-3
    assert (source_triangulate_pairs(pts) == []) == small  # RED for r <= 0.5 mm (lab: stayed 8-gons)
    t = g.triangulate_polygon(pts)
    assert_valid(pts, t)
    assert not t['degenerate']


@pytest.mark.parametrize('size', [6.0, 6e-4])
def test_defect1_concave_u_at_6m_and_0_6mm(size):
    pts = u_shape(size)
    if size < 1e-3:
        assert source_triangulate_pairs([(x, y * 0.5, z) for x, y, z in pts]) == []  # lab: 0.6 x 0.3 mm outline
    assert_valid(pts, g.triangulate_polygon(pts))


def test_scale_free_same_diagonals_for_the_same_shape():
    big = g.triangulate_polygon(u_shape(6000.0))['diagonals']
    assert g.triangulate_polygon(u_shape(6e-4))['diagonals'] == big
    shifted = [(x + 2345678.912, y + 1234567.891, 150.0) for x, y, _ in u_shape(6.0)]
    assert g.triangulate_polygon(shifted)['diagonals'] == g.triangulate_polygon(u_shape(6.0))['diagonals']


def test_defect2_exactly_n_minus_3_pairs_not_every_visible_pair():
    octo = ngon(1.0)
    assert len(source_triangulate_pairs(octo)) == 20  # lab: 20 pairs for 5 needed
    assert len(g.triangulate_polygon(octo)['diagonals']) == 5


def test_defect2_400_hexagons_1200_pairs_under_2s():
    hexes = [ngon(1.0, 6, c=(3.0 * x, 3.0 * y, 0.0)) for x in range(20) for y in range(20)]
    assert sum(len(source_triangulate_pairs(h)) for h in hexes) > 1200
    t0 = time.perf_counter()
    rows, degenerate = g.plan_faces([{'face': i + 1, 'verts': list(range(6 * i + 1, 6 * i + 7)), 'points': h}
                                     for i, h in enumerate(hexes)])
    assert time.perf_counter() - t0 < 2.0
    assert sum(len(r['pairs']) for r in rows) == 1200 and not degenerate


@pytest.mark.parametrize('shape', ['comb12', 'nonplanar_hex', 'ngon64', 'octagon_1km'])
def test_acceptance_shapes_valid(shape):
    pts = {'comb12': comb12, 'nonplanar_hex': nonplanar_hex, 'ngon64': lambda: ngon(1.0, 64),
           'octagon_1km': lambda: ngon(1000.0)}[shape]()
    t = g.triangulate_polygon(pts)
    assert_valid(pts, t)
    assert t['planar'] == (shape != 'nonplanar_hex')


def test_delaunay_flips_avoid_long_slivers():
    """A thin strip with many corners: the fan from one corner makes slivers, the result does not."""
    strip = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (3.0, 0.0, 0.0), (3.0, 1.0, 0.0), (2.0, 1.0, 0.0),
             (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    t = g.triangulate_polygon(strip)
    flat, _, _ = g.project(strip)
    ours = min(g._quality(*(flat[i] for i in tri)) for tri in t['triangles'])
    fan = min(g._quality(flat[0], flat[i], flat[i + 1]) for i in range(1, 7) if g._orient2(flat[0], flat[i],
                                                                                          flat[i + 1]) > 0)
    assert ours > fan and math.degrees(ours) > 40


def test_thin_strip_10m_by_half_mm():
    strip = [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 5e-4, 0.0), (5.0, 5e-4, 0.0),
             (0.0, 5e-4, 0.0)]
    assert_valid(strip, g.triangulate_polygon(strip))


def test_collinear_outline_is_reported_degenerate_but_still_has_n_minus_3():
    line = [(float(i), 0.0, 0.0) for i in range(5)]
    t = g.triangulate_polygon(line)
    assert t['degenerate'] and len(t['diagonals']) == 2


def test_zero_ngon_assertion_and_plan_ids():
    assert g.assert_triangulated([3, 3, 3]) == []
    assert g.assert_triangulated([3, 4, 3, 8]) == [2, 4]
    rows, _ = g.plan_faces([{'face': 7, 'verts': [11, 12, 13, 14], 'points': ngon(1.0, 4)},
                            {'face': 8, 'verts': [1, 2, 3], 'points': ngon(1.0, 3)}])
    assert len(rows) == 1 and rows[0]['face'] == 7 and len(rows[0]['pairs']) == 1
    assert set(rows[0]['pairs'][0]) in ({11, 13}, {12, 14})
    with pytest.raises(ValueError):
        g.plan_faces([{'face': 1, 'verts': [1, 2, 2, 3], 'points': ngon(1.0, 4)}])
    with pytest.raises(ValueError):
        g.triangulate_polygon([(0.0, 0.0, float('nan')), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (1.0, 1.0, 0.0)])


# ---- ucx.triangulate --------------------------------------------------------------------------------------
BOX_QUADS = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def box(raise_corner=None, dz=0.6):
    pts = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0], [0, 0, 2], [2, 0, 2], [2, 2, 2], [0, 2, 2]]
    if raise_corner is not None:
        pts[raise_corner][2] += dz
    return [tuple(float(c) for c in p) for p in pts], [list(q) for q in BOX_QUADS]


def prism(n, r=1.0, h=2.0, mid=False):
    ring = ngon(r, n)
    if mid:  # square prism with mid-edge vertices
        ring = [(1.0, -1.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (-1.0, 1.0, 0.0),
                (-1.0, 0.0, 0.0), (-1.0, -1.0, 0.0), (0.0, -1.0, 0.0)]
        n = len(ring)
    pts = [(x, y, 0.0) for x, y, _ in ring] + [(x, y, h) for x, y, _ in ring]
    polys = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    polys += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return pts, polys


def triangles_after(pts, polys, plan):
    """Triangles of the piece after applying plan pairs (rebuilt per polygon from ucx_polygon)."""
    tris = []
    sign = 1.0
    for p in polys:
        tris.extend(g.ucx_polygon(pts, p, [pts[v] for v in p], 1e-4, sign) or [])
    return tris


@pytest.mark.parametrize('corner', [4, 5])
def test_defect1_raised_corner_source_breaks_convexity_ours_keeps_it(corner):
    pts, polys = box(raise_corner=corner)
    src = [t for p in polys for t in source_ucx_triangles(p)]
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert plan['action'] == 'diagonals' and len(plan['pairs']) == 6
    ours = triangles_after(pts, polys, plan)
    assert ucx.convexity(pts, ours)['ok'] and len(src) == len(ours)


def test_defect1_source_fails_on_one_of_the_two_raised_corners():
    """Lab: 'the chosen diagonal made the piece non-convex in one of two cases'."""
    verdicts = []
    for corner in (4, 5):
        pts, polys = box(raise_corner=corner)
        verdicts.append(ucx.convexity(pts, [t for p in polys for t in source_ucx_triangles(p)])['convex'])
    assert sorted(verdicts) == [False, True]  # RED on the source model
    for corner in (4, 5):  # GREEN here
        pts, polys = box(raise_corner=corner)
        assert ucx.convexity(pts, triangles_after(pts, polys, g.ucx_plan(pts, polys, 1e-4)))['ok']


@pytest.mark.parametrize('piece', ['box', 'oct_prism', 'mid_edge_prism', 'prism64'])
def test_acceptance_pieces_triangulate_convex_closed(piece):
    pts, polys = {'box': box, 'oct_prism': lambda: prism(8), 'mid_edge_prism': lambda: prism(4, mid=True),
                  'prism64': lambda: prism(64)}[piece]()
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert plan['action'] == 'diagonals'
    assert len(plan['pairs']) == sum(len(p) - 3 for p in polys)
    tris = triangles_after(pts, polys, plan)
    chk = ucx.convexity(pts, tris)
    assert chk['ok'] and chk['closed'] and not chk['zero_area'], chk


def test_non_convex_piece_falls_back_to_its_convex_hull():
    pts = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    pts = [tuple(float(c) for c in p) for p in pts] + [(float(x), float(y), 1.0) for x, y, _ in pts]
    n = 6
    polys = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    polys += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert plan['action'] == 'hull' and 'not convex' in plan['reason']
    chk = ucx.convexity(plan['hull']['verts'], [tuple(t) for t in plan['hull']['tris']])
    assert chk['ok'], chk


def test_triangles_only_piece_needs_nothing():
    pts, polys = box()
    tris = [list(t) for p in polys for t in source_ucx_triangles(p)]
    assert g.ucx_plan(pts, tris, 1e-4)['action'] == 'none'


def test_convexity_post_check_detects_open_flipped_and_dented():
    pts, polys = box()
    tris = [t for p in polys for t in source_ucx_triangles(p)]
    assert ucx.convexity(pts, tris)['ok']
    assert ucx.convexity(pts, [t[::-1] for t in tris])['ok']  # fully flipped piece judged by shape
    open_chk = ucx.convexity(pts, tris[:-1])
    assert not open_chk['ok'] and not open_chk['closed'] and open_chk['open_edges'] > 0
    dented = [list(p) for p in pts]
    dented[6][2] = 1.0  # top corner pushed in by 1 m
    assert not ucx.convexity([tuple(p) for p in dented], tris)['convex']
    raised = [list(p) for p in pts]
    raised[6][2] = 2.0 + 5e-5  # within the 1e-4 m tolerance
    assert ucx.convexity([tuple(p) for p in raised], tris, tol=1e-4)['convex']


def test_defect2_non_poly_pieces_converted_or_listed_never_silent():
    cases = [('Box', 0, True), ('Editable_mesh', 0, True), ('Editable_Poly', 1, True), ('Editable_Poly', 0, True),
             ('line', 0, False)]
    assert [source_ucx_processed(c, m) for c, m, _ in cases] == [False, False, False, True, False]  # RED: silent
    got = [g.classify(c, m, conv) for c, m, conv in cases]
    assert [k for k, _ in got] == ['convert', 'convert', 'convert', 'poly', 'skip']
    assert all(why for k, why in got if k != 'poly')
    assert ec.skipped('UCX_line', got[-1][1])['reason']
    assert g.is_ucx_name('ucx_SM_A_01') and not g.is_ucx_name('SM_A')


# ---- export.pivot_place -----------------------------------------------------------------------------------
@pytest.mark.parametrize('x, lost', [(12345.678, 0.02), (2345678.912, 1.0)])
def test_defect_precision_get_set_roundtrip(x, lost):
    assert abs(float(source_text(x)) - x) > lost  # RED: 2.3 cm at 1e4, metres at 1e6 (lab 2.35 m)
    assert ('e+' in source_text(x)) == (x > 1e6)  # lab: '2.34568e+06' in the field
    text = g.fmt(x)
    assert 'e' not in text.lower() and text.count('.') == 1 and len(text.split('.')[1]) == g.DECIMALS
    assert abs(float(text) - x) <= 0.5e-4  # GREEN: fixed decimals, 0.1 mm
    assert g.fmt(-0.0) == '0.0000' and g.fmt(-1e-9) == '0.0000'
    assert g.fmt_point([1e6, -2.5, 150]) == ['1000000.0000', '-2.5000', '150.0000']


def rows_from_euler(x, y, z):
    """Max row-vector rotation rows for Euler XYZ degrees as the UI shows them: M = Rx * Ry * Rz."""
    def mat(axis, a):
        c, s = math.cos(math.radians(a)), math.sin(math.radians(a))
        return {'x': [[1, 0, 0], [0, c, s], [0, -s, c]], 'y': [[c, 0, -s], [0, 1, 0], [s, 0, c]],
                'z': [[c, s, 0], [-s, c, 0], [0, 0, 1]]}[axis]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(mat('x', x), mat('y', y)), mat('z', z))


def test_defect_rotation_sign_as_the_ui_shows_it():
    rows = rows_from_euler(0, 0, 30)
    assert rows[0][1] > 0  # row1 = (cos30, sin30, 0) for +30 about Z in Max
    assert source_rotation_z(30) == -30  # RED
    assert [round(v, 9) for v in g.euler_ui(rows)] == [0.0, 0.0, 30.0]  # GREEN
    for xyz in ((10, 20, 30), (-45, 15, 170), (90, 0, 0), (0, -60, -120)):
        assert [round(v, 6) for v in g.euler_ui(rows_from_euler(*xyz))] == [float(v) for v in xyz]
    scaled = [[c * 2.5 for c in r] for r in rows_from_euler(0, 0, 30)]
    assert round(g.euler_ui(scaled)[2], 9) == 30.0


SLAB_TOP = [(-11.0, -6.0, 150.0), (11.0, -6.0, 150.0), (11.0, 6.0, 150.0), (-11.0, 6.0, 150.0)]


def test_defect_floor_from_vertices_is_min_z_not_neighbour_face_centres():
    neighbour_faces = [[(-11.0, -6.0, 150.0), (11.0, -6.0, 150.0), (11.0, -6.0, 149.4), (-11.0, -6.0, 149.4)],
                       [(-10.0, -5.0, 150.0), (10.0, -5.0, 150.0), (10.0, -5.0, 159.0), (-10.0, -5.0, 159.0)]]
    source = [sum(p[2] for p in f) / 4 for f in neighbour_faces]  # bbox centres of faces around the vertices
    assert source == [149.7, 154.5] or all(abs(s - 150.0) > 0.25 for s in source)  # RED (lab 149.7 / 154.2)
    assert g.floor_level([p[2] for p in SLAB_TOP]) == (150.0, 'selection')  # GREEN


def test_defect_no_selection_refuses_instead_of_bbox_bottom():
    bbox_bottom = 149.4  # lab: 0.6 m below the clean floor over a slab
    assert bbox_bottom != 150.0
    with pytest.raises(ValueError, match='bbox bottom is never used'):
        g.floor_level([])
    assert g.floor_level([], explicit='150,000') == (150.0, 'explicit')


def test_defect_sloped_face_uses_min_not_centre():
    sloped = [(0.0, 0.0, 150.0), (4.0, 0.0, 150.0), (4.0, 3.0, 151.2), (0.0, 3.0, 151.2)]
    assert sum(p[2] for p in sloped) / 4 != 150.0  # RED: face centre
    assert g.floor_level([p[2] for p in sloped])[0] == 150.0


@pytest.mark.parametrize('bad', ['', '   ', 'abc', '1e6', 'nan', 'inf', '1.2.3', '--1', None, True, [150]])
def test_defect_empty_or_invalid_field_is_refused(bad):
    if bad == '':
        assert source_empty_field(bad) == 0.0  # RED: read as 0, object moved without a warning
    with pytest.raises(ValueError):
        g.parse_level(bad)


@pytest.mark.parametrize('text, value', [('150', 150.0), ('+150.000', 150.0), ('150,5', 150.5), ('-0.000', 0.0),
                                         ('−2.5', -2.5), ('.5', 0.5), (150, 150.0)])
def test_level_accepts_plain_decimals(text, value):
    assert g.parse_level(text) == value


def test_defect_combine_near_zero_keeps_the_offset():
    a_centre, b_centre = (12345.678, -6789.012, 155.0), (12375.678, -6789.012, 151.0)
    source = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]  # lab: both bbox centres aligned at zero, offset lost
    assert source[0] == source[1]
    pivot = g.pivot_point((12335.678, -6795.012, 149.4), (12385.678, -6783.012, 159.0), 150.0)
    moved = g.vpm_translate([a_centre, b_centre], pivot)
    assert [moved[1][i] - moved[0][i] for i in range(3)] == [30.0, 0.0, -4.0]
    assert pivot == [12360.678, -6789.012, 150.0]


def test_pivot_point_double_precision_at_msk_1e6():
    lo, hi = (2345668.912, 1234561.891, 149.4), (2345688.912, 1234573.891, 159.0)
    p = g.pivot_point(lo, hi, 150.0)
    assert abs(p[0] - 2345678.912) < 1e-9 and abs(p[1] - 1234567.891) < 1e-9 and p[2] == 150.0
    assert g.fmt_point(p) == ['2345678.9120', '1234567.8910', '150.0000']


def test_options_are_validated():
    assert g.check_options(None) == {'target': 'both', 'vpm_rotate_z': 0.0}
    assert g.check_options({'target': 'vpm', 'floor_z': '150,0', 'vpm_rotate_z': 30})['floor_z'] == 150.0
    for bad in ({'target': 'msk'}, {'floor': 1}, {'floor_z': ''}, {'vpm_rotate_z': 'x'}, {'vpm_rotate_z': 400},
                {'vpm_rotate_z': True}):
        with pytest.raises(ValueError):
            g.check_options(bad)
    assert g.pivot_targets('both') == ['npm', 'vpm'] and g.pivot_targets('npm') == ['npm']


# ---- glue module shape ------------------------------------------------------------------------------------
def test_glue_has_the_three_functions_and_loads_without_pymxs():
    tree = ast.parse((PKG / 'geom_max.py').read_text(encoding='utf-8'))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not any('pymxs' in ast.dump(n) for n in top)
    glue = _load(PKG / 'geom_max.py', 'agr_tools_geom_max_t')
    for fn in ('model_triangulate', 'ucx_triangulate', 'export_pivot_place'):
        assert callable(getattr(glue, fn))
    assert set(g.TOOLS.values()) == {'model_triangulate', 'ucx_triangulate', 'export_pivot_place'}
    core_tree = ast.parse((PKG / 'geom_core.py').read_text(encoding='utf-8'))
    imported = {a.name.split('.')[0] for n in ast.walk(core_tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names}
    assert imported <= {'math', 're', 'importlib', 'os', 'sys'}  # stdlib only


def test_dispatcher_reaches_the_geom_glue():
    rt = _load(PKG / 'runtime.py', 'agr_runtime_geom_t')
    for tool in ('model.triangulate', 'ucx.triangulate', 'export.pivot_place'):
        core_file, fn = rt.EDITS_080[tool]
        assert core_file == 'geom_core.py' and fn == g.TOOLS[tool]
