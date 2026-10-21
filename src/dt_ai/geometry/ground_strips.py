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
    if not np.isfinite(mesh.cell) or mesh.cell <= 0:
        raise ValueError('cell must be positive and finite')
    for ids in mesh.source_faces:
        if (not isinstance(ids, (tuple, list)) or not ids or len(ids) != len(set(ids))
                or any(isinstance(k, (bool, np.bool_)) or not isinstance(k, (int, np.integer)) or k < 0 for k in ids)):
            raise ValueError('complete nonempty source-face identities required')
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
        # A corner fan (two adjacent long sides) has no well-conditioned
        # tensor chart after a hard-size cut. Retain its original 0--2 split
        # and refine only the resulting poor triangles, not the entire mesh.
        variants = [(f, np.asarray(uv))]
        if len(f) == 4 and metric.max_edge_m > max_edge_m:
            variants = [(tuple(f[j] for j in ids), np.asarray(uv)[list(ids)])
                        for ids in ((0, 1, 2), (0, 2, 3))]
        for face, tex in variants:
            points = np.asarray([vertices[j] for j in face])
            r = face_metrics(points)
            if len(face) == 3 and (r.aspect > 8 or r.max_edge_m > max_edge_m):
                center = len(vertices)
                vertices.append(points.mean(axis=0).tolist())
                mids = [edge(face[j], face[(j+1)%3], Fraction(1, 2)) for j in range(3)]
                for j in range(3):
                    patches.append(((face[j], mids[j], center, mids[j-1]),
                                    np.array([tex[j], (tex[j]+tex[(j+1)%3])/2, np.mean(tex, axis=0),
                                              (tex[j-1]+tex[j])/2]), i))
            else:
                patches.append((face, tex, i))
    faces, uvs, slots, levels, sources = [], [], [], [], []
    for f, uv, owner in patches:
        p = np.asarray([vertices[j] for j in f])
        def evaluate(corners, u, v):
            u, v = float(u), float(v)
            return ((1-u)*corners[0]+(u-v)*corners[1]+v*corners[2] if u >= v
                    else (1-v)*corners[0]+u*corners[2]+(v-u)*corners[3])
        nu = nv = 1
        if len(f) == 4:
            e = np.linalg.norm(np.roll(p, -1, axis=0)-p, axis=1)
            means = [(e[0]+e[2])/2, (e[1]+e[3])/2]
            nu, nv = max(1, ceil(max(e[0], e[2])/max_edge_m)), max(1, ceil(max(e[1], e[3])/max_edge_m))
            if means[0] > means[1]:
                nu = max(nu, ceil(means[0]/(7.5*means[1])))
            else:
                nv = max(nv, ceil(means[1]/(7.5*means[0])))
        uc = [Fraction(k, nu) for k in range(nu+1)]
        vc = [Fraction(j, nv) for j in range(nv+1)]
        if len(f) == 4:
            for _ in range(16):
                if len(faces)+(len(uc)-1)*(len(vc)-1) > face_budget:
                    raise ValueError(f'local strip face budget exceeded at source face {owner}')
                split_u, split_v = set(), set()
                for va, vb in zip(vc, vc[1:]):
                    for ua, ub in zip(uc, uc[1:]):
                        cell = np.array([evaluate(p, u, v) for u, v in
                                         ((ua, va), (ub, va), (ub, vb), (ua, vb))])
                        e = np.linalg.norm(np.roll(cell, -1, axis=0)-cell, axis=1)
                        if e.min() <= 0 or not np.isfinite(e).all():
                            raise ValueError(f'degenerate strip cell at source face {owner}')
                        ratio = (e[0]+e[2])/(e[1]+e[3])
                        if ratio > 8 or max(e[0], e[2]) > max_edge_m:
                            split_u.add((ua+ub)/2)
                        if ratio < 1/8 or max(e[1], e[3]) > max_edge_m:
                            split_v.add((va+vb)/2)
                if not split_u and not split_v:
                    break
                uc = sorted(set(uc)|split_u)
                vc = sorted(set(vc)|split_v)
            else:
                raise ValueError(f'bounded strip sizing did not converge at source face {owner}')
        if len(faces)+(len(uc)-1)*(len(vc)-1) > face_budget:
            raise ValueError(f'local strip face budget exceeded at source face {owner}')
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
            for va, vb in zip(vc, vc[1:]):
                for ua, ub in zip(uc, uc[1:]):
                    coordinates = [(ua, va), (ub, va), (ub, vb), (ua, vb)]
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
