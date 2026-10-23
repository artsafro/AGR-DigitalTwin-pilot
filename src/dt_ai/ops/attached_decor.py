"""Attached decor clearance and rigid repair in local metres.

Pattern: attached-decor | new-case: source-bound placement and neighbour-closure repair.
No DCC, files, cached reports or inferred movement direction. Inputs are copied.
The construction gate conservatively rejects exactly 10 mm; xView remains 5 mm.
"""
from collections.abc import Mapping

import numpy as np

from dt_ai.ops import inv_xview as ix
from dt_ai.ops.inv_quads import PolyMesh

CLEARANCE_M = 0.010


def _snapshot(scene):
    if not isinstance(scene, Mapping) or not scene:
        raise ValueError('scene must be a nonempty mapping of named PolyMesh parts')
    result = {}
    for name, mesh in scene.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f'invalid part name: {name!r}')
        if not isinstance(mesh, PolyMesh):
            raise ValueError(f'{name}: expected PolyMesh')
        mesh = PolyMesh(np.array(mesh.vertices, dtype=float, copy=True), mesh.faces)
        if not mesh.faces:
            raise ValueError(f'{name}: no faces')
        used = {i for f in mesh.faces for i in f}
        if used != set(range(len(mesh.vertices))):
            raise ValueError(f'{name}: unused vertices')
        for k, f in enumerate(mesh.faces):
            p = mesh.vertices[list(f)]
            cross = np.cross(p[1:] - p[0], np.roll(p, -1, axis=0)[1:] - p[0])
            area = np.linalg.norm(cross.sum(axis=0)) / 2
            if not np.isfinite(area) or area <= ix.AREA_EPS_M2:
                raise ValueError(f'{name} face {k}: degenerate or nonfinite area')
        result[name] = mesh
    return result


def _joined(scene):
    vertices, faces, owners, local = [], [], [], []
    offset = 0
    for name, mesh in scene.items():
        vertices.append(mesh.vertices)
        faces.extend(tuple(i + offset for i in f) for f in mesh.faces)
        owners.extend([name] * len(mesh.faces))
        local.extend(range(len(mesh.faces)))
        offset += len(mesh.vertices)
    return PolyMesh(np.concatenate(vertices), tuple(faces)), owners, local


def _pairs(scene, distance):
    mesh, owners, local = _joined(scene)
    tol = ix.XviewTolerance(face_m=distance)
    return tuple((owners[a], local[a], owners[b], local[b], kind)
                 for a, b, kind, _ in ix.face_pairs(mesh, tol)
                 if owners[a] != owners[b])


def clearance_pairs(scene):
    """Inter-part contacts/area overlaps at <=10 mm, including tilted ends/boundaries.

    Uses inv_xview's per-vertex predicate, never a centroid or sampled gap.
    Polygon indices in returned (part, face, part, face, kind) rows are zero-based.
    Shared-index welded joints must be checked in their assembled mesh, not split
    into independent parts: this interface never guesses a weld by coordinates.
    """
    return _pairs(_snapshot(scene), CLEARANCE_M)
