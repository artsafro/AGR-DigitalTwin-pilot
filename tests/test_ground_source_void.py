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
