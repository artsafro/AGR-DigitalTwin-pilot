"""Plan contour and opening account from a DXF readback of one sheet (issue #967).

Pattern: wall-from-contour

The drawing is millimetres. Stored coordinates are metres:
``(x_mm - origin_mm) * 0.001 + frame_shift_m``. The default origin and shift are zero,
so the only conversion is the unit change; a building frame is whatever the caller passes.
Nothing in here picks an unmapped layer, an opening depth or an insert base point.

Guarantees (each has a test):
- Every model-space entity is one record in ``entities``, status ``used`` or ``dropped``,
  and the handles are unique. A count that does not match the model space is an error.
- A layer that is not in the caller's map is an error naming that layer. Nothing is written.
- A role other than ``wall``, ``symbol``, ``hatch`` or ``drop:<reason>`` is an error naming it.
- ``hatch`` layers hold HATCH entities only (anything else is an error naming the type); their boundary
  paths (even-odd per hatch) united are the drawn wall mass. A hatch with no area is an error naming it.
- ``contour_source`` is ``lines`` (default: the wall lines) or ``hatch`` (the hatch union, closed the same
  way as contours.py: grown by ``gap_close_m``, outlines filled, shrunk back). Anything else is an error;
  ``hatch`` with no hatch entity is an error.
- Coverage (review #989): when a hatch layer is mapped, the kept pieces must cover strictly more than
  COVERAGE_MIN_SHARE (0.9) of the hatch area and every bbox side must sit strictly within COVERAGE_BBOX_M
  (0.1 m) of the hatch bbox. Otherwise the extract is an error naming the coverage: no contour that lost
  the drawn wall is written. Exactly 0.9 or exactly 0.1 m fails. With no hatch layer the coverage is
  ``not measured`` with the reason.
- Overshoot (#1004): ``unaccounted_m2`` is the kept footprint minus the hatch closed at the fixed
  reference COVERAGE_REF_GAP_CLOSE_M (0.75 m = GAP_CLOSE_M; outlines plus the strips bridging gaps strictly
  under 1.5 m, filled). It does not follow the run's ``gap_close_m``: a wider run closing that bridges an
  opening the reference leaves open fails.
  It must be strictly under MAX_UNACCOUNTED_M2 (0.5 m2, the smallest kept piece); exactly 0.5 fails and
  the error names the area and its bbox. A footprint that closes over a notch the hatch leaves open fails.
  A ``gap_close_m`` that is not a finite number above 0.1 mm is an error naming it.
- A non-finite coordinate is an error naming the handle. An empty model space is an error.
- A wall or symbol entity whose type this reader does not support is an error naming the
  type (a CIRCLE on a wall layer is not a contour).
- A wall piece with area <= MIN_PIECE_M2 (0.5), including an area of exactly 0.5, is dropped.
- Gaps strictly narrower than ``2 * GAP_CLOSE_M`` (1.5 m) are closed. A gap of exactly
  1.5 m stays two pieces.
- ``z1`` missing, non-finite, or <= ``z0`` does not yield a runnable contour: the result is
  ``provisional`` and the CLI exits 2. The CLI never returns 0 for a provisional result.
- ``levels_m`` is a list of at least two finite, strictly increasing elevations. Anything else
  (empty, one value, NaN, inf, a bool, a step that does not rise) is an error naming ``levels_m``.
  One plan is copied into one band per consecutive pair. ``z0`` must equal the first elevation.
- An opening symbol becomes a cutter box only when the block name parses a finite width,
  height and level, the rotation is a right angle, ``opening_insert`` is ``centre``, and two
  wall faces sit strictly within 1.0 m on opposite sides of that centre. Otherwise the
  insert is dropped with the missing fact named. No default depth and no default base point.
  A face at exactly 1.0 m is not used.
- The CLI refuses an output or report path that is the input or the same file as the other
  output (exit 4, nothing written). It never deletes an input.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union

_BODY = Path(__file__).resolve().parent
if str(_BODY) not in sys.path:
    sys.path.insert(0, str(_BODY))
from contours import GAP_CLOSE_M, MIN_PIECE_M2  # noqa: E402

COVERAGE_MIN_SHARE = 0.9  # covered share of the wall hatch must be strictly above this
COVERAGE_BBOX_M = 0.1  # every bbox side strictly within this of the hatch bbox
# footprint area outside the hatch closed at the reference radius must stay strictly under the smallest
# kept piece (#1004). The reference is fixed (the default GAP_CLOSE_M), never the run's gap_close_m.
MAX_UNACCOUNTED_M2 = MIN_PIECE_M2
COVERAGE_REF_GAP_CLOSE_M = GAP_CLOSE_M
CONTOUR_SOURCES = ("lines", "hatch")
FACE_LIMIT_M = 1.0  # a host-wall face is strictly closer than this; exactly 1.0 m is not used
# L03 of АС.03. Only A-WALL-____-MCUT is the exterior cut. I-WALL stays out (accepted Q1).
# Symbol layers are read and then kept only when the block is a door or a window (Q3).
KPP1_ORIGIN_MM = (25884.5, 0.0)  # grid axis 1 / axis А, millimetres, from the plan
KPP1_FRAME_SHIFT_M = (-14.655, -5.355)  # minus jobs/KPP1/object.json to_object
KPP1_LAYER_ROLES = {
    "A-DETL-____-THIN": "drop:detail thin line",
    "A-DETL-GENF-OTLN": "drop:detail fill",
    "A-DETL-____-OTLN": "drop:detail outline",
    "A-____-NOTE-TEXT": "drop:note",
    "A-WALL-____-PATT": "hatch",
    "I-WALL-____-MCUT": "drop:interior wall cut, not used as the exterior contour (Q1)",
    "A-WALL-____-MCUT": "wall",
    "I-WALL-____-OTLN": "drop:interior wall outline, not used as the exterior contour (Q1)",
    "A-DOOR-____-OTLN": "symbol",
    "A-FLOR-____-OTLN": "drop:floor outline, not the wall cut",
    "A-GLAZ-CWMG-OTLN": "symbol",
    "S-STRS-____-OTLN": "drop:stair",
    "S-STRS-____-MBND": "drop:stair boundary",
    "A-GLAZ-____-OTLN": "symbol",
    "P-SANR-FIXT-OTLN": "drop:sanitary fixture",
    "I-FURN-____-OTLN": "drop:furniture",
    "A-DETL-____-MBND": "drop:detail boundary",
    "A-WALL-____-OTLN": "drop:wall outline fragments, not the plan cut",
    "A-GENM-____-OTLN": "drop:generic model outline",
    "G-____-____-TEXT": "drop:text",
    "S-GRID-____-IDEN": "drop:grid bubble",
    "S-GRID-____-OTLN": "drop:grid line",
    "G-____-____-SYMB": "drop:symbol",
    "A-____-____-DIMS": "drop:dimension",
    "A-AREA-____-IDEN": "drop:room area tag",
    "G-____-____-DIMS": "drop:dimension",
    "A-DOOR-____-IDEN": "drop:door tag",
    "A-WALL-____-IDEN": "drop:wall tag",
}
_SIZE = re.compile(r"(\d+(?:[.,]\d+)?)\s*[xх×]\s*(\d+(?:[.,]\d+)?)h?", re.IGNORECASE)
_LEVEL = re.compile(r"отм_?\s*([+-]?\d+)[_,.](\d+)")
_U = re.compile(r"\\U\+([0-9A-Fa-f]{4})")


def decode_dxf_text(text: str) -> str:
    """DXF ``\\U+XXXX`` escapes and already-decoded text, to one Unicode string."""
    return _U.sub(lambda m: chr(int(m.group(1), 16)), text or "")


def _role(spec: str) -> tuple[str, str]:
    if spec in ("wall", "symbol", "hatch"):
        return spec, ""
    if isinstance(spec, str) and spec.startswith("drop:"):
        reason = spec[5:].strip()
        if not reason:
            raise ValueError("drop role needs a reason")
        return "drop", reason
    raise ValueError(f"unknown role {spec!r}")


def _finite_point(pt, handle: str) -> tuple[float, float]:
    x, y = float(pt[0]), float(pt[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError(f"handle {handle}: non-finite coordinate")
    return x, y


def _to_m(x_mm: float, y_mm: float, origin_mm, frame_shift_m) -> tuple[float, float]:
    return ((x_mm - origin_mm[0]) * 0.001 + frame_shift_m[0],
            (y_mm - origin_mm[1]) * 0.001 + frame_shift_m[1])


def _segments(entity) -> list[LineString]:
    kind = entity.dxftype()
    handle = entity.dxf.handle
    if kind == "LINE":
        a = _finite_point(entity.dxf.start, handle)
        b = _finite_point(entity.dxf.end, handle)
        if a == b:
            return []
        return [LineString([a, b])]
    if kind == "LWPOLYLINE":
        pts = [_finite_point(p, handle) for p in entity.get_points("xy")]
        if entity.closed and pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        out = []
        for a, b in zip(pts, pts[1:]):
            if a != b:
                out.append(LineString([a, b]))
        return out
    raise ValueError(f"handle {handle}: unsupported {kind} on a wall layer")


def _hatch_area(entity, origin_mm, frame_shift_m):
    """The hatch's boundary paths in metres, even-odd inside one hatch. No area is an error naming it."""
    from ezdxf import path as dxf_path

    handle = str(entity.dxf.handle)
    rings = []
    for boundary in dxf_path.from_hatch(entity):
        pts = [_to_m(*_finite_point(v, handle), origin_mm, frame_shift_m) for v in boundary.flattening(0.5)]
        if len(pts) >= 3:
            ring = Polygon(pts).buffer(0)
            if not ring.is_empty and ring.area > 0:
                rings.append(ring)
    if not rings:
        raise ValueError(f"handle {handle}: hatch has no area")
    area = rings[0]
    for ring in rings[1:]:
        area = area.symmetric_difference(ring)
    if area.is_empty or area.area <= 0:
        raise ValueError(f"handle {handle}: hatch has no area")
    return area


def _split(parts) -> tuple[list[Polygon], list[Polygon]]:
    keep, dropped = [], []
    for part in parts:
        if part.geom_type != "Polygon":
            continue
        part = orient(part, 1.0)
        # exactly 0.5 m2 is not kept; a hair of float noise above 0.5 still counts as the threshold
        if part.area <= MIN_PIECE_M2 + 1e-6:
            dropped.append(part)
        else:
            keep.append(part)
    return keep, dropped


def _close_fill(areas: list, gap_close_m: float):
    """Hatched wall mass grown, outlines filled, shrunk back (contours.py closing), as one geometry.

    This is the area the closed hatch outlines account for: the hatch, the strips that bridge its gaps
    strictly under ``2 * gap_close_m``, and everything those closed outlines enclose.
    """
    radius = float(gap_close_m) - 1e-4
    thick = unary_union([a.buffer(radius, quad_segs=2) for a in areas])
    geoms = list(thick.geoms) if thick.geom_type == "MultiPolygon" else [thick]
    filled = []
    for geom in geoms:
        if geom.geom_type != "Polygon":
            continue
        shrunk = Polygon(geom.exterior).buffer(-radius, quad_segs=2)
        filled.extend(list(shrunk.geoms) if shrunk.geom_type == "MultiPolygon" else [shrunk])
    return unary_union([p for p in filled if not p.is_empty])


def _fill_pieces(areas: list, gap_close_m: float) -> tuple[list[Polygon], list[Polygon]]:
    """Hatched wall mass to plan pieces: the closed fill split into kept and dropped pieces."""
    merged = _close_fill(areas, gap_close_m)
    if merged.is_empty:
        return [], []
    return _split(list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged])


def coverage_check(keep: list, hatch, gap_close_m: float = GAP_CLOSE_M) -> dict:
    """Hatch share under the kept pieces, bbox offset and footprint area the hatch does not account for.

    ``unaccounted_m2`` is the kept footprint minus the hatch closed at the fixed COVERAGE_REF_GAP_CLOSE_M
    (``_close_fill``: outlines plus bridged gap strips, filled), whatever the run's ``gap_close_m`` is; the
    run's value is validated and reported only. It must stay strictly under MAX_UNACCOUNTED_M2. Fail-closed.
    """
    if hatch is None or hatch.is_empty or not hatch.area > 0:
        raise ValueError("coverage: the hatch reference has no area")
    if isinstance(gap_close_m, bool) or not isinstance(gap_close_m, (int, float)) \
            or not math.isfinite(gap_close_m) or gap_close_m <= 1e-4:
        raise ValueError(f"coverage: gap_close_m must be a finite number above 0.0001 m, got {gap_close_m!r}")
    parts = [p for p in keep if not p.is_empty and p.area > 0]
    kept = unary_union(parts) if parts else None
    hatch_area = float(hatch.area)
    if kept is None or kept.is_empty or not kept.area > 0:
        return {"status": "fail", "hatch_area_m2": round(hatch_area, 4), "kept_area_m2": 0.0,
                "covered_share": 0.0, "bbox_delta_m": None, "unaccounted_m2": None, "reason": "no kept piece"}
    share = round(float(kept.intersection(hatch).area) / hatch_area, 9)
    delta = round(max(abs(a - b) for a, b in zip(kept.bounds, hatch.bounds)), 9)
    # the hatch's own closed outlines count exactly; the closing adds the bridged strips and what they enclose
    own = [Polygon(g.exterior) for g in (hatch.geoms if hasattr(hatch, "geoms") else [hatch])
           if g.geom_type == "Polygon"]
    # fixed reference radius, never the run's gap_close_m: a wider run closing must not account for itself
    accounted = unary_union([_close_fill([hatch], COVERAGE_REF_GAP_CLOSE_M), *own])
    extra = kept.difference(accounted) if not accounted.is_empty else kept
    unaccounted = round(float(extra.area), 9)
    ok = (math.isfinite(share) and math.isfinite(delta) and math.isfinite(unaccounted)
          and share > COVERAGE_MIN_SHARE and delta < COVERAGE_BBOX_M and unaccounted < MAX_UNACCOUNTED_M2)
    return {"status": "pass" if ok else "fail", "hatch_area_m2": round(hatch_area, 4),
            "kept_area_m2": round(float(kept.area), 4), "covered_share": share, "bbox_delta_m": delta,
            "hatch_bbox_m": [round(v, 4) for v in hatch.bounds], "kept_bbox_m": [round(v, 4) for v in kept.bounds],
            "accounted_area_m2": round(float(accounted.area), 4), "unaccounted_m2": unaccounted,
            "unaccounted_bbox_m": [round(v, 4) for v in extra.bounds] if not extra.is_empty else None,
            "gap_close_m": gap_close_m, "ref_gap_close_m": COVERAGE_REF_GAP_CLOSE_M,
            "min_share": COVERAGE_MIN_SHARE, "max_bbox_delta_m": COVERAGE_BBOX_M,
            "max_unaccounted_m2": MAX_UNACCOUNTED_M2}


def _pieces(lines: list[LineString], gap_close_m: float) -> tuple[list[Polygon], list[Polygon]]:
    """Closed loops, plus gap-close of gaps strictly under ``2 * gap_close_m``.

    The buffer radius is 0.1 mm under ``gap_close_m``, so a gap of exactly
    ``2 * gap_close_m`` does not join.
    """
    if not lines:
        return [], []
    loops = [p for p in polygonize(lines) if p.geom_type == "Polygon" and p.area > 0]
    # just under gap_close_m, so a gap of exactly 2 * gap_close_m does not meet
    radius = float(gap_close_m) - 1e-4
    thick = unary_union([ln.buffer(radius, quad_segs=2) for ln in lines])
    geoms = list(thick.geoms) if thick.geom_type == "MultiPolygon" else [thick]
    filled = []
    for geom in geoms:
        if geom.geom_type != "Polygon":
            continue
        shrunk = Polygon(geom.exterior).buffer(-radius, quad_segs=2)
        if shrunk.is_empty:
            continue
        parts = list(shrunk.geoms) if shrunk.geom_type == "MultiPolygon" else [shrunk]
        filled.extend(p for p in parts if p.geom_type == "Polygon" and p.area > 0)
    # a bridged part that holds one closed loop keeps that loop, so a traced rectangle stays exact
    chosen, used = [], set()
    for poly in filled:
        cover = poly.buffer(1e-4)
        inside = [i for i, loop in enumerate(loops) if cover.covers(loop.representative_point())]
        if len(inside) == 1:
            chosen.append(loops[inside[0]])
            used.add(inside[0])
        else:
            chosen.append(poly)
    chosen.extend(loop for i, loop in enumerate(loops) if i not in used)
    if not chosen:
        return [], []
    merged = unary_union(chosen)
    if merged.is_empty:
        return [], []
    return _split(list(merged.geoms) if merged.geom_type == "MultiPolygon" else [merged])


def _parse_symbol(name: str) -> tuple[float, float, float] | None:
    """Width, height, level in metres from a block name, or None when the name has no size."""
    size = _SIZE.search(name)
    level = _LEVEL.search(name)
    if not size or not level:
        return None
    width = float(size.group(1).replace(",", ".")) / 1000.0
    height = float(size.group(2).replace(",", ".")) / 1000.0
    z = float(f"{level.group(1)}.{level.group(2)}")
    if not (math.isfinite(width) and math.isfinite(height) and math.isfinite(z) and width > 0 and height > 0):
        return None
    return width, height, z


def _wall_depth(insert: Point, rotation_deg: float, width_m: float, faces: list[LineString]):
    """Signed distances of the two host faces, or None.

    Faces at exactly FACE_LIMIT_M are ignored. The centre must lie strictly between them.
    """
    rot = math.radians(rotation_deg)
    along = (math.cos(rot), math.sin(rot))
    perp = (-along[1], along[0])
    half = width_m / 2.0
    signed = []
    for face in faces:
        a, b = face.coords[0], face.coords[-1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length == 0:
            continue
        direction = (dx / length, dy / length)
        if abs(direction[0] * along[0] + direction[1] * along[1]) < math.cos(math.radians(1.0)):
            continue
        vx, vy = a[0] - insert.x, a[1] - insert.y
        dist = vx * perp[0] + vy * perp[1]
        if not math.isfinite(dist) or abs(dist) >= FACE_LIMIT_M:
            continue
        # the face must overlap the door width, not merely the infinite line
        proj = [(a[0] - insert.x) * along[0] + (a[1] - insert.y) * along[1],
                (b[0] - insert.x) * along[0] + (b[1] - insert.y) * along[1]]
        if max(proj) < -half or min(proj) > half:
            continue
        signed.append(dist)
    pos = [d for d in signed if d > 0]
    neg = [d for d in signed if d < 0]
    if not pos or not neg:
        return None
    return min(pos), max(neg)  # closest face on each side; max(neg) is the least-negative


def _opening_box(width, height, level, insert, rotation, near, far):
    rot = math.radians(rotation)
    along = (math.cos(rot), math.sin(rot))
    perp = (-along[1], along[0])
    half = width / 2.0
    corners = []
    for s in (-half, half):
        for d in (near, far):
            corners.append((insert.x + along[0] * s + perp[0] * d,
                            insert.y + along[1] * s + perp[1] * d))
    xs, ys = zip(*corners)
    return {"min": [min(xs), min(ys), level], "max": [max(xs), max(ys), level + height]}


def _ring(polygon: Polygon) -> dict:
    def coords(ring):
        return [[round(float(x), 6), round(float(y), 6)] for x, y in list(ring.coords)[:-1]]
    return {"exterior": coords(polygon.exterior),
            "holes": [coords(r) for r in polygon.interiors]}


def _parse_levels(levels, z0: float) -> list[float]:
    """Finite, strictly increasing elevations. ``z0`` is the first one. Errors name ``levels_m``."""
    if isinstance(levels, str) or not isinstance(levels, (list, tuple)):
        raise ValueError(f"levels_m must be a list of elevations, got {levels!r}")
    if len(levels) < 2:
        raise ValueError(f"levels_m needs at least two elevations, got {levels!r}")
    out = []
    for i, z in enumerate(levels):
        if isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(float(z)):
            raise ValueError(f"levels_m[{i}] is not finite: {z!r}")
        out.append(float(z))
    for a, b in zip(out, out[1:]):
        if not b > a:
            raise ValueError(f"levels_m must increase, got {a} then {b}")
    if isinstance(z0, bool) or not isinstance(z0, (int, float)) or not math.isfinite(float(z0)):
        raise ValueError(f"z0 is not finite: {z0!r}")
    if float(z0) != out[0]:
        raise ValueError(f"z0 {float(z0)} does not match levels_m[0] {out[0]}")
    return out


def extract_plan(doc, layer_map: dict, *, z0: float, z1: float | None = None,
                 levels_m: list[float] | None = None,
                 opening_insert: str | None = None,
                 opening_decision: str | None = None,
                 origin_mm: tuple[float, float] = (0.0, 0.0),
                 frame_shift_m: tuple[float, float] = (0.0, 0.0),
                 gap_close_m: float = GAP_CLOSE_M, contour_source: str = "lines") -> dict:
    """One sheet's plan account. See the module docstring for the fail-closed rules."""
    if contour_source not in CONTOUR_SOURCES:
        raise ValueError(f"unknown contour_source {contour_source!r}; known: {', '.join(CONTOUR_SOURCES)}")
    if opening_insert not in (None, "centre"):
        raise ValueError(f"unknown opening_insert {opening_insert!r}; known: centre")
    if opening_decision is not None and (not isinstance(opening_decision, str) or not opening_decision.strip()):
        raise ValueError("opening_decision is empty")
    spans = None
    if levels_m is not None:
        if z1 is not None:
            raise ValueError("pass z1 or levels_m, not both")
        levels = _parse_levels(levels_m, z0)
        spans = list(zip(levels, levels[1:]))
        z0 = levels[0]
        runnable = True
        z1 = None
    else:
        if isinstance(z0, bool) or not isinstance(z0, (int, float)) or not math.isfinite(float(z0)):
            raise ValueError(f"z0 is not finite: {z0!r}")
        z0 = float(z0)
        runnable = z1 is not None
        if runnable:
            if isinstance(z1, bool) or not isinstance(z1, (int, float)) or not math.isfinite(float(z1)):
                raise ValueError(f"z1 is not finite: {z1!r}")
            z1 = float(z1)
            if z1 <= z0:
                raise ValueError(f"z1 must be > z0, got {z0}..{z1}")
    roles = {name: _role(spec) for name, spec in layer_map.items()}
    entities = list(doc.modelspace())
    if not entities:
        raise ValueError("empty model space")
    present = {e.dxf.layer for e in entities}
    missing = sorted(present - set(roles))
    if missing:
        raise ValueError(f"unmapped layer {missing[0]}")
    records = []
    wall_lines: list[tuple[str, LineString]] = []
    symbols = []
    hatches = []
    for entity in entities:
        handle = str(entity.dxf.handle)
        layer = entity.dxf.layer
        role, reason = roles[layer]
        kind = entity.dxftype()
        if role == "drop":
            records.append({"handle": handle, "layer": layer, "type": kind, "status": "dropped", "reason": reason})
            continue
        if role == "wall":
            for seg in _segments(entity):
                a = _to_m(seg.coords[0][0], seg.coords[0][1], origin_mm, frame_shift_m)
                b = _to_m(seg.coords[-1][0], seg.coords[-1][1], origin_mm, frame_shift_m)
                wall_lines.append((handle, LineString([a, b])))
            records.append({"handle": handle, "layer": layer, "type": kind, "status": "used", "reason": "wall"})
            continue
        if role == "hatch":
            if kind != "HATCH":
                raise ValueError(f"handle {handle}: unsupported {kind} on a hatch layer")
            hatches.append(_hatch_area(entity, origin_mm, frame_shift_m))
            records.append({"handle": handle, "layer": layer, "type": kind, "status": "used", "reason": "wall hatch"})
            continue
        if kind != "INSERT":
            raise ValueError(f"handle {handle}: unsupported {kind} on a symbol layer")
        _finite_point(entity.dxf.insert, handle)
        symbols.append(entity)
        records.append({"handle": handle, "layer": layer, "type": kind, "status": "used", "reason": "symbol"})

    by_handle: dict[str, list[LineString]] = {}
    for h, ln in wall_lines:
        by_handle.setdefault(h, []).append(ln)
    if contour_source == "hatch":
        if not hatches:
            raise ValueError("contour_source hatch needs a hatch layer with at least one HATCH")
        keep, small = _fill_pieces(hatches, gap_close_m)
    else:
        keep, small = _pieces([ln for _, ln in wall_lines], gap_close_m)
    if hatches:
        coverage = coverage_check(keep, unary_union(hatches), gap_close_m)
        if coverage["status"] != "pass":
            raise ValueError(
                f"coverage: kept {contour_source} pieces cover {coverage['covered_share']:.1%} of the wall hatch "
                f"({coverage['hatch_area_m2']} m2), bbox offset {coverage['bbox_delta_m']} m, "
                f"{coverage['unaccounted_m2']} m2 unaccounted by the closed hatch outlines "
                f"at {coverage.get('unaccounted_bbox_m')}; need > {COVERAGE_MIN_SHARE:.0%}, "
                f"< {COVERAGE_BBOX_M} m and < {MAX_UNACCOUNTED_M2} m2 unaccounted")
    else:
        coverage = {"status": "not measured", "reason": "no hatch layer mapped, no drawn wall mass to compare"}
    if not keep:
        raise ValueError("no plan contour")
    kept_cover = unary_union([p.buffer(1e-6) for p in keep])
    for rec in records:
        if rec["reason"] != "wall":
            continue
        segs = by_handle.get(rec["handle"])
        if not segs:
            rec["status"], rec["reason"] = "dropped", "zero-length wall entity"
            continue
        # the true midpoint of each segment; the entity stays used when any segment is on the kept contour
        if not any(kept_cover.covers(seg.interpolate(0.5, normalized=True)) for seg in segs):
            rec["status"] = "dropped"
            rec["reason"] = ("piece area <= 0.5 m2" if contour_source == "lines"
                             else "wall line outside the kept hatch contour")

    faces = [ln for _, ln in wall_lines]
    openings = []
    for entity in symbols:
        handle = str(entity.dxf.handle)
        rec = next(r for r in records if r["handle"] == handle)
        name = decode_dxf_text(entity.dxf.name)
        if "Дверь" not in name and "Окно" not in name:
            rec["status"], rec["reason"] = "dropped", f"symbol is not a door or window: {name[:80]}"
            continue
        if opening_insert is None:
            rec["status"], rec["reason"] = "dropped", "insert base point not declared"
            continue
        parsed = _parse_symbol(name)
        if parsed is None:
            rec["status"], rec["reason"] = "dropped", f"opening size or level not in the block name: {name[:80]}"
            continue
        width, height, level = parsed
        rotation = float(entity.dxf.rotation)
        if abs(rotation % 90.0) > 0.01 and abs(rotation % 90.0 - 90.0) > 0.01:
            rec["status"], rec["reason"] = "dropped", f"handle {handle}: not axis-aligned ({rotation})"
            continue
        ix, iy = _to_m(entity.dxf.insert.x, entity.dxf.insert.y, origin_mm, frame_shift_m)
        depth = _wall_depth(Point(ix, iy), rotation, width, faces)
        if depth is None:
            rec["status"], rec["reason"] = "dropped", f"handle {handle}: wall depth not found"
            continue
        near, far = depth
        box = _opening_box(width, height, level, Point(ix, iy), rotation, near, far)
        box["min"] = [round(v, 6) for v in box["min"]]
        box["max"] = [round(v, 6) for v in box["max"]]
        box["id"] = handle
        openings.append(box)
        rec["reason"] = "opening"

    handles = [r["handle"] for r in records]
    if len(handles) != len(set(handles)) or len(records) != len(entities):
        raise RuntimeError("entity account does not match the model space")
    rings = [_ring(p) for p in keep]
    dropped = [round(p.area, 4) for p in small]
    if spans is None:
        band = {"z0": z0, "polygons": rings, "dropped_piece_areas_m2": dropped}
        provisional = not runnable
        if runnable:
            band["z1"] = z1
        bands = [band]
        levels_out = [z0, z1] if runnable else [z0]
    else:
        # one plan, one band per storey; each band gets its own ring list
        bands = [{"z0": a, "z1": b, "polygons": copy.deepcopy(rings), "dropped_piece_areas_m2": list(dropped)}
                 for a, b in spans]
        levels_out = [spans[0][0], *[b for _, b in spans]]
        provisional = False
    result = {"schema": "body-contours/1", "synthetic_drawing": False, "provisional": provisional,
              "method": "plan wall lines from a DXF readback (tools/methods/body/plan_from_dxf.py)",
              "units": "m", "source_units": "mm",
              "origin_mm": [origin_mm[0], origin_mm[1]],
              "frame_shift_m": [frame_shift_m[0], frame_shift_m[1]],
              "levels_m": levels_out,
              "bands": bands, "openings": openings, "empty_bands": [], "coverage": coverage,
              "entities": records,
              "params": {"min_piece_m2": MIN_PIECE_M2, "gap_close_m": gap_close_m,
                         "face_limit_m": FACE_LIMIT_M, "opening_insert": opening_insert,
                         "contour_source": contour_source}}
    if opening_decision is not None:
        result["opening_decision"] = opening_decision.strip()
    return result


def sheet_census(doc) -> dict:
    """Titles, viewport scales and model-space layer counts. Read-only."""
    titles = []
    viewports = []
    for layout in doc.layouts:
        if layout.name == "Model":
            continue
        texts = []
        for entity in layout.query("TEXT MTEXT"):
            raw = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
            text = " ".join(decode_dxf_text(raw).replace("\n", " ").split())
            if text:
                texts.append({"layer": entity.dxf.layer, "xy": [round(entity.dxf.insert.x, 1),
                             round(entity.dxf.insert.y, 1)], "text": text[:180]})
        titles.append({"layout": layout.name, "texts": texts})
        for entity in layout.query("VIEWPORT"):
            height = float(entity.dxf.height or 0)
            view_h = float(getattr(entity.dxf, "view_height", 0) or 0)
            scale = round(view_h / height) if height > 1e-6 and view_h > height else None
            viewports.append({"layout": layout.name, "id": entity.dxf.id,
                              "paper_height": round(height, 3), "view_height": round(view_h, 3),
                              "scale": scale, "status": entity.dxf.status})
    layers: dict[str, int] = {}
    for entity in doc.modelspace():
        layers[entity.dxf.layer] = layers.get(entity.dxf.layer, 0) + 1
    return {"layouts": [lay.name for lay in doc.layouts], "paper": titles, "viewports": viewports,
            "model_layers": layers, "model_entities": sum(layers.values())}


def _map_list(items: list[str]) -> dict[str, str]:
    out = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"layer map entry {item!r} needs layer=role")
        layer, spec = item.split("=", 1)
        if not layer:
            raise ValueError("layer map entry has an empty layer")
        out[layer] = spec
    return out


def main(argv=None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from safe_write import Refused, guard_cli, publish_text

    argv = sys.argv[1:] if argv is None else argv
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("extract", "census"))
    parser.add_argument("dxf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("report", type=Path, nargs="?")
    parser.add_argument("--map", action="append", default=[])
    parser.add_argument("--z0", type=float)
    parser.add_argument("--z1", type=float)
    parser.add_argument("--levels", default=None, help="comma-separated elevations in metres, strictly increasing")
    parser.add_argument("--opening-insert", default=None)
    parser.add_argument("--opening-decision", default=None)
    parser.add_argument("--contour-source", default="lines", help="lines (wall lines) or hatch (wall hatch union)")
    parser.add_argument("--origin-mm", default="0,0")
    parser.add_argument("--frame-shift-m", default="0,0")
    args = parser.parse_args(argv)
    outs = [args.output] if args.command == "census" else [args.output, args.report]
    if args.command == "extract" and args.report is None:
        print("extract needs an output and a report path", file=sys.stderr)
        return 2
    try:
        guard_cli([args.dxf], outs)
        import ezdxf
        doc = ezdxf.readfile(args.dxf)
        if args.command == "census":
            publish_text(args.output, json.dumps(sheet_census(doc), ensure_ascii=False, indent=1))
            return 0
        ox, oy = (float(v) for v in args.origin_mm.split(","))
        sx, sy = (float(v) for v in args.frame_shift_m.split(","))
        levels = None
        z0 = args.z0
        if args.levels is not None:
            levels = [float(v) for v in args.levels.split(",") if v.strip()]
            if any(isinstance(v, bool) or not math.isfinite(v) for v in levels):
                raise ValueError(f"levels_m is not finite: {args.levels!r}")
            z0 = levels[0] if z0 is None else z0
        if z0 is None:
            raise ValueError("z0 is not finite: None")
        result = extract_plan(doc, _map_list(args.map), z0=z0, z1=args.z1, levels_m=levels,
                              opening_insert=args.opening_insert, opening_decision=args.opening_decision,
                              origin_mm=(ox, oy), frame_shift_m=(sx, sy), contour_source=args.contour_source)
    except Refused as exc:
        print(f"PLAN_DXF refused: {exc}", file=sys.stderr)
        return 4
    except (ValueError, OSError, KeyError) as exc:
        print(f"PLAN_DXF error: {exc}", file=sys.stderr)
        return 2
    body = {k: v for k, v in result.items() if k != "entities"}
    publish_text(args.output, json.dumps(body, ensure_ascii=False))
    publish_text(args.report, json.dumps({"entities": result["entities"], "provisional": result["provisional"]},
                                        ensure_ascii=False))
    return 0 if not result["provisional"] else 2


if __name__ == "__main__":
    sys.exit(main())
