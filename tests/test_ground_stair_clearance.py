"""Synthetic opt-in curb/stair clearance tests; source geometry is immutable."""
import copy
import numpy as np
import pytest
from shapely.geometry import box,LineString,mapping
from shapely.affinity import rotate,translate
from dt_ai.geometry import ground_cake as gc,ground_details as gd
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report,XviewTolerance


@pytest.mark.parametrize('angle,offset',[(0,0),(45,0),(0,-7600),(45,-7600)])
def test_opt_in_stair_clearance_is_closed_and_xview_clean(angle,offset):
    def geom(cs):
        return mapping(translate(rotate(LineString(cs),angle,origin=(0,0)),offset,offset))
    es=[dict(role='stairs',ref='S',handle='S',kind='INSERT',container=None,label='stairs',geometry=None)]
    for i,cs in enumerate([[(1,1),(3,1),(3,4),(1,4),(1,1)],[(1,2),(3,2)],[(1,3),(3,3)]]):
        es.append(dict(role='stairs',ref=f'S>{i}',handle=str(i),kind='LWPOLYLINE',container='S',geometry=geom(cs)))
    es.append(dict(role='curb_garden',ref='C',handle='C',kind='LWPOLYLINE',container=None,geometry=geom([(0,2.5),(5,2.5)])))
    original=copy.deepcopy(es)
    sampler=gc.ReliefSampler(gc.build_tin([(x+offset,y+offset,100+.2*y) for x in (-10,20) for y in (-10,20)]))
    boundary=box(offset-10,offset-10,offset+20,offset+20)
    m,rows,_=gd.build_details(es,boundary,sampler,stair_clearance_m=.012)
    assert es==original
    assert rows[-1]['stair_clearance_m']==.012
    assert rows[-1]['stair_trim_m2']>0
    for i,p in enumerate(m.verts[m.faces]):
        n=np.cross(p[1]-p[0],p[2]-p[0]);axes=[a for a in range(3) if a!=abs(n).argmax()]
        m.uv[i]=p[:,axes]/4
    q=pair_triangles(m)
    r=part_report('stairs_clearance',PolyMesh(q.verts,q.faces),XviewTolerance())
    assert not r.vertex_pairs and not r.face_pairs


@pytest.mark.parametrize('value',[-.001,.020001,float('nan'),float('inf'),True,None])
def test_bad_clearance_fails_before_source_processing(value):
    with pytest.raises(ValueError,match='stair_clearance_m'):
        gd.build_details([],box(0,0,1,1),None,stair_clearance_m=value)
