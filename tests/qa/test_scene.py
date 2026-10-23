import math

import random

from twinqa.scene import OVERLAP_EPS_M, find_blender, readback, scene_findings, ucx_triangle_limit

"""Scene stages from the Blender readback: rule logic on fixed readbacks, plus a real
background-Blender roundtrip (skipped when Blender is not installed)."""
import itertools
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
         tiles=(1001,), loc=(0, 0, 0), topology=None, omit_topology=False, world_scale=None, parent=None, materials=()):
    facts = {"name": name, "triangles": tris, "polygon_degrees": degrees or {"3": tris}, "rotation_euler_deg": list(rot),
             "scale": list(scale), "uv_channels": uv, "mirrored_uv_triangles": mirrored, "udim_tiles": list(tiles),
             "location": list(loc), "materials": list(materials)}
    if not omit_topology:
        facts["topology"] = _clean_topology(**(topology or {}))
    if world_scale is not None:
        facts["world_scale"] = list(world_scale)
    if parent is not None:
        facts["parent"] = parent
    return facts


UCX = "UCX_SM_Test_K_1_Main_001"


def rb(*meshes, other=(), units=None):
    if units is None:
        units = {"unit_scale_factor": 100.0, "original_unit_scale_factor": 100.0, "error": None}
    return {"source": "C:/x/SM_Test_K_1.fbx", "readback_ok": True, "meshes": list(meshes),
            "other_objects": list(other), "images": [], "fbx_units": units}


def statuses(found, stage):
    return {f.name: f.status for f in found[stage]}


@pytest.mark.parametrize("uv, expected", [(1, "pass"), (0, "fail"), (2, "fail")])
def test_v008_uv_contract_excludes_collision_only(uv, expected):
    """Ground UCX has no UV by design; render meshes still require exactly one channel."""
    found = scene_findings(rb(mesh(name="SM_Test_Ground", uv=uv),
                              mesh(name="UCX_SM_Test_Ground_001", uv=0)), "vpm", "ground", PROFILES.vpm)
    assert statuses(found, "V008")["one UV channel"] == expected
    assert statuses(found, "V008")["texel density"] == "not_run"
    assert statuses(found, "V008")["texel density upper"] == "not_run"
    assert statuses(found, "V010")["UCX present"] == "pass"
    assert statuses(found, "V010")["UCX triangle budget"] == "pass"


def test_clean_vpm_mesh_passes_scene_stages():
    found = scene_findings(rb(mesh()), "vpm", "oks", PROFILES.vpm)
    assert set(statuses(found, "V003").values()) == {"pass"}
    assert statuses(found, "V004") == {"applied transforms": "pass", "topology defects": "pass", "co-directional clearance": "not_run"}
    assert statuses(found, "V008") == {
        "one UV channel": "pass",
        "mirrored islands": "pass",
        "texel density": "not_run",
        "texel density upper": "not_run",
    }


@pytest.mark.parametrize("tris, status", [(150_000, "pass"), (150_001, "review"), (1_000_000, "review"),
                                          (1_000_001, "fail")])
def test_vpm_oks_triangles_project_target_and_hard_limit_conflict_1(tris, status):
    found = scene_findings(rb(mesh(tris=tris)), "vpm", "oks", PROFILES.vpm)
    assert next(f for f in found["V003"] if f.name == "triangle count").status == status


@pytest.mark.parametrize("model, budget", [(49_999, 15_000), (50_000, 2_500), (1_243_374, 62_169),
                                           (3_000_000, 100_000)])
def test_ucx_budget_is_checker_formula_conflict_3(model, budget):
    assert ucx_triangle_limit(model) == budget


@pytest.mark.parametrize("ucx_tris,status", [(5_000, "pass"), (5_001, "fail")])
def test_ucx_triangle_budget_at_limit_inclusive(ucx_tris, status):
    """UCX budget (reg p.36-37 §13.7-13.8): model 100 000 -> ceil(5 %) = 5 000 UCX triangles;
    exactly at the budget passes and budget+1 fails (the gate is `>` not `>=`)."""
    found = scene_findings(rb(mesh(tris=100_000), mesh(name="UCX_SM_Test_K_1_Main_001", tris=ucx_tris)),
                           "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V010")["UCX triangle budget"] == status


def test_ucx_excluded_from_model_triangles_and_budget_checked():
    found = scene_findings(rb(mesh(tris=100_000), mesh(name="UCX_SM_Test_K_1_Main_001", tris=5_001)), "vpm", "oks",
                           PROFILES.vpm)
    assert next(f for f in found["V003"] if f.name == "triangle count").observed.endswith(": 100000")
    assert statuses(found, "V010") == {"UCX present": "pass", "UCX material slots": "pass",
                                       "UCX triangle budget": "fail", "UCX shape and coverage": "not_run",
                                       "UCX intersections": "not_run", "UCX intersections coverage": "not_run",
                                       "UCX piece gap (advisory)": "not_run"}


# R05 / R07 (docs/domain/areas/ucx.md; reg p.36 §13.1, §13.3): own UCX in every non-lighting VPM FBX, no slots
@pytest.mark.parametrize("role", ["oks", "ground"])
def test_vpm_geometry_fbx_without_ucx_fails_r05(role):
    found = scene_findings(rb(mesh(materials=["M_Wall"])), "vpm", role, PROFILES.vpm)
    present = next(f for f in found["V010"] if f.name == "UCX present")
    assert present.status == "fail" and present.source_pdf_pages == [36]
    assert "UCX material slots" not in statuses(found, "V010")


@pytest.mark.parametrize("role", ["oks", "ground"])
def test_vpm_geometry_fbx_with_clean_ucx_passes_r05_r07(role):
    found = scene_findings(rb(mesh(materials=["M_Wall"]), mesh(name=UCX, tris=12)), "vpm", role, PROFILES.vpm)
    assert statuses(found, "V010")["UCX present"] == "pass"
    assert statuses(found, "V010")["UCX material slots"] == "pass"


def test_light_fbx_and_npm_are_exempt_from_ucx_r03_r05():
    light = scene_findings(rb(mesh(name="SM_Test_K_1_Light")), "vpm", "light", PROFILES.vpm)
    npm = scene_findings(rb(mesh()), "npm", "oks", PROFILES.npm)
    assert light["V010"] == [] and npm["V010"] == []


@pytest.mark.parametrize("slots", [["M_Ucx"], [None], [None, "M_Wall"]])  # an empty slot is still a slot
def test_ucx_with_material_slot_fails_r07(slots):
    found = scene_findings(rb(mesh(), mesh(name=UCX), mesh(name="UCX_SM_Test_K_1_Main_002", materials=slots)),
                           "vpm", "oks", PROFILES.vpm)
    finding = next(f for f in found["V010"] if f.name == "UCX material slots")
    assert finding.status == "fail" and "UCX_SM_Test_K_1_Main_002" in finding.observed
    assert UCX + "'" not in finding.observed  # the clean piece is not reported


def test_ucx_slots_unknown_without_readback_field_is_not_run_never_pass():
    ucx = mesh(name=UCX)
    del ucx["materials"]
    found = scene_findings(rb(mesh(), ucx), "vpm", "oks", PROFILES.vpm)
    assert statuses(found, "V010")["UCX material slots"] == "not_run"


def test_ucx_presence_and_slots_brute_force_probe():
    """Invariant probe: every combination of kind, role, UCX count, slot shape and render-mesh slots."""
    slot_shapes = ["absent", [], [None], ["M_Ucx"]]
    cases = 0
    for kind, role, n_ucx, render_slots in itertools.product(("vpm", "npm"), ("oks", "ground", "light"), range(3),
                                                             ([], ["M_Wall"])):
        for shapes in itertools.product(slot_shapes, repeat=n_ucx):
            pieces = []
            for i, shape in enumerate(shapes, 1):
                piece = mesh(name=f"UCX_SM_Test_K_1_Main_{i:03d}", materials=[] if shape == "absent" else shape)
                if shape == "absent":
                    del piece["materials"]
                pieces.append(piece)
            found = statuses(scene_findings(rb(mesh(materials=render_slots), *pieces), kind, role,
                                            PROFILES.vpm if kind == "vpm" else PROFILES.npm), "V010")
            cases += 1
            if kind != "vpm" or role == "light":
                assert found == {}, (kind, role, shapes)
                continue
            assert found["UCX present"] == ("pass" if n_ucx else "fail")
            if not n_ucx:
                assert "UCX material slots" not in found
                continue
            slotted = any(s not in ("absent", []) for s in shapes)
            expected = "fail" if slotted else "not_run" if "absent" in shapes else "pass"
            assert found["UCX material slots"] == expected, (shapes, found)
    print(f"UCX presence/slots probe: {cases}/{cases} combinations")
    assert cases == 2 * 3 * 2 * (1 + 4 + 16)


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


@pytest.mark.parametrize("kind", ["npm", "vpm"])
@pytest.mark.parametrize("rot, expected", [((0, 0, 0), "pass"), ((0, 0, 30), "fail")])
def test_v004_reset_rotation_both_profiles(kind, rot, expected):
    profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
    found = scene_findings(rb(mesh(rot=rot)), kind, "oks", profile)
    assert statuses(found, "V004")["applied transforms"] == expected


def test_v004_generated_rotation_probe():
    angles = [-180, -30, -0.002, 0, 0.0005, 0.001, 0.002, 30, 180]
    total = 0
    for kind in ("npm", "vpm"):
        profile = PROFILES.npm if kind == "npm" else PROFILES.vpm
        for axis in range(3):
            for angle in angles:
                rot = [0.0, 0.0, 0.0]
                rot[axis] = angle
                expected = "pass" if abs(angle) <= 0.001 else "fail"
                found = scene_findings(rb(mesh(rot=rot, scale=(1, 1, 1))), kind, "oks", profile)
                assert statuses(found, "V004")["applied transforms"] == expected
                total += 1
    print(f"{total}/{total} checked")


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
MAKE_UCX = """
import bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
bpy.context.object.name = 'SM_Test_K_1_Main'
bpy.context.object.data.materials.append(bpy.data.materials.new('M_Wall'))
if variant != 'missing':
    bpy.ops.mesh.primitive_cube_add(size=2.1, location=(0, 0, 1))
    bpy.context.object.name = 'UCX_SM_Test_K_1_Main_001'
    if variant == 'slot':
        bpy.context.object.data.materials.append(bpy.data.materials.new('M_Ucx'))
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant, present, slots", [("clean", "pass", "pass"), ("slot", "pass", "fail"),
                                                     ("missing", "fail", None)])
def test_blender_ucx_presence_and_slots_from_fbx_readback(tmp_path, variant, present, slots):
    fbx_path = tmp_path / f"{STEM}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_UCX, "--", str(fbx_path), variant], check=True, capture_output=True, timeout=300)
    found = statuses(scene_findings(readback(fbx_path), "vpm", "oks", PROFILES.vpm), "V010")
    assert found["UCX present"] == present
    assert found.get("UCX material slots") == slots
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
        v008 = {item.name: item.status for item in st["V008"].findings}
        assert v008["one UV channel"] == "pass"
        assert v008["mirrored islands"] == "pass"
        # The cube FBX has no diffuse size, so density stays not_run and the stage cannot pass.
        assert v008["texel density"] == "not_run"
        assert v008["texel density upper"] == "not_run"
        assert st["V008"].status == "not_run"
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


BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def ucx_box(name, lo, hi):
    """UCX mesh whose hull is an axis-aligned box (8 verts, 12 triangles)."""
    verts = [[hi[0] if i & 4 else lo[0], hi[1] if i & 2 else lo[1], hi[2] if i & 1 else lo[2]] for i in range(8)]
    m = mesh(name=name, tris=12)
    m["hull"] = {"verts": verts, "tris": [list(t) for t in BOX_TRIS]}
    return m


def _pair(a, b, kind="vpm", role="oks"):
    profile = PROFILES.vpm if kind == "vpm" else PROFILES.npm
    return statuses(scene_findings(rb(mesh(), a, b), kind, role, profile), "V010")


def test_ucx_overlap_5cm_fails_intersections():
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (0.95, 0, 0), (1.95, 1, 1)))
    assert st["UCX intersections"] == "fail"
    assert "fail" in st.values()


def test_ucx_nested_piece_fails_intersections():
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (4, 4, 4)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1, 1, 1), (2, 2, 2)))
    assert st["UCX intersections"] == "fail"


@pytest.mark.parametrize("gap_m", [0.002, 0.005, 0.01])
def test_ucx_gap_inside_band_passes_both(gap_m):
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1 + gap_m, 0, 0), (2 + gap_m, 1, 1)))
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == "pass"


def test_ucx_touching_boxes_pass_intersection_and_review_gap():
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1, 0, 0), (2, 1, 1)))
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == "review"


@pytest.mark.parametrize("gap_m", [0.001, 0.03])
def test_ucx_gap_outside_band_is_review(gap_m):
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1 + gap_m, 0, 0), (2 + gap_m, 1, 1)))
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == "review"


@pytest.mark.parametrize("gap_m,status", [(0.002, "pass"), (0.01, "pass"),
                                          (0.00199, "review"), (0.01001, "review")])
def test_ucx_gap_exact_boundaries_inclusive_d098(gap_m, status):
    """D098: neighbour gap 2 mm - 1 cm inclusive (reg p.36 §13.4). The floor (2 mm) and ceiling
    (10 mm) pass at equality; one 0.01 mm beyond (1.99 mm / 10.01 mm) flips to review."""
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1 + gap_m, 0, 0), (2 + gap_m, 1, 1)))
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == status


def test_ucx_one_metre_apart_is_not_a_neighbour():
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (2, 0, 0), (3, 1, 1)))
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == "pass"


def test_ucx_overlap_is_not_counted_in_the_gap_finding():
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (0.5, 0, 0), (1.5, 1, 1)))
    assert st["UCX intersections"] == "fail"
    assert st["UCX piece gap (advisory)"] == "pass"


def test_ucx_without_hull_is_not_run():
    st = statuses(scene_findings(rb(mesh(), mesh(name="UCX_SM_Test_K_1_Main_001"),
                                    mesh(name="UCX_SM_Test_K_1_Main_002")), "vpm", "oks", PROFILES.vpm), "V010")
    assert st["UCX intersections"] == "not_run"
    assert st["UCX intersections coverage"] == "not_run"
    assert st["UCX piece gap (advisory)"] == "not_run"


def test_single_ucx_piece_passes_both_pair_findings():
    found = scene_findings(rb(mesh(), ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))),
                           "vpm", "oks", PROFILES.vpm)
    st = statuses(found, "V010")
    assert st["UCX intersections"] == "pass"
    assert st["UCX piece gap (advisory)"] == "pass"


@pytest.mark.parametrize("kind, role", [("npm", "oks"), ("vpm", "light")])
def test_ucx_pair_findings_absent_for_npm_or_light(kind, role):
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (0.5, 0, 0), (1.5, 1, 1)), kind, role)
    assert "UCX intersections" not in st
    assert "UCX intersections coverage" not in st
    assert "UCX piece gap (advisory)" not in st


@pytest.mark.parametrize("seed", range(200))
def test_ucx_random_pair_gap_never_fails_and_overlap_matches_signed_gap(seed):
    rng = random.Random(seed)
    axis = rng.randrange(3)
    signed = rng.uniform(-0.05, 0.15)
    size_a = [rng.uniform(0.4, 2.0) for _ in range(3)]
    size_b = [rng.uniform(0.4, 2.0) for _ in range(3)]
    lo_b = [0.0, 0.0, 0.0]
    hi_b = [0.0, 0.0, 0.0]
    for i in range(3):
        if i == axis:
            lo_b[i] = size_a[i] + signed
        else:
            lo_b[i] = rng.uniform(-(size_b[i] - 0.25), size_a[i] - 0.25)
        hi_b[i] = lo_b[i] + size_b[i]
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), tuple(size_a)),
               ucx_box("UCX_SM_Test_K_1_Main_002", tuple(lo_b), tuple(hi_b)))
    assert st["UCX piece gap (advisory)"] != "fail"
    assert st["UCX intersections coverage"] == "pass"
    if abs(abs(signed) - OVERLAP_EPS_M) < 1e-6:
        return
    assert (st["UCX intersections"] == "fail") is (signed < -OVERLAP_EPS_M)


def _v010(*ucx):
    found = scene_findings(rb(mesh(), *ucx), "vpm", "oks", PROFILES.vpm)["V010"]
    return {f.name: f for f in found}


def _rotate_hull_z(piece, degrees):
    radians = math.radians(degrees)
    cosine, sine = math.cos(radians), math.sin(radians)
    piece["hull"]["verts"] = [[cosine * x - sine * y, sine * x + cosine * y, z]
                              for x, y, z in piece["hull"]["verts"]]
    return piece


def _two_boxes(name):
    """One UCX hull: [0,1]^3 and [3,4]x[0,1]x[0,1], tris of the second box offset by 8."""
    first = ucx_box(name, (0, 0, 0), (1, 1, 1))
    second = ucx_box(name, (3, 0, 0), (4, 1, 1))
    piece = mesh(name=name, tris=24)
    piece["hull"] = {"verts": first["hull"]["verts"] + second["hull"]["verts"],
                     "tris": first["hull"]["tris"] + [[i + 8 for i in tri] for tri in second["hull"]["tris"]]}
    return piece


def test_missing_hull_does_not_hide_proven_overlap():
    found = _v010(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (0.5, 0, 0), (1.5, 1, 1)),
                  mesh(name="UCX_SM_Test_K_1_Main_003"))
    assert found["UCX intersections"].status == "fail"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "UCX_SM_Test_K_1_Main_003" in coverage.observed
    assert "no hull" in coverage.observed


def test_missing_hull_blocks_pass_when_neighbours_are_clear():
    found = _v010(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (1.005, 0, 0), (2.005, 1, 1)),
                  mesh(name="UCX_SM_Test_K_1_Main_003"))
    assert found["UCX intersections"].status == "not_run"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "UCX_SM_Test_K_1_Main_003" in coverage.observed


@pytest.mark.parametrize("penetration_m", [0.0001, 0.00005, 0.00019])
def test_penetration_below_former_touch_allowance_fails(penetration_m):
    st = _pair(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)),
               ucx_box("UCX_SM_Test_K_1_Main_002", (1 - penetration_m, 0, 0), (2 - penetration_m, 1, 1)))
    assert st["UCX intersections"] == "fail"


@pytest.mark.parametrize("delta_m, intersections, gap", [(-0.0001, "fail", None), (0.0, "pass", "review"),
                                                         (0.005, "pass", "pass")])
def test_shared_z_rotation_keeps_overlap_touch_and_gap(delta_m, intersections, gap):
    left = _rotate_hull_z(ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1)), 30)
    right = _rotate_hull_z(ucx_box("UCX_SM_Test_K_1_Main_002", (1 + delta_m, 0, 0), (2 + delta_m, 1, 1)), 30)
    st = _pair(left, right)
    assert st["UCX intersections"] == intersections
    if gap is not None:
        assert st["UCX piece gap (advisory)"] == gap


def test_nonconvex_hull_between_boxes_is_unresolved_not_fail():
    found = _v010(_two_boxes("UCX_SM_Test_K_1_Main_001"),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (1.4, 0.2, 0.2), (2.6, 0.8, 0.8)))
    assert found["UCX intersections"].status == "not_run"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "UCX_SM_Test_K_1_Main_001" in coverage.observed
    assert "non-convex" in coverage.observed


def test_nonconvex_pair_does_not_hide_an_independent_overlap():
    found = _v010(_two_boxes("UCX_SM_Test_K_1_Main_001"),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (1.4, 0.2, 0.2), (2.6, 0.8, 0.8)),
                  ucx_box("UCX_SM_Test_K_1_Main_003", (10, 0, 0), (11, 1, 1)),
                  ucx_box("UCX_SM_Test_K_1_Main_004", (10.5, 0, 0), (11.5, 1, 1)))
    assert found["UCX intersections"].status == "fail"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "UCX_SM_Test_K_1_Main_001" in coverage.observed


def test_open_piece_bbox_touch_is_not_an_intersection_fail():
    opened = ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))
    opened["hull"]["tris"] = opened["hull"]["tris"][:-2]
    found = _v010(opened, ucx_box("UCX_SM_Test_K_1_Main_002", (1, 0, 0), (2, 1, 1)))
    assert found["UCX intersections"].status != "fail"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "open" in coverage.observed


def test_flat_degenerate_piece_coverage_not_run():
    flat = ucx_box("UCX_SM_Test_K_1_Main_001", (0, 0, 0), (1, 1, 1))
    for vert in flat["hull"]["verts"]:
        vert[2] = 0.0
    found = _v010(flat, ucx_box("UCX_SM_Test_K_1_Main_002", (0, 0, 0), (1, 1, 1)))
    assert found["UCX intersections"].status != "fail"
    coverage = found["UCX intersections coverage"]
    assert coverage.status == "not_run"
    assert "UCX_SM_Test_K_1_Main_001" in coverage.observed
    assert "degenerate" in coverage.observed


def test_nonconvex_piece_a_metre_away_is_resolved_by_bbox():
    found = _v010(_two_boxes("UCX_SM_Test_K_1_Main_001"),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (5, 0, 0), (6, 1, 1)))
    assert found["UCX intersections"].status == "pass"
    assert found["UCX intersections coverage"].status == "pass"
    assert found["UCX piece gap (advisory)"].status == "pass"


def test_rotated_pair_with_close_boxes_but_far_surfaces_is_not_a_wide_neighbour():
    # Diamond |x|+|y| <= 0.707 (unit square turned 45 deg) and a 10 cm box in its bbox corner:
    # bounding boxes overlap, surfaces are ~349 mm apart (> NEIGHBOUR_M), so no wide-gap review.
    found = _v010(_rotate_hull_z(ucx_box("UCX_SM_Test_K_1_Main_001", (-0.5, -0.5, 0), (0.5, 0.5, 1)), 45),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (0.6, 0.6, 0), (0.7, 0.7, 1)))
    assert found["UCX intersections"].status == "pass"
    assert found["UCX intersections coverage"].status == "pass"
    assert found["UCX piece gap (advisory)"].status == "pass"
    assert "wide=0" in found["UCX piece gap (advisory)"].observed


def test_nonconvex_neighbour_5cm_away_resolves_intersection_but_gap_is_unmeasured():
    found = _v010(_two_boxes("UCX_SM_Test_K_1_Main_001"),
                  ucx_box("UCX_SM_Test_K_1_Main_002", (4.05, 0, 0), (5.05, 1, 1)))
    assert found["UCX intersections"].status == "pass"
    assert found["UCX intersections coverage"].status == "pass"
    assert found["UCX piece gap (advisory)"].status == "not_run"
    assert "unmeasured=1" in found["UCX piece gap (advisory)"].observed


def _axis_box(name, axis, delta):
    lo, hi = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    lo[axis] += delta
    hi[axis] += delta
    return ucx_box(name, tuple(lo), tuple(hi))


@pytest.mark.parametrize("seed", range(200))
def test_ucx_rotated_penetration_fails_and_positive_gap_never_fails(seed):
    rng = random.Random(seed + 10_000)
    axis = rng.randrange(3)
    angle = rng.uniform(0.0, 360.0)
    penetration = rng.uniform(2e-5, 5e-3)
    left = _rotate_hull_z(_axis_box("UCX_SM_Test_K_1_Main_001", axis, 0.0), angle)
    right = _rotate_hull_z(_axis_box("UCX_SM_Test_K_1_Main_002", axis, 1.0 - penetration), angle)
    assert _pair(left, right)["UCX intersections"] == "fail"
    gap = rng.uniform(2e-5, 0.05)
    left = _rotate_hull_z(_axis_box("UCX_SM_Test_K_1_Main_001", axis, 0.0), angle)
    right = _rotate_hull_z(_axis_box("UCX_SM_Test_K_1_Main_002", axis, 1.0 + gap), angle)
    st = _pair(left, right)
    assert st["UCX intersections"] != "fail"
    assert st["UCX piece gap (advisory)"] != "fail"


MAKE_UCX_HULL = """
import bpy, sys
out, variant = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)

def cube(name, loc):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    bpy.context.object.name = name
    bpy.ops.object.modifier_add(type='TRIANGULATE')
    bpy.ops.object.modifier_apply(modifier='Triangulate')

cube('SM_Test_K_1_Main', (0, 0, 1))
cube('UCX_SM_Test_K_1_Main_001', (0, 0, 0.5))
# size 1: half-extent 0.5. overlap shares 0.5 m; gap leaves 2 mm between faces.
cube('UCX_SM_Test_K_1_Main_002', (0.5, 0, 0.5) if variant == 'overlap' else (1.002, 0, 0.5))
bpy.ops.export_scene.fbx(filepath=out)
"""


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
@pytest.mark.parametrize("variant", ["overlap", "gap"])
def test_blender_ucx_hull_roundtrip(tmp_path, variant):
    fbx_path = tmp_path / f"ucx_{variant}.fbx"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", MAKE_UCX_HULL, "--", str(fbx_path), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx_path)
    ucx = [m for m in report["meshes"] if m["name"].upper().startswith("UCX_")]
    other = [m for m in report["meshes"] if not m["name"].upper().startswith("UCX_")]
    assert ucx and all("hull" in m and m["hull"]["verts"] and m["hull"]["tris"] for m in ucx)
    assert other and all("hull" not in m for m in other)
    st = statuses(scene_findings(report, "vpm", "oks", PROFILES.vpm), "V010")
    assert st["UCX intersections"] == ("fail" if variant == "overlap" else "pass")


# --- #510: VPM Ground triangle limit from the site-area table (reg p.28-29 §3.10, [D010]) -------------------

def _ground_tri_finding(tris, kind="vpm", area=None, profile=None):
    found = scene_findings(rb(mesh(name="SM_Test_Ground", tris=tris), mesh(name="UCX_SM_Test_Ground_001", tris=4)),
                           kind, "ground", profile or (PROFILES.vpm if kind == "vpm" else PROFILES.npm),
                           ground_area_m2=area)
    return next(f for f in found["V003"] if f.name == "triangle count")


def _ground_bands():
    return PROFILES.vpm["geometry"]["ground_triangles_max_by_area_ha"]


@pytest.mark.parametrize("tris, status", [(1_650_000, "pass"), (1_650_001, "fail")])
def test_vpm_ground_triangles_by_site_area_boundary(tris, status):
    f = _ground_tri_finding(tris, area=3431.50)
    assert f.status == status
    assert f.data["area_m2"] == 3431.50 and f.data["area_ha"] == pytest.approx(0.34315)
    assert f.data["band"] == {"area_max": 0.5, "triangles_max": 1_650_000}
    assert "1650000" in f.expected


@pytest.mark.parametrize("area_m2, limit", [(500, 300_000), (500.0001, 705_000), (15_000, 3_150_000),
                                            (15_001, 4_500_000), (0.01, 300_000), (10**7, 4_500_000)])
def test_vpm_ground_limit_examples(area_m2, limit):
    from twinqa.scene import ground_triangle_limit
    assert ground_triangle_limit(PROFILES.vpm, area_m2)[0] == limit


@pytest.mark.parametrize("index", range(8))
def test_vpm_ground_limit_every_band_from_standard(index):
    """Every band edge comes from VPM_STANDARD.yaml: the upper edge is inclusive, just above the
    previous edge already belongs to this band; at the limit passes, limit + 1 fails."""
    from twinqa.scene import ground_triangle_limit
    bands = _ground_bands()
    assert len(bands) == 8
    band = bands[index]
    probes = [band["area_max"] * 10_000] if "area_max" in band else [band["area_above"] * 10_000 + 1]
    if index:
        probes.append(bands[index - 1]["area_max"] * 10_000 + 0.01)
    for area in probes:
        limit, chosen = ground_triangle_limit(PROFILES.vpm, area)
        assert (limit, chosen) == (band["triangles_max"], band)
        assert _ground_tri_finding(limit, area=area).status == "pass"
        assert _ground_tri_finding(limit + 1, area=area).status == "fail"


def test_vpm_ground_limit_follows_the_standard_not_code():
    import copy
    from twinqa.scene import ground_triangle_limit
    profile = copy.deepcopy(PROFILES.vpm)
    profile["geometry"]["ground_triangles_max_by_area_ha"][3]["triangles_max"] = 1_234_567
    assert ground_triangle_limit(profile, 3431.5)[0] == 1_234_567
    assert _ground_tri_finding(1_234_568, area=3431.5, profile=profile).status == "fail"


@pytest.mark.parametrize("tris", [12, 10_000_000])
def test_vpm_ground_without_area_stays_review_naming_operand(tris):
    f = _ground_tri_finding(tris)
    assert f.status == "review"
    assert "ground_area_m2" in f.observed and "missing" in f.observed
    assert f.data == {"area_m2": None, "area_ha": None, "band": None,
                      "basis": PROFILES.vpm["geometry"]["ground_area_basis"]}


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1, 0, -0.0, True, "3431.5", [3431.5]])
def test_vpm_ground_area_invalid_is_an_error_never_pass(bad):
    from twinqa.scene import ground_triangle_limit
    with pytest.raises(ValueError, match="ground_area_m2"):
        ground_triangle_limit(PROFILES.vpm, bad)
    with pytest.raises(ValueError, match="ground_area_m2"):
        _ground_tri_finding(12, area=bad)


def _edge_cases():
    """(area_m2, expected band index) at nextafter below / exact / nextafter above every YAML edge."""
    from decimal import Decimal
    bands = _ground_bands()
    cases = []
    for i, band in enumerate(bands[:-1]):
        edge = float(Decimal(repr(band["area_max"])) * 10_000)  # exact decimal m2 edge (0.05 ha -> 500.0)
        cases += [(math.nextafter(edge, 0), i, "below"), (edge, i, "exact"), (math.nextafter(edge, math.inf), i + 1, "above")]
    return cases


@pytest.mark.parametrize("area, index, side", _edge_cases(),
                         ids=[f"{c[0]!r}-{c[2]}" for c in _edge_cases()])
def test_vpm_ground_band_edge_nextafter(area, index, side):
    """Review #516 P1: an area one ulp above an edge belongs to the next band (500.00000000000006 m2 ->
    705 000); a rounded ha quotient must not drop it into the lower band and fail a valid count."""
    from twinqa.scene import ground_triangle_limit
    band = _ground_bands()[index]
    assert ground_triangle_limit(PROFILES.vpm, area) == (band["triangles_max"], band)
    assert _ground_tri_finding(band["triangles_max"], area=area).status == "pass"
    assert _ground_tri_finding(band["triangles_max"] + 1, area=area).status == "fail"


@pytest.mark.parametrize("area, tris", [(500.00000000000006, 705_000), (1000.0000000000001, 1_125_000)])
def test_vpm_ground_review_witnesses_pass(area, tris):
    f = _ground_tri_finding(tris, area=area)
    assert (f.status, f.data["band"]["triangles_max"]) == ("pass", tris)
    assert (f.measured, f.threshold) == (tris, tris)


def test_vpm_ground_finding_data_survives_report_round_trip():
    """Finding.data (area operands) and measured/threshold/margin (#462) both serialise and load back."""
    from dataclasses import asdict
    from twinqa.report import Finding
    f = _ground_tri_finding(1_650_001, area=3431.5)
    back = Finding.from_dict(json.loads(json.dumps(asdict(f))))
    assert back == f and back.data["band"]["triangles_max"] == 1_650_000 and back.margin < 0
    with pytest.raises(ValueError, match="data"):
        Finding.from_dict({**asdict(f), "data": [1]})


def test_report_json_carries_data_only_when_present():
    """Full-suite witness after merging #462: findings without operands keep the old key set; the
    Ground finding carries `data` and loads back through ValidationReport.from_dict."""
    from twinqa.report import Stage, ValidationReport
    ground = _ground_tri_finding(1_650_001, area=3431.5)
    plain = _ground_tri_finding(12, kind="npm")
    report = ValidationReport("vpm", "x.fbx", "a" * 64, "b" * 64, True,
                              [Stage("V003", "geometry", "blocking", [28], [ground, plain])])
    found = report.to_dict()["stages"][0]["findings"]
    assert found[0]["data"]["band"]["triangles_max"] == 1_650_000 and "data" not in found[1]
    back = ValidationReport.from_dict(json.loads(json.dumps(report.to_dict())))
    assert back.stages[0].findings == [ground, plain]


@pytest.mark.parametrize("table", [
    None, [],
    [{"area_max": 0.1, "triangles_max": 1}, {"area_max": 0.05, "triangles_max": 2}],
    [{"area_max": 0.05, "triangles_max": 1}, {"area_above": 0.1, "triangles_max": 2}],
    [{"area_max": 0.05}],
    [{"area_max": 0.05, "triangles_max": 1}],
    [{"area_above": 0.05, "triangles_max": 1}, {"area_max": 0.1, "triangles_max": 2}],
    [{"area_max": float("nan"), "triangles_max": 1}, {"area_above": float("nan"), "triangles_max": 2}],
])
def test_vpm_ground_malformed_table_is_an_error_naming_the_key(table):
    import copy
    from twinqa.scene import ground_triangle_limit
    profile = copy.deepcopy(PROFILES.vpm)
    if table is None:
        del profile["geometry"]["ground_triangles_max_by_area_ha"]
    else:
        profile["geometry"]["ground_triangles_max_by_area_ha"] = table
    with pytest.raises(ValueError, match="ground_triangles_max_by_area_ha"):
        ground_triangle_limit(profile, 3431.5)


def test_vpm_ground_limit_brute_force_matches_decimal_reference():
    """Probe: 5 000 seeded areas (plus every edge +-1e-6 m2) against an independent Decimal reference;
    the limit never decreases with area."""
    from decimal import Decimal
    from twinqa.scene import ground_triangle_limit
    bands = _ground_bands()

    def reference(area_m2):
        ha = Decimal(repr(area_m2)) / 10_000
        for b in bands:
            if "area_max" in b and ha <= Decimal(repr(b["area_max"])):
                return b["triangles_max"]
        return bands[-1]["triangles_max"]

    rng = random.Random(510)
    areas = [rng.uniform(0.001, 30_000) for _ in range(5_000)]
    for b in bands:
        edge = b.get("area_max", b.get("area_above")) * 10_000
        areas += [edge - 1e-6, edge, edge + 1e-6]
    previous = 0
    for area in sorted(areas):
        limit = ground_triangle_limit(PROFILES.vpm, area)[0]
        assert limit == reference(area), area
        assert limit >= previous
        previous = limit


@pytest.mark.parametrize("tris, status", [(180_000, "pass"), (180_001, "fail")])
@pytest.mark.parametrize("area", [None, 3431.5])
def test_npm_ground_total_unchanged_by_area(tris, status, area):
    f = _ground_tri_finding(tris, kind="npm", area=area)
    assert f.status == status and f.data == {}


@pytest.mark.parametrize("tris, status", [(150_000, "pass"), (150_001, "review"), (1_000_001, "fail")])
def test_vpm_oks_limits_unchanged_by_area(tris, status):
    found = scene_findings(rb(mesh(tris=tris)), "vpm", "oks", PROFILES.vpm, ground_area_m2=3431.5)
    assert next(f for f in found["V003"] if f.name == "triangle count").status == status


def _ground_cli(monkeypatch, tmp_path, tris, *extra):
    fbx = tmp_path / "SM_Test_Ground.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00")
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(
        mesh(name="SM_Test_Ground", tris=tris), mesh(name="UCX_SM_Test_Ground_001", tris=4)))
    return vp.main([str(fbx), "--profile", "vpm", "--scene", "--json", *extra])


def _cli_triangle_finding(capsys):
    data = json.loads(capsys.readouterr().out)
    v003 = next(s for s in data["stages"] if s["id"] == "V003")
    return next(f for f in v003["findings"] if f["name"] == "triangle count")


@pytest.mark.parametrize("tris, status", [(1_650_000, "pass"), (1_650_001, "fail")])
def test_validate_package_cli_passes_ground_area(monkeypatch, tmp_path, capsys, tris, status):
    _ground_cli(monkeypatch, tmp_path, tris, "--ground-area-m2", "3431.50")
    f = _cli_triangle_finding(capsys)
    assert f["status"] == status
    assert f["data"]["area_m2"] == 3431.5 and f["data"]["band"]["triangles_max"] == 1_650_000


def test_validate_package_cli_without_area_is_review(monkeypatch, tmp_path, capsys):
    _ground_cli(monkeypatch, tmp_path, 10_000_000)
    f = _cli_triangle_finding(capsys)
    assert f["status"] == "review" and "ground_area_m2" in f["observed"]


@pytest.mark.parametrize("bad", ["nan", "inf", "-5", "0", "abc", ""])
def test_validate_package_cli_rejects_bad_area(monkeypatch, tmp_path, capsys, bad):
    with pytest.raises(SystemExit) as exc:
        _ground_cli(monkeypatch, tmp_path, 12, "--ground-area-m2", bad)
    assert exc.value.code == 2
    assert "--ground-area-m2" in capsys.readouterr().err


@pytest.mark.parametrize("profile, scene, unused", [("npm", False, True), ("vpm", False, True),
                                                     ("npm", True, False), ("vpm", True, False)])
def test_validate_package_unused_ground_area_is_noted(monkeypatch, tmp_path, profile, scene, unused):
    """The unused note stays on a header-only read. A --scene readback consumes the area
    (VPM triangle band, and footprint coverage on both profiles), so it must not say unused."""
    fbx = tmp_path / "SM_Test_Ground.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00")
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh(name="SM_Test_Ground", tris=12)))
    report = vp.validate(fbx, profile, PROFILES, scene=scene, ground_area_m2=3431.5)
    noted = any("ground_area_m2 3431.5 unused" in n for n in report.notes)
    assert noted is unused
    if scene:
        names = [finding.name for stage in report.stages for finding in stage.findings]
        assert "ground footprint coverage" in names


# --- #651: Ground readback footprint coverage (top-down area vs ground_area_m2) -------------------

VATUTINO_GROUND_M2 = 3431.50
FOOTPRINT_HOLE_M2 = 1670.09


def _ground_surface(name, rects):
    """One render mesh. ``rects`` are (x0, y0, x1, y1) on Z=0; area is the union of those rectangles."""
    vertices, polygons = [], []
    for x0, y0, x1, y1 in rects:
        base = len(vertices)
        vertices.extend([[x0, y0, 0.0], [x1, y0, 0.0], [x1, y1, 0.0], [x0, y1, 0.0]])
        polygons.extend([[base, base + 1, base + 2], [base, base + 2, base + 3]])
    item = mesh(name=name, tris=len(polygons), degrees={"3": len(polygons)})
    item["face_geometry"] = {"vertices": vertices, "polygons": polygons}
    return item


def _footprint_finding(rects, area=VATUTINO_GROUND_M2, kind="vpm", extra=(), source="C:/x/SM_Vatutino_Ground.fbx"):
    profile = PROFILES.vpm if kind == "vpm" else PROFILES.npm
    report = rb(_ground_surface("SM_Vatutino_Ground", rects), *extra)
    report["source"] = source
    found = scene_findings(report, kind, "ground", profile, ground_area_m2=area)
    return next(item for item in found["V003"] if item.name == "ground footprint coverage")


def _area_tol():
    from twinqa.scene import GROUND_AREA_TOL_M2
    return GROUND_AREA_TOL_M2


def test_vatutino_ground_area_within_tolerance_passes():
    """3431.50 m2 top-down rectangle matches ground_area_m2; the finding stores measured / expected / difference."""
    finding = _footprint_finding([(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    assert finding.status == "pass"
    assert finding.data["measured_m2"] == pytest.approx(VATUTINO_GROUND_M2, abs=1e-6)
    assert finding.data["expected_m2"] == VATUTINO_GROUND_M2
    assert finding.data["difference_m2"] == pytest.approx(0.0, abs=1e-6)
    assert "filled_absence_m2" not in finding.data
    observed = finding.observed
    assert "3431.5" in observed and "measured" in observed and "expected" in observed and "difference" in observed


def test_net_excess_of_1670_09_fails():
    """A +1670.09 m2 net excess fails the scalar area check. It is not a hole-coverage measurement."""
    finding = _footprint_finding([
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
        (VATUTINO_GROUND_M2, 0.0, VATUTINO_GROUND_M2 + FOOTPRINT_HOLE_M2, 1.0),
    ])
    assert finding.status == "fail"
    assert finding.data["measured_m2"] == pytest.approx(VATUTINO_GROUND_M2 + FOOTPRINT_HOLE_M2, abs=1e-4)
    assert finding.data["expected_m2"] == VATUTINO_GROUND_M2
    assert finding.data["difference_m2"] == pytest.approx(FOOTPRINT_HOLE_M2, abs=1e-4)
    assert "filled_absence_m2" not in finding.data
    assert "filled absence" not in finding.observed
    assert "1670.09" in finding.observed or "1670.090" in finding.observed


def test_half_square_metre_fill_above_tolerance_fails():
    finding = _footprint_finding([
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
        (VATUTINO_GROUND_M2, 0.0, VATUTINO_GROUND_M2 + 0.5, 1.0),
    ])
    assert finding.status == "fail"
    assert finding.data["difference_m2"] == pytest.approx(0.5, abs=1e-9)
    assert "filled_absence_m2" not in finding.data
    assert abs(finding.data["difference_m2"]) > _area_tol()


def test_ground_area_missing_is_not_run_never_pass():
    profile = PROFILES.vpm
    report = rb(_ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)]))
    found = scene_findings(report, "vpm", "ground", profile)
    finding = next(item for item in found["V003"] if item.name == "ground footprint coverage")
    assert finding.status == "not_run"
    assert finding.status != "pass"


def test_ground_without_face_data_is_not_run_never_pass():
    found = scene_findings(rb(mesh(name="SM_Vatutino_Ground"), mesh(name="UCX_SM_Vatutino_Ground_001", tris=4)),
                           "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    finding = next(item for item in found["V003"] if item.name == "ground footprint coverage")
    assert finding.status == "not_run"
    assert finding.status != "pass"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_ground_coordinates_fail(bad):
    item = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    item["face_geometry"]["vertices"][0][0] = bad
    found = scene_findings(rb(item), "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    finding = next(f for f in found["V003"] if f.name == "ground footprint coverage")
    assert finding.status == "fail"
    assert finding.status != "pass"


def test_empty_face_geometry_fails_closed():
    item = mesh(name="SM_Vatutino_Ground", tris=0, degrees={"3": 0})
    item["face_geometry"] = {"vertices": [], "polygons": []}
    found = scene_findings(rb(item), "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    finding = next(f for f in found["V003"] if f.name == "ground footprint coverage")
    assert finding.status == "fail"


def test_partial_face_geometry_fails_closed():
    faced = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    bare = mesh(name="SM_Vatutino_GroundGlass")
    found = scene_findings(rb(faced, bare), "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    finding = next(f for f in found["V003"] if f.name == "ground footprint coverage")
    assert finding.status == "fail"


def test_unsupported_face_geometry_fails_closed():
    item = mesh(name="SM_Vatutino_Ground")
    item["face_geometry"] = {"vertices": {"0": [0.0, 0.0, 0.0]}, "polygons": []}
    found = scene_findings(rb(item), "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    finding = next(f for f in found["V003"] if f.name == "ground footprint coverage")
    assert finding.status == "fail"


def test_exactly_at_area_tolerance_fails_closed():
    """|difference| == GROUND_AREA_TOL_M2 fails; the gate is strict so the threshold itself is not a pass."""
    tol = _area_tol()
    over = _footprint_finding([
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
        (VATUTINO_GROUND_M2, 0.0, VATUTINO_GROUND_M2 + tol, 1.0),
    ])
    under = _footprint_finding([(0.0, 0.0, VATUTINO_GROUND_M2 - tol, 1.0)])
    assert over.status == "fail" and over.data["difference_m2"] == pytest.approx(tol, abs=1e-9)
    assert under.status == "fail" and under.data["difference_m2"] == pytest.approx(-tol, abs=1e-9)
    assert "filled_absence_m2" not in over.data and "filled_absence_m2" not in under.data
    inside = _footprint_finding([
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
        (VATUTINO_GROUND_M2, 0.0, VATUTINO_GROUND_M2 + tol / 2, 1.0),
    ])
    assert inside.status == "pass"
    assert inside.data["difference_m2"] == pytest.approx(tol / 2, abs=1e-9)
    assert "filled_absence_m2" not in inside.data


def test_ucx_area_is_excluded_and_stacked_cover_does_not_double_count():
    ucx = _ground_surface("UCX_SM_Vatutino_Ground_001", [(0.0, 0.0, FOOTPRINT_HOLE_M2, 1.0)])
    finding = _footprint_finding([(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)], extra=(ucx,))
    assert finding.status == "pass"
    assert finding.data["measured_m2"] == pytest.approx(VATUTINO_GROUND_M2, abs=1e-6)
    stacked = _footprint_finding([
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
        (0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
    ])
    assert stacked.status == "pass"
    assert stacked.data["measured_m2"] == pytest.approx(VATUTINO_GROUND_M2, abs=1e-6)


def test_npm_ground_uses_the_same_area_when_provided():
    finding = _footprint_finding([(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)], kind="npm")
    assert finding.status == "pass"
    assert finding.data["difference_m2"] == pytest.approx(0.0, abs=1e-6)
    bare = scene_findings(rb(mesh(name="SM_Vatutino_Ground")), "npm", "ground", PROFILES.npm)
    assert next(item for item in bare["V003"] if item.name == "ground footprint coverage").status == "not_run"


def test_oks_does_not_grow_a_footprint_finding():
    item = _ground_surface("SM_Test_K_1_Main", [(0.0, 0.0, 10.0, 10.0)])
    found = scene_findings(rb(item), "vpm", "oks", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    assert "ground footprint coverage" not in {f.name for f in found["V003"]}


def test_fill_above_tolerance_never_passes():
    """Invariant: a rectangular fill whose area is above GROUND_AREA_TOL_M2 never passes.

    Each case builds a site rectangle with a rectangular hole (four non-overlapping pieces) and
    checks the holed mesh against site-minus-hole, then drops a fill strictly inside the hole.
    """
    tol = _area_tol()
    rng = random.Random(651)
    cases = 0
    for _ in range(24):
        site_w = rng.uniform(40.0, 90.0)
        site_h = rng.uniform(40.0, 90.0)
        inset = rng.uniform(2.0, 6.0)
        hole_w = site_w - 2 * inset
        hole_h = site_h - 2 * inset
        frame = [
            (0.0, 0.0, site_w, inset),
            (0.0, site_h - inset, site_w, site_h),
            (0.0, inset, inset, site_h - inset),
            (site_w - inset, inset, site_w, site_h - inset),
        ]
        expected = site_w * site_h - hole_w * hole_h
        holed = _footprint_finding(frame, area=expected)
        assert holed.status == "pass", holed.data
        assert holed.data["measured_m2"] == pytest.approx(expected, abs=1e-4)
        fill_w = min(hole_w * 0.5, tol + rng.uniform(0.02, 2.0))
        fill_h = 1.0
        if fill_w * fill_h <= tol:
            fill_h = (tol / fill_w) + rng.uniform(0.05, 0.5)
        assert fill_w * fill_h > tol and fill_w < hole_w and fill_h < hole_h
        filled_rects = frame + [(inset, inset, inset + fill_w, inset + fill_h)]
        filled = _footprint_finding(filled_rects, area=expected)
        assert filled.status == "fail"
        assert filled.data["difference_m2"] == pytest.approx(fill_w * fill_h, abs=1e-4)
        assert filled.data["difference_m2"] > tol
        assert "filled_absence_m2" not in filled.data
        cases += 1
    assert cases == 24


# --- #651 review: spatial footprint-hole coverage, independent of net area -----------------------

FRAME_AREA_M2 = 3600.0


def _frame_rects():
    """100x100 frame with the open rectangle (10,10)-(90,90). Union area is 3600 m2."""
    return [
        (0.0, 0.0, 100.0, 10.0),
        (0.0, 90.0, 100.0, 100.0),
        (0.0, 10.0, 10.0, 90.0),
        (90.0, 10.0, 100.0, 90.0),
    ]


def _frame_hole_ring():
    return [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)]


def _witness_rects():
    """Same frame, minus (0,0)-(0.05,10) outside the hole, plus (10,10)-(10.5,11) inside it.

    Both patches are 0.5 m2, so the net top-down area stays 3600 m2.
    """
    rects = _frame_rects()
    rects[0] = (0.05, 0.0, 100.0, 10.0)
    rects.append((10.0, 10.0, 10.5, 11.0))
    return rects


def _coverage_findings(rects, area, holes, kind="vpm", extra=(), source="C:/x/SM_Frame_Ground.fbx"):
    profile = PROFILES.vpm if kind == "vpm" else PROFILES.npm
    report = rb(_ground_surface("SM_Frame_Ground", rects), *extra)
    report["source"] = source
    found = scene_findings(report, kind, "ground", profile, ground_area_m2=area, footprint_holes=holes)
    area_finding = next(item for item in found["V003"] if item.name == "ground footprint coverage")
    hole_finding = next(item for item in found["V003"] if item.name == "ground footprint hole coverage")
    return area_finding, hole_finding


def _assert_no_filled_absence_name(finding):
    blob = " ".join([finding.name, finding.observed, finding.expected, " ".join(finding.data)])
    assert "filled_absence" not in blob
    assert "filled absence" not in blob


def test_651_compensated_frame_hole_fill_fails():
    """100x100 frame, hole (10,10)-(90,90). Losing 0.5 m2 outside and covering 0.5 m2 inside
    keeps the net area at 3600. The hole-coverage finding still fails."""
    area_finding, hole_finding = _coverage_findings(_witness_rects(), FRAME_AREA_M2, [_frame_hole_ring()])
    assert area_finding.status == "pass"
    assert area_finding.data["measured_m2"] == pytest.approx(FRAME_AREA_M2, abs=1e-4)
    assert area_finding.data["difference_m2"] == pytest.approx(0.0, abs=1e-4)
    assert hole_finding.status == "fail"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(0.5, abs=1e-6)
    assert hole_finding.data["hole_coverage_m2"] > _area_tol()
    _assert_no_filled_absence_name(area_finding)
    _assert_no_filled_absence_name(hole_finding)


@pytest.mark.parametrize("kind", ["vpm", "npm"])
def test_651_clean_frame_hole_coverage_passes(kind):
    area_finding, hole_finding = _coverage_findings(_frame_rects(), FRAME_AREA_M2, [_frame_hole_ring()], kind=kind)
    assert area_finding.status == "pass"
    assert area_finding.data["difference_m2"] == pytest.approx(0.0, abs=1e-4)
    assert hole_finding.status == "pass"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(0.0, abs=1e-6)
    _assert_no_filled_absence_name(hole_finding)


def test_651_negative_face_indices_fail():
    """The 3431.50 m2 quad addressed as [-4,-3,-2] / [-4,-2,-1] is the same two triangles.
    Negative indices are a broken readback and fail closed."""
    item = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    assert item["face_geometry"]["polygons"] == [[0, 1, 2], [0, 2, 3]]
    item["face_geometry"]["polygons"] = [[-4, -3, -2], [-4, -2, -1]]
    finding = _footprint_finding_from(item)
    assert finding.status == "fail"
    assert "negative face index" in finding.observed


def test_651_polygon_with_fewer_than_3_indices_fails():
    item = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    item["face_geometry"]["polygons"].append([0, 1])
    finding = _footprint_finding_from(item)
    assert finding.status == "fail"
    assert "fewer than 3 indices" in finding.observed


def test_651_vertex_missing_z_fails():
    item = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    item["face_geometry"]["vertices"] = [vertex[:2] for vertex in item["face_geometry"]["vertices"]]
    finding = _footprint_finding_from(item)
    assert finding.status == "fail"
    assert "missing Z" in finding.observed


def test_651_out_of_range_face_index_fails():
    item = _ground_surface("SM_Vatutino_Ground", [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0)])
    item["face_geometry"]["polygons"] = [[0, 1, 99]]
    finding = _footprint_finding_from(item)
    assert finding.status == "fail"
    assert "out-of-range face index" in finding.observed


def test_651_compensated_hole_fill_with_short_polygon_fails():
    """The area-compensated witness plus a polygon [0, 1] fails both findings by name.
    A short polygon must not be skipped so the compensated fill can pass."""
    item = _ground_surface("SM_Frame_Ground", _witness_rects())
    item["face_geometry"]["polygons"].append([0, 1])
    report = rb(item)
    report["source"] = "C:/x/SM_Frame_Ground.fbx"
    found = scene_findings(report, "vpm", "ground", PROFILES.vpm,
                           ground_area_m2=FRAME_AREA_M2, footprint_holes=[_frame_hole_ring()])
    area_finding = next(item for item in found["V003"] if item.name == "ground footprint coverage")
    hole_finding = next(item for item in found["V003"] if item.name == "ground footprint hole coverage")
    assert area_finding.status == "fail" and "fewer than 3 indices" in area_finding.observed
    assert hole_finding.status == "fail" and "fewer than 3 indices" in hole_finding.observed


def test_651_hole_coverage_exactly_at_tolerance_fails_closed():
    """Coverage equal to GROUND_AREA_TOL_M2 fails. Half of that, with the same area removed
    outside the hole, passes. The scalar net stays inside the tolerance either way."""
    tol = _area_tol()
    area_finding, hole_finding = _coverage_findings(
        _compensated_fill_rects(tol), FRAME_AREA_M2, [_frame_hole_ring()])
    assert area_finding.status == "pass"
    assert hole_finding.status == "fail"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(tol, abs=1e-6)
    under_area, under_hole = _coverage_findings(
        _compensated_fill_rects(tol / 2), FRAME_AREA_M2, [_frame_hole_ring()])
    assert under_area.status == "pass"
    assert under_hole.status == "pass"
    assert under_hole.data["hole_coverage_m2"] == pytest.approx(tol / 2, abs=1e-6)


def test_651_spatial_check_without_hole_reference_is_not_run():
    """No hole polygon: the scalar check still runs; the hole check is not_run and never a pass."""
    area_finding, hole_finding = _coverage_findings(
        [(0.0, 0.0, VATUTINO_GROUND_M2, 1.0),
         (VATUTINO_GROUND_M2, 0.0, VATUTINO_GROUND_M2 + 0.5, 1.0)],
        VATUTINO_GROUND_M2, None)
    assert area_finding.status == "fail"
    assert area_finding.data["difference_m2"] == pytest.approx(0.5, abs=1e-6)
    assert "filled_absence_m2" not in area_finding.data
    assert hole_finding.status == "not_run"
    assert hole_finding.status != "pass"
    _assert_no_filled_absence_name(area_finding)
    _assert_no_filled_absence_name(hole_finding)


def test_651_hole_coverage_without_ground_area_still_fails_the_fill():
    report = rb(_ground_surface("SM_Frame_Ground", _witness_rects()))
    report["source"] = "C:/x/SM_Frame_Ground.fbx"
    found = scene_findings(report, "vpm", "ground", PROFILES.vpm, footprint_holes=[_frame_hole_ring()])
    area_finding = next(item for item in found["V003"] if item.name == "ground footprint coverage")
    hole_finding = next(item for item in found["V003"] if item.name == "ground footprint hole coverage")
    assert area_finding.status == "not_run"
    assert hole_finding.status == "fail"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(0.5, abs=1e-6)


def test_651_hole_check_without_face_data_is_not_run():
    found = scene_findings(rb(mesh(name="SM_Vatutino_Ground")), "vpm", "ground", PROFILES.vpm,
                           ground_area_m2=VATUTINO_GROUND_M2, footprint_holes=[_frame_hole_ring()])
    hole_finding = next(item for item in found["V003"] if item.name == "ground footprint hole coverage")
    assert hole_finding.status == "not_run"
    assert hole_finding.status != "pass"


def test_651_ucx_inside_hole_does_not_count():
    ucx = _ground_surface("UCX_SM_Frame_Ground_001", [(10.0, 10.0, 20.0, 20.0)])
    area_finding, hole_finding = _coverage_findings(
        _frame_rects(), FRAME_AREA_M2, [_frame_hole_ring()], extra=(ucx,))
    assert area_finding.status == "pass"
    assert hole_finding.status == "pass"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(0.0, abs=1e-6)


def test_651_malformed_hole_reference_fails():
    _area_finding, hole_finding = _coverage_findings(
        _frame_rects(), FRAME_AREA_M2, [[(0.0, 0.0), (1.0, 0.0)]])
    assert hole_finding.status == "fail"
    assert "footprint hole ring has fewer than 3 points" in hole_finding.observed


def test_651_validate_package_passes_footprint_holes(monkeypatch, tmp_path):
    fbx = tmp_path / "SM_Frame_Ground.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00")
    item = _ground_surface("SM_Frame_Ground", _witness_rects())
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(item))
    report = vp.validate(fbx, "vpm", PROFILES, scene=True, ground_area_m2=FRAME_AREA_M2,
                         footprint_holes=[_frame_hole_ring()])
    findings = [finding for stage in report.stages for finding in stage.findings]
    hole_finding = next(finding for finding in findings if finding.name == "ground footprint hole coverage")
    assert hole_finding.status == "fail"
    assert hole_finding.data["hole_coverage_m2"] == pytest.approx(0.5, abs=1e-6)


def test_651_hole_fill_above_tolerance_never_passes():
    """Invariant: Ground coverage inside the footprint hole above GROUND_AREA_TOL_M2 never passes.

    Each case also removes a slightly larger patch outside the hole, so the scalar net
    difference stays inside the tolerance and would pass on its own.
    """
    tol = _area_tol()
    rng = random.Random(651)
    cases = 0
    for _ in range(24):
        site_w = rng.uniform(40.0, 90.0)
        site_h = rng.uniform(40.0, 90.0)
        inset = rng.uniform(3.0, 8.0)
        hole_w = site_w - 2 * inset
        hole_h = site_h - 2 * inset
        frame = [
            (0.0, 0.0, site_w, inset),
            (0.0, site_h - inset, site_w, site_h),
            (0.0, inset, inset, site_h - inset),
            (site_w - inset, inset, site_w, site_h - inset),
        ]
        expected = site_w * site_h - hole_w * hole_h
        ring = [
            (inset, inset),
            (site_w - inset, inset),
            (site_w - inset, site_h - inset),
            (inset, site_h - inset),
        ]
        _clean_area, clean_hole = _coverage_findings(frame, expected, [ring])
        assert clean_hole.status == "pass"
        assert clean_hole.data["hole_coverage_m2"] == pytest.approx(0.0, abs=1e-4)
        max_w = hole_w - 0.4
        max_h = hole_h - 0.4
        fill_w = min(max_w, rng.uniform(0.4, 2.5))
        fill_h = min(max_h, (tol / fill_w) + rng.uniform(0.05, 0.8))
        if fill_w * fill_h <= tol:
            fill_h = min(max_h, (tol / fill_w) + 0.05)
        assert fill_w * fill_h > tol
        assert fill_w < max_w and fill_h < max_h
        fill = (inset + 0.1, inset + 0.1, inset + 0.1 + fill_w, inset + 0.1 + fill_h)
        removed = fill_w * fill_h + rng.uniform(0.01, 0.05)
        cut_h = min(inset * 0.5, 1.0)
        cut_w = removed / cut_h
        if cut_w >= site_w * 0.9:
            cut_h = removed / (site_w * 0.5)
            cut_w = removed / cut_h
        assert 0.0 < cut_h < inset and 0.0 < cut_w < site_w
        mutated = [
            (cut_w, 0.0, site_w, cut_h),
            (0.0, cut_h, site_w, inset),
            frame[1], frame[2], frame[3],
            fill,
        ]
        area_finding, hole_finding = _coverage_findings(mutated, expected, [ring])
        assert hole_finding.status == "fail"
        assert hole_finding.data["hole_coverage_m2"] == pytest.approx(fill_w * fill_h, abs=1e-3)
        assert hole_finding.data["hole_coverage_m2"] > tol
        assert area_finding.status == "pass"
        assert "filled absence" not in hole_finding.observed
        cases += 1
    assert cases == 24


def _footprint_finding_from(item):
    found = scene_findings(rb(item), "vpm", "ground", PROFILES.vpm, ground_area_m2=VATUTINO_GROUND_M2)
    return next(finding for finding in found["V003"] if finding.name == "ground footprint coverage")


def _compensated_fill_rects(fill_area):
    """Frame plus a fill_area patch inside the hole and the same area removed from the outer strip."""
    rects = _frame_rects()
    cut_w = fill_area / 10.0
    rects[0] = (cut_w, 0.0, 100.0, 10.0)
    rects.append((10.0, 10.0, 10.0 + fill_area, 11.0))
    return rects
