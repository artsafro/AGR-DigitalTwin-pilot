"""Scene stages from the Blender readback: rule logic on fixed readbacks, plus a real
background-Blender roundtrip (skipped when Blender is not installed)."""
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

import validate_package as vp
from test_validator import PROFILES, STEM, good_files
from twinqa.scene import find_blender, readback, scene_findings, ucx_triangle_limit


def _clean_topology(**overrides):
    topo = {
        "duplicate_vertices": 0,
        "duplicate_edges": 0,
        "duplicate_polygons": 0,
        "self_intersections": 0,
        "isolated_vertices": 0,
        "isolated_edges": 0,
        "isolated_polygons": 0,
        "zero_length_edges": 0,
        "duplicates_and_self_intersections": 0,
        "tol_m": 0.002,
    }
    topo.update(overrides)
    return topo


def mesh(name="SM_Test_K_1_Main", tris=12, degrees=None, rot=(0, 0, 0), scale=(1, 1, 1), uv=1, mirrored=0,
         tiles=(1001,), loc=(0, 0, 0), topology=None, omit_topology=False, world_scale=None, parent=None):
    facts = {"name": name, "triangles": tris, "polygon_degrees": degrees or {"3": tris}, "rotation_euler_deg": list(rot),
             "scale": list(scale), "uv_channels": uv, "mirrored_uv_triangles": mirrored, "udim_tiles": list(tiles),
             "location": list(loc)}
    if not omit_topology:
        facts["topology"] = _clean_topology(**(topology or {}))
    if world_scale is not None:
        facts["world_scale"] = list(world_scale)
    if parent is not None:
        facts["parent"] = parent
    return facts


def rb(*meshes, other=(), units=None):
    if units is None:
        units = {"unit_scale_factor": 100.0, "original_unit_scale_factor": 100.0, "error": None}
    return {"source": "C:/x/SM_Test_K_1.fbx", "readback_ok": True, "meshes": list(meshes),
            "other_objects": list(other), "images": [], "fbx_units": units}


def statuses(found, stage):
    return {f.name: f.status for f in found[stage]}


def test_clean_vpm_mesh_passes_scene_stages():
    found = scene_findings(rb(mesh()), "vpm", "oks", PROFILES.vpm)
    assert set(statuses(found, "V003").values()) == {"pass"}
    assert statuses(found, "V004") == {"applied transforms": "pass", "topology defects": "pass"}
    assert set(statuses(found, "V008").values()) == {"pass"}


@pytest.mark.parametrize("tris, status", [(150_000, "pass"), (150_001, "review"), (1_000_000, "review"),
                                          (1_000_001, "fail")])
def test_vpm_oks_triangles_project_target_and_hard_limit_conflict_1(tris, status):
    found = scene_findings(rb(mesh(tris=tris)), "vpm", "oks", PROFILES.vpm)
    assert next(f for f in found["V003"] if f.name == "triangle count").status == status


@pytest.mark.parametrize("model, budget", [(49_999, 15_000), (50_000, 2_500), (1_243_374, 62_169),
                                           (3_000_000, 100_000)])
def test_ucx_budget_is_checker_formula_conflict_3(model, budget):
    assert ucx_triangle_limit(model) == budget


def test_ucx_excluded_from_model_triangles_and_budget_checked():
    found = scene_findings(rb(mesh(tris=100_000), mesh(name="UCX_SM_Test_K_1_Main_001", tris=5_001)), "vpm", "oks",
                           PROFILES.vpm)
    assert next(f for f in found["V003"] if f.name == "triangle count").observed.endswith(": 100000")
    assert statuses(found, "V010") == {"UCX triangle budget": "fail", "UCX shape and coverage": "not_run"}


def test_npm_oks_over_150k_fails():
    found = scene_findings(rb(mesh(tris=150_001)), "npm", "oks", PROFILES.npm)
    assert next(f for f in found["V003"] if f.name == "triangle count").status == "fail"


@pytest.mark.parametrize("bad, stage, name", [
    ({"degrees": {"4": 6}}, "V003", "triangulated"),
    ({"rot": (90, 0, 0)}, "V004", "applied transforms"),
    ({"uv": 2}, "V008", "one UV channel"),
    ({"mirrored": 3}, "V008", "mirrored islands"),
])
def test_scene_defects_fail(bad, stage, name):
    found = scene_findings(rb(mesh(**bad)), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, stage)[name] == "fail"


def test_glass_outside_1001_and_split_pivot_fail():
    found = scene_findings(rb(mesh(), mesh("SM_Test_K_1_MainGlass", tiles=(1002,), loc=(1, 0, 0))), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V008")["glass tile"] == "fail"
    assert statuses(found, "V013")["shared pivot"] == "fail"


def test_light_in_main_fbx_fails_conflict_14():
    found = scene_findings(rb(mesh(), other=[{"name": "Omni", "type": "LIGHT"}]), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V003")["object types"] == "fail"


def with_bounds(m, lo, hi):
    m["bounds_m"] = [list(lo), list(hi)]
    return m


@pytest.mark.parametrize("lo, hi, status", [((-10, -5, 0), (10, 5, 30), "pass"),     # centred
                                            ((-8, -5, 0), (12, 5, 30), "pass"),      # 10 % of 20 m
                                            ((-7, -5, 0), (13, 5, 30), "fail")])     # 15 %
def test_pivot_at_geometric_centre_conflict_19(lo, hi, status):
    found = scene_findings(rb(with_bounds(mesh(), lo, hi)), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V013")["pivot at geometric centre"] == status


@pytest.mark.parametrize("kind, role", [("vpm", "oks"), ("npm", "oks"), ("npm", "ground"), ("vpm", "light")])
def test_v002_clean_readback_passes_units_and_scale(kind, role):
    profile = PROFILES.vpm if kind == "vpm" else PROFILES.npm
    found = scene_findings(rb(mesh()), kind, role, profile)
    assert statuses(found, "V002") == {"system units": "pass", "scale 1:1": "pass"}


@pytest.mark.parametrize("usf", [1.0, 0.1, 2.54, 100 * (1 + 1e-4)])
def test_v002_wrong_unit_scale_factor_fails(usf):
    found = scene_findings(rb(mesh(), units={"unit_scale_factor": usf, "original_unit_scale_factor": usf, "error": None}),
                           "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V002")["system units"] == "fail"


def test_v002_unit_scale_within_relative_tolerance_passes():
    usf = 100 * (1 + 1e-7)
    found = scene_findings(rb(mesh(), units={"unit_scale_factor": usf, "original_unit_scale_factor": 100.0, "error": None}),
                           "npm", "oks", PROFILES.npm)
    assert statuses(found, "V002")["system units"] == "pass"


def test_v002_missing_unit_scale_factor_fails_with_error():
    found = scene_findings(rb(mesh(), units={"unit_scale_factor": None, "original_unit_scale_factor": None,
                                            "error": "UnitScaleFactor not declared"}),
                           "vpm", "ground", PROFILES.vpm)
    finding = next(f for f in found["V002"] if f.name == "system units")
    assert finding.status == "fail" and "UnitScaleFactor not declared" in finding.observed


def test_v002_units_not_read_is_not_run():
    report = rb(mesh())
    del report["fbx_units"]
    found = scene_findings(report, "vpm", "oks", PROFILES.vpm)
    finding = next(f for f in found["V002"] if f.name == "system units")
    assert finding.status == "not_run" and finding.observed == "units not read"


@pytest.mark.parametrize("scale", [(100, 100, 100), (1, 1, 0.01)])
def test_v002_import_scale_not_one_fails(scale):
    found = scene_findings(rb(mesh(scale=scale), mesh(name="UCX_SM_Test_K_1_Main_001", scale=scale)),
                           "vpm", "oks", PROFILES.vpm)
    finding = next(f for f in found["V002"] if f.name == "scale 1:1")
    assert finding.status == "fail"
    assert "SM_Test_K_1_Main" in finding.observed and "UCX_SM_Test_K_1_Main_001" in finding.observed


@pytest.mark.parametrize("kind", ["npm", "vpm"])
def test_v002_inherited_parent_scale_fails(kind):
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    main = mesh(scale=(1, 1, 1), world_scale=(2, 2, 2), parent="Parent")
    ucx = mesh(name="UCX_SM_Test_K_1_Main_001", scale=(1, 1, 1), world_scale=(2, 2, 2), parent="Parent")
    found = scene_findings(rb(main, ucx), kind, "oks", profile)
    finding = next(f for f in found["V002"] if f.name == "scale 1:1")
    assert finding.status == "fail"
    assert "SM_Test_K_1_Main" in finding.observed and "UCX_SM_Test_K_1_Main_001" in finding.observed
    assert "world" in finding.observed


@pytest.mark.parametrize("kind", ["npm", "vpm"])
def test_v002_unit_parent_passes(kind):
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    found = scene_findings(rb(mesh(scale=(1, 1, 1), world_scale=(1, 1, 1), parent="Parent")), kind, "oks", profile)
    assert statuses(found, "V002")["scale 1:1"] == "pass"


def test_v002_direct_scale_fails_even_if_world_reported_one():
    found = scene_findings(rb(mesh(scale=(2, 2, 2), world_scale=(1, 1, 1))), "npm", "oks", PROFILES.npm)
    assert statuses(found, "V002")["scale 1:1"] == "fail"


def test_v002_world_scale_within_tolerance_passes():
    found = scene_findings(rb(mesh(world_scale=(1 + 1e-5, 1, 1 - 1e-5))), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V002")["scale 1:1"] == "pass"


def test_v002_import_scale_within_tolerance_passes():
    found = scene_findings(rb(mesh(scale=(1 + 1e-5, 1, 1 - 1e-5))), "npm", "ground", PROFILES.npm)
    assert statuses(found, "V002")["scale 1:1"] == "pass"


def test_v002_scale_fail_lists_at_most_five_meshes():
    meshes = [mesh(name=f"M{i}", scale=(2, 1, 1)) for i in range(6)]
    found = scene_findings(rb(*meshes), "npm", "oks", PROFILES.npm)
    observed = next(f for f in found["V002"] if f.name == "scale 1:1").observed
    assert all(f"M{i}" in observed for i in range(5))
    assert "M5" not in observed


def _scene_package(tmp_path):
    files = good_files()
    package = tmp_path / f"{STEM}.zip"
    with zipfile.ZipFile(package, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return package


def test_scene_readback_replaces_units_placeholder(monkeypatch, tmp_path):
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh()))
    report = vp.validate(_scene_package(tmp_path), None, PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    assert not any(f.name == "units and scale" for f in st["V002"].findings)
    assert statuses({"V002": st["V002"].findings}, "V002")["system units"] == "pass"


def test_scene_readback_centimetre_units_fail_package(monkeypatch, tmp_path):
    units = {"unit_scale_factor": 1.0, "original_unit_scale_factor": 1.0, "error": None}
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh(), units=units))
    report = vp.validate(_scene_package(tmp_path), None, PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    assert st["V002"].status == "fail" and report.exit_code == 1


def test_scene_readback_error_keeps_units_placeholder(monkeypatch, tmp_path):
    def boom(path, blender=None, timeout=600):
        raise RuntimeError("readback failed")

    monkeypatch.setattr(vp, "readback", boom)
    report = vp.validate(_scene_package(tmp_path), None, PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    assert any(f.name == "units and scale" and f.status == "not_run" for f in st["V002"].findings)


def test_origin_at_zero_and_ucx_exempt_from_shared_pivot():
    found = scene_findings(rb(mesh(loc=(5, 0, 0)), mesh(name="SM_Test_K_1_MainGlass", loc=(5, 0, 0)),
                              mesh(name="UCX_SM_Test_K_1_Main_001", loc=(9, 9, 0))), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V013")["origin at FBX zero"] == "fail"
    assert statuses(found, "V013")["shared pivot"] == "pass"


def test_readback_exit_code_7_with_valid_report_raises_runtime_error(monkeypatch):
    synthetic_fbx = Path("synthetic/model.fbx")
    report_data = {"readback_ok": True, "source": str(synthetic_fbx), "meshes": []}
    prefix = "HEAD_STDERR_PREFIX_DISCARDED_" * 5
    tail = "TAIL_STDERR_ERROR_CODE_7_REPORTED"
    long_stderr = f"{prefix}_{'A' * 350}_{tail}"
    assert len(long_stderr) > 400

    def fake_run(cmd, *args, **kwargs):
        Path(cmd[-1]).write_text(json.dumps(report_data), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=7, stdout="", stderr=long_stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        readback(synthetic_fbx, blender="not-executed")

    msg = str(exc_info.value)
    assert "exit 7" in msg
    assert long_stderr[-400:] in msg
    assert prefix not in msg


def test_readback_returncode_0_with_no_report_raises_runtime_error(monkeypatch):
    synthetic_fbx = Path("synthetic/model.fbx")

    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        readback(synthetic_fbx, blender="not-executed")

    assert "no report" in str(exc_info.value).lower()


def test_readback_timeout_raises_runtime_error_preserving_cause(monkeypatch):
    synthetic_fbx = Path("synthetic/model.fbx")
    timeout_duration = 45

    def fake_run(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout_duration)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        readback(synthetic_fbx, blender="not-executed", timeout=timeout_duration)

    err = exc_info.value
    msg = str(err).lower()
    assert "timed out" in msg or "timeout" in msg
    assert str(timeout_duration) in str(err)
    assert err.__cause__ is not None
    assert isinstance(err.__cause__, subprocess.TimeoutExpired)


def test_readback_returncode_0_with_valid_report_returns_dictionary(monkeypatch):
    synthetic_fbx = Path("synthetic/model.fbx")
    expected_data = {
        "source": str(synthetic_fbx),
        "readback_ok": True,
        "meshes": [
            {"name": "SM_Synthetic_Main", "triangles": 24, "polygon_degrees": {"3": 24}}
        ],
        "other_objects": [],
        "images": [],
    }

    def fake_run(cmd, *args, **kwargs):
        Path(cmd[-1]).write_text(json.dumps(expected_data), encoding="utf-8")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = readback(synthetic_fbx, blender="not-executed")
    units = result.pop("fbx_units")
    assert units["unit_scale_factor"] is None and units["original_unit_scale_factor"] is None
    assert units["error"]
    assert result == expected_data


@pytest.mark.parametrize("kind", ["npm", "vpm"])
@pytest.mark.parametrize("count, status", [(100, "pass"), (101, "fail")])
def test_topology_duplicate_limit(kind, count, status):
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    found = scene_findings(rb(mesh(topology={"duplicates_and_self_intersections": count})), kind, "oks", profile)
    assert statuses(found, "V004")["topology defects"] == status


@pytest.mark.parametrize("kind", ["npm", "vpm"])
@pytest.mark.parametrize("key", ["isolated_vertices", "isolated_edges", "isolated_polygons", "zero_length_edges"])
def test_topology_isolated_or_zero_length_fails(kind, key):
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    found = scene_findings(rb(mesh(topology={key: 1})), kind, "oks", profile)
    assert statuses(found, "V004")["topology defects"] == "fail"


def test_topology_missing_readback_is_not_run():
    found = scene_findings(rb(mesh(omit_topology=True)), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V004")["topology defects"] == "not_run"


def test_topology_error_is_not_run():
    found = scene_findings(rb(mesh(topology={"error": "RuntimeError: boom"})), "npm", "oks", PROFILES.npm)
    assert statuses(found, "V004")["topology defects"] == "not_run"


def test_topology_tolerance_mismatch_is_not_run():
    found = scene_findings(rb(mesh(topology={"tol_m": 0.001})), "vpm", "ground", PROFILES.vpm)
    assert statuses(found, "V004")["topology defects"] == "not_run"


def test_ucx_topology_defects_fail():
    found = scene_findings(rb(mesh(name="UCX_SM_Test_K_1_Main_001", topology={"zero_length_edges": 1})),
                           "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V004")["topology defects"] == "fail"


BLENDER = find_blender()
MAKE_CUBE = """
import bpy, sys
out, good = sys.argv[sys.argv.index('--') + 1], sys.argv[-1] == 'good'
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.object.name = 'SM_Test_K_1_Main'
if good:
    bpy.ops.object.modifier_add(type='TRIANGULATE'); bpy.ops.object.modifier_apply(modifier='Triangulate')
    bpy.ops.export_scene.fbx(filepath=out, apply_scale_options='FBX_SCALE_UNITS')
else:
    bpy.ops.mesh.uv_texture_add()  # second UV channel; quads stay
    bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["good", "bad"])
def test_blender_roundtrip_through_validator(tmp_path, variant):
    fbx_path = tmp_path / f"{STEM}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_CUBE, "--", str(fbx_path), variant], check=True, capture_output=True, timeout=300)
    files = good_files()
    files[f"{STEM}.fbx"] = fbx_path.read_bytes()
    package = tmp_path / f"{STEM}.zip"
    with zipfile.ZipFile(package, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    report = vp.validate(package, None, PROFILES, scene=True)
    st = {s.id: s for s in report.stages}
    assert any("scene readback" in n for n in report.notes)
    if variant == "good":
        assert st["V002"].findings[0].status == "pass"  # Blender writes binary FBX 7400
        assert st["V002"].status == "pass"
        assert {st[k].status for k in ("V003", "V004")} == {"pass"}
        assert st["V008"].status == "pass"
    else:
        assert st["V003"].status == "fail" and st["V008"].status == "fail"
        assert st["V002"].status == "fail"
        assert report.exit_code == 1


MAKE_TOPOLOGY = """
import bmesh, bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1, location=(0.5, 0.5, 0.5))
obj = bpy.context.active_object
obj.name = 'SM_Test_K_1_Main'
if variant == 'defect':
    bpy.ops.mesh.primitive_cube_add(size=1, location=(1.0, 0.75, 0.6))
    other = bpy.context.active_object
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    other.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.name = 'SM_Test_K_1_Main'
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.modifier_add(type='TRIANGULATE')
bpy.ops.object.modifier_apply(modifier='Triangulate')
if variant == 'defect':
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.new((10.0, 10.0, 10.0))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["clean", "defect"])
def test_blender_topology_counts(tmp_path, variant):
    fbx_path = tmp_path / f"topology_{variant}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_TOPOLOGY, "--", str(fbx_path), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx_path, blender=BLENDER)
    topo = report["meshes"][0]["topology"]
    found = scene_findings(report, "vpm", "oks", PROFILES.vpm)
    if variant == "clean":
        for key in ("duplicate_vertices", "duplicate_edges", "duplicate_polygons", "self_intersections",
                    "isolated_vertices", "isolated_edges", "isolated_polygons", "zero_length_edges",
                    "duplicates_and_self_intersections"):
            assert topo[key] == 0
        assert statuses(found, "V004")["topology defects"] == "pass"
    else:
        assert topo["isolated_vertices"] >= 1
        assert topo["self_intersections"] > 0
        assert statuses(found, "V004")["topology defects"] == "fail"


MAKE_FALSE_NEGATIVE = """
import bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
if variant == 'shared_vertex':
    base = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0), (1.0, 1.0, 1.0), (1.0, 1.0, -1.0)]
    local = [(0, 1, 2), (0, 3, 4)]
elif variant == 'folded_contact':
    # Synthetic boxes: a floor grid edge lies 1 mm under the upper box's foot.
    base = [(0,0,0), (0,0,1), (0,1,1), (0,1,0), (1,0,0), (1,1,0), (1,1,1), (1,0,1),
            (.399,0,0), (.399,0,1), (.399,1,1), (.399,1,0),
            (.1,.1,1), (.1,.1,1.5), (.1,.4,1.5), (.1,.4,1),
            (.4,.1,1), (.4,.4,1), (.4,.4,1.5), (.4,.1,1.5)]
    local = [(0,1,2), (0,2,3), (4,5,6), (4,6,7), (0,8,9), (0,9,1), (8,4,7), (8,7,9),
             (3,2,10), (3,10,11), (11,10,6), (11,6,5), (0,3,11), (0,11,8), (8,11,5), (8,5,4),
             (1,9,10), (1,10,2), (9,7,6), (9,6,10), (12,13,14), (12,14,15), (16,17,18), (16,18,19),
             (12,16,19), (12,19,13), (15,14,18), (15,18,17), (12,15,17), (12,17,16), (13,19,18), (13,18,14)]
else:
    base = [(-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (0.0, 1.0, 0.0),
            (0.0, -0.3, -0.5), (0.0, -0.1, 0.5), (0.0, -0.5, 0.5),
            (0.0, -0.2, 0.0), (0.0, -0.4, 0.0), (-2.0, -1.0, 0.0), (-1.0, -2.0, 0.0)]
    local = [(0, 1, 2), (3, 6, 7), (6, 4, 5), (6, 5, 7), (0, 8, 9)]
n = len(base)
verts, faces = [], []
for k in range(101):
    ox = 4.0 * k
    verts.extend([(x + ox, y, z) for x, y, z in base])
    faces.extend([tuple(i + n * k for i in face) for face in local])
mesh = bpy.data.meshes.new('SM_Test_K_1_Main')
obj = bpy.data.objects.new('SM_Test_K_1_Main', mesh)
bpy.context.scene.collection.objects.link(obj)
mesh.from_pydata(verts, [], faces)
mesh.update()
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.export_scene.fbx(filepath=out)
"""


MAKE_INHERITED_SCALE = """
import bpy, sys
out, mode = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
main = bpy.context.object
main.name = 'SM_Test_K_1_Main'
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
ucx = bpy.context.object
ucx.name = 'UCX_SM_Test_K_1_Main_001'
if mode == 'direct_scaled':
    main.scale = (2, 2, 2)
else:
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
    parent = bpy.context.object
    parent.name = 'Parent'
    parent.scale = (1, 1, 1) if mode == 'unit_parent' else (2, 2, 2)
    main.parent = parent
    ucx.parent = parent
bpy.ops.export_scene.fbx(filepath=out, apply_scale_options='FBX_SCALE_UNITS')
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["shared_vertex", "subdivided", "folded_contact"])
def test_blender_false_negative_crossings(tmp_path, variant):
    fbx_path = tmp_path / f"false_negative_{variant}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_FALSE_NEGATIVE, "--", str(fbx_path), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx_path, blender=BLENDER)
    topo = report["meshes"][0]["topology"]
    found = scene_findings(report, "vpm", "oks", PROFILES.vpm)
    if variant == "folded_contact":
        assert topo["self_intersections"] == 0
        assert statuses(found, "V004")["topology defects"] == "pass"
    else:
        assert topo["self_intersections"] >= 101
        assert statuses(found, "V004")["topology defects"] == "fail"


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("mode", ["unit_parent", "parent_scaled", "direct_scaled"])
@pytest.mark.parametrize("profile", ["npm", "vpm"])
def test_blender_v002_inherited_scale_roundtrip(tmp_path, mode, profile):
    fbx_path = tmp_path / f"{mode}_{profile}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_INHERITED_SCALE, "--", str(fbx_path), mode],
                   check=True, capture_output=True, timeout=300)
    found = scene_findings(readback(fbx_path), profile, "oks", getattr(PROFILES, profile))
    assert statuses(found, "V002")["system units"] == "pass"
    finding = next(f for f in found["V002"] if f.name == "scale 1:1")
    if mode == "unit_parent":
        assert finding.status == "pass"
    elif mode == "parent_scaled":
        assert finding.status == "fail"
        assert "SM_Test_K_1_Main" in finding.observed and "UCX_SM_Test_K_1_Main_001" in finding.observed
    else:
        assert finding.status == "fail"
        assert "SM_Test_K_1_Main local" in finding.observed
