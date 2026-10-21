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


def planar_patches(mesh, *, allowed_slots, protected_faces=(), plane_tolerance_m=1e-7):
    """Keep every seed triangle in one connected bounded semantic plane.

    Membership is tested against the fixed root plane, not pairwise normal
    similarity: a chain of locally similar triangles must not accumulate drift.
    Boundary corners, including collinear ones, are retained in the union.
    """
    _validate_seed(mesh)
    if (isinstance(plane_tolerance_m, bool) or not isinstance(plane_tolerance_m, (int, float))
            or not np.isfinite(plane_tolerance_m) or not 0 < plane_tolerance_m <= 1e-5):
        raise ValueError('plane tolerance must be finite, positive and <=10 micrometres')
    if (not isinstance(allowed_slots, (set, frozenset)) or not allowed_slots
            or any(not isinstance(s, str) or not s.strip() for s in allowed_slots)):
        raise ValueError('allowed_slots must be a nonempty set of named texture slots')
    for slot in mesh.slot:
        if slot not in allowed_slots:
            raise ValueError(f'unmapped texture slot: {slot}')
    if np.any(mesh.level != np.floor(mesh.level)):
        raise ValueError('every level must be integral')
    protected = set()
    for i in protected_faces:
        if (isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer))
                or not 0 <= i < len(mesh.faces) or i in protected):
            raise ValueError(f'invalid/duplicate protected source face: {i!r}')
        protected.add(int(i))
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
            directions = [next((int(x), int(y)) for x, y in zip(mesh.faces[k], np.roll(mesh.faces[k], -1))
                               if tuple(sorted((int(x), int(y)))) == edge) for k in (a, b)]
            if directions[0] != directions[1][::-1]:
                raise ValueError(f'inconsistent winding at source edge {edge}')
            if (a not in protected and b not in protected
                    and mesh.slot[a] == mesh.slot[b] and mesh.level[a] == mesh.level[b]):
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
                if (np.max(np.abs(p @ normal)) <= plane_tolerance_m
                        and normals[other] @ normal > 0):
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
