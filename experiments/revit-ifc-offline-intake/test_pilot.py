"""Round-trip, mutation and comparator tests for the synthetic IFC pilot."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import ifcopenshell
import pytest

_loaded = importlib.util.spec_from_file_location("pilot", Path(__file__).with_name("pilot.py"))
pilot = importlib.util.module_from_spec(_loaded)
_loaded.loader.exec_module(pilot)
Spec = pilot.Spec
TOL = {
    "spec_compare": {"level_elev_m": 0.03, "contour_area_rel": 0.02,
                     "contour_hausdorff_m": 0.05, "opening_bbox_m": 0.05},
    "verdict": {"enabled": True},
}

def _generate(tmp_path, prefix, name):
    spec = Spec.model_validate(pilot.mini_spec())
    path = tmp_path / name
    pilot.generate(spec, prefix, path)
    return spec, path

def _save(path, edit):
    handle = ifcopenshell.open(str(path))
    edit(handle)
    handle.write(str(path))
    return path

def _shift(point, dx=0.0, dz=0.0):
    x, y, z = (float(c) for c in point.Coordinates)
    point.Coordinates = (x + dx, y, z + dz)

def _compared(spec, extracted):
    payload = extracted.model_dump(mode="json")
    return pilot.compare_specs(spec.model_dump(mode="json"), payload, {}, {}, TOL)

@pytest.mark.parametrize("prefix", [None, "MILLI"], ids=["m", "mm"])
def test_roundtrip_counts_contour_openings_and_origin(tmp_path, prefix):
    spec, path = _generate(tmp_path, prefix, "round.ifc")
    extracted, report = pilot.extract(path)
    assert report["counts"] == pilot.expect_counts(spec)
    left, right = spec.model_dump(mode="json"), extracted.model_dump(mode="json")
    assert _compared(spec, extracted)["failing"] == []
    keys = ("wall", "x_m", "sill_m", "w_m", "h_m")
    for got, exp in zip(right["floors"], left["floors"], strict=True):
        assert pilot.np.allclose(got["contour"], exp["contour"], rtol=0.0, atol=1e-10)
        for actual, expected in zip(got["openings"], exp["openings"], strict=True):
            assert tuple(actual[k] for k in keys) == pytest.approx(tuple(expected[k] for k in keys), abs=1e-10)
    scale = 1000.0 if prefix == "MILLI" else 1.0
    raw = [c * scale for c in pilot.SHIFT_M] + [1.0]
    mapped = pilot.np.asarray(extracted.frame.to_object, dtype=float) @ pilot.np.array(raw, dtype=float)
    assert pilot.np.allclose(mapped[:3], 0.0, atol=1e-6)

def test_raw_storey_elevation_ignored(tmp_path):
    spec, path = _generate(tmp_path, None, "elev.ifc")
    _save(path, lambda handle: [setattr(row, "Elevation", 9999.0) for row in handle.by_type("IfcBuildingStorey")])
    extracted, _report = pilot.extract(path)
    assert _compared(spec, extracted)["failing"] == []
    assert [level.elev_m for level in extracted.levels] == pytest.approx([0.0, 3.0, 6.0])

def test_storey_placement_z_fails_level(tmp_path):
    spec, path = _generate(tmp_path, None, "storey-z.ifc")

    def edit(handle):
        storey = next(row for row in handle.by_type("IfcBuildingStorey") if row.Name == "L1")
        _shift(storey.ObjectPlacement.RelativePlacement.Location, dz=0.031)

    result = _compared(spec, pilot.extract(_save(path, edit))[0])
    assert pilot.row_of(result, "level elevation, m", "L1")["within"] is False

def test_opening_relative_x_fails_bbox(tmp_path):
    spec, path = _generate(tmp_path, None, "opening-x.ifc")

    def edit(handle):
        opening = handle.by_type("IfcOpeningElement")[0]
        _shift(opening.ObjectPlacement.RelativePlacement.Location, dx=0.051)

    result = _compared(spec, pilot.extract(_save(path, edit))[0])
    row = pilot.row_of(result, "opening pairs within bbox tolerance, m (worst pair)", "L0")
    assert row["within"] is False

def _slab_solid(handle):
    return handle.by_type("IfcSlab")[0].Representation.Representations[0].Items[0]

@pytest.mark.parametrize("kind", ["units", "slab", "voids", "names", "direction", "tilt"])
def test_broken_ifc_raises_intake_error(tmp_path, kind):
    _spec, path = _generate(tmp_path, None, f"{kind}.ifc")
    handle = ifcopenshell.open(str(path))
    if kind == "units":
        for unit in list(handle.by_type("IfcSIUnit")):
            if unit.UnitType == "LENGTHUNIT":
                handle.remove(unit)
        handle.by_type("IfcProject")[0].UnitsInContext = None
    elif kind == "slab":
        handle.by_type("IfcSlab")[0].Representation = None
    elif kind == "voids":
        for rel in list(handle.by_type("IfcRelVoidsElement")):
            handle.remove(rel)
    elif kind == "names":
        named = [w for w in handle.by_type("IfcWall") if w.Name in ("W0000", "W0001")]
        named[0].Name, named[1].Name = named[1].Name, named[0].Name
    elif kind == "direction":
        _slab_solid(handle).ExtrudedDirection.DirectionRatios = (1.0, 0.0, 0.0)
    else:
        _slab_solid(handle).Position.Axis.DirectionRatios = (0.0, 1.0, 0.0)
    handle.write(str(path))
    with pytest.raises(pilot.IntakeError):
        pilot.extract(path)

def _moved(index, axis, delta, also=None):
    base, other = pilot.mini_spec(), pilot.mini_spec()
    ring = [list(point) for point in other["floors"][0]["contour"]]
    ring[index][axis] += delta
    if also is not None:
        ring[also][axis] += delta
    other["floors"][0]["contour"] = ring
    return pilot.compare_specs(base, Spec.model_validate(other).model_dump(mode="json"), {}, {}, TOL)

def test_contour_area_and_hausdorff_margins():
    inside = _moved(2, 1, 8.0 * (0.02 - 1e-6), also=3)
    outside = _moved(2, 1, 8.0 * (0.02 + 1e-4), also=3)
    assert pilot.row_of(inside, "contour area, m2 (relative)", "L0")["within"] is True
    assert pilot.row_of(outside, "contour area, m2 (relative)", "L0")["within"] is False
    near = _moved(2, 0, 0.05 - 1e-6)
    far = _moved(2, 0, 0.05 + 1e-4)
    assert pilot.row_of(near, "contour Hausdorff, m", "L0")["within"] is True
    assert pilot.row_of(far, "contour Hausdorff, m", "L0")["within"] is False

def test_negative_returns_nine_booleans(tmp_path):
    flags = [value for value in pilot.negative(tmp_path, TOL).values() if isinstance(value, bool)]
    assert len(flags) == 9 and all(flags)
