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
    assert res.boundary is not None and res.boundary.area == pytest.approx(25854.04, abs=0.1)
    assert res.base_covering == "tile_light"
    assert sum(p.inside for p in res.planting) > 4000
