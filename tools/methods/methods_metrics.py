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

    Texture side: for a package, `tile_sides` = {UDIM tile or None (untiled): side px} read from its diffuse
    PNGs, applied per polygon by the UDIM tile of its UV centre (the package's files win over the readback:
    one bound image must not stand for every tile); else the readback's single square diffuse size
    (twinqa.scene rule). A polygon on a tile without a diffuse PNG gives null naming the tile."""
    side = None if tile_sides else _texture_side_px(rb)
    source = "readback"
    if tile_sides:
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


# ---- windows / glazing (class windows-glazing, #721) ---------------------------------------------------------------

GLASS_SUFFIX = "_MAINGLASS"  # VPM glazing object SM_{Address}_MainGlass (reg p.33 §10.4.2, WIN-13)
FRAME_TOKEN = "FRAME"  # a model-mesh material slot whose name holds this token carries frame geometry


def is_glass(name: str) -> bool:
    return name.upper().endswith(GLASS_SUFFIX)


def _components(polys: list[list[int]]) -> list[list[int]]:
    """Connected components (shared vertex index) of the given polygons; returns polygon-index lists."""
    parent = list(range(len(polys)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, p in enumerate(polys):
        for v in p:
            if v in owner:
                parent[find(i)] = find(owner[v])
            else:
                owner[v] = i
    groups = {}
    for i in range(len(polys)):
        groups.setdefault(find(i), []).append(i)
    return sorted(groups.values(), key=min)


def windows_glazing(rb: dict, extra: dict | None) -> dict:
    """Glass object count, glass triangle share and frame depth readout; null with a reason when unmeasurable.

    - glass_objects: model meshes named *_MainGlass; glass_triangles / glass_triangle_share over all
      model (non-UCX) triangles (null when there is no model triangle).
    - frame depth: polygons of model meshes whose slot material name holds FRAME_TOKEN, split into connected
      components; depth of one component = extent of its vertices along its smallest principal axis (the
      opening normal for a frame ring). Reported as min / median / max over the components. Null when there
      is no extra readback, the extra readback has no per-polygon material index, or no frame slot is used.
    """
    model = model_meshes(rb)
    tris_all = sum(int(m["triangles"]) for m in model)
    glass = [m for m in model if is_glass(m["name"])]
    tris_glass = sum(int(m["triangles"]) for m in glass)
    out = {"glass_objects": len(glass), "glass_object_names": sorted(m["name"] for m in glass),
           "glass_triangles": tris_glass,
           "glass_triangle_share": round(tris_glass / tris_all, 5) if tris_all else None,
           "glass_share_reason": None if tris_all else "no model triangle",
           "frame_token": FRAME_TOKEN, "frame_components": None, "frame_polygons": None,
           "frame_depth_m": None, "frame_reason": None}
    if not extra or not extra.get("ok"):
        out["frame_reason"] = "no extra readback"
        return out
    comps, polys_total = [], 0
    for m in model:
        info = extra["meshes"].get(m["name"])
        if info is None:
            raise MetricError(f"mesh {m['name']!r} missing from the extra readback")
        frame_slots = {i for i, s in enumerate(info["slots"]) if s and FRAME_TOKEN in s.upper()}
        if not frame_slots:
            continue
        per_poly = info.get("polygon_material_index")
        if per_poly is None:
            out["frame_reason"] = "extra readback has no per-polygon material index"
            return out
        fg = m["face_geometry"]
        if len(per_poly) != len(fg["polygons"]):
            raise MetricError(f"{m['name']}: {len(per_poly)} material indices for {len(fg['polygons'])} polygons")
        sel = [p for p, k in zip(fg["polygons"], per_poly) if int(k) in frame_slots]
        polys_total += len(sel)
        verts = np.asarray(fg["vertices"], float).reshape(-1, 3)
        for comp in _components(sel):
            idx = sorted({v for i in comp for v in sel[i]})
            pts = verts[idx]
            if len(pts) < 3 or not np.isfinite(pts).all():
                raise MetricError(f"{m['name']}: frame component with {len(pts)} points or a non-finite one")
            centred = pts - pts.mean(axis=0)
            axis = np.linalg.svd(centred, full_matrices=False)[2][-1]
            along = centred @ axis
            comps.append(float(along.max() - along.min()))
    if not comps:
        out["frame_reason"] = f"no polygon on a material slot named *{FRAME_TOKEN.title()}*"
        out.update({"frame_components": 0, "frame_polygons": 0})
        return out
    out.update({"frame_components": len(comps), "frame_polygons": polys_total,
                "frame_depth_m": {"min": round(min(comps), 4), "median": round(statistics.median(comps), 4),
                                  "max": round(max(comps), 4)}})
    return out


# ---- ground / terrain (class ground-terrain, #733) -----------------------------------------------------------------

GROUND_SAMPLE_M = 1.0  # fixed XY sample grid step for the vertical deviation (cell centres, anchored on the reference)
GROUND_HOLE_MIN_M2 = 1000.0  # footprint hole = plan hole of at least this area (Ground gate 1 rule, build_ground.py)
GROUND_CLOSE_M = 0.01  # footprint closing radius: seals float gaps between triangles, never a 1000 m2 hole
GROUND_MAX_PAIRS = 4_000_000  # sample x triangle candidate pairs per chunk
GROUND_METHOD = ("top surface = highest triangle straight above/below each XY sample (vertical faces skipped); "
                 "samples = centres of a fixed GROUND_SAMPLE_M grid anchored on floor(reference bbox min / step); "
                 "dz = output - reference on samples both surfaces cover; footprint = union of XY triangle "
                 "projections closed by GROUND_CLOSE_M; holes = interior rings >= GROUND_HOLE_MIN_M2; boundary = "
                 "summed exterior ring length; world XYZ = FBX XYZ + placement sidecar origin")


def placement_offset(path) -> tuple[np.ndarray | None, str | None]:
    """World origin of an FBX from its `<fbx>.placement.json` sidecar (tools/blender/ground_json_to_fbx.py,
    [D126]): (origin, None), or (None, reason) when there is no sidecar. A malformed sidecar is an error."""
    import json
    from pathlib import Path

    p = Path(str(path) + ".placement.json")
    if not p.is_file():
        return None, f"no placement sidecar {p.name}"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MetricError(f"{p.name}: not JSON ({exc})") from exc
    origin = data.get("origin_msk77_xyz") if isinstance(data, dict) else None
    if (not isinstance(origin, list) or len(origin) != 3
            or any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in origin)):
        raise MetricError(f"{p.name}: origin_msk77_xyz must be 3 finite numbers, got {origin!r}")
    if data.get("mesh_xyz = msk77_xyz - origin_msk77_xyz") is not True:
        raise MetricError(f"{p.name}: does not state mesh_xyz = msk77_xyz - origin_msk77_xyz")
    return np.asarray(origin, float), None


def _ground_tris(rb: dict, extra: dict | None, offset: np.ndarray) -> np.ndarray:
    v, t = _model_triangles(rb, extra)
    if not np.isfinite(v).all():
        raise MetricError("non-finite vertex in the model meshes")
    if len(t) and (t.min() < 0 or t.max() >= len(v)):
        raise MetricError("triangle index outside the vertex list")
    return (v + offset)[t]  # (n, 3, 3) world


def _xy_area2(tri: np.ndarray) -> np.ndarray:
    a, b, c = tri[:, 0, :2], tri[:, 1, :2], tri[:, 2, :2]
    return (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])


def sample_grid(ref_tri: np.ndarray, step: float = GROUND_SAMPLE_M) -> dict:
    """The fixed sample grid of a benchmark: cell centres over the reference XY bbox."""
    if isinstance(step, bool) or not isinstance(step, (int, float)) or not math.isfinite(step) or step <= 0:
        raise MetricError(f"sample step must be finite > 0, got {step!r}")
    if not len(ref_tri):
        raise MetricError("reference has no triangle")
    xy = ref_tri[:, :, :2].reshape(-1, 2)
    lo, hi = xy.min(0), xy.max(0)
    x0, y0 = math.floor(lo[0] / step) * step, math.floor(lo[1] / step) * step
    nx, ny = int(math.ceil((hi[0] - x0) / step)), int(math.ceil((hi[1] - y0) / step))
    return {"x0": x0, "y0": y0, "step": float(step), "nx": max(nx, 1), "ny": max(ny, 1)}


def top_z(tri: np.ndarray, grid: dict, eps: float = 1e-9) -> np.ndarray:
    """Highest Z of the triangles over every grid sample, shape (ny, nx); NaN where no triangle covers it."""
    x0, y0, s, nx, ny = grid["x0"], grid["y0"], grid["step"], grid["nx"], grid["ny"]
    out = np.full(nx * ny, -np.inf)
    tri = tri[np.abs(_xy_area2(tri)) > 1e-12]  # vertical faces have no XY area: skirts never decide the top
    if len(tri):
        xy = tri[:, :, :2]
        i0 = np.clip(np.ceil((xy[:, :, 0].min(1) - x0) / s - 0.5 - eps), 0, nx).astype(np.int64)
        i1 = np.clip(np.floor((xy[:, :, 0].max(1) - x0) / s - 0.5 + eps), -1, nx - 1).astype(np.int64)
        j0 = np.clip(np.ceil((xy[:, :, 1].min(1) - y0) / s - 0.5 - eps), 0, ny).astype(np.int64)
        j1 = np.clip(np.floor((xy[:, :, 1].max(1) - y0) / s - 0.5 + eps), -1, ny - 1).astype(np.int64)
        ni, nj = np.maximum(i1 - i0 + 1, 0), np.maximum(j1 - j0 + 1, 0)
        cnt = ni * nj
        start = 0
        while start < len(tri):
            csum = np.cumsum(cnt[start:])
            stop = start + max(1, int(np.searchsorted(csum, GROUND_MAX_PAIRS, side="right")))
            sel = np.arange(start, min(stop, len(tri)))
            start = int(sel[-1]) + 1
            c = cnt[sel]
            if not c.sum():
                continue
            ti = np.repeat(sel, c)
            k = np.arange(c.sum()) - np.repeat(np.cumsum(c) - c, c)
            gi = i0[ti] + k % ni[ti]
            gj = j0[ti] + k // ni[ti]
            px, py = x0 + (gi + 0.5) * s, y0 + (gj + 0.5) * s
            a, b, cc = tri[ti, 0], tri[ti, 1], tri[ti, 2]
            d = (b[:, 0] - a[:, 0]) * (cc[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (cc[:, 0] - a[:, 0])
            w1 = ((px - a[:, 0]) * (cc[:, 1] - a[:, 1]) - (py - a[:, 1]) * (cc[:, 0] - a[:, 0])) / d
            w2 = ((b[:, 0] - a[:, 0]) * (py - a[:, 1]) - (b[:, 1] - a[:, 1]) * (px - a[:, 0])) / d
            w0 = 1.0 - w1 - w2
            inside = (w0 >= -eps) & (w1 >= -eps) & (w2 >= -eps)
            z = w0 * a[:, 2] + w1 * b[:, 2] + w2 * cc[:, 2]
            np.maximum.at(out, (gj * nx + gi)[inside], z[inside])
    out[np.isneginf(out)] = np.nan
    return out.reshape(ny, nx)


def footprint(tri: np.ndarray, close_m: float = GROUND_CLOSE_M):
    """XY footprint: union of the projected triangles (vertical ones skipped), closed by close_m."""
    import shapely

    tri = tri[np.abs(_xy_area2(tri)) > 1e-12]
    if not len(tri):
        return shapely.Polygon()
    rings = np.concatenate([tri[:, :, :2], tri[:, :1, :2]], axis=1)
    union = shapely.union_all(shapely.polygons(rings), grid_size=1e-6)
    return union.buffer(close_m, join_style="mitre").buffer(-close_m, join_style="mitre")


def _parts(geom):
    return [g for g in getattr(geom, "geoms", [geom]) if g.geom_type == "Polygon" and not g.is_empty]


def footprint_holes(geom, hole_min_m2: float = GROUND_HOLE_MIN_M2):
    from shapely.geometry import Polygon

    return [Polygon(r) for p in _parts(geom) for r in p.interiors if Polygon(r).area >= hole_min_m2]


def ground_terrain(rb: dict, extra: dict | None, ref_rb: dict | None, ref_extra: dict | None,
                   offset: np.ndarray | None, ref_offset: np.ndarray | None, *, offset_reason: str | None = None,
                   ref_reason: str | None = None, sample_m: float = GROUND_SAMPLE_M,
                   hole_min_m2: float = GROUND_HOLE_MIN_M2) -> dict:
    """ground-terrain class metrics against the benchmark's reference surface. Each figure is measured or null
    with its reason: no reference readback, no placement sidecar (frames not comparable), no common sample."""
    model = model_meshes(rb)
    out = {"method": GROUND_METHOD, "sample_m": sample_m, "hole_min_m2": hole_min_m2,
           "triangles": int(sum(m["triangles"] for m in model)), "reference_triangles": None,
           "dz_max_m": None, "dz_p95_m": None, "dz_mean_m": None, "samples_reference": None, "samples_both": None,
           "samples_missing": None, "samples_extra": None, "dz_reason": None,
           "holes": None, "reference_holes": None, "holes_matched": None, "hole_count_diff": None,
           "boundary_m": None, "reference_boundary_m": None, "boundary_diff_m": None, "footprint_reason": None,
           "uv_present": None, "uv_reason": None}
    if ref_rb is not None:
        out["reference_triangles"] = int(sum(m["triangles"] for m in model_meshes(ref_rb)))
    if not model:
        out["uv_reason"] = out["dz_reason"] = out["footprint_reason"] = "no model mesh"
        return out
    if any("uv_channels" not in m for m in model):
        out["uv_reason"] = "readback has no uv_channels for a model mesh"
    else:
        out["uv_present"] = all(int(m["uv_channels"]) >= 1 for m in model)
    reason = None
    if ref_rb is None:
        reason = f"no reference surface: {ref_reason or 'no reference readback'}"
    elif not model_meshes(ref_rb):
        reason = "reference has no model mesh"
    elif offset is None or ref_offset is None:
        reason = "frames not comparable: " + (offset_reason or "no output placement") if offset is None else \
            "frames not comparable: " + (ref_reason or "no reference placement")
    if reason:
        out["dz_reason"] = out["footprint_reason"] = reason
        return out
    tri, ref = _ground_tris(rb, extra, offset), _ground_tris(ref_rb, ref_extra, ref_offset)
    grid = sample_grid(ref, sample_m)
    zo, zr = top_z(tri, grid), top_z(ref, grid)
    both = np.isfinite(zo) & np.isfinite(zr)
    out.update(samples_reference=int(np.isfinite(zr).sum()), samples_both=int(both.sum()),
               samples_missing=int((np.isfinite(zr) & ~np.isfinite(zo)).sum()),
               samples_extra=int((np.isfinite(zo) & ~np.isfinite(zr)).sum()))
    if both.any():
        dz = (zo - zr)[both]
        out.update(dz_max_m=round(float(np.abs(dz).max()), 4),
                   dz_p95_m=round(float(np.percentile(np.abs(dz), 95)), 4), dz_mean_m=round(float(dz.mean()), 4))
    else:
        out["dz_reason"] = "no sample covered by both surfaces"
    fo, fr = footprint(tri), footprint(ref)
    if fo.is_empty or fr.is_empty:
        out["footprint_reason"] = "empty XY footprint (only vertical faces)"
        return out
    ho, hr = footprint_holes(fo, hole_min_m2), footprint_holes(fr, hole_min_m2)
    matched = sum(1 for h in ho if any(r.contains(h.representative_point()) for r in hr))
    bo = sum(p.exterior.length for p in _parts(fo))
    br = sum(p.exterior.length for p in _parts(fr))
    out.update(holes=len(ho), reference_holes=len(hr), holes_matched=matched, hole_count_diff=len(ho) - len(hr),
               boundary_m=round(bo, 3), reference_boundary_m=round(br, 3), boundary_diff_m=round(bo - br, 3))
    return out
