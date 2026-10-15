"""Component-local signed volume for occluded solids.

Report-only prototype. Components are split by shared undirected vertex-index
edges. Positions are never welded and meshes are never merged.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


_REASON_OPEN = "open_or_nonmanifold_edge"
_REASON_WINDING = "inconsistent_winding"
_REASON_DEGENERATE = "degenerate_triangle"
_REASON_FAN = "vertex_not_single_fan"


def component_signed_volumes(meshes: list[dict]) -> list[dict]:
    """Signed volume of each index-connected component, per mesh."""
    results = []
    for mesh in meshes:
        results.extend(_mesh_components(mesh))
    return results


def positive_sum(results: list[dict]) -> float:
    """Diagnostic sum of signed volumes of eligible components."""
    return math.fsum(row["signed_volume"] for row in results if row["eligible"])


def _mesh_components(mesh: dict) -> list[dict]:
    vertices = np.asarray(mesh["vertices"], dtype=np.float64)
    triangles = [[int(i) for i in tri] for tri in mesh["triangles"]]
    out = []
    for tri_ids in _connected_components(triangles):
        out.append(_measure_component(str(mesh["name"]), vertices, triangles, tri_ids))
    return out


def _connected_components(triangles: list[list[int]]) -> list[list[int]]:
    """Union-find over triangle ids. Adjacent iff they share an index edge."""
    parent = list(range(len(triangles)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    edge_tris: dict[tuple[int, int], list[int]] = defaultdict(list)
    for tri_id, tri in enumerate(triangles):
        for edge in _undirected_edges(tri):
            edge_tris[edge].append(tri_id)
    for ids in edge_tris.values():
        for other in ids[1:]:
            union(ids[0], other)

    groups: dict[int, list[int]] = defaultdict(list)
    for tri_id in range(len(triangles)):
        groups[find(tri_id)].append(tri_id)
    components = [sorted(ids) for ids in groups.values()]
    components.sort(key=lambda ids: ids[0])
    return components


def _measure_component(name: str, vertices: np.ndarray, triangles: list[list[int]], tri_ids: list[int]) -> dict:
    edge_users: dict[tuple[int, int], list[int]] = defaultdict(list)
    directed: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for tri_id in tri_ids:
        tri = triangles[tri_id]
        for a, b in _directed_edges(tri):
            edge = _undirected(a, b)
            edge_users[edge].append(tri_id)
            directed[edge].append((a, b))

    edges_ok = all(_exactly_two_distinct(ids) for ids in edge_users.values())
    winding_ok = all(_opposite_pair(uses) for uses in directed.values())
    degenerate_ok = _triangles_nondegenerate(vertices, triangles, tri_ids)
    fan_ok = _single_fan_per_vertex(triangles, tri_ids, edge_users)

    reasons = []
    if not edges_ok:
        reasons.append(_REASON_OPEN)
    if not winding_ok:
        reasons.append(_REASON_WINDING)
    if not degenerate_ok:
        reasons.append(_REASON_DEGENERATE)
    if not fan_ok:
        reasons.append(_REASON_FAN)
    eligible = not reasons

    signed_volume = None
    sign = None
    if eligible:
        signed_volume = _signed_volume(vertices, triangles, tri_ids)
        sign = _sign_of(signed_volume)

    return {
        "mesh": name,
        "triangle_ids": list(tri_ids),
        "n_triangles": len(tri_ids),
        "eligible": eligible,
        "reasons": reasons,
        "status": "measured" if eligible else "not_measured",
        "signed_volume": signed_volume,
        "sign": sign,
    }


def _triangles_nondegenerate(vertices: np.ndarray, triangles: list[list[int]], tri_ids: list[int]) -> bool:
    used = _used_indices(triangles, tri_ids)
    pts = vertices[used]
    diagonal = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0)))
    limit = 1e-12 * diagonal * diagonal
    for tri_id in tri_ids:
        a, b, c = triangles[tri_id]
        if len({a, b, c}) < 3:
            return False
        area = 0.5 * float(np.linalg.norm(np.cross(vertices[b] - vertices[a], vertices[c] - vertices[a])))
        if not area > limit:
            return False
    return True


def _single_fan_per_vertex(triangles: list[list[int]], tri_ids: list[int], edge_users: dict) -> bool:
    incident: dict[int, list[int]] = defaultdict(list)
    for tri_id in tri_ids:
        seen = set()
        for vertex in triangles[tri_id]:
            if vertex not in seen:
                incident[vertex].append(tri_id)
                seen.add(vertex)
    member = set(tri_ids)
    for vertex, tris_v in incident.items():
        local = {tri_id: tri_id for tri_id in tris_v}

        def find(x: int, local=local) -> int:
            while local[x] != x:
                local[x] = local[local[x]]
                x = local[x]
            return x

        def union(a: int, b: int) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                local[rb] = ra

        for edge, users in edge_users.items():
            if vertex not in edge:
                continue
            group = [tri_id for tri_id in users if tri_id in member and tri_id in local]
            for other in group[1:]:
                union(group[0], other)
        if len({find(tri_id) for tri_id in tris_v}) != 1:
            return False
    return True


def _signed_volume(vertices: np.ndarray, triangles: list[list[int]], tri_ids: list[int]) -> float:
    used = _used_indices(triangles, tri_ids)
    reference = vertices[used].mean(axis=0)
    terms = []
    for tri_id in tri_ids:
        a, b, c = triangles[tri_id]
        pa = vertices[a] - reference
        pb = vertices[b] - reference
        pc = vertices[c] - reference
        terms.append(float(np.dot(pa, np.cross(pb, pc))))
    return math.fsum(terms) / 6.0


def _used_indices(triangles: list[list[int]], tri_ids: list[int]) -> list[int]:
    return sorted({vertex for tri_id in tri_ids for vertex in triangles[tri_id]})


def _directed_edges(tri: list[int]) -> list[tuple[int, int]]:
    a, b, c = tri
    return [(a, b), (b, c), (c, a)]


def _undirected_edges(tri: list[int]) -> list[tuple[int, int]]:
    return [_undirected(a, b) for a, b in _directed_edges(tri)]


def _undirected(a: int, b: int) -> tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def _exactly_two_distinct(ids: list[int]) -> bool:
    return len(ids) == 2 and ids[0] != ids[1]


def _opposite_pair(uses: list[tuple[int, int]]) -> bool:
    if len(uses) != 2:
        return False
    (a, b), (c, d) = uses
    return a == d and b == c and a != b


def _sign_of(volume: float) -> int | None:
    if volume > 0.0:
        return 1
    if volume < 0.0:
        return -1
    return None
