"""Pure standard library corner matcher for facade mesh roundtrip validation.

Uses a spatial hash grid with bucket width equal to `2 * xyz_tol` to query candidate
reference corners within the 27 neighboring 3D buckets, followed by exact Euclidean
distance filtering (`math.dist(obs[:3], ref[:3]) <= xyz_tol`) and strict Chebyshev
UV error filtering (`max(abs(obs_u - ref_u), abs(obs_v - ref_v)) < uv_tol`).

A cell width of `2 * xyz_tol` guarantees that any two points with Euclidean distance
`<= xyz_tol` differ along each axis by at most `0.5 * cell_size`. The integer coordinate
difference `floor(x_obs/C) - floor(x_ref/C)` is therefore strictly in `{-1, 0, 1}`,
ensuring 27-bucket query completeness across negative bucket edges and large coordinates.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import math
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class CornerMatchResult:
    """Result of matching observed corners to reference corners."""

    perfect: bool
    cardinality: int
    assignment: list[int]
    max_uv_error: float
    max_position_error_m: float


def maximum_matching(
    adjacency: Sequence[Iterable[int]], reference_count: int
) -> list[int]:
    """Compute maximum cardinality bipartite matching using iterative augmenting paths (BFS)."""
    adj = [list(edges) for edges in adjacency]
    match_u, match_v = [-1] * len(adj), [-1] * reference_count

    for root_u in range(len(adj)):
        if match_u[root_u] != -1:
            continue
        parent_v: dict[int, int] = {}
        queue: deque[int] = deque([root_u])
        visited_u: set[int] = {root_u}
        sink_v = -1
        while queue and sink_v == -1:
            curr_u = queue.popleft()
            for v in adj[curr_u]:
                if v < 0 or v >= reference_count or v in parent_v:
                    continue
                parent_v[v] = curr_u
                if match_v[v] == -1:
                    sink_v = v
                    break
                paired = match_v[v]
                if paired not in visited_u:
                    visited_u.add(paired)
                    queue.append(paired)

        if sink_v != -1:
            curr_v = sink_v
            while curr_v != -1:
                u = parent_v[curr_v]
                next_v = match_u[u]
                match_u[u], match_v[curr_v] = curr_v, u
                curr_v = next_v

    return match_u


def _validate_corners(
    corners: Any, name: str
) -> list[tuple[float, float, float, float, float]]:
    if not hasattr(corners, "__iter__"):
        raise ValueError(f"{name} must be an iterable")
    try:
        row_list = list(corners)
    except TypeError as err:
        raise ValueError(f"{name} must be an iterable of corners") from err

    validated: list[tuple[float, float, float, float, float]] = []
    for idx, row in enumerate(row_list):
        try:
            if len(row) != 5:
                raise ValueError(f"Corner {idx} in {name} has length {len(row)}, expected 5")
            vals = (float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]))
        except (TypeError, ValueError, IndexError) as err:
            raise ValueError(f"Corner {idx} in {name} is malformed: {err}") from err
        if not all(math.isfinite(v) for v in vals):
            raise ValueError(f"Corner {idx} in {name} has non-finite values: {vals}")
        validated.append(vals)
    return validated


def match_corners(
    reference: Any,
    observed: Any,
    xyz_tol: float = 0.002,
    uv_tol: float = 2e-6,
) -> CornerMatchResult:
    """Match observed mesh corners to reference corners."""
    try:
        xyz_tol_f, uv_tol_f = float(xyz_tol), float(uv_tol)
    except (TypeError, ValueError) as err:
        raise ValueError(f"Tolerances must be numeric floats: {err}") from err

    if not (math.isfinite(xyz_tol_f) and xyz_tol_f > 0):
        raise ValueError(f"xyz_tol must be finite and positive, got {xyz_tol}")
    if not (math.isfinite(uv_tol_f) and uv_tol_f > 0):
        raise ValueError(f"uv_tol must be finite and positive, got {uv_tol}")

    ref_pts = _validate_corners(reference, "reference")
    obs_pts = _validate_corners(observed, "observed")
    if not ref_pts or not obs_pts:
        return CornerMatchResult(
            perfect=(len(ref_pts) == 0 and len(obs_pts) == 0),
            cardinality=0,
            assignment=[-1] * len(obs_pts),
            max_uv_error=0.0,
            max_position_error_m=0.0,
        )

    # Spatial hash grid with cell size 2 * xyz_tol ensures that points within xyz_tol
    # differ by at most 0.5 * cell_size, bounding bin index delta to {-1, 0, 1}.
    cell_size = 2.0 * xyz_tol_f
    grid: dict[tuple[int, int, int], list[int]] = defaultdict(list)
    for idx, r in enumerate(ref_pts):
        grid[(math.floor(r[0] / cell_size), math.floor(r[1] / cell_size), math.floor(r[2] / cell_size))].append(idx)

    adjacency: list[list[int]] = []
    for o in obs_pts:
        cx, cy, cz = math.floor(o[0] / cell_size), math.floor(o[1] / cell_size), math.floor(o[2] / cell_size)
        eligible: list[int] = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for r_idx in grid.get((cx + dx, cy + dy, cz + dz), ()):
                        r = ref_pts[r_idx]
                        if math.dist(o[:3], r[:3]) <= xyz_tol_f and max(abs(o[3] - r[3]), abs(o[4] - r[4])) < uv_tol_f:
                            eligible.append(r_idx)
        adjacency.append(eligible)

    assignment = maximum_matching(adjacency, len(ref_pts))
    cardinality = sum(1 for v in assignment if v != -1)

    max_pos_err, max_uv_err = 0.0, 0.0
    for u, v in enumerate(assignment):
        if v != -1:
            max_pos_err = max(max_pos_err, math.dist(obs_pts[u][:3], ref_pts[v][:3]))
            max_uv_err = max(max_uv_err, max(abs(obs_pts[u][3] - ref_pts[v][3]), abs(obs_pts[u][4] - ref_pts[v][4])))

    return CornerMatchResult(
        perfect=(len(ref_pts) == len(obs_pts) == cardinality),
        cardinality=cardinality,
        assignment=assignment,
        max_uv_error=max_uv_err,
        max_position_error_m=max_pos_err,
    )
