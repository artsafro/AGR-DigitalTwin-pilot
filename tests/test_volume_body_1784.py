"""#1784 step 2: volume-lines -> per-volume BodyPlan + post-ops (tools/methods/body/volume_body.py)."""
import copy
import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "body"))
import volume_body as vb  # noqa: E402

CORE_DIRS = [os.environ.get("AGR_BODY_CORE", ""), str(ROOT / "tools" / "methods" / "body")]


def _core():
    for d in CORE_DIRS:
        if d and (Path(d) / "body_lattice.py").is_file():
            return vb.load_core(d)
    pytest.skip("shared body core #1736 (body_lattice.py) not on this branch; set AGR_BODY_CORE")


def _vl(clockwise=True):
    """Synthetic (not a real object): one 12 x 8 m volume, levels 0 / 0.6 / 3.0 / 4.0; ring in source order."""
    ring = [[0, 0], [12, 0], [12, 8], [0, 8], [0, 0]]
    if clockwise:
        ring = [[0, 0], [0, 8], [12, 8], [12, 0], [0, 0]]
    pts = ring[:-1]
    edges = {}
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        edges["A%02d" % (i + 1)] = {"volume": "A", "xy": [a, b], "facade": "F%d" % i, "seam": None,
                                    "length": math.dist(a, b), "visible_from": 0, "levels": [0, 0.6, 3.0, 4.0]}
    return {"volumes": {"A": {"ring": ring, "levels": [0.0, 0.6, 3.0, 4.0]}}, "edges": edges, "rectangles": []}


def _rect(edge, rect, state="cut", name="w"):
    return {"facade": "F", "kind": "surrounds", "name": name, "edge": edge, "projected_rect": rect,
            "snapped_rect": rect if state == "cut" else None, "state": state}


def _xy_at(ring, s):
    acc = 0.0
    for a, b in zip(ring, ring[1:] + ring[:1]):
        L = math.dist(a, b)
        if s <= acc + L + 1e-9:
            t = (s - acc) / L
            return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
        acc += L
    raise AssertionError(s)


@pytest.mark.parametrize("clockwise", [True, False])
def test_window_lands_where_the_source_rect_is(clockwise):
    """Regression (v003 sheet): a CW source ring was reversed from the wrong start point, windows moved sides."""
    vl = _vl(clockwise)
    edge = "A02"  # source side 2
    e = vl["edges"][edge]
    vl["rectangles"].append(_rect(edge, [2.0, 3.5, 0.6, 3.0]))
    plan = vb.plans_from_volume_lines(vl)["A"]["plan"]
    ring = plan["rings"][0]["xy"]
    assert sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) > 0  # CCW for the core
    w = plan["windows"][0]
    got = sorted([_xy_at(ring, w[1]), _xy_at(ring, w[2])])
    (ax, ay), (bx, by) = e["xy"]
    L = math.dist(e["xy"][0], e["xy"][1])
    want = sorted([(ax + (bx - ax) * s / L, ay + (by - ay) * s / L) for s in (2.0, 3.5)])
    for g, x in zip(got, want):
        assert math.dist(g, x) < 1e-6
    assert (w[3], w[4]) == (1, 2)


def test_every_rectangle_is_built_local_or_dropped():
    vl = _vl()
    vl["rectangles"] += [_rect("A01", [1.0, 2.0, 0.6, 3.0]), _rect("A01", [3.0, 4.0, 0.05, 2.175], "level_conflict"),
                         _rect("A03", [1, 2, 0, 4], "curtain_bbox_check"),
                         {"facade": "F9", "name": "inner", "state": "interior_excluded"}]
    e = vb.plans_from_volume_lines(vl)
    assert len(e["A"]["plan"]["windows"]) == 2
    assert e["A"]["local"] == [{"window": 1, "zt": 2.175}] or e["A"]["local"][0]["zt"] == 2.175
    assert [d["reason"] for d in e["A"]["dropped"]] == ["curtain_bbox_check"]
    assert [d["reason"] for d in e["_unbound"]["dropped"]] == ["interior_excluded"]


@pytest.mark.parametrize("rect,state,msg", [
    ([1.0, 2.0, 0.6, 2.2], "cut", "not on a level"),            # head off level and not a local state
    ([1.0, 2.0, 1.2, 3.0], "cut", "not within"),                # sill 0.6 m off any level
    ([1.0, 2.0, 0.6, 0.8], "cut", "not above"),                 # exactly-at-threshold head (0.2) snaps to sill
    ([2.0, 1.0, 0.6, 3.0], "cut", "empty rect"),
    ([1.0, float("nan"), 0.6, 3.0], "cut", "finite"),
    ([1.0, 2.0, 0.6, 4.5], "level_conflict", "above the volume top"),
])
def test_fail_closed_rectangles(rect, state, msg):
    vl = _vl()
    r = _rect("A01", rect, state)
    if state == "level_conflict":
        r["snapped_rect"] = None
    vl["rectangles"].append(r)
    with pytest.raises(ValueError, match=msg):
        vb.plans_from_volume_lines(vl)


def test_unknown_edge_and_empty_input_fail():
    vl = _vl()
    vl["rectangles"].append(_rect("Z99", [1, 2, 0.6, 3.0]))
    with pytest.raises(ValueError, match="no edge"):
        vb.plans_from_volume_lines(vl)
    with pytest.raises(ValueError, match="non-empty"):
        vb.plans_from_volume_lines({"volumes": {}, "edges": {}, "rectangles": []})


def test_touching_openings_merge_and_mixed_levels_fail():
    vl = _vl()
    vl["rectangles"] += [_rect("A01", [1.0, 2.0, 0.6, 3.0], name="a"), _rect("A01", [2.05, 3.0, 0.6, 3.0], name="b")]
    e = vb.plans_from_volume_lines(vl)["A"]
    assert len(e["plan"]["windows"]) == 1 and sorted(e["openings"][0]["names"]) == ["a", "b"]
    vl2 = _vl()
    vl2["rectangles"] += [_rect("A01", [1.0, 2.0, 0.6, 3.0], name="a"), _rect("A01", [2.0, 3.0, 0.0, 3.0], name="d")]
    with pytest.raises(ValueError, match="overlap or touch"):
        vb.plans_from_volume_lines(vl2)


def test_seam_mates_in_either_direction_and_mismatch_fails():
    vl = _vl(clockwise=False)
    vl["volumes"]["B"] = {"ring": [[12, 0], [20, 0], [20, 8], [12, 8], [12, 0]], "levels": [0.0, 3.0, 6.0]}
    pts = vl["volumes"]["B"]["ring"][:-1]
    for i in range(4):
        vl["edges"]["B%02d" % (i + 1)] = {"volume": "B", "xy": [pts[i], pts[(i + 1) % 4]], "levels": [0, 3, 6]}
    vl["edges"]["A02"].update(seam="J", mate="B04")   # A02 (12,0)->(12,8), B04 (12,8)->(12,0): opposite
    vl["edges"]["B04"].update(seam="J", mate="A02")
    e = vb.plans_from_volume_lines(vl)
    assert e["A"]["seams"][0]["hidden_to"] == 4.0 and e["B"]["seams"][0]["hidden_to"] == 4.0
    bad = copy.deepcopy(vl)
    bad["edges"]["A02"]["mate"] = "B01"
    with pytest.raises(ValueError, match="do not share"):
        vb.plans_from_volume_lines(bad)


def test_cli_refuses_output_containing_input(tmp_path):
    src = tmp_path / "vl.json"
    src.write_text("{}", encoding="utf-8")
    assert vb.main([str(src), str(tmp_path), "--core", str(tmp_path)]) == 2


def test_core_build_local_cut_closed_rings_no_facade_tris():
    core = _core()
    vl = _vl(clockwise=True)
    vl["rectangles"] += [_rect("A01", [1.0, 2.5, 0.6, 3.0], name="w1"), _rect("A01", [4.0, 6.0, 0.6, 3.0], name="w2"),
                         _rect("A02", [3.0, 4.2, 0.05, 2.175], "level_conflict", name="door")]
    e = vb.plans_from_volume_lines(vl)["A"]
    r = vb.build_volume(core, e)
    rep = r["report"]
    cl = rep["closure"][0]
    assert cl["closed_levels"] == cl["levels"] == 4
    assert rep["local_cuts"] == 1 and rep["openings"] == 3
    m = rep["body"]
    assert m["facade_triangles"] == 0 and m["non_manifold_edges"] == 0 and m["defect_cells"] == 0
    assert m["facade_ngons"] == 2  # the two neighbour cells of the door carry the +2.175 vertex [D375]
    assert rep["open_edges"]["other"] == 0
    zs = {round(p[2], 3) for p in r["body"]["verts"]}
    assert 2.175 in zs and 0.6 in zs


def test_core_build_seam_cells_removed_against_mate():
    core = _core()
    vl = _vl(clockwise=False)
    vl["volumes"]["B"] = {"ring": [[12, 0], [20, 0], [20, 8], [12, 8], [12, 0]], "levels": [0.0, 0.6, 3.0, 6.0]}
    pts = vl["volumes"]["B"]["ring"][:-1]
    for i in range(4):
        vl["edges"]["B%02d" % (i + 1)] = {"volume": "B", "xy": [pts[i], pts[(i + 1) % 4]], "levels": [0, .6, 3, 6]}
    vl["edges"]["A02"].update(seam="J", mate="B04")
    vl["edges"]["B04"].update(seam="J", mate="A02")
    ents = vb.plans_from_volume_lines(vl)
    ra, rb = vb.build_volume(core, ents["A"]), vb.build_volume(core, ents["B"])
    assert ra["report"]["hidden_seam_cells_removed"] == 3   # A's whole seam side (3 bands up to its top 4.0)
    assert rb["report"]["hidden_seam_cells_removed"] == 2   # B's seam side up to 3.0; 3.0..6.0 stays exterior
    assert ra["report"]["open_edges"]["other"] == 0 and rb["report"]["open_edges"]["other"] == 0
