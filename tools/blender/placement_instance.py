"""Blender headless instancing of placement-engine output (#296).

Pattern: none (new-case: DCC instancing wrapper of the #316 placement engine; library facts, linked
instances with the engine matrix, proven bottom-face deletion, run record stored in the scene, readback).

This script computes NO placement: pivots, rotation, scale, sinking and bottom-face verdicts come from the
plan written by ``tools/placement_site.py`` out of ``dt_ai.placement.engine.place``. It only
- ``facts``: imports each library object (FBX or inline synthetic mesh), bakes its rotation / scale and the
  optional ``base_scale`` into the mesh, and writes local bbox, triangles and bottom faces (downward faces on
  the lowest plane, polygon index kept) for the engine library entry;
- ``instance``: imports the Ground and the libraries the same way, creates one linked object per planned
  instance with ``matrix_world`` = plan matrix (already shifted by the scene origin offset), deletes the
  bottom faces the plan marks ``delete`` (single-user mesh copy), stores the seed and the run record in the
  scene (Text ``placement_run.json`` + scene custom properties), saves a NEW .blend and writes a readback:
  per instance the matrix, polygon and triangle count (after the deletion), lowest world z and the Ground
  height under the pivot (ray cast); per library the polygon and triangle count before deletion.

Usage:
  blender --background --factory-startup --python-exit-code 1 --python tools/blender/placement_instance.py --
      facts <spec.json> <facts.json>
  ... -- instance <spec.json> <plan.json> <out.blend> <readback.json>
Spec: {"libraries": [{"id", "fbx" | "mesh": {"vertices", "faces"}, "base_scale"?: float}],
       "ground": {"fbx" | "mesh"}, "run_record": {...}}.
"""
import json
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix, Vector

BOTTOM_NZ = -0.99      # face normal z below this counts as downward
BOTTOM_PLANE_M = 0.001  # face vertices within 1 mm of the lowest z


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 1.0


def _import(src, name):
    """-> one mesh object named `name` with identity transform and baked geometry."""
    if "mesh" in src:
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in src["mesh"]["vertices"]], [], [tuple(f) for f in src["mesh"]["faces"]])
        me.update()
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=src["fbx"])
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH" and not o.name.upper().startswith("UCX_")]
    if len(meshes) != 1:
        raise SystemExit(f"{src['fbx']}: expected 1 mesh object, got {[o.name for o in meshes]}")
    ob = meshes[0]
    for o in new:
        if o is not ob:
            bpy.data.objects.remove(o, do_unlink=True)
    ob.parent = None
    return ob


def load_library(lib):
    """Import + bake: mesh local coords = rotation/scale of the source node x base_scale; origin kept."""
    ob = _import(lib, "LIB_" + lib["id"])
    loc, rot, sca = ob.matrix_world.decompose()
    bake = rot.to_matrix().to_4x4() @ Matrix.Diagonal((*sca, 1.0))
    bs = float(lib.get("base_scale", 1.0))
    bake = Matrix.Scale(bs, 4) @ bake
    ob.data = ob.data.copy()
    ob.data.transform(bake)
    ob.data.update()
    ob.matrix_world = Matrix.Identity(4)
    ob.name = "LIB_" + lib["id"]
    return ob


def facts_of(ob):
    me = ob.data
    vs = [v.co for v in me.vertices]
    lo = [min(v[i] for v in vs) for i in range(3)]
    hi = [max(v[i] for v in vs) for i in range(3)]
    bottom = []
    for p in me.polygons:
        if p.normal.z < BOTTOM_NZ and all(abs(me.vertices[i].co.z - lo[2]) <= BOTTOM_PLANE_M for i in p.vertices):
            bottom.append({"index": p.index, "points": [list(me.vertices[i].co) for i in p.vertices]})
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    return {"bbox_min": lo, "bbox_max": hi, "triangles": tris, "polygons": len(me.polygons),
            "bottom_faces": bottom}


def cmd_facts(spec_path, out_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    reset()
    out = {}
    for lib in spec["libraries"]:
        ob = load_library(lib)
        out[lib["id"]] = {**facts_of(ob), "base_scale": float(lib.get("base_scale", 1.0))}
    Path(out_path).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"facts: {len(out)} libraries -> {out_path}")


def _ground_height(ground, x, y, top):
    ok, loc, _n, _i = ground.ray_cast(Vector((x, y, top)), Vector((0.0, 0.0, -1.0)))
    return loc.z if ok else None


def cmd_instance(spec_path, plan_path, blend_path, readback_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    out = Path(blend_path)
    if out.exists():
        raise SystemExit(f"{out} exists; saves go to a new versioned path")
    reset()
    ground = _import(spec["ground"], "Ground")
    ground.matrix_world = Matrix.Identity(4) if "mesh" in spec["ground"] else ground.matrix_world
    bpy.context.view_layer.update()
    libs = {}
    col_lib = bpy.data.collections.new("library")
    bpy.context.scene.collection.children.link(col_lib)
    col_lib.hide_render = True
    col_lib.hide_viewport = True
    for lib in spec["libraries"]:
        ob = load_library(lib)
        for c in ob.users_collection:
            c.objects.unlink(ob)
        col_lib.objects.link(ob)
        libs[lib["id"]] = ob
    col_inst = bpy.data.collections.new("instances")
    bpy.context.scene.collection.children.link(col_inst)
    for it in plan["instances"]:
        src = libs[it["library_id"]]
        me = src.data
        if it.get("delete_polygons"):
            me = src.data.copy()
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in it["delete_polygons"]], context="FACES_ONLY")
            bm.to_mesh(me)
            bm.free()
        ob = bpy.data.objects.new(it["name"], me)
        ob.matrix_world = Matrix(it["matrix"])
        ob["handle"] = it["handle"]
        ob["library_id"] = it["library_id"]
        col_inst.objects.link(ob)
    bpy.context.view_layer.update()
    rec = spec.get("run_record", {})
    txt = bpy.data.texts.new("placement_run.json")
    txt.write(json.dumps(rec, indent=1, sort_keys=True))
    sc = bpy.context.scene
    sc["placement_seed"] = int(plan["seed"])
    sc["placement_engine_schema"] = str(plan.get("engine_schema", ""))
    sc["placement_report_sha256"] = str(rec.get("engine_report_sha256", ""))
    top = max((v.co.z for v in ground.data.vertices), default=0.0)
    top = (ground.matrix_world @ Vector((0, 0, top))).z + 100.0
    rows = []
    for ob in col_inst.objects:
        M = ob.matrix_world
        zs = [(M @ v.co).z for v in ob.data.vertices]
        rows.append({"name": ob.name, "handle": ob["handle"], "library_id": ob["library_id"],
                     "matrix": [list(r) for r in M], "polygons": len(ob.data.polygons),
                     "triangles": sum(len(p.vertices) - 2 for p in ob.data.polygons),
                     "lowest_z": min(zs) if zs else None})
    by_name = {it["name"]: it for it in plan["instances"]}
    for r in rows:
        px, py = by_name[r["name"]]["scene_pivot"][:2]
        r["ground_z_at_pivot"] = _ground_height(ground, px, py, top)
    bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=True)
    stored = json.loads(bpy.data.texts["placement_run.json"].as_string())
    Path(readback_path).write_text(json.dumps({
        "blend": str(out), "seed": int(sc["placement_seed"]), "run_record": stored,
        "library_polygons": {k: len(v.data.polygons) for k, v in libs.items()},
        "library_triangles": {k: sum(len(p.vertices) - 2 for p in v.data.polygons) for k, v in libs.items()},
        "instances": rows}, indent=1), encoding="utf-8")
    print(f"instance: {len(rows)} objects -> {out}")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    if argv[:1] == ["facts"] and len(argv) == 3:
        cmd_facts(*argv[1:])
    elif argv[:1] == ["instance"] and len(argv) == 5:
        cmd_instance(*argv[1:])
    else:
        raise SystemExit(__doc__)


main()
