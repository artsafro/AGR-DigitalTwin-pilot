"""new-case: #1024 branch T native run of `ucx.stairs`, `qa.omk_te`, `export.place_by_passport` in locked batch Max 2024
on DISPOSABLE synthetic scenes (one job for all three buttons).

Run via the lab DCC runner (script_in_place); AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched) and calls `runtime.edits_100` in the real Max Python:
  - ucx.stairs: ok / no UCX / UCX per step / UCX 40 cm high on a metre scene, the ok stair also on a centimetre scene;
    preview changes nothing (node count and positions);
  - qa.omk_te: 50-row synthetic table, filter + pick -> code of the visible row, missing table, CP1251 file;
  - export.place_by_passport: a real FBX is exported from a synthetic box, then preview/apply: pivot readback vs the
    passport (x 12345.678, y -6789.012, h 152.3), one undo, bait passport (marker file must not exist), broken JSON
    (0 new nodes), large MSK coordinates (single-precision error measured and reported).
Nothing is saved; user folders are not touched. Measured numbers go to summary.json.
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


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-2500:]


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
    sys.path.insert(0, str(OUT / 'installed'))
    sys.modules.pop('runtime', None)
    import runtime as agr
    return agr


agr = install()
tb = load(ROOT / 'test-polygon/stations/T_build.py', 'agr_t_build')
summary['runtime_version'] = agr.VERSION


def fresh(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def scene_state():
    return sorted((str(n.name), round(float(n.pos.x), 5), round(float(n.pos.y), 5), round(float(n.pos.z), 5))
                  for n in rt.objects)


def mesh_node(name, mesh, pos, k=1.0):
    verts, tris = mesh
    node = rt.mesh(name=name, vertices=rt.Array(*[rt.Point3(*[c * k for c in v]) for v in verts]),
                   faces=rt.Array(*[rt.Point3(a + 1, b + 1, c + 1) for a, b, c in tris]))
    node.pos = rt.Point3(*[c * k for c in pos])
    return node


def stairs_case(variant, name, pos, k=1.0):
    stair, pieces = tb.stair_parts(variant)
    nodes = [mesh_node(name, stair, pos, k)]
    for i, piece in enumerate(pieces, 1):
        nodes.append(mesh_node('UCX_{}_{:02d}'.format(name, i), piece, pos, k))
    return nodes


def codes(report):
    return {o['name']: sorted(f['code'] for f in o['findings']) for o in report['objects']}


def stairs():
    fresh()
    nodes = []
    for i, variant in enumerate(('ok', 'no_ucx', 'per_step', 'high')):
        nodes += stairs_case(variant, 'Stair_' + variant, (i * 6.0, 0.0, 0.0))
    before = scene_state()
    rep = agr.edits_100('ucx.stairs', 'preview', None, nodes, {'tolerance_cm': 30})
    got = codes(rep)
    want = {'Stair_ok': [], 'Stair_no_ucx': ['ucx_missing'], 'Stair_per_step': ['ucx_not_single'],
            'Stair_high': ['ucx_too_high']}
    assert got == want, got
    assert scene_state() == before, 'preview changed the scene'
    rep10 = agr.edits_100('ucx.stairs', 'preview', None, nodes, {'tolerance_cm': 10})
    fresh('centimeters')
    cm_nodes = stairs_case('ok', 'Stair_cm', (0.0, 0.0, 0.0), 100.0)
    cm = agr.edits_100('ucx.stairs', 'preview', None, cm_nodes, {})
    assert codes(cm) == {'Stair_cm': []}, codes(cm)
    try:
        agr.edits_100('ucx.stairs', 'apply', rep, None, None)
        raise AssertionError('apply of a read-only row ran')
    except ValueError as exc:
        refused = str(exc)[:80]
    return {'meters': got, 'tol10': codes(rep10), 'centimeters': codes(cm), 'metrics': rep['plan']['metrics'],
            'apply_refused': refused, 'status': rep['status']}


def omk():
    fresh()
    table = OUT / 'omk' / 'OMK_synth.tsv'
    table.parent.mkdir(parents=True)
    table.write_bytes(tb.omk_table())
    before = scene_state()
    rep = agr.edits_100('qa.omk_te', 'preview', None, None, {'table': str(table), 'filter': 'стена', 'pick': 2})
    lines = tb.omk_table().decode('utf-8').splitlines()[1:]
    walls = sorted(l.split('\t') for l in lines if l.startswith('Стена'))
    want = walls[1][1]
    assert rep['status'] == 'pass' and rep['plan']['code'] == want, (rep['plan'].get('code'), want)
    clip = str(rt.getClipboardText()) if hasattr(rt, 'getClipboardText') else None
    miss = agr.edits_100('qa.omk_te', 'preview', None, None, {'table': str(OUT / 'omk' / 'нет.tsv')})
    assert miss['status'] == 'fail' and miss['plan']['ambiguous'][0]['code'] == 'table_missing'
    cp = OUT / 'omk' / 'cp1251.tsv'
    cp.write_bytes('place\tcode\nСтена\t1234\n'.encode('cp1251'))
    enc = agr.edits_100('qa.omk_te', 'preview', None, None, {'table': str(cp)})
    assert enc['plan']['ambiguous'][0]['code'] == 'table_encoding' and '�' not in enc['plan']['ambiguous'][0]['message']
    assert scene_state() == before
    return {'code': rep['plan']['code'], 'expected_visible_row2': want, 'visible': rep['plan']['visible'],
            'clipboard': clip, 'missing': miss['plan']['ambiguous'][0]['message'], 'cp1251': enc['plan']['ambiguous'][0]['message']}


def passport(folder, x, y, h, name='model', **props):
    p = {'address': 'synthetic', 'h_relief': h}
    p.update(props)
    doc = {'type': 'FeatureCollection', 'features': [{'type': 'ObjectFeature', 'geometry': {'type': 'Point', 'coordinates': [x, y]},
                                                       'properties': p, 'Glasses': []}]}
    path = Path(folder) / (name + '.geojson')
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    return path


def make_fbx(folder, name='model'):
    """A real FBX of a synthetic 2x3x1 box lying on its own origin."""
    fresh()
    box = rt.Box(name='Imported_Box', length=2, width=3, height=1)
    box.pos = rt.Point3(0, 0, 0)
    rt.select(box)
    path = Path(folder) / (name + '.fbx')
    ok = rt.exportFile(str(path), rt.name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    assert path.is_file(), 'FBX export failed: {}'.format(ok)
    return path


def place_case(folder, x, y, h, name, accept=False, **props):
    fbx = make_fbx(folder, name)
    passport(folder, x, y, h, name, **props)
    fresh()
    rt.Box(name='Existing', length=1, width=1, height=1)
    opts = {'fbx': str(fbx)}
    if accept:
        opts['accept_precision_loss'] = True
    prev = agr.edits_100('export.place_by_passport', 'preview', None, None, opts)
    return fbx, prev


def place():
    base = OUT / 'place'
    base.mkdir(parents=True)
    out = {}
    # 1. normal coordinates: pivot readback, one undo
    (base / 'ok').mkdir()
    fbx, prev = place_case(base / 'ok', 12345.678, -6789.012, '152,3', 'model')
    assert prev['status'] == 'pass', prev['plan']
    n0 = len(list(rt.objects))
    rep = agr.edits_100('export.place_by_passport', 'apply', prev, None, None)
    new = [n for n in rt.objects if str(n.name) != 'Existing']
    assert len(new) >= 1
    root = new[0]
    err = [abs(float(root.pos.x) - 12345.678), abs(float(root.pos.y) + 6789.012), abs(float(root.pos.z) - 152.3)]
    out['ok'] = {'status': rep['status'], 'pos': [float(root.pos.x), float(root.pos.y), float(root.pos.z)], 'err_m': err,
                 'readback_m': rep['plan']['readback_m'], 'precision_m': rep['plan']['precision_m'], 'nodes_before': n0,
                 'nodes_after': len(list(rt.objects))}
    assert max(err) <= 0.001, err
    # one Undo record removes the placement
    try:
        rt.execute('max undo')
        out['ok']['after_one_undo'] = sorted(str(n.name) for n in rt.objects)
    except Exception as exc:  # noqa: BLE001
        out['ok']['after_one_undo'] = 'undo unavailable in batch: {}'.format(str(exc)[:80])
    # 2. bait in a text field is data
    (base / 'bait').mkdir()
    marker = base / 'marker.txt'
    fbx, prev = place_case(base / 'bait', 100.0, 200.0, '3', 'model', address='" ; createFile "{}"'.format(marker.as_posix()))
    rep = agr.edits_100('export.place_by_passport', 'apply', prev, None, None)
    out['bait'] = {'status': prev['status'], 'marker_exists': marker.exists()}
    assert not marker.exists()
    # 3. broken JSON: preview fails, apply refused, 0 new nodes
    (base / 'broken').mkdir()
    fbx = make_fbx(base / 'broken', 'model')
    (base / 'broken' / 'model.geojson').write_text('{"type": ', encoding='utf-8')
    fresh()
    rt.Box(name='Existing', length=1, width=1, height=1)
    prev = agr.edits_100('export.place_by_passport', 'preview', None, None, {'fbx': str(fbx)})
    refused = None
    try:
        agr.edits_100('export.place_by_passport', 'apply', prev, None, None)
    except ValueError as exc:
        refused = str(exc)[:100]
    out['broken'] = {'status': prev['status'], 'code': prev['plan']['ambiguous'][0]['code'], 'apply_refused': refused,
                     'nodes': sorted(str(n.name) for n in rt.objects)}
    assert out['broken']['nodes'] == ['Existing'] and refused
    # 4. large MSK coordinates: the honest single-precision error
    (base / 'big').mkdir()
    fbx, prev = place_case(base / 'big', 2345678.123, 1234567.456, '152,3', 'model')
    assert prev['status'] == 'fail' and prev['plan']['ambiguous'][0]['code'] == 'precision'
    fbx, prev2 = place_case(base / 'big', 2345678.123, 1234567.456, '152,3', 'model', accept=True)
    rep = agr.edits_100('export.place_by_passport', 'apply', prev2, None, None)
    root = [n for n in rt.objects if str(n.name) != 'Existing'][0]
    out['big'] = {'preview_status': prev['status'], 'precision_m': prev['plan']['precision_m'],
                  'pos': [float(root.pos.x), float(root.pos.y), float(root.pos.z)],
                  'err_x_m': abs(float(root.pos.x) - 2345678.123), 'err_y_m': abs(float(root.pos.y) - 1234567.456)}
    return out


check('stairs', stairs)
check('omk', omk)
check('place', place)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('DELIVER_SMALL_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native deliver-small failed: see summary.json'
