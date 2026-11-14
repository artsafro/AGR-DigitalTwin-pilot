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


def test_reuse_reports_both_owners_when_one_texel_needs_flat_and_groove_normals():
    from tools.materials.course_grid_appearance import audit_sample_reuse
    def record(owner, normal):
        return dict(owner=owner, pixel=[11,27], maps=dict(Diffuse=[40.,32.,32.],ERM=[0.,252.,0.],Normal=normal))
    records=[record(['wall',6,0],[62.,127.,237.]),record(['wall',8,0],[127.,127.,255.])]
    report=audit_sample_reuse(records,max_rgb_error=2.)
    assert report['compatible'] is False
    assert report['samples']==2 and report['texels']==1
    assert report['conflicts']==[dict(pixel=[11,27],role='Normal',owners=[['wall',6,0],['wall',8,0]],max_rgb_delta=65.)]
    assert report['passed'] is False  # finite samples never certify the whole maps

