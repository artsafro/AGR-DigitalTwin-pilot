"""Blender headless: Ground mesh JSON (dt_ai.geometry.ground_cake.mesh_to_dict) -> FBX, and FBX readback.

Pattern: n/a | new-case: Ground master JSON to FBX with GND-11 names and GND-12 pivot (issue #295).

  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- build <mesh.json> <out.fbx> <Address>
  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- readback <in.fbx> <mesh.json> <report.json> [<tex_px> <lo> <hi>]
  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- render <in.fbx> <out_dir> <report.json>

build: object SM_<Address>_Ground, materials M_<Address>_Ground_<Slot> in the JSON slot order, one UV set,
GND-12 / V013 placement: object origin at FBX zero, the mesh is shifted so that its X/Y bounding-box centre is the
origin (Z unchanged: absolute heights, project zero = 0); the MSK-77 offset of that origin is written by code to
<out.fbx>.placement.json ([D126]) and added back by readback.
readback: in a clean process, imports the FBX and compares triangles, per-face material index (raw
material_index layer mapped through slot names), world vertex positions (sorted), unit scale, open edges
and normals facing down on the surface; with <tex_px lo hi> also the texel density (px per linear metre) of every
surface face (non-Skirt material) measured on the imported mesh.
render: Face Orientation equivalent (Cycles emission: front green, back red via the Backfacing attribute) from fixed
cameras (top orthographic + four 45 degree obliques around the bounding box); counts red pixels per PNG.
"""
import math
import json
import sys

import bpy
import bmesh
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]


def clean():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0


def build(src, out, address):
    d = json.load(open(src, encoding="utf-8"))
    clean()
    vs = d["verts"]
    xs = [v[0] for v in vs]
    ys = [v[1] for v in vs]
    piv = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0)
    me = bpy.data.meshes.new(f"SM_{address}_Ground")
    me.from_pydata([(x - piv[0], y - piv[1], z) for x, y, z in vs], [], d["faces"])
    for s in d["slots"]:
        me.materials.append(bpy.data.materials.new(f"M_{address}_Ground_{s}"))
    me.polygons.foreach_set("material_index", d["mat"])
    uvl = me.uv_layers.new(name="UVMap")
    flat = [c for f in d["uv"] for corner in f for c in corner]
    uvl.data.foreach_set("uv", flat)
    me.update()
    ob = bpy.data.objects.new(f"SM_{address}_Ground", me)
    bpy.context.scene.collection.objects.link(ob)
    json.dump({"fbx": out, "crs": "MSK-77 (SPOZU drawing coordinates, $INSUNITS=6 metres)",
               "origin_msk77_xyz": list(piv), "mesh_xyz = msk77_xyz - origin_msk77_xyz": True,
               "object_location": [0.0, 0.0, 0.0]}, open(out + ".placement.json", "w", encoding="utf-8"), indent=1)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=False, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="Y", axis_up="Z",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, bake_space_transform=False,
                             add_leaf_bones=False, path_mode="AUTO")
    print(json.dumps({"built": out, "pivot": piv, "verts": len(vs), "faces": len(d["faces"])}))


def readback(fbx, src, rep, *tex):
    import os
    d = json.load(open(src, encoding="utf-8"))
    pl = fbx + ".placement.json"
    off = Vector(json.load(open(pl, encoding="utf-8"))["origin_msk77_xyz"]) if os.path.exists(pl) else Vector((0, 0, 0))
    clean()
    bpy.ops.import_scene.fbx(filepath=fbx)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    out = {"fbx": fbx, "objects": [o.name for o in obs], "unit_scale_length": bpy.context.scene.unit_settings.scale_length}
    o = obs[0]
    out["object_scale"] = list(o.scale)
    out["object_location"] = [round(c, 4) for c in o.location]
    out["object_rotation"] = [round(c, 6) for c in o.rotation_euler]
    me = o.data
    from mathutils import Matrix
    mw = Matrix.Translation(off) @ o.matrix_world  # back to MSK-77 for the comparison with the master JSON
    out["placement_offset"] = list(off)
    out["materials"] = [m.name for m in me.materials]
    out["triangles"] = sum(len(p.vertices) - 2 for p in me.polygons)
    out["faces_expected"] = len(d["faces"])
    # raw material index per face -> slot name; compare against the JSON by face centre (FBX may reorder)
    want = {}
    for f, mi in zip(d["faces"], d["mat"]):
        c = tuple(round(sum(d["verts"][i][k] for i in f) / 3, 3) for k in range(3))
        want[c] = d["slots"][mi]
    mism = 0
    found = 0
    down = 0
    lv = d["level"]
    surf_c = {tuple(round(sum(d["verts"][i][k] for i in f) / 3, 3) for k in range(3))
              for f, l in zip(d["faces"], lv) if l >= 0}
    for p in me.polygons:
        c = mw @ p.center
        key = tuple(round(v, 3) for v in c)
        slot = me.materials[p.material_index].name.split("_Ground_", 1)[-1]
        if key in want:
            found += 1
            if want[key] != slot:
                mism += 1
        if key in surf_c and (mw.to_3x3() @ p.normal).z <= 0:
            down += 1
    out["faces_matched_by_centre"] = found
    # by face order (the FBX importer keeps polygon order): raw material_index -> slot name vs JSON
    names = [m.name.split("_Ground_", 1)[-1] for m in me.materials]
    idx = [0] * len(me.polygons)
    me.polygons.foreach_get("material_index", idx)
    out["material_mismatch_by_order"] = (sum(1 for i, mi in zip(idx, d["mat"]) if names[i] != d["slots"][mi])
                                         if len(idx) == len(d["mat"]) else "count differs")
    out["material_mismatch"] = mism
    out["surface_faces_normal_down"] = down
    bm = bmesh.new()
    bm.from_mesh(me)
    out["open_edges"] = sum(1 for e in bm.edges if e.is_boundary)
    out["nonmanifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    zs = [(mw @ v.co).z for v in me.vertices]
    xs = [(mw @ v.co).x for v in me.vertices]
    out["world_bbox"] = {"x": [min(xs), max(xs)], "z": [min(zs), max(zs)]}
    out["uv_layers"] = [u.name for u in me.uv_layers]
    if tex:
        px, lo, hi = float(tex[0]), float(tex[1]), float(tex[2])
        uvl = me.uv_layers.active.data
        dens = []
        straddle, mirrored, tiles = 0, 0, set()
        for p in me.polygons:
            if me.materials[p.material_index].name.endswith("_Skirt"):
                continue
            li = list(p.loop_indices)
            w = [o.matrix_world @ me.vertices[me.loops[i].vertex_index].co for i in li]  # local: float32-safe
            u = [uvl[i].uv for i in li]
            # UDIM containment on the imported UV (float32 tolerance 1e-6) and island winding vs face winding
            tu = math.floor(min(c[0] for c in u) + 1e-6)
            tv = math.floor(min(c[1] for c in u) + 1e-6)
            if max(c[0] for c in u) > tu + 1 + 1e-6 or max(c[1] for c in u) > tv + 1 + 1e-6:
                straddle += 1
            else:
                tiles.add(1001 + tu + 10 * tv)
            sa = sum((u[k][0] - u[0][0]) * (u[k + 1][1] - u[0][1]) - (u[k][1] - u[0][1]) * (u[k + 1][0] - u[0][0])
                     for k in range(1, len(u) - 1))
            fa = sum(((w[k] - w[0]).cross(w[k + 1] - w[0])).dot(p.normal) for k in range(1, len(w) - 1))
            if sa * fa < 0 and abs(sa) > 1e-14:
                mirrored += 1
            a3 = sum((w[k] - w[0]).cross(w[k + 1] - w[0]).length
                     for k in range(1, len(w) - 1)) / 2
            a2 = abs(sum((u[k][0] - u[0][0]) * (u[k + 1][1] - u[0][1]) - (u[k][1] - u[0][1]) * (u[k + 1][0] - u[0][0])
                         for k in range(1, len(u) - 1))) / 2
            if a3 > 1e-12 and a2 > 1e-16:
                dens.append(px * math.sqrt(a2 / a3))
        out["density"] = {"tex_px": px, "band": [lo, hi], "faces": len(dens), "min": min(dens), "max": max(dens),
                          "faces_below": sum(d < lo for d in dens), "faces_above": sum(d > hi for d in dens)}
        out["uv_tiles"] = {"straddling": straddle, "tiles": sorted(tiles), "mirrored_faces": mirrored}
    json.dump(out, open(rep, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out))


def render(fbx, out_dir, rep):
    import os
    clean()
    bpy.ops.import_scene.fbx(filepath=fbx)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    mat = bpy.data.materials.new("FaceOrientation")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mix = nt.nodes.new("ShaderNodeMixRGB")
    mix.inputs[1].default_value = (0, 1, 0, 1)  # front
    mix.inputs[2].default_value = (1, 0, 0, 1)  # back
    em = nt.nodes.new("ShaderNodeEmission")
    outn = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
    nt.links.new(mix.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], outn.inputs[0])
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for o in obs:
        for i in range(len(o.material_slots)):
            o.material_slots[i].material = mat
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            lo = [min(a, b) for a, b in zip(lo, w)]
            hi = [max(a, b) for a, b in zip(hi, w)]
    c = Vector([(a + b) / 2 for a, b in zip(lo, hi)])
    size = max(hi[0] - lo[0], hi[1] - lo[1])
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = 1024
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0, 0, 0)
    cam_d = bpy.data.cameras.new("C")
    cam = bpy.data.objects.new("C", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    views = {"top": (c + Vector((0, 0, size)), True)}
    for k, az in enumerate((45, 135, 225, 315)):
        r = math.radians(az)
        views[f"oblique{az}"] = (c + Vector((math.cos(r) * size, math.sin(r) * size, size)), False)
    os.makedirs(out_dir, exist_ok=True)
    res = {"fbx": fbx, "views": {}}
    for name, (pos, ortho) in views.items():
        cam.location = pos
        cam_d.type = "ORTHO" if ortho else "PERSP"
        cam_d.ortho_scale = size * 1.05
        cam_d.clip_end = size * 10
        d = c - pos
        cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(out_dir, f"face_orientation_{name}.png")
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path)
        px = list(img.pixels)
        red = green = 0
        for i in range(0, len(px), 4):
            r, g = px[i], px[i + 1]
            if r > 0.5 and g < 0.2:
                red += 1
            elif g > 0.5 and r < 0.2:
                green += 1
        res["views"][name] = {"png": path, "back_px": red, "front_px": green, "pixels": len(px) // 4}
        bpy.data.images.remove(img)
    json.dump(res, open(rep, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res))


if args[0] == "build":
    build(*args[1:4])
elif args[0] == "readback":
    readback(*args[1:])
elif args[0] == "render":
    render(*args[1:4])
else:
    raise SystemExit("usage: build <json> <fbx> <Address> | readback <fbx> <json> <report> [px lo hi] | render <fbx> <dir> <report>")
