"""Synthetic construction witnesses for #371; not delivery acceptance."""
import numpy as np
import pytest
from shapely.geometry import box
from shapely.affinity import rotate, translate
from dt_ai.geometry import ground_cake as gc, ground_details as gd
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report, XviewTolerance


@pytest.mark.parametrize('angle,offset', [(0,0), (27,0), (0,-7600), (27,-7600)])
@pytest.mark.parametrize('heights', [[100.2,100.4,100.6], [100.6,100.4,100.2], [100.4,100.2,100.6], [100.2,100.2,100.6]])
def test_stair_side_walls_share_every_riser_endpoint(angle, offset, heights):
    def place(poly):
        return translate(rotate(poly, angle, origin=(0,0)), offset, offset)
    sampler = gc.ReliefSampler(gc.build_tin([(x+offset,y+offset,100+.2*y) for x in (-10,20) for y in (-10,20)]))
    m = gd._stairs_solid(place(box(0,0,2,3)), [place(box(0,i,2,i+1)) for i in range(3)], heights, sampler)
    edges = {}
    for f in m.faces:
        for a,b in zip(f,np.roll(f,-1)):
            k=tuple(sorted((int(a),int(b))))
            edges[k]=edges.get(k,0)+1
    assert all(n==2 for n in edges.values()), 'T-junction on stair wall/riser edge'
    for i,tri in enumerate(m.verts[m.faces]):
        normal=np.cross(tri[1]-tri[0],tri[2]-tri[0])
        axes=[a for a in range(3) if a!=abs(normal).argmax()]
        m.uv[i]=tri[:,axes]/4
    q=pair_triangles(m)
    report=part_report('stairs',PolyMesh(q.verts,q.faces),XviewTolerance())
    assert not report.vertex_pairs
    assert not report.face_pairs
