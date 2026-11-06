"""new-case: #1024 branch K native run of body.capsules (1.0.12) and body.roof (1.0.13) in locked batch Max 2024.

Run via the lab DCC runner (script_in_place) on DISPOSABLE scenes; AGR_TEST_OUTPUT names a NEW directory,
AGR_TEST_PACKAGE the built MZP. Installs the MZP into OUT (no user folders touched), then in the real Max Python:
* capsules, metres and centimetres: synthetic badik with 8 openings (2 corner) -> preview pass -> apply: 8
  Editable_Poly capsules, role capsule, layer, placeholder material; read back in metres: only the rim open,
  faces inwards, depth / rim / outline, 0 crossings capsule x body and capsule x capsule, the same metric numbers in
  m and cm; the body unchanged; ONE undo removes all; selection restored; actor mcp cannot apply;
* refusals: non-planar border 50 mm -> ambiguous, no object; 200 openings: preview + apply time;
* roof, metres and centimetres: rect / L / U / terrace / mixed heights / 3 deg -> one slab (one polygon, normal up,
  level + 5 mm, inset 20 mm), 15 deg -> ambiguous + agent request;
* the K polygon stations (frag_k_caps, frag_k_roof) built by the polygon builder and pressed as run_inside_max does.
Until branch J merges openings_core, the openings come from the TEST stand-in K_build.synthetic_openings,
registered under capsule_max.OPENINGS_STANDIN (recorded in summary.json). Nothing is saved.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import traceback
import types

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'openings_source': 'K_build.synthetic_openings (test stand-in until branch J)', 'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t = time.time()
    try:
        summary['checks'][name] = fn()
        summary['checks'][name + '_s'] = round(time.time() - t, 2)
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


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
INST = OUT / 'installed'
kb = load(ROOT / 'test-polygon' / 'stations' / 'K_build.py', 'k_build_native')
cc = load(INST / 'capsule_core.py', 'k_native_capsule_core')
rc = load(INST / 'roof_core.py', 'k_native_roof_core')
host = agr._load_core('host_max.py', 'agr_tools_host_max').MaxHost()
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
STANDIN = load(INST / 'capsule_max.py', 'k_native_capsule_max').OPENINGS_STANDIN
sys.modules[STANDIN] = types.SimpleNamespace(find_openings=lambda mesh, opts: kb.synthetic_openings(mesh))
summary['runtime_version'] = agr.VERSION

BADIK8 = [{'wall': 0, 's': [1.5, 2.7], 'z': [0.9, 2.4]}, {'wall': 0, 's': [4.0, 5.2], 'z': [0.9, 2.4]},
          {'wall': 1, 's': [2.0, 3.2], 'z': [0.9, 2.4]}, {'wall': 2, 's': [3.0, 4.0], 'z': [0.15, 2.3]},
          {'wall': 3, 's': [2.0, 3.2], 'z': [0.9, 2.4]}, {'corner': 0, 'a': 1.5, 'b': 1.2, 'z': [3.9, 5.4]},
          {'corner': 2, 'a': 1.2, 'b': 1.5, 'z': [3.9, 5.4]}, {'wall': 0, 's': [2.0, 3.2], 'z': [3.9, 5.4]}]


def fresh(units):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def readback(node):
    ref, = host.refs([node])
    m = host.mesh(ref)
    # weld by position (snapshotAsMesh keeps the poly verts, but be explicit)
    idx, verts, remap = {}, [], []
    for v in m['verts']:
        key = tuple(round(c, 6) for c in v)
        if key not in idx:
            idx[key] = len(verts)
            verts.append(v)
        remap.append(idx[key])
    faces = [[remap[i] for i in f] for f in m['faces']]
    return {'verts': verts, 'faces': faces}


def capsules_case(units):
    fresh(units)
    data = kb.badik_mesh(8.0, 6.0, 7.0, 0.25, BADIK8)
    body = kb.mesh_node(rt, 'BODY_Brick_001', data)
    rt.select(body)
    before = emax.snapshot([body])
    t = time.time()
    p = agr.edits_100('body.capsules', 'preview')
    t_preview = time.time() - t
    assert p['status'] == 'pass' and len(p['plan']['capsules']) == 8, (p['status'], p['plan']['ambiguous'])
    try:
        agr.edits_100('body.capsules', 'apply', p, actor='mcp')
        raise AssertionError('apply by mcp was not refused')
    except ValueError as exc:
        assert str(exc).startswith('needs_human'), exc
    t = time.time()
    a = agr.edits_100('body.capsules', 'apply', p)
    t_apply = time.time() - t
    assert a['status'] == 'pass' and len(a['objects']) == 8, a['status']
    assert [str(n.name) for n in rt.selection] == ['BODY_Brick_001'], 'selection not restored'
    assert emax.snapshot([body]) == before, 'the body changed'
    caps = [rt.getAnimByHandle(o['handle']) for o in a['objects']]
    plan = cc.plan([{'handle': 1, 'name': 'BODY_Brick_001', 'openings': kb.synthetic_openings(readback(body))}])
    rows = {r['name']: r for r in plan['rows']}
    body_m = readback(body)
    out, metrics = [], {}
    for n in caps:
        name = str(n.name)
        r = rows[name]
        assert str(rt.classOf(n)) == 'Editable_Poly', rt.classOf(n)
        assert host.role(host.refs([n])[0]) == 'capsule'
        assert str(n.layer.name) == cc.LAYER and str(n.material.name) == cc.MATERIAL
        m = readback(n)
        # map the plan caps onto the read-back vertices, close the shell, check winding and openness
        pos = {tuple(round(c, 5) for c in v): i for i, v in enumerate(m['verts'])}
        caps_rb = [[pos[tuple(round(c, 5) for c in r['verts'][i])] for i in f] for f in r['caps']]
        closed = m['faces'] + caps_rb
        opened = cc.open_edges(m['faces'])
        rim = {tuple(sorted((f[i], f[(i + 1) % len(f)]))) for f in caps_rb for i in range(len(f))}
        assert set(opened) <= rim and opened, (name, 'open edges off the rim')
        assert not cc.open_edges(closed) and cc.signed_volume(m['verts'], closed) < 0, (name, 'not inward/closed')
        assert not cc.mesh_hits(m, body_m, 1e-4), (name, 'crosses the body')
        bb = cc.bbox(m['verts'])
        metrics[name] = [round(bb[1][i] - bb[0][i], 4) for i in range(3)]
        out.append(m)
    for i in range(len(out)):
        for j in range(i + 1, len(out)):
            assert not cc.mesh_hits(out[i], out[j], 1e-4), 'capsules cross'
    n_caps = len(caps)
    rt.execute('max undo')
    left = [str(o.name) for o in rt.objects if str(o.name).startswith('CAPSULE_')]
    lines = [json.loads(x) for x in (OUT / 'journal' / 'untitled.jsonl').read_text(encoding='utf-8').splitlines()]
    return {'capsules': n_caps, 'kinds': [r['kind'] for r in plan['rows']], 'bbox_m': metrics,
            'one_undo_removes_all': not left, 'left_after_undo': left, 'preview_s': round(t_preview, 2),
            'apply_s': round(t_apply, 2), 'journal_lines': len(lines),
            'done': a['plan']['done'][:2]}


RES = {}


def caps_m():
    RES['m'] = capsules_case('meters')
    return RES['m']


def caps_cm():
    RES['cm'] = capsules_case('centimeters')
    assert RES['cm']['bbox_m'] == RES['m']['bbox_m'], 'cm and m capsules differ in metres'
    return {'same_metric_as_m': True, **{k: RES['cm'][k] for k in ('capsules', 'one_undo_removes_all', 'apply_s')}}


def refusals():
    fresh('meters')
    data = kb.badik_mesh(4.0, 4.0, 3.5, 0.25, [{'wall': 0, 's': [1.4, 2.6], 'z': [0.9, 2.4], 'bump': 0.05}])
    body = kb.mesh_node(rt, 'BODY_Bump_001', data)
    p = agr.edits_100('body.capsules', 'preview', None, [body])
    codes = [f['code'] for o in p['objects'] for f in o['findings']]
    assert p['status'] == 'fail' and codes == ['border_nonplanar'] and not p['plan']['capsules'], (p['status'], codes)
    a = agr.edits_100('body.capsules', 'apply', p)
    assert not [o for o in rt.objects if str(o.name).startswith('CAPSULE_')], 'an object for an ambiguous border'
    try:
        agr.edits_100('body.capsules', 'preview', None, [])
        raise AssertionError('empty input accepted')
    except ValueError as exc:
        assert 'empty target set' in str(exc)
    return {'ambiguous': p['plan']['ambiguous'], 'apply_status': a['status']}


def two_hundred():
    fresh('meters')
    ops = [{'wall': k, 's': [2.5 + i * 2.5, 3.5 + i * 2.5], 'z': [0.9 + j * 3.0, 2.4 + j * 3.0]}
           for k in range(4) for i in range(10) for j in range(5)]
    body = kb.mesh_node(rt, 'BODY_Big_001', kb.badik_mesh(30.0, 30.0, 16.0, 0.25, ops))
    t = time.time()
    p = agr.edits_100('body.capsules', 'preview', None, [body])
    t1 = time.time()
    a = agr.edits_100('body.capsules', 'apply', p)
    t2 = time.time()
    assert len(a['objects']) == 200, len(a['objects'])
    total = t2 - t
    return {'openings': 200, 'preview_s': round(t1 - t, 2), 'apply_s': round(t2 - t1, 2), 'total_s': round(total, 2),
            'under_20_s': total <= 20.0}


RECT = [[0, 0], [20, 0], [20, 12], [0, 12]]
LSHAPE = [[0, 0], [20, 0], [20, 6], [8, 6], [8, 12], [0, 12]]
USHAPE = [[0, 0], [20, 0], [20, 12], [14, 12], [14, 5], [6, 5], [6, 12], [0, 12]]


def roof_case(units):
    out = {}
    cases = {'rect': (RECT, {}), 'L': (LSHAPE, {}), 'U': (USHAPE, {}), 'terrace': (RECT, {'terrace': True}),
             'heights': (LSHAPE, {'heights': [0.9, 1.2, 1.5, 0.9, 1.2, 1.5]}), 'slope3': (RECT, {'slope_deg': 3.0}),
             'slope15': (RECT, {'slope_deg': 15.0})}
    for key, (outline, kw) in cases.items():
        fresh(units)
        node = kb.mesh_node(rt, 'PARAPET_' + key, kb.parapet_mesh(outline, 9.0, 0.9, 0.3, **kw))
        before = emax.snapshot([node])
        p = agr.edits_100('body.roof', 'preview', None, [node])
        if key == 'slope15':
            codes = [f['code'] for o in p['objects'] for f in o['findings']]
            assert p['status'] == 'fail' and codes == ['roof_steep'] and len(p['plan']['agent_requests']) == 1
            out[key] = {'status': p['status'], 'agent_requests': len(p['plan']['agent_requests'])}
            continue
        assert p['status'] == 'pass' and len(p['plan']['slabs']) == 1, (key, p['plan']['ambiguous'])
        a = agr.edits_100('body.roof', 'apply', p)
        assert a['status'] == 'pass' and emax.snapshot([node]) == before
        slab = rt.getAnimByHandle(a['objects'][0]['handle'])
        assert int(rt.polyop.getNumFaces(slab)) == 1 and host.role(host.refs([slab])[0]) == 'roof'
        k = host.m_per_unit()
        pts = []
        for i in rt.polyop.getFaceVerts(slab, 1):
            q = rt.polyop.getVert(slab, int(i))
            pts.append([float(q.x) * k, float(q.y) * k, float(q.z) * k])
        zs = [v[2] for v in pts]
        n = cc._unit(cc.newell(pts))
        sides = []
        for i in range(len(pts)):
            a_, b_ = pts[i], pts[(i + 1) % len(pts)]
            sides.append(cc.poly_dist([(a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2], outline))
        rec = {'z_min': round(min(zs), 4), 'z_max': round(max(zs), 4), 'normal_z': round(n[2], 5),
               'inset_mm': [round(min(sides) * 1000, 2), round(max(sides) * 1000, 2)]}
        if not kw.get('slope_deg'):
            assert abs(min(zs) - 9.005) < 0.0005 and abs(max(zs) - 9.005) < 0.0005, rec
            assert all(abs(d - 0.02) < 0.001 for d in sides), rec
        assert n[2] > 0.99, rec
        out[key] = rec
    return out


def roof_m():
    RES['roof_m'] = roof_case('meters')
    return RES['roof_m']


def roof_cm():
    got = roof_case('centimeters')
    assert got == RES['roof_m'], 'cm and m roofs differ'
    return {'same_metric_as_m': True, 'cases': sorted(got)}


def polygon_rows():
    """The K stations as the nightly polygon presses them (preview of the named objects, frag scenes)."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    cat = OUT / 'catalog.json'
    cat.write_text(json.dumps(core.load_catalog(), ensure_ascii=False), encoding='utf-8')
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    import build_scene
    rows = []
    for button in ('body.capsules', 'body.roof'):
        doc = json.loads((ROOT / 'test-polygon' / 'expected' / (button + '.json')).read_text(encoding='utf-8'))
        scene = doc['objects'][0]['scene']
        build_scene.build(scene, texture_dir=str(OUT / 'textures'))
        nodes = [rt.getNodeByName(o['name']) for o in doc['objects']]
        rt.select(nodes)
        rep = agr.edits_100(doc['tool'], 'preview', None, nodes, doc.get('options'))
        by = {o['name']: sorted({f['code'] for f in o['findings']}) for o in rep['objects']}
        for o in doc['objects']:
            codes = by.get(o['name'], [])
            got = 'fail' if codes else 'pass'
            ok = got == o['expect'] and codes == sorted(o['codes'])
            rows.append('{} {} {} {}: expected {}{} got {}{} {}'.format(
                doc['station'], button, o['name'], scene, o['expect'], (' ' + ','.join(o['codes'])) if o['codes'] else '',
                got, (' ' + ','.join(codes)) if codes else '', 'OK' if ok else 'MISMATCH'))
    assert all(r.endswith('OK') for r in rows), rows
    return rows


check('capsules_m', caps_m)
check('capsules_cm', caps_cm)
check('capsules_refusals', refusals)
check('capsules_200', two_hundred)
check('roof_m', roof_m)
check('roof_cm', roof_cm)
check('polygon_rows_k', polygon_rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('CAPSULES_ROOF_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native K failed: see summary.json'
