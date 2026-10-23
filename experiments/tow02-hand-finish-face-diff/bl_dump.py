"""Blender headless dump (5.1.2). Usage:
  blender -b --factory-startup --python bl_dump.py -- fbx <in.fbx> <prefix> <out.json>
  blender -b <copy.blend> --python bl_dump.py -- blend <out.json>
fbx: imports the FBX into an empty scene and dumps world-space verts, polygons, loop UVs of objects named <prefix>*.
blend: dumps world face centroids + normals per mesh object (ground-truth part per face).
Prints one line 'DUMP {...}' with counts and timings. Works only on copies; saves nothing.
"""
import bpy, json, sys, time

a = sys.argv[sys.argv.index("--") + 1:]
t0 = time.perf_counter()
if a[0] == "fbx":
    src, prefix, out = a[1], a[2], a[3]
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.import_scene.fbx(filepath=src)
    t_imp = time.perf_counter() - t0
    res = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.name.startswith(prefix):
            continue
        m, me = o.matrix_world, o.data
        uv = me.uv_layers.active.data if me.uv_layers.active else None
        res[o.name] = dict(
            matrix=[list(r) for r in m],
            verts=[list(m @ v.co) for v in me.vertices],
            polys=[list(p.vertices) for p in me.polygons],
            uv=[c for l in uv for c in l.uv] if uv else [])
    json.dump(res, open(out, "w"))
    print("DUMP " + json.dumps(dict(objects=sorted(o.name for o in bpy.data.objects), dumped={k: [len(v["verts"]), len(v["polys"])] for k, v in res.items()},
                                     matrix={k: [[round(x, 4) for x in r] for r in v["matrix"]] for k, v in res.items()},
                                     t_import_s=round(t_imp, 3), t_total_s=round(time.perf_counter() - t0, 3))))
else:
    out = a[1]
    res = {}
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        m = o.matrix_world; n3 = m.to_3x3().inverted().transposed()
        res[o.name] = [[*(m @ p.center), *(n3 @ p.normal).normalized()] for p in o.data.polygons]
    json.dump(res, open(out, "w"))
    print("DUMP " + json.dumps(dict(objects=len(res), faces=sum(len(v) for v in res.values()),
                                     t_total_s=round(time.perf_counter() - t0, 3))))
