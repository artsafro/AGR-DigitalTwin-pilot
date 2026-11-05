"""elv-tc-vpm: VPM delivery export v004 = delivery_export_v003.py with the image paths of the in-memory master copy
remapped to the tex-v005 set (warm-beige wood) before the thumbnail render; output names v004. Geometry, UCX, pivot,
names: unchanged code. The master .blend (tex-v004 paths) is never saved.

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python delivery_export_v004.py --     <elv_full_v007_tex.blend> <delivery_dir> <tex-v005/textures>
v003 header follows.
elv-tc-vpm: VPM delivery export v003 (= v002 with the customer stem SM_Elevatornaya_Vl_1_A_001, the pivot offset of
v002 kept fixed so the MSK-77 point derived for delivery v003 stays valid, UCX builder input without the interior capsules
P43 and the 22 mm cover strips P44) from the textured master build-v007 (headless Blender 5.1).

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python delivery_export_v003.py -- \
    <elv_full_v006_tex.blend> <delivery_dir>

Works on an in-memory export copy; the master .blend is never saved. Writes (never overwrites):
  <delivery_dir>/package/SM_Elevatornaya_1A.fbx   FBX 7.4 binary, metres, Z up, meshes only, one collection
  <delivery_dir>/thumbnail_256.jpg                GeoJSON imageBase64 source (textured workbench render)
  <delivery_dir>/export_meta_v004.json            pivot offset, bbox, triangle counts, UCX build report
  <delivery_dir>/elv_delivery_v004_export_tri.blend  the triangulated export copy (for inspection)
Steps:
- pivot (reg p.32-33 §9, [D018]): geometry of Main + MainGlass is translated by -(cx, cy, 0) where (cx, cy) is
  the plan centre of their joint bbox; Z stays: z 0 = +-0.000 = abs 167.65 (booklet sheets 10/18/19).
  Every object keeps an identity transform (origin 0,0,0, rotation 0, scale 1).
- UCX (reg p.36-37 §13): shared builder tools/blender/ucx_build.py::build_into_scene on Main + MainGlass with
  the thin / exempt parts removed from the builder input only (R03 lights, R04 railings, ladders, downpipes,
  sign frames <= 5 cm); budget by [D012] from the triangulated model count.
- export copy: custom face attributes and custom properties removed, image nodes removed (no texture paths,
  reg p.30 §4.2), Main/MainGlass triangulated (reg p.29 §3.17), UCX without materials and UV.
"""
import bmesh
import bpy
import importlib.util
import json
import os
import sys
from pathlib import Path

from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("ucx_build_driver", ROOT / "tools/blender/ucx_build.py")
ucxd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ucxd)

ADDRESS = "Elevatornaya_Vl_1_A_001"
STEM = f"SM_{ADDRESS}"
UCX_EXCLUDE = {  # builder input only; the parts stay in the delivered Main
    "P11_SignFrames": "R04 thin frames 10x10 mm, 20 mm off the facade",
    "P34_Railings": "R04 railings <= 5 cm",
    "P38_FireLadders": "R04 rod ladders <= 5 cm",
    "P39_Downpipes": "R04 thin pipes",
    "P40_Arktos": "R03 lighting fixtures",
    "P42_Lights": "R03 lighting fixtures (housings + glow faces)",
    "P43_InteriorCapsules": "interior (behind glass, not reachable; inside the building hull)",
    "P44_CoverStrips": "R04 thin strips 22 mm, 6 mm off the facade (covered by the facade pieces)",
}

src, out_dir, tex_dir = sys.argv[sys.argv.index("--") + 1:][:3]
out_dir = Path(out_dir)
pkg = out_dir / "package"
fbx_path = pkg / f"{STEM}.fbx"
thumb = out_dir / "thumbnail_256.jpg"
meta_path = out_dir / "export_meta_v004.json"
blend_out = out_dir / "elv_delivery_v004_export_tri.blend"
for p in (fbx_path, thumb, meta_path, blend_out):
    if p.exists():
        raise SystemExit(f"output exists, refusing to overwrite: {p}")
pkg.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=src)
# v004: point the UDIM image sets of the in-memory copy at the new texture set (thumbnail only; exported FBX has no paths)
tex_dir = Path(tex_dir).resolve()
remapped = []
for im in bpy.data.images:
    if im.filepath and "_1.<UDIM>.png" in im.filepath:
        new_p = tex_dir / Path(bpy.path.abspath(im.filepath)).name
        if not any(tex_dir.glob(new_p.name.replace("<UDIM>", "*"))):
            raise SystemExit(f"missing UDIM set in {tex_dir}: {new_p.name}")
        im.filepath = str(new_p)
        im.reload()
        remapped.append(str(new_p))
if len(remapped) != 3:
    raise SystemExit(f"expected 3 UDIM image sets (Diffuse/ERM/Normal), got {remapped}")
sc = bpy.context.scene
main = bpy.data.objects[f"{STEM}_Main"]
glass = bpy.data.objects[f"{STEM}_MainGlass"]
others = [o for o in sc.objects if o not in (main, glass)]
if others:
    raise SystemExit(f"unexpected objects in the master: {[o.name for o in others]}")
for o in (main, glass):
    if o.matrix_world != Matrix.Identity(4) or o.parent or o.modifiers:
        raise SystemExit(f"{o.name}: non-identity transform, parent or modifiers")

pts = [v.co.copy() for o in (main, glass) for v in o.data.vertices]
lo = Vector([min(p[i] for p in pts) for i in range(3)])
hi = Vector([max(p[i] for p in pts) for i in range(3)])
centre_bbox = Vector((round((lo.x + hi.x) / 2, 4), round((lo.y + hi.y) / 2, 4), 0.0))
centre = Vector((35.1000, -24.2535, 0.0))      # v003: the delivery v002 offset, fixed (MSK-77 point derivation)
if (centre_bbox - centre).length > 0.10:
    raise SystemExit(f"bbox centre moved: {centre_bbox} vs {centre}")

# --- 256x256 thumbnail (textured, before the export material changes) ---
for m in bpy.data.materials:  # workbench TEXTURE shows the active image node: the Diffuse UDIM set
    if m.use_nodes:
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and "_Diffuse_" in n.image.name:
                m.node_tree.nodes.active = n
sc.render.engine = "BLENDER_WORKBENCH"
sc.display.shading.light = "STUDIO"
sc.display.shading.color_type = "TEXTURE"
sc.render.resolution_x = sc.render.resolution_y = 256
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 92
sc.render.film_transparent = False
cam = bpy.data.objects.new("ThumbCam", bpy.data.cameras.new("ThumbCam"))
sc.collection.objects.link(cam)
sc.camera = cam
size = (hi - lo).length
cam.data.type = "ORTHO"
cam.data.ortho_scale = size * 0.85
d = Vector((1.0, -0.8, 0.6)).normalized()  # from the south-east: main facade I-A (east) and the south facade
cam.location = (lo + hi) / 2 + d * size * 2
cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
cam.data.clip_end = size * 10
sc.render.filepath = str(thumb)
bpy.ops.render.render(write_still=True)
bpy.data.objects.remove(cam)

# --- pivot: move geometry, keep identity transforms ---
shift = Matrix.Translation(-centre)
for o in (main, glass):
    o.data.transform(shift)
    o.data.update()

# --- UCX input: Main without exempt parts + MainGlass (temporary object, removed after the build) ---
raw_ids = main.get("part_ids")
part_ids = json.loads(raw_ids) if isinstance(raw_ids, str) else list(raw_ids)
excl_idx = {i for i, pid in enumerate(part_ids) if pid in UCX_EXCLUDE}
tmp_me = main.data.copy()
bm = bmesh.new()
bm.from_mesh(tmp_me)
lay = bm.faces.layers.int.get("part_idx")
drop = [f for f in bm.faces if f[lay] in excl_idx]
excluded_faces = len(drop)
bmesh.ops.delete(bm, geom=drop, context="FACES")
bm.to_mesh(tmp_me)
bm.free()
tmp = bpy.data.objects.new("UCX_INPUT_TMP", tmp_me)
sc.collection.objects.link(tmp)


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


model_tris = tri_count(main) + tri_count(glass)
ucx_objs, res = ucxd.build_into_scene([tmp, glass], ADDRESS, "Main", model_triangles=model_tris)
pts_s = ucxd.ub.sample_surface(*ucxd.world_arrays([tmp, glass]), max(res.cell_m / 2, 0.1))
dev = ucxd.ub.main_deviation(pts_s, res)
bpy.data.objects.remove(tmp)
bpy.data.meshes.remove(tmp_me)

# --- export copy hygiene ---
for o in (main, glass):
    for k in list(o.keys()):
        del o[k]
    for k in list(o.data.keys()):
        del o.data[k]
    for name in ("part_idx", "mat_id", "udim"):
        a = o.data.attributes.get(name)
        if a:
            o.data.attributes.remove(a)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
for m in bpy.data.materials:
    for k in list(m.keys()):
        del m[k]
    if m.use_nodes:
        for n in [n for n in m.node_tree.nodes if n.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL"}]:
            m.node_tree.nodes.remove(n)
for o in ucx_objs:
    o.data.materials.clear()
    for uvl in list(o.data.uv_layers):
        o.data.uv_layers.remove(uvl)
deliver = [main, glass] + ucx_objs
for o in deliver:
    for c in list(o.users_collection):
        if c != sc.collection:
            c.objects.unlink(o)
    if sc.collection not in o.users_collection:
        sc.collection.objects.link(o)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
for o in sc.objects:
    o.select_set(o in deliver)

bpy.ops.export_scene.fbx(filepath=str(fbx_path), use_selection=True, object_types={"MESH"},
                         axis_forward="Y", axis_up="Z", apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                         global_scale=1.0, bake_space_transform=False, use_mesh_modifiers=False,
                         mesh_smooth_type="FACE", use_triangles=False, use_custom_props=False,
                         add_leaf_bones=False, bake_anim=False, path_mode="STRIP", embed_textures=False)

pts2 = [v.co for o in (main, glass) for v in o.data.vertices]
lo2 = [min(p[i] for p in pts2) for i in range(3)]
hi2 = [max(p[i] for p in pts2) for i in range(3)]
ucx_tris = sum(len(o.data.polygons) for o in ucx_objs)
meta = {
    "source_blend": os.path.abspath(src),
    "fbx": str(fbx_path),
    "pivot": {
        "rule": "origin 0,0,0; plan bbox centre of Main+MainGlass at X/Y 0; Z 0 = +-0.000 = abs 167.65 (booklet sheets 10, 18, 19)",
        "offset_subtracted_m": [centre.x, centre.y, centre.z],
        "bbox_centre_source_m": [centre_bbox.x, centre_bbox.y],
        "inverse": "source/Revit-FBX metres (build-v006 frame = build-v004 frame) = delivered + offset_subtracted_m; abs height = z + 167.65",
        "bbox_source_m": [[round(lo.x, 4), round(lo.y, 4), round(lo.z, 4)], [round(hi.x, 4), round(hi.y, 4), round(hi.z, 4)]],
        "bbox_delivered_m": [[round(v, 4) for v in lo2], [round(v, 4) for v in hi2]],
    },
    "triangles": {"main": tri_count(main), "glass": tri_count(glass), "model_excl_ucx": model_tris, "ucx": ucx_tris},
    "ucx": {
        "builder": "tools/blender/ucx_build.py build_into_scene (src/dt_ai/geometry/ucx_build.py)",
        "pieces": len(ucx_objs), "first": ucx_objs[0].name, "last": ucx_objs[-1].name,
        "budget_D012": res.budget, "cell_m": res.cell_m, "gap_m": res.gap_m, "facade_angle_deg": round(res.angle_deg, 3),
        "attempts": res.attempts, "builder_input_excluded_parts": UCX_EXCLUDE, "excluded_faces": excluded_faces,
        "main_to_ucx_max_m": round(float(dev.max()), 4), "main_to_ucx_p99_m": round(float(sorted(dev)[int(len(dev) * 0.99)]), 4),
        "samples": int(len(dev)),
    },
    "thumbnail": str(thumb),
    "thumbnail_textures": remapped,
    "blender": bpy.app.version_string,
}
meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(blend_out))
print("DELIVERY_EXPORT", json.dumps({k: meta[k] for k in ("pivot", "triangles")}), json.dumps({k: v for k, v in meta["ucx"].items() if k != "attempts"}))
