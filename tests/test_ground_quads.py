"""Synthetic regression cases for the v015 conforming quad mesher."""
import numpy as np
import pytest

from dt_ai.geometry.ground_cake import Mesh


def mesh(verts, faces):
    v = np.asarray(verts, float)
    f = np.asarray(faces, int)
    return Mesh(v, f, ['TileLight'] * len(f), np.zeros(len(f), int), v[f, :2], 4.)


def test_grid_square_stays_one_quad_without_steiner_cuts():
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0)], [(0, 1, 2), (0, 2, 3)])
    result = remesh(src)
    assert len(result.faces) == 1
    assert set(result.faces[0]) == {0, 1, 2, 3}
    assert result.source_faces == ((0, 1),)


def test_residual_triangle_uses_two_quad_transition_not_global_subdivision():
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, 0), (4, 4, 0), (0, 4, 0), (8, 2, 0)],
               [(0, 1, 2), (0, 2, 3), (1, 4, 2)])
    src.slot[2] = 'LawnRolled'
    result = remesh(src)
    assert len(result.faces) == 5  # triangle's 3 + square's 2
    assert all(len(f) == 4 for f in result.faces)
    from collections import Counter
    edges = Counter(tuple(sorted((a, f[(i + 1) % 4])))
                    for f in result.faces for i, a in enumerate(f))
    middle = np.flatnonzero(np.all(result.verts == (4, 2, 0), axis=1)).item()
    assert edges[tuple(sorted((1, middle)))] == 2
    assert edges[tuple(sorted((2, middle)))] == 2


def test_serialized_planar_patch_retains_quad_with_micrometre_rounding():
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, .112344), (4, 4, .234568), (0, 4, .122223)],
               [(0, 1, 2), (0, 2, 3)])
    src.uv[1, 2] += 0.0000004
    assert len(remesh(src).faces) == 1


@pytest.mark.parametrize('kind', ['empty', 'nan', 'inf', 'zero_area', 'duplicate', 'slot', 'uv', 'cell'])
def test_invalid_seed_fails_closed(kind):
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, 0), (0, 4, 0)], [(0, 1, 2)])
    if kind == 'empty':
        src.faces = np.empty((0, 3), int)
        src.slot, src.level, src.uv = [], np.zeros(0, int), np.empty((0, 3, 2))
    elif kind in ('nan', 'inf'):
        src.verts[0, 0] = float(kind)
    elif kind == 'zero_area':
        src.verts[2] = (2, 0, 0)
    elif kind == 'duplicate':
        src.faces = np.array([(0, 1, 2), (2, 0, 1)])
        src.slot *= 2
        src.level = np.zeros(2, int)
        src.uv = src.verts[src.faces, :2]
    elif kind == 'slot':
        src.slot = ['']
    elif kind == 'uv':
        src.uv[0, 0, 0] = np.nan
    else:
        src.cell = np.inf
    with pytest.raises(ValueError):
        remesh(src)


def test_nonmanifold_shared_edge_is_rejected_before_remeshing():
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, 0), (2, 4, 0), (2, -4, 0), (2, 8, 0)],
               [(0, 1, 2), (1, 0, 3), (0, 1, 4)])
    with pytest.raises(ValueError, match='nonmanifold.*0.*1'):
        remesh(src)


@pytest.mark.parametrize('seed', range(30))
def test_generated_planar_patches_preserve_coverage_uv_and_source_inventory(seed):
    from dt_ai.geometry.ground_quads import remesh
    from dt_ai.ops.inv_quads import PolyMesh, part_report
    from shapely.geometry import MultiPoint, Polygon
    from shapely.ops import unary_union
    from dt_ai.geometry.ground_cake import _tri_piece
    rng = np.random.default_rng(seed)
    poly = MultiPoint(rng.uniform(-4, 4, (12, 2))).convex_hull
    verts, faces, index = [], [], {}
    for triangle in _tri_piece(poly):
        f = []
        for xy in triangle:
            if xy not in index:
                index[xy] = len(verts)
                verts.append((*xy, 0))
            f.append(index[xy])
        faces.append(f)
    src = mesh(verts, faces)
    saved = src.verts.copy(), src.faces.copy(), src.uv.copy()
    q = remesh(src)
    polys = [Polygon(q.verts[list(f), :2]) for f in q.faces]
    assert all(p.is_valid and p.area > 0 for p in polys)
    assert unary_union(polys).symmetric_difference(poly).area < 1e-11
    assert abs(sum(p.area for p in polys) - poly.area) < 1e-11
    assert {p for parents in q.source_faces for p in parents} == set(range(len(src.faces)))
    assert all(len(f) == 4 for f in q.faces)
    assert part_report('ground', PolyMesh(q.verts, q.faces), 'VPM-GROUND').passed
    for f, uv in zip(q.faces, q.uv):
        np.testing.assert_allclose(q.verts[list(f), :2], uv, atol=1e-12)
    for actual, before in zip((src.verts, src.faces, src.uv), saved):
        np.testing.assert_array_equal(actual, before)


def test_triangle_becomes_three_conforming_quads_without_moving_surface():
    from dt_ai.geometry.ground_quads import remesh
    src = mesh([(0, 0, 0), (4, 0, 0), (0, 4, 0)], [(0, 1, 2)])
    result = remesh(src)
    assert len(result.faces) == 3
    assert all(len(f) == 4 for f in result.faces)
    assert result.source_faces == ((0,),) * 3
    assert result.slot == ['TileLight'] * 3
    np.testing.assert_array_equal(result.verts[:3], src.verts)
    for f, uv in zip(result.faces, result.uv):
        np.testing.assert_allclose(result.verts[list(f), :2], uv)
    from dt_ai.ops.inv_quads import PolyMesh, part_report
    assert part_report('surface', PolyMesh(result.verts, result.faces), 'VPM-GROUND').passed
