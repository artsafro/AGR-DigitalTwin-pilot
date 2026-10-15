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
- self_intersections: number of distinct unordered polygon pairs (p, q), p != q,
  such that p and q share no cluster and some fan triangle of p and some fan
  triangle of q intersect properly. An edge of one triangle crosses the plane of
  the other at a point strictly inside the other triangle: signed distances of
  the segment endpoints to the plane have opposite signs and each |d| > tol
  (the regulatory 0.002 m distance tolerance, so penetrations within the
  tolerance are not counted); the crossing point is inside the triangle with
  barycentric coordinates all > 1e-9. Coplanar or touching-only pairs are not
  self-intersections. Polygons are triangulated with a fan from their first
  vertex. A transversal that lands on a triangle edge (barycentric coordinate 0,
  as when two axis-aligned cubes overlap by half a metre on every axis and meet
  along a face diagonal) is counted: the closed-triangle test uses epsilon
  1e-9. Coplanar face contact never produces opposite-sign distances above tol.
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
    src_rows: list[np.ndarray] = []
    dst_rows: list[np.ndarray] = []
    pair_ids: list[int] = []
    kept = 0
    for p, q in pairs:
        if poly_clusters[p] & poly_clusters[q]:
            continue
        fa, fb = fans[p], fans[q]
        if len(fa) == 0 or len(fb) == 0:
            continue
        for tri in fa:
            src_rows.append(np.repeat(tri.reshape(1, 3), len(fb), axis=0))
            dst_rows.append(fb)
            pair_ids.extend([kept] * len(fb))
        for tri in fb:
            src_rows.append(np.repeat(tri.reshape(1, 3), len(fa), axis=0))
            dst_rows.append(fa)
            pair_ids.extend([kept] * len(fa))
        kept += 1
    if kept == 0:
        return 0
    src = np.concatenate(src_rows, axis=0)
    dst = np.concatenate(dst_rows, axis=0)
    ids = np.asarray(pair_ids, dtype=np.int64)
    hit_pairs: set[int] = set()
    step = 8192
    for start in range(0, len(src), step):
        stop = start + step
        hits = _edges_pierce(vertices, src[start:stop], dst[start:stop], tol)
        if np.any(hits):
            hit_pairs.update(ids[start:stop][hits].tolist())
    return len(hit_pairs)


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


def _edges_pierce(vertices: np.ndarray, src: np.ndarray, dst: np.ndarray, tol: float) -> np.ndarray:
    """True where any edge of src crosses the plane of dst inside that triangle."""
    out = np.zeros(len(src), dtype=bool)
    if len(src) == 0:
        return out
    for e0, e1 in ((0, 1), (1, 2), (2, 0)):
        out |= _segment_pierces(vertices[src[:, e0]], vertices[src[:, e1]], vertices[dst], tol)
    return out


def _segment_pierces(origin: np.ndarray, end: np.ndarray, triangles: np.ndarray, tol: float) -> np.ndarray:
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
    plane_tol = tol if tol > 0 else _PLANE_EPS
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
    return inside
