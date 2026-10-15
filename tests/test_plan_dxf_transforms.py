"""Transformed straight-plan DXF regression. The oracle parses spec JSON itself."""

from __future__ import annotations

import json
import math
import shutil
from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from dt_ai.cad.plan_dxf import (
    PlanTransform,
    audit_plan_dxf,
    build_plan_features,
    census,
    compare_plan,
    read_plan_dxf,
    spec_from_mapping,
    write_plan_dxf,
)

BENCH = Path(__file__).resolve().parents[1] / "benchmark"
NAMES = ("bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace")
ORDER = ("identity", "rotation37", "translation", "rotation37_then_translation")
SHIFT_M = (Decimal(600000), Decimal(7500000), Decimal(150))
PI = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164")
_TRIG = None


def _d(value):
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _series(angle, cosine):
    with localcontext() as ctx:
        ctx.prec = 50
        term = Decimal(1) if cosine else angle
        total = term
        k = 0 if cosine else 1
        for _ in range(80):
            term = -term * angle * angle / (Decimal(k + 1) * Decimal(k + 2))
            k += 2
            total += term
        return total


def trig37():
    global _TRIG
    if _TRIG is None:
        with localcontext() as ctx:
            ctx.prec = 50
            angle = Decimal(37) * PI / Decimal(180)
            _TRIG = (_series(angle, True), _series(angle, False))
    return _TRIG


def transform_metres(x, y, z, name):
    rotate = name in ("rotation37", "rotation37_then_translation")
    shift = name in ("translation", "rotation37_then_translation")
    with localcontext() as ctx:
        ctx.prec = 50
        x, y, z = _d(x), _d(y), _d(z)
        if rotate:
            cos_a, sin_a = trig37()
            x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a
        if shift:
            x, y, z = x + SHIFT_M[0], y + SHIFT_M[1], z + SHIFT_M[2]
        return x, y, z


def expand_floors(raw):
    names = [item["name"] for item in raw["levels"]]
    full = {item["level"]: item for item in raw["floors"] if item.get("contour") is not None}
    floors = []
    for item in raw["floors"]:
        if item.get("contour") is not None:
            floors.append(item)
            continue
        first = names.index(item["level"])
        last = names.index(item.get("repeat_to") or item["level"])
        template = full[item["typical_of"]]
        for index in range(first, last + 1):
            floors.append({
                "level": names[index],
                "contour": template["contour"],
                "openings": template.get("openings") or [],
            })
    return floors


def _ring(contour, level):
    points = []
    for point in contour:
        if len(point) < 2 or isinstance(point[0], dict) or isinstance(point[1], dict):
            raise ValueError(f"floor {level}: contour point must be [x, y] in metres")
        points.append((_d(point[0]), _d(point[1])))
    return points


def _opening(contour, opening, elev):
    wall = int(opening["wall"])
    x0, y0 = contour[wall]
    x1, y1 = contour[(wall + 1) % len(contour)]
    dx, dy = x1 - x0, y1 - y0
    with localcontext() as ctx:
        ctx.prec = 50
        length = (dx * dx + dy * dy).sqrt()
        if length == 0:
            raise ValueError("opening wall has zero length")
        ux, uy = dx / length, dy / length
        start, width = _d(opening["x_m"]), _d(opening["w_m"])
        z0 = elev + _d(opening["sill_m"])
        z1 = z0 + _d(opening["h_m"])
        ax, ay = x0 + ux * start, y0 + uy * start
        bx, by = x0 + ux * (start + width), y0 + uy * (start + width)
    return [(ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1)]


def oracle_features(raws, name):
    features = []
    for raw in raws:
        prefix = (raw["id"].split("-")[1] if "-" in raw["id"] else raw["id"]).upper()
        elevation = {item["name"]: _d(item["elev_m"]) for item in raw["levels"]}
        for floor in expand_floors(raw):
            ring = _ring(floor["contour"], floor["level"])
            z = elevation[floor["level"]]
            features.append(_oracle_feature(
                f"{prefix}_{floor['level']}_CONTOUR", "LWPOLYLINE", True,
                [(x, y, z) for x, y in ring], name))
            for index, opening in enumerate(floor.get("openings") or []):
                features.append(_oracle_feature(
                    f"{prefix}_{floor['level']}_OPEN_{index}", "POLYLINE", True,
                    _opening(ring, opening, z), name))
        for level in raw["levels"]:
            features.append(_oracle_feature(
                f"{prefix}_{level['name']}_LEVEL", "POINT", False,
                [(Decimal(0), Decimal(0), elevation[level["name"]])], name))
    return features


def _oracle_feature(layer, kind, closed, metres, name):
    vertices = []
    for x, y, z in metres:
        x, y, z = transform_metres(x, y, z, name)
        vertices.append([float(x * 1000), float(y * 1000), float(z * 1000)])
    return {"layer": layer, "kind": kind, "closed": closed, "vertices_mm": vertices}


def _transform(name):
    rotation = 37.0 if "rotation37" in name else 0.0
    shift = (600000.0, 7500000.0, 150.0) if "translation" in name else (0.0, 0.0, 0.0)
    return PlanTransform(rotation_deg=rotation, shift_m=shift)


@pytest.fixture
def plans(tmp_path):
    raws, specs = [], []
    folder = tmp_path / "inputs"
    for name in NAMES:
        target = folder / name
        target.mkdir(parents=True)
        shutil.copy2(BENCH / name / "spec.json", target / "spec.json")
        text = (target / "spec.json").read_text(encoding="utf-8")
        raws.append(json.loads(text, parse_float=Decimal))
        specs.append(spec_from_mapping(json.loads(text)))
    return specs, raws


def test_oracle_census_is_21_entities_69_coordinates(plans):
    _specs, raws = plans
    for name in ORDER:
        found = census(oracle_features(raws, name))
        assert found["entities"] == 21
        assert found["coordinates"] == 69
        assert found["LWPOLYLINE"] == 6
        assert found["POLYLINE"] == 6
        assert found["POINT"] == 9
        assert found["layers"] == 21


@pytest.mark.parametrize("name", ORDER, ids=ORDER)
def test_transformed_round_trip_within_0_01_mm(name, plans, tmp_path):
    specs, raws = plans
    written = build_plan_features(specs, _transform(name))
    path = tmp_path / f"{name}.dxf"
    write_plan_dxf(written, path)
    actual, info = read_plan_dxf(path)
    report = compare_plan(oracle_features(raws, name), actual, info["insunits"])
    found = census(actual)
    audited = audit_plan_dxf(path)
    assert report["ok"] is True
    assert found["entities"] == 21 and found["coordinates"] == 69
    assert all(item["raw_flag"] == {"LWPOLYLINE": 1, "POLYLINE": 9, "POINT": None}[item["kind"]] for item in actual)
    assert info["insunits"] == 4
    assert report["max_deviation_mm"] <= 1e-5
    assert audited["errors"] == 0 and audited["fixes"] == 0


@pytest.mark.parametrize("name", ORDER, ids=ORDER)
def test_writer_matches_oracle_before_serialization(name, plans):
    specs, raws = plans
    written = build_plan_features(specs, _transform(name))
    report = compare_plan(oracle_features(raws, name), written, 4)
    assert report["ok"] is True
    assert report["max_deviation_mm"] <= 1e-5


def test_0_011_mm_rejected_0_009_mm_accepted_at_large_coordinates(plans, tmp_path):
    specs, raws = plans
    name = "rotation37_then_translation"
    path = tmp_path / f"{name}.dxf"
    write_plan_dxf(build_plan_features(specs, _transform(name)), path)
    actual, _info = read_plan_dxf(path)
    oracle = oracle_features(raws, name)
    shifted = deepcopy(actual)
    shifted[0]["vertices_mm"][0][0] += 0.011
    rejected = compare_plan(oracle, shifted, 4)
    assert rejected["ok"] is False and "coordinate deviation" in rejected["errors"]
    near = deepcopy(actual)
    near[0]["vertices_mm"][0][0] += 0.009
    assert compare_plan(oracle, near, 4)["ok"] is True


def test_missing_entity_fails(plans, tmp_path):
    specs, raws = plans
    path = tmp_path / "plan.dxf"
    write_plan_dxf(build_plan_features(specs), path)
    actual, info = read_plan_dxf(path)
    report = compare_plan(oracle_features(raws, "identity"), actual[:-1], info["insunits"])
    assert report["ok"] is False and "missing" in report["errors"]


def test_extra_unsupported_line_fails(plans, tmp_path):
    import ezdxf

    specs, raws = plans
    path = tmp_path / "extra.dxf"
    write_plan_dxf(build_plan_features(specs), path)
    doc = ezdxf.readfile(path)
    doc.modelspace().add_line((0, 0), (1, 0))
    edited = tmp_path / "extra-line.dxf"
    doc.saveas(edited)
    actual, info = read_plan_dxf(edited)
    report = compare_plan(oracle_features(raws, "identity"), actual, info["insunits"])
    assert report["ok"] is False and "unsupported" in report["errors"]


def test_wrong_closed_flag_fails(plans, tmp_path):
    specs, raws = plans
    path = tmp_path / "plan.dxf"
    write_plan_dxf(build_plan_features(specs), path)
    actual, _info = read_plan_dxf(path)
    actual[0]["closed"] = False
    report = compare_plan(oracle_features(raws, "identity"), actual, 4)
    assert report["ok"] is False and "wrong closed flag" in report["errors"]


def test_wrong_raw_flag_fails(plans, tmp_path):
    specs, raws = plans
    path = tmp_path / "plan.dxf"
    write_plan_dxf(build_plan_features(specs), path)
    actual, _info = read_plan_dxf(path)
    actual[0]["raw_flag"] = 0
    report = compare_plan(oracle_features(raws, "identity"), actual, 4)
    assert report["ok"] is False and "wrong raw flag" in report["errors"]


def test_wrong_units_fails(plans, tmp_path):
    import ezdxf

    specs, raws = plans
    source = tmp_path / "mm.dxf"
    write_plan_dxf(build_plan_features(specs), source)
    doc = ezdxf.readfile(source)
    doc.header["$INSUNITS"] = 6
    path = tmp_path / "metres.dxf"
    doc.saveas(path)
    actual, info = read_plan_dxf(path)
    report = compare_plan(oracle_features(raws, "identity"), actual, info["insunits"])
    assert info["insunits"] == 6
    assert report["ok"] is False and "wrong units" in report["errors"]


def test_nonfinite_coordinate_rejected(plans, tmp_path):
    specs, raws = plans
    with pytest.raises(ValueError):
        write_plan_dxf(
            [{"layer": "NAN", "kind": "POINT", "closed": False, "vertices_mm": [[math.nan, 0.0, 0.0]]}],
            tmp_path / "nan.dxf")
    path = tmp_path / "plan.dxf"
    write_plan_dxf(build_plan_features(specs), path)
    actual, _info = read_plan_dxf(path)
    actual[0]["vertices_mm"][0][0] = math.inf
    assert compare_plan(oracle_features(raws, "identity"), actual, 4)["ok"] is False


def test_empty_readback_fails(plans):
    _specs, raws = plans
    report = compare_plan(oracle_features(raws, "identity"), [], 4)
    assert report["ok"] is False and "empty readback" in report["errors"]


def test_write_refuses_existing_path(plans, tmp_path):
    specs, _raws = plans
    path = tmp_path / "once.dxf"
    features = build_plan_features(specs)
    write_plan_dxf(features, path)
    with pytest.raises(FileExistsError):
        write_plan_dxf(features, path)


def test_audit_reports_fix_for_undefined_linetype(tmp_path):
    import ezdxf

    path = tmp_path / "ghost.dxf"
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    line = doc.modelspace().add_line((0, 0), (1, 0))
    line.dxf.linetype = "GHOST"
    doc.saveas(path)
    audited = audit_plan_dxf(path)
    assert audited["fixes"] > 0


def _rotation_plan(plans, tmp_path, filename):
    import ezdxf

    specs, raws = plans
    name = "rotation37_then_translation"
    source = tmp_path / f"{name}.dxf"
    write_plan_dxf(build_plan_features(specs, _transform(name)), source)
    doc = ezdxf.readfile(source)
    edited = tmp_path / filename
    return specs, raws, name, doc, edited


def test_lwpolyline_bulge_rejected_as_unsupported_curve(plans, tmp_path):
    _specs, raws, name, doc, edited = _rotation_plan(plans, tmp_path, "bulge.dxf")
    entity = next(item for item in doc.modelspace() if item.dxftype() == "LWPOLYLINE")
    points = list(entity.get_points("xyseb"))
    first = list(points[0])
    first[4] = 1.0
    points[0] = first
    entity.set_points(points, format="xyseb")
    doc.saveas(edited)
    actual, info = read_plan_dxf(edited)
    report = compare_plan(oracle_features(raws, name), actual, info["insunits"])
    assert report["ok"] is False and "unsupported curve" in report["errors"]


def test_repeated_first_vertex_fails_point_count(plans, tmp_path):
    _specs, raws, name, doc, edited = _rotation_plan(plans, tmp_path, "repeat-lw.dxf")
    entity = next(item for item in doc.modelspace() if item.dxftype() == "LWPOLYLINE")
    points = list(entity.get_points("xyseb"))
    points.append(points[0])
    entity.set_points(points, format="xyseb")
    doc.saveas(edited)
    actual, info = read_plan_dxf(edited)
    contour = next(item for item in actual if item["kind"] == "LWPOLYLINE")
    report = compare_plan(oracle_features(raws, name), actual, info["insunits"])
    assert len(contour["vertices_mm"]) == 5
    assert report["ok"] is False and "point count" in report["errors"]
    assert census(actual)["coordinates"] == 70


def test_polyline_repeated_first_vertex_fails_point_count(plans, tmp_path):
    _specs, raws, name, doc, edited = _rotation_plan(plans, tmp_path, "repeat-poly.dxf")
    entity = next(item for item in doc.modelspace() if item.dxftype() == "POLYLINE")
    entity.append_vertex(entity.vertices[0].dxf.location)
    doc.saveas(edited)
    actual, info = read_plan_dxf(edited)
    opening = next(item for item in actual if item["kind"] == "POLYLINE")
    report = compare_plan(oracle_features(raws, name), actual, info["insunits"])
    assert len(opening["vertices_mm"]) == 5
    assert report["ok"] is False and "point count" in report["errors"]
    assert census(actual)["coordinates"] == 70


def test_cyclic_shift_and_reverse_contour_matches(plans, tmp_path):
    specs, raws = plans
    name = "rotation37_then_translation"
    path = tmp_path / f"{name}.dxf"
    write_plan_dxf(build_plan_features(specs, _transform(name)), path)
    actual, info = read_plan_dxf(path)
    contour = next(item for item in actual if item["kind"] == "LWPOLYLINE")
    vertices = contour["vertices_mm"]
    assert len(vertices) == 4
    contour["vertices_mm"] = list(reversed(vertices[1:] + vertices[:1]))
    report = compare_plan(oracle_features(raws, name), actual, info["insunits"])
    assert report["ok"] is True


def test_rounded_corner_contour_rejected(plans):
    specs, _raws = plans
    data = specs[0].model_dump()
    point = data["floors"][0]["contour"][0]
    data["floors"][0]["contour"][0] = [point[0], point[1], {"r": 1.0}]
    with pytest.raises(ValueError):
        build_plan_features([spec_from_mapping(data)])
