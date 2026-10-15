"""Straight-entity plan proxies in WCS and straight-entity serialization.

Pattern: none — straight-entity CAD serialization proxy (REVIEW_CHECKLIST Q1: new-case).
This is not an approved architectural pattern and provides no architectural or delivery
certification.

Supported: closed LWPOLYLINE contours, closed 3D POLYLINE rectangles for
wall-plane openings, and POINT level markers. Drawings are R2018 with
INSUNITS=4 (millimetres). Curves and rounded corners, blocks, UCS variants,
terrace parapets, CRS or geodetic correctness, and delivery QA are not
supported or certified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from dt_ai.spec.model import Spec

TOL_MM = 0.01
_RAW_FLAG = {"LWPOLYLINE": 1, "POLYLINE": 9, "POINT": None}


@dataclass(frozen=True)
class PlanTransform:
    """Rotate about the origin around +Z, then translate. Coordinates are metres."""

    rotation_deg: float = 0.0
    shift_m: tuple[float, float, float] = (0, 0, 0)

    def apply(self, x: float, y: float, z: float) -> tuple[float, float, float]:
        cosine = math.cos(math.radians(self.rotation_deg))
        sine = math.sin(math.radians(self.rotation_deg))
        x, y, z = float(x), float(y), float(z)
        shift_x, shift_y, shift_z = self.shift_m
        return (
            cosine * x - sine * y + float(shift_x),
            sine * x + cosine * y + float(shift_y),
            z + float(shift_z),
        )


IDENTITY = PlanTransform()


def _prefix(spec_id: str) -> str:
    parts = spec_id.split("-")
    return (parts[1] if len(parts) > 1 else spec_id).upper()


def _xy(point, level: str) -> tuple[float, float]:
    if len(point) < 2 or isinstance(point[0], dict) or isinstance(point[1], dict):
        raise ValueError(f"floor {level}: contour point must be [x, y] in metres")
    if any(isinstance(part, dict) for part in point):
        raise ValueError(f"floor {level}: rounded corners are not drawn")
    return float(point[0]), float(point[1])


def _opening_metres(contour, opening, elev_m: float) -> list[tuple[float, float, float]]:
    x0, y0 = contour[opening.wall]
    x1, y1 = contour[(opening.wall + 1) % len(contour)]
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        raise ValueError(f"opening wall {opening.wall} has zero length")
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    ax, ay = x0 + ux * opening.x_m, y0 + uy * opening.x_m
    bx = x0 + ux * (opening.x_m + opening.w_m)
    by = y0 + uy * (opening.x_m + opening.w_m)
    z0 = elev_m + opening.sill_m
    return [(ax, ay, z0), (bx, by, z0), (bx, by, z0 + opening.h_m), (ax, ay, z0 + opening.h_m)]


def _vertex_mm(transform: PlanTransform, x: float, y: float, z: float) -> list[float]:
    x, y, z = transform.apply(x, y, z)
    if not all(math.isfinite(value) for value in (x, y, z)):
        raise ValueError("non-finite coordinate")
    return [round(value * 1000.0, 6) for value in (x, y, z)]


def _feature(layer: str, kind: str, closed: bool, metres, transform: PlanTransform) -> dict:
    return {
        "layer": layer,
        "kind": kind,
        "closed": closed,
        "vertices_mm": [_vertex_mm(transform, *point) for point in metres],
        "raw_flag": _RAW_FLAG[kind],
    }


def build_plan_features(specs, transform: PlanTransform = IDENTITY) -> list[dict]:
    features = []
    for spec in specs:
        prefix = _prefix(spec.id)
        elevation = {level.name: level.elev_m for level in spec.levels}
        for floor in spec.expanded_floors():
            z = elevation[floor.level]
            ring = [_xy(point, floor.level) for point in floor.contour]
            features.append(_feature(
                f"{prefix}_{floor.level}_CONTOUR", "LWPOLYLINE", True,
                [(x, y, z) for x, y in ring], transform))
            for index, opening in enumerate(floor.openings):
                features.append(_feature(
                    f"{prefix}_{floor.level}_OPEN_{index}", "POLYLINE", True,
                    _opening_metres(ring, opening, z), transform))
        for level in spec.levels:
            features.append(_feature(
                f"{prefix}_{level.name}_LEVEL", "POINT", False,
                [(0.0, 0.0, elevation[level.name])], transform))
    layers = [item["layer"] for item in features]
    if len(layers) != len(set(layers)):
        raise ValueError("duplicate feature layer")
    if not features:
        raise ValueError("no features")
    return features


def spec_from_mapping(data: dict) -> Spec:
    body = {key: value for key, value in data.items() if key not in ("synthetic", "note")}
    return Spec.model_validate(body)


def _finite_vertices(vertices) -> bool:
    for vertex in vertices:
        if len(vertex) < 3 or not all(
                isinstance(number, (int, float)) and not isinstance(number, bool) and math.isfinite(number)
                for number in vertex[:3]):
            return False
    return True


def write_plan_dxf(features, path) -> None:
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    for feature in features:
        if not _finite_vertices(feature["vertices_mm"]):
            raise ValueError("non-finite coordinate")
    import ezdxf

    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4
    model = doc.modelspace()
    for feature in features:
        if feature["layer"] not in doc.layers:
            doc.layers.add(feature["layer"])
        attribs = {"layer": feature["layer"]}
        vertices = feature["vertices_mm"]
        if feature["kind"] == "LWPOLYLINE":
            model.add_lwpolyline(
                [(vertex[0], vertex[1]) for vertex in vertices], close=True,
                dxfattribs={**attribs, "elevation": vertices[0][2]})
        elif feature["kind"] == "POLYLINE":
            model.add_polyline3d(vertices, close=True, dxfattribs=attribs)
        elif feature["kind"] == "POINT":
            model.add_point(vertices[0], dxfattribs=attribs)
        else:
            raise ValueError(feature["kind"])
    doc.saveas(path)


def _closed(entity) -> bool:
    for name in ("is_closed", "closed"):
        if hasattr(entity, name):
            value = getattr(entity, name)
            return bool(value() if callable(value) else value)
    return bool(int(entity.dxf.flags) & 1)


def _as_wcs(entity, x, y, z) -> list[float]:
    extrusion = (0.0, 0.0, 1.0)
    if entity.dxf.hasattr("extrusion"):
        raw = entity.dxf.extrusion
        extrusion = (float(raw[0]), float(raw[1]), float(raw[2]))
    if abs(extrusion[0]) > 1e-9 or abs(extrusion[1]) > 1e-9 or abs(extrusion[2] - 1.0) > 1e-9:
        from ezdxf.math import OCS
        point = OCS(extrusion).to_wcs((x, y, z))
        return [float(point.x), float(point.y), float(point.z)]
    return [float(x), float(y), float(z)]


def _decoded(entity, kind: str, closed: bool, vertices, raw_flag, unsupported_curve: bool = False) -> dict:
    item = {
        "layer": entity.dxf.layer,
        "kind": kind,
        "closed": closed,
        "vertices_mm": vertices,
        "raw_flag": raw_flag,
    }
    if unsupported_curve:
        item["unsupported_curve"] = True
    return item


def read_plan_dxf(path) -> tuple[list[dict], dict]:
    import ezdxf

    doc = ezdxf.readfile(path)
    entities = []
    for entity in doc.modelspace():
        kind = entity.dxftype()
        if kind == "LWPOLYLINE":
            z = float(entity.dxf.elevation)
            closed = _closed(entity)
            points = entity.get_points("xyb")
            vertices = [_as_wcs(entity, point[0], point[1], z) for point in points]
            curve = any(abs(float(point[2])) > 0 for point in points)
            entities.append(_decoded(entity, kind, closed, vertices, int(entity.dxf.flags), curve))
        elif kind == "POLYLINE":
            closed = _closed(entity)
            vertices = []
            curve = False
            for vertex in entity.vertices:
                location = vertex.dxf.location
                vertices.append(_as_wcs(entity, location.x, location.y, location.z))
                if vertex.dxf.hasattr("bulge") and abs(float(vertex.dxf.bulge)) > 0:
                    curve = True
            entities.append(_decoded(entity, kind, closed, vertices, int(entity.dxf.flags), curve))
        elif kind == "POINT":
            location = entity.dxf.location
            vertices = [_as_wcs(entity, location.x, location.y, location.z)]
            entities.append(_decoded(entity, kind, False, vertices, None))
        else:
            entities.append({"layer": entity.dxf.layer, "kind": kind, "unsupported": True})
    counts: dict[str, int] = {}
    for item in entities:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    info = {"insunits": int(doc.header.get("$INSUNITS", 0)), "counts": counts, "entities": len(entities)}
    return entities, info


def census(features) -> dict:
    counts: dict[str, int] = {}
    for item in features:
        counts[item["kind"]] = counts.get(item["kind"], 0) + 1
    coordinates = sum(len(item.get("vertices_mm") or []) for item in features)
    return {
        "entities": len(features),
        "coordinates": coordinates,
        "layers": len({item["layer"] for item in features}),
        **counts,
    }


def _ring_deviation(expected, actual) -> float:
    best = None
    for sequence in (actual, list(reversed(actual))):
        for shift in range(len(sequence)):
            rotated = sequence[shift:] + sequence[:shift]
            deviation = max(math.dist(left, right) for left, right in zip(expected, rotated))
            best = deviation if best is None else min(best, deviation)
    return best


def _unique(errors: list[str]) -> list[str]:
    found = []
    for error in errors:
        if error not in found:
            found.append(error)
    return found


def compare_plan(expected, actual, units, tol_mm: float = TOL_MM) -> dict:
    errors = []
    if units != 4:
        errors.append("wrong units")
    if not actual:
        errors.append("empty readback")
    if len(expected) != len({item["layer"] for item in expected}):
        errors.append("duplicate expected layer")
    if len(actual) != len({item["layer"] for item in actual}):
        errors.append("duplicate layer")
    if any(item.get("unsupported") for item in actual):
        errors.append("unsupported")
    if any(item.get("unsupported_curve") for item in actual):
        errors.append("unsupported curve")
    expected_map = {item["layer"]: item for item in expected}
    actual_map = {}
    for item in actual:
        actual_map.setdefault(item["layer"], item)
    if set(expected_map) - set(actual_map):
        errors.append("missing")
    if set(actual_map) - set(expected_map):
        errors.append("extra")
    max_deviation = None
    for layer, wanted in expected_map.items():
        found = actual_map.get(layer)
        if found is None or found.get("unsupported"):
            continue
        if found["kind"] != wanted["kind"]:
            errors.append("wrong kind")
        if bool(found["closed"]) != bool(wanted["closed"]):
            errors.append("wrong closed flag")
        if "raw_flag" in found and found["raw_flag"] != _RAW_FLAG.get(wanted["kind"]):
            errors.append("wrong raw flag")
        vertices = found.get("vertices_mm") or []
        if not _finite_vertices(vertices):
            errors.append("nonfinite")
            continue
        if len(vertices) != len(wanted["vertices_mm"]):
            errors.append("point count")
            continue
        if wanted["kind"] == "POINT":
            deviation = math.dist(wanted["vertices_mm"][0], vertices[0])
        else:
            deviation = _ring_deviation(wanted["vertices_mm"], vertices)
        max_deviation = deviation if max_deviation is None else max(max_deviation, deviation)
        if deviation > tol_mm:
            errors.append("coordinate deviation")
    return {"ok": not errors, "errors": _unique(errors), "max_deviation_mm": max_deviation}


def audit_plan_dxf(path) -> dict:
    from ezdxf import recover

    doc, auditor = recover.readfile(str(path))
    follow = doc.audit()
    return {
        "errors": len(auditor.errors) + len(follow.errors),
        "fixes": len(auditor.fixes) + len(follow.fixes),
    }
