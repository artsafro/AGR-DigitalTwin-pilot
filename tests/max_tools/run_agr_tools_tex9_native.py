"""new-case: #979 branch B native run in locked batch Max on DISPOSABLE synthetic scenes (lab DCC runner only).

AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP. The MZP is installed into OUT (no user
folders touched); every texture is written by this script under OUT; nothing is saved.
Buttons: tex.erm_normal_check, udim.slots (read), udim.matid_unwrap, tex.finish_map, atlas.groundel (+ the npm
profile of the atlas.npm rework), atlas.flora (preview -> apply on export copies / new files), each through
runtime.edits_090 exactly as the panel presses it. Sources are compared before/after (mesh hash with MatIDs,
stack, material, file md5).
"""
import hashlib
import json
import math
import os
import struct
import sys
import time
import traceback
import zlib
from pathlib import Path

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
TEX = OUT / 'tex'
TEX.mkdir()
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_NO_PROMPT'] = '1'
os.environ['AGR_TEST_OUTPUT_ATLAS'] = str(OUT / 'atlases')
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}, 'seconds': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t0 = time.time()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary['seconds'][name] = round(time.time() - t0, 2)


def install():
    rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
    rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
    rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
    rt.makeDir(rt.AGRToolsStartupRoot, all=True)
    rt.fileIn(str(PACKAGE))
    sys.path.insert(0, str(OUT / 'installed'))
    import runtime as agr
    return agr


agr = install()
tq = agr._load_core('texqa_core.py', 'agr_tools_texqa_core')
emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')


# ---- helpers ------------------------------------------------------------------------------------------------
def reset(units='meters'):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def png(path, w, h, px, ch):
    Path(path).write_bytes(tq.write_png(w, h, px, ch))
    return str(path)


def md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


def box(name, w=1.0, l=1.0, h=1.0, pos=(0, 0, 0), poly=True):
    b = rt.Box(name=name, width=w, length=l, height=h)
    b.pos = rt.Point3(*pos)
    if poly:
        rt.convertToPoly(b)
    return b


def bitmap(path):
    t = rt.Bitmaptexture()
    t.filename = str(path)
    return t


def source_state(nodes):
    snap = emax.snapshot(nodes)
    for s, n in zip(snap, sorted(nodes, key=lambda x: int(rt.getHandleByAnim(x)))):
        s['stack'] = [str(rt.classOf(n.baseObject))] + [str(rt.classOf(m)) for m in n.modifiers]
        s['material'] = None if n.material is None else str(n.material.name)
    return snap


def run(tool, nodes, options=None):
    rep = agr.edits_090(tool, 'preview', None, nodes, options)
    assert agr.parse_report(json.dumps(rep)) == rep
    return rep


def apply(tool, nodes, preview):
    rep = agr.edits_090(tool, 'apply', preview, nodes)
    assert agr.parse_report(json.dumps(rep)) == rep
    return rep


# ---- pictures -----------------------------------------------------------------------------------------------
def dome(size, directx):
    px = bytearray()
    c, R = (size - 1) / 2.0, 0.42 * size
    for y in range(size):
        for x in range(size):
            dx, dy = (x - c) / R, (y - c) / R
            r2 = dx * dx + dy * dy
            if r2 < 0.98:
                hz = math.sqrt(1 - r2)
                nx, g = dx / hz, -dy / hz
                ln = math.sqrt(nx * nx + g * g + 1)
                nx, g, nz = nx / ln, g / ln, 1 / ln
            else:
                nx, g, nz = 0.0, 0.0, 1.0
            g = -g if directx else g
            px += bytes((int(round((nx + 1) * 127.5)), int(round((g + 1) * 127.5)), int(round((nz + 1) * 127.5))))
    return bytes(px)


def jpeg_bytes():
    sof = b'\xff\xc0' + struct.pack('>HBHHB', 11, 8, 64, 64, 1) + b'\x01\x11\x00'
    return b'\xff\xd8\xff\xe0' + struct.pack('>H', 16) + b'JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00' + sof + b'\xff\xd9'


def pattern(side, seed, w=None):
    w = w or side
    return bytes(v for y in range(side) for x in range(w) for v in ((x * 7 + seed * 40) % 256, (y * 5 + seed * 20) % 256,
                                                                     (x + y + seed * 9) % 256))


# ---- tex.erm_normal_check -----------------------------------------------------------------------------------
def erm_normal():
    reset()
    files = {
        'flat': png(TEX / 'T_Flat_Normal_1.1001.png', 64, 64, bytes((128, 128, 255)) * 4096, 3),
        'dx': png(TEX / 'T_Dx_Normal_1.1001.png', 96, 96, dome(96, True), 3),
        'gl': png(TEX / 'T_Gl_Normal_1.1001.png', 96, 96, dome(96, False), 3),
        'alpha': png(TEX / 'T_Al_Normal_1.1001.png', 32, 32, bytes((128, 128, 255, 255)) * 1024, 4),
        'erm0': png(TEX / 'T_Clean_ERM_1.1001.png', 32, 32, bytes((0, 140, 0)) * 1024, 3),
        'glow': png(TEX / 'T_Glow_ERM_1.1001.png', 32, 32, bytes((0, 140, 0)) * 512 + bytes((200, 140, 0)) * 512, 3),
        'grey': png(TEX / 'T_Grey_ERM_1.1001.png', 32, 32, bytes((120, 120, 120)) * 1024, 3),
    }
    jpg = TEX / 'T_Jpg_Normal_1.1001.png'
    jpg.write_bytes(jpeg_bytes())
    files['jpg'] = str(jpg)
    before = {k: md5(v) for k, v in files.items()}
    nodes = []
    for i, (key, role) in enumerate((('flat', 'n'), ('dx', 'n'), ('gl', 'n'), ('alpha', 'n'), ('jpg', 'n'),
                                     ('erm0', 'e'), ('glow', 'e'), ('grey', 'e'))):
        b = box('SM_Ermn_{}_Main'.format(key), pos=(i * 2, 0, 0))
        m = rt.Standardmaterial(name='M_Ermn_{}'.format(key))
        if role == 'n':
            nb = rt.Normal_Bump()
            nb.normal_map = bitmap(files[key])
            m.bumpMap = nb
        else:
            m.specularLevelMap = bitmap(files[key])
        b.material = m
        nodes.append(b)
    h = agr._load_core('texqa_max.py', 'agr_tools_texqa_max')
    summary['probe'] = {'slots': [[str(rt.getSubTexmapSlotName(nodes[0].material, i)),
                                   str(rt.classOf(rt.getSubTexmap(nodes[0].material, i)))]
                                  for i in range(1, int(rt.getNumSubTexmaps(nodes[0].material)) + 1)
                                  if rt.getSubTexmap(nodes[0].material, i) is not None],
                        'maps': [[m['slot'], m['path']] for m in h.material_maps(nodes[0].material)],
                        'emissive': h.emissive(nodes[0].material)}
    rep = run('tex.erm_normal_check', nodes)
    got = codes(rep)
    want = {'SM_Ermn_flat_Main': [], 'SM_Ermn_dx_Main': [], 'SM_Ermn_gl_Main': ['normal_opengl'],
            'SM_Ermn_alpha_Main': ['alpha_channel'], 'SM_Ermn_jpg_Main': ['format_mismatch'],
            'SM_Ermn_erm0_Main': [], 'SM_Ermn_glow_Main': ['erm_false_emission'], 'SM_Ermn_grey_Main': ['erm_grey']}
    assert got == want, got
    assert {k: md5(v) for k, v in files.items()} == before
    try:
        agr.edits_090('tex.erm_normal_check', 'apply', rep, nodes)
        raise AssertionError('apply accepted on a read row')
    except ValueError:
        pass
    return {'codes': got, 'md5_unchanged': True, 'done': len(rep['plan']['done'])}


# ---- udim.slots -----------------------------------------------------------------------------------------------
def slots():
    reset()
    tiny = tq.write_png(4, 4, bytes(48), 3)
    sets = {
        'Clean': ['T_Clean_{}_1.{}.png'.format(m, t) for m in ('Diffuse', 'ERM', 'Normal') for t in range(1001, 1006)],
        'Gap': ['T_Gap_Diffuse_1.{}.png'.format(t) for t in (1001, 1002, 1004, 1005)],
        'Over': ['T_Over_{}_1.{}.png'.format(m, t) for m in ('Diffuse', 'ERM', 'Normal') for t in range(1001, 1035)],
        'Slots': ['T_Slots_Diffuse_{}.1001.png'.format(s) for s in (1, 2, 4)],
    }
    nodes = []
    for i, (key, names) in enumerate(sets.items()):
        folder = TEX / ('slots_' + key)
        folder.mkdir()
        mm = rt.MultiMaterial(numsubs=len(names))
        mm.name = 'M_Slots_' + key
        for k, name in enumerate(names):
            (folder / name).write_bytes(tiny)
            sub = rt.Standardmaterial(name='S{}_{}'.format(key, k))
            sub.diffuseMap = bitmap(folder / name)
            mm.materialList[k] = sub
        b = box('SM_Slots_{}_Main'.format(key), pos=(i * 2, 0, 0))
        b.material = mm
        nodes.append(b)
    rep = run('udim.slots', nodes)
    got = codes(rep)
    want = {'SM_Slots_Clean_Main': [], 'SM_Slots_Gap_Main': ['udim_gap'], 'SM_Slots_Over_Main': ['maps_over_100'],
            'SM_Slots_Slots_Main': ['slot_gap']}
    assert got == want, got
    return {'codes': got}


# ---- udim.matid_unwrap ------------------------------------------------------------------------------------------
MAF = ((1, (0.5, 0.5, 0.8)), (2, (1.2, 0.4, 0.4)), (7, (0.3, 0.3, 2.0)), (12, (2.0, 1.0, 0.1)), (40, (0.8, 0.8, 0.8)))


def maf(name, scale):
    parts = []
    for k, (mid, (w, l, h)) in enumerate(MAF):
        b = box('tmp_{}'.format(k), w * scale, l * scale, h * scale, (k * 3.0 * scale, 0, 0))
        for f in range(1, int(rt.polyop.getNumFaces(b)) + 1):
            rt.polyop.setFaceMatID(b, f, mid)
        parts.append(b)
    base = parts[0]
    for p in parts[1:]:
        rt.polyop.attach(base, p)
    base.name = name
    return base


def unwrap_one(units, scale):
    reset(units)
    node = maf('SM_Maf_{}_Main'.format(units), scale)
    bent = rt.Plane(name='SM_MafBend_{}_Main'.format(units), length=1.0 * scale, width=2.0 * scale,
                    lengthsegs=4, widthsegs=8)
    bent.pos = rt.Point3(0, 5 * scale, 0)
    rt.addModifier(bent, rt.Bend(angle=60))
    rt.addModifier(bent, rt.Materialmodifier(materialID=3))
    nodes = [node, bent]
    before = source_state(nodes)
    rep = run('udim.matid_unwrap', nodes, {'px_per_m': 200.0})
    assert rep['status'] == 'pass', codes(rep)
    t0 = time.time()
    out = apply('udim.matid_unwrap', nodes, rep)
    seconds = time.time() - t0
    assert out['status'] == 'pass', codes(out)
    assert source_state(nodes) == before, 'source changed'
    rows = [r for r in out['plan']['done'] if r['source'] == node.name]
    tiles = {r['id']: r['tiles_after'] for r in rows}
    assert tiles == {1: [1001], 2: [1002], 7: [1007], 12: [1012], 40: [1040]}, tiles
    dens = [r['px_per_m'] for r in rows]
    assert all(abs(d - 200.0) <= 4.0 for d in dens), dens
    assert out['plan']['collapsed_copies'] and out['plan']['collapsed_copies'][0]['source'] == bent.name
    assert [str(rt.classOf(m)) for m in bent.modifiers] == ['Materialmodifier', 'Bend']
    return {'density': dens, 'tiles': tiles, 'copies': out['plan']['copies'], 'apply_s': round(seconds, 2),
            'collapsed': out['plan']['collapsed_copies']}


def matid_unwrap():
    m = unwrap_one('meters', 1.0)
    cm = unwrap_one('centimeters', 100.0)
    for a, b in zip(m['density'], cm['density']):
        assert abs(a - b) <= 0.01 * a, (m['density'], cm['density'])
    reset()
    bad = maf('SM_MafBad_Main', 1.0)
    rt.polyop.setFaceMatID(bad, 1, 101)
    rep = run('udim.matid_unwrap', [bad])
    assert codes(rep) == {'SM_MafBad_Main': ['id_out_of_range']}, codes(rep)
    # 5000 polygons
    reset()
    p = rt.Plane(name='SM_Maf5000_Main', length=10, width=10, lengthsegs=50, widthsegs=100)
    rt.convertToPoly(p)
    for f in range(1, int(rt.polyop.getNumFaces(p)) + 1):
        rt.polyop.setFaceMatID(p, f, 1 + (f % 5))
    t0 = time.time()
    rep = run('udim.matid_unwrap', [p])
    out = apply('udim.matid_unwrap', [p], rep)
    big = round(time.time() - t0, 2)
    assert out['status'] == 'pass' and big < 30, big
    return {'meters': m, 'centimeters': cm, 'bad': codes(rep), 'polys_5000_s': big}


# ---- tex.finish_map -------------------------------------------------------------------------------------------
LEGEND = {'finishes': [{'name': 'Plaster_White', 'ral': 'RAL 9010', 'color': '#F1ECE1'},
                       {'name': 'Plaster_Grey', 'ral': 'RAL 7044', 'color': [183, 179, 168]},
                       {'name': 'Brick_Red', 'color': '#8E402A'},
                       {'name': 'Metal_Graphite', 'ral': 'RAL 7024', 'color': '#474A51'},
                       {'name': 'Glass_Dark', 'color': '#20262B'}],
          'ids': [{'id': 1, 'finish': 'Plaster_White'}, {'id': 2, 'finish': 'Plaster_Grey'},
                  {'id': 3, 'finish': 'Brick_Red'}, {'id': 4, 'finish': 'Metal_Graphite'}],
          'seams_m': [3.0, 6.0]}


def oks(name, ids, pos):
    b = box(name, 10.0, 8.0, 9.0, pos)
    # Box faces: 1 bottom, 2 top, 3..6 sides
    for f, mid in zip(range(1, 7), (ids[0], ids[0]) + tuple(ids)):
        rt.polyop.setFaceMatID(b, f, mid)
    b.material = rt.Standardmaterial(name='M_' + name)
    return b


def finish_map():
    reset()
    legend = OUT / 'legend.json'
    legend.write_text(json.dumps(LEGEND), encoding='utf-8')
    good = oks('SM_Finish_001_Main', (1, 2, 3, 4), (20, 30, 0))
    before = source_state([good])
    rep = run('tex.finish_map', [good], {'legend': str(legend)})
    assert codes(rep) == {'SM_Finish_001_Main': []}, codes(rep)
    out = apply('tex.finish_map', [good], rep)
    assert out['status'] == 'pass' and source_state([good]) == before
    seams = out['plan']['done'][0]['seams']
    assert all(s['ok'] for s in seams) and [s['z_m'] for s in seams] == [3.0, 6.0], seams
    copy = rt.getNodeByName(out['plan']['copies'][0])
    subs = sorted(str(s.name) for s in copy.material.materialList)
    assert subs == ['Brick_Red', 'Metal_Graphite', 'Plaster_Grey', 'Plaster_White'], subs
    bad = oks('SM_Finish_002_Main', (1, 2, 3, 7), (40, 30, 0))
    rep2 = run('tex.finish_map', [bad], {'legend': str(legend)})
    assert codes(rep2) == {'SM_Finish_002_Main': ['finish_id_absent', 'finish_id_unmapped']}, codes(rep2)
    try:
        run('tex.finish_map', [good], {})
        raise AssertionError('preview without a legend accepted')
    except ValueError:
        pass
    return {'seams': seams, 'per_facade': out['plan']['done'][0]['seams_per_facade'], 'subs': subs,
            'bad': codes(rep2)}


# ---- atlas.groundel / atlas.npm (npm profile) ---------------------------------------------------------------------
def plane_el(name, side_m, tex_path, pos, opacity=None):
    p = rt.Plane(name=name, length=side_m, width=side_m, lengthsegs=1, widthsegs=1)
    p.pos = rt.Point3(*pos)
    rt.convertToPoly(p)
    m = rt.Standardmaterial(name='M_' + name)
    if tex_path:
        m.diffuseMap = bitmap(tex_path)
    if opacity:
        m.opacityMap = bitmap(opacity)
    p.material = m
    return p


def groundel():
    reset()
    sides = (256, 384, 512, 768, 1024, 256)
    nodes = []
    files = []
    for k, s in enumerate(sides):
        side = s if s != 384 else 256
        f = png(TEX / 'T_GroundEl_{}_d_1.png'.format(k), side, side, pattern(side, k), 3)
        files.append(f)
        nodes.append(plane_el('SM_GroundEl_{}_GroundEl'.format(k), 0.6 + 0.2 * k, f, (k * 3, 40, 0)))
    before = source_state(nodes)
    md5s = [md5(f) for f in files]
    rep = run('atlas.groundel', nodes)
    got = codes(rep)
    assert got['SM_GroundEl_4_GroundEl'] == ['groundel_size'] and got['SM_GroundEl_0_GroundEl'] == [], got
    out = apply('atlas.groundel', nodes, rep)
    w = out['plan']['written']
    assert w['color_type'] == 2 and w['size'][0] <= 512, w
    assert source_state(nodes) == before and [md5(f) for f in files] == md5s
    # does not fit -> fail with the calculation, nothing written
    reset()
    big = [plane_el('SM_GroundElBig_{}_GroundEl'.format(k), 25.0, png(TEX / 'T_Big_{}_d_1.png'.format(k), 64, 64,
                                                                       pattern(64, k), 3), (k * 30, 0, 0))
           for k in range(6)]
    rep2 = run('atlas.groundel', big)
    assert all('atlas_overflow' in c for c in codes(rep2).values()) and rep2['plan']['calc'], codes(rep2)
    try:
        apply('atlas.groundel', big, rep2)
        raise AssertionError('overflow applied')
    except ValueError:
        pass
    # missing map
    reset()
    miss = plane_el('SM_GroundElMiss_GroundEl', 1.0, None, (0, 0, 0))
    rep3 = run('atlas.groundel', [miss])
    assert codes(rep3) == {'SM_GroundElMiss_GroundEl': ['map_missing']}, codes(rep3)
    return {'codes': got, 'written': w, 'overflow_calc': rep2['plan']['calc']['cells_area_px2'],
            'missing': codes(rep3)}


def npm_rework():
    """VPM_to_NPM acceptance through the npm profile: RGB, RGBA, plug colour; 24 bit, padding 8, reduced atlas,
    Ground 35 +- 0.1 px/m; a TGA is reported, never a crash."""
    reset()
    a = plane_el('SM_Npm_A_Ground', 2.0, png(TEX / 'npm_rgb.png', 64, 64, pattern(64, 1), 3), (0, 0, 0))
    rgba = bytes(v for y in range(64) for x in range(64) for v in (100, 120, 30, 255 if x < 40 else 60))
    b = plane_el('SM_Npm_B_Ground', 2.0, png(TEX / 'npm_rgba.png', 64, 64, rgba, 4), (5, 0, 0))
    c = plane_el('SM_Npm_C_Ground', 2.0, None, (10, 0, 0))
    c.material.diffuse = rt.color(20, 140, 40)
    rep = run('atlas.groundel', [a, b, c], {'profile': 'npm', 'size': 2048})
    assert rep['status'] == 'pass', codes(rep)
    texel = rep['plan']['atlas']['texel_px_per_m']
    assert all(abs(t - 35.0) <= 0.1 for t in texel.values()), texel
    out = apply('atlas.groundel', [a, b, c], rep)
    w = out['plan']['written']
    assert w['color_type'] == 2 and w['size'][0] < 2048 and w['opacity'], w
    tga = TEX / 'npm.tga'
    tga.write_bytes(bytes([0, 0, 2]) + bytes(9) + struct.pack('<HH', 4, 4) + b'\x18\x00' + bytes(48))
    d = plane_el('SM_Npm_D_Ground', 2.0, str(tga), (15, 0, 0))
    rep2 = run('atlas.groundel', [d], {'profile': 'npm', 'size': 2048})
    assert codes(rep2) == {'SM_Npm_D_Ground': ['texture_unsupported']} and rep2['plan']['skipped'], rep2['plan']
    return {'texel': texel, 'written': w, 'tga': rep2['plan']['skipped']}


# ---- atlas.flora ------------------------------------------------------------------------------------------------
def card(name, tex, pos, segs=(4, 8), opacity=None):
    p = rt.Plane(name=name, length=1.0, width=0.5, lengthsegs=segs[1], widthsegs=segs[0])
    p.pos = rt.Point3(*pos)
    rt.convertToPoly(p)
    m = rt.Standardmaterial(name='M_' + name)
    m.diffuseMap = bitmap(tex)
    if opacity:
        m.opacityMap = bitmap(opacity)
    p.material = m
    return p


def flora():
    reset()
    leaf_px = bytes(v for y in range(64) for x in range(64) for v in (40, 120 + x % 50, 30, 255 if x < 48 else 0))
    leaf = png(TEX / 'T_Leaf_d_1.png', 64, 64, leaf_px, 4)
    bark = png(TEX / 'T_Bark_d_1.png', 512, 256, pattern(256, 3, 512), 3)
    bark_o = png(TEX / 'T_Bark_o_1.png', 512, 256, bytes(255 if y < 200 else 0 for y in range(256) for x in range(512)), 1)
    grass = png(TEX / 'T_Grass_d_1.png', 128, 128, bytes((30, 140, 40)) * (128 * 128), 3)
    l1 = card('SM_Leaf_Flora', leaf, (0, 0, 0))
    l2 = rt.instance(l1)
    l2.name = 'SM_LeafInst_Flora'
    l2.pos = rt.Point3(2, 0, 0)
    bk = card('SM_Bark_Flora', bark, (4, 0, 0), opacity=bark_o)
    gr = card('SM_Grass_Flora', grass, (6, 0, 0))
    bend = rt.Plane(name='SM_LeafBend_Flora', length=1.0, width=0.5, lengthsegs=8, widthsegs=4)
    bend.pos = rt.Point3(8, 0, 0)
    rt.addModifier(bend, rt.Bend(angle=45))
    bend.material = l1.material
    nodes = [l1, l2, bk, gr, bend]
    before = source_state(nodes)
    md5s = [md5(f) for f in (leaf, bark, bark_o, grass)]
    rep = run('atlas.flora', nodes)
    assert rep['status'] == 'pass', codes(rep)
    atlas = rep['plan']['atlas']
    assert len(atlas['tiles']) == 3 and max(t['scale'] for t in atlas['tiles']) <= 1.0, atlas
    out = apply('atlas.flora', nodes, rep)
    w = out['plan']['written']
    assert w['diffuse_color_type'] == 2 and w['opacity'] and w['opacity_color_type'] == 0, w
    inst = [r for r in out['plan']['done'] if r['source'] == 'SM_LeafInst_Flora'][0]
    assert inst['faces_in_tile'] == inst['faces'] == 64, inst
    assert source_state(nodes) == before and [md5(f) for f in (leaf, bark, bark_o, grass)] == md5s
    return {'atlas': atlas, 'written': w, 'instance': inst, 'done': out['plan']['done']}


for name, fn in (('tex.erm_normal_check', erm_normal), ('udim.slots', slots), ('udim.matid_unwrap', matid_unwrap),
                 ('tex.finish_map', finish_map), ('atlas.groundel', groundel), ('atlas.npm_rework', npm_rework),
                 ('atlas.flora', flora)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
print('AGR_979B_SUMMARY ' + json.dumps({'errors': sorted(summary['errors']), 'seconds': summary['seconds']}))
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
