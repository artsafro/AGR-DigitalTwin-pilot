"""Window / glazing variants of the methods catalog, pure numpy (class windows-glazing, #721).

Pattern: new-case: window opening extraction and three window representations measured side by side (#721).

Our own code (no team script text). Input: the glass polygons of a benchmark model in world metres (Z up).
`extract_openings` groups them into planar rectangular openings; every input polygon ends in an opening or
in the drop list with its reason. The variant builders return plain arrays the Blender driver
(`build_variant_blender.py`) turns into meshes:

- `modelled-frames`: frame ring + mullions as closed solids (built with Blender bmesh ops in the driver,
  from `frame_plan`), glass panes as one `*_MainGlass` object.
- `atlas-planes`: one quad per opening in the Main mesh, UV on the atlas cell of its window type
  (type = width x height rounded to 0.1 m); no frame geometry, no glass object.
- `inset-glass-trim`: glass pane shrunk by the trim width at the source glass plane (the inset the source
  already has) + a flat frame ring around it UV-mapped on a trim-sheet strip; frame depth 0 by construction.
"""
from __future__ import annotations

import math

import numpy as np

VARIANTS = ("modelled-frames", "atlas-planes", "inset-glass-trim")
WELD_M = 0.001  # vertex weld for polygon adjacency
PLANE_TOL_M = 0.005  # two polygons are coplanar when offsets differ <= 5 mm ...
PLANE_COS = math.cos(math.radians(5.0))  # ... and normals within 5 deg
MAX_VERTICAL_NZ = 0.7  # |n_z| above this = roof / skylight glass, not a facade window (dropped with reason)
MIN_SIDE_M = 0.2  # an opening narrower or lower than this is dropped with its reason
MIN_FILL = 0.6  # glass area / bounding rectangle below this = not a rectangle, dropped with its reason
FRAME_W_M = 0.06  # frame face width (outer ring)
FRAME_D_M = 0.07  # frame depth along the opening normal (modelled-frames)
PANE_MAX_W_M = 1.2  # a pane wider than this gets a vertical mullion
TRIM_W_M = 0.06  # flat frame ring width (inset-glass-trim)


def _newell(p: np.ndarray) -> np.ndarray:
    return np.cross(p, np.roll(p, -1, axis=0)).sum(axis=0) / 2.0  # area vector


def extract_openings(polygons: list, model_centre_xy=None) -> tuple[list[dict], list[dict]]:
    """Group glass polygons (each an (k, 3) world array) into rectangular openings.

    Returns (openings, dropped). An opening: centre, u (horizontal), v (up in the plane), n (outward when
    `model_centre_xy` is given), width, height, polygons (input indices), fill. A dropped entry names the
    input polygon indices and the reason. No polygon is lost: sum of both index lists = all inputs.
    """
    polys = [np.asarray(p, float).reshape(-1, 3) for p in polygons]
    for i, p in enumerate(polys):
        if len(p) < 3 or not np.isfinite(p).all():
            raise ValueError(f"glass polygon {i} has {len(p)} points or a non-finite coordinate")
    area_vec = [_newell(p) for p in polys]
    areas = [float(np.linalg.norm(a)) for a in area_vec]
    dropped, live = [], []
    for i, a in enumerate(areas):
        (dropped.append({"polygons": [i], "reason": "zero-area glass polygon"}) if a < 1e-9 else live.append(i))
    normals = {i: area_vec[i] / areas[i] for i in live}
    offsets = {i: float(normals[i] @ polys[i].mean(axis=0)) for i in live}
    parent = {i: i for i in live}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edge_owner: dict = {}
    for i in live:
        key = [tuple(np.round(q / WELD_M).astype(np.int64)) for q in polys[i]]
        for a, b in zip(key, key[1:] + key[:1]):
            e = (a, b) if a <= b else (b, a)
            for j in edge_owner.get(e, []):
                d = float(normals[i] @ normals[j])
                if abs(d) >= PLANE_COS and abs(offsets[i] - math.copysign(1, d) * offsets[j]) <= PLANE_TOL_M:
                    parent[find(i)] = find(j)
            edge_owner.setdefault(e, []).append(i)
    groups: dict = {}
    for i in live:
        groups.setdefault(find(i), []).append(i)
    openings = []
    for members in sorted(groups.values(), key=min):
        ref = normals[max(members, key=lambda k: areas[k])]
        n = np.sum([area_vec[k] if area_vec[k] @ ref >= 0 else -area_vec[k] for k in members], axis=0)
        area = float(np.linalg.norm(n))
        n = n / area
        if abs(n[2]) > MAX_VERTICAL_NZ:
            dropped.append({"polygons": members, "reason": f"not a facade window: |n_z| = {abs(n[2]):.2f}"})
            continue
        pts = np.concatenate([polys[k] for k in members])
        if model_centre_xy is not None:
            c = pts.mean(axis=0)
            if (c[0] - model_centre_xy[0]) * n[0] + (c[1] - model_centre_xy[1]) * n[1] < 0:
                n = -n
        u = np.array([-n[1], n[0], 0.0])
        u /= np.linalg.norm(u)
        v = np.cross(n, u)
        pu, pv = pts @ u, pts @ v
        w, h = float(pu.max() - pu.min()), float(pv.max() - pv.min())
        if w < MIN_SIDE_M or h < MIN_SIDE_M:
            dropped.append({"polygons": members, "reason": f"opening {w:.2f} x {h:.2f} m under {MIN_SIDE_M} m"})
            continue
        fill = area / (w * h)
        if fill < MIN_FILL:
            dropped.append({"polygons": members, "reason": f"not rectangular: fill {fill:.2f} < {MIN_FILL}"})
            continue
        d = float(np.median(pts @ n))
        centre = u * (pu.max() + pu.min()) / 2 + v * (pv.max() + pv.min()) / 2 + n * d
        openings.append({"centre": centre, "u": u, "v": v, "n": n, "width": w, "height": h,
                         "polygons": sorted(members), "fill": round(fill, 4)})
    return openings, dropped


def rect(o: dict, inset: float = 0.0, du=(None, None)) -> np.ndarray:
    """Corners (CCW seen from +n) of the opening rectangle, shrunk by `inset`; du limits the u range."""
    hw, hh = o["width"] / 2 - inset, o["height"] / 2 - inset
    u0 = -hw if du[0] is None else du[0]
    u1 = hw if du[1] is None else du[1]
    c, u, v = o["centre"], o["u"], o["v"]
    return np.array([c + u * u0 - v * hh, c + u * u1 - v * hh, c + u * u1 + v * hh, c + u * u0 + v * hh])


def panes(o: dict) -> int:
    return max(1, math.ceil((o["width"] - 2 * FRAME_W_M) / PANE_MAX_W_M))


def tile_offset(tile: int) -> tuple[int, int]:
    if not 1001 <= tile <= 1100:
        raise ValueError(f"UDIM tile {tile} outside 1001..1100")
    return (tile - 1001) % 10, (tile - 1001) // 10


def metric_uv(points: np.ndarray, o: dict, scale: float, tile: int) -> np.ndarray:
    """Planar UV of points in the opening frame: the two in-plane-or-depth axes with the largest extent,
    metres x `scale`, from the opening's lower-left corner, inside UDIM `tile` (clipped to [0, 1))."""
    local = np.stack([(points - o["centre"]) @ o["u"], (points - o["centre"]) @ o["v"],
                      (points - o["centre"]) @ o["n"]], axis=1)
    ext = local.max(axis=0) - local.min(axis=0)
    a, b = sorted(np.argsort(-ext)[:2])
    uv = np.stack([local[:, a] - local[:, a].min(), local[:, b] - local[:, b].min()], axis=1) * scale
    du, dv = tile_offset(tile)
    return np.clip(uv, 0.0, 0.999) + np.array([du, dv], float)


def trim_scale(openings: list[dict]) -> float:
    """UV metres -> tile scale: 0.25 (4 m per tile) unless the longest frame bar needs a smaller one."""
    longest = max([max(o["width"], o["height"]) for o in openings] + [4.0])
    return 1.0 / longest


def window_types(openings: list[dict]) -> list[tuple]:
    return sorted({(round(o["width"], 1), round(o["height"], 1)) for o in openings})


def atlas_planes(openings: list[dict], tile: int) -> dict:
    """One quad per opening; UV = the atlas cell of its type (grid g x g in `tile`, 2 % margin)."""
    types = window_types(openings)
    g = max(1, math.ceil(math.sqrt(len(types)))) if types else 1
    du, dv = tile_offset(tile)
    verts, faces, uvs = [], [], []
    for o in openings:
        k = types.index((round(o["width"], 1), round(o["height"], 1)))
        cx, cy = k % g, k // g
        m = 0.02 / g
        u0, u1 = du + cx / g + m, du + (cx + 1) / g - m
        v0, v1 = dv + cy / g + m, dv + (cy + 1) / g - m
        base = len(verts)
        verts += list(rect(o))
        faces.append([base, base + 1, base + 2, base + 3])
        uvs.append([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
    return {"verts": np.array(verts).reshape(-1, 3), "faces": faces, "uvs": uvs, "types": types, "grid": g}


def inset_glass_trim(openings: list[dict], tile: int) -> dict:
    """Glass pane = opening shrunk by TRIM_W_M at the source plane; flat frame ring (4 bars) around it on a
    trim strip (metric UV, `trim_scale`). Ring and pane share the inner edge, never overlap."""
    s = trim_scale(openings)
    frame_v, frame_f, frame_uv, glass_v, glass_f, glass_uv = [], [], [], [], [], []
    for o in openings:
        outer, inner = rect(o), rect(o, TRIM_W_M)
        base = len(frame_v)
        frame_v += list(outer) + list(inner)  # one welded ring: 8 vertices, 4 mitred bars
        for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
            frame_f.append([base + a, base + b, base + 4 + b, base + 4 + a])
            frame_uv.append(metric_uv(np.array([outer[a], outer[b], inner[b], inner[a]]), o, s, tile).tolist())
        base = len(glass_v)
        glass_v += list(inner)
        glass_f.append([base, base + 1, base + 2, base + 3])
        glass_uv.append([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    return {"frame": (np.array(frame_v).reshape(-1, 3), frame_f, frame_uv),
            "glass": (np.array(glass_v).reshape(-1, 3), glass_f, glass_uv), "trim_scale": s}


def frame_plan(o: dict) -> dict:
    """Inputs of the bmesh frame build of one opening: outer rectangle, pane count, widths, depth."""
    return {"outer": rect(o), "panes": panes(o), "frame_w": FRAME_W_M, "mullion_w": FRAME_W_M,
            "depth": FRAME_D_M}
