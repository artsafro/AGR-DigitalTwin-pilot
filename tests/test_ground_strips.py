"""Selective quad-strip refinement feasibility; not source/model acceptance."""
import numpy as np
from dt_ai.geometry.ground_quads import QuadMesh
from dt_ai.ops.inv_texel import face_metrics


def rectangle():
    return QuadMesh(np.array([[0., 0., 0.], [8., 0., 0.], [8., .1, 0.], [0., .1, 0.]]),
                    ((0, 1, 2, 3),), ['CurbGarden'], np.array([-2]),
                    (np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]]),), ((0, 1),), 4.)


def test_long_strip_is_split_without_all_seed_triangle_steiner_expansion():
    from dt_ai.geometry.ground_strips import local_strips
    source = rectangle()
    out = local_strips(source, max_edge_m=3.9)
    assert len(out.faces) >= 10
    assert all(len(f) == 4 for f in out.faces)
    assert all(face_metrics(out.verts[list(f)]).aspect <= 8 for f in out.faces)
    assert sum(face_metrics(out.verts[list(f)]).area_m2 for f in out.faces) == .8
    assert all(s == 'CurbGarden' for s in out.slot)
    assert all(l == -2 for l in out.level)
    assert all(ids == (0, 1) for ids in out.source_faces)
    for f, uv in zip(out.faces, out.uv):
        assert np.allclose(uv, out.verts[list(f), :2]/[8., .1])
