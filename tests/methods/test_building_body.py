"""building-body class metrics on tiny synthetic inputs (#727).

Pattern: new-case: tests of the building-body methods class (deviation, closed shells, budget, null paths).
"""
from __future__ import annotations

import json

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
    assert rv.main(args + ["--source-readback", str(tmp_path / "src.json")]) == 0
    body = last_row(tmp_path / "results.jsonl")["class_metrics"]["body"]
    assert body["deviation_max_m"] == pytest.approx(0.2, abs=1e-6) and body["closed_shell_share"] == 1.0
    md = rmd.write(tmp_path / "results.jsonl").read_text(encoding="utf-8")
    assert "Deviation src->variant max / p95 m" in md and "| 0.2 / " in md and "1/1 (100.0%)" in md


def test_cli_missing_source_fbx_is_an_error_and_appends_nothing(tmp_path):
    bench = bench_file(tmp_path, classes=("building-body",))  # source C:/synthetic/SM_Test.fbx does not exist
    args = cli_args(tmp_path, rb_of(cube()), {"ok": False}, benchmarks=bench, results=tmp_path / "results.jsonl")
    args[args.index("ucx-collisions")] = "building-body"
    assert rv.main(args) == 2
    assert not (tmp_path / "results.jsonl").exists()


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
