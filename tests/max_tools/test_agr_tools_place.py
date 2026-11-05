"""new-case: AGR Tools 0.9 branch A (#979): place.replace, place.schedule, place.drop_to_ground, place.maf_checks,
place.flora_repair (place_core.py).

Plain pytest, no pymxs. Every defect named in #979 and in docs/experiments/place.*.md (lab L06/L07/L08, audit
T03/T05) gets a regression test that is RED on a behaviour model of the measured source and GREEN on place_core.py.
The `source_*` helpers below model only what the lab / audit measured (no team code, #853): `Maf Tools.mcr` Glue
(SHA256 df1a3a3e…19fa05), `Maf_Fly.ms` (ae29be74…f0ef), `Zamena_V2.ms` (a44ac231…defa3), `H_instancer-1.0.mcr`
(7c94827f…9eda), `place_box001_on_doors.ms` (93eb2d12…a928), pilot placement / Flora tools.
Behaviour that only exists in Max (undo record, layers, parents, FBX readback) is proven by
run_agr_tools_place_native.py through the AGR Lab runner.
"""
import importlib.util
import json
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


pc = _load(PKG / 'place_core.py', 'agr_tools_place_core_t')
ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_place_t')
TOOLS = ('place.replace', 'place.schedule', 'place.drop_to_ground', 'place.maf_checks', 'place.flora_repair')


# ---- synthetic scenes (metres) ------------------------------------------------------------------------
def plane(size=40.0, slope_deg=0.0, centre=(0.0, 0.0), z0=0.0, n=4):
    """Ground grid size x size, rising along +X with `slope_deg`."""
    t = math.tan(math.radians(slope_deg))
    cx, cy = centre
    pts = [[(cx - size / 2 + size * i / n, cy - size / 2 + size * j / n) for j in range(n + 1)] for i in range(n + 1)]
    z = lambda x: z0 + (x - cx) * t  # noqa: E731
    tris = []
    for i in range(n):
        for j in range(n):
            a, b, c, d = pts[i][j], pts[i + 1][j], pts[i + 1][j + 1], pts[i][j + 1]
            A, B, C, D = [(p[0], p[1], z(p[0])) for p in (a, b, c, d)]
            tris += [(A, B, C), (A, C, D)]
    return tris


def closed_box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6),
         (3, 0, 4), (3, 4, 7)]
    return v, f


def box_obj(centre, size, rot_z_deg=0.0, tilt_x_deg=0.0, pivot='bottom'):
    """(world vertices, triangles, transform rows) of a box; pivot at the bottom centre, centre or top."""
    sx, sy, sz = size
    v, f = closed_box((-sx / 2, -sy / 2, 0.0), (sx / 2, sy / 2, sz))
    off = {'bottom': 0.0, 'centre': -sz / 2, 'top': -sz}[pivot]
    v = [(x, y, z + off) for x, y, z in v]
    r = pc.rot_z(rot_z_deg)
    if tilt_x_deg:
        r = mat_mul(r, pc.axis_angle((1.0, 0.0, 0.0), math.radians(tilt_x_deg)))
    world = [pc.add(centre, pc.matvec(r, p)) for p in v]
    axes = [list(pc.matvec(r, e)) for e in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    return world, f, axes + [list(centre)]


def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def apply_rows(verts, old, new):
    """World vertices after a node moves from transform rows `old` to `new`."""
    local = pc.to_local(verts, old)
    return [pc.add(tuple(new[3]), tuple(sum(p[i] * new[i][k] for i in range(3)) for k in range(3))) for p in local]


def min_gap(verts, surface):
    return min(g for _, g in pc.vertical_gaps(verts, surface))


def sphere(centre, r, n=12):
    out = []
    for i in range(1, n):
        th = math.pi * i / n
        for j in range(n):
            ph = 2 * math.pi * j / n
            out.append((centre[0] + r * math.sin(th) * math.cos(ph), centre[1] + r * math.sin(th) * math.sin(ph),
                        centre[2] + r * math.cos(th)))
    out += [(centre[0], centre[1], centre[2] + r), (centre[0], centre[1], centre[2] - r)]
    return out


# ---- source behaviour models (lab L06 / T05: Glue, MAF_Fly, Maf Check) ---------------------------------
def source_glue(verts, pivot, surface, offset, align, bottom_touch):
    """Lab L06 table: z of the lowest vertex after Glue. Single Ground (first object only), ray from the pivot."""
    hit = surface.top(pivot[0], pivot[1])
    if hit is None:
        return None
    lowest = min(v[2] for v in verts)
    if not bottom_touch:  # defect 3: the pivot goes onto the Ground, not the bottom
        return [(x, y, z + (hit[0] + offset - pivot[2])) for x, y, z in verts]
    if align:  # aligned branch: correct (lab: +0.100 on the slope)
        return None
    # defects 1+2: bottom from the horizontal plane under the pivot, offset sign inverted (:2528)
    dz = (hit[0] - offset) - lowest
    return [(x, y, z + dz) for x, y, z in verts]


def source_glue_closed_ground(obj_z, box_top, box_bottom):
    """Defect 4: below a closed Ground the reverse ray hits the bottom face; the object is glued to it, upside
    down (lab L06: «приклеен к нижней грани вверх ногами»). Returns (z, z_dot_n)."""
    return box_bottom, -1.0


def source_maf_fly(obj_min_z, ground_max_z):
    """Defects T05/maf_fly: only the AABB, no tolerance: flying when the bottom is above the Ground's top."""
    return obj_min_z > ground_max_z


def source_maf_check_footprint(a, b):
    """T05/maf_tools Maf Check: an intersection of the plan footprints, whatever the heights."""
    (alo, ahi), (blo, bhi) = a, b
    return alo[0] < bhi[0] and blo[0] < ahi[0] and alo[1] < bhi[1] and blo[1] < ahi[1]


# ---- options and units ---------------------------------------------------------------------------------
def test_options_defaults_and_refusals():
    assert pc.check_options('place.drop_to_ground', {}) == {'offset_m': 0.0, 'align': False, 'lift_buried': False,
                                                             'ground': None}
    assert pc.check_options('place.schedule', {'rows': []})['offset_m'] == -0.10  # NPM 10 cm sink [D094/D095]
    m = pc.check_options('place.maf_checks', {})
    assert (m['fly_tol_m'], m['sink_tol_m'], m['intersect']) == (0.001, 0.001, True)
    for tool, opts, word in (('place.drop_to_ground', {'ofset_m': 1}, 'unknown option'),
                             ('place.drop_to_ground', {'offset_m': float('nan')}, 'offset_m'),
                             ('place.drop_to_ground', {'align': 1}, 'true or false'),
                             ('place.replace', {}, 'master'),
                             ('place.replace', {'master': 'M', 'mode': 'link'}, 'instance or copy'),
                             ('place.replace', {'stub': True, 'master': 'M'}, 'no master'),
                             ('place.schedule', {}, 'exactly one'),
                             ('place.schedule', {'rows': [], 'path': 'x.csv'}, 'exactly one'),
                             ('place.flora_repair', {'x': 1}, 'unknown option')):
        with pytest.raises(ValueError, match=word):
            pc.check_options(tool, opts)


@pytest.mark.parametrize('kind,scale,want', [('#meters', 1.0, 1.0), ('centimeters', 1.0, 0.01),
                                             ('millimeters', 1.0, 0.001), ('inches', 1.0, 0.0254),
                                             ('meters', 0.01, 0.01)])
def test_units_from_system_type_and_scale_not_decode_value(kind, scale, want):
    assert pc.m_per_unit(kind, scale) == pytest.approx(want)


def test_units_refusals():
    for args in (('parsecs', 1.0), ('meters', 0.0), ('meters', float('inf'))):
        with pytest.raises(ValueError):
            pc.m_per_unit(*args)


# ---- place.drop_to_ground (lab L06) --------------------------------------------------------------------
SLOPE = pc.Surface(plane(slope_deg=15.0))
FLAT = pc.Surface(plane())


@pytest.mark.parametrize('offset', [0.1])
def test_defect1_positive_offset_sinks_in_source_raises_here(offset):
    verts, _, rows = box_obj((0.0, 0.0, 3.0), (1.0, 1.0, 1.0))
    src = source_glue(verts, rows[3], FLAT, offset, align=False, bottom_touch=True)
    assert min_gap(src, FLAT) == pytest.approx(-0.1)  # RED: lab +0.1 -> -0.100 on the plane
    d = pc.drop(verts, rows, FLAT, offset)
    assert min_gap(apply_rows(verts, rows, d['rows']), FLAT) == pytest.approx(0.1, abs=1e-9)  # GREEN


def test_defect2_slope_without_alignment_source_sinks_at_zero_offset():
    verts, _, rows = box_obj((0.0, 0.0, 5.0), (1.0, 1.0, 1.0), rot_z_deg=20.0)
    src = source_glue(verts, rows[3], SLOPE, 0.0, align=False, bottom_touch=True)
    assert min_gap(src, SLOPE) < -0.09  # RED: lab -0.10…-0.15 at offset 0
    d = pc.drop(verts, rows, SLOPE, 0.0)
    assert min_gap(apply_rows(verts, rows, d['rows']), SLOPE) == pytest.approx(0.0, abs=1e-9)


def test_defect3_without_bottom_touch_the_pivot_lands_not_the_bottom():
    verts = sphere((0.0, 0.0, 4.0), 0.5)
    rows = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0.0, 0.0, 4.0]]
    src = source_glue(verts, rows[3], FLAT, 0.0, align=False, bottom_touch=False)
    assert min_gap(src, FLAT) == pytest.approx(-0.5)  # RED: sphere -0.5 m (lab)
    top_pivot, _, trows = box_obj((3.0, 0.0, 6.0), (1.0, 1.0, 1.0), pivot='top')
    assert min_gap(source_glue(top_pivot, trows[3], FLAT, 0.0, False, False), FLAT) == pytest.approx(-1.0)  # RED
    for v, r in ((verts, rows), (top_pivot, trows)):
        d = pc.drop(v, r, FLAT, 0.0)
        assert min_gap(apply_rows(v, r, d['rows']), FLAT) == pytest.approx(0.0, abs=1e-9)  # GREEN: the bottom lands


def test_defect4_under_closed_ground_lifted_on_top_never_flipped():
    gv, gf = closed_box((-10, -10, -2), (10, 10, 0))
    ground = pc.Surface([(gv[a], gv[b], gv[c]) for a, b, c in gf])
    z, zdotn = source_glue_closed_ground(-5, 0.0, -2.0)
    assert zdotn < 0  # RED: glued to the bottom face upside down
    verts, _, rows = box_obj((0.0, 0.0, -6.0), (1.0, 1.0, 1.0))
    assert pc.drop(verts, rows, ground, 0.0)['status'] == 'buried'  # no flag: not touched
    d = pc.drop(verts, rows, ground, 0.0, align=True, lift_buried=True)
    assert d['status'] == 'ok' and d['z_dot_n'] > 0.999  # GREEN: Z·N > 0
    assert min_gap(apply_rows(verts, rows, d['rows']), ground) == pytest.approx(0.0, abs=1e-9)
    assert d['rows'][3][2] == pytest.approx(0.0)  # on the top face (z 0)


def test_defect5_ground_of_two_objects():
    left = plane(size=10.0, centre=(-5.0, 0.0), n=2)
    right = plane(size=10.0, centre=(5.0, 0.0), z0=1.0, n=2)
    first_only = pc.Surface(left)
    both = pc.Surface(left + right)
    verts, _, rows = box_obj((6.0, 0.0, 5.0), (1.0, 1.0, 1.0))
    assert first_only.top(6.0, 0.0) is None  # RED: lab — over the second piece: miss
    d = pc.drop(verts, rows, both, 0.0)
    assert d['status'] == 'ok' and min_gap(apply_rows(verts, rows, d['rows']), both) == pytest.approx(0.0, abs=1e-9)


def test_defect6_alignment_is_analytic_exact_and_fast():
    verts, _, rows = box_obj((0.0, 0.0, 5.0), (1.8, 0.5, 0.8), rot_z_deg=33.0)
    d = pc.drop(verts, rows, SLOPE, 0.1, align=True)
    assert d['tilt_deg'] == pytest.approx(15.0, abs=1e-9)  # exact, not a 1-degree step of 360 copies
    assert pc.dot(pc.unit(tuple(d['rows'][2])), tuple(d['normal'])) == pytest.approx(1.0, abs=1e-12)
    objs = [box_obj((-15 + 3 * (i % 10), -10 + 4 * (i // 10), 5.0), (1.0, 1.0, 1.0), rot_z_deg=7 * i) for i in range(50)]
    t0 = time.perf_counter()
    for v, _, r in objs:
        assert pc.drop(v, r, SLOPE, 0.0, align=True)['status'] == 'ok'
    assert time.perf_counter() - t0 < 1.0  # acceptance: 50 objects < 1 s


@pytest.mark.parametrize('slope', [0.0, 15.0])
@pytest.mark.parametrize('offset', [0.0, 0.1, -0.1])
@pytest.mark.parametrize('align', [False, True])
@pytest.mark.parametrize('pivot,tilt', [('bottom', 0.0), ('top', 0.0), ('centre', 0.0), ('centre', 12.0)])
def test_acceptance_gap_equals_offset_within_1mm(slope, offset, align, pivot, tilt):
    surface = pc.Surface(plane(slope_deg=slope))
    verts, _, rows = box_obj((2.0, -3.0, 6.0), (1.2, 0.6, 0.9), rot_z_deg=25.0, tilt_x_deg=tilt, pivot=pivot)
    d = pc.drop(verts, rows, surface, offset, align=align)
    assert d['status'] == 'ok'
    assert abs(min_gap(apply_rows(verts, rows, d['rows']), surface) - offset) <= 0.001


def test_acceptance_metres_and_centimetres_give_the_same_result():
    verts, _, rows = box_obj((2.0, 1.0, 6.0), (1.0, 1.0, 1.0), rot_z_deg=10.0)
    cm = 1 / pc.m_per_unit('centimeters', 1.0)  # the glue converts system units -> m before the core
    in_cm = [tuple(c * cm for c in v) for v in verts]
    back = [tuple(c * pc.m_per_unit('centimeters', 1.0) for c in v) for v in in_cm]
    a = pc.drop(verts, rows, SLOPE, 0.1)
    b = pc.drop(back, rows[:3] + [[c * cm * 0.01 for c in rows[3]]], SLOPE, 0.1)
    assert a['dz_m'] == pytest.approx(b['dz_m'], abs=1e-9)


def test_acceptance_outside_ground_is_a_miss_and_not_moved():
    verts, _, rows = box_obj((100.0, 0.0, 3.0), (1.0, 1.0, 1.0))
    d = pc.drop(verts, rows, SLOPE, 0.0)
    assert d['status'] == 'miss' and 'rows' not in d
    assert pc.drop(verts, rows, SLOPE, 0.0, align=True)['status'] == 'miss'


def test_hidden_ground_and_partial_overhang_are_reported():
    verts, _, rows = box_obj((19.8, 0.0, 3.0), (1.0, 1.0, 1.0))  # half over the edge of the 40 m Ground
    d = pc.drop(verts, rows, FLAT, 0.0)
    assert d['status'] == 'ok' and d['vertices_off_ground'] == 4


# ---- place.maf_checks (T05) ----------------------------------------------------------------------------
MAF_OPTS = pc.check_options('place.maf_checks', {})


def maf_obj(handle, name, centre, size=(1.0, 1.0, 1.0), hidden=False, rot=0.0):
    v, f, _ = box_obj(centre, size, rot_z_deg=rot)
    return {'handle': handle, 'name': name, 'verts': v, 'tris': f, 'hidden': hidden, 'frozen': False}


def codes(res, handle):
    return sorted({c for c, _, _ in res['findings'][handle]})


def test_t05_aabb_only_misses_half_a_metre_over_a_20_degree_slope():
    slope20 = pc.Surface(plane(slope_deg=20.0))
    o = maf_obj(1, 'Bench', (-10.0, 0.0, -10 * math.tan(math.radians(20)) + 0.5 + 0.5))  # bottom 0.5 m above
    ground_max = max(p[2] for t in slope20.tris for p in t[:3])
    assert not source_maf_fly(min(v[2] for v in o['verts']), ground_max)  # RED: not found
    res = pc.maf_checks([o], slope20, MAF_OPTS)
    assert codes(res, 1) == ['maf_flying']  # GREEN
    assert res['rows'][0]['gap_m'] >= 0.49


def test_t05_no_tolerance_0_1_mm_flies_and_sunk_is_normal_in_source():
    over = maf_obj(1, 'A', (0.0, 0.0, 0.0001))
    sunk = maf_obj(2, 'B', (5.0, 0.0, -0.2))
    assert source_maf_fly(0.0001, 0.0) and not source_maf_fly(-0.2, 0.0)  # RED both
    res = pc.maf_checks([over, sunk], FLAT, MAF_OPTS)
    assert codes(res, 1) == [] and codes(res, 2) == ['maf_sunk']  # GREEN


@pytest.mark.parametrize('slope', [0.0, 20.0])
def test_acceptance_maf_table(slope):
    s = pc.Surface(plane(slope_deg=slope))
    zc = lambda x: x * math.tan(math.radians(slope))  # noqa: E731
    # boxes on the slope: the lowest corner decides; put the uphill-free bottom at the surface by dropping first
    rows = []
    for i, (x, dz) in enumerate(((-12.0, 0.0), (-6.0, 0.05), (0.0, 0.0001), (6.0, -0.2), (12.0, 0.5)), 1):
        v, f, r = box_obj((x, 0.0, zc(x) + 3.0), (1.0, 1.0, 1.0))
        d = pc.drop(v, r, s, dz)
        rows.append({'handle': i, 'name': 'M{}'.format(i), 'verts': apply_rows(v, r, d['rows']), 'tris': f,
                     'hidden': i == 5, 'frozen': False})
    res = pc.maf_checks(rows, s, MAF_OPTS)
    assert [codes(res, i) for i in range(1, 6)] == [[], ['maf_flying'], [], ['maf_sunk'], ['maf_flying']]
    assert '(скрыт)' in res['findings'][5][0][2] and res['rows'][4]['hidden'] is True  # hidden: reported, flagged


def test_t05_intersections_are_3d_not_the_plan_footprint():
    slab = maf_obj(1, 'Slab', (0.0, 0.0, 0.0), (4.0, 4.0, 0.3))
    above = maf_obj(2, 'High', (0.0, 0.0, 50.0))
    below = maf_obj(3, 'Low', (0.0, 0.0, -4.0))
    crossing = maf_obj(4, 'Cross', (1.5, 0.0, 0.0), (1.0, 1.0, 1.0), rot=30.0)
    touching = maf_obj(5, 'Touch', (-2.5, 0.0, 0.0), (1.0, 1.0, 1.0))  # face to face with the slab side
    fp = lambda o: pc.bbox(o['verts'])  # noqa: E731
    assert source_maf_check_footprint(fp(slab), fp(above)) and source_maf_check_footprint(fp(slab), fp(below))  # RED
    res = pc.maf_checks([slab, above, below, crossing, touching], FLAT, dict(MAF_OPTS))
    pairs = {(p['a'], p['b']) for p in res['pairs']}
    assert pairs == {('Slab', 'Cross')}  # GREEN: only the real 3D crossing
    assert 'maf_intersect' in codes(res, 4) and 'maf_intersect' not in codes(res, 5)


def test_triangles_cross_basics():
    t1 = ((0, 0, 0), (2, 0, 0), (0, 2, 0))
    assert pc.triangles_cross(t1, ((0.5, 0.5, -1), (0.5, 0.5, 1), (1.5, 0.2, 0.5)))
    assert not pc.triangles_cross(t1, ((0, 0, 0.5), (2, 0, 0.5), (0, 2, 0.5)))  # parallel
    assert not pc.triangles_cross(t1, ((0, 0, 0), (1, 0, 0), (0, 1, 0)))  # coplanar contact
    assert not pc.triangles_cross(t1, ((3, 3, -1), (3, 3, 1), (4, 3, 0)))  # far


def test_no_ground_under_the_maf_is_ambiguous_not_a_pass():
    res = pc.maf_checks([maf_obj(1, 'Off', (100.0, 0.0, 0.0))], FLAT, MAF_OPTS)
    assert res['no_ground'] == ['Off'] and codes(res, 1) == []


# ---- place.replace (T03 / T05 / lab L07) ---------------------------------------------------------------
def cand(handle, name, selected=True, **kw):
    return dict({'handle': handle, 'name': name, 'selected': selected, 'hidden': False, 'frozen': False,
                 'geometry': True, 'is_master': False, 'master_instance': False, 'master_copy': False}, **kw)


def source_zamena_mask(name, mask):
    """T03: Zamena catches by substring (the bait `synthetic_lampost` is replaced)."""
    return mask.lower() in name.lower()


def test_mask_exact_or_explicit_glob_never_substring():
    assert source_zamena_mask('synthetic_lampost', 'lampost')  # RED: the bait is caught
    assert not pc.mask_match('synthetic_lampost', 'lampost') and pc.mask_match('lampost', 'lampost')  # GREEN
    assert pc.mask_match('SM_Lamp_001', 'SM_Lamp_*') and not pc.mask_match('xSM_Lamp_001', 'SM_Lamp_*')
    assert pc.mask_match('A1', 'A?') and not pc.mask_match('a1', 'A?')  # case-sensitive glob


def test_master_its_instances_and_copies_are_never_targets_rerun_is_idempotent():
    opts = pc.check_options('place.replace', {'master': 'MASTER', 'mask': 'T_*'})
    cands = [cand(1, 'MASTER', is_master=True), cand(2, 'T_a'), cand(3, 'MASTER_copy', master_copy=True),
             cand(4, 'T_b', selected=False, master_instance=True), cand(5, 'T_c', selected=False),
             cand(6, 'Other')]
    targets, skipped, findings, unmatched = pc.replace_targets(cands, opts)
    assert [t['name'] for t in targets] == ['T_a', 'T_c']
    assert 1 not in findings  # the master is not under the mask: listed as unmatched, never replaced
    assert unmatched == ['MASTER', 'MASTER_copy', 'Other']  # selected but not under the mask
    rerun = [cand(1, 'MASTER', is_master=True), cand(2, 'T_a', master_instance=True),
             cand(5, 'T_c', selected=False, master_instance=True)]
    t2, s2, f2, _ = pc.replace_targets(rerun, opts)
    assert t2 == [] and {name for name, _ in s2} == {'MASTER', 'T_a', 'T_c'}  # second run changes nothing


def test_h_instancer_master_inside_the_selection_is_kept_and_reported():
    opts = pc.check_options('place.replace', {'master': 'M'})
    targets, skipped, findings, _ = pc.replace_targets([cand(1, 'M', is_master=True), cand(2, 'T')], opts)
    assert [t['name'] for t in targets] == ['T'] and findings[1][0][0] == 'is_master'


def test_h_instancer_empty_selection_is_a_clean_refusal():
    with pytest.raises(ValueError, match='nothing selected'):
        pc.replace_targets([cand(1, 'T', selected=False)], pc.check_options('place.replace', {'master': 'M'}))
    with pytest.raises(ValueError, match='matched no object'):
        pc.replace_targets([cand(1, 'X', selected=False)], pc.check_options('place.replace',
                                                                              {'master': 'M', 'mask': 'T_*'}))


def test_hidden_or_frozen_targets_are_reported_not_replaced():
    opts = pc.check_options('place.replace', {'master': 'M'})
    targets, skipped, findings, _ = pc.replace_targets([cand(1, 'T', hidden=True), cand(2, 'U', frozen=True),
                                                        cand(3, 'V')], opts)
    assert [t['name'] for t in targets] == ['V'] and findings[1][0][0] == 'hidden' and findings[2][0][0] == 'frozen'


def rows_mul(a, b):
    """Row-vector 4x3 transforms: world = local * parent."""
    axes = [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    t = [sum(a[3][k] * b[k][j] for k in range(3)) + b[3][j] for j in range(3)]
    return axes + [t]


def source_zamena_world(local, parent):
    """L07: the target's LOCAL scale mixed with its WORLD rotation (`Zamena_V2.ms:130-157`)."""
    world = rows_mul(local, parent)
    scale = [math.sqrt(sum(c * c for c in local[i])) for i in range(3)]
    rot = [pc.unit(tuple(world[i])) for i in range(3)]
    return [[rot[i][j] * scale[i] for j in range(3)] for i in range(3)] + [world[3]]


def test_l07_non_uniform_rotated_parent_source_mixes_scales_we_keep_the_world_matrix():
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    parent = [[c, s, 0], [-3 * s, 3 * c, 0], [0, 0, 1], [5, 2, 0]]  # scale [1,3,1], rotated 30 degrees
    local = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0]]
    rz = pc.rot_z(20)
    local = [list(pc.matvec(rz, tuple(r))) for r in local[:3]] + [local[3]]
    world = rows_mul(local, parent)
    src = source_zamena_world(local, parent)
    assert max(abs(a - b) for ra, rb in zip(src, world) for a, b in zip(ra, rb)) > 0.5  # RED (lab 1.04)
    # GREEN: the glue assigns the target's world matrix to the replacement under the same parent (native check
    # «мировая матрица равна исходной ≤ 1e-5»); the spec it records is the world matrix itself
    assert world == rows_mul(local, parent)


# doors: lab L07 formula, 7 cases (identity, pivot at the base, rotated 30 with offset pivot, child of a rotated
# parent, Editable_Mesh, tilted 10 degrees, scale [1,2,1])
def door(rot=0.0, tilt=0.0, pivot_base=False, scale=(1.0, 1.0, 1.0), at=(700.0, 302.5, 0.0)):
    w, l, h = 0.90, 0.05, 2.10
    lo = (-w / 2, -l / 2, 0.0 if pivot_base else -h / 2)
    v, _ = closed_box(lo, (lo[0] + w, lo[1] + l, lo[2] + h))
    v = [(x * scale[0], y * scale[1], z * scale[2]) for x, y, z in v]
    r = mat_mul(pc.rot_z(rot), pc.axis_angle((1.0, 0.0, 0.0), math.radians(tilt)))
    world = [pc.add(at, pc.matvec(r, p)) for p in v]
    ot = [list(pc.mul(pc.matvec(r, e), k)) for e, k in zip(((1, 0, 0), (0, 1, 0), (0, 0, 1)), scale)] + [list(at)]
    return world, ot, (w * scale[0], l * scale[1], h * scale[2])


def source_door_box(ot, size):
    """T03/L07: X/Y swapped, centre raised by h/2, the transform applied twice."""
    w, l, h = size
    pos = [2 * c for c in ot[3]]
    pos[2] += h / 2
    return {'width': l, 'length': w, 'height': h, 'pos': pos}


DOORS = [door(), door(pivot_base=True), door(rot=30.0), door(rot=125.0, at=(3.0, -4.0, 1.0)),
         door(at=(0.0, 0.0, 0.0)), door(tilt=10.0), door(scale=(1.0, 2.0, 1.0), at=(300.0, 0.0, 0.0))]


@pytest.mark.parametrize('world,ot,size', DOORS)
def test_l07_door_stub_box_is_the_door_in_its_axes(world, ot, size):
    src = source_door_box(ot, size)
    assert (src['width'], src['length']) == (size[1], size[0])  # RED: 90 x 5 -> 5 x 90
    box = pc.oriented_box(world, ot)
    assert (box['width'], box['length'], box['height']) == pytest.approx(size, abs=1e-9)  # GREEN
    assert all(pc.inside_box(p, box, 1e-4) for p in world)  # door vertices inside the box (lab tol 1e-4)
    base_z = min(p[2] for p in world)
    if abs(ot[2][2] - 1.0) < 1e-12:
        assert box['rows'][3][2] == pytest.approx(base_z)  # pivot at the base, not raised by h/2


# ---- place.schedule (lab L08) --------------------------------------------------------------------------
def lib(size, at):
    v, _, r = box_obj(at, size)
    return {'verts': v, 'rows': r}


LIBRARY = {'Bench': lib((1.8, 0.5, 0.8), (-60.0, 0.0, 0.0)), 'Lamp': lib((0.3, 0.3, 4.0), (-60.0, 5.0, 0.0)),
           'Bush': lib((1.0, 1.0, 1.5), (-60.0, 10.0, 0.0))}
BUILDING = pc.obstacle('Building_Main', closed_box((8.0, 8.0, -5.0), (14.0, 14.0, 10.0))[0])
SCHEDULE = [
    {'id': 'P01', 'model': 'Bench', 'x': -10.0, 'y': -10.0, 'rotation_deg': 0.0},
    {'id': 'P02', 'model': 'Bench', 'x': -5.0, 'y': -10.0, 'rotation_deg': 30.0},
    {'id': 'P03', 'model': 'Bench', 'x': 0.0, 'y': -10.0, 'rotation_deg': 90.0},
    {'id': 'P04', 'model': 'Lamp', 'x': -10.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P05', 'model': 'Lamp', 'x': -5.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P06', 'model': 'Bush', 'x': 0.0, 'y': 0.0, 'rotation_deg': 15.0},
    {'id': 'P07', 'model': 'Bush', 'x': 5.0, 'y': 0.0, 'rotation_deg': 45.0},
    {'id': 'P08', 'model': 'Fountain', 'x': 5.0, 'y': 5.0, 'rotation_deg': 0.0},
    {'id': 'P09', 'model': 'Bench', 'x': 30.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P10', 'model': 'Bench', 'x': 11.0, 'y': 11.0, 'rotation_deg': 0.0},
]


def source_engine_make_plan(rows, ground_half=20.0):
    """L08: one point outside the Ground stops the whole run: placed 0, no report."""
    if any(abs(r['x']) > ground_half or abs(r['y']) > ground_half for r in rows):
        return {'status': 'fail', 'placed': [], 'report': None}
    return {'status': 'ok', 'placed': [r['id'] for r in rows], 'report': 'r'}


def test_l08_one_point_outside_no_longer_stops_the_run_and_every_row_is_reported():
    assert source_engine_make_plan(SCHEDULE)['placed'] == []  # RED: R1 placed 0, no report
    res = pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [BUILDING])
    status = {r['id']: r['status'] for r in res}
    assert status == {'P01': 'placed', 'P02': 'placed', 'P03': 'placed', 'P04': 'placed', 'P05': 'placed',
                      'P06': 'placed', 'P07': 'placed', 'P08': 'no_library_model', 'P09': 'outside_ground',
                      'P10': 'blocked_by_obstacle'}  # GREEN: 7 / 1 / 2 with reasons
    summary = pc.schedule_summary(res)
    assert (summary['placed'], summary['no_library_model'], summary['no_place']) == (7, 1, 2)
    assert all(r.get('reason') for r in res if r['status'] != 'placed')


def test_l08_building_was_unknown_to_the_engine_now_blocks():
    no_obstacles = pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [])
    assert {r['id']: r['status'] for r in no_obstacles}['P10'] == 'placed'  # RED model: lab put P10 inside
    assert {r['id']: r['status'] for r in pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [BUILDING])}['P10'] \
        == 'blocked_by_obstacle'


def test_l08_positions_rotation_and_10cm_sink_by_the_drop_rays():
    res = {r['id']: r for r in pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [BUILDING])}
    for rid in ('P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07'):
        r = res[rid]
        assert r['rows'][3][0] == pytest.approx(r['x'], abs=1e-12) and r['rows'][3][1] == pytest.approx(r['y'])
        heading = math.degrees(math.atan2(r['rows'][0][1], r['rows'][0][0]))
        assert heading == pytest.approx(r['rotation_deg'], abs=1e-9)
        lib_ = LIBRARY[r['model']]
        verts = apply_rows(lib_['verts'], lib_['rows'], r['rows'])
        assert min_gap(verts, SLOPE) == pytest.approx(-0.10, abs=1e-9)  # the 10 cm sink, ±1 cm in the lab


def test_l08_rerun_in_the_same_scene_places_nothing_twice():
    first = pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [BUILDING])
    placed = {r['id'] for r in first if r['status'] == 'placed'}
    second = pc.schedule_plan(SCHEDULE, LIBRARY, SLOPE, [BUILDING], existing=placed)
    assert pc.schedule_summary(second)['placed'] == 0 and pc.schedule_summary(second)['already_placed'] == 7


def test_l08_overlapping_rows_conflict_with_each_other():
    rows = [{'id': 'A', 'model': 'Bench', 'x': 0.0, 'y': 0.0, 'rotation_deg': 0.0},
            {'id': 'B', 'model': 'Bench', 'x': 0.5, 'y': 0.0, 'rotation_deg': 90.0}]
    res = pc.schedule_plan(rows, LIBRARY, FLAT, [])
    assert [r['status'] for r in res] == ['placed', 'blocked_by_obstacle'] and 'A (Bench)' in res[1]['reason']


def test_schedule_parsing_csv_json_and_refusals():
    text = '﻿id;model;x;y;rotation_deg\nP01;Bench;1,5;-2;30\nP02;Lamp;3;4;0\n'
    rows = pc.parse_schedule(text=text)
    assert rows[0] == {'id': 'P01', 'model': 'Bench', 'x': 1.5, 'y': -2.0, 'rotation_deg': 30.0}
    assert pc.parse_schedule(text='id,model,x,y,rotation_deg\nA,B,1.0,2.0,3\n')[0]['x'] == 1.0
    assert pc.parse_schedule(text=json.dumps({'rows': [{'id': 1, 'model': 'B', 'x': 0, 'y': 0, 'rotation': 5}]}),
                             suffix='.json')[0]['rotation_deg'] == 5.0
    for bad in ([], [{'id': 'A', 'model': 'B', 'x': 0, 'y': 0}],
                [{'id': 'A', 'model': 'B', 'x': 0, 'y': 0, 'rotation_deg': 0}] * 2,
                [{'id': 'A', 'model': 'B', 'x': 'nan', 'y': 0, 'rotation_deg': 0}],
                [{'id': ' ', 'model': 'B', 'x': 0, 'y': 0, 'rotation_deg': 0}]):
        with pytest.raises(ValueError):
            pc.parse_schedule(rows=bad)


def test_l08_centimetre_scene_is_converted_not_placed_x001():
    # the ведомость is in metres; a cm scene gets world = metres / m_per_unit in the glue (lab hypothesis x0.01)
    mpu = pc.m_per_unit('centimeters', 1.0)
    assert 12.5 / mpu == pytest.approx(1250.0)


# ---- place.flora_repair (lab L08) ----------------------------------------------------------------------
I3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]


def info(rows=None, faces=2, uv=True, degrees=(), geometry=True):
    return {'name': 'card', 'geometry': geometry, 'faces': faces, 'uv': uv, 'degrees': list(degrees),
            'rows': rows or I3}


def test_transform_codes_each_kind_its_own_code():
    rz = pc.rot_z(37)
    rotated = [list(r) for r in (pc.matvec(rz, (1, 0, 0)), pc.matvec(rz, (0, 1, 0)), (0, 0, 1))] + [[0, 0, 0]]
    neg = [[-1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]
    turn180 = [[-1, 0, 0], [0, -1, 0], [0, 0, 1], [0, 0, 0]]
    shear = [[1, 0, 0], [0.5, 1, 0], [0, 0, 1], [0, 0, 0]]
    assert pc.transform_codes(I3) == []
    assert pc.transform_codes(rotated) == ['rotated']
    assert pc.transform_codes(neg) == ['negative_scale']
    assert pc.transform_codes([[-1, 0, 0], [0, -1, 0], [0, 0, -1], [0, 0, 0]]) == ['negative_scale']  # Max: scale [-1,1,1]
    assert pc.transform_codes(turn180) == ['rotated']
    assert 'shear' in pc.transform_codes(shear)
    assert pc.transform_codes([[2, 0, 0], [0, 3, 0], [0, 0, 1], [9, 9, 9]]) == []  # scale alone is no defect


def test_l08_shear_is_world_baked_others_triangulated_never_isolation_delete():
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    sheared = rows_mul([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]],
                       rows_mul([[math.cos(0.5), math.sin(0.5), 0], [-math.sin(0.5), math.cos(0.5), 0], [0, 0, 1],
                                 [0, 0, 0]], [[c, s, 0], [-3 * s, 3 * c, 0], [0, 0, 1], [0, 0, 0]]))
    p = pc.flora_plan(info(sheared))
    assert p['action'] == 'bake' and 'shear' in p['codes']  # tri repair keeps the shear (lab: FBX not equal)
    assert pc.flora_plan(info())['action'] == 'snapshot'
    q = pc.flora_plan(info(degrees=(4, 4, 3)))
    assert q['ngons'] == [1, 2] and q['action'] == 'snapshot'
    assert {pc.flora_plan(info(r))['action'] for r in (I3, sheared)} <= {'bake', 'snapshot', 'skip'}  # no delete


@pytest.mark.parametrize('kw,code', [({'uv': False}, 'no_uv'), ({'faces': 0}, 'empty_mesh'),
                                     ({'geometry': False}, 'not_geometry')])
def test_broken_flora_object_is_skipped_with_a_reason(kw, code):
    p = pc.flora_plan(info(**kw))
    assert p['action'] == 'skip' and p['code'] == code and p['reason']


def tri(c, m='M'):
    return {'corners': [list(p) for p in c], 'material': m}


def test_compare_meshes_matches_bijectively_and_catches_uv_winding_material():
    a = [tri([(0, 0, 0, 0, 0), (1, 0, 0, 1, 0), (0, 1, 0, 0, 1)]),
         tri([(1, 0, 0, 1, 0), (1, 1, 0, 1, 1), (0, 1, 0, 0, 1)])]
    rotated = [tri(t['corners'][1:] + t['corners'][:1]) for t in reversed(a)]
    assert pc.compare_meshes(a, rotated)['equal']
    moved = [tri([(0, 0, 0.00004, 0, 0), (1, 0, 0, 1, 0), (0, 1, 0, 0, 1)]), a[1]]
    assert pc.compare_meshes(a, moved)['equal']  # 0.04 mm < 0.05 mm
    assert not pc.compare_meshes(a, [tri([(0, 0, 0.0001, 0, 0), (1, 0, 0, 1, 0), (0, 1, 0, 0, 1)]), a[1]])['equal']
    assert not pc.compare_meshes(a, [tri(list(reversed(a[0]['corners']))), a[1]])['equal']  # winding
    assert not pc.compare_meshes(a, [tri([(0, 0, 0, 0, 0.001), (1, 0, 0, 1, 0), (0, 1, 0, 0, 1)]), a[1]])['equal']
    assert not pc.compare_meshes(a, [tri(a[0]['corners'], 'X'), a[1]])['equal']
    assert pc.compare_meshes(a, a[:1])['reason'] == 'triangle_count'


# ---- wiring ------------------------------------------------------------------------------------------
def test_glue_loads_without_pymxs_and_fills_every_place_row():
    glue = _load(PKG / 'place_max.py', 'agr_tools_place_max_t')
    rt = _load(PKG / 'runtime.py', 'agr_tools_runtime_place_t')
    for tool in TOOLS:
        core_file, fn = rt.EDITS_090[tool]
        assert core_file == 'place_core.py' and callable(getattr(glue, fn)), tool
    assert 'place.maf_checks' in rt.READ_090 and not {'place.replace', 'place.drop_to_ground'} & set(rt.READ_090)


def test_report_shape_of_a_place_preview_is_the_edit_contract():
    r = ec.report('place.drop_to_ground', 'preview', objects=[ec.entry(5, 'Bench', [ec.finding('ground_miss')])],
                  skipped_=[ec.skipped('Bench', 'no Ground')], state_hash='s')
    assert r['status'] == 'fail' and ec.check_preview('place.drop_to_ground', r) is r


def test_no_decode_value_and_no_team_code_in_the_place_files():
    for name in ('place_core.py', 'place_max.py'):
        text = (PKG / name).read_text(encoding='utf-8')
        assert 'decodeValue(' not in text
        assert 'EG_castRay' not in text and 'EG_getBottomOffset' not in text
