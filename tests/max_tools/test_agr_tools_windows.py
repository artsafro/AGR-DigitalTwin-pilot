"""new-case: AGR Tools 1.0 branch J (#1024): win.place (1.0.9) and win.generate (1.0.10), modules openings_core,
winplace_core, windowgen_core.

Plain pytest, no pymxs. Every defect measured by lab L10 (docs/experiments/win.place.md, win.generate.md) gets a
regression test that is RED on a behaviour model of the measured source and GREEN on the branch J code. The
`source_*` helpers model only what the lab measured on Geo Window Placer (GeoAGR.ms:56673-57352; frame
:56942-57025, match :57117-57124, place :57126-57146, centerpivot :57090) and the #1024 defaults the owner answers
of 06.11.2026 replaced; no GeoAGR code is copied (#853). Behaviour that only exists in Max (one undo record,
instances, user props, cm scene) is proven by run_agr_tools_windows_native.py through the AGR Lab runner.
"""
import importlib.util
import json
import math
import sys
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


oc = _load(PKG / 'openings_core.py', 'agr_tools_openings_core_t')
wg = _load(PKG / 'windowgen_core.py', 'agr_tools_windowgen_core_t')
wp = _load(PKG / 'winplace_core.py', 'agr_tools_winplace_core_t')
cc = _load(PKG / 'contract_core.py', 'agr_tools_contract_core_win_t')
jb = _load(ROOT / 'test-polygon/stations/J_build.py', 'agr_polygon_j_build_t')
LIB = wg.load_library(str(ROOT / 'library/windows'))
STD = LIB['standard']
T = LIB['by_id']
REPORT = wg.library_report(LIB['types'], STD)
OFFER = set(wg.offerable(REPORT))
OPTS = wp.check_options({})


def info(tid):
    m = wg.build_type(T[tid], STD)
    return {'size_m': m['size_m'], 'frame_mid_m': m['frame_mid_m'], 'face_axis': m['face_axis']}


def scaled(mesh, k):
    return dict(mesh, verts=[[c * k for c in v] for v in mesh['verts']])


@pytest.fixture(scope='module')
def badik():
    spec = jb.kpp1_badik()
    return spec, jb.facade(spec), oc.find_openings_report(jb.facade(spec))


def _nearest(truth, origin):
    return min(truth, key=lambda t: math.dist(t['centre'], origin))


# ---- behaviour models of the source (lab L10 measurements) ---------------------------------------------------
def source_candidates(mesh):
    """Geo Window Placer takes every open border as a candidate (L10 r1: outer facade contours too)."""
    v, f, _ = oc.weld(mesh['verts'], mesh['faces'], 1e-4)
    return oc.boundary_loops(f)


def source_frame_width(border):
    """The active frame (:56942-57025) spans the loop's extreme points: a corner L loop gets the diagonal."""
    pts = [p for p in border]
    best = max(((a, b) for a in pts for b in pts), key=lambda ab: math.dist(ab[0][:2], ab[1][:2]))
    return math.dist(best[0][:2], best[1][:2])


def source_is_window(border):
    """No shape test: any loop whose bbox matches a type size is a window (arches included)."""
    return True


def source_fit(ow, oh, tw, th, m_per_unit, thresh=0.2):
    """spn_thresh 0.2 in SYSTEM units over |dw| + |dh| (:57117-57124)."""
    return (abs(ow - tw) + abs(oh - th)) / m_per_unit <= thresh


def source_centre_error(ow, oh, tw, th):
    """Alignment by the bottom-left corner: the centre is off by half the size difference."""
    return math.hypot((ow - tw) / 2, (oh - th) / 2)


def source_normal_deg(face_axis):
    """Frame match (:57133-57134) is right; the auto-rotation (:57137-57143) flips a -Y model by 180 deg."""
    return 180.0 if face_axis == '-y' else 0.0


def source_merges(a, b):
    """#1024 K2 default before the owner answer: WT-07 = WT-10 (same size)."""
    return abs(a['width_m'] - b['width_m']) < 0.002 and abs(a['height_m'] - b['height_m']) < 0.002


ISSUE_GLASS_AT_FRAME_MIDDLE = 0.5  # #1024 question 4 default: glass on the frame middle


# ---- openings_core ---------------------------------------------------------------------------------------------
def test_outer_contours_are_not_openings(badik):
    spec, mesh, rep = badik
    src = source_candidates(mesh)
    assert len(src) == len(rep['openings']) + len(rep['rejected'])  # RED: the source keeps the outer contour
    assert len(src) > len(rep['openings'])
    assert all(r['why'].startswith('external') for r in rep['rejected'])  # GREEN


def test_flat_wall_outer_contour_is_rejected_by_coverage():
    spec = jb.kpp1_badik_30()
    rep = oc.find_openings_report(jb.facade(spec))
    assert len(rep['openings']) == 3 and len(rep['rejected']) == 1
    assert 'covered' in rep['rejected'][0]['why']


@pytest.mark.parametrize('k', [1.0, 100.0])
def test_rect_frames_are_exact_at_0_90_30_deg_and_at_the_wall_end(k):
    for spec in (jb.kpp1_badik(), jb.kpp1_badik_30()):
        mesh = scaled(jb.facade(spec), 1.0)  # the host gives metres for m and cm scenes alike
        found = [o for o in oc.find_openings(mesh) if o['kind'] == 'rect']
        truth = [t for t in jb.truth(spec) if t['kind'] == 'rect']
        assert len(found) == len(truth)
        for o in found:
            t = _nearest(truth, o['frame']['origin'])
            assert math.dist(t['centre'], o['frame']['origin']) <= 0.0005
            assert wp.angle_deg(t['z'], o['frame']['z']) <= 0.01
            assert abs(o['w'] - t['w']) <= 0.0005 and abs(o['h'] - t['h']) <= 0.0005
            assert o['depth'] == pytest.approx(0.25, abs=1e-6) and o['status'] == 'ok'


def test_frame_normal_points_to_the_street_not_into_the_building(badik):
    spec, mesh, rep = badik
    for o in rep['openings']:
        if o['kind'] == 'rect':
            t = _nearest(jb.truth(spec), o['frame']['origin'])
            assert wp.angle_deg(o['frame']['z'], t['z']) < 0.01  # z = street side (source comment says so, :57001)
            x, y, z = o['frame']['x'], o['frame']['y'], o['frame']['z']
            assert abs(sum(a * b for a, b in zip(y, (0, 0, 1))) - 1) < 1e-9  # y up
            cr = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]]
            assert math.dist(cr, z) < 1e-9  # right-handed


def test_arch_is_not_a_rectangle(badik):
    spec, mesh, rep = badik
    arch = [o for o in rep['openings'] if o['kind'] == 'nonrect']
    assert len(arch) == 1 and source_is_window(arch[0]['border'])  # RED: source takes it as W01 by bbox
    assert arch[0]['status'] == 'ambiguous' and arch[0]['fill'] < 0.95  # GREEN


def test_corner_opening_has_two_branches_not_a_diagonal(badik):
    spec, mesh, rep = badik
    corner = [o for o in rep['openings'] if o['corner']]
    assert len(corner) == 1
    c = corner[0]
    diag = source_frame_width(c['border'])
    branches = [b['w'] for b in c['branches']]
    assert abs(diag - sum(branches)) > 0.4  # RED: the source frame is the diagonal (L10: 495 mm vs 2 x 600)
    assert branches == pytest.approx([0.95, 0.95], abs=1e-6)  # GREEN: 1.2 m on each wall minus the 0.25 reveal
    assert c['status'] == 'ambiguous' and c['kind'] == 'corner'
    assert wp.angle_deg(c['branches'][0]['z'], c['branches'][1]['z']) == pytest.approx(90.0, abs=1e-6)


def test_find_openings_signature_and_marker_fields(badik):
    spec, mesh, rep = badik
    o = next(o for o in rep['openings'] if o['kind'] == 'rect')
    for k in cc.OPENING_FIELDS + ('id', 'border', 'frame'):
        assert k in o
    f = oc.marker_fields(o)
    assert cc.parse_opening(cc.dump_opening(**f)) == f
    assert oc.find_openings({'verts': [], 'faces': []}) == []


def test_openings_options_are_metres_and_checked():
    with pytest.raises(ValueError):
        oc.check_options({'min_side': 1})
    with pytest.raises(ValueError):
        oc.check_options({'max_depth_m': -1})
    rep = oc.find_openings_report(jb.facade(jb.kpp1_badik()), {'min_side_m': 1.6})
    assert all(min(o['w'], o['h']) >= 1.6 for o in rep['openings'] if o['w'])


def test_wall_without_reveals_uses_face_normals():
    spec = {'name': 'flat', 'points': [[0, 0], [6, 0]], 'height': 3.0, 'reveal': 0.0, 'corners': [],
            'holes': [{'wall': 0, 'kind': 'rect', 'u': 1.0, 'sill': 0.9, 'w': 1.18, 'h': 1.8}]}
    mesh = jb.facade(spec)
    mesh = dict(mesh, faces=[f for f, m in zip(mesh['faces'], mesh['mat_ids']) if m == 1])  # no reveal quads
    ops = oc.find_openings(mesh)
    assert len(ops) == 1 and ops[0]['depth'] == 0.0
    assert wp.angle_deg(ops[0]['frame']['z'], (0, -1, 0)) < 1e-6


def test_facade_builder_has_no_t_junctions():
    for spec in (jb.kpp1_badik(), jb.kpp1_badik_30()):
        loops = source_candidates(jb.facade(spec))
        holes = len(spec['holes']) + len(spec['corners']) + 1  # + the outer contour
        assert len(loops) == holes


# ---- winplace_core -----------------------------------------------------------------------------------------------
def test_kpp1_acceptance_centre_and_normal(badik):
    """K2 acceptance: KPP1-W01..W03 on the synthetic KPP1 body, centre <= 5 mm, normal <= 0.5 deg."""
    spec, mesh, rep = badik
    p = wp.plan(rep['openings'], [], T, OFFER, info, OPTS)
    truth = jb.truth(spec)
    placed = [a for a in p['actions'] if a['status'] == 'place']
    assert len(placed) == sum(1 for t in truth if t['type'])
    for a in placed:
        t = _nearest(truth, a['opening']['frame']['origin'])
        assert a['type'] == t['type']
        W, D, H = info(a['type'])['size_m']
        c = wp.apply_rows(a['rows'], [W / 2, D / 2, H / 2])
        assert math.dist(c, t['centre']) <= 0.005
        assert wp.angle_deg(wp.face_normal_world(a['rows'], '-y'), t['z']) <= 0.5
        assert a['findings'] == []


def test_minus_y_models_face_the_street_without_auto_rotation():
    fr = {'origin': [1, 2, 3], 'x': [1, 0, 0], 'y': [0, 0, 1], 'z': [0, -1, 0]}
    assert source_normal_deg('-y') == 180.0  # RED: Win_Typical faces -Y, the source turns it into the building
    for axis in ('-y', '+y'):
        rows = wp.placement_rows(fr, [1.18, 0.1, 1.8], axis)
        assert wp.angle_deg(wp.face_normal_world(rows, axis), fr['z']) < 1e-9  # GREEN for both stored axes
        r = rows[:3]
        det = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1]) - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
               + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
        assert det == pytest.approx(1.0)  # a rotation, never a mirror


def test_face_axis_is_stored_for_every_type():
    rows = {r['id']: r for r in REPORT['types']}
    assert set(rows) == set(T) and all(r['face_axis'] in wg.FACE_AXES for r in rows.values())
    assert all(STD['types'][f'WT-{n:02d}']['face_axis'] == '-y' for n in range(1, 25))


@pytest.mark.parametrize('extra_mm,accepted', [(10, True), (50, False)])
def test_threshold_is_per_axis_in_metres_same_in_m_and_cm(extra_mm, accepted):
    w01 = T['KPP1-W01']
    ow, oh = w01['width_m'] + extra_mm / 1000.0, w01['height_m']
    m = wp.match({'w': ow, 'h': oh}, [T[i] for i in OFFER], OPTS['fit_tol_m'])
    assert (m['type'] == 'KPP1-W01') is accepted
    if not accepted:
        assert m['status'] == 'none' and m['type'] is None


def test_source_threshold_depends_on_the_scene_units():
    w = T['KPP1-W01']
    assert source_fit(w['width_m'] + 0.150, w['height_m'], w['width_m'], w['height_m'], 1.0)  # m: +150 mm taken
    assert not source_fit(w['width_m'] + 0.005, w['height_m'], w['width_m'], w['height_m'], 0.01)  # cm: +5 refused
    tol = OPTS['fit_tol_m']
    assert wp.match({'w': w['width_m'] + 0.150, 'h': w['height_m']}, [w], tol)['type'] is None
    assert wp.match({'w': w['width_m'] + 0.005, 'h': w['height_m']}, [w], tol)['type'] == 'KPP1-W01'


def test_alignment_by_the_centre():
    w = T['KPP1-W01']
    fr = {'origin': [0, 0, 0], 'x': [1, 0, 0], 'y': [0, 0, 1], 'z': [0, -1, 0]}
    o = {'w': w['width_m'] + 0.010, 'h': w['height_m'], 'frame': fr, 'depth': 0.25}
    assert source_centre_error(o['w'], o['h'], w['width_m'], w['height_m']) == pytest.approx(0.005)  # RED
    mi = info('KPP1-W01')
    rows = wp.placement_rows(fr, mi['size_m'], '-y')
    W, D, H = mi['size_m']
    assert math.dist(wp.apply_rows(rows, [W / 2, D / 2, H / 2]), fr['origin']) < 1e-9  # GREEN
    assert wp.check_fit(o, w, mi, rows, '-y', OPTS) == []


def test_fit_check_names_gap_cut_and_protrusion():
    w = T['KPP1-W01']
    fr = {'origin': [0, 0, 0], 'x': [1, 0, 0], 'y': [0, 0, 1], 'z': [0, -1, 0]}
    mi = info('KPP1-W01')
    rows = wp.placement_rows(fr, mi['size_m'], '-y')
    codes = lambda o, opts=OPTS: sorted({c for c, _ in wp.check_fit(o, w, mi, rows, '-y', opts)})  # noqa: E731
    assert codes({'w': w['width_m'] + 0.06, 'h': w['height_m'], 'frame': fr, 'depth': 0.25}) == ['fit_gap']
    assert codes({'w': w['width_m'] - 0.01, 'h': w['height_m'], 'frame': fr, 'depth': 0.25}) == ['intersects_body']
    assert codes({'w': w['width_m'], 'h': w['height_m'], 'frame': fr, 'depth': 0.02}) == ['protrudes']


def test_frame_middle_on_the_border_plane_and_recess():
    fr = {'origin': [0, 0, 0], 'x': [1, 0, 0], 'y': [0, 0, 1], 'z': [0, -1, 0]}
    mi = info('KPP1-W01')
    W, D, H = mi['size_m']
    for recess in (0.0, 0.03):
        rows = wp.placement_rows(fr, mi['size_m'], '-y', recess)
        face = wp.apply_rows(rows, [W / 2, 0.0, H / 2])  # frame face, local y = 0
        back = wp.apply_rows(rows, [W / 2, D, H / 2])
        assert face[1] == pytest.approx(-D / 2 + recess) and back[1] == pytest.approx(D / 2 + recess)


def test_non_standard_arch_and_corner_are_ambiguous_with_drafts(badik):
    spec, mesh, rep = badik
    p = wp.plan(rep['openings'], [], T, OFFER, info, OPTS)
    amb = [a for a in p['actions'] if a['status'] == 'ambiguous']
    kinds = sorted(a['opening']['kind'] for a in amb)
    assert kinds == ['corner', 'nonrect', 'rect']  # 1.5 x 1.5 (rect, no type), arch, corner
    assert all(a['rows'] is None for a in amb)  # no rectangular window in the arch
    for a in amb:
        d = wg.draft_entry(dict(a['opening'], marker=a['marker']), STD)
        assert d['schema'] == wg.DRAFT_SCHEMA and d['status'] == 'draft' and d['source']['opening'] == a['marker']
        assert d['panes_m'][0][0] == pytest.approx(STD['families']['F100']['face_m'])


def test_markers_are_updated_not_duplicated_and_their_type_wins(badik):
    spec, mesh, rep = badik
    o = next(o for o in rep['openings'] if o['kind'] == 'rect' and abs(o['w'] - 1.18) < 1e-6 and o['h'] < 2)
    mk = {'name': 'OPEN_007', 'handle': 77, 'rows': wp.marker_rows(o['frame']), 'type': 'KPP1-W01', 'opening': None}
    p = wp.plan([o], [mk], T, OFFER, info, OPTS)
    a, = p['actions']
    assert a['marker'] == 'OPEN_007' and not a['marker_new'] and a['type'] == 'KPP1-W01'
    p2 = wp.plan([o], [dict(mk, type='WT-02')], T, OFFER, info, OPTS)
    assert p2['actions'][0]['status'] == 'ambiguous' and 'карантин' in p2['actions'][0]['why'][-1]
    p3 = wp.plan([o, o], [mk], T, OFFER, info, OPTS)
    assert [x['marker'] for x in p3['actions']] == ['OPEN_007', 'OPEN_008']


def test_a_typed_marker_without_border_places_by_its_transform():
    fr = {'origin': [5, 0, 1.8], 'x': [1, 0, 0], 'y': [0, 0, 1], 'z': [0, -1, 0]}
    w = T['KPP1-W03']
    mk = {'name': 'OPEN_001', 'handle': 9, 'rows': wp.marker_rows(fr), 'type': 'KPP1-W03',
          'opening': {'w': w['width_m'], 'h': w['height_m'], 'sill': 0.9, 'depth': 0.25, 'wall': 'X', 'corner': False}}
    p = wp.plan([], [mk], T, OFFER, info, OPTS)
    a, = p['actions']
    assert a['status'] == 'place' and a['source'] == 'marker' and a['findings'] == []


def test_two_types_of_one_size_are_ambiguous_not_random():
    """GeoAGR.ms:45538 (author note): pick by size, not at random. WT-07 and WT-10 share 2514 x 2614."""
    m = wp.match({'w': 2.514, 'h': 2.614}, [T['WT-07'], T['WT-10']], 0.02)
    assert m['status'] == 'ambiguous' and set(m['others']) == {'WT-07', 'WT-10'}


def test_quarantined_type_is_never_offered():
    wt02 = T['WT-02']
    assert 'WT-02' not in OFFER
    m = wp.match({'w': wt02['width_m'], 'h': wt02['height_m']}, [T[i] for i in OFFER], 0.02)
    assert m['type'] != 'WT-02'


def test_options_are_checked():
    for bad in ({'fit_tol': 1}, {'fit_tol_m': 0}, {'statuses': ['quarantine']}, {'library': ''}):
        with pytest.raises(ValueError):
            wp.check_options(bad)


# ---- windowgen_core ------------------------------------------------------------------------------------------------
def _members(m):
    """Frame members of a generated mesh from its glass fields (metres)."""
    f = sorted(r for k, r in m['fields'] if k == 'glass')
    return f


def test_wt11_section_by_the_f100_standard():
    """L10 minimal acceptance 2: face 57 +- 0.5, depth 100 +- 0.5, mullion/transom 50 +- 0.5, glass a plane at the
    set depth, glass fields = panes_m +- 1 mm."""
    m = wg.build_type(T['WT-11'], STD)
    assert m['family'] == 'F100' and m['status'] == 'ok'
    f = _members(m)
    xs = sorted({r[0] for r in f} | {r[2] for r in f})
    zs = sorted({r[1] for r in f} | {r[3] for r in f})
    W, D, H = m['size_m']
    assert xs[0] * 1000 == pytest.approx(57, abs=0.5) and (W - xs[-1]) * 1000 == pytest.approx(57, abs=0.5)
    assert zs[0] * 1000 == pytest.approx(57, abs=0.5) and (H - zs[-1]) * 1000 == pytest.approx(57, abs=0.5)
    assert (xs[2] - xs[1]) * 1000 == pytest.approx(50, abs=0.5) and (zs[2] - zs[1]) * 1000 == pytest.approx(50, abs=0.5)
    assert D * 1000 == pytest.approx(100, abs=0.5)
    assert max(v[1] for v in m['verts']) == pytest.approx(D) and min(v[1] for v in m['verts']) == pytest.approx(0.0)
    gl = {m['verts'][i][1] for fi in m['parts']['glass'] for i in m['faces'][fi]}
    assert len(gl) == 1 and gl.pop() == pytest.approx(0.08)  # one plane 80 mm from the face (owner 06.11, as in Win_Typical)
    for (k, r), src in zip(sorted(m['fields']), sorted(T['WT-11']['panes_m'])):
        assert max(abs(a - b) for a, b in zip(r, src)) <= 0.001


def test_glass_is_80_mm_from_the_face_not_the_frame_middle():
    m = wg.build_type(T['WT-11'], STD)
    middle = ISSUE_GLASS_AT_FRAME_MIDDLE * m['depth_m']
    assert abs(middle - 0.0804) > 0.02  # RED: the #1024 default (frame middle) is 30 mm off the source
    assert m['glass_y_m'] == pytest.approx(0.08)  # GREEN


def test_frame_mesh_is_closed_and_faces_minus_y():
    for tid in ('WT-11', 'KPP1-W02', 'W01', 'WT-13', 'D03'):
        m = wg.build_type(T[tid], STD)
        frame = wg.part_mesh(m, 'frame')
        solid = [f for f, mid in zip(frame['faces'], frame['mat_ids']) if mid != wg.MAT_OPAQUE]
        _, faces, _ = oc.weld(frame['verts'], solid, 1e-6)
        assert oc.boundary_loops(faces) == [], tid  # watertight frame
        front = [f for f, mid in zip(m['faces'], m['mat_ids']) if mid == wg.MAT_FACE and
                 all(abs(m['verts'][i][1]) < 1e-9 for i in f)]
        assert front and all(oc.face_normal(m['verts'], f)[1] == pytest.approx(-1.0) for f in front)
        assert m['face_axis'] == '-y' and m['face_axis_m'] == 0.0


def test_doors_get_f73_and_balcony_blocks_f58():
    assert wg.build_type(T['WT-13'], STD)['family'] == 'F73'
    assert wg.build_type(T['D02'], STD)['family'] == 'F73'
    assert wg.build_type(T['WT-01'], STD)['family'] == 'F58'
    m = wg.build_type(T['WT-13'], STD)
    assert m['depth_m'] == pytest.approx(0.073) and m['glass_y_m'] == pytest.approx(0.0334)


def test_wt02_is_quarantined_standard_not_applicable():
    q = wg.quality(T['WT-02'], STD)
    assert q['status'] == 'quarantine' and 'неприменим' in q['why'][0]


def test_wt07_and_wt10_are_not_merged():
    a, b = T['WT-07'], T['WT-10']
    assert source_merges(a, b)  # RED: the K2 default merged them by size
    rows = {r['id']: r for r in REPORT['types']}
    assert rows['WT-07']['verdict'] == 'pass' and rows['WT-10']['verdict'] == 'pass'  # GREEN (owner 06.11)
    assert not wg.same_subdivision(a, b)


def test_same_subdivision_is_a_duplicate_with_same_as():
    twin = dict(T['WT-11'], id='WT-11-copy', status='unconfirmed')
    rep = wg.library_report([T['WT-11'], twin], STD)
    rows = {r['id']: r for r in rep['types']}
    assert rows['WT-11-copy']['verdict'] == 'duplicate' and rows['WT-11-copy']['same_as'] == 'WT-11'
    assert wg.offerable(rep) == ['WT-11']


def test_library_report_covers_67_types():
    assert len(REPORT['types']) == 67 and sum(REPORT['counts'].values()) == 67
    q = {r['id'] for r in REPORT['types'] if r['verdict'] == 'quarantine'}
    assert {'WT-02', 'D04', 'CW_021', 'CW_022', 'ELV-17'} <= q
    assert REPORT['counts']['duplicate'] == 0


@pytest.mark.parametrize('bad,word', [
    ({'typed': False}, 'типизирован'), ({'panes_m': [], 'opaque_m': None}, 'разбивки'),
    ({'width_m': 9.0}, 'пределов'), ({'panes_m': [[0.05, 0.05, 0.6, 1.0], [0.5, 0.05, 1.1, 1.0]]}, 'перекрываются'),
    ({'panes_m': [[0.05, 0.05, 0.09, 1.0]]}, 'вырожденное'), ({'source': {'occurrences': 0}}, 'встречается')])
def test_quality_criteria(bad, word):
    e = dict(T['KPP1-W01'], **bad)
    q = wg.quality(e, STD)
    assert q['status'] == 'quarantine' and any(word in w for w in q['why']), q


def test_standard_is_validated():
    doc = json.loads((ROOT / 'library/windows/standard.json').read_text(encoding='utf-8'))
    assert doc['families']['F100']['face_m'] == 0.057 and doc['families']['F100']['impost_m'] == 0.05
    for mutate in (lambda d: d.update(schema='x'), lambda d: d['families']['F100'].pop('depth_m'),
                   lambda d: d['role_family'].update(window='F999'), lambda d: d['types']['WT-01'].update(face_axis='z')):
        d = json.loads(json.dumps(doc))
        mutate(d)
        with pytest.raises(ValueError):
            wg.load_standard(d)


def test_npm_variant_is_one_plane():
    m = wg.build_type(T['WT-11'], STD, {'variant': 'npm'})
    assert len(m['faces']) == 1 and m['parts']['glass'] == []
    with pytest.raises(ValueError):
        wg.build_type(T['WT-11'], STD, {'variant': 'x'})


def test_preview_sheet_png_and_obj():
    png = wg.sheet_png(LIB['types'], STD, REPORT)
    assert png[:8] == b'\x89PNG\r\n\x1a\n' and len(png) > 1000
    obj = wg.to_obj(wg.build_type(T['WT-11'], STD), 'WT-11')
    assert obj.count('\nf ') == len(wg.build_type(T['WT-11'], STD)['faces']) and 'g WT-11_glass' in obj


def test_library_dir_resolution(tmp_path):
    assert Path(wg.library_dir()) == (ROOT / 'library/windows').resolve()
    with pytest.raises(ValueError, match='options.library'):
        wg.library_dir(str(tmp_path))
    assert Path(wg.library_dir(None, {'AGR_TOOLS_REPO': str(ROOT)}, str(tmp_path / 'x' / 'y' / 'z' / 'm.py'))) == \
        (ROOT / 'library/windows').resolve()


# ---- glue files load without pymxs and name their functions ------------------------------------------------------
def test_glue_functions_exist_and_load_without_pymxs():
    wpm = _load(PKG / 'winplace_max.py', 'agr_tools_winplace_max_t')
    wgm = _load(PKG / 'windowgen_max.py', 'agr_tools_windowgen_max_t')
    assert callable(wpm.win_place) and callable(wgm.win_generate)
    with pytest.raises(ValueError):
        wgm.check_options({'ids': []})
    assert wgm.check_options({'ids': 'all'})['ids'] == 'all'


def test_polygon_fragment_expectations_match_the_cores():
    """The J stations: the PASS wall places 2 windows, the FAIL wall gives no_type + opening_ambiguous; the
    win.generate markers: WT-11 pass, WT-02 quarantine."""
    doc = json.loads((ROOT / 'test-polygon/stations/J.json').read_text(encoding='utf-8'))
    st = {s['button']: s for s in doc['stations']}
    for o in st['win.place']['objects']:
        rep = oc.find_openings_report(jb.facade(o['extra']['j']['spec']))
        p = wp.plan(rep['openings'], [], T, OFFER, info, OPTS)
        codes = sorted({('opening_ambiguous' if a['opening']['kind'] != 'rect' else 'no_type')
                        for a in p['actions'] if a['status'] != 'place'})
        want = next(e for e in st['win.place']['expected'] if e['name'] == o['name'])
        assert codes == sorted(want['codes'])
    rows = {r['id']: r for r in REPORT['types']}
    assert rows['WT-11']['verdict'] == 'pass' and rows['WT-02']['verdict'] == 'quarantine'


def test_committed_quality_report_matches_the_generator():
    """library/windows/quality.json is the K2 report of the committed library + standard (rebuilt by
    tools/library/build_window_types.py --quality-of); every type keeps its face axis there."""
    committed = json.loads((ROOT / 'library/windows/quality.json').read_text(encoding='utf-8'))
    assert committed == json.loads(wg.report_json(REPORT))
