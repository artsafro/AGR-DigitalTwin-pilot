"""adapters/cad SPOZU reader (issue #195): synthetic DXF fixtures built in the test, no user files.

Clean case (GREEN) plus one RED fixture per validation finding; `acad` tests need the AutoCAD
2025 core console; the Vatutino test is opt-in (DT_SPOZU_VATUTINO = path to a local COPY).
"""

from __future__ import annotations

import json
import math
import os
import random
import re
from pathlib import Path

import ezdxf
import pytest
from shapely import union_all
from shapely.geometry import Polygon

from adapters.cad import spozu
from adapters.cad.spozu import SpozuConfig, SpozuConfigError, read_spozu_dxf

ROOT = Path(__file__).resolve().parents[1]
VATUTINO_CONFIG = ROOT / "adapters/cad/configs/vatutino_dom2.yaml"
EXTERNAL = 1


def rect(x0, y0, x1, y1, k=1.0):
    return [(x0 * k, y0 * k), (x1 * k, y0 * k), (x1 * k, y1 * k), (x0 * k, y1 * k)]


def base_config(**over) -> dict:
    cfg = {
        "project": "synthetic",
        "boundary": {"layer": "BOUNDARY"},
        "coverings": [
            {"type": "tile", "layers": ["COV_TILE"]},
            {"type": "lawn", "layers": ["COV_LAWN"]},
            {"type": "deck", "layers": ["COV_DECK"], "sources": ["hatch", "polyline"]},
        ],
        "planting": {"layers": ["PLANT"], "positions": {"Oak": "1"}},
        "maf": {"layers": ["MAF"], "positions": {"Bench": "M1"}},
        "elevations": {"layers": ["SPOT"], "containers": ["VP_CONTAINER"], "value": "text"},
        "ignore_layers": ["0", "Defpoints"],
    }
    cfg.update(over)
    return cfg


def clean_doc(k: float = 1.0, insunits: int = 6):
    """100 x 100 plot: tile 0..60 with a 20 x 20 hole, lawn in the hole and 60..100, points, heights."""
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    msp.add_lwpolyline(rect(0, 0, 100, 100, k), close=True, dxfattribs={"layer": "BOUNDARY"})
    h = msp.add_hatch(dxfattribs={"layer": "COV_TILE"})
    h.paths.add_polyline_path(rect(0, 0, 100, 60, k), is_closed=True, flags=EXTERNAL)
    h.paths.add_polyline_path(rect(40, 20, 60, 40, k), is_closed=True)
    for r in (rect(40, 20, 60, 40, k), rect(0, 60, 100, 100, k)):
        lh = msp.add_hatch(dxfattribs={"layer": "COV_LAWN"})
        lh.paths.add_polyline_path(r, is_closed=True, flags=EXTERNAL)
    for name in ("Oak", "Bench"):
        doc.blocks.new(name).add_circle((0, 0), 0.5 * k)
    msp.add_blockref("Oak", (10 * k, 70 * k), dxfattribs={"layer": "PLANT"})
    msp.add_blockref("Bench", (80 * k, 10 * k), dxfattribs={"layer": "MAF"})
    vp = doc.blocks.new("VP")
    vp.add_mtext("145.50", dxfattribs={"layer": "SPOT", "insert": (50 * k, 50 * k, 0)})
    vp.add_text("146,25", dxfattribs={"layer": "SPOT", "insert": (20 * k, 80 * k, 0)})
    msp.add_blockref("VP", (0, 0), dxfattribs={"layer": "VP_CONTAINER"})
    return doc


def codes(res):
    return sorted(f.code for f in res.findings)


# ---------------------------------------------------------------- GREEN


def test_clean_case_typed_result_no_findings():
    res = read_spozu_dxf(clean_doc(), SpozuConfig.from_dict(base_config()))
    assert res.findings == []
    assert res.boundary.area == pytest.approx(10000)
    tile, lawn = res.coverings["tile"], res.coverings["lawn"]
    assert tile.area == pytest.approx(5600)
    assert [len(p.interiors) for p in tile.polygons] == [1]  # hole kept
    assert lawn.area == pytest.approx(4400)
    assert res.coverings["deck"].polygons == []
    assert res.base_covering == "tile"
    assert [(p.label, p.position, p.inside) for p in res.planting] == [("Oak", "1", True)]
    assert [(p.label, p.position) for p in res.maf] == [("Bench", "M1")]
    assert sorted(e.z for e in res.elevations) == [145.5, 146.25]
    assert {(round(e.x), round(e.y)) for e in res.elevations} == {(50, 50), (20, 80)}
    json.dumps(res.to_dict())  # serialisable for the Ground procedure


def test_units_millimetres_become_metres():
    res = read_spozu_dxf(clean_doc(k=1000.0, insunits=4), SpozuConfig.from_dict(base_config()))
    assert res.findings == []
    assert res.unit_scale == 0.001
    assert res.boundary.area == pytest.approx(10000)
    assert res.coverings["tile"].area == pytest.approx(5600)
    assert (res.planting[0].x, res.planting[0].y) == pytest.approx((10, 70))


def test_base_covering_is_largest_area():
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_LAWN"})
    # lawn grows by nothing inside the plot (outside), tile stays base
    h.paths.add_polyline_path(rect(200, 200, 300, 300), is_closed=True, flags=EXTERNAL)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.base_covering == "tile"
    assert res.coverings["lawn"].area == pytest.approx(4400)  # clipped to the plot
    cfg = base_config()
    cfg["coverings"][0]["layers"], cfg["coverings"][1]["layers"] = ["COV_LAWN"], ["COV_TILE"]
    res2 = read_spozu_dxf(clean_doc(), SpozuConfig.from_dict(cfg))
    assert res2.base_covering == "lawn"


def test_boundary_handle_selects_among_candidates():
    doc = clean_doc()
    other = doc.modelspace().add_lwpolyline(rect(500, 500, 510, 510), close=True, dxfattribs={"layer": "BOUNDARY"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert "boundary_ambiguous" in codes(res) and res.boundary is None
    first = next(e for e in doc.modelspace().query("LWPOLYLINE[layer=='BOUNDARY']") if e.dxf.handle != other.dxf.handle)
    res2 = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config(boundary={"layer": "BOUNDARY", "handle": first.dxf.handle})))
    assert res2.findings == [] and res2.boundary.area == pytest.approx(10000)


def test_ignore_layers_glob_silences_unmapped():
    doc = clean_doc()
    doc.modelspace().add_line((0, 0), (1, 1), dxfattribs={"layer": "XREF$0$roads"})
    assert codes(read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))) == ["unmapped_layer"]
    cfg = base_config(ignore_layers=["0", "XREF$0$*"])
    assert read_spozu_dxf(doc, SpozuConfig.from_dict(cfg)).findings == []


# ---------------------------------------------------------------- RED: one per finding


def test_open_polyline_contour_is_a_finding():
    doc = clean_doc()
    e = doc.modelspace().add_lwpolyline([(5, 65), (15, 65), (15, 75)], dxfattribs={"layer": "COV_DECK"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    f = [x for x in res.findings if x.code == "open_contour"]
    assert [x.handle for x in f] == [e.dxf.handle]
    assert res.coverings["deck"].polygons == []


def test_open_hatch_edge_loop_is_a_finding():
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    ep = h.paths.add_edge_path(flags=EXTERNAL)
    ep.add_line((5, 65), (15, 65))
    ep.add_line((15, 65), (15, 75))
    ep.add_line((15, 75), (6, 74))  # does not return to (5, 65)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle) for x in res.findings] == [("open_contour", h.dxf.handle)]
    assert res.coverings["deck"].area == 0


def test_self_intersecting_hatch_is_a_finding_not_repaired():
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path([(5, 65), (15, 75), (15, 65), (5, 75)], is_closed=True, flags=EXTERNAL)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle) for x in res.findings] == [("self_intersecting_contour", h.dxf.handle)]
    assert res.coverings["deck"].area == 0


def test_self_intersecting_closed_polyline_is_a_finding():
    doc = clean_doc()
    e = doc.modelspace().add_lwpolyline([(5, 65), (15, 75), (15, 65), (5, 75)], close=True, dxfattribs={"layer": "COV_DECK"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle) for x in res.findings] == [("self_intersecting_contour", e.dxf.handle)]


def test_overlapping_coverings_is_a_finding():
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path(rect(0, 50, 100, 70), is_closed=True, flags=EXTERNAL)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    ov = [x for x in res.findings if x.code == "overlapping_coverings"]
    pairs = {tuple(sorted(x.layer.split(" / "))): x.area for x in ov}
    assert pairs.keys() == {("deck", "tile"), ("deck", "lawn")}
    assert pairs[("deck", "tile")] == pytest.approx(1000)
    assert pairs[("deck", "lawn")] == pytest.approx(1000)


def test_points_outside_boundary_are_findings():
    doc = clean_doc()
    msp = doc.modelspace()
    o = msp.add_blockref("Oak", (150, 150), dxfattribs={"layer": "PLANT"})
    b = msp.add_blockref("Bench", (-5, 50), dxfattribs={"layer": "MAF"})
    t = doc.blocks["VP"].add_text("140.00", dxfattribs={"layer": "SPOT", "insert": (120, 20, 0)})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    out = [x for x in res.findings if x.code == "point_outside_boundary"]
    assert len(out) == 3
    assert {x.handle for x in out} >= {o.dxf.handle, b.dxf.handle}
    assert [p.inside for p in res.planting] == [True, False]
    assert sorted(e.inside for e in res.elevations) == [False, True, True]
    assert t is not None


def test_unmapped_layer_is_a_finding():
    doc = clean_doc()
    doc.modelspace().add_line((1, 1), (2, 2), dxfattribs={"layer": "MYSTERY"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.layer) for x in res.findings] == [("unmapped_layer", "MYSTERY")]


def test_open_boundary_is_a_finding_and_no_guess():
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    e = doc.modelspace().add_lwpolyline([(0, 0), (100, 0), (100, 100), (0, 100)], dxfattribs={"layer": "BOUNDARY"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.boundary is None
    assert ("open_contour", e.dxf.handle) in [(x.code, x.handle) for x in res.findings]
    assert "boundary_not_found" in codes(res)


def test_unparsed_elevation_text_is_a_finding():
    doc = clean_doc()
    t = doc.blocks["VP"].add_text("h=?", dxfattribs={"layer": "SPOT", "insert": (30, 30, 0)})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle) for x in res.findings] == [("elevation_unparsed", t.dxf.handle)]
    assert len(res.elevations) == 2


# ---------------------------------------------------------------- config


def test_unknown_units_without_config_raise():
    with pytest.raises(SpozuConfigError):
        read_spozu_dxf(clean_doc(insunits=0), SpozuConfig.from_dict(base_config()))
    res = read_spozu_dxf(clean_doc(k=1000, insunits=0), SpozuConfig.from_dict(base_config(units="mm")))
    assert res.boundary.area == pytest.approx(10000)


def test_layer_mapped_twice_is_a_config_error():
    cfg = base_config()
    cfg["coverings"][1]["layers"] = ["COV_TILE"]
    with pytest.raises(SpozuConfigError):
        SpozuConfig.from_dict(cfg)


def test_vatutino_config_loads_from_inventory_map():
    cfg = spozu.load_config(VATUTINO_CONFIG)
    assert cfg.boundary_layer == "ПР_ЛГР_предлагаемые" and cfg.boundary_handle == "568BF"
    types = {c.type for c in cfg.coverings}
    assert {"tile_light", "tile_red", "tile_dark", "mulch", "lawn_reinforced", "lawn_rolled"} <= types
    assert "!_А101_деревья" in cfg.planting_layers and "!_А101_маф" in cfg.maf_layers
    assert len(cfg.planting_positions) == 17


def test_reader_code_has_no_hard_coded_project_layers():
    for f in ("spozu.py", "dwg.py"):
        text = (ROOT / "adapters/cad" / f).read_text(encoding="utf-8")
        assert not re.search(r"[А-Яа-яЁё]", text), f"{f}: Cyrillic literal (project layer names belong in configs/)"


# ---------------------------------------------------------------- probes (generated)


def _probe_doc(rng: random.Random, k: float, insunits: int):
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = insunits
    msp = doc.modelspace()
    w, hgt = rng.uniform(20, 300), rng.uniform(20, 300)
    ox, oy = rng.uniform(-20000, 20000), rng.uniform(-20000, 20000)
    msp.add_lwpolyline([((ox + x) * k, (oy + y) * k) for x, y in rect(0, 0, w, hgt)], close=True, dxfattribs={"layer": "BOUNDARY"})
    # one tile hatch inside with 0..3 disjoint holes
    hx0, hy0, hx1, hy1 = 0.1 * w, 0.1 * hgt, 0.9 * w, 0.9 * hgt
    h = msp.add_hatch(dxfattribs={"layer": "COV_TILE"})
    h.paths.add_polyline_path([((ox + x) * k, (oy + y) * k) for x, y in rect(hx0, hy0, hx1, hy1)], is_closed=True, flags=EXTERNAL)
    n_holes = rng.randint(0, 3)
    hole_area = 0.0
    cw = (hx1 - hx0) / 3
    for i in range(n_holes):
        x0 = hx0 + i * cw + 0.2 * cw
        y0 = hy0 + 0.2 * (hy1 - hy0)
        hw, hh = 0.5 * cw, 0.3 * (hy1 - hy0)
        h.paths.add_polyline_path([((ox + x) * k, (oy + y) * k) for x, y in rect(x0, y0, x0 + hw, y0 + hh)], is_closed=True)
        hole_area += hw * hh
    doc.blocks.new("Oak")
    n_out = 0
    for _ in range(rng.randint(1, 12)):
        px, py = rng.uniform(-0.5 * w, 1.5 * w), rng.uniform(-0.5 * hgt, 1.5 * hgt)
        if abs(px) < 1e-3 or abs(py) < 1e-3 or abs(px - w) < 1e-3 or abs(py - hgt) < 1e-3:
            continue
        n_out += not (0 < px < w and 0 < py < hgt)
        msp.add_blockref("Oak", ((ox + px) * k, (oy + py) * k), dxfattribs={"layer": "PLANT"})
    expected = {"plot": w * hgt, "tile": (hx1 - hx0) * (hy1 - hy0) - hole_area, "holes": n_holes, "out": n_out}
    return doc, expected


@pytest.mark.parametrize("seed", range(60))
def test_probe_units_holes_outside_points(seed):
    """Generated probe: metres for every unit, holes kept, every outside point flagged once."""
    rng = random.Random(1950 + seed)
    insunits, k = rng.choice([(6, 1.0), (4, 1000.0), (5, 100.0), (1, 1 / 0.0254), (2, 1 / 0.3048)])
    doc, exp = _probe_doc(rng, k, insunits)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.boundary.area == pytest.approx(exp["plot"], rel=1e-6)
    assert res.coverings["tile"].area == pytest.approx(exp["tile"], rel=1e-6)
    assert sum(len(p.interiors) for p in res.coverings["tile"].polygons) == exp["holes"]
    out = [f for f in res.findings if f.code == "point_outside_boundary"]
    assert len(out) == exp["out"] == sum(not p.inside for p in res.planting)
    assert len({f.handle for f in out}) == len(out)
    assert math.isclose(res.unit_scale * k, 1.0, rel_tol=1e-12)


@pytest.mark.parametrize("seed", range(40))
def test_probe_overlap_finding_matches_brute_force(seed):
    """Generated probe: an overlap finding exists iff two covering types share > tol m2 inside the plot."""
    rng = random.Random(7700 + seed)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(rect(0, 0, 100, 100), close=True, dxfattribs={"layer": "BOUNDARY"})
    boxes = {}
    for lay in ("COV_TILE", "COV_LAWN"):
        x0, y0 = rng.uniform(-30, 90), rng.uniform(-30, 90)
        x1, y1 = x0 + rng.uniform(1, 60), y0 + rng.uniform(1, 60)
        boxes[lay] = (x0, y0, x1, y1)
        h = msp.add_hatch(dxfattribs={"layer": lay})
        h.paths.add_polyline_path(rect(x0, y0, x1, y1), is_closed=True, flags=EXTERNAL)

    def clip(b):
        return max(b[0], 0), max(b[1], 0), min(b[2], 100), min(b[3], 100)

    a, b = clip(boxes["COV_TILE"]), clip(boxes["COV_LAWN"])
    ov = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    found = [f for f in res.findings if f.code == "overlapping_coverings"]
    if ov > 0.01 + 1e-6:
        assert len(found) == 1 and found[0].area == pytest.approx(ov, abs=1e-4)
    elif ov < 0.01 - 1e-6:
        assert found == []


# ---------------------------------------------------------------- AutoCAD (core console)


@pytest.mark.acad
def test_acad_dwg_roundtrip_through_core_console(tmp_path):
    """Synthetic DXF -> DWG (core console DXFIN + SAVEAS) -> adapter DWG path -> same result."""
    from adapters.cad.dwg import dwg_to_dxf, make_dwg_from_dxf

    src = tmp_path / "clean.dxf"
    clean_doc().saveas(src)
    dwg = make_dwg_from_dxf(src, tmp_path / "clean.dwg")
    before = spozu.sha256_file(dwg)
    conv = dwg_to_dxf(dwg, tmp_path / "conv")
    assert spozu.sha256_file(dwg) == before
    res = read_spozu_dxf(conv.dxf, SpozuConfig.from_dict(base_config()))
    assert res.boundary.area == pytest.approx(10000)
    assert res.coverings["tile"].area == pytest.approx(5600)
    assert res.base_covering == "tile"
    assert len(res.planting) == 1 and len(res.maf) == 1 and len(res.elevations) == 2


@pytest.mark.acad
def test_vatutino_copy_counts(tmp_path_factory):
    """Opt-in: DT_SPOZU_VATUTINO = a local COPY (.dwg or .dxf) of the Vatutino SPOZU; reports counts."""
    path = os.environ.get("DT_SPOZU_VATUTINO")
    if not path or not Path(path).exists():
        pytest.skip("DT_SPOZU_VATUTINO not set or file missing")
    res = spozu.read_spozu(path, spozu.load_config(VATUTINO_CONFIG), workdir=tmp_path_factory.mktemp("vatutino"))
    summary = res.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    out = os.environ.get("DT_SPOZU_VATUTINO_REPORT")
    if out:
        Path(out).write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    assert res.boundary is not None and res.boundary.area == pytest.approx(25854.04, abs=0.01)
    assert res.base_covering == "tile_light"
    assert sum(p.inside for p in res.planting) > 4000


# ---------------------------------------------------------------- review round 1 regressions (P1-1..3)


def test_open_hatch_polyline_path_is_a_finding_not_closed():
    """P1-1: a polyline path with is_closed=False is open; ezdxf must not add the closing edge."""
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path([(5, 65), (15, 65), (15, 75), (5, 75)], is_closed=False, flags=EXTERNAL)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle) for x in res.findings] == [("open_contour", h.dxf.handle)]
    assert res.coverings["deck"].area == 0 and res.coverings["deck"].sources == []


@pytest.mark.parametrize("closed_flag", [False, True])
def test_hatch_polyline_path_closed_controls(closed_flag):
    """P1-1 controls: is_closed=True, or is_closed=False with last vertex == first vertex, is a closed loop."""
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    pts = rect(5, 5, 15, 15) + ([] if closed_flag else [(5, 5)])
    h.paths.add_polyline_path(pts, is_closed=closed_flag, flags=EXTERNAL)
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert "open_contour" not in codes(res)
    assert res.coverings["deck"].area == pytest.approx(100)


def _attrib_doc():
    doc = clean_doc()
    msp = doc.modelspace()
    oak = next(e for e in msp.query("INSERT") if e.dxf.name == "Oak")
    bench = next(e for e in msp.query("INSERT") if e.dxf.name == "Bench")
    return doc, oak, bench


@pytest.mark.parametrize("value", [None, "", "   "])
def test_missing_or_empty_label_attribute_is_a_finding(value):
    """P1-2: attrib:<TAG> configured, attribute absent or empty -> unresolved label + label_missing."""
    doc, oak, bench = _attrib_doc()
    if value is not None:
        oak.add_attrib("SPECIES", value, (10, 70))
        bench.add_attrib("PRODUCT", value, (80, 10))
    pl = {"layers": ["PLANT"], "positions": {"Oak": "1"}, "label": "attrib:SPECIES"}
    maf = {"layers": ["MAF"], "positions": {"Bench": "M1"}, "label": "attrib:PRODUCT"}
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config(planting=pl, maf=maf)))
    assert sorted((x.code, x.handle) for x in res.findings) == sorted(
        [("label_missing", oak.dxf.handle), ("label_missing", bench.dxf.handle)])
    assert all("SPECIES" in x.detail or "PRODUCT" in x.detail for x in res.findings)
    assert [p.label for p in res.planting] == [None] and [p.label for p in res.maf] == [None]
    assert res.planting[0].position == "1"  # the block name still keys the schedule position
    assert res.summary()["planting"]["species_inside"] == 0


def test_present_label_attribute_is_used():
    doc, oak, _ = _attrib_doc()
    oak.add_attrib("SPECIES", "Verified oak", (10, 70))
    pl = {"layers": ["PLANT"], "positions": {"Oak": "1"}, "label": "attrib:SPECIES"}
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config(planting=pl)))
    assert res.findings == []
    assert [p.label for p in res.planting] == ["Verified oak"]


def _container_block(doc, name="GROUND_CONTAINER"):
    blk = doc.blocks.new(name)
    h = blk.add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path(rect(0, 0, 2, 2), is_closed=True, flags=EXTERNAL)
    p = blk.add_blockref("Oak", (2, 2), dxfattribs={"layer": "PLANT"})
    b = blk.add_blockref("Bench", (3, 3), dxfattribs={"layer": "MAF"})
    return blk, h, p, b


def test_nested_ground_inputs_rotated_container():
    """P1-3: rotated container on an ignored layer: hatch, plant and MAF in WCS with provenance."""
    doc = clean_doc()
    _, h, p, b = _container_block(doc)
    ins = doc.modelspace().add_blockref("GROUND_CONTAINER", (20, 70), dxfattribs={"layer": "0", "rotation": 90})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.coverings["deck"].area == pytest.approx(4)
    assert res.coverings["deck"].sources == [f"{ins.dxf.handle}>{h.dxf.handle}"]
    assert len(res.planting) == 2 and len(res.maf) == 2
    nested = [x for x in res.planting if x.container]
    assert len(nested) == 1 and (nested[0].x, nested[0].y) == pytest.approx((18, 72))
    assert nested[0].handle == p.dxf.handle and nested[0].container == ins.dxf.handle
    assert nested[0].label == "Oak" and nested[0].position == "1" and nested[0].inside
    m = [x for x in res.maf if x.container][0]
    assert (m.x, m.y) == pytest.approx((17, 73)) and m.handle == b.dxf.handle
    # the deck sits on the lawn -> the overlap is reported, nothing else
    assert codes(res) == ["overlapping_coverings"]
    assert res.findings[0].area == pytest.approx(4)


def test_nested_repeated_and_two_level_inserts():
    doc = clean_doc()
    _, h, _, _ = _container_block(doc)
    msp = doc.modelspace()
    a = msp.add_blockref("GROUND_CONTAINER", (20, 70), dxfattribs={"layer": "0", "rotation": 90})
    b = msp.add_blockref("GROUND_CONTAINER", (30, 70), dxfattribs={"layer": "0"})
    outer = doc.blocks.new("OUTER")
    inner = outer.add_blockref("GROUND_CONTAINER", (1, 1), dxfattribs={"layer": "0"})
    c = msp.add_blockref("OUTER", (50, 80), dxfattribs={"layer": "0", "xscale": 2, "yscale": 2})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    deck = res.coverings["deck"]
    assert deck.area == pytest.approx(4 + 4 + 16)
    assert sorted(deck.sources) == sorted([f"{a.dxf.handle}>{h.dxf.handle}", f"{b.dxf.handle}>{h.dxf.handle}",
                                           f"{c.dxf.handle}>{inner.dxf.handle}>{h.dxf.handle}"])
    nested = sorted((round(x.x, 6), round(x.y, 6), x.ref) for x in res.planting if x.container)
    assert [(x, y) for x, y, _ in nested] == [(18, 72), (32, 72), (56, 86)]
    assert len({r for _, _, r in nested}) == 3  # one provenance path per instance
    assert len(res.maf) == 4


def test_nested_layer_zero_inherits_insert_layer():
    doc = clean_doc()
    blk = doc.blocks.new("DECK0")
    h = blk.add_hatch(dxfattribs={"layer": "0"})
    h.paths.add_polyline_path(rect(0, 0, 3, 3), is_closed=True, flags=EXTERNAL)
    doc.modelspace().add_blockref("DECK0", (5, 5), dxfattribs={"layer": "COV_DECK"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.coverings["deck"].area == pytest.approx(9)


def test_nested_invalid_outside_and_label_combined():
    """P1-1 + P1-2 + P1-3 together: open hatch, unlabeled plant and an outside plant inside a container."""
    doc = clean_doc()
    blk, _, named, _ = _container_block(doc)
    bad = blk.add_hatch(dxfattribs={"layer": "COV_DECK"})
    bad.paths.add_polyline_path(rect(5, 5, 8, 8), is_closed=False, flags=EXTERNAL)
    far = blk.add_blockref("Oak", (500, 0), dxfattribs={"layer": "PLANT"})
    named.add_attrib("SPECIES", "Verified oak", (2, 2))
    far.add_attrib("SPECIES", "Far oak", (500, 0))
    ins = doc.modelspace().add_blockref("GROUND_CONTAINER", (20, 70), dxfattribs={"layer": "0", "rotation": 90})
    pl = {"layers": ["PLANT"], "positions": {"Oak": "1"}, "label": "attrib:SPECIES"}
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config(planting=pl)))
    got = sorted((x.code, x.handle, x.ref) for x in res.findings if x.code != "overlapping_coverings")
    top_oak = next(e for e in doc.modelspace().query("INSERT") if e.dxf.name == "Oak")
    H = ins.dxf.handle
    assert got == sorted([
        ("open_contour", bad.dxf.handle, f"{H}>{bad.dxf.handle}"),
        ("label_missing", top_oak.dxf.handle, top_oak.dxf.handle),
        ("point_outside_boundary", far.dxf.handle, f"{H}>{far.dxf.handle}"),
    ])
    assert res.coverings["deck"].area == pytest.approx(4)
    assert sorted(str(p.label) for p in res.planting) == ["Far oak", "None", "Verified oak"]


def test_nested_cycle_and_depth_are_findings():
    doc = clean_doc()
    loop = doc.blocks.new("LOOP")
    loop.add_blockref("Oak", (1, 1), dxfattribs={"layer": "PLANT"})
    loop.add_blockref("LOOP", (1, 0), dxfattribs={"layer": "0"})
    doc.modelspace().add_blockref("LOOP", (20, 20), dxfattribs={"layer": "0"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert codes(res) == ["nested_cycle"]
    assert len(res.planting) == 2  # the plant of the first level is still read
    doc2 = clean_doc()
    prev = None
    for i in range(spozu.MAX_NESTING + 2):
        blk = doc2.blocks.new(f"L{i}")
        if prev is None:
            blk.add_blockref("Oak", (0, 0), dxfattribs={"layer": "PLANT"})
        else:
            blk.add_blockref(prev, (0, 0), dxfattribs={"layer": "0"})
        prev = f"L{i}"
    doc2.modelspace().add_blockref(prev, (20, 20), dxfattribs={"layer": "0"})
    res2 = read_spozu_dxf(doc2, SpozuConfig.from_dict(base_config()))
    assert codes(res2) == ["nesting_too_deep"] and len(res2.planting) == 1


def test_nested_polyline_that_cannot_be_transformed_is_a_finding():
    """Non-uniform scaling of a bulged covering polyline: reported, never exploded into lines silently."""
    doc = clean_doc()
    blk = doc.blocks.new("BULGE")
    pl = blk.add_lwpolyline([(0, 0, 0), (2, 0, 1), (2, 2, 0), (0, 2, 0)], format="xyb", close=True,
                            dxfattribs={"layer": "COV_DECK"})
    ins = doc.modelspace().add_blockref("BULGE", (5, 5), dxfattribs={"layer": "0", "xscale": 1, "yscale": 3})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(x.code, x.handle, x.ref) for x in res.findings] == [
        ("nested_unsupported", pl.dxf.handle, f"{ins.dxf.handle}>{pl.dxf.handle}")]
    assert res.coverings["deck"].area == 0


def test_nested_boundary_is_found_with_provenance():
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    blk = doc.blocks.new("PLOT")
    b = blk.add_lwpolyline(rect(0, 0, 10, 10), close=True, dxfattribs={"layer": "BOUNDARY"})
    ins = doc.modelspace().add_blockref("PLOT", (100, 0), dxfattribs={"layer": "0", "rotation": 90})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.findings == [] and res.boundary.area == pytest.approx(100)
    assert res.boundary_handle == f"{ins.dxf.handle}>{b.dxf.handle}"
    assert res.boundary.bounds == pytest.approx((90, 0, 100, 10))
    cfg = base_config(boundary={"layer": "BOUNDARY", "handle": f"{ins.dxf.handle}>{b.dxf.handle}"})
    assert read_spozu_dxf(doc, SpozuConfig.from_dict(cfg)).boundary.area == pytest.approx(100)


def test_minsert_expands_to_one_point_per_cell():
    doc = clean_doc()
    m = doc.modelspace().add_blockref("Oak", (10, 10), dxfattribs={"layer": "PLANT"})
    m.grid(size=(2, 3), spacing=(5, 4))  # rows x cols, row spacing, col spacing
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    grid = sorted((round(p.x, 6), round(p.y, 6)) for p in res.planting if p.handle == m.dxf.handle)
    assert grid == sorted((10 + 4 * c, 10 + 5 * r) for r in range(2) for c in range(3))
    assert len({p.ref for p in res.planting}) == len(res.planting)


@pytest.mark.parametrize("seed", range(40))
def test_probe_nested_instances_match_brute_force(seed):
    """Generated probe: random instances (rotation, uniform scale, mirror, 1-2 levels) of a container ->
    deck area = union of the transformed squares inside the plot, one plant per instance at the
    transformed WCS point, every outside plant flagged exactly once."""
    from shapely.geometry import box

    rng = random.Random(4100 + seed)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(rect(0, 0, 100, 100), close=True, dxfattribs={"layer": "BOUNDARY"})
    doc.blocks.new("Oak")
    blk = doc.blocks.new("C")
    h = blk.add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path(rect(0, 0, 1, 1), is_closed=True, flags=EXTERNAL)
    blk.add_blockref("Oak", (0.5, 0.5), dxfattribs={"layer": "PLANT"})
    wrap = doc.blocks.new("W")
    wrap.add_blockref("C", (0, 0), dxfattribs={"layer": "0"})
    exp_pts, polys = [], []
    for _ in range(rng.randint(1, 6)):
        x, y = rng.uniform(-10, 110), rng.uniform(-10, 110)
        rot, sc = rng.uniform(0, 360), rng.uniform(0.5, 3)
        mx = rng.choice([1, -1])
        msp.add_blockref(rng.choice(["C", "W"]), (x, y),
                         dxfattribs={"layer": "0", "rotation": rot, "xscale": sc * mx, "yscale": sc})
        a = math.radians(rot)

        def tf(px, py, a=a, sc=sc, mx=mx, x=x, y=y):
            px, py = px * sc * mx, py * sc
            return x + px * math.cos(a) - py * math.sin(a), y + px * math.sin(a) + py * math.cos(a)

        exp_pts.append(tf(0.5, 0.5))
        polys.append(Polygon([tf(*q) for q in rect(0, 0, 1, 1)]))
    plot = box(0, 0, 100, 100)
    exp_area = union_all([p.intersection(plot) for p in polys]).area
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.coverings["deck"].area == pytest.approx(exp_area, abs=1e-4)  # GRID snapping: <= perimeter * 1e-6
    got = sorted((p.x, p.y) for p in res.planting)
    exp = sorted(exp_pts)
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        assert g == pytest.approx(e, abs=1e-6)
    n_out = sum(not (0 <= px <= 100 and 0 <= py <= 100) for px, py in exp_pts)
    out = [f for f in res.findings if f.code == "point_outside_boundary"]
    assert len(out) == n_out and len({f.ref for f in out}) == n_out
    assert {f.code for f in res.findings} <= {"point_outside_boundary", "overlapping_coverings"}


# ---------------------------------------------------------------- review round 2 regressions (P1-1, P1-2)


def _affine(x, y, rot=0.0, sx=1.0, sy=1.0):
    """2D affine of an INSERT (scale, then rotate, then move) as (a, b, c, d, e, f): X = a*u + b*v + c."""
    r = math.radians(rot)
    co, si = math.cos(r), math.sin(r)
    return (co * sx, -si * sy, x, si * sx, co * sy, y)


def _compose(p, q):
    """p after q."""
    a, b, c, d, e, f = p
    A, B, C, D, E, F = q
    return (a * A + b * D, a * B + b * E, a * C + b * F + c, d * A + e * D, d * B + e * E, d * C + e * F + f)


def _apply(m, u, v):
    a, b, c, d, e, f = m
    return a * u + b * v + c, d * u + e * v + f


def _grid_cells(rows, cols, rsp, csp):
    return [(c * csp, r * rsp) for r in range(rows) for c in range(cols)]


def test_nested_minsert_cells_follow_parent_transform():
    """Round 2 P1-1 (reviewer input): a 2x3 Oak MINSERT inside a container scaled 2 and rotated 90."""
    doc = clean_doc()
    blk = doc.blocks.new("ARRAY_CONTAINER")
    m = blk.add_blockref("Oak", (1, 1), dxfattribs={"layer": "PLANT"})
    m.grid(size=(2, 3), spacing=(5, 4))
    ins = doc.modelspace().add_blockref("ARRAY_CONTAINER", (20, 20),
                                        dxfattribs={"layer": "0", "xscale": 2, "yscale": 2, "rotation": 90})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    got = sorted((p.x, p.y) for p in res.planting if p.container)
    exp = [(8, 22), (8, 30), (8, 38), (18, 22), (18, 30), (18, 38)]
    assert len(got) == 6
    for g, e in zip(got, exp):
        assert g == pytest.approx(e, abs=1e-6)
    refs = [p.ref for p in res.planting if p.container]
    assert len(set(refs)) == 6 and all(r.startswith(f"{ins.dxf.handle}>{m.dxf.handle}") for r in refs)
    assert res.findings == []


@pytest.mark.parametrize("parent", [(-2, 2, 35), (2, 3, 0), (-1, 1, 0), (2, 2, 90)])
def test_nested_minsert_controls_mirror_nonuniform(parent):
    """Reviewer controls: (xscale, yscale, rotation) of the parent; brute-force expected cells."""
    sx, sy, rot = parent
    doc = clean_doc()
    blk = doc.blocks.new("ARRAY_CONTAINER")
    m = blk.add_blockref("Oak", (1, 1), dxfattribs={"layer": "PLANT"})
    m.grid(size=(2, 3), spacing=(5, 4))
    doc.modelspace().add_blockref("ARRAY_CONTAINER", (20, 20),
                                  dxfattribs={"layer": "0", "xscale": sx, "yscale": sy, "rotation": rot})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    M = _affine(20, 20, rot, sx, sy)
    exp = sorted(_apply(M, 1 + u, 1 + v) for u, v in _grid_cells(2, 3, 5, 4))
    got = sorted((p.x, p.y) for p in res.planting if p.container)
    assert len(got) == 6
    for g, e in zip(got, exp):
        assert g == pytest.approx(e, abs=1e-6)
    n_out = sum(not (0 <= x <= 100 and 0 <= y <= 100) for x, y in exp)
    assert len([f for f in res.findings if f.code == "point_outside_boundary"]) == n_out
    assert {f.code for f in res.findings} <= {"point_outside_boundary"}


def test_nested_minsert_of_hatch_container_mirrored_outside_and_label():
    """Combined: mirrored parent holding a MINSERT of a hatch+plant container; one cell outside the
    plot, plants without the configured SPECIES attribute -> per-cell findings with unique refs."""
    doc = clean_doc()
    c = doc.blocks.new("CELL")
    h = c.add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path(rect(0, 0, 1, 1), is_closed=True, flags=EXTERNAL)
    c.add_blockref("Oak", (0.5, 0.5), dxfattribs={"layer": "PLANT"})
    arr = doc.blocks.new("ARR")
    g = arr.add_blockref("CELL", (0, 0), dxfattribs={"layer": "0"})
    g.grid(size=(1, 3), spacing=(3, 3))  # columns at u = 0, 3, 6
    ins = doc.modelspace().add_blockref("ARR", (5, 30), dxfattribs={"layer": "0", "xscale": -1, "yscale": 1})
    pl = {"layers": ["PLANT"], "positions": {"Oak": "1"}, "label": "attrib:SPECIES"}
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config(planting=pl)))
    nested = sorted((round(p.x, 6), round(p.y, 6)) for p in res.planting if p.container)
    assert nested == [(-1.5, 30.5), (1.5, 30.5), (4.5, 30.5)]
    out = [f for f in res.findings if f.code == "point_outside_boundary"]
    assert len(out) == 1 and out[0].ref.startswith(f"{ins.dxf.handle}>{g.dxf.handle}")
    lm = [f for f in res.findings if f.code == "label_missing"]
    assert len(lm) == 4 and len({f.ref for f in lm}) == 4  # 3 cells + the top-level Oak
    # mirrored cells cover x in [4,5], [1,2], [-2,-1]; the last one is outside the plot
    assert res.coverings["deck"].area == pytest.approx(2)
    assert len(res.coverings["deck"].sources) == 2


@pytest.mark.parametrize("seed", range(40))
def test_probe_nested_minsert_match_brute_force(seed):
    """Generated probe: point-symbol or hatch-container MINSERTs, 1 or 2 block levels below a parent
    with rotation, mirror and (one level) non-uniform scale -> every cell at the composed WCS point,
    deck area = union of composed cell squares in the plot, every outside cell flagged once."""
    from shapely.geometry import box

    rng = random.Random(9500 + seed)
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()
    msp.add_lwpolyline(rect(0, 0, 100, 100), close=True, dxfattribs={"layer": "BOUNDARY"})
    doc.blocks.new("Oak")
    cell = doc.blocks.new("CELL")
    h = cell.add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path(rect(0, 0, 1, 1), is_closed=True, flags=EXTERNAL)
    cell.add_blockref("Oak", (0.5, 0.5), dxfattribs={"layer": "PLANT"})
    exp_pts, polys = [], []
    for i in range(rng.randint(1, 4)):
        what = rng.choice(["Oak", "CELL"])
        rows, cols = rng.randint(1, 3), rng.randint(1, 3)
        rsp, csp = rng.uniform(1.5, 4), rng.uniform(1.5, 4)
        ox, oy = rng.uniform(-3, 3), rng.uniform(-3, 3)
        two = rng.random() < 0.5
        child_rot = rng.uniform(0, 360) if two else 0.0
        arr = doc.blocks.new(f"A{i}")
        mi = arr.add_blockref(what, (ox, oy), dxfattribs={"layer": "PLANT" if what == "Oak" else "0",
                                                          "rotation": child_rot})
        if rows * cols > 1:
            mi.grid(size=(rows, cols), spacing=(rsp, csp))
        top_name, inner = f"A{i}", _affine(ox, oy, child_rot)
        if two:
            wx, wy, wr, ws = rng.uniform(-2, 2), rng.uniform(-2, 2), rng.uniform(0, 360), rng.uniform(0.5, 2)
            w = doc.blocks.new(f"W{i}")
            w.add_blockref(f"A{i}", (wx, wy), dxfattribs={"layer": "0", "rotation": wr, "xscale": ws, "yscale": ws})
            top_name, inner = f"W{i}", _compose(_affine(wx, wy, wr, ws, ws), inner)
        x, y, rot = rng.uniform(-10, 110), rng.uniform(-10, 110), rng.uniform(0, 360)
        mx = rng.choice([1, -1])
        if two:  # a rotated child below a non-uniform parent is a shear: uniform parent only
            sx = sy = rng.uniform(0.5, 2.5)
        else:
            sx, sy = rng.uniform(0.5, 2.5), rng.uniform(0.5, 2.5)
            rot = rng.choice([rot, 0.0])
        msp.add_blockref(top_name, (x, y), dxfattribs={"layer": "0", "rotation": rot, "xscale": sx * mx, "yscale": sy})
        M = _compose(_affine(x, y, rot, sx * mx, sy), inner)
        for u, v in _grid_cells(rows, cols, rsp, csp):
            if what == "Oak":
                exp_pts.append(_apply(M, u, v))
            else:
                exp_pts.append(_apply(M, u + 0.5, v + 0.5))
                polys.append(Polygon([_apply(M, u + p, v + q) for p, q in rect(0, 0, 1, 1)]))
    plot = box(0, 0, 100, 100)
    exp_area = union_all([p.intersection(plot) for p in polys]).area if polys else 0.0
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert res.coverings["deck"].area == pytest.approx(exp_area, abs=1e-4)
    got = sorted((p.x, p.y) for p in res.planting)
    exp = sorted(exp_pts)
    assert len(got) == len(exp)
    for g, e in zip(got, exp):
        assert g == pytest.approx(e, abs=1e-6)
    assert len({p.ref for p in res.planting}) == len(res.planting)
    n_out = sum(not (0 <= px <= 100 and 0 <= py <= 100) for px, py in exp_pts)
    out = [f for f in res.findings if f.code == "point_outside_boundary"]
    assert len(out) == n_out and len({f.ref for f in out}) == n_out
    assert {f.code for f in res.findings} <= {"point_outside_boundary", "overlapping_coverings"}


def _unknown_block(doc, name="UNKNOWN_CONTENT", layer="NEW_COVERING"):
    blk = doc.blocks.new(name)
    h = blk.add_hatch(dxfattribs={"layer": layer})
    h.paths.add_polyline_path(rect(0, 0, 2, 2), is_closed=True, flags=EXTERNAL)
    return blk, h


@pytest.mark.parametrize("depth", [1, 2])
def test_nested_unmapped_layer_is_a_finding(depth):
    """Round 2 P1-2 (reviewer input): NEW_COVERING hatch in a block inserted on ignored layer 0."""
    doc = clean_doc()
    _, h = _unknown_block(doc)
    name = "UNKNOWN_CONTENT"
    path = []
    if depth == 2:
        w = doc.blocks.new("WRAP")
        path.append(w.add_blockref(name, (0, 0), dxfattribs={"layer": "0"}).dxf.handle)
        name = "WRAP"
    ins = doc.modelspace().add_blockref(name, (10, 10), dxfattribs={"layer": "0"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(f.code, f.layer) for f in res.findings] == [("unmapped_layer", "NEW_COVERING")]
    f = res.findings[0]
    assert f.ref == ">".join([ins.dxf.handle, *path, h.dxf.handle]) and f.handle == h.dxf.handle
    assert "1 entities" in f.detail and "1 in blocks" in f.detail
    assert [round(c.area, 6) for c in res.coverings.values()] == [5600, 4400, 0]  # no covering guessed for NEW_COVERING


def test_nested_unmapped_layer_repeated_ignored_atomic_and_mixed():
    """Repeated instances -> one finding with the count; ignored-layer and atomic-symbol content is not
    reported; a mixed container keeps its valid covering and reports only the unknown layer."""
    doc = clean_doc()
    msp = doc.modelspace()
    blk, h = _unknown_block(doc)
    d = blk.add_hatch(dxfattribs={"layer": "COV_DECK"})
    d.paths.add_polyline_path(rect(0, 0, 1, 1), is_closed=True, flags=EXTERNAL)
    blk.add_line((0, 0), (1, 1), dxfattribs={"layer": "Defpoints"})  # ignored layer
    doc.blocks.get("Oak").add_circle((0, 0), 0.2, dxfattribs={"layer": "SYMBOL_GRAPHICS"})  # atomic symbol
    blk.add_blockref("Oak", (1.5, 1.5), dxfattribs={"layer": "PLANT"})
    for x in (10, 20, 30):
        msp.add_blockref("UNKNOWN_CONTENT", (x, 10), dxfattribs={"layer": "0"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    un = [f for f in res.findings if f.code == "unmapped_layer"]
    assert [(f.layer, f.handle) for f in un] == [("NEW_COVERING", h.dxf.handle)]
    assert "3 entities" in un[0].detail and "3 in blocks" in un[0].detail
    assert res.coverings["deck"].area == pytest.approx(3)
    assert len(res.planting) == 4
    assert {f.code for f in res.findings} == {"unmapped_layer", "overlapping_coverings"}


def test_nested_layer_zero_content_inherits_unmapped_insert_layer():
    """Layer-0 block content on an unmapped insert layer counts under that layer (model space + nested)."""
    doc = clean_doc()
    blk = doc.blocks.new("ZERO")
    blk.add_line((0, 0), (1, 1), dxfattribs={"layer": "0"})
    w = doc.blocks.new("ZWRAP")
    w.add_blockref("ZERO", (0, 0), dxfattribs={"layer": "0"})
    doc.modelspace().add_blockref("ZWRAP", (5, 5), dxfattribs={"layer": "MYSTERY"})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(f.code, f.layer) for f in res.findings] == [("unmapped_layer", "MYSTERY")]
    assert "3 entities (1 model-space, 2 in blocks)" in res.findings[0].detail


def test_nested_untransformable_content_on_unknown_layer_is_unmapped():
    doc = clean_doc()
    blk = doc.blocks.new("BULGE_UNKNOWN")
    pl = blk.add_lwpolyline([(0, 0, 0), (2, 0, 1), (2, 2, 0), (0, 2, 0)], format="xyb", close=True,
                            dxfattribs={"layer": "NEW_COVERING"})
    ins = doc.modelspace().add_blockref("BULGE_UNKNOWN", (5, 5), dxfattribs={"layer": "0", "yscale": 3})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert [(f.code, f.layer, f.ref) for f in res.findings] == [
        ("unmapped_layer", "NEW_COVERING", f"{ins.dxf.handle}>{pl.dxf.handle}")]


# ---------------------------------------------------------------- #295: contours and make_valid repair


def test_elevation_contours_give_vertices_with_polyline_z():
    doc = clean_doc()
    vp = doc.blocks.new("VPC")
    c = vp.add_lwpolyline([(10, 10), (50, 10), (90, 30)], dxfattribs={"layer": "CONTOUR", "elevation": 145.3})
    msp = doc.modelspace()
    msp.add_blockref("VPC", (0, 0), dxfattribs={"layer": "VP_CONTAINER"})
    cfg = base_config(elevations={"layers": ["SPOT"], "containers": ["VP_CONTAINER"], "value": "text",
                                  "contour_layers": ["CONTOUR"]})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(cfg))
    cont = [e for e in res.elevations if e.source == "contour"]
    assert sorted((e.x, e.y) for e in cont) == [(10, 10), (50, 10), (90, 30)]
    assert {e.z for e in cont} == {145.3}
    assert all(e.handle == c.dxf.handle for e in cont)
    assert res.summary()["elevations"]["contours"] == 1
    assert [e.source for e in res.elevations].count("point") == 2
    assert "unmapped_layer" not in codes(res)


def test_contours_not_read_without_config():
    doc = clean_doc()
    doc.modelspace().add_lwpolyline([(10, 10), (50, 10)], dxfattribs={"layer": "CONTOUR", "elevation": 145.3})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(base_config()))
    assert all(e.source == "point" for e in res.elevations)


def test_contour_layer_mapped_twice_is_config_error():
    cfg = base_config(elevations={"layers": ["SPOT"], "contour_layers": ["SPOT"]})
    with pytest.raises(SpozuConfigError):
        SpozuConfig.from_dict(cfg)


def test_3d_polyline_contour_with_varying_z_is_a_finding():
    doc = clean_doc()
    doc.modelspace().add_polyline3d([(10, 10, 1), (20, 10, 2)], dxfattribs={"layer": "CONTOUR"})
    cfg = base_config(elevations={"layers": ["SPOT"], "containers": ["VP_CONTAINER"], "contour_layers": ["CONTOUR"]})
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(cfg))
    assert "elevation_unparsed" in codes(res)
    assert all(e.source == "point" for e in res.elevations)


def test_self_intersecting_hatch_repaired_with_make_valid_when_configured():
    doc = clean_doc()
    h = doc.modelspace().add_hatch(dxfattribs={"layer": "COV_DECK"})
    h.paths.add_polyline_path([(5, 65), (15, 75), (15, 65), (5, 75)], is_closed=True, flags=EXTERNAL)
    cfg = base_config()
    cfg["coverings"][2]["repair"] = "make_valid"
    res = read_spozu_dxf(doc, SpozuConfig.from_dict(cfg))
    rep = [x for x in res.findings if x.code == "repaired_contour"]
    assert [x.handle for x in rep] == [h.dxf.handle]
    assert "self_intersecting_contour" not in codes(res)  # the deck lies on the lawn: overlap stays a finding
    assert res.coverings["deck"].area == pytest.approx(50.0)  # bow-tie: two triangles of 25 m2
    assert rep[0].area == pytest.approx(50.0)


def test_unknown_repair_mode_is_config_error():
    cfg = base_config()
    cfg["coverings"][2]["repair"] = "buffer0"
    with pytest.raises(SpozuConfigError):
        SpozuConfig.from_dict(cfg)
