"""Selective anisotropic Ground quad cells, diagnostic only.

Pattern: n/a | new-case: refine only poor texel faces instead of all-triangle Steiner expansion (#371).
This local stage intentionally does NOT certify neighbour conformity, xView,
relief, UV density, global budgets or delivery. Callers must measure them before
use; boundary transition construction is a separate stage. No IO is performed.
"""
from fractions import Fraction
from math import ceil

import numpy as np

from dt_ai.geometry.ground_quads import QuadMesh
from dt_ai.ops.inv_texel import PolyMesh, face_metrics


def local_strips(mesh: QuadMesh, *, max_edge_m: float, face_budget: int = 180000) -> QuadMesh:
    """Split long quads directionally; only bad triangles receive three patches.

    Points use the source quad's fixed 0--2 fan, never a guessed bilinear relief.
    A new quad crossing that fan can still change implicit tessellation: both
    diagonals, actual exported triangles and layer gaps remain mandatory probes.
    """
    PolyMesh(mesh.verts, mesh.faces)
    n = len(mesh.faces)
    if (not n or len(mesh.slot) != n or len(mesh.level) != n or len(mesh.uv) != n
            or len(mesh.source_faces) != n):
        raise ValueError('complete nonempty polygon metadata required')
    if (isinstance(max_edge_m, bool) or not isinstance(max_edge_m, (int, float))
            or not np.isfinite(max_edge_m) or max_edge_m <= 0):
        raise ValueError('max_edge_m must be finite and positive')
    if isinstance(face_budget, bool) or not isinstance(face_budget, int) or face_budget <= 0:
        raise ValueError('face_budget must be a positive integer')
    vertices = mesh.verts.tolist()
    edges = {}
    def edge(a, b, t):
        if t == 0:
            return a
        if t == 1:
            return b
        key = (a, b, t) if a < b else (b, a, 1-t)
        if key not in edges:
            edges[key] = len(vertices)
            vertices.append(((1-float(t))*np.asarray(vertices[a])+float(t)*np.asarray(vertices[b])).tolist())
        return edges[key]
    patches = []
    for i, (f, uv) in enumerate(zip(mesh.faces, mesh.uv)):
        if (len(f) not in (3, 4) or np.shape(uv) != (len(f), 2) or not np.isfinite(uv).all()
                or not isinstance(mesh.slot[i], str) or not mesh.slot[i].strip()
                or not np.isfinite(mesh.level[i]) or mesh.level[i] != int(mesh.level[i])):
            raise ValueError(f'invalid face metadata at {i}')
        p = mesh.verts[list(f)]
        metric = face_metrics(p)
        if metric.degenerate:
            raise ValueError(f'degenerate source face {i}')
        if len(f) == 3 and (metric.aspect > 8 or metric.max_edge_m > max_edge_m):
            center = len(vertices)
            vertices.append(p.mean(axis=0).tolist())
            mids = [edge(f[j], f[(j+1)%3], Fraction(1, 2)) for j in range(3)]
            for j in range(3):
                patches.append(((f[j], mids[j], center, mids[j-1]),
                                np.array([uv[j], (uv[j]+uv[(j+1)%3])/2, np.mean(uv, axis=0),
                                          (uv[j-1]+uv[j])/2]), i))
        else:
            patches.append((f, np.asarray(uv), i))
    faces, uvs, slots, levels, sources = [], [], [], [], []
    for f, uv, owner in patches:
        p = np.asarray([vertices[j] for j in f])
        nu = nv = 1
        if len(f) == 4:
            e = np.linalg.norm(np.roll(p, -1, axis=0)-p, axis=1)
            means = [(e[0]+e[2])/2, (e[1]+e[3])/2]
            nu, nv = max(1, ceil(max(e[0], e[2])/max_edge_m)), max(1, ceil(max(e[1], e[3])/max_edge_m))
            if means[0] > means[1]:
                nu = max(nu, ceil(means[0]/(7.5*means[1])))
            else:
                nv = max(nv, ceil(means[1]/(7.5*means[0])))
        if len(faces)+nu*nv > face_budget:
            raise ValueError(f'local strip face budget exceeded at source face {owner}')
        def evaluate(corners, u, v):
            u, v = float(u), float(v)
            return ((1-u)*corners[0]+(u-v)*corners[1]+v*corners[2] if u >= v
                    else (1-v)*corners[0]+u*corners[2]+(v-u)*corners[3])
        def point(u, v):
            if v == 0:
                return edge(f[0], f[1], u)
            if u == 1:
                return edge(f[1], f[2], v)
            if v == 1:
                return edge(f[3], f[2], u)
            if u == 0:
                return edge(f[0], f[3], v)
            key = (u, v)
            if key not in interior:
                interior[key] = len(vertices)
                vertices.append(evaluate(p, u, v).tolist())
            return interior[key]
        if len(f) == 3:
            cells = [(f, uv)]
        else:
            interior = {}
            cells = []
            for j in range(nv):
                for k in range(nu):
                    coordinates = [(Fraction(k, nu), Fraction(j, nv)), (Fraction(k+1, nu), Fraction(j, nv)),
                                   (Fraction(k+1, nu), Fraction(j+1, nv)), (Fraction(k, nu), Fraction(j+1, nv))]
                    cells.append((tuple(point(u, v) for u, v in coordinates),
                                  np.array([evaluate(uv, u, v) for u, v in coordinates])))
        for cell, tex in cells:
            faces.append(cell)
            uvs.append(tex)
            slots.append(mesh.slot[owner])
            levels.append(mesh.level[owner])
            sources.append(mesh.source_faces[owner])
    return QuadMesh(np.asarray(vertices), tuple(faces), slots, np.asarray(levels),
                    tuple(uvs), tuple(sources), mesh.cell)
