"""NPM UV readback against the atlas cells of npm_atlas.json (#1580), V006 "UV atlas padding".

Pattern: n/a | new-case: readback check of the exported NPM FBX UVs against the npm_atlas.json regions and the
8 px inter-island padding (reg p.9 §5.4) at the atlas resolution.

Before #1580 nobody read the UVs of the exported NPM mesh: tools/derive/npm_atlas.py validate_export measures the
declared regions and the PNGs (before export_npm runs), and tools/qa/validate_package.py dropped its V006 "8 px
padding" stub when a scene was passed. This check reads the FBX back (tools/blender/fbx_readback.py, polygon_uv per
corner) and requires every face of every textured (non-UCX, non-glass) mesh to lie inside ONE finish region of
npm_atlas.json, i.e. outside the padding band of its cell:

- the layout itself: integer atlas / cell / pad px, pad >= 4 px per side (8 px between islands of neighbouring
  cells), every region whole-pixel, inside its own cell with >= MIN_PAD_PX to each cell edge, one region per cell;
- the face's cell is the one containing its UV centroid; no cell -> fail "outside every atlas cell";
- a corner more than UV_TOL outside the region of that cell -> fail ("padding band" when the face stays in the
  cell, "crosses cell" otherwise), naming the mesh, face index and finish;
- the atlas resolution is bound to the FBX: an embedded image of atlas x atlas px must exist;
- empty input (no textured mesh, no faces, missing / partial polygon_uv, unreadable FBX) fails, never passes.

CLI (the `agr vpm-to-npm` route runs it after export_npm):
    python -m twinqa.npm_uv <npm.fbx> <npm_atlas.json> [--blender EXE] [--json]
exit 0 pass, 1 fail, 2 usage / unreadable layout.
"""
from __future__ import annotations

import argparse
import json
import math
import numbers
import sys
from pathlib import Path

from twinqa.report import Finding

NAME = "UV atlas padding"
PAGES = [9]
MIN_PAD_PX = 4          # per side -> 8 px between islands of neighbouring cells (reg p.9 §5.4)
UV_TOL = 1e-5           # ~0.02 px at 2048 px: FBX float32 UVs + readback rounding to 1e-6
PX_TOL = 1e-6
GLASS_SUFFIXES = ("MainGlass", "GroundGlass", "GroundElGlass")
EXPECTED = (f"every face of every textured NPM mesh inside one npm_atlas.json region, outside the padding band "
            f"(>= {MIN_PAD_PX} px per side = 8 px between islands, reg p.9 §5.4) at the atlas resolution")


class AtlasLayoutError(ValueError):
    """npm_atlas.json cannot be used as the reference for the readback check."""


def _int(value, what):
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise AtlasLayoutError(f"npm_atlas.json {what} must be an integer: {value!r}")
    return int(value)


def _real(value, what):
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise AtlasLayoutError(f"npm_atlas.json {what} must be a finite number: {value!r}")
    return float(value)


def load_layout(atlas: dict) -> dict:
    """Validate npm_atlas.json; returns {atlas, cell, pad, regions: [{name, u0, v0, u1, v1, cell_uv, pad_px}]}."""
    if not isinstance(atlas, dict):
        raise AtlasLayoutError("npm_atlas.json must be an object")
    size, cell, pad = (_int(atlas.get(k), k) for k in ("atlas", "cell", "pad"))
    if size <= 0 or not 0 < cell <= size:
        raise AtlasLayoutError(f"npm_atlas.json atlas {size} / cell {cell} px invalid")
    if pad < MIN_PAD_PX or 2 * pad >= cell:
        raise AtlasLayoutError(f"npm_atlas.json pad {pad} px: require {MIN_PAD_PX} <= pad < cell / 2 "
                               f"(8 px between islands, reg p.9 §5.4)")
    finishes = atlas.get("finishes")
    if not isinstance(finishes, dict) or not finishes:
        raise AtlasLayoutError("npm_atlas.json has no finish regions")
    regions, cells = [], {}
    for name, region in finishes.items():
        if not isinstance(region, dict):
            raise AtlasLayoutError(f"finish {name}: region is not an object")
        u0, v0, rs = (_real(region.get(k), f"{name}.{k}") for k in ("u0", "v0", "size"))
        x, y, length = u0 * size, (1.0 - v0 - rs) * size, rs * size   # pixels, rows from the top
        if length <= 0 or x < -PX_TOL or y < -PX_TOL or x + length > size + PX_TOL or y + length > size + PX_TOL:
            raise AtlasLayoutError(f"finish {name}: region outside the {size} px atlas or empty")
        col, row = int(math.floor((x + PX_TOL) / cell)), int(math.floor((y + PX_TOL) / cell))
        cx, cy = col * cell, row * cell
        if cx + cell > size or cy + cell > size:
            raise AtlasLayoutError(f"finish {name}: cell ({col}, {row}) leaves the atlas")
        side = min(x - cx, y - cy, cx + cell - x - length, cy + cell - y - length)
        if side < MIN_PAD_PX - PX_TOL:
            raise AtlasLayoutError(f"finish {name}: region {side:.3f} px from its cell edge; require "
                                   f">= {MIN_PAD_PX} px per side (8 px between islands, reg p.9 §5.4)")
        if (col, row) in cells:
            raise AtlasLayoutError(f"finish {name}: cell ({col}, {row}) already holds {cells[(col, row)]}")
        cells[(col, row)] = name
        regions.append({"name": str(name), "u0": u0, "v0": v0, "u1": u0 + rs, "v1": v0 + rs, "pad_px": side,
                        "cell_uv": (cx / size, 1.0 - (cy + cell) / size, (cx + cell) / size, 1.0 - cy / size)})
    return {"atlas": size, "cell": cell, "pad": pad, "regions": regions}


def _cell_of(layout, u, v):
    for region in layout["regions"]:
        a, b, c, d = region["cell_uv"]
        if a <= u < c and b <= v < d:
            return region
    return None


def _outside_px(region, corners, size):
    """Largest distance in px of a corner outside the region (0 when every corner is inside)."""
    worst = 0.0
    for u, v in corners:
        du = max(region["u0"] - u, u - region["u1"], 0.0)
        dv = max(region["v0"] - v, v - region["v1"], 0.0)
        worst = max(worst, du * size, dv * size)
    return worst


def check_meshes(meshes: list[dict], layout: dict) -> dict:
    """Per-face check of the textured meshes; returns {faces, meshes, bad: [...], errors: [...], min_inner_px}."""
    size = layout["atlas"]
    tol_px = UV_TOL * size
    out = {"faces": 0, "meshes": [], "bad": [], "errors": [], "min_inner_px": None}
    for mesh in meshes:
        name = mesh.get("name", "?")
        geometry = mesh.get("face_geometry") or {}
        polygons, corner_uv = geometry.get("polygons"), geometry.get("polygon_uv")
        if not isinstance(polygons, list) or not isinstance(corner_uv, list) or len(polygons) != len(corner_uv):
            count = len(corner_uv) if isinstance(corner_uv, list) else None
            out["errors"].append(f"{name}: no polygon_uv per polygon ({count} for "
                                 f"{len(polygons) if isinstance(polygons, list) else None} polygons)")
            continue
        out["meshes"].append(name)
        for index, corners in enumerate(corner_uv):
            try:
                pts = [(float(u), float(v)) for u, v in corners]
            except (TypeError, ValueError):
                out["errors"].append(f"{name} face {index}: unreadable UV corners {corners!r}")
                continue
            if len(pts) < 3 or not all(math.isfinite(c) for p in pts for c in p):
                out["errors"].append(f"{name} face {index}: needs >= 3 finite UV corners")
                continue
            out["faces"] += 1
            cu, cv = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            region = _cell_of(layout, cu, cv)
            if region is None:
                out["bad"].append({"mesh": name, "face": index, "finish": None,
                                   "reason": "outside every atlas cell", "centroid_uv": [cu, cv]})
                continue
            outside = _outside_px(region, pts, size)
            if outside > tol_px:
                a, b, c, d = region["cell_uv"]
                in_cell = all(a - UV_TOL <= u <= c + UV_TOL and b - UV_TOL <= v <= d + UV_TOL for u, v in pts)
                out["bad"].append({"mesh": name, "face": index, "finish": region["name"],
                                   "reason": "padding band" if in_cell else "crosses cell",
                                   "outside_region_px": round(outside, 3)})
                continue
            inner = min(min(u - region["u0"], region["u1"] - u, v - region["v0"], region["v1"] - v)
                        for u, v in pts) * size + region["pad_px"]
            out["min_inner_px"] = inner if out["min_inner_px"] is None else min(out["min_inner_px"], inner)
    return out


def npm_uv_findings(rb: dict, atlas: dict, src: str | None = None) -> list[Finding]:
    """V006 "UV atlas padding" of one NPM OKS FBX readback against its npm_atlas.json (never a vacuous pass)."""
    src = src or Path(str(rb.get("source", "?"))).name

    def fail(observed, data=None):
        return [Finding(NAME, "fail", f"{src}: {observed}", EXPECTED, list(PAGES), src, data=dict(data or {}))]

    try:
        layout = load_layout(atlas)
    except AtlasLayoutError as exc:
        return fail(f"atlas layout unusable: {exc}")
    if not rb.get("readback_ok"):
        return fail(f"FBX readback failed: {rb.get('error', 'no meshes')}")
    meshes = [m for m in rb.get("meshes") or [] if not str(m.get("name", "")).upper().startswith("UCX_")
              and not str(m.get("name", "")).endswith(GLASS_SUFFIXES)]
    if not meshes:
        return fail("no textured (non-UCX, non-glass) mesh to check")
    size = layout["atlas"]
    sizes = [list(i.get("size") or []) for i in rb.get("images") or []]
    if [size, size] not in sizes:
        return fail(f"no embedded {size} x {size} px atlas image (images {sizes}); the padding is measured at "
                    f"the atlas resolution of npm_atlas.json")
    result = check_meshes(meshes, layout)
    data = {"faces": result["faces"], "meshes": result["meshes"], "atlas_px": size, "cell_px": layout["cell"],
            "pad_px": layout["pad"], "bad_faces": len(result["bad"]), "bad": result["bad"][:20],
            "errors": result["errors"][:20], "min_distance_to_cell_edge_px": result["min_inner_px"]}
    if result["errors"]:
        return fail(f"partial UV readback: {result['errors'][:5]}", data)
    if not result["faces"]:
        return fail("no faces to check", data)
    if result["bad"]:
        first = "; ".join(f"{b['mesh']} face {b['face']} ({b['finish']}): {b['reason']}" for b in result["bad"][:5])
        return fail(f"{len(result['bad'])} of {result['faces']} faces leave their atlas region: {first}", data)
    margin = result["min_inner_px"]
    return [Finding(NAME, "pass", f"{src}: {result['faces']} faces in {len(layout['regions'])} regions; nearest "
                    f"corner {margin:.2f} px from its cell edge (>= {MIN_PAD_PX} px)", EXPECTED, list(PAGES), src,
                    measured=margin, threshold=float(MIN_PAD_PX), margin=(margin - MIN_PAD_PX) / MIN_PAD_PX,
                    data=data)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m twinqa.npm_uv", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("fbx", type=Path)
    ap.add_argument("atlas", type=Path, help="npm_atlas.json of this OKS")
    ap.add_argument("--blender", help="Blender executable (default: TWINQA_BLENDER / pinned install)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        atlas = json.loads(a.atlas.read_text(encoding="utf-8"))
        load_layout(atlas)
    except (OSError, ValueError) as exc:
        print(f"Error: {a.atlas}: {exc}", file=sys.stderr)
        return 2
    if not a.fbx.is_file():
        print(f"Error: {a.fbx} does not exist", file=sys.stderr)
        return 2
    from twinqa.scene import readback
    try:
        rb = readback(a.fbx, blender=a.blender)
    except (OSError, RuntimeError, ValueError) as exc:
        rb = {"readback_ok": False, "error": str(exc), "source": str(a.fbx)}
    findings = npm_uv_findings(rb, atlas, a.fbx.name)
    sys.stdout.reconfigure(encoding="utf-8")
    for f in findings:
        print(json.dumps(f.__dict__, ensure_ascii=False, default=str) if a.json
              else f"V006 {f.name}: {f.status.upper()} {f.observed}")
    return 0 if all(f.status == "pass" for f in findings) else 1


if __name__ == "__main__":
    sys.exit(main())
