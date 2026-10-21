"""Extract connected exact-plane regions for contour-first Ground diagnostics.

Pattern: n/a | new-case: discard artificial grid edges without discarding source faces (#371).
This pure primitive is not a remesher or an acceptance certificate. Consumers must
prove boundary conformity, texel/shape/spacing, budgets and exported-file parity.
"""
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

from dt_ai.geometry.ground_quads import _validate_seed


@dataclass(frozen=True)
class PlanarPatch:
    source_faces: tuple[int, ...]
    slot: str
    level: int
    origin: np.ndarray
    axes: np.ndarray
    polygon: Polygon

    def to_world(self, xy):
        return self.origin + np.asarray(xy) @ self.axes


def planar_patches(mesh, *, allowed_slots):
    """Keep every seed triangle in one connected semantic plane (0.1 um bound).

    Membership is tested against the fixed root plane, not pairwise normal
    similarity: a chain of locally similar triangles must not accumulate drift.
    Boundary corners, including collinear ones, are retained in the union.
    """
    _validate_seed(mesh)
    incidence = defaultdict(list)
    for i, face in enumerate(mesh.faces):
        for a, b in zip(face, np.roll(face, -1)):
            incidence[tuple(sorted((int(a), int(b))))].append(i)
    neighbours = [set() for _ in mesh.faces]
    for edge, faces in incidence.items():
        if len(faces) > 2:
            raise ValueError(f'nonmanifold seed edge {edge}')
        if len(faces) == 2:
            a, b = faces
            if mesh.slot[a] == mesh.slot[b] and mesh.level[a] == mesh.level[b]:
                neighbours[a].add(b)
                neighbours[b].add(a)
    triangles = mesh.verts[mesh.faces]
    normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    seen = set()
    patches = []
    for root, triangle in enumerate(triangles):
        if root in seen:
            continue
        origin = triangle[0]
        u = triangle[1]-origin
        u = u/np.linalg.norm(u)
        normal = normals[root]
        axes = np.array([u, np.cross(normal, u)])
        members = {root}
        pending = [root]
        seen.add(root)
        while pending:
            for other in sorted(neighbours[pending.pop()]):
                if other in seen:
                    continue
                p = triangles[other]-origin
                if (np.max(np.abs(p @ normal)) <= 1e-7
                        and normals[other] @ normal >= 1-1e-12):
                    seen.add(other)
                    members.add(other)
                    pending.append(other)
        ids = tuple(sorted(members))
        pieces = [Polygon((triangles[i]-origin) @ axes.T) for i in ids]
        polygon = unary_union(pieces)
        if not isinstance(polygon, Polygon) or not polygon.is_valid or polygon.is_empty:
            raise ValueError(f'patch at source face {root}: unsupported disconnected/invalid union')
        patches.append(PlanarPatch(ids, mesh.slot[root], int(mesh.level[root]),
                                   origin.copy(), axes, polygon))
    return tuple(patches)
