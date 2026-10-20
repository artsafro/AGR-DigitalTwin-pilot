"""Site placement wrapper (#296): engine output -> scene plan -> scene check, synthetic data only."""
import copy
import math
import random

import pytest

from dt_ai.placement import engine
from tools import placement_site as ps

OFFSET = [100.0, 200.0, 0.0]


def ground(z0=10.0, slope=0.05, n=6, size=20.0):
    """Tilted synthetic Ground grid around (100, 200) in world coordinates (synthetic)."""
    vs, ts = [], []
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = 90.0 + size * i / n, 190.0 + size * j / n
            vs.append([x, y, z0 + slope * (x - 90.0)])
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            ts += [[a, a + 1, a + n + 2], [a, a + n + 2, a + n + 1]]
    return vs, ts


def box_facts(lo, hi, bottom=True):
    pts = [[lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]], [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]]]
    return {"bbox_min": lo, "bbox_max": hi, "triangles": 12, "polygons": 6,
            "bottom_faces": [{"index": 0, "points": pts}] if bottom else []}


FACTS = {"TREE": box_facts([-1.0, -1.0, 0.0], [1.0, 1.0, 5.0], bottom=False),
         "BENCH": box_facts([-0.9, -0.25, 0.0], [0.9, 0.25, 0.8])}


def points(n=12, seed=7):
    rnd = random.Random(seed)
    out = []
    for k in range(n):
        lab = "Липа" if k % 2 else "Скамья"
        out.append({"x": 95 + 10 * rnd.random(), "y": 195 + 10 * rnd.random(), "z": 0.0, "label": lab,
                    "handle": f"H{k:03d}", "inside": True, "rotation": 360 * rnd.random(), "position": None})
    return out


ASSIGN = {"Липа": "TREE", "Скамья": "BENCH"}


def library():
    return [ps.flora_entry("TREE", FACTS["TREE"], (4.5, 5.5)),
            ps.maf_entry("BENCH", FACTS["BENCH"], [1.8, 0.5, 0.8])]


def run(seed=11, pts=None):
    vs, ts = ground()
    keep, excl = ps.select_points(pts if pts is not None else points(), ASSIGN)
    rep = engine.place(keep, vs, ts, library(), seed, label_map=ASSIGN)
    return rep, excl


def fake_readback(rep, plan, facts=FACTS):
    """What a correct DCC returns: plan matrices, polygons minus deleted, exact sinking (synthetic)."""
    rows = []
    for it in plan["instances"]:
        e = next(i for i in rep["instances"] if i["handle"] == it["handle"])
        rows.append({"name": it["name"], "handle": it["handle"], "library_id": it["library_id"],
                     "matrix": copy.deepcopy(it["matrix"]),
                     "polygons": facts[it["library_id"]]["polygons"] - len(it["delete_polygons"]),
                     "lowest_z": e["ground_z"] - e["sink_m"] - OFFSET[2],
                     "ground_z_at_pivot": e["ground_z"] - OFFSET[2]})
    return {"seed": plan["seed"], "instances": rows,
            "library_polygons": {k: v["polygons"] for k, v in facts.items()}}


# ---------------------------------------------------------------- selection
def test_select_points_lists_every_excluded_point():
    pts = points()
    pts[0]["inside"] = False
    pts[1]["label"] = "Ольха"
    pts[2]["inside"] = None
    keep, excl = ps.select_points(pts, {**ASSIGN, "Ольха": None})
    assert len(keep) + len(excl) == len(pts)
    assert {e["handle"]: e["reason"] for e in excl} == {"H000": "outside_boundary", "H001": "no_library_model",
                                                        "H002": "outside_boundary"}


# ---------------------------------------------------------------- base scale / entries
@pytest.mark.parametrize("h,band,exp", [(5.0, (4.5, 5.5), 1.0), (0.99, (1.25, 2.0), None), (7.0, (4.5, 5.5), None)])
def test_flora_base_scale_lands_inside_band(h, band, exp):
    s = ps.flora_base_scale(h, band)
    if exp is not None:
        assert s == exp
    e = ps.flora_entry("X", {"bbox_min": [0, 0, 0], "bbox_max": [1, 1, h * s]}, band)
    rep = engine.place([], [[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], [e], 1)
    assert rep["library"]["X"]["valid"] is True, rep["library"]


@pytest.mark.parametrize("bad", [(float("nan"), (1, 2)), (1.0, (0, 2)), (1.0, (2, 1)), (-1.0, (1, 2)),
                                 (1.0, (1, float("inf")))])
def test_flora_base_scale_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        ps.flora_base_scale(*bad)


def test_flora_base_scale_exactly_at_band_edge_is_inside():
    assert ps.flora_base_scale(0.8 * 1.25, (1.25, 2.0)) == 1.0
    assert ps.flora_base_scale(1.2 * 2.0, (1.25, 2.0)) == 1.0


# ---------------------------------------------------------------- plan
def test_plan_equals_engine_output_and_scene_check_passes():
    rep, _ = run()
    assert rep["status"] in ("pass", "review"), rep["findings"]
    plan = ps.make_plan(rep, FACTS, OFFSET)
    assert len(plan["instances"]) == rep["totals"]["placed"] == 12
    rb = fake_readback(rep, plan)
    assert ps.compare_scene(rep, rb, FACTS, OFFSET) == []
    s = ps.sinking(rb, kind_of={"TREE": "flora", "BENCH": "maf"})
    assert s["ok"] and s["measured"] == 12 and set(s["per_kind"]) == {"flora", "maf"}


def test_plan_deletes_only_engine_delete_faces():
    rep, _ = run()
    plan = ps.make_plan(rep, FACTS, OFFSET)
    for it, e in zip(sorted(plan["instances"], key=lambda d: d["handle"]), rep["instances"]):
        want = [0] if any(v["action"] == "delete" for v in e.get("bottom_faces", [])) else []
        assert it["delete_polygons"] == want


@pytest.mark.parametrize("mutate", ["fail_status", "failed_point", "error_finding", "no_instances", "nan_offset"])
def test_plan_stops_on_engine_failure(mutate):
    rep, _ = run()
    off = list(OFFSET)
    if mutate == "fail_status":
        rep["status"] = "fail"
    elif mutate == "failed_point":
        rep["failed"] = [{"handle": "HX", "library_id": "TREE", "code": "point_outside_ground"}]
    elif mutate == "error_finding":
        rep["findings"].append({"code": "seed_invalid", "severity": "error", "handle": None,
                                "library_id": None, "detail": "x"})
    elif mutate == "no_instances":
        rep["instances"] = []
    else:
        off[0] = float("nan")
    with pytest.raises(ps.PlacementStopped):
        ps.make_plan(rep, FACTS, off)


def test_point_outside_ground_stops_the_run():
    pts = points()
    pts[3]["x"] = 500.0
    rep, _ = run(pts=pts)
    with pytest.raises(ps.PlacementStopped) as ei:
        ps.make_plan(rep, FACTS, OFFSET)
    assert any("H003" in r for r in ei.value.reasons)


def test_missing_library_id_stops_the_run():
    vs, ts = ground()
    keep, _ = ps.select_points(points(), ASSIGN)
    rep = engine.place(keep, vs, ts, library()[:1], 11, label_map=ASSIGN)
    with pytest.raises(ps.PlacementStopped):
        ps.make_plan(rep, FACTS, OFFSET)


# ---------------------------------------------------------------- scene check catches every deviation
@pytest.mark.parametrize("mutate", ["drop", "extra", "rot", "scale", "pivot", "library", "seed", "polygons",
                                    "nan", "duplicate"])
def test_compare_scene_detects_deviation(mutate):
    rep, _ = run()
    plan = ps.make_plan(rep, FACTS, OFFSET)
    rb = fake_readback(rep, plan)
    r0 = rb["instances"][0]
    if mutate == "drop":
        rb["instances"].pop(0)
    elif mutate == "extra":
        rb["instances"].append({**copy.deepcopy(r0), "handle": "ZZZ"})
    elif mutate == "rot":
        a = math.radians(1.0)
        M = r0["matrix"]
        for i in range(2):
            x, y = M[0][i], M[1][i]
            M[0][i], M[1][i] = math.cos(a) * x - math.sin(a) * y, math.sin(a) * x + math.cos(a) * y
    elif mutate == "scale":
        for i in range(3):
            for j in range(3):
                r0["matrix"][i][j] *= 1.001
    elif mutate == "pivot":
        r0["matrix"][2][3] += 0.01
    elif mutate == "library":
        r0["library_id"] = "BENCH" if r0["library_id"] == "TREE" else "TREE"
    elif mutate == "seed":
        rb["seed"] = 12
    elif mutate == "polygons":
        r0["polygons"] += 1
    elif mutate == "nan":
        r0["matrix"][0][3] = float("nan")
    else:
        rb["instances"].append(copy.deepcopy(r0))
    assert ps.compare_scene(rep, rb, FACTS, OFFSET) != []


def test_other_seed_same_counts_different_rotations():
    a, _ = run(seed=1)
    b, _ = run(seed=2)
    assert a["counts"] == b["counts"]
    ra = {i["handle"]: i["rot_z_deg"] for i in a["instances"] if i["kind"] == "flora"}
    rb = {i["handle"]: i["rot_z_deg"] for i in b["instances"] if i["kind"] == "flora"}
    assert ra != rb


@pytest.mark.parametrize("dz,ok", [(0.0, True), (0.0099, True), (0.0101, False), (-0.0101, False)])
def test_sinking_tolerance_at_threshold(dz, ok):
    rep, _ = run()
    rb = fake_readback(rep, ps.make_plan(rep, FACTS, OFFSET))
    rb["instances"][0]["lowest_z"] -= dz
    assert ps.sinking(rb)["ok"] is ok


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf")])
def test_sinking_missing_measurement_fails(bad):
    rep, _ = run()
    rb = fake_readback(rep, ps.make_plan(rep, FACTS, OFFSET))
    rb["instances"][0]["ground_z_at_pivot"] = bad
    assert ps.sinking(rb)["ok"] is False


def test_sinking_empty_fails():
    assert ps.sinking({"instances": []})["ok"] is False


def test_generated_probe_scene_equals_engine(tmp_path):
    """Probe: 200 random seeds / point sets -> plan + exact readback always compares clean."""
    for k in range(200):
        rep, _ = run(seed=k, pts=points(n=8, seed=k))
        plan = ps.make_plan(rep, FACTS, OFFSET)
        assert ps.compare_scene(rep, fake_readback(rep, plan), FACTS, OFFSET) == []


# ---------------------------------------------------------------- PR #344 round 1 regressions (helpers)
def test_scene_triangles_counts_placed_geometry_with_mixed_deletion():
    """Quad bottom deleted on one bench (12 -> 10), kept on the other; an n-gon instance counts n - 2."""
    rb = {"instances": [{"handle": "A", "library_id": "BENCH", "triangles": 10},
                        {"handle": "B", "library_id": "BENCH", "triangles": 12},
                        {"handle": "C", "library_id": "HEX", "triangles": 4}]}
    assert ps.scene_triangles(rb) == {"BENCH": {"instances": 2, "total": 22, "min": 10, "max": 12},
                                      "HEX": {"instances": 1, "total": 4, "min": 4, "max": 4}}


@pytest.mark.parametrize("bad", [None, -1, 1.5, float("nan")])
def test_scene_triangles_missing_readback_fails_closed(bad):
    with pytest.raises(ps.PlacementStopped):
        ps.scene_triangles({"instances": [{"handle": "A", "library_id": "BENCH", "triangles": bad}]})


def test_compare_scene_detects_wrong_triangles_after_deletion():
    rep, _ = run()
    plan = ps.make_plan(rep, FACTS, OFFSET)
    rb = fake_readback(rep, plan)
    rb["library_triangles"] = {k: v["triangles"] for k, v in FACTS.items()}
    for r, it in zip(rb["instances"], plan["instances"]):
        r["triangles"] = 12 - 2 * len(it["delete_polygons"])
    assert ps.compare_scene(rep, rb, FACTS, OFFSET) == []
    k = next(i for i, it in enumerate(plan["instances"]) if it["delete_polygons"])
    rb["instances"][k]["triangles"] = 12                  # bottom reported deleted but triangles not reduced
    assert any("triangles" in m for m in ps.compare_scene(rep, rb, FACTS, OFFSET))


@pytest.mark.parametrize("mism,sink_ok,n", [([], True, 0), (["x: pivot"], True, 1), ([], False, 1),
                                            (["a", "b"], False, 3)])
def test_qa_gate(mism, sink_ok, n):
    s = {"ok": sink_ok, "out_of_tol": [] if sink_ok else [{"handle": "H", "sink_m": 1.1}]}
    assert len(ps.qa_gate(mism, s)) == n


def test_ground_exceptions_bind_to_fingerprint():
    pts = points(4)
    snap = {k: pts[1][k] for k in ps.EXCEPTION_POINT_KEYS}
    snap["library_id"] = ASSIGN[pts[1]["label"]]
    exc = [{"handle": "H001", "reason": "hole", "ground_master_sha256": {"npm": "A"}, "point": snap,
            "approved": {"by": "user", "date": "2026-10-20", "quote": "q"}}]
    keep, excl, stale = ps.apply_ground_exceptions(pts, exc, "npm", "A", ASSIGN)
    assert [p["handle"] for p in keep] == ["H000", "H002", "H003"] and stale == []
    assert excl[0]["handle"] == "H001" and excl[0]["reason"] == "ground_exception"
    keep, excl, stale = ps.apply_ground_exceptions(pts, exc, "npm", "B", ASSIGN)
    assert len(keep) == 4 and excl == [] and stale == ["H001"]
    exc[0].pop("approved")
    with pytest.raises(ps.PlacementStopped):
        ps.apply_ground_exceptions(pts, exc, "npm", "A", ASSIGN)


@pytest.mark.parametrize("field,value", [("x", 1.0), ("y", -3.0), ("label", "Липа"), ("rotation", 7.0)])
def test_ground_exception_stops_on_changed_point_identity(field, value):
    pts = points(4)
    snap = {k: pts[1][k] for k in ps.EXCEPTION_POINT_KEYS}
    snap["library_id"] = ASSIGN[pts[1]["label"]]
    exc = [{"handle": "H001", "reason": "hole", "ground_master_sha256": {"npm": "A"}, "point": snap,
            "approved": {"by": "user", "date": "2026-10-20", "quote": "q"}}]
    pts[1][field] = value if field != "x" else pts[1]["x"] + value
    with pytest.raises(ps.PlacementStopped, match="point identity changed"):
        ps.apply_ground_exceptions(pts, exc, "npm", "A", ASSIGN)
    exc[0].pop("point")
    with pytest.raises(ps.PlacementStopped, match="malformed"):
        ps.apply_ground_exceptions(points(4), exc, "npm", "A", ASSIGN)


def test_ground_exception_for_absent_point_stops():
    exc = [{"handle": "NOPE", "reason": "hole", "ground_master_sha256": {"npm": "A"},
            "point": {"handle": "NOPE", "label": "Скамья", "x": 0.0, "y": 0.0, "z": 0.0, "rotation": 0.0,
                      "library_id": ASSIGN["Скамья"]},
            "approved": {"by": "user", "date": "2026-10-20", "quote": "q"}}]
    with pytest.raises(ps.PlacementStopped, match="not among"):
        ps.apply_ground_exceptions(points(4), exc, "npm", "A", ASSIGN)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), None, "1.0", True])
def test_validate_points_rejects_non_finite(bad):
    pts = points(3)
    pts[2]["x"] = bad
    with pytest.raises(ps.PlacementStopped, match="H002.*non-finite"):
        ps.validate_points(pts)
    ps.validate_points(points(3))
