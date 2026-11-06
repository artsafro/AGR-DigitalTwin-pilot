"""new-case: #1024 branch F native run in locked batch Max 2024 on DISPOSABLE scenes: project.passport,
source.intake, scene.source_class, scene.small_parts and their polygon rows (stations 1.0.1, 1.0.2, 1.0.3, 1.0.8).

Run via the lab DCC runner (script_in_place). Env: AGR_TEST_OUTPUT (a NEW directory), AGR_TEST_PACKAGE (the built
MZP), AGR_POLYGON_CATALOG (polygon_core.load_catalog() written by the caller, with stations/F.json). Installs the MZP
into OUT (no user folders), journal under OUT. Every scene is built here and saved only under OUT.
Checks:
* polygon: each frag_f_* scene of the 4 stations is built, saved under OUT, the button pressed in preview through
  runtime.edits_100 with the station options; rows compared with test-polygon/expected (polygon_core.compare_report);
* passport: create on a saved scene (new folder, valid by the schema, file property agr_passport = path + sha,
  persisted through save/load), 3 presses -> 3 journal lines, roles read back, open + refresh with a history copy,
  a passport with a broken schema -> error, apply by mcp -> needs_human;
* intake: an FBX-like source in cm, Y up, at 2 345 678 m -> copy in metres, Z up, near zero, originals unchanged,
  passport source + normalization written; ONE undo removes the copies;
* source_class: closed box monolithic, 40 panels panelised, empty selection -> error, scene unchanged;
* small_parts: only Bolt_M12 and Уголок_50 found, apply moves them to `optimize` with agr_source_layer, second run
  finds 0 new, ONE undo puts the layers back.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
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
           'checks': {}, 'errors': {}, 'polygon_rows': []}
assert not rt.maxFileName, 'only an empty batch document is allowed'
BUTTONS = ('project.passport', 'source.intake', 'scene.source_class', 'scene.small_parts')


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]


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
summary['runtime_version'] = agr.VERSION
pc = agr._load_core('passport_core.py', 'agr_tools_passport_core_native')
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max_native')


def fresh(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def save(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert rt.saveMaxFile(str(path), quiet=True), path
    return path


def mesh_node(name, verts, faces):
    return rt.mesh(name=name, vertices=rt.Array(*[rt.Point3(*p) for p in verts]),
                   faces=rt.Array(*[rt.Point3(*(i + 1 for i in f)) for f in faces]))


BOX_F = [(0, 2, 1), (1, 2, 3), (4, 5, 6), (5, 7, 6), (0, 1, 4), (1, 5, 4), (2, 6, 3), (3, 6, 7), (0, 4, 2), (2, 4, 6),
         (1, 3, 5), (3, 7, 5)]


def box(name, size, at=(0, 0, 0)):
    w, l, h = size
    x0, y0, z0 = at
    return mesh_node(name, [(x0 + dx * w, y0 + dy * l, z0 + dz * h) for dz in (0, 1) for dy in (0, 1)
                            for dx in (0, 1)], BOX_F)


def journal_lines(doc):
    jc = agr._load_core('journal_core.py', 'agr_tools_journal_core_native')
    return jc.read_lines(jc.journal_path(doc))[0]


# ---- polygon rows -----------------------------------------------------------------------------------------
def polygon():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    import build_scene
    assert os.environ.get('AGR_POLYGON_CATALOG'), 'AGR_POLYGON_CATALOG not set'
    rows, bad = [], []
    for button in BUTTONS:
        doc = json.loads((ROOT / 'test-polygon' / 'expected' / (button + '.json')).read_text(encoding='utf-8'))
        assert doc['shipped'] and doc['tool'] == button, (button, doc['shipped'], doc['tool'])
        scenes = []
        for o in doc['objects']:
            if o['scene'] not in scenes:
                scenes.append(o['scene'])
        for scene in scenes:
            build_scene.build(scene, texture_dir=str(OUT / 'textures'))
            build_scene.save(OUT / 'polygon' / (scene + '.max'))
            mine = [o for o in doc['objects'] if o['scene'] == scene]
            nodes = [rt.getNodeByName(o['name']) for o in mine]
            assert all(n is not None for n in nodes), [o['name'] for o, n in zip(mine, nodes) if n is None]
            rt.select(nodes)
            try:
                report = agr.edits_100(button, 'preview', None, nodes, doc.get('options'))
            except Exception as exc:  # noqa: BLE001 - an error is a row, never a pass
                report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
            mism = core.compare_report(mine, report)
            got = {o['name']: sorted({f['code'] for f in o['findings']}) for o in report.get('objects', [])}
            for o in mine:
                row = {'station': doc['station'], 'button': button, 'scene': scene, 'name': o['name'],
                       'expect': o['expect'], 'codes': o['codes'], 'got': got.get(o['name']),
                       'ok': not any(m.get('name') in (o['name'], '') for m in mism)}
                rows.append(row)
            bad += mism
    summary['polygon_rows'] = rows
    assert not bad, bad[:6]
    return {'rows': len(rows), 'ok': sum(r['ok'] for r in rows)}


# ---- project.passport -------------------------------------------------------------------------------------
def passport():
    fresh()
    host = agr._load_core('host_max.py', 'agr_tools_host_max_native').MaxHost()
    b = box('BODY_Brick_001', (10, 8, 30))
    g = box('GLASS_01', (1, 0.1, 1), (0, -1, 3))
    t = box('SM_Thing_Main', (1, 1, 1), (20, 0, 0))
    host.set_role(host.refs([b])[0], 'body')
    layer = rt.LayerManager.newLayerFromName('GLASS_main')
    layer.addNode(g)
    scene = save(OUT / 'scenes' / 'KPP1.max')
    doc = str(scene)
    root = OUT / 'proj'
    opts = {'root': str(root), 'project_id': 'KPP1', 'title': 'КПП-1'}
    before = len(journal_lines(doc))
    for _ in range(3):
        prev = agr.edits_100('project.passport', 'preview', None, None, opts)
    assert len(journal_lines(doc)) - before == 3, 'three presses, three journal lines'
    assert prev['plan']['action'] == 'create' and not root.exists(), 'preview wrote files'
    codes = {o['name']: [f['code'] for f in o['findings']] for o in prev['objects']}
    assert codes == {'BODY_Brick_001': [], 'GLASS_01': [], 'SM_Thing_Main': ['role_missing']}, codes
    try:
        agr.edits_100('project.passport', 'apply', prev, actor='mcp')
        raise AssertionError('apply by mcp was not refused')
    except ValueError as exc:
        assert str(exc).startswith('needs_human'), exc
    done = agr.edits_100('project.passport', 'apply', prev)
    path = root / 'jobs' / 'KPP1' / 'passport.json'
    p, sha = pc.read(str(path))
    assert sha == done['plan']['sha256']
    assert p['parts'] == [{'name': 'BODY_Brick_001', 'role': 'body'}, {'name': 'GLASS_01', 'role': 'glass'}], p['parts']
    idx = int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport'))
    link = pc.parse_link(str(rt.fileProperties.getPropertyValue(rt.name('custom'), idx)))
    assert link == {'path': str(path).replace('\\', '/'), 'sha256': sha}, link
    save(scene)
    rt.resetMaxFile(rt.name('noPrompt'))
    assert rt.loadMaxFile(str(scene), quiet=True)
    idx = int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport'))
    assert idx > 0 and pc.parse_link(str(rt.fileProperties.getPropertyValue(rt.name('custom'), idx)))['sha256'] == sha
    # roles read back after load; a role change refreshes the parts on the second press (open + history)
    host = agr._load_core('host_max.py', 'agr_tools_host_max_native2').MaxHost()
    thing = rt.getNodeByName('SM_Thing_Main')
    assert host.role(host.refs([rt.getNodeByName('BODY_Brick_001')])[0]) == 'body'
    host.set_role(host.refs([thing])[0], 'decor')
    prev2 = agr.edits_100('project.passport', 'preview', None, None, {})
    assert prev2['plan']['action'] == 'open' and prev2['status'] == 'pass', prev2['plan']['action']
    agr.edits_100('project.passport', 'apply', prev2)
    p2, sha2 = pc.read(str(path))
    assert {'name': 'SM_Thing_Main', 'role': 'decor'} in p2['parts'] and sha2 != sha
    assert (path.parent / 'history' / 'passport_v001.json').is_file()
    jl = [json.loads(x) for x in (path.parent / 'journal.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(jl) >= 6 and p2['journal']['lines'] == len(jl), (len(jl), p2['journal']['lines'])  # copied before its own line
    # a passport broken by hand: an error, the file is left as it is
    broken = dict(p2, source=dict(p2['source'], level='D'))
    raw = json.dumps(broken)
    path.write_text(raw, encoding='utf-8')
    try:
        agr.edits_100('project.passport', 'preview', None, None, {})
        raise AssertionError('broken passport accepted')
    except ValueError as exc:
        assert 'level' in str(exc), exc
    assert path.read_text(encoding='utf-8') == raw
    path.write_bytes(pc.dumps(p2))
    return {'passport': str(path), 'sha256': sha2, 'parts': len(p2['parts']), 'journal_lines': len(jl),
            'stages': [s['status'] for s in p2['stages']].count('todo')}


# ---- source.intake ----------------------------------------------------------------------------------------
def intake():
    """Continues on the scene of passport(): the passport is linked, intake writes source + normalization."""
    assert int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport')) > 0, 'run passport() first'
    for n in list(rt.objects):
        rt.delete(n)
    # cm numbers, Y up (height 30 m on Y), 2 345 678 m east
    src = box('SRC_Main', (2000, 3000, 1500), (234567808.0, 0, 50000.0))  # float32-exact x
    src2 = box('SRC_Part_Main', (500, 500, 500), (234568800.0, 500.0, 50000.0))  # inside the bbox
    snap = emax.snapshot([src, src2])
    rt.select([src, src2])
    prev = agr.edits_100('source.intake', 'preview', None, None, {'source_up_axis': 'Y',
                                                                 'source_path': 'C:/src/KPP1.fbx'})
    plan = prev['plan']
    assert plan['normalization']['source_units'] == 'cm' and plan['normalization']['origin_m'][0] == 2345678.0, plan
    assert emax.snapshot([src, src2]) == snap, 'preview changed the scene'
    rep = agr.edits_100('source.intake', 'apply', prev)
    copies = [rt.getNodeByName(n) for n in rep['plan']['readback']['copies']]
    assert len(copies) == 2 and all(str(c.layer.name) == 'AGR_intake' for c in copies)
    size = rep['plan']['readback']['size_m']
    lo = rep['plan']['readback']['min_m']
    assert [round(s, 2) for s in size] == [20.0, 15.0, 30.0], size
    assert all(-1.0 <= c <= 1.0 for c in lo), lo
    assert emax.snapshot([src, src2]) == snap, 'originals changed'
    link = pc.parse_link(str(rt.fileProperties.getPropertyValue(
        rt.name('custom'), int(rt.fileProperties.findProperty(rt.name('custom'), 'agr_passport')))))
    p, _ = pc.read(link['path'])
    assert p['normalization']['source_up_axis'] == 'Y' and p['normalization']['origin_m'][0] == 2345678.0
    assert p['source']['path'] == 'C:/src/KPP1.fbx' and p['source']['class'] == 'monolithic', p['source']
    names = [str(c.name) for c in copies]
    rt.execute('max undo')  # ONE undo removes the whole run
    assert all(rt.getNodeByName(n) is None for n in names), 'copies survived one undo'
    # 3dsmaxbatch merges every pymxs undo record of one ExecuteFile into one step (job 20261105-003249-e0800495,
    # run_agr_tools_edits_native.py): the same undo may remove the setup boxes too; recorded, not asserted.
    summary['intake_undo_setup_alive'] = bool(rt.isValidNode(src))
    return {'size_m': size, 'min_m': lo, 'origin_m': p['normalization']['origin_m'], 'class': p['source']['class'],
            'level': p['source']['level'], 'findings': sorted({f['code'] for o in prev['objects']
                                                               for f in o['findings']})}


# ---- scene.source_class -----------------------------------------------------------------------------------
def source_class():
    fresh()
    shell = box('SM_Shell_Main', (10, 8, 30))
    verts, faces = [], []
    for i in range(40):
        x = i * 1.5
        b = len(verts)
        verts += [(x, 20, 0), (x + 1.2, 20, 0), (x + 1.2, 20, 3), (x, 20, 3)]
        faces += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    panels = mesh_node('SM_Panels_Main', verts, faces)
    snap = emax.snapshot([shell, panels])
    r = agr.edits_100('scene.source_class', 'preview', None, [shell, panels])
    cls = r['plan']['classes']
    assert cls['SM_Shell_Main']['class'] == 'monolithic' and cls['SM_Panels_Main']['class'] == 'panelised', cls
    assert cls['SM_Panels_Main']['parts'] == 40
    rt.clearSelection()
    try:
        agr.edits_100('scene.source_class', 'preview')
        raise AssertionError('empty selection accepted')
    except ValueError as exc:
        assert 'empty selection' in str(exc), exc
    assert emax.snapshot([shell, panels]) == snap
    return {'classes': {k: (v['class'], v['parts'], round(v['largest_share'], 4)) for k, v in cls.items()},
            'source': r['plan']['source']['class']}


# ---- scene.small_parts ------------------------------------------------------------------------------------
def small_parts():
    fresh()
    sizes = {'Bolt_M12': (0.02, 0.02, 0.06), 'Studio_Main': (1, 1, 1), 'Minute_Hand': (1, 0.2, 0.2),
             'Шпиль': (0.5, 0.5, 4), 'М120_Panel': (1.2, 0.1, 3), 'Стеклопакет_01': (1.2, 0.04, 1.5),
             'Уголок_50': (0.05, 0.05, 0.1)}
    work = rt.LayerManager.newLayerFromName('FACADE_parts')
    nodes = []
    for i, (name, size) in enumerate(sizes.items()):
        n = box(name, size, (i * 2.0, 0, 0))
        work.addNode(n)
        nodes.append(n)
    rt.select(rt.getNodeByName('Studio_Main'))
    prev = agr.edits_100('scene.small_parts', 'preview')
    assert prev['plan']['done'] == ['Bolt_M12', 'Уголок_50'], prev['plan']['done']
    rep = agr.edits_100('scene.small_parts', 'apply', prev)
    assert [m['name'] for m in rep['plan']['moved']] == ['Bolt_M12', 'Уголок_50']
    for name in ('Bolt_M12', 'Уголок_50'):
        n = rt.getNodeByName(name)
        assert str(n.layer.name) == 'optimize' and str(rt.getUserProp(n, 'agr_source_layer')) == 'FACADE_parts'
    assert [str(n.name) for n in rt.selection] == ['Studio_Main'], [str(n.name) for n in rt.selection]
    again = agr.edits_100('scene.small_parts', 'preview')
    assert again['plan']['done'] == [] and again['plan']['found'] == 0 and len(again['plan']['skipped']) == 2
    rt.execute('max undo')  # ONE undo: the layers are back (batch may merge the setup into it, see intake())
    alive = [n for n in nodes if rt.isValidNode(n)]
    layers = {str(n.name): str(n.layer.name) for n in alive}
    assert set(layers.values()) <= {'FACADE_parts'}, layers
    summary['small_parts_undo_setup_alive'] = len(alive)
    return {'found': prev['plan']['done'], 'second_run_new': again['plan']['found'], 'layers_after_undo': 'FACADE_parts'}


check('polygon_rows', polygon)
check('passport', passport)
if 'passport' in summary['checks']:
    check('intake', intake)
check('source_class', source_class)
check('small_parts', small_parts)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('PASSPORT_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'branch F native failed: see summary.json'
