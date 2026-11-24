"""#1838 Ground DXF relief: placed-block coordinates are explicit (``insert_chain`` / ``definition_only``).

Pattern: n/a | new-case: tests/test_ground_relief_placement_1838.py - placed-block relief placement regressions.

Synthetic DXFs only: a RELIEF block (planning-mark INSERTs + a 3D design-contour polyline) placed by
model-space INSERTs. The analytic oracle is the covers-path convention
``model = insert + R(angle) * (sx*x, sy*y)``, ``z' = iz + sz*z`` with block base point (0, 0, 0).
"""
import math
from pathlib import Path

import pytest
import ezdxf

from dt_ai.geometry import ground_site as gs

ROOT = Path(__file__).resolve().parents[1]
MARKS = [(0.0, 0.0, 10.0), (10.0, 0.0, 12.0), (0.0, 10.0, 11.0)]
CONTOUR = [(2.0, 2.0, 5.0), (8.0, 2.0, 5.0), (8.0, 8.0, 5.0)]
LOCAL = [*MARKS, *CONTOUR]
RELIEF_SPEC = {"block": "RELIEF", "insert_names": ["MARK"], "contour_layers": ["CONT"]}


def relief_doc(placements):
    """A DXF with a RELIEF block placed by the given model-space ``(insert_xy, attribs)`` INSERTs."""
    doc = ezdxf.new()
    block = doc.blocks.new("RELIEF", base_point=(0.0, 0.0, 0.0))
    for x, y, z in MARKS:
        block.add_blockref("MARK", (x, y, z))
    block.add_polyline3d(CONTOUR, dxfattribs={"layer": "CONT"})
    handles = []
    for xy, kw in placements:
        handles.append(doc.modelspace().add_blockref("RELIEF", xy, dxfattribs=kw).dxf.handle)
    return doc, handles


def expected(ix=0.0, iy=0.0, iz=0.0, sx=1.0, sy=1.0, sz=1.0, angle=0.0):
    a = math.radians(angle)
    return [(ix + sx * x * math.cos(a) - sy * y * math.sin(a),
             iy + sx * x * math.sin(a) + sy * y * math.cos(a),
             iz + sz * z) for x, y, z in LOCAL]


def assert_points_close(actual, expected_):
    assert len(actual) == len(expected_), (len(actual), len(expected_))
    for pa, pe in zip(sorted(actual), sorted(expected_)):
        assert pa == pytest.approx(pe, rel=1e-9, abs=1e-9), (pa, pe)


def test_modelspace_behaviour_unchanged():
    doc = ezdxf.new()
    msp = doc.modelspace()
    for x, y, z in MARKS:
        msp.add_blockref("MARK", (x, y, z))
    msp.add_polyline3d(CONTOUR, dxfattribs={"layer": "CONT"})
    pts = gs.relief_from_dxf(doc, {"insert_names": ["MARK"], "contour_layers": ["CONT"]})
    assert_points_close(pts, LOCAL)


def test_identity_placement_equals_local_coordinates():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {})])
    placed = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})
    local = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "definition_only": True})
    assert_points_close(placed, local)


def test_placed_block_translation():
    doc, handles = relief_doc([((100.0, 200.0, 0.0), {})])
    pts = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})
    assert_points_close(pts, expected(100.0, 200.0))


@pytest.mark.parametrize("sx,sy,angle", [(2, 2, 90), (-2, 2, 30), (3, -3, -45), (0.5, 0.5, 180)])
def test_placed_block_rotation_scale_reflection(sx, sy, angle):
    doc, handles = relief_doc([((10.0, 20.0, 0.0), {"xscale": sx, "yscale": sy, "rotation": angle})])
    pts = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})
    assert_points_close(pts, expected(10.0, 20.0, sx=sx, sy=sy, angle=angle))


def test_generated_similarity_marks_and_contours():
    """Probe: 5 scales x 13 angles x 2 reflections against the independent analytic oracle."""
    cases = 0
    for scale in [0.125, 0.5, 1.0, 3.0, 16.0]:
        for angle in range(-180, 181, 30):
            for mirror in (-1, 1):
                doc, handles = relief_doc(
                    [((7.0, -3.0, 0.0), {"xscale": mirror * scale, "yscale": scale, "rotation": angle})])
                pts = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})
                assert_points_close(pts, expected(7.0, -3.0, sx=mirror * scale, sy=scale, angle=angle))
                cases += 1
    assert cases == 5 * 13 * 2


def test_definition_only_reads_local_despite_placement():
    doc, _ = relief_doc([((100.0, 200.0, 0.0), {"xscale": 2, "yscale": 2, "rotation": 90})])
    pts = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "definition_only": True})
    assert_points_close(pts, LOCAL)


def test_block_without_selector_and_two_inserts_refuses_listing_handles():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {}), ((50.0, 50.0, 0.0), {})])
    with pytest.raises(ValueError, match="placement must be explicit") as exc:
        gs.relief_from_dxf(doc, dict(RELIEF_SPEC))
    assert handles[0] in str(exc.value) and handles[1] in str(exc.value)


def test_block_without_selector_and_one_insert_still_refuses():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {})])
    with pytest.raises(ValueError, match="placement must be explicit"):
        gs.relief_from_dxf(doc, dict(RELIEF_SPEC))


def test_block_never_placed_refuses():
    doc, _ = relief_doc([])
    with pytest.raises(ValueError, match="not placed in model space"):
        gs.relief_from_dxf(doc, dict(RELIEF_SPEC))


def test_insert_chain_without_block_refuses():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {})])
    with pytest.raises(ValueError, match="need a block"):
        gs.relief_from_dxf(doc, {"insert_names": ["MARK"], "insert_chain": [handles[0]]})


def test_definition_only_and_chain_mutually_exclusive():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {})])
    with pytest.raises(ValueError, match="mutually exclusive"):
        gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]], "definition_only": True})


def test_definition_only_not_bool_refused():
    doc, _ = relief_doc([((0.0, 0.0, 0.0), {})])
    with pytest.raises(ValueError, match="definition_only"):
        gs.relief_from_dxf(doc, {**RELIEF_SPEC, "definition_only": "yes"})


def test_nested_insert_chain_composed():
    doc = ezdxf.new()
    relief = doc.blocks.new("RELIEF", base_point=(0.0, 0.0, 0.0))
    for x, y, z in MARKS:
        relief.add_blockref("MARK", (x, y, z))
    relief.add_polyline3d(CONTOUR, dxfattribs={"layer": "CONT"})
    parent = doc.blocks.new("PARENT", base_point=(0.0, 0.0, 0.0))
    inner = parent.add_blockref("RELIEF", (10.0, 20.0, 0.0), dxfattribs={"rotation": 90})
    outer = doc.modelspace().add_blockref("PARENT", (100.0, 200.0, 0.0),
                                          dxfattribs={"xscale": 2, "yscale": 2, "rotation": 90})
    pts = gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [outer.dxf.handle, inner.dxf.handle]})
    # inner: (x,y,z) -> (10 - y, 20 + x, z); outer: (X,Y,Z) -> (100 - 2Y, 200 + 2X, Z)
    assert_points_close(pts, [(60.0 - 2.0 * x, 220.0 - 2.0 * y, z) for x, y, z in LOCAL])


def test_unsupported_non_uniform_scale_refused():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {"xscale": 2, "yscale": 3})])
    with pytest.raises(ValueError, match="non-uniform XY scale"):
        gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})


def test_non_finite_insert_refused():
    doc, handles = relief_doc([((0.0, 0.0, 0.0), {})])
    ins = doc.entitydb[handles[0]]
    ins.dxf.insert = (float("nan"), 0.0, 0.0)
    with pytest.raises(ValueError, match="INSERT"):
        gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [handles[0]]})


def test_chain_not_placing_the_block_refused():
    doc, _ = relief_doc([((0.0, 0.0, 0.0), {})])
    # a chain whose last INSERT references a different block cannot place RELIEF
    doc.blocks.new("OTHER", base_point=(0.0, 0.0, 0.0))
    other = doc.modelspace().add_blockref("OTHER", (0.0, 0.0, 0.0))
    with pytest.raises(ValueError, match="does not place"):
        gs.relief_from_dxf(doc, {**RELIEF_SPEC, "insert_chain": [other.dxf.handle]})


def test_relief_fewer_than_three_points_refuses():
    doc = ezdxf.new()
    doc.modelspace().add_blockref("MARK", (0.0, 0.0, 10.0))
    with pytest.raises(ValueError, match="relief: 1 points found"):
        gs.relief_from_dxf(doc, {"insert_names": ["MARK"]})


def test_relief_non_finite_source_point_refused():
    doc = ezdxf.new()
    doc.modelspace().add_blockref("MARK", (0.0, 0.0, 10.0))
    doc.modelspace().add_blockref("MARK", (10.0, 0.0, float("nan")))
    doc.modelspace().add_blockref("MARK", (0.0, 10.0, 11.0))
    with pytest.raises(ValueError, match="non-finite"):
        gs.relief_from_dxf(doc, {"insert_names": ["MARK"]})


def test_cli_placed_block_relief_fresh_process(tmp_path):
    """Fresh-process `dt ground site` accepts ``insert_chain`` and extracts every placed mark + contour point."""
    import json
    import subprocess
    import sys

    def plane(x, y):
        return 100.0 + 0.05 * x - 0.03 * y

    grid = [(x, y, plane(x, y)) for x in (-1.0, 7.0, 14.0, 21.0) for y in (-1.0, 7.0, 14.0, 21.0)]
    doc = ezdxf.new()
    msp = doc.modelspace()
    b = msp.add_lwpolyline([(0, 0), (20, 0), (20, 20), (0, 20)], close=True)
    lawn = msp.add_hatch(color=3)
    lawn.paths.add_polyline_path([(0, 0), (20, 0), (20, 20), (0, 20)], is_closed=True)
    lawn.bgcolor = (96, 150, 64)
    rub = msp.add_hatch(color=253)
    rub.paths.add_polyline_path([(5, 5), (10, 5), (10, 10), (5, 10)], is_closed=True)
    rub.bgcolor = (246, 115, 44)
    blk = doc.blocks.new("RELIEF", base_point=(0.0, 0.0, 0.0))
    for x, y, z in grid:
        blk.add_blockref("MARK", (x, y, z))
    contour = [(2.0, 2.0, plane(2.0, 2.0)), (8.0, 2.0, plane(8.0, 2.0)), (8.0, 8.0, plane(8.0, 8.0))]
    blk.add_polyline3d(contour, dxfattribs={"layer": "CONT"})
    ins = msp.add_blockref("RELIEF", (0.0, 0.0, 0.0))  # identity placement
    dxf = tmp_path / "site.dxf"
    doc.saveas(dxf)
    spec = {
        "site": "SYN", "dxf": {"path": str(dxf), "sha256": gs.sha256(dxf)},
        "boundary": {"handle": b.dxf.handle},
        "zero": {"project_zero_m": 100.0, "source": "synthetic"}, "base_id": 1,
        "covers": [{"id": 1, "name": "Lawn", "hatches": [lawn.dxf.handle]},
                   {"id": 2, "name": "Rubber", "hatches": [rub.dxf.handle]}],
        "relief": {"block": "RELIEF", "insert_names": ["MARK"], "contour_layers": ["CONT"],
                   "insert_chain": [ins.dxf.handle]},
        "params": {"origin_xy": [0, 0], "cell": 4.0, "chord": 0.02},
    }
    p = tmp_path / "spec.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools/ground/build_ground_site.py"),
                        str(p), str(tmp_path / "out")], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    rep = json.loads((tmp_path / "out/ground-report.json").read_text(encoding="utf-8"))
    assert rep["geometry_status"] == "built"
    assert rep["stages"]["sources"]["relief_points"] == len(grid) + len(contour)
