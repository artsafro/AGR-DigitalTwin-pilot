"""Plan contours + level heights of a building body: the shared "drawing" input of the building-body variants (#727).

Pattern: new-case: level bands and plan contours measured from a source mesh (stand-in for DWG plans + sections).

The benchmark set carries no DWG plan per object, so the drawing input is MEASURED from the benchmark source
mesh, the same way for every variant (this is what a plan + section give: a contour per storey and the level
heights). It is marked `"synthetic_drawing": true` in the JSON: it is not a drawing of the real object.

- Levels: z of horizontal faces (|n.z| >= 0.99) rounded to LEVEL_ROUND_M, kept when their area is at least
  LEVEL_MIN_SHARE of the largest such area; plus the lowest and highest vertex z; levels closer than
  LEVEL_MERGE_M merge into the lower one. A band is the span between two consecutive levels.
- Band contour: plan (XY) polygons from (a) the horizontal sections of every triangle at SECTION_FRACTIONS of
  the band height, grown by GAP_CLOSE_M (round, 2 segments per quarter), outer outlines filled, shrunk back by GAP_CLOSE_M - wall gaps
  (openings) up to 1.5 m close, inner rooms and courtyards are filled (limit) - and (b) the horizontal faces lying at the band's bottom or
  top level; pieces below MIN_PIECE_M2 dropped (listed), the union simplified by SIMPLIFY_M. A band with no
  polygon is listed in `empty_bands` (no guess, no copy from the band below).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient

LEVEL_ROUND_M = 0.05
LEVEL_MIN_SHARE = 0.05
LEVEL_MERGE_M = 0.5
SECTION_FRACTIONS = (0.05, 0.25, 0.5, 0.75, 0.95)
MIN_PIECE_M2 = 0.5
SIMPLIFY_M = 0.02
GAP_CLOSE_M = 0.75
PRECISION_M = 0.001  # coordinates snapped to 1 mm before the GEOS unions (robust and fast)
HORIZONTAL_NZ = 0.99


def soup(rb: dict) -> tuple[np.ndarray, np.ndarray]:
    """World vertices and fan triangles of every non-UCX mesh of a readback."""
    vs, ts, off = [np.zeros((0, 3))], [np.zeros((0, 3), np.int64)], 0
    for m in rb["meshes"]:
        if m["name"].upper().startswith("UCX_"):
            continue
        fg = m["face_geometry"]
        v = np.asarray(fg["vertices"], float).reshape(-1, 3)
        t = np.array([(p[0], p[i], p[i + 1]) for p in fg["polygons"] for i in range(1, len(p) - 1)],
                     np.int64).reshape(-1, 3)
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    v, t = np.concatenate(vs), np.concatenate(ts)
    if not len(t):
        raise ValueError("source has no model triangle")
    if not np.isfinite(v).all():
        raise ValueError("source has a non-finite vertex")
    return v, t


def levels(v: np.ndarray, t: np.ndarray) -> list[float]:
    p = v[t]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = np.linalg.norm(n, axis=1) / 2
    with np.errstate(invalid="ignore", divide="ignore"):
        nz = np.abs(n[:, 2]) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    hor = (nz >= HORIZONTAL_NZ) & (area > 0)
    acc: dict = {}
    for z, a in zip(np.round(p[hor, :, 2].mean(1) / LEVEL_ROUND_M) * LEVEL_ROUND_M, area[hor]):
        acc[round(float(z), 4)] = acc.get(round(float(z), 4), 0.0) + float(a)
    top = max(acc.values()) if acc else 0.0
    zs = sorted({round(float(v[:, 2].min()), 4), round(float(v[:, 2].max()), 4)} |
                {z for z, a in acc.items() if a >= LEVEL_MIN_SHARE * top})
    out = [zs[0]]
    for z in zs[1:]:
        if z - out[-1] >= LEVEL_MERGE_M:
            out.append(z)
    if out[-1] < zs[-1]:  # the top vertex level is never merged away: it ends the last band
        out[-1] = zs[-1]
    return out


def section(v: np.ndarray, t: np.ndarray, z: float) -> list[LineString]:
    p = v[t]
    d = p[:, :, 2] - z
    segs = []
    cross = (d.min(1) < 0) & (d.max(1) > 0)
    for tri, dd in zip(p[cross], d[cross]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (dd[i] < 0) != (dd[j] < 0):
                s = dd[i] / (dd[i] - dd[j])
                pts.append(tuple((tri[i] + s * (tri[j] - tri[i]))[:2]))
        if len(pts) == 2 and pts[0] != pts[1]:
            segs.append(LineString(pts))
    return segs


def band_contour(v, t, z0: float, z1: float) -> tuple[list[Polygon], list[float]]:
    lines = []
    for f in SECTION_FRACTIONS:
        lines += section(v, t, z0 + f * (z1 - z0))
    polys = []
    if lines:  # close wall gaps (openings) up to 2 * GAP_CLOSE_M, keep the outer outline, shrink back
        grid = shapely.set_precision(np.array(lines, dtype=object), PRECISION_M)
        thick = shapely.union_all(shapely.buffer(grid, GAP_CLOSE_M, quad_segs=2))  # per-segment buffers: fast in GEOS
        filled = shapely.union_all([Polygon(q.exterior) for q in shapely.get_parts(thick) if q.geom_type == "Polygon"])
        polys = [q for q in shapely.get_parts(filled.buffer(-GAP_CLOSE_M, quad_segs=2)) if q.geom_type == "Polygon"]
    p = v[t]
    n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    ln = np.linalg.norm(n, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        nz = np.abs(n[:, 2]) / np.maximum(ln, 1e-12)
    zc = p[:, :, 2].mean(1)
    flat = (nz >= HORIZONTAL_NZ) & (ln > 0) & ((np.abs(zc - z0) < LEVEL_ROUND_M) | (np.abs(zc - z1) < LEVEL_ROUND_M))
    polys += [Polygon(tri[:, :2]) for tri in p[flat]]
    polys = [q for q in polys if q.area > 0]
    if not polys:
        return [], []
    merged = shapely.union_all(shapely.set_precision(np.array(polys, dtype=object), PRECISION_M)).simplify(SIMPLIFY_M)
    keep, dropped = [], []
    for q in shapely.get_parts(merged):
        if q.geom_type != "Polygon":
            continue
        q = Polygon(q.exterior, [r for r in q.interiors if Polygon(r).area >= MIN_PIECE_M2])
        (keep if q.area >= MIN_PIECE_M2 else dropped).append(q)
    return [orient(q, 1.0) for q in keep], [round(q.area, 4) for q in dropped]


def contours(rb: dict) -> dict:
    v, t = soup(rb)
    lv = levels(v, t)
    bands, empty = [], []
    for z0, z1 in zip(lv, lv[1:]):
        polys, dropped = band_contour(v, t, z0, z1)
        if not polys:
            empty.append([z0, z1])
            continue
        bands.append({"z0": z0, "z1": z1, "dropped_piece_areas_m2": dropped,
                      "polygons": [{"exterior": [list(map(float, c)) for c in q.exterior.coords[:-1]],
                                    "holes": [[list(map(float, c)) for c in r.coords[:-1]] for r in q.interiors]}
                                   for q in polys]})
    if not bands:
        raise ValueError("no band gave a plan contour")
    return {"schema": "body-contours/1", "synthetic_drawing": True,
            "method": "levels from horizontal-face area, contours from closed sections (tools/methods/body/contours.py)",
            "levels_m": lv, "bands": bands, "empty_bands": empty,
            "params": {"level_round_m": LEVEL_ROUND_M, "level_min_share": LEVEL_MIN_SHARE,
                       "level_merge_m": LEVEL_MERGE_M, "section_fractions": list(SECTION_FRACTIONS),
                       "min_piece_m2": MIN_PIECE_M2, "simplify_m": SIMPLIFY_M, "gap_close_m": GAP_CLOSE_M}}


def polygons(band: dict) -> list[Polygon]:
    out = []
    for p in band["polygons"]:
        q = Polygon(p["exterior"], p["holes"])
        if not q.is_valid or q.area <= 0 or not all(math.isfinite(c) for c in q.bounds):
            raise ValueError(f"band {band['z0']}..{band['z1']}: invalid contour")
        out.append(q)
    return out


if __name__ == "__main__":
    rb = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    Path(sys.argv[2]).write_text(json.dumps(contours(rb)), encoding="utf-8")
