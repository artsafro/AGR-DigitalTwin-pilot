"""new-case: #979 branch D native run of export.batch, scene.maps_usage and light.check in locked batch Max on
DISPOSABLE synthetic scenes.

Run via the AGR Lab runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched), then in the real Max Python:
* light.check - the same light file in metres and in centimetres (Spot 1.0/1.49/1.5/1.51 m, Omni 4.9/5.0 m,
  Target Spot measured at the light, 3 Spots 1 m apart, Photometric/Directional/Skylight beside an Omni, a light
  without root, a hidden offender, a root scaled 0.5): identical codes and metre distances; 251 lights -> count
  finding, 260 lights -> the pair after the 250th found; the macro press selects the visible offenders only;
  transforms, wirecolor and names unchanged;
* scene.maps_usage - the T08 synthetic (12 files, 2 truly unused; Blend, DoubleSided, Shell, renderable spline,
  environment, light projector, a copy used through another folder): exactly 2 extra; a missing map with a
  same-name file stays missing; files on disk and the scene unchanged;
* export.batch - 3 groups (clean / dirty geometry / existing FBX): while qa.procedural_objects (branch C) answers
  not_implemented every group is refused and nothing is written; with a stand-in answer of that row (no
  procedural object) the clean group is written and read back, the dirty one fails at the gates, the existing FBX
  gets `_v002` and stays byte-identical, the originals are unchanged; a stand-in procedural offender blocks only
  its group.
Nothing is saved; the scenes are reset between parts.
"""
import hashlib
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
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')  # report memory of this run only
os.environ['AGR_NO_PROMPT'] = '1'
os.environ['AGR_TOOLS_REPO'] = str(ROOT)  # export gates/readback in the project interpreter when Max lacks numpy
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
EDIT = agr._edit_core()


def fresh(units='meters'):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0


def P(*v):
    return rt.Point3(*[float(x) for x in v])


def state_of_scene():
    out = []
    for n in rt.objects:
        tm = n.transform
        out.append((str(n.name), [round(float(c), 6) for r in (tm.row1, tm.row2, tm.row3, tm.row4) for c in (r.x, r.y, r.z)],
                    [int(n.wirecolor.r), int(n.wirecolor.g), int(n.wirecolor.b)], bool(n.isHidden)))
    return sorted(out)


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


# ---- light.check -----------------------------------------------------------------------------------------
def light_file(units):
    """The light file of the acceptance, positions in metres x k system units."""
    fresh(units)
    k = 100.0 if units == 'centimeters' else 1.0
    root = rt.Dummy(name='Addr_Root', pos=P(0, 0, 0))

    def mk(maker, name, x, y=0.0, z=3.0, parent=root, hidden=False):
        if maker == rt.targetSpot:  # pymxs: without an explicit target the Target Spot has none
            n = maker(name=name, target=rt.Targetobject(name=name + '.Target'))
        else:
            n = maker(name=name)
        n.pos = P(x * k, y * k, z * k)
        if parent is not None:
            n.parent = parent
        if hidden:
            n.isHidden = True
        return n

    for i, d in enumerate((1.0, 1.49, 1.5, 1.51)):
        mk(rt.freeSpot, 'Addr_Spot_{:03d}'.format(2 * i + 1), 20.0 * i)
        mk(rt.freeSpot, 'Addr_Spot_{:03d}'.format(2 * i + 2), 20.0 * i + d)
    ts1 = mk(rt.targetSpot, 'Addr_Spot_011', 100.0)
    ts2 = mk(rt.targetSpot, 'Addr_Spot_012', 102.0)  # sources 2 m apart, targets 0.5 m apart
    ts1.target.pos = P(100.75 * k, 0, 0)
    ts2.target.pos = P(101.25 * k, 0, 0)
    for i in range(3):
        mk(rt.freeSpot, 'Addr_Spot_{:03d}'.format(21 + i), 120.0 + i)  # 3 Spots 1 m apart -> 2 pairs
    mk(rt.Omnilight, 'Addr_Omni_001', 140.0)
    mk(rt.freeSpot, 'Addr_Spot_031', 144.9)     # Omni-Spot 4.9
    mk(rt.Omnilight, 'Addr_Omni_002', 160.0)
    mk(rt.Omnilight, 'Addr_Omni_003', 165.0)    # Omni-Omni 5.0 -> norm
    mk(rt.Omnilight, 'Addr_Omni_004', 180.0)
    mk(rt.Free_Light, 'Addr_Photo_001', 181.0)  # beside an Omni: type finding, no pair
    mk(rt.Directionallight, 'Addr_Dir_001', 181.0, 1.0)
    mk(rt.Skylight, 'Addr_Sky_001', 181.0, 2.0)
    mk(rt.Omnilight, 'Addr_Omni_005', 200.0, parent=None)  # no root
    mk(rt.freeSpot, 'Addr_Spot_041', 220.0)
    mk(rt.freeSpot, 'Addr_Spot_042', 221.0, hidden=True)   # hidden offender: reported, never selected
    return root


LIGHT_BAD = {'Addr_Spot_001': ['light_spot_distance'], 'Addr_Spot_002': ['light_spot_distance'],
             'Addr_Spot_003': ['light_spot_distance'], 'Addr_Spot_004': ['light_spot_distance'],
             'Addr_Spot_021': ['light_spot_distance'], 'Addr_Spot_022': ['light_spot_distance'],
             'Addr_Spot_023': ['light_spot_distance'],
             'Addr_Omni_001': ['light_omni_distance'], 'Addr_Spot_031': ['light_omni_distance'],
             'Addr_Photo_001': ['light_type'], 'Addr_Dir_001': ['light_type'], 'Addr_Sky_001': ['light_type'],
             'Addr_Omni_005': ['light_no_root'], 'Addr_Spot_041': ['light_spot_distance']}


def light_units():
    out = {}
    for units in ('meters', 'centimeters'):
        light_file(units)
        before = state_of_scene()
        r = agr.edits_090('light.check', 'preview')
        assert agr.parse_report(json.dumps(r)) == r
        got = {n: c for n, c in codes(r).items() if c}
        assert got == LIGHT_BAD, (units, got)
        assert [(a['item'], a['flags']) for a in r['plan']['ambiguous']] == [('Addr_Spot_042', ['hidden'])], units
        assert state_of_scene() == before, units
        out[units] = {'pairs': sorted((p['a'], p['b'], p['d_m']) for p in r['plan']['pairs']),
                      'summary': r['plan']['summary'], 'status': r['status']}
    assert out['meters']['pairs'] == out['centimeters']['pairs'] or \
        [(a, b, round(d, 4)) for a, b, d in out['meters']['pairs']] == \
        [(a, b, round(d, 4)) for a, b, d in out['centimeters']['pairs']]
    assert len(out['meters']['pairs']) == 6  # 1.0, 1.49, 2 of the 3-in-a-row, Omni-Spot 4.9, the hidden pair
    return out


def light_select_press():
    """The macro press (runtime.ui -> edit_ui) selects the visible offenders only; the scene stays unchanged."""
    light_file('meters')
    keep = rt.Box(name='Smoke_Selected')
    rt.select(keep)
    before = state_of_scene()
    import __main__
    mod = getattr(__main__, 'agr_tools_runtime', None) or agr
    ran = bool(rt.macros.run('AGR Tools', 'AGRToolsLightCheck'))  # the registered macro (runtime.ui inside)
    macro_pick = sorted(str(n.name) for n in rt.selection)
    rt.select(keep)
    rep = mod.ui('light.check')
    picked = sorted(str(n.name) for n in rt.selection)
    assert picked == sorted(LIGHT_BAD), picked
    assert 'Addr_Spot_042' not in picked
    assert state_of_scene() == before
    assert ran and macro_pick == picked, (ran, macro_pick)
    return {'selected': len(picked), 'status': rep['status'], 'macro_ran': ran}


def light_count_and_scale():
    out = {}
    fresh('meters')
    root = rt.Dummy(name='Addr_Root', pos=P(0, 0, 0))
    for i in range(251):
        n = rt.Omnilight(name='Addr_Omni_{:03d}'.format(i + 1))
        n.pos = P(10.0 * (i % 20), 10.0 * (i // 20), 3)
        n.parent = root
    t = time.perf_counter()
    r = agr.edits_090('light.check', 'preview')
    out['ms_251'] = round((time.perf_counter() - t) * 1000)
    assert {n: c for n, c in codes(r).items() if c} == {'Addr_Omni_251': ['light_count']}, codes(r)
    for i in range(7):
        n = rt.freeSpot(name='Addr_Spot_{:03d}'.format(i + 1))
        n.pos = P(1000.0 + (1.0 if i == 6 else 10.0 * i), 500, 3)  # light no. 258: 1 m from no. 252
        n.parent = root
    for i in range(2):
        n = rt.freeSpot(name='Addr_Spot_{:03d}'.format(8 + i))
        n.pos = P(2000.0 + 1.2 * i, 0, 3)  # pair no. 259/260
        n.parent = root
    r = agr.edits_090('light.check', 'preview')
    pairs = {(p['a'], p['b']) for p in r['plan']['pairs']}
    assert ('Addr_Spot_008', 'Addr_Spot_009') in pairs and r['plan']['summary']['lights'] == 260, pairs
    out['pairs_260'] = r['plan']['summary']['pairs_checked']
    fresh('meters')
    root = rt.Dummy(name='Addr_Root', pos=P(0, 0, 0))
    a, b = rt.freeSpot(name='Addr_Spot_001'), rt.freeSpot(name='Addr_Spot_002')
    a.pos, b.pos = P(0, 0, 3), P(2, 0, 3)
    a.parent = b.parent = root
    root.scale = P(0.5, 0.5, 0.5)  # world distance 1.0 m
    r = agr.edits_090('light.check', 'preview')
    assert [p['d_m'] for p in r['plan']['pairs']] == [1.0], r['plan']['pairs']
    out['scaled_root_d_m'] = r['plan']['pairs'][0]['d_m']
    return out


# ---- scene.maps_usage --------------------------------------------------------------------------------------
def _png(path, rgb):
    tex = agr._load_core('tex_core.py', 'agr_tools_tex_core')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tex.solid_png(8, rgb))
    return str(path)


def _bitmap(path):
    t = rt.Bitmaptexture()
    t.filename = str(path)
    return t


def _std(name, path):
    m = rt.Standardmaterial(name=name)
    m.diffuseMap = _bitmap(path)
    return m


def _disk(root):
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(root).rglob('*')) if p.is_file()}


def _scene_maps():
    out = []
    for tm in rt.getClassInstances(rt.BitmapTexture):
        out.append(str(tm.filename))
    return sorted(out)


def maps_t08():
    fresh('meters')
    base = OUT / 't08'
    maps = base / 'maps'
    files = {}
    for i, name in enumerate(('a_std', 'b_multi', 'c_blend', 'd_double', 'e_shell', 'f_spline', 'g_env', 'h_proj',
                              'i_moved', 'j_std', 'k_unused', 'l_unused')):
        files[name] = _png(maps / (name + '.png'), (10 * i, 100, 200))
    old = base / 'old' / 'i_moved.png'
    old.parent.mkdir(parents=True)
    old.write_bytes(Path(files['i_moved']).read_bytes())
    boxes = []
    for i in range(7):
        b = rt.Box(name='SM_T08_{}_Main'.format(i), pos=P(5 * i, 0, 0))
        boxes.append(b)
    boxes[0].material = _std('M_a', files['a_std'])
    multi = rt.Multimaterial(numsubs=2)
    multi.materialList[0] = _std('M_b', files['b_multi'])
    boxes[1].material = multi
    blend = rt.Blend()
    blend.map1 = _std('M_c', files['c_blend'])
    boxes[2].material = blend
    double = rt.DoubleSided()
    double.material1 = _std('M_d', files['d_double'])
    boxes[3].material = double
    shell = rt.Shell_Material()
    shell.originalMaterial = _std('M_e', files['e_shell'])
    boxes[4].material = shell
    boxes[5].material = _std('M_i', str(old))
    boxes[6].material = _std('M_j', files['j_std'])
    spline = rt.Circle(name='Spline_T08', radius=1.0)
    spline.render_renderable = True
    spline.material = _std('M_f', files['f_spline'])
    rt.environmentMap = _bitmap(files['g_env'])
    lamp = rt.Omnilight(name='Lamp_T08')
    lamp.projector = True
    lamp.projectorMap = _bitmap(files['h_proj'])
    disk = _disk(base)
    scene = (_scene_maps(), state_of_scene())
    r = agr.edits_090('scene.maps_usage', 'preview', None, None, {'folders': [str(maps)]})
    assert agr.parse_report(json.dumps(r)) == r
    extra = sorted(Path(x['path']).name for x in r['plan']['extra'])
    assert extra == ['k_unused.png', 'l_unused.png'], (extra, r['plan']['table'])
    assert r['plan']['missing'] == [] and [Path(c['path']).name for c in r['plan']['copies']] == ['i_moved.png']
    assert _disk(base) == disk and (_scene_maps(), state_of_scene()) == scene
    return {'summary': r['plan']['summary'], 'extra': extra, 'sources': sorted({s for u in r['plan']['used']
                                                                               for s in u['sources']}),
            'status': r['status']}


def maps_missing():
    fresh('meters')
    base = OUT / 'gone'
    maps = base / 'maps'
    namesake = _png(maps / 'e_moved.png', (1, 2, 3))
    ok = _png(maps / 'ok.png', (4, 5, 6))
    gone = str(base / 'elsewhere' / 'e_moved.png').replace('\\', '/')
    a = rt.Box(name='SM_Gone_Main')
    a.material = rt.Standardmaterial(name='M_gone')
    rt.execute('(getNodeByName "SM_Gone_Main").material.diffuseMap = Bitmaptexture fileName:"{}"'.format(gone))
    b = rt.Box(name='SM_Ok_Main', pos=P(5, 0, 0))
    b.material = _std('M_ok', ok)
    disk = _disk(base)
    r = agr.edits_090('scene.maps_usage', 'preview', None, None, {'folders': [str(maps)]})
    assert codes(r) == {'SM_Gone_Main': ['map_missing'], 'SM_Ok_Main': []}, codes(r)
    miss = r['plan']['missing']
    assert len(miss) == 1 and Path(miss[0]['candidates'][0]).name == 'e_moved.png', miss
    assert [Path(x['path']).name for x in r['plan']['extra']] == ['e_moved.png']
    assert _disk(base) == disk
    rep = agr.ui('scene.maps_usage')  # the macro path (whole scene, default folders: the used maps' folder)
    return {'missing': [m['path'] for m in miss], 'candidate': miss[0]['candidates'], 'ui_status': rep['status']}


# ---- export.batch ------------------------------------------------------------------------------------------
def _export_box(name, pos, path, size=(8, 6, 6)):
    b = rt.Box(name=name, width=size[0], length=size[1], height=size[2], pos=P(*pos))
    b.mapcoords = True
    rt.convertToPoly(b)
    for face in range(1, int(rt.polyop.getNumFaces(b)) + 1):
        rt.polyop.setFaceMatID(b, face, 1)  # a Box has IDs 1-6; one Standard material = ID 1
    mat = rt.Standardmaterial(name='M_{}_1'.format(name))
    b.material = mat
    rt.setUserPropBuffer(b, 'MapChannel:1 = UV\r\nAGR_EXPORT_PATH={}\r\nAGR_TEXEL_PROFILE=NPM\r\n'
                            'AGR_TEXEL_MAP=M_{}_1=128\r\n'.format(str(path).replace('\\', '/'), name))
    return b


def batch_scene(out):
    fresh('meters')
    out.mkdir(parents=True)
    a = _export_box('SM_BatchClean_Main', (0, 0, 0), out / 'clean.fbx')
    a2 = _export_box('SM_BatchClean2_Main', (20, 0, 0), out / 'clean.fbx')
    d = _export_box('SM_BatchDirty_Main', (40, 0, 0), out / 'dirty.fbx')
    twin = rt.copy(d)
    twin.pos = P(40, 0, 0.001)
    rt.polyop.attach(d, twin)  # a 1 mm double skin: xView overlap
    o = _export_box('SM_BatchOld_Main', (60, 0, 0), out / 'old.fbx')
    (out / 'old.fbx').write_bytes(b'previous delivery')
    return [a, a2, d, o]


def _stand_in(offenders=()):
    real = agr.edits_090

    def edits(tool, mode, preview=None, nodes=None, options=None):
        if tool == 'qa.procedural_objects':
            objs = [EDIT.entry(int(rt.getHandleByAnim(rt.getNodeByName(n))), n,
                               [EDIT.finding('procedural_class', (), 'stand-in: ForestPackPro')]) for n in offenders]
            return EDIT.report(tool, 'preview', objs, state_hash='stand-in for branch C')
        return real(tool, mode, preview, nodes, options)
    return real, edits


def batch_refused_while_c_is_empty():
    out = OUT / 'batch_refused'
    batch_scene(out)
    proc = agr.edits_090('qa.procedural_objects', 'preview')
    if proc['status'] != 'not_implemented':
        return {'skipped': 'qa.procedural_objects is implemented: ' + proc['status']}
    p = agr.edits_090('export.batch', 'preview')
    assert all(c == ['procedural_unchecked'] for c in codes(p).values()) and p['plan']['done'] == [], codes(p)
    a = agr.edits_090('export.batch', 'apply', p)
    assert a['plan']['done'] == [] and sorted(x.name for x in out.iterdir()) == ['old.fbx']
    return {'preview': p['status'], 'apply_done': a['plan']['done'], 'files': sorted(x.name for x in out.iterdir())}


def batch_acceptance():
    out = OUT / 'batch'
    nodes = batch_scene(out)
    real, edits = _stand_in()
    agr.edits_090 = edits
    try:
        snap = agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot(nodes)
        p = edits('export.batch', 'preview')
        rows = {Path(g['requested']).name: g for g in p['plan']['groups']}
        assert rows['clean.fbx']['status'] == 'pass' and rows['old.fbx']['status'] == 'pass', rows
        assert rows['dirty.fbx']['status'] == 'fail' and rows['dirty.fbx']['stopped'] == 'xview', rows['dirty.fbx']
        assert Path(rows['old.fbx']['target']).name == 'old_v002.fbx'
        assert sorted(x.name for x in out.iterdir()) == ['old.fbx']
        a = edits('export.batch', 'apply', p)
        done = {Path(d['item']).name: d for d in a['plan']['done']}
        assert set(done) == {'clean.fbx', 'old_v002.fbx'}, a['plan']
        assert done['clean.fbx']['readback']['object_count'] == 2 and done['old_v002.fbx']['readback']['object_count'] == 1
        assert (out / 'old.fbx').read_bytes() == b'previous delivery'
        files = sorted(x.name for x in out.iterdir())
        assert files == ['clean.fbx', 'clean.report.json', 'old.fbx', 'old_v002.fbx', 'old_v002.report.json'], files
        assert agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot(nodes) == snap
        assert a['status'] == 'fail' and codes(a)['SM_BatchDirty_Main']
        # a stand-in procedural offender blocks only its group (the files above now exist: clean -> _v002)
        _, blocked = _stand_in(['SM_BatchOld_Main'])
        agr.edits_090 = blocked
        q = blocked('export.batch', 'preview')
        st = {Path(g['requested']).name: (g['status'], Path(g['target']).name) for g in q['plan']['groups']}
        assert st == {'clean.fbx': ('pass', 'clean_v002.fbx'), 'dirty.fbx': ('fail', 'dirty.fbx'),
                      'old.fbx': ('blocked', 'old_v003.fbx')}, st
        assert codes(q)['SM_BatchOld_Main'] == ['procedural_object']
    finally:
        agr.edits_090 = real
    return {'preview_groups': {k: (v['status'], Path(v['target']).name) for k, v in rows.items()},
            'apply_done': {k: v['readback']['object_count'] for k, v in done.items()}, 'files': files,
            'dirty_codes': codes(a)['SM_BatchDirty_Main'], 'blocked': st, 'snapshot_unchanged': True}


for name, fn in (('light_units', light_units), ('light_select_press', light_select_press),
                 ('light_count_and_scale', light_count_and_scale), ('maps_t08', maps_t08),
                 ('maps_missing', maps_missing), ('batch_refused_while_c_is_empty', batch_refused_while_c_is_empty),
                 ('batch_acceptance', batch_acceptance)):
    check(name, fn)
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
print('AGR_979D_SUMMARY ' + json.dumps(summary, ensure_ascii=True)[:3000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
