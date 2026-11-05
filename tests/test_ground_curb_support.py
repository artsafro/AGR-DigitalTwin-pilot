"""Synthetic raised-cake/curb-bottom witnesses for #371, not delivery evidence."""
import numpy as np
import pytest
from shapely.geometry import box
from dt_ai.geometry import ground_cake as gc, ground_details as gd
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report, XviewTolerance


def fixture(slope=1., offset=0.):
    sampler=gc.ReliefSampler(gc.build_tin([(x+offset,y+offset,100+slope*x) for x in (-2,6) for y in (-2,6)]))
    curb=gd._curb_solid(box(offset,offset,offset+2,offset+1),sampler,.05,'CurbGarden')
    v=np.array([[offset-1,offset-1,99.012],[offset+4,offset-1,104.012],[offset+4,offset+4,104.012],[offset-1,offset+4,99.012]])
    v[:,2]=100.012+slope*(v[:,0]-offset)
    support=gc.Mesh(v,np.array([[0,1,2],[0,2,3]]),['Mulch']*2,np.ones(2,int),np.zeros((2,3,2)),4.)
    return curb,support


def report(curb,support):
    m=gd.combine([curb,support])
    for i,p in enumerate(m.verts[m.faces]):
        n=np.cross(p[1]-p[0],p[2]-p[0]);axes=[a for a in range(3) if a!=abs(n).argmax()]
        m.uv[i]=p[:,axes]/4
    q=pair_triangles(m)
    return part_report('curb_support',PolyMesh(q.verts,q.faces),XviewTolerance())


@pytest.mark.parametrize('offset',[0.,-7600.])
def test_curb_bottom_trims_to_normal_gap_without_moving_top_or_contour(offset):
    curb,support=fixture(offset=offset)
    assert report(curb,support).face_pairs, 'fixture must reproduce sub-5 mm support gap'
    original=curb.verts.copy()
    fitted=gd.fit_curb_bottom(curb,support)
    assert np.array_equal(fitted.verts[:,:2],original[:,:2])
    top=np.unique(curb.faces[np.cross(curb.verts[curb.faces[:,1]]-curb.verts[curb.faces[:,0]],curb.verts[curb.faces[:,2]]-curb.verts[curb.faces[:,0]])[:,2]>0])
    assert np.array_equal(fitted.verts[top],original[top])
    assert np.array_equal(fitted.faces,curb.faces) and fitted.slot==curb.slot
    dz=fitted.verts[:,2]-original[:,2]
    assert 0<dz.max()<.01 and dz.min()==0
    r=report(fitted,support)
    assert not r.vertex_pairs and not r.face_pairs


def test_real_world_overlay_does_not_invent_a_support_hole():
    import json
    from pathlib import Path
    data=json.loads((Path(__file__).parent/'data/ground-v015-curb-support-overlay.json').read_text())
    p=np.array(data['bottom']);v=np.vstack([p+np.array([0,0,.05]),p])
    f=np.array([[2,1,0],[3,4,5],[0,1,4],[0,4,3],[1,2,5],[1,5,4],[2,0,3],[2,3,5]])
    curb=gc.Mesh(v,f,['CurbGarden']*len(f),np.full(len(f),-2),np.zeros((len(f),3,2)),4.)
    triangles=np.array(data['support_triangles'])
    support=gc.Mesh(triangles.reshape(-1,3),np.arange(triangles.size//3).reshape(-1,3),['Mulch']*len(triangles),np.zeros(len(triangles),int),np.zeros((len(triangles),3,2)),4.)
    fitted=gd.fit_curb_bottom(curb,support)
    assert np.array_equal(fitted.faces,curb.faces)
    assert fitted.report['curb_support_fit']['measured_trim_m']<.01


@pytest.mark.parametrize('field,value',[('gap_m',0),('gap_m',.005),('gap_m',float('nan')),('gap_m',float('inf')),('gap_m',True),('max_trim_m',0),('max_trim_m',.0100001),('max_trim_m',float('nan'))])
def test_invalid_fit_limits_fail_without_mutating_inputs(field,value):
    curb,support=fixture()
    before=curb.verts.copy();sf=support.faces.copy()
    with pytest.raises(ValueError):gd.fit_curb_bottom(curb,support,**{field:value})
    assert np.array_equal(curb.verts,before) and np.array_equal(support.faces,sf)


@pytest.mark.parametrize('kind',['empty','partial','nan','inf','unknown_slot','bad_index','incomplete_support'])
def test_invalid_fit_geometry_fails_without_mutating_curb(kind):
    curb,support=fixture();before=curb.verts.copy()
    if kind=='empty':support=gd._empty()
    if kind=='partial':support.level=np.empty(0,int)
    if kind in ('nan','inf'):support.verts[0,0]=float(kind)
    if kind=='unknown_slot':curb.slot[0]='UnmappedCurb'
    if kind=='bad_index':support.faces[0,0]=len(support.verts)
    if kind=='incomplete_support':support.verts[:,0]+=20
    with pytest.raises(ValueError):gd.fit_curb_bottom(curb,support)
    assert np.array_equal(curb.verts,before)


def test_reaching_trim_limit_is_refused_not_accepted():
    curb,support=fixture()
    actual=gd.fit_curb_bottom(curb,support).report['curb_support_fit']['measured_trim_m']
    before=curb.verts.copy()
    with pytest.raises(ValueError,match='reaches'):
        gd.fit_curb_bottom(curb,support,max_trim_m=actual)
    assert np.array_equal(curb.verts,before)


def test_empty_support_slot_is_named_and_refused():
    curb,support=fixture();support.slot[0]=''
    with pytest.raises(ValueError,match='slot'):
        gd.fit_curb_bottom(curb,support)
