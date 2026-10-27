"""Our kernel from drawings (#727): one prism per level band and plan contour, by dt_ai.ops.contour.extrude_polygon.

Pattern: primitive-first | new-case: building body as stacked contour prisms of our own kernel (methods class building-body).

    uv run python tools/methods/body/kernel_prisms.py <contours.json> <mesh.json>

Input: contours.json (tools/methods/body/contours.py: level heights + plan contour per band). Every band
polygon becomes a closed prism from z0 to z1 (NumpyExtrude: constrained-Delaunay caps, two triangles per side
edge, outward normals, holes kept). Prisms are not welded or unioned: adjacent bands touch with coincident
caps (that is what the kernel gives; the measurement shows it). Writes {"vertices", "triangles", "prisms",
"kernel_s"}; body_blender.py export-mesh then writes the FBX.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import contours as body_contours  # noqa: E402
from dt_ai.ops.contour import extrude_polygon  # noqa: E402


def prisms(data: dict) -> dict:
    t0 = time.perf_counter()
    vs, ts, off, n = [], [], 0, 0
    for band in data["bands"]:
        z0, z1 = float(band["z0"]), float(band["z1"])
        for poly in body_contours.polygons(band):
            m = extrude_polygon(poly, axis=2, base_m=z0, height_m=z1 - z0)
            vs.append(np.asarray(m.vertices, float))
            ts.append(np.asarray(m.triangles, int) + off)
            off += len(m.vertices)
            n += 1
    if not n:
        raise ValueError("no band polygon to extrude")
    v, t = np.concatenate(vs), np.concatenate(ts)
    return {"vertices": v.round(6).tolist(), "triangles": t.tolist(), "prisms": n,
            "kernel_s": round(time.perf_counter() - t0, 3)}


if __name__ == "__main__":
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    if src.resolve() == out.resolve():
        raise SystemExit("output resolves to the input")
    out.write_text(json.dumps(prisms(json.loads(src.read_text(encoding="utf-8")))), encoding="utf-8")
