"""Closed source links must not disappear when a face is subdivided (synthetic)."""
import math
import pytest
from tools.materials.course_grid_audit import audit_corners


def subdivided_corner(valence=4):
    points = [[0,0,0], [1,0,0], [0,1,0], [0,0,1], [.5,.5,0], [.5,0,.5]]
    faces = [[0,3,1], [0,2,3], [0,1,4], [0,4,2]]
    if valence == 5:
        faces = [[0,3,5], [0,5,1], *faces[1:]]
    return [{'object':'synthetic', 'face':i, 'vertices':vs, 'xyz':[points[v] for v in vs]}
            for i,vs in enumerate(faces)]


@pytest.mark.parametrize('valence', [4,5])
def test_subdividing_one_face_does_not_hide_intrinsic_corner_defect(valence):
    result = audit_corners(subdivided_corner(valence), anisotropy_limit=1.02)
    witness = next(c for c in result['corners'] if c['vertex']==0)
    assert len(witness['faces']) == valence
    assert witness['angle_sum_deg'] == pytest.approx(270)
    assert witness['defect_deg'] == pytest.approx(90)
    assert witness['max_angle_change_deg'] < 6
    assert result['passed'] is False


def test_open_link_does_not_become_a_closed_fan():
    assert audit_corners(subdivided_corner()[:-1], anisotropy_limit=1.02)['corners'] == []


def test_subdivided_fan_rigid_transform_and_input_order_probe():
    for seed in range(20):
        rows = subdivided_corner(5)
        a = seed*.37
        for r in rows:
            r['xyz'] = [[math.cos(a)*x-math.sin(a)*y+seed,
                         math.sin(a)*x+math.cos(a)*y-seed,z+seed] for x,y,z in r['xyz']]
        rows.reverse()
        corners = audit_corners(rows, anisotropy_limit=1.02)['corners']
        assert len(corners)==1
        assert corners[0]['defect_deg'] == pytest.approx(90, abs=1e-8)
