"""new-case: NPM opacity swaps under the kernel invariants. All meshes are SYNTHETIC."""
import numpy as np
import pytest

from dt_ai.ops import operations
from dt_ai.ops.invariants import Context, Mesh
from dt_ai.ops.silhouette import silhouette_deviations
from tests.ops.test_invariants import box
from tests.ops.test_primitive import join


def railing(angle=0, depth=0.05, count=16):
    """Posts + rails + evenly spaced balusters; 240 triangles at count=16."""
    y = depth / 2
    pieces = [box((0, -y, 0), (.05, y, 1.2)), box((1.95, -y, 0), (2, y, 1.2)),
              box((.05, -y, 0), (1.95, y, .05)), box((.05, -y, 1.15), (1.95, y, 1.2))]
    pieces += [box((x - .015, -y, .05), (x + .015, y, 1.15)) for x in np.linspace(.12, 1.88, count)]
    mesh = join(*pieces)
    c, s = np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    return Mesh(mesh.vertices @ rot.T, mesh.triangles)


def snapshot(scene):
    return {p: (m.vertices.copy(), m.triangles.copy()) for p, m in scene.items()}


def assert_unchanged(scene, before):
    assert set(scene) == set(before)
    for p, (v, t) in before.items():
        np.testing.assert_array_equal(scene[p].vertices, v)
        np.testing.assert_array_equal(scene[p].triangles, t)


@pytest.mark.parametrize("angle", [0, 30])
def test_railing_becomes_one_midplane_quad_without_mutating_input(angle):
    scene = {"railing": railing(angle)}
    before = snapshot(scene)
    ctx = Context(opacity_parts=frozenset({"railing"}))
    result = operations.run_operation(scene, "to_opacity_plane", "railing",
                                      lambda s: operations.to_opacity_plane(s, "railing"), ctx)
    assert result.applied, result.question
    assert result.report.passed and result.question is None
    assert result.notes == {"faces_before": 240, "faces_after": 2}
    plane = result.scene["railing"]
    assert plane.vertices.shape == (4, 3) and plane.triangles.shape == (2, 3)
    normal = np.array([-np.sin(np.deg2rad(angle)), np.cos(np.deg2rad(angle)), 0])
    assert plane.vertices @ normal == pytest.approx(np.zeros(4), abs=1e-12)
    tangent = np.array([normal[1], -normal[0], 0])
    assert sorted(plane.vertices @ tangent) == pytest.approx([0, 0, 2, 2], abs=1e-12)
    assert sorted(plane.vertices[:, 2]) == pytest.approx([0, 0, 1.2, 1.2], abs=1e-12)
    assert max(silhouette_deviations(scene["railing"], plane, .07 / 32).values()) <= .07
    assert ctx.opacity_parts == frozenset({"railing"})
    assert_unchanged(scene, before)
