"""Geometric wall-to-edge binder for the synthetic one-upright-wall-per-edge subset."""

import numpy as np

UnresolvedBinding = None


def make_geometric_binder(pilot):
    """Return bind_walls_geometric with the same signature and dict shape as pilot.bind_walls."""
    global UnresolvedBinding

    class UnresolvedBinding(pilot.IntakeError):
        def __init__(self, evidence):
            super().__init__(evidence["reason"])
            self.evidence = evidence

    def bind_walls_geometric(walls, ring, storey_z, building_placement, scale):
        walls = sorted(list(walls), key=lambda wall: wall.GlobalId or "")
        pts, ccw = pilot.contour_xy([[float(p[0]), float(p[1])] for p in ring])
        frames = pilot.edge_frames(pts, ccw)
        inv_b = np.linalg.inv(pilot.matrix_si(building_placement, scale))
        by_wall = {wall.GlobalId: [] for wall in walls}
        by_edge = {i: [] for i in range(len(frames))}
        eligible = []
        for wall in walls:
            place = wall.ObjectPlacement
            if place is None:
                continue
            local = inv_b @ pilot.matrix_si(place, scale)
            origin = local[:3, 3]
            axis = local[:3, 0]
            norm = float(np.linalg.norm(axis))
            if norm <= 1e-9:
                continue
            axis = axis / norm
            for i, (origin_xy, xdir, _length, _side) in enumerate(frames):
                origin_err = max(
                    abs(float(origin[0]) - float(origin_xy[0])),
                    abs(float(origin[1]) - float(origin_xy[1])),
                    abs(float(origin[2]) - float(storey_z)),
                )
                axis_err = max(
                    abs(float(axis[0]) - float(xdir[0])),
                    abs(float(axis[1]) - float(xdir[1])),
                    abs(float(axis[2])),
                )
                if origin_err <= 1e-4 and axis_err <= 1e-4:
                    gid = wall.GlobalId
                    eligible.append([gid, i, float(origin_err), float(axis_err)])
                    by_wall[gid].append(i)
                    by_edge[i].append(gid)
        walls_without = sorted(gid for gid, edges in by_wall.items() if not edges)
        walls_multi = {gid: sorted(edges) for gid, edges in by_wall.items() if len(edges) > 1}
        edges_without = sorted(i for i, gids in by_edge.items() if not gids)
        edges_multi = {str(i): sorted(gids) for i, gids in by_edge.items() if len(gids) > 1}
        eligible.sort(key=lambda row: (row[0], row[1], row[2], row[3]))
        unique = (
            len(walls) == len(frames)
            and not walls_without
            and not walls_multi
            and not edges_without
            and not edges_multi
        )
        evidence = {
            "reason": "unique geometric binding" if unique else "unresolved geometric binding",
            "n_walls": len(walls),
            "n_edges": len(frames),
            "walls_without_edge": walls_without,
            "walls_with_multiple_edges": dict(sorted(walls_multi.items())),
            "edges_without_wall": edges_without,
            "edges_with_multiple_walls": dict(sorted(edges_multi.items(), key=lambda item: int(item[0]))),
            "eligible_pairs": eligible,
        }
        bind_walls_geometric.last_evidence = evidence
        if not unique:
            raise UnresolvedBinding(evidence)
        chosen = {}
        wall_by_gid = {wall.GlobalId: wall for wall in walls}
        for gid, edge, _origin_err, _axis_err in eligible:
            chosen[edge] = wall_by_gid[gid]
        return chosen

    bind_walls_geometric.last_evidence = None
    bind_walls_geometric.UnresolvedBinding = UnresolvedBinding
    return bind_walls_geometric
