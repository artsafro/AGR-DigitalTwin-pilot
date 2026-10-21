"""Synthetic small-jog perimeter witnesses; original terrain must stay bounded."""
import numpy as np
import pytest
from shapely.geometry import Polygon,MultiPolygon
from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report,XviewTolerance


@pytest.mark.parametrize('offset',[0.,-7600.])
def test_boundary_straightening_removes_a_three_mm_jog_before_skirt(offset):
    poly=Polygon([(offset,offset),(offset+2,offset),(offset+2,offset+1),(offset+2.003,offset+1),(offset+2.003,offset+2),(offset,offset+2)])
    plan=gc.Plan(MultiPolygon([poly]),[],[gc.Layer('TileGrey','tile',0,MultiPolygon([poly]))],.006)
    sampler=gc.ReliefSampler(gc.build_tin([(x+offset,y+offset,100+.1*x) for x in (-2,6) for y in (-2,6)]))
    flat=gc.build_flat(plan,cell=4,chord=0,snap=.001)
    projected,misses=gc.project_z(flat,sampler,.006)
    assert not misses
    def report(mesh):
        mesh=gc.add_skirt(mesh)
        for i,p in enumerate(mesh.verts[mesh.faces]):
            n=np.cross(p[1]-p[0],p[2]-p[0]); axes=[a for a in range(3) if a!=abs(n).argmax()]
            mesh.uv[i]=p[:,axes]/4
        q=pair_triangles(mesh)
        return part_report('jog',PolyMesh(q.verts,q.faces),XviewTolerance())
    assert report(projected).face_pairs, 'fixture must reproduce skirt contact across jog'
    fixed=gc.straighten_base_boundary(projected,sampler,chord_m=.006)
    assert fixed.report['boundary_straightening']['max_displacement_m']<.01
    r=report(fixed)
    assert not r.vertex_pairs and not r.face_pairs
