"""new-case: #1024 branch G native run in locked batch Max 2024 on DISPOSABLE synthetic scenes: body.prepare (1.0.4),
model.attach_by_material (1.0.5), model.move_apart (1.0.6) and the live polygon rows of their stations.

Run via the lab DCC runner (script_in_place). AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP,
AGR_POLYGON_CATALOG the catalog with fragments (polygon_core.py --catalog, written before the job).
Installs the MZP into OUT (no user folders touched). Acceptance of the lab reports L14
(docs/experiments/model.attach_by_material.md, model.move_apart.md) and #1024 1.0.4. Nothing is saved.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]
    print('AGR_G check', name, 'error' if name in summary['errors'] else 'ok')


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
# The batch runner executes this whole script inside ONE outer undo hold: `max undo` would then roll back the
# scene set-up too (job 20261106-044415-f3028608: 201 -> 0 objects). Close it so each apply is its own record,
# build the test scenes under undo(False), and re-open a hold at the end for the wrapper.
OUTER_HOLD = bool(rt.theHold.Holding())
if OUTER_HOLD:
    rt.theHold.Accept('AGR branch G native: set-up')
summary['outer_hold_at_start'] = OUTER_HOLD
GLOBALS_BEFORE = set(str(x) for x in rt.execute('globalVars.gather()'))


def no_undo(fn, *args):
    import pymxs
    with pymxs.undo(False):
        return fn(*args)


def reset(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def undo():
    rt.execute('max undo')


def k_m():
    return {'meters': 1.0, 'centimeters': 0.01}[str(rt.units.SystemType).lstrip('#').lower()]


def fill_multi(mm, subs, ids):
    rt.execute('(fn f mm subs ids = (for i = 1 to subs.count do (mm.materialList[i] = subs[i]; '
               'mm.materialIDList[i] = ids[i]); ok); f)')(mm, subs, ids)


# ---- model.attach_by_material ----------------------------------------------------------------------------------
def mix_scene(prefix='synthetic_box'):
    """Lab scene `mix` (job 20261106-022928-efe08cb9): 200 boxes 1 m, three materials, 10 Multi/Sub (2 slots, IDs
    7/9), 10 Editable_Mesh, 5 without material, 4 with another material named Mat_A, one child in the selection
    and one child outside it."""
    k = k_m()
    s = 1.0 / k
    a, b, c = (rt.StandardMaterial(name=n) for n in ('Mat_A', 'Mat_B', 'Mat_C'))
    a2, d = rt.StandardMaterial(name='Mat_A'), rt.StandardMaterial(name='Mat_D')
    ms = rt.MultiMaterial(numsubs=2)
    ms.name = 'MS_Two'
    fill_multi(ms, [d, b], [7, 9])
    nodes = []
    for i in range(200):
        n = rt.Box(name='{}_{:04d}'.format(prefix, i), length=s, width=s, height=s,
                   pos=rt.Point3((i % 20) * 2 * s, (i // 20) * 2 * s, 0))
        if i < 10:
            rt.convertTo(n, rt.Editable_Poly)
            rt.polyop.setFaceMatID(n, [1, 3, 5], 7)
            rt.polyop.setFaceMatID(n, [2, 4, 6], 9)
            n.material = ms
        elif i < 15:
            n.name = n.name + '_nomat'
        elif i < 19:
            n.material = a2
        else:
            if i < 29:
                rt.convertTo(n, rt.Editable_Mesh)
            n.material = (a, b, c)[i % 3]
        nodes.append(n)
    nodes[50].parent = nodes[49]
    out = rt.Box(name='outside_child', length=s / 2, width=s / 2, height=s / 2, pos=nodes[60].pos)
    out.parent = nodes[60]
    return nodes, out


def plain_scene(n_boxes):
    k = k_m()
    s = 1.0 / k
    mats = [rt.StandardMaterial(name=n) for n in ('Mat_A', 'Mat_B', 'Mat_C')]
    nodes = []
    for i in range(n_boxes):
        n = rt.Box(name='plain_{:05d}'.format(i), length=s, width=s, height=s,
                   pos=rt.Point3((i % 50) * 2 * s, (i // 50) * 2 * s, 0))
        n.material = mats[i % 3]
        nodes.append(n)
    return nodes


def areas_of(report, key):
    return {(x['name'], x['key']): x['area_m2'] for x in report['plan'][key]}


def attach_case(units, mode):
    reset(units)
    nodes, outside = no_undo(mix_scene)
    names_before = sorted(str(n.name) for n in rt.objects)
    opts = None if mode == 'split' else {'mode': 'one'}
    p = agr.edits_100('model.attach_by_material', 'preview', None, nodes, opts)
    codes = sorted({f['code'] for o in p['objects'] for f in o['findings']})
    t = time.time()
    r = agr.edits_100('model.attach_by_material', 'apply', p)
    secs = round(time.time() - t, 3)
    assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
    before, after = r['plan']['areas_before'], r['plan']['areas_after']
    diffs = [(x['name'], x['area_m2'], y['area_m2']) for x, y in zip(before, after) if abs(x['area_m2'] - y['area_m2']) > 1e-6]
    assert len(before) == len(after) and not diffs, (before, after)
    results = [rt.getNodeByName(x['name']) for x in r['plan']['results']]
    import re
    assert all(re.match(r'^BODY_[A-Za-z0-9]+_\d{3}$', str(n.name)) for n in results), [str(n.name) for n in results]
    assert outside.parent is not None and str(outside.parent.name).startswith('BODY_'), 'outside child not re-parented'
    out = {'units': units, 'mode': mode, 'objects_in': r['plan']['objects_in'], 'objects_out': r['plan']['objects_out'],
           'results': [x['name'] for x in r['plan']['results']], 'preview_codes': codes,
           'warnings': r['plan']['warnings'], 'areas': [(x['name'], x['area_m2']) for x in after],
           'apply_s': secs, 'outside_child_parent': str(outside.parent.name)}
    if mode == 'one':
        res = results[0]
        assert rt.classOf(res.material) == rt.MultiMaterial
        slots = [str(x) for x in res.material.names]
        assert 'No_Material' in slots, slots
        out['slots'] = slots
    else:
        assert any(n.startswith('BODY_NoMaterial_') for n in out['results'])
        assert 'BODY_MatA_001' in out['results'] and 'BODY_MatA_002' in out['results'], out['results']
    undo()
    after_undo = sorted(str(n.name) for n in rt.objects)
    assert after_undo == names_before, ('one undo did not restore', len(after_undo), len(names_before))
    out['undo_restored'] = len(after_undo)
    assert str(rt.getNodeByName('outside_child').parent.name) == 'synthetic_box_0060'
    return out


def attach():
    rows = [attach_case(u, m) for u in ('meters', 'centimeters') for m in ('split', 'one')]
    reset()
    try:
        agr.edits_100('model.attach_by_material', 'preview', None, [], None)
        raise AssertionError('empty selection accepted')
    except ValueError as exc:
        empty = str(exc)
    return {'cases': rows, 'empty_selection': empty}


def attach_speed():
    reset()
    nodes = no_undo(plain_scene, 2000)
    t0 = time.time()
    p = agr.edits_100('model.attach_by_material', 'preview', None, nodes, None)
    t1 = time.time()
    r = agr.edits_100('model.attach_by_material', 'apply', p)
    t2 = time.time()
    assert r['status'] == 'pass' and r['plan']['objects_out'] == 3
    total = round(t2 - t0, 3)
    assert total <= 10.0, total
    return {'boxes': 2000, 'preview_s': round(t1 - t0, 3), 'apply_s': round(t2 - t1, 3), 'total_s': total,
            'areas': [(x['name'], x['area_m2']) for x in r['plan']['areas_after']]}


# ---- model.move_apart ------------------------------------------------------------------------------------------
GAPS_MM = (0, 1, 2, 5, 10, 15, 20, 25)
RANGES = {'main': (0, 2, 3), 'coplanar': (5, 20, 10), 'wide': (0, 20, 10)}


def quad(name, z_m, flip, x_m, mesh=False):
    k = k_m()
    q = rt.Plane(name=name, length=1.0 / k, width=1.0 / k, lengthsegs=1, widthsegs=1, pos=rt.Point3(x_m / k, 0, z_m / k))
    if mesh:
        rt.convertTo(q, rt.Editable_Mesh)
        if flip:
            rt.meshop.flipNormals(q, [1, 2])
    else:
        rt.convertTo(q, rt.Editable_Poly)
        if flip:
            rt.polyop.flipNormals(q, [1])
    return q


def world_verts(n):
    k = k_m()
    if rt.classOf(n.baseObject) == rt.Editable_Poly:
        pts = [rt.polyop.getVert(n, i) for i in range(1, int(rt.polyop.getNumVerts(n)) + 1)]
    else:
        pts = [rt.meshop.getVert(n, i) for i in range(1, int(rt.meshop.getNumVerts(n)) + 1)]
    return [(float(p.x) * k, float(p.y) * k, float(p.z) * k) for p in pts]


def zgap(lo, hi):
    return abs(world_verts(hi)[0][2] - world_verts(lo)[0][2])


def move_case(units, kind, rng):
    reset(units)
    lo_mm, hi_mm, to_mm = RANGES[rng]
    pairs = []
    for i, g in enumerate(GAPS_MM):
        x = i * 3.0
        a = no_undo(quad, 'lo_{}'.format(g), 0.0, kind == 'bi', x)
        b = no_undo(quad, 'hi_{}'.format(g), g / 1000.0, False, x)
        pairs.append((g, a, b))
    nodes = [n for _g, a, b in pairs for n in (a, b)]
    before = {str(n.name): world_verts(n) for n in nodes}
    opts = {'min_mm': lo_mm, 'max_mm': hi_mm, 'to_mm': to_mm}
    p = agr.edits_100('model.move_apart', 'preview', None, nodes, opts)
    r = agr.edits_100('model.move_apart', 'apply', p)
    assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
    table = []
    for g, a, b in pairs:
        got = zgap(a, b) * 1000.0
        lat = max(max(abs(q[0] - v[0]), abs(q[1] - v[1])) for n in (a, b)
                  for v, q in zip(before[str(n.name)], world_verts(n))) * 1000.0
        inside = lo_mm <= g <= hi_mm
        ok = (abs(got - to_mm) <= 0.01 if inside else abs(got - g) <= 1e-6) and lat <= 0.01
        table.append({'gap_mm': g, 'after_mm': round(got, 6), 'lateral_mm': round(lat, 6), 'in_range': inside,
                      'ok': ok})
    assert all(x['ok'] for x in table), table
    return {'units': units, 'kind': kind, 'range': rng, 'to_mm': to_mm, 'counts': r['plan']['counts'], 'table': table}


def move_apart():
    cases = [move_case(u, kd, rg) for u in ('meters', 'centimeters') for kd in ('bi', 'co') for rg in sorted(RANGES)]
    # T08-02: 10 mm in [5, 20] (Move Faces never moved it) and the one-undo exact return; an Editable_Mesh pair
    reset()
    a, b = no_undo(quad, 't08_lo', 0.0, True, 0.0), no_undo(quad, 't08_hi', 0.010, False, 0.0)
    m1 = no_undo(lambda: quad('mesh_lo', 0.0, True, 5.0, mesh=True))
    m2 = no_undo(lambda: quad('mesh_hi', 0.001, False, 5.0, mesh=True))
    nodes = [a, b, m1, m2]
    before = {str(n.name): world_verts(n) for n in nodes}
    p = agr.edits_100('model.move_apart', 'preview', None, nodes, {'min_mm': 0, 'max_mm': 20, 'to_mm': 25})
    agr.edits_100('model.move_apart', 'apply', p)
    t08 = zgap(a, b) * 1000.0
    mesh_gap = zgap(m1, m2) * 1000.0
    assert abs(t08 - 25.0) <= 0.01 and abs(mesh_gap - 25.0) <= 0.01, (t08, mesh_gap)
    undo()
    back = max(abs(q[i] - v[i]) for n in nodes for v, q in zip(before[str(n.name)], world_verts(n)) for i in range(3))
    assert back <= 1e-9, back
    # a primitive and a node with a modifier are skipped with a reason, never collapsed
    prim = rt.Box(name='prim_box')
    mod = quad('with_mod', 0.0, False, 10.0)
    rt.addModifier(mod, rt.Bend())
    p = agr.edits_100('model.move_apart', 'preview', None, [a, b, prim, mod], None)
    skipped = [s['item'] for s in p['plan']['skipped']]
    assert 'prim_box' in skipped and 'with_mod' in skipped, skipped
    assert rt.classOf(prim) == rt.Box and len(list(mod.modifiers)) == 1
    return {'cases': len(cases), 'grid': cases, 't08_02_after_mm': round(t08, 6),
            'mesh_after_mm': round(mesh_gap, 6), 'undo_max_dev_m': back, 'skipped': skipped}


# ---- body.prepare ----------------------------------------------------------------------------------------------
def body_scene(mats, k):
    nodes = []
    for i, m in enumerate(mats):
        n = rt.Box(name='Box{:03d}'.format(i + 1), length=10 / k, width=10 / k, height=10 / k,
                   pos=rt.Point3(i * 12 / k, 0, 0))
        if m:
            n.material = rt.StandardMaterial(name=m)
        nodes.append(n)
    return nodes


def body_prepare():
    out = {}
    for units in ('meters', 'centimeters'):
        reset(units)
        k = k_m()
        mats = ['Кирпич', 'Brick', 'Brick', None, 'Glass_01']
        nodes = no_undo(body_scene, mats, k)
        rt.select(nodes)
        p = agr.edits_100('body.prepare', 'preview', None, nodes, {'levels': [0.0, 3.3, 9.9]})
        assert p['status'] == 'pass', p
        r = agr.edits_100('body.prepare', 'apply', p)
        assert r['status'] == 'pass', r
        roles = [str(rt.getUserProp(n, 'agr_role')) for n in nodes]
        names = [str(n.name) for n in nodes]
        levels = {x: round(float(rt.getNodeByName(x).pos.z) * k, 6) for x in ('LEVEL_L1', 'LEVEL_L2', 'LEVEL_roof')}
        assert roles == ['body'] * 5, roles
        assert names == ['BODY_Kirpich_001', 'BODY_Brick_001', 'BODY_Brick_002', 'BODY_NoMaterial_001',
                         'BODY_Glass01_001'], names
        assert levels == {'LEVEL_L1': 0.0, 'LEVEL_L2': 3.3, 'LEVEL_roof': 9.9}, levels
        assert all(str(n.layer.name) == 'BODY_main' for n in nodes)
        sel = sorted(str(n.name) for n in rt.selection)
        # repeated height -> refused (preview fail with the reason, apply refuses)
        p2 = agr.edits_100('body.prepare', 'preview', None, nodes, {'levels': [3.3005], 'level_names': ['L9']})
        assert p2['status'] == 'fail' and '1 mm' in p2['plan']['ambiguous'][0], p2['plan']['ambiguous']
        try:
            agr.edits_100('body.prepare', 'apply', p2)
            raise AssertionError('repeated height applied')
        except ValueError as exc:
            refused = str(exc)
        try:
            agr.edits_100('body.prepare', 'preview', None, nodes, {'pick': 3})
            raise AssertionError('pickPoint in batch')
        except ValueError as exc:
            pick = str(exc)
        undo()
        restored = [str(n.name) for n in nodes]
        assert restored == ['Box001', 'Box002', 'Box003', 'Box004', 'Box005'], restored
        assert rt.getNodeByName('LEVEL_L1') is None and rt.getUserProp(nodes[0], 'agr_role') is None
        out[units] = {'roles': roles, 'names': names, 'levels': levels, 'selection_after': sel,
                      'refused': refused[:160], 'pick_batch': pick[:120], 'undo_names': restored}
    return out


# ---- live polygon rows of the stations of branch G -------------------------------------------------------------
def polygon():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    import build_scene
    reset()
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    rows = []
    for button in ('body.prepare', 'model.attach_by_material', 'model.move_apart'):
        doc = json.loads((ROOT / 'test-polygon' / 'expected' / (button + '.json')).read_text(encoding='utf-8'))
        assert doc['shipped'], button
        names = [o['name'] for o in doc['objects'] if o['scene'] == 'polygon_all']
        nodes = [rt.getNodeByName(n) for n in names]
        assert all(n is not None for n in nodes), names
        rt.select(nodes)
        try:
            report = agr.edits_100(doc['tool'], 'preview', None, nodes, doc.get('options'))
        except Exception as exc:  # noqa: BLE001
            report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
        mism = core.compare_report(doc['objects'], report)
        got = {o['name']: sorted({f['code'] for f in o['findings']}) for o in report.get('objects') or ()}
        for o in doc['objects']:
            bad = [m for m in mism if m.get('name') == o['name']]
            rows.append({'station': doc.get('station'), 'button': button, 'name': o['name'], 'expect': o['expect'],
                         'codes': o['codes'], 'actual': got.get(o['name']), 'result': 'OK' if not bad else 'НЕ OK',
                         'detail': [m.get('detail') for m in bad]})
        if mism and not any(m.get('name') for m in mism):
            rows.append({'station': doc.get('station'), 'button': button, 'name': '*', 'result': 'НЕ OK',
                         'detail': mism})
    (OUT / 'polygon_rows.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
    assert all(r['result'] == 'OK' for r in rows), rows
    return rows


def globals_unchanged():
    now = set(str(x) for x in rt.execute('globalVars.gather()'))
    new = sorted(now - GLOBALS_BEFORE)
    assert not new, new
    assert not rt.execute('globalVars.isGlobal #dist'), '::dist leaked'
    return {'globals_before': len(GLOBALS_BEFORE), 'new': new}


check('attach_by_material', attach)
check('attach_speed_2000', attach_speed)
check('move_apart', move_apart)
check('body_prepare', body_prepare)
check('globals_unchanged', globals_unchanged)  # before the polygon: its E2 builder declares agr979e2_poly
check('polygon_rows_G', polygon)
if OUTER_HOLD:
    rt.theHold.Begin()
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('AGR_G_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native branch G failed: see summary.json'
