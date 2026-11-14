"""new-case: saved-mesh fixed-frame chart projection regressions."""
import math
import pytest
from tools.materials.course_grid_native import project_saved_points


def test_saved_points_use_source_plane_frame_not_old_precast_offsets():
    ref=[[0.,0.,0.],[2.,0.,0.],[2.,0.,1.],[0.,0.,1.]]
    chart=[[10.,-4.],[12.,-4.],[12.,-3.],[10.,-3.]]
    points=[[.010002,.000004,.5],[1.997999,-.000004,.75]]
    out=project_saved_points(points,ref,chart)
    assert out[0]==pytest.approx([10.010002,-3.5])
    assert out[1]==pytest.approx([11.997999,-3.25])


@pytest.mark.parametrize('value',[float('nan'),float('inf')])
def test_saved_projection_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        project_saved_points([[value,0,0]],[[0,0,0],[1,0,0],[0,0,1]],[[0,0],[1,0],[0,1]])
