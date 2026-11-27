"""#1784 v007 ([D410]): roof well inside the parapet - the top cap becomes a parapet band, well walls and a deck.

Synthetic data only (not a real object). Loads the shared body core #1736 (body_lattice.py) from main.
"""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "methods" / "body"))
import volume_body as vb  # noqa: E402

CORE = vb.load_core(str(ROOT / "tools" / "methods" / "body"))


def _vl(levels=(0.0, 3.0, 6.0, 7.2), rects=()):
    """One 12 x 8 m CCW volume A, edges A01..A04; optional window rects."""
    ring = [[0, 0], [12, 0], [12, 8], [0, 8]]
    vl = {"volumes": {"A": {"ring": ring + [ring[0]], "levels": list(levels)}}, "edges": {}, "rectangles": list(rects)}
    for i in range(4):
        a, b = ring[i], ring[(i + 1) % 4]
        vl["edges"]["A%02d" % (i + 1)] = {"volume": "A", "xy": [a, b], "facade": "F%d" % i, "seam": None,
                                          "length": math.dist(a, b), "visible_from": 0}
    return vl


def _win(rect, name="w"):
    return {"facade": "F0", "kind": "surrounds", "name": name, "edge": "A01", "projected_rect": rect,
            "snapped_rect": rect, "state": "cut"}


def _build(vl, cfg):
    e = vb.plans_from_volume_lines(vl, cfg)["A"]
    return vb.build_volume(CORE, e)


def _key_faces(body):
    vv = body["verts"]
    return {tuple(sorted(tuple(round(c, 3) for c in vv[i]) for i in f["v"])) for f in body["faces"]}


def test_roof_well_replaces_only_the_cap_and_stays_closed():
    flat = _build(_vl(rects=[_win([2.0, 4.0, 3.0, 6.0])]), {})
    well = _build(_vl(rects=[_win([2.0, 4.0, 3.0, 6.0])]), {"roof_wells": {"A": {"deck_z": 6.5, "parapet_m": 0.2}}})
    gone = _key_faces(flat["body"]) - _key_faces(well["body"])
    assert len(gone) == 1  # only the flat top cap
    rep = well["report"]
    assert rep["roof_well"]["deck_z"] == 6.5 and rep["roof_well"]["faces_added"] == 2 * rep["roof_well"]["segments"] + 1
    m = rep["body"]
    assert m["non_manifold_edges"] == 0 and m["bowtie_vertices"] == 0 and m["defect_cells"] == 0
    assert rep["open_edges"]["other"] == 0
    assert rep["open_edges"] == flat["report"]["open_edges"]  # the well adds no boundary
    vv = well["body"]["verts"]
    deck = [f for f in well["body"]["faces"] if f["mat"] == "ROOF"]
    assert len(deck) == 1 and all(abs(vv[i][2] - 6.5) < 1e-9 for i in deck[0]["v"])
    xs = [vv[i][0] for i in deck[0]["v"]]
    ys = [vv[i][1] for i in deck[0]["v"]]
    assert min(xs) == pytest.approx(0.2) and max(xs) == pytest.approx(11.8)
    assert min(ys) == pytest.approx(0.2) and max(ys) == pytest.approx(7.8)
    walls = [f for f in well["body"]["faces"] if f["mat"] == "WALL" and len(f["v"]) == 4
             and {round(vv[i][2], 3) for i in f["v"]} == {6.5, 7.2}]
    assert walls  # the inner well walls face the well: normal toward the centre (6, 4)
    for f in walls:
        co = [vv[i] for i in f["v"]]
        nx, ny, _, _ = vb._normal(co)
        cx, cy = sum(p[0] for p in co) / 4, sum(p[1] for p in co) / 4
        assert nx * (6 - cx) + ny * (4 - cy) > 0


def test_roof_well_edge_depth_and_window_guard():
    vl = _vl(rects=[_win([2.0, 4.0, 3.0, 7.2])])  # head at the top, above any deck
    with pytest.raises(ValueError, match="reveal"):
        _build(vl, {"roof_wells": {"A": {"deck_z": 6.5, "parapet_m": 0.15}}})
    ok = _build(vl, {"roof_wells": {"A": {"deck_z": 6.5, "parapet_m": 0.15, "parapet_m_by_edge": {"A01": 0.3}}}})
    deck = next(f for f in ok["body"]["faces"] if f["mat"] == "ROOF")
    vv = ok["body"]["verts"]
    assert min(vv[i][1] for i in deck["v"]) == pytest.approx(0.3)
    assert min(vv[i][0] for i in deck["v"]) == pytest.approx(0.15)


def test_roof_well_and_base_config_are_validated():
    with pytest.raises(ValueError, match="deck_z"):
        vb.plans_from_volume_lines(_vl(), {"roof_wells": {"A": {"deck_z": 5.0, "parapet_m": 0.2}}})
    with pytest.raises(ValueError, match="edge X9"):
        vb.plans_from_volume_lines(_vl(), {"roof_wells": {"A": {"deck_z": 6.5, "parapet_m": 0.2,
                                                                 "parapet_m_by_edge": {"X9": 0.3}}}})
    plan = vb.plans_from_volume_lines(_vl(), {"base_by_volume": {"A": -0.1}})["A"]["plan"]
    assert plan["z0"] == -0.1 and plan["step"] == pytest.approx(7.3)
