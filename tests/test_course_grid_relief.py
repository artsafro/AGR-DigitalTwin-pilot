"""new-case: measured source relief transport without changing physical scale."""
import numpy as np
import pytest


def test_source_float_field_bilinear_keeps_signed_relief_not_rgb_quantization():
    from tools.materials.course_grid_appearance import sample_chart_field
    field=np.array([[[.25,-.5],[.5,-1.]],[[0.,0.],[1.,-2.]]],dtype=float)
    uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    chart=[[0.,0.],[2.,0.],[2.,2.],[0.,2.]]
    got=sample_chart_field(field,uv,chart,[[.5,.5],[1.5,1.5],[1.,1.]])
    assert np.array(got)==pytest.approx(np.array([[0.,0.],[.5,-1.],[.4375,-.875]]))


def test_relief_rotates_in_tangent_frame_not_the_uv_island_or_geometry():
    from tools.materials.course_grid_appearance import compose_relief_normal
    # Exact neutral underlying vector [0,0,1], +U relief in the source plane.
    base=[[127.5,127.5,255.]]
    source=[[1.,0.,0.],[0.,1.,0.]]
    target=[[0.,1.,0.],[-1.,0.,0.]]
    result=compose_relief_normal(base,[[1.,0.]],source,target)
    assert np.array(result)==pytest.approx(np.array([[127.5,37.3438853987152,217.6561146012848]]))


def test_source_renderer_equation_can_be_replayed_without_normal_rescaling():
    from tools.materials.course_grid_appearance import compose_relief_normal
    axes=[[1.,0.,0.],[0.,1.,0.]]
    assert np.array(compose_relief_normal([[127.5,127.5,255.]],[[0.,0.]],axes,axes))==pytest.approx(np.array([[127.5,127.5,255.]]))
    # 45-degree groove slope, not compressed into a narrower colour seam.
    result=compose_relief_normal([[127.5,127.5,255.]],[[1.,0.]],axes,axes)
    assert np.array(result)==pytest.approx(np.array([[217.6561146012848,127.5,217.6561146012848]]))
