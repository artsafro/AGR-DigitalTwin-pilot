"""primitive_box and the silhouette test (cloud card C4, D082). All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops.invariants import Context, Mesh, winding_number
from dt_ai.ops.operations import _box_mesh, primitive_box, run_operation
from dt_ai.ops.silhouette import silhouette_deviation, silhouette_deviations
from tests.ops.test_invariants import box, quad


def join(*meshes):
    """One part made of several closed meshes."""
    offsets = np.cumsum([0] + [len(m.vertices) for m in meshes[:-1]])
    return Mesh(np.concatenate([m.vertices for m in meshes]),
                np.concatenate([m.triangles + o for m, o in zip(meshes, offsets)]))


def run(part_mesh, **kwargs):
    scene = {"p": part_mesh}
    return scene, run_operation(scene, "primitive", "p", lambda s: primitive_box(s, "p", **kwargs),
                                params={"build_as": "box", **kwargs})


def test_box_mesh_is_closed_with_outward_normals():
    b = _box_mesh(np.array([0.0, 0.0, 0.0]), np.array([2.0, 1.0, 3.0]))
    assert len(b.triangles) == 12
    assert winding_number([[1, 0.5, 1.5]], b)[0] == pytest.approx(1, abs=1e-6)       # +1 = outward orientation
    assert winding_number([[5, 5, 5]], b)[0] == pytest.approx(0, abs=1e-6)


def test_a_box_part_is_replaced_by_the_same_box():
    scene, r = run(box((0, 0, 0), (2, 1, 3)))
    assert r.applied and r.report.passed
    assert r.scene["p"].vertices.min(0).tolist() == [0, 0, 0] and r.scene["p"].vertices.max(0).tolist() == [2, 1, 3]
    assert r.scene["p"] is not scene["p"] and scene["p"].triangles.shape == (12, 3)


def test_small_deviation_inside_the_limit_is_replaced_by_the_bounding_box():
    """A box with a 30 mm tab on one side: the bounding box is 30 mm off at most, the limit is 70 mm."""
    part = join(box((0, 0, 0), (1, 1, 1)), box((1, 0.4, 0.4), (1.03, 0.6, 0.6)))
    scene, r = run(part)
    assert r.applied
    assert r.scene["p"].vertices.max(0)[0] == pytest.approx(1.03)
    dev = silhouette_deviations(part, r.scene["p"])
    assert max(dev.values()) == pytest.approx(0.03, abs=0.02)


def test_deviation_over_the_limit_is_refused_with_the_view_and_the_alternative():
    """An L-shaped part: the bounding box fills a 0.5 m corner."""
    part = join(box((0, 0, 0), (1, 1, 1)), box((1, 0, 0), (1.5, 0.5, 1)))
    scene, r = run(part)
    assert not r.applied and r.scene is scene and r.report is None
    assert "top view" in r.question and "rebuild it by contour" in r.question


def test_the_limit_is_a_parameter():
    part = join(box((0, 0, 0), (1, 1, 1)), box((1, 0.4, 0.4), (1.03, 0.6, 0.6)))
    assert not run(part, silhouette_max_m=0.01)[1].applied
    assert run(part, silhouette_max_m=0.07)[1].applied


def test_a_frame_with_a_hole_is_not_a_box():
    """Four bars round a 0.6 m opening: the silhouette of the box fills the opening."""
    bars = [box((0, 0, 0), (1, 0.1, 0.1)), box((0, 0, 0.9), (1, 0.1, 1.0)),
            box((0, 0, 0.1), (0.2, 0.1, 0.9)), box((0.8, 0, 0.1), (1, 0.1, 0.9))]
    scene, r = run(join(*bars))
    assert not r.applied and "front view" in r.question


def test_flat_and_empty_parts_are_refused():
    scene, r = run(quad(0.0))
    assert not r.applied and "flat along z" in r.question and "plane, not a box" in r.question
    scene, r = run(Mesh(np.zeros((0, 3)), np.zeros((0, 3), int)))
    assert not r.applied and "no faces" in r.question


def test_a_part_turned_off_the_axes_fails_the_test():
    c, s = np.cos(np.pi / 4), np.sin(np.pi / 4)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    b = box((-1, -1, 0), (1, 1, 1))
    turned = Mesh(b.vertices @ rot.T, b.triangles)
    assert not run(turned)[1].applied


def test_replacement_that_breaks_an_invariant_is_rolled_back():
    """The ridge of a roof-like part is flat on top once boxed, and lands 3 mm under a neighbour sheet facing up."""
    roof = Mesh(np.array([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, 0.5, 1.0)], float),
                np.array([(0, 2, 1), (0, 3, 2), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]))
    sheet = quad(1.003, size=1.0)
    scene = {"p": roof, "sheet": sheet}
    ctx = Context(opacity_parts=frozenset({"sheet"}))          # a one-sided sheet: its back is allowed
    r = run_operation(scene, "primitive", "p", lambda s: primitive_box(s, "p", silhouette_max_m=10.0), ctx)
    assert not r.applied and r.scene is scene
    assert [b.name for b in r.report.broken] == ["no_close_overlap"]


# ---- silhouette ------------------------------------------------------------------------------------------------

def test_silhouette_deviation_is_zero_for_equal_and_symmetric():
    a, b = box((0, 0, 0), (1, 1, 1)), box((0, 0, 0), (1, 1, 1.05))
    assert silhouette_deviation(a, a, 1) == pytest.approx(0, abs=1e-9)
    assert silhouette_deviation(a, b, 1) == pytest.approx(silhouette_deviation(b, a, 1))
    assert silhouette_deviation(a, b, 2) == pytest.approx(0, abs=1e-9)     # the top view does not see the height


@pytest.mark.parametrize("extra", [0.03, 0.07, 0.2])
def test_silhouette_deviation_measures_the_overhang_within_one_step(extra):
    a, b = box((0, 0, 0), (1, 1, 1)), box((0, 0, 0), (1 + extra, 1, 1))
    assert silhouette_deviation(a, b, 2) == pytest.approx(extra, abs=0.0176)


def test_empty_silhouette_is_infinitely_far_from_a_solid_one():
    empty = Mesh(np.zeros((0, 3)), np.zeros((0, 3), int))
    assert silhouette_deviation(empty, box((0, 0, 0), (1, 1, 1)), 2) == float("inf")
    assert silhouette_deviation(empty, empty, 2) == 0.0
