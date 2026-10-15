"""Closed-component signed-volume diagnostic helper (Card #93 / Task #111).

Scoped as a new-case, bounded optional report-only diagnostic. It identifies
edge-connected components within individual meshes, checks closed-manifold
eligibility, and computes high-precision signed volumes using compensated summation.
No registered building-node pattern is defined or modified by this helper.
For detailed semantics and evidence boundary, see docs/qa/component-volume.md.
"""

from __future__ import annotations

from collections import defaultdict, deque
import math
from typing import Any

import numpy as np


def _normalize_array(
    raw: Any, name: str, field: str, allowed_kinds: tuple[str, ...], n_verts: int | None = None
) -> np.ndarray:
    """Normalize and validate coordinate or index arrays without silent casts."""
    if isinstance(raw, np.ndarray):
        if raw.ndim != 2 or raw.shape[1] != 3:
            raise ValueError(f"Mesh '{name}' {field} must have shape (*, 3), got {raw.shape}.")
        if raw.dtype.kind not in allowed_kinds:
            raise ValueError(f"Mesh '{name}' {field} must have numeric kind in {allowed_kinds}, got {raw.dtype}.")
        if field == "vertices":
            if not np.all(np.isfinite(raw)):
                raise ValueError(f"Mesh '{name}' vertices contain non-finite values.")
            return raw.astype(np.float64, copy=False)
        if raw.size > 0:
            if np.any(raw < 0):
                raise ValueError(f"Mesh '{name}' triangle indices must be non-negative.")
            if n_verts is not None and np.any(raw >= n_verts):
                raise ValueError(f"Mesh '{name}' triangle indices out of bounds (n_verts={n_verts}).")
        return raw.astype(np.int64, copy=False)

    if isinstance(raw, (list, tuple)):
        if len(raw) == 0:
            return np.empty((0, 3), dtype=np.float64 if field == "vertices" else np.int64)
        is_v = field == "vertices"
        rows = []
        for i, row in enumerate(raw):
            if not isinstance(row, (list, tuple, np.ndarray)) or len(row) != 3:
                raise ValueError(f"Mesh '{name}' {field} row {i} must have 3 elements.")
            entry = []
            for val in row:
                if isinstance(val, bool) or not isinstance(
                    val, (int, float, np.integer, np.floating) if is_v else (int, np.integer)
                ):
                    type_str = "real numeric" if is_v else "integer"
                    raise ValueError(f"Mesh '{name}' {field} index/coord must be {type_str}, got {type(val).__name__}.")
                if is_v:
                    fval = float(val)
                    if not math.isfinite(fval):
                        raise ValueError(f"Mesh '{name}' vertex {i} contains non-finite coordinate: {val}")
                    entry.append(fval)
                else:
                    ival = int(val)
                    if ival < 0:
                        raise ValueError(f"Mesh '{name}' triangle {i} index is negative ({ival}).")
                    if n_verts is not None and ival >= n_verts:
                        raise ValueError(f"Mesh '{name}' triangle {i} index out of bounds ({ival} >= {n_verts}).")
                    entry.append(ival)
            rows.append(entry)
        return np.asarray(rows, dtype=np.float64 if is_v else np.int64)

    raise ValueError(f"Mesh '{name}' {field} must be a list or ndarray, got {type(raw).__name__}.")


def _validate_mesh(mesh: Any, idx: int) -> tuple[str, np.ndarray, np.ndarray]:
    """Validate mesh structure and return normalized coordinate and index arrays."""
    if not isinstance(mesh, dict):
        raise ValueError(f"Mesh at index {idx} must be a dictionary, got {type(mesh).__name__}.")
    for key in ("name", "vertices", "triangles"):
        if key not in mesh:
            raise ValueError(f"Mesh at index {idx} must contain key '{key}'.")
    name = mesh["name"]
    if not isinstance(name, str):
        raise ValueError(f"Mesh at index {idx} 'name' must be a string, got {type(name).__name__}.")
    vertices = _normalize_array(mesh["vertices"], name, "vertices", ("i", "u", "f"))
    triangles = _normalize_array(mesh["triangles"], name, "triangles", ("i", "u"), n_verts=len(vertices))
    return name, vertices, triangles


def _partition_components(triangles: np.ndarray) -> list[list[int]]:
    """Partition triangles into components by shared undirected index edges."""
    edge_to_triangles: dict[tuple[int, int], list[int]] = defaultdict(list)
    for t_idx, (u, v, w) in enumerate(triangles):
        edges = {(min(u, v), max(u, v)) for u, v in ((u, v), (v, w), (w, u)) if u != v}
        for edge in edges:
            edge_to_triangles[edge].append(t_idx)

    tri_adj: dict[int, list[int]] = defaultdict(list)
    for tri_list in edge_to_triangles.values():
        if len(tri_list) > 1:
            first_t = tri_list[0]
            for other_t in tri_list[1:]:
                tri_adj[first_t].append(other_t)
                tri_adj[other_t].append(first_t)

    visited = [False] * len(triangles)
    components: list[list[int]] = []
    for t_start in range(len(triangles)):
        if visited[t_start]:
            continue
        comp: list[int] = []
        queue = deque([t_start])
        visited[t_start] = True
        while queue:
            curr = queue.popleft()
            comp.append(curr)
            for neighbor in tri_adj[curr]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    queue.append(neighbor)
        comp.sort()
        components.append(comp)

    components.sort(key=lambda c: c[0])
    return components


def _check_single_vertex_fans(
    triangles: np.ndarray, comp_tri_ids: list[int], unique_verts: list[int]
) -> bool:
    """Verify that every unique vertex in the component forms a single incident face fan.

    Complexity: O(F + V + total incident entries) time for fan work and O(F) extra storage.
    """
    vert_to_tris: dict[int, list[int]] = defaultdict(list)
    for t in comp_tri_ids:
        seen_verts: set[int] = set()
        for v in triangles[t]:
            v_int = int(v)
            if v_int not in seen_verts:
                seen_verts.add(v_int)
                vert_to_tris[v_int].append(t)

    for v_idx in unique_verts:
        incident_tris = vert_to_tris.get(int(v_idx), [])
        if len(incident_tris) <= 1:
            continue

        adj: dict[int, list[int]] = defaultdict(list)
        edge_neighbor_to_tris: dict[int, list[int]] = defaultdict(list)
        for t in incident_tris:
            for other in {x for x in triangles[t] if x != v_idx}:
                edge_neighbor_to_tris[other].append(t)

        for tris in edge_neighbor_to_tris.values():
            if len(tris) > 1:
                first = tris[0]
                for other in tris[1:]:
                    adj[first].append(other)
                    adj[other].append(first)

        visited: set[int] = set()
        fan_count = 0
        for t in incident_tris:
            if t not in visited:
                fan_count += 1
                if fan_count > 1:
                    return False
                q = deque([t])
                visited.add(t)
                while q:
                    curr = q.popleft()
                    for nbr in adj[curr]:
                        if nbr not in visited:
                            visited.add(nbr)
                            q.append(nbr)
    return True


def _check_eligibility(
    vertices: np.ndarray, triangles: np.ndarray, comp_tri_ids: list[int]
) -> tuple[bool, list[str], list[int]]:
    """Check closed-manifold criteria: degeneracy, edges, winding, and vertex fans."""
    reasons: list[str] = []
    comp_tris = triangles[comp_tri_ids]
    unique_verts = sorted(int(v) for v in np.unique(comp_tris))

    v_comp = vertices[unique_verts]
    bbox_diag_sq = float(np.sum((v_comp.max(axis=0) - v_comp.min(axis=0)) ** 2))
    area_threshold = 1e-12 * bbox_diag_sq

    u, v, w = comp_tris[:, 0], comp_tris[:, 1], comp_tris[:, 2]
    if np.any((u == v) | (v == w) | (w == u)):
        reasons.append("degenerate_triangle")
    else:
        cross = np.cross(vertices[v] - vertices[u], vertices[w] - vertices[u])
        if np.any(0.5 * np.linalg.norm(cross, axis=1) <= area_threshold):
            reasons.append("degenerate_triangle")

    comp_edge_uses: dict[tuple[int, int], list[tuple[int, tuple[int, int]]]] = defaultdict(list)
    for t_idx, (tu, tv, tw) in zip(comp_tri_ids, comp_tris):
        for d_edge in ((tu, tv), (tv, tw), (tw, tu)):
            du, dv = int(d_edge[0]), int(d_edge[1])
            undirected = (min(du, dv), max(du, dv)) if du != dv else (du, dv)
            comp_edge_uses[undirected].append((t_idx, (du, dv)))

    has_edge_violation = False
    has_winding_violation = False
    for uses in comp_edge_uses.values():
        if len(uses) != 2 or len({t_id for t_id, _ in uses}) != 2:
            has_edge_violation = True
        elif uses[0][1] == uses[1][1]:
            has_winding_violation = True

    if has_edge_violation:
        reasons.append("open_or_nonmanifold_edge")
    if has_winding_violation:
        reasons.append("inconsistent_winding")
    if not _check_single_vertex_fans(triangles, comp_tri_ids, unique_verts):
        reasons.append("vertex_not_single_fan")

    return (len(reasons) == 0), reasons, unique_verts


def _compute_component_volume(
    vertices: np.ndarray, triangles: np.ndarray, comp_tri_ids: list[int], unique_verts: list[int]
) -> tuple[float, int | None]:
    """Compute centroid-shifted signed volume using math.fsum compensated summation."""
    r = np.array([math.fsum(vertices[unique_verts, j]) for j in range(3)], dtype=np.float64) / len(unique_verts)
    comp_tris = triangles[comp_tri_ids]
    a = vertices[comp_tris[:, 0]] - r
    b = vertices[comp_tris[:, 1]] - r
    c = vertices[comp_tris[:, 2]] - r
    dots = np.sum(a * np.cross(b, c), axis=1)

    signed_volume = math.fsum(dots.tolist()) / 6.0
    sign = 1 if signed_volume > 0.0 else (-1 if signed_volume < 0.0 else None)
    return signed_volume, sign


def component_signed_volumes(meshes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute signed volumes of edge-connected closed-manifold components.

    Splits triangles by shared undirected index edges strictly per mesh.
    Never welds or merges meshes across boundaries or coordinate positions.

    Returns a list of dicts with schema:
    - mesh: str
    - n_triangles: int
    - triangle_ids: list[int] (sorted ascending local triangle IDs)
    - eligible: bool
    - reasons: list[str]
    - status: "measured" | "not_measured"
    - signed_volume: float | None
    - sign: 1 | -1 | None
    """
    if not isinstance(meshes, list):
        raise ValueError(f"Input 'meshes' must be a list of dicts, got {type(meshes).__name__}.")

    results: list[dict[str, Any]] = []

    for idx, mesh in enumerate(meshes):
        name, vertices, triangles = _validate_mesh(mesh, idx)
        if len(triangles) == 0:
            continue

        for comp_tri_ids in _partition_components(triangles):
            eligible, reasons, unique_verts = _check_eligibility(vertices, triangles, comp_tri_ids)
            vol, sgn = _compute_component_volume(vertices, triangles, comp_tri_ids, unique_verts) if eligible else (None, None)
            results.append({
                "mesh": name,
                "n_triangles": len(comp_tri_ids),
                "triangle_ids": comp_tri_ids,
                "eligible": eligible,
                "reasons": reasons,
                "status": "measured" if eligible else "not_measured",
                "signed_volume": vol,
                "sign": sgn,
            })

    return results
