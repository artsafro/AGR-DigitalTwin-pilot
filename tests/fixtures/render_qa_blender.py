"""new-case: synthetic Blender render QA end-to-end fixtures, never real model data."""
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("render_qa", ROOT / "tools/qa/render_qa.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
OUT = Path(sys.argv[sys.argv.index("--") + 1])
OUT.mkdir(parents=True, exist_ok=False)


def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.render.resolution_x = sc.render.resolution_y = 64
    sc.render.resolution_percentage = 100
    sc.display.shading.background_type = "WORLD"
    sc.world = bpy.data.worlds.new("World")
    sc.world.color = (0, 0, 0)
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
    cube = bpy.context.object
    cube.name = "Target"
    bpy.ops.mesh.primitive_plane_add(size=100)
    bpy.context.object.name = "Ground"
    data = bpy.data.cameras.new("Camera")
    data.type = "ORTHO"
    data.ortho_scale = 5
    camera = bpy.data.objects.new("Camera", data)
    sc.collection.objects.link(camera)
    camera.location = (0, -10, 5)
    camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = camera
    bpy.context.view_layer.update()
    return sc, cube, camera


config = {"targets": ["Target"], "cameras": ["Camera"],
          "ground_resting": ["Target"], "ground_objects": ["Ground"]}
results = {}
for case, expected in [("good", []), ("cropped", ["cropped"]),
                       ("empty", ["empty"]), ("floating", ["floating"]),
                       ("occluded", ["empty"])]:
    sc, cube, camera = scene()
    if case == "cropped":
        camera.location.x += 2
    elif case == "empty":
        cube.scale = (0.1, 0.1, 0.1)
        cube.location.z = 0.1  # small grounded target, coverage below 5%, no crop
    elif case == "floating":
        cube.location.z += 0.1
    elif case == "occluded":
        bpy.ops.mesh.primitive_cube_add(location=(0, -4, 2), scale=(5, 0.3, 5))
        bpy.context.object.name = "Occluder"
    bpy.context.view_layer.update()
    report = qa.check_scene(sc, config, OUT / case)
    actual = sorted({f["code"] for f in report["frames"][0]["failures"]})
    assert actual == expected, (case, actual, report)
    results[case] = report
    if case == "good":
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "good.blend"))
        (OUT / "config.json").write_text(json.dumps(config), encoding="utf-8")
        facts = report["frames"][0]["objects"][0]
        assert facts["visible_faces"] > 0 and facts["coverage"] > 0.05
        assert 0 <= report["frames"][0]["pixels"]["background_share"] < 1
        try:
            qa.check_scene(sc, config, OUT / case)
        except FileExistsError:
            pass
        else:
            raise AssertionError("repeat output must not overwrite")

probes = {}
for label in ("centimetres", "raised_terrain", "behind_camera", "union_coverage"):
    sc, cube, camera = scene()
    settings = dict(config)
    if label == "centimetres":
        sc.unit_settings.scale_length = 0.01
        for obj in (cube, sc.objects["Ground"]):
            obj.location *= 100
            obj.scale *= 100
        camera.location *= 100
        camera.data.ortho_scale *= 100
        camera.data.clip_end *= 100
        cube.location.z += 10
        expected = ["floating"]
    elif label == "raised_terrain":
        sc.objects["Ground"].location.z = 3
        cube.location.z += 3
        camera.location.z += 3
        expected = []
    elif label == "behind_camera":
        camera.rotation_euler = (Vector((0, 0, -1)) - camera.location).to_track_quat("Z", "Y").to_euler()
        expected = ["empty"]
    else:
        camera.location = (0, 0, 10)
        camera.rotation_euler = (0, 0, 0)
        cube.scale = (0.45, 0.45, 0.45)
        cube.location = (-1, 0, 0.45)
        bpy.ops.mesh.primitive_cube_add(size=0.9, location=(1, 0, 0.45))
        bpy.context.object.name = "SecondTarget"
        settings = {**config, "targets": ["Target", "SecondTarget"],
                    "ground_resting": ["Target", "SecondTarget"]}
        expected = []
    bpy.context.view_layer.update()
    report = qa.check_scene(sc, settings, OUT / label)
    actual = sorted({f["code"] for f in report["frames"][0]["failures"]})
    assert actual == expected, (label, report)
    if label == "union_coverage":
        assert all(o["object_coverage"] < 0.05 for o in report["frames"][0]["objects"])
        assert report["frames"][0]["coverage"] > 0.05
    probes[label] = report["status"]

for label in ("missing_camera", "missing_object", "missing_terrain", "empty_mesh"):
    sc, cube, camera = scene()
    settings = dict(config)
    if label == "missing_camera":
        settings["cameras"] = ["UnknownCamera"]
    elif label == "missing_object":
        settings["targets"] = settings["ground_resting"] = ["UnknownObject"]
    elif label == "missing_terrain":
        sc.objects["Ground"].location.x += 500
    else:
        cube.data.clear_geometry()
    bpy.context.view_layer.update()
    try:
        qa.check_scene(sc, settings, OUT / label)
    except ValueError:
        assert not (OUT / label).exists()
        probes[label] = "error, no writes"
    else:
        raise AssertionError(f"{label} did not fail closed")

# Hostile in-memory state and destination collisions at the real render boundary.
sc, cube, camera = scene()
def move_target(*args):
    cube.location.z += 2
    bpy.context.view_layer.update()
bpy.app.handlers.render_pre.append(move_target)
try:
    try:
        qa.check_scene(sc, config, OUT / "changed-state")
    except ValueError as exc:
        assert "changed" in str(exc).lower(), str(exc)
    else:
        raise AssertionError("changed geometry must not publish a stale pass")
finally:
    bpy.app.handlers.render_pre.remove(move_target)

sc, cube, camera = scene()
sentinel = OUT / "sentinel.json"
sentinel.write_bytes(b"never overwrite this input")
def collide(*args):
    (OUT / "collision" / "frame_0000.png").hardlink_to(sentinel)
bpy.app.handlers.render_pre.append(collide)
try:
    try:
        qa.check_scene(sc, config, OUT / "collision")
    except FileExistsError:
        pass
    else:
        raise AssertionError("precreated render path must never be overwritten")
finally:
    bpy.app.handlers.render_pre.remove(collide)
assert sentinel.read_bytes() == b"never overwrite this input"
probes["state_changed"] = "error, no stale pass"
probes["hardlink_collision"] = "error, input unchanged"
(OUT / "probes.json").write_text(json.dumps(probes, indent=2), encoding="utf-8")

(OUT / "fixtures.json").write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
print("FIXTURE_VERDICTS", {k: v["status"] for k, v in results.items()})
