"""primitive_box and the silhouette test (cloud card C4, D082). All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops.invariants import Context, Mesh, winding_number
from dt_ai.ops.operations import _box_mesh, primitive_box, run_operation, to_opacity_plane
from dt_ai.ops.silhouette import SILHOUETTE_MAX_M, silhouette_deviation, silhouette_deviations
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


@pytest.mark.parametrize("axis", [0, 1])
def test_edge_on_quad_is_a_line_not_an_empty_silhouette(axis):
    plane = quad(0, size=1)
    solid = box((0, 0, -0.025), (1, 1, 0.025))
    assert silhouette_deviation(solid, plane, axis) == pytest.approx(0.025)
    assert silhouette_deviation(plane, plane, axis) == 0.0


def test_point_projection_is_valid_and_measures_distance():
    a = Mesh(np.array([[0, 0, z] for z in (0, 1, 2)]), np.array([[0, 1, 2]]))
    b = Mesh(a.vertices + [0.03, 0.04, 0], a.triangles)
    assert silhouette_deviation(a, b, 2) == pytest.approx(0.05)
    assert silhouette_deviation(a, a, 2) == 0.0


def test_empty_silhouette_is_infinitely_far_from_a_solid_one():
    empty = Mesh(np.zeros((0, 3)), np.zeros((0, 3), int))
    assert silhouette_deviation(empty, box((0, 0, 0), (1, 1, 1)), 2) == float("inf")
    assert silhouette_deviation(empty, empty, 2) == 0.0


def _rigid(mesh, seed):
    """The seeded rigid motion from the opacity probe (QR rotation, shift in [-10, 10])."""
    rng = np.random.default_rng(seed)
    rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    shift = rng.uniform(-10, 10, size=3)
    return Mesh(mesh.vertices @ rotation.T + shift, mesh.triangles)


def _flat(x0, y0, x1, y1):
    v = np.array([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], float)
    return Mesh(v, np.array([(0, 1, 2), (0, 2, 3)]))


def _cover_around_ring(outer, width, margin):
    """Inner square plus an outer frame, leaving a ring of `width` uncovered."""
    hole0, hole1 = width, outer - width
    span0, span1 = -margin, outer + margin
    return join(
        _flat(hole0, hole0, hole1, hole1),
        _flat(span0, span0, span1, 0),
        _flat(span0, outer, span1, span1),
        _flat(span0, 0, 0, outer),
        _flat(outer, 0, span1, outer),
    )


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5, 6, 7])
def test_rotated_50mm_slab_stays_within_half_thickness_of_its_midplane(seed):
    """A 50 mm slab is at most 0.025 m from its PCA mid-plane, in every orthographic view.

    Seed 0 is the published reproducer: the old symmetric fallback reported
    {'top': 1.0398858997941611, 'front': 0.00858, 'side': 0.02354}.
    """
    assert SILHOUETTE_MAX_M == 0.07
    slab = box((0, -0.025, 0), (2, 0.025, 1.2))
    moved = _rigid(slab, seed)
    plane = to_opacity_plane({"p": moved}, "p")["p"]
    dev = silhouette_deviations(moved, plane, SILHOUETTE_MAX_M / 32)
    assert max(dev.values()) <= 0.025


@pytest.mark.parametrize("seed", range(6))
def test_holed_ring_missed_by_the_grid_keeps_its_interior_reach(seed):
    """A ring thinner than the sample step still reports the interior reach, not the reverse leg.

    The cover touches both rings, so a boundary-only distance is 0. The symmetric
    Hausdorff distance follows a 1 m frame corner and is sqrt(2). The farthest
    material point sits in the square corner: radius width * sqrt(2) / (1 + sqrt(2)).
    """
    rng = np.random.default_rng(1000 + seed)
    width = float(rng.uniform(0.05, 0.35))
    outer = 10.0
    solid = _flat(-1.0, -1.0, outer + 1.0, outer + 1.0)
    cover = _cover_around_ring(outer, width, margin=1.0)
    dev = silhouette_deviation(solid, cover, 2, step_m=max(width * 5, 1.0))
    corner = width * np.sqrt(2) / (1 + np.sqrt(2))
    assert dev == pytest.approx(corner, abs=1e-6)
    assert width / 2 < dev < 1.0
