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


@pytest.mark.parametrize("profile, scene", [("npm", True), ("vpm", False)])
def test_validate_package_unused_ground_area_is_noted(monkeypatch, tmp_path, profile, scene):
    fbx = tmp_path / "SM_Test_Ground.fbx"
    fbx.write_bytes(b"Kaydara FBX Binary  \x00")
    monkeypatch.setattr(vp, "readback", lambda path, blender=None, timeout=600: rb(mesh(name="SM_Test_Ground", tris=12)))
    report = vp.validate(fbx, profile, PROFILES, scene=scene, ground_area_m2=3431.5)
    assert any("ground_area_m2 3431.5 unused" in n for n in report.notes)
