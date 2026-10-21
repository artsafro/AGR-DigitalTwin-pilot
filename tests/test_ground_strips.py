"""Selective quad-strip refinement feasibility; not source/model acceptance."""
import numpy as np
import pytest
from dt_ai.geometry.ground_quads import QuadMesh
from dt_ai.ops.inv_texel import face_metrics


def rectangle():
    return QuadMesh(np.array([[0., 0., 0.], [8., 0., 0.], [8., .1, 0.], [0., .1, 0.]]),
                    ((0, 1, 2, 3),), ['CurbGarden'], np.array([-2]),
                    (np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]]),), ((0, 1),), 4.)


def test_taper_is_sized_at_every_cell_not_only_average_width():
    from dt_ai.geometry.ground_strips import local_strips
    source = rectangle()
    source.verts[2, 1] = .1
    source.verts[3, 1] = 1.
    out = local_strips(source, max_edge_m=3.9)
    assert all(face_metrics(out.verts[list(f)]).aspect <= 8 for f in out.faces)


@pytest.mark.parametrize('field', ['slot', 'uv', 'source_faces', 'cell'])
def test_partial_or_nonfinite_metadata_cannot_produce_cells(field):
    from dt_ai.geometry.ground_strips import local_strips
    source = rectangle()
    if field == 'slot':
        source.slot = [' ']
    elif field == 'uv':
        source.uv[0][0, 0] = np.nan
    elif field == 'source_faces':
        source.source_faces = ((),)
    else:
        source.cell = np.nan
    with pytest.raises(ValueError):
        local_strips(source, max_edge_m=3.9)


@pytest.mark.parametrize('edge', [0, -1, np.nan, np.inf, True])
def test_invalid_sizing_never_passes(edge):
    from dt_ai.geometry.ground_strips import local_strips
    with pytest.raises(ValueError):
        local_strips(rectangle(), max_edge_m=edge)


def test_budget_exhaustion_is_error_not_partial_success():
    from dt_ai.geometry.ground_strips import local_strips
    with pytest.raises(ValueError, match='budget'):
        local_strips(rectangle(), max_edge_m=3.9, face_budget=2)


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
