"""new-case: #979 branch A native acceptance of place.* in locked batch Max on DISPOSABLE synthetic scenes.

Run via the AGR Lab runner; AGR_TEST_OUTPUT must name a NEW directory, AGR_TEST_PACKAGE the built MZP.
Installs the MZP into OUT (no user folders touched) and presses the five buttons through runtime.edits_090
(preview -> apply), checking the «Минимальная приёмка» of docs/experiments/place.*.md and the #979 sections:

* drop_to_ground: slope 15° + flat Ground (the flat one hidden: two Ground objects), pivot bottom / top / centre,
  tilted, sphere; offset 0 / +0.1 / -0.1 m with and without alignment -> smallest vertical gap = offset ± 1 mm;
  metres = centimetres; a miss and a buried object stay; no temporary nodes; one undo restores every transform and
  keeps the user's previous action; 50 objects timed.
* maf_checks: flat + 20° Ground, the #979 table (pass / 5 cm / 0.1 mm / sunk 0.2 / 0.5 m over the slope /
  intersecting pair / hidden flying); scene and selection unchanged.
* replace: 8 Z1 targets (no parent, rotated, scale [1,2,3], under parent scale 2, under rotated [1,3,1] parent, with a
  child, on L_targets, with agr_id), bait synthetic_lampost, master + MASTER_copy; instance mode; re-run changes
  nothing; one undo; copy mode; door stubs (7 doors) by the oriented bbox.
* schedule: 10 rows -> 7 placed, P08 no model, P09 outside Ground, P10 in the building; pivot ±1 mm, rotation
  ±0.01°, sink 10 cm ±1 cm, instances on placement_instances; re-run adds nothing; one undo; centimetre scene.
* flora_repair: 8-object set (identity, negative scale, rotated, quads, instance, no UV, Noise bush, shear child);
  copies on AGR_flora_repair, originals unchanged, FBX readback of every copy equals the source (0.05 mm, UV 2e-5);
  the sheared original's own FBX does not; one undo removes only the copies.
Nothing is saved; the scenes are never written.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import traceback

from pymxs import runtime as rt

OUT = Path(os.environ['AGR_TEST_OUTPUT'])
OUT.mkdir(parents=True, exist_ok=False)
PACKAGE = Path(os.environ['AGR_TEST_PACKAGE'])
os.environ['LOCALAPPDATA'] = str(OUT / 'localappdata')
os.environ['AGR_NO_PROMPT'] = '1'
summary = {'max_version': list(rt.maxVersion())[:3], 'package_sha256': hashlib.sha256(PACKAGE.read_bytes()).hexdigest(),
           'checks': {}, 'errors': {}}
assert not rt.maxFileName, 'only an empty batch document is allowed'


def check(name, fn):
    t0 = time.perf_counter()
    try:
        summary['checks'][name] = fn()
    except Exception:  # noqa: BLE001 - recorded; the run fails at the end
        summary['errors'][name] = traceback.format_exc()[-3000:]
    summary.setdefault('seconds', {})[name] = round(time.perf_counter() - t0, 2)


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
core = agr._load_core('place_core.py', 'agr_tools_place_core')
glue = agr._load_core('place_max.py', 'agr_tools_place_max')
summary['runtime_version'] = agr.VERSION


# ---- scene helpers ------------------------------------------------------------------------------------
def quiet():
    import pymxs
    return pymxs.undo(False)  # scene setup outside any undo record: the run's record is the one to undo


def reset(units='meters'):
    rt.resetMaxFile(rt.Name('noPrompt'))
    rt.units.SystemType = rt.Name(units)
    rt.units.SystemScale = 1.0
    return 1.0 / core.m_per_unit(units, 1.0)  # system units per metre


def ground(name, size, slope=0.0, at=(0.0, 0.0, 0.0), k=1.0, n=4):
    t = math.tan(math.radians(slope))
    w, l = size
    verts, faces = [], []
    for i in range(n + 1):
        for j in range(n + 1):
            x, y = -w / 2 + w * i / n, -l / 2 + l * j / n
            verts.append(rt.Point3((at[0] + x) * k, (at[1] + y) * k, (at[2] + x * t) * k))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j + 1
            b, c, d = a + (n + 1), a + (n + 1) + 1, a + 1
            faces += [rt.Point3(a, b, c), rt.Point3(a, c, d)]
    return rt.mesh(name=name, vertices=rt.Array(*verts), faces=rt.Array(*faces))


def box(name, size, at, k=1.0, rot_z=0.0, tilt_x=0.0, pivot=None, mapcoords=True):
    w, l, h = size
    b = rt.Box(name=name, width=w * k, length=l * k, height=h * k, mapcoords=mapcoords)
    if tilt_x:
        rt.rotate(b, rt.EulerAngles(float(tilt_x), 0, 0))
    if rot_z:
        rt.rotate(b, rt.EulerAngles(0, 0, float(rot_z)))
    b.pos = rt.Point3(*(c * k for c in at))
    if pivot == 'top':
        b.pivot = rt.Point3(b.pos.x, b.pos.y, float(b.max.z))
    elif pivot == 'centre':
        b.pivot = rt.Point3(b.pos.x, b.pos.y, (float(b.max.z) + float(b.min.z)) / 2)
    return b


def mpu():
    return core.m_per_unit(str(rt.units.SystemType), float(rt.units.SystemScale))


def gap_of(node, grounds):
    s = glue._surface(core, grounds, mpu())
    verts, _ = glue._mesh(node, mpu())
    gaps = core.vertical_gaps(verts, s)
    return min(g for _, g in gaps) if gaps else None


def rows_of(node):
    tm = node.transform
    return [round(float(v), 7) for r in (tm.row1, tm.row2, tm.row3, tm.row4) for v in (r.x, r.y, r.z)]


def user_action(name):
    """A user's action before the run, as its own MAXScript undo record. Measured in 0.8 (job
    20261105-003249-e0800495): in 3dsmaxbatch the pymxs undo records of one python.ExecuteFile collapse into one
    step, so whether this action survives the run's undo is recorded (UNDO_KEEPS_USER), not asserted; isolation
    from earlier user actions is shown in interactive Max by the release smoke (branch R)."""
    rt.execute('undo "user action" on (Box name:"{}" width:0.1 length:0.1 height:0.1 pos:[500,500,0])'.format(name))


UNDO_KEEPS_USER = {}


def user_kept(where, name='User_Before'):
    UNDO_KEEPS_USER[where] = rt.getNodeByName(name) is not None
    return True


def undo():
    rt.execute('max undo')


def names():
    return sorted(str(o.name) for o in rt.objects)


def press(tool, nodes, options=None):
    p = agr.edits_090(tool, 'preview', None, nodes, options)
    assert agr.parse_report(json.dumps(p)) == p
    return p


def apply(tool, p):
    r = agr.edits_090(tool, 'apply', p)
    assert agr.parse_report(json.dumps(r)) == r
    return r


def codes(report):
    return {o['name']: sorted({f['code'] for f in o['findings']}) for o in report['objects']}


# ---- place.drop_to_ground -----------------------------------------------------------------------------
def _drop_scene_raw(units='meters'):
    k = reset(units)
    g1 = ground('Relief_A_Ground', (20.0, 20.0), 15.0, (-10.0, 0.0, 0.0), k)
    g2 = ground('Relief_B_Ground', (20.0, 20.0), 0.0, (10.0, 0.0, 3.0), k)
    g2.isHidden = True  # hidden Ground still works
    objs = [box('D_bottom', (1.0, 1.0, 1.0), (-15.0, -5.0, 5.0), k, rot_z=20.0),
            box('D_top', (1.0, 0.6, 0.8), (-10.0, 0.0, 6.0), k, rot_z=-35.0, pivot='top'),
            box('D_centre', (0.8, 0.8, 0.8), (-5.0, 5.0, 6.0), k, pivot='centre'),
            box('D_tilted', (1.2, 0.6, 0.9), (-12.0, 6.0, 6.0), k, tilt_x=12.0, rot_z=25.0),
            box('D_over_B', (1.0, 1.0, 1.0), (12.0, 0.0, 8.0), k)]
    sph = rt.Sphere(name='D_sphere', radius=0.5 * k, segs=16)
    sph.pos = rt.Point3(-8.0 * k, -7.0 * k, 6.0 * k)
    objs.append(sph)
    miss = box('D_miss', (1.0, 1.0, 1.0), (60.0, 0.0, 3.0), k)
    buried = box('D_buried', (1.0, 1.0, 1.0), (-10.0, -2.0, -12.0), k)
    return [g1, g2], objs, miss, buried


def drop():
    out = {'cases': [], 'worst_mm': 0.0}
    by_units = {}
    for units in ('meters', 'centimeters'):
        for offset in (0.0, 0.1, -0.1):
            for align in (False, True):
                if units == 'centimeters' and offset != 0.1:
                    continue
                grounds, objs, miss, buried = _drop_scene(units)
                user_action('User_Before')
                before = names()
                keep = {str(n.name): rows_of(n) for n in objs + [miss, buried]}
                p = press('place.drop_to_ground', objs + [miss, buried], {'offset_m': offset, 'align': align})
                c = codes(p)
                assert c['D_miss'] == ['ground_miss'] and c['D_buried'] == ['under_ground'], c
                assert all(c[str(n.name)] == [] for n in objs), c
                r = apply('place.drop_to_ground', p)
                assert r['status'] == 'pass', r['objects']
                assert names() == before, 'temporary nodes left'
                assert rows_of(miss) == keep['D_miss'] and rows_of(buried) == keep['D_buried']
                gaps = {str(n.name): gap_of(n, grounds) for n in objs}
                worst = max(abs(g - offset) for g in gaps.values())
                assert worst <= 0.001, gaps
                if align:
                    for n in objs[:4]:
                        z = n.transform.row3
                        assert float(z.z) > 0, str(n.name)  # never flipped
                by_units.setdefault((offset, align), {})[units] = gaps
                out['worst_mm'] = max(out['worst_mm'], worst * 1000)
                undo()
                assert all(rows_of(n) == keep[str(n.name)] for n in objs), 'one undo restores every transform'
                user_kept('drop')
                out['cases'].append({'units': units, 'offset': offset, 'align': align, 'worst_mm': worst * 1000})
    for (offset, align), per in by_units.items():
        if 'centimeters' in per:
            d = max(abs(per['meters'][k] - per['centimeters'][k]) for k in per['meters'])
            assert d <= 0.001, (offset, align, d)
            out['m_vs_cm_mm'] = d * 1000
    # buried with the flag: lifted onto the top, not flipped
    grounds, objs, miss, buried = _drop_scene()
    r = apply('place.drop_to_ground', press('place.drop_to_ground', [buried], {'lift_buried': True, 'align': True}))
    assert r['status'] == 'pass' and abs(gap_of(buried, grounds)) <= 0.001 and float(buried.transform.row3.z) > 0
    # 50 objects with alignment
    reset()
    g = ground('Fifty_Ground', (40.0, 40.0), 15.0)
    many = [box('F{:02d}'.format(i), (0.5, 0.5, 0.5), (-15 + 3 * (i % 10), -12 + 5 * (i // 10), 8.0), rot_z=7 * i)
            for i in range(50)]
    t0 = time.perf_counter()
    p = press('place.drop_to_ground', many, {'align': True})
    t1 = time.perf_counter()
    r = apply('place.drop_to_ground', p)
    t2 = time.perf_counter()
    assert r['status'] == 'pass' and max(abs(gap_of(n, [g])) for n in many) <= 0.001
    out['fifty'] = {'preview_s': round(t1 - t0, 3), 'apply_s': round(t2 - t1, 3)}
    try:
        agr.edits_090('place.drop_to_ground', 'apply', p)
    except ValueError as exc:
        out['stale_refused'] = type(exc).__name__
    else:
        raise AssertionError('a used preview was applied again')
    return out


# ---- place.maf_checks ---------------------------------------------------------------------------------
def maf():
    out = {}
    for slope in (0.0, 20.0):
        reset()
        t = math.tan(math.radians(slope))
        g = ground('Maf_Ground', (40.0, 40.0), slope)

        def on(name, x, gap, size=(1.0, 1.0, 1.0)):
            # lowest corner of an axis-aligned box over the slope rising along +X is the uphill one (x + w/2)
            return box(name, size, (x, 0.0, (x + size[0] / 2) * t + gap))
        objs = [on('M_ok', -12.0, 0.0), on('M_5cm', -8.0, 0.05), on('M_01mm', -4.0, 0.0001),
                on('M_sunk', 0.0, -0.2), on('M_half', 4.0, 0.5), on('M_cross_a', 10.0, 0.0),
                box('M_cross_b', (1.0, 1.0, 1.0), (10.6, 0.3, (10.6 + 0.5) * t), rot_z=30.0)]
        hidden = on('M_hidden_fly', 14.0, 0.3)
        hidden.isHidden = True
        keep = rt.Box(name='Keep_Selected')
        rt.select(keep)
        snap = agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot(objs + [hidden])
        p = press('place.maf_checks', objs + [hidden])
        c = codes(p)
        want = {'M_ok': [], 'M_5cm': ['maf_flying'], 'M_01mm': [], 'M_sunk': ['maf_sunk'], 'M_half': ['maf_flying'],
                'M_hidden_fly': ['maf_flying']}
        for k, v in want.items():
            assert c[k] == v, (slope, k, c[k])
        assert 'maf_intersect' in c['M_cross_a'] and 'maf_intersect' in c['M_cross_b'], c
        assert p['plan']['hidden'] == ['M_hidden_fly'] and p['plan']['selects'] is False
        assert [str(n.name) for n in rt.selection] == ['Keep_Selected'], 'read-only row selected something'
        assert agr._load_core('edit_max.py', 'agr_tools_edit_max').snapshot(objs + [hidden]) == snap
        try:
            agr.edits_090('place.maf_checks', 'apply', p)
        except ValueError as exc:
            assert 'read-only' in str(exc)
        else:
            raise AssertionError('apply of a read row accepted')
        out['slope_{:g}'.format(slope)] = c
    return out


# ---- place.replace ------------------------------------------------------------------------------------
def _replace_scene_raw():
    reset()
    master = box('MASTER', (0.4, 0.4, 0.4), (-20.0, 0.0, 0.0))
    rt.addModifier(master, rt.Bend(angle=20))
    mcopy = rt.copy(master)
    mcopy.name = 'MASTER_copy'
    mcopy.pos = rt.Point3(-22.0, 0.0, 0.0)
    targets = {}
    targets['T_none'] = box('T_none', (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))
    targets['T_rot'] = box('T_rot', (1.0, 1.0, 1.0), (3.0, 0.0, 0.0), rot_z=37.0, tilt_x=10.0)
    targets['T_scale'] = box('T_scale', (1.0, 1.0, 1.0), (6.0, 0.0, 0.0))
    targets['T_scale'].scale = rt.Point3(1, 2, 3)
    p2 = rt.Dummy(name='Parent_S2', pos=rt.Point3(9.0, 0.0, 0.0))
    p2.scale = rt.Point3(2, 2, 2)
    targets['T_under_s2'] = box('T_under_s2', (1.0, 1.0, 1.0), (10.0, 1.0, 0.0), rot_z=15.0)
    targets['T_under_s2'].parent = p2
    pnu = rt.Dummy(name='Parent_NU', pos=rt.Point3(14.0, 0.0, 0.0))
    rt.rotate(pnu, rt.EulerAngles(0, 0, 30))
    pnu.scale = rt.Point3(1, 3, 1)
    targets['T_under_nu'] = box('T_under_nu', (1.0, 1.0, 1.0), (15.0, 2.0, 0.0), rot_z=20.0)
    targets['T_under_nu'].parent = pnu
    targets['T_with_child'] = box('T_with_child', (1.0, 1.0, 1.0), (18.0, 0.0, 0.0))
    child = box('Child_of_T', (0.2, 0.2, 0.2), (18.0, 0.0, 2.0))
    child.parent = targets['T_with_child']
    targets['T_layer'] = box('T_layer', (1.0, 1.0, 1.0), (21.0, 0.0, 0.0))
    rt.LayerManager.newLayerFromName('L_targets').addNode(targets['T_layer'])
    targets['T_props'] = box('T_props', (1.0, 1.0, 1.0), (24.0, 0.0, 0.0))
    rt.setUserPropBuffer(targets['T_props'], 'agr_id=Z1-0042\r\nnote=keep\r\n')
    bait = box('synthetic_lampost', (1.0, 1.0, 1.0), (27.0, 0.0, 0.0))
    return master, mcopy, targets, child, bait


def replace():
    out = {}
    master, mcopy, targets, child, bait = _replace_scene()
    user_action('User_Before')
    info = {k: {'rows': glue._rows(n.transform, 1.0), 'layer': str(n.layer.name),
                'parent': None if n.parent is None else str(n.parent.name), 'props': str(rt.getUserPropBuffer(n))}
            for k, n in targets.items()}
    bait_rows = rows_of(bait)
    rt.select(list(targets.values()) + [master])  # master inside the selection (h_instancer defect)
    p = press('place.replace', None, {'master': 'MASTER', 'mask': 'T_*'})
    assert sorted(p['plan']['replaced']) == sorted(targets) and 'MASTER' in p['plan']['unmatched'], p['plan']
    r = apply('place.replace', p)
    assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
    worst = 0.0
    for k, i in info.items():
        n = rt.getNodeByName(k)
        assert n is not None and rt.areNodesInstances(n, master), k
        got = glue._rows(n.transform, 1.0)
        err = max(abs(a - b) for ra, rb in zip(got, i['rows']) for a, b in zip(ra, rb))
        worst = max(worst, err)
        assert err <= 1e-5, (k, err)
        assert str(n.layer.name) == i['layer'] and str(rt.getUserPropBuffer(n)) == i['props'], k
        assert (None if n.parent is None else str(n.parent.name)) == i['parent'], k
    assert str(child.parent.name) == 'T_with_child' and rt.areNodesInstances(child.parent, master)
    assert rt.isValidNode(master) and rt.isValidNode(mcopy) and rows_of(bait) == bait_rows
    out['matrix_error'] = worst
    out['layer'] = str(rt.getNodeByName('T_layer').layer.name)
    out['agr_id'] = str(rt.getUserProp(rt.getNodeByName('T_props'), 'agr_id'))
    count = len(rt.objects)
    again = press('place.replace', [], {'master': 'MASTER', 'mask': 'T_*'})
    assert again['plan']['replaced'] == [] and len(rt.objects) == count, again['plan']
    out['rerun_skipped'] = len(again['plan']['skipped'])
    undo()
    assert all(not rt.areNodesInstances(rt.getNodeByName(k), master) for k in targets), 'one undo restores targets'
    user_kept('replace')
    assert str(rt.getNodeByName('Child_of_T').parent.name) == 'T_with_child'
    # copy mode
    master, mcopy, targets, child, bait = _replace_scene()
    r = apply('place.replace', press('place.replace', [targets['T_rot']], {'master': 'MASTER', 'mode': 'copy'}))
    n = rt.getNodeByName('T_rot')
    assert r['status'] == 'pass' and not rt.areNodesInstances(n, master) and len(n.modifiers) == 1
    out['copy_mode'] = 'independent copy with the Bend'
    # door stubs
    reset()
    doors = []
    for i, (rot, tilt, piv, scale, parent) in enumerate((
            (0, 0, 'centre', (1, 1, 1), None), (0, 0, 'base', (1, 1, 1), None), (30, 0, 'offset', (1, 1, 1), None),
            (0, 0, 'centre', (1, 1, 1), 'rot'), (0, 0, 'mesh', (1, 1, 1), None), (0, 10, 'centre', (1, 1, 1), None),
            (0, 0, 'centre', (1, 2, 1), None))):
        d = box('Door_{}'.format(i), (0.9, 0.05, 2.1), (7.0 * i, 3.0, 0.0), rot_z=rot, tilt_x=tilt)
        if piv == 'base':
            pass
        elif piv == 'offset':
            d.pivot = rt.Point3(d.pos.x + 0.3, d.pos.y + 0.02, d.pos.z + 1.0)
        elif piv == 'mesh':
            rt.convertToMesh(d)
        else:
            d.pivot = rt.Point3(d.pos.x, d.pos.y, d.pos.z + 1.05)
        if scale != (1, 1, 1):
            d.scale = rt.Point3(*scale)
        if parent:
            pr = rt.Dummy(name='DoorParent', pos=rt.Point3(7.0 * i - 1, 2.0, 0.0))
            rt.rotate(pr, rt.EulerAngles(0, 0, 25))
            d.parent = pr
        doors.append(d)
    door_verts = {str(d.name): glue._mesh(d, 1.0)[0] for d in doors}
    p = press('place.replace', doors, {'stub': True})
    r = apply('place.replace', p)
    assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
    dims = {}
    for row in p['plan']['rows']:
        bx = row['box']
        node = rt.getNodeByName(row['name'])
        assert str(rt.classOf(node)) == 'Box', row['name']
        want = (0.9, 0.05 * (2 if row['name'] == 'Door_6' else 1), 2.1)
        assert max(abs(a - b) for a, b in zip((bx['width'], bx['length'], bx['height']), want)) <= 1e-4, (row, want)
        assert all(core.inside_box(v, bx, 1e-4) for v in door_verts[row['name']]), row['name']
        dims[row['name']] = [round(bx['width'], 5), round(bx['length'], 5), round(bx['height'], 5)]
    out['doors'] = dims
    return out


# ---- place.schedule -----------------------------------------------------------------------------------
ROWS = [
    {'id': 'P01', 'model': 'Lib_Bench', 'x': -10.0, 'y': -10.0, 'rotation_deg': 0.0},
    {'id': 'P02', 'model': 'Lib_Bench', 'x': -5.0, 'y': -10.0, 'rotation_deg': 30.0},
    {'id': 'P03', 'model': 'Lib_Bench', 'x': 0.0, 'y': -10.0, 'rotation_deg': 90.0},
    {'id': 'P04', 'model': 'Lib_Lamp', 'x': -10.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P05', 'model': 'Lib_Lamp', 'x': -5.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P06', 'model': 'Lib_Bush', 'x': 0.0, 'y': 0.0, 'rotation_deg': 15.0},
    {'id': 'P07', 'model': 'Lib_Bush', 'x': 5.0, 'y': 0.0, 'rotation_deg': 45.0},
    {'id': 'P08', 'model': 'Lib_Fountain', 'x': 5.0, 'y': 5.0, 'rotation_deg': 0.0},
    {'id': 'P09', 'model': 'Lib_Bench', 'x': 30.0, 'y': 0.0, 'rotation_deg': 0.0},
    {'id': 'P10', 'model': 'Lib_Bench', 'x': 11.0, 'y': 11.0, 'rotation_deg': 0.0},
]


def _schedule_scene_raw(units='meters'):
    k = reset(units)
    g = ground('Site_Ground', (40.0, 40.0), 15.0, k=k)
    box('Building_Main', (6.0, 6.0, 10.0), (11.0, 11.0, -3.0), k)
    libs = [box('Lib_Bench', (1.8, 0.5, 0.8), (-60.0, 0.0, 0.0), k), box('Lib_Lamp', (0.3, 0.3, 4.0), (-60.0, 5.0, 0.0), k),
            box('Lib_Bush', (1.0, 1.0, 1.5), (-60.0, 10.0, 0.0), k)]
    return g, libs, k


def _placed():
    return [o for o in rt.objects if rt.getUserProp(o, 'AGR_SCHEDULE_ROW') is not None]


def schedule():
    out = {}
    for units in ('meters', 'centimeters'):
        g, libs, k = _schedule_scene(units)
        user_action('User_Before')
        p = press('place.schedule', None, {'rows': ROWS})
        s = p['plan']['summary']
        assert (s['placed'], s['no_library_model'], s['no_place']) == (7, 1, 2), s
        status = {r['id']: r['status'] for r in p['plan']['rows']}
        assert status['P08'] == 'no_library_model' and status['P09'] == 'outside_ground' and \
            status['P10'] == 'blocked_by_obstacle', status
        r = apply('place.schedule', p)
        assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
        placed = _placed()
        assert sorted(str(o.name) for o in placed) == sorted('{}_{}'.format(x['model'], x['id']) for x in ROWS[:7])
        worst = {'pivot_mm': 0.0, 'rot_deg': 0.0, 'sink_mm': 0.0}
        for o in placed:
            row = next(x for x in ROWS if x['id'] == str(rt.getUserProp(o, 'AGR_SCHEDULE_ROW')))
            lib = rt.getNodeByName(row['model'])
            assert rt.areNodesInstances(o, lib) and str(o.layer.name) == 'placement_instances'
            m = mpu()
            worst['pivot_mm'] = max(worst['pivot_mm'], 1000 * math.hypot(float(o.pos.x) * m - row['x'],
                                                                         float(o.pos.y) * m - row['y']))
            heading = math.degrees(math.atan2(float(o.transform.row1.y), float(o.transform.row1.x)))
            worst['rot_deg'] = max(worst['rot_deg'], abs((heading - row['rotation_deg'] + 180) % 360 - 180))
            worst['sink_mm'] = max(worst['sink_mm'], 1000 * abs(gap_of(o, [g]) + 0.10))
        assert worst['pivot_mm'] <= 1 and worst['rot_deg'] <= 0.01 and worst['sink_mm'] <= 10, worst
        assert rt.getNodeByName('Lib_Bench_P09') is None and rt.getNodeByName('Lib_Bench_P10') is None
        count = len(rt.objects)
        again = press('place.schedule', None, {'rows': ROWS})
        assert again['plan']['summary']['placed'] == 0 and again['plan']['summary']['already_placed'] == 7
        apply('place.schedule', again)
        dup = len(names()) - len(set(names()))
        assert len(rt.objects) == count and dup == 0
        undo()
        empty_record = len(_placed()) == 7  # the empty second run left its own (empty) record
        if empty_record:
            undo()
        assert not _placed() and user_kept('schedule')  # one record removed all 7
        out[units] = dict(worst, summary=s, rerun_empty_undo_record=empty_record)
    return out


# ---- place.flora_repair -------------------------------------------------------------------------------
FBX = [('Animation', False), ('EmbedTextures', False), ('ASCII', False), ('FileVersion', 'FBX201400'),
       ('UpAxis', 'Z'), ('Cameras', False), ('Lights', False), ('SmoothingGroups', True)]


def _card(name, pos, mat):
    c = rt.Plane(name=name, width=1.0, length=2.0, widthsegs=2, lengthsegs=2, mapcoords=True)
    rt.convertToMesh(c)
    c.pos = rt.Point3(*pos)
    c.material = mat
    return c


def _flora_scene_raw():
    reset()
    mats = []
    for i in range(3):
        m = rt.Standardmaterial(name='M_Flora_{}'.format(i))
        mats.append(m)
    ident = _card('F_identity', (0, 0, 0), mats[0])
    neg = _card('F_negative', (3, 0, 0), mats[0])
    neg.scale = rt.Point3(-1, 1, 1)
    rot = _card('F_rotated', (6, 0, 0), mats[1])
    rt.rotate(rot, rt.EulerAngles(90, 0, 37))
    quads = rt.Plane(name='F_quads', width=1.0, length=2.0, widthsegs=2, lengthsegs=2, mapcoords=True)
    rt.convertToPoly(quads)
    quads.pos = rt.Point3(9, 0, 0)
    quads.material = mats[1]
    inst = rt.instance(rot)
    inst.name = 'F_instance'
    inst.pos = rt.Point3(12, 0, 0)
    nouv = rt.Plane(name='F_no_uv', width=1.0, length=1.0, mapcoords=False)
    rt.convertToMesh(nouv)
    rt.execute('meshop.setMapSupport $F_no_uv 1 false')
    nouv.pos = rt.Point3(15, 0, 0)
    bush = rt.GeoSphere(name='F_bush', radius=0.6, segs=4, mapcoords=True)
    bush.pos = rt.Point3(18, 0, 0)
    rt.addModifier(bush, rt.Noisemodifier(strength=rt.Point3(0.1, 0.1, 0.1), scale=0.5))
    bush.material = mats[2]
    parent = rt.Dummy(name='F_parent', pos=rt.Point3(21, 0, 0))
    rt.rotate(parent, rt.EulerAngles(0, 0, 30))
    shear = _card('F_shear', (21.5, 1.0, 0.0), mats[2])
    rt.rotate(shear, rt.EulerAngles(0, 0, 25))
    shear.parent = parent
    parent.scale = rt.Point3(1, 3, 1)  # scaled AFTER the link: the child inherits it at -5 degrees -> world shear
    return [ident, neg, rot, quads, inst, nouv, bush, shear]


def _readback(node, path):
    """Export one node to a NEW FBX and import it back into this scene; the imported nodes are deleted after."""
    rt.pluginManager.loadClass(rt.FbxExporter)
    rt.pluginManager.loadClass(rt.FbxImporter)
    for key, value in FBX:
        rt.FBXExporterSetParam(key, value)
    rt.select(node)
    assert rt.exportFile(str(path), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP), path
    before = {int(rt.getHandleByAnim(o)) for o in rt.objects}
    rt.FBXImporterSetParam('Mode', rt.Name('create'))
    assert rt.importFile(str(path), rt.Name('noPrompt'), using=rt.FBXIMP), path
    new = [o for o in rt.objects if int(rt.getHandleByAnim(o)) not in before]
    geo = [o for o in new if rt.superClassOf(o) == rt.GeometryClass]
    assert len(geo) == 1, [str(o.name) for o in new]
    tris = glue.triangles(geo[0], mpu())
    rt.delete(new)
    return tris


def flora():
    out = {}
    emax = agr._load_core('edit_max.py', 'agr_tools_edit_max')
    # pass 1: one undo removes only the copies (before any FBX import touches the undo stack)
    nodes = _flora_scene()
    user_action('User_Before')
    r = apply('place.flora_repair', press('place.flora_repair', nodes))
    made = [rt.getAnimByHandle(x['handle']) for x in r['plan']['copies']]
    assert len(made) == 7 and all(rt.isValidNode(cn) for cn in made)
    undo()
    assert all(not rt.isValidNode(cn) for cn in made), 'one undo removes the copies'
    assert all(rt.isValidNode(n) for n in nodes) and user_kept('flora')
    out['undo'] = 'one record removed {} copies, originals stay'.format(len(made))
    # pass 2: codes, originals, FBX readback
    nodes = _flora_scene()
    before = emax.snapshot(nodes)
    expected = {str(n.name): glue.triangles(n, mpu()) for n in nodes if str(n.name) != 'F_no_uv'}
    p = press('place.flora_repair', nodes)
    c = codes(p)
    assert c['F_identity'] == [] and c['F_negative'] == ['negative_scale'] and c['F_rotated'] == ['rotated'], c
    assert 'ngon' in c['F_quads'] and c['F_no_uv'] == ['no_uv'] and 'shear' in c['F_shear'], c
    assert any(s['item'] == 'F_no_uv' for s in p['plan']['skipped'])
    assert p['plan']['fbx_would_differ'] == ['F_shear']
    out['codes'] = c
    r = apply('place.flora_repair', p)
    assert r['status'] == 'pass', [o for o in r['objects'] if o['findings']]
    assert emax.snapshot(nodes) == before and r['plan']['originals_unchanged']
    copies = {x['source']: rt.getAnimByHandle(x['handle']) for x in r['plan']['copies']}
    assert all(str(cn.layer.name) == 'AGR_flora_repair' for cn in copies.values())
    fbx_dir = OUT / 'fbx'
    fbx_dir.mkdir()
    readback = {}
    for src, cn in copies.items():
        got = core.compare_meshes(expected[src], _readback(cn, fbx_dir / (src + '_copy.fbx')))
        readback[src] = got['equal']
    assert all(readback.values()), readback
    out['readback_copies_equal'] = readback
    # the lab L08 baseline (source FBX of the sheared card differs) is a measurement here, not a gate of the button
    shear_src = rt.getNodeByName('F_shear')
    alone = core.compare_meshes(expected['F_shear'], _readback(shear_src, fbx_dir / 'F_shear_original.fbx'))
    out['shear_original_fbx_equal_child_only'] = alone['equal']
    out['shear_original_fbx_equal_with_parent'] = _readback_hierarchy(shear_src, expected['F_shear'],
                                                                      fbx_dir / 'F_shear_with_parent.fbx')
    return out


def _readback_hierarchy(child, expected, path):
    rt.select([child.parent, child])
    for key, value in FBX:
        rt.FBXExporterSetParam(key, value)
    assert rt.exportFile(str(path), rt.Name('noPrompt'), selectedOnly=True, using=rt.FBXEXP), path
    before = {int(rt.getHandleByAnim(o)) for o in rt.objects}
    rt.FBXImporterSetParam('Mode', rt.Name('create'))
    assert rt.importFile(str(path), rt.Name('noPrompt'), using=rt.FBXIMP), path
    new = [o for o in rt.objects if int(rt.getHandleByAnim(o)) not in before]
    geo = [o for o in new if rt.superClassOf(o) == rt.GeometryClass]
    got = core.compare_meshes(expected, glue.triangles(geo[0], mpu()))['equal'] if len(geo) == 1 else None
    rt.delete(new)
    return got


def _quietly(fn):
    def wrapped(*a, **kw):
        with quiet():
            return fn(*a, **kw)
    return wrapped


_drop_scene = _quietly(_drop_scene_raw)
_replace_scene = _quietly(_replace_scene_raw)
_schedule_scene = _quietly(_schedule_scene_raw)
_flora_scene = _quietly(_flora_scene_raw)

for name, fn in (('drop_to_ground', drop), ('maf_checks', maf), ('replace', replace), ('schedule', schedule),
                 ('flora_repair', flora)):
    check(name, fn)
summary['undo_keeps_user_action_batch'] = UNDO_KEEPS_USER
summary['scene_saved'] = bool(str(rt.maxFileName))
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
print('AGR_979A_SUMMARY ' + json.dumps(summary, ensure_ascii=True, default=str)[:4000])
assert not summary['errors'] and not summary['scene_saved'], sorted(summary['errors'])
