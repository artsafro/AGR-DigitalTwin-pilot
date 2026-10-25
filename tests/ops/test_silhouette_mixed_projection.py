"""new-case: mixed polygon/edge-on source projections exposed by the Skolkovo mullions."""
import numpy as np
import pytest
import shapely

from dt_ai.ops.invariants import Mesh
from dt_ai.ops.operations import primitive_box, run_operation
from dt_ai.ops.silhouette import silhouette, silhouette_deviations


def open_mullion(tilt=3e-8):
    # Synthetic 50 x 100 x 250 mm open tube: a tiny source tilt creates
    # polygon area on one side, while the other three project edge-on.
    v = np.array([[.05, .1, 0], [0, .1, 0], [0, .1-tilt, .25], [.05, .1-tilt, .25],
                  [.05, 0, 0], [.05, 0, .25], [0, 0, 0], [0, 0, .25]])
    f = np.array([[0,1,2],[2,3,0],[4,0,5],[3,5,0],[6,4,5],[5,7,6],[1,6,2],[7,2,6]])
    return Mesh(v, f)


def test_mixed_projection_preserves_all_edge_on_surfaces():
    mesh = open_mullion()
    projected = silhouette(mesh, 2)
    for xy in ((.025, 0), (0, .05), (.05, .05), (.025, .1)):
        assert projected.distance(shapely.Point(xy)) < 1e-12, xy
    assert projected.area == pytest.approx(.05 * 3e-8, abs=1e-16)


def test_mixed_projection_no_longer_spuriously_refuses_a_small_cap():
    source = open_mullion()
    result = run_operation({'p': source}, 'primitive_box', 'p', lambda s: primitive_box(s, 'p'))
    assert result.applied, result.question
    # Filling the real rectangular perimeter is at most 25 mm away from it.
    assert silhouette_deviations(source, result.scene['p'])['top'] <= .025 + 1e-9


@pytest.mark.parametrize('axis', [0, 1, 2])
@pytest.mark.parametrize('translation', [0., 1000.])
def test_generated_mixed_projections_keep_separate_vertical_fins(axis, translation):
    v = np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0], [2,0,0],[3,0,0],[3,0,1]])
    f = np.array([[0,1,2],[0,2,3],[4,5,6]])
    order = [i for i in range(3) if i != axis] + [axis]
    world = np.zeros_like(v, dtype=float)
    world[:, order] = v
    world += translation
    mesh = Mesh(world, f)
    projected = silhouette(mesh, axis)
    expected = shapely.union_all([shapely.box(translation,translation,translation+1,translation+1),
                                 shapely.LineString([(translation+2,translation),(translation+3,translation)])])
    assert projected.equals(expected)


def test_mixed_projection_retains_diagnostic_for_a_removed_fin():
    v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0], [2,0,0],[3,0,0],[3,0,1]])
    full=Mesh(v,np.array([[0,1,2],[0,2,3],[4,5,6]]))
    reduced=Mesh(v[:4],np.array([[0,1,2],[0,2,3]]))
    assert silhouette_deviations(full,reduced)['top'] == pytest.approx(2.)


def test_uncovered_polygon_sampling_does_not_hide_a_separate_line():
    v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0], [2,0,0],[3,0,0],[3,0,1]])
    full=Mesh(v,np.array([[0,1,2],[0,2,3],[4,5,6]]))
    reduced=Mesh(np.array([[0,0,0],[.9,0,0],[.9,1,0],[0,1,0]]),np.array([[0,1,2],[0,2,3]]))
    assert silhouette_deviations(full,reduced)['top'] == pytest.approx(2.1)
