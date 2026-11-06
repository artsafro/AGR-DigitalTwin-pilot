"""new-case: #1024 branch M native run of vpm.build / udim.rescale / udim.distortion in locked batch Max 2024.

Run via the lab DCC runner (script_in_place) on DISPOSABLE synthetic scenes; AGR_TEST_OUTPUT names a NEW directory,
AGR_TEST_PACKAGE the built MZP (installed into OUT, no user folder touched). Nothing is saved.

Checks (lab L09 minimal acceptance, docs/experiments/vpm.build.md, udim.rescale.md, udim.distortion.md):
* vpm.build on the L09 facade (test-polygon/stations/M_build.py: 4 walls, one at 30 degrees, a bay, openings with
  reveals, panels id 3, brick id 7, glass id 31) in metres, in centimetres and at 2 345 678 m, input projected and
  «artist»: read-back seam 0 px on internal and chain edges, texel +-1 %, UDIM 1001.. per mesh (body 1001-1002,
  glass 1001), 0 triangles across a tile line; the working object (Editable_Poly + modifier) is unchanged and its
  stack not collapsed; one undo removes the run; the file step writes vpm_table.json into a NEW folder; ~20 000
  faces timed; an id >= 1001 fails closed.
* udim.rescale: plane 256 -> 512 px/m in m and cm (512 +- 1 %), around UV (0, 0), polygon selection scope keeps the
  element whole, the material and its bitmap untouched (md5, same instance), copy + one undo; no UV -> finding.
* udim.distortion: the 16-quad plane (5 stretched, 3 sheared) as Editable_Mesh, Editable_Poly, under Unwrap_UVW and
  in cm: exactly the 8 polygons; a Box primitive does not throw; selection and sub-object level unchanged.
* the M stations of the live polygon (polygon_all built from polygon_core.load_catalog()): every expected row.
"""
import hashlib
import importlib.util
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
TILE, STEP = 4096, 3.6
TEXEL = TILE / STEP


def check(name, fn):
    t = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    print('VPM_NATIVE', name, 'ok' if name in summary['checks'] else 'ERROR', round(time.time() - t, 1), 's')


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
MB = load(ROOT / 'test-polygon' / 'stations' / 'M_build.py', 'agr_polygon_M_build_native')
summary['runtime_version'] = agr.VERSION


def fresh(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def mesh_hash(n):
    return agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot([n])[0]


def stack(n):
    return [str(rt.classOf(n.baseObject))] + [str(rt.classOf(m)) for m in n.modifiers]


def facade_node(name, units='meters', pos=(0.0, 0.0, 0.0), artist=False, poly=False, modifier=False, **kw):
    mesh = MB.facade(**kw)
    if artist:
        mesh = MB.artist_uv(mesh)
    n = MB.build_node(rt, mesh, name)
    k = 1.0 / {'meters': 1.0, 'centimeters': 0.01}[units]
    n.position = rt.point3(*[c * k for c in pos])
    if poly:
        rt.convertToPoly(n)
    if modifier:
        rt.addModifier(n, rt.Uvwmap())  # a stack the build must not collapse (it re-projects on a copy)
    return n


def build(n, options):
    pre = agr.edits_100('vpm.build', 'preview', nodes=[n], options=options)
    return pre, agr.edits_100('vpm.build', 'apply', pre, nodes=[n])


def vpm_rows(rep):
    return [{k: r.get(k) for k in ('object', 'part', 'tiles', 'udim_table', 'seam_internal_max_px',
                                   'seam_chain_max_px', 'crossing_pieces', 'texel_px_per_m', 'readback', 'faces_in',
                                   'out_tris')} for r in rep['plan']['done']]


def assert_vpm_ok(rep):
    assert rep['status'] == 'pass', [o['findings'] for o in rep['objects']]
    parts = {r['part']: r for r in rep['plan']['done']}
    assert parts['body']['readback']['tiles'] == [1001, 1002], parts['body']['readback']
    if 'glass' in parts:
        assert parts['glass']['readback']['tiles'] == [1001], parts['glass']['readback']
    for r in parts.values():
        rb = r['readback']
        assert rb['seam_internal_max_px'] <= 0.01 and rb['seam_chain_max_px'] <= 0.01, rb
        assert rb['crossing'] == 0, rb
        for lo, hi in rb['texel_px_per_m'].values():
            assert abs(lo / TEXEL - 1) <= 0.01 and abs(hi / TEXEL - 1) <= 0.01, rb['texel_px_per_m']
    return parts


def vpm_metres():
    fresh()
    n = facade_node('BODY_Facade_001', poly=True, modifier=True)
    before, st = mesh_hash(n), stack(n)
    t = time.time()
    pre, app = build(n, {'glass_ids': [31], 'out_dir': str(OUT / 'vpm_out')})
    dt = time.time() - t
    parts = assert_vpm_ok(app)
    assert mesh_hash(n) == before and stack(n) == st, 'working object changed / stack collapsed'
    copies = app['plan']['copies']
    assert len(copies) == 2 and all(rt.getNodeByName(c) is not None for c in copies), copies
    glass = rt.getNodeByName([c for c in copies if '_glass_' in c][0])
    assert sorted({int(rt.getFaceMatID(glass.mesh, i)) for i in range(1, int(glass.mesh.numfaces) + 1)}) == [31]
    table = json.loads(Path(app['plan']['files'][0]['path']).read_text(encoding='ascii'))
    assert [m['udim_table'] for m in table['meshes']] == [{'3': 1001, '7': 1002}, {'31': 1001}], table['meshes']
    again = agr.edits_100('vpm.build', 'apply', agr.edits_100('vpm.build', 'preview', nodes=[n],
                                                             options={'glass_ids': [31], 'out_dir': str(OUT / 'vpm_out')}),
                          nodes=[n])
    assert again['plan']['out_dir'] != app['plan']['out_dir'], 'file step overwrote the folder'
    rt.execute('max undo')
    gone = [c for c in again['plan']['copies'] if rt.getNodeByName(c) is not None]
    assert not gone, 'one undo did not remove the run: ' + repr(gone)
    assert rt.isValidNode(n) and mesh_hash(n) == before
    return {'rows': vpm_rows(app), 'seconds': round(dt, 2), 'steps': app['plan']['steps'],
            'out_dir': app['plan']['out_dir'], 'second_out_dir': again['plan']['out_dir'], 'stack_kept': st,
            'renumber': app['plan']['renumber'], 'fold_max_px': parts['body']['readback']['seam_fold_max_px']}


def vpm_units_far_artist():
    out = {}
    for label, units, pos, artist in (('cm', 'centimeters', (0, 0, 0), False),
                                      ('far_2345678m', 'meters', (2345678.0, 1234567.0, 0.0), False),
                                      ('artist', 'meters', (0, 0, 0), True)):
        fresh(units)
        n = facade_node('BODY_Facade_' + label, units=units, pos=pos, artist=artist)
        _pre, app = build(n, {'glass_ids': [31], 'grid_zero_m': list(pos)})
        assert_vpm_ok(app)
        out[label] = vpm_rows(app)
    ref = summary['checks'].get('vpm_build_metres', {}).get('rows')
    if ref:
        for label in ('cm', 'far_2345678m'):
            for a, b in zip(out[label], ref):
                assert a['tiles'] == b['tiles'] and a['out_tris'] == b['out_tris'], (label, a, b)
    return out


def vpm_fail_closed_and_empty():
    fresh()
    n = facade_node('BODY_Bad_001')
    mid = [int(rt.getFaceMatID(n, i)) for i in range(1, int(n.numfaces) + 1)]
    for i, m in enumerate(mid, 1):
        if m == 7:
            rt.setFaceMatID(n, i, 1005)
    pre = agr.edits_100('vpm.build', 'preview', nodes=[n], options={'glass_ids': [31]})
    codes = sorted({f['code'] for o in pre['objects'] for f in o['findings']})
    assert pre['status'] == 'fail' and codes == ['id_range'], codes
    try:
        agr.edits_100('vpm.build', 'apply', pre, nodes=[n])
        raise AssertionError('apply of a failing build made copies')
    except ValueError as exc:
        refused = str(exc)[:120]
    rt.clearSelection()
    try:
        agr.edits_100('vpm.build', 'preview', nodes=None)
        raise AssertionError('empty selection passed')
    except ValueError as exc:
        empty = str(exc)[:120]
    return {'codes': codes, 'apply_refused': refused, 'empty': empty}


def vpm_20000_faces():
    fresh()
    n = facade_node('BODY_Big_001', height=22.0, col=0.6, floor=1.0, margin=0.15)
    faces = int(n.mesh.numfaces)
    t = time.time()
    pre = agr.edits_100('vpm.build', 'preview', nodes=[n], options={'glass_ids': [31]})
    t1 = time.time()
    app = agr.edits_100('vpm.build', 'apply', pre, nodes=[n])
    t2 = time.time()
    assert_vpm_ok(app)
    return {'faces': faces, 'preview_s': round(t1 - t, 2), 'apply_s': round(t2 - t1, 2),
            'within_10s_preview': (t1 - t) <= 10.0}


def plane_node(name, units='meters', kind='plane16', poly=False, unwrap=False):
    mesh = {'plane16': MB.plane16(), 'clean': MB.plane16(stretched=(), sheared=()),
            'nouv': dict(MB.plane16(), uvs=None, face_uvs=None)}[kind]
    n = MB.build_node(rt, mesh, name)
    if poly:
        rt.convertToPoly(n)
    if unwrap:
        rt.addModifier(n, rt.Unwrap_UVW())
    return n


def rescale():
    out = {}
    for units in ('meters', 'centimeters'):
        fresh(units)
        n = plane_node('SM_Plane_' + units, units, 'clean', poly=True)
        bmp_path = OUT / ('map_' + units + '.png')
        b = rt.bitmap(64, 64, color=rt.color(200, 100, 50), filename=str(bmp_path))
        rt.save(b)
        rt.close(b)
        md5 = hashlib.md5(bmp_path.read_bytes()).hexdigest()
        mat = rt.StandardMaterial(name='M_Plane')
        mat.diffuseMap = rt.Bitmaptexture(filename=str(bmp_path))
        n.material = mat
        rt.polyop.setFaceSelection(n, rt.execute('#{1..2}'))  # scope: 2 polygons; their UV element moves whole
        before = mesh_hash(n)
        pre = agr.edits_100('udim.rescale', 'preview', nodes=[n], options={'target_px_per_m': 512})
        app = agr.edits_100('udim.rescale', 'apply', pre, nodes=[n])
        assert app['status'] == 'pass', app['objects']
        row = app['plan']['done'][0]
        assert abs(row['readback_px_per_m'] / 512 - 1) <= 0.01, row
        assert row['scope'] == 'selection' and row['faces_scope'] == 4, row
        assert mesh_hash(n) == before and n.material == mat and str(mat.diffuseMap.filename) == str(bmp_path)
        assert hashlib.md5(bmp_path.read_bytes()).hexdigest() == md5, 'map rewritten'
        assert not list(bmp_path.parent.glob('map_*_id*.png')), 'GeoAGR-like _id<N> files'
        c = rt.getNodeByName(app['plan']['copies'][0])
        assert c.material != mat, 'the copy shares the original material instance'
        rt.execute('max undo')
        assert rt.getNodeByName(app['plan']['copies'][0]) is None, 'one undo did not remove the copy'
        out[units] = {k: row[k] for k in ('scale', 'before_px_per_m', 'after_px_per_m', 'readback_px_per_m',
                                          'faces_scope', 'faces_scaled', 'elements', 'scope', 'unit_m')}
    assert abs(out['meters']['scale'] - out['centimeters']['scale']) < 1e-9, out
    fresh()
    n = plane_node('SM_NoUV', kind='nouv')
    pre = agr.edits_100('udim.rescale', 'preview', nodes=[n], options={'target_px_per_m': 512})
    out['no_uv'] = sorted({f['code'] for o in pre['objects'] for f in o['findings']})
    assert pre['status'] == 'fail' and out['no_uv'] == ['no_uv'], pre
    return out


def distortion():
    out = {}
    want = {'texel_scale': [1, 6, 9, 12, 14], 'anisotropy': [1, 3, 6, 8, 9, 12, 14, 15]}
    for label, units, poly, unwrap in (('mesh_m', 'meters', False, False), ('poly_m', 'meters', True, False),
                                       ('unwrap_m', 'meters', True, True), ('poly_cm', 'centimeters', True, False)):
        fresh(units)
        n = plane_node('SM_Dist_' + label, units, 'plane16', poly, unwrap)
        rt.select(n)
        sel_before = [str(x.name) for x in rt.selection]
        level = int(rt.subObjectLevel) if rt.subObjectLevel is not None else None
        h0 = mesh_hash(n)
        rep = agr.edits_100('udim.distortion', 'preview', nodes=[n])
        got = {f['code']: f['ids'] for o in rep['objects'] for f in o['findings']}
        expect = want if (poly and not unwrap) else {k: sorted({t for f in v for t in (2 * f - 1, 2 * f)}) for k, v in want.items()}
        assert got == expect, (label, got)
        assert [str(x.name) for x in rt.selection] == sel_before and mesh_hash(n) == h0
        assert (int(rt.subObjectLevel) if rt.subObjectLevel is not None else None) == level
        out[label] = {'codes': {k: len(v) for k, v in got.items()}, 'unit': rep['plan']['done'][0]['unit'],
                      'target': rep['plan']['done'][0]['target_px_per_m']}
    fresh()
    box = rt.Box(name='SM_Box_Prim', length=2, width=2, height=2)
    rt.select(box)
    rep = agr.edits_100('udim.distortion', 'preview', nodes=[box])
    out['box_primitive'] = {'status': rep['status'], 'codes': sorted({f['code'] for o in rep['objects']
                                                                       for f in o['findings']})}
    return out


def polygon_rows():
    """My stations of the live polygon: build polygon_all from load_catalog() and press every M row."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    sys.path.insert(0, str(ROOT / 'src'))  # polygon_core.load_catalog reads dt_ai (uv_nudge)
    import polygon_core as core
    cat = OUT / 'catalog.json'
    pre = os.environ.get('AGR_M_CATALOG')  # load_catalog() written by the uv env before the job (dt_ai deps)
    text = Path(pre).read_text(encoding='utf-8') if pre else json.dumps(core.load_catalog(), ensure_ascii=False)
    cat.write_text(text, encoding='utf-8')
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    import build_scene
    fresh()
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    frag = json.loads((ROOT / 'test-polygon' / 'stations' / 'M.json').read_text(encoding='utf-8'))
    rows, bad = [], []
    for st in frag['stations']:
        for exp in st['expected']:
            n = rt.getNodeByName(exp['name'])
            assert n is not None, exp['name']
            try:
                rep = agr.edits_100(st['button'], 'preview', nodes=[n], options=st.get('options') or {})
                status = rep['status']
                codes = sorted({f['code'] for o in rep['objects'] for f in o['findings']})
            except Exception as exc:  # noqa: BLE001 - an expected `error` row
                status, codes = 'error', [type(exc).__name__ + ': ' + str(exc)[:80]]
            ok = status == exp['expect'] and (status != 'fail' or codes == sorted(exp['codes']))
            rows.append({'station': st['button'], 'object': exp['name'], 'expect': exp['expect'],
                         'got': status, 'codes': codes, 'match': ok})
            if not ok:
                bad.append(rows[-1])
    assert not bad, bad
    return rows


check('vpm_build_metres', vpm_metres)
check('vpm_build_cm_far_artist', vpm_units_far_artist)
check('vpm_build_fail_closed', vpm_fail_closed_and_empty)
check('vpm_build_20000_faces', vpm_20000_faces)
check('udim_rescale', rescale)
check('udim_distortion', distortion)
check('polygon_rows_M', polygon_rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('VPM_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native branch M failed: see summary.json'
