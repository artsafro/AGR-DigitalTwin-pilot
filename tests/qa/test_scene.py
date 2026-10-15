"""Scene stages from the Blender readback: rule logic on fixed readbacks, plus a real
background-Blender roundtrip (skipped when Blender is not installed)."""
import json
import math
import random
import subprocess
import zipfile
from pathlib import Path

import pytest

import validate_package as vp
from test_validator import PROFILES, STEM, good_files
from twinqa.scene import OVERLAP_EPS_M, find_blender, readback, scene_findings, ucx_triangle_limit

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
                                       "UCX intersections": "not_run", "UCX intersections coverage": "not_run",
                                       "UCX piece gap (advisory)": "not_run"}


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
