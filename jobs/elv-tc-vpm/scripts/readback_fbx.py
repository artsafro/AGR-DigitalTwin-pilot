"""elv-tc-vpm: read an exported FBX back in a fresh Blender and report units, transforms, slots, counts, bbox.

blender -b --factory-startup --python readback_fbx.py -- <in.fbx> <out.json> [reference_checks.json]
With reference_checks.json (check_pilot.py output of the source blend) the tris per object are compared.
"""
import bpy, bmesh, sys, os, json, hashlib

argv = sys.argv[sys.argv.index("--") + 1:]
src, out = argv[0], argv[1]
ref = json.load(open(argv[2], encoding="utf-8")) if len(argv) > 2 else None
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.import_scene.fbx(filepath=src)
sc = bpy.context.scene
rep = {"fbx": src, "sha256": hashlib.sha256(open(src, "rb").read()).hexdigest(),
       "fbx_header": open(src, "rb").read(27).decode("latin-1", "replace"),
       "scene_unit": {"system": sc.unit_settings.system, "scale_length": sc.unit_settings.scale_length},
       "objects": {}}
for ob in sc.objects:
    if ob.type != "MESH":
        rep["objects"][ob.name] = {"type": ob.type}
        continue
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    ws = [ob.matrix_world @ v.co for v in me.vertices]
    sizes = {}
    for f in bm.faces:
        sizes[len(f.verts)] = sizes.get(len(f.verts), 0) + 1
    o = {"location": [round(x, 6) for x in ob.location], "rotation_deg": [round(x * 57.29578, 4) for x in ob.rotation_euler],
         "scale": [round(x, 6) for x in ob.scale], "faces": len(me.polygons), "face_sizes": sizes,
         "material_slots": [m.name if m else None for m in me.materials],
         "bbox_world": [[round(min(v[i] for v in ws), 3) for i in range(3)], [round(max(v[i] for v in ws), 3) for i in range(3)]],
         "zero_area_faces": sum(1 for f in bm.faces if f.calc_area() < 1e-8),
         "open_edges": sum(1 for e in bm.edges if len(e.link_faces) == 1),
         "nonmanifold_edges": sum(1 for e in bm.edges if len(e.link_faces) > 2)}
    used = {}
    for p in me.polygons:
        n = me.materials[p.material_index].name if me.materials else "-"
        used[n] = used.get(n, 0) + 1
    o["faces_by_material"] = used
    if ref and ob.name in ref["objects"]:
        o["tris_source_blend"] = ref["objects"][ob.name]["tris"]
        o["tris_match"] = ref["objects"][ob.name]["tris"] == len(me.polygons)
        o["bbox_source_blend"] = ref["objects"][ob.name]["bbox_world"]
    rep["objects"][ob.name] = o
    bm.free()
json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, o in rep["objects"].items():
    print("READBACK", k, {x: o.get(x) for x in ("location", "rotation_deg", "scale", "faces", "face_sizes", "tris_match",
                                                  "bbox_world", "zero_area_faces")})
print("UNITS", rep["scene_unit"], rep["fbx_header"])
