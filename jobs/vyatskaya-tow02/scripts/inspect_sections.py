"""Planar sections of the TOW02 source in the building-local frame (read only).

Engine gap: EG6 (measurement helper of the EG6 build scripts, e.g. build_fins.py).

Source arrays: outputs/measure-v001/source_npz/<object>.npz exported from the Blender work copy
(world coordinates, metres): co (N,3), tri (M,3), mat (M,) material name per triangle.
Local frame: world rotated by LOCAL_ANGLE_DEG about Z (min-area rectangle of slab z=48.1).
"""
import math
from pathlib import Path

import numpy as np

NPZ_DIR = Path(__file__).resolve().parent.parent / "outputs" / "measure-v001" / "source_npz"
OBJECTS = ["RC_TOW_02", "RC_TOW_Lapatki_02", "SLAB_TOW_02"]
LOCAL_ANGLE_DEG = 56.7
_A = math.radians(LOCAL_ANGLE_DEG)
R = np.array([[math.cos(_A), -math.sin(_A), 0], [math.sin(_A), math.cos(_A), 0], [0, 0, 1]])


def load(name):
    """Return (co_local, tri, mat) for one source object."""
    d = np.load(NPZ_DIR / f"{name}.npz")
    return d["co"] @ R, d["tri"], d["mat"]


def cut(co, tri, mat, axis, val):
    """Intersect triangles with plane coord[axis]==val; list of (p0, p1, material)."""
    P = co[tri]
    s = P[:, :, axis] - val
    sel = (s.min(1) < 0) & (s.max(1) > 0)
    P, s, m = P[sel], s[sel], mat[sel]
    segs = []
    for i in range(len(P)):
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if s[i, a] * s[i, b] < 0:
                t = s[i, a] / (s[i, a] - s[i, b])
                pts.append(P[i, a] + (P[i, b] - P[i, a]) * t)
        if len(pts) == 2:
            segs.append((pts[0], pts[1], m[i]))
    return segs


if __name__ == "__main__":
    D = {o: load(o) for o in OBJECTS}
    allco = np.concatenate([D[o][0] for o in OBJECTS[:2]])
    print("local bbox", allco.min(0).round(3), allco.max(0).round(3))
