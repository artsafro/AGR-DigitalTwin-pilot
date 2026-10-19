"""The checkers' weld is a distance weld (issue #101): vertices within weld_m (inclusive) of a group's first vertex
are one vertex, whatever the grid; vertices farther apart than weld_m are never one."""
import numpy as np
import pytest

from dt_ai.geometry.from_spec import BuildError, _hold
from twinqa.geometry.mesh import edge_uses, weld

W = 0.003


def same(vertices, a, b):
    ids = weld(np.asarray(vertices, dtype=float), W)
    return ids[a] == ids[b]


def test_points_a_millimetre_apart_are_one_whatever_the_grid():
    assert same([[0.001, 0, 0], [0.002, 0, 0]], 0, 1)


def test_points_exactly_the_weld_apart_are_one():
    assert same([[0, 0, 0], [0.003, 0, 0]], 0, 1)
    assert same([[0.001, 0, 0], [0.004, 0, 0]], 0, 1)   # 0.0030000000000000005 in floats


def test_points_farther_than_the_weld_are_two_even_if_close_on_every_axis():
    assert not same([[-0.0014] * 3, [0.0014] * 3], 0, 1)   # 4.85 mm apart, 2.8 mm on each axis


def test_a_chain_does_not_weld_beyond_the_weld_distance():
    chain = np.array([[i * 0.002, 0, 0] for i in range(10)])
    ids = weld(chain, W)
    for i in range(len(chain)):
        assert np.linalg.norm(chain[ids == ids[i]] - chain[i], axis=1).max() <= 2 * W
    assert len(set(ids.tolist())) > 1


def test_ids_are_compact():
    ids = weld(np.array([[0, 0, 0], [5, 0, 0], [0.001, 0, 0], [9, 9, 9]], dtype=float), W)
    assert sorted(set(ids.tolist())) == [0, 1, 2]


@pytest.mark.parametrize("dx", [0.0, 0.001])
def test_open_edges_do_not_depend_on_where_the_mesh_lies(dx):
    v = np.array([[.001, 0, 0], [.010, 0, 0], [.001, 1, 0], [.011, 0, 0], [.002, 0, 0], [.001, -1, 0]]) + [dx, 0, 0]
    t = np.array([[0, 1, 2], [3, 4, 5]])
    _, counts, _ = edge_uses(t, weld(v, W))
    assert int((counts == 1).sum()) == 4


class _M:
    def __init__(self, vertices, faces):
        self.vertices, self.faces = vertices, [(f, 0) for f in faces]


def test_the_engine_holds_its_mesh_by_the_checkers_weld():
    # a quad whose two near corners are 1 mm apart collapses under the 3 mm weld, wherever the grid lies
    quad = [[0.001, 0, 0], [0.002, 0, 0], [0.002, 0, 1], [0.001, 0, 1]]
    with pytest.raises(BuildError, match="collapses"):
        _hold(_M(quad, [[0, 1, 2, 3]]), [0.0, 1.0], W)
