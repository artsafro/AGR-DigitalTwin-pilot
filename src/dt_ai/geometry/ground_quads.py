"""Conforming editable Ground patches from constrained triangle seeds.

Pattern: n/a | new-case: Steiner quad patches and source-preserving triangle pairs (#371).

Unpaired triangles become three quads. Coplanar, convex, same-slot/level seed
pairs become quad patches; parity propagation adds local two/four-quad
transitions, never T-junctions. Pair planarity allows 10 micrometres of serialized
coordinate noise and UV affinity allows 2e-6 UV units. Corner UVs are otherwise
interpolated locally; discontinuous shared-edge UVs prevent pairing.

CHECKPOINT ONLY: not integrated into the Ground builder. Real-size v014 probes
exceed the unchanged surface budget. This primitive does not assert budget,
xView, relief/gap, exported-file or delivery acceptance. See the v015 mesher
checkpoint report under jobs/VATUTINO-SITE/. No IO is performed.
"""
from collections import defaultdict
from dataclasses import dataclass
import heapq

from dt_ai.ops.inv_quads import PLANAR_DEG, PolyMesh, _mergeable

import numpy as np

from dt_ai.geometry.ground_cake import Mesh


@dataclass
class QuadMesh:
    verts: np.ndarray
    faces: tuple[tuple[int, ...], ...]
    slot: list[str]
    level: np.ndarray
    uv: np.ndarray | tuple[np.ndarray, ...]
    source_faces: tuple[tuple[int, ...], ...]
    cell: float


def _edges(face):
    return [tuple(sorted((int(a), int(face[(i + 1) % len(face)]))))
            for i, a in enumerate(face)]


def _pair(mesh, a, b, edge):
    f, g = tuple(mesh.faces[a]), tuple(mesh.faces[b])
    if mesh.slot[a] != mesh.slot[b] or mesh.level[a] != mesh.level[b]:
        return None
    if not _mergeable(mesh.verts, f, g, edge, 0.001):
        return None
    p = mesh.verts[list(f)]
    normal = np.cross(p[1] - p[0], p[2] - p[0])
    normal /= np.linalg.norm(normal)
    if np.max(np.abs((mesh.verts[list(g)] - p[0]) @ normal)) > 1e-5:
        return None
    successor = {}
    for face in (f, g):
        for x, y in zip(face, (*face[1:], face[0])):
            if tuple(sorted((x, y))) != edge:
                if x in successor:
                    return None  # inconsistent winding
                successor[x] = y
    ring = [f[0]]
    for _ in range(3):
        if ring[-1] not in successor:
            return None
        ring.append(successor[ring[-1]])
    if len(set(ring)) != 4 or successor.get(ring[-1]) != ring[0]:
        return None
    uv = dict(zip(f, mesh.uv[a]))
    for v, u in zip(g, mesh.uv[b]):
        if v in uv and not np.allclose(uv[v], u, atol=1e-10, rtol=0):
            return None
        uv[v] = u
    coeff = np.linalg.lstsq((p[1:] - p[0]).T,
                           (mesh.verts[ring] - p[0]).T, rcond=None)[0].T
    predicted = mesh.uv[a][0] + coeff @ (mesh.uv[a][1:] - mesh.uv[a][0])
    actual = np.asarray([uv[v] for v in ring])
    if not np.allclose(predicted, actual, atol=2e-6, rtol=0):
        return None
    return tuple(ring), actual


def _patches(mesh, pairer=_pair):
    incidence = defaultdict(list)
    for k, face in enumerate(mesh.faces):
        for e in _edges(face):
            incidence[e].append(k)
    candidates, adjacent = {}, [set() for _ in mesh.faces]
    for edge, ids in incidence.items():
        if len(ids) > 2:
            raise ValueError(f'nonmanifold seed edge {edge}: faces {ids}')
        if len(ids) != 2:
            continue
        a, b = ids
        merged = pairer(mesh, a, b, edge)
        if merged is not None:
            candidates[a, b] = merged
            adjacent[a].add(b)
            adjacent[b].add(a)
    heap = [(len(ns), k) for k, ns in enumerate(adjacent) if ns]
    heapq.heapify(heap)
    paired, used = {}, set()
    while heap:
        degree, a = heapq.heappop(heap)
        if a in used:
            continue
        ns = adjacent[a] - used
        if not ns:
            continue
        if degree != len(ns):
            heapq.heappush(heap, (len(ns), a))
            continue
        b = min(ns, key=lambda j: (len(adjacent[j] - used), j))
        used.update((a, b))
        pair = tuple(sorted((a, b)))
        paired[pair[0]] = (candidates[pair], pair)
        for j in adjacent[a] | adjacent[b]:
            if j not in used:
                heapq.heappush(heap, (len(adjacent[j] - used), j))
    out = []
    for k, face in enumerate(mesh.faces):
        if k in paired:
            (ring, uv), parent = paired[k]
            out.append((ring, uv, parent))
        elif k not in used:
            out.append((tuple(face), mesh.uv[k], (k,)))
    return out


def _ring(face, uv, verts, split):
    """Boundary vertices/UVs including only requested edge midpoints."""
    points, tex = [], []
    for i, a in enumerate(face):
        b = face[(i + 1) % len(face)]
        points.append(verts[a])
        tex.append(uv[i])
        if tuple(sorted((int(a), int(b)))) in split:
            points.append((verts[a] + verts[b]) / 2)
            tex.append((uv[i] + uv[(i + 1) % len(face)]) / 2)
    return np.asarray(points), np.asarray(tex)


def _transition(points):
    """Two convex quads filling a six-vertex planar ring, or no valid split."""
    for i in range(3):
        parts = [tuple((i + j) % 6 for j in range(4)),
                 tuple((i + 3 + j) % 6 for j in range(4))]
        valid = True
        for ids in parts:
            p = points[list(ids)]
            e = np.roll(p, -1, axis=0) - p
            n = np.cross(e[0], e[1])
            length = np.linalg.norm(n)
            if length <= 1e-14 or not np.all(np.cross(e, np.roll(e, -1, axis=0)) @ (n / length) > 1e-14):
                valid = False
                break
        if valid:
            return parts
    return None


def pair_triangles(mesh: Mesh, *, excluded_pairs=()) -> QuadMesh:
    """Option (a): D129-compatible pairing, no new points or changed tessellation.

    Every output face carries its exact source triangle IDs. The quad's 0--2
    diagonal is the original shared edge, so its fixed-fan tessellation is exactly
    the source surface (including nonplanar pairs within D129's one degree).
    UV discontinuities, material/level boundaries and inconsistent winding are
    not crossed. ``excluded_pairs`` names zero-based source triangle pairs proven
    unsafe by an export/alternate-diagonal check; these candidates are not merged.
    Alternate valid matches remain possible. Exclusion is not a safety certificate:
    every resulting/exported face still requires checks. This primitive neither
    relaxes D129 nor claims xView acceptance.
    """
    _validate_seed(mesh)
    excluded = set()
    for ids in excluded_pairs:
        if (not isinstance(ids, (tuple, list)) or len(ids) != 2
                or any(isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer))
                       or not 0 <= i < len(mesh.faces) for i in ids)
                or ids[0] == ids[1]):
            raise ValueError(f'invalid excluded pair: {ids!r}')
        key = tuple(sorted(map(int, ids)))
        if key in excluded:
            raise ValueError(f'duplicate excluded pair: {ids!r}')
        excluded.add(key)

    def pair(m, a, b, edge):
        if tuple(sorted((a, b))) in excluded:
            return None
        f, g = tuple(m.faces[a]), tuple(m.faces[b])
        if m.slot[a] != m.slot[b] or m.level[a] != m.level[b]:
            return None
        if not _mergeable(m.verts, f, g, edge, PLANAR_DEG):
            return None
        # Start at the shared diagonal: the exporter must keep this tessellation.
        start = edge[0]
        successor = {}
        for tri in (f, g):
            for x, y in zip(tri, (*tri[1:], tri[0])):
                if tuple(sorted((x, y))) != edge:
                    if x in successor:
                        return None
                    successor[x] = y
        ring = [start]
        for _ in range(3):
            if ring[-1] not in successor:
                return None
            ring.append(successor[ring[-1]])
        if len(set(ring)) != 4 or successor.get(ring[-1]) != start:
            return None
        uv = dict(zip(f, m.uv[a]))
        for v, value in zip(g, m.uv[b]):
            if v in uv and not np.allclose(uv[v], value, atol=1e-6, rtol=0):
                return None
            uv[v] = value
        return tuple(ring), np.asarray([uv[v] for v in ring])

    patches = _patches(mesh, pair)
    return QuadMesh(mesh.verts.copy(), tuple(f for f, _, _ in patches),
                    [mesh.slot[ids[0]] for _, _, ids in patches],
                    np.array([mesh.level[ids[0]] for _, _, ids in patches]),
                    tuple(uv.copy() for _, uv, _ in patches),
                    tuple(ids for _, _, ids in patches), mesh.cell)


def _validate_seed(mesh: Mesh):
    """Reject malformed or ambiguous triangle seeds before either conversion."""
    checked = PolyMesh(mesh.verts, tuple(map(tuple, mesh.faces)))
    if not checked.faces or any(len(f) != 3 for f in checked.faces):
        raise ValueError('nonempty triangle seed required')
    n = len(checked.faces)
    if len(mesh.slot) != n or any(not isinstance(s, str) or not s.strip() for s in mesh.slot):
        raise ValueError('every seed face requires a nonblank texture slot')
    if np.shape(mesh.level) != (n,) or not np.isfinite(mesh.level).all():
        raise ValueError('every seed face requires a finite level')
    if np.shape(mesh.uv) != (n, 3, 2) or not np.isfinite(mesh.uv).all():
        raise ValueError('every seed corner requires finite UV coordinates')
    if not np.isfinite(mesh.cell) or mesh.cell <= 0:
        raise ValueError('cell must be positive and finite')
    seen = set()
    for k, f in enumerate(checked.faces):
        p = checked.vertices[list(f)]
        area = np.linalg.norm(np.cross(p[1] - p[0], p[2] - p[0])) / 2
        if not np.isfinite(area) or area <= 1e-12:
            raise ValueError(f'seed face {k}: degenerate or nonfinite area')
        key = tuple(sorted(f))
        if key in seen:
            raise ValueError(f'seed face {k}: duplicate face {key}')
        seen.add(key)


def remesh(mesh: Mesh) -> QuadMesh:
    """Conforming all-quad remesh; shared vertices and per-corner UV seams persist."""
    _validate_seed(mesh)
    patches = _patches(mesh)
    vertices = mesh.verts.tolist()
    midpoints = {}
    faces, uvs, slots, levels, sources = [], [], [], [], []
    split = {e for f, _, _ in patches if len(f) == 3 for e in _edges(f)}
    changed = True
    while changed:
        changed = False
        for face, uv, _ in patches:
            if len(face) != 4:
                continue
            es = _edges(face)
            marked = [e in split for e in es]
            if sum(marked) % 2:
                i = marked.index(True)
                j = (i + 2) % 4 if sum(marked) == 1 else marked.index(False)
                split.add(es[j])
                changed = True
            if sum(e in split for e in es) == 2:
                ring, _ = _ring(face, uv, mesh.verts, split)
                if _transition(ring) is None:
                    split.update(es)
                    changed = True
    for face, uv, parent in patches:
        es = _edges(face)
        if not any(e in split for e in es):
            faces.append(face)
            uvs.append(uv)
            slots.append(mesh.slot[parent[0]])
            levels.append(mesh.level[parent[0]])
            sources.append(parent)
            continue
        if len(face) == 4 and sum(e in split for e in es) == 2:
            ids = []
            for i, a in enumerate(face):
                ids.append(int(a))
                edge = es[i]
                if edge in split:
                    if edge not in midpoints:
                        midpoints[edge] = len(vertices)
                        vertices.append(mesh.verts[list(edge)].mean(axis=0).tolist())
                    ids.append(midpoints[edge])
            ring, tex = _ring(face, uv, mesh.verts, split)
            transition = _transition(ring)
            if transition is None:
                raise ValueError('quad transition closure inconsistent')
            for part in transition:
                faces.append(tuple(ids[j] for j in part))
                uvs.append(tex[list(part)])
                slots.append(mesh.slot[parent[0]])
                levels.append(mesh.level[parent[0]])
                sources.append(parent)
            continue
        center = len(vertices)
        vertices.append(mesh.verts[list(face)].mean(axis=0).tolist())
        mids = []
        for edge in es:
            if edge not in midpoints:
                midpoints[edge] = len(vertices)
                vertices.append(mesh.verts[list(edge)].mean(axis=0).tolist())
            mids.append(midpoints[edge])
        for i, a in enumerate(face):
            faces.append((int(a), mids[i], center, mids[i - 1]))
            uvs.append([uv[i], (uv[i] + uv[(i + 1) % len(face)]) / 2,
                        uv.mean(axis=0), (uv[i - 1] + uv[i]) / 2])
            slots.append(mesh.slot[parent[0]])
            levels.append(mesh.level[parent[0]])
            sources.append(parent)
    return QuadMesh(np.asarray(vertices), tuple(faces), slots, np.asarray(levels),
                    np.asarray(uvs), tuple(sources), mesh.cell)

