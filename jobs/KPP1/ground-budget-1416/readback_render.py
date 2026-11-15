"""KPP1 #1416: fresh-process readback + same-camera before/after renders of the derived Ground copy.

Pattern: n/a | new-case: job script; compares source vs simplified FBX per object (names, materials,
UV layers, world vertex sets of untouched meshes, world bounds) and renders both with identical cameras.

  blender -b --factory-startup -noaudio --python readback_render.py -- <src.fbx> <copy.fbx> <new_render_dir>
"""
import bpy
import hashlib
import json
import math
import os
import sys
from collections import Counter

from mathutils import Vector
from mathutils.bvhtree import BVHTree

FLORA = "SM_77_05_0009005_117_Flora"


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    objs = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    info = {}
    for n, o in objs.items():
        pts = [o.matrix_world @ v.co for v in o.data.vertices]
        key = hashlib.sha256(repr(sorted(tuple(round(c, 5) for c in p) for p in pts)).encode()).hexdigest()
        uv = o.data.uv_layers.active
        info[n] = {
            "tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
            "materials": [m.name for m in o.data.materials if m],
            "uv_layers": [l.name for l in o.data.uv_layers],
            "uv_hash": hashlib.sha256(repr(sorted((round(d.uv.x, 6), round(d.uv.y, 6)) for d in uv.data)).encode()).hexdigest(),
            "world_points_hash": key,
            "bbox": [[round(min(p[i] for p in pts), 4) for i in range(3)], [round(max(p[i] for p in pts), 4) for i in range(3)]],
        }
    return objs, info


def setup_render(cam_loc, target, path):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1200, 900
    cam = bpy.data.objects.get("CamBA") or bpy.data.objects.new("CamBA", bpy.data.cameras.new("CamBA"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.location = cam_loc
    cam.rotation_euler = (Vector(target) - Vector(cam_loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = 35
    cam.data.clip_start = 0.05
    sc.camera = cam
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.color = (0.35, 0.6, 0.3, 1) if "Flora" in o.name else (0.7, 0.7, 0.68, 1)
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    # wire pass: same camera, wireframe modifier on Flora
    fl = bpy.data.objects[FLORA]
    w = fl.modifiers.new("wire", "WIREFRAME")
    w.thickness = 0.01
    w.use_replace = True
    sc.render.filepath = path.replace(".png", "_wire.png")
    bpy.ops.render.render(write_still=True)
    fl.modifiers.remove(w)


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    src, cp, out = a[0], a[1], os.path.realpath(a[2])
    if os.path.exists(out):
        print("RB-FAIL output exists")
        sys.exit(2)
    objs, s_info = load(src)
    fl = objs[FLORA]
    src_pts = [fl.matrix_world @ v.co for v in fl.data.vertices]
    s_pts = {n: [o.matrix_world @ v.co for v in o.data.vertices] for n, o in objs.items() if n != FLORA}
    objs2, c_info = load(cp)
    fl2 = objs2[FLORA]
    bvh = BVHTree.FromPolygons([fl2.matrix_world @ v.co for v in fl2.data.vertices], [p.vertices[:] for p in fl2.data.polygons])
    dev = [(bvh.find_nearest(p)[3], p) for p in src_pts]
    worst = max(dev, key=lambda t: t[0])
    cells = Counter((math.floor(p.x / 10), math.floor(p.y / 10)) for d, p in dev if d > 0.001)
    (cx, cy), cnt = cells.most_common(1)[0]
    cell_pts = [p for d, p in dev if d > 0.001 and (math.floor(p.x / 10), math.floor(p.y / 10)) == (cx, cy)]
    cz = sum(p.z for p in cell_pts) / len(cell_pts)
    cams = {
        "A_max_deviation": (tuple(worst[1] + Vector((4, -4, 3))), tuple(worst[1])),
        "B_densest_cell": ((cx * 10 + 5 + 12, cy * 10 + 5 - 12, cz + 9), (cx * 10 + 5, cy * 10 + 5, cz)),
    }
    checks = {}
    for n in s_info:
        same = {k: s_info[n][k] == c_info.get(n, {}).get(k) for k in ("materials", "uv_layers", "world_points_hash", "uv_hash", "bbox")}
        if n != FLORA:
            a_pts, b_pts = s_pts[n], [objs2[n].matrix_world @ v.co for v in objs2[n].data.vertices]
            same["max_vertex_drift_m"] = max((a - b).length for a, b in zip(a_pts, b_pts)) if len(a_pts) == len(b_pts) else None
            same["within_0.1mm"] = same["max_vertex_drift_m"] is not None and same["max_vertex_drift_m"] <= 1e-4
        checks[n] = same
    os.makedirs(out + ".partial")
    for state, path in (("before", src), ("after", cp)):
        load(path)
        for cname, (loc, tgt) in cams.items():
            setup_render(loc, tgt, os.path.join(out + ".partial", f"{cname}_{state}.png"))
    rep = {"source": s_info, "copy": c_info, "same": checks, "worst_dev_m": worst[0], "worst_point": list(worst[1]),
           "densest_cell_10m": [cx, cy], "densest_cell_moved_verts": cnt, "cameras": {k: [list(v[0]), list(v[1])] for k, v in cams.items()}}
    with open(os.path.join(out + ".partial", "readback.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    os.rename(out + ".partial", out)
    print("RB-OK", json.dumps(checks))


main()
