"""Hatch area and inventory checks for tools/source/inspect_ground_dxf.py (issue #194).

Synthetic DXF built in memory plus one anonymised real excerpt (two hatches and the plot
boundary of the Vatutino paving SPOZU, translated to a local origin).
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import ezdxf
import pytest
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("inspect_ground_dxf", ROOT / "tools/source/inspect_ground_dxf.py")
m = importlib.util.module_from_spec(spec)
sys.modules["inspect_ground_dxf"] = m
spec.loader.exec_module(m)

FIXTURE = ROOT / "tests/fixtures/spozu/vatutino_hatch_excerpt.dxf"
EXTERNAL, OUTERMOST, DEFAULT = 1, 16, 0


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def new_hatch(loops, style=0, extrusion=None):
    doc = ezdxf.new()
    msp = doc.modelspace()
    attribs = {"hatch_style": style}
    if extrusion:
        attribs["extrusion"] = extrusion
    h = msp.add_hatch(dxfattribs=attribs)
    for pts, flag in loops:
        h.paths.add_polyline_path(pts, is_closed=True, flags=flag)
    return doc, h


def test_hole_free_control():
    _, h = new_hatch([(rect(0, 0, 10, 20), EXTERNAL)])
    assert m.hatch_area(h).area == pytest.approx(200.0)


def test_outermost_islands_are_subtracted_not_added():
    # legacy formula (EXTERNAL or OUTERMOST -> +area) gave 10200
    loops = [(rect(0, 0, 100, 100), EXTERNAL), (rect(10, 10, 20, 20), OUTERMOST), (rect(50, 50, 60, 60), OUTERMOST)]
    _, h = new_hatch(loops)
    assert m.hatch_area(h).area == pytest.approx(9800.0)


@pytest.mark.parametrize("style,expected", [(0, 7600.0), (1, 7500.0), (2, 10000.0)])
def test_nested_islands_follow_hatch_style(style, expected):
    loops = [
        (rect(0, 0, 100, 100), EXTERNAL),
        (rect(20, 20, 70, 70), OUTERMOST),
        (rect(40, 40, 50, 50), DEFAULT),
    ]
    _, h = new_hatch(loops, style=style)
    assert m.hatch_area(h).area == pytest.approx(expected)


def test_loop_order_does_not_matter():
    loops = [
        (rect(40, 40, 50, 50), DEFAULT),
        (rect(20, 20, 70, 70), OUTERMOST),
        (rect(0, 0, 100, 100), EXTERNAL),
    ]
    _, h = new_hatch(loops)
    assert m.hatch_area(h).area == pytest.approx(7600.0)


def test_boundary_crossing_is_clipped():
    _, h = new_hatch([(rect(0, 0, 20, 10), EXTERNAL)])
    r = m.hatch_area(h, boundary=box(10, -5, 30, 50))
    assert r.area == pytest.approx(200.0)
    assert r.area_in_plot == pytest.approx(100.0)


def test_arc_edges_are_flattened_within_tolerance():
    doc = ezdxf.new()
    h = doc.modelspace().add_hatch()
    ep = h.paths.add_edge_path(flags=EXTERNAL)
    ep.add_arc((0, 0), 5.0, 0, 360)
    assert m.hatch_area(h, tol=0.001).area == pytest.approx(math.pi * 25, rel=1e-3)


def test_mirrored_ocs_hatch_is_measured_in_wcs():
    # extrusion (0,0,-1): OCS x is WCS -x
    _, h = new_hatch([(rect(0, 0, 10, 10), EXTERNAL)], extrusion=(0, 0, -1))
    assert m.hatch_area(h, boundary=box(-10, 0, 0, 10)).area_in_plot == pytest.approx(100.0)
    assert m.hatch_area(h, boundary=box(0, 0, 10, 10)).area_in_plot == pytest.approx(0.0, abs=1e-9)


def test_invalid_loop_is_reported_not_repaired():
    bowtie = [(0, 0), (10, 10), (10, 0), (0, 10)]
    _, h = new_hatch([(bowtie, EXTERNAL)])
    r = m.hatch_area(h, boundary=box(0, 0, 10, 10))
    assert r.area is None and r.area_in_plot is None
    assert r.issues and "invalid loop" in r.issues[0]


def test_inventory_totals_match_model_space():
    doc, _ = new_hatch([(rect(0, 0, 10, 10), EXTERNAL)])
    msp = doc.modelspace()
    blk = doc.blocks.new("Tree")
    blk.add_attdef("NAME", (0, 0))
    msp.add_line((0, 0), (1, 1), dxfattribs={"layer": "L1"})
    msp.add_blockref("Tree", (5, 5), dxfattribs={"layer": "P"}).add_auto_attribs({"NAME": "oak"})
    msp.add_blockref("Tree", (50, 50), dxfattribs={"layer": "P"})
    doc.blocks.new("Unused")
    inv = m.inventory(doc, boundary=box(0, 0, 10, 10))
    c = inv["checks"]
    assert c["msp_entities"] == c["sum_layer_type_counts"] == 4
    assert c["insert_total"] == c["sum_block_insert_counts"] == 2
    assert c["hatch_total"] == c["hatches_measured"] == 1
    assert inv["blocks"]["Tree"]["in_plot"] == 1
    assert inv["blocks"]["Tree"]["attribs"]["NAME"] == 1
    assert inv["blocks"]["Tree"]["attdefs"] == ["NAME"]
    assert "Unused" in inv["unused_block_defs"]
    assert inv["layers"]["P"]["types"] == {"INSERT": 2}
    md = m.render_markdown("t", inv, "X", 0.001)
    assert "`Tree` | 2 | 1 |" in md


# Real excerpt: paving file hatches 150B41 (1 external + 10 OUTERMOST loops) and 181ECB,
# plot boundary 568BF; coordinates shifted to the boundary bbox min (anonymised).
@pytest.mark.parametrize(
    "handle,expected,legacy",
    [("150B41", 2016.15, 9665.19), ("181ECB", 611.55, 2506.85)],
)
def test_real_excerpt_islands(handle, expected, legacy):
    doc = ezdxf.readfile(FIXTURE)
    by_src = {e.get_xdata("AGR")[0][1]: e for e in doc.modelspace().query("HATCH") if e.has_xdata("AGR")}
    hatch = by_src[handle]
    bnd = m.boundary_polygon(doc, [e for e in doc.modelspace().query("LWPOLYLINE")][0].dxf.handle)
    r = m.hatch_area(hatch, boundary=bnd)
    assert not r.issues
    assert r.area == pytest.approx(expected, abs=0.05)
    assert r.area_in_plot == pytest.approx(expected, abs=0.05)  # fully inside the plot
    assert abs(r.area - legacy) > 1000


def test_layer_overlap_is_measured_by_geometry():
    doc = ezdxf.new()
    msp = doc.modelspace()
    for layer, pts in (("A", rect(0, 0, 10, 10)), ("A", rect(10, 0, 20, 10)), ("B", rect(15, 0, 30, 10))):
        msp.add_hatch(dxfattribs={"layer": layer}).paths.add_polyline_path(pts, is_closed=True, flags=EXTERNAL)
    plot = box(0, 0, 25, 10)
    hs = [m.hatch_area(h, boundary=plot) for h in msp.query("HATCH")]
    un = m.layer_unions(hs, plot)
    assert un["A"].area == pytest.approx(200.0)
    assert un["B"].area == pytest.approx(100.0)  # clipped at x=25
    assert m.overlaps(un, ["A", "B"]) == [("A", "B", pytest.approx(50.0))]


def test_polygonal_drops_stray_lines_from_overlays():
    from shapely.geometry import GeometryCollection, LineString

    g = GeometryCollection([box(0, 0, 1, 1), LineString([(2, 2), (3, 3)])])
    out = m._polygonal(g)
    assert out.geom_type == "MultiPolygon" and out.area == pytest.approx(1.0)


# --- Curved plot boundary (review round 2): bulges, OCS, closed validation ---


def _boundary_doc(points, close=True, extrusion=None):
    doc = ezdxf.new()
    attribs = {"extrusion": extrusion} if extrusion else {}
    pl = doc.modelspace().add_lwpolyline(points, format="xyb", close=close, dxfattribs=attribs)
    return doc, pl.dxf.handle


def test_two_semicircle_boundary_is_a_circle():
    # legacy vertex-only ring: 2 points -> "degenerate loop" ValueError
    doc, hnd = _boundary_doc([(1, 0, 1), (-1, 0, 1)])
    poly = m.boundary_polygon(doc, hnd)
    assert poly.area == pytest.approx(math.pi, rel=1e-3)
    assert poly.length == pytest.approx(2 * math.pi, rel=1e-3)


def test_open_boundary_is_rejected():
    doc, hnd = _boundary_doc([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)], close=False)
    with pytest.raises(ValueError, match="not closed"):
        m.boundary_polygon(doc, hnd)


def test_unflagged_boundary_ending_at_start_is_closed():
    doc, hnd = _boundary_doc([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0), (0, 0, 0)], close=False)
    assert m.boundary_polygon(doc, hnd).area == pytest.approx(100.0)


def test_mirrored_ocs_curved_boundary_is_in_wcs():
    # OCS circle centre (5, 0), r = 1, extrusion -Z -> WCS centre (-5, 0)
    doc, hnd = _boundary_doc([(6, 0, 1), (4, 0, 1)], extrusion=(0, 0, -1))
    poly = m.boundary_polygon(doc, hnd)
    assert poly.centroid.x == pytest.approx(-5.0, abs=1e-6)
    assert poly.area == pytest.approx(math.pi, rel=1e-3)


R = 10.0
CIRCLE_AREA = math.pi * R * R


@pytest.mark.parametrize(
    "style,expected",
    [(0, CIRCLE_AREA - 100.0 + 4.0), (1, CIRCLE_AREA - 100.0), (2, CIRCLE_AREA)],
)
def test_curved_boundary_clips_islands_by_style(style, expected):
    # 40 x 40 hatch, island 10 x 10, island-in-island 2 x 2, all centred on a circular plot r = 10
    doc, hnd = _boundary_doc([(R, 0, 1), (-R, 0, 1)])
    plot = m.boundary_polygon(doc, hnd)
    loops = [(rect(-20, -20, 20, 20), EXTERNAL), (rect(-5, -5, 5, 5), OUTERMOST), (rect(-1, -1, 1, 1), DEFAULT)]
    _, h = new_hatch(loops, style=style)
    r = m.hatch_area(h, boundary=plot)
    assert r.area_in_plot == pytest.approx(expected, rel=1e-3)


def test_curved_boundary_clips_mirrored_ocs_hatch():
    # OCS rect (0,0)-(20,20) with extrusion -Z covers WCS x in [-20, 0]: a quarter of the circular plot
    doc, hnd = _boundary_doc([(R, 0, 1), (-R, 0, 1)])
    plot = m.boundary_polygon(doc, hnd)
    _, h = new_hatch([(rect(0, 0, 20, 20), EXTERNAL)], extrusion=(0, 0, -1))
    assert m.hatch_area(h, boundary=plot).area_in_plot == pytest.approx(CIRCLE_AREA / 4, rel=1e-3)


def _fixture_boundary(doc):
    return [e for e in doc.modelspace().query("LWPOLYLINE")][0]


def test_real_boundary_keeps_its_four_bulges():
    doc = ezdxf.readfile(FIXTURE)
    pl = _fixture_boundary(doc)
    assert sum(1 for v in pl.get_points("xyseb") if v[4]) == 4
    poly = m.boundary_polygon(doc, pl.dxf.handle)
    assert poly.area == pytest.approx(25854.05, abs=0.05)  # chord-only ring: 25725.08
    assert poly.length == pytest.approx(641.947, abs=0.005)  # chord-only ring: 639.216


def test_real_light_tile_crossing_a_bulge_is_clipped_by_the_arc():
    # paving hatch FAA81 (light tile, style 1, 2 loops) crosses a curved edge of 568BF
    doc = ezdxf.readfile(FIXTURE)
    by_src = {e.get_xdata("AGR")[0][1]: e for e in doc.modelspace().query("HATCH") if e.has_xdata("AGR")}
    plot = m.boundary_polygon(doc, _fixture_boundary(doc).dxf.handle)
    r = m.hatch_area(by_src["FAA81"], boundary=plot)
    assert not r.issues
    assert r.area == pytest.approx(562.86, abs=0.05)
    assert r.area_in_plot == pytest.approx(301.13, abs=0.05)  # chord-only ring: 282.42


@pytest.mark.parametrize("bulge", [0.05, -0.3, 0.7, 1.0, -1.0])
def test_arc_points_lie_on_the_circle_within_tol(bulge):
    tol = 1e-3
    p1, p2 = (0.0, 0.0), (100.0, 0.0)
    pts = [p1, *m.arc_points(p1, p2, bulge, tol), p2]
    sweep = 4 * math.atan(bulge)
    r = 100.0 / (2 * abs(math.sin(sweep / 2)))
    # the arc midpoint lies bulge * c / 2 right of the chord; the centre is r back towards the chord
    cy = -bulge * 50.0 + math.copysign(r, bulge)
    for x, y in pts:
        assert math.hypot(x - 50.0, y - cy) == pytest.approx(r, abs=1e-9)
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        assert r - math.hypot(mx - 50.0, my - cy) <= tol + 1e-12


def test_bulged_polyline2d_boundary_is_supported():
    doc = ezdxf.new()
    pl = doc.modelspace().add_polyline2d([(1, 0, 1), (-1, 0, 1)], format="xyb", close=True)
    assert m.boundary_polygon(doc, pl.dxf.handle).area == pytest.approx(math.pi, rel=1e-3)


def _green_area(verts):
    """Exact area of a closed bulged polyline: signed chord shoelace + signed circular segments."""
    k = len(verts)
    area, arc_len = 0.0, 0.0
    for i in range(k):
        (x1, y1, b), (x2, y2, _) = verts[i], verts[(i + 1) % k]
        area += 0.5 * (x1 * y2 - x2 * y1)
        c = math.hypot(x2 - x1, y2 - y1)
        if b and c:
            th = 4 * math.atan(b)
            r = c / (2 * math.sin(th / 2))
            area += r * r / 2 * (th - math.sin(th))
            arc_len += abs(r * th)
    return abs(area), arc_len


def test_random_bulged_boundaries_match_the_exact_area():
    import random

    rng = random.Random(194)
    checked = rejected = 0
    while checked < 200:
        k = rng.randint(2, 9)
        angs = sorted(rng.uniform(0, 2 * math.pi) for _ in range(k))
        sx, sy = rng.uniform(-2e4, 2e4), rng.uniform(-2e4, 2e4)
        verts = [
            (sx + r * math.cos(a), sy + r * math.sin(a), rng.choice([0.0, rng.uniform(-0.6, 0.6), rng.uniform(0.6, 1.0)]))
            for r, a in ((rng.uniform(20, 200), a) for a in angs)
        ]
        if k == 2:
            verts = [(x, y, rng.uniform(0.2, 1.0)) for x, y, _ in verts]
        exact, arc_len = _green_area(verts)
        doc, hnd = _boundary_doc(verts, extrusion=rng.choice([None, (0, 0, -1)]))
        try:
            poly = m.boundary_polygon(doc, hnd)
        except ValueError as exc:  # bulges made the ring self-intersect: reported, never repaired
            assert "invalid loop" in str(exc)
            rejected += 1
            continue
        checked += 1
        assert abs(poly.area - exact) <= 2 / 3 * m.BOUNDARY_TOL * arc_len + 1e-6 * exact
    assert rejected < checked
