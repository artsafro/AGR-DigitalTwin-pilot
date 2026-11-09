"""new-case: #1024 branch S native run of stage 9 (`ucx.gap` 1.0.27, `light.export` 1.0.29, `pack.deliver` 1.0.26)
in locked batch Max 2024 on DISPOSABLE synthetic scenes (one runner job for every button and polygon row).

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP,
AGR_PYTHON / AGR_TOOLS_REPO the validator of qa.package. Installs the MZP into OUT (no user folders touched).
* polygon: the stations of test-polygon/stations/S.json are built with S_build exactly as build/build_scene.py does
  (scene per `frag_s_*`, saved into OUT so the scene has a folder) and pressed in preview like run_inside_max.py;
  rows {button, scene, name, expect, got, codes, ok} go to polygon_rows.json;
* ucx.gap acceptance (L13): pairs -2/0/1/2/4/10/40 mm in m and cm, apply on copies, SAT readback >= 4.00 mm
  +- 0.01 for < 4 mm, wider pairs unchanged, originals and foreign UCX_Other_001 byte-equal, one undo record, repeat
  without change, m == cm;
* light.export acceptance (L13): 3 Free Spot, 2 Omni, 1 Target Spot, 1 Photometric under the root: 7 lights + 1 root
  in the readback, Omni there, Target Spot direction, no other top node; an existing FBX keeps its sha256 (a new
  `_v002` beside it, refuse mode refuses); export.zip + qa.package accept the VPM archive with `_Light.fbx`;
* pack.deliver: preview + apply on a synthetic VPM scene: run folder `Сдача_*`, deliver.json, stage 9 in the
  passport copy (done or blocked with the blockers listed).
"""
import hashlib
import importlib.util
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
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'
SCENES = OUT / 'scenes'
SCENES.mkdir()


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
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
summary['runtime_version'] = agr.VERSION
S_BUILD = load(ROOT / 'test-polygon/stations/S_build.py', 'S_build')
FRAG = json.loads((ROOT / 'test-polygon/stations/S.json').read_text(encoding='utf-8'))
host = agr._load_core('host_max.py', 'agr_tools_host_max').MaxHost()
gapc = agr._load_core('ucx10_core.py', 'agr_tools_ucx10_core')
lightc = agr._load_core('light_core.py', 'agr_tools_light_core')


def fresh(units='meters'):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def build(objs):
    """Scene nodes made with undo OFF: the only undo records are those of the buttons."""
    import pymxs
    with pymxs.undo(False):
        return _build(objs)


def _build(objs):
    made = {}
    for o in objs:
        made[o['name']] = S_BUILD.make(o, rt)
    for o in objs:
        if o.get('parent'):
            made[o['name']].parent = made[o['parent']]
    return made


def save(name):
    path = SCENES / (name + '.max')
    assert rt.saveMaxFile(str(path), quiet=True), path
    return path


def codes_of(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report.get('objects') or ()}


# ---- polygon rows ---------------------------------------------------------------------------------------------
def polygon():
    rows, reports = [], {}
    for st in FRAG['stations']:
        scenes = []
        for o in st['objects']:
            if o['scene'] not in scenes:
                scenes.append(o['scene'])
        for scene in scenes:
            mine = [o for o in st['objects'] if o['scene'] == scene]
            units = (mine[0].get('extra') or {}).get('units', 'meters')
            fresh(units)
            made = build(mine)
            save(scene)
            rt.select(list(made.values()))
            try:
                rep = agr.edits_100(st['button'], 'preview', None, list(made.values()), st.get('options'))
            except Exception as exc:  # noqa: BLE001
                rep = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc), 'objects': []}
            reports['{}@{}'.format(st['button'], scene)] = rep
            got = codes_of(rep)
            want = {e['name']: e for e in st.get('expected') or () if e['scene'] == scene}
            for o in mine:
                g = got.get(o['name'])
                status = 'error' if rep.get('status') == 'error' else ('absent' if g is None else
                                                                        ('fail' if g else 'pass'))
                e = want.get(o['name'])
                ok = None if e is None else (status == e['expect'] and (g or []) == e['codes'])
                rows.append({'button': st['button'], 'scene': scene, 'name': o['name'],
                             'expect': None if e is None else e['expect'],
                             'expected_codes': None if e is None else e['codes'],
                             'got': status, 'codes': g, 'ok': ok})
    (OUT / 'polygon_rows.json').write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding='utf-8')
    (OUT / 'polygon_reports.json').write_text(json.dumps(reports, indent=1, ensure_ascii=False, default=str),
                                              encoding='utf-8')
    bad = [r for r in rows if r['ok'] is False]
    assert not bad, bad
    return {'rows': len(rows), 'checked': sum(r['ok'] is not None for r in rows),
            'pass_rows': sum(r['got'] == 'pass' for r in rows), 'fail_rows': sum(r['got'] == 'fail' for r in rows)}


# ---- ucx.gap acceptance -----------------------------------------------------------------------------------------
GAPS_MM = (-2, 0, 1, 2, 4, 10, 40)


def _gap_scene(units):
    fresh(units)
    objs = []
    for i, g in enumerate(GAPS_MM):
        fam = 'G{}'.format(i)
        y = i * 3.0
        objs += [{'name': 'UCX_{}_01'.format(fam), 'extra': {'kind': 'box', 'min': [0, y, 0], 'max': [1, y + 1, 1],
                                                            'units': units}},
                 {'name': 'UCX_{}_02'.format(fam), 'extra': {'kind': 'box', 'min': [1 + g / 1000.0, y, 0],
                                                            'max': [2 + g / 1000.0, y + 1, 1], 'units': units}}]
    objs.append({'name': 'UCX_Other_001', 'extra': {'kind': 'box', 'min': [1, 30, 0], 'max': [2, 31, 1],
                                                     'units': units}})
    return build(objs)


def _pieces(nodes):
    out = {}
    for n, ref in zip(nodes, host.refs(nodes)):
        m = host.mesh(ref)
        out[str(n.name)] = gapc.piece(m['verts'], m['faces'])
    return out


def gap_acceptance():
    res = {}
    for units in ('meters', 'centimeters'):
        made = _gap_scene(units)
        nodes = list(made.values())
        emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
        before = emax.snapshot(nodes)
        prev = agr.edits_100('ucx.gap', 'preview', None, nodes)
        app = agr.edits_100('ucx.gap', 'apply', prev)
        assert emax.snapshot(nodes) == before, 'originals changed'
        copies = {c['source']: rt.maxOps.getNodeByHandle(c['handle']) for c in app['plan']['copies']}
        assert 'UCX_Other_001' not in copies and rt.getNodeByName('UCX_Other_001') is not None
        layer = rt.LayerManager.getLayerFromName('AGR_export')
        assert all(str(c.layer.name) == 'AGR_export' for c in copies.values())
        gaps = {}
        for i, g in enumerate(GAPS_MM):
            a, b = 'UCX_G{}_01'.format(i), 'UCX_G{}_02'.format(i)
            if g < 4:
                pa, pb = _pieces([copies[a], copies[b]]).values()
                got = gapc.separation(pa, pb)[0]
                assert abs(got - 0.004) <= 1e-5, (units, g, got)
                for k in (pa, pb):
                    assert agr._load_core('ucx_core.py', 'agr_tools_ucx_core').convexity(k['verts'], k['tris'])['ok']
            else:
                assert a not in copies, (a, 'a pair >= 4 mm was copied/changed')
                pa, pb = _pieces([made[a], made[b]]).values()
                got = gapc.separation(pa, pb)[0]
                assert abs(got - g / 1000.0) <= 1e-6, (units, g, got)
            gaps[str(g)] = round(got * 1000, 4)
        # repeat on the result (copies renamed to their source family): nothing to do
        rows = []
        for src, c in copies.items():
            m = host.mesh(host.refs([c])[0])
            rows.append({'handle': int(c.inode.handle), 'name': src, 'verts': m['verts'], 'tris': m['faces']})
        again = gapc.plan(rows, gapc.gap_options(None))
        assert again['pairs'] == [], again['pairs']
        # one undo record: one undo removes every copy, the originals stay
        n_copies = len(copies)
        rt.execute('max undo')
        left = [c for c in copies.values() if rt.isValidNode(c)]
        gone = [str(k) for k, n in made.items() if not rt.isValidNode(n)]
        assert not left and not gone, 'after one undo: copies left {}, originals gone {}'.format(len(left), gone)
        assert emax.snapshot(nodes) == before
        res[units] = {'gap_after_mm': gaps, 'copies': n_copies, 'status_apply': app['status'],
                      'pairs_fixed': prev['plan']['summary']['pairs_fixed'], 'undo_one_record': True,
                      'layer': None if layer is None else str(layer.name)}
    summary['checks']['ucx_gap_values'] = res
    diff = {g: abs(res['meters']['gap_after_mm'][g] - res['centimeters']['gap_after_mm'][g])
            for g in res['meters']['gap_after_mm']}
    assert max(diff.values()) <= 0.01, ('m != cm', diff)
    return res


# ---- light.export acceptance ------------------------------------------------------------------------------------
def _light_scene(stem='SM_TestAddr', photometric=True):
    fresh('meters')
    objs = [{'name': stem + '_Root', 'pos': [0, 0, 0], 'extra': {'kind': 'dummy'}}]
    spec = [('Spot_001', 'freeSpot', [0, 0, 3]), ('Spot_002', 'freeSpot', [3, 0, 3]), ('Spot_003', 'freeSpot', [6, 0, 3]),
            ('Omni_001', 'Omnilight', [0, 6, 3]), ('Omni_002', 'Omnilight', [0, 12, 3]),
            ('Spot_004', 'targetSpot', [9, 9, 4])]
    if photometric:
        spec.append(('Photo_001', 'Free_Light', [12, 0, 3]))
    for suffix, cls, pos in spec:
        extra = {'kind': 'light', 'light': cls}
        if cls == 'targetSpot':
            extra['aim'] = [11, 13, 0]
        objs.append({'name': stem + '_' + suffix, 'pos': pos, 'extra': extra, 'parent': stem + '_Root'})
    made = build(objs)
    return made


def light_acceptance():
    made = _light_scene()
    folder = OUT / 'light_out'
    folder.mkdir()
    old = folder / 'SM_TestAddr_Light.fbx'
    old.write_bytes(b'old light file: must survive')
    old_sha = hashlib.sha256(old.read_bytes()).hexdigest()
    prev = agr.edits_100('light.export', 'preview', options={'folder': str(folder)})
    assert prev['plan']['target'].endswith('SM_TestAddr_Light_v002.fbx'), prev['plan']['target']
    app = agr.edits_100('light.export', 'apply', prev)
    rb = app['plan']['readback']
    codes = codes_of(app)
    assert hashlib.sha256(old.read_bytes()).hexdigest() == old_sha
    assert rb['lights'] == 7 and rb['tops'] == 1 and rb['version'] == 7400, rb
    assert 'Omni' in rb['kinds'] and 'Spot' in rb['kinds'], rb
    assert codes['SM_TestAddr_Photo_001'] == ['light_type'], codes
    bad = {k: v for k, v in codes.items() if v and k != 'SM_TestAddr_Photo_001'}
    refuse_error = None
    try:
        p2 = agr.edits_100('light.export', 'preview', options={'folder': str(folder), 'on_exists': 'refuse'})
        agr.edits_100('light.export', 'apply', p2)
    except ValueError as exc:
        refuse_error = str(exc)[:200]
    assert refuse_error and 'перезапись' in refuse_error, refuse_error
    leftovers = sorted(p.name for p in folder.iterdir())
    return {'target': Path(app['plan']['target']).name, 'readback': {k: rb[k] for k in ('lights', 'tops', 'version',
                                                                                         'kinds', 'angles_deg')},
            'raw': rb['raw'], 'codes_not_clean': bad, 'old_sha_kept': True, 'refuse': refuse_error,
            'files': leftovers}


def light_package():
    """VPM set SM_TestAddr.fbx + SM_TestAddr_Light.fbx (Omni/Spot only) -> export.zip with validator (qa.package)."""
    made = _light_scene(photometric=False)
    folder = OUT / 'vpm_set'
    folder.mkdir()
    import pymxs
    with pymxs.undo(False):
        box = rt.Box(name='SM_TestAddr', length=4, width=4, height=3)
    rt.select([box])
    assert rt.exportFile(str(folder / 'SM_TestAddr.fbx'), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    prev = agr.edits_100('light.export', 'preview', options={'folder': str(folder)})
    app = agr.edits_100('light.export', 'apply', prev)
    # the rest of a VPM set (export.zip refuses a set without GeoJSON / PNG): placeholders, judged by the validator
    import struct
    import zlib

    def png(path):
        raw = bytes([0, 128, 128, 128])
        chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        sig = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        path.write_bytes(sig + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
                         + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    for kind in ('Diffuse', 'ERM', 'Normal'):
        png(folder / 'T_TestAddr_{}_1.1001.png'.format(kind))
    (folder / 'SM_TestAddr.geojson').write_text('{"type": "FeatureCollection", "features": []}', encoding='utf-8')
    zp = agr.edits_080('export.zip', 'preview', options={'folder': str(folder)})
    za = agr.edits_080('export.zip', 'apply', zp)
    stages = []
    for table in za['plan'].get('reports') or ():
        for s in table.get('stages') or ():
            stages.append({'id': s['id'], 'status': s['status'], 'non_pass': (s.get('non_pass') or [])[:4]})
    # placeholders fail V007 (1x1 PNG) and V011 (0 features) by design; only the light rules are judged here
    light_lines = [s for s in stages if any('light' in str(x).lower() for x in s['non_pass'])]
    assert 'SM_TestAddr_Light.fbx' in [m['name'] for a in zp['plan']['archives'] for m in a['members']]
    assert za['plan'].get('reports'), 'validator did not run on the archive'
    assert not light_lines, light_lines
    v012 = [st for st in stages if st['id'] == 'V012']
    assert v012 and v012[0]['status'] != 'fail', v012  # V012 holds the light FBX rules (light_findings)
    return {'v012': v012, 'light_apply': app['status'], 'light_codes': codes_of(app), 'zip_status': za['status'],
            'archives': za['plan'].get('archives') and [a['name'] for a in zp['plan']['archives']],
            'members': [m['name'] for a in zp['plan']['archives'] for m in a['members']],
            'marker': za['plan'].get('marker'), 'stages': stages, 'light_problems': light_lines}


# ---- pack.deliver -----------------------------------------------------------------------------------------------
def _passport_file(name):
    passport = {'schema': 1, 'project_id': 'PolyDeliver', 'source': {'path': 'x.max', 'level': 'C', 'class': 'max'},
                'normalization': {'units': 'm', 'up_axis': 'Z', 'scale': 1.0, 'origin_m': [0, 0, 0]},
                'stages': [{'id': i, 'status': 'done' if i < 9 else 'todo'} for i in range(10)]
                + [{'id': 'agent', 'status': 'todo'}], 'parts': [], 'openings': [], 'materials': [],
                'journal': {'path': 'journal.jsonl'}, 'agent_requests': [], 'questions': []}
    ppath = OUT / name
    ppath.write_text(json.dumps(passport, ensure_ascii=False), encoding='utf-8')
    return ppath


def _deliver_run(label, objs, options):
    fresh('meters')
    build(objs)
    save('deliver_' + label)
    folder = OUT / ('deliver_' + label)
    folder.mkdir()
    ppath = _passport_file('passport_' + label + '.json')
    opts = dict(options, folder=str(folder), passport=str(ppath))
    prev = agr.edits_100('pack.deliver', 'preview', None, None, opts)
    app = agr.edits_100('pack.deliver', 'apply', prev)
    run = Path(app['plan']['run_folder'])
    body = json.loads((run / 'deliver.json').read_text(encoding='utf-8'))
    pp = json.loads((run / 'passport.json').read_text(encoding='utf-8'))
    assert pp['stages'][9] == body['stage'] and body['stage']['status'] in ('done', 'blocked')
    assert (body['stage']['status'] == 'blocked') == bool(body['blockers'])
    assert json.loads(ppath.read_text(encoding='utf-8'))['stages'][9]['status'] == 'todo', 'passport overwritten'
    return {'preview_status': prev['status'], 'preview_steps': {r['id']: r['status'] for r in prev['plan']['steps']},
            'preview_blockers': [b[:220] for b in prev['plan']['blockers']], 'apply_status': app['status'],
            'apply_steps': {r['id']: r['status'] for r in app['plan']['steps']},
            'apply_errors': {r['id']: r.get('error') or r.get('top') for r in app['plan']['steps']
                             if r['status'] in ('error', 'fail')},
            'stage': body['stage'], 'files': sorted(str(p.relative_to(run)) for p in run.rglob('*')),
            'run_folder': run.name}


def deliver():
    st = next(s for s in FRAG['stations'] if s['button'] == 'pack.deliver')
    out = {}
    # (a) the station: a touching UCX pair -> stage 9 blocked by ucx.gap, only deliver.json + passport copy
    out['station'] = a = _deliver_run('station', st['objects'], st.get('options') or {})
    assert a['stage']['status'] == 'blocked' and any(b.startswith('ucx.gap') for b in a['stage']['blockers'])
    assert a['files'] == ['deliver.json', 'passport.json'], a['files']
    # (b) every check on (only qa.sintez skipped: no SINTEZ table on a synthetic scene): the full blocker list
    full = {'skip': {'qa.sintez': 'нет таблицы SINTEZ на синтетике'}}
    out['full_checks'] = _deliver_run('full', st['objects'], full)
    # (c) no blocker (UCX 10 mm apart): the files are written into the run folder
    objs = []
    for o in st['objects']:
        o = json.loads(json.dumps(o))
        if o['name'] == 'UCX_PolyDeliver_02':
            o['extra']['min'][0] += 0.01
            o['extra']['max'][0] += 0.01
        objs.append(o)
    out['files'] = c = _deliver_run('files', objs, st.get('options') or {})
    assert c['preview_blockers'] == [], c['preview_blockers']
    assert 'SM_PolyDeliver_Light.fbx' in c['files'], c['files']
    return out


def journal():
    lines = []
    for p in (OUT / 'journal').glob('*.jsonl'):
        lines += [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines()]
    tools = sorted({x['tool'] for x in lines})
    assert {'ucx.gap', 'light.export', 'pack.deliver'} <= set(tools), tools
    return {'lines': len(lines), 'tools': tools}


check('polygon_rows', polygon)
check('ucx_gap_acceptance', gap_acceptance)
check('light_export_acceptance', light_acceptance)
check('light_export_package', light_package)
check('pack_deliver', deliver)
check('journal', journal)
rt.resetMaxFile(rt.Name('noPrompt'))
print('DELIVER_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native stage 9 failed: see summary.json'
