"""Hook `after` stage `body` (#1619 polygon stage 2, Blender 5.1): assemble, export and read back stage 2.

Pattern: n/a | new-case: stage-2 scene of the training polygon (accepted body appended unchanged + inset elements).

blender -b --factory-startup --python stage2_blend.py -- STAGE2.json BODY.blend OUT_DIR NAME_VERSION [--dump BODY.npz]

* the accepted body is APPENDED from its review .blend (no edit, no modifier, no re-export of its own file) into
  the collection `Body_Stage1`; every stage-2 element of STAGE2.json (stage2_plan.py) becomes its own object in
  its own collection (`Stage2_Windows`, `Stage2_Glass`, `Stage2_Capsules`) - never joined into one mesh (D336);
* writes OUT_DIR/NAME_VERSION.blend and .fbx (FBX settings of module_build.py), then reads the FBX back in a fresh
  scene: per collection faces / quads / triangles / thin triangles (min angle < 5 deg), objects, and the body
  vertices against BODY.npz (dump of the accepted FBX) -> OUT_DIR/NAME_VERSION.readback.json.
Refuses an OUT_DIR that holds BODY.blend.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

argv = sys.argv[sys.argv.index('--') + 1:]
plan_path, body_blend, out, name = argv[:4]
dump = argv[argv.index('--dump') + 1] if '--dump' in argv else None
if os.path.abspath(out) == os.path.abspath(os.path.dirname(body_blend)):
    sys.exit('OUT_DIR must not hold the accepted body')
os.makedirs(out, exist_ok=True)
COLOURS = {'WIN_Frame': (0.85, 0.85, 0.83, 1), 'WIN_Frame_Back': (0.6, 0.6, 0.6, 1),
           'WIN_Infill': (0.3, 0.3, 0.32, 1), 'WIN_Glass': (0.35, 0.55, 0.75, 0.35),
           'LIB_Interior_Stub': (0.45, 0.3, 0.2, 1)}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1.0


def coll(n):
    c = bpy.data.collections.get(n) or bpy.data.collections.new(n)
    if c.name not in scene.collection.children:
        scene.collection.children.link(c)
    return c


with bpy.data.libraries.load(body_blend, link=False) as (src, dst):
    dst.objects = [n for n in src.objects]
body_c = coll('Body_Stage1')
body_objs = []
for ob in dst.objects:
    if ob is not None and ob.type == 'MESH':
        body_c.objects.link(ob)
        body_objs.append(ob.name)

plan = json.load(open(plan_path, encoding='utf-8'))
mats = {}
for el in plan['elements']:
    me = bpy.data.meshes.new(el['name'])
    me.from_pydata(el['verts'], [], el['faces'])
    me.validate(clean_customdata=False)
    for m in dict.fromkeys(el['mats']):
        if m not in mats:
            mats[m] = bpy.data.materials.new(m)
            mats[m].diffuse_color = COLOURS.get(m, (0.5, 0.5, 0.5, 1))
        me.materials.append(mats[m])
    order = list(dict.fromkeys(el['mats']))
    for p, m in zip(me.polygons, el['mats']):
        p.material_index = order.index(m)
    ob = bpy.data.objects.new(el['name'], me)
    coll(el['collection']).objects.link(ob)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, name + '.blend'))
fbx = os.path.join(out, name + '.fbx')
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=False, mesh_smooth_type='FACE', path_mode='COPY',
                         embed_textures=False)

# ---- read back -------------------------------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)


def group(n):
    if n in body_objs:
        return 'Body_Stage1'
    if n.startswith('CAPSULE_'):
        return 'Stage2_Capsules'
    return 'Stage2_Glass' if n.endswith('_Glass') else 'Stage2_Windows'


def min_angle(pts):
    out = 180.0
    for i in range(3):
        a, b, c = pts[i], pts[(i + 1) % 3], pts[(i + 2) % 3]
        u, v = b - a, c - a
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if nu < 1e-12 or nv < 1e-12:
            return 0.0
        out = min(out, math.degrees(math.acos(max(-1.0, min(1.0, float(u @ v) / (nu * nv))))))
    return out


rep = {}
body_v = None
for ob in bpy.context.scene.objects:
    if ob.type != 'MESH':
        continue
    g = group(ob.name)
    r = rep.setdefault(g, {'objects': 0, 'faces': 0, 'quads': 0, 'tris': 0, 'ngons': 0, 'thin_tris': 0})
    r['objects'] += 1
    me = ob.data
    mw = np.array(ob.matrix_world)
    co = np.array([mw @ np.array([*v.co, 1.0]) for v in me.vertices])[:, :3]
    for p in me.polygons:
        n = len(p.vertices)
        r['faces'] += 1
        r['quads' if n == 4 else 'tris' if n == 3 else 'ngons'] += 1
        if n == 3 and min_angle([co[i] for i in p.vertices]) < 5.0:
            r['thin_tris'] += 1
    if g == 'Body_Stage1':
        body_v = co
for r in rep.values():
    r['quad_share'] = round(r['quads'] / r['faces'], 6) if r['faces'] else None
    r['thin_tri_share'] = round(r['thin_tris'] / r['faces'], 6) if r['faces'] else None
res = {'fbx': os.path.basename(fbx), 'collections': rep, 'body_objects': body_objs,
       'elements_expected': len(plan['elements'])}
if dump and body_v is not None:
    ref = np.load(dump)['verts']
    a = body_v[np.lexsort(np.round(body_v, 3).T)]
    b = ref[np.lexsort(np.round(ref, 3).T)]
    dev = float(np.abs(a - b).max()) if a.shape == b.shape else None
    res['body_vs_accepted'] = {'verts': [int(len(body_v)), int(len(ref))], 'max_dev_m': dev,
                               'equal_1e-5': bool(dev is not None and dev <= 1e-5)}
json.dump(res, open(os.path.join(out, name + '.readback.json'), 'w'), indent=1)
print('STAGE2_READBACK', json.dumps(res))
