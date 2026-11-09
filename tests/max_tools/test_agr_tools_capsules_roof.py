"""new-case: #1024 branch K — body.capsules (1.0.12) and body.roof (1.0.13): cores, glue contract, acceptance.

Regression pairs: every defect measured in the lab (L10 docs/experiments/body.capsules.md, L13 body.roof.md) is
RED on a behaviour model of the source chain (Max: createShape -> cap -> Edit_Poly outline -> Shell / move) and
GREEN on capsule_core / roof_core. The models below encode only the lab measurements, not Max code.
"""
import importlib.util
import json
from pathlib import Path
import sys
import time
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
AGR = ROOT / 'adapters' / 'max' / 'agr_tools'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cc = _load(AGR / 'capsule_core.py', 'k_capsule_core')
rc = _load(AGR / 'roof_core.py', 'k_roof_core')
ec = _load(AGR / 'edit_core.py', 'k_edit_core')
kb = _load(ROOT / 'test-polygon' / 'stations' / 'K_build.py', 'k_build')

BADIK8 = [{'wall': 0, 's': [1.5, 2.7], 'z': [0.9, 2.4]}, {'wall': 0, 's': [4.0, 5.2], 'z': [0.9, 2.4]},
          {'wall': 1, 's': [2.0, 3.2], 'z': [0.9, 2.4]}, {'wall': 2, 's': [3.0, 4.0], 'z': [0.15, 2.3]},
          {'wall': 3, 's': [2.0, 3.2], 'z': [0.9, 2.4]}, {'corner': 0, 'a': 1.5, 'b': 1.2, 'z': [3.9, 5.4]},
          {'corner': 2, 'a': 1.2, 'b': 1.5, 'z': [3.9, 5.4]}, {'wall': 0, 's': [2.0, 3.2], 'z': [3.9, 5.4]}]
REVEAL = 0.25


@pytest.fixture(scope='module')
def badik():
    return kb.badik_mesh(8.0, 6.0, 7.0, REVEAL, BADIK8)


@pytest.fixture(scope='module')
def capsules(badik):
    return cc.plan([{'handle': 7, 'name': 'BODY_Brick_001', 'openings': kb.synthetic_openings(badik)}])


# ---- behaviour models of the source chain (lab measurements only) ---------------------------------------------
def source_capsule(opening, m_per_unit=1.0, outline=0.1, depth=1.0, rim=0.05):
    """L10, Max 2024 chain: createShape -> convertToPoly cap -> Edit_Poly outline -> Shell.
    * corner, arch (m), non-planar border: the cap is EMPTY (0 faces) without an error;
    * outline and Shell take system units: metre numbers in a cm scene give 1 mm / 10 mm;
    * the cap normal looks into the building, Shell keeps it: 100 % of the capsule faces look OUTWARDS;
    * the rim stands on the frame middle (+50 mm) with the 100 mm outline in front of the reveal end: the
      front cap crosses the 4 reveals of its own opening."""
    loop = opening['border']
    n = cc._unit(cc.newell(loop))
    c = cc.centroid(loop)
    ds = [cc._dot(cc._sub(p, c), n) for p in loop]
    u = cc._unit(cc._cross([0.0, 0.0, 1.0], n))
    v = cc._cross(n, u)
    corners = len(cc.clean2([[cc._dot(cc._sub(p, c), u), cc._dot(cc._sub(p, c), v)] for p in loop]))
    if opening.get('corner') or max(ds) - min(ds) > 0.001 or corners > 4:  # corner / non-planar / arch
        return {'faces': 0, 'error': None}
    return {'faces': 6, 'error': None, 'outline_m': outline * m_per_unit, 'depth_m': (depth + rim) * m_per_unit,
            'normals_inward': 0.0, 'reveals_crossed': 4}


def source_roof_c2_flat(loop_pts, lift=0.02):
    """L13, C2 as first written: a horizontal slab at the mean loop height (+ lift) - wrong on a slope."""
    zm = sum(p[2] for p in loop_pts) / len(loop_pts) + lift
    return [[p[0], p[1], zm] for p in loop_pts]


def _rim_plane_dist(row, opening):
    """Signed distance of the rim (open loop) from the border plane along the wall normal (outwards)."""
    z = opening['frame']['z']
    b0 = opening['border'][0]
    rim = {i for f in row['caps'] for i in f}
    return [cc._dot(cc._sub(row['verts'][i], b0), z) for i in rim]


# ==== body.capsules: regressions RED -> GREEN ====================================================================
def test_red_green_corner_cap_empty(badik):
    corner = [o for o in badik['openings'] if o['corner']]
    assert len(corner) == 2
    assert all(source_capsule(o)['faces'] == 0 for o in corner)          # RED: empty, no error
    for o in corner:
        row = cc.capsule(o, cc.options())                                 # GREEN: one L-capsule
        assert row['kind'] == 'corner' and len(row['faces']) >= 8


def test_red_green_arch_cap_empty():
    b = kb.badik_mesh(8.0, 6.0, 7.0, REVEAL, [{'wall': 0, 's': [1.5, 2.7], 'z': [0.9, 2.9], 'arch': 16}])
    op, = kb.synthetic_openings(b)
    assert source_capsule(op)['faces'] == 0                               # RED
    row = cc.capsule(op, cc.options())                                    # GREEN: offset of the round head
    chk = cc.check_capsule(row)
    assert chk == {'open_edges': len(row['rim']), 'open_off_rim': 0, 'closed_open_edges': 0, 'bad_edges': 0,
                   'inward': True}
    assert not cc.mesh_hits(row, b, 1e-4)
    assert abs(row['size_m'][0] - 1.4) < 0.001 and abs(row['size_m'][1] - 2.2) < 0.002


@pytest.mark.parametrize('bump,verdict', [(0.05, 'border_nonplanar'), (0.02, 'border_nonplanar'), (0.003, None)])
def test_red_green_nonplanar_border(bump, verdict):
    b = kb.badik_mesh(8.0, 6.0, 7.0, REVEAL, [{'wall': 0, 's': [1.5, 2.7], 'z': [0.9, 2.4], 'bump': bump}])
    op, = kb.synthetic_openings(b)
    if bump > 0.01:
        assert source_capsule(op)['faces'] == 0                           # RED: empty object, no error
    p = cc.plan([{'handle': 1, 'name': 'B', 'openings': [op]}])
    if verdict:
        assert not p['rows'] and p['findings'][1][0][0] == verdict and p['ambiguous']  # GREEN: ambiguous
    else:
        assert len(p['rows']) == 1 and not p['ambiguous']


def test_red_green_units_cm_scene(badik):
    op = badik['openings'][0]
    src = source_capsule(op, m_per_unit=0.01)                            # metre numbers in a cm scene
    assert abs(src['outline_m'] - 0.001) < 1e-9                           # RED: 1 mm
    row = cc.capsule(op, cc.options())                                    # GREEN: core in metres ...
    assert abs(row['outline_m'] - 0.1) < 1e-12
    calls = []
    fake = types.SimpleNamespace(
        Point3=lambda x, y, z: calls.append((x, y, z)) or (x, y, z), Array=lambda *a: list(a),
        mesh=lambda vertices, faces: types.SimpleNamespace(name=''), setEdgeVis=lambda *a: None,
        update=lambda n: None, convertTo=lambda n, c: None, Editable_Poly=object,
        getNodeByName=lambda n: None, uniqueName=lambda n: n)
    cm = _glue_module()
    cm._rt = lambda: fake
    cm.make_poly(cc, 'CAPSULE_x', row['verts'], row['faces'], 0.01)       # ... the glue divides by m/unit
    xs = [c[0] for c in calls[:len(row['verts'])]]
    assert abs((max(xs) - min(xs)) / 100.0 - row['size_m'][0]) < 1e-9


def test_red_green_normals_inward(capsules):
    assert source_capsule({'border': [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]]})['normals_inward'] == 0.0  # RED
    for r in capsules['rows']:                                           # GREEN: 100 % inwards
        assert cc.check_capsule(r)['inward']


def test_red_green_rim_on_frame_middle_crosses_no_reveal(badik, capsules):
    assert source_capsule(badik['openings'][0])['reveals_crossed'] == 4    # RED (lab: all 13 openings)
    for r in capsules['rows']:                                           # GREEN: rim 100 mm wider, 0 hits
        assert not cc.mesh_hits(r, badik, 1e-4), r['name']


# ==== body.capsules: acceptance #1024 1.0.12 + owner answer 06.11 ==================================================
def test_badik_eight_openings_eight_capsules(capsules):
    assert len(capsules['rows']) == 8 and not capsules['ambiguous'] and not capsules['skipped']
    assert [r['kind'] for r in capsules['rows']].count('corner') == 2
    assert all(r['name'].startswith('CAPSULE_BODY_Brick_001_') for r in capsules['rows'])
    assert cc.ROLE == 'capsule' and cc.LAYER.startswith('CAPSULE_')


def test_capsule_open_only_at_rim(capsules):
    for r in capsules['rows']:
        chk = cc.check_capsule(r)
        assert chk['open_off_rim'] == 0 and chk['closed_open_edges'] == 0 and chk['bad_edges'] == 0, r['name']
        assert chk['open_edges'] == (4 if r['kind'] == 'planar' else 6)


def test_capsule_depth_rim_outline(badik, capsules):
    ops = {o['id']: o for o in kb.synthetic_openings(badik)}
    for r in capsules['rows']:
        op = ops[r['opening']]
        z = op['frame']['z']
        if r['kind'] == 'planar':
            d = [cc._dot(cc._sub(v, op['border'][0]), z) for v in r['verts']]
            assert abs(min(d) + 1.0) < 0.01                               # depth 1.0 +- 0.01 m from the border plane
            rim = _rim_plane_dist(r, op)
            assert all(abs(x - 0.05) < 0.002 for x in rim)                # rim on the frame middle +- 2 mm
            w = max(cc._dot(p, op['frame']['x']) for p in op['border']) - min(cc._dot(p, op['frame']['x'])
                                                                           for p in op['border'])
            h = max(p[2] for p in op['border']) - min(p[2] for p in op['border'])
            assert abs(r['size_m'][0] - w - 0.2) < 0.001 or abs(r['size_m'][1] - w - 0.2) < 0.001
            assert abs(r['size_m'][0] - h - 0.2) < 0.001 or abs(r['size_m'][1] - h - 0.2) < 0.001
        else:
            assert abs(r['height_m'] - (1.5 + 0.2)) < 0.001               # outline 100 mm above and below


def test_corner_capsule_two_branches_parallel_to_walls(badik, capsules):
    for r in [x for x in capsules['rows'] if x['kind'] == 'corner']:
        e1, e2 = r['axes']
        assert abs(e1[0] * e2[0] + e1[1] * e2[1]) < 1e-9
        for ax in (e1, e2):                                              # each branch along a world wall axis
            assert min(abs(abs(ax[0]) - 1.0), abs(abs(ax[1]) - 1.0)) < 1e-9
        # every vertical side face is parallel to one of the two walls
        for f in r['faces']:
            n = cc.face_normal(r['verts'], f)
            if abs(n[2]) < 1e-9:
                assert max(abs(n[0] * e1[0] + n[1] * e1[1]), abs(n[0] * e2[0] + n[1] * e2[1])) > 1 - 1e-9


def test_capsules_do_not_cross_each_other(capsules):
    rows = capsules['rows']
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            assert not cc.mesh_hits(rows[i], rows[j], 1e-4)


def test_close_openings_overlap_is_ambiguous():
    b = kb.badik_mesh(8.0, 6.0, 7.0, REVEAL, [{'wall': 0, 's': [1.0, 2.0], 'z': [0.9, 2.4]},
                                               {'wall': 0, 's': [2.1, 3.1], 'z': [0.9, 2.4]}])
    p = cc.plan([{'handle': 1, 'name': 'B', 'openings': kb.synthetic_openings(b)}])
    assert not p['rows'] and {c for c, _ in p['findings'][1]} == {'capsules_overlap'}


def test_cm_and_m_give_the_same_metric_capsules(badik):
    # the core sees metres from host.mesh in both scenes: scale the input by 1 (m) and check idempotence of plan
    a = cc.plan([{'handle': 1, 'name': 'B', 'openings': badik['openings']}])
    b = cc.plan([{'handle': 1, 'name': 'B', 'openings': json.loads(json.dumps(badik['openings']))}])
    assert [r['verts'] for r in a['rows']] == [r['verts'] for r in b['rows']]


def test_refusals_never_empty_objects():
    ops = [{'id': 1, 'border': [[0, 0, 0], [1, 0, 0]], 'frame': {'z': [0, -1, 0]}, 'corner': False},
           {'id': 2, 'border': [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], 'frame': {}, 'corner': False},
           {'id': 3, 'border': [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], 'frame': {'z': [1, 0, 0]},
            'corner': False},
           {'id': 4, 'border': [[0, 0.04, 0], [1, 0.04, 0], [1, 0.04, 1], [0, 0.04, 1]], 'frame': {'z': [0, -1, 0]},
            'corner': False, 'depth': 0.04}]
    p = cc.plan([{'handle': 1, 'name': 'B', 'openings': ops}])
    assert not p['rows']
    assert [c for c, _ in p['findings'][1]] == ['border_short', 'frame_missing', 'border_not_in_wall',
                                                'reveal_too_shallow']
    q = cc.plan([{'handle': 1, 'name': 'B', 'openings': []}])
    assert q['findings'][1][0][0] == 'no_openings' and q['skipped']
    with pytest.raises(ValueError, match='empty target set'):
        cc.plan([])


def test_rim_option_border_plane_and_options_validation(badik):
    op = badik['openings'][0]
    row = cc.capsule(op, cc.options({'rim': 'border_plane'}))
    assert all(abs(x) < 1e-9 for x in _rim_plane_dist(row, op))
    for bad in ({'outline_m': 0}, {'rim': 'x'}, {'foo': 1}, {'interior_depth_m': float('nan')}):
        with pytest.raises(ValueError):
            cc.options(bad)


def test_two_hundred_openings_under_twenty_seconds():
    ops = []
    for k in range(4):
        for i in range(10):
            for j in range(5):
                ops.append({'wall': k, 's': [2.5 + i * 2.5, 3.5 + i * 2.5], 'z': [0.9 + j * 3.0, 2.4 + j * 3.0]})
    b = kb.badik_mesh(30.0, 30.0, 16.0, REVEAL, ops)
    t = time.time()
    p = cc.plan([{'handle': 1, 'name': 'B', 'openings': b['openings']}])
    dt = time.time() - t
    assert len(p['rows']) == 200 and not p['ambiguous']
    assert dt < 20.0, dt


# ==== body.roof: regressions RED -> GREEN ==========================================================================
def _parapet(outline, **kw):
    return kb.parapet_mesh(outline, 9.0, 0.9, 0.3, **kw)


RECT = [[0, 0], [20, 0], [20, 12], [0, 12]]
LSHAPE = [[0, 0], [20, 0], [20, 6], [8, 6], [8, 12], [0, 12]]
USHAPE = [[0, 0], [20, 0], [20, 12], [14, 12], [14, 5], [6, 5], [6, 12], [0, 12]]


def test_red_green_slope_slab_follows_the_loop_plane():
    m = _parapet(RECT, slope_deg=3.0)
    loops, _ = rc.boundary_loops(m['faces'])
    loop = max(loops, key=len) if loops else None
    pts = [m['verts'][i] for i in loop]
    flat = source_roof_c2_flat(pts)
    err = max(abs(f[2] - p[2]) for f, p in zip(flat, pts))
    assert err > 0.3                                                       # RED: 0.33 m here (lab: 544 mm)
    p = rc.plan([{'handle': 1, 'name': 'P', 'mesh': m}])
    s, = p['rows']                                                         # GREEN: plane of the loop + lift
    n = s['normal']
    c = cc.centroid(pts)
    assert max(abs(cc._dot(cc._sub(v, c), n) - 0.005) for v in s['verts']) < 1e-6
    assert abs(s['slope_deg'] - 3.0) < 0.01


def test_red_green_default_lift_is_five_mm():
    assert rc.DEFAULTS['lift_m'] == 0.005 and rc.DEFAULTS['inset_m'] == 0.02      # owner 06.11 (issue said 20)


def test_red_green_steep_roof_goes_to_the_agent():
    p = rc.plan([{'handle': 1, 'name': 'P', 'mesh': _parapet(RECT, slope_deg=15.0)}])
    assert not p['rows'] and p['findings'][1][0][0] == 'roof_steep' and p['ambiguous']
    req, = p['agent_requests']
    assert req['stage'] == 4 and req['tool'] == 'body.roof' and req['handle'] == 1


# ==== body.roof: acceptance #1024 1.0.13 ===========================================================================
def _side_insets(slab, outline):
    """Distance of every slab edge from the parallel contour edge (plan), metres."""
    out = []
    sv = [[v[0], v[1]] for v in slab['verts']]
    for i in range(len(sv)):
        a, b = sv[i], sv[(i + 1) % len(sv)]
        mid = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
        out.append(cc.poly_dist(mid, outline))
    return out


@pytest.mark.parametrize('outline', [RECT, LSHAPE, USHAPE], ids=['rect', 'L', 'U'])
@pytest.mark.parametrize('kw', [{}, {'terrace': True}, {'heights': 'mixed'}], ids=['plain', 'terrace', 'heights'])
def test_roof_flat_cases(outline, kw):
    if kw.get('heights'):
        kw = {'heights': [0.9 + 0.3 * (i % 3) for i in range(len(outline))]}
    p = rc.plan([{'handle': 1, 'name': 'P', 'mesh': _parapet(outline, **kw)}])
    s, = p['rows']
    assert not p['ambiguous'] and not p['findings'][1]
    assert all(abs(v[2] - 9.005) < 0.0005 for v in s['verts'])            # level + 5 mm +- 0.5 mm
    assert all(abs(d - 0.02) < 0.001 for d in _side_insets(s, outline))   # inset 20 +- 1 mm per side
    assert s['gaps'] == 0 and not s['outside']                            # 0 gaps, inside the outer line
    assert cc.face_normal(s['verts'], s['faces'][0])[2] > 0.999           # normal up
    assert len(s['faces']) == 1 and s['name'] == 'ROOF_P_001'


def test_roof_bottom_of_a_box_is_not_a_rim(badik):
    p = rc.plan([{'handle': 1, 'name': 'B', 'mesh': badik}])
    assert not p['rows'] and p['findings'][1][0][0] == 'no_roof_loop' and p['skipped']


def test_roof_options():
    assert rc.options({'lift_m': 0.02})['lift_m'] == 0.02
    for bad in ({'inset_m': 0}, {'x': 1}, {'lift_m': -1}):
        with pytest.raises(ValueError):
            rc.options(bad)
    with pytest.raises(ValueError, match='empty target set'):
        rc.plan([])


# ==== glue contract (fake pymxs) ===================================================================================
def _glue_module():
    return _load(AGR / 'capsule_max.py', 'k_capsule_max')


class _Node:
    def __init__(self, h, name):
        self.h, self.name = h, name


def _fake_ctx(meshes, options=None):
    nodes = [_Node(h, name) for h, name in meshes]
    store = {n.h: m for n, (_, m) in zip(nodes, meshes.items())} if isinstance(meshes, dict) else None
    return nodes, store


def _ctx(core, bodies, options=None):
    """bodies: [(handle, name, mesh)] -> (ctx, nodes, fake rt)."""
    nodes = [_Node(h, n) for h, n, _ in bodies]
    mesh = {h: m for h, _, m in bodies}
    rt = types.SimpleNamespace(selection=nodes, isValidNode=lambda n: True, canConvertTo=lambda n, c: True,
                               TriMeshGeometry=object, getHandleByAnim=lambda n: n.h,
                               getAnimByHandle=lambda h: next(n for n in nodes if n.h == h))
    host = types.SimpleNamespace(refs=lambda ns: [{'host': 'offline', 'doc': 'x', 'handle': n.h, 'name': n.name}
                                                  for n in ns],
                                 mesh=lambda ref: dict(mesh[ref['handle']], ref=ref), m_per_unit=lambda: 0.01)
    emax = types.SimpleNamespace(snapshot=lambda ns: [{'handle': n.h, 'name': n.name} for n in ns])
    ctx = types.SimpleNamespace(edit=ec, core=core, emax=emax, host=host, options=dict(options or {}))
    return ctx, nodes, rt


def test_glue_capsules_preview_report(badik, monkeypatch):
    cm = _glue_module()
    ctx, nodes, rt = _ctx(cc, [(11, 'BODY_Brick_001', badik)])
    cm._rt = lambda: rt
    standin = types.SimpleNamespace(find_openings=lambda mesh, opts: kb.synthetic_openings(mesh))
    monkeypatch.setitem(sys.modules, cm.OPENINGS_STANDIN, standin)
    r = cm.body_capsules(ctx, 'preview', None, None)
    ec.validate_report(r)
    assert r['status'] == 'pass' and len(r['plan']['capsules']) == 8 and r['plan']['handles'] == [11]
    assert r['plan']['options']['outline_m'] == 0.1 and r['plan']['role'] == 'capsule'
    ec.check_preview('body.capsules', json.loads(json.dumps(r)))
    rt.selection = []
    with pytest.raises(ValueError, match='empty target set'):
        cm.body_capsules(ctx, 'preview', None, None)


def test_glue_capsules_without_branch_j_is_a_clear_error(badik, monkeypatch):
    cm = _glue_module()
    ctx, nodes, rt = _ctx(cc, [(11, 'BODY_Brick_001', badik)])
    cm._rt = lambda: rt
    monkeypatch.delitem(sys.modules, cm.OPENINGS_STANDIN, raising=False)
    oc = (AGR / 'openings_core.py').read_text(encoding='utf-8')
    if 'raise NotImplementedError' not in oc:
        pytest.skip('openings_core implemented (branch J merged)')
    with pytest.raises(ValueError, match='branch J'):
        cm.body_capsules(ctx, 'preview', None, None)


def test_glue_roof_preview_report():
    rm = _load(AGR / 'roof_max.py', 'k_roof_max')
    ok, steep = _parapet(LSHAPE), _parapet(RECT, slope_deg=15.0)
    ctx, nodes, rt = _ctx(rc, [(21, 'PARAPET_A', ok), (22, 'PARAPET_B', steep)])
    cm = _glue_module()
    cm._rt = lambda: rt
    rm._rt = lambda: rt
    rm._glue = lambda: cm
    r = rm.body_roof(ctx, 'preview', nodes, None)
    ec.validate_report(r)
    assert r['status'] == 'fail' and [s['name'] for s in r['plan']['slabs']] == ['ROOF_PARAPET_A_001']
    assert r['objects'][1]['findings'][0]['code'] == 'roof_steep' and len(r['plan']['agent_requests']) == 1


def test_runtime_registry_points_at_the_glue():
    src = (AGR / 'runtime.py').read_text(encoding='utf-8')
    assert "'body.capsules': ('capsule_core.py', 'body_capsules')" in src
    assert "'body.roof': ('roof_core.py', 'body_roof')" in src
    assert hasattr(_glue_module(), 'body_capsules')
    assert hasattr(_load(AGR / 'roof_max.py', 'k_roof_max2'), 'body_roof')
