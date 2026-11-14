"""new-case: source-bound all-map samples, never a constant joint Normal claim."""
import numpy as np
import pytest


def test_chart_sampling_preserves_top_down_png_and_bilinear_pixel_centres():
    from tools.materials.course_grid_appearance import sample_chart_rgb
    # Synthetic 2x2 PNG, bottom-left chart origin. Do not derive this oracle
    # from the production affine solver or PNG indexing implementation.
    image=np.array([[[10,20,30],[30,40,50]],[[50,60,70],[70,80,90]]],dtype=np.uint8)
    chart=[[0.,0.],[2.,0.],[2.,2.],[0.,2.]]
    uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    result=sample_chart_rgb(image,uv,chart,[[.5,.5],[1.5,1.5],[1.,1.]])
    assert np.asarray(result)==pytest.approx(np.array([[50.,60.,70.],[30.,40.,50.],[40.,50.,60.]]))
