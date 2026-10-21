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
