"""Form check v1 - Blender side (background, read-only import, never saves the scene).

mode `extract`: same algorithm as the frozen t_563a40f7 `extract.py` - boundary loops (opening back rims) and
horizontal sections; adds a label z map (63B: label = real + 8.82), an optional object-name filter and an offset.
mode `render`: neutral judge panels in the #41 look - untextured grey (0.8), studio light, cavity, white background,
orthographic; the scene is cropped by bisecting at the six crop-box planes (no caps) or framed on its bbox.

usage: blender -b --factory-startup --python blender_scene.py -- extract <in.fbx> <out.json> <label=real,...> [name_regex] [dx,dy,dz]
       blender -b --factory-startup --python blender_scene.py -- render <in.fbx> <out_dir> <spec.json>
render spec: {"crop": [x0, y0, z0, x1, y1, z1] | "bbox", "name_re": "..." | null, "x_offset": [dx, dy, dz] | null,
              "panels": [{"name": "V1", "dir": [dx, dy, dz]}, ...]}   (dir = view direction, camera -> scene)

new-case: tools/qa/form_check/blender_scene.py - form check v1 Blender readback and judge renders
"""
import json
import math
import re
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector


def extract(argv):
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


def render(argv):
    fbx, out_dir, spec = argv[0], argv[1], json.load(open(argv[2], encoding="utf-8"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    name_re = re.compile(spec["name_re"]) if spec.get("name_re") else None
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH" and (name_re is None or name_re.search(o.name))]
    obj_names = [o.name for o in objs]
    off = Vector(spec.get("x_offset") or (0, 0, 0))
    bm = bmesh.new()
    for o in objs:
        tmp = bmesh.new()
        tmp.from_mesh(o.data)
        tmp.transform(o.matrix_world)
        tmp.transform(Matrix.Translation(off))
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
    for o in list(bpy.context.scene.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    if spec["crop"] == "bbox":
        vs = [v.co for v in bm.verts]
        x0, y0, z0 = (min(c[i] for c in vs) for i in range(3))
        x1, y1, z1 = (max(c[i] for c in vs) for i in range(3))
    else:
        x0, y0, z0, x1, y1, z1 = spec["crop"]
        for co, no in (((x0, 0, 0), (-1, 0, 0)), ((x1, 0, 0), (1, 0, 0)), ((0, y0, 0), (0, -1, 0)),
                       ((0, y1, 0), (0, 1, 0)), ((0, 0, z0), (0, 0, -1)), ((0, 0, z1), (0, 0, 1))):
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no,
                                   clear_outer=True)
    me = bpy.data.meshes.new("FormCheckCrop")
    bm.to_mesh(me)
    nfaces = len(bm.faces)
    bm.free()
    ob = bpy.data.objects.new("FormCheckCrop", me)
    bpy.context.scene.collection.objects.link(ob)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type, sh.single_color = "STUDIO", "SINGLE", (0.8, 0.8, 0.8)
    sh.show_cavity, sh.cavity_type = True, "BOTH"
    sh.background_type = "VIEWPORT"
    sh.background_color = (1.0, 1.0, 1.0)
    sc.render.film_transparent = False
    sc.render.resolution_x, sc.render.resolution_y = 1200, 700
    cam = bpy.data.objects.new("FormCheckCam", bpy.data.cameras.new("FormCheckCam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    centre = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    corners = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    diag = (Vector((x1, y1, z1)) - Vector((x0, y0, z0))).length
    asp = sc.render.resolution_y / sc.render.resolution_x
    rows = {}
    for p in spec["panels"]:
        d = Vector(p["dir"]).normalized()
        cam.location = centre - d * (diag + 5)
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.data.clip_start, cam.data.clip_end = 0.01, 2 * diag + 20
        bpy.context.view_layer.update()
        inv = cam.matrix_world.inverted()
        loc = [inv @ c for c in corners]
        span_x = max(v.x for v in loc) - min(v.x for v in loc)
        span_y = max(v.y for v in loc) - min(v.y for v in loc)
        cam.data.ortho_scale = max(span_x, span_y / asp) * 1.05
        sc.render.filepath = f"{out_dir}/{p['name']}.png"
        bpy.ops.render.render(write_still=True)
        rows[p["name"]] = {"dir": list(d), "ortho_scale": cam.data.ortho_scale}
    json.dump({"fbx": fbx, "objects": obj_names, "faces_after_crop": nfaces, "panels": rows},
              open(f"{out_dir}/render.json", "w"), indent=1)
    print("FORMCHECK_RENDER", nfaces, list(rows))


if __name__ == "__main__":
    _argv = sys.argv[sys.argv.index("--") + 1:]
    {"extract": extract, "render": render}[_argv[0]](_argv[1:])
