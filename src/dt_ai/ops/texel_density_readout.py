"""Per face and per material texel density from the assigned map size (#548).

px/m is ``map_px * sqrt(uv_area / world_area)``, evaluated by
``dt_ai.geometry.ground_cake.texel_density`` (the pilot area texel function). The pixel
size is the size assigned to that face's material. A missing assignment is an error
that names the material; nothing is filled in from a fixed size or from another material.

Bands are the locked standards, applied as a closed interval (inclusive edges, the same
contract as ``twinqa.uv.density_findings``): VPM ``uv.diffuse_density_px_per_m``
(D160, 512..1706 px/m) and NPM ``textures.ground_density_px_per_square_meter`` (10..40).
D097 decided the NPM unit is px per linear metre; this readout uses that linear formula
on the locked numbers.

A zero area or a zero map size is the non-positive threshold (``at_threshold``) and
raises. Empty, partial, unsupported and non-finite input raises, or is listed in
``dropped`` with a reason. ``passed`` is true only when every reported face and every
assigned material is inside the band and nothing was dropped.

A polygon uses the Newell vector area in world space and the shoelace area in UV.
An absolute fan is not the area: a concave ring would count the overlap. A
self-intersecting ring, a ring more than ``PLANAR_TOL_M`` (1 mm) off its Newell
plane, or a degenerate ring is dropped with an error that names the face, in world
and in UV. Publication links the partial onto the destination and does not replace
an existing file.

    uv run python -m dt_ai.ops.texel_density_readout --input faces.json --output out.json --report report.json

Pattern: none | new-case: agent texel-density readout from the assigned map pixel size (#548).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from dt_ai.geometry.ground_cake import texel_density
from twinqa.profiles import load_profiles

METHOD = "dt_ai.geometry.ground_cake.texel_density"
SCHEMA = "texel-density-readout-v1"
REPORT_SCHEMA = "texel-density-readout-report-v1"
PLANAR_TOL_M = 1e-3  # 1 mm off the Newell plane: the contour lattice, beyond this the ring is nonplanar
_WORLD_AREA_EPS = 1e-12  # same floor texel_density uses before it returns NaN
_UV_AREA_EPS = 1e-16
_WORLD_EDGE_EPS_M = 1e-12
_UV_EDGE_EPS = 1e-15
_BANDS: dict | None = None


class ReadoutError(ValueError):
    """The readout cannot pass. The message names the rejected input."""


def _real(value) -> bool:
    return not isinstance(value, (bool, np.bool_)) and isinstance(value, (int, float, np.integer, np.floating))


def _band(node, source: str) -> dict:
    try:
        lo, hi = node["min"], node["max"]
    except (TypeError, KeyError) as exc:
        raise ReadoutError(f"unsupported band at {source}") from exc
    if not _real(lo) or not _real(hi) or not math.isfinite(float(lo)) or not math.isfinite(float(hi)) or float(lo) >= float(hi):
        raise ReadoutError(f"unsupported band at {source}")
    return {"min": float(lo), "max": float(hi), "source": source}


def density_bands() -> dict:
    """VPM and NPM texel bands from the locked standards. Numbers are not typed here."""
    global _BANDS
    if _BANDS is None:
        profiles = load_profiles()
        npm = profiles.npm["textures"]["ground_density_px_per_square_meter"]
        vpm = profiles.vpm["uv"]["diffuse_density_px_per_m"]
        _BANDS = {
            "NPM": _band(npm, "standards/NPM_STANDARD.yaml textures.ground_density_px_per_square_meter"),
            "VPM": _band(vpm, "standards/VPM_STANDARD.yaml uv.diffuse_density_px_per_m"),
        }
    return _BANDS


def _require_area(value, label: str) -> float:
    if not _real(value):
        raise ReadoutError(f"unsupported {label}")
    number = float(value)
    if not math.isfinite(number):
        raise ReadoutError(f"non-finite {label}")
    if number == 0.0:
        raise ReadoutError(f"at_threshold: zero {label}")
    if number < 0.0:
        raise ReadoutError(f"negative {label}")
    return number


def _require_map_px(value, material: str | None) -> int:
    where = f"material {material!r}: " if material else ""
    if not _real(value):
        raise ReadoutError(f"{where}unsupported map size {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ReadoutError(f"{where}non-finite map size")
    if isinstance(value, (float, np.floating)) and not number.is_integer():
        raise ReadoutError(f"{where}unsupported map size {value!r}")
    px = int(number)
    if px == 0:
        raise ReadoutError(f"{where}at_threshold: map size 0")
    if px < 0:
        raise ReadoutError(f"{where}negative map size {px}")
    return px


def px_per_m(uv_area: float, world_area: float, map_px: int) -> float:
    """px/m for one pair of areas. The ratio is computed by ``texel_density`` on an equal-area triangle."""
    uv_area = _require_area(uv_area, "uv area")
    world_area = _require_area(world_area, "world area")
    px = _require_map_px(map_px, None)
    # Base 1 and height 2*area: texel_density's 0.5 * base * height returns these areas unchanged
    # (a reconstructed right triangle with leg sqrt(2*area) does not).
    verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0 * world_area, 0.0]], dtype=np.float64)
    faces = np.array([[0, 1, 2]], dtype=np.int64)
    uv = np.array([[[0.0, 0.0], [1.0, 0.0], [0.0, 2.0 * uv_area]]], dtype=np.float64)
    value = float(texel_density(verts, faces, uv, px)[0])
    if not math.isfinite(value):
        raise ReadoutError("non-finite density")
    return value


def _classify(value: float, band: dict) -> tuple[str, str]:
    lo, hi = band["min"], band["max"]
    if lo <= value <= hi:
        return "pass", ""
    if value < lo:
        return "fail", f"below {lo:g} px/m"
    return "fail", f"above {hi:g} px/m"


def _triangle_areas(xyz, uv) -> tuple[float, float]:
    """UV area and world area with the same split ``texel_density`` uses, before the ratio."""
    p = np.asarray(xyz, dtype=np.float64)
    q = np.asarray(uv, dtype=np.float64)
    world = 0.5 * float(np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])))
    e1, e2 = q[1] - q[0], q[2] - q[0]
    uv_area = 0.5 * abs(float(e1[0] * e2[1] - e1[1] * e2[0]))
    return uv_area, world


def _coords(points, width: int, label: str) -> list[list[float]]:
    if isinstance(points, (str, bytes)) or not isinstance(points, (list, tuple)):
        raise ReadoutError(f"partial {label}")
    out = []
    for point in points:
        if isinstance(point, (str, bytes)) or not isinstance(point, (list, tuple)) or len(point) != width:
            raise ReadoutError(f"partial {label}")
        nums = []
        for coord in point:
            if not _real(coord):
                raise ReadoutError(f"partial {label}")
            number = float(coord)
            if not math.isfinite(number):
                raise ReadoutError(f"non-finite {label}")
            nums.append(number)
        out.append(nums)
    return out


def _polygon_error(face_id: str, text: str) -> ReadoutError:
    return ReadoutError(f"face {face_id!r}: {text}")


def _newell_vector(points: np.ndarray) -> np.ndarray:
    """2 x signed area vector. Subtract the first corner so a face far from the origin keeps its area."""
    local = points - points[0]
    return np.cross(local, np.roll(local, -1, axis=0)).sum(axis=0)


def _shoelace(points: np.ndarray) -> float:
    local = points - points[0]  # local frame: a far-from-origin ring keeps its area
    x, y = local[:, 0], local[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def _zero_edge(points: np.ndarray, eps: float) -> bool:
    return bool(np.any(np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1) <= eps))


def _simple_2d(points: np.ndarray) -> bool:
    """True when no two non-adjacent edges of a closed 2D ring touch or cross.

    Adjacent edges share a vertex and are not a self-intersection. A vertex lying on a
    non-adjacent edge, a collinear overlap, or a proper crossing is not simple.
    """
    ring = np.asarray(points, dtype=np.float64)
    count = len(ring)
    if count:
        ring = ring - ring.min(axis=0)  # local frame: tolerances follow the ring extent, not its offset
    scale = max(float(np.max(np.abs(ring))) if count else 0.0, 1e-12)
    eps = 1e-12 * scale * scale

    def orient(a, b, c) -> int:
        signed = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        if abs(signed) <= eps:
            return 0
        return 1 if signed > 0 else -1

    def on_segment(a, b, c) -> bool:
        pad = 1e-15 * scale
        return (min(a[0], b[0]) - pad <= c[0] <= max(a[0], b[0]) + pad
                and min(a[1], b[1]) - pad <= c[1] <= max(a[1], b[1]) + pad)

    for i in range(count):
        a, b = ring[i], ring[(i + 1) % count]
        for j in range(i + 2, count):
            if i == 0 and j == count - 1:
                continue
            c, d = ring[j], ring[(j + 1) % count]
            o1, o2 = orient(a, b, c), orient(a, b, d)
            o3, o4 = orient(c, d, a), orient(c, d, b)
            if o1 != o2 and o3 != o4 and 0 not in (o1, o2, o3, o4):
                return False
            if ((o1 == 0 and on_segment(a, b, c)) or (o2 == 0 and on_segment(a, b, d))
                    or (o3 == 0 and on_segment(c, d, a)) or (o4 == 0 and on_segment(c, d, b))):
                return False
    return True


def _plane_distance(points: np.ndarray, newell: np.ndarray) -> float:
    norm = float(np.linalg.norm(newell))
    if norm == 0.0:
        return 0.0
    unit = newell / norm
    return float(np.max(np.abs((points - points.mean(axis=0)) @ unit)))


def _world_simple(points: np.ndarray, newell: np.ndarray) -> bool:
    """Simplicity in the plane of the ring. A cancelling bowtie has no trustworthy normal, so every
    axis is checked and any crossing rejects the ring. A real plane uses its dominant axis only:
    an edge-on projection of a simple ring is not a self-intersection."""
    span = float(np.max(np.ptp(points, axis=0))) if len(points) else 0.0
    norm = float(np.linalg.norm(newell))
    if norm > _WORLD_AREA_EPS * max(span, 1e-12):
        axis = int(np.argmax(np.abs(newell)))
        keep = [index for index in range(3) if index != axis]
        return _simple_2d(points[:, keep])
    return all(_simple_2d(points[:, list(pair)]) for pair in ((0, 1), (0, 2), (1, 2)))


def _measure(xyz, uv, map_px: int, face_id: str = "") -> tuple[float, float, float]:
    xyz = _coords(xyz, 3, "world coordinate")
    uv = _coords(uv, 2, "UV coordinate")
    if len(xyz) != len(uv):
        raise ReadoutError("partial face: UV count does not match the world corners")
    if len(xyz) < 3:
        raise ReadoutError("partial face: fewer than 3 corners")
    world_pts = np.asarray(xyz, dtype=np.float64)
    uv_pts = np.asarray(uv, dtype=np.float64)
    if _zero_edge(world_pts, _WORLD_EDGE_EPS_M):
        raise _polygon_error(face_id, "degenerate world polygon")
    if _zero_edge(uv_pts, _UV_EDGE_EPS):
        raise _polygon_error(face_id, "degenerate UV polygon")
    if len(xyz) == 3:
        uv_area, world = _triangle_areas(xyz, uv)
        if world < _WORLD_AREA_EPS:
            raise _polygon_error(face_id, "degenerate world polygon")
        if uv_area < _UV_AREA_EPS:
            raise _polygon_error(face_id, "degenerate UV polygon")
        packed = uv_pts.reshape(1, 3, 2)
        value = float(texel_density(world_pts, np.array([[0, 1, 2]], dtype=np.int64), packed, map_px)[0])
        if not math.isfinite(value):
            raise _polygon_error(face_id, "degenerate world polygon")
        return value, uv_area, world
    # Newell / shoelace, not an absolute fan: the fan double-counts a concave notch.
    newell = _newell_vector(world_pts)
    if _plane_distance(world_pts, newell) > PLANAR_TOL_M:
        raise _polygon_error(face_id, "nonplanar world polygon")
    if not _world_simple(world_pts, newell):
        raise _polygon_error(face_id, "self-intersecting world polygon")
    world = float(np.linalg.norm(newell) / 2.0)
    if world < _WORLD_AREA_EPS:
        raise _polygon_error(face_id, "degenerate world polygon")
    if not _simple_2d(uv_pts):
        raise _polygon_error(face_id, "self-intersecting UV polygon")
    uv_area = abs(_shoelace(uv_pts))
    if uv_area < _UV_AREA_EPS:
        raise _polygon_error(face_id, "degenerate UV polygon")
    return px_per_m(uv_area, world, map_px), uv_area, world


def _drop(kind: str, index: int, reason: str, *, name=None, face_id=None) -> dict:
    item = {"kind": kind, "index": index, "reason": reason, "px_per_m": None}
    if kind == "material":
        item["name"] = name
    else:
        item["id"] = face_id
        item["material"] = name
    return item


def _materials(materials: list) -> tuple[dict, list, list]:
    dropped = []
    parsed = []
    for index, item in enumerate(materials):
        if not isinstance(item, dict):
            dropped.append(_drop("material", index, "partial material"))
            parsed.append(None)
            continue
        name = item.get("name")
        if not isinstance(name, str) or name == "":
            dropped.append(_drop("material", index, "partial material name"))
            parsed.append(None)
            continue
        parsed.append((index, name, item))
    counts: dict[str, int] = defaultdict(int)
    for entry in parsed:
        if entry is not None:
            counts[entry[1]] += 1
    sizes = {}
    kept = []
    for entry in parsed:
        if entry is None:
            continue
        index, name, item = entry
        if counts[name] > 1:
            dropped.append(_drop(
                "material", index, f"duplicate material {name!r}: refusing the first entry", name=name,
            ))
            continue
        if "map_px" not in item or item["map_px"] is None:
            dropped.append(_drop(
                "material", index, f"unmapped material {name!r}: no assigned map size", name=name,
            ))
            continue
        try:
            sizes[name] = _require_map_px(item["map_px"], name)
        except ReadoutError as exc:
            dropped.append(_drop("material", index, str(exc), name=name))
            continue
        kept.append((index, name, sizes[name]))
    return sizes, kept, dropped


def readout(payload: dict) -> dict:
    """Per-face and per-material px/m for one NPM or VPM assignment.

    ``materials`` is a list of ``{name, map_px}``. ``faces`` is a list of
    ``{id, material, xyz, uv}``. Every face and every material ends in ``faces`` /
    ``materials`` or in ``dropped`` with a reason.
    """
    if not isinstance(payload, dict):
        raise ReadoutError("unsupported payload")
    missing = [key for key in ("profile", "materials", "faces") if key not in payload]
    if missing:
        raise ReadoutError("partial: missing " + ", ".join(missing))
    profile = payload["profile"]
    bands = density_bands()
    if profile not in bands:
        raise ReadoutError(f"unsupported profile {profile!r}")
    materials = payload["materials"]
    faces = payload["faces"]
    if not isinstance(materials, list) or not isinstance(faces, list):
        raise ReadoutError("partial: materials and faces must be lists")
    if len(faces) == 0:
        raise ReadoutError("empty: no faces")
    band = bands[profile]
    sizes, kept, dropped = _materials(materials)
    reasons = {item["name"]: item["reason"] for item in dropped if item["kind"] == "material" and item.get("name")}
    face_rows = []
    for index, face in enumerate(faces):
        if not isinstance(face, dict):
            dropped.append(_drop("face", index, "unsupported face"))
            continue
        face_id = face.get("id")
        material = face.get("material")
        if not isinstance(face_id, str) or face_id == "":
            dropped.append(_drop("face", index, "partial face: no id", face_id=face_id, name=material))
            continue
        if not isinstance(material, str) or material == "":
            dropped.append(_drop("face", index, "partial face: no material", face_id=face_id))
            continue
        if material not in sizes:
            reason = reasons.get(material) or f"unmapped material {material!r}: no assigned map size"
            dropped.append(_drop("face", index, reason, face_id=face_id, name=material))
            continue
        try:
            value, uv_area, world = _measure(face.get("xyz"), face.get("uv"), sizes[material], face_id)
        except ReadoutError as exc:
            dropped.append(_drop("face", index, str(exc), face_id=face_id, name=material))
            continue
        status, reason = _classify(value, band)
        face_rows.append({
            "kind": "face",
            "index": index,
            "id": face_id,
            "material": material,
            "map_px": sizes[material],
            "uv_area": uv_area,
            "world_area_m2": world,
            "px_per_m": value,
            "status": status,
            "reason": reason,
        })
    by_name = defaultdict(list)
    for row in face_rows:
        by_name[row["material"]].append(row)
    material_rows = []
    for index, name, map_px in kept:
        group = by_name.get(name, [])
        if not group:
            material_rows.append({
                "kind": "material", "index": index, "name": name, "map_px": map_px,
                "face_count": 0, "uv_area": 0.0, "world_area_m2": 0.0, "px_per_m": None,
                "min_px_per_m": None, "max_px_per_m": None, "status": "fail", "reason": "no faces",
            })
            continue
        uv_area = sum(item["uv_area"] for item in group)
        world = sum(item["world_area_m2"] for item in group)
        value = px_per_m(uv_area, world, map_px)
        status, reason = _classify(value, band)
        if any(item["status"] != "pass" for item in group):
            status = "fail"
            reason = reason or "a face is outside the band"
        material_rows.append({
            "kind": "material", "index": index, "name": name, "map_px": map_px,
            "face_count": len(group), "uv_area": uv_area, "world_area_m2": world,
            "px_per_m": value,
            "min_px_per_m": min(item["px_per_m"] for item in group),
            "max_px_per_m": max(item["px_per_m"] for item in group),
            "status": status, "reason": reason,
        })
    face_seen = {row["index"] for row in face_rows} | {item["index"] for item in dropped if item["kind"] == "face"}
    material_seen = {row["index"] for row in material_rows} | {
        item["index"] for item in dropped if item["kind"] == "material"
    }
    if face_seen != set(range(len(faces))) or material_seen != set(range(len(materials))):
        raise ReadoutError("internal: an input element was not reported")
    passed = (
        not dropped
        and all(row["status"] == "pass" for row in face_rows)
        and all(row["status"] == "pass" for row in material_rows)
    )
    return {
        "schema": SCHEMA,
        "profile": profile,
        "method": METHOD,
        "band": band,
        "status": "pass" if passed else "fail",
        "passed": passed,
        "counts": {
            "faces": len(faces),
            "reported": len(face_rows),
            "dropped": len(dropped),
            "materials": len(materials),
        },
        "faces": face_rows,
        "materials": material_rows,
        "dropped": dropped,
    }


def _dumps(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _key(path: Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def _distinct(input_path: Path, output_path: Path, report_path: Path) -> None:
    roles = {
        "input": Path(input_path),
        "output": Path(output_path),
        "report": Path(report_path),
        "output.partial": Path(str(output_path) + ".partial"),
        "report.partial": Path(str(report_path) + ".partial"),
    }
    seen = {}
    idents = {}
    for role, path in roles.items():
        key = _key(path)
        if key in seen:
            raise ReadoutError(f"{role} is the same file as {seen[key]}")
        seen[key] = role
        if path.exists():
            st = path.stat()
            ident = (st.st_dev, st.st_ino)
            if ident in idents:
                raise ReadoutError(f"{role} is the same file as {idents[ident]}")
            idents[ident] = role


def _commit_partial(partial: Path, dest: Path) -> None:
    """Link the finished partial onto dest. ``os.link`` fails if dest already exists, so a file
    created after the exists() precheck is left untouched. Tests replace this to open that window."""
    os.link(partial, dest)


def _publish(dest: Path, data: bytes) -> None:
    partial = Path(str(dest) + ".partial")
    if dest.exists() or partial.exists():
        raise ReadoutError(f"{dest} exists; write a new file")
    with open(partial, "xb") as handle:
        handle.write(data)
    try:
        _commit_partial(partial, dest)
    except FileExistsError as exc:
        if partial.exists():
            partial.unlink()
        raise ReadoutError(f"{dest} exists; write a new file") from exc
    partial.unlink()


def _report(result: dict, raw: bytes) -> dict:
    return {
        "schema": REPORT_SCHEMA,
        "status": result["status"],
        "passed": result["passed"],
        "method": result["method"],
        "profile": result["profile"],
        "band": result["band"],
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "counts": result["counts"],
        "faces": [
            {"index": row["index"], "id": row["id"], "material": row["material"], "map_px": row["map_px"],
             "px_per_m": row["px_per_m"], "status": row["status"], "reason": row["reason"]}
            for row in result["faces"]
        ],
        "materials": [
            {"index": row["index"], "name": row["name"], "map_px": row["map_px"], "px_per_m": row["px_per_m"],
             "status": row["status"], "reason": row["reason"]}
            for row in result["materials"]
        ],
        "dropped": result["dropped"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Texel density from the assigned map size (#548).")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        _distinct(args.input, args.output, args.report)
        if not args.input.is_file():
            raise ReadoutError(f"input not found: {args.input}")
        for path in (args.output, args.report, Path(str(args.output) + ".partial"), Path(str(args.report) + ".partial")):
            if path.exists():
                raise ReadoutError(f"{path} exists; write a new file")
        raw = args.input.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        result = readout(payload)
        report = _report(result, raw)
        output_bytes, report_bytes = _dumps(result), _dumps(report)
        _publish(args.output, output_bytes)
        _publish(args.report, report_bytes)
    except (ReadoutError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for item in result["dropped"]:
        print(f"error: {item['reason']}", file=sys.stderr)
    sys.stdout.write(report_bytes.decode("utf-8"))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
