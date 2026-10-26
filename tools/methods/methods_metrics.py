"""Metric functions behind tools/methods/run_variant.py (methods catalog, #706).

Pattern: new-case: one comparable metric row per variant output (methods catalog #706).
Pure numpy / stdlib; inputs are the Blender readback (tools/blender/fbx_readback.py) and the methods
extra readback (tools/methods/extra_readback_blender.py). Every metric is measured or `null` with a
`reason`; nothing is guessed. Shared checker thresholds are imported, never redefined here:
xView 2 mm / 5 mm / cos 0.9999 (0.81 deg) from dt_ai.ops.inv_xview, UCX checks from twinqa.scene.
"""
from __future__ import annotations

import math
import statistics

import numpy as np

from dt_ai.geometry.ucx_build import _flood_exterior, sample_surface
from dt_ai.ops.inv_xview import tolerance_for
from dt_ai.ops.inv_xview import mesh_report as xview_mesh_report
from twinqa.geometry.ucx_audit import weld
from twinqa.scene import _texture_side_px, _ucx_piece, scene_findings, ucx_triangle_limit
from twinqa.uv import edge_densities

SCHEMA = "methods-row/1"
CLASSES = ("building-body", "windows-glazing", "ground-terrain", "ucx-collisions", "texturing-by-drawings",
           "sources")
FIT_MAX_POINTS = 60_000  # model surface samples for the UCX fit (deterministic stride above this)
FIT_MAX_PAIRS = 400_000_000  # point x triangle pairs for exact outside distances (stride above this)
FIT_MAX_CELLS = 3_000_000  # voxel cells for the volume figures (cell grows above this)
ENVELOPE_CLOSE_M = 1.0  # voxel closing radius for the model envelope (closes openings up to 2 m)
DEVIATION_STEPS_M = (0.10, 0.30, 1.00)  # R11 / R12 / R13 tolerances (reg p.36 §13.5, [D134]) as shares only
SSIM_METHOD = ("SSIM, luma (ITU-R 601) of RGB, 7x7 uniform window, C1=(0.01)^2, C2=(0.03)^2, mean over the "
               "image; render and reference must have the same size and view (aligned renders, no resampling); "
               "value = mean over the benchmark's reference views")


class MetricError(ValueError):
    """Input that cannot be measured honestly (partial, unmapped, mismatched)."""


def is_ucx(name: str) -> bool:
    return name.upper().startswith("UCX_")


def model_meshes(rb: dict) -> list[dict]:
    return [m for m in rb["meshes"] if not is_ucx(m["name"])]


def ucx_meshes(rb: dict) -> list[dict]:
    return [m for m in rb["meshes"] if is_ucx(m["name"])]


def counts(rb: dict) -> tuple[dict, dict]:
    model, ucx = model_meshes(rb), ucx_meshes(rb)
    triangles = {"model": int(sum(m["triangles"] for m in model)), "ucx": int(sum(m["triangles"] for m in ucx))}
    objects = {"meshes": len(rb["meshes"]), "model": len(model), "ucx": len(ucx),
               "other": len(rb.get("other_objects") or [])}
    return triangles, objects


def xview(rb: dict, profile: str = "VPM") -> dict:
    """xView Overlapping Vertices / Faces on every non-UCX mesh, shared thresholds (never changed here)."""
    tol = tolerance_for(profile)
    per, verts, faces = {}, 0, 0
    for m in model_meshes(rb):
        fg = m["face_geometry"]
        r = xview_mesh_report(fg["vertices"], fg["polygons"], profile, part=m["name"])
        per[m["name"]] = {"vertex_pairs": r["vertex_pairs"], "face_pairs": r["face_pairs"]}
        verts += r["vertex_pairs"]
        faces += r["face_pairs"]
    if not per:
        return {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min,
                "overlapping_vertices": None, "overlapping_faces": None, "passed": None, "reason": "no model mesh"}
    return {"vertex_m": tol.vertex_m, "face_m": tol.face_m, "parallel_cos_min": tol.parallel_cos_min,
            "overlapping_vertices": verts, "overlapping_faces": faces, "passed": verts == 0 and faces == 0,
            "per_mesh": per}


def ucx_check(rb: dict, profile: dict) -> dict:
    """V010 (presence, slots, budget, intersections, coverage, advisory gap) + V012 UCX names, plus closed/convex.

    status: fail = any gating finding fails; pass = every gating finding passes; open = no fail but a
    gating finding is not_run / review. Advisory findings never decide the status.
    """
    found = scene_findings(rb, "vpm", "oks", profile)
    checks = {}
    for stage in ("V010", "V012"):
        for f in found.get(stage, []):
            if stage == "V012" and "UCX" not in f.name:
                continue
            checks[f.name] = f.status
    gating = {k: v for k, v in checks.items() if "advisory" not in k}
    if not gating:
        status = "open"
    elif any(v == "fail" for v in gating.values()):
        status = "fail"
    elif all(v == "pass" for v in gating.values()):
        status = "pass"
    else:
        status = "open"
    ucx = ucx_meshes(rb)
    reasons = {}
    for m in ucx:
        r = _ucx_piece(m)["reason"] or "ok"
        reasons[r] = reasons.get(r, 0) + 1
    model_tris, _ = counts(rb)
    return {"status": status, "checks": checks, "pieces": len(ucx), "closed_convex": reasons.get("ok", 0),
            "piece_reasons": reasons, "limit_triangles": ucx_triangle_limit(model_tris["model"]),
            "triangles": model_tris["ucx"]}


def _udim(uv) -> int | None:
    u = sum(p[0] for p in uv) / len(uv)
    v = sum(p[1] for p in uv) / len(uv)
    return 1001 + int(math.floor(u)) + 10 * int(math.floor(v)) if 0 <= u < 10 and v >= 0 else None


def texel(rb: dict, tile_sides: dict | None = None) -> dict:
    """px/m over every polygon edge of every non-UCX mesh (twinqa.uv.edge_densities); null when not readable.

    Texture side: the readback's single square diffuse size (twinqa.scene rule); else, for a package,
    `tile_sides` = {UDIM tile or None (untiled): side px} read from its diffuse PNGs, applied per polygon by
    the UDIM tile of its UV centre. A polygon on a tile without a diffuse PNG gives null naming the tile."""
    side = _texture_side_px(rb)
    source = "readback"
    if side is None and tile_sides:
        source = "package diffuse PNG"
    elif side is None:
        return {"min_px_m": None, "median_px_m": None, "texture_px": None,
                "reason": "no single square diffuse texture size in the readback"}
    values, used = [], set()
    for m in model_meshes(rb):
        fg = m["face_geometry"]
        puv = fg.get("polygon_uv")
        if puv is None or len(puv) != len(fg["polygons"]):
            return {"min_px_m": None, "median_px_m": None, "texture_px": side, "reason": f"no corner UV on {m['name']}"}
        for poly, uv in zip(fg["polygons"], puv):
            px = side
            if px is None:
                tile = _udim(uv) if None not in tile_sides else None
                if tile not in tile_sides:
                    return {"min_px_m": None, "median_px_m": None, "texture_px": None,
                            "reason": f"{m['name']}: UV tile {tile} has no diffuse PNG in the package"}
                px = tile_sides[tile]
            used.add(px)
            values.extend(edge_densities([fg["vertices"][i] for i in poly], uv, px))
    values = [x for x in values if math.isfinite(x)]
    if not values:
        return {"min_px_m": None, "median_px_m": None, "texture_px": side, "reason": "no measurable edge"}
    return {"min_px_m": round(min(values), 3), "median_px_m": round(statistics.median(values), 3),
            "texture_px": side if side is not None else sorted(used), "texture_px_source": source,
            "edges": len(values), "reason": None}


def package_tile_sides(folder) -> dict | None:
    """{UDIM tile | None: square side px} of the diffuse PNGs (`*Diffuse*` / `*_d_*`) in an extracted package.
    None when there is none; a non-square or duplicated tile raises MetricError naming the file."""
    import re
    from pathlib import Path

    from PIL import Image

    out = {}
    for png in sorted(Path(folder).rglob("*.png")):
        if not re.search(r"(?i)(diffuse|_d_\d)", png.stem):
            continue
        tile_m = re.search(r"\.(1\d{3})$", png.stem)
        tile = int(tile_m.group(1)) if tile_m else None
        with Image.open(png) as im:
            w, h = im.size
        if w != h:
            raise MetricError(f"diffuse {png.name} is not square ({w}x{h})")
        if tile in out:
            raise MetricError(f"two diffuse PNGs for tile {tile} ({png.name})")
        out[tile] = w
    if None in out and len(out) > 1:
        raise MetricError("package mixes tiled and untiled diffuse PNGs")
    return out or None


def matid(rb: dict, extra: dict) -> dict:
    """Material-slot integrity per mesh: every used material_index has a slot with a material; no unused
    slot on a model mesh; UCX has no slot. A mesh missing from the extra readback is an error by name."""
    if not extra or not extra.get("ok"):
        return {"passed": None, "problems": [], "reason": "no extra readback"}
    problems, checked = [], 0
    for m in rb["meshes"]:
        info = extra["meshes"].get(m["name"])
        if info is None:
            raise MetricError(f"mesh {m['name']!r} missing from the extra readback")
        checked += 1
        slots, used = info["slots"], {int(k): v for k, v in info["polygons_by_material_index"].items()}
        if is_ucx(m["name"]):
            if slots:
                problems.append(f"{m['name']}: UCX has {len(slots)} material slot(s)")
            continue
        for idx in sorted(used):
            if idx >= len(slots):
                problems.append(f"{m['name']}: {used[idx]} polygon(s) use material index {idx} without a slot")
            elif slots[idx] is None:
                problems.append(f"{m['name']}: slot {idx} is empty but used by {used[idx]} polygon(s)")
        unused = [i for i in range(len(slots)) if i not in used]
        if unused:
            problems.append(f"{m['name']}: unused slot(s) {unused}")
    return {"passed": not problems, "problems": problems, "meshes_checked": checked,
            "material_ids": sorted({mid for m in model_meshes(rb)
                                    for mid in map(int, extra["meshes"][m["name"]]["polygons_by_material_index"])})}


# ---- UCX fit (class ucx-collisions) -------------------------------------------------------------------------------

def _model_triangles(rb: dict, extra: dict | None):
    vs, ts, off = [], [], 0
    for m in model_meshes(rb):
        v = np.asarray(m["face_geometry"]["vertices"], float).reshape(-1, 3)
        if extra and extra.get("ok"):
            t = np.asarray(extra["meshes"][m["name"]]["tris"], np.int64).reshape(-1, 3)
        else:  # fan triangulation of the readback polygons
            t = np.array([(p[0], p[i], p[i + 1]) for p in m["face_geometry"]["polygons"]
                          for i in range(1, len(p) - 1)], np.int64).reshape(-1, 3)
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    if not vs:
        raise MetricError("no model mesh")
    return np.concatenate(vs), np.concatenate(ts)


def _pieces(rb: dict):
    out = []
    for m in ucx_meshes(rb):
        hull = m.get("hull") or {}
        if not hull.get("verts") or not hull.get("tris"):
            raise MetricError(f"UCX {m['name']!r} has no hull in the readback")
        wv, wt = weld(hull["verts"], hull["tris"])
        v, t = np.asarray(wv, float).reshape(-1, 3), np.asarray(wt, np.int64).reshape(-1, 3)
        n = np.cross(v[t[:, 1]] - v[t[:, 0]], v[t[:, 2]] - v[t[:, 0]])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-12
        n = n[ok] / ln[ok, None]
        c = v.mean(axis=0)
        d = np.einsum("ij,ij->i", n, v[t[ok, 0]])
        flip = (n @ c - d) > 0  # centroid must be on the inner side
        n[flip], d[flip] = -n[flip], -d[flip]
        out.append({"name": m["name"], "v": v, "t": t, "n": n, "d": d, "lo": v.min(axis=0), "hi": v.max(axis=0)})
    return out


def _inside_any(points: np.ndarray, pieces, tol: float = 1e-6) -> np.ndarray:
    inside = np.zeros(len(points), bool)
    for p in pieces:
        box = np.all((points >= p["lo"] - tol) & (points <= p["hi"] + tol), axis=1) & ~inside
        if box.any():
            q = points[box]
            inside[np.nonzero(box)[0][np.all(q @ p["n"].T - p["d"] <= tol, axis=1)]] = True
    return inside


def point_triangle_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Exact distances, broadcasting p (..., 3) against triangles a, b, c (..., 3) (Ericson, closest point)."""
    p, a, b, c = np.broadcast_arrays(p, a, b, c)
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = (ab * ap).sum(-1), (ac * ap).sum(-1)
    bp = p - b
    d3, d4 = (ab * bp).sum(-1), (ac * bp).sum(-1)
    cp = p - c
    d5, d6 = (ab * cp).sum(-1), (ac * cp).sum(-1)
    va, vb, vc = d3 * d6 - d5 * d4, d5 * d2 - d1 * d6, d1 * d4 - d3 * d2
    with np.errstate(divide="ignore", invalid="ignore"):
        denom = va + vb + vc
        v = np.where(denom != 0, vb / denom, 0.0)
        w = np.where(denom != 0, vc / denom, 0.0)
        q = a + ab * v[..., None] + ac * w[..., None]  # interior
        t_ab = np.clip(np.where((d1 - d3) != 0, d1 / (d1 - d3), 0), 0, 1)
        t_ac = np.clip(np.where((d2 - d6) != 0, d2 / (d2 - d6), 0), 0, 1)
        t_bc = np.clip(np.where(((d4 - d3) + (d5 - d6)) != 0, (d4 - d3) / ((d4 - d3) + (d5 - d6)), 0), 0, 1)
    cand = np.stack([q, a, b, c, a + ab * t_ab[..., None], a + ac * t_ac[..., None],
                     b + (c - b) * t_bc[..., None]])
    region_interior = (va > 0) & (vb > 0) & (vc > 0)
    dist = np.linalg.norm(cand - p[None], axis=-1)
    dist[0] = np.where(region_interior, dist[0], np.inf)
    return dist.min(axis=0)


def _samples(v, t, max_points: int):
    spacing, pts = 0.25, np.zeros((0, 3))
    for _ in range(12):
        pts = np.unique(np.round(sample_surface(v, t, spacing), 4), axis=0)
        if len(pts) <= max_points:
            return pts, spacing, 1
        spacing *= 1.5
    stride = math.ceil(len(pts) / max_points)
    return pts[::stride], spacing, stride


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    """Chebyshev (cube) dilation by r cells."""
    out = mask.copy()
    for axis in range(3):
        for _ in range(r):
            grow = out.copy()
            sl_a, sl_b = [slice(None)] * 3, [slice(None)] * 3
            sl_a[axis], sl_b[axis] = slice(1, None), slice(None, -1)
            grow[tuple(sl_a)] |= out[tuple(sl_b)]
            grow[tuple(sl_b)] |= out[tuple(sl_a)]
            out = grow
    return out


def _envelope(surface: np.ndarray, r: int) -> np.ndarray:
    """Model envelope: closing of the surface cells by r, then the cells the exterior flood cannot reach."""
    pad = np.pad(surface, r + 1)
    ext = _flood_exterior(_dilate(pad, r))
    solid = ~_dilate(ext, r)
    return solid[(slice(r + 1, -(r + 1)),) * 3] | surface


def ucx_fit(rb: dict, extra: dict | None, max_points: int = FIT_MAX_POINTS) -> dict:
    """One-sided model -> UCX deviation [D134] and voxel volume figures. Measurement only: no R11-R13
    zone classification (pedestrian / Ground) is made, so the shares are not a tolerance verdict."""
    v, t = _model_triangles(rb, extra)
    pieces = _pieces(rb)
    if not pieces:
        return {"reason": "no UCX piece", "model_to_ucx_max_m": None}
    pts, spacing, stride = _samples(v, t, max_points)
    inside = _inside_any(pts, pieces)
    out_pts = pts[~inside]
    tri = np.concatenate([p["v"][p["t"]] for p in pieces])
    dist = np.zeros(len(pts))
    dstride = max(1, math.ceil(len(out_pts) * len(tri) / FIT_MAX_PAIRS))
    sel = np.nonzero(~inside)[0][::dstride]
    best = np.full(len(sel), np.inf)
    chunk = max(1, 500_000 // max(1, len(tri)))
    for s in range(0, len(sel), chunk):
        q = pts[sel[s:s + chunk]][:, None, :]
        best[s:s + chunk] = point_triangle_distance(q, tri[None, :, 0], tri[None, :, 1], tri[None, :, 2]).min(axis=1)
    measured = np.zeros(len(pts), bool)
    measured[inside] = True
    measured[sel] = True
    dist[sel] = best
    d = dist[measured]
    # voxel volumes on one world grid: model solid = surface cells + enclosed cells (exterior flood fill)
    cell = 0.25
    lo, hi = np.minimum(v.min(0), np.min([p["lo"] for p in pieces], 0)), np.maximum(
        v.max(0), np.max([p["hi"] for p in pieces], 0))
    while np.prod(np.ceil((hi - lo) / cell) + 3) > FIT_MAX_CELLS:
        cell *= 1.25
    origin = lo - cell
    dims = (np.ceil((hi - origin) / cell).astype(np.int64) + 2)
    surf_pts = sample_surface(v, t, cell / 2)
    idx = np.clip(np.floor((surf_pts - origin) / cell).astype(np.int64), 0, dims - 1)
    surface = np.zeros(tuple(dims), bool)
    surface[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    solid = _envelope(surface, max(1, round(ENVELOPE_CLOSE_M / cell)))
    centres = origin + (np.argwhere(np.ones(tuple(dims), bool)) + 0.5) * cell
    in_ucx = _inside_any(centres, pieces).reshape(tuple(dims))
    cv = cell ** 3
    ucx_m3, model_m3 = float(in_ucx.sum() * cv), float(solid.sum() * cv)
    excess_m3 = float((in_ucx & ~solid).sum() * cv)
    hollow_m3 = float((solid & ~in_ucx).sum() * cv)
    return {
        "method": "model surface samples -> union of UCX pieces (0 inside); exact point-triangle distance; "
                  "volumes by voxel centres; model envelope = surface cells closed by ENVELOPE_CLOSE_M (morphological "
                  "closing: openings up to 2 m such as windows and doors are closed, wider courtyards stay open)",
        "samples": int(len(pts)), "sample_spacing_m": round(spacing, 4), "sample_stride": stride,
        "distance_stride": dstride, "measured_samples": int(measured.sum()),
        "model_to_ucx_max_m": round(float(d.max()), 4), "model_to_ucx_p95_m": round(float(np.percentile(d, 95)), 4),
        "share_over_m": {f"{x:.2f}": round(float((d > x).mean()), 5) for x in DEVIATION_STEPS_M},
        "voxel_m": round(cell, 4), "ucx_volume_m3": round(ucx_m3, 3), "model_envelope_m3": round(model_m3, 3),
        "ucx_outside_model_m3": round(excess_m3, 3),
        "ucx_outside_share": round(excess_m3 / ucx_m3, 4) if ucx_m3 > 0 else None,
        "envelope_uncovered_m3": round(hollow_m3, 3),
        "envelope_uncovered_share": round(hollow_m3 / model_m3, 4) if model_m3 > 0 else None,
        "reason": None,
    }


# ---- render vs reference --------------------------------------------------------------------------------------------

def _luma(path) -> np.ndarray:
    from PIL import Image

    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=float) / 255.0
    return rgb @ np.array([0.299, 0.587, 0.114])


def _box(x: np.ndarray, k: int) -> np.ndarray:
    c = np.pad(x, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)


def ssim(a: np.ndarray, b: np.ndarray, k: int = 7) -> float:
    if a.shape != b.shape:
        raise MetricError(f"render {b.shape} and reference {a.shape} differ in size; renders must be aligned")
    if min(a.shape) < k:
        raise MetricError(f"image smaller than the {k}x{k} window")
    if not (np.isfinite(a).all() and np.isfinite(b).all()):
        raise MetricError("non-finite pixel")
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    ma, mb = _box(a, k), _box(b, k)
    va, vb = _box(a * a, k) - ma * ma, _box(b * b, k) - mb * mb
    cov = _box(a * b, k) - ma * mb
    s = ((2 * ma * mb + c1) * (2 * cov + c2)) / ((ma * ma + mb * mb + c1) * (va + vb + c2))
    return float(s.mean())


def render_score(references: dict, renders: dict) -> dict:
    """SSIM of each variant render against the benchmark reference of the same view.

    No reference -> value null; references but no render -> value null; a render for an unknown view, or
    a reference view without its render, is an error naming it (no partial mean is reported)."""
    base = {"method": SSIM_METHOD, "value": None, "per_view": None}
    if not references:
        return {**base, "reason": "benchmark has no reference picture"}
    if not renders:
        return {**base, "reason": "no variant render given"}
    unknown = sorted(set(renders) - set(references))
    if unknown:
        raise MetricError(f"render view(s) {unknown} have no reference picture")
    missing = sorted(set(references) - set(renders))
    if missing:
        raise MetricError(f"reference view(s) {missing} have no render")
    per = {view: round(ssim(_luma(references[view]), _luma(renders[view])), 5) for view in sorted(references)}
    return {**base, "value": round(sum(per.values()) / len(per), 5), "per_view": per, "reason": None}
