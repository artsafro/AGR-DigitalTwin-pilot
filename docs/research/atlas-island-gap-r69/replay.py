"""Standing #69 replay: same-tile UV island gap census on AC08 NPM v007 (rejected) vs v010 (accepted), OBSERVE.

Contract: docs/research/autoresearch-atlas-island-gap.md. Runner layout reuses #68 (atlas-seam-r68/replay.py).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import statistics
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import nearest_points, unary_union

from twinqa.sintez_uv import _polygons

ROOT = Path(__file__).resolve().parents[3]
BASE = "4288c54de328db7a5037b57707862319f7aa6ff0"
DRIVE = Path("G:/Мой диск/AGR-evidence")
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.1/blender.exe")
PINS = {BLENDER: "1e6624af112b3c936f4b038b025ebd2bf00ae72c4b62881a6787166d71c58fa5"}
VERSIONS = {  # label, SM_Nku_1.zip SHA-256 (same pins as #67/#68)
    "v007": ("rejected", "271ee11bf78200ef883814a4ac108ef289098d0f106da01e8d9fc57da888c295"),
    "v010": ("accepted", "2fe983791566477e297aeefa09f04a1b7d176312c3fce1a8c9f1cf26138013bb"),
}
FLOOR_PX, UV_EPS, OVERLAP_PX2, TEXTURED = 8.0, 1e-6, 0.01, 4096
ROUNDS, READBACK_LIMIT_S, BUDGET_S = 3, 120.0, 900.0
# R2 amendment: the real NPM (export_npm_meta.json -> package-npm) on its 2048 atlas next to the ZIP.
NPM = {"v007": ("0d1fa6c036bb553459dd0e9baec8be4ace8bc61d5acea6aab585d713f2292d0f",
                "772a2768ca396a4c6b404357ad30a676de4bf6928be053db1d956fb3b675a516"),
       "v010": ("8f0cb8b7e922850eab15198d0bd40cf2ca1e2bfed12e9c4912173b4aef565ab3",
                "88e0392ea057013e4eb33e9240a3856a1728fb8380433cab9662f73052473278")}
PACKAGE = "vpm"  # set by main(): "vpm" = R1 frozen fixture SM_Nku_1.zip, "npm" = R2 0000_Nku_1.zip


def _tile(uv):
    cu, cv = (statistics.fmean(a) for a in zip(*uv, strict=True))
    u, v = math.floor(cu), math.floor(cv)
    return 1001 + u + 10 * v, (u, v)


def islands(rb):
    """{tile: [(face ids, shapely union in tile UV 0..1)]}, faces joined by a shared UV edge on one tile."""
    faces = []  # (tile, local uv ring)
    for mesh in rb["meshes"]:
        if str(mesh.get("name", "")).startswith("UCX_"):  # collision hulls carry no UV (R1 crash, see log)
            continue
        for _, _, uv, _ in _polygons(mesh):
            tile, (u0, v0) = _tile(uv)
            faces.append((tile, [(u - u0, v - v0) for u, v in uv]))
    parent = list(range(len(faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    q = 1 / UV_EPS
    edges = {}
    for i, (tile, ring) in enumerate(faces):
        keys = [(round(u * q), round(v * q)) for u, v in ring]
        for a, b in zip(keys, keys[1:] + keys[:1], strict=True):
            if a == b:
                continue
            k = (tile, min(a, b), max(a, b))
            if k in edges:
                parent[find(i)] = find(edges[k])
            else:
                edges[k] = i
    groups = defaultdict(list)
    for i in range(len(faces)):
        groups[find(i)].append(i)
    out = defaultdict(list)
    for members in groups.values():
        tile = faces[members[0]][0]
        polys = [Polygon(faces[i][1]).buffer(0) for i in members]
        out[tile].append((sorted(members), unary_union([p for p in polys if not p.is_empty])))
    return out


def census(isl, sides):
    tiles = {}
    for tile, items in sorted(isl.items()):
        side = sides.get(tile)
        pairs, sub, overlap, gaps = 0, [], 0, []
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i][1], items[j][1]
                pairs += 1
                if a.intersection(b).area * side * side > OVERLAP_PX2:
                    overlap += 1
                    continue
                gap = a.distance(b) * side
                gaps.append(gap)
                if gap < FLOOR_PX:
                    sub.append([i, j, round(gap, 6)])
        tiles[tile] = {"tile_px": side, "textured": side == TEXTURED, "islands": len(items), "pairs": pairs,
                       "overlap_pairs": overlap, "sub_floor_pairs": len(sub), "sub_floor": sub[:20],
                       "min_gap_px": round(min(gaps), 6) if gaps else None}
    tex = [t for t in tiles.values() if t["textured"]]
    gaps = [t["min_gap_px"] for t in tex if t["min_gap_px"] is not None]
    measured = sum(t["pairs"] - t["overlap_pairs"] for t in tex)  # R2: empty gap set = not applicable
    return {"N69": sum(t["sub_floor_pairs"] for t in tex), "measured_gaps": measured,
            "overlap_pairs_textured": sum(t["overlap_pairs"] for t in tex),
            "min_gap_px_textured": min(gaps) if gaps else None,
            "applicable": measured > 0, "tiles": {str(k): v for k, v in tiles.items()}}


def witness(isl, sides, target_px):
    """Move the smaller island of the closest textured pair with gap >= 8 px to `target_px` (in memory)."""
    best = None
    for tile, items in isl.items():
        if sides.get(tile) != TEXTURED:
            continue
        side = sides[tile]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a, b = items[i][1], items[j][1]
                if a.intersection(b).area * side * side > OVERLAP_PX2:
                    continue
                gap = a.distance(b) * side
                if gap >= FLOOR_PX and (best is None or gap < best[0]):
                    best = (gap, tile, i, j)
    if best is None:
        return None
    gap, tile, i, j = best
    items = list(isl[tile])
    small, big = (i, j) if items[i][1].area <= items[j][1].area else (j, i)
    p, q = nearest_points(items[small][1], items[big][1])
    d = (gap - target_px) / sides[tile]
    ux, uy = (q.x - p.x) / math.hypot(q.x - p.x, q.y - p.y), (q.y - p.y) / math.hypot(q.x - p.x, q.y - p.y)
    items[small] = (items[small][0], affinity.translate(items[small][1], ux * d, uy * d))
    moved = dict(isl)
    moved[tile] = items
    return {"from_gap_px": round(gap, 6), "target_px": target_px, "tile": tile, "changed_islands": 1,
            "result": census(moved, sides)}


def fixture(v):
    d = DRIVE / f"559-tec26-oks-ac08-pilot-{v}"
    return d / ("0000_Nku_1.zip" if PACKAGE == "npm" else "SM_Nku_1.zip")


def npm_atlas(v):
    return DRIVE / f"559-tec26-oks-ac08-pilot-{v}" / "T_Nku_1_001_Main_d_1.png"


def preflight():
    if PACKAGE == "npm":
        pins = PINS | {fixture(v): z for v, (z, _) in NPM.items()} | {npm_atlas(v): a for v, (_, a) in NPM.items()}
    else:
        pins = PINS | {fixture(v): h for v, (_, h) in VERSIONS.items()}
    for p, expected in pins.items():
        with p.open("rb") as f:
            if hashlib.file_digest(f, "sha256").hexdigest() != expected:
                raise ValueError(f"fixture hash mismatch: {p}")
    subprocess.run(["git", "diff", "--quiet", BASE, "--", "src", "tools", "standards", "adapters",
                    "uv.lock", "pyproject.toml"], cwd=ROOT, check=True)
    return {str(p): h for p, h in pins.items()}


def one(v, out, timeout):
    from twinqa.scene import readback

    member = "0000_Nku_1_01.fbx" if PACKAGE == "npm" else "SM_Nku_1.fbx"
    fbx = out / f"{v}_{member}"
    sides = {}
    if PACKAGE == "npm":  # one 2048 atlas = tile 1001, decoded side checked
        with Image.open(npm_atlas(v)) as im:
            if im.size != (TEXTURED, TEXTURED):
                raise ValueError(f"{v}: NPM atlas {im.size} != {TEXTURED}")
        sides = {1001: TEXTURED}
    with zipfile.ZipFile(fixture(v)) as z:
        fbx.write_bytes(z.read(member))
        for name in z.namelist():
            if "_Diffuse_" in name and name.endswith(".png"):
                with Image.open(io.BytesIO(z.read(name))) as im:
                    w, h = im.size
                if w != h:
                    raise ValueError(f"{v}: non-square {name}")
                sides[int(name.rsplit(".", 2)[1])] = w
    t0 = time.perf_counter()
    rb = readback(fbx, blender=str(BLENDER), timeout=timeout)
    seconds = time.perf_counter() - t0
    isl = islands(rb)
    missing = sorted(set(isl) - set(sides))
    if missing:
        raise ValueError(f"{v}: faces on tiles without Diffuse: {missing}")
    row = census(isl, sides) | {"readback_s": round(seconds, 3),
                                "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest()}
    if v == "v010":
        row["witness"] = {"W1_4px": witness(isl, sides, 4.0), "W2_9px": witness(isl, sides, 9.0)}
    return row


def main(out, package="vpm"):
    global PACKAGE, TEXTURED
    PACKAGE = package
    if package == "npm":
        TEXTURED = 2048
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pins = preflight()
    start, rounds, status = time.perf_counter(), [], "complete"
    for r in range(ROUNDS):
        row = {}
        for v in VERSIONS:
            row[v] = one(v, out, timeout=int(READBACK_LIMIT_S * 2))
            if row[v]["readback_s"] > READBACK_LIMIT_S or time.perf_counter() - start > BUDGET_S:
                status = "budget_stop"
        rounds.append(row)
        if status != "complete":
            break
    wall = time.perf_counter() - start

    def series(v, k):
        vals = [r[v][k] for r in rounds if v in r]
        return {"values": vals, "spread": (max(vals) - min(vals)) if None not in vals else None}

    summary = {v: {k: series(v, k) for k in ("N69", "min_gap_px_textured", "overlap_pairs_textured")}
               for v in VERSIONS}
    stable = all(s["spread"] == 0 for v in summary.values() for s in v.values() if s["spread"] is not None)
    applicable = all(r[v]["applicable"] for r in rounds for v in r)
    n7, n10 = (statistics.median(summary[v]["N69"]["values"]) for v in ("v007", "v010"))
    if status != "complete" or not stable or not applicable or len(rounds) < ROUNDS:
        verdict = "inconclusive"
    else:
        verdict = "confirmed" if n7 > n10 else "refuted"
    receipt = {"card": "t_de9ede95", "package": PACKAGE, "contract": "docs/research/autoresearch-atlas-island-gap.md", "base": BASE,
               "pins": pins, "labels": {v: lab for v, (lab, _) in VERSIONS.items()}, "status": status,
               "wall_s": round(wall, 3), "rounds": rounds, "summary": summary, "stable": stable,
               "applicable": applicable, "N69_median": {"v007": n7, "v010": n10}, "H69": verdict,
               "rule_fires_on_accepted_control": n10 > 0}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1), encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("status", "wall_s", "N69_median", "H69", "stable", "applicable",
                                              "rule_fires_on_accepted_control")}))


if __name__ == "__main__":
    main(sys.argv[1], "npm" if "--npm" in sys.argv[2:] else "vpm")
