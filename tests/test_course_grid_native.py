"""new-case: saved-mesh fixed-frame chart projection regressions."""
import math
import pytest
from tools.materials.course_grid_native import project_saved_points, rigid_triangle_uv


def test_saved_points_use_source_plane_frame_not_old_precast_offsets():
    ref=[[0.,0.,0.],[2.,0.,0.],[2.,0.,1.],[0.,0.,1.]]
    chart=[[10.,-4.],[12.,-4.],[12.,-3.],[10.,-3.]]
    points=[[.010002,.000004,.5],[1.997999,-.000004,.75]]
    out=project_saved_points(points,ref,chart)
    assert out[0]==pytest.approx([10.010002,-3.5])
    assert out[1]==pytest.approx([11.997999,-3.25])


def test_rigid_triangle_preserves_long_edge_heading_and_frozen_density():
    import numpy as np
    xyz=[[0,0,0],[1,0,0],[.99,.00001,.000002]]
    old=[[.3,.4],[.425,.4],[.42375,.40000125]]
    uv=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    e=np.array(xyz)[1:]-xyz[0];q=(np.array(uv)[1:]-uv[0])*4096
    a=e[0]/np.linalg.norm(e[0]);n=np.cross(e[0],e[1]);n/=np.linalg.norm(n);b=np.cross(n,a)
    singular=np.linalg.svd(np.linalg.solve(np.c_[e@a,e@b],q),compute_uv=False)
    assert singular==pytest.approx([512.1,512.1],abs=1e-5)
    assert uv[0]==old[0] and uv[1][1]==uv[0][1]


@pytest.mark.parametrize('value',[float('nan'),float('inf')])
def test_saved_projection_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        project_saved_points([[value,0,0]],[[0,0,0],[1,0,0],[0,0,1]],[[0,0],[1,0],[0,1]])
