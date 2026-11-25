"""#1736 shared body core: lattice builder, plan format, Revit + DWG adapters, jobs re-pointed.

Pattern: n/a | new-case: tests of tools/methods/body/body_lattice.py (pure core), plan_adapter_dwg.py, `agr body`.
"""
import importlib.util
import json
import math
import random
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BODY = ROOT / "tools" / "methods" / "body"
sys.path.insert(0, str(BODY))
import body_lattice as core  # noqa: E402
import plan_adapter_dwg as dwg  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _plan(**kw):
    p = {"step": 3.0, "z0": 10.0, "floors": 3, "loops": [0.0, 0.9, 2.4],
         "rings": [{"xy": [[0, 0], [12, 0], [12, 8], [0, 8]], "cuts": [3.0, 5.0, 7.0, 9.0], "zones":
                    [[0.0, 6.0, "WALL_A"], [6.0, 40.0, "WALL_B"]]}],
         "windows": [[0, 3.0, 5.0, 1, 2, 0.2], [0, 7.0, 9.0, 1, 2, 0.0]],
         "insets": [{"box": [6.0, 8.0, 0.3, 1.0, 0.5, 0.6, 180.0]}],
         "materials": {"WALL_A": [1, 1, 1], "WALL_B": [0.5, 0.5, 0.5], "WINDOW": [0, 0, 1], "INSET": [0, 1, 1]},
         "wall_tile_m": 3.0}
    p.update(kw)
    return p


def _edges(faces):
    cnt = {}
    for f in faces:
        v = f["v"]
        for a, b in zip(v, v[1:] + v[:1]):
            cnt[frozenset((a, b))] = cnt.get(frozenset((a, b)), 0) + 1
    return cnt


# ---- module: lattice by construction ----------------------------------------------------------------------
def test_module_is_all_quads_with_reveal_on_shared_vertices():
    m = core.build_module(_plan())
    n_st = 4 + 4  # 4 corners + 4 cuts
    walls = n_st * 3 - 1  # 3 bands, one cell removed by the r > 0 opening
    reveal = 2 * 1 + 2 * 1  # jambs (1 band) + sill + head (1 segment)
    assert len(m["faces"]) == walls + reveal + 6
    assert all(len(f["v"]) == 4 for f in m["faces"])  # facade triangles: 0 (decision 4)
    rv = [f for f in m["faces"] if f["mat"] == "WALL_A" and len({round(m["verts"][i][1], 6) for i in f["v"]}) > 1
          and all(m["verts"][i][1] <= 0.2 + 1e-9 for i in f["v"]) and any(m["verts"][i][1] > 1e-9 for i in f["v"])]
    assert len(rv) == 4  # the reveal tube of the s=3..5 opening
    grid = set(range(n_st * 4))
    assert all(len(set(f["v"]) & grid) == 2 for f in rv)  # every reveal quad welded to the wall on 2 vertices
    assert m["report"]["openings"] == 1 and m["report"]["reveal_faces"] == 4
    assert m["materials"] == ["WALL_A", "WALL_B", "WINDOW", "INSET"]
    # the wall + reveal shell has open edges only at the reveal back (stage-2 window) and the band top/bottom
    shell = [f for f in m["faces"] if f["mat"] != "INSET"]
    open_e = [e for e, c in _edges(shell).items() if c == 1]
    zs = lambda e: {round(m["verts"][i][2], 6) for i in e}  # noqa: E731
    back = [e for e in open_e if all(abs(m["verts"][i][1] - 0.2) < 1e-9 for i in e)]
    assert len(back) == 4 and all(zs(e) <= {0.0, 3.0} for e in open_e if e not in back)


def test_wall_faces_point_outward_and_reveal_faces_into_the_opening():
    m = core.build_module(_plan(insets=[]))
    for f in m["faces"]:
        co = [m["verts"][i] for i in f["v"]]
        n = core._newell(co)
        c = [sum(p[k] for p in co) / 4 for k in range(3)]
        if all(abs(p[1]) < 1e-9 for p in co):  # south wall y = 0: outward = -y
            assert n[1] < 0
        if f["mat"] == "WALL_A" and abs(n[2]) > 1e-9:  # sill faces up at z 0.9, head down at z 2.4
            assert (n[2] > 0) == (abs(c[2] - 0.9) < 1e-9)


def test_inset_box_is_a_separate_closed_shell_outside_the_wall():
    m = core.build_module(_plan())
    box = [f for f in m["faces"] if f["mat"] == "INSET"]
    assert len(box) == 6 and all(c == 2 for c in _edges(box).values())
    ids = {i for f in box for i in f["v"]}
    assert not ids & {i for f in m["faces"] if f["mat"] != "INSET" for i in f["v"]}  # BM-04 / D336: not welded
    assert all(m["verts"][i][1] >= 8.0 - 1e-9 for i in ids)  # d along the outward normal of the north wall


def test_replicate_welds_the_shared_level_once():
    p = _plan(insets=[])
    m = core.build_module(p)
    b = core.replicate(m, p)
    n_lvl = 8  # stations on a ring level
    assert len(b["verts"]) == p["floors"] * len(m["verts"]) - (p["floors"] - 1) * n_lvl
    assert len(b["faces"]) == p["floors"] * len(m["faces"])
    assert len({tuple(round(c, 6) for c in v) for v in b["verts"]}) == len(b["verts"])  # no duplicate vertex
    assert b["report"]["body"] == {"verts": len(b["verts"]), "faces": len(b["faces"]), "floors": 3}


def test_max_side_from_plan_or_argument_splits_long_sides():
    p = _plan(windows=[], insets=[], rings=[{"xy": [[0, 0], [12, 0], [12, 8], [0, 8]]}],
              materials={"WALL_A": [1, 1, 1]})
    assert core.build_module(p)["report"]["rings"][0]["points"] == 4
    assert core.build_module(dict(p, max_side_m=3.6))["report"]["rings"][0]["points"] == 4 + 3 + 2 + 3 + 2
    assert core.build_module(p, max_side=3.6)["report"]["rings"][0]["points"] == 14


# ---- depth field corner (#1742 §5.7b) ---------------------------------------------------------------------
def _old_inner_offset(xy, r):  # module_build before #1736 (mitre at one depth)
    pts = [tuple(map(float, p)) for p in xy]
    nrm = [(-(q[1] - p[1]) / math.dist(p, q), (q[0] - p[0]) / math.dist(p, q)) for p, q in zip(pts, pts[1:])]
    out = []
    for i, (x, y) in enumerate(pts):
        n1, n2 = nrm[max(0, i - 1)], nrm[min(len(nrm) - 1, i)]
        mx, my = n1[0] + n2[0], n1[1] + n2[1]
        m = math.hypot(mx, my)
        mx, my = mx / m, my / m
        k = r / (mx * n1[0] + my * n1[1])
        out.append((x + mx * k, y + my * k))
    return out


def test_offset_run_probe_corner_on_both_offset_lines():
    rng = random.Random(1736)
    n_ok = n = 0
    for _ in range(500):
        a = rng.uniform(-170, 170)  # turn at the corner, sharp concave and convex included
        L1, L2 = rng.uniform(0.5, 5), rng.uniform(0.5, 5)
        p0, p1 = (0.0, 0.0), (L1, 0.0)
        p2 = (L1 + L2 * math.cos(math.radians(a)), L2 * math.sin(math.radians(a)))
        d1, d2 = rng.uniform(0.01, 0.9), rng.uniform(0.01, 0.9)
        n += 1
        o = core.offset_run([p0, p1, p2], [d1, d2])
        # distance of the corner to each side's line = that side's depth, on the inner (left) side
        def side_dist(p, q, x):
            return ((q[0] - p[0]) * (x[1] - p[1]) - (q[1] - p[1]) * (x[0] - p[0])) / math.dist(p, q)
        if abs(side_dist(p0, p1, o[1]) - d1) < 1e-9 and abs(side_dist(p1, p2, o[1]) - d2) < 1e-9:
            n_ok += 1
    assert n_ok == n == 500


def test_offset_run_equal_depth_equals_the_old_mitre():
    rng = random.Random(7)
    for _ in range(200):
        pts = [(0.0, 0.0)]
        ang = 0.0
        for _ in range(4):
            ang += rng.uniform(-80, 80)
            L = rng.uniform(0.5, 3)
            pts.append((pts[-1][0] + L * math.cos(math.radians(ang)), pts[-1][1] + L * math.sin(math.radians(ang))))
        r = rng.uniform(0.05, 0.5)
        assert all(math.dist(a, b) < 1e-9 for a, b in zip(core.inner_offset(pts, r), _old_inner_offset(pts, r)))


@pytest.mark.parametrize("depths", [[0.0, 0.2], [0.2, 1.0], [float("nan"), 0.2], [0.2, float("inf")], [0.2]])
def test_offset_run_fails_closed(depths):
    with pytest.raises(ValueError):
        core.offset_run([(0, 0), (1, 0), (1, 1)], depths)


def test_offset_run_refuses_fold_back():
    with pytest.raises(ValueError, match="folds back"):
        core.offset_run([(0, 0), (1, 0), (0, 0.0 + 0.0)], [0.2, 0.2])


# ---- plan format: fail closed -----------------------------------------------------------------------------
BAD = [
    ({}, "misses"),
    (dict(_plan(), step=float("nan")), "step"),
    (dict(_plan(), step=float("inf")), "step"),
    (dict(_plan(), floors=0), "floors"),
    (dict(_plan(), floors=True), "floors"),
    (dict(_plan(), loops=[0.5, 1.0]), "loops"),
    (dict(_plan(), loops=[0.0, 3.0]), "loops"),  # exactly at step = outside the module
    (dict(_plan(), loops=[]), "loops"),
    (dict(_plan(), rings=[{"xy": [[0, 0], [0, 8], [12, 8], [12, 0]]}]), "counter-clockwise"),
    (dict(_plan(), rings=[{"xy": [[0, 0], [1, 0]]}]), "xy"),
    (dict(_plan(), rings=[{"xy": [[0, 0], [1, 0], [1, float("nan")]]}]), "xy"),
    (dict(_plan(), rings=[{"xy": [[0, 0], [12, 0], [12, 8], [0, 8]], "zones": [[0, 40, "MISSING"]]}]), "MISSING"),
    (dict(_plan(), windows=[[0, 3.0, 5.0, 1, 4, 0.2]]), "loops inside"),
    (dict(_plan(), windows=[[0, 3.0, 5.0, 1, 2, 1.0]]), "reveal"),
    (dict(_plan(), windows=[[1, 3.0, 5.0, 1, 2, 0.2]]), "ring index"),
    (dict(_plan(), windows=[[0, 3.0, 5.0, 1, 2, float("nan")]]), "finite"),
    (dict(_plan(), insets=[{"box": [0, 0, 0, 0, 1, 1, 0]}]), "w, d, h"),
    (dict(_plan(), materials={}), "materials"),
]


@pytest.mark.parametrize("plan,word", BAD)
def test_validate_plan_fails_closed_naming_the_key(plan, word):
    with pytest.raises(ValueError, match=word):
        core.validate_plan(plan)


def test_face_in_no_zone_is_an_error():
    p = _plan(rings=[{"xy": [[0, 0], [12, 0], [12, 8], [0, 8]], "cuts": [3.0, 5.0, 7.0, 9.0],
                      "zones": [[0.0, 6.0, "WALL_A"]]}])
    with pytest.raises(ValueError, match="no finish zone"):
        core.build_module(p)


def test_load_plan_rejects_duplicate_keys(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{"step": 3, "step": 4}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        core.load_plan(f)


# ---- lines from the openings list [D373] --------------------------------------------------------------
def test_keep_lines_threshold_and_openings():
    kept, dropped = core.keep_lines([
        {"at": 0.9, "reason": "opening", "length": 0.8, "width": 0.8},   # an opening line is always a reason
        {"at": 0.4, "reason": "zone", "length": 1.4},                    # < 1.5 m -> texture
        {"at": 3.3, "reason": "belt", "length": 1.5},                    # exactly at threshold -> kept
        {"at": 2.0, "reason": "niche", "length": 0.7}, {"at": 2.0, "reason": "niche", "length": 0.8},  # no sum
        {"at": 2.6, "reason": "zone", "length": 0.4}, {"at": 2.6, "reason": "zone", "length": 1.6}])
    assert kept == [0.9, 2.6, 3.3]
    assert [d["at"] for d in dropped] == [0.4, 2.0] and all("texture" in d["why"] for d in dropped)


@pytest.mark.parametrize("bad", [{"at": float("nan"), "reason": "zone", "length": 2},
                                 {"at": 1, "reason": "vertex", "length": 2},
                                 {"at": 1, "reason": "zone", "length": -1}])
def test_keep_lines_fails_closed(bad):
    with pytest.raises(ValueError):
        core.keep_lines([bad])


def test_snap_ten_cm_and_fail_closed():
    assert core.snap(0.94) == 0.9 and core.snap(0.95) in (0.9, 1.0) and core.snap(2.449) == 2.4
    for v in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            core.snap(v)


# ---- adapters: both give the plan format the core reads ---------------------------------------------------
def test_revit_route_floor_from_dump_is_a_body_plan(tmp_path):
    r5 = _load(ROOT / "tests" / "test_body_training_1619_r5.py", "r5_for_1736")
    spec = r5._spec(tmp_path, r5._crop(tmp_path), "--openings")
    core.validate_plan(spec)
    m = core.build_module(spec)
    assert m["report"].get("openings", 0) == len(spec["windows"]) > 0
    assert all(len(f["v"]) == 4 for f in m["faces"])


KPP1 = ROOT / "docs" / "methods" / "building-body" / "kpp1-drawing" / "plan-contours.json"
CFG = {"materials": {"WALL_A": [0.8, 0.8, 0.8]}, "zone": "WALL_A"}


def test_dwg_route_kpp1_drawing_is_a_body_plan():
    plans, rep = dwg.adapt(json.loads(KPP1.read_text(encoding="utf-8")), CFG)
    assert [(p["z0"], p["step"]) for p in plans] == [(0.0, 3.9), (3.9, 4.009)]
    for p in plans:
        core.validate_plan(p)
        m = core.build_module(p)
        assert all(len(f["v"]) == 4 for f in m["faces"]) and m["report"]["module"]["tris"] == 0
    assert all(d["why"].startswith(("collinear", "duplicate", "outer")) for d in rep["dropped"])
    # same top-level format as the Revit route
    assert set(core.REQUIRED) <= set(plans[0])


def _box_contours():
    return {"schema": "body-contours/1", "bands": [{"z0": 0.0, "z1": 4.0, "polygons": [
        {"exterior": [[0, 0], [10, 0], [10, 6], [0, 6]], "holes": [[[1, 1], [2, 1], [2, 2]]]}]}]}


def test_dwg_route_places_openings_by_the_explicit_facade_map():
    ops = {"openings": [{"id": "W1", "facade": "south", "left_m": 2.04, "right_m": 3.52, "sill_m": 0.93,
                         "head_m": 2.41},
                        {"id": "W2", "facade": "south", "left_m": 5.0, "right_m": 6.0, "sill_m": 3.5,
                         "head_m": 4.5}]}  # crosses the band top
    cfg = dict(CFG, facades={"south": {"ring_s0_m": 0.0, "direction": 1, "reveal_m": 0.2}})
    (plan,), rep = dwg.adapt(_box_contours(), cfg, ops)
    assert plan["loops"] == [0.0, 0.9, 2.4] and plan["windows"] == [[0, 2.0, 3.5, 1, 2, 0.2]]
    assert {2.0, 3.5} <= set(plan["rings"][0]["cuts"])
    whys = {d.get("what"): d["why"] for d in rep["dropped"]}
    assert whys["W2"] == "opening crosses the band" and any("hole" in str(k) for k in whys)
    m = core.build_module(plan)
    assert m["report"]["openings"] == 1 and m["report"]["module"]["tris"] == 0


def test_dwg_route_unmapped_facade_is_an_error_naming_it():
    ops = {"openings": [{"id": "W9", "facade": "east", "left_m": 1, "right_m": 2, "sill_m": 1, "head_m": 2}]}
    with pytest.raises(ValueError, match="'east'"):
        dwg.adapt(_box_contours(), dict(CFG, facades={}), ops)


def test_dwg_route_unknown_zone_material_and_schema_are_errors():
    with pytest.raises(ValueError, match="zone"):
        dwg.adapt(_box_contours(), {"materials": {"A": [1, 1, 1]}, "zone": "B"})
    with pytest.raises(ValueError, match="schema"):
        dwg.adapt({"schema": "other"}, CFG)


def test_dwg_cli_refuses_output_holding_an_input(tmp_path):
    c = tmp_path / "c.json"
    c.write_text(json.dumps(_box_contours()), encoding="utf-8")
    g = tmp_path / "g.json"
    g.write_text(json.dumps(CFG), encoding="utf-8")
    assert dwg.main([str(c), str(g), str(tmp_path)]) == 2  # exists + holds the inputs
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c.json", "g.json"]
    assert dwg.main([str(c), str(g), str(tmp_path / "out")]) == 0
    assert dwg.main([str(c), str(g), str(tmp_path / "out")]) == 2  # second run: exists


# ---- jobs call the core -----------------------------------------------------------------------------------
def test_jobs_call_the_core_and_define_no_builder():
    mb = _load(ROOT / "jobs/garibaldi22/body-training-1619/hooks/module_build.py", "mb_1736")
    assert mb.inner_offset is core.inner_offset and mb.box_corners is core.box_corners
    assert mb.jamb_uv is core.jamb_uv
    for rel in ("jobs/garibaldi22/body-training-1619/hooks/module_build.py", "jobs/POLY63-C/hooks/build_body.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "body_lattice" in src and "bmesh" not in src.split("def _run_stage2")[0]
        assert "git\", \"show" not in src
    sk = json.loads((ROOT / "docs/agents/skeletons.json").read_text(encoding="utf-8"))
    body = sk["stages"]["body"] if "stages" in sk else sk["body"]
    assert "tools/methods/body/body_lattice.py" in body["owners"] and "agr body" in body["calls"]
    assert {"build_module", "replicate", "offset_run", "inner_offset"} <= set(body["entry_defs"])


def test_agr_body_help_and_usage():
    from dt_ai.cli import agr
    assert agr.main(["body", "--help"]) == 0
    assert agr.main(["body"]) == 2


BLENDER = Path("C:/Program Files/Blender Foundation/Blender 4.4/blender.exe")


@pytest.mark.skipif(not BLENDER.exists(), reason="Blender 4.4 not installed")
def test_blender_writer_matches_the_pure_core_and_refuses_existing_out(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(_plan()), encoding="utf-8")
    out = tmp_path / "out"
    w = str(BODY / "body_lattice_blender.py")
    cmd = [str(BLENDER), "-b", "--factory-startup", "--python-exit-code", "1", "--python", w, "--", str(plan), str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    rep = json.loads((out / "build.json").read_text(encoding="utf-8"))
    pure = core.replicate(core.build_module(_plan()), _plan())["report"]
    assert rep["module"] == pure["module"] and rep["body"] == pure["body"]
    assert {p.name for p in out.iterdir()} >= {"module.blend", "body.blend", "body.fbx", "build.json"}
    r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    assert r2.returncode != 0 and "refused" in (r2.stdout + r2.stderr)


# ---- lines of a new building from the openings list (KPP1 route) [D373] --------------------------
SPEC = {"S": {"surrounds": [{"rect": [0.3, 5.3, 1.125, 6.7]}], "doors": [{"rect": [6.0, 7.2, 0.0, 2.1]}],
              "grilles": [[8.0, 8.4, 3.05, 3.45], [9.0, 9.4, 3.05, 3.45], [10.0, 10.4, 3.05, 3.45],
                          [11.0, 11.4, 3.05, 3.45]]},
        "N": {"portals": [{"rect": [1.0, 4.0, 0.9, 2.7]}], "surrounds": [[0.5, 1.5, 4.8, 6.7]]}}


def test_lines_from_facades_snaps_and_drops_small_pieces():
    r = dwg.lines_from_facades(SPEC, 0.0, 3.9)
    assert r["levels"] == [0.9, 1.1, 2.1, 2.7]  # four 0.4 m grilles on one line stay texture (no summing)
    assert sorted(d["at"] for d in r["levels_dropped"]) == [3.0, 3.4]
    assert r["stations"]["S"] == [0.3, 5.3, 6.0, 7.2] and r["stations"]["N"] == [1.0, 4.0]
    assert [o["rect"] for o in r["outside"]] == [[0.5, 1.5, 4.8, 6.7]]  # every element: kept or reported
    assert len(r["elements"]) + len(r["outside"]) == 8


@pytest.mark.parametrize("spec,word", [({"S": {"balcony": [[0, 1, 0, 1]]}}, "balcony"),
                                       ({"S": {"doors": [[0, 1, 0, float("nan")]]}}, "finite"),
                                       ({"S": {"doors": [[1, 0, 0, 1]]}}, "u0 < u1"),
                                       ({"S": {"doors": [[0, 1, 0]]}}, "4 finite")])
def test_lines_from_facades_fails_closed(spec, word):
    with pytest.raises(ValueError, match=word):
        dwg.lines_from_facades(spec, 0.0, 3.9)


def test_lines_cli_and_sheet_refuse_existing_output(tmp_path):
    sheet = _load(BODY / "lines_sheet.py", "lines_sheet_1736")
    src = tmp_path / "spec.json"
    src.write_text(json.dumps(SPEC), encoding="utf-8")
    out = tmp_path / "lines.json"
    assert dwg.main(["lines", str(src), "0", "3.9", str(src)]) == 2  # output = input
    assert dwg.main(["lines", str(src), "0", "nan", str(out)]) == 2 and not out.exists()
    assert dwg.main(["lines", str(src), "0", "3.9", str(out)]) == 0
    assert dwg.main(["lines", str(src), "0", "3.9", str(out)]) == 2
    png = tmp_path / "s.png"
    assert sheet.main([str(out), str(png)]) == 0 and png.stat().st_size > 0
    assert sheet.main([str(out), str(png)]) == 2


# ---- hard check: every level a closed ring, every station a continuous vertical (KPP1 step 1) [D373] -----
def _ring_ctx(p):
    m = core.build_module(p)
    pts, perim = core.ring_points(p["rings"][0]["xy"], p["rings"][0].get("cuts", []))
    n, levels = len(pts), p["loops"] + [p["step"]]
    grid = [[li * n + k for k in range(n)] for li in range(len(levels))]
    wins = [(w[1], w[2], int(w[3]), int(w[4]), float(w[5])) for w in p["windows"]]
    return m, grid, pts, perim, wins


def test_ring_closure_reported_and_gaps_only_inside_openings():
    p = _plan(insets=[], windows=[[0, 3.0, 7.0, 0, 3, 0.2]], loops=[0.0, 0.9, 2.4])  # tall opening, 2 inner levels
    p["rings"][0]["cuts"] = [3.0, 5.0, 7.0]
    m = core.build_module(p)
    c = m["report"]["rings"][0]["closure"]
    assert c["closed_levels"] == c["levels"] == 4 and c["continuous_stations"] == c["stations"]
    assert c["gaps_in_openings"] == 2 * 2 + 3  # levels 1, 2 x 2 segments; station s=5 x 3 bands


def test_ring_closure_probe_every_removed_lattice_edge_is_caught():
    p = _plan(insets=[])
    m, grid, pts, perim, wins = _ring_ctx(p)
    n = len(pts)
    lattice = [frozenset((grid[li][k], grid[li][(k + 1) % n])) for li in range(len(grid)) for k in range(n)]
    lattice += [frozenset((grid[li][k], grid[li + 1][k])) for li in range(len(grid) - 1) for k in range(n)]
    present = [e for e in lattice if any(e <= set(f["v"]) and len(e & set(f["v"])) == 2 for f in m["faces"])]
    caught = 0
    for e in present:  # brute force: cut each lattice edge (drop the faces on it): a loop now ends there
        faces = [f for f in m["faces"] if not e <= set(f["v"])]
        try:
            core.ring_closure(faces, grid, pts, perim, wins)
        except ValueError as err:
            caught += ("ring not closed" in str(err) or "vertical loop broken" in str(err))
    assert caught == len(present) == len(lattice)  # this plan has no inner-opening gaps


# Review r1 P1-1 (PR #1770): a window edge off its ring's stations or outside [0, perimeter]
# used to be silently resized, dropped or left as a hole without reveal.
@pytest.mark.parametrize("win", [
    [0, 1.0, 5.5, 1, 2, 0.2],    # off-station both ends, r>0: hole at 0..3, no reveal
    [0, 2.5, 5.5, 1, 2, 0.2],    # off-station both ends, r>0: opening built at 3..5
    [0, 3.5, 4.5, 1, 2, 0.0],    # off-station, r=0: whole cell 3..5 painted WINDOW
    [0, 100.0, 102.0, 1, 2, 0.0],  # beyond the perimeter (40 m): dropped with no report
    [0, 3.0, 5.5, 1, 2, 0.2],    # one end on a station, the other off
    [0, -1.0, 3.0, 1, 2, 0.0],   # negative start
])
def test_window_edges_must_be_stations_of_its_ring(win):
    p = _plan(windows=[win])
    with pytest.raises(ValueError, match="window") as e:
        core.build_module(p)
    assert repr(win[1]) in str(e.value) or str(win[1]) in str(e.value)


def test_window_on_station_control_and_max_side_stations_are_accepted():
    m = core.build_module(_plan(windows=[[0, 3.0, 5.0, 1, 2, 0.2], [0, 7.0, 9.0, 1, 2, 0.0]]))
    assert m["report"]["rings"][0]["closure"]
    # a station produced by the max_side split (12 m side / 3.6 -> 4 pieces of 3.0 m at s=3,6,9) is valid
    p = _plan(rings=[{"xy": [[0, 0], [12, 0], [12, 8], [0, 8]], "cuts": [],
                      "zones": [[0.0, 40.0, "WALL_A"]]}], windows=[[0, 6.0, 9.0, 1, 2, 0.2]])
    core.build_module(p, max_side=3.6)
    with pytest.raises(ValueError, match="not a station of ring 0"):
        core.build_module(p)  # without the split 6..9 are not stations (new check names it)
