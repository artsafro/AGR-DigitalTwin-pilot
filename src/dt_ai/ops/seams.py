"""Atomic, source-labelled polygon seam operations in metres (#530).

new-case: conform shared near-parallel seams before joining or dissolving parts.
Pure numpy geometry on invariants.Mesh / inv_quads.PolyMesh; no DCC or files.
Boundary welds may move by at most 5 mm; they are not separation nudges. A caller
must explicitly request any rigid separation (at least 6 mm); residual contacts
or area overlaps refuse the entire operation, leaving all inputs unchanged.
This is topology repair, not a Boolean union or a quad retopologizer.
"""
from collections import defaultdict
from dataclasses import dataclass, replace

import numpy as np

from dt_ai.ops.invariants import Mesh
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, face_pairs
from dt_ai.ops.operations import OperationRefused

_FACE_M = 0.005
_CLEAR_M = 0.006
_COS = 0.9999
_EPS = 1e-8


@dataclass(frozen=True)
class SeamResult:
    mesh: PolyMesh
    face_sources: tuple  # each output polygon -> ((input part, input polygon), ...)
    vertex_sources: tuple  # each output vertex -> ((input part, input vertex), ...)
    dropped_vertices: tuple  # unused input vertices, with reason
    max_weld_m: float
    displacements: dict  # explicit rigid part translations, never implicit nudges


def _poly(mesh):
    if isinstance(mesh, Mesh):
        return PolyMesh(mesh.vertices, tuple(map(tuple, mesh.triangles)))
    if not isinstance(mesh, PolyMesh):
        raise ValueError(f'unsupported mesh {type(mesh).__name__}')
    return PolyMesh(mesh.vertices.copy(), mesh.faces)


def _plane(v, f):
    q = v[list(f)] - v[f[0]]
    n = np.cross(q, np.roll(q, -1, axis=0)).sum(axis=0)
    length = np.linalg.norm(n)
    if not np.isfinite(length) or length <= 1e-12:
        raise OperationRefused('degenerate or unmeasurable polygon')
    n /= length
    if np.max(np.abs(q @ n)) > _FACE_M:
        raise OperationRefused('polygon is nonplanar beyond 5 mm')
    return n, length / 2


def _compact(v, faces, sources):
    used = sorted({i for f in faces for i in f})
    ids = {old: new for new, old in enumerate(used)}
    return v[used], [tuple(ids[i] for i in f) for f in faces], [sources[i] for i in used]


def _weld(v, faces, sources):
    # Only coincident points: no transitive distance-cluster or global 5 mm weld.
    representatives = []
    remap = np.arange(len(v))
    for i, p in enumerate(v):
        hits = np.flatnonzero(np.linalg.norm(v[representatives] - p, axis=1) <= _EPS)
        if len(hits):
            j = representatives[hits[0]]
            remap[i] = j
            sources[j] = sources[j] + sources[i]
        else:
            representatives.append(i)
    changed = [tuple(int(remap[i]) for i in f) for f in faces]
    if any(len(set(f)) != len(f) for f in changed):
        raise OperationRefused('weld would collapse a polygon')
    return _compact(v, changed, sources)


def join_parts(parts, *, displacements=None):
    """Join nonempty named parts, splitting receiving edges at shared T-vertices.

    Larger faces anchor a boundary weld (ties: source part name, face index).
    Endpoint contacts share one original authoritative vertex, never swap snaps.
    Near-parallel incident faces are required
    for a noncoincident weld. Interior overlaps need an explicit >=6 mm rigid
    separation in `displacements={part: vector}`; they are never guessed away.
    Full face-pair postcondition (contact AND area) gates the returned result.
    Unused input vertices are reported; every input face retains its source id.
    """
    if not parts or any(not isinstance(k, str) or not k for k in parts):
        raise ValueError('parts must have nonempty string names')
    if len({id(m) for m in parts.values()}) != len(parts):
        raise ValueError('duplicated mesh input')
    offsets = {} if displacements is None else dict(displacements)
    for name, d in offsets.items():
        if name not in parts:
            raise ValueError(f'unknown displacement part {name!r}')
        d = np.asarray(d, float)
        if d.shape != (3,) or not np.isfinite(d).all() or not np.isfinite(np.linalg.norm(d)):
            raise ValueError(f'{name}: displacement must be a finite 3-vector')
        if np.linalg.norm(d) < _CLEAR_M:
            raise ValueError(f'{name}: separation displacement must be >= 6 mm')
        offsets[name] = d.copy()
    vertices, faces, fs, vs, owners, dropped = [], [], [], [], [], []
    for name, raw in parts.items():
        mesh = _poly(raw)
        if not len(mesh.vertices) or not mesh.faces:
            raise ValueError(f'{name}: empty mesh')
        used = sorted({i for f in mesh.faces for i in f})
        dropped.extend((name, i, 'unused input vertex') for i in range(len(mesh.vertices)) if i not in set(used))
        remap = {i: len(vertices) + k for k, i in enumerate(used)}
        vertices.extend(mesh.vertices[used] + offsets.get(name, np.zeros(3)))
        vs.extend(((name, i),) for i in used)
        for i, f in enumerate(mesh.faces):
            faces.append(tuple(remap[j] for j in f))
            fs.append(((name, i),))
            owners.append(name)
    v = np.array(vertices, float)
    original = {label: point.copy() for point, labels in zip(v, vs) for label in labels}
    # Freeze source incidence and target geometry for simultaneous, deterministic snaps.
    planes = [_plane(v, f) for f in faces]
    incidence = [[] for _ in v]
    for fi, f in enumerate(faces):
        for i in f:
            incidence[i].append(fi)
    # Stable source labels break equal-area ties independently of part order.
    order = sorted(range(len(faces)), key=lambda i: (-planes[i][1], fs[i]))
    rank = {fi: priority for priority, fi in enumerate(order)}
    authority = [min(rank[fi] for fi in incident) for incident in incidence]
    parent = list(range(len(v)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    best = np.full(len(v), len(faces))
    snapped = v.copy()
    for fi in order:
        f = faces[fi]
        n, _ = planes[fi]
        a = v[list(f)]
        b = np.roll(a, -1, axis=0)
        edges = b - a
        lengths = np.einsum('ij,ij->i', edges, edges)
        if np.any(lengths <= 1e-20):
            raise OperationRefused('zero length polygon edge')
        lo, hi = a.min(0) - _FACE_M, a.max(0) + _FACE_M
        candidates = np.flatnonzero(np.all((v >= lo) & (v <= hi), axis=1) & (best > rank[fi]))
        for i in candidates:
            if any(owners[j] == owners[fi] for j in incidence[i]):
                continue
            if not any(abs(np.dot(planes[j][0], n)) >= _COS for j in incidence[i]):
                continue
            plane_d = np.dot(v[i] - a[0], n)
            if abs(plane_d) > _FACE_M:
                continue
            projected = v[i] - plane_d * n
            t = np.clip(np.einsum('ij,ij->i', projected - a, edges) / lengths, 0, 1)
            points = a + t[:, None] * edges
            distances = np.linalg.norm(points - projected, axis=1)
            e = int(np.argmin(distances))
            # Only boundary projection is a seam; an interior overlap is not a seam.
            if distances[e] > _EPS or np.linalg.norm(points[e] - v[i]) > _FACE_M:
                continue
            snapped[i], best[i] = points[e], rank[fi]
            # Endpoint contacts are one equivalence class, not two independent
            # projections into each other's frozen positions. Include unilateral
            # corner contacts too (the reciprocal projection may miss a boundary).
            for endpoint in (f[e], f[(e + 1) % len(f)]):
                if np.linalg.norm(points[e] - v[endpoint]) <= _EPS:
                    aroot, broot = root(i), root(endpoint)
                    if (authority[aroot], vs[aroot]) > (authority[broot], vs[broot]):
                        aroot, broot = broot, aroot
                    parent[broot] = aroot
    groups = defaultdict(list)
    for i in range(len(v)):
        groups[root(i)].append(i)
    for anchor, members in groups.items():
        if len(members) > 1:
            snapped[members] = v[anchor]
    v, faces, vs = _weld(snapped, faces, vs)
    max_weld = max(float(np.linalg.norm(point - original[label]))
                   for point, labels in zip(v, vs) for label in labels)
    if max_weld > _FACE_M:
        raise OperationRefused('combined weld movement exceeds 5 mm')
    # Conform all edges, including the neighbour's edges in the same part. Points
    # inserted here already exist, so no source surface or vertex is silently lost.
    conformed = []
    for f in faces:
        ring = []
        for a, b in zip(f, f[1:] + f[:1]):
            edge = v[b] - v[a]
            den = np.dot(edge, edge)
            t = (v - v[a]) @ edge / den
            residual = np.linalg.norm(v - (v[a] + t[:, None] * edge), axis=1)
            ids = np.flatnonzero((t > _EPS) & (t < 1 - _EPS) & (residual <= _EPS))
            ring.append(a)
            ring.extend(int(i) for i in ids[np.argsort(t[ids], kind='stable')])
        if len(set(ring)) != len(ring):
            raise OperationRefused('conforming an edge would repeat a face vertex')
        conformed.append(tuple(ring))
    mesh = PolyMesh(v, tuple(conformed))
    for f in mesh.faces:
        _plane(v, f)
    pairs = face_pairs(mesh, XviewTolerance())
    if pairs:
        raise OperationRefused(f'join leaves {len(pairs)} xView contact/area pairs; first {pairs[0]}; '
                               'provide a valid separation or rebuild the joint')
    return SeamResult(mesh, tuple(fs), tuple(vs), tuple(dropped), max_weld,
                      {k: tuple(map(float, d)) for k, d in offsets.items()})


def simplify_part(parts, part, *, line_m=0.002):
    """Dissolve connected near-coplanar disks, then conform ALL seams atomically.

    Non-disk patches (holes/branching boundaries) are kept, never filled. A removed
    straight boundary point is restored when a neighbour still needs it. Thus face
    count is reduced without leaving the neighbour's boundary as a T-junction.
    Use polygon source labels to carry caller-owned material/UV data; this operation
    deliberately accepts no implicit material defaults or attribute interpolation.
    """
    if part not in parts:
        raise ValueError(f'unknown simplification part {part!r}')
    if isinstance(line_m, bool) or not np.isfinite(line_m) or not 0 <= line_m <= 0.002:
        raise ValueError('line_m must be finite and in [0, 0.002]')
    mesh = _poly(parts[part])
    if not mesh.faces:
        raise ValueError(f'{part}: empty mesh')
    v, faces = mesh.vertices, mesh.faces
    planes = [_plane(v, f) for f in faces]
    edge_faces = defaultdict(list)
    for fi, f in enumerate(faces):
        for a, b in zip(f, f[1:] + f[:1]):
            edge_faces[tuple(sorted((a, b)))].append(fi)
    neighbours = defaultdict(set)
    for ids in edge_faces.values():
        if len(ids) == 2:
            a, b = ids
            neighbours[a].add(b)
            neighbours[b].add(a)
    pending = set(range(len(faces)))
    output, source = [], []
    while pending:
        seed = min(pending)
        pending.remove(seed)
        group, queue = [seed], [seed]
        normal = planes[seed][0]
        anchor = v[faces[seed][0]]
        while queue:
            current = queue.pop()
            for other in sorted(neighbours[current] & pending):
                if np.dot(normal, planes[other][0]) < _COS:
                    continue
                if np.max(np.abs((v[list(faces[other])] - anchor) @ normal)) > line_m + 1e-12:
                    continue
                pending.remove(other)
                group.append(other)
                queue.append(other)
        edges = defaultdict(list)
        for fi in group:
            f = faces[fi]
            for a, b in zip(f, f[1:] + f[:1]):
                edges[tuple(sorted((a, b)))].append((a, b))
        boundary = [items[0] for items in edges.values() if len(items) == 1]
        next_vertex = dict(boundary)
        disk = bool(boundary) and len(next_vertex) == len(boundary)
        disk &= len({b for a, b in boundary}) == len(boundary)
        disk &= all(len(items) <= 2 and (len(items) == 1 or items[0] == items[1][::-1])
                    for items in edges.values())
        ring = []
        if disk:
            at = min(next_vertex)
            while at not in ring and at in next_vertex:
                ring.append(at)
                at = next_vertex[at]
            disk = len(ring) == len(boundary) and at == ring[0]
        if not disk:
            output.extend(faces[i] for i in sorted(group))
            source.extend(((part, i),) for i in sorted(group))
            continue
        # Each candidate chord is checked against EVERY original boundary point
        # it replaces, preventing a chain of individually small cumulative errors.
        paths = [[i] for i in ring]
        changed = True
        while changed and len(ring) > 3:
            changed = False
            for i in range(len(ring)):
                prev = (i - 1) % len(ring)
                a, b = v[ring[prev]], v[ring[(i + 1) % len(ring)]]
                edge = b - a
                den = np.dot(edge, edge)
                if den <= 1e-20:
                    continue
                removed = paths[prev] + paths[i]
                q = v[removed]
                t = (q - a) @ edge / den
                distance = np.linalg.norm(q - (a + t[:, None] * edge), axis=1)
                if np.all((t >= 0) & (t <= 1) & (distance <= line_m + 1e-12)):
                    paths[prev] = removed
                    del paths[i]
                    del ring[i]
                    changed = True
                    break
        output.append(tuple(ring))
        source.append(tuple((part, i) for i in sorted(group)))
    simplified = PolyMesh(v.copy(), tuple(output))
    result = join_parts({**parts, part: simplified})
    fs = tuple(tuple(original for name, i in labels
                     for original in (source[i] if name == part else ((name, i),)))
               for labels in result.face_sources)
    return replace(result, face_sources=fs)
