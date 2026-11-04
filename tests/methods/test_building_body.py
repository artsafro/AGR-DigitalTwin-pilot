"""building-body class metrics on tiny synthetic inputs (#727).

Pattern: new-case: tests of the building-body methods class (deviation, closed shells, budget, null paths).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from tests.methods.test_methods_catalog import BOX_T, bench_file, box, cli_args, last_row, mesh, mm, rmd, rv


def rb_of(*meshes):
    return {"readback_ok": True, "blender": "synthetic", "meshes": list(meshes), "other_objects": [], "images": [],
            "materials": []}


def cube(name="SM_Test_Main", lo=(0, 0, 0), hi=(1, 1, 1), tris=BOX_T):
    return mesh(name, box(lo, hi), tris)


def test_identical_body_has_zero_deviation_and_one_closed_shell():
    b = mm.building_body(rb_of(cube()), rb_of(cube()))
    assert b["deviation_max_m"] == 0.0 and b["deviation_p95_m"] == 0.0 and b["deviation_samples"] > 0
    assert b["closed_shell_share"] == 1.0 and b["components"] == 1 and b["closed_components"] == 1
    assert b["triangles"] == 12 and b["triangle_budget"] == 150_000 and b["within_budget"] is True
    assert b["deviation_reason"] is None and b["shell_reason"] is None


def test_deviation_is_one_sided_source_to_variant():
    # variant is the source shifted 0.1 m along x: the source face x=0 is 0.1 m from the variant
    b = mm.building_body(rb_of(cube(lo=(0.1, 0, 0), hi=(1.1, 1, 1))), rb_of(cube()))
    assert b["deviation_max_m"] == pytest.approx(0.1, abs=1e-6)
    # a variant that contains the whole source surface plus extra geometry deviates 0 (one-sided)
    big = rb_of(cube(), cube("SM_Test_Main_2", (5, 5, 5), (6, 6, 6)))
    assert mm.building_body(big, rb_of(cube()))["deviation_max_m"] == 0.0


def test_open_box_is_not_a_closed_shell_and_shares_count_triangles():
    open_box = cube(tris=BOX_T[2:])  # bottom removed
    b = mm.building_body(rb_of(open_box, cube("SM_Test_Main_2", (3, 0, 0), (4, 1, 1))), None)
    assert b["components"] == 2 and b["closed_components"] == 1
    assert b["closed_shell_share"] == pytest.approx(12 / 22, abs=1e-5)


def test_split_vertices_are_welded_before_the_edge_count():
    v = box((0, 0, 0), (1, 1, 1))
    verts, tris = [], []
    for t in BOX_T:  # every triangle has its own three vertices (FBX corner split)
        tris.append([len(verts), len(verts) + 1, len(verts) + 2])
        verts += [list(v[i]) for i in t]
    assert mm.closed_shells(rb_of(mesh("SM_Test_Main", verts, tris)))["closed_shell_share"] == 1.0


def test_null_with_reason_paths_never_a_number():
    b = mm.building_body(rb_of(cube()), None)
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "no source readback"
    ucx_only = rb_of(mesh("UCX_SM_Test_Main_001", box((0, 0, 0), (1, 1, 1)), BOX_T, uv=False, materials=()))
    b = mm.building_body(rb_of(cube()), ucx_only)
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "source has no model triangle"
    b = mm.building_body(ucx_only, rb_of(cube()))
    assert b["deviation_max_m"] is None and b["deviation_reason"] == "variant has no model triangle"
    assert b["closed_shell_share"] is None and b["shell_reason"] == "no model triangle"


def test_failed_or_nonfinite_source_is_an_error_not_a_null():
    with pytest.raises(mm.MetricError, match="source readback failed"):
        mm.building_body(rb_of(cube()), {"readback_ok": False, "error": "boom"})
    bad = cube()
    bad["face_geometry"]["vertices"][0] = [float("nan"), 0, 0]
    with pytest.raises(mm.MetricError, match="non-finite"):
        mm.building_body(rb_of(cube()), rb_of(bad))
    with pytest.raises(mm.MetricError, match="no triangle"):
        mm.nearest_triangle_distance(np.zeros((1, 3)), np.zeros((0, 3, 3)))


@pytest.mark.parametrize("n, within", [(150_000, True), (150_001, False)])
def test_budget_exactly_at_threshold(n, within):
    m = cube()
    m["triangles"] = n  # counts() reads the readback triangle count
    b = mm.building_body(rb_of(m), None)
    assert b["within_budget"] is within and b["budget_share"] == round(n / 150_000, 5)


def test_grid_distance_matches_brute_force_on_random_soup():
    rng = np.random.default_rng(727)
    for _ in range(20):
        tri = rng.uniform(-5, 5, (int(rng.integers(1, 40)), 3, 3)) * rng.uniform(0.05, 1)
        pts = rng.uniform(-8, 8, (200, 3))
        brute = mm.point_triangle_distance(pts[:, None], tri[None, :, 0], tri[None, :, 1], tri[None, :, 2]).min(1)
        np.testing.assert_allclose(mm.nearest_triangle_distance(pts, tri, r0=0.05), brute, atol=1e-9)


def test_cli_writes_body_metrics_and_results_md_column(tmp_path):
    rb = rb_of(cube())
    (tmp_path / "src.json").write_text(json.dumps(rb_of(cube(lo=(0, 0, 0), hi=(1, 1, 1.2)))), encoding="utf-8")
    bench = bench_file(tmp_path, classes=("building-body",))
    args = cli_args(tmp_path, rb, {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    assert rv.main(args + ["--source-readback", str(tmp_path / "src.json"), "--synthetic", SYN]) == 0
    body = last_row(tmp_path / "results.jsonl")["class_metrics"]["body"]
    assert body["deviation_max_m"] == pytest.approx(0.2, abs=1e-6) and body["closed_shell_share"] == 1.0
    md = rmd.write(tmp_path / "results.jsonl").read_text(encoding="utf-8")
    assert "Deviation src->variant max / p95 m" in md and "| 0.2 / " in md and "1/1 (100.0%)" in md


def test_cli_missing_source_fbx_is_an_error_and_appends_nothing(tmp_path):
    bench = bench_file(tmp_path, classes=("building-body",))  # source C:/synthetic/SM_Test.fbx does not exist
    args = cli_args(tmp_path, rb_of(cube()), {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    assert rv.main(args + ["--synthetic", SYN]) == 2
    assert not (tmp_path / "results.jsonl").exists()


SYN = "plan contours measured from the source mesh (synthetic drawing)"


def _body_args(tmp_path):
    (tmp_path / "src.json").write_text(json.dumps(rb_of(cube())), encoding="utf-8")
    bench = bench_file(tmp_path, classes=("building-body",))
    args = cli_args(tmp_path, rb_of(cube()), {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    return args + ["--source-readback", str(tmp_path / "src.json")]


@pytest.mark.parametrize("extra", [[], ["--synthetic", ""], ["--synthetic", "   "], ["--synthetic", "\t\n"]])
def test_body_row_without_a_synthetic_marker_is_refused_and_appends_nothing(tmp_path, extra):
    # user decision 2026-11-02 [D187] (option a): no drawing-backed body input exists yet, so every building-body row
    # must say it is synthetic and why; a missing or blank reason is refused before anything is written
    assert rv.main(_body_args(tmp_path) + extra) == 4
    assert not (tmp_path / "results.jsonl").exists()


def test_body_row_carries_the_synthetic_marker_and_results_md_lists_it(tmp_path):
    assert rv.main(_body_args(tmp_path) + ["--synthetic", f"  {SYN} "]) == 0
    row = last_row(tmp_path / "results.jsonl")
    assert row["synthetic"] is True and row["synthetic_reason"] == SYN
    md = rmd.write(tmp_path / "results.jsonl").read_text(encoding="utf-8")
    assert f"- {SYN} (R1)" in md and "Synthetic inputs and why:" in md


def test_other_classes_keep_their_row_shape_without_the_marker(tmp_path):
    from tests.methods.test_methods_catalog import scene

    rb, extra = scene()
    assert rv.main(cli_args(tmp_path, rb, extra)) == 0
    row = last_row(tmp_path / "results.jsonl")
    assert "synthetic" not in row and "synthetic_reason" not in row
    assert "Synthetic inputs" not in rmd.write(tmp_path / "results.jsonl").read_text(encoding="utf-8")


def test_batch_marks_every_variant_synthetic_with_a_reason():
    batch = _load_batch()
    for v in (batch.BASELINE,) + batch.VARIANTS:
        assert batch.synthetic_reason(v).strip(), v
    with pytest.raises(KeyError):
        batch.synthetic_reason("no-such-variant")


# Rule 42: a decision id must be free on main AND in every open PR. Recorded inventory of the open-PR claim that this
# scope decision collided with in review round 2 (PR #576 adds D186 = task intake, 2026-10-22).
OPEN_PR_DECISIONS = {"D186": "PR #576 (task intake, 2026-10-22)"}
DECISIONS_MD = Path(__file__).resolve().parents[2] / "docs" / "decisions.md"


def _decision_rows() -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in DECISIONS_MD.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| (D\d+) \|", line)
        if m:
            rows.setdefault(m.group(1), []).append(line)
    return rows


def id_collisions(decision_id: str, own_marker: str, main_rows: dict[str, list[str]],
                  open_prs: dict[str, str]) -> list[str]:
    """Every other owner of decision_id: a main row not about own_marker, or an open PR claim."""
    hits = [f"main: {r[:60]}" for r in main_rows.get(decision_id, []) if own_marker not in r]
    if decision_id in open_prs:
        hits.append(open_prs[decision_id])
    return hits


@pytest.mark.parametrize("decision_id,taken", [("D186", True), ("D185", True), ("D187", False)])
def test_scope_decision_id_collision_witness(decision_id, taken):
    # occupied: D186 (open PR #576), D185 (a main row about another job); free control: D187 (only our #727 row)
    hits = id_collisions(decision_id, "#727", _decision_rows(), OPEN_PR_DECISIONS)
    assert bool(hits) is taken, hits


def test_scope_decision_is_free_logged_once_and_cited_by_every_reason():
    batch = _load_batch()
    sid, rows = batch.SCOPE_DECISION, _decision_rows()
    assert id_collisions(sid, "#727", rows, OPEN_PR_DECISIONS) == []
    assert len(rows.get(sid, [])) == 1 and "#727" in rows[sid][0] and "2026-11-02" in rows[sid][0]
    for v in (batch.BASELINE,) + batch.VARIANTS:
        assert f"[{sid}]" in batch.synthetic_reason(v) and "D186" not in batch.synthetic_reason(v), v
    results = DECISIONS_MD.parent / "methods" / "building-body" / "results.jsonl"
    reasons = [json.loads(x)["synthetic_reason"] for x in results.read_text(encoding="utf-8").splitlines() if x]
    assert len(reasons) == 12 and all(f"[{sid}]" in r and "D186" not in r for r in reasons)


@pytest.mark.parametrize("variant,make", [("source-as-is", ()), ("kernel-prisms", ("out",)),
                                          ("max-pymxs-cleanup", ("rep",))])
def test_measure_only_with_a_missing_output_or_report_writes_no_row(tmp_path, variant, make):
    import types

    batch = _load_batch()
    out, rep = tmp_path / "SM_X.fbx", tmp_path / "SM_X.fbx.variant.json"
    for name in make:
        {"out": out, "rep": rep}[name].write_text("x", encoding="utf-8")
    a = types.SimpleNamespace(results=tmp_path / "results.jsonl", benchmarks=tmp_path / "b.json")
    assert batch._measure_existing(a, "synth", variant, out, rep) == 2
    assert not a.results.exists()


def _load_batch():
    import importlib.util

    spec = importlib.util.spec_from_file_location("body_batch_t", TOOLS / "body" / "run_benchmarks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- shared contour input + our kernel's prisms ---------------------------------------------------------------------

from tests.methods.test_methods_catalog import _load, TOOLS  # noqa: E402

bc = _load("body_contours", TOOLS / "body" / "contours.py")
kp = _load("body_kernel_prisms", TOOLS / "body" / "kernel_prisms.py")


def test_two_storey_box_gives_two_bands_and_closed_prisms_matching_it():
    # 10 x 6 m storey 0..3 m under a 6 x 6 m storey 3..6 m (synthetic, closed boxes)
    rb = rb_of(cube("SM_Test_Main", (0, 0, 0), (10, 6, 3)), cube("SM_Test_Main_2", (0, 0, 3), (6, 6, 6)))
    c = bc.contours(rb)
    assert c["synthetic_drawing"] is True and c["levels_m"] == [0.0, 3.0, 6.0] and not c["empty_bands"]
    areas = [round(sum(q.area for q in bc.polygons(b)), 2) for b in c["bands"]]
    assert areas == [60.0, 36.0]
    m = kp.prisms(c)
    out = rb_of(mesh("SM_Test_Main", m["vertices"], m["triangles"], uv=False))
    b = mm.building_body(out, rb)
    assert b["deviation_max_m"] == pytest.approx(0.0, abs=1e-6)
    # each prism is closed, but stacked prisms share the edge (0,0,3)-(0,6,3) four times: one non-manifold shell
    assert b["components"] == 1 and b["closed_shell_share"] == 0.0
    single = mm.building_body(rb_of(mesh("SM_Test_Main", *[kp.prisms({"bands": c["bands"][:1]})[k]
                                                           for k in ("vertices", "triangles")], uv=False)), None)
    assert single["closed_shell_share"] == 1.0


def test_hole_touching_the_outline_is_filled_never_a_repeated_vertex():
    from shapely.geometry import Polygon

    q = bc.simple_rings(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(0, 0), (3, 1), (1, 3)], [(5, 5), (7, 5), (7, 7), (5, 7)]]))
    assert len(q.interiors) == 1 and Polygon(q.interiors[0]).area == 4.0  # touching triangle hole filled
    kp.prisms({"bands": [{"z0": 0, "z1": 3, "polygons": [{"exterior": list(q.exterior.coords)[:-1],
                                                           "holes": [list(r.coords)[:-1] for r in q.interiors]}]}]})


def test_contours_fail_closed_on_empty_or_nonfinite_source():
    with pytest.raises(ValueError, match="no model triangle"):
        bc.contours(rb_of())
    bad = cube()
    bad["face_geometry"]["vertices"][0] = [float("inf"), 0, 0]
    with pytest.raises(ValueError, match="non-finite"):
        bc.contours(rb_of(bad))
    with pytest.raises(ValueError, match="no band polygon"):
        kp.prisms({"bands": []})



# ---- review round 1 of PR #729: conservative closed shells ---------------------------------------------------------

def test_doubled_flat_sheet_is_not_a_closed_shell():
    """Reviewer input: one triangle and its reverse pass the 'every edge twice' count but enclose nothing."""
    s = mm.closed_shells(rb_of(mesh("SM_Test_Main", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2), (0, 2, 1)])))
    assert s["closed_shell_share"] == 0.0 and s["components"] == 1 and s["closed_components"] == 0
    assert s["open_reasons"] == {"duplicated triangle (doubled sheet)": 1} and s["reason"] is None


def test_flat_pillow_with_two_triangulations_has_zero_volume_and_is_open():
    v = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]  # top (0,1,2),(0,2,3) / bottom (1,0,3),(1,3,2): no duplicate
    s = mm.closed_shells(rb_of(mesh("SM_Test_Main", v, [(0, 1, 2), (0, 2, 3), (1, 0, 3), (1, 3, 2)])))
    assert s["closed_shell_share"] == 0.0 and s["open_reasons"] == {"zero enclosed volume": 1}


def test_inconsistent_winding_box_is_open_but_controls_stay_closed():
    flipped = [BOX_T[0][::-1]] + BOX_T[1:]
    s = mm.closed_shells(rb_of(cube(tris=flipped)))
    assert s["closed_shell_share"] == 0.0 and s["open_reasons"] == {"inconsistent winding": 1}
    assert mm.closed_shells(rb_of(cube()))["closed_shell_share"] == 1.0
    inside_out = [t[::-1] for t in BOX_T]  # consistently inward: still a closed shell (|volume| > 0)
    assert mm.closed_shells(rb_of(cube(tris=inside_out)))["closed_shell_share"] == 1.0


def test_weld_collapsed_triangle_stays_in_the_denominator():
    v = box((0, 0, 0), (1, 1, 1)) + [[5, 5, 5], [5, 5, 5.00001], [5.00001, 5, 5]]  # < 0.1 mm: collapses
    s = mm.closed_shells(rb_of(mesh("SM_Test_Main", v, BOX_T + [(8, 9, 10)])))
    assert s["closed_shell_share"] == pytest.approx(12 / 13, abs=1e-5)
    assert s["open_reasons"] == {"triangles collapsed by weld": 1}


def test_doubled_sheet_next_to_a_box_counts_only_the_box():
    sheet = mesh("SM_Test_Main_2", [(5, 0, 0), (6, 0, 0), (5, 1, 0)], [(0, 1, 2), (0, 2, 1)])
    b = mm.building_body(rb_of(cube(), sheet), None)
    assert b["closed_shell_share"] == pytest.approx(12 / 14, abs=1e-5) and b["closed_components"] == 1


# ---- review round 1: standalone writers refuse input/output aliases (fresh processes) -------------------------------

import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

sw = _load("safe_write", TOOLS / "safe_write.py")
bo = _load("body_openings", TOOLS / "body" / "openings.py")


def _src_readback(tmp_path):
    p = tmp_path / "source.json"
    p.write_text(json.dumps(rb_of(cube("SM_Test_Main", (0, 0, 0), (4, 4, 3)))), encoding="utf-8")
    return p


def _run(script, *args):
    return subprocess.run([sys.executable, str(TOOLS / "body" / script), *map(str, args)], capture_output=True,
                          text=True, timeout=300)


def _aliases(tmp_path, src):
    """(label, path) aliases of src: the same path, another spelling, a hard link, a symlink when allowed."""
    out = [("same path", src), ("dotted path", src.parent / "." / src.name)]
    hard = tmp_path / "hard.json"
    os.link(src, hard)
    out.append(("hard link", hard))
    try:
        os.symlink(src, tmp_path / "sym.json")
        out.append(("symlink", tmp_path / "sym.json"))
    except OSError:
        pass  # Windows without symlink privilege: the other aliases still run
    return out


def test_contours_cli_refuses_every_alias_of_its_input_and_writes_a_distinct_output(tmp_path):
    src = _src_readback(tmp_path)
    before = src.read_bytes()
    for label, alias in _aliases(tmp_path, src):
        r = _run("contours.py", src, alias)
        assert r.returncode == 4 and "refused" in r.stderr, (label, r.returncode, r.stderr[-300:])
        assert src.read_bytes() == before, label
    ok = _run("contours.py", src, tmp_path / "c.json")
    assert ok.returncode == 0, ok.stderr[-400:]
    assert json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))["bands"] and src.read_bytes() == before


def test_kernel_prisms_cli_refuses_aliases_and_writes_a_distinct_output(tmp_path):
    src = _src_readback(tmp_path)
    assert _run("contours.py", src, tmp_path / "c.json").returncode == 0
    c = tmp_path / "c.json"
    before = c.read_bytes()
    for label, alias in _aliases(tmp_path, c):
        r = _run("kernel_prisms.py", c, alias)
        assert r.returncode == 4 and "refused" in r.stderr, (label, r.stderr[-300:])
        assert c.read_bytes() == before, label
    r = _run("kernel_prisms.py", c, tmp_path / "m.json")
    assert r.returncode == 0 and json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["prisms"] == 1


def test_guard_cli_refuses_output_output_alias_and_hard_linked_target(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text("{}", encoding="utf-8")
    with pytest.raises(sw.Refused, match="two outputs"):
        sw.guard_cli([a], [b, tmp_path / "." / "b.json"])
    os.link(a, tmp_path / "a2.json")
    with pytest.raises(sw.Refused):
        sw.guard_cli([b], [tmp_path / "a2.json"])  # a hard link of another file is never replaced
    sw.guard_cli([a], [b, tmp_path / "c.json"])  # control: distinct outputs pass


def _exec_max(cfg):
    """Run max_cleanup_pymxs.py with a stub pymxs that fails on first use: the guard must stop before it."""
    import types

    class Boom:
        def __getattr__(self, name):
            raise AssertionError(f"Max touched ({name}) before the alias guard")

    mod = types.ModuleType("pymxs")
    mod.runtime = Boom()
    sys.modules["pymxs"] = mod
    try:
        code = (TOOLS / "body" / "max_cleanup_pymxs.py").read_text(encoding="utf-8")
        exec(compile(code, "max_cleanup_pymxs.py", "exec"), {"CONFIG": cfg, "__name__": "__max__"})
    finally:
        del sys.modules["pymxs"]


@pytest.mark.parametrize("pair", [("src", "out"), ("src", "report"), ("out", "report")])
def test_max_cleanup_refuses_aliases_before_touching_max(tmp_path, pair):
    src = tmp_path / "copy.fbx"
    src.write_bytes(b"fbx")
    cfg = {"src": str(src), "out": str(tmp_path / "o.fbx"), "report": str(tmp_path / "o.fbx.variant.json")}
    cfg[pair[1]] = cfg[pair[0]]
    with pytest.raises(RuntimeError, match="refused"):
        _exec_max(cfg)
    assert src.read_bytes() == b"fbx" and not (tmp_path / "o.fbx.variant.json").exists()


def test_max_cleanup_distinct_paths_pass_the_guard_and_reach_max(tmp_path):
    src = tmp_path / "copy.fbx"
    src.write_bytes(b"fbx")
    cfg = {"src": str(src), "out": str(tmp_path / "o.fbx"), "report": str(tmp_path / "o.fbx.variant.json")}
    with pytest.raises(AssertionError, match="Max touched"):  # control: the guard lets it through to pymxs
        _exec_max(cfg)


# ---- review round 1: opening schedule (fail closed) and the Blender opening cut -------------------------------------

def test_opening_schedule_validates_and_names_the_bad_opening():
    assert bo.schedule({"bands": []}) == []
    ok = bo.schedule({"openings": [{"id": "W1", "min": [0, 0, 1], "max": [1, 0.5, 2]}]})
    assert ok == [{"id": "W1", "min": [0.0, 0.0, 1.0], "max": [1.0, 0.5, 2.0]}]
    bad = [({"openings": {}}, "must be a list"),
           ({"openings": [{"min": [0, 0, 0], "max": [1, 1, 1]}]}, "no id"),
           ({"openings": [{"id": "W2", "min": [0, 0, 0], "max": [1, 1, 1], "sill": 1}]}, r"'W2': unknown key"),
           ({"openings": [{"id": "W3", "min": [0, 0, 0], "max": [1, 1, 1]}] * 2}, "'W3': duplicate"),
           ({"openings": [{"id": "W4", "min": [0, 0, float("nan")], "max": [1, 1, 1]}]}, "'W4': non-finite"),
           ({"openings": [{"id": "W5", "min": [0, 0, 1], "max": [1, 1, 1]}]}, "'W5': min must be < max"),
           ({"openings": [{"id": "W6", "min": [0, 0], "max": [1, 1, 1]}]}, r"'W6': min must be \[x, y, z\]"),
           ({"openings": [{"id": "W7", "min": [0, "a", 0], "max": [1, 1, 1]}]}, "'W7': min is not numeric")]
    for data, msg in bad:
        with pytest.raises(ValueError, match=msg):
            bo.schedule(data)


def _square_contours(openings):
    ring = [[0, 0], [4, 0], [4, 4], [0, 4]]
    return {"schema": "body-contours/1", "synthetic_drawing": True, "levels_m": [0.0, 3.0],
            "bands": [{"z0": 0.0, "z1": 3.0, "polygons": [{"exterior": ring, "holes": []}]}], "openings": openings}


def _blender_body(tmp_path, data, name="c.json", out_name="SM_Test.fbx"):
    from dt_ai.core.blender_runner import blender_executable

    src = tmp_path / name
    src.write_text(json.dumps(data), encoding="utf-8")
    out = tmp_path / "v" / out_name
    out.parent.mkdir(exist_ok=True)
    r = subprocess.run([blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(TOOLS / "body" / "body_blender.py"), "--", "gn-union", str(src), str(out),
                        "SM_Test_Main"], capture_output=True, text=True, timeout=600)
    rep = out.with_name(out.name + ".variant.json")
    return r, out, (json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else None)


@pytest.mark.blender
def test_blender_gn_cuts_a_synthetic_opening_and_the_readback_shows_it(tmp_path):
    """SYNTHETIC opening schedule: a 1 x 0.5 x 1 m notch through the south face of a 4 x 4 x 3 m body."""
    from twinqa.scene import readback

    r, out, rep = _blender_body(tmp_path, _square_contours([{"id": "W1", "min": [1.5, -0.1, 1.0],
                                                             "max": [2.5, 0.5, 2.0]}]))
    assert r.returncode == 0 and rep["ok"], (rep, r.stderr[-500:])
    assert rep["openings"] == [{"id": "W1", "removed_m3": pytest.approx(0.5, abs=1e-6)}]
    rb = readback(out)
    s = mm.closed_shells(rb)
    assert s["closed_shell_share"] == 1.0, s  # the cut body stays one closed shell
    v, t = mm._mesh_soup(rb)
    tri = v[t]
    vol = abs(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2])).sum()) / 6
    assert vol == pytest.approx(48 - 0.5, abs=1e-3)
    # no surface left inside the opening: the notch centre is >= 0.25 m from every face
    assert mm.nearest_triangle_distance(np.array([[2.0, 0.25, 1.5]]), tri)[0] == pytest.approx(0.25, abs=1e-4)


@pytest.mark.blender
def test_blender_gn_opening_that_misses_the_body_is_an_error_naming_it(tmp_path):
    r, out, rep = _blender_body(tmp_path, _square_contours([{"id": "W9", "min": [10, 10, 1], "max": [11, 11, 2]}]))
    assert r.returncode == 1 and not rep["ok"] and "'W9' removes no volume" in rep["error"]
    r, out, rep = _blender_body(tmp_path, _square_contours([{"id": "W8", "min": [1, 1, 1], "max": [2, 2, 2],
                                                             "head": 2}]), name="c2.json")
    assert r.returncode == 1 and "'W8': unknown key" in rep["error"]


@pytest.mark.blender
def test_blender_body_refuses_output_aliasing_its_input(tmp_path):
    data = _square_contours([])
    r, out, rep = _blender_body(tmp_path, data, name="SM_Test.fbx")  # out_name collides only in another folder
    assert r.returncode == 0  # control: distinct paths build
    src = tmp_path / "v" / "same.json"
    src.write_text(json.dumps(data), encoding="utf-8")
    before = src.read_bytes()
    from dt_ai.core.blender_runner import blender_executable

    for target in (src, src.parent / "." / src.name):
        p = subprocess.run([blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
                            "--python", str(TOOLS / "body" / "body_blender.py"), "--", "gn-union", str(src),
                            str(target), "SM_Test_Main"], capture_output=True, text=True, timeout=600)
        assert p.returncode == 4 and "refused" in p.stderr and src.read_bytes() == before
    rep_alias = tmp_path / "v" / "x.fbx.variant.json"  # the input IS the report path of out=x.fbx
    rep_alias.write_text(json.dumps(data), encoding="utf-8")
    p = subprocess.run([blender_executable(), "--background", "--factory-startup", "--python-exit-code", "1",
                        "--python", str(TOOLS / "body" / "body_blender.py"), "--", "gn-union", str(rep_alias),
                        str(tmp_path / "v" / "x.fbx"), "SM_Test_Main"], capture_output=True, text=True, timeout=600)
    assert p.returncode == 4 and not (tmp_path / "v" / "x.fbx").exists()
    assert json.loads(rep_alias.read_text(encoding="utf-8")) == data


# ---- review round 2: combined regression of every guard fixed so far -------------------------------------------------

def test_combined_round1_and_round2_guards_on_one_input(tmp_path):
    """One input through every fixed guard: doubled sheet + box, blank vs [D187] marker, results alias, contours alias."""
    batch = _load_batch()
    sheet = mesh("SM_Test_Main_2", [(5, 0, 0), (6, 0, 0), (5, 1, 0)], [(0, 1, 2), (0, 2, 1)])
    (tmp_path / "src.json").write_text(json.dumps(rb_of(cube())), encoding="utf-8")
    bench = bench_file(tmp_path, classes=("building-body",))
    results = tmp_path / "results.jsonl"
    args = cli_args(tmp_path, rb_of(cube(), sheet), {"ok": False}, benchmarks=bench, results=results)
    args[args.index("ucx-collisions")] = "building-body"
    args += ["--source-readback", str(tmp_path / "src.json")]
    assert rv.main(args + ["--synthetic", "  "]) == 4 and not results.exists()  # blank marker: nothing written
    src = tmp_path / "src.json"
    before = src.read_bytes()
    alias = [a for a in args]
    alias[alias.index("--results") + 1] = str(src)  # results file aliasing an input: refused, input unchanged
    assert rv.main(alias + ["--synthetic", batch.synthetic_reason("kernel-prisms")]) == 4 and src.read_bytes() == before
    assert rv.main(args + ["--synthetic", batch.synthetic_reason("kernel-prisms")]) == 0  # control
    row = last_row(results)
    assert batch.SCOPE_DECISION == "D187" and row["synthetic"] is True
    assert "[D187]" in row["synthetic_reason"] and "D186" not in row["synthetic_reason"]
    assert row["class_metrics"]["body"]["closed_shell_share"] == pytest.approx(12 / 14, abs=1e-5)
    r = _run("contours.py", src, src)  # round-1 data-loss witness, fresh process
    assert r.returncode == 4 and src.read_bytes() == before


# --- #735: synthetic vs drawing side by side (user decision 2026-11-04 [D194]) ---

def _cmp_row(rid, bench, variant, tris, dev=(0.5, 0.2), shells=(1, 2), synthetic=True):
    r = {"row": rid, "class": "building-body", "benchmark": bench, "variant": variant, "triangles": {"model": tris},
         "class_metrics": {"body": {"deviation_max_m": dev[0], "deviation_p95_m": dev[1],
                                    "closed_components": shells[0], "components": shells[1]}}}
    if synthetic is not None:
        r["synthetic"] = synthetic
        if synthetic is True:
            r["synthetic_reason"] = "measured from the source mesh"
    return r


def _cmp_lines(md):
    part = md.split("Synthetic vs drawing", 1)[1]
    return [ln for ln in part.splitlines() if ln.startswith("| ") and not ln.startswith("| Object")]


def test_results_md_puts_synthetic_and_drawing_numbers_side_by_side():
    rows = [_cmp_row("R1", "kpp1", "kernel-prisms", 3896, (0.75, 0.275), (1, 2)),
            _cmp_row("R2", "kpp1", "kernel-prisms", 4100, (0.05, 0.01), (2, 2), synthetic=None)]
    lines = _cmp_lines(rmd.render(rows, "building-body"))
    assert lines == ["| kpp1 | kernel-prisms | R1 / R2 | 3896 / 4100 | 0.75 / 0.05 | 0.275 / 0.01 | 1/2 / 2/2 "
                     "| measured |"]


def test_synthetic_row_without_a_drawing_row_says_not_measured_never_a_number():
    lines = _cmp_lines(rmd.render([_cmp_row("R1", "ac08", "kernel-prisms", 40)], "building-body"))
    assert lines == ["| ac08 | kernel-prisms | R1 / - | 40 / - | 0.5 / - | 0.2 / - | 1/2 / - "
                     "| not measured: no drawing row in results.jsonl |"]


def test_drawing_row_without_a_synthetic_row_is_listed_not_dropped():
    rows = [_cmp_row("R1", "ac08", "kernel-prisms", 40),
            _cmp_row("R2", "tow02", "blender-gn-union", 900, synthetic=False)]
    lines = _cmp_lines(rmd.render(rows, "building-body"))
    assert len(lines) == 2 and lines[1].startswith("| tow02 | blender-gn-union | - / R2 | - / 900 |")
    assert lines[1].endswith("| no synthetic row |")


@pytest.mark.parametrize("dup", [True, None])
def test_two_rows_of_one_kind_for_one_object_and_variant_is_an_error_naming_them(dup):
    rows = [_cmp_row("R1", "kpp1", "kernel-prisms", 1, synthetic=dup),
            _cmp_row("R2", "kpp1", "kernel-prisms", 2, synthetic=dup), _cmp_row("R3", "kpp1", "x", 3)]
    with pytest.raises(ValueError, match=r"R1.*R2"):
        rmd.render(rows, "building-body")


@pytest.mark.parametrize("bad", ["false", "true", 1, 0, None.__class__])
def test_non_boolean_synthetic_marker_is_an_error_naming_the_row(bad):
    with pytest.raises(ValueError, match="R1"):
        rmd.render([_cmp_row("R1", "kpp1", "kernel-prisms", 1, synthetic=bad)], "building-body")


def test_no_synthetic_row_means_no_comparison_section():
    md = rmd.render([_cmp_row("R1", "kpp1", "kernel-prisms", 1, synthetic=None)], "building-body")
    assert "Synthetic vs drawing" not in md


def test_committed_building_body_results_md_is_regenerated_and_all_rows_stay_synthetic_per_d194():
    results = DECISIONS_MD.parent / "methods" / "building-body" / "results.jsonl"
    rows = rmd.read_rows(results)
    md = rmd.render(rows, "building-body")
    assert (results.parent / "RESULTS.md").read_text(encoding="utf-8") == md
    lines = _cmp_lines(md)
    assert len(lines) == 12 and all(ln.endswith("| not measured: no drawing row in results.jsonl |") for ln in lines)
    assert {(r["benchmark"], r["synthetic"]) for r in rows} == {("kpp1", True), ("ac08", True), ("tow02", True)}
    d194 = _decision_rows().get("D194", [])
    assert len(d194) == 1 and "#735" in d194[0] and "2026-11-04" in d194[0]
    assert id_collisions("D194", "#735", _decision_rows(), OPEN_PR_DECISIONS) == []
    for doc in ("VARIANTS.md", "WHEN.md"):
        assert "[D194]" in (results.parent / doc).read_text(encoding="utf-8"), doc
