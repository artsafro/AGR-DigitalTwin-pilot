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


@pytest.mark.parametrize('mutation', ['empty','partial','unknown','nan','inf','duplicate','boolean','pixel','range'])
def test_reuse_invalid_or_incomplete_samples_never_become_compatible(mutation):
    from tools.materials.course_grid_appearance import audit_sample_reuse
    import copy
    records=[dict(owner=['wall',6,0],pixel=[11,27],maps=dict(Diffuse=[40.,32.,32.],ERM=[0.,252.,0.],Normal=[62.,127.,237.]))]
    if mutation=='empty':records=[]
    elif mutation=='partial':del records[0]['maps']['Normal']
    elif mutation=='unknown':records[0]['maps']['ORM']=records[0]['maps'].pop('ERM')
    elif mutation in ('nan','inf'):records[0]['maps']['Normal'][0]=float(mutation)
    elif mutation=='duplicate':records.append(copy.deepcopy(records[0]))
    elif mutation=='boolean':records[0]['maps']['Normal'][0]=True
    elif mutation=='pixel':records[0]['pixel'][0]=-.1
    elif mutation=='range':records[0]['maps']['Normal'][0]=256.
    with pytest.raises(ValueError):audit_sample_reuse(records,max_rgb_error=2.)


@pytest.mark.parametrize('error',[float('nan'),float('inf'),True,-1.,256.])
def test_reuse_nonfinite_or_unsupported_tolerance_refuses(error):
    from tools.materials.course_grid_appearance import audit_sample_reuse
    with pytest.raises(ValueError):audit_sample_reuse([],max_rgb_error=error)


@pytest.mark.parametrize('mutation',['empty','nan','inf','boolean','outside','partial','nonaffine','zero','unsupported','uvrange'])
def test_source_frame_invalid_inputs_never_produce_samples(mutation):
    from tools.materials.course_grid_appearance import sample_chart_rgb
    image=np.zeros((2,2,3),dtype=np.uint8)
    chart=[[0.,0.],[2.,0.],[2.,2.],[0.,2.]];uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]];points=[[1.,1.]]
    if mutation=='empty':points=[]
    elif mutation in ('nan','inf'):points[0][0]=float(mutation)
    elif mutation=='boolean':points[0][0]=True
    elif mutation=='outside':points=[[3.,1.]]
    elif mutation=='partial':uv.pop()
    elif mutation=='nonaffine':uv[2][0]=.8
    elif mutation=='zero':uv=[[0.,0.]]*4
    elif mutation=='unsupported':image=image.astype(float)
    elif mutation=='uvrange':uv[0][0]=-.1
    with pytest.raises(ValueError):sample_chart_rgb(image,uv,chart,points)


def test_reuse_checks_every_pair_not_only_first_owner():
    from tools.materials.course_grid_appearance import audit_sample_reuse
    samples=[dict(owner=['wall',i,0],pixel=[0,0],maps={r:[float(10+delta),0.,0.] for r in ('Diffuse','ERM','Normal')}) for i,delta in enumerate((0,2,-2))]
    report=audit_sample_reuse(samples,max_rgb_error=2.)
    assert len(report['conflicts'])==3
    assert all(r['owners']==[['wall',1,0],['wall',2,0]] and r['max_rgb_delta']==4 for r in report['conflicts'])


def test_generated_affine_source_sampling_and_threshold_probe():
    from tools.materials.course_grid_appearance import sample_chart_rgb,audit_sample_reuse
    rng=np.random.default_rng(1326)
    image=rng.integers(0,256,(9,7,3),dtype=np.uint8)
    for trial in range(100):
        shift=rng.uniform(-100.,100.,2);scale=rng.uniform(.1,8.,2)
        chart=[(shift+scale*np.array(p)).tolist() for p in [[0.,0.],[1.,0.],[1.,1.],[0.,1.]]]
        uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
        x,y=int(rng.integers(0,7)),int(rng.integers(0,9))
        point=shift+scale*np.array([(x+.5)/7,1-(y+.5)/9])
        result=sample_chart_rgb(image,uv,chart,[point.tolist()])
        assert np.array(result[0])==pytest.approx(image[y,x],abs=1e-9)
    # RGB tolerance is inclusive, not an unspecified colour-space acceptance.
    samples=[dict(owner=['wall',i,0],pixel=[0,0],maps={r:[float(i*2),0.,0.] for r in ('Diffuse','ERM','Normal')}) for i in (0,1)]
    assert audit_sample_reuse(samples,max_rgb_error=2.)['compatible'] is True
    assert audit_sample_reuse(samples,max_rgb_error=np.nextafter(2.,0.))['compatible'] is False

