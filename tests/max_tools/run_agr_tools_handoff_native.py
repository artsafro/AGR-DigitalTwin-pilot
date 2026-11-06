"""new-case: #1024 branch BH native run of the Max <-> Blender handoff in locked batch 3ds Max 2024, DISPOSABLE scenes.

Run via the lab DCC runner (script_in_place) in two Max jobs around one Blender job (tools/blender/handoff_blender.py):

  AGR_HANDOFF_PHASE=export   builds the synthetic scene in CENTIMETRES and saves it under OUT (never elsewhere):
      bundle 001  BODY_Brick_001 (octagonal prism: two 8-gon caps, 3 matIDs, smoothing: smooth sides + hard caps,
                  UV channel 1 in UDIM 1001 and channel 2 in 1002, pivot moved off the geometry, rotated 30 deg),
                  BODY_Brick_002 (an INSTANCE of it), GLASS_001 (child of BODY_Brick_001); materials Standard Legacy
                  with Bitmaptexture maps diffuse (U tiling 2), bump, opacity and a Multi/Sub 1/2/3; markers OPEN_001
                  and LEVEL_L1 (sidecar only);
      bundle 002  KPP1-like copy (facade of J_build.facade with the KPP1 openings, parapet of K_build, bolts) with the
                  library ids 3/9/12/16/29/35 on the faces (Multi/Sub with gaps);
      then handoff.export preview -> apply for both (job_dir under OUT).
  AGR_HANDOFF_PHASE=return   loads that scene (AGR_HANDOFF_SCENE), and per bundle (AGR_HANDOFF_JOB/handoff/<seq>) with
      the FBX of the Blender job (AGR_HANDOFF_BLENDER/<seq>/return/model.fbx): handoff.import -> handoff.verify
      (Max + Blender readbacks against readback_max.json) -> «Восстановить материалы» (001: reuse of the scene
      materials; 002: rebuilt from materials.json) -> verify again -> agent.accept (branch U gate). Then a FRESH
      scene: import 001 without the originals, restore (rebuilt), a stray object is reported as unmatched.
Writes OUT/summary.json and OUT/table.md. Nothing outside OUT is written; the loaded scene is never saved.
"""
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import time
import traceback
import types
import zlib

from pymxs import runtime as rt

ROOT = Path(os.environ.get('AGR_TOOLS_REPO') or Path(__file__).resolve().parents[2])
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PHASE = os.environ['AGR_HANDOFF_PHASE']
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
TOOLS = ROOT / 'adapters' / 'max' / 'agr_tools'
summary = {'phase': PHASE, 'max_version': list(rt.maxVersion())[:3], 'checks': {}, 'errors': {}, 'timings': {},
           'reports': {}}


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EDIT = load(TOOLS / 'edit_core.py', 'agr_tools_edit_core')
CORE = load(TOOLS / 'handoff_core.py', 'agr_tools_handoff_core')
GLUE = load(TOOLS / 'handoff_max.py', 'agr_tools_handoff_max')
BCORE = load(TOOLS / 'agentbridge_core.py', 'agr_tools_agentbridge_core')
BMAX = load(TOOLS / 'agentbridge_max.py', 'agr_tools_agentbridge_max')
HOST = load(TOOLS / 'host_max.py', 'agr_tools_host_max').MaxHost()


def check(name, fn):
    t0 = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['timings'][name] = round(time.time() - t0, 2)


def ctx(core, options=None):
    return types.SimpleNamespace(agr=types.SimpleNamespace(), edit=EDIT, core=core, emax=None,
                                 options=dict(options or {}), host=HOST)


def press(tool, fn, core, nodes=None, options=None, apply=True, key=None):
    """preview -> apply of that preview, as runtime._dispatch_edit does (validate, check_preview)."""
    prev = fn(ctx(core, options), 'preview', nodes, None)
    EDIT.validate_report(prev, {tool})
    out = {'preview': prev}
    if apply:
        EDIT.check_preview(tool, prev)
        app = fn(ctx(core), 'apply', nodes, prev)
        EDIT.validate_report(app, {tool})
        out['apply'] = app
    summary['reports'][key or tool] = out
    return out


def png(path, rgb, size=8):
    raw = b''.join(b'\x00' + bytes(rgb) * size for _ in range(size))

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    path.write_bytes(data)
    return path


def fill_multi(mm, subs, ids):
    rt.execute('(fn f mm subs ids = (mm.numsubs = subs.count; for i = 1 to subs.count do (mm.materialList[i] = '
               'subs[i]; mm.materialIDList[i] = ids[i]); ok); f)')(mm, subs, ids)


def layer(name):
    return rt.LayerManager.getLayerFromName(name) or rt.LayerManager.newLayerFromName(name)


def bitmap(name, path, **props):
    t = rt.Bitmaptexture(fileName=str(path))
    t.name = name
    for k, v in props.items():
        setattr(t.coords, k, v)
    return t


# ---- phase export --------------------------------------------------------------------------------------------------
def build_synthetic():
    import pymxs
    maps = OUT / 'maps'
    maps.mkdir()
    diff = png(maps / 'bh_diffuse.png', (200, 120, 80))
    bump = png(maps / 'bh_bump.png', (128, 128, 128))
    opac = png(maps / 'bh_opacity.png', (255, 255, 255))
    with pymxs.undo(False):
        s1 = rt.StandardMaterial(name='BH_Cap_Top')
        s1.diffuseMap = bitmap('BH_Cap_Top_diffuse', diff, U_Tiling=2.0)
        s1.diffuse = rt.Color(200, 120, 80)
        s2 = rt.StandardMaterial(name='BH_Cap_Bottom')
        s2.bumpMap = bitmap('BH_Cap_Bottom_bump', bump)
        s2.bumpMapAmount = 45.0
        s3 = rt.StandardMaterial(name='BH_Side')
        s3.diffuseMap = bitmap('BH_Side_diffuse', diff, V_Offset=0.25)
        s3.opacityMap = bitmap('BH_Side_opacity', opac)
        s3.specularLevel = 30.0
        s3.glossiness = 25.0
        mm = rt.MultiMaterial()
        mm.name = 'BH_Multi'
        fill_multi(mm, [s1, s2, s3], [1, 2, 3])
        glass = rt.StandardMaterial(name='BH_Glass')
        glass.opacityMap = bitmap('BH_Glass_opacity', opac)
        glass.opacity = 40.0
        glass.diffuse = rt.Color(90, 120, 140)
        c = rt.Cylinder(radius=50, height=120, sides=8, heightsegs=1, capsegs=1, smooth=True, mapcoords=True)
        c.name = 'BODY_Brick_001'
        rt.convertToPoly(c)
        po = rt.polyop
        po.setMapSupport(c, 2, True)
        nmv = int(po.getNumMapVerts(c, 1))
        po.setNumMapVerts(c, 2, nmv)
        for i in range(1, nmv + 1):
            p = po.getMapVert(c, 1, i)
            po.setMapVert(c, 2, i, rt.Point3(float(p.x) + 1.0, float(p.y), 0.0))
        nf = int(po.getNumFaces(c))
        po.setNumMapFaces(c, 2, nf)
        for f in range(1, nf + 1):
            po.setMapFace(c, 2, f, po.getMapFace(c, 1, f))
        c.pos = rt.Point3(250, -130, 40)
        rt.rotate(c, rt.EulerAngles(0, 0, 30))
        c.pivot = c.pos + rt.Point3(20, 10, -15)
        c.material = mm
        rt.setUserProp(c, 'agr_role', 'body')
        inst = rt.instance(c)
        inst.name = 'BODY_Brick_002'
        inst.pos = inst.pos + rt.Point3(300, 0, 0)
        inst.material = mm
        rt.setUserProp(inst, 'agr_role', 'body')
        g = rt.Box(length=40, width=60, height=2)
        g.name = 'GLASS_001'
        rt.convertToPoly(g)
        g.pos = rt.Point3(250, -190, 60)
        g.material = glass
        g.parent = c
        rt.setUserProp(g, 'agr_role', 'glass')
        rt.setUserProp(g, 'agr_note', 'synthetic BH glass')
        layer('BODY_main').addNode(c)
        layer('BODY_main').addNode(inst)
        layer('GLASS_main').addNode(g)
        o = rt.Point(name='OPEN_001')
        o.pos = rt.Point3(250, -190, 60)
        rt.setUserProp(o, 'agr_role', 'opening')
        rt.setUserProp(o, 'agr_window_type', 'WT-07')
        rt.setUserProp(o, 'agr_opening', json.dumps({'w': 0.6, 'h': 0.4, 'sill': 0.6, 'depth': 0.2,
                                                     'wall': 'BODY_Brick_001', 'corner': False}, sort_keys=True))
        lv = rt.Point(name='LEVEL_L1')
        lv.pos = rt.Point3(0, 0, 0)
    return [c, inst, g]


def build_kpp1():
    import pymxs
    JB = load(ROOT / 'test-polygon' / 'stations' / 'J_build.py', 'J_build')
    KB = load(ROOT / 'test-polygon' / 'stations' / 'K_build.py', 'K_build')
    W, L, PT, PH, PTh = 27.66, 11.66, 8.65, 0.555, 0.3
    roof = PT - PH
    wall_top = roof - 0.3
    holes = []

    def add(wall, u, t, floor):
        w, h = JB.KPP1[t]
        sill = 0.3 if t == 'KPP1-W02' else (0.9 if floor == 1 else 4.8)
        holes.append({'wall': wall, 'kind': 'rect', 'u': u, 'sill': sill, 'w': w, 'h': h, 'type': t})
    for u, t in ((2.0, 'KPP1-W01'), (6.0, 'KPP1-W03'), (10.0, 'KPP1-W01'), (14.0, 'KPP1-W02'), (18.0, 'KPP1-W01'),
                 (22.0, 'KPP1-W03')):
        add(0, u, t, 1)
    for u, t in ((2.0, 'KPP1-W01'), (6.0, 'KPP1-W03'), (10.0, 'KPP1-W01'), (18.0, 'KPP1-W01'), (22.0, 'KPP1-W03')):
        add(0, u, t, 2)
    for fl in (1, 2):
        for u in (3.0, 9.0, 15.0, 21.0):
            add(2, u, 'KPP1-W01', fl)
        add(3, 4.83, 'KPP1-W03', fl)
    spec = {'name': 'KPP1_Facade', 'points': [[0, 0], [W, 0], [W, L], [0, L], [0, 0]], 'height': wall_top,
            'reveal': 0.23, 'holes': holes, 'corners': []}
    data = JB.facade(spec)
    ids = []
    for f, mid in zip(data['faces'], data['mat_ids']):
        z = sum(data['verts'][i][2] for i in f) / len(f)
        ids.append(3 if mid == 2 else 16 if z < 0.9 else 12 if z < 2.7 else 9 if z < 7.1 else 12)
    data['mat_ids'] = ids
    with pymxs.undo(False):
        subs = [rt.StandardMaterial(name='KPP1_AR_{:02d}'.format(i)) for i in (16, 12, 9, 3, 29, 35)]
        for s, col in zip(subs, ((110, 110, 110), (120, 125, 130), (30, 60, 110), (240, 240, 235), (80, 80, 80),
                                 (160, 160, 160))):
            s.diffuse = rt.Color(*col)
        mm = rt.MultiMaterial()
        mm.name = 'KPP1_AR'
        fill_multi(mm, subs, [16, 12, 9, 3, 29, 35])
        facade = JB.mesh_node(rt, data, 'KPP1_Facade')
        facade.material = mm
        rt.addModifier(facade, rt.Uvwmap(maptype=4))
        rt.collapseStack(facade)
        inner = [[PTh, PTh], [W - PTh, PTh], [W - PTh, L - PTh], [PTh, L - PTh]]
        pdata = KB.parapet_mesh(inner, roof, PH, PTh)
        parapet = KB.mesh_node(rt, 'KPP1_Parapet', {'verts': pdata['verts'], 'faces': pdata['faces']})
        for i, f in enumerate(pdata['faces'], 1):
            pts = [pdata['verts'][j] for j in f]
            n = JB._newell(pts)
            ln = (n[0] ** 2 + n[1] ** 2 + n[2] ** 2) ** 0.5 or 1.0
            rt.polyop.setFaceMatID(parapet, i, 35 if abs(n[2] / ln) > 0.7 else 29)
        parapet.material = mm
        rt.addModifier(parapet, rt.Uvwmap(maptype=4))
        rt.collapseStack(parapet)
        bolts = []
        for i, x in enumerate((1.0, 9.0)):
            b = rt.Box(name='Bolt_M12_{:02d}'.format(i + 1), length=2, width=2, height=6)
            b.pos = rt.Point3(x * 100, -5, 700)
            rt.convertToMesh(b)
            b.material = subs[4]
            bolts.append(b)
        for n in [facade, parapet]:
            rt.setUserProp(n, 'agr_role', 'body')
            layer('BODY_kpp1').addNode(n)
        for b in bolts:
            rt.setUserProp(b, 'agr_role', 'equipment')
            layer('EQUIPMENT_kpp1').addNode(b)
    return [facade, parapet] + bolts


def phase_export():
    assert not rt.maxFileName, 'only an empty batch document is allowed'
    rt.units.SystemType = rt.name('centimeters')
    rt.units.SystemScale = 1.0
    sets = {}
    check('build_synthetic', lambda: [str(n.name) for n in sets.setdefault('001', build_synthetic())])
    check('build_kpp1', lambda: [str(n.name) for n in sets.setdefault('002', build_kpp1())])
    scene = OUT / 'scene' / 'handoff_synth.max'
    scene.parent.mkdir()
    assert rt.saveMaxFile(str(scene), quiet=True), scene
    summary['scene'] = str(scene)
    job = OUT / 'job'
    job.mkdir()
    for seq, nodes in sorted(sets.items()):
        def run(seq=seq, nodes=nodes):
            r = press(CORE.TOOL_EXPORT, GLUE.handoff_export, CORE, nodes, {'job_dir': str(job), 'seq': seq},
                      key='export_' + seq)
            a = r['apply']
            bundle = Path(a['plan']['bundle'])
            mats = json.loads((bundle / 'materials.json').read_text(encoding='utf-8'))
            man = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
            return {'status': [r['preview']['status'], a['status']], 'bundle': str(bundle),
                    'files': sorted(os.listdir(bundle)), 'done': a['plan']['done'],
                    'materials_objects': [[o['name'], o['role'], o['material'] and mats['nodes'][o['material']]['name'],
                                           o['material'] and mats['nodes'][o['material']]['class'], o['mat_ids']]
                                          for o in mats['objects']],
                    'maps': mats['maps'], 'node_count': len(mats['nodes']),
                    'slots': {o['name']: o['slots'] for o in man['objects']},
                    'instance_of': {o['name']: o['instance_of'] for o in man['objects']}}
        check('export_' + seq, run)


# ---- phase return --------------------------------------------------------------------------------------------------
def accept(request):
    def fn(c, mode, nodes, preview):
        c.core = BCORE
        return BMAX.agent_accept(c, mode, nodes, preview)
    r = press(BCORE.TOOL_ACCEPT, fn, BCORE, [], {'request': request}, key='accept_' + Path(request).parent.name)
    return r


def roundtrip(seq, reuse, blender):
    job = Path(os.environ['AGR_HANDOFF_JOB'])
    bundle = job / 'handoff' / seq
    fbx = Path(blender) / seq / 'return' / 'model.fbx'
    rid = 'bh' + seq
    res = {}
    imp = press(CORE.TOOL_IMPORT, GLUE.handoff_import, CORE, [],
                {'bundle': str(bundle), 'fbx': str(fbx), 'request_id': rid,
                 'agent_dir': str(OUT / ('agent_' + rid))}, key='import_' + seq)['apply']
    res['import'] = {'status': imp['status'], 'done': imp['plan']['done'], 'ambiguous': imp['plan']['ambiguous'],
                     'imported': imp['plan']['imported']}
    layer_name = imp['plan']['layer']
    ver_opts = {'bundle': str(bundle), 'layer': layer_name,
                'blender_readback': str(Path(blender) / seq / 'readback_blender.json')}
    v1 = press(CORE.TOOL_VERIFY, GLUE.handoff_verify, CORE, [], ver_opts, apply=False, key='verify1_' + seq)['preview']
    res['verify_before_restore'] = {'discrepancies': v1['plan']['discrepancies'], 'tables': v1['plan']['tables']}
    rest = press(CORE.TOOL_RESTORE, GLUE.handoff_restore_materials, CORE, [],
                 {'bundle': str(bundle), 'layer': layer_name, 'reuse': reuse}, key='restore_' + seq)['apply']
    res['restore'] = {'status': rest['status'], 'objects': rest['objects'], 'done': rest['plan']['done'],
                      'skipped': rest['plan']['skipped'], 'ambiguous': rest['plan']['ambiguous'],
                      'rebuilt': rest['plan']['rebuilt'], 'reused': rest['plan']['reused'],
                      'diff_count': rest['plan']['diff_count']}
    v2 = press(CORE.TOOL_VERIFY, GLUE.handoff_verify, CORE, [], ver_opts, apply=False, key='verify2_' + seq)['preview']
    res['verify'] = {'discrepancies': v2['plan']['discrepancies'], 'tables': v2['plan']['tables'],
                     'objects': v2['objects']}
    acc = accept(imp['plan']['request'])['apply']
    res['accept'] = {'verdict': acc['plan']['verdict'], 'done': acc['plan']['done'], 'objects': acc['objects']}
    return res


def fresh_restore(blender):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('centimeters')
    rt.units.SystemScale = 1.0
    job = Path(os.environ['AGR_HANDOFF_JOB'])
    bundle = job / 'handoff' / '001'
    imp = press(CORE.TOOL_IMPORT, GLUE.handoff_import, CORE, [],
                {'bundle': str(bundle), 'fbx': str(Path(blender) / '001' / 'return' / 'model.fbx'),
                 'request_id': 'bhfresh', 'agent_dir': str(OUT / 'agent_bhfresh')}, key='import_fresh')['apply']
    lay = imp['plan']['layer']
    rest = press(CORE.TOOL_RESTORE, GLUE.handoff_restore_materials, CORE, [],
                 {'bundle': str(bundle), 'layer': lay, 'reuse': 'never'}, key='restore_fresh')['apply']
    w = GLUE.MaterialWriter(rt)
    mats = json.loads((bundle / 'materials.json').read_text(encoding='utf-8'))
    got = {}
    for n in rt.objects:
        if str(n.layer.name) == lay and n.material is not None:
            got[str(n.name)] = w.ref(n.material)
    paths = sorted(m['path'] for m in CORE.map_list(w.nodes))
    want = sorted(m['path'] for m in mats['maps'])
    v = press(CORE.TOOL_VERIFY, GLUE.handoff_verify, CORE, [], {'bundle': str(bundle), 'layer': lay}, apply=False,
              key='verify_fresh')['preview']
    stray = rt.Box(name='Stray_Box')
    layer(lay).addNode(stray)
    neg = GLUE.handoff_restore_materials(ctx(CORE, {'bundle': str(bundle), 'layer': lay}), 'preview', [], None)
    return {'restore_status': rest['status'], 'diff_count': rest['plan']['diff_count'], 'rebuilt': rest['plan']['rebuilt'],
            'objects': rest['objects'], 'skipped': rest['plan']['skipped'], 'ambiguous': rest['plan']['ambiguous'],
            'map_paths_equal': paths == want, 'map_paths': paths,
            'node_names': sorted({w.nodes[k]['name'] for k in w.nodes}),
            'stray_reported': [o['name'] for o in neg['objects'] if any(f['code'] == 'unmatched' for f in o['findings'])],
            'verify_discrepancies': v['plan']['discrepancies'], 'verify_tables': v['plan']['tables']}


def phase_return():
    assert not rt.maxFileName, 'only an empty batch document is allowed'
    blender = os.environ['AGR_HANDOFF_BLENDER']
    assert rt.loadMaxFile(os.environ['AGR_HANDOFF_SCENE'], useFileUnits=True, quiet=True), 'scene not loaded'
    for seq, reuse in (('001', 'scene'), ('002', 'never')):
        check('roundtrip_' + seq, lambda seq=seq, reuse=reuse: roundtrip(seq, reuse, blender))
    check('fresh_restore_001', lambda: fresh_restore(blender))


def table_md():
    lines = ['# BH handoff native — phase {}'.format(PHASE), '']
    for name, val in summary['checks'].items():
        if isinstance(val, dict) and 'verify' in val:
            lines += ['## {}'.format(name), '', '| Свойство | Max (возврат) | Blender |', '|---|---|---|']
            t = val['verify']['tables']
            bl = {r[0]: r for r in t.get('blender', [])}
            for row in t['max']:
                b = bl.get(row[0])
                lines.append('| {} | {} {} | {} |'.format(row[1], row[2], row[3], '{} {}'.format(b[2], b[3]) if b
                                                           else '-'))
            lines += ['', 'restore: {} diff {} rebuilt {} reused {}; accept: {}'.format(
                val['restore']['status'], val['restore']['diff_count'], val['restore']['rebuilt'],
                val['restore']['reused'], val['accept']['verdict']), '']
    lines += ['errors: {}'.format(sorted(summary['errors'])), '']
    return '\n'.join(lines)


t_all = time.time()
try:
    if PHASE == 'export':
        phase_export()
    elif PHASE == 'return':
        phase_return()
    else:
        raise ValueError('AGR_HANDOFF_PHASE must be export or return')
except Exception:  # noqa: BLE001
    summary['errors']['phase'] = traceback.format_exc()[-3000:]
summary['timings']['total'] = round(time.time() - t_all, 2)
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
(OUT / 'table.md').write_text(table_md(), encoding='utf-8')
print('HANDOFF_NATIVE', PHASE, 'errors:', sorted(summary['errors']))
if summary['errors']:
    raise RuntimeError('handoff native: ' + ', '.join(sorted(summary['errors'])))
