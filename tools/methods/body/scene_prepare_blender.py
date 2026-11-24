"""Blender side of `agr scene prepare` (#1867, step 0 [D390]): layered copy of a Revit FBX for Artem's correction.

Pattern: n/a | new-case: imports SRC.fbx (never saved back), puts every mesh into one collection per layer (named by
the Max layer, e.g. 01_ТЕЛО), colours objects by layer, writes NEW scene_layers.blend, split_PROPOSED.fbx (one root
empty per layer, so the grouping survives the FBX into 3ds Max) and Workbench renders for the review sheet.

    blender44 -b --factory-startup --python tools/methods/body/scene_prepare_blender.py -- SRC.fbx ASSIGN.json OUT_DIR

ASSIGN.json (written by dt_ai.intake.scene_prepare): {"layers": [{"id", "max_layer", "color"}], "objects": {name: id},
"closeups": [id, ...]}. Writes OUT_DIR/blend_report.json: {"collections": {id: n}, "missing": [names in ASSIGN not in
the FBX], "unassigned": [meshes not in ASSIGN], "nonmesh", "renders": {"overview"|id: png}}. Every output must be new.
"""
import json
import os
import sys

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402


def _new(path):
    if os.path.exists(path):
        raise SystemExit(f"refused: {path} exists")
    return path


def _render(scene, cam, objs, path, direction=(1.0, -1.4, 0.9), res=(1600, 1000)):
    coords = [ob.matrix_world @ Vector(c) for ob in objs for c in ob.bound_box]
    if not coords:
        return None
    lo = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    hi = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    centre = (lo + hi) / 2
    d = Vector(direction).normalized()
    cam.location = centre + d * max((hi - lo).length, 1.0) * 2.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    flat = [v for c in coords for v in c]
    loc, scale = cam.camera_fit_coords(bpy.context.evaluated_depsgraph_get(), flat)
    cam.location = loc
    cam.data.ortho_scale = scale * 1.08
    scene.render.filepath = _new(path)
    bpy.ops.render.render(write_still=True)
    return os.path.basename(path)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 3:
        raise SystemExit("usage: scene_prepare_blender.py -- SRC.fbx ASSIGN.json OUT_DIR")
    src, assign_path, out = argv
    with open(assign_path, encoding="utf-8") as fh:
        assign = json.load(fh)
    blend, fbx, report = (os.path.join(out, n) for n in ("scene_layers.blend", "split_PROPOSED.fbx", "blend_report.json"))
    for p in (blend, fbx, report):
        _new(p)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    scene = bpy.context.scene
    layers = {la["id"]: la for la in assign["layers"]}
    colls, roots = {}, {}
    for lid, la in layers.items():
        c = bpy.data.collections.new(la["max_layer"])
        scene.collection.children.link(c)
        c.color_tag = "NONE"
        colls[lid] = c
        e = bpy.data.objects.new(la["max_layer"], None)
        c.objects.link(e)
        roots[lid] = e
    counts = {lid: 0 for lid in layers}
    unassigned, nonmesh, by_layer = [], 0, {lid: [] for lid in layers}
    names = set()
    for ob in list(scene.objects):
        if ob.type == "EMPTY" and ob.name in {la["max_layer"] for la in layers.values()}:
            continue
        if ob.type != "MESH":
            nonmesh += 1
            continue
        names.add(ob.name)
        lid = assign["objects"].get(ob.name)
        if lid not in layers:
            unassigned.append(ob.name)
            continue
        mw = ob.matrix_world.copy()
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        colls[lid].objects.link(ob)
        ob.parent = roots[lid]
        ob.matrix_world = mw
        r, g, b = (v / 255.0 for v in layers[lid]["color"])
        ob.color = (r, g, b, 1.0)
        counts[lid] += 1
        by_layer[lid].append(ob)
    missing = sorted(set(assign["objects"]) - names)
    for ob in list(scene.objects):  # source empties left without children are dropped from the proposed copy
        if ob.type == "EMPTY" and ob not in roots.values() and not ob.children:
            bpy.data.objects.remove(ob)
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True)
    bpy.ops.object.select_all(action="DESELECT")
    for lid in layers:
        roots[lid].select_set(True)
        for ob in by_layer[lid]:
            ob.select_set(True)
    bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True, object_types={"EMPTY", "MESH"}, apply_unit_scale=True,
                             add_leaf_bones=False, bake_anim=False)
    # renders: Workbench, object colours, orthographic
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("w")
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    renders = {}
    every = [ob for obs in by_layer.values() for ob in obs]
    shown = [ob for ob in every if ob not in by_layer.get("INTERIOR_OUT", [])]
    for ob in by_layer.get("INTERIOR_OUT", []):
        ob.hide_render = True
    renders["overview"] = _render(scene, cam, shown or every, os.path.join(out, "render_overview.png"))
    for lid in assign.get("closeups", []):
        obs = by_layer.get(lid) or []
        if not obs:
            continue
        seed = obs[len(obs) // 2].matrix_world.translation
        near = [ob for ob in obs if (ob.matrix_world.translation - seed).length < 8.0] or obs[:1]
        renders[lid] = _render(scene, cam, near, os.path.join(out, f"render_{lid}.png"), res=(800, 640))
    rep = {"schema": "agr-scene-blend/1", "collections": counts, "missing": missing, "unassigned": sorted(unassigned),
           "nonmesh": nonmesh, "renders": {k: v for k, v in renders.items() if v}, "blend": os.path.basename(blend),
           "fbx": os.path.basename(fbx), "blender": bpy.app.version_string}
    with open(report, "x", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print("SCENE_BLEND_OK", counts)


main()
