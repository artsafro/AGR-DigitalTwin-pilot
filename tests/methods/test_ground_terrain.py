"""ground-terrain class metrics and variant meshers on a tiny synthetic input (#733).

Pattern: new-case: tests of the ground-terrain methods class (flat plane with one square hole, shifted surface,
null-with-reason paths, placement sidecars, CLI row, RESULTS.md columns, variant meshers).
"""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pytest

from tests.methods.test_methods_catalog import TOOLS, _load, last_row, mesh, rmd, rv

mm = _load("methods_metrics", TOOLS / "methods_metrics.py")
gv = _load("methods_ground_variants", TOOLS / "ground" / "ground_variants.py")


def plane(size=120, cell=10, hole=((40, 80), (40, 80)), z=10.0, dz=0.0, shift=(0.0, 0.0), bump=None):
    """Flat square plane of quads (split in two triangles); cells inside `hole` are left out."""
    n = size // cell
    verts = []
    for j in range(n + 1):
        for i in range(n + 1):
            zz = z + dz + (bump[1] if bump and (i * cell, j * cell) == bump[0] else 0.0)
            verts.append([i * cell - shift[0], j * cell - shift[1], zz])
    tris = []
    for j in range(n):
        for i in range(n):
            cx, cy = (i + 0.5) * cell, (j + 0.5) * cell
            if hole and hole[0][0] < cx < hole[0][1] and hole[1][0] < cy < hole[1][1]:
                continue
            a, b, c, d = j * (n + 1) + i, j * (n + 1) + i + 1, (j + 1) * (n + 1) + i + 1, (j + 1) * (n + 1) + i
            tris += [[a, b, c], [a, c, d]]
    return verts, tris


def ground_rb(verts, tris, *, uv=True, name="SM_Test_Ground"):
    m = mesh(name, verts, tris, uv=uv, materials=("M_Test_Ground_Surface",))
    rb = {"source": "C:/synthetic/SM_Test_Ground.fbx", "readback_ok": True, "blender": "synthetic", "meshes": [m],
          "other_objects": [], "images": [], "materials": []}
    extra = {"ok": True, "meshes": {name: {"slots": ["M_Test_Ground_Surface"],
                                           "polygons_by_material_index": {"0": len(tris)},
                                           "polygon_material_index": [0] * len(tris), "tris": tris}}}
    return rb, extra


ZERO = np.zeros(3)


def measure(out, ref=None, offset=ZERO, ref_offset=ZERO, **kw):
    ref = ref or ground_rb(*plane())
    return mm.ground_terrain(out[0], out[1], ref[0], ref[1], offset, ref_offset, **kw)


def test_identical_plane_with_hole_measures_zero_and_one_hole():
    g = measure(ground_rb(*plane()))
    assert g["dz_max_m"] == 0 and g["dz_p95_m"] == 0 and g["dz_mean_m"] == 0 and g["dz_reason"] is None
    assert g["samples_reference"] == g["samples_both"] == 120 * 120 - 40 * 40
    assert g["samples_missing"] == g["samples_extra"] == 0
    assert (g["holes"], g["reference_holes"], g["holes_matched"], g["hole_count_diff"]) == (1, 1, 1, 0)
    assert g["boundary_m"] == g["reference_boundary_m"] == 480.0 and g["boundary_diff_m"] == 0
    assert g["triangles"] == g["reference_triangles"] == 2 * (144 - 16)
    assert g["uv_present"] is True and g["uv_reason"] is None and g["footprint_reason"] is None


def test_shifted_surface_is_caught_by_the_deviation():
    g = measure(ground_rb(*plane(dz=0.05)))
    assert g["dz_max_m"] == pytest.approx(0.05) and g["dz_p95_m"] == pytest.approx(0.05)
    assert g["dz_mean_m"] == pytest.approx(0.05)
    down = measure(ground_rb(*plane(dz=-0.2)))
    assert down["dz_max_m"] == pytest.approx(0.2) and down["dz_mean_m"] == pytest.approx(-0.2)


def test_local_bump_moves_max_not_p95():
    g = measure(ground_rb(*plane(bump=((20, 20), 0.5))))
    assert 0.4 < g["dz_max_m"] <= 0.5 and g["dz_p95_m"] == 0


def test_placement_offsets_align_frames_and_a_wrong_offset_is_caught():
    shifted = ground_rb(*plane(shift=(5.0, 7.0)))
    assert measure(shifted, offset=np.array([5.0, 7.0, 0.0]))["dz_max_m"] == 0
    g = measure(ground_rb(*plane(dz=-1.0)), offset=np.array([0.0, 0.0, 1.0]))
    assert g["dz_max_m"] == 0
    wrong = measure(shifted)  # same mesh, offset forgotten: holes no longer line up
    assert wrong["holes_matched"] == 0 and wrong["samples_missing"] > 0


def test_filled_hole_is_counted_against_the_reference():
    g = measure(ground_rb(*plane(hole=None)))
    assert (g["holes"], g["reference_holes"], g["holes_matched"], g["hole_count_diff"]) == (0, 1, 0, -1)
    assert g["samples_extra"] == 40 * 40 and g["samples_missing"] == 0
    assert g["boundary_diff_m"] == 0  # the hole ring is not boundary: only exterior rings count


def test_hole_threshold_at_exactly_1000_m2_counts_and_900_does_not():
    at = ground_rb(*plane(hole=((40, 60), (30, 80))))  # 20 x 50 = 1000 m2
    assert measure(at, ref=at)["holes"] == 1
    small = ground_rb(*plane(hole=((40, 70), (40, 70))))  # 30 x 30 = 900 m2
    assert measure(small, ref=small)["holes"] == 0
    assert measure(small, ref=small, hole_min_m2=100.0)["holes"] == 1


def test_boundary_length_difference_is_measured():
    smaller = ground_rb(*plane(size=100, hole=((40, 80), (40, 80))))
    g = measure(smaller)
    assert g["boundary_m"] == 400.0 and g["boundary_diff_m"] == -80.0
    assert g["samples_missing"] > 0


@pytest.mark.parametrize("case, field, needle", [
    ("no_ref", "dz_reason", "no reference surface"),
    ("no_offset", "dz_reason", "frames not comparable"),
    ("no_ref_offset", "footprint_reason", "frames not comparable"),
])
def test_deviation_and_footprint_null_with_reason(case, field, needle):
    out = ground_rb(*plane())
    if case == "no_ref":
        g = mm.ground_terrain(out[0], out[1], None, None, ZERO, None, ref_reason="reference FBX missing")
    elif case == "no_offset":
        g = measure(out, offset=None, offset_reason="no placement sidecar X")
    else:
        g = measure(out, ref_offset=None, ref_reason="no placement sidecar R")
    for key in ("dz_max_m", "dz_p95_m", "holes", "boundary_m", "boundary_diff_m", "hole_count_diff"):
        assert g[key] is None, key
    assert needle in g[field] and g["dz_reason"] and g["footprint_reason"]
    assert g["triangles"] == 256 and g["uv_present"] is True  # still measured


def test_uv_null_with_reason_and_false_without_uv():
    rb, extra = ground_rb(*plane(), uv=False)
    assert measure((rb, extra))["uv_present"] is False
    del rb["meshes"][0]["uv_channels"]
    g = measure((rb, extra))
    assert g["uv_present"] is None and "uv_channels" in g["uv_reason"]


def test_no_common_sample_and_no_model_mesh_are_null_with_reason():
    far = ground_rb(*plane(shift=(-1000.0, 0.0)))
    g = measure(far)
    assert g["dz_max_m"] is None and g["dz_reason"] == "no sample covered by both surfaces"
    empty = ({"readback_ok": True, "meshes": [], "other_objects": []}, {"ok": True, "meshes": {}})
    g = measure(empty)
    assert g["triangles"] == 0 and g["dz_reason"] == g["uv_reason"] == "no model mesh"


def test_vertical_skirt_never_decides_the_top():
    verts, tris = plane()
    base = len(verts)
    verts = verts + [[0, 0, 10.0], [120, 0, 10.0], [120, 0, 5.0], [0, 0, 5.0]]
    tris = tris + [[base, base + 1, base + 2], [base, base + 2, base + 3]]
    g = measure(ground_rb(verts, tris))
    assert g["dz_max_m"] == 0 and g["boundary_diff_m"] == 0


def test_fail_closed_on_nan_and_bad_step():
    verts, tris = plane()
    verts[5][2] = float("nan")
    with pytest.raises(mm.MetricError, match="non-finite"):
        measure(ground_rb(verts, tris))
    for bad in (0.0, -1.0, float("nan"), float("inf")):
        with pytest.raises(mm.MetricError, match="sample step"):
            measure(ground_rb(*plane()), sample_m=bad)


def test_placement_sidecar_read_missing_and_malformed(tmp_path):
    fbx = tmp_path / "SM_X.fbx"
    off, reason = mm.placement_offset(fbx)
    assert off is None and "no placement sidecar" in reason
    side = tmp_path / "SM_X.fbx.placement.json"
    side.write_text(json.dumps({"origin_msk77_xyz": [1.5, -2.0, 0.0],
                                "mesh_xyz = msk77_xyz - origin_msk77_xyz": True}), encoding="utf-8")
    off, reason = mm.placement_offset(fbx)
    assert reason is None and list(off) == [1.5, -2.0, 0.0]
    for bad in ({"origin_msk77_xyz": [1, 2], "mesh_xyz = msk77_xyz - origin_msk77_xyz": True},
                {"origin_msk77_xyz": [1, 2, float("nan")], "mesh_xyz = msk77_xyz - origin_msk77_xyz": True},
                {"origin_msk77_xyz": [1, 2, 3]}, [1, 2, 3]):
        side.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(mm.MetricError):
            mm.placement_offset(fbx)
    side.write_text("{not json", encoding="utf-8")
    with pytest.raises(mm.MetricError, match="not JSON"):
        mm.placement_offset(fbx)


# ---- run_variant row + RESULTS.md ---------------------------------------------------------------------------------

def _sidecar(fbx, origin=(0.0, 0.0, 0.0)):
    (fbx.parent / (fbx.name + ".placement.json")).write_text(json.dumps(
        {"origin_msk77_xyz": list(origin), "mesh_xyz = msk77_xyz - origin_msk77_xyz": True}), encoding="utf-8")


def ground_cli(tmp_path, out_rb, *, ref_present=True, ref_sha=None, sidecars=True, report=None):
    ref = tmp_path / "ref" / "SM_Ref_Ground.fbx"
    ref.parent.mkdir(exist_ok=True)
    if ref_present:
        ref.write_bytes(b"synthetic reference fbx")
        if sidecars:
            _sidecar(ref)
    sha = ref_sha or (hashlib.sha256(b"synthetic reference fbx").hexdigest())
    bench = tmp_path / "benchmarks.json"
    bench.write_text(json.dumps({"schema": "methods-benchmarks/1", "objects": [
        {"id": "synth", "classes": ["ground-terrain"], "source": {"kind": "fbx", "local_path": str(ref), "sha256": sha},
         "reference_pictures": {}}]}), encoding="utf-8")
    out = tmp_path / "SM_Test_Ground.fbx"
    out.write_bytes(b"synthetic output fbx")
    if sidecars:
        _sidecar(out)
    rbr, exr = ground_rb(*plane())
    for name, data in (("rb.json", out_rb[0]), ("extra.json", out_rb[1]), ("ref_rb.json", rbr), ("ref_extra.json", exr)):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    args = [str(out), "--bench", "synth", "--class", "ground-terrain", "--variant", "v1", "--benchmarks", str(bench),
            "--readback", str(tmp_path / "rb.json"), "--extra", str(tmp_path / "extra.json"),
            "--reference-readback", str(tmp_path / "ref_rb.json"), "--reference-extra", str(tmp_path / "ref_extra.json"),
            "--results", str(tmp_path / "results.jsonl")]
    if report:
        (tmp_path / "v.variant.json").write_text(json.dumps(report), encoding="utf-8")
        args += ["--variant-report", str(tmp_path / "v.variant.json")]
    else:
        args += ["--wall-time-s", "1.0"]
    return args


def test_run_variant_writes_ground_class_metrics(tmp_path):
    rep = {"ok": True, "wall_time_s": 2.5, "input": {"kind": "adapter-v4", "sha256": "ab" * 32}}
    assert rv.main(ground_cli(tmp_path, ground_rb(*plane(dz=0.03)), report=rep)) == 0
    row = last_row(tmp_path / "results.jsonl")
    g = row["class_metrics"]["ground"]
    assert g["dz_max_m"] == pytest.approx(0.03) and g["holes"] == 1 and g["uv_present"] is True
    assert row["input"] == rep["input"] and row["wall_time_s"] == 2.5
    md = rmd.render(rmd.read_rows(tmp_path / "results.jsonl"), "ground-terrain")
    assert "dz max / p95 m" in md and "0.03 / 0.03" in md and "1 / 1 (1)" in md


def test_run_variant_ground_without_reference_or_sidecar_is_null_with_reason(tmp_path):
    assert rv.main(ground_cli(tmp_path, ground_rb(*plane()), ref_present=False)) == 0
    g = last_row(tmp_path / "results.jsonl")["class_metrics"]["ground"]
    assert g["dz_max_m"] is None and "no reference surface" in g["dz_reason"]
    md = rmd.render(rmd.read_rows(tmp_path / "results.jsonl"), "ground-terrain")
    assert "ground dz: no reference surface" in md


def test_run_variant_ground_without_output_sidecar_is_null_with_reason(tmp_path):
    args = ground_cli(tmp_path, ground_rb(*plane()), sidecars=False)
    _sidecar(tmp_path / "ref" / "SM_Ref_Ground.fbx")
    assert rv.main(args) == 0
    g = last_row(tmp_path / "results.jsonl")["class_metrics"]["ground"]
    assert g["dz_max_m"] is None and "no placement sidecar SM_Test_Ground.fbx.placement.json" in g["dz_reason"]


def test_run_variant_ground_reference_sha_mismatch_is_an_error(tmp_path):
    assert rv.main(ground_cli(tmp_path, ground_rb(*plane()), ref_sha="0" * 64)) == 2
    assert not (tmp_path / "results.jsonl").exists()


def test_run_variant_results_aliasing_the_reference_sidecar_is_refused(tmp_path):
    args = ground_cli(tmp_path, ground_rb(*plane()))
    side = tmp_path / "ref" / "SM_Ref_Ground.fbx.placement.json"
    before = side.read_bytes()
    args[args.index("--results") + 1] = str(side)
    assert rv.main(args) == 4
    assert side.read_bytes() == before


# ---- variant meshers ----------------------------------------------------------------------------------------------

def square_with_hole():
    from shapely.geometry import Polygon

    return Polygon([(0, 0), (120, 0), (120, 120), (0, 120)], [[(40, 40), (80, 40), (80, 80), (40, 80)]])


@pytest.mark.parametrize("cell", [4.0, 7.0])
def test_cdt_mesh_covers_the_plan_exactly_and_keeps_the_hole(cell):
    from shapely.geometry import Polygon

    poly = square_with_hole().difference(Polygon([(0, 0), (13.3, 0), (0, 9.1)]))  # a slanted cut
    v, t = gv.cdt_mesh(poly, cell)
    area = 0.5 * np.abs(np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]]))
    assert area.sum() == pytest.approx(poly.area, rel=1e-9) and (area > 0).all()
    cent = v[t].mean(axis=1)
    assert not gv.inside_even_odd(cent, [[(40, 40), (80, 40), (80, 80), (40, 80)]]).any()
    edges = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    assert counts.max() <= 2  # welded: an interior edge is shared by exactly two triangles
    side = np.max(np.linalg.norm(v[t] - np.roll(v[t], 1, axis=1), axis=2))
    assert side <= cell * np.sqrt(2) + 1e-6


def test_cdt_mesh_refuses_bad_cell_and_empty_plan():
    from shapely.geometry import Polygon

    for bad in (0.0, -2.0, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="cell"):
            gv.cdt_mesh(square_with_hole(), bad)
    with pytest.raises(ValueError, match="empty"):
        gv.cdt_mesh(Polygon(), 4.0)


def test_inside_even_odd_brute_force_against_shapely():
    from shapely.geometry import Point

    poly = square_with_hole()
    rings = gv.plan_rings(poly)
    rng = np.random.default_rng(733)
    pts = rng.uniform(-10, 130, size=(2000, 2))
    want = np.array([poly.contains(Point(p)) for p in pts])
    on_edge = np.array([poly.boundary.distance(Point(p)) < 1e-9 for p in pts])
    got = gv.inside_even_odd(pts, rings)
    assert (got == want)[~on_edge].all()


def test_relief_projection_counts_misses_and_never_invents_nan():
    pts = [(0, 0, 1.0), (10, 0, 2.0), (0, 10, 3.0), (10, 10, 4.0)]
    z, misses = gv.project_relief(np.array([[5.0, 5.0], [0.0, 0.0], [20.0, 20.0]]), pts)
    assert z[1] == pytest.approx(1.0) and 2.0 <= z[0] <= 3.0 and np.isfinite(z).all()
    assert misses == [2] and z[2] == pytest.approx(4.0)  # nearest relief point, reported as a miss


def test_mesh_dict_matches_the_ground_fbx_writer_layout():
    v = np.array([[0.0, 0.0, 1.0], [4.0, 0.0, 1.0], [0.0, 4.0, 1.0]])
    d = gv.mesh_dict(v, np.array([[0, 1, 2]]), {"variant": "x"})
    assert d["slots"] == ["Surface"] and d["mat"] == [0] and len(d["uv"]) == 1 and len(d["uv"][0]) == 3
    assert d["uv"][0][1][0] == pytest.approx(4.0 * gv.UV_PER_M)


def test_variant_driver_refuses_output_aliasing_the_input(tmp_path):
    src = tmp_path / "in.json"
    src.write_text("{}", encoding="utf-8")
    drv = _load("methods_ground_build", TOOLS / "ground" / "build_variant.py")
    assert drv.main(["cdt", str(src), "--cell", "4", "--out", str(tmp_path)]) == 4
    assert drv.main(["cdt", str(src), "--cell", "0", "--out", str(tmp_path / "o")]) == 4
    assert drv.main(["nope", str(src), "--cell", "4", "--out", str(tmp_path / "o")]) == 4
    assert src.read_text(encoding="utf-8") == "{}" and not (tmp_path / "o").exists()


# ---- committed docs -----------------------------------------------------------------------------------------------

BASE = TOOLS.parents[1] / "docs" / "methods" / "ground-terrain"


def test_committed_results_regenerate_byte_identical():
    if not (BASE / "results.jsonl").is_file():
        pytest.skip("no committed ground-terrain rows yet")
    assert rmd.render(rmd.read_rows(BASE / "results.jsonl"), "ground-terrain") == \
        (BASE / "RESULTS.md").read_text(encoding="utf-8")


def test_when_rules_cite_existing_rows_and_numbers():
    if not (BASE / "results.jsonl").is_file():
        pytest.skip("no committed ground-terrain rows yet")
    n = len(rmd.read_rows(BASE / "results.jsonl"))
    text = (BASE / "WHEN.md").read_text(encoding="utf-8")
    assert len(text.splitlines()) <= 15
    rules = [ln for ln in text.splitlines() if ln.startswith("- ")]
    assert rules
    for rule in rules:
        cited = [int(x) for x in re.findall(r"\bR(\d+)\b", rule)]
        assert cited and all(1 <= c <= n for c in cited), rule
        assert re.search(r"\d", re.sub(r"\bR\d+\b", "", rule)), f"rule without a number: {rule}"
