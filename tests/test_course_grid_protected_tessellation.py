"""new-case: real native-boundary regression retains every protected node."""
import numpy as np
import pytest
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import face_pairs, tolerance_for
from tools.materials import course_grid_native as native


# Source715/brick62: float32 intermediate points are not perfectly collinear.
POINTS = [[1.3104900121688843,-1.2631808519363403,0.0],
 [1.2987421751022339,-1.2631808519363403,0.0],
 [-0.27053582668304443,-1.2631810903549194,0.0],
 [-0.28951549530029297,-1.2631810903549194,0.0],
 [-0.28951549530029297,-1.2631810903549194,-0.10999999940395355],
 [1.3104900121688843,-1.2631808519363403,-0.10999999940395355]]
OTHER = [1.2987425327301025,-1.2131811380386353,0.0]


@pytest.mark.parametrize('reverse', [False, True])
def test_native_protected_boundary_avoids_singular_newell_fan(reverse):
    points = list(reversed(POINTS)) if reverse else POINTS
    vertices = np.array(points + [OTHER])
    other = (6, points.index(POINTS[2]), points.index(POINTS[1]))
    before = face_pairs(PolyMesh(vertices,(tuple(range(6)),other)),tolerance_for('VPM'))
    assert [p[2] for p in before] == ([] if reverse else ['area'])
    triangles = native.triangulate_native_boundary(points)
    assert len(triangles) == 4
    assert set(i for t in triangles for i in t) == set(range(6))
    assert face_pairs(PolyMesh(vertices,tuple(map(tuple,triangles))+(other,)),tolerance_for('VPM')) == []
    areas = [np.cross(vertices[t[1]]-vertices[t[0]], vertices[t[2]]-vertices[t[0]]) for t in triangles]
    boundary_normal = sum((np.cross(a,b) for a,b in zip(vertices[:6],np.roll(vertices[:6],-1,axis=0))),np.zeros(3))
    assert all(np.dot(a,boundary_normal) > 0 for a in areas)


@pytest.mark.parametrize('points', [[], [[0,0,0]]*3, [[0,0,0],[1,0,0],[2,0,0]],
 [[0,0,0],[1,0,0],[1,float('nan'),0]]])
def test_native_boundary_refuses_missing_or_degenerate_surface(points):
    with pytest.raises(ValueError):
        native.triangulate_native_boundary(points)
