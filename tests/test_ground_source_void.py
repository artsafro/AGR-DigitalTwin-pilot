"""Source-contour remainder recovery, synthetic controls (#371)."""
import numpy as np
import pytest
from shapely.geometry import box
from dt_ai.geometry import ground_cake as gc
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report, XviewTolerance


def test_small_source_void_keeps_plane_uv_and_one_metre_perimeter():
    v=np.array([(0,0,0),(4,0,.04),(4,4,.12),(0,4,.08)],float)
    f=np.array([(0,1,2),(0,2,3)])
    m=gc.Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f,:2]/4,4.)
    r=gc.cut_base_void(m,box(1,.5,2,1))
    surf=r.level==0
    assert sum(p.area for p in gc.face_polys(r,surf))==pytest.approx(15.5)
    np.testing.assert_allclose(r.verts[r.faces[surf],2],.01*r.verts[r.faces[surf],0]+.02*r.verts[r.faces[surf],1],atol=1e-12)
    np.testing.assert_allclose(r.uv[surf],r.verts[r.faces[surf],:2]/4,atol=1e-12)
    walls=r.verts[r.faces[r.level==-1]]
    assert len(walls)==8
    assert set(r.slot)=={'TileLight','Skirt'}
    assert r.report['base_void']['trimmed_source_faces']==[0]
    assert sorted(set(r.report['base_void']['source_faces']))==[-1,0,1]
    x=part_report('source-void',PolyMesh(r.verts,tuple(map(tuple,r.faces))),XviewTolerance())
    assert not x.vertex_pairs and not x.face_pairs
    assert walls[:,:,2].min()==pytest.approx(-.98)
    for key in ('verts','faces','uv'):
        np.testing.assert_array_equal(getattr(m,key),{'verts':v,'faces':f,'uv':v[f,:2]/4}[key])


@pytest.mark.parametrize('angle,shift',[(0,0),(31,10000),(90,-15000),(179,20000)])
def test_generated_source_void_crosses_old_edge_conformingly(angle,shift):
    from shapely import affinity
    a=np.radians(angle);rot=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    xy=np.array([(0,0),(4,0),(4,4),(0,4)],float) @ rot.T + shift
    v=np.column_stack((xy,.01*xy[:,0]+.02*xy[:,1]))
    f=np.array([(0,1,2),(0,2,3)])
    m=gc.Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f,:2]/4,4.)
    void=affinity.translate(affinity.rotate(box(1,1,2,2),angle,origin=(0,0)),shift,shift)
    r=gc.cut_base_void(m,void)
    assert sum(p.area for p in gc.face_polys(r,r.level==0))==pytest.approx(15.)
    x=part_report('generated-void',PolyMesh(r.verts,tuple(map(tuple,r.faces))),XviewTolerance())
    assert not x.vertex_pairs and not x.face_pairs
    assert sorted(set(r.report['base_void']['source_faces']))==[-1,0,1]


@pytest.mark.parametrize('kind',['empty','outside','touch','hole','none','partial_uv','nan_uv','raised','depth_nan','depth_inf','depth_low'])
def test_source_void_refuses_invalid_or_unsupported_input(kind):
    from shapely.geometry import Polygon
    v=np.array([(0,0,0),(4,0,0),(4,4,0),(0,4,0)],float)
    f=np.array([(0,1,2),(0,2,3)])
    m=gc.Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f,:2]/4,4.)
    void=box(1,1,2,2);depth=1.
    if kind=='empty':void=Polygon()
    elif kind=='outside':void=box(8,8,9,9)
    elif kind=='touch':void=box(0,0,1,1)
    elif kind=='hole':void=Polygon([(1,1),(3,1),(3,3),(1,3)], [[(1.5,1.5),(2,1.5),(2,2),(1.5,2)]])
    elif kind=='none':void=None
    elif kind=='partial_uv':m.uv=m.uv[:1]
    elif kind=='nan_uv':m.uv[0,0,0]=np.nan
    elif kind=='raised':m.level[0]=1
    elif kind=='depth_nan':depth=np.nan
    elif kind=='depth_inf':depth=np.inf
    else:depth=np.nextafter(1.,0.)
    with pytest.raises(ValueError):gc.cut_base_void(m,void,depth=depth)
