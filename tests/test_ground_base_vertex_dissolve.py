"""Dissolve an internal construction sample, never split/displace a fan (#371)."""
import numpy as np
import pytest
from dt_ai.geometry import ground_cake as gc


def mesh():
    v=np.array([(0,0,0),(4,0,.04),(4,4,.12),(0,4,.08),(2,2,.0601)],float)
    f=np.array([(0,1,4),(1,2,4),(2,3,4),(3,0,4)])
    return gc.Mesh(v,f,['TileLight']*4,np.zeros(4,int),v[f,:2]/4,4.)


def test_dissolve_keeps_boundary_positions_uv_slot_and_drop_disposition():
    m=mesh();r=gc.dissolve_base_vertex(m,4)
    np.testing.assert_array_equal(r.verts,m.verts[:4])
    assert len(r.faces)==2 and r.slot==['TileLight']*2
    np.testing.assert_allclose(r.uv,r.verts[r.faces,:2]/4)
    assert r.report['base_vertex_dissolve']['removed_vertex']==4
    assert r.report['base_vertex_dissolve']['source_faces']==[0,1,2,3]
    assert r.report['base_vertex_dissolve']['reason']=='interior construction sample; caller must remeasure relief'
    assert len(m.verts)==5 and len(m.faces)==4


@pytest.mark.parametrize('kind',['boundary','mixed_slot','raised','uv_seam','bool','out_of_range','winding'])
def test_dissolve_refuses_unsupported_owner_or_boundary(kind):
    m=mesh();index=4
    if kind=='boundary':index=0
    elif kind=='mixed_slot':m.slot[0]='LawnRolled'
    elif kind=='raised':m.level[0]=1
    elif kind=='uv_seam':m.uv[0,0,0]+=.1
    elif kind=='bool':index=True
    elif kind=='winding':
        m.faces[0]=m.faces[0,::-1];m.uv[0]=m.uv[0,::-1]
    else:index=5
    with pytest.raises(ValueError):gc.dissolve_base_vertex(m,index)
