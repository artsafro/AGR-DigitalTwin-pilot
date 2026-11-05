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


def l_prism():
    pts = [(0, 0, 0), (2, 0, 0), (2, 1, 0), (1, 1, 0), (1, 2, 0), (0, 2, 0)]
    pts = [tuple(float(c) for c in p) for p in pts] + [(float(x), float(y), 1.0) for x, y, _ in pts]
    n = 6
    polys = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    polys += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    return pts, polys


def test_non_convex_piece_is_reported_and_hull_only_on_request():
    """#979: a piece that no turn makes convex is reported (not silently replaced); the 0.8 hull is opt-in."""
    pts, polys = l_prism()
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert plan['action'] == 'diagonals' and not plan['convex'] and 'still not convex' in plan['reason']
    assert plan['refused'] and all(t for t in plan['tris'])
    plan = g.ucx_plan(pts, polys, 1e-4, nonconvex='hull')
    assert plan['action'] == 'hull' and 'not convex' in plan['reason']
    chk = ucx.convexity(plan['hull']['verts'], [tuple(t) for t in plan['hull']['tris']])
    assert chk['ok'], chk
    with pytest.raises(ValueError):
        g.ucx_plan(pts, polys, 1e-4, nonconvex='drop')


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
    assert imported <= {'math', 're', 'importlib', 'os', 'sys', 'struct'}  # stdlib only


def test_dispatcher_reaches_the_geom_glue():
    rt = _load(PKG / 'runtime.py', 'agr_runtime_geom_t')
    for tool in ('model.triangulate', 'ucx.triangulate', 'export.pivot_place'):
        core_file, fn = rt.EDITS_080[tool]
        assert core_file == 'geom_core.py' and fn == g.TOOLS[tool]


# ==== #979 rework (branch E2) ==============================================================================
# Team scripts are read for ideas only (#853), named by file and SHA256:
#   AlexYo_ConcaveFixer.ms 1ff3ef251f3ffb2b631b158be803b34c1652419a4d338ffd117431d7bee7e40e (T03 card)
#   rotate_pivot_tool.ms (AC Pivot Align) 6344571ffbe927de8a481462136d6dd84f9e0ff7d28d167198891b8fc5f41e20 (T06, L07)
#   straighten_object.ms 94005feffe55aff35a2a3201376e6c054d2627556555b661510d390fb5010221 (T08 card)
#   align_door_pivots_to_bottom.ms e22ab117fb9741ce5afb9f8069bd63abe4ccab2d431a9b4609a12a4750611608 (T03 card)
# The source_* models below are written from the measured card findings, not from the code.

# ---- ucx.triangulate: turning reflex diagonals ---------------------------------------------------------------
def source_concavefixer(points, tris, sign=1.0):
    """T03: every edge with the far vertex in front of the plane by more than 0 is «concave» (1e-6 noise too) and
    is turned without a plan-convexity check; the run says «Fixed: n»."""
    tris = [tuple(t) for t in tris]
    fixed = 0
    for row in g.concave_edges(points, tris, 0.0, sign):
        _, a, b, ti, tj, c, d = row
        tris[ti], tris[tj] = (c, a, d), (d, b, c)
        fixed += 1
        break
    return tris, fixed


def valley_box(diag_valley=True, dz=0.6):
    """2 m UCX box whose top corner 6 is raised; the top quad 4-5-6-7 split by one of its two diagonals."""
    pts, quads = box(raise_corner=6, dz=dz)
    tris = []
    for q in quads[:1] + quads[2:]:
        a, b, c, d = q
        tris += [[a, b, c], [a, c, d]]
    a, b, c, d = quads[1]  # top [4, 5, 6, 7]
    tris += [[a, b, d], [b, c, d]] if diag_valley else [[a, b, c], [a, c, d]]
    return pts, tris


def test_e2_ucx_valley_diagonal_becomes_convex_in_one_turn():
    pts, tris = valley_box(True)
    assert not ucx.convexity(pts, [tuple(t) for t in tris])['convex']  # RED: the piece as triangulated
    plan = g.ucx_plan(pts, tris, 1e-4)
    assert plan['action'] == 'mesh' and len(plan['flips']) == 1 and plan['convex'] and not plan['refused']
    chk = ucx.convexity(pts, [tuple(t) for t in plan['tris']])
    assert chk['ok'] and chk['closed'] and not chk['zero_area']
    assert len(plan['tris']) == len(tris) and max(max(t) for t in plan['tris']) == len(pts) - 1
    pts2, tris2 = valley_box(False)  # the ridge diagonal is already right: nothing to turn
    assert g.ucx_plan(pts2, tris2, 1e-4)['action'] == 'none'


def dart():
    """Two triangles of a lid seen from above: a=(2,2) b=(0,0) c=(2,0) and d=(2.5,3) lifted by 0.5 —
    edge a-b is reflex, but the quad a-d-b-c is an arrowhead («dart») in plan."""
    pts = [(2.0, 2.0, 0.0), (0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.5, 3.0, 0.5)]
    return pts, [(0, 1, 2), (1, 0, 3)]


def test_e2_ucx_dart_is_not_turned_and_is_reported():
    pts, tris = dart()
    src, fixed = source_concavefixer(pts, tris)
    normals = [g._tri_normal(pts, t, 1.0)[2] for t in src]
    assert fixed == 1 and min(normals) < 0  # RED: «Fixed: 1» and a triangle turned face-down (T03: z -0.82)
    got, flips, refused = g.flip_concave(pts, tris, 1e-4)
    assert flips == [] and got == list(tris)
    assert refused and refused[0]['reason'] == 'dart' and refused[0]['edge'] == [0, 1]
    assert 'dart' in g.REFUSE_TEXT['dart']
    # the same lid on a closed prism with quad walls: the lid edge is a dart, the wall corners are creases
    plan_xy = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (2.5, 3.0)]
    pts = [(x, y, 0.0) for x, y in plan_xy] + [(x, y, z) for (x, y), z in zip(plan_xy, (1.0, 1.0, 1.0, 1.5))]
    polys = [[6, 4, 5], [4, 6, 7], [2, 1, 0], [0, 3, 2]] + [[i, (i + 1) % 4, 4 + (i + 1) % 4, 4 + i] for i in range(4)]
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert plan['flips'] == [] and not plan['convex']
    assert {tuple(r['edge']): r['reason'] for r in plan['refused']} == {(4, 6): 'dart', (2, 6): 'crease'}


def test_e2_ucx_fold_of_1e6_is_not_concave():
    pts, tris = valley_box(True, dz=1e-6)
    src, fixed = source_concavefixer(pts, tris)
    assert fixed == 1  # RED: the source turns a 1e-6 fold
    plan = g.ucx_plan(pts, tris, 1e-4)
    assert plan['action'] == 'none' and plan['flips'] == [] and plan['convex']


def noisy_lid(n=12, noise=0.02, seed=3):
    """Closed piece: a flat base and a lid grid of n x n quads with noisy heights (T03 «noisy mesh»)."""
    import random
    rnd = random.Random(seed)
    top = [(i / n * 4.0, j / n * 2.0, 1.0 + rnd.uniform(-noise, noise)) for j in range(n + 1) for i in range(n + 1)]
    base = [(x, y, 0.0) for x, y, _ in top]
    pts = top + base
    m = n + 1
    off = len(top)
    polys = []
    for j in range(n):
        for i in range(n):
            a, b, c, d = j * m + i, j * m + i + 1, (j + 1) * m + i + 1, (j + 1) * m + i
            polys.append([a, b, c, d])
            polys.append([off + a, off + d, off + c, off + b])
    rim = [j for j in range(m)] + [m * k + n for k in range(1, m)] + \
          [n * m + i for i in range(n - 1, -1, -1)] + [m * k for k in range(n - 1, 0, -1)]
    for k in range(len(rim)):
        a, b = rim[k], rim[(k + 1) % len(rim)]
        polys.append([b, a, off + a, off + b])
    return pts, polys


def test_e2_ucx_noisy_grid_reaches_a_fixed_point_with_zero_quads():
    pts, polys = noisy_lid()
    t0 = time.time()
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert time.time() - t0 < 10.0
    assert all(len(t) == 3 for t in plan['tris'])  # T03: 85 quads were left after refused createEdge calls
    assert len(plan['tris']) == sum(len(p) - 2 for p in polys)
    fan = [tuple(t) for p in polys for t in source_ucx_triangles(p)]
    after = len(g.concave_edges(pts, [tuple(t) for t in plan['tris']], 1e-4))
    assert len(plan['refused']) == after and plan['flips']
    # every turn of a reflex edge inside a convex-in-plan quad adds a tetrahedron: the piece only gets fuller
    assert g._signed_volume(pts, [tuple(t) for t in plan['tris']]) > g._signed_volume(pts, fan)
    locked = {(min(p[i], p[(i + 1) % 4]), max(p[i], p[(i + 1) % 4])) for p in polys for i in range(4)}
    sign = 1.0 if g._signed_volume(pts, fan) >= 0 else -1.0
    _, again, _ = g.flip_concave(pts, plan['tris'], 1e-4, sign, locked)
    assert again == []  # fixed point: the same pass on its own result turns nothing
    assert {r['reason'] for r in plan['refused']} <= {'crease', 'dart', 'still_concave', 'folded', 'sharp',
                                                      'edge_exists', 'cycle', 'degenerate'}
    if after:
        assert not plan['convex'] and 'still not convex' in plan['reason']


def test_e2_ucx_refused_edges_name_their_reason():
    pts, polys = l_prism()
    plan = g.ucx_plan(pts, polys, 1e-4)
    assert {r['reason'] for r in plan['refused']} <= set(g.REFUSE_TEXT)
    assert all(set(r) == {'edge', 'reason', 'depth'} for r in plan['refused'])


# ---- export.pivot_place: axes ------------------------------------------------------------------------------
def cell(angle, size=(4.0, 1.0, 0.5), unit=1.0, steps=(8, 2, 1)):
    """L07 cell 4 x 1 x 0.5 m (scaled by `unit`, 100 for cm) turned by `angle` about Z, baked into the mesh,
    in object space around the pivot (the node itself carries the far X/Y)."""
    a = math.radians(angle)
    sx, sy, sz = (s * unit for s in size)
    out = []
    for i in range(steps[0] + 1):
        for j in range(steps[1] + 1):
            for k in range(steps[2] + 1):
                x, y, z = -sx / 2 + sx * i / steps[0], -sy / 2 + sy * j / steps[1], sz * k / steps[2]
                out.append((x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z))
    return out


IDENT = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
SCENES = {'m_zero': (1.0, (0.0, 0.0)), 'cm': (100.0, (234567800.0, 123456700.0)),
          'm_far': (1.0, (2345678.0, 1234567.0))}


def source_ac_axis(points_obj, node_xy):
    """L07: the axis is fitted on WORLD float32 vertices (rounding at 2.3e6 m is 0.25 m), then the long side."""
    world = [(g.f32(p[0] + node_xy[0]), g.f32(p[1] + node_xy[1])) for p in points_obj]
    cx, cy = world[0]
    return g.min_area_rect([(x - cx, y - cy) for x, y in world])['angle']


@pytest.mark.parametrize('scene', sorted(SCENES))
@pytest.mark.parametrize('angle', [17, 45, 89, 135])
def test_e2_pivot_axis_within_0_01_deg_in_m_cm_and_far_from_zero(scene, angle):
    unit, xy = SCENES[scene]
    pts = [tuple(g.f32(c) for c in p) for p in cell(angle, unit=unit)]  # Max stores object vertices as float32
    ax = g.axes_long_side(pts, IDENT)
    assert g.axis_error_deg(ax['rows'], angle) <= g.ANGLE_TOL_DEG
    assert ax['rows'][2] == [0.0, 0.0, 1.0] and ax['uncertainty'] < g.ANGLE_TOL_DEG
    assert abs(ax['angle'] - angle) <= g.ANGLE_TOL_DEG  # the sign rule: [0, 180), 135° stays 135°


def test_e2_pivot_far_from_zero_source_model_is_off_by_more_than_0_01_deg():
    """RED: L07 measured 1.43° (17°) and 1.0° (89°) at 2 345 678 m; the world-float32 model shows the same class."""
    errs = [abs(source_ac_axis(cell(a), SCENES['m_far'][1]) - a) for a in (17, 89)]
    errs = [min(e, 180 - e) for e in errs]
    assert max(errs) > 0.01
    errs_cm = [abs(source_ac_axis(cell(a, unit=100.0), SCENES['cm'][1]) - a) for a in (17, 89)]
    assert max(min(e, 180 - e) for e in errs_cm) > 0.01


def test_e2_pivot_sign_rule_135_is_not_minus_45():
    ax = g.axes_long_side(cell(135), IDENT)
    source = ax['angle'] - 180.0  # T06: the source put X at -45° for the 135° cell
    assert source == -45.0
    assert abs(ax['angle'] - 135.0) < 1e-9 and ax['rows'][0][0] < 0 < ax['rows'][0][1]
    assert g.canonical_angle(-45) == 135.0 and g.canonical_angle(180) == 0.0 and g.canonical_angle(359.9999999999) == 0.0


def source_pairs_limit(n):
    return 3 <= n <= 512  # L07: «Requires 3..512 vertices», O(n³) (512 vertices 56.8 s)


def test_e2_pivot_5000_vertices_under_2_s_no_vertex_limit():
    pts = cell(17, steps=(49, 9, 9))
    assert len(pts) == 5000 and not source_pairs_limit(len(pts))  # RED: refused by the source
    t0 = time.time()
    ax = g.axes_long_side(pts, IDENT)
    assert time.time() - t0 < 2.0 and g.axis_error_deg(ax['rows'], 17) <= g.ANGLE_TOL_DEG


def test_e2_pivot_calipers_match_brute_force():
    import random
    rnd = random.Random(11)
    for _ in range(150):
        pts = [(rnd.uniform(-5, 5), rnd.uniform(-2, 2)) for _ in range(rnd.randint(3, 60))]
        hull = g.hull2d(pts)
        best = None
        for i in range(len(hull)):
            p, q = hull[i], hull[(i + 1) % len(hull)]
            a = math.atan2(q[1] - p[1], q[0] - p[0])
            al = [h[0] * math.cos(a) + h[1] * math.sin(a) for h in hull]
            ac = [-h[0] * math.sin(a) + h[1] * math.cos(a) for h in hull]
            area = (max(al) - min(al)) * (max(ac) - min(ac))
            best = area if best is None else min(best, area)
        r = g.min_area_rect(pts)
        assert math.isclose(r['long'] * r['short'], best, rel_tol=1e-9)


def test_e2_pivot_square_and_too_far_vertices_refuse_with_the_exact_reason():
    with pytest.raises(ValueError, match='square or degenerate footprint'):
        g.axes_long_side(cell(30, size=(1.0, 1.0, 0.5)), IDENT)
    far = [(p[0] + 2345678.0, p[1], p[2]) for p in cell(17)]  # pivot at the origin: vertices stored far away
    with pytest.raises(ValueError, match='axis uncertainty'):
        g.axes_long_side([tuple(g.f32(c) for c in p) for p in far], IDENT)


def rot_rows(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return {'x': [[1, 0, 0], [0, c, s], [0, -s, c]], 'y': [[c, 0, -s], [0, 1, 0], [s, 0, c]],
            'z': [[c, s, 0], [-s, c, 0], [0, 0, 1]]}[axis]


def test_e2_pivot_pca_straightens_a_turned_slab():
    """T08: straighten_object ran PCA before the rotation and straightened nothing (row3 not +Z)."""
    slab = cell(0, size=(120.0, 40.0, 10.0), steps=(12, 4, 2))
    turn = g.mat3_mul(rot_rows('x', 20), rot_rows('z', 30))
    source_rows = IDENT  # RED model: the node frame is left as it was
    ax = g.axes_pca(slab, turn)
    assert ax['rows'][2][2] > 0 and source_rows[2] == [0.0, 0.0, 1.0]
    for got, want in zip(ax['rows'], turn):
        assert abs(abs(g._dot(tuple(got), tuple(want))) - 1.0) < 1e-9
    with pytest.raises(ValueError, match='principal axes undefined'):
        g.axes_pca(cell(0, size=(1.0, 1.0, 1.0), steps=(2, 2, 2)), IDENT)


def test_e2_pivot_offset_keeps_the_mesh_in_place_far_from_zero():
    """T03 doors: the pivot moved in world axes and the mesh slid 491 / 1675 units. Here the node frame and the
    objectOffset are recomputed in double: world vertices do not move (<= 1e-6 m at 2 345 678 m)."""
    pts = [tuple(g.f32(c) for c in p) for p in cell(30, size=(0.9, 0.05, 2.1))]
    node = [[g.f32(c) for c in r] for r in rot_rows('z', 30)] + [[g.f32(2345678.912), g.f32(1234567.891), 150.0]]
    off = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [0.25, -0.5, 0.0]]
    before = g.world_points(pts, off, node)
    obj_rot = g.mat3_mul([r[:] for r in off[:3]], [r[:] for r in node[:3]])
    ax = g.axes_long_side(pts, obj_rot)
    lo, hi = g.frame_bounds(pts, obj_rot, ax['rows'])
    local = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]]
    po_r = g.vec_mat(off[3], node[:3])
    pivot = [po_r[i] + node[3][i] + g.frame_point(local, ax['rows'])[i] for i in range(3)]
    pos32 = [g.f32(v) for v in pivot]
    mo, po = g.new_offset(node, off, ax['rows'], pos32)
    after = g.world_points(pts, [*mo, po], [*ax['rows'], pos32])
    assert max(math.dist(a, b) for a, b in zip(before, after)) <= 1e-6
    source = g.world_points(pts, off, [*ax['rows'], pos32])  # RED: node moved/turned, offset not compensated
    assert max(math.dist(a, b) for a, b in zip(before, source)) > 0.1
    assert abs(pivot[2] - min(p[2] for p in before)) < 1e-6  # bottom of the door in its own frame
    assert g.axis_error_deg(ax['rows'], 60) <= g.ANGLE_TOL_DEG  # baked 30° + node 30°


def test_e2_pivot_unit_scale_and_options():
    assert g.check_unit_scale([[1, 0, 0], [0, 1, 0], [0, 0, 1], [5, 5, 5]]) == ''
    assert 'Reset XForm' in g.check_unit_scale([[2, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]])
    assert g.check_options(None) == {'target': 'both', 'vpm_rotate_z': 0.0}  # 0.8 shape unchanged
    o = g.check_options({'orient': 'long_side', 'pivot_at': 'bottom_centre', 'target': 'npm'})
    assert o['orient'] == 'long_side' and o['pivot_at'] == 'bottom_centre'
    for bad in ({'orient': 'x'}, {'pivot_at': 'top'}, {'pivot_at': 'centre', 'floor_z': 150}):
        with pytest.raises(ValueError):
            g.check_options(bad)


def test_e2_pivot_refusals_have_codes_for_the_report():
    for words, code in (('square or degenerate footprint: x', 'pivot_axis_undefined'),
                        ('axis uncertainty 0.2° > 0.01°', 'pivot_axis_uncertain'),
                        ('node scale is 2, 1, 1 not 1', 'pivot_node_scale'), ('other', 'pivot_refused')):
        assert g.refusal_code(words) == code


def test_e2_glue_keeps_editable_mesh_and_uses_native_setters():
    """T03 doors: Editable_Mesh was skipped silently. The glue takes any TriMesh-convertible node, reads the
    evaluated object (`n.mesh`) and sets the frame through node transform + objectOffset (no vertex edit)."""
    text = (PKG / 'geom_max.py').read_text(encoding='utf-8')
    assert 'canConvertTo(n, rt.TriMeshGeometry)' in text and 'local m = n.mesh' in text
    assert 'n.objectOffsetPos = opos' in text and 'n.objectOffsetRot' in text
    assert 'k[1].transform = k[2]' in text  # children keep their world transform
