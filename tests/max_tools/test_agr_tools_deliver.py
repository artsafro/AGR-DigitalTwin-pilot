"""new-case: AGR Tools 1.0 (#1024) stage 9 of branch S: `ucx.gap` (1.0.27), `light.export` (1.0.29) and `pack.deliver`
(1.0.26) judged without pymxs.

Every defect named for the buttons (lab 1.0 L13: docs/experiments/ucx.gap.md, docs/experiments/light.export.md;
#1024 «редакция 1» §9/§15) has a test that is RED on a model of the source behaviour and GREEN on the branch S
cores. The source models are written from the MEASURED behaviour (no source code copied, #853): GeoAGR UCX Move
`GeoAGR.ms:61446-61599`, MultiPass `facesOverlap` `GeoAGR.ms:62188` (T10-01); GeoAGR Export HighPoly
`GeoAGR.ms:66904-67035` (light pick `:66915`), ReSave Lights FBXs `:65127` (X01), Archivate filter `:66307`.
"""
import ast
import importlib.util
import json
import math
import struct
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'


def _load(path, name):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core')
uc = _load(PKG / 'ucx_core.py', 'agr_tools_ucx_core')
gc = _load(PKG / 'ucx10_core.py', 'agr_tools_ucx10_core_t')
lc = _load(PKG / 'light_core.py', 'agr_tools_light_core_s')
dc = _load(PKG / 'deliver_core.py', 'agr_tools_deliver_core_t')
pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_s')
OPTS = gc.gap_options(None)
MM = 0.001


# ==== ucx.gap =====================================================================================================
def box(x0, y0, z0, x1, y1, z1):
    v, t = uc._convex_hull([[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])
    return [list(p) for p in v], [list(f) for f in t]


def row(h, name, mesh):
    return {'handle': h, 'name': name, 'verts': mesh[0], 'tris': mesh[1]}


def pair(gap_m, unit=1.0):
    """Two 1 m cubes along X with a gap (negative = overlap); unit = metres of one system unit (rows in metres)."""
    return [row(1, 'UCX_Body_01', box(0, 0, 0, 1, 1, 1)), row(2, 'UCX_Body_02', box(1 + gap_m, 0, 0, 2 + gap_m, 1, 1))]


def gap_after(result, a=1, b=2):
    pa, pb = result['pieces'][a], result['pieces'][b]
    return gc.separation(gc.piece(pa['verts'], pa['tris']), gc.piece(pb['verts'], pb['tris']))[0]


def geoagr_ucx_move(gap_sys):
    """GeoAGR UCX Move LMB (lab L13 table, measured): a ray hit d with d < 0.002 or 0.002 < d <= 0.03 SYSTEM
    units moves both faces by (d - 0.005) / 2; a touch (0) and an overlap (< 0) give no hit; Alt pushes a touch
    by +2.5 mm on both sides and deepens an overlap to -3 mm."""
    if gap_sys <= 0:
        return gap_sys
    if gap_sys < 0.002 or 0.002 < gap_sys <= 0.03:
        return 0.005
    if gap_sys == 0.002:
        return 0.005
    return gap_sys


def geoagr_faces_overlap(a, b):
    """MultiPass facesOverlap GeoAGR.ms:62188 (T10-01, measured): an AABB overlap counts as an intersection."""
    (alo, ahi), (blo, bhi) = gc._aabb(a), gc._aabb(b)
    return all(alo[k] <= bhi[k] and blo[k] <= ahi[k] for k in range(3))


@pytest.mark.parametrize('gap_mm', [-2, 0])
def test_red_geoagr_misses_touch_and_overlap(gap_mm):
    assert geoagr_ucx_move(gap_mm * MM) == gap_mm * MM            # RED: nothing found, nothing moved
    res = gc.plan(pair(gap_mm * MM), OPTS)                         # GREEN: found and opened to 4 mm
    assert res['pairs'][0]['code'] == ('ucx_overlap' if gap_mm < 0 else 'ucx_touch')
    assert gap_after(res) == pytest.approx(0.004, abs=gc.TOL_M)


@pytest.mark.parametrize('gap_mm', [10, 25])
def test_red_geoagr_shrinks_10_25_mm_gaps_to_5(gap_mm):
    assert geoagr_ucx_move(gap_mm * MM) == pytest.approx(0.005)    # RED: a wider gap is reduced
    res = gc.plan(pair(gap_mm * MM), OPTS)                          # GREEN: >= target never changes
    assert res['pairs'] == [] and not any(p['changed'] for p in res['pieces'].values())


def test_red_geoagr_centimetre_scene_changes_nothing():
    gap_m = 0.001
    gap_sys_cm = gap_m / 0.01                                       # 0.1 system units in a cm scene
    assert geoagr_ucx_move(gap_sys_cm) == gap_sys_cm                # RED: thresholds in system units
    cm = [dict(r, verts=[[c * 0.01 for c in v] for v in r['verts']])
          for r in [row(1, 'UCX_Body_01', box(0, 0, 0, 100, 100, 100)),
                    row(2, 'UCX_Body_02', box(100.1, 0, 0, 200.1, 100, 100))]]
    res_cm, res_m = gc.plan(cm, OPTS), gc.plan(pair(gap_m), OPTS)   # GREEN: host gives metres -> m == cm
    assert gap_after(res_cm) == pytest.approx(gap_after(res_m), abs=1e-9) == pytest.approx(0.004, abs=gc.TOL_M)


def test_red_alt_deepens_an_overlap_and_there_is_no_alt_here():
    alt_overlap = -0.003                                            # RED (measured): Alt -2 mm -> -3 mm
    assert alt_overlap < -0.002
    with pytest.raises(ValueError):
        gc.gap_options({'alt': True})
    assert gap_after(gc.plan(pair(-0.002), OPTS)) == pytest.approx(0.004, abs=gc.TOL_M)


def test_red_multipass_aabb_is_not_an_intersection_sat_is():
    # two tetrahedra whose AABBs overlap but which do not intersect (A: x + y <= 1, B: x + y >= 1.2)
    a = gc.piece([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
    bv = [[1.1, 1.1, 0], [0.1, 1.1, 0], [1.1, 0.1, 0], [1.1, 1.1, 1]]
    b = gc.piece(bv, [list(t) for t in uc._convex_hull(bv)[1]])
    assert geoagr_faces_overlap(a, b)                               # RED: AABB says «intersection»
    g, _ = gc.separation(a, b)                                      # GREEN: SAT finds the gap
    assert g == pytest.approx(0.2 / math.sqrt(2), abs=1e-9)


@pytest.mark.parametrize('scale', [1.0, 0.01])
@pytest.mark.parametrize('gap_mm', [-2, 0, 1, 2, 4, 10, 40])
def test_l13_acceptance_table_in_m_and_cm(gap_mm, scale):
    rows = [dict(r, verts=[[c for c in v] for v in r['verts']]) for r in pair(gap_mm * MM)]
    rows.append(row(3, 'UCX_Other_001', box(1, 2, 0, 2, 3, 1)))    # foreign family touching nothing of ours
    res = gc.plan(rows, OPTS)
    after = gap_after(res)
    if gap_mm < 4:
        assert after == pytest.approx(0.004, abs=gc.TOL_M)
        p = res['pairs'][0]
        assert p['shift_a_m'] == pytest.approx(p['shift_b_m'], abs=1e-9)       # both planes equally
        assert p['shift_a_m'] == pytest.approx((0.004 - gap_mm * MM) / 2, abs=1e-9)
    else:
        assert after == pytest.approx(gap_mm * MM, abs=1e-9) and res['pairs'] == []
    assert res['pieces'][3]['changed'] is False and res['pieces'][3]['verts'] == [
        [round(c, 9) for c in v] for v in rows[2]['verts']]
    for p in res['pieces'].values():                                # convex, closed, volume kept almost
        assert uc.convexity(p['verts'], p['tris'])['ok']
    again = gc.plan([{'handle': h, 'name': p['name'], 'verts': p['verts'], 'tris': p['tris']}
                     for h, p in res['pieces'].items()], OPTS)
    assert again['pairs'] == [] and not any(p['changed'] for p in again['pieces'].values())   # repeat: no change


def test_staircase_of_five_touching_steps_gets_4_mm_everywhere():
    rows = [row(i + 1, 'UCX_Stairs_{:02d}'.format(i + 1), box(i * 0.3, 0, 0, (i + 1) * 0.3, 1.2, (i + 1) * 0.15))
            for i in range(5)]
    res = gc.plan(rows, OPTS)
    assert res['summary']['pairs_fixed'] == 4 and res['summary']['left'] == []
    for i in range(1, 5):
        assert gap_after(res, i, i + 1) == pytest.approx(0.004, abs=gc.TOL_M)


def test_gap_parameter_range_and_deep_overlap_and_thin_piece():
    assert gap_after(gc.plan(pair(0.0), gc.gap_options({'gap_m': 0.002}))) == pytest.approx(0.002, abs=gc.TOL_M)
    assert gap_after(gc.plan(pair(0.0), gc.gap_options({'gap_m': 0.01}))) == pytest.approx(0.01, abs=gc.TOL_M)
    for bad in (0.001, 0.011, 'x', True, float('nan')):
        with pytest.raises(ValueError):
            gc.gap_options({'gap_m': bad})
    with pytest.raises(ValueError):
        gc.gap_options({'mode': 'split'})
    deep = gc.plan(pair(-0.05), OPTS)
    assert deep['pairs'][0]['action'] == 'ambiguous' and deep['ambiguous']
    assert not any(p['changed'] for p in deep['pieces'].values())
    thin = gc.plan([row(1, 'UCX_T_01', box(0, 0, 0, 0.021, 1, 1)), row(2, 'UCX_T_02', box(0.021, 0, 0, 1, 1, 1))],
                   OPTS)
    assert thin['pairs'][0]['action'] == 'ambiguous'
    assert {c for c, _ in thin['findings'][1]} == {'ucx_too_thin'}


def test_non_convex_piece_empty_scope_and_report():
    l_shape = uc._convex_hull([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    verts = [list(v) for v in l_shape[0]]
    tris = [list(t) for t in l_shape[1]]
    tris[0] = tris[0][::-1]                                           # one flipped face: not closed/convex
    res = gc.plan([row(1, 'UCX_A_01', (verts, tris)), row(2, 'Box001', box(0, 0, 0, 1, 1, 1))], OPTS)
    assert res['findings'][1][0][0] == 'ucx_not_convex' and res['skipped'][0]['item'] == 'Box001'
    with pytest.raises(ValueError):
        gc.plan([], OPTS)
    rows = pair(0.001)
    res = gc.plan(rows, OPTS)
    rep = gc.gap_report(ec, 'preview', rows, res, OPTS, state_hash='s')
    assert rep['status'] == 'fail' and rep['plan']['units'] == 'm' and rep['plan']['done']
    assert {f['code'] for o in rep['objects'] for f in o['findings']} == {'ucx_gap_small'}
    ok = gc.gap_report(ec, 'preview', pair(0.01), gc.plan(pair(0.01), OPTS), OPTS, state_hash='s')
    assert ok['status'] == 'pass'


# ==== light.export ================================================================================================
def _fbx_node(name, props=(), children=()):
    body = b''
    for p in props:
        if isinstance(p, str):
            raw = p.encode('latin-1')
            body += b'S' + struct.pack('<I', len(raw)) + raw
        elif isinstance(p, float):
            body += b'D' + struct.pack('<d', p)
        else:
            body += b'L' + struct.pack('<q', p)
    return (name, len(props), body, list(children))


def _fbx_bytes(nodes, version=7400):
    """Minimal binary FBX writer for the tests (node records of FBX 7.x: 13-byte headers < 7500, else 25)."""
    head = 25 if version >= 7500 else 13
    fmt = '<QQQ' if version >= 7500 else '<III'

    def enc(node, at):
        name, count, body, children = node
        inner = at + head + len(name) + len(body)
        kids = b''
        for c in children:
            kids += enc(c, inner + len(kids))
        if children:
            kids += bytes(head)
        end = inner + len(kids)
        return struct.pack(fmt, end, count, len(body)) + bytes([len(name)]) + name.encode('latin-1') + body + kids
    out = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', version)
    for n in nodes:
        out += enc(n, len(out))
    return out + bytes(head)


def _p(name, *vals):
    return _fbx_node('P', (name, 'Lcl', '', 'A') + tuple(float(v) for v in vals))


def fbx_scene(models, version=7400):
    """models: [(id, name, kind 'Null'|'Light', parent id, light type int|None, rotation xyz deg)]."""
    objs, conns = [], []
    for mid, name, kind, parent, ltype, rot in models:
        p70 = [_p('Lcl Rotation', *rot)]
        if ltype is not None:  # Max writes the FBX light axis as PostRotation (-90, 0, 0) (job 20261106-044737)
            p70.append(_p('PostRotation', -90.0, 0.0, 0.0))
        objs.append(_fbx_node('Model', (mid, name + '\x00\x01Model', kind),
                              [_fbx_node('Properties70', (), p70)]))
        conns.append(_fbx_node('C', ('OO', mid, parent)))
        if ltype is not None:
            aid = mid + 100000
            objs.append(_fbx_node('NodeAttribute', (aid, name + '\x00\x01NodeAttribute', 'Light'),
                                  [_fbx_node('Properties70', (), [_fbx_node('P', ('LightType', 'enum', '', '',
                                                                                   int(ltype)))])]))
            conns.append(_fbx_node('C', ('OO', aid, mid)))
    return _fbx_bytes([_fbx_node('Objects', (), objs), _fbx_node('Connections', (), conns)], version)


IDENT = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def light_scene(folder, root='SM_TestAddr_Root'):
    """L13 scene: 3 Free Spot, 2 Omni, 1 Target Spot, 1 Photometric under one root Dummy."""
    helpers = [{'handle': 10, 'name': root, 'cls': 'Dummy', 'parent': None, 'hidden': False, 'frozen': False}]
    spec = [('SM_TestAddr_Spot_001', 'freeSpot'), ('SM_TestAddr_Spot_002', 'freeSpot'),
            ('SM_TestAddr_Spot_003', 'freeSpot'), ('SM_TestAddr_Omni_001', 'Omnilight'),
            ('SM_TestAddr_Omni_002', 'Omnilight'), ('SM_TestAddr_Spot_004', 'targetSpot'),
            ('SM_TestAddr_Photo_001', 'Free_Light')]
    lights = [{'handle': 20 + i, 'name': n, 'cls': c, 'parent': 10, 'hidden': False, 'frozen': False,
               'rot': lc.euler_matrix((-30.0, 0.0, 45.0)) if c == 'targetSpot' else IDENT,
               'target': 99 if c == 'targetSpot' else None} for i, (n, c) in enumerate(spec)]
    return lights, helpers, lc.export_options({'folder': str(folder)})


def geoagr_light_pick(lights, helpers):
    """GeoAGR Export HighPoly GeoAGR.ms:66915 (L13, measured): the light file takes nodes whose NAME contains
    `Spot` or `Root` - Omni and Photometric are lost."""
    return [r['name'] for r in list(helpers) + list(lights) if 'Spot' in r['name'] or 'Root' in r['name']]


def test_red_geoagr_name_substring_loses_omni_and_photometric(tmp_path):
    lights, helpers, opts = light_scene(tmp_path)
    picked = geoagr_light_pick(lights, helpers)
    assert not any('Omni' in n or 'Photo' in n for n in picked)            # RED
    plan = lc.export_plan(lights, helpers, opts)                           # GREEN: by hierarchy
    assert len(plan['lights']) == 7 and plan['export'][0] == 10 and len(plan['export']) == 8
    assert {r['kind'] for r in plan['lights']} == {'omni', 'spot', None}
    assert plan['target'] == str(tmp_path / 'SM_TestAddr_Light.fbx') and plan['blockers'] == []
    assert {c for c, _ in plan['findings'][26]} == {'light_type'}          # Photometric: exported, flagged


def _scene_fbx(plan, rot_target=(-30.0, 0.0, 45.0), drop=(), types_=None, version=7400, extra_top=()):
    kinds = types_ or {'spot': 2, 'omni': 0, None: 0}
    models = [(1, plan['root']['name'], 'Null', 0, None, (0, 0, 0))]
    for i, r in enumerate(plan['lights']):
        if r['name'] in drop:
            continue
        rot = rot_target if r['target'] else (0, 0, 0)
        models.append((100 + i, r['name'], 'Light', 1, kinds[r['kind']], rot))
    for j, name in enumerate(extra_top):
        models.append((900 + j, name, 'Null', 0, None, (0, 0, 0)))
    return lc.fbx_lights(fbx_scene(models, version))


def test_readback_counts_kinds_parents_and_direction(tmp_path):
    lights, helpers, opts = light_scene(tmp_path)
    plan = lc.export_plan(lights, helpers, opts)
    found, summary = lc.readback_findings(plan, _scene_fbx(plan))
    assert found == {} and summary['lights'] == 7 and summary['tops'] == 1


def test_red_target_spot_loses_its_direction(tmp_path):
    lights, helpers, opts = light_scene(tmp_path)
    plan = lc.export_plan(lights, helpers, opts)
    found, _ = lc.readback_findings(plan, _scene_fbx(plan, rot_target=(0, 0, 0)))  # RED model: no direction
    assert {c for c, _ in found[25]} == {'light_direction'}
    found, _ = lc.readback_findings(plan, _scene_fbx(plan, extra_top=('SM_TestAddr_Spot_004.Target',)))
    assert {c for c, _ in found[10]} == {'light_readback_extra'}                # a target at the top: 2 roots


def test_measured_max_target_spot_rotation_matches_its_aim():
    # job 20261106-044737-6d28f847: Target Spot at (9, 9, 4) aimed at (11, 13, 0) -> Lcl (48.19, 0, -26.565), Post -90
    m = {'r': [48.18968510422141, 0.0, -26.56505117707799], 'pre': [0, 0, 0], 'post': [-90.0, 0.0, 0.0]}
    rot = lc.fbx_world_rotation(m)
    aim = [-rot[i][2] for i in range(3)]                 # a Max light shines along its local -Z
    n = math.sqrt(2.0 ** 2 + 4.0 ** 2 + 4.0 ** 2)
    assert aim == pytest.approx([2.0 / n, 4.0 / n, -4.0 / n], abs=1e-9)


def test_red_lost_omni_is_found_by_the_readback(tmp_path):
    lights, helpers, opts = light_scene(tmp_path)
    plan = lc.export_plan(lights, helpers, opts)
    found, _ = lc.readback_findings(plan, _scene_fbx(plan, drop=('SM_TestAddr_Omni_001', 'SM_TestAddr_Photo_001')))
    assert {c for c, _ in found[23]} == {'light_readback_missing'}
    assert 'light_readback_count' in {c for c, _ in found[10]}


def test_red_resave_writes_fbx_77(tmp_path):
    lights, helpers, opts = light_scene(tmp_path)
    plan = lc.export_plan(lights, helpers, opts)
    found, _ = lc.readback_findings(plan, _scene_fbx(plan, version=7700))
    assert 'light_fbx_version' in {c for c, _ in found[10]}


def test_red_no_ucx_no_light_file(tmp_path):
    def geoagr_export(has_ucx):
        return ['SM_TestAddr.fbx', 'SM_TestAddr_Light.fbx'] if has_ucx else []   # L13: messageBox, no file
    assert geoagr_export(False) == []                                             # RED
    lights, helpers, opts = light_scene(tmp_path)
    assert lc.export_plan(lights, helpers, opts)['target']                         # GREEN: no UCX input at all
    src = (PKG / 'light_core.py').read_text(encoding='utf-8')
    assert 'UCX' not in src.split('# light.export (#1024')[1].split('def export_options')[1]


def test_red_existing_file_is_never_overwritten(tmp_path):
    (tmp_path / 'SM_TestAddr_Light.fbx').write_bytes(b'old')
    lights, helpers, opts = light_scene(tmp_path)
    plan = lc.export_plan(lights, helpers, opts)                                   # default: next version
    assert plan['target'] == str(tmp_path / 'SM_TestAddr_Light_v002.fbx')
    refuse = lc.export_plan(lights, helpers, dict(opts, on_exists='refuse'))
    assert refuse['target'] is None and refuse['blockers'] and 'light_fbx_exists' in {
        c for c, _ in refuse['findings'][10]}
    rep = lc.export_report(ec, 'preview', lights, refuse, opts, state_hash='s')
    assert rep['status'] == 'fail' and rep['plan']['ambiguous']
    assert (tmp_path / 'SM_TestAddr_Light.fbx').read_bytes() == b'old'


def test_red_light_fbx_left_out_of_the_vpm_archive():
    names = ['SM_TestAddr.fbx', 'SM_TestAddr_Light.fbx', 'T_TestAddr_Diffuse_1.1001.png']

    def geoagr_archive_filter(n):  # GeoAGR.ms:66307 (L04/L13): the VPM set = model FBX + textures only
        return n == 'SM_TestAddr.fbx' or n.startswith('T_')
    assert 'SM_TestAddr_Light.fbx' not in [n for n in names if geoagr_archive_filter(n)]    # RED
    vpm = pc.classify_folder(names)['vpm']                                                     # GREEN (export.zip 0.9)
    assert vpm['TestAddr']['light'] == 'SM_TestAddr_Light.fbx' if 'TestAddr' in vpm else \
        vpm['SM_TestAddr'.split('SM_', 1)[1]]['light'] == 'SM_TestAddr_Light.fbx'


def test_root_rules(tmp_path):
    lights, helpers, opts = light_scene(tmp_path, root='Root_TestAddr')       # GeoAGR btnCreateRoot name
    plan = lc.export_plan(lights, helpers, opts)
    assert plan['stem'] == 'SM_TestAddr' and 'light_root_name' in {c for c, _ in plan['findings'][10]}
    two = helpers + [{'handle': 11, 'name': 'SM_Other_Root', 'cls': 'Dummy', 'parent': None, 'hidden': False,
                      'frozen': False}]
    moved = [dict(lights[0], parent=11)] + lights[1:]
    plan2 = lc.export_plan(moved, two, opts)
    assert plan2['root'] is None and plan2['blockers']
    plan3 = lc.export_plan(moved, two, dict(opts, root='SM_Other_Root'))
    assert plan3['root']['handle'] == 11 and {c for c, _ in plan3['findings'][21]} == {'light_outside_root'}
    orphan = [dict(r, parent=None) for r in lights]
    assert lc.export_plan(orphan, [], opts)['blockers']
    with pytest.raises(ValueError):
        lc.export_plan([], helpers, opts)
    with pytest.raises(ValueError):
        lc.export_options({'stem': 'bad name'})
    with pytest.raises(ValueError):
        lc.export_options({'overwrite': True})


def test_written_scene_passes_the_qa_package_light_rules(tmp_path):
    sys.path.insert(0, str(ROOT / 'src'))
    sys.path.insert(0, str(ROOT / 'tools' / 'qa'))
    vp = pytest.importorskip('validate_package')
    lights, helpers, opts = light_scene(tmp_path)
    lights = [r for r in lights if r['cls'] != 'Free_Light']                  # Photometric is not a VPM type
    plan = lc.export_plan(lights, helpers, opts)
    data = fbx_scene([(1, 'SM_TestAddr_Root', 'Null', 0, None, (0, 0, 0))] +
                     [(100 + i, r['name'], 'Light', 1, 2 if r['kind'] == 'spot' else 0, (0, 0, 0))
                      for i, r in enumerate(plan['lights'])])
    out = vp.light_findings('SM_TestAddr_Light.fbx', data, 'SM_TestAddr', [])
    assert [f.status for f in out] == ['pass']
    assert lc.fbx_lights(data)['version'] == 7400


def test_unreadable_fbx_is_an_error():
    with pytest.raises(ValueError):
        lc.fbx_lights(b'not an fbx')
    with pytest.raises(ValueError):
        lc.fbx_lights(fbx_scene([(1, 'R', 'Null', 0, None, (0, 0, 0))])[:-40])


# ==== pack.deliver ================================================================================================
def rep(status, objects=()):
    return {'schema': 1, 'tool': 't', 'status': status, 'objects': list(objects), 'plan': {}}


def test_deliver_options():
    o = dc.deliver_options(None)
    assert o['skip'] == {} and o['folder'] is None
    with pytest.raises(ValueError):
        dc.deliver_options({'skip': {'qa.omk_te': ''}})
    with pytest.raises(ValueError):
        dc.deliver_options({'skip': {'nope': 'x'}})
    with pytest.raises(ValueError):
        dc.deliver_options({'force': True})
    assert dc.deliver_options({'skip': {'qa.omk_te': 'ветка T не слита'}})['skip']


def test_blockers_and_step_results():
    res = [dc.step_result('qa.names', rep('pass')),
           dc.step_result('qa.tris', rep('fail', [{'handle': 5, 'name': 'SM_A', 'findings': [
               {'code': 'tri_limit', 'ids': [], 'detail': '200k'}]}])),
           dc.step_result('qa.omk_te', rep('not_implemented')),
           dc.step_result('ucx.gap', error=RuntimeError('boom')),
           dc.step_result('qa.sintez', skipped='нет таблицы SINTEZ'),
           dc.step_result('export.zip', planned='после FBX')]
    block = dc.blockers(res)
    assert [b.split(':')[0] for b in block] == ['qa.tris', 'qa.omk_te', 'ucx.gap']
    assert 'SM_A: tri_limit 200k' in block[0]
    assert dc.step_result('qa.names', {'status': 'pass?'})['status'] == 'error'   # a claimed pass is not trusted
    report = dc.deliver_report(ec, 'preview', res, [], block, dc.deliver_options(None), state_hash='s')
    assert report['status'] == 'fail' and report['plan']['skipped'][0]['item'] == 'qa.sintez'
    clean = dc.deliver_report(ec, 'preview', res[:1], [], [], dc.deliver_options(None), state_hash='s')
    assert clean['status'] == 'pass'


def test_merge_objects_prefixes_codes_and_keeps_one_entry_per_handle():
    objs = dc.merge_objects([('ucx.gap', rep('fail', [{'handle': 7, 'name': 'UCX_A_01', 'findings': [
        {'code': 'ucx_touch', 'ids': [], 'detail': 'x'}]}])), ('qa.names', rep('pass', [
            {'handle': 7, 'name': 'UCX_A_01', 'findings': []}, {'handle': 8, 'name': 'SM_A', 'findings': []}])),
        ('export.zip', rep('pass', [{'handle': 0, 'name': 'zip', 'findings': []}]))])
    assert [o['handle'] for o in objs] == [7, 8]
    assert [f['code'] for f in objs[0]['findings']] == ['ucx.gap/ucx_touch']


def _passport():
    stages = [{'id': i, 'status': 'done' if i < 9 else 'todo'} for i in range(10)] + [{'id': 'agent',
                                                                                         'status': 'todo'}]
    return {'schema': 1, 'project_id': 'KPP1', 'source': {'path': 'x.max', 'level': 'A', 'class': 'max'},
            'normalization': {'units': 'm', 'up_axis': 'Z', 'scale': 1.0, 'origin_m': [0, 0, 0]},
            'stages': stages, 'parts': [], 'openings': [], 'materials': [], 'journal': {'path': 'j.jsonl'},
            'agent_requests': [], 'questions': []}


def test_stage_9_into_the_passport():
    import datetime
    t0 = datetime.datetime(2026, 11, 6, 10, 0, tzinfo=datetime.timezone.utc)
    t1 = t0 + datetime.timedelta(seconds=42)
    done = dc.stage_entry('done', [], t0, t1)
    assert done == {'id': 9, 'status': 'done', 'started': '2026-11-06T10:00:00Z', 'finished': '2026-11-06T10:00:42Z',
                    'seconds': 42.0, 'blockers': []}
    with pytest.raises(ValueError):
        dc.stage_entry('done', ['x'], t0, t1)
    with pytest.raises(ValueError):
        dc.stage_entry('blocked', [], t0, t1)
    p = _passport()
    out = dc.passport_with_stage(p, dc.stage_entry('blocked', ['qa.omk_te: нет'], t0, t1))
    assert out['stages'][9]['status'] == 'blocked' and p['stages'][9]['status'] == 'todo'
    jsonschema = pytest.importorskip('jsonschema')
    schema = json.loads((ROOT / 'schemas/ProjectPassport.schema.json').read_text(encoding='utf-8'))
    jsonschema.validate(out, schema)
    with pytest.raises(ValueError):
        dc.passport_with_stage(dict(p, stages=p['stages'][:5]), done)
    with pytest.raises(ValueError):
        dc.passport_with_stage(dict(p, schema=2), done)


def test_run_folder_is_always_new(tmp_path):
    a = dc.run_folder(tmp_path, '20261106_120000')
    b = dc.run_folder(tmp_path, '20261106_120000')
    assert Path(a).name == 'Сдача_20261106_120000' and Path(b).name == 'Сдача_20261106_120000_2'


def _deliver_max(monkeypatch):
    dm = _load(PKG / 'deliver_max.py', 'agr_tools_deliver_max_t')
    return dm


def test_glue_previews_turn_errors_and_stubs_into_blockers(monkeypatch, tmp_path):
    dm = _deliver_max(monkeypatch)
    calls = []

    def ok(*a, **k):
        calls.append((a, k))
        return rep('pass')

    def edits_100(tool, mode, preview=None, nodes=None, options=None, actor='panel'):
        calls.append((tool, mode, options))
        if tool == 'qa.omk_te':
            return rep('not_implemented')
        if tool == 'light.export':
            r = rep('pass')
            r['plan'] = {'stem': 'SM_TestAddr'}
            return r
        return rep('pass')

    def boom(*a, **k):
        raise RuntimeError('no SINTEZ table')

    agr = types.SimpleNamespace(checks_050=ok, checks_070=ok, edits_100=edits_100,
                                edits_090=lambda tool, *a, **k: boom() if tool == 'qa.sintez' else rep('pass'),
                                export_preview=lambda nodes=None, target=None: (calls.append(('export', target))
                                                                                or rep('pass')))
    ctx = types.SimpleNamespace(core=dc, agr=agr)
    opts = dc.deliver_options({'folder': str(tmp_path)})
    results, reports = dm._previews(ctx, opts, [], str(tmp_path))
    status = {r['id']: r['status'] for r in results}
    assert status['qa.omk_te'] == 'not_implemented' and status['qa.sintez'] == 'error'
    assert status['export.zip'] == 'planned' and status['export.checked'] == 'pass'
    assert ('export', str(tmp_path / 'SM_TestAddr.fbx')) in calls                  # stem from the light root
    assert [b.split(':')[0] for b in dc.blockers(results)] == ['qa.sintez', 'qa.omk_te']
    skipped = dc.deliver_options({'folder': str(tmp_path), 'skip': {'qa.omk_te': 'ветка T', 'qa.sintez': 'нет'}})
    results, _ = dm._previews(ctx, skipped, [], str(tmp_path))
    assert dc.blockers(results) == []


# ==== static rules (IMPL.md) ======================================================================================
MINE = ('deliver_core.py', 'deliver_max.py', 'ucx10_core.py', 'ucx10_max.py', 'light_core.py', 'light_max.py')


@pytest.mark.parametrize('name', MINE)
def test_no_decode_value_no_clear_undo_no_globals(name):
    src = (PKG / name).read_text(encoding='utf-8')
    code = '\n'.join(l for l in src.splitlines() if not l.lstrip().startswith('#'))
    tree = ast.parse(src)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert 'decodeValue' not in calls and 'clearUndoBuffer' not in code
    assert 'global ' not in ''.join(n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)
                                    and isinstance(n.value, str) and 'fn ' in n.value)  # no MAXScript globals


@pytest.mark.parametrize('name', ('deliver_core.py', 'ucx10_core.py', 'light_core.py'))
def test_cores_are_stdlib_only(name):
    tree = ast.parse((PKG / name).read_text(encoding='utf-8'))
    mods = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert 'pymxs' not in mods and mods <= set(sys.stdlib_module_names)


def test_every_step_is_registered_in_its_dispatcher():
    """Native job 20261106-045201-57241d42: export.zip was sent to edits_090 (it is a 0.8 row of edits_080)."""
    rt = _load(PKG / 'runtime.py', 'agr_runtime_deliver_t')
    table = {'edit080': rt.EDITS_080, 'edit090': rt.EDITS_090, 'edit100': rt.EDITS_100}
    for step, _phase, kind in dc.STEPS:
        if kind in table:
            assert step in table[kind], (step, kind)
    assert 'pack.deliver' in rt.EDITS_100 and 'pack.deliver' not in rt.READ_100
    src = (PKG / 'deliver_max.py').read_text(encoding='utf-8')
    assert "edits_080('export.zip'" in src and "edits_090('export.zip'" not in src
