"""#1784 step 2 v005 ([D376]) and #1802: seam band, partial reveal above a joint, contour cuts, reveal seats, edge clamps.

Synthetic data only (not a real object). The core #1736 (body_lattice.py) is needed for the build tests; they skip
without it (set AGR_BODY_CORE, e.g. the read-only PR #1770 head c97cf3ec).
"""
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


def _vol(vl, name, ring, levels, prefix):
    vl["volumes"][name] = {"ring": ring + [ring[0]], "levels": levels}
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        vl["edges"]["%s%02d" % (prefix, i + 1)] = {"volume": name, "xy": [a, b], "facade": "F%s%d" % (prefix, i),
                                                    "seam": None, "length": math.dist(a, b), "visible_from": 0}


def _two(a_levels=(0.0, 0.6, 3.0, 4.0), b_levels=(0.0, 3.0, 6.0), b_shift=0.0):
    """A 12 x 8 m (CCW) and B 8 x 8 m east of it; A02 (12,0)->(12,8) is the seam with B04 (12,8)->(12,0)."""
    vl = {"volumes": {}, "edges": {}, "rectangles": []}
    _vol(vl, "A", [[0, 0], [12, 0], [12, 8], [0, 8]], list(a_levels), "A")
    x = 12 + b_shift
    _vol(vl, "B", [[x, 0], [20, 0], [20, 8], [x, 8]], list(b_levels), "B")
    vl["edges"]["A02"].update(seam="J", mate="B04")
    vl["edges"]["B04"].update(seam="J", mate="A02")
    return vl


def _one(levels=(0.0, 0.6, 3.0, 4.0)):
    vl = {"volumes": {}, "edges": {}, "rectangles": []}
    _vol(vl, "A", [[0, 0], [12, 0], [12, 8], [0, 8]], list(levels), "A")
    return vl


def _rect(edge, rect, state="cut", name="w", source_rect=None):
    r = {"facade": "F", "kind": "surrounds", "name": name, "edge": edge, "projected_rect": rect,
         "snapped_rect": rect if state == "cut" else None, "state": state}
    if source_rect is not None:
        r["source_rect"] = source_rect
    return r


def _seam_faces(body, x=12.0):
    return [f for f in body["faces"] if all(abs(body["verts"][i][0] - x) < 1e-6 for i in f["v"])]


def _sound(rep):
    m = rep["body"]
    assert m["facade_triangles"] == 0 and m["non_manifold_edges"] == 0 and m["defect_cells"] == 0, m
    assert m["bowtie_vertices"] == 0, m
    assert rep["open_edges"]["other"] == 0, rep["open_edges"]


# ---- #1802: hidden seam band and weld tolerance ---------------------------------------------------------------
def test_1802_seam_hides_only_the_common_band_of_both_volumes():
    """RED before the fix: A's seam faces below the mate's base (0..2 m) were removed -> a hole reported as 'seam'."""
    core = _core()
    ents = vb.plans_from_volume_lines(_two(b_levels=(2.0, 3.0, 6.0)))
    sa = ents["A"]["seams"][0]
    assert (sa["hidden_from"], sa["hidden_to"]) == (2.0, 4.0)
    ra = vb.build_volume(core, ents["A"])
    assert ra["report"]["hidden_seam_cells_removed"] == 1           # only band 3.0..4.0 lies inside [2, 4]
    left = [min(ra["body"]["verts"][i][2] for i in f["v"]) for f in _seam_faces(ra["body"])]
    assert sorted(round(z, 3) for z in left) == [0.0, 0.6]          # bands 0..0.6 and 0.6..3.0 stay


def test_1802_seam_ends_must_weld_within_a_millimetre():
    """RED before the fix: mate ends 4 cm apart were accepted and both seam sides removed -> a 4 cm slit."""
    with pytest.raises(ValueError, match=r"A02.*B04|B04.*A02"):
        vb.plans_from_volume_lines(_two(b_shift=0.04))
    ok = vb.plans_from_volume_lines(_two(b_shift=0.0005))
    assert ok["A"]["seams"][0]["mate"] == "B04"


# ---- [D376] (1) partial reveal above a joint ------------------------------------------------------------------
def test_d376_partial_reveal_above_the_mate_top():
    """A window crossing the visible band of a seam side opens only above the joint (sill = the side's visible_from)."""
    core = _core()
    vl = _two(a_levels=(0.0, 0.6, 3.0, 4.0), b_levels=(0.0, 1.5))
    vl["edges"]["A02"]["visible_from"] = 1.5
    vl["rectangles"].append(_rect("A02", [2.0, 4.0, 0.6, 3.0], "crosses_visible_band", "seven"))
    e = vb.plans_from_volume_lines(vl)["A"]
    assert len(e["plan"]["windows"]) == 1 and e["local"] == [{"window": 0, "zs": 1.5}]
    assert e["openings"][0]["partial_from"] == 1.5
    r = vb.build_volume(core, e)
    _sound(r["report"])
    win = [f for f in r["body"]["faces"] if f["mat"] == "WINDOW"]
    zs = sorted({round(r["body"]["verts"][i][2], 3) for f in win for i in f["v"]})
    assert zs == [1.5, 3.0]


def test_d376_partial_reveal_fully_hidden_is_dropped():
    vl = _two(b_levels=(0.0, 3.5))
    vl["edges"]["A02"]["visible_from"] = 3.5
    vl["rectangles"].append(_rect("A02", [2.0, 4.0, 0.6, 3.0], "crosses_visible_band", "hidden"))
    e = vb.plans_from_volume_lines(vl)["A"]
    assert e["plan"]["windows"] == [] and e["dropped"][0]["reason"] == "hidden_below_visible_band"


# ---- [D376] (2) contour cut with local sill and head, stacked runs welded ---------------------------------------
def test_d376_contour_cut_local_sill_and_head():
    core = _core()
    vl = _one()
    cfg = {"extra_rectangles": [_rect("A01", [1.0, 5.0, 1.2, 3.5], "contour_cut", "glz")]}
    e = vb.plans_from_volume_lines(vl, cfg)["A"]
    assert e["local"] == [{"window": 0, "zt": 3.5, "zs": 1.2}]
    r = vb.build_volume(core, e)
    _sound(r["report"])
    assert r["report"]["body"]["facade_ngons"] == 4  # each jamb neighbour carries one local vertex per local edge
    win = [f for f in r["body"]["faces"] if f["mat"] == "WINDOW"]
    assert sorted({round(r["body"]["verts"][i][2], 3) for f in win for i in f["v"]}) == [1.2, 3.5]


def test_d376_contour_cut_needs_its_state_for_off_level_sill():
    vl = _one()
    vl["rectangles"].append(_rect("A01", [1.0, 5.0, 1.2, 3.0], "cut", "w"))
    with pytest.raises(ValueError, match="not within"):
        vb.plans_from_volume_lines(vl)


def test_d376_stacked_contour_cuts_weld_into_one_mouth():
    """Lower run (sill local) under a wider upper run: the shared level leaves no zero-thickness transom."""
    core = _core()
    vl = _one(levels=(0.0, 0.6, 2.0, 3.0, 3.4, 4.0))  # both runs span two bands: seat side edges are Ts
    cfg = {"extra_rectangles": [_rect("A01", [1.0, 5.0, 1.2, 3.0], "contour_cut", "low"),
                                _rect("A01", [1.0, 8.0, 3.0, 3.8], "contour_cut", "up")]}
    e = vb.plans_from_volume_lines(vl, cfg)["A"]
    r = vb.build_volume(core, e)
    _sound(r["report"])
    assert r["report"]["stacked_faces_removed"] == 2   # the head of "low" and the sill of "up" over one segment
    assert r["report"]["stacked_plane_joins"] == 1    # one glazing seat over the shared segment, no bow-tie
    V = r["body"]["verts"]
    seat = [f for f in r["body"]["faces"] if f["mat"] == "WINDOW" and len(f["v"]) == 5]
    assert len(seat) == 1  # it keeps the corner the upper run's next plane uses: no T-contact (xView overlap)
    assert any(abs(V[i][0] - 5.0) < 1e-6 and abs(V[i][2] - 3.0) < 1e-6 for i in seat[0]["v"])
    at3 = [f for f in r["body"]["faces"] if f["mat"] != "WINDOW" and f["mat"] != "ROOF"
           and all(abs(r["body"]["verts"][i][2] - 3.0) < 1e-6 for i in f["v"])]
    xs = sorted({round(r["body"]["verts"][i][0], 3) for f in at3 for i in f["v"]})
    assert xs and min(xs) >= 5.0 - 1e-6  # the only horizontal reveal at 3.0 is the sill of "up" beyond x = 5


def test_d376_rect_may_run_over_the_next_side_of_the_ring():
    vl = _one()
    cfg = {"extra_rectangles": [_rect("A01", [10.0, 14.0, 0.6, 3.0], "contour_cut", "corner")]}
    e = vb.plans_from_volume_lines(vl, cfg)["A"]
    assert abs(e["plan"]["windows"][0][2] - e["plan"]["windows"][0][1] - 4.0) < 1e-9
    bad = {"extra_rectangles": [_rect("A01", [10.0, 50.0, 0.6, 3.0], "contour_cut", "far")]}
    with pytest.raises(ValueError, match="perimeter"):
        vb.plans_from_volume_lines(vl, bad)


# ---- [D376] (4) one mouth per pair: the seat depth -------------------------------------------------------------
def test_d376_reveal_by_name_sets_the_seat_and_blocks_merge():
    core = _core()
    cfg = {"reveal_m_by_name": {"pair": 0.394}}
    vl = _one()
    vl["rectangles"] += [_rect("A01", [1.0, 2.0, 0.6, 3.0], name="pair"), _rect("A01", [2.5, 3.5, 0.6, 3.0], name="n")]
    e = vb.plans_from_volume_lines(vl, cfg)["A"]
    assert sorted(w[5] for w in e["plan"]["windows"]) == [0.15, 0.394]
    _sound(vb.build_volume(core, e)["report"])
    touch = _one()
    touch["rectangles"] += [_rect("A01", [1.0, 2.0, 0.6, 3.0], name="pair"), _rect("A01", [2.0, 3.0, 0.6, 3.0], name="n")]
    with pytest.raises(ValueError, match="overlap or touch"):  # different seats cannot share a jamb
        vb.plans_from_volume_lines(touch, cfg)
    with pytest.raises(ValueError, match="reveal"):
        vb.plans_from_volume_lines(_one(), {"reveal_m_by_name": {"x": 1.2}})


# ---- [D376] (3) an opening narrowed at the edge end must be an agreed edge ----------------------------------------
def test_d376_edge_clamp_must_be_agreed():
    vl = _one()
    vl["rectangles"].append(_rect("A01", [10.5, 12.0, 0.6, 3.0], name="door", source_rect=[3.0, 4.768, 0.6, 3.0]))
    with pytest.raises(ValueError, match="agreed_edge_clamps"):
        vb.plans_from_volume_lines(copy.deepcopy(vl))
    e = vb.plans_from_volume_lines(copy.deepcopy(vl), {"agreed_edge_clamps": {"door": 0.268}})["A"]
    assert e["agreed_edges"] == [{"name": "door", "edge": "A01", "clamp_m": 0.268, "agreed_m": 0.268}]
    with pytest.raises(ValueError, match="agreed"):
        vb.plans_from_volume_lines(copy.deepcopy(vl), {"agreed_edge_clamps": {"door": 0.20}})
