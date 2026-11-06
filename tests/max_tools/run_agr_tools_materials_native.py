"""new-case: #1024 branch L native run of mat.table, mat.tiles and tex.plug_colour in locked batch Max 2024 on DISPOSABLE
scenes (lab DCC runner, script_in_place). AGR_TEST_OUTPUT names a NEW directory, AGR_TEST_PACKAGE the built MZP.

Installs the MZP into OUT (no user folders touched), then in the real Max Python through runtime.edits_100:
* mat.table: mid-poly ids {3, 7, 12, 31} on a body + glass id 39 on a glass object -> pass, UDIM 1001..1004 and 1001
  per mesh (V9); ids {3, 1005} -> fail udim_id_on_geometry; glass id on a body -> glass_not_on_glass. Apply: one
  Multi/Sub AGR_Library_v001 (slot = library id; used slots 3, 7, 12, 31, 39), user props, sidecar materials_table.json beside a disposable
  passport, ONE undo record (pymxs.undo spy, theHold active; batch max undo only observed), selection restored, no new global; apply by mcp
  refused; a stale preview refused.
* mat.tiles: preview by face ids (facade/ground/crumb, pass) and by agr_tile 4.0 m (fail); apply of the three K3
  maps into a NEW folder, PNG readback, CIEDE2000 of the recoloured mean body vs RAL read back from the files; a
  second apply into the same folder is refused.
* tex.plug_colour: the lab L14 synthetic set (solid, grey 128, 9.4 % first blue, row-0 blue, RGBA 62.5 % transparent,
  palette 30/70, 512^2, 256x1024, JPG via .NET, TGA): chosen colours, decisions, sources' SHA256 unchanged, no dialog.
* polygon rows of the L stations (frag_l_*): built by build_scene, pressed (preview) and compared by
  polygon_core.compare_report.
Nothing of the user is saved; the scenes are reset between blocks.
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
os.environ['AGR_POLYGON_OUT'] = str(OUT / 'polygon')
os.environ['AGR_POLYGON_ROOT'] = str(ROOT)
os.environ.setdefault('AGR_TOOLS_REPO', str(ROOT))
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}, 'polygon_rows': []}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t0 = time.time()
    try:
        summary['checks'][name] = fn()
        summary['checks'][name + '_s'] = round(time.time() - t0, 2)
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
tex = agr._load_core('tex_core.py', 'agr_tools_tex_core')
tiles = agr._load_core('tiles_core.py', 'agr_tools_tiles_core')


def reset():
    rt.resetMaxFile(rt.name('noPrompt'))
    rt.units.SystemType = rt.name('meters')
    rt.units.SystemScale = 1.0


def ids_box(name, ids, role, x):
    b = rt.Box(name=name, width=4, length=4, height=3)
    b.pos = rt.Point3(x, 0, 0)
    rt.convertToMesh(b)
    for f in range(1, int(rt.getNumFaces(b)) + 1):
        rt.setFaceMatID(b, f, ids[(f - 1) % len(ids)])
    rt.update(b)
    rt.setUserProp(b, 'agr_role', role)
    return b


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


# ---- mat.table --------------------------------------------------------------------------------------------------
def mat_table():
    reset()
    body = ids_box('BODY_Mid_001', [3, 7, 12, 31], 'body', 0)
    glass = ids_box('GLASS_Mid_001', [39], 'glass', 6)
    udim = ids_box('BODY_Udim_001', [3, 1005], 'body', 12)
    wrong = ids_box('BODY_Glass_001', [3, 39], 'body', 18)
    r = agr.edits_100('mat.table', 'preview', None, [body, glass, udim, wrong])
    got = codes(r)
    assert r['status'] == 'fail' and got == {'BODY_Mid_001': [], 'GLASS_Mid_001': [],
                                             'BODY_Udim_001': ['udim_id_on_geometry'],
                                             'BODY_Glass_001': ['glass_not_on_glass']}, got
    table = [(t['mesh'], t['library_id'], t['udim']) for t in r['plan']['table']]
    assert table == [('BODY_Mid_001', 3, 1001), ('BODY_Mid_001', 7, 1002), ('BODY_Mid_001', 12, 1003),
                     ('BODY_Mid_001', 31, 1004), ('GLASS_Mid_001', 39, 1001)], table
    # disposable passport -> sidecar
    jobs = OUT / 'jobs' / 'POLY'
    jobs.mkdir(parents=True)
    passport = jobs / 'passport.json'
    passport.write_text('{"schema": 1}\n', encoding='utf-8')
    rt.fileProperties.addProperty(rt.name('custom'), 'agr_passport',
                                  json.dumps({'path': str(passport), 'sha256': hashlib.sha256(passport.read_bytes()).hexdigest()}))
    nodes = [body, glass]
    rt.select([body])
    p = agr.edits_100('mat.table', 'preview', None, nodes)
    assert p['status'] == 'pass' and not p['plan']['skipped'], p['plan']['skipped']
    try:
        agr.edits_100('mat.table', 'apply', p, nodes, actor='mcp')
        raise AssertionError('apply by mcp was not refused')
    except ValueError as exc:
        assert str(exc).startswith('needs_human'), exc
    before_globals = bool(rt.globalVars.isGlobal(rt.name('agrMultiSub')))
    # undo spy: every pymxs.undo record opened during the apply (edit_max.undo_record imports pymxs at call time)
    import contextlib
    import pymxs
    real_undo, records = pymxs.undo, []

    @contextlib.contextmanager
    def spy(flag, label=''):
        with real_undo(flag, label):
            records.append((str(label), bool(rt.theHold.Holding())))
            yield
    pymxs.undo = spy
    try:
        a = agr.edits_100('mat.table', 'apply', p, nodes)
    finally:
        pymxs.undo = real_undo
    assert records == [('AGR Tools: mat.table', True)], records  # ONE undo record, theHold active
    assert a['status'] == 'pass' and sorted(a['plan']['done']) == ['BODY_Mid_001', 'GLASS_Mid_001'], a['plan']
    mm = body.material
    assert str(mm.name) == 'AGR_Library_v001' and glass.material == mm
    slot_ids = [int(x) for x in mm.materialIDList]
    assert slot_ids == list(range(1, 40)), slot_ids  # slot k is library id k (no id writes, see matlib_max)
    used = [k for k in slot_ids if rt.getSubMtl(mm, k) is not None]
    ids = used
    assert used == [3, 7, 12, 31, 39], used
    subs = [str(rt.getSubMtl(mm, k).name) for k in used]
    cls = sorted({str(rt.classOf(rt.getSubMtl(mm, k))) for k in used})
    assert json.loads(str(rt.getUserProp(body, 'agr_udim_table'))) == {'3': 1001, '7': 1002, '12': 1003, '31': 1004}
    assert json.loads(str(rt.getUserProp(glass, 'agr_udim_table'))) == {'39': 1001}
    sidecar = Path(a['plan']['written'])
    doc = json.loads(sidecar.read_text(encoding='utf-8'))
    assert sidecar.parent == jobs and doc['materials'][0]['udim'] == 1001 and doc['library']['version'] == 'v001'
    sel = [str(n.name) for n in rt.selection]
    assert sel == ['BODY_Mid_001'], sel
    assert not bool(rt.globalVars.isGlobal(rt.name('agrMultiSub'))) and not before_globals
    # max undo inside one batch ExecuteFile is not isolating (0.8 job 20261105-003249-e0800495: records merge; job
    # 20261106-050740-4eeffb37: materials stayed): recorded as an observation, the record itself is asserted above.
    rt.execute('max undo')
    nb, ng = rt.getNodeByName('BODY_Mid_001'), rt.getNodeByName('GLASS_Mid_001')
    undone = {'body_alive': nb is not None, 'glass_alive': ng is not None,
              'body_material': None if nb is None or nb.material is None else str(nb.material.name),
              'glass_material': None if ng is None or ng.material is None else str(ng.material.name)}
    if nb is None or ng is None:  # the merged batch step removed the setup too: rebuild it for the next checks
        reset()
        nb = ids_box('BODY_Mid_001', [3, 7, 12, 31], 'body', 0)
        ng = ids_box('GLASS_Mid_001', [39], 'glass', 6)
        rt.fileProperties.addProperty(rt.name('custom'), 'agr_passport', json.dumps({'path': str(passport), 'sha256': None}))
    body, glass = nb, ng
    nodes = [body, glass]
    # stale preview: the scene changed since
    p = agr.edits_100('mat.table', 'preview', None, nodes)
    rt.setFaceMatID(body, 1, 7)
    rt.update(body)
    try:
        agr.edits_100('mat.table', 'apply', p, nodes)
        raise AssertionError('stale preview accepted')
    except ValueError as exc:
        stale = str(exc)[:80]
    rt.setFaceMatID(body, 1, 3)
    rt.update(body)
    # second apply on the same preview writes a new versioned sidecar, never over the first
    a2 = agr.edits_100('mat.table', 'apply', agr.edits_100('mat.table', 'preview', None, nodes), nodes)
    assert Path(a2['plan']['written']).name == 'materials_table_v002.json', a2['plan']['written']
    return {'preview_codes': got, 'table': table, 'multisub_ids': ids, 'subs': subs, 'sub_classes': cls,
            'sidecar': sidecar.name, 'second_sidecar': Path(a2['plan']['written']).name, 'stale': stale,
            'undo_records': records, 'batch_max_undo_observed': undone, 'selection': sel}


# ---- mat.tiles --------------------------------------------------------------------------------------------------
def mat_tiles():
    reset()
    ok = ids_box('TILE_K3_001', [14, 18, 27], 'body', 0)
    bad = ids_box('TILE_4m_001', [14], 'body', 6)
    rt.setUserProp(bad, 'agr_tile', json.dumps({'base_map': 'facade_600x1200', 'period_m': 4.0, 'fit': False}))
    t0 = time.time()
    r = agr.edits_100('mat.tiles', 'preview', None, [ok, bad], {'out_dir': str(OUT / 'tiles_nodes')})
    preview_s = round(time.time() - t0, 2)
    got = codes(r)
    assert got == {'TILE_K3_001': [], 'TILE_4m_001': ['module_not_dividing', 'not_seamless']}, got
    opts = {'maps': ['facade_600x1200', 'ground_100x300', 'crumb_1x1'], 'records': [14, 15, 18, 27, 39],
            'out_dir': str(OUT / 'tiles')}
    p = agr.edits_100('mat.tiles', 'preview', None, None, opts)
    assert p['status'] == 'pass', (p['plan']['ambiguous'], [m.get('findings') for m in p['plan']['maps']])
    t0 = time.time()
    a = agr.edits_100('mat.tiles', 'apply', p)
    apply_s = round(time.time() - t0, 2)
    man = json.loads((OUT / 'tiles' / 'tiles_manifest.json').read_text(encoding='utf-8'))
    files = {f['name']: f for f in man['files']}
    # read back a recoloured D map with the 0.8 decoder and measure the mean body colour vs RAL 7024
    d = next(n for n in files if n.startswith('L014_') and n.endswith('_D.png'))
    m = next(n for n in files if n == 'facade_600x1200_mask.png')
    img, _ = tex.decode_png((OUT / 'tiles' / d).read_bytes())
    msk, _ = tex.decode_png((OUT / 'tiles' / m).read_bytes())
    assert (img.w, img.h) == (3686, 3686), (img.w, img.h)
    acc, n = [0, 0, 0], 0
    for y in range(0, img.h, 7):
        for x in range(0, img.w, 7):
            o = (y * img.w + x) * 3
            if msk.px[o + 1] == 0:
                for c in range(3):
                    acc[c] += img.px[o + c]
                n += 1
    mean = [v / n for v in acc]
    de = tiles.delta_e2000(mean, [0x47, 0x4A, 0x51])
    assert de <= 2.0, (mean, de)
    # edge columns of the mask equal the half joints of both sides (seamless): G of column 0 == G of column w-1
    g0 = [msk.px[(y * msk.w) * 3 + 1] for y in range(msk.h)]
    g1 = [msk.px[(y * msk.w + msk.w - 1) * 3 + 1] for y in range(msk.h)]
    edge = sum(abs(a_ - b_) for a_, b_ in zip(g0, g1)) / msk.h
    assert edge <= 1.0, edge
    try:
        agr.edits_100('mat.tiles', 'apply', p)
        raise AssertionError('second apply into an existing folder was not refused')
    except Exception as exc:  # noqa: BLE001 - stale preview (folder exists) or FileExistsError
        refused = type(exc).__name__ + ': ' + str(exc)[:80]
    return {'preview_codes': got, 'preview_s': preview_s, 'apply_s': apply_s, 'written': a['plan']['written'],
            'files': sorted(files), 'D_7024_mean_body': [round(v, 2) for v in mean], 'D_7024_dE2000': round(de, 3),
            'mask_edge_G_levels': edge, 'second_apply': refused,
            'maps': [{k: m_[k] for k in ('base_map', 'size_px', 'seam_levels', 'grey_ref')} for m_ in man['maps']]}


# ---- tex.plug_colour --------------------------------------------------------------------------------------------
def _png(path, w, h, n, px):
    path.write_bytes(tex.encode_png(tex.Image(w, h, n, bytes(px))))


def plug_colour():
    reset()
    src = OUT / 'plug_src'
    src.mkdir()
    _png(src / 'solid.png', 64, 64, 3, bytes([200, 100, 50]) * 4096)
    _png(src / 'grey128.png', 64, 64, 3, bytes([128] * 3) * 4096)
    mix = bytearray(bytes([200, 100, 50]) * 4096)
    for i in range(385):  # 9.4 % blue first in scan order
        mix[i * 3:i * 3 + 3] = bytes([0, 0, 255])
    _png(src / 'mix.png', 64, 64, 3, mix)
    row0 = bytearray(bytes([200, 100, 50]) * 4096)
    row0[0:64 * 3] = bytes([0, 0, 255]) * 64
    _png(src / 'row0.png', 64, 64, 3, row0)
    rgba = bytearray()
    for i in range(4096):
        rgba += bytes([0, 0, 0, 0]) if i < 2560 else bytes([0, 255, 0, 255])
    _png(src / 'rgba.png', 64, 64, 4, rgba)
    (src / 'pal.png').write_bytes(tex.encode_palette_png(10, 10, [(10, 20, 30), (200, 100, 50)],
                                                         [0] * 30 + [1] * 70))
    _png(src / 'big512.png', 512, 512, 3, bytes([1, 2, 3]) * (512 * 512))
    _png(src / 'tall.png', 256, 1024, 3, bytes([4, 5, 6]) * (256 * 1024))
    bmp = rt.dotNetObject('System.Drawing.Bitmap', str(src / 'solid.png'))
    bmp.Save(str(src / 'solid.jpg'), rt.dotNetClass('System.Drawing.Imaging.ImageFormat').Jpeg)
    bmp.Dispose()
    tga = bytearray([0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 8, 0, 24, 0x20]) + bytes([50, 100, 200]) * 64
    (src / 'solid.tga').write_bytes(bytes(tga))
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir()}
    t0 = time.time()
    r = agr.edits_100('tex.plug_colour', 'preview', None, None, {'folder': str(src)})
    took = round(time.time() - t0, 2)
    rows = {Path(x['file']).name: x for x in r['plan']['files']}
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in src.iterdir()}
    assert after == before, 'sources changed'
    want = {'solid.png': ([200, 100, 50], 'pass'), 'grey128.png': ([128, 128, 128], 'pass'),
            'mix.png': ([200, 100, 50], 'spread'), 'rgba.png': ([0, 255, 0], 'pass'),
            'pal.png': ([200, 100, 50], 'spread'), 'big512.png': ([1, 2, 3], 'pass'),
            'tall.png': ([4, 5, 6], 'pass'), 'solid.tga': ([200, 100, 50], 'pass')}
    for name, (rgb, dec) in want.items():
        assert (rows[name]['chosen'], rows[name]['decision']) == (rgb, dec), (name, rows[name])
    assert rows['rgba.png']['transparent_share'] == 0.625
    assert {'rgb': [0, 0, 255], 'share': 0.015625} in rows['row0.png']['top']
    jpg = rows['solid.jpg']
    assert jpg['decoder'] == 'dotnet' and max(abs(a - b) for a, b in zip(jpg['chosen'], [200, 100, 50])) <= 3, jpg
    try:
        agr.edits_100('tex.plug_colour', 'apply', r)
        raise AssertionError('apply of a read-only row')
    except ValueError as exc:
        ro = str(exc)[:60]
    # node mode: a plane whose material bitmap is a plug
    pl = rt.Plane(name='PLUG_Node_001', width=2, length=2)
    mat = rt.StandardMaterial(name='M_Plug')
    mat.diffuseMap = rt.BitmapTexture(filename=str(src / 'mix.png'))
    pl.material = mat
    rn = agr.edits_100('tex.plug_colour', 'preview', None, [pl])
    assert codes(rn) == {'PLUG_Node_001': ['plug_spread']}, codes(rn)
    return {'seconds': took, 'files': {k: {'chosen': v.get('chosen'), 'decision': v['decision'],
                                           'transparent_share': v.get('transparent_share'), 'stride': v.get('stride')}
                                       for k, v in sorted(rows.items())},
            'jpg_chosen': jpg['chosen'], 'read_only_apply': ro, 'node_mode': codes(rn), 'sources_unchanged': True}


# ---- polygon rows of branch L -------------------------------------------------------------------------------------
def polygon_rows():
    sys.path.insert(0, str(ROOT / 'test-polygon' / 'build'))
    sys.path.insert(0, str(ROOT / 'test-polygon'))
    import polygon_core as core
    import build_scene
    cat = OUT / 'polygon' / 'catalog.json'  # polygon + fragments, as run_polygon.py hands it to the builder
    cat.parent.mkdir(parents=True, exist_ok=True)
    # load_catalog predicts with dt_ai (not in Max Python): the project interpreter writes it, as run_polygon.py does
    import subprocess
    code = ('import json, sys; sys.path[:0] = [sys.argv[1]]; import polygon_core as c; '
            'open(sys.argv[2], "w", encoding="utf-8").write(json.dumps(c.load_catalog(), ensure_ascii=False))')
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / 'src'), str(ROOT)]))
    subprocess.run([os.environ['AGR_PYTHON'], '-c', code, str(ROOT / 'test-polygon'), str(cat)], check=True, env=env,
                   cwd=str(ROOT), timeout=600)
    os.environ['AGR_POLYGON_CATALOG'] = str(cat)
    out = []
    frags = {b: st for b, st in core.load_fragments().items() if st['branch'] == 'L'}
    assert sorted(frags) == ['mat.table', 'mat.tiles', 'tex.plug_colour'], sorted(frags)
    for button, st in sorted(frags.items()):
        scenes = sorted({o['scene'] for o in st['objects']})
        for scene in scenes:
            reset()
            build_scene.build(scene, texture_dir=str(OUT / 'polygon' / 'textures'))
            names = [o['name'] for o in st['objects'] if o['scene'] == scene]
            nodes = [rt.getNodeByName(n) for n in names]
            rt.select(nodes)
            try:
                report = agr.edits_100(st['tool'], 'preview', None, nodes, st['options'])
            except Exception as exc:  # noqa: BLE001
                report = {'status': 'error', 'error': '{}: {}'.format(type(exc).__name__, exc)}
            exp = [e for e in st['expected'] if e['scene'] == scene]
            mism = core.compare_report(exp, report)
            live = core.actual_codes(report) or {}
            for e in exp:
                got = live.get(e['name'])
                out.append({'button': button, 'name': e['name'],
                            'expected': '{} {}'.format(e['expect'], ','.join(e['codes'])).strip(),
                            'got': None if got is None else '{} {}'.format('fail' if got else 'pass', ','.join(got)).strip(),
                            'ok': not [m for m in mism if m.get('name') in (e['name'], '')]})
    summary['polygon_rows'] = out
    bad = [r for r in out if not r['ok']]
    assert not bad, bad
    return {'rows': len(out), 'ok': sum(r['ok'] for r in out)}


check('mat_table', mat_table)
check('mat_tiles', mat_tiles)
check('tex_plug_colour', plug_colour)
check('polygon_L', polygon_rows)
journal = OUT / 'journal' / 'untitled.jsonl'
summary['journal_lines'] = len(journal.read_text(encoding='utf-8').splitlines()) if journal.is_file() else 0
(OUT / 'summary.json').write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
print('MATERIALS_NATIVE checks', sorted(k for k in summary['checks'] if not k.endswith('_s')),
      'errors', sorted(summary['errors']))
assert not summary['errors'], 'native materials run failed: see summary.json'
