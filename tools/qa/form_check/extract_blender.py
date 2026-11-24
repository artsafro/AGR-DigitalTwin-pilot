"""Form check v1 - read-only scene readback (Blender, background). Same algorithm as the frozen t_563a40f7
`extract.py`: boundary loops (opening back rims) and horizontal sections; adds a label map for fragments whose
key uses label heights (63B: label = real + 8.82) and an optional object-name filter.

usage: blender -b --factory-startup --python extract_blender.py -- <in.fbx> <out.json> <label=real,...> [name_regex] [dx,dy,dz]
Never saves the scene; the FBX is only imported.
"""
import json
import math
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

argv = sys.argv[sys.argv.index("--") + 1:]
fbx, out_path = argv[0], argv[1]
zmap = [(kv.split("=")[0], float(kv.split("=")[1])) for kv in argv[2].split(",")]
name_re = re.compile(argv[3]) if len(argv) > 3 and argv[3] else None
offset = Vector([float(v) for v in argv[4].split(",")]) if len(argv) > 4 and argv[4] else Vector((0, 0, 0))
shift = zmap[0][1] - float(zmap[0][0])  # real - label
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
objs = [x for x in bpy.context.scene.objects if x.type == "MESH" and (name_re is None or name_re.search(x.name))]
bm = bmesh.new()
for o in objs:
    tmp = bmesh.new()
    tmp.from_mesh(o.data)
    tmp.transform(Matrix.Translation(offset) @ o.matrix_world)
    me = bpy.data.meshes.new("tmp")
    tmp.to_mesh(me)
    tmp.free()
    bm.from_mesh(me)
object_list = [{"name": o.name, "faces": len(o.data.polygons), "materials": [m.name for m in o.data.materials if m]}
               for o in objs]
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
adj = {}
for e in bm.edges:
    if e.is_boundary:
        a, b = e.verts
        adj.setdefault(a.index, []).append(b.index)
        adj.setdefault(b.index, []).append(a.index)
seen, loops = set(), []
for s in adj:
    if s in seen:
        continue
    comp, stack = [], [s]
    while stack:
        v = stack.pop()
        if v in seen:
            continue
        seen.add(v)
        comp.append(v)
        stack += adj[v]
    pts = [bm.verts[i].co.copy() for i in comp]
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    cx, cy = sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)
    sxx = sum((p.x - cx) ** 2 for p in pts)
    syy = sum((p.y - cy) ** 2 for p in pts)
    sxy = sum((p.x - cx) * (p.y - cy) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    d = Vector((math.cos(ang), math.sin(ang), 0))
    proj = [(p - Vector((cx, cy, 0))).dot(d) for p in pts]
    loops.append({"n": len(comp), "c": [round(cx, 4), round(cy, 4)], "dir": [round(d.x, 4), round(d.y, 4)],
                  "w": round(max(proj) - min(proj), 4), "z": [round(zmin - shift, 4), round(zmax - shift, 4)]})
secs = {}
for label, z in zmap:
    b2 = bm.copy()
    r = bmesh.ops.bisect_plane(b2, geom=b2.verts[:] + b2.edges[:] + b2.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1))
    secs[label] = [[[round(v.co.x, 4), round(v.co.y, 4)] for v in e.verts]
                   for e in r["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    b2.free()
json.dump({"fbx": fbx, "objects": object_list, "faces": len(bm.faces), "verts": len(bm.verts), "loops": loops,
           "sections": secs, "z_map": dict(zmap)}, open(out_path, "w"), indent=0)
print("FORMCHECK_EXTRACT loops", len(loops), "sections", {k: len(v) for k, v in secs.items()})
