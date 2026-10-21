"""new-case: public render-QA configuration and numerical verdict contracts."""
import importlib.util
from pathlib import Path
import itertools
import types
import json
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_checker():
    spec = importlib.util.spec_from_file_location("render_qa", ROOT / "tools/qa/render_qa.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_numeric_verdicts():
    qa = load_checker()
    config = qa.validate_config({"targets": ["Cube"], "cameras": ["Camera"],
                                 "ground_resting": ["Cube"], "ground_objects": ["Ground"]})
    assert config["thresholds"]["crop_margin"] == 0.02
    assert config["thresholds"]["minimum_coverage"] == 0.05
    assert config["thresholds"]["floating_m"] == 0.01
    good = {"bbox": [0.2, 0.2, 0.8, 0.8], "depth": [1, 3],
            "coverage": 0.36, "visible_faces": 2, "ground_gap_m": 0.0}
    assert qa.verdicts("Cube", "Camera", good, config["thresholds"]) == []
    for key, value, expected in [("bbox", [-0.03, 0.2, 0.8, 0.8], "cropped"),
                                  ("coverage", 0.04, "empty"),
                                  ("visible_faces", 0, "empty"),
                                  ("ground_gap_m", 0.1, "floating")]:
        failures = qa.verdicts("Cube", "Camera", {**good, key: value}, config["thresholds"])
        assert [f["code"] for f in failures] == [expected]
        assert all(f["object"] == "Cube" and f["frame"] == "Camera" for f in failures)


@pytest.mark.parametrize("bad", [
    {}, {"targets": []}, {"targets": ["A", "A"], "cameras": ["C"]},
    {"targets": ["A"], "cameras": ["C", "C"]},
    {"targets": ["A"], "cameras": ["C"], "unknown": 1},
    {"targets": ["A"], "cameras": ["C"], "ground_resting": ["B"]},
    {"targets": ["A"], "cameras": ["C"], "ground_resting": ["A"]},
    *[{"targets": ["A"], "cameras": ["C"], "thresholds": {key: value}}
      for key, value in [("crop_margin", float("nan")), ("floating_m", float("inf")),
                         ("minimum_coverage", 0), ("crop_margin", True),
                         ("background_rgb", [0, 0]), ("unmapped", 2)]]])
def test_config_rejects_invalid(bad):
    with pytest.raises(ValueError):
        load_checker().validate_config(bad)


def test_wholly_offscreen_positive_depth_is_cropped_and_empty():
    qa = load_checker()
    facts = {"bbox": [2, 0.2, 3, 0.8], "depth": [1, 3],
             "coverage": 0, "visible_faces": 0, "ground_gap_m": 0}
    assert [f["code"] for f in qa.verdicts("A", "C", facts, qa.DEFAULTS)] == ["cropped", "empty"]


def test_threshold_boundaries():
    qa = load_checker()
    good = {"bbox": [0.2, 0.2, 0.8, 0.8], "depth": [1, 3],
            "coverage": 0.36, "visible_faces": 2, "ground_gap_m": 0}
    for key, value, code in [("bbox", [-0.02, 0.2, 0.8, 0.8], "crop_boundary"),
                             ("coverage", 0.05, "coverage_boundary"),
                             ("ground_gap_m", 0.01, "floating_boundary")]:
        assert [f["code"] for f in qa.verdicts("A", "C", {**good, key: value}, qa.DEFAULTS)] == [code]


def test_output_isolation(tmp_path):
    qa = load_checker()
    scene = tmp_path / "input.blend"
    config = tmp_path / "config.json"
    scene.write_bytes(b"source")
    config.write_text('{"targets":["A"],"cameras":["C"]}')
    alias = tmp_path / "alias.json"
    alias.hardlink_to(config)
    aliases = [config, scene, alias, tmp_path / "nested" / ".." / "config.json"]
    import os
    if os.name == "nt":
        aliases += [Path(str(config).upper()), Path(str(config).replace("/", "\\"))]
        junction = tmp_path / "junction"
        linked = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(tmp_path)],
                                capture_output=True)
        assert linked.returncode == 0, linked.stdout + linked.stderr
        aliases.append(junction / "config.json")
    for output in aliases:
        with pytest.raises((ValueError, FileExistsError)):
            qa.validate_paths(scene, config, output, tmp_path / "renders")
        assert scene.read_bytes() == b"source"
        assert json.loads(config.read_text())["targets"] == ["A"]
        assert not (tmp_path / "renders").exists()
    with pytest.raises(ValueError):
        qa.validate_paths(scene, scene, tmp_path / "out.json", tmp_path / "renders")
    with pytest.raises(ValueError):
        qa.validate_paths(scene, config, tmp_path / "renders" / "out.json", tmp_path / "renders")


def test_duplicate_json_keys(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"targets":["A"],"targets":["B"],"cameras":["C"]}')
    with pytest.raises(ValueError, match="targets"):
        load_checker().read_config(path)


def test_input_mutation_cannot_publish_pass(tmp_path, monkeypatch):
    import sys
    qa = load_checker()
    scene, config = tmp_path / "scene.blend", tmp_path / "config.json"
    scene.write_bytes(b"scene")
    config.write_text('{"targets":["A"],"cameras":["C"]}')
    fake = types.SimpleNamespace(app=types.SimpleNamespace(version=(5, 1, 2)),
        ops=types.SimpleNamespace(wm=types.SimpleNamespace(open_mainfile=lambda **kw: None)),
        data=types.SimpleNamespace(images=[], libraries=[]), context=types.SimpleNamespace(scene=None))
    monkeypatch.setitem(sys.modules, "bpy", fake)
    def mutate(*args):
        config.write_text("changed during run")
        return {"status": "pass"}
    monkeypatch.setattr(qa, "check_scene", mutate)
    with pytest.raises(ValueError, match="Input changed"):
        qa.main(["--scene", str(scene), "--config", str(config),
                 "--report", str(tmp_path / "report.json"), "--renders", str(tmp_path / "renders")])
    assert not (tmp_path / "report.json").exists()


@pytest.mark.parametrize("key,value", [("visible_faces", float("nan")), ("visible_faces", -1),
    ("visible_faces", 1.5), ("coverage", -0.1), ("coverage", 1.1), ("bbox", [0.8, 0.2, 0.1, 0.8])])
def test_invalid_measurement(key, value):
    qa = load_checker()
    facts = {"bbox": [0.2, 0.2, 0.8, 0.8], "depth": [1, 3],
             "coverage": 0.36, "visible_faces": 2, "ground_gap_m": 0}
    facts[key] = value
    with pytest.raises(ValueError):
        qa.verdicts("A", "C", facts, qa.DEFAULTS)


@pytest.mark.blender
def test_blender_fixtures(tmp_path):
    blender = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
    if not blender.exists():
        pytest.skip("Blender 5.1.2 not installed")
    output = tmp_path / "fixtures"
    result = subprocess.run([str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
                             "--python", str(ROOT / "tests/fixtures/render_qa_blender.py"), "--", str(output)],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    reports = json.loads((output / "fixtures.json").read_text())
    assert {name: report["status"] for name, report in reports.items()} == {
        "good": "pass", "cropped": "fail", "empty": "fail", "floating": "fail", "occluded": "fail"}
    command = [str(blender), "--background", "--factory-startup", "--python-exit-code", "1",
               "--python", str(ROOT / "tools/qa/render_qa.py"), "--",
               "--scene", str(output / "good.blend"), "--config", str(output / "config.json"),
               "--report", str(output / "cli.json"), "--renders", str(output / "cli-renders")]
    first = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert first.returncode == 0, first.stdout + first.stderr
    receipt = (output / "cli.json").read_bytes()
    assert json.loads(receipt)["status"] == "pass"
    repeat = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert repeat.returncode != 0
    assert (output / "cli.json").read_bytes() == receipt
    bad = json.loads((output / "config.json").read_text())
    bad["thresholds"] = {"minimum_coverage": 0.99}
    (output / "config.json").write_text(json.dumps(bad))
    command[command.index("--report") + 1] = str(output / "bad-cli.json")
    command[command.index("--renders") + 1] = str(output / "bad-cli-renders")
    failed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert json.loads((output / "bad-cli.json").read_text())["status"] == "fail"


@pytest.mark.blender
@pytest.mark.parametrize("modifier_type", ["SUBSURF", "MULTIRES"])
def test_blender_rejects_subdivision_level_mismatch(tmp_path, modifier_type):
    blender = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
    if not blender.exists():
        pytest.skip("Blender 5.1.2 not installed")
    renders = tmp_path / "must-not-exist"
    script = f'''
import bpy, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("qa", {str(ROOT / "tools/qa/render_qa.py")!r})
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
assert bpy.app.version == (5, 1, 2)
scene = bpy.context.scene
cube = scene.objects["Cube"]
modifier = cube.modifiers.new("SubdivisionMismatch", {modifier_type!r})
if modifier.type == "MULTIRES":
    bpy.context.view_layer.objects.active = cube
    bpy.ops.object.multires_subdivide(modifier=modifier.name)
modifier.levels = 0
modifier.render_levels = 1
try:
    qa.check_scene(scene, {{"targets": ["Cube"], "cameras": ["Camera"]}}, {str(renders)!r})
except ValueError as exc:
    assert "Cube" in str(exc) and "SubdivisionMismatch" in str(exc), str(exc)
else:
    raise AssertionError("Viewport/render subdivision mismatch accepted")
assert not Path({str(renders)!r}).exists()
'''
    result = subprocess.run([str(blender), "--background", "--factory-startup",
                             "--python-exit-code", "1", "--python-expr", script],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.blender
@pytest.mark.parametrize("mode", ["visible_camera", "holdout_shader", "is_holdout",
                                 "is_shadow_catcher", "layer_holdout", "layer_indirect",
                                 "layer_exclude", "material_override"])
@pytest.mark.parametrize("role", ["target", "occluder"])
def test_blender_rejects_render_visibility_overrides(tmp_path, mode, role):
    blender = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
    if not blender.exists():
        pytest.skip("Blender 5.1.2 not installed")
    script = f'''
import bpy, importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("qa", {str(ROOT / "tools/qa/render_qa.py")!r})
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)
assert bpy.app.version == (5, 1, 2)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1
scene.render.engine = "CYCLES"
scene.cycles.samples = 1
scene.render.resolution_x = scene.render.resolution_y = 32
scene.render.resolution_percentage = 100
scene.world = bpy.data.worlds.new("BlackWorld")
scene.world.use_nodes = True
scene.world.node_tree.nodes.get("Background").inputs[0].default_value = (0, 0, 0, 1)
bpy.ops.mesh.primitive_cube_add()
target = bpy.context.object
target.name = "Target"
material = bpy.data.materials.new("OpaqueControl")
material.use_nodes = True
nodes = material.node_tree.nodes
nodes.clear()
output = nodes.new("ShaderNodeOutputMaterial")
emission = nodes.new("ShaderNodeEmission")
material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
target.data.materials.append(material)
bpy.ops.object.camera_add(location=(0, 0, 10))
camera = bpy.context.object
camera.name = "Camera"
camera.data.type = "ORTHO"
camera.data.ortho_scale = 5
scene.camera = camera
config = {{"targets": ["Target"], "cameras": ["Camera"]}}
root = Path({str(tmp_path)!r})
bpy.context.view_layer.update()
control = qa.check_scene(scene, config, root / "opaque-before")
assert control["status"] == "pass", control
assert control["frames"][0]["pixels"]["background_share"] < 1
obj = target
if {role!r} == "occluder":
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 4))
    obj = bpy.context.object
    obj.name = "Occluder"
    material = material.copy()
    obj.data.materials.append(material)
    nodes = material.node_tree.nodes
    output = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    emission = next(n for n in nodes if n.type == "EMISSION")
collection = bpy.data.collections.new("VisibilityCollection")
scene.collection.children.link(collection)
for owner in list(obj.users_collection):
    owner.objects.unlink(obj)
collection.objects.link(obj)
bpy.context.view_layer.update()
layer = bpy.context.view_layer.layer_collection.children[collection.name]
mode = {mode!r}
if mode == "holdout_shader":
    holdout = nodes.new("ShaderNodeHoldout")
    material.node_tree.links.new(holdout.outputs[0], output.inputs["Surface"])
elif mode == "visible_camera":
    obj.visible_camera = False
elif mode.startswith("is_"):
    setattr(obj, mode, True)
elif mode == "material_override":
    bpy.context.view_layer.material_override = material
else:
    setattr(layer, {{"layer_holdout": "holdout", "layer_indirect": "indirect_only",
                    "layer_exclude": "exclude"}}[mode], True)
bpy.context.view_layer.update()
try:
    qa.check_scene(scene, config, root / "must-not-exist")
except ValueError as exc:
    expected_name = ("VisibilityCollection" if mode.startswith("layer_") else
                     bpy.context.view_layer.name if mode == "material_override" else obj.name)
    assert expected_name in str(exc), (expected_name, str(exc))
else:
    raise AssertionError("Unsupported render visibility accepted: " + mode)
assert not (root / "must-not-exist").exists()
# Reset to prove rejection does not poison later opaque checks.
obj.visible_camera = True
obj.is_holdout = obj.is_shadow_catcher = False
layer.exclude = layer.holdout = layer.indirect_only = False
bpy.context.view_layer.material_override = None
material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
if mode == "holdout_shader":
    nodes.remove(holdout)
bpy.context.view_layer.update()
assert qa.check_scene(scene, config, root / "opaque-after")["status"] == "pass"
'''
    result = subprocess.run([str(blender), "--background", "--factory-startup",
                             "--python-exit-code", "1", "--python-expr", script],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr


def test_generated_verdict_grid():
    qa = load_checker()
    # Independent literal oracle over 3 x 3 x 3 x 2 = 54 measurements.
    for outside, coverage, gap, visible in itertools.product(
            (0, 0.019, 0.021), (0.049, 0.051, 0.8), (0, 0.009, 0.011), (0, 2)):
        facts = {"bbox": [-outside, 0.2, 0.8, 0.8], "depth": [1, 3],
                 "coverage": coverage, "ground_gap_m": gap, "visible_faces": visible}
        expected = (["cropped"] if outside == 0.021 else [])
        expected += ["empty"] if coverage == 0.049 or visible == 0 else []
        expected += ["floating"] if gap == 0.011 else []
        assert [f["code"] for f in qa.verdicts("A", "C", facts, qa.DEFAULTS)] == expected


@pytest.mark.parametrize("key", ["bbox", "depth", "coverage", "ground_gap_m"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_measurement(key, value):
    facts = {"bbox": [0.2, 0.2, 0.8, 0.8], "depth": [1, 3],
             "coverage": 0.36, "visible_faces": 2, "ground_gap_m": 0}
    facts[key] = [value, 0.2, 0.8, 0.8] if key == "bbox" else [value, 3] if key == "depth" else value
    qa = load_checker()
    with pytest.raises(ValueError, match="Nonfinite"):
        qa.verdicts("A", "C", facts, qa.DEFAULTS)
