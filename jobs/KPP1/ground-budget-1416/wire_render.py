"""KPP1 #1416 [D313]: wireframe renders of the packaged NPM Ground v003 (quads visible) for Artem.

Pattern: n/a | new-case: job script; fresh-process FBX readback of the packaged Ground (+ R1 building as grey
context, no wire), polygon-size statistics, and four Workbench renders with a Wireframe modifier that keeps
quads as quads: top-down overview of the whole site, densest 10 m cell, skirt (perimeter) edge, building edge.

  blender -b --factory-startup -noaudio --python wire_render.py -- <ground.fbx> <building.fbx> <new_out_dir>

The output dir must not exist; everything is written to <out>.partial and renamed at the end.
"""
import bmesh
import bpy
import hashlib
import json
import math
import os
import sys
from collections import Counter

from mathutils import Vector

COLORS = {"Flora": (0.35, 0.62, 0.30, 1), "GroundEl": (0.45, 0.55, 0.75, 1), "Ground": (0.78, 0.75, 0.68, 1)}
WIRE = (0.04, 0.04, 0.04, 1)
BUILDING = (0.92, 0.92, 0.92, 1)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def kind(name):
    for k in ("GroundEl", "Flora", "Ground"):
        if name.endswith(k):
            return k
    raise SystemExit(f"unmapped Ground mesh name: {name}")


def import_fbx(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if len(argv) != 3:
        raise SystemExit("usage: -- <ground.fbx> <building.fbx> <new_out_dir>")
    ground, building, out = (os.path.abspath(a) for a in argv)
    for p in (ground, building):
        if not os.path.isfile(p):
            raise SystemExit(f"input missing: {p}")
    if os.path.exists(out) or os.path.exists(out + ".partial"):
        raise SystemExit(f"output exists: {out}")
    if out in (ground, building) or os.path.dirname(ground) == out or os.path.dirname(building) == out:
        raise SystemExit("output aliases an input")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    gobjs = import_fbx(ground)
    bobjs = import_fbx(building)
    if not gobjs:
        raise SystemExit("no meshes in Ground FBX")
    stats, centers, boundary = {}, [], []
    for o in gobjs:
        k = kind(o.name)
        o.color = COLORS[k]
        mw = o.matrix_world
        sides = Counter(len(p.vertices) for p in o.data.polygons)
        stats[o.name] = {"polygons": len(o.data.polygons), "tris_equiv": sum(len(p.vertices) - 2 for p in o.data.polygons),
                         "by_sides": {str(s): c for s, c in sorted(sides.items())}}
        centers += [(mw @ p.center).xy[:] for p in o.data.polygons]
        if k == "Ground":
            ec = Counter(tuple(sorted(e)) for p in o.data.polygons for e in p.edge_keys)
            bverts = {v for e, c in ec.items() if c == 1 for v in e}
            boundary += [mw @ o.data.vertices[v].co for v in bverts]
    for o in bobjs:
        o.color = BUILDING
    pts = [o.matrix_world @ Vector(c) for o in gobjs for c in o.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    mid = (lo + hi) / 2
    # densest 10 m cell
    cells = Counter((math.floor(x / 10), math.floor(y / 10)) for x, y in centers)
    (cx, cy), dense_n = cells.most_common(1)[0]
    dense = Vector(((cx + 0.5) * 10, (cy + 0.5) * 10, 0))
    zs = [o.matrix_world @ v.co for o in gobjs for v in o.data.vertices if abs((o.matrix_world @ v.co).x - dense.x) < 6 and abs((o.matrix_world @ v.co).y - dense.y) < 6]
    dense.z = sum(p.z for p in zs) / len(zs)
    # skirt edge: boundary vertex closest to the middle of the min-Y side
    if not boundary:
        raise SystemExit("SM_Kpp_1_Ground has no boundary edges (skirt edge not found)")
    target = Vector((mid.x, lo.y, 0))
    skirt = min(boundary, key=lambda p: (p.xy - target.xy).length)
    # building edge
    if bobjs:
        bp = [o.matrix_world @ Vector(c) for o in bobjs for c in o.bound_box]
        blo = Vector([min(p[i] for p in bp) for i in range(3)])
        bhi = Vector([max(p[i] for p in bp) for i in range(3)])
        bld = Vector((bhi.x, blo.y, blo.z))
    else:
        raise SystemExit("no meshes in building FBX")

    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "OBJECT"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
    sc.view_settings.view_transform = "Standard"
    # Quad review view (display only, like the 3ds Max QUAD review copy [D270]): the wire copies get
    # their own mesh with coplanar triangle pairs joined to quads; the packaged FBX stays triangulated.
    wires, quad_view = [], {}
    for o in gobjs:
        w = o.copy()
        w.data = o.data.copy()
        bm = bmesh.new()
        bm.from_mesh(w.data)
        bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(40),
                                 angle_shape_threshold=math.radians(40))
        quad_view[o.name] = {str(s): c for s, c in sorted(Counter(len(f.verts) for f in bm.faces).items())}
        bm.to_mesh(w.data)
        bm.free()
        sc.collection.objects.link(w)
        w.color = WIRE
        m = w.modifiers.new("wire", "WIREFRAME")
        m.use_replace = True
        m.use_even_offset = False
        m.offset = 1.0
        wires.append((w, m))
    cam = bpy.data.objects.new("CamWire", bpy.data.cameras.new("CamWire"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    span = max(hi.x - lo.x, hi.y - lo.y)
    shots = {
        "01_overview_top": {"loc": (mid.x, mid.y, hi.z + 500), "tgt": (mid.x, mid.y, mid.z), "ortho": span * 0.8, "wire": 0.12},
        "02_densest_cell": {"loc": (dense.x - 14, dense.y - 14, dense.z + 14), "tgt": tuple(dense), "wire": 0.02},
        "03_skirt_edge": {"loc": (skirt.x + 10, skirt.y - 18, skirt.z + 7), "tgt": (skirt.x, skirt.y, skirt.z - 1), "wire": 0.015},
        "04_building_edge": {"loc": (bld.x + 25, bld.y - 25, bld.z + 18), "tgt": (bld.x, bld.y, bld.z), "wire": 0.015},
    }
    os.makedirs(out + ".partial")
    for name, s in shots.items():
        cam.location = s["loc"]
        cam.rotation_euler = (Vector(s["tgt"]) - Vector(s["loc"])).to_track_quat("-Z", "Y").to_euler()
        if "ortho" in s:
            cam.data.type, cam.data.ortho_scale = "ORTHO", s["ortho"] * 4 / 3
            cam.data.clip_end = 2000
        else:
            cam.data.type, cam.data.lens = "PERSP", 30
            cam.data.clip_start, cam.data.clip_end = 0.05, 2000
        for _, m in wires:
            m.thickness = s["wire"]
        sc.render.filepath = os.path.join(out + ".partial", f"{name}.png")
        bpy.ops.render.render(write_still=True)
        s["loc"], s["tgt"] = [round(v, 3) for v in s["loc"]], [round(v, 3) for v in s["tgt"]]
    report = {"ground_fbx": ground, "ground_sha256": sha(ground), "building_fbx": building, "building_sha256": sha(building),
              "meshes": stats, "quad_review_view_by_sides": quad_view, "tris_equiv_total": sum(v["tris_equiv"] for v in stats.values()),
              "bbox": [[round(v, 3) for v in lo], [round(v, 3) for v in hi]],
              "densest_cell_10m": {"center": [round(dense.x, 2), round(dense.y, 2)], "polygons": dense_n},
              "skirt_point": [round(v, 3) for v in skirt], "building_corner": [round(v, 3) for v in bld],
              "cameras": shots, "renderer": f"Blender {bpy.app.version_string} Workbench + Wireframe modifier (quads kept)"}
    with open(os.path.join(out + ".partial", "wire-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    os.rename(out + ".partial", out)
    print("WIRE_OK", json.dumps(quad_view), report["tris_equiv_total"])


main()
