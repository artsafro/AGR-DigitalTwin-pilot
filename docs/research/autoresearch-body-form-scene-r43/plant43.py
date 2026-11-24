"""Standing #43 plant/export (derived verbatim from rig41.py; size = param, no crop, no render).
Standing #41 evidence-only rig: neutral, facade-registered ortho views of the G22 k2 SE crop.

Usage: blender ... --python rig41.py -- ROOT FBX VARIANT OUTDIR
VARIANT in {A, R, P_fill, P_recess, P_corner}. Planted defects are evaluator controls built in memory on a copy
of the accepted body; nothing is saved as a model. Frame/openings come from the held-out key (evaluator-only).
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

root, src, variant, param, out = sys.argv[sys.argv.index('--') + 1:]
root, src, out = Path(root), Path(src).resolve(), Path(out).resolve()
param = float(param)
KEY = Path('C:/x/t_563a40f7/key/heldout-key-v001.json')
BOX = (536.9, 1036.8, 16.8, 552.5, 1060.5, 19.6)

spec = importlib.util.spec_from_file_location('verifier_views', root / 'tools/blender/verifier_views.py')
views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(views)
views._load(src)

key = json.loads(KEY.read_text(encoding='utf-8'))
ring = {v['ring_index']: Vector((*v['xy'], 0.0)) for v in key['contour_vertices_in_box']}
ops = {o['id']: o for o in key['openings']}
u = (ring[17] - ring[16]).normalized()          # facade frame, 39.186 deg
n = Vector((-u.y, u.x, 0.0))                     # V1 side is -n, V2 side is +n
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and not o.name.startswith('UCX_')]
bpy.ops.object.select_all(action='DESELECT')
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
body = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)


def frame_box(name, origin, a, b, ext_a, ext_b, z0, z1):
    """Box with sides along unit vectors a/b from origin over [ext_a] x [ext_b] x [z0, z1]."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    vs = []
    for z in (z0, z1):
        for sa, sb in ((ext_a[0], ext_b[0]), (ext_a[1], ext_b[0]), (ext_a[1], ext_b[1]), (ext_a[0], ext_b[1])):
            p = origin + a * sa + b * sb
            vs.append(bm.verts.new((p.x, p.y, z)))
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        bm.faces.new([vs[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def boolean(cutter, op):
    m = body.modifiers.new('plant', 'BOOLEAN')
    m.operation, m.solver, m.object = op, 'EXACT', cutter
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter)


plant = {}
if variant == 'P_fill':
    o = ops['6361420']
    a0, a1 = ring[22], (ring[23] - ring[22]).normalized()
    s0, s1 = o['edge_s_m']
    z0, z1 = o['sill_head_z_m']
    d = o['reveal_depth_m']
    # flush fill: from 1 mm behind the facade plane (+n side is outside) to past the reveal back
    boolean(frame_box('fill', a0, a1, n, (s0 - 0.01, s1 + 0.01), (-d - 0.05, -0.001), z0 - 0.01, z1 + 0.01), 'UNION')
    plant = {'opening': '6361420', 'segment': [22, 23], 's': [s0, s1], 'z': [z0, z1]}
elif variant == 'P_recess':
    z0, z1 = ops['4259780']['sill_head_z_m']
    # V1 side: outside is -n; carve 0.13 m deep into the wall from the facade plane of seg 16-17
    boolean(frame_box('recess', ring[16], u, n, (0.6, 2.4), (-0.05, param), z0, z1), 'DIFFERENCE')
    plant = {'segment': [16, 17], 's': [0.6, 2.4], 'z': [z0, z1], 'depth': param}
elif variant == 'P_corner':
    c = ring[21]
    d1, d2 = (ring[20] - c).normalized(), (ring[22] - c).normalized()
    bis = (d1 + d2).normalized()
    # square rotated so its diagonal lies along the corner bisector; cuts 0.8 m legs on both walls
    a, b = (d1 - d2).normalized(), bis
    leg = param
    h = leg * math.sqrt(0.5)
    boolean(frame_box('chamfer', c, a, b, (-h * 1.5, h * 1.5), (-5.0, h), 10.0, 26.0), 'DIFFERENCE')
    plant = {'corner_ring': 21, 'leg_m': leg}
elif variant not in ('A', 'R'):
    raise SystemExit(f'unknown variant {variant}')


assert not out.exists(), out
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.export_scene.fbx(filepath=str(out), use_selection=True)
(out.with_suffix('.plant.json')).write_text(json.dumps({'variant': variant, 'param': param, 'plant': plant,
    'faces': len(body.data.polygons)}), encoding='utf-8')
print('PLANT43', variant, param, len(body.data.polygons))

