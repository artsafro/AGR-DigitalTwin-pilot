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


def mesh(name="SM_Test_K_1_Main", tris=12, degrees=None, rot=(0, 0, 0), scale=(1, 1, 1), uv=1, mirrored=0,
         tiles=(1001,), loc=(0, 0, 0), materials=()):
    return {"name": name, "triangles": tris, "polygon_degrees": degrees or {"3": tris}, "rotation_euler_deg": list(rot),
            "scale": list(scale), "uv_channels": uv, "mirrored_uv_triangles": mirrored, "udim_tiles": list(tiles),
            "location": list(loc), "materials": list(materials)}


UCX = "UCX_SM_Test_K_1_Main_001"


def rb(*meshes, other=()):
    return {"source": "C:/x/SM_Test_K_1.fbx", "readback_ok": True, "meshes": list(meshes),
            "other_objects": list(other), "images": []}


def statuses(found, stage):
    return {f.name: f.status for f in found[stage]}


def test_clean_vpm_mesh_passes_scene_stages():
    found = scene_findings(rb(mesh()), "vpm", "oks", PROFILES.vpm)
    assert set(statuses(found, "V003").values()) == {"pass"}
    assert statuses(found, "V004") == {"applied transforms": "pass"}
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
    assert statuses(found, "V010") == {"UCX present": "pass", "UCX material slots": "pass",
                                       "UCX triangle budget": "fail", "UCX shape and coverage": "not_run"}


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
    assert result == expected_data


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
        assert {st[k].status for k in ("V003", "V004")} == {"pass"}
        assert st["V008"].status == "pass"
    else:
        assert st["V003"].status == "fail" and st["V008"].status == "fail"
        assert report.exit_code == 1
