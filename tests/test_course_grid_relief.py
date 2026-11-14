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


@pytest.mark.parametrize('case', ['empty','partial','nan','inf','boolean','mirror','tilt','scale','shear','range','backward','zero'])
def test_relief_partial_or_unsupported_frames_refuse(case):
    from tools.materials.course_grid_appearance import compose_relief_normal
    base=[[127.5,127.5,255.]];relief=[[1.,0.]]
    source=[[1.,0.,0.],[0.,1.,0.]];target=[[1.,0.,0.],[0.,1.,0.]]
    if case=='empty':relief=[]
    elif case=='partial':base.append(base[0].copy())
    elif case in ('nan','inf'):relief[0][0]=float(case)
    elif case=='boolean':source[0][0]=True
    elif case=='mirror':target[0][0]=-1.
    elif case=='tilt':target=[[1.,0.,0.],[0.,0.,1.]]
    elif case=='scale':target[0][0]=2.
    elif case=='shear':target[1][0]=.01
    elif case=='range':base[0][0]=256.
    elif case=='backward':base[0][2]=0.
    elif case=='zero':base[0]=[127.5]*3
    with pytest.raises(ValueError):compose_relief_normal(base,relief,source,target)


@pytest.mark.parametrize('case', ['empty','partial','nan','inf','boolean','object','channels','outside'])
def test_signed_field_incomplete_or_nonfinite_refuses(case):
    from tools.materials.course_grid_appearance import sample_chart_field
    image=np.zeros((2,2,2),dtype=float)
    uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    points=[[.5,.5]]
    if case=='empty':image=np.zeros((0,2,2),dtype=float)
    elif case=='partial':uv.pop()
    elif case in ('nan','inf'):image[0,0,0]=float(case)
    elif case=='boolean':image=image.astype(bool)
    elif case=='object':image=image.astype(object)
    elif case=='channels':image=np.zeros((2,2,4))
    elif case=='outside':points=[[2.,2.]]
    with pytest.raises(ValueError):sample_chart_field(image,uv,[[0.,0.],[1.,0.],[1.,1.],[0.,1.]],points)


def test_generated_source_relief_replay_and_rotated_world_vectors():
    from tools.materials.course_grid_appearance import compose_relief_normal
    rng=np.random.default_rng(1326)
    identity=np.array([[1.,0.,0.],[0.,1.,0.]])
    for _ in range(100):
        theta=float(rng.uniform(-np.pi,np.pi));c,s=np.cos(theta),np.sin(theta)
        target=np.array([[c,s,0.],[-s,c,0.]])
        normal=rng.uniform(-.9,.9,3);normal[2]=rng.uniform(.01,1.)
        relief=rng.uniform(-1.,1.,2)
        got=np.asarray(compose_relief_normal([((normal+1)*127.5).tolist()],[relief.tolist()],identity.tolist(),target.tolist()))[0]/127.5-1
        # Independent world-space sum, then project the resulting world vector.
        world=normal[0]*target[0]+normal[1]*target[1]+np.array([relief[0],relief[1],normal[2]])
        expected=world/np.linalg.norm(world)
        actual=got[0]*target[0]+got[1]*target[1]+np.array([0.,0.,got[2]])
        assert actual==pytest.approx(expected,abs=1e-12)
