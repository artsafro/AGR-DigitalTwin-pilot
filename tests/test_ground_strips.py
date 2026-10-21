"""Selective quad-strip refinement feasibility; not source/model acceptance."""
import numpy as np
import pytest
from dt_ai.geometry.ground_quads import QuadMesh
from dt_ai.ops.inv_texel import face_metrics


def rectangle():
    return QuadMesh(np.array([[0., 0., 0.], [8., 0., 0.], [8., .1, 0.], [0., .1, 0.]]),
                    ((0, 1, 2, 3),), ['CurbGarden'], np.array([-2]),
                    (np.array([[0., 0.], [1., 0.], [1., 1.], [0., 1.]]),), ((0, 1),), 4.)


def test_real_narrow_end_requires_nonuniform_longitudinal_cuts():
    import json
    from pathlib import Path
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from dt_ai.geometry.ground_strips import local_strips
    from dt_ai.ops.inv_xview import vertex_pairs
    d = json.loads((Path(__file__).parent/'data/ground-v015-strict-taper.json').read_text())
    seed = QuadMesh(np.array(d['verts']), tuple(map(tuple, d['faces'])), d['slot'], np.array(d['level']),
                    tuple(map(np.array, d['uv'])), tuple(map(tuple, d['source_faces'])), d['cell'])
    result = local_strips(seed, max_edge_m=3.9)
    assert all(face_metrics(result.verts[list(f)]).aspect <= 8 for f in result.faces)
    expected = Polygon(seed.verts[:, :2])
    actual = unary_union([Polygon(result.verts[list(f), :2]) for f in result.faces])
    assert expected.symmetric_difference(actual).area < 1e-9
    assert len(vertex_pairs(result.verts, .002)[0]) == 0


def test_short_adjacent_edges_do_not_explode_a_vpm_tensor_grid():
    import json
    from pathlib import Path
    from dt_ai.geometry.ground_strips import local_strips
    from dt_ai.ops.inv_xview import vertex_pairs
    d = json.loads((Path(__file__).parent/'data/ground-v015-strict-corner.json').read_text())
    seed = QuadMesh(np.array(d['verts']), tuple(map(tuple, d['faces'])), d['slot'], np.array(d['level']),
                    tuple(map(np.array, d['uv'])), tuple(map(tuple, d['source_faces'])), d['cell'])
    result = local_strips(seed, max_edge_m=3.9, face_budget=100)
    assert len(result.faces) < 100
    metrics = [face_metrics(result.verts[list(f)]) for f in result.faces]
    assert all(r.aspect <= 8 and r.max_edge_m <= 3.9 for r in metrics)
    assert sum(r.area_m2 for r in metrics) == pytest.approx(face_metrics(seed.verts).area_m2, abs=1e-5)
    assert len(vertex_pairs(result.verts, .002)[0]) == 0


@pytest.mark.parametrize('shape', ['short_edge', 'near_collinear'])
def test_acute_triangle_does_not_put_midpoint_or_centroid_next_to_source_vertex(shape):
    from dt_ai.geometry.ground_strips import local_strips
    from dt_ai.ops.inv_xview import vertex_pairs
    points = ([[0., 0., 0.], [1., 0., 0.], [1., .003, 0.]] if shape == 'short_edge'
              else [[.204, .171, -.000062], [-.207, -.171, -.001317], [0., 0., 0.]])
    vertices = np.array(points)
    seed = QuadMesh(vertices, ((0, 1, 2),), ['TileLight'], np.array([0]),
                    (vertices[:, :2]/4,), ((56,),), 4.)
    result = local_strips(seed, max_edge_m=3.9)
    assert len(vertex_pairs(result.verts, .002)[0]) == 0
    assert all(face_metrics(result.verts[list(f)]).aspect <= 8 for f in result.faces)
    area = sum(face_metrics(result.verts[list(f)]).area_m2 for f in result.faces)
    assert area == pytest.approx(face_metrics(vertices).area_m2, rel=1e-8)


def test_shared_edge_cuts_respect_other_original_vertices_not_only_local_corners():
    from dt_ai.geometry.ground_strips import local_strips
    from dt_ai.ops.inv_xview import vertex_pairs
    v = np.array([[.204, .171, -.000062], [-.207, -.171, -.001317], [0., 0., 0.],
                  [-2.025, -1.623, -.012104]])
    faces = ((0, 1, 2), (3, 1, 0))
    seed = QuadMesh(v, faces, ['TileLight']*2, np.array([0, 0]),
                    tuple(v[list(f), :2]/4 for f in faces), ((56,), (61,)), 4.)
    out = local_strips(seed, max_edge_m=3.9)
    assert len(vertex_pairs(out.verts, .002)[0]) == 0
    assert all(face_metrics(out.verts[list(f)]).aspect <= 8 for f in out.faces)
    assert set(out.source_faces) == {(56,), (61,)}


def test_centimetre_triangle_needs_distributed_not_clustered_staggered_rails():
    from dt_ai.geometry.ground_strips import local_strips
    from dt_ai.ops.inv_xview import vertex_pairs
    v = np.array([[0., 0., 0.], [.003, 0., .0003], [.015, .006, .001403]])
    seed = QuadMesh(v, ((0, 1, 2),), ['TileLight'], np.array([0]), (v[:, :2]/4,), ((985,),), 4.)
    out = local_strips(seed, max_edge_m=3.9)
    assert len(vertex_pairs(out.verts, .002)[0]) == 0
    assert all(face_metrics(out.verts[list(f)]).aspect <= 8 for f in out.faces)


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
