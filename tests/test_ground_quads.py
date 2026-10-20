"""Synthetic regression cases for the v015 conforming quad mesher."""
import numpy as np

from dt_ai.geometry.ground_cake import Mesh


def mesh(verts, faces):
    v = np.asarray(verts, float)
    f = np.asarray(faces, int)
    return Mesh(v, f, ['TileLight'] * len(f), np.zeros(len(f), int), v[f, :2], 4.)


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
