"""new-case: #908 branch C native check of ucx.rename, qa.names_fix and udim.ids_to_udims in locked batch Max.

Run via the lab DCC runner on DISPOSABLE synthetic scenes; AGR_TEST_OUTPUT must name a NEW directory,
AGR_TEST_PACKAGE the built MZP. Installs the MZP into OUT (no user folders touched), then runs the minimal
acceptance of each lab report through runtime.edits_080 (preview -> JSON round trip -> apply):
* ucx.rename (docs/experiments/ucx.rename.md): model/helper skipped, stable order, mask, ONE undo restores all
  names, a second run gives the same names;
* qa.names_fix (qa.names_fix.md): donor + targets + no-index + own material; mask names on export copies, donor
  and every existing file unchanged (md5), folder `_001_` unchanged, no map to a missing file, report lists the
  skipped object, the missing file and the kept material; a repeat run is refused (ambiguous);
* udim.ids_to_udims (udim.ids_to_udims.md): IDs 1, 2 (two islands, one outside 0..1), 7, 11, 25, 101, zero-extent
  5 and a second object with ID 4; working objects unchanged; copies tile-checked; texel mode within 1 %;
  FBX export of the copies read back and the per-face tile check repeated on the file.
Files are written only below OUT; the scene is never saved.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

import pymxs
from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]


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
summary['runtime_version'] = agr.VERSION


def roundtrip(report):
    """What an MCP client / the panel hands back: the preview as JSON text."""
    return json.loads(json.dumps(report))


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def reset():
    rt.resetMaxFile(rt.Name('noPrompt'))


# ---- ucx.rename ----------------------------------------------------------------------------------------------
def ucx():
    reset()
    with pymxs.undo(False):  # setup outside any undo record: the run's record is the only one to undo
        names = ['SM_Addr_Main', 'UCX_SM_Addr_Main_003', 'UCX_SM_Addr_Main_001', 'ucx_SM_Addr_Main_7',
                 'UCX_SM_Addr_Ground_01']
        nodes = [rt.Box(name=n, length=1, width=1, height=1) for n in names]
        helper = rt.Point(name='Point001')
        nodes.append(helper)
    before = {int(rt.getHandleByAnim(n)): str(n.name) for n in nodes}
    rt.select(nodes)
    prev = agr.edits_080('ucx.rename', 'preview')
    # 0.9 (#979 E1): a piece to be renamed carries `ucx_name`; the canonical one in place passes
    codes = {o['name']: [f['code'] for f in o['findings']] for o in prev['objects']}
    assert prev['status'] == 'fail' and agr.parse_report(json.dumps(prev)) == prev, prev
    assert codes == {'UCX_SM_Addr_Main_003': ['ucx_name'], 'UCX_SM_Addr_Main_001': [], 'ucx_SM_Addr_Main_7': ['ucx_name'],
                     'UCX_SM_Addr_Ground_01': ['ucx_name']}, codes
    assert {s['item'] for s in prev['plan']['skipped']} == {'SM_Addr_Main', 'Point001'}, prev['plan']['skipped']
    applied = agr.edits_080('ucx.rename', 'apply', roundtrip(prev))
    names_after = {h: str(rt.getAnimByHandle(h).name) for h in before}
    expected = {'SM_Addr_Main': 'SM_Addr_Main', 'UCX_SM_Addr_Main_003': 'UCX_SM_Addr_Main_002',
                'UCX_SM_Addr_Main_001': 'UCX_SM_Addr_Main_001', 'ucx_SM_Addr_Main_7': 'UCX_SM_Addr_Main_003',
                'UCX_SM_Addr_Ground_01': 'UCX_SM_Addr_Ground_001', 'Point001': 'Point001'}
    assert {before[h]: n for h, n in names_after.items()} == expected, names_after
    assert applied['status'] == 'pass' and agr.parse_report(json.dumps(applied)) == applied
    assert sorted(str(n.name) for n in rt.selection) == sorted(expected.values()), 'selection not restored'
    # stale preview is refused after the scene changed
    try:
        agr.edits_080('ucx.rename', 'apply', roundtrip(prev))
    except ValueError as exc:
        stale = type(exc).__name__ + ': ' + str(exc)[:120]
    else:
        raise AssertionError('stale preview accepted')
    rt.execute('max undo')  # ONE undo restores every name
    undone = {h: str(rt.getAnimByHandle(h).name) for h in before}
    assert undone == before, ('one undo did not restore all names', undone)
    rt.select(nodes)  # the undo also reverts the selection the run restored
    second = agr.edits_080('ucx.rename', 'apply', roundtrip(agr.edits_080('ucx.rename', 'preview')))
    again = {before[h]: str(rt.getAnimByHandle(h).name) for h in before}
    assert again == expected, again
    third = agr.edits_080('ucx.rename', 'preview')
    assert third['plan']['done'] == [] and len(third['plan']['unchanged']) == 4, third['plan']
    return {'preview_done': prev['plan']['done'], 'skipped': prev['plan']['skipped'], 'stale_refused': stale,
            'one_undo_restores': True, 'second_run_same': second['plan']['done'] == prev['plan']['done'],
            'idempotent_third_preview_done': third['plan']['done']}


# ---- qa.names_fix ---------------------------------------------------------------------------------------------
def _png(path, rgb):
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\x00' + bytes(rgb) * 4 for _ in range(4))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    return str(path)


def _bitmap(path, name):
    return rt.Bitmaptexture(filename=path, name=name)


def names_fix():
    reset()
    tex = OUT / 'names_tex'
    d = _png(tex / 'T_Test_001_Main_d_1.png', (200, 10, 10))
    n = _png(tex / '_001_' / 'T_Test_001_Main_n_1.png', (128, 128, 255))
    r_missing = str(tex / 'T_Test_001_Main_r_1.png')
    exist3 = _png(tex / 'T_Test_003_Main_d_1.png', (1, 2, 3))
    own = _png(tex / 'own_diffuse.png', (9, 9, 9))
    with pymxs.undo(False):
        donor = rt.Box(name='SM_Test_001_Main')
        mat = rt.PhysicalMaterial(name='DonorMat')
        mat.base_color_map = _bitmap(d, 'dmap')
        mat.bump_map = rt.Normal_Bump(normal_map=_bitmap(n, 'nmap'))
        mat.roughness_map = _bitmap(r_missing, 'rmap')
        donor.material = mat
        t2 = rt.Box(name='SM_Test_002_Main', pos=rt.Point3(3, 0, 0))
        t3 = rt.Box(name='SM_Test_003_Main', pos=rt.Point3(6, 0, 0))
        noidx = rt.Box(name='Box001', pos=rt.Point3(9, 0, 0))
        mine = rt.Box(name='SM_Test_004_Main', pos=rt.Point3(12, 0, 0))
        omat = rt.PhysicalMaterial(name='OwnMat')
        omat.base_color_map = _bitmap(own, 'omap')
        mine.material = omat
    files_before = {str(p.relative_to(tex)): md5(p) for p in tex.rglob('*') if p.is_file()}
    dirs_before = sorted(str(p.relative_to(tex)) for p in tex.rglob('*') if p.is_dir())
    work = [donor, t2, t3, noidx, mine]
    work_before = [(str(o.name), str(o.material.name) if o.material else None) for o in work]
    donor_maps = (str(mat.base_color_map.filename), str(mat.bump_map.normal_map.filename), str(mat.roughness_map.filename))
    nodes_before = len(rt.objects)
    rt.select(work)
    prev = agr.edits_080('qa.names_fix', 'preview', options={'donor': 'SM_Test_001_Main'})
    assert agr.parse_report(json.dumps(prev)) == prev
    plan = prev['plan']
    assert [s['item'] for s in plan['skipped']] == ['Box001'], plan['skipped']
    fails = ' | '.join(f['reason'] for f in plan['failures'])
    assert 'T_Test_001_Main_r_1.png' in fails, fails
    assert any(x.get('action') == 'kept (own material)' and x.get('material') == 'OwnMat' for x in plan['done']), plan['done']
    applied = agr.edits_080('qa.names_fix', 'apply', roundtrip(prev))
    assert agr.parse_report(json.dumps(applied)) == applied
    copies = [o for o in rt.objects if str(o.layer.name) == 'AGR_export_names']
    names = sorted(str(c.name) for c in copies)
    assert names == ['SM_Test_001_Main', 'SM_Test_002_Main', 'SM_Test_003_Main', 'SM_Test_004_Main'], names
    assert len(rt.objects) == nodes_before + 4
    # working side untouched
    assert [(str(o.name), str(o.material.name) if o.material else None) for o in work] == work_before
    assert (str(mat.base_color_map.filename), str(mat.bump_map.normal_map.filename),
            str(mat.roughness_map.filename)) == donor_maps
    files_after = {str(p.relative_to(tex)): md5(p) for p in tex.rglob('*') if p.is_file()}
    assert {k: files_after[k] for k in files_before} == files_before, 'an existing file changed'
    assert sorted(str(p.relative_to(tex)) for p in tex.rglob('*') if p.is_dir()) == dirs_before, 'folders changed'
    new_files = sorted(set(files_after) - set(files_before))
    maps, broken = {}, []
    checks = agr._checks_core()
    for c in copies:
        m = c.material
        assert m is not None and m != mat and m != omat, str(c.name)
        for prop in ('base_color_map', 'roughness_map', 'bump_map'):
            t = rt.getProperty(m, rt.Name(prop))
            if t is not None and rt.classOf(t) == rt.Normal_Bump:
                t = t.normal_map
            if t is None:
                continue
            fn = str(t.filename)
            maps[str(c.name) + '.' + prop] = (fn, str(t.name))
            if not os.path.isfile(fn):
                broken.append(fn)
        mfind = [f for f in checks.name_findings(str(m.name), 'M', 'npm') if f[0] not in ('name_case', 'name_digits')]
        assert mfind == [], (str(m.name), mfind)
    assert not broken, broken
    # 0.9 (#979 V1): T_Test_003_Main_d_1.png exists with OTHER content: not overwritten AND not linked; the copy's
    # map stays on the donor's file and the conflict is a failure in the report
    kept = maps['SM_Test_003_Main.base_color_map']
    assert os.path.basename(kept[0]) == 'T_Test_001_Main_d_1.png' and kept[1] == 'dmap', kept
    assert 'other content' in fails, fails
    for key, (fn, tname) in maps.items():
        if key.startswith('SM_Test_004_Main') or key == 'SM_Test_003_Main.base_color_map':
            continue
        stem = os.path.splitext(os.path.basename(fn))[0]
        assert stem == tname and checks.name_findings(stem + '.png', 'T', 'npm') == [], (key, fn, tname)
    assert maps['SM_Test_002_Main.bump_map'][0].replace('\\', '/').endswith('/_001_/T_Test_002_Main_n_1.png'), maps
    assert md5(exist3) == files_before['T_Test_003_Main_d_1.png']
    # repeat run: refused for the existing copies, nothing overwritten
    rt.select(work)
    again = agr.edits_080('qa.names_fix', 'preview', options={'donor': 'SM_Test_001_Main'})
    rep = {a['item'] for a in again['plan']['ambiguous'] if 'repeat run' in a['reason']}
    assert rep == {'SM_Test_001_Main', 'SM_Test_002_Main', 'SM_Test_003_Main', 'SM_Test_004_Main'}, again['plan']['ambiguous']
    return {'status_preview': prev['status'], 'status_apply': applied['status'], 'copies': names,
            'new_files': new_files, 'maps': maps, 'failures': plan['failures'], 'skipped': plan['skipped'],
            'repeat_run_ambiguous': sorted(rep), 'existing_003_md5_unchanged': True}


# ---- udim.ids_to_udims ----------------------------------------------------------------------------------------
QUADS_A = [(1, (0, 0, 1, 1), (0.1, 0.1, 0.3, 0.3)), (2, (2, 0, 1, 1), (0.0, 0.0, 0.2, 0.2)),
           (2, (4, 0, 1, 1), (1.5, 1.2, 0.2, 0.2)), (7, (0, 3, 4, 1), (0.2, 0.2, 0.8, 0.2)),
           (11, (0, 5, 1, 1), (0.5, 0.5, 0.1, 0.1)), (25, (0, 7, 2, 2), (0.3, 0.3, 0.4, 0.4)),
           (101, (0, 9, 1, 1), (0.6, 0.6, 0.2, 0.2)), (5, (0, 11, 1, 1), (0.4, 0.4, 0.0, 0.0))]
QUADS_B = [(4, (0, 0, 2, 1), (0.0, 0.0, 0.5, 0.25))]


def _poly(name, quads, x0):
    p = rt.convertToPoly(rt.Editable_Mesh())
    p.name = name
    uvs, fuv = [], []
    for f, (mid, (x, y, w, h), (u, v, uw, vh)) in enumerate(quads):
        for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h)):
            rt.polyop.createVert(p, rt.Point3(px + x0, py, 0))
        b = 4 * f + 1
        rt.polyop.createPolygon(p, agr._max_array([b, b + 1, b + 2, b + 3]))
        uvs += [(u, v), (u + uw, v), (u + uw, v + vh), (u, v + vh)]
        fuv.append([4 * f, 4 * f + 1, 4 * f + 2, 4 * f + 3])
    for f, (mid, _, _) in enumerate(quads, 1):
        rt.polyop.setFaceMatID(p, f, mid)
    agr._write_channel(p, uvs, fuv)
    multi = rt.MultiMaterial(numsubs=101, name='M_Udim_Test')
    for i in range(101):
        mat = rt.Standardmaterial(name='ID_{}'.format(i + 1))
        multi.materialList[i] = mat
        multi.materialIDList[i] = i + 1
    p.material = multi
    return p


def _tiles_by_id(core, mesh, ids_of_face):
    bad = []
    for f, mid in enumerate(ids_of_face):
        if 1 <= mid <= 100 and mid != 5:
            if core.face_tile(mesh['uvs'], mesh['face_uvs'][f]) != 1000 + mid:
                bad.append((f + 1, mid))
    return bad


def udim():
    reset()
    core = agr._load_core('udim_core.py', 'agr_tools_udim_core')
    with pymxs.undo(False):
        a = _poly('SM_UdimA_Main', QUADS_A, 0)
        b = _poly('SM_UdimB_Main', QUADS_B, 20)
    work = [a, b]
    before = [agr._read_channel(n) for n in work]
    stacks = [int(n.modifiers.count) for n in work]
    count0 = len(rt.objects)
    rt.select(work)
    prev = agr.edits_080('udim.ids_to_udims', 'preview')
    assert agr.parse_report(json.dumps(prev)) == prev and prev['status'] == 'fail'  # 101 and 5 are findings
    codes = {(o['name'], f['code']) for o in prev['objects'] for f in o['findings']}
    assert codes == {('SM_UdimA_Main', 'udim_id_out_of_range'), ('SM_UdimA_Main', 'udim_zero_extent')}, codes
    applied = agr.edits_080('udim.ids_to_udims', 'apply', roundtrip(prev))
    assert agr.parse_report(json.dumps(applied)) == applied
    copies = [o for o in rt.objects if str(o.layer.name) == 'AGR_export_udim']
    assert len(copies) == 2 and len(rt.objects) == count0 + 2
    assert [agr._read_channel(n) for n in work] == before and [int(n.modifiers.count) for n in work] == stacks
    fit = {}
    for c in copies:
        mesh = agr._read_channel(c)
        assert all(abs(x) < 1e6 and x == x for p in mesh['uvs'] for x in p), 'NaN/inf UV'
        bad = _tiles_by_id(core, mesh, mesh['ids'])
        assert not bad, (str(c.name), bad)
        fit[str(c.name)] = {'faces': len(mesh['ids']), 'ids': sorted(set(mesh['ids']))}
    placed = sorted((d['object'], d['id'], d['tile']) for d in applied['plan']['done'])
    assert {(x[1], x[2]) for x in placed} == {(1, 1001), (2, 1002), (7, 1007), (11, 1011), (25, 1025), (4, 1004)}, placed
    # texel mode
    rt.select(work)
    tprev = agr.edits_080('udim.ids_to_udims', 'preview', options={'mode': 'texel'})
    tapp = agr.edits_080('udim.ids_to_udims', 'apply', roundtrip(tprev))
    spread = tapp['plan']['texel_spread']
    assert spread <= 0.01, spread
    tcopies = [o for o in rt.objects if str(o.layer.name) == 'AGR_export_udim' and o not in copies]
    assert len(tcopies) == 2
    # FBX readback of the texel copies: per-face tile check on the file
    fbx = OUT / 'udim_copies.fbx'
    rt.select(tcopies)
    rt.FBXExporterSetParam('ASCII', False)
    rt.FBXExporterSetParam('Triangulate', False)
    ok = rt.exportFile(str(fbx), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP)
    assert ok and fbx.is_file(), 'FBX export failed'
    reset()
    rt.importFile(str(fbx), rt.Name('noPrompt'), using=rt.FBXIMP)
    readback = {}
    for o in rt.objects:
        if rt.superClassOf(o) != rt.GeometryClass:
            continue
        rt.convertToPoly(o)
        mesh = agr._read_channel(o)
        mat = o.material
        ids = []
        for mid in mesh['ids']:
            if mat is not None and rt.classOf(mat) == rt.MultiMaterial:
                sub = [mat.materialList[i] for i in range(len(mat.materialIDList)) if int(mat.materialIDList[i]) == mid]
                ids.append(int(str(sub[0].name).split('_')[-1]) if sub and sub[0] is not None else mid)
            else:
                ids.append(mid)
        bad = _tiles_by_id(core, mesh, ids)
        readback[str(o.name)] = {'faces': len(ids), 'ids': sorted(set(ids)), 'outside': bad}
    assert len(readback) == 2 and not any(v['outside'] for v in readback.values()), readback
    return {'preview_status': prev['status'], 'findings': sorted(codes), 'placed': placed, 'fit_copies': fit,
            'skipped': prev['plan']['skipped'], 'texel_spread': spread, 'fbx_readback': readback,
            'per_id_a': prev['plan']['per_object'][0]['ids']}


# ---- 0.9 rework (#979 E1): T06 acceptance scene ---------------------------------------------------------------
def names_fix_e1():
    """Prefix collision, shared material (diffuse + specular level + reflection), foreign read-only target, odd
    inputs, a name held by an unselected object; library profile with a separate copy folder. Foreign file md5
    unchanged, `_m` from one slot, 0 duplicate node names after apply, homoglyph/translit order-free."""
    import stat
    reset()
    tex = OUT / 'names_e1'
    src_d = _png(tex / 'src_d.png', (10, 20, 30))
    spec = _png(tex / 'spec.png', (40, 40, 40))
    refl = _png(tex / 'refl.png', (50, 50, 50))
    bench = _png(tex / 'bench.png', (60, 60, 60))
    foreign = _png(tex / 'T_Bench_002_Main_d_1.png', (1, 1, 1))
    os.chmod(foreign, stat.S_IREAD)
    chair = _png(tex / 'chair.png', (70, 70, 70))
    with pymxs.undo(False):
        shared = rt.Standardmaterial(name='Shared')
        shared.diffuseMap = _bitmap(src_d, 'dmap')
        shared.specularLevelMap = _bitmap(spec, 'smap')
        shared.reflectionMap = _bitmap(refl, 'rmap')
        a = rt.Box(name='SM_Chair_001_Main')
        b = rt.Box(name='XX_Chair_001_Main', pos=rt.Point3(3, 0, 0))
        a.material = shared
        b.material = shared
        c = rt.Box(name='SM_Bench_002_Main', pos=rt.Point3(6, 0, 0))
        c.material = rt.Standardmaterial(name='B', diffuseMap=_bitmap(bench, 'bmap'))
        odd = rt.Box(name='Bench', pos=rt.Point3(9, 0, 0))
        odd.material = rt.Standardmaterial(name='Odd')
        held = rt.Box(name='SM_Held_001_Main', pos=rt.Point3(12, 0, 0))  # NOT selected
        dup = rt.Box(name='sm_Held_1_main', pos=rt.Point3(15, 0, 0))
        dup.material = rt.Standardmaterial(name='D')
        lib = rt.Box(name='Acme_Сhair_A12_LOW', pos=rt.Point3(18, 0, 0))  # Cyrillic С homoglyph, LOW
        lib.material = rt.Standardmaterial(name='L', diffuseMap=_bitmap(chair, 'lmap'))
    files_before = {str(p.relative_to(tex)): md5(p) for p in tex.rglob('*') if p.is_file()}
    rt.select([a, b, c, odd, dup])
    prev = agr.edits_080('qa.names_fix', 'preview')
    plan = prev['plan']
    fails = ' | '.join(f['reason'] for f in plan['failures'])
    assert 'other content' in fails and 'reflectionMap' in fails, fails
    assert {s['item'] for s in plan['skipped']} == {'Bench'}, plan['skipped']
    held_amb = [x for x in plan['ambiguous'] if x['item'] == 'SM_Held_001_Main']
    assert held_amb and 'another scene object' in held_amb[0]['reason'], plan['ambiguous']
    applied = agr.edits_080('qa.names_fix', 'apply', roundtrip(prev))
    copies = [o for o in rt.objects if str(o.layer.name) == 'AGR_export_names']
    names_all = [str(o.name) for o in rt.objects if str(o.layer.name) == 'AGR_export_names'] + ['SM_Held_001_Main']
    assert sorted(str(x.name) for x in copies) == ['SM_Bench_002_Main', 'SM_Chair_001_Main', 'SM_XX_Chair_001_Main']
    assert len(names_all) == len(set(names_all)), names_all
    files_after = {str(p.relative_to(tex)): md5(p) for p in tex.rglob('*') if p.is_file()}
    assert files_after['T_Bench_002_Main_d_1.png'] == files_before['T_Bench_002_Main_d_1.png'], 'foreign file changed'
    m_files = sorted(k for k in files_after if k.endswith('_m_1.png'))
    assert m_files == ['T_Chair_001_Main_m_1.png', 'T_XX_Chair_001_Main_m_1.png'], m_files
    for k in m_files:
        assert files_after[k] == files_before['spec.png'], (k, 'not from specularLevelMap')
    by = {str(x.name): x for x in copies}
    assert str(by['SM_Bench_002_Main'].material.diffuseMap.filename) == bench  # stays on its source
    mats = sorted(str(x.material.name) for x in copies)
    assert len(mats) == len(set(mats)), mats
    # library profile: homoglyph + case fixed, map copied into a separate folder, source folder untouched
    out_lib = OUT / 'names_e1_lib'
    rt.select([lib])
    lprev = agr.edits_080('qa.names_fix', 'preview', options={'profile': 'library', 'folder': str(out_lib)})
    lapp = agr.edits_080('qa.names_fix', 'apply', roundtrip(lprev))
    lcopy = [o for o in rt.objects if str(o.layer.name) == 'AGR_export_names' and str(o.name).startswith('Acme')]
    assert [str(o.name) for o in lcopy] == ['Acme_Chair_A12_low'], [str(o.name) for o in lcopy]
    assert sorted(p.name for p in out_lib.iterdir()) == ['T_Acme_Chair_A12_low_d.png']
    assert str(lcopy[0].material.name) == 'M_Acme_Chair_A12_low'
    os.chmod(foreign, stat.S_IREAD | stat.S_IWRITE)
    return {'failures': plan['failures'], 'ambiguous': plan['ambiguous'], 'copies': sorted(by), 'm_files': m_files,
            'status_apply': applied['status'], 'library_copy': str(lcopy[0].name), 'library_status': lapp['status']}


for name, fn in (('ucx_rename', ucx), ('names_fix', names_fix), ('names_fix_e1', names_fix_e1),
                 ('ids_to_udims', udim)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_908C_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
