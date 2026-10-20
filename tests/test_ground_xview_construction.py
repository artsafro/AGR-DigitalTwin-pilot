"""Synthetic construction witnesses for #371; not delivery acceptance."""
import numpy as np
from shapely.geometry import box
from dt_ai.geometry import ground_cake as gc, ground_details as gd
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report, XviewTolerance


def test_stair_side_walls_share_every_riser_endpoint():
    sampler = gc.ReliefSampler(gc.build_tin([(x,y,100+.2*y) for x in (-10,20) for y in (-10,20)]))
    m = gd._stairs_solid(box(0,0,2,3), [box(0,i,2,i+1) for i in range(3)], [100.2,100.4,100.6], sampler)
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
