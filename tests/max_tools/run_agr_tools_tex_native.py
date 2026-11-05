"""new-case: #908 branch B native run of tex.format_fix, tex.placeholders, scene.missing_maps in locked batch Max.

Run via the lab DCC runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched) and runs the lab "minimal acceptance" of each button in the
real Max Python on SYNTHETIC files under OUT/data and a disposable unsaved scene:
* format_fix: RGBA half-transparent, palette, gray8, RGB16, RGB8 control, JPG (written by .NET System.Drawing),
  512x256, 1536^2 noise; output folder out/; sources unchanged; every output IHDR depth 8 / colour type 2.
* placeholders: slot 1, UDIM 1001, sizes 128 + 256, D [101,117,92], ERM [0,200,0], N default, folder without
  trailing separator; re-run refuses (md5 unchanged), version mode writes _v002.
* missing_maps: existing, missing without candidate, one candidate, two candidates (.png + .tga), hidden and UCX
  owners, a material without maps, a UDIM bitmap with one of three UV tiles missing; disk, names, file names and
  the save-required flag unchanged; no apply.
Nothing is saved; the scene is never written.

0.9 (#979 branch E1, cards T01/T02/T05/T06) adds:
* format_fix_e1: defaults (dither on, max_rmse 0.03): 1536^2 noise -> refused for quality (RMSE in the reason, not
  «готово»), 256^2 textured file under the limit untouched, RGBA half transparent -> colour type 2, 16-bit gray ->
  8 bit (not 255), %TEMP% listing identical before/after (a JPG decoded through .NET in between); panel press
  from a selection reports per object (`tex_quality` finding);
* placeholders_e1: UDIMs [1001, 1001] -> second set refused, never written twice; metal slot ERM [0,0,255]; TGA
  diffuse source -> Diffuse skipped with reason, ERM/Normal written; two selected addresses -> two sets, an
  existing file -> `placeholder_exists` on its object only;
* missing_maps_e1: missing map of SM_Bench_001_Main with mask candidates .png and .jpg -> both, rank 2, ambiguous,
  without any search folder; a relative search folder is refused; disk unchanged.
"""
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
import time
import traceback
import zlib

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
DATA = OUT / 'data'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}, 'seconds': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.time() - t, 2)


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    return agr


agr = install()
tex = agr._load_core('tex_core.py', 'agr_tools_tex_core')
checks_core = agr._load_core('checks_core.py', 'agr_tools_checks_core')
model = agr._load_core('ui_model.py', 'agr_tools_ui_model')
MACRO = {a.tool: a.macro for a in model.ACTIONS if a.tool in ('tex.format_fix', 'tex.placeholders',
                                                               'scene.missing_maps')}


# ---- synthetic files ----------------------------------------------------------------------------------
def _chunk(kind, body):
    return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)


def _png(w, h, ctype, depth, rows, plte=None):
    out = b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
    if plte:
        out += _chunk(b'PLTE', plte)
    return out + _chunk(b'IDAT', zlib.compress(b''.join(b'\x00' + r for r in rows), 6)) + _chunk(b'IEND', b'')


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def tree(root):
    return sorted((str(p.relative_to(root)), md5(p)) for p in Path(root).rglob('*') if p.is_file())


def jpg(path, colour, w=64, h=64):
    """A real JPG written by .NET System.Drawing (the decoder the glue uses is the same API)."""
    bmp = rt.dotNetObject('System.Drawing.Bitmap', w, h)
    g = rt.dotNetClass('System.Drawing.Graphics').FromImage(bmp)
    g.Clear(rt.dotNetClass('System.Drawing.Color').FromArgb(*colour))
    g.Dispose()
    bmp.Save(str(path), rt.dotNetClass('System.Drawing.Imaging.ImageFormat').Jpeg)
    bmp.Dispose()


def format_data():
    src = DATA / 'fmt'
    src.mkdir(parents=True)
    w = 64
    files = {
        '01_rgba_half.png': _png(w, w, 6, 8, [bytes((200, 40, 40, 255)) * (w // 2) + bytes((0, 255, 0, 0)) * (w // 2)] * w),
        '02_palette.png': _png(32, 32, 3, 8, [bytes(((x + y) % 3 for x in range(32))) for y in range(32)],
                               plte=bytes((255, 0, 0, 0, 255, 0, 0, 0, 255))),
        '03_gray8.png': _png(32, 32, 0, 8, [bytes((x * 8) % 256 for x in range(32))] * 32),
        '05_rgb16.png': _png(32, 32, 2, 16, [b''.join(struct.pack('>HHH', x * 2000, y * 2000, 65535) for x in range(32))
                                            for y in range(32)]),
        '06_control.png': _png(32, 32, 2, 8, [b''.join(bytes((x * 7 % 256, y * 7 % 256, 99)) for x in range(32))
                                              for y in range(32)]),
        '07_wide.png': _png(512, 256, 2, 8, [b''.join(bytes((x % 256, y % 256, 50)) for x in range(512))
                                             for y in range(256)]),
    }
    rnd = random.Random(908)
    files['08_noise.png'] = _png(1536, 1536, 2, 8, [rnd.randbytes(1536 * 3) for _ in range(1536)])
    for k, v in files.items():
        (src / k).write_bytes(v)
    jpg(src / '04_photo.jpg', (10, 120, 30))
    return src


# ---- format_fix ---------------------------------------------------------------------------------------
def format_fix():
    src = format_data()
    sources = sorted(str(p) for p in src.iterdir())
    before = {p: md5(p) for p in sources}
    out = DATA / 'fmt_out' / 'out'
    # 0.8 lab L03 acceptance under the 0.8 settings (no dithering, no quality floor); 0.9 defaults: format_fix_e1
    opts = {'files': sources, 'out': str(out), 'background': [0, 0, 0], 'dither': False, 'max_rmse': 1.0}
    prev = agr.edits_080('tex.format_fix', 'preview', options=opts)
    assert agr.parse_report(json.dumps(prev)) == prev
    assert not out.exists(), 'preview wrote files'
    rep = agr.edits_080('tex.format_fix', 'apply', prev)
    assert {p: md5(p) for p in sources} == before, 'sources changed'
    written = rep['plan']['written']
    assert len(written) == 8 and not rep['plan']['skipped'], (rep['plan']['skipped'], written)
    fmt = {}
    for w in written:
        info = checks_core.png_info(Path(w).read_bytes())
        # 8 bits per channel, no alpha; palette (colour type 3) allowed: decision of Artem 05.11.2026
        assert info[2] == 8 and info[4] is False and info[3] in (2, 3), (w, info)
        fmt[Path(w).name] = list(info[:2])
    by = {Path(f['source']).name: f for f in rep['plan']['files']}
    img, _ = tex.decode_png(Path(by['01_rgba_half.png']['out']).read_bytes())
    assert img.px[(10 * 64 + 63) * 3:(10 * 64 + 64) * 3] == b'\x00\x00\x00'
    assert img.px[(10 * 64 + 1) * 3:(10 * 64 + 2) * 3] == bytes((200, 40, 40))
    jimg, _ = tex.decode_png(Path(by['04_photo.jpg']['out']).read_bytes())
    mean = [sum(jimg.px[c::3]) / (len(jimg.px) // 3) for c in range(3)]
    assert all(abs(m - e) < 4 for m, e in zip(mean, (10, 120, 30))), mean
    assert by['07_wide.png']['size_px'] == [512, 256] and 'not square' in by['07_wide.png']['notes'][0]
    noise = by['08_noise.png']
    assert noise['bytes_out'] <= 3 * 1024 * 1024 and noise['rmse'] > 0, noise
    assert noise['encoding'] == 'palette_quantized', noise
    assert Path(by['02_palette.png']['out']).read_bytes() == (src / '02_palette.png').read_bytes()
    assert Path(by['06_control.png']['out']).read_bytes() == (src / '06_control.png').read_bytes()
    with_alpha_refused = agr.edits_080('tex.format_fix', 'preview',
                                       options={'files': [sources[0]], 'out': str(DATA / 'never')})
    assert 'forbidden' in with_alpha_refused['plan']['skipped'][0]['reason']
    try:
        agr.edits_080('tex.format_fix', 'apply', prev)
    except Exception as exc:  # noqa: BLE001 - the stale preview must be refused
        stale = type(exc).__name__
    else:
        raise AssertionError('second apply accepted')
    return {'written': len(written), 'sizes': fmt, 'noise': {k: noise[k] for k in ('bytes_in', 'lossless_bytes', 'bytes_out', 'rmse',
                                                                                      'actions', 'encoding', 'colours',
                                                                                      'max_channel_error')},
            'jpg_mean': [round(m, 1) for m in mean], 'second_apply': stale,
            'preview_hash': prev['plan']['hash'][:16]}


def format_fix_from_selection():
    """Panel press path: maps of the selected object, default new folder beside the source, preview only."""
    folder = DATA / 'sel'
    folder.mkdir(parents=True)
    tex_path = folder / 'T_sel_d_1.png'
    tex_path.write_bytes(_png(8, 8, 3, 8, [bytes(8)] * 8, plte=bytes((1, 2, 3))))
    box = rt.Box(name='SM_Sel_Main', length=1, width=1, height=1)
    box.material = rt.StandardMaterial(name='M_Sel_Main_1', diffuseMap=rt.BitmapTexture(filename=str(tex_path)))
    rt.select(box)
    ok = bool(rt.macros.run('AGR Tools', MACRO['tex.format_fix']))
    rep = json.loads((Path(agr.reports_dir()) / 'tex.format_fix.json').read_text(encoding='utf-8'))
    assert ok and rep['plan']['mode'] == 'preview' and rep['plan']['files'][0]['source'] == str(tex_path), rep
    assert Path(rep['plan']['out']).parent == folder and not Path(rep['plan']['out']).exists()
    rt.delete(box)
    return {'out': Path(rep['plan']['out']).name, 'actions': rep['plan']['files'][0]['actions']}


# ---- placeholders -------------------------------------------------------------------------------------
def placeholders():
    folder = DATA / 'maps'  # no trailing separator
    opts = {'folder': str(folder), 'address': 'Addr', 'slots': [1], 'udim': 1001, 'sizes': [128, 256],
            'colours': {'Diffuse': [101, 117, 92], 'ERM': [0, 200, 0]}}
    prev = agr.edits_080('tex.placeholders', 'preview', options=opts)
    assert not folder.exists()
    rep = agr.edits_080('tex.placeholders', 'apply', prev)
    written = rep['plan']['written']
    want = {'Diffuse': (101, 117, 92), 'ERM': (0, 200, 0), 'Normal': (128, 128, 255)}
    assert len(written) == 6
    for w in written:
        p = Path(w)
        assert folder in p.parents and p.name.startswith('T_Addr_') and p.name.endswith('_1.1001.png'), w
        data = p.read_bytes()
        side = int(p.parent.name)
        assert checks_core.png_info(data)[:5] == (side, side, 8, 2, False)
        img, _ = tex.decode_png(data)
        assert set(zip(*[iter(img.px)] * 3)) == {want[p.name.split('_')[2]]}, w
    assert not list(DATA.glob('maps*.png'))
    keep = {w: md5(w) for w in written}
    again = agr.edits_080('tex.placeholders', 'preview', options=opts)
    assert again['plan']['done'] == [] and len(again['plan']['skipped']) == 6
    ver = agr.edits_080('tex.placeholders', 'apply',
                        agr.edits_080('tex.placeholders', 'preview', options=dict(opts, on_exists='version')))
    assert all('_v002.png' in w for w in ver['plan']['written']) and len(ver['plan']['written']) == 6
    assert {w: md5(w) for w in written} == keep
    box = rt.Box(name='SM_Addr2_Ground', length=1, width=1, height=1)
    rt.select(box)
    sel = agr.edits_080('tex.placeholders', 'preview', options={'folder': str(DATA / 'maps_sel')})
    rt.delete(box)
    names = sorted(Path(d['path']).name for d in sel['plan']['done'])
    assert names == ['T_Addr2_Ground_Diffuse_1.1001.png', 'T_Addr2_Ground_ERM_1.1001.png',
                     'T_Addr2_Ground_Normal_1.1001.png'], names
    try:
        agr.edits_080('tex.placeholders', 'preview', options={'address': 'Addr'})
    except ValueError as exc:
        unsaved = str(exc)
    else:
        raise AssertionError('unsaved scene accepted a relative default folder')
    assert 'not saved' in unsaved
    return {'written': [str(Path(w).relative_to(DATA)) for w in written], 'refused_again': 6,
            'versioned': len(ver['plan']['written']), 'from_selection': names}


# ---- missing maps -------------------------------------------------------------------------------------
def _bitmap_mat(name, path):
    return rt.StandardMaterial(name=name, diffuseMap=rt.BitmapTexture(filename=str(path), name='Map_' + name))


def _udim_plane():
    p = rt.Plane(name='SM_Udim_Main', length=1, width=3, lengthsegs=1, widthsegs=3)
    rt.convertToMesh(p)
    m = p.mesh
    nv = int(rt.getNumVerts(m))
    rt.meshop.setMapSupport(m, 1, True)
    rt.meshop.setNumMapVerts(m, 1, nv)
    for i in range(1, nv + 1):
        v = rt.getVert(m, i)
        rt.meshop.setMapVert(m, 1, i, rt.Point3(float(v.x) + 1.5, float(v.y) + 0.5, 0))
    for f in range(1, int(rt.getNumFaces(m)) + 1):
        rt.meshop.setMapFace(m, 1, f, rt.getFace(m, f))
    rt.update(p)
    return p


def missing_maps():
    root = DATA / 'scene'
    (root / 'cands' / 'a').mkdir(parents=True)
    (root / 'cands' / 'b').mkdir(parents=True)
    ok = root / 'T_ok_d_1.png'
    ok.write_bytes(_png(64, 32, 2, 8, [bytes(64 * 3)] * 32))
    (root / 'cands' / 'a' / 'T_one_d_1.png').write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    (root / 'cands' / 'a' / 'T_two_d_1.png').write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    (root / 'cands' / 'b' / 'T_two_d_1.tga').write_bytes(bytes([0, 0, 2]) + bytes(9) + struct.pack('<HH', 4, 4)
                                                          + b'\x18\x00' + bytes(48))
    (root / 'T_u_Diffuse_1.1001.png').write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    (root / 'T_u_Diffuse_1.1003.png').write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    gone = root / 'gone'
    nodes = {}
    for name, path in (('SM_Ok_Main', ok), ('SM_None_Main', gone / 'T_none_d_1.png'),
                       ('SM_One_Main', gone / 'T_one_d_1.png'), ('SM_Two_Main', gone / 'T_two_d_1.png'),
                       ('SM_Hid_Main', gone / 'T_hid_d_1.png'), ('UCX_SM_X_Main_001', gone / 'T_ucx_d_1.png')):
        b = rt.Box(name=name, length=1, width=1, height=1)
        b.material = _bitmap_mat('M_' + name, path)
        nodes[name] = b
    rt.hide(nodes['SM_Hid_Main'])
    plain = rt.Box(name='SM_NoMaps_Main', length=1, width=1, height=1)
    plain.material = rt.StandardMaterial(name='M_NoMaps')
    udim = _udim_plane()
    udim.material = _bitmap_mat('M_Udim', root / 'T_u_Diffuse_1.<UDIM>.png')
    names_before = sorted(str(n.name) for n in rt.objects)
    files_before = {str(n.name): str(n.material.diffuseMap.filename) for n in rt.objects
                    if n.material is not None and rt.isProperty(n.material, 'diffuseMap') and n.material.diffuseMap is not None}
    disk_before = tree(DATA)
    rt.setSaveRequired(False)
    rep = agr.edits_080('scene.missing_maps', 'preview', options={'search': [str(root / 'cands')]})
    assert agr.parse_report(json.dumps(rep)) == rep
    assert tree(DATA) == disk_before, 'disk changed'
    assert sorted(str(n.name) for n in rt.objects) == names_before
    assert {str(n.name): str(n.material.diffuseMap.filename) for n in rt.objects if n.material is not None
            and rt.isProperty(n.material, 'diffuseMap') and n.material.diffuseMap is not None} == files_before
    save_required = bool(rt.getSaveRequired())
    rows = {os.path.basename(r['path']): r for r in rep['plan']['maps']}
    paths = [r['path'] for r in rep['plan']['maps']]
    assert len(paths) == len(set(paths))
    missing = sorted(k for k, r in rows.items() if not r['exists'])
    assert missing == ['T_hid_d_1.png', 'T_none_d_1.png', 'T_one_d_1.png', 'T_two_d_1.png', 'T_u_Diffuse_1.1002.png',
                       'T_ucx_d_1.png'], missing
    assert rows['T_hid_d_1.png']['hidden'] and rows['T_ucx_d_1.png']['ucx']
    assert rows['T_two_d_1.png']['ambiguous'] and [c['rank'] for c in rows['T_two_d_1.png']['candidates']] == [0, 1]
    assert len(rows['T_one_d_1.png']['candidates']) == 1 and not rows['T_one_d_1.png']['ambiguous']
    assert rows['T_none_d_1.png']['candidates'] == []
    assert rows['T_ok_d_1.png']['exists'] and rows['T_ok_d_1.png']['size_px'] == [64, 32]
    assert [rows['T_u_Diffuse_1.{}.png'.format(t)]['in_uv'] for t in (1001, 1002, 1003)] == [True, True, True]
    objs = {o['name']: o for o in rep['objects']}
    assert 'SM_NoMaps_Main' not in objs or not objs['SM_NoMaps_Main']['findings']
    assert not any('M_NoMaps' in json.dumps(r['owners']) for r in rep['plan']['maps'])
    assert rep['status'] == 'fail' and rep['plan']['ambiguous']
    try:
        agr.edits_080('scene.missing_maps', 'apply', rep)
    except ValueError as exc:
        assert 'read-only' in str(exc)
    else:
        raise AssertionError('read-only tool accepted apply')
    rt.select(nodes['SM_Ok_Main'])
    ok_macro = bool(rt.macros.run('AGR Tools', MACRO['scene.missing_maps']))
    saved = json.loads((Path(agr.reports_dir()) / 'scene.missing_maps.json').read_text(encoding='utf-8'))
    # the panel press has no search folder: same paths/missing, candidates only from scene asset folders
    assert ok_macro and [saved['plan']['summary'][k] for k in ('paths', 'missing', 'hidden', 'ucx')] == \
        [rep['plan']['summary'][k] for k in ('paths', 'missing', 'hidden', 'ucx')], saved['plan']['summary']
    assert [str(n.name) for n in rt.selection] == ['SM_Ok_Main']
    (OUT / 'missing_maps_table.txt').write_text('\n'.join(rep['plan']['table']), encoding='utf-8')
    return {'summary': rep['plan']['summary'], 'missing': missing, 'save_required_after': save_required,
            'notes': rep['plan']['notes'], 'table_lines': len(rep['plan']['table'])}


# ---- 0.9 rework (#979 E1) -------------------------------------------------------------------------------
def format_fix_e1():
    import tempfile
    src = DATA / 'fmt_e1'
    src.mkdir(parents=True)
    rnd = random.Random(979)
    files = {
        'T_noise_d_1.png': _png(1536, 1536, 2, 8, [rnd.randbytes(1536 * 3) for _ in range(1536)]),
        'T_tex_d_1.png': _png(256, 256, 2, 8, [b''.join(bytes((x, y, (x * y) % 256)) for x in range(256))
                                               for y in range(256)]),
        'T_rgba_d_1.png': _png(64, 64, 6, 8, [bytes((200, 40, 40, 255)) * 32 + bytes((0, 255, 0, 0)) * 32] * 64),
        'T_g16_d_1.png': _png(16, 16, 0, 16, [struct.pack('>16H', *([1000] * 16))] * 16),
    }
    for k, v in files.items():
        (src / k).write_bytes(v)
    jpg(src / 'T_photo_d_1.jpg', (10, 120, 30))
    sources = sorted(str(p) for p in src.iterdir())
    temp = Path(tempfile.gettempdir())
    temp_before = sorted(p.name for p in temp.iterdir())
    t0 = time.time()
    prev = agr.edits_080('tex.format_fix', 'preview', options={'files': sources, 'out': str(DATA / 'fmt_e1_out'),
                                                               'background': [0, 0, 0]})
    seconds = round(time.time() - t0, 1)
    rep = agr.edits_080('tex.format_fix', 'apply', prev)
    temp_after = sorted(p.name for p in temp.iterdir())
    by = {Path(f['source']).name: f for f in rep['plan']['files']}
    noise = by['T_noise_d_1.png']
    assert noise.get('quality_fail') and 'max_rmse' in noise['reason'] and 'out' not in noise, noise
    assert by['T_tex_d_1.png']['actions'] == ['copied_unchanged']
    assert checks_core.png_info(Path(by['T_rgba_d_1.png']['out']).read_bytes())[3] == 2
    g16, _ = tex.decode_png(Path(by['T_g16_d_1.png']['out']).read_bytes())
    assert set(g16.px) == {4}, sorted(set(g16.px))[:4]
    assert len(rep['plan']['written']) == 4 and temp_after == temp_before, (set(temp_after) ^ set(temp_before))
    # panel press from the selection: one object per texture owner, `tex_quality` on the noise owner
    good = rt.Box(name='SM_FmtOk_Main', length=1, width=1, height=1)
    good.material = rt.StandardMaterial(name='M_FmtOk', diffuseMap=rt.BitmapTexture(filename=str(src / 'T_tex_d_1.png')))
    bad = rt.Box(name='SM_FmtBad_Main', length=1, width=1, height=1)
    bad.material = rt.StandardMaterial(name='M_FmtBad', diffuseMap=rt.BitmapTexture(filename=str(src / 'T_noise_d_1.png')))
    rt.select([good, bad])
    sel = agr.edits_080('tex.format_fix', 'preview')
    codes = {o['name']: [f['code'] for f in o['findings']] for o in sel['objects']}
    rt.delete([good, bad])
    assert codes == {'SM_FmtOk_Main': [], 'SM_FmtBad_Main': ['tex_quality']} and sel['status'] == 'fail', codes
    return {'noise': {k: noise.get(k) for k in ('encoding', 'rmse', 'tried', 'reason')}, 'preview_seconds': seconds,
            'temp_unchanged': True, 'selection_codes': codes}


def placeholders_e1():
    folder = DATA / 'maps_e1'
    prev = agr.edits_080('tex.placeholders', 'preview', options={
        'folder': str(folder), 'address': 'Dup', 'udims': [1001, 1001], 'slots': [1, 2], 'metal_slots': [2]})
    dup = [f for f in prev['plan']['files'] if f.get('code') == 'placeholder_duplicate']
    rep = agr.edits_080('tex.placeholders', 'apply', prev)
    written = rep['plan']['written']
    assert len(dup) == 6 and len(written) == len(set(written)) == 6, (len(dup), written)
    erm2 = [w for w in written if '_ERM_2.' in w][0]
    img, _ = tex.decode_png(Path(erm2).read_bytes())
    assert set(zip(*[iter(img.px)] * 3)) == {(0, 0, 255)}
    tga = DATA / 'src_e1.tga'
    tga.write_bytes(bytes([0, 0, 2]) + bytes(9) + struct.pack('<HH', 4, 4) + b'\x18\x00' + bytes(48))
    t = agr.edits_080('tex.placeholders', 'preview', options={'folder': str(DATA / 'maps_tga'), 'address': 'Tga',
                                                              'diffuse_from': str(tga)})
    by = {f['map']: f for f in t['plan']['files']}
    assert by['Diffuse'].get('code') == 'placeholder_source' and 'reason' not in by['ERM'], by
    sel_folder = DATA / 'maps_sel_e1'
    sel_folder.mkdir()
    (sel_folder / 'T_PhBad_Diffuse_1.1001.png').write_bytes(b'old')
    a = rt.Box(name='SM_PhOk_Main', length=1, width=1, height=1)
    b = rt.Box(name='SM_PhBad_Main', length=1, width=1, height=1)
    rt.select([a, b])
    two = agr.edits_080('tex.placeholders', 'preview', options={'folder': str(sel_folder)})
    rt.delete([a, b])
    codes = {o['name']: [f['code'] for f in o['findings']] for o in two['objects']}
    assert codes == {'SM_PhOk_Main': [], 'SM_PhBad_Main': ['placeholder_exists']}, codes
    assert (sel_folder / 'T_PhBad_Diffuse_1.1001.png').read_bytes() == b'old'
    return {'duplicates_refused': len(dup), 'written': len(written), 'tga_reason': by['Diffuse']['reason'],
            'two_sets_codes': codes}


def missing_maps_e1():
    root = DATA / 'scene_e1'
    lib = root / 'lib'
    lib.mkdir(parents=True)
    ok = lib / 'T_MmOk_d_1.png'
    ok.write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    (lib / 'T_Bench_001_Main_d_1.png').write_bytes(_png(4, 4, 2, 8, [bytes(12)] * 4))
    jpg(lib / 'T_Bench_001_Main_d_1.jpg', (1, 2, 3), 4, 4)
    good = rt.Box(name='SM_MmOk_Main', length=1, width=1, height=1)
    good.material = _bitmap_mat('M_MmOk', ok)
    bench = rt.Box(name='SM_Bench_001_Main', length=1, width=1, height=1)
    bench.material = _bitmap_mat('M_Bench', lib / 'old' / 'src_diffuse.png')
    disk = tree(root)
    # without nodes the tool reads the whole scene (the 0.8 check's nodes are still there): name the two objects
    rep = agr.edits_080('scene.missing_maps', 'preview', nodes=[good, bench])
    assert tree(root) == disk
    row = [r for r in rep['plan']['maps'] if r['path'].endswith('src_diffuse.png')][0]
    names = sorted(Path(c['path']).name for c in row['candidates'])
    assert names == ['T_Bench_001_Main_d_1.jpg', 'T_Bench_001_Main_d_1.png'] and row['ambiguous'], row
    assert {c['rank'] for c in row['candidates']} == {2} and row['owners'][0]['role'] == 'diffuse', row
    codes = {o['name']: [f['code'] for f in o['findings']] for o in rep['objects']}
    assert codes == {'SM_MmOk_Main': [], 'SM_Bench_001_Main': ['map_missing']}, codes
    try:
        agr.edits_080('scene.missing_maps', 'preview', options={'search': ['123']})
    except ValueError as exc:
        relative = str(exc)[:80]
    else:
        raise AssertionError('relative search folder accepted')
    rt.delete([good, bench])
    return {'candidates': row['candidates'], 'masks': row['masks'], 'slot': row['owners'][0]['slot'],
            'relative_refused': relative}


for name, fn in (('format_fix', format_fix), ('format_fix_selection', format_fix_from_selection),
                 ('placeholders', placeholders), ('missing_maps', missing_maps),
                 ('format_fix_e1', format_fix_e1), ('placeholders_e1', placeholders_e1),
                 ('missing_maps_e1', missing_maps_e1)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908B_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:4000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
