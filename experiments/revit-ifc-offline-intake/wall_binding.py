"""Geometric wall binding for synthetic IFC offline intake pilot (new-case).

Provenance: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/107, report: docs/experiments/hyp-107.md.
Status: experimental new-case; not a proven generic IFC pattern and no registry pattern is claimed.
Contracts:
- Scope: report-only, explicit geometric opt-in; strict mode is default (delivery_passed=false).
- Topology: synthetic one-wall-per-edge constraint on horizontal slab contours.
- Tolerances: ORIGIN_TOLERANCE_M = 1e-4 m, AXIS_TOLERANCE = 1e-4 (normalized X-axis residual).
- Determinism: walls sorted by GlobalId and entity id; Name and Tag are ignored.
- Fail-closed: returns complete edge_idx -> wall mapping or raises UnresolvedBinding.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

ORIGIN_TOLERANCE_M: float = 1e-4
AXIS_TOLERANCE: float = 1e-4


class UnresolvedBinding(ValueError):
    """Raised when geometric wall binding cannot find a unique 1-to-1 match."""

    def __init__(self, message: str, evidence: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.evidence: dict[str, Any] = evidence if evidence is not None else {}


def make_geometric_binder(pilot_helpers: Any) -> tuple[type[UnresolvedBinding], Any]:
    IntakeError = getattr(pilot_helpers, "IntakeError", ValueError)
    contour_xy = getattr(pilot_helpers, "contour_xy")
    edge_frames = getattr(pilot_helpers, "edge_frames")
    matrix_si = getattr(pilot_helpers, "matrix_si")

    class BoundUnresolvedBinding(UnresolvedBinding, IntakeError):
        """Concrete UnresolvedBinding subclass inheriting from pilot.IntakeError."""

    def bind_walls_geometric(
        walls: list[Any],
        ring: list[Any],
        storey_z: float,
        building_placement: Any,
        scale: float,
    ) -> dict[int, Any]:
        bind_walls_geometric.last_evidence = None

        seen_gids: set[str] = set()
        invalid_ids: set[str] = set()
        for w in walls:
            gid = getattr(w, "GlobalId", None)
            if not isinstance(gid, str) or not gid:
                invalid_ids.add(str(gid))
            elif gid in seen_gids:
                invalid_ids.add(gid)
            else:
                seen_gids.add(gid)
        has_invalid_gid = len(invalid_ids) > 0

        sorted_walls = sorted(
            walls,
            key=lambda w: (
                str(getattr(w, "GlobalId", "")),
                getattr(w, "id", lambda: 0)() if callable(getattr(w, "id", None)) else getattr(w, "id", 0),
            ),
        )

        pts, ccw = contour_xy([[float(p[0]), float(p[1])] for p in ring])
        frames = edge_frames(pts, ccw)
        n_edges, n_walls = len(frames), len(sorted_walls)

        is_finite_z = False
        try:
            is_finite_z = math.isfinite(float(storey_z))
        except (ValueError, TypeError):
            is_finite_z = False

        raw_inv_b = None
        if building_placement is not None:
            try:
                b_mat = matrix_si(building_placement, scale)
                inv = np.linalg.inv(b_mat)
                if np.all(np.isfinite(inv)):
                    raw_inv_b = inv
            except Exception:
                raw_inv_b = None

        eligible_pairs: list[list[Any]] = []
        wall_to_edges: dict[str, list[int]] = {str(getattr(w, "GlobalId", "")): [] for w in sorted_walls}
        edge_to_walls: dict[int, list[str]] = {i: [] for i in range(n_edges)}

        if raw_inv_b is not None and not has_invalid_gid and is_finite_z:
            for w in sorted_walls:
                w_gid = str(w.GlobalId)
                if getattr(w, "ObjectPlacement", None) is None:
                    continue
                try:
                    w_mat = matrix_si(w.ObjectPlacement, scale)
                    local = raw_inv_b @ w_mat
                    if not np.all(np.isfinite(local)):
                        continue
                except Exception:
                    continue

                origin = local[:3, 3]
                axis = local[:3, 0]
                norm = float(np.linalg.norm(axis))
                if norm <= 1e-9 or not math.isfinite(norm):
                    continue
                norm_axis = axis / norm
                if not np.all(np.isfinite(origin)) or not np.all(np.isfinite(norm_axis)):
                    continue

                for i, (origin_xy, xdir, _length, _side) in enumerate(frames):
                    origin_error = max(
                        abs(float(origin[0]) - origin_xy[0]),
                        abs(float(origin[1]) - origin_xy[1]),
                        abs(float(origin[2]) - float(storey_z)),
                    )
                    axis_error = max(
                        abs(float(norm_axis[0]) - xdir[0]),
                        abs(float(norm_axis[1]) - xdir[1]),
                        abs(float(norm_axis[2]) - 0.0),
                    )
                    if origin_error <= ORIGIN_TOLERANCE_M and axis_error <= AXIS_TOLERANCE:
                        eligible_pairs.append([w_gid, i, float(origin_error), float(axis_error)])
                        wall_to_edges[w_gid].append(i)
                        edge_to_walls[i].append(w_gid)

        eligible_pairs.sort(key=lambda p: (str(p[0]), int(p[1])))
        walls_without_edge = sorted([gid for gid, edges in wall_to_edges.items() if len(edges) == 0])
        walls_with_multiple_edges = {gid: sorted(edges) for gid, edges in wall_to_edges.items() if len(edges) > 1}
        edges_without_wall = sorted([i for i, wids in edge_to_walls.items() if len(wids) == 0])
        edges_with_multiple_walls = {str(i): sorted(wids) for i, wids in edge_to_walls.items() if len(wids) > 1}

        if has_invalid_gid:
            reason = "invalid_or_duplicate_wall_global_id"
        elif n_walls != n_edges:
            reason = "cardinality_mismatch"
        elif walls_without_edge or walls_with_multiple_edges or edges_without_wall or edges_with_multiple_walls:
            reason = "unresolved_mapping"
        else:
            reason = "exact_match"

        evidence: dict[str, Any] = {
            "reason": reason,
            "n_walls": n_walls,
            "n_edges": n_edges,
            "walls_without_edge": walls_without_edge,
            "walls_with_multiple_edges": walls_with_multiple_edges,
            "edges_without_wall": edges_without_wall,
            "edges_with_multiple_walls": edges_with_multiple_walls,
            "eligible_pairs": eligible_pairs,
            "invalid_ids": sorted(invalid_ids),
        }

        bind_walls_geometric.last_evidence = evidence

        if reason == "exact_match":
            wall_by_gid = {w.GlobalId: w for w in sorted_walls}
            return {edges[0]: wall_by_gid[gid] for gid, edges in wall_to_edges.items()}

        raise BoundUnresolvedBinding(f"geometric binding unresolved: {reason}", evidence)

    bind_walls_geometric.last_evidence = None
    bind_walls_geometric.UnresolvedBinding = BoundUnresolvedBinding
    return BoundUnresolvedBinding, bind_walls_geometric
