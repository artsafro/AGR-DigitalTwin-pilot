"""Synthetic tests for tools/library/maf_site_set.py (#313)."""

import importlib.util
import math
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "tools" / "library" / "maf_site_set.py"
    spec = importlib.util.spec_from_file_location("maf_site_set", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mss = _load()


# --- dimension verdict [D094] -------------------------------------------------

def test_dimension_pass_within_tolerance():
    out = mss.dimension_verdict([1.80, 0.47, 0.80], [1.8, 0.5, 0.72])
    assert out["verdict"] == "pass"
    assert out["plan_axes_swapped"] is False


def test_dimension_plan_swap_allowed_height_not():
    out = mss.dimension_verdict([0.5, 1.8, 0.72], [1.8, 0.5, 0.72])
    assert out["verdict"] == "pass" and out["plan_axes_swapped"] is True
    out = mss.dimension_verdict([1.8, 0.72, 0.5], [1.8, 0.5, 0.72])
    assert out["verdict"] == "fail"


def test_dimension_fail_over_tolerance():
    out = mss.dimension_verdict([1.708, 1.999, 2.387], [1.09, 1.09, None])
    assert out["verdict"] == "fail"


def test_dimension_missing_size_is_review_not_pass():
    out = mss.dimension_verdict([1.0, 1.0, 0.5], [1.0, 1.0, None])
    assert out["verdict"] == "review"


def test_dimension_user_exception_turns_fail_into_review_with_reason():
    out = mss.dimension_verdict([1.708, 1.999, 2.387], [1.09, 1.09, None], exception="Q8 seat diameter")
    assert out["verdict"] == "review"
    assert "Q8" in out["reason"]
    # an exception never upgrades to pass
    out = mss.dimension_verdict([1.09, 1.09, 1.0], [1.09, 1.09, 1.0], exception="x")
    assert out["verdict"] == "review"


def test_dimension_exactly_at_threshold_is_pass_like_maf_checks():
    out = mss.dimension_verdict([1.1, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert out["verdict"] == "pass"
    out = mss.dimension_verdict([1.1001, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert out["verdict"] == "fail"


@pytest.mark.parametrize("bad", [[1, 1], [1, 1, float("nan")], [1, 1, float("inf")], [1, -1, 1],
                                 [1, 1, 0], None, [True, 1, 1], "abc"])
def test_dimension_bad_measured_raises(bad):
    with pytest.raises(ValueError):
        mss.dimension_verdict(bad, [1, 1, 1])


@pytest.mark.parametrize("bad", [[1, 1], [1, float("nan"), 1], [1, 0, 1], [None, None, None]])
def test_dimension_bad_schedule_raises(bad):
    with pytest.raises(ValueError):
        mss.dimension_verdict([1, 1, 1], bad)


def test_dimension_probe_random_never_pass_beyond_tolerance():
    rng = random.Random(313)
    for _ in range(2000):
        spec = [rng.uniform(0.2, 5) for _ in range(3)]
        meas = [s + rng.uniform(-0.3, 0.3) for s in spec]
        meas = [max(m, 0.01) for m in meas]
        if rng.random() < 0.5:
            meas[0], meas[1] = meas[1], meas[0]
        out = mss.dimension_verdict(meas, spec)
        plan_ok = min(
            max(abs(meas[0] - spec[0]), abs(meas[1] - spec[1])),
            max(abs(meas[1] - spec[0]), abs(meas[0] - spec[1])),
        ) <= 0.1 + 1e-9
        ok = plan_ok and abs(meas[2] - spec[2]) <= 0.1 + 1e-9
        assert (out["verdict"] == "pass") == ok


# --- budget [D097] -----------------------------------------------------------

def _row(pid, raw, npm, vpm, n):
    return {"set_id": pid, "tris_raw": raw, "tris_npm": npm, "tris_vpm": vpm, "instances": n}


def test_budget_totals_and_under_share():
    out = mss.budget([_row("a", 100, 50, 100, 4), _row("b", 10, 10, 10, 1)], npm_share=1000)
    assert out["npm_total"] == 210 and out["vpm_total"] == 410 and out["raw_total"] == 410
    assert out["npm_within_share"] is True and out["overrun"] == []


def test_budget_at_share_is_within_and_over_lists_causes():
    out = mss.budget([_row("a", 10, 10, 10, 100)], npm_share=1000)
    assert out["npm_within_share"] is True
    out = mss.budget([_row("a", 10, 10, 10, 100), _row("b", 1, 1, 1, 1)], npm_share=1000)
    assert out["npm_within_share"] is False
    assert out["overrun"][0]["set_id"] == "a" and out["overrun_tris"] == 1


@pytest.mark.parametrize("bad", [[], [_row("a", -1, 1, 1, 1)], [_row("a", 1, 1.5, 1, 1)],
                                 [_row("a", 1, 1, 1, True)], [_row("a", 1, None, 1, 1)],
                                 [{"set_id": "a"}]])
def test_budget_bad_input_raises(bad):
    with pytest.raises(ValueError):
        mss.budget(bad, npm_share=60000)


# --- UV inside the material slot -------------------------------------------

RECTS = {"steel": [0.0, 0.0, 0.25, 0.25], "wood": [0.5, 0.5, 0.75, 0.75]}


def test_uv_inside_and_outside_counted_per_material():
    faces = [("steel", [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("wood", [(0.6, 0.6), (0.7, 0.6), (0.8, 0.7)]),
             ("wood", [(0.6, 0.6), (0.7, 0.6), (0.7, 0.7)])]
    out = mss.uv_slot_report(faces, RECTS)
    assert out["faces_outside"] == 1
    assert out["materials"]["steel"]["outside"] == 0
    assert out["materials"]["wood"]["faces"] == 2 and out["materials"]["wood"]["outside"] == 1


def test_uv_boundary_inside_unknown_and_nan_outside():
    faces = [("steel", [(0.0, 0.0), (0.25, 0.25), (0.0, 0.25)]),
             ("glass", [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("steel", [(float("nan"), 0.1), (0.2, 0.1), (0.2, 0.2)]),
             (None, [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]),
             ("steel", [])]
    out = mss.uv_slot_report(faces, RECTS)
    assert out["materials"]["steel"]["outside"] == 2
    assert out["materials"]["glass"]["outside"] == 1
    assert out["materials"]["None"]["outside"] == 1
    assert out["faces_outside"] == 4


def test_uv_empty_raises():
    with pytest.raises(ValueError):
        mss.uv_slot_report([], RECTS)


def test_uv_probe_random():
    rng = random.Random(7)
    faces, expected = [], 0
    for _ in range(3000):
        name = rng.choice(["steel", "wood"])
        u0, v0, u1, v1 = RECTS[name]
        pts = []
        bad = False
        for _ in range(3):
            u, v = rng.uniform(-0.1, 1.1), rng.uniform(-0.1, 1.1)
            pts.append((u, v))
            bad |= not (u0 - 1e-9 <= u <= u1 + 1e-9 and v0 - 1e-9 <= v <= v1 + 1e-9)
        expected += bad
        faces.append((name, pts))
    assert mss.uv_slot_report(faces, RECTS)["faces_outside"] == expected


def test_remap_into_rect_stays_inside():
    rng = random.Random(1)
    for _ in range(500):
        t = (rng.random(), rng.random())
        u, v = mss.remap_into_rect(t, RECTS["wood"])
        assert 0.5 <= u <= 0.75 and 0.5 <= v <= 0.75
    with pytest.raises(ValueError):
        mss.remap_into_rect((1.5, 0.5), RECTS["wood"])
    with pytest.raises(ValueError):
        mss.remap_into_rect((float("nan"), 0.5), RECTS["wood"])


# --- dominant upward plane (table-top height) -------------------------------

def test_dominant_up_plane_picks_largest_area():
    faces = [(0.76, 2.0, 1.0), (0.761, 2.1, 1.0), (0.91, 0.3, 1.0), (0.0, 5.0, -1.0), (0.4, 9.0, 0.2)]
    z = mss.dominant_up_plane(faces)
    assert math.isclose(z, 0.76, abs_tol=0.005)


def test_dominant_up_plane_none_up_raises():
    with pytest.raises(ValueError):
        mss.dominant_up_plane([(0.0, 1.0, -1.0)])
    with pytest.raises(ValueError):
        mss.dominant_up_plane([])


# --- outward orientation (mirrors twinqa.geometry.maf_surface) ---------------

CUBE_V = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)]
CUBE_F = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]


def _facts(coords, polys):
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from twinqa.geometry.maf_surface import surface_facts
    normals = [[[0.0, 0.0, 1.0]] * len(p) for p in polys]
    return surface_facts([list(c) for c in coords], polys, normals)


def _apply(polys, flips):
    return [list(reversed(p)) if i in flips else list(p) for i, p in enumerate(polys)]


def test_orient_outward_cube_ok_needs_no_flip():
    assert mss.orient_outward(CUBE_V, CUBE_F) == set()


def test_orient_outward_fixes_one_flipped_face_and_inverted_cube():
    bad = _apply(CUBE_F, {2})
    flips = mss.orient_outward(CUBE_V, bad)
    fixed = _apply(bad, flips)
    facts = _facts(CUBE_V, fixed)
    assert facts["flipped_faces"] == 0 and facts["inconsistent_edges"] == 0
    inverted = _apply(CUBE_F, set(range(6)))
    assert mss.orient_outward(CUBE_V, inverted) == set(range(6))


def test_orient_outward_probe_random_flips_two_cubes():
    rng = random.Random(42)
    coords = CUBE_V + [(x + 3, y, z) for x, y, z in CUBE_V]
    polys = CUBE_F + [[i + 8 for i in f] for f in CUBE_F]
    for _ in range(200):
        bad = _apply(polys, {i for i in range(12) if rng.random() < 0.5})
        fixed = _apply(bad, mss.orient_outward(coords, bad))
        facts = _facts(coords, fixed)
        assert facts["flipped_faces"] == 0 and facts["inconsistent_edges"] == 0


def test_orient_outward_flat_component_untouched():
    coords = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    assert mss.orient_outward(coords, [[0, 1, 2, 3]]) == set()


# --- material-map coverage (review round 1, P1) ---------------------------------

ATLAS_NAMES = ["steel", "wood"]


def test_material_map_complete_resolves_every_source():
    got = mss.resolve_material_map(["1", "2"], {"1": "wood", "2": "steel"}, ATLAS_NAMES)
    assert got == {"1": "wood", "2": "steel"}


def test_material_map_missing_source_without_wildcard_raises_and_names_it():
    with pytest.raises(mss.MaterialMapError) as err:
        mss.resolve_material_map(["1", "2"], {"not_present_in_source": "wood"}, ATLAS_NAMES)
    assert err.value.missing == ["1", "2"]
    assert "1" in str(err.value) and "2" in str(err.value)


def test_material_map_explicit_wildcard_covers_the_rest():
    got = mss.resolve_material_map(["1", "2", "None"], {"1": "wood", "*": "steel"}, ATLAS_NAMES)
    assert got == {"1": "wood", "2": "steel", "None": "steel"}


def test_material_map_unknown_target_raises():
    with pytest.raises(mss.MaterialMapError) as err:
        mss.resolve_material_map(["1"], {"1": "gold"}, ATLAS_NAMES)
    assert err.value.unknown_targets == ["gold"]
    with pytest.raises(mss.MaterialMapError):
        mss.resolve_material_map(["1"], {"1": "wood", "*": "gold"}, ATLAS_NAMES)


def test_material_map_empty_sources_raises():
    with pytest.raises(mss.MaterialMapError):
        mss.resolve_material_map([], {"*": "wood"}, ATLAS_NAMES)


# --- real builder, synthetic two-material cube (Blender, opt-in) ---------------

import json  # noqa: E402
import subprocess  # noqa: E402

from twinqa.scene import find_blender  # noqa: E402

BLENDER = find_blender()
BUILDER = ROOT / "tools" / "blender" / "maf_site_set_build.py"
_SYNTH = """
import bpy, sys
fbx, png = sys.argv[sys.argv.index('--') + 1:]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1)
o = bpy.context.active_object
for n in ('src_wood', 'src_steel'):
    o.data.materials.append(bpy.data.materials.new(n))
for p in o.data.polygons:
    p.material_index = 0 if p.normal.z > 0.5 else 1
bpy.ops.export_scene.fbx(filepath=fbx, use_selection=True)
img = bpy.data.images.new('atlas', 8, 8)
img.filepath_raw = png
img.file_format = 'PNG'
img.save()
"""


def _synthetic(tmp_path):
    src = tmp_path / "out" / "src"
    src.mkdir(parents=True)
    png = tmp_path / "atlas.png"
    subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                    "--python-expr", _SYNTH, "--", str(src / "synth.fbx"), str(png)],
                   check=True, capture_output=True, timeout=300)
    atlas = {"materials": {"steel": {"uv": [0.0, 0.0, 0.5, 0.5]}, "wood": {"uv": [0.5, 0.5, 1.0, 1.0]}}}
    (tmp_path / "atlas.json").write_text(json.dumps(atlas), encoding="utf-8")
    return png


def _run_builder(tmp_path, png, material_map):
    pos = {"set_id": "SYN_01", "catalogue_id": "MAF_9999", "source_fbx": "C:/nowhere/synth.fbx",
           "decimate_ratio": 1.0, "material_map": material_map, "smoothing_deg": 40.0, "height_rule": "max"}
    (tmp_path / "cfg.json").write_text(json.dumps({"smoothing_deg": 40.0, "positions": [pos]}), encoding="utf-8")
    out = tmp_path / "out"
    proc = subprocess.run([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1",
                           "--python", str(BUILDER), "--", str(tmp_path / "cfg.json"), str(tmp_path / "atlas.json"),
                           str(png), str(out)], capture_output=True, text=True, timeout=600)
    return proc, out


def _materials(report, role):
    return {k: v["faces"] for k, v in report["positions"][0][role]["readback"]["uv_slots"]["materials"].items()}


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_builder_rejects_missing_material_map_before_export(tmp_path):
    png = _synthetic(tmp_path)
    proc, out = _run_builder(tmp_path, png, {"not_present_in_source": "wood"})
    assert proc.returncode != 0
    assert "src_wood" in proc.stderr and "src_steel" in proc.stderr
    assert not (out / "npm").exists() and not (out / "vpm").exists()
    assert not (out / "build-report.json").exists()


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_builder_complete_map_keeps_identities_and_slots(tmp_path):
    png = _synthetic(tmp_path)
    proc, out = _run_builder(tmp_path, png, {"src_wood": "wood", "src_steel": "steel"})
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads((out / "build-report.json").read_text(encoding="utf-8"))
    for role in ("npm", "vpm"):
        assert _materials(report, role) == {"wood": 2, "steel": 10}  # top quad = 2 tris, rest steel
        assert report["positions"][0][role]["readback"]["uv_slots"]["faces_outside"] == 0
        assert report["positions"][0][role]["wildcard_faces"] == 0


@pytest.mark.blender
@pytest.mark.skipif(BLENDER is None, reason="Blender not installed")
def test_builder_explicit_wildcard_maps_the_rest_on_purpose(tmp_path):
    png = _synthetic(tmp_path)
    proc, out = _run_builder(tmp_path, png, {"src_wood": "wood", "*": "wood"})
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads((out / "build-report.json").read_text(encoding="utf-8"))
    for role in ("npm", "vpm"):
        assert _materials(report, role) == {"wood": 12}
        assert report["positions"][0][role]["wildcard_faces"] == 10
