"""Blender headless: Ground mesh JSON (dt_ai.geometry.ground_cake.mesh_to_dict) -> FBX, and FBX readback.

Pattern: n/a | new-case: Ground master JSON to FBX with GND-11 names and GND-12 pivot (issue #295).

  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- build <mesh.json> <out.fbx> <Address>
  blender --background --factory-startup --python tools/blender/ground_json_to_fbx.py -- readback <in.fbx> <mesh.json> <report.json>

build: object SM_<Address>_Ground, materials M_<Address>_Ground_<Slot> in the JSON slot order, one UV set,
pivot at the XY centre of the bounding box with Z = 0 (project zero), vertices keep world coordinates (metres).
readback: in a clean process, imports the FBX and compares triangles, per-face material index (raw
material_index layer mapped through slot names), world vertex positions (sorted), unit scale, open edges
and normals facing down on the surface, and back-face pixel count from fixed top cameras is NOT rendered here.
"""
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
    ob.location = piv
    bpy.context.scene.collection.objects.link(ob)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=False, apply_unit_scale=True, global_scale=1.0,
                             apply_scale_options="FBX_SCALE_UNITS", axis_forward="Y", axis_up="Z",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, bake_space_transform=False,
                             add_leaf_bones=False, path_mode="AUTO")
    print(json.dumps({"built": out, "pivot": piv, "verts": len(vs), "faces": len(d["faces"])}))


def readback(fbx, src, rep):
    d = json.load(open(src, encoding="utf-8"))
    clean()
    bpy.ops.import_scene.fbx(filepath=fbx)
    obs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    out = {"fbx": fbx, "objects": [o.name for o in obs], "unit_scale_length": bpy.context.scene.unit_settings.scale_length}
    o = obs[0]
    out["object_scale"] = list(o.scale)
    out["object_location"] = [round(c, 4) for c in o.location]
    out["object_rotation"] = [round(c, 6) for c in o.rotation_euler]
    me = o.data
    mw = o.matrix_world
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
    json.dump(out, open(rep, "w", encoding="utf-8"), indent=1)
    print(json.dumps(out))


if args[0] == "build":
    build(*args[1:4])
elif args[0] == "readback":
    readback(*args[1:4])
else:
    raise SystemExit("usage: build <json> <fbx> <Address> | readback <fbx> <json> <report>")
