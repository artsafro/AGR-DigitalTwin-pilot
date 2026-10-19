"""Synthetic Ground detail tracer bullets (#295)."""
import numpy as np
import pytest
from shapely.geometry import box
from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry import ground_details as gd


def sampler():
    return gc.ReliefSampler(gc.build_tin([(x,y,100+.01*x) for x in (-10,20) for y in (-10,20)]))


def element(role, coords, ref='C'):
    return {'role':role,'ref':ref,'handle':ref,'kind':'LWPOLYLINE','container':None,'geometry':{'type':'LineString','coordinates':coords},'problem':None}


def test_detail_uv_diagonal_four_m_cell_is_contained_in_band():
    v=np.array([[0,0,0],[4,4,.1],[4,0,0]],float); f=np.array([[0,1,2]])
    uv=gd.triangle_uv(v,f)
    assert gc.uv_tile_report(uv)['straddling']==0
    assert 520<=gc.texel_density(v,f,uv,4096)[0]<=1706


def test_curbs_follow_tin_with_approved_cross_sections_closed_and_in_boundary():
    e=element('curb_garden',[(1,2,0),(9,2,0)])
    m,report=gd.build_details([e],box(0,0,10,10),sampler())
    assert report[0]['status']=='modeled' and report[0]['width_m']==.08 and report[0]['height_m']==.05
    assert np.ptp(m.verts[:,1])==pytest.approx(.08,abs=.002)
    z,hit=sampler().sample(m.verts[:,:2]); delta=m.verts[:,2]-z
    assert delta.max()-delta.min()==pytest.approx(.05,abs=1e-6) and hit.all()
    edges={}
    for f in m.faces:
        for a,b in zip(f,np.roll(f,1)):
            k=tuple(sorted((a,b)));edges[k]=edges.get(k,0)+1
    assert all(c==2 for c in edges.values())
    assert all(box(0,0,10,10).covers(p) for p in gc.face_polys(m))


def test_unknown_cross_section_and_unsupported_are_explicit_dispositions():
    e=element('curb_wood',[(1,2,0),(9,2,0)])
    m,r=gd.build_details([e],box(0,0,10,10),sampler())
    assert len(m.faces)==0 and r[0]['status']=='skipped' and 'height' in r[0]['reason']


@pytest.mark.parametrize('closure_gap',[0.,.0019])
def test_stair_treads_from_plan_and_vp_are_horizontal_with_risers(closure_gap):
    es=[{'role':'stairs','ref':'S','handle':'S','kind':'INSERT','container':None,'label':'stairs','geometry':None}]
    es += [dict(element('stairs',c,f'S>{i}'),container='S') for i,c in enumerate([
        [(1,1,0),(3,1,0),(3,4,0),(1,4,0),(1,1,0)], [(1,2,0),(3,2,0)],[(1,3,0),(3,3,0)]])]
    es[1]['geometry']['coordinates'][-1]=(1+closure_gap,1,0)
    sp=gc.ReliefSampler(gc.build_tin([(x,y,100+.2*y) for x in (-10,20) for y in (-10,20)]))
    m,r=gd.build_details(es,box(0,0,10,10),sp)
    assert r[0]['status']=='modeled' and r[0]['treads']==3
    pts=m.verts[m.faces]; n=np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0]); tops=n[:,2]>1e-9
    assert tops.any() and np.all(np.ptp(pts[tops,:,2],axis=1)<1e-8)
    assert np.any(abs(n[:,2])<1e-12)
