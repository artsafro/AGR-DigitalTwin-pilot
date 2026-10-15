"""Live-session twin realization (Blender 4.4.0 live via blender_exec.py; runs INSIDE Blender).

Expects a global CFG = {"dump": <dump.json>, "blend": <out.blend>, "fbx": <out.fbx>} set by the caller.
Same data-API realization as tools/export/export_mesh_blender.py (polygons, ID_<n> slots, LEVEL empties),
but WITHOUT read_factory_settings (the user's scene stays): only owned datablocks are created, the
.blend is written with bpy.data.libraries.write (the open file is not re-saved), the FBX exports the
owned selection only, and every owned datablock is removed at the end. Prints one compact JSON line.
"""
import json
import time
from pathlib import Path

import bpy

t0 = time.perf_counter()
dump = json.loads(Path(CFG["dump"]).read_text(encoding="utf-8"))  # noqa: F821 (CFG injected)
blend, fbx = Path(CFG["blend"]), Path(CFG["fbx"])  # noqa: F821
for p in (blend, fbx):
    if p.exists():
        raise SystemExit(f"{p} exists")
KINDS = ("objects", "meshes", "materials", "scenes", "collections")
before = {k: len(getattr(bpy.data, k)) for k in KINDS}
TAG = "agrexp_"
objs, meshes, mats = [], [], {}
scene = bpy.context.scene
try:
    for m in dump["meshes"]:
        polys = [list(p) for p in m["polygons"]]
        tris_per = [len(p) - 2 for p in polys]
        mids, k, pmid = m["material_ids"], 0, []
        for n in tris_per:
            ids = set(mids[k:k + n])
            if len(ids) != 1:
                raise SystemExit(f"{m['name']}: mixed ids in polygon")
            pmid.append(ids.pop())
            k += n
        data = bpy.data.meshes.new(TAG + m["name"])
        meshes.append(data)
        data.from_pydata([tuple(v) for v in m["vertices"]], [], polys)
        for n in range(1, max(pmid) + 1):
            if n not in mats:
                mats[n] = bpy.data.materials.new(f"{TAG}ID_{n:02d}")
            data.materials.append(mats[n])
        for poly, mid in zip(data.polygons, pmid):
            poly.material_index = mid - 1
        if data.validate(clean_customdata=False) or len(data.polygons) != len(polys):
            raise SystemExit(f"{m['name']}: Blender changed polygons")
        data.update()
        obj = bpy.data.objects.new(m["name"], data)
        scene.collection.objects.link(obj)
        objs.append(obj)
    for h in dump.get("helpers", []):
        e = bpy.data.objects.new(h["name"], None)
        e.location = h["location"]
        scene.collection.objects.link(e)
        objs.append(e)
    # object names may get a .001 suffix if the user's scene already has that name: report it
    renamed = [o.name for o, src in zip(objs, [m["name"] for m in dump["meshes"]] + [h["name"] for h in dump.get("helpers", [])]) if o.name != src]
    # material names carry TAG in the live scene; rename for export so slots read ID_<n> like the baseline
    for n, mat in mats.items():
        mat.name = f"ID_{n:02d}"
    t_build = time.perf_counter() - t0
    blend.parent.mkdir(parents=True, exist_ok=True)
    # a .blend holding only owned data: a temporary scene that links the owned objects (opened files
    # show their scene objects; loose objects would be invisible to readback)
    tmp_scene = bpy.data.scenes.new(TAG + "scene")
    tmp_scene.unit_settings.system, tmp_scene.unit_settings.scale_length = "METRIC", 1.0
    for o in objs:
        tmp_scene.collection.objects.link(o)
    bpy.data.libraries.write(str(blend), {tmp_scene}, fake_user=False)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, object_types={"MESH", "EMPTY"},
                             apply_unit_scale=True, use_mesh_modifiers=False, add_leaf_bones=False)
    t_io = time.perf_counter() - t0 - t_build
finally:
    if "tmp_scene" in globals():
        bpy.data.scenes.remove(tmp_scene)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    for me in meshes:
        bpy.data.meshes.remove(me)
    for mat in mats.values():
        bpy.data.materials.remove(mat)
after = {k: len(getattr(bpy.data, k)) for k in KINDS}
print(json.dumps({"build_s": round(t_build, 4), "io_s": round(t_io, 4), "renamed": renamed,
                  "clean": before == after, "version": bpy.app.version_string,
                  "units": [scene.unit_settings.system, scene.unit_settings.scale_length]}))
