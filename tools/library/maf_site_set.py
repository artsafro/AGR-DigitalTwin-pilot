"""Pure helpers for the Vatutino site MAF set (#313): dimension verdict, budget, UV slots, table-top.

Pattern: new-case: site MAF set assembly - dimension verdict with plan swap and recorded user exception,
NPM/VPM budget against the MAF share [D097], per-material UV-slot measurement, dominant upward plane.
No bpy import: the Blender build script (tools/blender/maf_site_set_build.py) loads this file by path.
The dimension tolerance follows [D094] and twinqa.maf_checks: a deviation equal to 0.1 m passes.
"""

from __future__ import annotations

import math

DIMENSION_TOL_M = 0.10  # [D094]
NPM_MAF_SHARE = 60_000  # [D097], MAF-07: planning share of the shared 180 000 NPM Ground budget
_EPS = 1e-9


def _finite(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _measured(value) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("measured size must be three finite positive numbers")
    if any(not _finite(v) or v <= 0 for v in value):
        raise ValueError("measured size must be three finite positive numbers")
    return [float(v) for v in value]


def _schedule(value) -> list[float | None]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("schedule size must have three entries (None = missing)")
    out: list[float | None] = []
    for v in value:
        if v is None:
            out.append(None)
        elif not _finite(v) or v <= 0:
            raise ValueError("schedule size entries must be finite positive numbers or None")
        else:
            out.append(float(v))
    if all(v is None for v in out):
        raise ValueError("schedule size has no known axis")
    return out


def _deviations(meas, spec):
    return [None if s is None else abs(m - s) for m, s in zip(meas, spec)]


def _worst(devs):
    known = [d for d in devs if d is not None]
    return max(known) if known else 0.0


def dimension_verdict(measured, schedule, tol_m: float = DIMENSION_TOL_M, exception: str | None = None) -> dict:
    """Measured L/W/H vs schedule L/W/H (m). Plan L/W may swap; height never swaps.

    pass: every known axis within tol and no axis missing; review: an axis is missing, or a user exception
    is recorded (an exception never yields pass); fail: a known axis exceeds tol.
    """
    meas = _measured(measured)
    spec = _schedule(schedule)
    straight = _deviations(meas, spec)
    swapped_meas = [meas[1], meas[0], meas[2]]
    swapped = _deviations(swapped_meas, spec)
    use_swap = _worst(swapped[:2]) < _worst(straight[:2]) - _EPS
    devs, aligned = (swapped, swapped_meas) if use_swap else (straight, meas)
    over = any(d is not None and d > tol_m + _EPS for d in devs)
    missing = any(d is None for d in devs)
    if exception:
        verdict, reason = "review", f"user exception: {exception}" + (" (outside tolerance)" if over else "")
    elif over:
        verdict, reason = "fail", f"deviation above {tol_m:g} m"
    elif missing:
        verdict, reason = "review", "schedule size missing on an axis"
    else:
        verdict, reason = "pass", f"all axes within {tol_m:g} m"
    return {"aligned_m": aligned, "deviation_m": devs, "plan_axes_swapped": use_swap,
            "verdict": verdict, "reason": reason}


def _count(value, label) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def budget(rows, npm_share: int = NPM_MAF_SHARE) -> dict:
    """Triangles raw / NPM / VPM x instances; NPM total against the MAF share. Overrun lists the causes."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("budget needs at least one position")
    out_rows, raw_t, npm_t, vpm_t = [], 0, 0, 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("budget row must be an object")
        n = _count(row.get("instances"), "instances")
        raw = _count(row.get("tris_raw"), "tris_raw")
        npm = _count(row.get("tris_npm"), "tris_npm")
        vpm = _count(row.get("tris_vpm"), "tris_vpm")
        item = {"set_id": row.get("set_id"), "instances": n, "tris_raw": raw, "tris_npm": npm, "tris_vpm": vpm,
                "raw_total": raw * n, "npm_total": npm * n, "vpm_total": vpm * n}
        out_rows.append(item)
        raw_t += raw * n
        npm_t += npm * n
        vpm_t += vpm * n
    within = npm_t <= npm_share
    overrun = [] if within else sorted(out_rows, key=lambda r: -r["npm_total"])
    return {"rows": out_rows, "raw_total": raw_t, "npm_total": npm_t, "vpm_total": vpm_t,
            "npm_share": npm_share, "npm_within_share": within,
            "overrun_tris": max(0, npm_t - npm_share), "overrun": overrun}


def uv_slot_report(faces, rects: dict, eps: float = 1e-6) -> dict:
    """Count faces whose UV corners leave their material's atlas rect [u0, v0, u1, v1].

    A face with an unknown material, no corners or a non-finite UV counts as outside.
    """
    if not faces:
        raise ValueError("no faces to measure")
    mats: dict[str, dict] = {}
    total_out = 0
    for material, uvs in faces:
        key = str(material)
        entry = mats.setdefault(key, {"faces": 0, "outside": 0, "uv_min": None, "uv_max": None})
        entry["faces"] += 1
        rect = rects.get(material) if material is not None else None
        bad = rect is None or not uvs
        for uv in uvs or ():
            u, v = uv
            if not (_finite(u) and _finite(v)):
                bad = True
                continue
            lo, hi = entry["uv_min"], entry["uv_max"]
            entry["uv_min"] = [u, v] if lo is None else [min(lo[0], u), min(lo[1], v)]
            entry["uv_max"] = [u, v] if hi is None else [max(hi[0], u), max(hi[1], v)]
            if rect is not None and not (rect[0] - eps <= u <= rect[2] + eps and rect[1] - eps <= v <= rect[3] + eps):
                bad = True
        if bad:
            entry["outside"] += 1
            total_out += 1
    return {"faces": sum(m["faces"] for m in mats.values()), "faces_outside": total_out, "materials": mats}


def remap_into_rect(t, rect, inset: float = 0.0) -> tuple[float, float]:
    """Map a normalised (s, t) in [0, 1]^2 into rect [u0, v0, u1, v1] (with an optional inset)."""
    s, q = t
    if not (_finite(s) and _finite(q)) or not (0.0 <= s <= 1.0 and 0.0 <= q <= 1.0):
        raise ValueError("normalised coordinate must be finite and inside [0, 1]")
    u0, v0, u1, v1 = rect
    du, dv = (u1 - u0) * inset, (v1 - v0) * inset
    return (u0 + du + s * (u1 - u0 - 2 * du), v0 + dv + q * (v1 - v0 - 2 * dv))


def dominant_up_plane(faces, bin_m: float = 0.005, min_nz: float = 0.99) -> float:
    """Height of the largest-area upward horizontal plane. faces = (z, area, normal_z)."""
    bins: dict[int, list[float]] = {}
    for z, area, nz in faces:
        if not (_finite(z) and _finite(area) and _finite(nz)) or nz < min_nz or area <= 0:
            continue
        key = int(round(z / bin_m))
        acc = bins.setdefault(key, [0.0, 0.0])
        acc[0] += area
        acc[1] += area * z
    if not bins:
        raise ValueError("no upward horizontal faces")
    # merge neighbouring bins so a plane split by rounding is not undercounted
    best_key = max(bins, key=lambda k: sum(bins.get(k + d, [0.0, 0.0])[0] for d in (-1, 0, 1)))
    area = sum(bins.get(best_key + d, [0.0, 0.0])[0] for d in (-1, 0, 1))
    zsum = sum(bins.get(best_key + d, [0.0, 0.0])[1] for d in (-1, 0, 1))
    return zsum / area


def _tet(o, a, b, c):
    ax, ay, az = a[0] - o[0], a[1] - o[1], a[2] - o[2]
    bx, by, bz = b[0] - o[0], b[1] - o[1], b[2] - o[2]
    cx, cy, cz = c[0] - o[0], c[1] - o[1], c[2] - o[2]
    return (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0


def orient_outward(coords, polygons) -> set[int]:
    """Faces to reverse so every component winds consistently and outward (volume about the bottom centre > 0).

    Mirrors the readback rule of twinqa.geometry.maf_surface.surface_facts: adjacency over edges shared by
    exactly two faces (vertex ids are already welded), outward by the signed volume about the component's
    bottom centre; a flat component (|volume| tiny) is left as it is.
    """
    edges: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    for fi, poly in enumerate(polygons):
        m = len(poly)
        for k in range(m):
            a, b = poly[k], poly[(k + 1) % m]
            if a != b:
                edges.setdefault((min(a, b), max(a, b)), []).append((fi, a, b))
    adj: dict[int, list[tuple[int, bool]]] = {}
    for occ in edges.values():
        if len(occ) != 2 or occ[0][0] == occ[1][0]:
            continue
        (f0, s0, e0), (f1, s1, e1) = occ
        same = (s0, e0) == (s1, e1)  # same direction = inconsistent winding
        adj.setdefault(f0, []).append((f1, same))
        adj.setdefault(f1, []).append((f0, same))
    flips: set[int] = set()
    seen: set[int] = set()
    for seed in range(len(polygons)):
        if seed in seen:
            continue
        flip = {seed: False}
        order = [seed]
        seen.add(seed)
        i = 0
        while i < len(order):
            face = order[i]
            i += 1
            for other, same in adj.get(face, ()):
                if other not in flip:
                    flip[other] = flip[face] ^ same
                    seen.add(other)
                    order.append(other)
        pts_all = [coords[j] for f in order for j in polygons[f]]
        xs = [p[0] for p in pts_all]
        ys = [p[1] for p in pts_all]
        zs = [p[2] for p in pts_all]
        origin = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, min(zs))
        diag = math.sqrt((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2 + (max(zs) - min(zs)) ** 2)
        volume = 0.0
        for f in order:
            pts = [coords[j] for j in polygons[f]]
            if flip[f]:
                pts.reverse()
            for k in range(1, len(pts) - 1):
                volume += _tet(origin, pts[0], pts[k], pts[k + 1])
        if abs(volume) <= 1e-9 or abs(volume) <= 1e-6 * diag ** 3:
            flips.update(f for f in order if flip[f])  # still make the winding consistent
            continue
        outward_is_propagated = volume > 0
        flips.update(f for f in order if flip[f] == outward_is_propagated)
    return flips


class MaterialMapError(ValueError):
    """A position's material_map does not cover its source materials or names a material outside the atlas."""

    def __init__(self, missing, unknown_targets, message):
        super().__init__(message)
        self.missing = list(missing)
        self.unknown_targets = list(unknown_targets)


def resolve_material_map(source_names, material_map: dict, atlas_names) -> dict:
    """Return {source material name: atlas material} for every source name, or raise MaterialMapError.

    A source name absent from the map is covered only by an explicit "*" entry; there is no implicit
    fallback, so an incomplete map never silently becomes the first atlas colour (#313 review P1).
    Every target, including "*", must be an atlas material.
    """
    names = list(dict.fromkeys(str(n) for n in source_names))
    if not names:
        raise MaterialMapError([], [], "no source materials to map")
    atlas = set(atlas_names)
    unknown = sorted({str(t) for t in material_map.values()} - atlas)
    wildcard = material_map.get("*")
    missing = [n for n in names if n not in material_map and wildcard is None]
    if missing or unknown:
        parts = []
        if missing:
            parts.append("source materials without a mapping (no '*'): " + ", ".join(missing))
        if unknown:
            parts.append("targets not in the atlas: " + ", ".join(unknown))
        raise MaterialMapError(missing, unknown, "; ".join(parts))
    return {n: material_map.get(n, wildcard) for n in names}
