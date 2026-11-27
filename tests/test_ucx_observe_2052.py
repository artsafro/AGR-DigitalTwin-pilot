"""new-case: synthetic regressions for #2052 UCX observations and FBX import flags."""
import ast
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from dt_ai.core.blender_runner import blender_executable, run_blender
from dt_ai.geometry import ucx_command
from test_agr_ucx_1404 import BUILD, box, mesh, two
from twinqa import scene

ROOT = Path(__file__).resolve().parents[1]


def _main_readback(source, pieces, **extra):
    meshes = [{"name": "SM_T_Main"}, *pieces]
    for item in meshes:
        tris = len(item["hull"]["tris"]) if "hull" in item else 12
        item.update(triangles=tris, polygon_degrees={"3": tris}, materials=[],
                    rotation_euler_deg=[0, 0, 0], scale=[1, 1, 1], location=[0, 0, 0],
                    uv_channels=1, mirrored_uv_triangles=0, udim_tiles=[1001])
    return {"source": str(source), "readback_ok": True, "meshes": meshes, "other_objects": [], "images": [], **extra}


@pytest.mark.parametrize("driver", ["ucx_audit", "ucx_build", "ucx_resolve", "fbx_readback"])
def test_fbx_import_requests_no_image_search(driver):
    tree = ast.parse((ROOT / "tools/blender" / f"{driver}.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and ast.unparse(node.func) == "bpy.ops.import_scene.fbx"]
    assert calls
    for call in calls:
        assert any(kw.arg == "use_image_search" and ast.literal_eval(kw.value) is False for kw in call.keywords)


def test_v010_warns_only_for_disconnected_bodies():
    one = box(0, 1)
    # Simulate FBX split vertices: each triangle has independent indices.
    split = {"verts": [one["verts"][i] for tri in one["tris"] for i in tri],
             "tris": [list(range(i, i + 3)) for i in range(0, 36, 3)]}
    verts, tris = [], []
    for n in range(298):
        body = box(2*n, 2*n + 1)
        tris.extend([[len(verts) + i for i in tri] for tri in body["tris"]])
        verts.extend(body["verts"])
    rb = _main_readback("SM_T_Main.fbx", [mesh("UCX_SM_T_Main_001", split),
                        mesh("UCX_SM_T_Main_002", {"verts": verts, "tris": tris})])
    warnings = [f for f in ucx_command._v010(rb, "Main") if f["name"] == "UCX disconnected bodies (advisory)"]
    assert len(warnings) == 1
    assert warnings[0]["status"] == "review"
    assert "UCX_SM_T_Main_002" in warnings[0]["observed"] and "298" in warnings[0]["observed"]
    assert "UCX_SM_T_Main_001" not in warnings[0]["observed"]


@pytest.mark.parametrize("observation", [
    {"status": "observed", "passages": [{"volume_m3": 1.25, "blocked_m3": 1.25, "blocked_share": 1.0}]},
    {"status": "not_measured", "reason": "section budget"},
])
def test_agr_ucx_serializes_passage_observation_without_gating(tmp_path, monkeypatch, observation):
    from dt_ai.core import blender_runner

    model = tmp_path / "model.fbx"
    model.touch()
    out = tmp_path / "out.fbx"
    pieces = two(0.004)
    for piece in pieces:
        piece["name"] = piece["name"].replace("Ground", "Main")
    native = Mock(return_value=_main_readback(out, pieces, passages=observation))
    monkeypatch.setattr(scene, "readback", native)
    monkeypatch.setattr(blender_runner, "run_blender", Mock(return_value=BUILD))
    assert ucx_command.main([str(model), str(out), "Main"]) == 0
    report = json.loads((tmp_path / "out.fbx.agr_ucx.json").read_text(encoding="utf-8"))
    assert report["steps"]["passages"] == observation
    assert "passages" not in report["passed_checks"]
    native.assert_called_once_with(out, None, observe_passages=True)


@pytest.mark.blender
@pytest.mark.skipif(not Path(blender_executable()).is_file(), reason="Blender not installed")
def test_native_section_readback_reports_distinct_passages_and_union(tmp_path):
    # Separate slab-only porches have 1 m³ each below their roofs; duplicate UCX must not double count.
    fbx = tmp_path / "porches.fbx"
    readback = tmp_path / "facts.json"
    fixtures = [("SM_T_Main", box(0, 1, 0, 1, 11, 11.5)),
                ("Porch", box(2, 3, 0, 1, 11, 11.5)),
                ("Datum", box(4, 5, 0, 1, 10, 10.5)),
                ("UCX_SM_T_Main_001", box(0, 1, 0, 1, 10, 11)),
                ("UCX_SM_T_Main_002", box(0, 1, 0, 1, 10, 11))]
    script = tmp_path / "make_porches.py"
    script.write_text(f"""import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
for name, hull in {fixtures!r}:
    data = bpy.data.meshes.new(name)
    data.from_pydata(hull['verts'], [], hull['tris'])
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
bpy.ops.export_scene.fbx(filepath={str(fbx)!r})
""", encoding="utf-8")
    run_blender(script, outputs=[fbx], log_path=tmp_path / "make.log")
    report = run_blender(ROOT / "tools/blender/fbx_readback.py", [fbx, readback, "--observe-passages"],
                         output_json=readback, log_path=tmp_path / "readback.log")
    assert report["readback_ok"]
    obs = report["passages"]
    assert obs["status"] == "observed"
    assert [(p["volume_m3"], p["blocked_m3"], p["blocked_share"]) for p in obs["passages"]] == [
        (1.0, 1.0, 1.0), (1.0, 0.0, 0.0)]
    assert [m["body_count"] for m in report["meshes"] if m["name"].startswith("UCX_")] == [1, 1]
