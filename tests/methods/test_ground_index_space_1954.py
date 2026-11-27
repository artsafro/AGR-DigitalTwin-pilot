"""ground-terrain: triangles and coordinates come from one bound import, or the surface is not measured (#1954).

Pattern: new-case: index-space and FBX-binding controls of methods_metrics.ground_terrain (synthetic only).

Fixture (issue #1954): a 2 m nonplanar quad, ring [[0,0,0],[2,0,0],[2,2,1],[0,2,0]], triangles [[0,1,2],[0,2,3]]
(diagonal 0-2, centre z 0.5). The same two triangles in vertex order [3,0,1,2] are [[1,2,3],[1,3,0]]. The other
diagonal (1-3) puts the centre at z 0.0, so one 2 m sample at (1, 1) tells the two triangulations apart.
On origin/main 8a2fa635 the permuted triangles were applied to the readback's vertex list and the centre read 0.0.
"""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from tests.methods.test_ground_terrain import SYN_SHA, ground_cli, ground_rb, measure, mm, plane
from tests.methods.test_methods_catalog import last_row, mesh, rmd, rv

RING = [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [2.0, 2.0, 1.0], [0.0, 2.0, 0.0]]
TRIS = [[0, 1, 2], [0, 2, 3]]
ORDER = [3, 0, 1, 2]  # permuted[k] = RING[ORDER[k]]
P_RING = [RING[i] for i in ORDER]
P_TRIS = [[1, 2, 3], [1, 3, 0]]  # the same two triangles in the permuted index space
OTHER = "6" * 64


def quad(verts=RING, tris=TRIS, *, own=True, sha=SYN_SHA, ex_verts=None, ex_tris=None):
    """(readback, extra) of the quad; the extra may come from another index space (ex_verts / ex_tris)."""
    rb, extra = ground_rb(verts, tris, sha=sha)
    e = extra["meshes"]["SM_Test_Ground"]
    e["tris"] = ex_tris if ex_tris is not None else tris
    if own:
        e["vertices"] = ex_verts if ex_verts is not None else verts
    else:
        del e["vertices"]
    return rb, extra


def fan_quad(polygon, verts=RING, sha=SYN_SHA):
    """Readback with one quad polygon and no extra: the polygon-fan (reconstructed) path."""
    m = mesh("SM_Test_Ground", verts, [polygon], materials=("M_Test_Ground_Surface",))
    m["triangles"] = 2
    m["polygon_degrees"] = {"4": 1}
    rb = {"source": "C:/synthetic/q.fbx", "source_sha256": sha, "readback_ok": True, "blender": "synthetic",
          "meshes": [m], "other_objects": [], "images": [], "materials": []}
    return rb, None


def centre(out, ref=None, **kw):
    return measure(out, ref or quad(), sample_m=2.0, **kw)


def test_positive_control_reads_the_imported_diagonal():
    g = centre(quad())
    assert g["samples_both"] == 1 and g["dz_max_m"] == 0 and g["dz_reason"] is None
    assert g["surface_verified"] is True and g["surface_note"] is None
    for side in ("output", "reference"):
        ev = g["surface_evidence"][side]
        assert ev["triangulation"] == mm.GROUND_IMPORTED and ev["index_space"] == "extra readback vertices"
        assert ev["readback"] == ev["extra"] == mm.BOUND and ev["fbx_sha256"] == SYN_SHA
    # the shared top_z reader on the same triangles: centre 0.5 on diagonal 0-2, 0.0 on diagonal 1-3
    v = np.asarray(RING)
    grid = mm.sample_grid(v[np.asarray(TRIS)], 2.0)
    assert mm.top_z(v[np.asarray(TRIS)], grid)[0, 0] == pytest.approx(0.5)
    assert mm.top_z(v[np.asarray([[0, 1, 3], [1, 2, 3]])], grid)[0, 0] == pytest.approx(0.0)


@pytest.mark.parametrize("side", ("output", "reference"))
def test_permuted_extra_with_its_own_vertices_measures_the_same_surface(side):
    """Readback in ring order, extra in the permuted order with its own vertex list: mapped, dz 0 (was -0.5)."""
    permuted = quad(RING, TRIS, ex_verts=P_RING, ex_tris=P_TRIS)
    g = centre(permuted) if side == "output" else centre(quad(), ref=permuted)
    assert g["dz_max_m"] == 0 and g["dz_mean_m"] == 0 and g["surface_verified"] is True
    # and the other way round: readback permuted, extra in ring order
    g = centre(quad(P_RING, P_TRIS, ex_verts=RING, ex_tris=TRIS))
    assert g["dz_max_m"] == 0 and g["surface_verified"] is True


@pytest.mark.parametrize("side", ("output", "reference"))
def test_extra_without_its_own_vertex_list_is_not_measured(side):
    """The origin/main repro: permuted triangles, no vertex list -> index space unknown -> null with the reason."""
    legacy = quad(RING, TRIS, own=False, ex_tris=P_TRIS)
    g = centre(legacy) if side == "output" else centre(quad(), ref=legacy)
    for key in ("dz_max_m", "dz_p95_m", "dz_mean_m", "holes", "boundary_m"):
        assert g[key] is None, key
    assert g["dz_reason"].startswith("not measured: ") and f"{side} mesh 'SM_Test_Ground'" in g["dz_reason"]
    assert "index space" in g["dz_reason"] and g["footprint_reason"] == g["dz_reason"]
    assert g["surface_verified"] is False and g["surface_note"] == "no surface measured"
    ev = g["surface_evidence"][side]
    assert ev["verified_import"] is False and ev["index_space"].startswith("unknown")
    assert "not used" in ev["triangulation"] and ev["triangulation"] != mm.GROUND_IMPORTED


@pytest.mark.parametrize("side", ("output", "reference"))
@pytest.mark.parametrize("doc", ("readback", "extra"))
def test_evidence_of_another_fbx_is_an_error(side, doc):
    bad = quad()
    bad[0 if doc == "readback" else 1]["source_sha256"] = OTHER
    with pytest.raises(mm.MetricError, match="source_sha256 666666666666 is not the intended FBX"):
        centre(bad) if side == "output" else centre(quad(), ref=bad)


@pytest.mark.parametrize("side", ("output", "reference"))
@pytest.mark.parametrize("case", ("rb_no_sha", "extra_no_sha", "caller_no_sha", "caller_empty_sha"))
def test_unbound_evidence_is_not_measured(side, case):
    q, kw = quad(), {}
    if case == "rb_no_sha":
        del q[0]["source_sha256"]
    elif case == "extra_no_sha":
        del q[1]["source_sha256"]
    else:
        kw["sha256" if side == "output" else "ref_sha256"] = None if case == "caller_no_sha" else ""
    g = centre(q, **kw) if side == "output" else centre(quad(), ref=q, **kw)
    assert g["dz_max_m"] is None and g["boundary_m"] is None and g["surface_verified"] is False
    assert g["dz_reason"].startswith(f"not measured: {side} ")
    assert ("cannot be bound" in g["dz_reason"]) if "no_sha" in case and case != "caller_no_sha" else \
        ("intended FBX sha256 not given" in g["dz_reason"])


@pytest.mark.parametrize("side", ("output", "reference"))
@pytest.mark.parametrize("case", ("moved_vertex", "fewer_vertices", "empty_vertices", "nan_vertex", "not_list"))
def test_extra_vertices_must_be_the_readback_mesh(side, case):
    """Same name, same triangle count, right sha256 - but not the readback's vertices: an error, never a pass."""
    ex_v = copy.deepcopy(RING)
    if case == "moved_vertex":
        ex_v[2][2] = 0.7
    elif case == "fewer_vertices":
        ex_v = ex_v[:3]
    elif case == "empty_vertices":
        ex_v = []
    elif case == "nan_vertex":
        ex_v[1][0] = float("nan")
    else:
        ex_v = "0 0 0"
    bad = quad(ex_verts=ex_v, ex_tris=[[0, 1, 2], [0, 2, 1]] if case == "fewer_vertices" else TRIS)
    with pytest.raises(mm.MetricError, match="extra readback vertices|non-finite|outside the vertex list"):
        centre(bad) if side == "output" else centre(quad(), ref=bad)


def test_index_and_count_negative_controls_still_hold_with_own_vertices():
    for tris in ([[0, 1, 4], [0, 2, 3]], [[0, 1, 2]], [[0, 1, 2.0], [0, 2, 3]]):
        with pytest.raises(mm.MetricError, match="triangle"):
            centre(quad(ex_tris=tris))


def test_reconstructed_fan_is_labelled_and_depends_on_the_polygon_start():
    """No extra: the readback polygon is fanned. Ring start 0 -> diagonal 0-2 (dz 0 vs the imported reference);
    start 1 -> diagonal 1-3 (dz -0.5). Measured, but never labelled a verified imported surface."""
    for polygon, dz in (([0, 1, 2, 3], 0.0), ([1, 2, 3, 0], -0.5)):
        g = centre(fan_quad(polygon))
        assert g["dz_mean_m"] == pytest.approx(dz) and g["samples_both"] == 1
        ev = g["surface_evidence"]["output"]
        assert ev["triangulation"] == mm.GROUND_FAN and ev["index_space"] == "readback polygons"
        assert ev["verified_import"] is False and ev["extra"] is None and ev["readback"] == mm.BOUND
        assert g["surface_verified"] is False and "output reconstructed fan" in g["surface_note"]
        assert "NOT the FBX's imported triangulation" in g["surface_note"]
    g = centre(quad(), ref=fan_quad([0, 1, 2, 3]))
    assert g["surface_verified"] is False and g["surface_note"].count("reconstructed fan") == 1
    assert g["surface_note"].startswith("not a verified imported-surface measurement: reference ")
    unbound = fan_quad([0, 1, 2, 3])
    del unbound[0]["source_sha256"]
    g = centre(unbound)
    assert g["dz_max_m"] is None and "cannot be bound" in g["dz_reason"]


def test_mixed_valid_and_legacy_mesh_is_not_measured_not_dropped():
    """Two model meshes: one with its own vertex list, one legacy. The legacy one is named, nothing is measured."""
    rb, extra = quad()
    rb2, extra2 = ground_rb([[x + 3, y, z] for x, y, z in RING], TRIS, name="SM_Test_Ground_B")
    rb["meshes"] += rb2["meshes"]
    extra["meshes"].update(extra2["meshes"])
    del extra["meshes"]["SM_Test_Ground_B"]["vertices"]
    g = centre((rb, extra))
    assert g["dz_max_m"] is None and "'SM_Test_Ground_B'" in g["dz_reason"] and g["triangles"] == 4


def test_ucx_mesh_stays_excluded_from_the_ground_surface():
    rb, extra = quad()
    rb["meshes"].append(mesh("UCX_SM_Test_Ground_00", [[0, 0, 5], [2, 0, 5], [2, 2, 5]], [[0, 1, 2]]))
    g = centre((rb, extra))  # the UCX piece at z 5 has no extra entry and never decides the top
    assert g["dz_max_m"] == 0 and g["surface_verified"] is True and g["triangles"] == 2


def test_unrelated_class_metrics_ignore_the_new_extra_fields():
    """windows-glazing / matid read the extra exactly as before; the added vertices/source_sha256 change nothing."""
    rb, extra = quad()
    lean = copy.deepcopy(extra)
    del lean["source_sha256"], lean["meshes"]["SM_Test_Ground"]["vertices"]
    assert mm.matid(rb, extra) == mm.matid(rb, lean)
    assert mm.windows_glazing(rb, extra) == mm.windows_glazing(rb, lean)


@pytest.mark.parametrize("seed", range(40))
def test_probe_random_vertex_permutations_measure_identically(seed):
    """Brute force: a random nonplanar grid and a random vertex permutation of it (triangles remapped). With its
    own vertex list the extra measures exactly like the unpermuted mesh; without it, it is not measured."""
    rng = np.random.default_rng(seed)
    verts, tris = plane(size=20, cell=2, hole=None)
    verts = [[x, y, float(rng.uniform(-1, 1))] for x, y, _ in verts]
    perm = rng.permutation(len(verts))  # new index k holds old vertex perm[k]
    inv = np.argsort(perm)
    p_verts = [verts[i] for i in perm]
    p_tris = [[int(inv[i]) for i in t] for t in tris]
    ref = ground_rb(verts, tris)
    base = measure(ground_rb(verts, tris), ref, sample_m=0.5)
    g = measure(quad(verts, tris, ex_verts=p_verts, ex_tris=p_tris), ref, sample_m=0.5)
    keys = ("dz_max_m", "dz_p95_m", "dz_mean_m", "samples_both", "boundary_m", "holes")
    assert [g[k] for k in keys] == [base[k] for k in keys] and g["dz_max_m"] == 0 and g["surface_verified"]
    legacy = measure(quad(verts, tris, own=False, ex_tris=p_tris), ref, sample_m=0.5)
    assert legacy["dz_max_m"] is None and "index space" in legacy["dz_reason"]


# ---- run_variant (fresh rows, RESULTS.md) --------------------------------------------------------------------------

def _quad_cli(tmp_path, out_rb):
    args = ground_cli(tmp_path, out_rb)
    rbr, exr = quad()
    sha = json.loads((tmp_path / "ref_rb.json").read_text(encoding="utf-8"))["source_sha256"]
    for name, data in (("ref_rb.json", rbr), ("ref_extra.json", exr)):
        (tmp_path / name).write_text(json.dumps({**data, "source_sha256": sha}), encoding="utf-8")
    return args


def test_run_variant_row_shows_evidence_and_triangulation_source(tmp_path):
    assert rv.main(_quad_cli(tmp_path, quad(RING, TRIS, ex_verts=P_RING, ex_tris=P_TRIS))) == 0
    g = last_row(tmp_path / "results.jsonl")["class_metrics"]["ground"]
    assert g["surface_verified"] is True and g["dz_max_m"] == 0
    out_ev, ref_ev = g["surface_evidence"]["output"], g["surface_evidence"]["reference"]
    assert out_ev["fbx_sha256"] != ref_ev["fbx_sha256"]  # each side bound to its own FBX
    assert out_ev["triangulation"] == ref_ev["triangulation"] == mm.GROUND_IMPORTED


def test_run_variant_unbound_or_legacy_extra_is_a_null_row_with_the_reason(tmp_path):
    legacy = quad(RING, TRIS, own=False, ex_tris=P_TRIS)
    assert rv.main(_quad_cli(tmp_path, legacy)) == 0
    g = last_row(tmp_path / "results.jsonl")["class_metrics"]["ground"]
    assert g["dz_max_m"] is None and "index space" in g["dz_reason"]
    md = rmd.render(rmd.read_rows(tmp_path / "results.jsonl"), "ground-terrain")
    assert "ground dz: not measured: output mesh 'SM_Test_Ground'" in md


def test_run_variant_extra_of_another_fbx_exits_2_and_appends_nothing(tmp_path):
    bad = quad()
    bad[1]["source_sha256"] = OTHER
    assert rv.main(_quad_cli(tmp_path, bad)) == 2
    assert not (tmp_path / "results.jsonl").exists()


def test_run_variant_fan_row_is_labelled_reconstructed_in_results_md(tmp_path):
    args = _quad_cli(tmp_path, quad())
    k = args.index("--extra")
    del args[k:k + 2]
    rb, _ = fan_quad([1, 2, 3, 0])
    rb["source_sha256"] = json.loads((tmp_path / "rb.json").read_text(encoding="utf-8"))["source_sha256"]
    (tmp_path / "rb.json").write_text(json.dumps(rb), encoding="utf-8")
    assert rv.main(args) == 0
    g = last_row(tmp_path / "results.jsonl")["class_metrics"]["ground"]
    assert g["surface_verified"] is False and g["dz_max_m"] is not None
    md = rmd.render(rmd.read_rows(tmp_path / "results.jsonl"), "ground-terrain")
    assert "ground surface: not a verified imported-surface measurement: output reconstructed fan" in md


def test_measure_is_pure_on_bound_inputs():
    out, ref = quad(RING, TRIS, ex_verts=P_RING, ex_tris=P_TRIS), quad()
    snap = copy.deepcopy((out, ref))
    centre(out, ref=ref)
    assert (out, ref) == snap
