"""new-case: AGR Tools 0.5.0 diagnostics in locked batch Max on a disposable synthetic scene.

Run via dcc_batch.py; AGR_TEST_OUTPUT must name a NEW directory. All data is synthetic.
Installs the built MZP into OUT, builds a throwaway scene, runs the five read-only checks
(core API and the registered macros) and proves the scene state is unchanged after each one.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import zlib

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
os.environ['AGR_TOOLS_REPO'] = str(ROOT)
_venv_python = ROOT / '.venv' / 'Scripts' / 'python.exe'
if _venv_python.is_file():
    os.environ['AGR_PYTHON'] = str(_venv_python)
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ.get('AGR_TEST_PACKAGE', ROOT / 'tmp/AGR-Tools-0.5.0.mzp'))
print('AGR_PACKAGE_SHA256', hashlib.sha256(PACKAGE.read_bytes()).hexdigest())
print('AGR_CHECKS_START version={} file={}'.format(rt.maxVersion()[0], rt.maxFileName))
assert rt.maxVersion()[0] in (26000, 28000)
assert not rt.maxFileName, 'only an empty batch document is allowed'
rt.units.SystemType = rt.name('meters')

rt.execute('global AGRToolsInstallRoot; global AGRToolsStartupRoot')
rt.AGRToolsInstallRoot = str(OUT / 'installed') + '/'
rt.AGRToolsStartupRoot = str(OUT / 'startup') + '/'
rt.makeDir(rt.AGRToolsStartupRoot, all=True)
rt.fileIn(str(PACKAGE))
assert rt.execute('global AGRToolsRegistered; AGRToolsRegistered == true'), 'MZP macros not registered'
sys.path.insert(0, str(OUT / 'installed'))
import runtime as agr  # noqa: E402

assert agr.VERSION == '0.5.0'
results = {'version': list(rt.maxVersion()), 'checks': {}, 'read_only': {}, 'macros': {}}


def png(w, h, depth=8, ctype=2):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\x00' * 16)) + chunk(b'IEND', b''))


TEX = OUT / 'textures'
TEX.mkdir()


def tex(name, w, h, **kw):
    p = TEX / name
    p.write_bytes(png(w, h, **kw))
    return str(p)


def material(name, maps=()):
    m = rt.standardMaterial(name=name)
    slots = ('diffuseMap', 'bumpMap', 'specularMap')
    for slot, path in zip(slots, maps):
        setattr(m, slot, rt.bitmapTexture(filename=path))
    return m


def plane(name, fbx, ls=1, ws=1, pos=(0, 0, 0)):
    n = rt.plane(name=name, length=1, width=1, lengthsegs=ls, widthsegs=ws, mapcoords=True,
                 pos=rt.Point3(*pos))
    if fbx:
        rt.setUserProp(n, 'AGR_EXPORT_PATH', fbx)
    return n


def two_island_mesh(name, fbx, gap_px, size=2048):
    """Two UV islands side by side with an exact gap in pixels of a size_px map."""
    g = gap_px / float(size)
    verts = [rt.Point3(x, y, 0) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1), (2, 0), (3, 0), (3, 1), (2, 1))]
    faces = [rt.Point3(1, 2, 3), rt.Point3(1, 3, 4), rt.Point3(5, 6, 7), rt.Point3(5, 7, 8)]
    uv = [(0.1, 0.1), (0.4, 0.1), (0.4, 0.4), (0.1, 0.4),
          (0.4 + g, 0.1), (0.7 + g, 0.1), (0.7 + g, 0.4), (0.4 + g, 0.4)]
    m = rt.mesh(vertices=verts, faces=faces)
    m.name = name
    rt.setNumTVerts(m, len(uv))
    for i, (u, v) in enumerate(uv):
        rt.setTVert(m, i + 1, rt.Point3(u, v, 0))
    rt.buildTVFaces(m)
    for i, f in enumerate(faces):
        rt.setTVFace(m, i + 1, f)
    rt.update(m)
    rt.setUserProp(m, 'AGR_EXPORT_PATH', fbx)
    return m


def state():
    """Digest of everything a diagnostic must not change."""
    rows = []
    for n in sorted(rt.objects, key=lambda o: int(rt.getHandleByAnim(o))):
        snap = rt.snapshotAsMesh(n)
        try:
            faces = int(snap.numfaces)
        finally:
            rt.delete(snap)
        rows.append([int(rt.getHandleByAnim(n)), str(n.name), str(rt.classOf(n)), faces, str(n.transform),
                     str(n.pivot), str(n.material.name) if n.material else None, str(rt.getUserPropBuffer(n)),
                     int(n.modifiers.count)])
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest(), len(rows)


def codes(report):
    agr.parse_report(json.dumps(report))
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


def run(label, tool, nodes=None, path=None):
    before = state()
    report = agr.checks_050(tool, nodes, path)
    after = state()
    assert before == after, label + ': scene changed'
    results['read_only'][label] = {'objects': before[1], 'digest_unchanged': True}
    results['checks'][label] = report
    return report


NPM_01 = 'C:/o/0001_Tverskaya_12_01.fbx'
NPM_02 = 'C:/o/0001_Tverskaya_12_02.fbx'
NPM_GR = 'C:/o/0001_Tverskaya_12_Ground.fbx'
VPM = 'C:/o/SM_Tverskaya_12.fbx'
VPM_GR = 'C:/o/SM_Tverskaya_12_Ground.fbx'

# --- names (D2, D4) ----------------------------------------------------------------------------------
n1 = plane('SM_Tverskaya_12_Main', VPM)
n1.material = material('M_Tverskaya_12_Main_2')
n2 = plane('SM_Tverskaya_12_001_MainGlass', NPM_01)
n3 = plane('SM_tverskaya_12_001_Main_1', NPM_01)
n4 = rt.box(name='UCX_SM_Tverskaya_12_Ground_001', length=1, width=1, height=1)
rt.setUserProp(n4, 'AGR_EXPORT_PATH', VPM_GR)
n5 = plane('SM_Tverskaya_12_Ground', None)
got = codes(run('names', 'names', [n1, n2, n3, n4, n5]))
assert got['SM_Tverskaya_12_Main'] == [], got            # slot 2 material is legal (D4)
assert got['SM_Tverskaya_12_001_MainGlass'] == [], got   # MainGlass is not Main (D2)
assert got['UCX_SM_Tverskaya_12_Ground_001'] == [], got  # UCX is not Ground (D2)
assert got['SM_tverskaya_12_001_Main_1'] == ['name_case', 'name_suffix', 'name_type'], got
assert got['SM_Tverskaya_12_Ground'] == ['fbx_unmapped'], got
print('AGR_CHECKS_NAMES', json.dumps(got, sort_keys=True))
for n in (n1, n2, n3, n4, n5):
    rt.delete(n)

# --- triangle limits per FBX (D8) --------------------------------------------------------------------
a1 = plane('SM_Tverskaya_12_001_Main', NPM_01, 250, 150)          # 75 000
a2 = plane('SM_Tverskaya_12_001_MainGlass', NPM_01, 250, 150)     # 75 000 -> FBX 01 == 150 000
b1 = plane('SM_Tverskaya_12_002_Main', NPM_02, 250, 150)
b2 = plane('SM_Tverskaya_12_002_MainGlass', NPM_02, 250, 150)
b3 = rt.box(name='SM_Tverskaya_12_003_Main', length=1, width=1, height=1)  # +12 -> FBX 02 == 150 012
rt.setUserProp(b3, 'AGR_EXPORT_PATH', NPM_02)
g1 = plane('SM_Tverskaya_12_Ground', NPM_GR, 340, 250)            # 170 000 <= 180 000
tris_nodes = [a1, a2, b1, b2, b3, g1]
rep = run('tris', 'tris', tris_nodes)
got = codes(rep)
table = {r['fbx']: (r['render_triangles'], r['limit']) for r in rep['plan']['fbx']}
assert table == {NPM_01: (150000, 150000), NPM_02: (150012, 150000), NPM_GR: (170000, 180000)}, table
assert got['SM_Tverskaya_12_001_Main'] == ['tri_at_limit'] and got['SM_Tverskaya_12_002_Main'] == ['tri_limit'], got
assert got['SM_Tverskaya_12_Ground'] == [], got  # per FBX: Ground is not added to OKS (D8)
print('AGR_CHECKS_TRIS', json.dumps({k.split('/')[-1]: v for k, v in table.items()}, sort_keys=True))
for n in tris_nodes:
    rt.delete(n)

# --- textures: every object (D1), empty map array (D3), sizes, VPM padding 16 px ----------------------
t1 = plane('SM_Tverskaya_12_001_Main', NPM_01)
t1.material = material('M_Tverskaya_12_001_Main_1', [tex('T_Tverskaya_12_001_Main_d_1.png', 1000, 1000)])
t2 = plane('SM_Tverskaya_12_002_Main', NPM_02)
t2.material = material('M_Tverskaya_12_002_Main_1', [tex('T_Tverskaya_12_002_Main_d_1.png', 1024, 1024)])
t3 = plane('SM_Tverskaya_12_MainGlass', VPM)
t4 = plane('SM_Tverskaya_12_Main', VPM)
t4.material = material('M_Tverskaya_12_Main_1')
vset = [tex(f'T_Tverskaya_12_{m}_1.1001.png', 2048, 2048) for m in ('Diffuse', 'ERM', 'Normal')]
t5 = two_island_mesh('SM_Pad_10px_Main', 'C:/o/SM_Pad_10px.fbx', 10)
t5.material = material('M_Pad_10px_Main_1', vset)
t6 = two_island_mesh('SM_Pad_20px_Main', 'C:/o/SM_Pad_20px.fbx', 20)
t6.material = material('M_Pad_20px_Main_1', vset)
t7 = plane('SM_Tverskaya_12_003_Main', NPM_01)
t7.material = material('M_Tverskaya_12_003_Main_1', [str(TEX / 'T_Missing_003_Main_d_1.png')])
tex_nodes = [t1, t2, t3, t4, t5, t6, t7]
rep = run('textures', 'textures', tex_nodes)
got = codes(rep)
assert got['SM_Tverskaya_12_001_Main'] == ['tex_size'], got   # first object's map is read (D1)
assert got['SM_Tverskaya_12_002_Main'] == [], got
assert got['SM_Tverskaya_12_MainGlass'] == [], got
assert any(d['name'] == 'SM_Tverskaya_12_MainGlass' for d in rep['plan']['dropped']), rep['plan']['dropped']
assert got['SM_Tverskaya_12_Main'] == ['tex_missing'], got    # empty usedMaps array = no maps (D3)
assert got['SM_Pad_10px_Main'] == ['tex_padding'], got        # 10 px < 16 px at 2048
assert got['SM_Pad_20px_Main'] == [], got
assert got['SM_Tverskaya_12_003_Main'] == ['tex_missing'], got
print('AGR_CHECKS_TEXTURES', json.dumps(got, sort_keys=True))
for n in tex_nodes:
    rt.delete(n)

# --- padding per atlas (review r1 P1): two-slot Multimaterial, atlas shared by two objects -------------
def island_mesh(name, fbx, islands):
    """One UV square per (x0, size, matID) island; geometry quads side by side."""
    verts, faces, uv, mids = [], [], [], []
    for k, (x0, s, mid) in enumerate(islands):
        b = 4 * k
        verts += [rt.Point3(2 * k + x, y, 0) for x, y in ((0, 0), (1, 0), (1, 1), (0, 1))]
        faces += [rt.Point3(b + 1, b + 2, b + 3), rt.Point3(b + 1, b + 3, b + 4)]
        uv += [(x0, 0.1), (x0 + s, 0.1), (x0 + s, 0.1 + s), (x0, 0.1 + s)]
        mids += [mid, mid]
    m = rt.mesh(vertices=verts, faces=faces)
    m.name = name
    rt.setNumTVerts(m, len(uv))
    for i, (u, v) in enumerate(uv):
        rt.setTVert(m, i + 1, rt.Point3(u, v, 0))
    rt.buildTVFaces(m)
    for i, f in enumerate(faces):
        rt.setTVFace(m, i + 1, f)
        rt.setFaceMatID(m, i + 1, mids[i])
    rt.update(m)
    rt.setUserProp(m, 'AGR_EXPORT_PATH', fbx)
    return m


TWO = 'C:/o/0002_TwoSlot_01.fbx'
s1 = island_mesh('SM_TwoSlot_001_Main', TWO, [(0.1, 0.8, 1), (0.1, 0.8, 2)])  # same UV square, 2 atlases
mm = rt.multimaterial(numsubs=2)
mm.name = 'M_TwoSlot_001_Main'
mm.materialList[0] = material('M_TwoSlot_001_Main_1', [tex('T_TwoSlot_001_Main_d_1.png', 1024, 1024)])
mm.materialList[1] = material('M_TwoSlot_001_Main_2', [tex('T_TwoSlot_001_Main_d_2.png', 1024, 1024)])
s1.material = mm
SH = 'C:/o/0003_Shared_01.fbx'
shared = material('M_Shared_Main_1', [tex('T_Shared_Main_d_1.png', 1024, 1024)])
s2 = island_mesh('SM_Shared_001_Main', SH, [(0.1, 0.3, 1)])
s3 = island_mesh('SM_Shared_002_Main', SH, [(0.4, 0.3, 1)])  # touches s2's island in the shared atlas
s2.material = s3.material = shared
atlas_nodes = [s1, s2, s3]
rep = run('textures_atlas', 'textures', atlas_nodes)
got = codes(rep)
assert got['SM_TwoSlot_001_Main'] == [], got           # r1 pooled both slots -> false tex_padding
assert got['SM_Shared_001_Main'] == ['tex_padding'] and got['SM_Shared_002_Main'] == ['tex_padding'], got
assert rep['plan']['dropped'] == [], rep['plan']['dropped']
print('AGR_CHECKS_TEXTURES_ATLAS', json.dumps(got, sort_keys=True))
for n in atlas_nodes:
    rt.delete(n)

# --- pivot (VPM-2.9-4.b, VPM-2.9-5), metres and centimetres ------------------------------------------
PIV = 'C:/o/SM_Pivot_1.fbx'
p1 = plane('SM_Pivot_1_Main', PIV)
p2 = plane('SM_Pivot_1_MainGlass', PIV)
p2.pivot = rt.Point3(0, 0, 0.05)
p3 = rt.box(name='UCX_SM_Pivot_1_Main_001', length=1, width=1, height=1, pos=rt.Point3(5, 5, 5))
rt.setUserProp(p3, 'AGR_EXPORT_PATH', PIV)
piv_nodes = [p1, p2, p3]
rep = run('pivot_m', 'pivot', piv_nodes)
got = codes(rep)
assert got['SM_Pivot_1_Main'] == [] and got['SM_Pivot_1_MainGlass'] == ['pivot_mismatch', 'pivot_z'], got
assert [d['name'] for d in rep['plan']['dropped']] == ['UCX_SM_Pivot_1_Main_001'], rep['plan']['dropped']
rt.units.SystemType = rt.name('centimeters')  # 0.05 units = 0.5 mm: inside the 1 mm tolerance
got_cm = codes(run('pivot_cm', 'pivot', piv_nodes))
assert got_cm['SM_Pivot_1_MainGlass'] == [], got_cm
rt.units.SystemType = rt.name('meters')
print('AGR_CHECKS_PIVOT m={} cm={}'.format(json.dumps(got, sort_keys=True), json.dumps(got_cm, sort_keys=True)))

# --- macros (the rollout buttons) run on the selection and keep the scene -------------------------------
for macro, tool in (('AGRToolsNames', 'names'), ('AGRToolsTris', 'tris'), ('AGRToolsTextures', 'textures'),
                    ('AGRToolsPivot', 'pivot')):
    rt.select(piv_nodes)
    before = state()
    assert rt.macros.run('AGR Tools', macro), macro
    assert state() == before, macro + ': scene changed'
    results['macros'][macro] = {'ran': True, 'digest_unchanged': True,
                                'selected_offenders': sorted(str(n.name) for n in rt.selection)}
assert results['macros']['AGRToolsPivot']['selected_offenders'] == ['SM_Pivot_1_MainGlass'], results['macros']
mcr = (OUT / 'installed' / 'agr_tools.mcr').read_text(encoding='utf-8')
assert 'macroScript AGRToolsGeojson' in mcr and '"GeoJSON check"' in mcr  # its dialog is not opened in batch
for n in piv_nodes:
    rt.delete(n)

# --- GeoJSON: the pilot twinqa checker through the project Python ---------------------------------------
broken = OUT / 'SM_Tverskaya_12.geojson'
broken.write_bytes(b'{"type": ')
empty = OUT / 'SM_Empty_12.geojson'
empty.write_bytes(b'{}')
geo = {}
for label, path in (('broken', str(broken)), ('empty_object', str(empty)), ('missing', str(OUT / 'SM_None.geojson')),
                    ('wrong_ext', str(OUT / 'x.json')), ('no_path', '')):
    before = state()
    r = agr.checks_050('geojson', path=path)
    assert state() == before
    agr.parse_report(json.dumps(r))
    assert r['status'] == 'fail', (label, r)
    geo[label] = [(f['name'], f['status']) for f in r['plan']['findings']][:4]
    results['checks']['geojson_' + label] = r
assert geo['broken'][0] == ('JSON', 'fail'), geo
assert geo['missing'][0][0] == 'checker' and geo['wrong_ext'][0][0] == 'file', geo
print('AGR_CHECKS_GEOJSON', json.dumps(geo, sort_keys=True))

with (OUT / 'results.json').open('x', encoding='utf-8') as f:
    json.dump(results, f, indent=2, default=str, allow_nan=False)
print('AGR_CHECKS_COMPLETE names=5 tris=6 textures=7+atlas3 pivot=3+cm macros=4 geojson=5 read_only=true')
