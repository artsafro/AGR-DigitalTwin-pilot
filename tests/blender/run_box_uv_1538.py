"""new-case: #1538 real-Blender probes of tools/blender/box_uv.py on a synthetic panel facade (synthetic data).

Run through dt_ai.core.blender_runner: `-- <report.json> [<render.png>]`. No file is opened or saved; the
scene is the factory-startup scene plus generated objects; the optional render writes only <render.png>.
"""
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/blender'))
import box_uv  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
output = Path(args[0])
render = Path(args[1]) if len(args) > 1 else None
assert bpy.app.version[:2] == (5, 1), bpy.app.version_string
T = 4096
report = {}


def mesh_object(name, verts, faces, uv=None, location=(0, 0, 0), rot_z=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    obj.rotation_euler = (0.0, 0.0, rot_z)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.update()   # matrix_world from location/rotation
    if uv is not None:
        layer = me.uv_layers.new(name='UVMap')
        for i, d in enumerate(layer.uv):
            d.vector = uv(i)
    return obj


def facade(name, wa=(3, 1.5), wb=(2, 1.5), rows=(3, 1.0), cap=0.3, **kw):
    """L facade: wall A (normal -Y) along X, wall B (normal +X) along Y, welded corner column,
    parapet cap strip (normal +Z) on wall A. Returns (object, listed faces, unlisted faces)."""
    verts, faces, index = [], [], {}

    def v(p):
        key = tuple(round(c, 9) for c in p)
        if key not in index:
            index[key] = len(verts)
            verts.append(key)
        return index[key]

    na, pa = wa
    nb, pb = wb
    nr, ph = rows
    xa = na * pa
    for j in range(nr):
        z0, z1 = j * ph, (j + 1) * ph
        for i in range(na):   # wall A at y=0, outward -Y: CCW seen from -Y
            x0, x1 = i * pa, (i + 1) * pa
            faces.append([v((x0, 0, z0)), v((x1, 0, z0)), v((x1, 0, z1)), v((x0, 0, z1))])
        for i in range(nb):   # wall B at x=xa, outward +X
            y0, y1 = i * pb, (i + 1) * pb
            faces.append([v((xa, y0, z0)), v((xa, y1, z0)), v((xa, y1, z1)), v((xa, y0, z1))])
    top = nr * ph
    caps = []
    for i in range(na):
        x0, x1 = i * pa, (i + 1) * pa
        caps.append(len(faces))
        faces.append([v((x0, -cap, top)), v((x1, -cap, top)), v((x1, 0, top)), v((x0, 0, top))])
    obj = mesh_object(name, verts, faces, uv=lambda i: (7.25 + 0.001 * i, 3.5), **kw)
    unlisted = [caps[-1]]
    listed = [f for f in range(len(faces)) if f not in unlisted]
    return obj, listed, unlisted


def scene_objects():
    return list(bpy.context.scene.objects)


def world(obj, p):
    return obj.matrix_world @ obj.data.vertices[p].co


def loop_uvs(obj, faces):
    layer, polys = obj.data.uv_layers.active, obj.data.polygons
    return [tuple(layer.uv[li].vector) for f in faces
            for li in range(polys[f].loop_start, polys[f].loop_start + polys[f].loop_total)]


def measure(obj, faces, uvs=None):
    """Seam jumps across interior edges between coplanar listed faces + per-face texel (px/m)."""
    me = obj.data
    layer = me.uv_layers.active
    listed = set(faces)
    corner = {}
    for f in faces:
        poly = me.polygons[f]
        for k, li in enumerate(range(poly.loop_start, poly.loop_start + poly.loop_total)):
            uv = uvs[f][k] if uvs else tuple(layer.uv[li].vector)
            corner[(f, me.loops[li].vertex_index)] = uv
    edges = {}
    for f in faces:
        vs = list(me.polygons[f].vertices)
        for a, b in zip(vs, vs[1:] + vs[:1]):
            edges.setdefault(frozenset((a, b)), []).append(f)
    normal = {f: (obj.matrix_world.to_3x3() @ me.polygons[f].normal).normalized() for f in faces}
    interior = broken = 0
    worst = 0.0
    for e, fs in edges.items():
        if len(fs) != 2 or not set(fs) <= listed:
            continue
        f, g = fs
        if normal[f].dot(normal[g]) < 1 - 1e-6:
            continue   # corner edge: not between coplanar faces
        interior += 1
        for vert in e:
            du = corner[(f, vert)][0] - corner[(g, vert)][0]
            dv = corner[(f, vert)][1] - corner[(g, vert)][1]
            off = max(abs(du - round(du)), abs(dv - round(dv)))
            worst = max(worst, off)
            if off > 1e-5:
                broken += 1
                break
    texel = []
    for f in faces:
        poly = me.polygons[f]
        pts = [corner[(f, vi)] for vi in poly.vertices]
        a_uv = abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))) / 2
        wpts = [world(obj, vi) for vi in poly.vertices]
        n = (wpts[1] - wpts[0]).cross(wpts[2] - wpts[0]).length / 2 + (wpts[2] - wpts[0]).cross(
            wpts[3] - wpts[0]).length / 2 if len(wpts) == 4 else (wpts[1] - wpts[0]).cross(wpts[2] - wpts[0]).length / 2
        texel.append(math.sqrt(a_uv * T * T / n))
    return {'interior_edges': interior, 'broken_edges': broken, 'worst_offset': round(worst, 9),
            'texel_min': round(min(texel), 3), 'texel_max': round(max(texel), 3)}


def per_tile_snap(obj, faces, plan):
    """Negative witness: the rejected v1 approach - every face snapped into the tile on its own."""
    out = {}
    for f in faces:
        uvs = plan[f]
        umin, vmin = min(u for u, _ in uvs), min(v for _, v in uvs)
        out[f] = [(u - umin + 8 / T, v - vmin + 8 / T) for u, v in uvs]
    return out


def selection_state():
    return sorted((o.name, o.select_get()) for o in bpy.context.scene.objects), \
        getattr(bpy.context.view_layer.objects.active, 'name', None)


# ------------------------------------------------------------------ main fixture
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
target, listed, unlisted = facade('ELV_Main_Trim', location=(100.37, -54.6, 5.3))
glass = mesh_object('ELV_MainGlass', [(0, -1, 0), (1, -1, 0), (1, -1, 1), (0, -1, 1)], [[0, 1, 2, 3]],
                    uv=lambda i: (0.1 * i + 0.05, 0.2))
ucx = mesh_object('UCX_ELV_Main_Trim', [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [[0, 1, 2, 3]])
other = mesh_object('ELV_Ground', [(0, 0, -1), (5, 0, -1), (5, 5, -1), (0, 5, -1)], [[0, 1, 2, 3]])
for o in scene_objects():
    o.select_set(o.name != target.name)       # the target is deliberately NOT selected or active
bpy.context.view_layer.objects.active = glass
sel0 = selection_state()
before = box_uv.uv_fingerprint(scene_objects(), detail=target.name, faces=listed)
res = box_uv.box_project_uv(target, listed, 819.2, 1001)   # 4096 / 819.2 = 5 m box
after = box_uv.uv_fingerprint(scene_objects(), detail=target.name, faces=listed)
m = measure(target, listed)
report['main'] = {'measure': m, 'violations': box_uv.uv_violations(before, after, target.name),
                  'islands': len(res['islands']), 'period_m': res['period_m'],
                  'ucx_layers': len(ucx.data.uv_layers), 'other_layers': len(other.data.uv_layers),
                  'selection_unchanged': selection_state() == sel0,
                  'tiles': sorted({(math.floor(u), math.floor(v)) for u, v in loop_uvs(target, listed)})}
plan, _ = box_uv.plan_box_uv([(f, list(target.data.polygons[f].vertices),
                               [tuple(world(target, v)) for v in target.data.polygons[f].vertices]) for f in listed],
                             819.2, 1001)
report['per_tile_snap'] = measure(target, listed, per_tile_snap(target, listed, plan))

# new layer on a target without UVs; second object keeps no UV layer
bare, bare_faces, _ = facade('ELV_Bare', wa=(2, 1.5), wb=(2, 1.0), location=(0.2, 0.5, 0.1))
bare.data.uv_layers.remove(bare.data.uv_layers[0])
b0 = box_uv.uv_fingerprint(scene_objects(), detail=bare.name, faces=bare_faces)
res_b = box_uv.box_project_uv(bare, bare_faces + [len(bare.data.polygons) - 1], 1024, 1002)
b1 = box_uv.uv_fingerprint(scene_objects(), detail=bare.name, faces=bare_faces)
report['bare'] = {'created': res_b['created_layer'], 'layer': res_b['uv_layer'],
                  'violations': box_uv.uv_violations(b0, b1, bare.name, res_b['created_layer'] and res_b['uv_layer']),
                  'ucx_layers': len(ucx.data.uv_layers), 'other_layers': len(other.data.uv_layers),
                  'measure': measure(bare, list(range(len(bare.data.polygons))))}

# ------------------------------------------------------------------ fail-closed probes: nothing written
shared = mesh_object('ELV_Shared_A', [(0, 0, 0), (1, 0, 0), (1, 0, 1)], [[0, 1, 2]])
twin = bpy.data.objects.new('ELV_Shared_B', shared.data)
bpy.context.scene.collection.objects.link(twin)
cam = bpy.data.objects.new('ELV_Empty', None)
bpy.context.scene.collection.objects.link(cam)
big, big_faces, _ = facade('ELV_Big', wa=(5, 1.5), location=(0.0, 0.0, 0.0))   # 7.5 m wall > 5 m period
nan_obj = mesh_object('ELV_NaN', [(0, 0, 0), (1, 0, 0), (1, 0, float('nan'))], [[0, 1, 2]])
cases = {
    'empty_faces': (target, [], 819.2, 1001), 'duplicate_face': (target, [0, 0], 819.2, 1001),
    'face_out_of_range': (target, [10 ** 6], 819.2, 1001), 'negative_face': (target, [-1], 819.2, 1001),
    'bool_face': (target, [True], 819.2, 1001), 'faces_not_iterable': (target, 5, 819.2, 1001),
    'px_nan': (target, listed, math.nan, 1001), 'px_inf': (target, listed, math.inf, 1001),
    'px_511.99': (target, listed, 511.99, 1001), 'px_1706.01': (target, listed, 1706.01, 1001),
    'px_bool': (target, listed, True, 1001), 'tile_1000': (target, listed, 819.2, 1000),
    'tile_1101': (target, listed, 819.2, 1101), 'tile_float': (target, listed, 819.2, 1001.0),
    'shared_mesh': (shared, [0], 819.2, 1001), 'not_mesh': (cam, [0], 819.2, 1001),
    'overflow': (big, big_faces, 819.2, 1001), 'nan_vertex': (nan_obj, [0], 819.2, 1001),
}
fail = {}
for name, (obj, faces, px, tile) in cases.items():
    f0 = box_uv.uv_fingerprint(scene_objects())
    try:
        box_uv.box_project_uv(obj, faces, px, tile)
        fail[name] = 'NO ERROR'
    except box_uv.BoxUVError as exc:
        fail[name] = 'error' if box_uv.uv_fingerprint(scene_objects()) == f0 else f'error but wrote: {exc}'
    except Exception as exc:   # noqa: BLE001 - any other type is a finding
        fail[name] = f'{type(exc).__name__}: {exc}'
report['fail_closed'] = fail
# #1574: directional texel of a rotated / sloped face below 512 px/m is a BoxUVTexelError, nothing written
rot40 = mesh_object('ELV_Rot40', [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [[0, 1, 2, 3]],
                    location=(0.1, 0.1, 0.1), rot_z=math.radians(40))
c50, s50 = math.cos(math.radians(50)), math.sin(math.radians(50))
slope50 = mesh_object('ELV_Slope50', [(0, 0, 0), (1, 0, 0), (1, c50, s50), (0, c50, s50)], [[0, 1, 2, 3]],
                      location=(0.1, 0.1, 0.1))
for name, obj, px in (('texel_rot40_px600', rot40, 600), ('texel_slope50_px512', slope50, 512)):
    f0 = box_uv.uv_fingerprint(scene_objects())
    try:
        box_uv.box_project_uv(obj, [0], px, 1001)
        fail[name] = 'NO ERROR'
    except box_uv.BoxUVTexelError as exc:
        fail[name] = 'error' if box_uv.uv_fingerprint(scene_objects()) == f0 else f'error but wrote: {exc}'
    except Exception as exc:   # noqa: BLE001 - any other type is a finding
        fail[name] = f'{type(exc).__name__}: {exc}'
for name, px in (('px_512', 512), ('px_1706', 1706)):   # inclusive regulation bounds
    small, sf, _ = facade('ELV_' + name, wa=(1, 1.0), wb=(1, 1.0), rows=(1, 1.0), cap=0.2, location=(0.1, 0.1, 0.1))
    try:
        box_uv.box_project_uv(small, sf, px, 1001)
        fail[name] = 'ok' if measure(small, sf)['broken_edges'] == 0 else 'broken'
    except box_uv.BoxUVError as exc:
        fail[name] = f'error: {exc}'

# ------------------------------------------------------------------ #1600: native float32 storage + world matrix
period_cases = []
for px in (1000, 1706):
    period = T / px
    for offset in (0, 3, 2000, -2000):
        for delta_px in (0, 1):
            xs = [(offset + f) * period + (delta_px / px if f == 1 else 0)
                  for f in (0.1, 1, 1.5)]
            verts = [(x, 0, z) for x in xs for z in (0.1 * period, 0.6 * period)]
            obj = mesh_object('ELV_Period1600', verts, [[0, 2, 3, 1], [2, 4, 5, 3]],
                              uv=lambda i: (7.25, 3.5))
            before_uv = loop_uvs(obj, [0, 1])
            if delta_px:
                try:
                    box_uv.box_project_uv(obj, [0, 1], px, 1012, margin_px=0)
                    raise AssertionError('off-line cut accepted')
                except box_uv.BoxUVOverflow:
                    assert loop_uvs(obj, [0, 1]) == before_uv
            else:
                result = box_uv.box_project_uv(obj, [0, 1], px, 1012, margin_px=0)
                assert len(result['islands']) == 2 and result['period_cut_edges'] == 1
                assert measure(obj, [0, 1])['broken_edges'] == 0
                assert all(1 <= c <= 2 for uv in loop_uvs(obj, [0, 1]) for c in uv)
            period_cases.append({'px': px, 'offset': offset, 'delta_px': delta_px, 'ok': True})
report['period_float32'] = period_cases

translated_cases = []
for offset in (0, 3):
    for rotation in (0, -math.pi / 2):
        for delta_px in (0, 1):
            px = 1706
            period = T / px
            location = (offset + 0.37) * period
            xs = [(offset + f) * period - location + (delta_px / px if f == 1 else 0)
                  for f in (0.1, 1, 1.5)]
            # Inverse of the exact 0/-90 degree rotation, before native float32 storage.
            verts = [((x, 0, z) if rotation == 0 else (0, x, z))
                     for x in xs for z in (0.1 * period, 0.6 * period)]
            obj = mesh_object('ELV_Translated1600', verts, [[0, 2, 3, 1], [2, 4, 5, 3]],
                              uv=lambda i: (7.25, 3.5))
            obj.location.x = location
            obj.rotation_euler.z = rotation
            bpy.context.view_layer.update()
            before_uv = loop_uvs(obj, [0, 1])
            if delta_px:
                try:
                    box_uv.box_project_uv(obj, [0, 1], px, 1012, margin_px=0)
                    raise AssertionError('translated off-line cut accepted')
                except box_uv.BoxUVOverflow:
                    assert loop_uvs(obj, [0, 1]) == before_uv
            else:
                result = box_uv.box_project_uv(obj, [0, 1], px, 1012, margin_px=0)
                assert len(result['islands']) == 2 and result['period_cut_edges'] == 1
                assert all(1 <= c <= 2 for uv in loop_uvs(obj, [0, 1]) for c in uv)
            translated_cases.append({'offset': offset, 'rotation': rotation, 'delta_px': delta_px, 'ok': True})
report['translated_float32'] = translated_cases

# ------------------------------------------------------------------ generated probes
rng = random.Random(1538)
gen = {'n': 0, 'pass': 0, 'overflow_nothing_written': 0, 'fail': []}
for k in range(100):
    px = rng.uniform(512, 1706)
    period = T / px
    pa, h = rng.uniform(0.2, 0.6), rng.uniform(0.2, 0.5)
    na, nb = max(2, int(period * 0.3 / pa)), max(2, int(period * 0.25 / pa))
    obj, fs, _ = facade(f'ELV_Gen{k}', wa=(na, pa), wb=(nb, pa), rows=(max(2, int(0.3 * period / h)), h),
                        cap=rng.uniform(0.1, 0.4),
                        location=(rng.uniform(-500, 500), rng.uniform(-500, 500), rng.uniform(-20, 80)),
                        rot_z=rng.choice([0, 0.5, 1, 1.5]) * math.pi)
    tile = rng.randint(1001, 1100)
    gen['n'] += 1
    g0 = box_uv.uv_fingerprint(scene_objects(), detail=obj.name, faces=fs)
    g_full = box_uv.uv_fingerprint(scene_objects())
    try:
        r = box_uv.box_project_uv(obj, fs, px, tile)
    except box_uv.BoxUVOverflow:
        if box_uv.uv_fingerprint(scene_objects()) == g_full:
            gen['overflow_nothing_written'] += 1
        else:
            gen['fail'].append(k)
        continue
    g1 = box_uv.uv_fingerprint(scene_objects(), detail=obj.name, faces=fs)
    me = measure(obj, fs)
    tu, tv = (tile - 1001) % 10, (tile - 1001) // 10
    inside = all(tu <= u <= tu + 1 and tv <= v <= tv + 1 for u, v in loop_uvs(obj, fs))
    good = (me['broken_edges'] == 0 and me['interior_edges'] > 0 and abs(me['texel_min'] - px) < 0.01
            and abs(me['texel_max'] - px) < 0.01 and inside and not box_uv.uv_violations(g0, g1, obj.name))
    if good:
        gen['pass'] += 1
    else:
        gen['fail'].append({'k': k, 'measure': me, 'inside': inside})
report['generated'] = gen

# ------------------------------------------------------------------ checker render (evidence)
if render:
    for o in list(bpy.data.objects):
        if o.name not in (target.name, glass.name):
            bpy.data.objects.remove(o)
    img = bpy.data.images.new('checker_1538', 1024, 1024)
    img.generated_type = 'COLOR_GRID'
    mat = bpy.data.materials.new('checker')
    mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage')
    node.image = img
    bsdf = mat.node_tree.nodes['Principled BSDF']
    mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
    mat.node_tree.nodes.active = node
    target.data.materials.append(mat)
    scene = bpy.context.scene
    camd = bpy.data.cameras.new('cam')
    camo = bpy.data.objects.new('cam', camd)
    scene.collection.objects.link(camo)
    camo.location = target.location + Vector((9.0, -7.0, 4.0))
    centre = target.matrix_world @ target.data.vertices[0].co
    centre.x += 3.0
    centre.y += 1.0
    centre.z += 1.5
    camo.rotation_euler = (centre - camo.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = camo
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'TEXTURE'
    scene.render.resolution_x, scene.render.resolution_y = 1280, 800
    scene.render.filepath = str(render)
    bpy.ops.render.render(write_still=True)   # evidence only; the library itself uses no operators
    report['render'] = str(render)

output.write_text(json.dumps(report, indent=1), encoding='utf-8')
