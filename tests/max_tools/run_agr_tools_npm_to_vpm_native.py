"""new-case: #1024 branch Q native run of npm.to_vpm (1.0.24) and udim.udims_to_ids (1.0.25) in locked batch Max 2024.

Run via the lab DCC runner (script_in_place) on DISPOSABLE synthetic scenes; AGR_TEST_OUTPUT names a NEW directory,
AGR_TEST_PACKAGE the built MZP (installed into OUT, no user folder touched). Nothing is saved.

Checks (lab L11 minimal acceptance, docs/experiments/npm.to_vpm.md; #1024 §1.0.24, «редакция 1» 26):
* table round trip, metres and centimetres: vpm.build (M) -> npm.build (P, coordinate maps) -> npm.to_vpm by the
  `npm_table.json` next to the atlas: UV of the returned VPM = UV of the source VPM (float32), every triangle in its
  UDIM, body and glass separate (each from 1001), slots = the library materials of the scene, texel = the source
  texel +-1 %, the NPM object / atlas / table unchanged, one undo removes the run;
* regions (no table) on a 16-bit coordinate atlas 2048: ids 2, 5, 9, 12 kept, UDIM = 1000 + ID, crop = region size,
  crop vs UV <= 1 px (incl. the stack at the atlas edge and the one outside the first UDIM), a second run writes a
  NEW folder;
* windows, metres and centimetres: 12 KPP1 planes + one turned 90 deg + one without a type (noise 4 mm): 13 instances
  of the right types, centre +-5 mm, normal <= 0.5 deg, the planes on the hidden layer `_npm_src`, the untyped one
  reported; the same in m and cm;
* udim.udims_to_ids on an Editable_Mesh with an Unwrap_UVW on top: IDs 1, 2, 11 + 4 ambiguous triangles, IDs and stack
  unchanged, apply refused;
* the Q stations of the live polygon (polygon_all from polygon_core.load_catalog()): every expected row.
"""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import struct
import sys
import time
import traceback
import zlib

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
    t = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    print('N2V_NATIVE', name, 'ok' if name in summary['checks'] else 'ERROR', round(time.time() - t, 1), 's')


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
# The batch runner executes the whole script inside ONE outer undo hold, so every pymxs undo record of the file merges
# into it and one `max undo` rolls back the set-up too (job 20261106-070529-76860bcb: vpm.build and npm.build objects
# gone with the npm.to_vpm copies; branch G, job 20261106-044415-f3028608). Close it so each apply is its own record
# (as in a GUI session) and re-open a hold at the end for the wrapper.
OUTER_HOLD = bool(rt.theHold.Holding())
if OUTER_HOLD:
    rt.theHold.Accept('AGR branch Q native: set-up')
summary['outer_hold_at_start'] = OUTER_HOLD
MB = load(ROOT / 'test-polygon' / 'stations' / 'M_build.py', 'agr_polygon_M_build_native_q')
QB = load(ROOT / 'test-polygon' / 'stations' / 'Q_build.py', 'agr_polygon_Q_build_native')
TQ = agr._load_core('texqa_core.py', 'agr_tools_texqa_core')
NC = agr._load_core('npm_core.py', 'agr_tools_npm_core_native_q')
summary['runtime_version'] = agr.VERSION
MAPS = OUT / 'maps'
MAPS.mkdir()
EMAX = agr._load_core('edit_max.py', 'agr_tools_edit_max')


def coord_png(path, w, h, tint=0):
    px = bytearray()
    for y in range(h):
        for x in range(w):
            px += bytes((x % 256, y % 256, tint))
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


def snap(n):
    return EMAX.snapshot([n])[0]


def mpu():
    return {'meters': 1.0, 'centimeters': 0.01}[str(rt.units.SystemType).lower().lstrip('#')]


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


def tri_data(n):
    """[(mat id, [3 world-metre points], [3 uv])] of every face of a node."""
    m = rt.snapshotAsMesh(n)
    k = mpu()
    out = []
    for f in range(1, int(m.numfaces) + 1):
        face = rt.getFace(m, f)
        tf = rt.meshop.getMapFace(m, 1, f)
        pts = [rt.getVert(m, int(i)) for i in (face.x, face.y, face.z)]
        uvs = [rt.meshop.getMapVert(m, 1, int(i)) for i in (tf.x, tf.y, tf.z)]
        out.append((int(rt.getFaceMatID(m, f)), [[float(p.x) * k, float(p.y) * k, float(p.z) * k] for p in pts],
                    [[float(q.x), float(q.y)] for q in uvs]))
    return out


def texel(data, mid, map_w):
    ua = ga = 0.0
    for m, p, q in data:
        if m != mid:
            continue
        ua += 0.5 * abs((q[1][0] - q[0][0]) * (q[2][1] - q[0][1]) - (q[2][0] - q[0][0]) * (q[1][1] - q[0][1]))
        e1 = [p[1][j] - p[0][j] for j in range(3)]
        e2 = [p[2][j] - p[0][j] for j in range(3)]
        c = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]]
        ga += 0.5 * math.sqrt(sum(x * x for x in c))
    return map_w * math.sqrt(ua / ga)


def make_vpm(units, tag):
    fresh(units)
    small = [(0.0, 0.0), (3.6, 0.0), (3.6, 3.6), (0.0, 3.6)]
    n = MB.build_node(rt, MB.facade(height=6.0, footprint=small, brick_from=3.0), 'SM_N2v{}_Main'.format(tag))
    pre = agr.edits_100('vpm.build', 'preview', nodes=[n], options={'glass_ids': [31], 'out_dir': str(OUT / ('vpm_' + tag))})
    app = agr.edits_100('vpm.build', 'apply', pre, nodes=[n])
    assert app['status'] == 'pass', app['objects']
    copies = [rt.getNodeByName(c) for c in app['plan']['copies']]
    table = json.loads(Path(app['plan']['files'][0]['path']).read_text(encoding='ascii'))
    for c in copies:
        c.material = multi('M_glass', {31: (70, 90, 110)}) if '_glass_' in str(c.name) else \
            multi('M_body', {3: PANEL_MAP, 7: BRICK_MAP})
    rt.delete(n)
    return copies, NC.udim_table_of(table, [str(c.name) for c in copies])


def table_round_trip(units, tag):
    copies, udim = make_vpm(units, tag)
    body = [c for c in copies if '_glass_' not in str(c.name)][0]
    glass = [c for c in copies if '_glass_' in str(c.name)][0]
    src = {'body': tri_data(body), 'glass': tri_data(glass)}
    pre = agr.edits_100('npm.build', 'preview', nodes=copies, options={'udim_table': udim, 'out_dir': str(OUT / ('npm_' + tag))})
    app = agr.edits_100('npm.build', 'apply', pre, nodes=copies)
    assert app['status'] == 'pass', app['objects']
    npm = rt.getNodeByName(app['plan']['copies'][0])
    files = {f['kind']: f['path'] for f in app['plan']['files']}
    before = (snap(npm), md5(files['diffuse']), md5(files['table']))
    rt.select(npm)
    t = time.time()
    p2 = agr.edits_100('npm.to_vpm', 'preview', nodes=None, options={})
    assert p2['status'] == 'pass', p2['objects']
    a2 = agr.edits_100('npm.to_vpm', 'apply', p2, nodes=None)
    dt = time.time() - t
    assert a2['status'] == 'pass', a2['objects']
    done = p2['plan']['done'][0]
    assert done['mode'] == 'table' and done['table'] == os.path.normpath(files['table']), done
    rb = a2['plan']['readback'][0]
    names = {c['part']: c['copy'] for c in rb['copies']}
    assert set(names) == {'body', 'glass'}, names
    worst, out_udim = 0.0, 0
    tex = {}
    for part in ('body', 'glass'):
        back = tri_data(rt.getNodeByName(names[part]))
        assert len(back) == len(src[part]), (part, len(back), len(src[part]))
        for (m1, p1, q1), (m0, p0, q0) in zip(back, src[part]):
            assert m1 == m0
            assert max(abs(a - b) for x, y in zip(p1, p0) for a, b in zip(x, y)) <= 1e-4
            worst = max(worst, max(abs(a - b) for x, y in zip(q1, q0) for a, b in zip(x, y)))
            tile = udim[str(m1)]
            u0, v0 = (tile - 1001) % 10, (tile - 1001) // 10
            if not all(u0 - 1e-6 <= u <= u0 + 1 + 1e-6 and v0 - 1e-6 <= v <= v0 + 1 + 1e-6 for u, v in q1):
                out_udim += 1
        if part == 'body':
            for mid, w in ((3, 128), (7, 96)):
                tex[mid] = [round(texel(back, mid, w), 4), round(texel(src['body'], mid, w), 4)]
                assert abs(tex[mid][0] / tex[mid][1] - 1) <= 0.01, tex
    assert worst <= 1e-5 and out_udim == 0, (worst, out_udim)
    bnode = rt.getNodeByName(names['body'])
    subs = {int(i): s for i, s in zip(bnode.material.materialIDList, bnode.material.materialList)}
    lib = {int(i): s for i, s in zip(body.material.materialIDList, body.material.materialList)}
    assert sorted(subs) == [3, 7] and all(subs[i] == lib[i] for i in subs), 'slots are not the library materials'
    assert rb['materials']['body'] == {'3': 'scene', '7': 'scene'}, rb['materials']
    assert (snap(npm), md5(files['diffuse']), md5(files['table'])) == before, 'NPM / atlas / table changed'
    assert [str(x.name) for x in rt.selection] == [str(npm.name)], 'selection not restored'
    npm_name = str(npm.name)
    scene_before = sorted(str(x.name) for x in rt.objects)
    rt.execute('max undo')
    scene_after = sorted(str(x.name) for x in rt.objects)
    gone = sorted(set(scene_before) - set(scene_after))
    assert rt.getNodeByName(names['body']) is None and rt.getNodeByName(names['glass']) is None, 'undo kept copies'
    # one undo removes exactly the npm.to_vpm run: the NPM of npm.build and the VPM objects stay
    assert gone == sorted(names.values()), ('one undo removed more than the run', gone)
    assert rt.getNodeByName(npm_name) is not None, 'NPM gone after one undo'
    return {'seconds': round(dt, 2), 'uv_max_diff_vs_vpm': worst, 'tris': {k: len(v) for k, v in src.items()},
            'udim': done['udim'], 'texel_back_vs_vpm': tex, 'copies': names, 'undo_removed': gone}


def table_metres():
    return table_round_trip('meters', 'm')


def table_cm():
    return table_round_trip('centimeters', 'cm')


def regions_16bit():
    fresh('meters')
    W = 2048
    atlas = OUT / 'atlas16' / 'T_Atlas16_d_1.png'
    atlas.parent.mkdir()
    atlas.write_bytes(QB.coord16_png(W, W))
    mesh = QB.atlas_npm('SM_Unatlas_Main')
    n = QB.build_node(rt, mesh, 'SM_Unatlas_Main')
    mat = rt.StandardMaterial(name='M_atlas')
    mat.diffuseMap = rt.Bitmaptexture(filename=str(atlas))
    n.material = mat
    before = (snap(n), md5(atlas))
    opts = {'mode': 'regions', 'out_dir': str(OUT / 'regions')}
    pre = agr.edits_100('npm.to_vpm', 'preview', nodes=[n], options=opts)
    assert pre['status'] == 'pass', pre['objects']
    app = agr.edits_100('npm.to_vpm', 'apply', pre, nodes=[n])
    assert app['status'] == 'pass', app['objects']
    crops = app['plan']['crops'][0]
    copy = rt.getNodeByName(app['plan']['readback'][0]['copies'][0]['copy'])
    data = tri_data(copy)
    worst, sizes = 0.0, {}
    for f in crops['files']:
        raw_png = Path(f['path']).read_bytes()
        ch = []
        pos = 8
        while pos < len(raw_png):
            ln, kind = struct.unpack('>I4s', raw_png[pos:pos + 8])
            ch.append((kind, raw_png[pos + 8:pos + 8 + ln]))
            pos += 12 + ln
        cw, chh, depth, ctype = struct.unpack('>IIBB', ch[0][1][:10])
        assert depth == 16 and ctype == 2, (depth, ctype)
        x0, y0, x1, y1 = f['box_px']
        assert (cw, chh) == (x1 - x0, y1 - y0) and cw < W
        sizes[f['library_id']] = [cw, chh]
        raw = zlib.decompress(b''.join(b for k, b in ch if k == b'IDAT'))
        tu, tv = (f['udim'] - 1001) % 10, (f['udim'] - 1001) // 10
        for mid, _p, q in data:
            if mid != f['library_id']:
                continue
            for u, v in q:
                assert tu - 1e-6 <= u <= tu + 1 + 1e-6 and tv - 1e-6 <= v <= tv + 1 + 1e-6
                x = min(cw - 1, int((u - tu) * cw))
                y = min(chh - 1, int((1 - (v - tv)) * chh))
                off = y * (cw * 6 + 1) + 1 + x * 6
                ax = (struct.unpack('>H', raw[off:off + 2])[0] - 16) / 32.0
                ay = (struct.unpack('>H', raw[off + 2:off + 4])[0] - 16) / 32.0
                worst = max(worst, abs(ax + 0.5 - ((u - tu) * cw + x0)), abs(ay + 0.5 - ((1 - (v - tv)) * chh + y0)))
    assert worst <= 1.0, worst
    ids = sorted({m for m, _p, _q in data})
    assert ids == [2, 5, 9, 12], ids
    assert {f['library_id']: f['udim'] for f in crops['files']} == {2: 1002, 5: 1005, 9: 1009, 12: 1012}
    assert (snap(n), md5(atlas)) == before, 'NPM or atlas changed'
    again = agr.edits_100('npm.to_vpm', 'apply', agr.edits_100('npm.to_vpm', 'preview', nodes=[n], options=opts), nodes=[n])
    assert again['plan']['crops'][0]['folder'] != crops['folder'], 'second run overwrote the crops'
    straddle = QB.atlas_npm('SM_Unatlas_Bad')
    straddle['uvs'][straddle['uv_tris'][straddle['mat_ids'].index(9)][1]] = [1.2, 0.5]
    b = QB.build_node(rt, straddle, 'SM_Unatlas_Bad')
    b.material = mat
    bad = agr.edits_100('npm.to_vpm', 'preview', nodes=[b], options=dict(opts, out_dir=str(OUT / 'regions_bad')))
    codes = sorted({x['code'] for o in bad['objects'] for x in o['findings']})
    assert codes == ['region_straddle'], codes
    try:
        agr.edits_100('npm.to_vpm', 'apply', bad, nodes=[b])
        raise AssertionError('a blocking finding applied')
    except ValueError as exc:
        refused = str(exc)[:140]
    assert not (OUT / 'regions_bad').exists(), 'refused run wrote files'
    return {'crop_vs_uv_px': round(worst, 4), 'crop_px': sizes, 'udim': {str(f['library_id']): f['udim'] for f in crops['files']},
            'folders': [crops['folder'], again['plan']['crops'][0]['folder']], 'straddle': codes, 'refused': refused}


def windows(units):
    fresh(units)
    o = QB.station_options()
    mesh, _rows, _p = QB.npm('SM_N2vWin_Main')
    planes = QB.window_planes(rotated=True, untyped=True)
    QB.add_planes(mesh, planes)
    n = QB.build_node(rt, mesh, 'SM_N2vWin_Main')
    before = snap(n)
    pre = agr.edits_100('npm.to_vpm', 'preview', nodes=[n], options=o)
    codes = sorted({x['code'] for ob in pre['objects'] for x in ob['findings']})
    assert codes == ['window_no_type'], codes
    app = agr.edits_100('npm.to_vpm', 'apply', pre, nodes=[n])
    rb = app['plan']['readback'][0]
    wins = rb['windows']
    assert len(wins) == 13, len(wins)
    typed = [p for p in planes if p['type']]
    got = []
    for w, p in zip(wins, typed):
        assert w['type'] == p['type'] and w['rotated'] == p['rotated'], (w, p)
        inst = rt.getNodeByName(w['instance'])
        assert rt.isValidNode(inst) and rt.getUserProp(inst, 'agr_window_type') == p['type']
        assert w['centre_mm'] <= 5.0 and w['normal_deg'] <= 0.5, w
        got.append([w['type'], w['rotated'], w['centre_mm'], w['normal_deg']])
    src = [x for x in rt.objects if str(x.name).endswith('_npm_win_src')]
    assert len(src) == 1 and src[0].isHidden and str(src[0].layer.name) == '_npm_src', src
    assert int(src[0].mesh.numfaces) == sum(2 * p['split'] for p in planes)
    assert snap(n) == before, 'NPM changed'
    masters = sorted(str(x.name) for x in rt.objects if str(x.name).startswith('WINLIB_'))
    made = sorted([w['instance'] for w in wins] + [str(x.name) for x in rt.objects if str(x.name).startswith(
        ('GLASS_NPM_',))] + masters + [str(src[0].name)] + [c['copy'] for c in rb['copies']])
    scene_before = sorted(str(x.name) for x in rt.objects)
    rt.execute('max undo')
    gone = sorted(set(scene_before) - set(str(x.name) for x in rt.objects))
    assert gone == made, ('one undo did not remove exactly the run', gone, made)
    assert rt.getNodeByName('SM_N2vWin_Main') is not None and snap(n) == before
    return {'instances': got, 'masters': masters, 'untyped': codes, 'undo_removed': len(gone),
            'done': pre['plan']['done'][0]['windows']}


def windows_m():
    return windows('meters')


def windows_cm():
    out = windows('centimeters')
    ref = summary['checks'].get('windows_metres')
    if ref:
        assert [x[:2] for x in out['instances']] == [x[:2] for x in ref['instances']], (out, ref)
    return out


def udim_view():
    fresh('meters')
    n = QB.build_node(rt, QB.udim_plane('SM_UdimView_Native', bad=True), 'SM_UdimView_Native')
    rt.addModifier(n, rt.Unwrap_UVW())
    before = (snap(n), [str(rt.classOf(m)) for m in n.modifiers],
              [int(rt.getFaceMatID(n.mesh, i)) for i in range(1, int(n.mesh.numfaces) + 1)])
    rep = agr.edits_100('udim.udims_to_ids', 'preview', nodes=[n])
    assert rep['status'] == 'fail'
    codes = [x['code'] for o in rep['objects'] for x in o['findings']]
    assert codes == ['udim_ambiguous'], codes
    rows = rep['plan']['done'][0]['rows']
    assert [(r['udim'], r['id']) for r in rows] == [(1001, 1), (1002, 2), (1011, 11)], rows
    amb = rep['objects'][0]['findings'][0]['ids']
    assert amb == [7, 8, 9, 10], amb
    after = (snap(n), [str(rt.classOf(m)) for m in n.modifiers],
             [int(rt.getFaceMatID(n.mesh, i)) for i in range(1, int(n.mesh.numfaces) + 1)])
    assert after == before, 'udim.udims_to_ids changed the object'
    try:
        agr.edits_100('udim.udims_to_ids', 'apply', rep, nodes=[n])
        raise AssertionError('apply of a read-only row passed')
    except ValueError as exc:
        refused = str(exc)[:100]
    return {'rows': rows, 'ambiguous': amb, 'refused': refused}


def polygon_rows():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    sys.path.insert(0, str(ROOT / 'src'))
    import polygon_core as core
    cat = OUT / 'catalog.json'
    pre = os.environ.get('AGR_Q_CATALOG')
    text = Path(pre).read_text(encoding='utf-8') if pre else json.dumps(core.load_catalog(), ensure_ascii=False)
    cat.write_text(text, encoding='utf-8')
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    import build_scene
    fresh()
    build_scene.build('polygon_all', texture_dir=str(OUT / 'textures'))
    frag = json.loads((ROOT / 'test-polygon' / 'stations' / 'Q.json').read_text(encoding='utf-8'))
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


check('table_metres', table_metres)
check('table_cm', table_cm)
check('regions_16bit', regions_16bit)
check('windows_metres', windows_m)
check('windows_cm', windows_cm)
check('udim_udims_to_ids', udim_view)
check('polygon_rows_Q', polygon_rows)
if OUTER_HOLD:
    rt.theHold.Begin()
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('N2V_NATIVE checks', sorted(summary['checks']), 'errors', sorted(summary['errors']))
assert not summary['errors'], 'native branch Q failed: see summary.json'
