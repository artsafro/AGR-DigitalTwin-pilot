"""Regulatory topology defect count (reg p.8 §3.7, p.29 §3.11) for scene stage V004.

new-case: regulatory topology count on an FBX readback (issue #160)

Per mesh object, with ``tol`` = 0.002 m unless the caller overrides it. Vertex
positions are world coordinates. A cluster is a connected component of the graph
that links two vertices at Euclidean distance <= tol + 1e-9. Clusters are built
by grid hashing (cell size ``tol``), neighbour-cell comparisons and union-find.

- duplicate_vertices: number of vertices minus number of clusters (2 coincident
  vertices = 1 duplicate; 3 = 2).
- duplicate_edges: map every edge (polygon sides plus loose edges, unique by
  vertex-index pair) to its unordered cluster pair; ignore edges whose two ends
  are in the same cluster (zero-length or degenerate, not duplicates); count =
  number of such edges minus the number of distinct cluster pairs among them.
- duplicate_polygons: map every polygon to the sorted tuple of the clusters of
  its vertices (a multiset, sorted); count = polygons minus distinct keys.
- self_intersections: number of distinct unordered polygon pairs that meet
  either rule below (the union of both). Polygons are triangulated with a fan
  from their first vertex; fan diagonals are edges for the second rule. Pairs
  that share 3 or more vertex clusters are not tested (duplicate polygons are
  counted elsewhere). Coplanar face contact and touching-only contact are not
  self-intersections. ``candidate_pairs`` still decides which polygon pairs are
  tested. In both rules ``tol`` is the regulatory distance tolerance (0.002 m
  unless the caller overrides it); a penetration within ``tol`` is not counted.
  Pierce. An edge of one fan triangle crosses the plane of another at a point
  inside that triangle. The signed distances of the segment endpoints to the
  plane have opposite signs and each absolute value is greater than ``tol``.
  The crossing point is inside the closed triangle: every barycentric coordinate
  is greater than -1e-9, so a transversal that lands on a triangle edge is
  counted (two axis-aligned cubes that overlap by half a metre on every axis
  and meet along a face diagonal). When the polygons share one cluster, that
  hit counts only if the crossing point is farther than ``tol`` from the shared
  vertex, using the position of a vertex of polygon p (the lower polygon index)
  in that cluster. When they share two clusters, it counts only if the point is
  farther than ``tol`` from the segment joining p's vertex in each of those
  clusters. A pair that only meets at the shared vertex or along that shared
  segment is not a self-intersection.
  Edge-on-plane crossing. For a fan triangle t of one polygon (plane pi_t, unit
  normal n) and a fan triangle s of the other, and with the two polygons
  swapped: exactly two vertices of s are an edge e with absolute signed distance
  to pi_t at most ``tol``, and the third vertex (the apex) is beyond ``tol`` on
  one side (sign sigma). The edge e is not a side of t by unordered cluster
  pair, so a welded junction (e is a side of t) is not counted. The part of e
  inside the closed triangle t — the segment projected into the plane of t and
  clipped against t's three edge half-planes with epsilon 1e-9 — is longer than
  ``tol``. Some other fan triangle of the mesh, belonging to any polygon other
  than the polygon of t, has an edge with the same unordered cluster pair as e
  and an apex whose signed distance to pi_t is beyond ``tol`` with the opposite
  sign. That neighbour is taken from the mesh edge map, not from the candidate
  list. The counted polygon pair is (polygon of t, the polygon whose fan
  triangle on e has the positive apex). A tested triangle with sigma = -1 does
  not add its own polygon; the positive polygon is read from the edge map, so
  one crossing surface contributes one pair even when only the negative side
  was a candidate.
- isolated_vertices: vertices used by no edge and no polygon.
- isolated_edges: edges from the given edge list that are not a side of any
  polygon (loose or wire edges). When no edge list is given, this is 0.
- isolated_polygons: polygons that share no vertex index with any other polygon
  (a connected component, through shared vertex indices, of exactly one polygon).
- zero_length_edges: edges (polygon sides and given edges) whose length is
  <= 1e-6 m.
- duplicates_and_self_intersections: duplicate_vertices + duplicate_edges +
  duplicate_polygons + self_intersections.
"""
from __future__ import annotations

import numpy as np

TOL_M = 0.002
ZERO_EDGE_M = 1e-6
_PLANE_EPS = 1e-9
_LINK_EPS = 1e-9


def count_defects(vertices, polygons, edges=None, tol=TOL_M, candidate_pairs=None) -> dict:
    """vertices: (n,3) floats; polygons: sequence of vertex-index sequences (len >= 3);
    edges: optional (m,2) vertex-index pairs = ALL edges of the mesh incl. loose ones (Blender mesh.edges);
    when None, edges = the unique polygon sides. candidate_pairs: optional iterable of (p, q) polygon index
    pairs to test for self-intersection (e.g. from a BVH); when None, candidates come from an internal
    axis-aligned bounding box broad phase (vectorised, sort-and-sweep or grid; must handle 20 000 triangles
    in a few seconds). Returns a dict with the 9 integer keys above plus "tol_m": tol."""
    verts = np.asarray(vertices, dtype=np.float64)
    if verts.size == 0:
        verts = np.zeros((0, 3), dtype=np.float64)
    elif verts.ndim != 2 or verts.shape[1] != 3:
        verts = verts.reshape(-1, 3)
    polys = [np.asarray(poly, dtype=np.int64).reshape(-1) for poly in polygons]
    tol = float(tol)
    clusters = _cluster_ids(verts, tol)
    side_set = _polygon_sides(polys)
    given_set = None if edges is None else _edge_set(edges)
    all_edges = set(side_set)
    if given_set is not None:
        all_edges |= given_set
    edge_arr = _edges_array(all_edges)

    duplicate_vertices = int(len(verts) - (0 if len(verts) == 0 else len(np.unique(clusters))))
    duplicate_edges = _duplicate_edges(edge_arr, clusters)
    duplicate_polygons = _duplicate_polygons(polys, clusters)
    self_intersections = _self_intersections(verts, polys, clusters, candidate_pairs, tol)
    isolated_vertices = _isolated_vertices(len(verts), polys, given_set if given_set is not None else side_set)
    isolated_edges = 0 if given_set is None else len(given_set - side_set)
    isolated_polygons = _isolated_polygons(polys)
    zero_length_edges = _zero_length(verts, edge_arr)
    duplicates_and_self_intersections = (
        duplicate_vertices + duplicate_edges + duplicate_polygons + self_intersections
    )
    return {
        "duplicate_vertices": duplicate_vertices,
        "duplicate_edges": duplicate_edges,
        "duplicate_polygons": duplicate_polygons,
        "self_intersections": self_intersections,
        "isolated_vertices": isolated_vertices,
        "isolated_edges": isolated_edges,
        "isolated_polygons": isolated_polygons,
        "zero_length_edges": zero_length_edges,
        "duplicates_and_self_intersections": duplicates_and_self_intersections,
        "tol_m": tol,
    }


def _cluster_ids(vertices: np.ndarray, tol: float) -> np.ndarray:
    n = len(vertices)
    parent = np.arange(n, dtype=np.int64)
    if n == 0 or tol <= 0:
        return parent
    eps2 = (tol + _LINK_EPS) ** 2
    cell = np.floor(vertices / tol).astype(np.int64)
    buckets: dict[tuple[int, int, int], list[int]] = {}
    for i in range(n):
        key = (int(cell[i, 0]), int(cell[i, 1]), int(cell[i, 2]))
        buckets.setdefault(key, []).append(i)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = int(parent[i])
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    offsets = [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if (dx, dy, dz) > (0, 0, 0)
    ]
    for key, idxs in buckets.items():
        _link_close(idxs, vertices, idxs, vertices, eps2, union, intra=True)
        for dx, dy, dz in offsets:
            nb = buckets.get((key[0] + dx, key[1] + dy, key[2] + dz))
            if nb:
                _link_close(idxs, vertices, nb, vertices, eps2, union, intra=False)
    for i in range(n):
        find(i)
    _, inverse = np.unique(parent, return_inverse=True)
    return inverse.astype(np.int64, copy=False)


def _link_close(ia, pa, ib, pb, eps2, union, intra: bool) -> None:
    ia = np.asarray(ia, dtype=np.int64)
    ib = np.asarray(ib, dtype=np.int64)
    block = 96
    n_a, n_b = len(ia), len(ib)
    for i0 in range(0, n_a, block):
        aa = pa[ia[i0:i0 + block]]
        i_slice = ia[i0:i0 + block]
        j_from = i0 if intra else 0
        for j0 in range(j_from, n_b, block):
            bb = pb[ib[j0:j0 + block]]
            j_slice = ib[j0:j0 + block]
            dist2 = np.sum((aa[:, None, :] - bb[None, :, :]) ** 2, axis=-1)
            if intra and i0 == j0:
                close = dist2 <= eps2
                close = np.triu(close, 1) if close.shape[0] == close.shape[1] else close
                ii, jj = np.nonzero(close)
            else:
                ii, jj = np.nonzero(dist2 <= eps2)
            if len(ii) == 0:
                continue
            for a, b in zip(i_slice[ii].tolist(), j_slice[jj].tolist()):
                union(a, b)


def _polygon_sides(polys: list[np.ndarray]) -> set[tuple[int, int]]:
    sides: set[tuple[int, int]] = set()
    for poly in polys:
        m = len(poly)
        if m < 2:
            continue
        for i in range(m):
            a = int(poly[i])
            b = int(poly[(i + 1) % m])
            sides.add((a, b) if a <= b else (b, a))
    return sides


def _edge_set(edges) -> set[tuple[int, int]]:
    arr = np.asarray(edges, dtype=np.int64)
    if arr.size == 0:
        return set()
    arr = arr.reshape(-1, 2)
    out: set[tuple[int, int]] = set()
    for a, b in arr.tolist():
        out.add((a, b) if a <= b else (b, a))
    return out


def _edges_array(pairs: set[tuple[int, int]]) -> np.ndarray:
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    return np.asarray(sorted(pairs), dtype=np.int64)


def _duplicate_edges(edge_arr: np.ndarray, clusters: np.ndarray) -> int:
    if len(edge_arr) == 0 or len(clusters) == 0:
        return 0
    c0 = clusters[edge_arr[:, 0]]
    c1 = clusters[edge_arr[:, 1]]
    lo = np.minimum(c0, c1)
    hi = np.maximum(c0, c1)
    mask = lo != hi
    if not np.any(mask):
        return 0
    stacked = np.stack((lo[mask], hi[mask]), axis=1)
    return int(stacked.shape[0] - np.unique(stacked, axis=0).shape[0])


def _duplicate_polygons(polys: list[np.ndarray], clusters: np.ndarray) -> int:
    if not polys or len(clusters) == 0:
        return 0
    keys = [tuple(sorted(int(c) for c in clusters[poly])) for poly in polys]
    return len(keys) - len(set(keys))


def _isolated_vertices(n: int, polys: list[np.ndarray], edges: set[tuple[int, int]]) -> int:
    if n == 0:
        return 0
    used = np.zeros(n, dtype=bool)
    for poly in polys:
        if len(poly):
            used[poly] = True
    if edges:
        idx = np.fromiter((v for pair in edges for v in pair), dtype=np.int64, count=len(edges) * 2)
        if len(idx):
            used[idx] = True
    return int(np.count_nonzero(~used))


def _isolated_polygons(polys: list[np.ndarray]) -> int:
    n = len(polys)
    if n == 0:
        return 0
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb if ra < rb else ra] = ra if ra < rb else rb

    owners: dict[int, int] = {}
    for pi, poly in enumerate(polys):
        for v in {int(i) for i in poly.tolist()}:
            prev = owners.get(v)
            if prev is None:
                owners[v] = pi
            else:
                union(prev, pi)
    sizes: dict[int, int] = {}
    roots = [find(i) for i in range(n)]
    for r in roots:
        sizes[r] = sizes.get(r, 0) + 1
    return sum(1 for r in roots if sizes[r] == 1)


def _zero_length(vertices: np.ndarray, edge_arr: np.ndarray) -> int:
    if len(edge_arr) == 0 or len(vertices) == 0:
        return 0
    delta = vertices[edge_arr[:, 0]] - vertices[edge_arr[:, 1]]
    length = np.linalg.norm(delta, axis=1)
    return int(np.count_nonzero(length <= ZERO_EDGE_M))


def _self_intersections(vertices, polys, clusters, candidate_pairs, tol: float) -> int:
    n_poly = len(polys)
    if n_poly < 2 or len(vertices) == 0:
        return 0
    if candidate_pairs is None:
        pairs = _aabb_pairs(vertices, polys)
    else:
        seen: set[tuple[int, int]] = set()
        pairs = []
        for p, q in candidate_pairs:
            a, b = int(p), int(q)
            if a == b:
                continue
            if a > b:
                a, b = b, a
            if (a, b) not in seen and 0 <= a < n_poly and 0 <= b < n_poly:
                seen.add((a, b))
                pairs.append((a, b))
    if not pairs:
        return 0
    poly_clusters = [set(int(c) for c in clusters[poly]) for poly in polys]
    fans = []
    for poly in polys:
        if len(poly) < 3:
            fans.append(np.zeros((0, 3), dtype=np.int64))
            continue
        p0 = int(poly[0])
        fans.append(np.asarray([(p0, int(poly[i]), int(poly[i + 1])) for i in range(1, len(poly) - 1)], dtype=np.int64))
    edge_map, fan_ids = _fan_edge_map(fans, clusters)
    usable: list[tuple[int, int, set[int]]] = []
    for p, q in pairs:
        shared = poly_clusters[p] & poly_clusters[q]
        if len(shared) >= 3 or len(fans[p]) == 0 or len(fans[q]) == 0:
            continue
        usable.append((p, q, shared))
    if not usable:
        return 0
    pierced = _pierce_pairs(vertices, polys, clusters, fans, usable, tol)
    on_plane = _edge_on_plane_pairs(vertices, fans, fan_ids, usable, edge_map, clusters, tol)
    return len(pierced | on_plane)


def _aabb_pairs(vertices: np.ndarray, polys: list[np.ndarray]) -> list[tuple[int, int]]:
    """Sort-and-sweep on polygon bounding boxes. Overlaps are deterministic."""
    n = len(polys)
    if n < 2:
        return []
    mins = np.empty((n, 3), dtype=np.float64)
    maxs = np.empty((n, 3), dtype=np.float64)
    for i, poly in enumerate(polys):
        pts = vertices[poly]
        mins[i] = pts.min(axis=0)
        maxs[i] = pts.max(axis=0)
    order = np.argsort(mins[:, 0], kind="mergesort")
    active: list[int] = []
    pairs: list[tuple[int, int]] = []
    max_x = maxs[:, 0]
    for raw in order:
        idx = int(raw)
        x0 = float(mins[idx, 0])
        if active:
            act = np.asarray(active, dtype=np.int64)
            active = act[max_x[act] >= x0].tolist()
        if active:
            act = np.asarray(active, dtype=np.int64)
            overlap = (
                (maxs[idx, 1] >= mins[act, 1])
                & (maxs[act, 1] >= mins[idx, 1])
                & (maxs[idx, 2] >= mins[act, 2])
                & (maxs[act, 2] >= mins[idx, 2])
            )
            for j in act[overlap].tolist():
                pairs.append((idx, j) if idx < j else (j, idx))
        active.append(idx)
    return pairs


def _plane_tol(tol: float) -> float:
    return tol if tol > 0 else _PLANE_EPS


def _fan_edge_map(fans, clusters):
    """Unordered cluster-pair -> (polygon index, fan id, apex vertex) for every fan edge."""
    edge_map: dict[tuple[int, int], list[tuple[int, int, int]]] = {}
    fan_ids: list[np.ndarray] = []
    next_id = 0
    for pi, fan in enumerate(fans):
        ids = np.empty(len(fan), dtype=np.int64)
        for ti in range(len(fan)):
            ids[ti] = next_id
            vs = [int(fan[ti, 0]), int(fan[ti, 1]), int(fan[ti, 2])]
            cs = [int(clusters[v]) for v in vs]
            for i in range(3):
                a, b = cs[i], cs[(i + 1) % 3]
                if a == b:
                    continue
                key = (a, b) if a < b else (b, a)
                edge_map.setdefault(key, []).append((pi, next_id, vs[(i + 2) % 3]))
            next_id += 1
        fan_ids.append(ids)
    return edge_map, fan_ids


def _shared_simplex(poly, clusters, shared, vertices):
    """Positions of polygon p's vertex in each shared cluster, padded to two slots."""
    slots = np.zeros((2, 3), dtype=np.float64)
    count = 0
    for cluster in shared:
        for vertex in poly.tolist():
            index = int(vertex)
            if int(clusters[index]) == int(cluster):
                slots[count] = vertices[index]
                count += 1
                break
    return count, slots


def _pierce_pairs(vertices, polys, clusters, fans, usable, tol: float) -> set[tuple[int, int]]:
    src_rows: list[np.ndarray] = []
    dst_rows: list[np.ndarray] = []
    pair_rows: list[tuple[int, int]] = []
    simplex_n: list[int] = []
    simplex_pts: list[np.ndarray] = []
    for p, q, shared in usable:
        count, slots = _shared_simplex(polys[p], clusters, shared, vertices) if shared else (0, np.zeros((2, 3)))
        fa, fb = fans[p], fans[q]
        for tri in fa:
            n = len(fb)
            src_rows.append(np.repeat(tri.reshape(1, 3), n, axis=0))
            dst_rows.append(fb)
            pair_rows.extend([(p, q)] * n)
            simplex_n.extend([count] * n)
            simplex_pts.extend([slots] * n)
        for tri in fb:
            n = len(fa)
            src_rows.append(np.repeat(tri.reshape(1, 3), n, axis=0))
            dst_rows.append(fa)
            pair_rows.extend([(p, q)] * n)
            simplex_n.extend([count] * n)
            simplex_pts.extend([slots] * n)
    if not src_rows:
        return set()
    src = np.concatenate(src_rows, axis=0)
    dst = np.concatenate(dst_rows, axis=0)
    counts = np.asarray(simplex_n, dtype=np.int64)
    slots = np.stack(simplex_pts, axis=0)
    hits: set[tuple[int, int]] = set()
    step = 8192
    for start in range(0, len(src), step):
        stop = min(start + step, len(src))
        mask = _edges_pierce(vertices, src[start:stop], dst[start:stop], tol, counts[start:stop], slots[start:stop])
        if np.any(mask):
            hits.update(pair_rows[start + i] for i in np.flatnonzero(mask).tolist())
    return hits


def _edge_on_plane_pairs(vertices, fans, fan_ids, usable, edge_map, clusters, tol: float) -> set[tuple[int, int]]:
    t_rows: list[np.ndarray] = []
    s_rows: list[np.ndarray] = []
    s_fan_rows: list[np.ndarray] = []
    plane_rows: list[np.ndarray] = []
    other_rows: list[np.ndarray] = []
    for p, q, _shared in usable:
        _stack_directed(fans[p], fans[q], fan_ids[q], p, q, t_rows, s_rows, s_fan_rows, plane_rows, other_rows)
        _stack_directed(fans[q], fans[p], fan_ids[p], q, p, t_rows, s_rows, s_fan_rows, plane_rows, other_rows)
    if not t_rows:
        return set()
    t_idx = np.concatenate(t_rows, axis=0)
    s_idx = np.concatenate(s_rows, axis=0)
    s_fan = np.concatenate(s_fan_rows, axis=0)
    plane_poly = np.concatenate(plane_rows, axis=0)
    other_poly = np.concatenate(other_rows, axis=0)
    plane_tol = _plane_tol(tol)
    hits: set[tuple[int, int]] = set()
    step = 8192
    for start in range(0, len(t_idx), step):
        stop = start + step
        mask, unit = _exactly_two_on_plane(vertices, t_idx[start:stop], s_idx[start:stop], plane_tol)
        if not np.any(mask):
            continue
        _accept_on_plane_rows(
            hits, np.flatnonzero(mask), vertices, clusters, edge_map, plane_tol, tol,
            t_idx[start:stop], s_idx[start:stop], s_fan[start:stop],
            plane_poly[start:stop], other_poly[start:stop], unit,
        )
    return hits


def _stack_directed(t_fan, s_fan, s_ids, plane, other, t_rows, s_rows, s_fan_rows, plane_rows, other_rows):
    nt, ns = len(t_fan), len(s_fan)
    if nt == 0 or ns == 0:
        return
    t_rows.append(np.repeat(t_fan, ns, axis=0))
    s_rows.append(np.tile(s_fan, (nt, 1)))
    s_fan_rows.append(np.tile(s_ids, nt))
    plane_rows.append(np.full(nt * ns, plane, dtype=np.int64))
    other_rows.append(np.full(nt * ns, other, dtype=np.int64))


def _exactly_two_on_plane(vertices, t_idx, s_idx, plane_tol: float):
    """Vectorised step 1: exactly two vertices of s on the plane of t, apex beyond tol."""
    v0 = vertices[t_idx[:, 0]]
    v1 = vertices[t_idx[:, 1]]
    v2 = vertices[t_idx[:, 2]]
    normal = np.cross(v1 - v0, v2 - v0)
    norm_len = np.linalg.norm(normal, axis=1)
    valid = norm_len > 1e-15
    unit = np.zeros_like(normal)
    unit[valid] = normal[valid] / norm_len[valid, None]
    dist = np.stack(
        [
            np.einsum("ij,ij->i", unit, vertices[s_idx[:, k]] - v0)
            for k in range(3)
        ],
        axis=1,
    )
    on_plane = np.abs(dist) <= plane_tol
    beyond = np.abs(dist) > plane_tol
    mask = valid & (np.sum(on_plane, axis=1) == 2) & (np.sum(beyond, axis=1) == 1)
    return mask, unit


def _accept_on_plane_rows(hits, rows, vertices, clusters, edge_map, plane_tol, tol, t_idx, s_idx, s_fan, plane_poly, other_poly, unit):
    for row in rows.tolist():
        tri_s = s_idx[row]
        signed = np.array(
            [float(np.dot(unit[row], vertices[int(tri_s[k])] - vertices[int(t_idx[row, 0])])) for k in range(3)]
        )
        on_plane = np.abs(signed) <= plane_tol
        apex_local = int(np.flatnonzero(~on_plane)[0])
        edge_local = [k for k in range(3) if k != apex_local]
        va, vb = int(tri_s[edge_local[0]]), int(tri_s[edge_local[1]])
        ca, cb = int(clusters[va]), int(clusters[vb])
        if ca == cb:
            continue
        key = (ca, cb) if ca < cb else (cb, ca)
        tri_t = [int(t_idx[row, k]) for k in range(3)]
        if key in _triangle_cluster_edges(tri_t, clusters):
            continue
        length = _segment_inside_triangle_length(vertices[va], vertices[vb], vertices[tri_t])
        if not length > tol:
            continue
        plane_p = int(plane_poly[row])
        fan_s = int(s_fan[row])
        origin = vertices[tri_t[0]]
        positive, negative = _apex_sides(
            edge_map.get(key, ()), plane_p, fan_s, unit[row], origin, vertices, plane_tol
        )
        if signed[apex_local] > plane_tol:
            counted = [int(other_poly[row])] if negative else []
        else:
            counted = positive
        for other in counted:
            if other == plane_p:
                continue
            hits.add((plane_p, other) if plane_p < other else (other, plane_p))


def _triangle_cluster_edges(tri, clusters) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    cs = [int(clusters[v]) for v in tri]
    for i in range(3):
        a, b = cs[i], cs[(i + 1) % 3]
        if a != b:
            keys.add((a, b) if a < b else (b, a))
    return keys


def _apex_sides(entries, plane_poly: int, fan_s: int, unit, origin, vertices, plane_tol: float):
    """Polygons of other fan triangles on this edge whose apex is beyond tol, by sign."""
    positive: list[int] = []
    negative = False
    for poly_i, fan_i, apex in entries:
        if fan_i == fan_s or poly_i == plane_poly:
            continue
        dist = float(np.dot(unit, vertices[apex] - origin))
        if dist > plane_tol:
            positive.append(int(poly_i))
        elif dist < -plane_tol:
            negative = True
    return positive, negative


def _segment_inside_triangle_length(a, b, tri) -> float:
    """Length of the plane-projected segment that lies in the closed triangle."""
    v0, v1, v2 = tri[0], tri[1], tri[2]
    normal = np.cross(v1 - v0, v2 - v0)
    nn2 = float(np.dot(normal, normal))
    if nn2 <= 1e-30:
        return 0.0
    unit = normal / np.sqrt(nn2)
    a_p = a - unit * float(np.dot(unit, a - v0))
    b_p = b - unit * float(np.dot(unit, b - v0))
    edge_u = v1 - v0
    edge_v = v2 - v0

    def bary(point):
        rel = point - v0
        b1 = float(np.dot(np.cross(rel, edge_v), normal) / nn2)
        b2 = float(np.dot(np.cross(edge_u, rel), normal) / nn2)
        return (1.0 - b1 - b2, b1, b2)

    start = bary(a_p)
    end = bary(b_p)
    t0, t1 = 0.0, 1.0
    for c0, c1 in zip(start, end):
        delta = c1 - c0
        if abs(delta) <= 1e-18:
            if c0 < -_PLANE_EPS:
                return 0.0
            continue
        bound = (-_PLANE_EPS - c0) / delta
        if delta > 0.0:
            t0 = max(t0, bound)
        else:
            t1 = min(t1, bound)
    if t1 <= t0:
        return 0.0
    return float((t1 - t0) * np.linalg.norm(b_p - a_p))


def _edges_pierce(vertices, src, dst, tol, simplex_n=None, simplex_pts=None) -> np.ndarray:
    """True where any edge of src crosses the plane of dst inside that triangle.

    When a row carries a shared simplex (1 vertex or 2), the hit counts only if
    the pierce point is farther than ``tol`` from that simplex.
    """
    out = np.zeros(len(src), dtype=bool)
    if len(src) == 0:
        return out
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        inside, point = _segment_pierce_detail(vertices[src[:, e0]], vertices[src[:, e1]], vertices[dst], tol)
        if simplex_n is not None:
            inside &= _farther_than_simplex(point, simplex_n, simplex_pts, tol)
        out |= inside
    return out


def _farther_than_simplex(points, simplex_n, simplex_pts, tol: float) -> np.ndarray:
    far = np.ones(len(points), dtype=bool)
    one = simplex_n == 1
    two = simplex_n == 2
    if np.any(one):
        far[one] = np.linalg.norm(points[one] - simplex_pts[one, 0], axis=1) > tol
    if np.any(two):
        far[two] = _distance_to_segment(points[two], simplex_pts[two, 0], simplex_pts[two, 1]) > tol
    return far


def _distance_to_segment(points, start, end) -> np.ndarray:
    span = end - start
    length2 = np.einsum("ij,ij->i", span, span)
    scale = np.einsum("ij,ij->i", points - start, span)
    scale = np.divide(scale, length2, out=np.zeros_like(scale), where=length2 > 1e-30)
    scale = np.clip(scale, 0.0, 1.0)
    proj = start + scale[:, None] * span
    return np.linalg.norm(points - proj, axis=1)


def _segment_pierces(origin: np.ndarray, end: np.ndarray, triangles: np.ndarray, tol: float) -> np.ndarray:
    inside, _point = _segment_pierce_detail(origin, end, triangles, tol)
    return inside


def _segment_pierce_detail(origin: np.ndarray, end: np.ndarray, triangles: np.ndarray, tol: float):
    v0 = triangles[:, 0]
    v1 = triangles[:, 1]
    v2 = triangles[:, 2]
    normal = np.cross(v1 - v0, v2 - v0)
    norm_len = np.linalg.norm(normal, axis=1)
    valid = norm_len > 1e-15
    unit = np.zeros_like(normal)
    unit[valid] = normal[valid] / norm_len[valid, None]
    d_origin = np.einsum("ij,ij->i", unit, origin - v0)
    d_end = np.einsum("ij,ij->i", unit, end - v0)
    denom = d_origin - d_end
    plane_tol = _plane_tol(tol)
    crosses = valid & (np.abs(d_origin) > plane_tol) & (np.abs(d_end) > plane_tol) & (d_origin * d_end < 0)
    crosses &= np.abs(denom) > 0
    t = np.zeros(len(origin), dtype=np.float64)
    t[crosses] = d_origin[crosses] / denom[crosses]
    point = origin + t[:, None] * (end - origin)
    edge_u = v1 - v0
    edge_v = v2 - v0
    rel = point - v0
    nn2 = np.einsum("ij,ij->i", normal, normal)
    safe = nn2 > 1e-30
    b1 = np.einsum("ij,ij->i", np.cross(rel, edge_v), normal)
    b2 = np.einsum("ij,ij->i", np.cross(edge_u, rel), normal)
    b1 = np.divide(b1, nn2, out=np.zeros_like(b1), where=safe)
    b2 = np.divide(b2, nn2, out=np.zeros_like(b2), where=safe)
    b0 = 1.0 - b1 - b2
    # Closed by 1e-9 so a proper transversal along a triangulation diagonal counts.
    # The open test (all coordinates > 1e-9) still rejects points outside the triangle.
    inside = (b0 > -_PLANE_EPS) & (b1 > -_PLANE_EPS) & (b2 > -_PLANE_EPS) & safe & crosses
    return inside, point
