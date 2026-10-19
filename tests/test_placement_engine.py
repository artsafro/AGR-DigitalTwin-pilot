"""Placement engine (#316): Flora / MAF instances on SPOZU points over a Ground mesh [D095, D096, D100, D108, D126].

All data is SYNTHETIC and generated here; no user file, no DCC.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass

import numpy as np
import pytest

from dt_ai.placement.engine import main, place, report_json

SINK = 0.10
TOL = 1e-3


# ---------------------------------------------------------------- synthetic data
@dataclass
class Pt:  # shaped like adapters.cad.spozu.PointItem (read-only duck type)
    x: float
    y: float
    z: float
    layer: str
    label: str | None
    position: str | None
    handle: str
    inside: bool | None
    rotation: float = 0.0


def grid(n=50, step=1.0, f=lambda x, y: 0.1 * x + 0.05 * y, skip=lambda i, j: False, x0=0.0, y0=0.0):
    """Regular (n x n cells) triangle grid, z = f(x, y); cells for which skip(i, j) are left out (holes)."""
    xs = x0 + np.arange(n + 1) * step
    ys = y0 + np.arange(n + 1) * step
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    V = np.stack([X.ravel(), Y.ravel(), f(X.ravel(), Y.ravel())], axis=1)
    idx = lambda i, j: i * (n + 1) + j  # noqa: E731
    T = []
    for i in range(n):
        for j in range(n):
            if skip(i, j):
                continue
            a, b, c, d = idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)
            T += [(a, b, c), (a, c, d)]
    return V, np.asarray(T, dtype=np.int64).reshape(-1, 3)


PLATE = (10.0, 20.0)  # stacked plate patch [10,20] x [10,20], 6 mm above the base


def plane(x, y):
    return 0.1 * x + 0.05 * y


def sloped_ground_with_plate():
    V, T = grid()
    pv, pt = grid(n=10, f=lambda x, y: plane(x, y) + 0.006, x0=PLATE[0], y0=PLATE[0])
    return np.vstack([V, pv]), np.vstack([T, pt + len(V)])


def top_z(x, y):
    on_plate = PLATE[0] <= x <= PLATE[1] and PLATE[0] <= y <= PLATE[1]
    return plane(x, y) + (0.006 if on_plate else 0.0)


def bush_vertices(h=2.0, crown=1.5, n=60, seed=7):
    rng = np.random.default_rng(seed)
    a = rng.uniform(0, 2 * np.pi, n)
    r = rng.uniform(0, crown / 2, n)
    z = rng.uniform(0.05, h, n)
    v = np.stack([r * np.cos(a) + 0.3, r * np.sin(a) - 0.2, z], axis=1)  # off-origin local frame
    v = np.vstack([v, [[0.3 + crown / 2, -0.2, 1.0], [0.3 - crown / 2, -0.2, 1.0],
                       [0.3, -0.2 + crown / 2, 1.0], [0.3, -0.2 - crown / 2, 1.0], [0.3, -0.2, 0.0], [0.3, -0.2, h]]])
    return v


def bbox(v):
    return [float(c) for c in v.min(0)], [float(c) for c in v.max(0)]


def flora_entry(id_="B1", h=2.0, crown=1.5, sched_h=None, sched_c=None, verts=None):
    v = bush_vertices(h, crown) if verts is None else verts
    lo, hi = bbox(v)
    return {"id": id_, "kind": "flora", "bbox_min": lo, "bbox_max": hi,
            "schedule_height_m": sched_h if sched_h is not None else h,
            "schedule_crown_m": sched_c if sched_c is not None else crown}


def box_vertices(half=1.0, h=1.0, z0=0.25, cx=0.5, cy=-0.5):
    return np.array([[cx + sx * half, cy + sy * half, z] for sx in (-1, 1) for sy in (-1, 1) for z in (z0, z0 + h)])


def maf_entry(id_="M1", half=1.0, h=1.0, z0=0.25, cx=0.5, cy=-0.5, **extra):
    v = box_vertices(half, h, z0, cx, cy)
    lo, hi = bbox(v)
    bottom = [[cx - half, cy - half, z0], [cx + half, cy - half, z0], [cx + half, cy + half, z0], [cx - half, cy + half, z0]]
    return {"id": id_, "kind": "maf", "bbox_min": lo, "bbox_max": hi, "bottom_faces": [bottom], **extra}


def mat(inst):
    return np.asarray(inst["matrix"], dtype=float)


def to_world(inst, v):
    M = mat(inst)
    h = np.hstack([v, np.ones((len(v), 1))])
    return (h @ M.T)[:, :3]


def flora_points(n, seed=1, label="B1", lo=1.0, hi=49.0, rotation=0.0):
    rnd = random.Random(seed)
    return [Pt(rnd.uniform(lo, hi), rnd.uniform(lo, hi), 0.0, "PL", label, label, f"F{i:05d}", True, rotation)
            for i in range(n)]


def ks_uniform(samples, a, b):
    s = np.sort((np.asarray(samples) - a) / (b - a))
    n = len(s)
    return float(max(np.max(np.arange(1, n + 1) / n - s), np.max(s - np.arange(n) / n)))


# ---------------------------------------------------------------- Flora
def test_flora_sinks_10cm_below_topmost_ground_at_every_instance():
    V, T = sloped_ground_with_plate()
    verts = bush_vertices()
    pts = flora_points(400) + [Pt(12.5 + i, 15.3, 0, "PL", "B1", "B1", f"P{i}", True) for i in range(6)]
    rep = place(pts, V, T, [flora_entry(verts=verts)], seed=42)
    assert rep["status"] == "pass", rep["findings"]
    assert len(rep["instances"]) == len(pts)
    sinks = []
    for inst in rep["instances"]:
        w = to_world(inst, verts)
        sinks.append(top_z(inst["pivot_x"], inst["pivot_y"]) - w[:, 2].min())
        assert inst["ground_z"] == pytest.approx(top_z(inst["pivot_x"], inst["pivot_y"]), abs=1e-6)
        assert inst["sink_m"] == pytest.approx(SINK, abs=TOL)
    print(f"flora sink min={min(sinks):.6f} max={max(sinks):.6f} n={len(sinks)}")
    assert all(abs(s - SINK) <= TOL for s in sinks)
    on_plate = [i for i in rep["instances"] if i["handle"].startswith("P")]
    assert len(on_plate) == 6 and all(
        i["ground_z"] == pytest.approx(plane(i["pivot_x"], i["pivot_y"]) + 0.006, abs=1e-9) for i in on_plate)


def test_flora_pivot_on_spozu_point():
    V, T = sloped_ground_with_plate()
    verts = bush_vertices()
    e = flora_entry(verts=verts)
    rep = place([Pt(5.25, 7.75, 3.0, "PL", "B1", "B1", "A", True)], V, T, [e], seed=1)
    inst = rep["instances"][0]
    assert (inst["pivot_x"], inst["pivot_y"]) == (5.25, 7.75)
    # the plant's horizontal centre (bbox centre) sits on the point
    c = np.array([[(e["bbox_min"][0] + e["bbox_max"][0]) / 2, (e["bbox_min"][1] + e["bbox_max"][1]) / 2, 0.0]])
    assert to_world(inst, c)[0, :2] == pytest.approx([5.25, 7.75], abs=1e-9)


def test_flora_rotation_uniform_ks_and_point_rotation_ignored():
    V, T = grid()
    pts = flora_points(2000, seed=3)
    rep = place(pts, V, T, [flora_entry()], seed=2026)
    rots = [i["rot_z_deg"] for i in rep["instances"]]
    assert len(rots) == 2000 and all(0.0 <= r < 360.0 for r in rots)
    d = ks_uniform(rots, 0.0, 360.0)
    crit = 1.36 / math.sqrt(len(rots))  # alpha = 0.05
    print(f"rotation KS D={d:.5f} crit={crit:.5f} n={len(rots)}")
    assert d < crit
    rotated = [Pt(p.x, p.y, p.z, p.layer, p.label, p.position, p.handle, p.inside, 45.0) for p in pts]
    again = place(rotated, V, T, [flora_entry()], seed=2026)
    assert json.loads(report_json(again))["instances"] == json.loads(report_json(rep))["instances"]


def test_flora_scale_uniform_in_plus_minus_10_percent():
    V, T = grid()
    rep = place(flora_points(2000, seed=4), V, T, [flora_entry()], seed=5)
    sc = [i["scale"] for i in rep["instances"]]
    assert min(sc) >= 0.9 and max(sc) <= 1.1
    d = ks_uniform(sc, 0.9, 1.1)
    print(f"scale KS D={d:.5f}")
    assert d < 1.36 / math.sqrt(len(sc))


def test_flora_scale_narrowed_near_band_edge():
    V, T = grid()
    e = flora_entry(h=2.0 * 1.18, crown=1.5, sched_h=2.0, sched_c=1.5)  # model at +18 %
    rep = place(flora_points(500), V, T, [e], seed=9)
    assert rep["status"] == "pass"
    sc = [i["scale"] for i in rep["instances"]]
    assert max(sc) <= 1.2 / 1.18 + 1e-12 and min(sc) >= 0.9
    assert max(sc) > 1.0  # the narrowed range is still used, not collapsed to 1
    h_model = e["bbox_max"][2] - e["bbox_min"][2]
    assert all(0.8 * 2.0 - 1e-9 <= h_model * s <= 1.2 * 2.0 + 1e-9 for s in sc)
    lib = rep["library"]["B1"]
    assert lib["scale_range"][1] == pytest.approx(1.2 / 1.18 * (2.0 * 1.18) / h_model, rel=1e-9)


def test_flora_crown_band_narrows_low_side():
    V, T = grid()
    e = flora_entry(h=2.0, crown=1.5 * 0.85, sched_h=2.0, sched_c=1.5)  # crown at -15 %
    rep = place(flora_points(300), V, T, [e], seed=9)
    sc = [i["scale"] for i in rep["instances"]]
    crown = max(e["bbox_max"][0] - e["bbox_min"][0], e["bbox_max"][1] - e["bbox_min"][1])
    assert min(sc) * crown >= 0.8 * 1.5 - 1e-9 and max(sc) <= 1.1


@pytest.mark.parametrize("factor,ok", [(1.25, False), (0.75, False), (1.2, True), (0.8, True)])
def test_flora_band_edge_and_outside(factor, ok):
    V, T = grid()
    e = flora_entry(h=2.0 * factor, sched_h=2.0)
    rep = place(flora_points(20), V, T, [e], seed=9)
    if ok:
        assert rep["status"] == "pass" and len(rep["instances"]) == 20
        sc = [i["scale"] for i in rep["instances"]]
        h = e["bbox_max"][2] - e["bbox_min"][2]
        assert all(0.8 * 2.0 - 1e-9 <= h * s <= 1.2 * 2.0 + 1e-9 for s in sc)
    else:
        assert rep["status"] == "fail" and rep["instances"] == []
        assert {f["code"] for f in rep["failed"]} == {"flora_out_of_band"}
        assert len(rep["failed"]) == 20


# ---------------------------------------------------------------- reproducibility
def test_reproducible_bytes_shuffle_and_seed():
    V, T = sloped_ground_with_plate()
    lib = [flora_entry(), maf_entry()]
    pts = flora_points(300) + [Pt(30 + i, 30, 0, "MAF", "M1", "M1", f"M{i}", True, 15.0 * i) for i in range(5)]
    a = report_json(place(pts, V, T, lib, seed=11))
    b = report_json(place(pts, V, T, lib, seed=11))
    shuffled = pts[:]
    random.Random(0).shuffle(shuffled)
    c = report_json(place(shuffled, V, T, lib[::-1], seed=11))
    ha, hb, hc = (hashlib.sha256(s.encode()).hexdigest() for s in (a, b, c))
    print(f"sha256 run1={ha} run2={hb} shuffled={hc}")
    assert ha == hb == hc
    r1 = json.loads(a)
    r2 = json.loads(report_json(place(pts, V, T, lib, seed=12)))
    assert r1["counts"] == r2["counts"] and r1["seed"] == 11 and r2["seed"] == 12
    i1 = {i["handle"]: i for i in r1["instances"]}
    i2 = {i["handle"]: i for i in r2["instances"]}
    assert i1.keys() == i2.keys()
    assert all((i1[h]["pivot_x"], i1[h]["pivot_y"], i1[h]["pivot_z"]) ==
               (i2[h]["pivot_x"], i2[h]["pivot_y"], i2[h]["pivot_z"]) for h in i1)
    fl = [h for h in i1 if i1[h]["kind"] == "flora"]
    assert sum(i1[h]["rot_z_deg"] != i2[h]["rot_z_deg"] for h in fl) == len(fl)
    assert sum(i1[h]["scale"] != i2[h]["scale"] for h in fl) == len(fl)
    assert all(i1[h]["rot_z_deg"] == i2[h]["rot_z_deg"] for h in i1 if i1[h]["kind"] == "maf")


def test_report_records_seed_and_input_hashes():
    V, T = grid()
    rep = place(flora_points(10), V, T, [flora_entry()], seed=3)
    assert rep["seed"] == 3
    assert set(rep["input_hashes"]) == {"points", "ground", "library"}
    V2 = V.copy()
    V2[0, 2] += 1.0
    assert place(flora_points(10), V2, T, [flora_entry()], seed=3)["input_hashes"]["ground"] != \
        rep["input_hashes"]["ground"]


# ---------------------------------------------------------------- MAF placement
def test_maf_pivot_rotation_and_sinking():
    V, T = sloped_ground_with_plate()
    e = maf_entry()
    verts = box_vertices()
    pts = [Pt(5 + 3 * i, 8 + 2.5 * i, 0, "MAF", "M1", "M1", f"M{i}", True, 37.5 * i) for i in range(15)]
    rep = place(pts, V, T, [e], seed=1)
    assert len(rep["instances"]) == 15
    sinks = []
    for p, inst in zip(sorted(pts, key=lambda q: q.handle), rep["instances"]):
        assert inst["kind"] == "maf" and inst["scale"] == 1.0
        # unit: DXF INSERT rotation, degrees counter-clockwise (adapters/cad/spozu.py PointItem.rotation)
        assert inst["rot_z_deg"] == pytest.approx(p.rotation % 360.0)
        w = to_world(inst, verts)
        centre = w.mean(0)
        assert centre[:2] == pytest.approx([p.x, p.y], abs=1e-9)  # footprint centre on the point
        sinks.append(top_z(p.x, p.y) - w[:, 2].min())
    print(f"maf sink min={min(sinks):.6f} max={max(sinks):.6f} n={len(sinks)}")
    assert all(abs(s - SINK) <= TOL for s in sinks)


def test_maf_rotation_is_ccw_degrees():
    V, T = grid(f=lambda x, y: 0 * x)
    e = maf_entry(cx=0.0, cy=0.0)
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "R", True, 90.0)], V, T, [e], seed=1)
    w = to_world(rep["instances"][0], np.array([[1.0, 0.0, 0.25]]))
    assert w[0, :2] == pytest.approx([25.0, 26.0], abs=1e-9)  # local +X -> world +Y at 90 deg


def test_maf_dimension_deviation_reported_not_enforced():
    V, T = grid()
    e = maf_entry(spec_dims_m=[2.0, 2.0, 1.3])  # model height 1.0: 0.30 m off
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "D", True)], V, T, [e], seed=1)
    assert len(rep["instances"]) == 1
    f = [f for f in rep["findings"] if f["code"] == "maf_dims_off_spec"]
    assert f and f[0]["severity"] == "warn"


# ---------------------------------------------------------------- MAF bottom faces
def faces(rep):
    return rep["instances"][0]["bottom_faces"]


def flat(**kw):
    return grid(f=lambda x, y: 0.0 * x, **kw)


def test_bottom_face_flat_ground_delete():
    V, T = flat()
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "A", True, 20)], V, T, [maf_entry(half=2.0)], seed=1)
    f = faces(rep)[0]
    assert f["action"] == "delete" and f["reasons"] == [] and f["min_gap_m"] == pytest.approx(0.1, abs=1e-9)
    assert rep["status"] == "pass"


def test_bottom_face_hole_under_footprint_review():
    V, T = flat(skip=lambda i, j: (i, j) == (26, 26))  # cell [26,27]^2 inside the footprint [23,27]^2
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "A", True)], V, T, [maf_entry(half=2.0, cx=0, cy=0)], seed=1)
    f = faces(rep)[0]
    assert f["action"] == "review" and "ground_border" in f["reasons"]
    assert rep["status"] == "review"


def test_bottom_face_depression_between_face_vertices_review():
    V, T = flat()
    k = 26 * 51 + 26  # ground vertex (26, 26), inside the outline, not a face vertex and not the pivot
    V[k, 2] = -0.3
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "A", True)], V, T, [maf_entry(half=2.0, cx=0, cy=0)], seed=1)
    inst = rep["instances"][0]
    assert inst["ground_z"] == 0.0
    corners = to_world(inst, np.array([[sx * 2.0, sy * 2.0, 0.25] for sx in (-1, 1) for sy in (-1, 1)]))
    assert all(0.0 - c[2] > 0 for c in corners)  # a vertex-only check would pass
    f = faces(rep)[0]
    assert f["action"] == "review" and "exposed_bottom" in f["reasons"] and f["min_gap_m"] < 0
    assert rep["exposed_bottoms"] == [{"handle": "A", "face": 0, "min_gap_m": f["min_gap_m"]}]


def test_bottom_face_over_ground_border_review():
    V, T = flat()
    rep = place([Pt(1, 25, 0, "MAF", "M1", "M1", "A", True)], V, T, [maf_entry(half=2.0, cx=0, cy=0)], seed=1)
    f = faces(rep)[0]
    assert f["action"] == "review"
    assert {"ground_border", "ground_missing"} <= set(f["reasons"])


def test_bottom_face_touching_border_review():
    V, T = flat()  # outline edge exactly on the mesh border x = 0
    rep = place([Pt(2, 25, 0, "MAF", "M1", "M1", "A", True)], V, T, [maf_entry(half=2.0, cx=0, cy=0)], seed=1)
    f = faces(rep)[0]
    assert f["action"] == "review" and "ground_border" in f["reasons"]


def test_bottom_face_steep_slope_exposed_review():
    V, T = grid(f=lambda x, y: 0.5 * x)
    rep = place([Pt(25, 25, 0, "MAF", "M1", "M1", "S", True)], V, T, [maf_entry(half=2.0, cx=0, cy=0)], seed=1)
    f = faces(rep)[0]
    assert f["action"] == "review" and f["reasons"] == ["exposed_bottom"]
    assert rep["exposed_bottoms"][0]["handle"] == "S"


def test_bottom_face_stacked_plate_uses_topmost():
    V, T = sloped_ground_with_plate()
    rep = place([Pt(15, 15, 0, "MAF", "M1", "M1", "A", True)], V, T, [maf_entry(half=0.5, cx=0, cy=0)], seed=1)
    inst = rep["instances"][0]
    assert inst["ground_z"] == pytest.approx(plane(15, 15) + 0.006, abs=1e-9)


def test_bottom_face_delete_is_sound_on_random_terrain():
    """Brute-force probe: a `delete` verdict implies the topmost Ground is strictly above the face on a dense
    sample of the outline interior (and every sample has a height)."""
    rng = np.random.default_rng(316)
    n_delete = n_review = 0
    for t in range(6):
        H = rng.normal(0, 0.06 * (t + 1), (21, 21))

        def f(x, y, H=H):
            return H[np.clip(np.rint(x).astype(int), 0, 20), np.clip(np.rint(y).astype(int), 0, 20)]

        V, T = grid(n=20, f=f)
        pts = [Pt(float(rng.uniform(3, 17)), float(rng.uniform(3, 17)), 0, "MAF", "M1", "M1", f"T{t}_{k}", True,
                  float(rng.uniform(0, 360))) for k in range(25)]
        rep = place(pts, V, T, [maf_entry(half=1.2, cx=0.1, cy=-0.2)], seed=1)
        for inst in rep["instances"]:
            face = inst["bottom_faces"][0]
            if face["action"] != "delete":
                n_review += 1
                continue
            n_delete += 1
            uv = np.stack(np.meshgrid(np.linspace(-1.2, 1.2, 25), np.linspace(-1.2, 1.2, 25)), -1).reshape(-1, 2)
            local = np.column_stack([uv[:, 0] + 0.1, uv[:, 1] - 0.2, np.full(len(uv), 0.25)])
            w = to_world(inst, local)
            from dt_ai.placement.engine import GroundIndex
            g = GroundIndex(V, T)
            for x, y, z in w:
                gz = g.height(x, y)
                assert gz is not None and gz > z
    print(f"random terrain faces: delete={n_delete} review={n_review}")
    assert n_delete > 0 and n_review > 0


# ---------------------------------------------------------------- fail-closed probes
def failed_codes(rep):
    return {f["handle"]: f["code"] for f in rep["failed"]}


def test_point_outside_ground_extent_fails():
    V, T = grid()
    rep = place([Pt(60, 10, 0, "PL", "B1", "B1", "X", True), Pt(10, 10, 0, "PL", "B1", "B1", "Y", True)],
                V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail" and failed_codes(rep) == {"X": "point_outside_ground"}
    assert [i["handle"] for i in rep["instances"]] == ["Y"]


def test_point_over_ground_hole_fails():
    V, T = grid(skip=lambda i, j: 30 <= i < 33 and 30 <= j < 33)
    rep = place([Pt(31.5, 31.5, 0, "PL", "B1", "B1", "H", True)], V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail" and failed_codes(rep) == {"H": "point_over_ground_hole"}
    rep = place([Pt(31.5, 31.5, 0, "MAF", "M1", "M1", "H", True)], V, T, [maf_entry()], seed=1)
    assert failed_codes(rep) == {"H": "point_over_ground_hole"} and rep["instances"] == []


@pytest.mark.parametrize("field", ["x", "y", "z", "rotation"])
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("label", ["B1", "M1"])
def test_non_finite_point_fails(field, bad, label):
    V, T = grid()
    p = {"x": 10.0, "y": 10.0, "z": 0.0, "label": label, "position": label, "handle": "N", "inside": True,
         "rotation": 0.0}
    p[field] = bad
    rep = place([p], V, T, [flora_entry(), maf_entry()], seed=1)
    assert rep["status"] == "fail" and failed_codes(rep) == {"N": "point_non_finite"}
    assert rep["instances"] == []
    json.loads(report_json(rep))  # still valid strict JSON


@pytest.mark.parametrize("label,code", [(None, "label_missing"), ("", "label_missing"), ("ZZZ", "library_id_unknown")])
def test_label_missing_or_unknown_fails(label, code):
    V, T = grid()
    rep = place([Pt(10, 10, 0, "PL", label, None, "L", True)], V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail" and failed_codes(rep) == {"L": code}


def test_label_map_resolves_and_unknown_mapped_id_fails():
    V, T = grid()
    pts = [Pt(10, 10, 0, "PL", "1", "1", "A", True), Pt(11, 10, 0, "PL", "2", "2", "B", True)]
    rep = place(pts, V, T, [flora_entry("BUSH-01")], seed=1, label_map={"1": "BUSH-01", "2": "NOPE"})
    assert [i["library_id"] for i in rep["instances"]] == ["BUSH-01"]
    assert failed_codes(rep) == {"B": "library_id_unknown"}


def test_duplicate_handle_fails_all_copies():
    V, T = grid()
    pts = [Pt(10, 10, 0, "PL", "B1", "B1", "D", True), Pt(12, 12, 0, "PL", "B1", "B1", "D", True),
           Pt(14, 14, 0, "PL", "B1", "B1", "E", True)]
    rep = place(pts, V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail"
    assert sorted(f["code"] for f in rep["failed"]) == ["duplicate_handle", "duplicate_handle"]
    assert [i["handle"] for i in rep["instances"]] == ["E"]


@pytest.mark.parametrize("handle", [None, ""])
def test_missing_handle_fails(handle):
    V, T = grid()
    rep = place([{"x": 1.0, "y": 1.0, "z": 0.0, "label": "B1", "handle": handle, "rotation": 0.0}], V, T,
                [flora_entry()], seed=1)
    assert rep["status"] == "fail" and [f["code"] for f in rep["failed"]] == ["handle_missing"]


@pytest.mark.parametrize("case", ["no_triangles", "zero_area", "nan_vertex", "bad_index", "bad_shape"])
def test_empty_or_degenerate_ground_fails_every_point(case):
    V, T = grid(n=4)
    if case == "no_triangles":
        T = np.zeros((0, 3), dtype=np.int64)
    elif case == "zero_area":
        T = np.array([[0, 0, 1], [2, 2, 2], [0, 1, 2]])  # (0,1,2) are collinear on the grid's first column
    elif case == "nan_vertex":
        V = V.copy()
        V[3, 2] = np.nan
    elif case == "bad_index":
        T = T.copy()
        T[0, 0] = 10_000
    else:
        V = V[:, :2]
    pts = flora_points(5, lo=0.5, hi=3.5)
    rep = place(pts, V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail" and rep["instances"] == [] and len(rep["failed"]) == 5
    assert {f["code"] for f in rep["failed"]} == {"ground_invalid"}
    assert any(f["code"] == "ground_invalid" and f["severity"] == "error" for f in rep["findings"])


@pytest.mark.parametrize("key,val", [("bbox_min", [0, 0, float("nan")]), ("bbox_max", [1, float("inf"), 2]),
                                     ("schedule_height_m", float("nan")), ("schedule_crown_m", 0.0),
                                     ("bbox_max", [-1, -1, -1]), ("kind", "tree")])
def test_library_entry_invalid_fails_its_points(key, val):
    V, T = grid()
    e = flora_entry()
    e[key] = val
    rep = place(flora_points(4) + [Pt(5, 5, 0, "MAF", "M1", "M1", "OK", True)], V, T, [e, maf_entry()], seed=1)
    assert rep["status"] == "fail"
    assert {f["code"] for f in rep["failed"]} == {"library_entry_invalid"} and len(rep["failed"]) == 4
    assert [i["handle"] for i in rep["instances"]] == ["OK"]


def test_maf_entry_nan_bottom_face_fails():
    V, T = grid()
    e = maf_entry()
    e["bottom_faces"][0][1][0] = float("nan")
    rep = place([Pt(5, 5, 0, "MAF", "M1", "M1", "A", True)], V, T, [e], seed=1)
    assert failed_codes(rep) == {"A": "library_entry_invalid"}


def test_duplicate_library_id_fails():
    V, T = grid()
    rep = place([Pt(5, 5, 0, "PL", "B1", "B1", "A", True)], V, T, [flora_entry(), flora_entry()], seed=1)
    assert failed_codes(rep) == {"A": "library_entry_invalid"}


@pytest.mark.parametrize("seed", [None, 1.5, True, "7"])
def test_seed_missing_or_invalid_fails_run(seed):
    V, T = grid()
    rep = place(flora_points(5) + [Pt(5, 5, 0, "MAF", "M1", "M1", "A", True)], V, T, [flora_entry(), maf_entry()],
                seed=seed)
    assert rep["status"] == "fail" and rep["instances"] == [] and len(rep["failed"]) == 6
    assert {f["code"] for f in rep["failed"]} == {"seed_invalid"}


# ---------------------------------------------------------------- counts
def test_counts_placed_plus_failed_equals_input_per_library_id():
    V, T = grid(skip=lambda i, j: 30 <= i < 33 and 30 <= j < 33)
    pts = flora_points(50) + [Pt(31.5, 31.5, 0, "PL", "B1", "B1", "HOLE", True),
                              Pt(99, 1, 0, "MAF", "M1", "M1", "OUT", True),
                              Pt(5, 5, 0, "MAF", "M1", "M1", "IN", True),
                              Pt(6, 6, 0, "PL", "Q", "Q", "UNK", True),
                              Pt(7, 7, 0, "PL", None, None, "NOL", True)]
    rep = place(pts, V, T, [flora_entry(), maf_entry()], seed=1)
    c = rep["counts"]
    assert c["B1"]["input"] == 51 and c["B1"]["failed"] == 1 + sum(1 for p in pts[:50] if 30 <= p.x < 33 and 30 <= p.y < 33)
    assert c["M1"] == {"input": 2, "placed": 1, "failed": 1}
    assert c["Q"] == {"input": 1, "placed": 0, "failed": 1}
    assert c["<no label>"] == {"input": 1, "placed": 0, "failed": 1}
    for v in c.values():
        assert v["placed"] + v["failed"] == v["input"]
    t = rep["totals"]
    assert t["input"] == len(pts) == t["placed"] + t["failed"] == len(rep["instances"]) + len(rep["failed"])


def test_empty_point_list_fails():
    V, T = grid()
    rep = place([], V, T, [flora_entry()], seed=1)
    assert rep["status"] == "fail" and any(f["code"] == "no_points" for f in rep["findings"])


# ---------------------------------------------------------------- CLI
def _write_input(path, pts, V, T, lib, seed):
    path.write_text(json.dumps({"points": pts, "ground": {"vertices": V.tolist(), "triangles": T.tolist()},
                                "library": lib, "seed": seed}), encoding="utf-8")


def test_cli_pass_fail_and_output_equals_input(tmp_path):
    V, T = grid(n=10)
    ok = [{"x": 5.0, "y": 5.0, "z": 0.0, "label": "B1", "handle": "A", "rotation": 0.0}]
    inp = tmp_path / "in.json"
    out = tmp_path / "out.json"
    _write_input(inp, ok, V, T, [flora_entry()], 1)
    assert main(["--input", str(inp), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "pass"
    bad = ok + [{"x": 50.0, "y": 5.0, "z": 0.0, "label": "B1", "handle": "B", "rotation": 0.0}]
    _write_input(inp, bad, V, T, [flora_entry()], 1)
    assert main(["--input", str(inp), "--output", str(out)]) != 0
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "fail"
    _write_input(inp, ok, V, T, [flora_entry()], None)
    assert main(["--input", str(inp), "--output", str(out)]) != 0
    before = inp.read_bytes()
    assert main(["--input", str(inp), "--output", str(tmp_path / "." / "in.json")]) != 0
    assert inp.read_bytes() == before
