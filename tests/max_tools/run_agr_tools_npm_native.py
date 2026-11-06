"""new-case: #1024 branch P native run of npm.build (1.0.22) and atlas.facade_strip (1.0.23) in locked batch Max 2024.

Run via the lab DCC runner (script_in_place) on DISPOSABLE synthetic scenes; AGR_TEST_OUTPUT names a NEW directory,
AGR_TEST_PACKAGE the built MZP (installed into OUT, no user folder touched). Nothing is saved.

Checks (lab L11 minimal acceptance, docs/experiments/npm.build.md; #1024 §1.0.22, «редакция 1» §13):
* npm.build on the VPM of branch M (vpm.build of the L09 facade: body ids 3/7 in UDIM 1001/1002, glass id 31 in its
  own object) with coordinate-encoded PNG maps, in metres and centimetres: texel 39 px/m +-1 % on every texture ID
  (read back from the NPM copy), rigid transfer (table returns the VPM UV), one NPM object with the glass faces,
  atlas 24-bit RGB <= 2048, the atlas pixels follow the UV (<= 1 px on the coordinate maps), plug and glass colours
  exact, npm_table.json next to the atlas, VPM objects and maps unchanged, one undo removes the run, a second run
  writes a NEW folder, tex.check / atlas.sets_count on the NPM copy; a missing map refuses (no file written).
* atlas.facade_strip on 4 strips + 2 unique panels with PNG maps: texel +-1 %, UV in cells, originals unchanged.
* the P stations of the live polygon (polygon_all from polygon_core.load_catalog()): every expected row.
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
TEXEL = 39.0


def check(name, fn):
    t = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    print('NPM_NATIVE', name, 'ok' if name in summary['checks'] else 'ERROR', round(time.time() - t, 1), 's')


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
MB = load(ROOT / 'test-polygon' / 'stations' / 'M_build.py', 'agr_polygon_M_build_native_p')
PB = load(ROOT / 'test-polygon' / 'stations' / 'P_build.py', 'agr_polygon_P_build_native')
TQ = agr._load_core('texqa_core.py', 'agr_tools_texqa_core')
NC = agr._load_core('npm_core.py', 'agr_tools_npm_core_native')
summary['runtime_version'] = agr.VERSION
MAPS = OUT / 'maps'
MAPS.mkdir()


def coord_png(path, w, h, tint=0):
    """R = x, G = y (< 256), B = tint: the atlas pixel tells which source pixel it came from."""
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes((x, y, tint))
    Path(path).write_bytes(TQ.write_png(w, h, bytes(px), 3))
    return str(path)


PANEL_MAP = coord_png(MAPS / 'T_Panel_Diffuse.png', 128, 128, 10)
BRICK_MAP = coord_png(MAPS / 'T_Brick_Diffuse.png', 96, 96, 200)


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def fresh(units='meters'):
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name(units)
    rt.units.SystemScale = 1.0


def mesh_hash(n):
    return agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot([n])[0]


def multi(name, mats):
    ids = sorted(mats)
    mm = rt.MultiMaterial(numsubs=len(ids))
    mm.name = name
    for i, mid in enumerate(ids):
        sub = rt.StandardMaterial(name='M_lib_{}'.format(mid))
        spec = mats[mid]
        if isinstance(spec, str):
            sub.diffuseMap = rt.Bitmaptexture(filename=spec)
        else:
            sub.diffuse = rt.color(*spec)
        mm.materialList[i] = sub
        mm.materialIDList[i] = mid
    return mm


def make_vpm(units, tag):
    """vpm.build (branch M) of the small L09 facade -> body + glass VPM copies with Multi/Sub materials."""
    fresh(units)
    small = [(0.0, 0.0), (3.6, 0.0), (3.6, 3.6), (0.0, 3.6)]
    n = MB.build_node(rt, MB.facade(height=6.0, footprint=small, brick_from=3.0), 'SM_Npm{}_Main'.format(tag))
    pre = agr.edits_100('vpm.build', 'preview', nodes=[n], options={'glass_ids': [31], 'out_dir': str(OUT / ('vpm_' + tag))})
    app = agr.edits_100('vpm.build', 'apply', pre, nodes=[n])
    assert app['status'] == 'pass', app['objects']
    copies = [rt.getNodeByName(c) for c in app['plan']['copies']]
    table = json.loads(Path(app['plan']['files'][0]['path']).read_text(encoding='ascii'))
    for c in copies:
        if '_glass_' in str(c.name):
            c.material = multi('M_glass', {31: (70, 90, 110)})
        else:
            c.material = multi('M_body', {3: PANEL_MAP, 7: BRICK_MAP})
    rt.delete(n)
    return copies, NC.udim_table_of(table, [str(c.name) for c in copies])


def uv_state(n):
    m = n.mesh
    return [(round(float(rt.meshop.getMapVert(m, 1, i).x), 7), round(float(rt.meshop.getMapVert(m, 1, i).y), 7))
            for i in range(1, int(rt.meshop.getNumMapVerts(m, 1)) + 1)]


def atlas_pixels_follow_uv(app, table_rows):
    """Decode the atlas; at the centre of 40 NPM UV corners of texture IDs the pixel's R/G must be the source pixel
    the table maps it to (<= 1 px, periodic)."""
    files = {f['kind']: f['path'] for f in app['plan']['files']}
    pic = TQ.read_png(Path(files['diffuse']).read_bytes())
    rgb, size = pic.rgb(), pic.w
    worst, n = 0.0, 0
    for row in table_rows:
        if row['kind'] != 'texture':
            continue
        w = 128 if row['library_id'] == 3 else 96
        u0, v0, u1, v1 = row['region']
        for i in range(1, 6):
            for j in range(1, 5):
                au, av = u0 + (u1 - u0) * i / 6.0, v0 + (v1 - v0) * j / 5.0
                x, y = int(au * size), int((1 - av) * size)
                cu, cv = (x + 0.5) / size, 1 - (y + 0.5) / size
                su, sv = (cu - row['shift'][0]) / row['scale'][0], (cv - row['shift'][1]) / row['scale'][1]
                want_x, want_y = (su * w) % w, (-sv * w) % w
                got = rgb[(y * size + x) * 3:(y * size + x) * 3 + 2]
                dx = abs(got[0] + 0.5 - want_x)
                dy = abs(got[1] + 0.5 - want_y)
                worst = max(worst, min(dx, w - dx), min(dy, w - dy))
                n += 1
    return round(worst, 3), n


def npm_build(units='meters', tag='m'):
    copies, udim = make_vpm(units, tag)
    before = {str(c.name): (mesh_hash(c), uv_state(c)) for c in copies}
    maps_before = {p: md5(p) for p in (PANEL_MAP, BRICK_MAP)}
    opts = {'udim_table': udim, 'out_dir': str(OUT / ('npm_' + tag))}
    t = time.time()
    pre = agr.edits_100('npm.build', 'preview', nodes=copies, options=opts)
    assert pre['status'] == 'pass', pre['objects']
    app = agr.edits_100('npm.build', 'apply', pre, nodes=copies)
    dt = time.time() - t
    assert app['status'] == 'pass', app['objects']
    npm_names = app['plan']['copies']
    assert len(npm_names) == 1, npm_names
    npm = rt.getNodeByName(npm_names[0])
    ids = sorted({int(rt.getFaceMatID(npm.mesh, i)) for i in range(1, int(npm.mesh.numfaces) + 1)})
    assert ids == [3, 7, 31], ids  # glass joined the NPM object, ids kept
    rb = app['plan']['readback'][0]
    for t_ in rb['texel_px_per_m'].values():
        assert abs(t_ / TEXEL - 1) <= 0.01, rb
    assert rb['rigid_max_uv'] <= 1e-5 and rb['outside_cell'] == 0, rb
    files = {f['kind']: f['path'] for f in app['plan']['files']}
    w, h, depth, ctype, alpha = agr._load_core('checks_core.py', 'agr_tools_checks_core').png_info(
        Path(files['diffuse']).read_bytes())
    assert w == h and w <= 2048 and (depth, ctype, alpha) == (8, 2, False), (w, h, depth, ctype, alpha)
    table = json.loads(Path(files['table']).read_text(encoding='ascii'))
    rows = table['table']
    worst_px, samples = atlas_pixels_follow_uv(app, rows)
    assert worst_px <= 1.0, worst_px
    pic = TQ.read_png(Path(files['diffuse']).read_bytes())
    glass = [r for r in rows if r['library_id'] == 31][0]
    gx, gy = glass['cell_px'][0] + 2, glass['cell_px'][1] + 2
    assert pic.rgb()[(gy * w + gx) * 3:(gy * w + gx) * 3 + 3] == bytes((255, 255, 255)), 'glass cell not white'
    # table returns the VPM UV: NPM faces = body faces then glass faces (attach order)
    bymid = {r['library_id']: r for r in rows}
    worst_uv = 0.0
    nm = npm.mesh
    off = 0
    for c in copies:
        cm = c.mesh
        for f in range(1, int(cm.numfaces) + 1):
            mid = int(rt.getFaceMatID(cm, f))
            a = rt.meshop.getMapFace(nm, 1, f + off)
            s = rt.meshop.getMapFace(cm, 1, f)
            for ai, si in ((a.x, s.x), (a.y, s.y), (a.z, s.z)):
                pa = rt.meshop.getMapVert(nm, 1, int(ai))
                ps = rt.meshop.getMapVert(cm, 1, int(si))
                back = ((float(pa.x) - bymid[mid]['shift'][0]) / bymid[mid]['scale'][0],
                        (float(pa.y) - bymid[mid]['shift'][1]) / bymid[mid]['scale'][1])
                worst_uv = max(worst_uv, abs(back[0] - float(ps.x)), abs(back[1] - float(ps.y)))
        off += int(cm.numfaces)
    assert worst_uv <= 2e-4, worst_uv  # float32 storage of the atlas UV / scale (~0.27): ~1e-5 UV of the VPM
    for c in copies:
        assert (mesh_hash(c), uv_state(c)) == before[str(c.name)], 'VPM copy changed'
    assert {p: md5(p) for p in maps_before} == maps_before, 'source maps changed'
    checks = {}
    for tool in ('textures',):
        rep = agr.checks_050(tool, [npm])
        checks['tex.check'] = {'status': rep.get('status'), 'codes': sorted({f.get('code') for o in rep.get('objects', [])
                                                                                for f in o.get('findings', [])})}
    rep = agr.checks_070('sets_count', [npm], select=False)
    checks['atlas.sets_count'] = {'status': rep.get('status'), 'codes': sorted({
        f.get('code') for o in rep.get('objects', []) for f in o.get('findings', [])})}
    again = agr.edits_100('npm.build', 'apply', agr.edits_100('npm.build', 'preview', nodes=copies, options=opts),
                          nodes=copies)
    assert again['plan']['out_dir'] != app['plan']['out_dir'], 'second run overwrote the folder'
    rt.execute('max undo')
    left = sorted(str(x.name) for x in rt.objects if '_NPM_' in str(x.name))
    assert rt.getNodeByName(again['plan']['copies'][0]) is None, ('one undo did not remove the second run', left,
                                                                    again['plan']['copies'])
    return {'seconds': round(dt, 2), 'atlas_px': w, 'texel': rb['texel_px_per_m'], 'rigid_max_uv': rb['rigid_max_uv'],
            'table_back_to_vpm_uv_max': worst_uv, 'atlas_px_vs_uv_worst': worst_px, 'samples': samples,
            'udim': {r['library_id']: [r['udim'], r['udim_source']] for r in rows}, 'checks': checks,
            'files': [os.path.basename(p) for p in files.values()], 'out_dir': app['plan']['out_dir'],
            'second_out_dir': again['plan']['out_dir'], 'sources_px': table.get('sources_px'),
            'fill': app['plan']['done'][0]['fill']}


def npm_metres():
    return npm_build('meters', 'm')


def npm_cm():
    out = npm_build('centimeters', 'cm')
    ref = summary['checks'].get('npm_build_metres')
    if ref:
        assert out['atlas_px'] == ref['atlas_px'] and out['texel'] == ref['texel'], (out, ref)
    return out


def npm_fail_closed():
    copies, udim = make_vpm('meters', 'bad')
    body = [c for c in copies if '_glass_' not in str(c.name)][0]
    body.material = multi('M_body', {3: PANEL_MAP, 7: str(MAPS / 'T_Missing_Diffuse.png')})
    out_dir = OUT / 'npm_bad'
    pre = agr.edits_100('npm.build', 'preview', nodes=copies, options={'udim_table': udim, 'out_dir': str(out_dir)})
    codes = sorted({f['code'] for o in pre['objects'] for f in o['findings']})
    assert pre['status'] == 'fail' and codes == ['map_missing'], codes
    try:
        agr.edits_100('npm.build', 'apply', pre, nodes=copies)
        raise AssertionError('apply of a failing build wrote something')
    except ValueError as exc:
        refused = str(exc)[:120]
    assert not out_dir.exists(), 'a refused build created files'
    rt.clearSelection()
    try:
        agr.edits_100('npm.build', 'preview', nodes=None)
        raise AssertionError('empty selection passed')
    except ValueError as exc:
        empty = str(exc)[:120]
    return {'codes': codes, 'apply_refused': refused, 'empty': empty}


def facade_strip():
    out = {}
    for units in ('meters', 'centimeters'):
        fresh(units)
        mesh = PB.strip_facade('SM_Strip_' + units)
        node = PB.build_node(rt, mesh, 'SM_Strip_' + units)
        mats = {}
        for i, (mid, name) in enumerate(sorted(PB.STRIP_MAPS.items())):
            mats[mid] = coord_png(MAPS / '{}_{}'.format(units, name), 48 if mid < 200 else 64, 32 if mid < 200 else 64,
                                  i * 40)
        node.material = multi('M_strip', mats)
        before = (mesh_hash(node), uv_state(node))
        opts = {'period_by_id': PB.PERIODS, 'out_dir': str(OUT / ('strip_' + units))}
        pre = agr.edits_100('atlas.facade_strip', 'preview', nodes=[node], options=opts)
        assert pre['status'] == 'pass', pre['objects']
        app = agr.edits_100('atlas.facade_strip', 'apply', pre, nodes=[node])
        assert app['status'] == 'pass', app['objects']
        rb = app['plan']['readback'][0]
        assert all(abs(t / TEXEL - 1) <= 0.01 for t in rb['texel_px_per_m'].values()), rb
        assert rb['outside_cell'] == 0 and rb['rigid_max_uv'] <= 1e-5, rb
        assert (mesh_hash(node), uv_state(node)) == before, 'original changed'
        files = {f['kind']: f['path'] for f in app['plan']['files']}
        w, h, depth, ctype, alpha = agr._load_core('checks_core.py', 'agr_tools_checks_core').png_info(
            Path(files['diffuse']).read_bytes())
        assert w == h and w <= 2048 and (depth, ctype) == (8, 2)
        done = app['plan']['done'][0]
        out[units] = {'atlas_px': w, 'texel': rb['texel_px_per_m'], 'strips': app['plan'].get('strips'),
                      'unique_ids': done['unique_ids'], 'fill': done['fill'], 'pad_px': done['pad_px']}
    assert out['meters']['texel'] == out['centimeters']['texel'], out
    assert out['meters']['atlas_px'] == out['centimeters']['atlas_px'] and \
        abs(out['meters']['fill'] - out['centimeters']['fill']) < 1e-6, out  # same layout in m and cm
    return out


def polygon_rows():
    """My stations of the live polygon: build polygon_all from load_catalog() and press every P row."""
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    sys.path.insert(0, str(ROOT / 'src'))
    import polygon_core as core
    cat = OUT / 'catalog.json'
    pre = os.environ.get('AGR_P_CATALOG')
    text = Path(pre).read_text(encoding='utf-8') if pre else json.dumps(core.load_catalog(), ensure_ascii=False)
    cat.write_text(text, encoding='utf-8')
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    import build_scene
    fresh()
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    frag = json.loads((ROOT / 'test-polygon' / 'stations' / 'P.json').read_text(encoding='utf-8'))
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


check('npm_build_metres', npm_metres)
check('npm_build_cm', npm_cm)
check('npm_build_fail_closed', npm_fail_closed)
check('facade_strip', facade_strip)
check('polygon_rows_P', polygon_rows)
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('NPM_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native branch P failed: see summary.json'
