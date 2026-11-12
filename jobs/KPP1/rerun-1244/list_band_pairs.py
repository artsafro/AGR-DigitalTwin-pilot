"""List the V004 co-directional pairs inside the 5-20 mm band of a KPP1 FBX (#1244).

Pattern: n/a | new-case: job-local receipt that lists and classifies the in-band V004 pairs.

Uses the validator's own readback (`twinqa.scene.readback`) and pair kernel
(`twinqa.clearance.co_directional_pairs`, band edges from the profile and `BAND_EDGE_TOL_M`),
so the count must equal the `in_band` figure of `tools/qa/validate_package.py --scene`;
a mismatch exits 1 and writes nothing.

    uv run python jobs/KPP1/rerun-1244/list_band_pairs.py <fbx> <vpm|npm> <out.json>
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from twinqa.clearance import BAND_EDGE_TOL_M, co_directional_distribution, co_directional_pairs
from twinqa.profiles import load_profiles
from twinqa.scene import readback


def _faces(meshes: list[dict]) -> tuple[list[dict], dict]:
    faces, lookup = [], {}
    for mesh in meshes:
        if mesh["name"].upper().startswith("UCX_"):
            continue
        if "face_geometry" not in mesh:
            raise ValueError(f"{mesh['name']}: no face geometry in readback")
        shape = mesh["face_geometry"]
        verts = shape["vertices"]
        for index, polygon in enumerate(shape["polygons"]):
            points = [verts[v] for v in polygon]
            if not np.all(np.isfinite(np.asarray(points, dtype=float))):
                raise ValueError(f"{mesh['name']}#{index}: non-finite vertex coordinate")
            if len(points) >= 3:
                face = {"object": mesh["name"], "index": index, "points": points}
                faces.append(face)
                lookup[(mesh["name"], index)] = np.asarray(points, dtype=float)
    return faces, lookup


def _normal(points: np.ndarray) -> np.ndarray:
    n = np.zeros(3)
    for a, b in zip(points, np.roll(points, -1, axis=0)):
        n += np.cross(a, b)
    length = float(np.linalg.norm(n))
    if not math.isfinite(length) or length == 0.0:
        raise ValueError("degenerate face")
    return n / length


def _axis(normal: np.ndarray) -> str:
    k = int(np.argmax(np.abs(normal)))
    return ("+" if normal[k] > 0 else "-") + "XYZ"[k]


def band_pairs(fbx: Path, kind: str) -> dict:
    if kind not in ("vpm", "npm"):
        raise ValueError(f"unsupported profile {kind!r}; expected vpm or npm")
    band = load_profiles().profile(kind)["geometry"]["near_coplanar_spacing_m"]
    lo, hi = float(band["min"]), float(band["max"])
    rb = readback(fbx)
    faces, lookup = _faces(rb["meshes"])
    if not faces:
        raise ValueError(f"{fbx}: no measurable faces")
    pairs = co_directional_pairs(faces)
    dist = co_directional_distribution(pairs, lo, hi)
    rows = []
    for p in pairs:
        d = p["distance_m"]
        if d < lo - BAND_EDGE_TOL_M or d > hi + BAND_EDGE_TOL_M:
            continue
        a, b = lookup[tuple(p["a"])], lookup[tuple(p["b"])]
        n = _normal(a)
        ca, cb = a.mean(axis=0), b.mean(axis=0)
        rows.append({"a": p["a"], "b": p["b"], "distance_mm": round(d * 1000, 4),
                     "overlap_area_m2": round(p["projected_area_m2"], 6), "normal_axis": _axis(n),
                     "centre_a": [round(float(x), 4) for x in ca], "centre_b": [round(float(x), 4) for x in cb],
                     "bbox_a_m": [[round(float(x), 4) for x in a.min(axis=0)], [round(float(x), 4) for x in a.max(axis=0)]],
                     "bbox_b_m": [[round(float(x), 4) for x in b.min(axis=0)], [round(float(x), 4) for x in b.max(axis=0)]],
                     "z_range_m": [round(float(min(a[:, 2].min(), b[:, 2].min())), 4),
                                   round(float(max(a[:, 2].max(), b[:, 2].max())), 4)]})
    if len(rows) != dist["in_band"]:
        raise RuntimeError(f"listed {len(rows)} pairs, distribution says in_band={dist['in_band']}")
    rows.sort(key=lambda r: (r["normal_axis"], r["distance_mm"], r["centre_a"]))
    return {"fbx": str(fbx), "sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(), "profile": kind,
            "band_mm": [lo * 1000, hi * 1000], "distribution": {k: dist[k] for k in
                                                                ("pairs", "below_band", "in_band", "above_band",
                                                                 "min_mm", "max_mm", "histogram_mm")},
            "in_band_by_axis": dict(Counter(r["normal_axis"] for r in rows)),
            "in_band_distance_mm": dict(Counter(f"{r['distance_mm']:.1f}" for r in rows)),
            "in_band_pairs": rows}


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    fbx, kind, out = Path(argv[0]), argv[1], Path(argv[2])
    if not fbx.is_file():
        print(f"no such FBX: {fbx}", file=sys.stderr)
        return 2
    if out.resolve() == fbx.resolve():
        print("output path resolves to the input FBX", file=sys.stderr)
        return 2
    try:
        report = band_pairs(fbx, kind)
    except (ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("profile", "distribution", "in_band_by_axis", "in_band_distance_mm")}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
