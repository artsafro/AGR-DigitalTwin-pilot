"""Synthetic bounded perimeter-weld witnesses, plus the unresolved real acute wedge."""
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
    fixed=gc.weld_base_boundary(projected)
    assert fixed.report['boundary_weld']['max_displacement_m']<.0021
    r=report(fixed)
    assert not r.vertex_pairs and not r.face_pairs


def test_collinear_boundary_chain_is_not_a_weld_candidate():
    # Three distinct samples 3 mm apart on an already straight boundary are not
    # a seam. Connected-distance clustering alone would move an endpoint 3 mm.
    ring=np.array([[0,0,100],[1,0,100],[1.003,0,100],[1.006,0,100],[2,0,100],[2,2,100],[0,2,100]],float)
    v=np.vstack([ring,[1,1,100]])
    f=np.array([[i,(i+1)%len(ring),len(ring)] for i in range(len(ring))])
    m=gc.Mesh(v,f,['TileGrey']*len(f),np.zeros(len(f),int),np.zeros((len(f),3,2)),4.)
    fixed=gc.weld_base_boundary(m)
    assert fixed.report['boundary_weld']['groups']==[]
    assert fixed.report['boundary_weld']['max_displacement_m']==0


def test_nondefective_short_corner_is_not_a_weld_candidate():
    # Three near corners form a 4.24 mm diameter chain, but no near-parallel
    # curtains overlap. Their proximity alone is not permission to change them.
    ring=np.array([[0,-1,100],[1,-1,100],[2.003,0,100],[2,0,100],[2,.003,100],[1.9,2,100],[0,2,100]],float)
    v=np.vstack([ring,[1,.5,100]])
    f=np.array([[i,(i+1)%len(ring),len(ring)] for i in range(len(ring))])
    m=gc.Mesh(v,f,['TileGrey']*len(f),np.zeros(len(f),int),np.zeros((len(f),3,2)),4.)
    fixed=gc.weld_base_boundary(m)
    assert fixed.report['boundary_weld']['groups']==[]
    assert fixed.report['boundary_weld']['max_displacement_m']==0


def simple_base():
    v=np.array([[0,0,100],[2,0,100],[2,2,100],[0,2,100]],float)
    return gc.Mesh(v,np.array([[0,1,2],[0,2,3]]),['TileGrey']*2,np.zeros(2,int),np.zeros((2,3,2)),4.)


@pytest.mark.parametrize('field,value',[('weld_m',0),('weld_m',.0042),('weld_m',float('nan')),('weld_m',float('inf')),('weld_m',True),('displacement_limit_m',0),('displacement_limit_m',.0022)])
def test_boundary_weld_rejects_invalid_limits_without_writes(field,value):
    m=simple_base();before=m.verts.copy()
    with pytest.raises(ValueError):gc.weld_base_boundary(m,**{field:value})
    assert np.array_equal(m.verts,before)


@pytest.mark.parametrize('kind',['empty','partial','nan','inf','detail_level','no_base','bad_index'])
def test_boundary_weld_refuses_unsupported_meshes(kind):
    m=simple_base()
    if kind=='empty':m=gc.Mesh(np.empty((0,3)),np.empty((0,3),int),[],np.empty(0,int),np.empty((0,3,2)),4.)
    if kind=='partial':m.level=np.empty(0,int)
    if kind in ('nan','inf'):m.verts[0,0]=float(kind)
    if kind=='detail_level':m.level[:]=-2
    if kind=='no_base':m.level[:]=1
    if kind=='bad_index':m.faces[0,0]=4
    with pytest.raises(ValueError):gc.weld_base_boundary(m)


def test_real_acute_notch_is_still_a_failure_not_a_hidden_pass():
    v=np.array([[-7691.007,-15248.688,152.017682],[-7691.2305,-15248.001,151.996786],[-7691.2305,-15248.001,150.996786],[-7691.007,-15248.688,151.017682],[-7691.016,-15248.688,152.017123],[-7691.016,-15248.688,151.017123]])
    r=part_report('remaining_real_notch',PolyMesh(v,((0,1,2,3),(1,4,5,2))),XviewTolerance())
    assert not r.vertex_pairs
    assert len(r.face_pairs)==1 and r.face_pairs[0][2]=='area'
    assert r.face_pairs[0][3]==0
    assert not r.xview_faces, 'native-contact parity and stricter area gate are distinct'


def test_empty_boundary_slot_is_named_and_refused():
    m=simple_base();m.slot[0]=''
    with pytest.raises(ValueError,match='slot'):
        gc.weld_base_boundary(m)
