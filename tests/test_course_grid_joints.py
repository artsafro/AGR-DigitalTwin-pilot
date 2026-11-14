"""new-case: clipped/junction-aware joint measurements never require an outside centre."""
import pytest
from tools.materials.course_grid_native import joint_cross_section


def test_clipped_thin_face_has_a_measurable_joint_not_a_missing_5mm_centre():
    face=[[0.,0.],[.003,0.],[.003,1.],[0.,1.]]
    zone=[[0.,0.],[.01,0.],[.01,1.],[0.,1.]]
    out=joint_cross_section(face,[zone],[face],[0.,.5],[1.,0.])
    assert out['passed'] and out['classification']=='clipped'
    assert out['expected_width_mm']==pytest.approx(3.)
    assert out['max_centre_error_mm']==pytest.approx(0.)
    assert out['nominal_centre_outside_face']


def test_crossing_joint_union_is_not_mislabeled_as_a_15mm_centre_error():
    face=[[0.,0.],[.04,0.],[.04,1.],[0.,1.]]
    out=joint_cross_section(face,[face],[face],[0.,.5],[1.,0.])
    assert out['passed'] and out['classification']=='junction'
    assert out['expected_width_mm']==pytest.approx(40.)
    assert out['max_centre_error_mm']==0


def test_missing_and_false_extra_joint_fail_with_complete_intervals():
    face=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]];zone=[[0.,0.],[.01,0.],[.01,1.],[0.,1.]]
    far=[[.1,0.],[.11,0.],[.11,1.],[.1,1.]]
    out=joint_cross_section(face,[zone],[far],[0.,.5],[1.,0.])
    assert not out['passed'] and out['missing_intervals']==1 and out['false_intervals']==1


@pytest.mark.parametrize('point',[[float('nan'),0],[float('inf'),0],[]])
def test_nonfinite_partial_probe_is_error(point):
    face=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    with pytest.raises(ValueError):joint_cross_section(face,[face],[face],point,[1,0])
