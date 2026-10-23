"""Attached decor clearance and rigid repair in local metres.

Pattern: attached-decor | new-case: source-bound placement and neighbour-closure repair.
No DCC, files, cached reports or inferred movement direction. Inputs are copied.
The construction gate conservatively rejects exactly 10 mm; xView remains 5 mm.
"""
from collections.abc import Mapping
from dataclasses import dataclass

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


@dataclass(frozen=True)
class RigidMove:
    scene: dict
    moved: tuple
    contacts: tuple
    clearance: tuple


def move_rigid(scene, seeds, vector, *, fixed):
    """Move the transitive <=10 mm parallel-neighbour closure by one vector.

    `fixed` explicitly identifies stationary hosts/obstacles (not guessed from names).
    Neighbours of fixed parts are still tested; fixed parts only stop propagation.
    Whole parts move, never selected end vertices. Refuse if ANY inv_xview face pair
    remains anywhere at 5 mm, including internal pairs and newly reached obstacles.
    Return no candidate on failure and never mutate caller arrays. Remaining 10 mm
    construction failures stay visible in `clearance`; zero xView is not acceptance.
    """
    for selection in (seeds, fixed):
        if not isinstance(selection, (list, tuple, set, frozenset)) or any(
                not isinstance(x, str) or not x for x in selection) or len(set(selection)) != len(selection):
            raise ValueError('selection must contain distinct nonempty part names, not a string')
    scene = _snapshot(scene)
    moving, fixed = set(seeds), set(fixed)
    for label in moving | fixed:
        if label not in scene:
            raise ValueError(f'unknown part: {label!r}')
    if not moving or moving & fixed:
        raise ValueError('seeds must be nonempty and disjoint from fixed parts')
    vector = np.asarray(vector, dtype=float)
    if vector.shape != (3,) or not np.isfinite(vector).all() or not np.any(vector):
        raise ValueError('vector must be a finite nonzero (3,) translation')
    near = _pairs(scene, CLEARANCE_M)
    while True:
        expanded = moving | {b for a, _, b, _, _ in near if a in moving and b not in fixed} | \
            {a for a, _, b, _, _ in near if b in moving and a not in fixed}
        if expanded == moving:
            break
        moving = expanded
    after = {name: PolyMesh(mesh.vertices + vector if name in moving else mesh.vertices.copy(), mesh.faces)
             for name, mesh in scene.items()}
    after = _snapshot(after)  # finite translations can still collapse geometry at float64 precision
    mesh, owners, local = _joined(after)
    contacts = ix.face_pairs(mesh, ix.XviewTolerance())
    if contacts:
        named = [(owners[a], local[a], owners[b], local[b], kind) for a, b, kind, _ in contacts]
        raise ValueError(f'rigid move leaves face contacts/overlaps: {named[:5]}')
    return RigidMove(after, tuple(sorted(moving)), (), _pairs(after, CLEARANCE_M))
