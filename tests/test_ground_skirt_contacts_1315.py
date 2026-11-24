"""#1315 Ground core: snap-rounding rim steps gave two xView skirt contacts on SIL13.

Pattern: n/a | new-case: tests/test_ground_skirt_contacts_1315.py - partition rim steps vs skirt contacts.
The local geometry below is SIL13-DERIVED (a 0.2 m window of the shared-core surface outline and the TIN lines the
relief refinement clips there, local coordinates); it is test input, not a model of the object. The real-source
check is ``tests/test_ground_relief_short_edges_1315.py::test_sil13_core_ground_has_no_short_edges`` (job marker).
"""
import math

import numpy as np
from shapely.geometry import MultiLineString, Polygon

from dt_ai.geometry import ground_cake as gc
from dt_ai.ops.inv_xview import mesh_report

SNAP = 0.003
# SIL13 window around witness pair FBX (22203, 23790): diagonal site outline, a TIN mark on it at (-69.777, 27.222)
SURFACE = Polygon([(-69.877, 27.29735), (-69.877, 27.322), (-69.677, 27.322), (-69.677, 27.14898)])
TIN = MultiLineString([[(-69.677, 27.148), (-69.777, 27.222)], [(-69.777, 27.222), (-69.677, 27.18659)],
                       [(-69.777, 27.222), (-69.72232, 27.322)], [(-69.777, 27.222), (-69.75844, 27.322)],
                       [(-69.777, 27.222), (-69.83209, 27.322)], [(-69.777, 27.222), (-69.87129, 27.322)],
                       [(-69.777, 27.222), (-69.877, 27.29619)]])


def _rim_steps(faces, snap=SNAP):
    """Rim vertices owned by one face whose two rim edges are both <= 2 snap (the one-pixel stair)."""
    use, owners = {}, {}
    rings = [list(f.exterior.coords)[:-1] for f in faces]
    for i, r in enumerate(rings):
        for a, b in zip(r, r[1:] + r[:1]):
            use[frozenset((a, b))] = use.get(frozenset((a, b)), 0) + 1
            owners.setdefault(a, set()).add(i)
    out = []
    for r in rings:
        for k, v in enumerate(r):
            a, b = r[k - 1], r[(k + 1) % len(r)]
            if len(owners[v]) == 1 and use[frozenset((a, v))] == 1 and use[frozenset((v, b))] == 1 \
                    and math.dist(a, v) <= 2 * snap and math.dist(v, b) <= 2 * snap:
                out.append(v)
    return out


def _mesh(faces):
    verts, idx, tris = [], {}, []
    for f in faces:
        for t in gc._tri_piece(f):
            tri = []
            for p in t:
                key = (round(p[0], 9), round(p[1], 9))
                if key not in idx:
                    idx[key] = len(verts)
                    verts.append((p[0], p[1], 0.0))
                tri.append(idx[key])
            tris.append(tri)
    n = len(tris)
    return gc.Mesh(np.array(verts, float), np.array(tris, int), ["Base"] * n, np.zeros(n, int),
                   np.zeros((n, 3, 2)), 3.0, {})


def test_partition_rim_has_no_snap_step(monkeypatch):
    faces = gc._partition([SURFACE.boundary, TIN], SURFACE, SNAP)
    assert _rim_steps(faces) == []
    monkeypatch.setattr(gc, "_cut_rim_steps", lambda f, snap: f)
    raw = gc._partition([SURFACE.boundary, TIN], SURFACE, SNAP)
    assert len(_rim_steps(raw)) == 1  # the SIL13 stair at the TIN mark (-69.777, 27.222)
    assert 0 < sum(f.area for f in raw) - sum(f.area for f in faces) <= 2 * SNAP * SNAP


def test_skirt_over_sil13_window_has_no_xview_contact():
    m = gc.add_skirt(_mesh(gc._partition([SURFACE.boundary, TIN], SURFACE, SNAP)), 1.0)
    r = mesh_report(m.verts, m.faces, profile="NPM-GROUND", part="window")
    assert (r["vertex_pairs"], r["face_pairs"]) == (0, 0)


TOOTH = Polygon([(0, 0), (1, 0), (1, 1), (0.003, 1), (0.003, 1.003), (0, 1.003)])  # convex 3 mm stair at (0.003, 1.003)


def test_convex_one_pixel_step_is_cut():
    cut = gc._cut_rim_steps([TOOTH], SNAP)[0]
    assert (0.003, 1.003) not in list(cut.exterior.coords) and len(cut.exterior.coords) == 6
    assert 0 < TOOTH.area - cut.area <= 2 * SNAP * SNAP and cut.is_valid


def test_step_shared_with_a_neighbour_or_reflex_is_kept():
    # the stair vertex also belongs to a neighbour face: cutting it would open a T-junction
    neighbour = Polygon([(0.003, 1.003), (0.5, 1.5), (0, 1.5)])
    out = gc._cut_rim_steps([TOOTH, neighbour], SNAP)
    assert out[0] is TOOTH and out[1] is neighbour
    # a reflex 3 mm step (cutting would add area outside the face) stays
    reflex = Polygon([(0, 0), (1, 0), (1, 0.997), (0.997, 0.997), (0.997, 1), (0, 1)])
    assert gc._cut_rim_steps([reflex], SNAP)[0] is reflex


def test_clean_partition_is_returned_unchanged():
    faces = [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]), Polygon([(1, 0), (2, 0), (2, 1), (1, 1)])]
    out = gc._cut_rim_steps(faces, SNAP)
    assert all(a is b for a, b in zip(out, faces))
