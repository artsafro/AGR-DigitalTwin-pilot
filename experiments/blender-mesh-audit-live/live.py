"""Live side of the mesh_audit experiment; run inside the open Blender 4.4 via blender_exec.py.

    python C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py --code \
      "ROOT=r'<worktree>';OUT=r'<temp dir>';exec(open(ROOT+'/experiments/blender-mesh-audit-live/live.py').read(),globals())"

For every <OUT>/*__<defect>.json fixture: builds a mesh object (from_pydata, prefix EXP_t72060caa_),
runs (1) mesh_audit core on data extracted exactly like technical_library/mesh_audit/blender.py,
(2) bmesh checks, (3) writes export_faces.py-style faces to <stem>__faces.json. Median of 5 runs.
Removes every object/mesh/collection it created. Results: <OUT>/live.json.
"""
import glob
import json
import os
import statistics
import sys
import time

import bmesh
import bpy

sys.path.insert(0, ROOT + "/technical_library/mesh_audit")  # noqa: F821 (ROOT from caller)
import importlib  # noqa: E402

import core  # noqa: E402

importlib.reload(core)
PFX = "EXP_t72060caa_"


def med(fn, n=5):
    ts = []
    r = None
    for _ in range(n):
        t = time.perf_counter()
        r = fn()
        ts.append((time.perf_counter() - t) * 1000)
    return r, round(statistics.median(ts), 2)


def live_core(obj):  # same extraction as technical_library/mesh_audit/blender.py
    unit = bpy.context.scene.unit_settings.scale_length
    mesh = obj.data
    vertices = [list((obj.matrix_world @ v.co) * unit) for v in mesh.vertices]
    faces = [list(p.vertices) for p in mesh.polygons]
    return core.inspect_mesh(vertices, faces, [list(e.vertices) for e in mesh.edges],
                             [p.material_index for p in mesh.polygons])


def bm_checks(obj, near_m=0.001):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    inconsistent = sum(1 for e in bm.edges if len(e.link_loops) == 2
                       and e.link_loops[0].vert == e.link_loops[1].vert)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    zero = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    near = len(bmesh.ops.find_doubles(bm, verts=bm.verts, dist=near_m)["targetmap"])
    bow = 0
    for f in bm.faces:
        ls = [lp.vert.co for lp in f.loops]
        tn = [(ls[k] - ls[0]).cross(ls[k + 1] - ls[0]) for k in range(1, len(ls) - 1)]
        if any(a.dot(b) < 0 for a in tn for b in tn):
            bow += 1
    bm.free()
    return {"inconsistent_edges": inconsistent, "non_manifold_edges": non_manifold,
            "boundary_edges": boundary, "zero_area_faces": zero, "loose_verts": loose,
            "near_dup_verts_1mm": near, "bowtie_faces": bow}


def export_faces(obj):  # same as tools/blender/export_faces.py
    world = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return [{"object": obj.name, "index": p.index, "points": [list(world[i]) for i in p.vertices]}
            for p in obj.data.polygons]


before = len(bpy.data.objects)
col = bpy.data.collections.new(PFX + "col")
bpy.context.scene.collection.children.link(col)
rows = {}
try:
    for path in sorted(glob.glob(os.path.join(OUT, "bench-*__*.json"))):  # noqa: F821
        stem = os.path.basename(path)[:-5]
        if stem.endswith("__faces"):
            continue
        fx = json.load(open(path, encoding="utf-8"))
        t = time.perf_counter()
        me = bpy.data.meshes.new(PFX + stem)
        me.from_pydata([tuple(x) for x in fx["vertices"]], [], [tuple(p) for p in fx["polygons"]])
        me.update()
        obj = bpy.data.objects.new(PFX + stem, me)
        col.objects.link(obj)
        build_ms = round((time.perf_counter() - t) * 1000, 2)
        lc, t_lc = med(lambda: live_core(obj))
        bc, t_bc = med(lambda: bm_checks(obj))
        faces, t_ex = med(lambda: export_faces(obj))
        with open(os.path.join(OUT, stem + "__faces.json"), "w", encoding="utf-8") as fh:  # noqa: F821
            json.dump(faces, fh)
        rows[stem] = {"live_core": lc, "live_core_ms": t_lc, "bmesh": bc, "bmesh_ms": t_bc,
                      "export_ms": t_ex, "build_ms": build_ms,
                      "mesh_v": len(me.vertices), "mesh_e": len(me.edges), "mesh_f": len(me.polygons)}
finally:
    for o in list(col.objects):
        m = o.data
        bpy.data.objects.remove(o)
        bpy.data.meshes.remove(m)
    bpy.data.collections.remove(col)
with open(os.path.join(OUT, "live.json"), "w", encoding="utf-8") as fh:  # noqa: F821
    json.dump({"blender": bpy.app.version_string, "rows": rows}, fh, indent=1)
print(json.dumps({"rows": len(rows), "objects_before": before, "objects_after": len(bpy.data.objects),
                  "leftover": [m.name for m in bpy.data.meshes if m.name.startswith(PFX)]}))
