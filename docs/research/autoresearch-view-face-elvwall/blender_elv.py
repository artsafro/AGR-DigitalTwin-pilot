"""#167 Blender adapter: ELV FBX -> the UNCHANGED #163 wall stage (blender_walls.py steps 1-3).

blender -b --factory-startup --python blender_elv.py -- <fbx> <outdir> <params.json> <blender_walls_163.py>
Only the import block differs from #163 (Revit FBX instead of the category OBJ): object sets are chosen by frozen
Revit type-name regexes (params), and meshes whose world max z > 30 m are deleted (#145 stray-batten rule). Everything
from '# ---- 1.' on is executed from the pinned #163 blob text.
"""
import json
import math
import re
import sys

import bpy
import mathutils
import numpy as np

src, outdir, pfile, blob = sys.argv[sys.argv.index('--') + 1:][:4]
P = json.load(open(pfile, encoding='utf-8'))
code = open(blob, encoding='utf-8').read()
tail = code[code.index('# ---- 1.'):]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
sc = bpy.context.scene


def world_z(ob):
    co = np.zeros(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get('co', co)
    M = np.array(ob.matrix_world)
    return co.reshape(-1, 3) @ M[2, :3] + M[2, 3]


zmax = {ob.name: world_z(ob).max() for ob in sc.objects if ob.type == 'MESH' and len(ob.data.vertices)}
drop = [sc.objects[n] for n, z in zmax.items() if z > P['max_world_z']]
for ob in drop:
    bpy.data.objects.remove(ob, do_unlink=True)
names = [ob.name for ob in sc.objects if ob.type == 'MESH']
glass = {n for n in names if re.search(P['glass_regex'], n)}
hidden = {n for n in names if re.search(P['hidden_regex'], n)}
facade = {n for n in names if re.search(P['facade_regex'], n)}
for ob in sc.objects:
    if ob.type == 'MESH':
        ob.color = (0, 0, 0, 1) if ob.name in glass else (0.6, 0.6, 0.6, 1)
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
zs = np.concatenate([world_z(ob) for ob in sc.objects if ob.name in facade and len(ob.data.vertices)])
print('ELV_SETS', json.dumps(dict(dropped=len(drop), meshes=len(names), glass=len(glass), hidden=len(hidden),
                                  facade=len(facade), facade_z=[round(min(zs), 3), round(max(zs), 3)])))
exec(compile(tail, 'blender_walls_163_tail', 'exec'))
