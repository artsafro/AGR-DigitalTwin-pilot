"""new-case: #979 branch C native run of qa.address, qa.normals, qa.sintez, qa.facade_compare and
qa.procedural_objects in locked batch Max on DISPOSABLE synthetic scenes.

Run via the AGR Lab runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then in the real Max Python:
* qa.address — SM_ objects named with the lab L05 addresses (Latin ones) + the full list through options.addresses:
  the primary code of each address as in docs/experiments/qa.address.md «Минимальная приёмка»;
* qa.normals — the same physical scene in metres and in centimetres (pairs of quads 0 / 1 mm / 2 cm / 5 cm, 0° / 5°,
  1 m and 0.2 m; elements A, C, B; flipped box; Box primitive converted to poly with 2 flipped faces; L volume; two
  boxes, second flipped; glass without a second side; Flora card with its back side; Editable_Mesh; primitive):
  identical codes and face ids; materials, viewport settings, command panel, selection and the scene unchanged;
* qa.sintez — preflight from the scene vs a SINTEZ fixture: a scaled box -> sintez_mismatch only on it;
* qa.facade_compare — 7 panels (6 joints) vs sheets with 6 and 7 joints, metres and centimetres; renderer and
  viewport the same before and after; the picture is a new file, a second press writes _v002;
* qa.procedural_objects — Populate IdleArea / Flow / Crowd, Chaos Scatter when present, a Box: exactly the
  procedural ones listed, nothing collapsed; Missing_* class names this Max knows are recorded; export.batch (branch
  D) blocks only the group with a procedural object through runtime.edits_090.
Nothing is saved; the scenes are reset between parts.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback

from pymxs import runtime as rt

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'tests' / 'max_tools' / 'fixtures_qa9'
OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')  # report memory of this run only
os.environ['AGR_NO_PROMPT'] = '1'
os.environ['AGR_TOOLS_REPO'] = str(ROOT)
venv = ROOT / '.venv' / 'Scripts' / 'python.exe'
if venv.is_file():
    os.environ['AGR_PYTHON'] = str(venv)
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    try:
        summary['checks'][name] = fn()
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
    import runtime as agr
    return agr


agr = install()
summary['runtime_version'] = agr.VERSION
EMAX = agr._load_core('edit_max.py', 'agr_tools_edit_max')


def fresh(units='meters'):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def P(*v):
    return rt.Point3(*[float(x) for x in v])


def mesh_node(name, verts, faces, k=1.0, poly=True, sg=1):
    node = rt.mesh(name=name, vertices=rt.Array(*[P(x * k, y * k, z * k) for x, y, z in verts]),
                   faces=rt.Array(*[P(a + 1, b + 1, c + 1) for a, b, c in faces]))
    for i in range(1, len(faces) + 1):
        rt.setFaceSmoothGroup(node, i, sg)
    rt.update(node)
    if poly:
        rt.convertToPoly(node)
    return node


def quad(z=0.0, tilt=0.0, size=1.0, flip=False, off=0.0):
    t = math.radians(tilt)
    h = size / 2
    v = [(x + off, y * math.cos(t), z + y * math.sin(t)) for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))]
    f = [(0, 1, 2), (0, 2, 3)]
    return v, ([(p, r, q) for p, q, r in f] if flip else f)


def box(o=(0, 0, 0), s=(1, 1, 1), flip=False):
    x, y, z = o
    a, b, c = s
    v = [(x, y, z), (x + a, y, z), (x + a, y + b, z), (x, y + b, z), (x, y, z + c), (x + a, y, z + c),
         (x + a, y + b, z + c), (x, y + b, z + c)]
    f = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5), (2, 3, 7),
         (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return v, ([(p, r, q) for p, q, r in f] if flip else f)


def l_shape(o=(0, 0, 0)):
    pts = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
    v = [(x + o[0], y + o[1], 0) for x, y in pts] + [(x + o[0], y + o[1], 1) for x, y in pts]
    f = [(0, 3, 1), (1, 3, 2), (0, 5, 3), (3, 5, 4), (6, 7, 9), (7, 8, 9), (6, 9, 11), (9, 10, 11)]
    for i in range(6):
        j = (i + 1) % 6
        f += [(i, j, j + 6), (i, j + 6, i + 6)]
    return v, f


def merge(*parts):
    v, f = [], []
    for pv, pf in parts:
        n = len(v)
        v += pv
        f += [(a + n, b + n, c + n) for a, b, c in pf]
    return v, f


def shift(vf, dx=0.0, dy=0.0):
    v, f = vf
    return [(x + dx, y + dy, z) for x, y, z in v], f


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


def ids(report):
    return {o['name']: sorted({tuple(f['ids']) for f in o['findings']}) for o in report['objects']}


def view_state():
    """Renderer, Nitrous active-view settings, command panel, selection, material handles: must not change."""
    out = {'renderer': str(rt.classOf(rt.renderers.current)), 'panel': str(rt.getCommandPanelTaskMode()),
           'selection': sorted(int(rt.getHandleByAnim(n)) for n in rt.selection),
           'materials': sorted((str(n.name), int(rt.getHandleByAnim(n.material)) if n.material else 0)
                               for n in rt.objects)}
    try:
        vs = rt.NitrousGraphicsManager.GetActiveViewportSetting()
        out['nitrous'] = {k: str(getattr(vs, k)) for k in ('VisualStyleMode', 'ShowEdgedFacesEnabled',
                                                            'AmbientOcclusionEnabled', 'ShadowsEnabled')}
    except Exception as exc:  # noqa: BLE001 - batch Max may have no Nitrous view
        out['nitrous'] = 'n/a: ' + type(exc).__name__
    return out


def scene_hash(nodes=None):
    """Names, classes, transforms and (where Max gives one) the mesh hash of every node."""
    nodes = list(nodes) if nodes is not None else [n for n in rt.objects]
    rows = []
    for n in nodes:
        try:
            mesh = EMAX.mesh_hash(n) if rt.canConvertTo(n, rt.TriMeshGeometry) else None
        except RuntimeError:  # Populate Crowd: convertible by class, no mesh
            mesh = 'no mesh'
        rows.append([int(rt.getHandleByAnim(n)), str(n.name), str(rt.classOf(n)), EMAX._matrix(n.transform), mesh])
    return hashlib.sha256(json.dumps(sorted(rows), sort_keys=True).encode()).hexdigest()


# ---- qa.address ------------------------------------------------------------------------------------------
ADDRESS = {
    'Tverskaya_7': None, 'Tverskaya_7_Str_1': None, 'Tverskaya_7_K_2': None, 'PervyjAvtozavodskijPrd_7': None,
    'Parkovaya_7': None, 'Valovaya_7': None, '2jKotelnicheskijPer_7': None, 'PosAkulovo_7': None,
    'Tverskaya__7': 'addr_parts', 'TverskayaUlicza_7': 'addr_abbr', 'Qwxz_7': 'addr_street_unknown',
    'Tverskaya_7A': 'addr_parts', 'tverskaya_7': 'addr_case', 'TVERSKAYA_7': 'addr_case',
    'PervyyAvtozavodskijPrd_7': 'addr_translit', 'Tverskaya_Dom_7': None, 'Tverskaya_Uch_7': None,
}
ONLY_OPTIONS = {'Тверская_7': 'addr_chars', 'Tverskaya 7': 'addr_chars', 'Tverskaya_7.': 'addr_chars', '_': 'addr_parts',
                '': 'addr_parts', 'Tverskaya7': 'addr_parts', 'Tverskaya_7' + '_Str_1' * 40: 'addr_length',
                '_Tverskaya_7': 'addr_parts', 'Tverskaya_7_': 'addr_parts'}


def address():
    fresh()
    nodes = []
    for i, a in enumerate(ADDRESS):
        n = rt.Box(name='SM_{}_Main'.format(a), pos=P(i * 2, 0, 0))
        nodes.append(n)
    rt.select(nodes)
    before, h0 = view_state(), scene_hash()
    r = agr.edits_090('qa.address', 'preview', None, None)
    got = codes(r)
    want = {'SM_{}_Main'.format(a): [c] if c else [] for a, c in ADDRESS.items()}
    assert got == want, (got, want)
    warns = sorted((w['address'], w['text']) for w in r['plan']['warnings'])
    assert [a for a, _ in warns] == ['Tverskaya_Dom_7', 'Tverskaya_Uch_7'], warns
    allx = dict(ADDRESS, **ONLY_OPTIONS)
    r2 = agr.edits_090('qa.address', 'preview', options={'addresses': list(allx)})
    prim = {x['address']: x['primary'] for x in r2['plan']['addresses']}
    assert prim == allx, {k: (prim.get(k), v) for k, v in allx.items() if prim.get(k) != v}
    assert view_state() == before and scene_hash() == h0
    return {'objects': len(got), 'options_addresses': len(prim), 'failed': r2['plan']['summary']['failed'],
            'directory': r['plan']['directory']['count'], 'warnings': warns}


# ---- qa.normals ------------------------------------------------------------------------------------------
def normals_scene(units):
    fresh(units)
    k = 100.0 if units == 'centimeters' else 1.0
    made = {}
    x = 0.0
    for size in (1.0, 0.2):
        for gap in (0.0, 0.001, 0.02, 0.05):
            for tilt in (0.0, 5.0):
                name = 'SM_Pair_{}_{}_{}_Main'.format(int(size * 10), int(gap * 1000), int(tilt))
                made[name] = mesh_node(name, *shift(merge(quad(0, size=size), quad(gap, tilt, size=size)), x), k=k)
                x += 2.0
    made['SM_ACB_Main'] = mesh_node('SM_ACB_Main', *shift(merge(quad(0), quad(0, off=10), quad(0.001)), 0, 10), k=k)
    made['SM_BoxFlip_Main'] = mesh_node('SM_BoxFlip_Main', *box((0, 20, 0), flip=True), k=k)
    made['SM_BoxOk_Main'] = mesh_node('SM_BoxOk_Main', *box((3, 20, 0)), k=k)
    made['SM_L_Main'] = mesh_node('SM_L_Main', *l_shape((6, 20, 0)), k=k)
    made['SM_TwoBoxes_Main'] = mesh_node('SM_TwoBoxes_Main', *merge(box((12, 20, 0)), box((16, 20, 0), flip=True)), k=k)
    made['SM_Pane_001_MainGlass'] = mesh_node('SM_Pane_001_MainGlass', *shift(quad(0), 0, 30), k=k)
    made['SM_Card_Flora'] = mesh_node('SM_Card_Flora', *shift(merge(quad(0), quad(-0.005, flip=True)), 3, 30), k=k)
    made['SM_MeshPair_Main'] = mesh_node('SM_MeshPair_Main', *shift(merge(quad(0), quad(0.001)), 6, 30), k=k,
                                         poly=False)
    prim = rt.Box(name='SM_Primitive_Main', pos=P(9 * k, 30 * k, 0), width=k, length=k, height=k)
    made['SM_Primitive_Main'] = prim
    pb = rt.Box(name='SM_PolyBox2Flip_Main', pos=P(12 * k, 30 * k, 0), width=k, length=k, height=k)
    rt.convertToPoly(pb)
    rt.polyop.flipNormals(pb, rt.execute('#{1, 2}'))
    made['SM_PolyBox2Flip_Main'] = pb
    mat = rt.StandardMaterial(name='M_Probe')
    made['SM_BoxOk_Main'].material = mat
    return made


NORMALS_WANT = {
    'SM_Pair_10_0_0_Main': ['double_face'], 'SM_Pair_10_0_5_Main': ['double_face'],
    'SM_Pair_10_1_0_Main': ['double_face'], 'SM_Pair_10_1_5_Main': ['double_face'],
    'SM_Pair_10_20_0_Main': [], 'SM_Pair_10_20_5_Main': [], 'SM_Pair_10_50_0_Main': [], 'SM_Pair_10_50_5_Main': [],
    'SM_Pair_2_0_0_Main': ['double_face'], 'SM_Pair_2_0_5_Main': ['double_face'],
    'SM_Pair_2_1_0_Main': ['double_face'], 'SM_Pair_2_1_5_Main': ['double_face'],
    'SM_Pair_2_20_0_Main': [], 'SM_Pair_2_20_5_Main': [], 'SM_Pair_2_50_0_Main': [], 'SM_Pair_2_50_5_Main': [],
    'SM_ACB_Main': ['double_face'], 'SM_BoxFlip_Main': ['normal_inward'], 'SM_BoxOk_Main': [], 'SM_L_Main': [],
    'SM_TwoBoxes_Main': ['normal_inward'], 'SM_Pane_001_MainGlass': ['missing_double_side'], 'SM_Card_Flora': [],
    'SM_MeshPair_Main': ['double_face'], 'SM_Primitive_Main': [],
}


def normals():
    out = {}
    for units in ('meters', 'centimeters'):
        made = normals_scene(units)
        rt.select([made['SM_BoxOk_Main']])
        rt.setCommandPanelTaskMode(rt.Name('create'))
        before, h0 = view_state(), scene_hash()
        r = agr.edits_090('qa.normals', 'preview', None, list(made.values()))
        assert view_state() == before, (before, view_state())
        assert scene_hash() == h0
        got = codes(r)
        pb = made['SM_PolyBox2Flip_Main']
        # Measured, not assumed: does Editable_Poly keep two flipped faces of a closed box (lab L05: not built)?
        nz = [round(float(rt.polyop.getFaceNormal(pb, f).z), 3) for f in (1, 2)]
        flipped = nz[0] > 0 and nz[1] < 0  # box bottom normal -z, top +z when not flipped
        want = dict(NORMALS_WANT, SM_PolyBox2Flip_Main=['normal_inward'] if flipped else [])
        assert got == want, {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        flags = r['plan']['flags']
        assert flags['SM_PolyBox2Flip_Main']['ids'] == 'poly', flags['SM_PolyBox2Flip_Main']
        out[units] = {'codes': got, 'ids': ids(r), 'm_per_unit': r['plan']['m_per_unit'],
                      'poly_flip': {'face_normal_z_1_2': nz, 'kept_flipped': flipped,
                                    'ids': ids(r)['SM_PolyBox2Flip_Main'],
                                    'faces': int(rt.polyop.getNumFaces(pb)), 'verts': int(rt.polyop.getNumVerts(pb))}}
        if flipped:
            assert out[units]['poly_flip']['ids'] == [(1, 2)], out[units]['poly_flip']
    assert out['meters']['ids'] == out['centimeters']['ids']
    return {'meters_equals_centimeters': True, 'objects': len(out['meters']['codes']),
            'm_per_unit': [out['meters']['m_per_unit'], out['centimeters']['m_per_unit']],
            'poly_flip': out['meters']['poly_flip'], 'twoboxes_ids': out['meters']['ids']['SM_TwoBoxes_Main'],
            'flip_ids': out['meters']['ids']['SM_BoxFlip_Main']}


# ---- qa.sintez -------------------------------------------------------------------------------------------
def sintez():
    fresh()
    a = rt.Box(name='SM_SintezA_Main', pos=P(0, 0, 0))
    b = rt.Box(name='SM_SintezB_Main', pos=P(5, 0, 0))
    for n in (a, b):
        rt.convertToPoly(n)
        rt.setUserProp(n, 'AGR_EXPORT_PATH', 'C:/agr-out/0101_Synthetic_01.fbx')
    b.scale = P(2, 1, 1)
    rt.select([a, b])
    h0 = scene_hash()
    r = agr.edits_090('qa.sintez', 'preview', options={'sintez': str(FIX / 'sintez_hp_all_verified.json')})
    assert codes(r) == {'SM_SintezA_Main': [], 'SM_SintezB_Main': ['sintez_mismatch']}, codes(r)
    r2 = agr.edits_090('qa.sintez', 'preview', options={'sintez': str(FIX / 'sintez_hp_2_3_17_failed.json')})
    assert codes(r2) == {'SM_SintezA_Main': ['sintez_unmatched'],
                         'SM_SintezB_Main': ['sintez_mismatch', 'sintez_unmatched']}, codes(r2)
    assert scene_hash() == h0
    return {'table': r['plan']['table'], 'with_2_3_17_failed': codes(r2)}


# ---- qa.facade_compare ------------------------------------------------------------------------------------
def panels(k, y=0.0):
    parts, x = [], 0.0
    for _ in range(7):
        v = [(x, y, 0), (x + 0.98, y, 0), (x + 0.98, y, 3.0), (x, y, 3.0)]
        parts.append((v, [(0, 1, 2), (0, 2, 3)]))
        x += 1.0
    return merge(*parts)


def facade():
    res = {}
    for units in ('meters', 'centimeters'):
        fresh(units)
        k = 100.0 if units == 'centimeters' else 1.0
        n6 = mesh_node('SM_Facade6_Main', *panels(k), k=k)
        n7 = mesh_node('SM_Facade7_Main', *panels(k, 5.0), k=k)
        rt.select([n6, n7])
        before, h0 = view_state(), scene_hash()
        opts = {'px_per_m': 50, 'out': str(OUT / ('facade_' + units)),
                'sheets': {'SM_Facade6_Main': {'path': str(FIX / 'facade_sheet_6.pgm'), 'px_per_m': 50},
                           'SM_Facade7_Main': {'path': str(FIX / 'facade_sheet_7.pgm'), 'px_per_m': 50}}}
        r = agr.edits_090('qa.facade_compare', 'preview', options=opts)
        assert codes(r) == {'SM_Facade6_Main': [], 'SM_Facade7_Main': ['facade_joints']}, codes(r)
        r2 = agr.edits_090('qa.facade_compare', 'preview', options=opts)
        names = sorted(Path(f['image']).name for f in r2['plan']['facades'])
        assert names == ['facade_SM_Facade6_Main_v002.png', 'facade_SM_Facade7_Main_v002.png'], names
        assert view_state() == before and scene_hash() == h0
        res[units] = {'counts': [(f['name'], f['sheet'], f['vpm']) for f in r['plan']['facades']],
                      'images': sorted(p.name for p in (OUT / ('facade_' + units)).iterdir()),
                      'renderer': before['renderer']}
    assert res['meters']['counts'] == res['centimeters']['counts']
    return res


# ---- qa.procedural_objects --------------------------------------------------------------------------------
def procedural():
    fresh()
    made, absent = {}, []
    for cls, name in (('IdleAreaObj', 'Proc_Idle'), ('Flow', 'Proc_Flow'), ('Crowd', 'Proc_Crowd'),
                      ('ChaosScatter', 'Proc_Chaos')):
        try:
            node = getattr(rt, cls)()
            node.name = name
            made[name] = node
        except Exception as exc:  # noqa: BLE001 - not creatable on this machine: recorded
            absent.append('{}: {}'.format(cls, type(exc).__name__))
    box_ = rt.Box(name='SM_ProcBox_Main', pos=P(10, 0, 0))
    rt.convertToPoly(box_)
    classes_before = {str(n.name): str(rt.classOf(n)) for n in rt.objects}
    h0 = scene_hash()
    r = agr.edits_090('qa.procedural_objects', 'preview')
    got = codes(r)
    assert got.pop('SM_ProcBox_Main') == []
    assert got == {n: ['proc_object'] for n in made}, got
    assert {str(n.name): str(rt.classOf(n)) for n in rt.objects} == classes_before  # nothing collapsed
    assert scene_hash() == h0 and r['plan']['warnings'] and r['plan']['blocking'] == sorted(
        int(rt.getHandleByAnim(n)) for n in made.values())
    n = agr.edits_090('qa.normals', 'preview', None, list(made.values()) + [box_])
    normals_skipped = [x['item'] for x in n['plan']['skipped']]
    missing = sorted({str(c) for sc in ('GeometryClass', 'shape', 'helper', 'light', 'modifier', 'material',
                                        'textureMap') for c in getattr(rt, sc).classes if 'missing' in str(c).lower()})
    # export.batch (branch D) through runtime.edits_090: the group with the IdleArea is blocked, the other not
    out = OUT / 'batch'
    out.mkdir()
    rt.setUserProp(box_, 'AGR_EXPORT_PATH', str(out / 'clean.fbx'))
    if 'Proc_Idle' in made:
        rt.setUserProp(made['Proc_Idle'], 'AGR_EXPORT_PATH', str(out / 'proc.fbx'))
    b = agr.edits_090('export.batch', 'preview')
    groups = {Path(g['requested']).name: g['status'] for g in b['plan']['groups']}
    assert groups.get('proc.fbx') == 'blocked' and groups.get('clean.fbx') != 'blocked', groups
    assert b['plan']['procedural']['state'] == 'checked'
    return {'made': {n: str(rt.classOf(x)) for n, x in made.items()}, 'absent': absent,
            'products': [(p['product'], p['status']) for p in r['plan']['products']], 'missing_classes': missing,
            'batch_groups': groups, 'normals_skipped': normals_skipped}


for name, fn in (('address', address), ('normals', normals), ('sintez', sintez), ('facade', facade),
                 ('procedural', procedural)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
print('AGR_979C_SUMMARY ' + json.dumps(summary, ensure_ascii=True, default=str)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
