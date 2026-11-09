"""new-case: #1024 branch J native run of win.place (1.0.9) and win.generate (1.0.10) in locked batch Max 2024 on
DISPOSABLE scenes, plus the J rows of the live polygon.

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP,
AGR_TOOLS_REPO the worktree (the window library is read from its library/windows; Win_Typical.max is not opened).
Installs the MZP into OUT (no user folders touched), then:

* win.place, scenes in metres AND centimetres: the L10 synthetic KPP1 facade (walls 24 m / 12 m at 0 / 90 deg with a
  corner, 10 m at 30 deg; KPP1-W01..W03, one 10 cm from the wall end, a 1.5 x 1.5, an arch, a corner L opening)
  and a source window with an off-centre pivot. preview -> apply: windows on every typed opening, centre <= 5 mm and
  normal <= 0.5 deg against the generator truth, instances of one master per type, markers OPEN_<nnn> with
  agr_opening, ambiguous + draft files for the 1.5 x 1.5 / arch / corner; walls and the source window unchanged;
  the selection restored; a re-run plans nothing new; ONE `max undo` removes everything the apply made.
* win.generate: markers WT-11 / WT-02 / an unknown id -> pass / quarantine / unknown_type; apply writes a NEW folder
  (quality.json, sheet.png, OBJ, meshes.json); ids "all" -> the 67-type sheet; the scene is unchanged.
* polygon: builds polygon_all with the J fragment and presses win.place / win.generate on the J stations; the
  rows are compared with expected/ (polygon_core.compare_report).
Nothing is saved; the scenes are never written.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

from pymxs import runtime as rt

ROOT = Path(os.environ.get('AGR_TOOLS_REPO') or Path(__file__).resolve().parents[2])
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_JOURNAL_DIR'] = str(OUT / 'journal')
os.environ['AGR_NO_PROMPT'] = '1'
os.environ['AGR_TOOLS_REPO'] = str(ROOT)
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'repo': str(ROOT), 'checks': {}, 'errors': {}, 'seconds': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.perf_counter() - t0, 2)


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
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
summary['runtime_version'] = agr.VERSION
jb = load(ROOT / 'test-polygon/stations/J_build.py', 'agr_j_build_native')
oc = agr._load_core('openings_core.py', 'agr_tools_openings_core')
wp = agr._load_core('winplace_core.py', 'agr_tools_winplace_core')
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')


def quiet():
    import pymxs
    return pymxs.undo(False)  # scene setup outside any undo record: the run's record is the one to undo


def reset(units):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def mpu():
    return {'meters': 1.0, 'centimeters': 0.01}[str(rt.units.SystemType).lower().lstrip('#')]


def rows_of(node):
    tm = node.transform
    return [round(float(v), 6) for r in (tm.row1, tm.row2, tm.row3, tm.row4) for v in (r.x, r.y, r.z)]


def build_facades():
    """The L10 facades at the origin (metres in the spec; jb.mesh_node scales to the scene units)."""
    specs = [jb.kpp1_badik('J_Badik'), jb.kpp1_badik_30('J_Badik30')]
    nodes = []
    with quiet():
        for s in specs:
            nodes.append(jb.mesh_node(rt, jb.facade(s), s['name']))
        k = 1.0 / mpu()
        src = rt.Box(name='SRC_Window_001', width=1.18 * k, length=0.1 * k, height=1.8 * k)
        src.pos = rt.Point3(30 * k, -5 * k, 0)
        src.pivot = rt.Point3(30.4 * k, -5 * k, 0.2 * k)  # off-centre pivot: the source centerpivot'ed it (:57090)
    truth = []
    for s in specs:
        truth += jb.truth(s)
    return specs, nodes, src, truth


def win_nodes(prefix):
    return sorted((n for n in rt.objects if str(n.name).startswith(prefix)), key=lambda n: str(n.name))


def place_run(units):
    reset(units)
    specs, walls, src, truth = build_facades()
    rt.select(walls)
    sel_before = sorted(str(n.name) for n in rt.selection)
    snap_before = emax.snapshot(walls + [src])
    src_pivot = [float(c) for c in (src.pivot.x, src.pivot.y, src.pivot.z)]
    t0 = time.perf_counter()
    drafts = OUT / ('drafts_' + units)
    p = agr.edits_100('win.place', 'preview', None, walls, {'drafts_dir': str(drafts)})
    t_preview = time.perf_counter() - t0
    assert agr.parse_report(json.dumps(p)) == p
    plan = p['plan']
    counts = plan['counts']
    assert counts['openings'] == 16 and counts['place'] == 13 and counts['rejected'] == 2, counts
    assert len(plan['ambiguous']) == 3 and len(plan['drafts']) == 3, plan['ambiguous']
    codes = sorted({f['code'] for o in p['objects'] for f in o['findings']})
    assert codes == ['no_type', 'opening_ambiguous'], codes
    t0 = time.perf_counter()
    a = agr.edits_100('win.place', 'apply', p)
    t_apply = time.perf_counter() - t0
    wins, glasses, markers = win_nodes('WIN_'), win_nodes('GLASS_'), win_nodes('OPEN_')
    masters = win_nodes('WINLIB_')
    assert len(wins) == 13 and len(glasses) == 13 and len(markers) == 16, (len(wins), len(glasses), len(markers))
    worst_c, worst_n, per_type = 0.0, 0.0, {}
    gen = agr._load_core('windowgen_core.py', 'agr_tools_windowgen_core')
    lib = gen.load_library(gen.library_dir())
    for w in wins:
        tid = str(rt.getUserProp(w, 'agr_window_type'))
        m = gen.build_type(lib['by_id'][tid], lib['standard'])
        W, D, H = m['size_m']
        tm = w.transform
        rows = [[float(r.x), float(r.y), float(r.z)] for r in (tm.row1, tm.row2, tm.row3)]
        rows.append([float(tm.row4.x) * mpu(), float(tm.row4.y) * mpu(), float(tm.row4.z) * mpu()])
        c = wp.apply_rows(rows, [W / 2, D / 2, H / 2])
        t = min(truth, key=lambda q: math.dist(q['centre'], c))
        assert t['type'] == tid, (str(w.name), tid, t['type'])
        worst_c = max(worst_c, math.dist(c, t['centre']))
        worst_n = max(worst_n, wp.angle_deg(wp.face_normal_world(rows, '-y'), t['z']))
        master = rt.getNodeByName('WINLIB_' + tid)
        assert rt.areNodesInstances(w, master), str(w.name)
        per_type[tid] = per_type.get(tid, 0) + 1
        mk = rt.getNodeByName(str(rt.getUserProp(w, 'agr_opening_marker')))
        assert mk is not None and str(rt.getUserProp(mk, 'agr_window_type')) == tid
    assert worst_c <= 0.005 and worst_n <= 0.5, (worst_c, worst_n)
    for mk in markers:
        agr_op = json.loads(str(rt.getUserProp(mk, 'agr_opening')))
        assert set(agr_op) == {'w', 'h', 'sill', 'depth', 'wall', 'corner'} and str(rt.getUserProp(mk, 'agr_role')) == 'opening'
    corner = [mk for mk in markers if json.loads(str(rt.getUserProp(mk, 'agr_opening')))['corner']]
    assert len(corner) == 1
    assert emax.snapshot(walls + [src]) == snap_before, 'walls / source window changed'
    assert [float(c) for c in (src.pivot.x, src.pivot.y, src.pivot.z)] == src_pivot, 'source pivot moved'
    assert sorted(str(n.name) for n in rt.selection) == sel_before, 'selection not restored'
    files = sorted(x.name for x in drafts.iterdir())
    assert len(files) == 3, files
    again = agr.edits_100('win.place', 'preview', None, walls, {'drafts_dir': str(drafts)})
    assert not again['plan']['done'] and len(again['plan']['skipped']) == 13, again['plan']['skipped'][:3]
    rt.execute('max undo')
    left = [str(n.name) for n in rt.objects if str(n.name).startswith(('WIN', 'GLASS_', 'OPEN_'))]
    assert not left, left[:8]
    assert emax.snapshot(walls + [src]) == snap_before
    return {'units': units, 'openings': counts['openings'], 'placed': len(wins), 'glass': len(glasses),
            'markers': len(markers), 'masters': len(masters), 'per_type': per_type, 'ambiguous': plan['ambiguous'],
            'rejected': [r['why'][:60] for r in plan['rejected']], 'worst_centre_mm': round(worst_c * 1000, 4),
            'worst_normal_deg': round(worst_n, 5), 'apply_status': a['status'], 'drafts': files,
            'rerun_skipped': len(again['plan']['skipped']), 'undo': 'one max undo removed every node of the apply',
            'preview_s': round(t_preview, 2), 'apply_s': round(t_apply, 2)}


check('win_place_meters', lambda: place_run('meters'))
check('win_place_centimeters', lambda: place_run('centimeters'))


def generate_run():
    reset('meters')
    made = []
    with quiet():
        for name, tid in (('OPEN_901', 'WT-11'), ('OPEN_902', 'WT-02'), ('OPEN_903', 'ZZ-99')):
            n = rt.Point(name=name)
            rt.setUserProp(n, 'agr_role', 'opening')
            rt.setUserProp(n, 'agr_window_type', tid)
            made.append(n)
    snap = emax.snapshot(made)
    rt.select(made)
    p = agr.edits_100('win.generate', 'preview', None, made, {'out': str(OUT / 'wingen')})
    codes = {o['name']: sorted(f['code'] for f in o['findings']) for o in p['objects']}
    assert codes == {'OPEN_901': [], 'OPEN_902': ['quarantine'], 'OPEN_903': ['unknown_type']}, codes
    a = agr.edits_100('win.generate', 'apply', p)
    out = Path(a['plan']['out'])
    files = sorted(x.name for x in out.iterdir())
    assert files == ['WT-11.obj', 'meshes.json', 'quality.json', 'sheet.png'], files
    every = agr.edits_100('win.generate', 'preview', None, [], {'ids': 'all', 'out': str(OUT / 'wingen_all')})
    b = agr.edits_100('win.generate', 'apply', every)
    all_files = sorted(x.name for x in Path(b['plan']['out']).iterdir())
    q = json.loads((Path(b['plan']['out']) / 'quality.json').read_text(encoding='utf-8'))
    assert q['counts'] == {'pass': 61, 'quarantine': 6, 'duplicate': 0}, q['counts']
    v = {r['id']: r['verdict'] for r in q['types']}
    assert v['WT-07'] == v['WT-10'] == 'pass' and v['WT-02'] == 'quarantine'
    assert emax.snapshot(made) == snap and len(list(rt.objects)) == 3, 'win.generate changed the scene'
    # the OBJ comes back into Max: frame + glass faces, metres -> scene units
    try:
        rt.importFile(str(out / 'WT-11.obj'), rt.Name('noPrompt'))
        imported = len([n for n in rt.objects if n not in made])
    except Exception as exc:  # noqa: BLE001 - the OBJ importer is optional evidence, the files are the result
        imported = 'import error: ' + str(exc)[:120]
    return {'codes': codes, 'files': files, 'all_files': len(all_files), 'counts': q['counts'],
            'sheet_bytes': (Path(b['plan']['out']) / 'sheet.png').stat().st_size, 'obj_imported': imported}


check('win_generate', generate_run)


def polygon_rows():
    """The J stations of the live polygon: build polygon_all, press like build/run_inside_max.py, compare."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as pc
    import build_scene
    if not os.environ.get('AGR_POLYGON_CATALOG'):  # the builder input WITH the station fragments (run_polygon.py)
        path = OUT / 'catalog.json'
        path.write_text(json.dumps(pc.load_catalog(), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        os.environ['AGR_POLYGON_CATALOG'] = str(path)
    rt.resetMaxFile(rt.Name('noPrompt'))
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    rows = []
    for button in ('win.place', 'win.generate'):
        doc = pc.load_expected(button)
        names = [o['name'] for o in doc['objects'] if o['scene'] == 'polygon_all']
        st = pc.load_fragments()[button]
        names += [o['name'] for o in st['objects'] if o['name'] not in names]  # the seal is selected too
        nodes = [rt.getNodeByName(n) for n in names]
        assert all(n is not None for n in nodes), names
        rt.select(nodes)
        try:
            report = agr.edits_100(doc['tool'], 'preview', None, nodes, doc.get('options'))
        except Exception as exc:  # noqa: BLE001
            report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
        expected = [o for o in doc['objects'] if o['scene'] == 'polygon_all']
        bad = pc.compare_report(expected, report)
        got = pc.actual_codes(report) or {}
        for o in expected:
            rows.append({'station': doc['station'], 'button': button, 'name': o['name'], 'expect': o['expect'],
                         'codes': o['codes'], 'got': got.get(o['name']),
                         'ok': not [m for m in bad if m.get('name') in (o['name'], '')]})
        if bad:
            rows.append({'station': doc['station'], 'button': button, 'mismatch': bad})
    assert all(r.get('ok') for r in rows if 'mismatch' not in r) and not any('mismatch' in r for r in rows), rows
    return rows


check('polygon_J', polygon_rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('WINDOWS_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native windows run failed: see summary.json'
