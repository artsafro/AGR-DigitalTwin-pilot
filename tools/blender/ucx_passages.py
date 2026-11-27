"""new-case: OBSERVE covered through-space sampled in horizontal sections (#2047, #2052).

Reuse #2047's mid-cell grid and opposite-ray test. This is a geometry proxy, not a
walkability proof: apertures/open surfaces can let rays through; small or curved
passages can be missed. Volumes are estimates of sampled cells, not Boolean solids.
"""
import math

from mathutils import Vector
from mathutils.bvhtree import BVHTree

STEP_M = 0.5
HEIGHT_M = 5.0
MAX_SAMPLES = 1_000_000
UP = Vector((0, 0, 1))
DIRECTIONS = [Vector((math.cos(k * math.pi / 4), math.sin(k * math.pi / 4), 0)) for k in range(8)]


def _geometry(objects):
    verts, tris = [], []
    for obj in objects:
        mesh = obj.data
        mesh.calc_loop_triangles()
        offset = len(verts)
        verts.extend(obj.matrix_world @ v.co for v in mesh.vertices)
        tris.extend(tuple(i + offset for i in tri.vertices) for tri in mesh.loop_triangles)
    return verts, tris


def _bounds(verts):
    return tuple(tuple(fn(p[i] for p in verts) for i in range(3)) for fn in (min, max))


def _inside(point, tree, hi_z):
    """Odd upward surface crossings; independent of imported triangle winding."""
    origin = point.copy()
    crossings = 0
    while origin.z <= hi_z:
        hit, _, _, _ = tree.ray_cast(origin, UP)
        if hit is None:
            break
        crossings += 1
        # Advance past the hit, including at float32 storage precision in the local frame.
        origin.z = hit.z + max(1e-5, 2e-7 * abs(hit.z))
    return crossings % 2 == 1


def _summarize(cells, origin):
    """Join face-neighbours in each section and across consecutive sections (6-connectivity)."""
    passages = []
    remaining = set(cells)
    for seed in cells:
        if seed not in remaining:
            continue
        remaining.remove(seed)
        stack = [seed]
        count = blocked = 0
        lo, hi = list(seed), list(seed)
        while stack:
            cell = stack.pop()
            count += 1
            blocked += cells[cell]
            x, y, z = cell
            for neighbour in ((x-1, y, z), (x+1, y, z), (x, y-1, z), (x, y+1, z), (x, y, z-1), (x, y, z+1)):
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    stack.append(neighbour)
            for i, value in enumerate(cell):
                lo[i], hi[i] = min(lo[i], value), max(hi[i], value)
        passages.append({"id": len(passages) + 1, "volume_m3": count * STEP_M**3,
                         "blocked_m3": blocked * STEP_M**3, "blocked_share": blocked / count,
                         "bounds_m": [[origin[i] + STEP_M * bound[i] for i in range(3)]
                                      for bound in (lo, [n + 1 for n in hi])]})
    return passages


def observe(objects):
    """Estimate the blocked union over sampled passage cells, regardless of the UCX verdict."""
    render, collisions = [], []
    for obj in objects:
        (collisions if obj.name.upper().startswith("UCX_") else render).append(obj)
    verts, tris = _geometry(render)
    if not tris:
        return {"status": "not_measured", "reason": "no render triangles"}
    lo, hi = _bounds(verts)
    nx, ny = (int((hi[i] - lo[i]) / STEP_M) + 1 for i in (0, 1))
    nz = int(HEIGHT_M / STEP_M)
    if nx * ny * nz > MAX_SAMPLES:
        return {"status": "not_measured", "reason": "horizontal section sample budget exceeded",
                "grid": [nx, ny, nz], "max_samples": MAX_SAMPLES}

    anchor = Vector(lo)
    model = BVHTree.FromPolygons([v - anchor for v in verts], tris, all_triangles=True)
    pieces = []
    for obj in collisions:
        vertices, faces = _geometry([obj])
        if faces:
            local = [v - anchor for v in vertices]
            lower, upper = _bounds(local)
            pieces.append((lower, upper, BVHTree.FromPolygons(local, faces, all_triangles=True)))

    cells = {}
    for k in range(nz):
        z = (k + 0.5) * STEP_M
        active = [(lo, hi, bvh) for lo, hi, bvh in pieces if lo[2] <= z <= hi[2]]
        for i in range(nx):
            x = (i + 0.5) * STEP_M
            column = [(lo, hi, bvh) for lo, hi, bvh in active if lo[0] <= x <= hi[0]]
            for j in range(ny):
                y = (j + 0.5) * STEP_M
                point = Vector((x, y, z))
                if model.ray_cast(point, UP)[0] is None:
                    continue
                if not any(model.ray_cast(point, DIRECTIONS[d])[0] is None
                           and model.ray_cast(point, DIRECTIONS[d+4])[0] is None for d in range(4)):
                    continue
                cells[i, j, k] = any(lo[1] <= y <= hi[1] and _inside(point, bvh, hi[2])
                                     for lo, hi, bvh in column)
    return {"status": "observed", "step_m": STEP_M, "band_m": [lo[2], lo[2] + HEIGHT_M],
            "grid": [nx, ny, nz], "passages": _summarize(cells, lo)}
