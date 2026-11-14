"""new-case: saved-mesh fixed-frame chart projection regressions."""
import math
import pytest
from tools.materials.course_grid_native import project_saved_points, rigid_triangle_uv, encode_triangle_uv


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


def test_float32_encoding_keeps_legal_band_with_subpixel_quantization_only():
    import numpy as np
    xyz=[[104.9970932006836,56.44607162475586,.15000119805336],
         [104.25457763671875,55.141239166259766,.14409610629081726],
         [104.25953674316406,55.149932861328125,.14409610629081726]]
    old=[[.6429628133773804,.4401338994503021],[.45526301860809326,.43939563632011414],
         [.4565143287181854,.43939563632011414]]
    ideal=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    out=encode_triangle_uv(xyz,ideal,tile_px=4096)
    assert min(out['singular_px_m'])>=512
    assert max(out['singular_px_m'])<=1706
    assert max(out['singular_px_m'])/min(out['singular_px_m'])<=1.02
    assert out['max_encoding_error_px']<.01
    assert np.asarray(out['uv'],dtype=np.float32).astype(float).tolist()==out['uv']


def test_unrepresentable_skinny_triangle_refuses_instead_of_lowering_gate():
    xyz=[[0,0,0],[1,0,0],[.99,.00001,.000002]]
    old=[[.3,.4],[.425,.4],[.42375,.40000125]]
    ideal=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    with pytest.raises(ValueError,match='encoding exceeds'):
        encode_triangle_uv(xyz,ideal,tile_px=4096)


@pytest.mark.parametrize('value',[float('nan'),float('inf')])
def test_saved_projection_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        project_saved_points([[value,0,0]],[[0,0,0],[1,0,0],[0,0,1]],[[0,0],[1,0],[0,1]])
