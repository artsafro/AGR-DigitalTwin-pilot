"""Import one FBX in a fresh factory-startup Blender and dump world-space mesh geometry (#386; copy of experiments/hyp-281/readback.py).

    blender --background --factory-startup --disable-autoexec --python-exit-code 1 \
        --python experiments/hyp-386/readback.py -- <in.fbx> <out.json>

Raw float32 mesh coordinates and matrix_world are read as Python floats; the world transform is
applied in double precision here (mathutils works in float32 and would add its own rounding).
"""
import json
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compatibility import paths, inventory

fbx, out = (Path(a).resolve() for a in sys.argv[sys.argv.index("--") + 1:])
paths(fbx, out)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
objs = []
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        objs.append({"name": ob.name, "type": ob.type})
        continue
    m = [[float(ob.matrix_world[r][c]) for c in range(4)] for r in range(4)]
    me = ob.data
    raw = [tuple(float(c) for c in v.co) for v in me.vertices]
    world = [tuple(m[r][0] * x + m[r][1] * y + m[r][2] * z + m[r][3] for r in range(3)) for x, y, z in raw]
    me.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in me.loop_triangles]
    objs.append({"name": ob.name, "type": "MESH", "matrix_world": m, "raw": raw, "world": world,
                 "tris": tris, "polygons": len(me.polygons)})
inventory(objs, {f'P{k}_{s}' for k in range(3) for s in 'AB'})
if any(o['type'] != 'MESH' for o in objs):
    raise ValueError('unsupported non-mesh objects')
out.write_text(json.dumps({"fbx": str(fbx), "blender": bpy.app.version_string, "objects": objs}, allow_nan=False), encoding="utf-8")
print(f"READBACK {len(objs)} objects -> {out.name}")
