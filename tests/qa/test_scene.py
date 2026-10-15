"""Scene stages from the Blender readback: rule logic on fixed readbacks, plus a real
background-Blender roundtrip (skipped when Blender is not installed)."""
import json
import random
import subprocess
import zipfile
from pathlib import Path

import pytest

import validate_package as vp
from test_validator import PROFILES, STEM, good_files
from twinqa.geometry.ucx_audit import TOUCH_M
from twinqa.scene import find_blender, readback, scene_findings, ucx_triangle_limit

BOX_TRIS = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
            (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]


def mesh(name="SM_Test_K_1_Main", tris=12, degrees=None, rot=(0, 0, 0), scale=(1, 1, 1), uv=1, mirrored=0,
         tiles=(1001,), loc=(0, 0, 0)):
    return {"name": name, "triangles": tris, "polygon_degrees": degrees or {"3": tris}, "rotation_euler_deg": list(rot),
            "scale": list(scale), "uv_channels": uv, "mirrored_uv_triangles": mirrored, "udim_tiles": list(tiles),
            "location": list(loc)}


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
    assert statuses(found, "V010") == {"UCX triangle budget": "fail", "UCX shape and coverage": "not_run",
                                       "UCX intersections": "not_run", "UCX piece gap (advisory)": "not_run"}


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
    if abs(abs(signed) - TOUCH_M) >= 1e-6:
        assert (st["UCX intersections"] == "fail") is (signed < -TOUCH_M)


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


MAKE_UCX = """
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
                    "--python-expr", MAKE_UCX, "--", str(fbx_path), variant],
                   check=True, capture_output=True, timeout=300)
    report = readback(fbx_path)
    ucx = [m for m in report["meshes"] if m["name"].upper().startswith("UCX_")]
    other = [m for m in report["meshes"] if not m["name"].upper().startswith("UCX_")]
    assert ucx and all("hull" in m and m["hull"]["verts"] and m["hull"]["tris"] for m in ucx)
    assert other and all("hull" not in m for m in other)
    st = statuses(scene_findings(report, "vpm", "oks", PROFILES.vpm), "V010")
    assert st["UCX intersections"] == ("fail" if variant == "overlap" else "pass")
