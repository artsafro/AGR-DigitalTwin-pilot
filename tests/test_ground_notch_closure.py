"""Approved local contour closure; numerical limits are not exceptions."""
import numpy as np
import pytest
from dt_ai.geometry import ground_cake as gc
from dt_ai.geometry.ground_quads import pair_triangles
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import part_report, XviewTolerance

XY=np.array([[-7691.007,-15248.688],[-7691.2305,-15248.001],[-7691.016,-15248.688]])

def fixture():
    # Both sides of the actual approved notch, with upward winding.
    v=np.array([[*XY[0],152.017682],[*XY[1],151.996786],[*XY[2],152.017123],[-7690.5,-15248.688,152.05],[-7691.5,-15248.688,151.98]])
    f=np.array([[0,3,1],[1,4,2]])
    return gc.Mesh(v,f,['TileLight']*2,np.zeros(2,int),v[f][:,:,:2]/4,4.)

def test_approved_notch_adds_exactly_one_base_triangle_before_skirt():
    m=fixture();before=m.verts.copy()
    fixed=gc.close_base_notch(m,XY,approval_reference='Artem #371 2026-10-21 16:58')
    assert np.array_equal(m.verts,before)
    assert len(fixed.faces)==3 and np.array_equal(fixed.faces[:2],m.faces)
    assert np.array_equal(fixed.verts,m.verts)
    assert fixed.slot==['TileLight']*3 and list(fixed.level)==[0]*3
    tri=fixed.verts[fixed.faces[-1]]
    assert np.cross(tri[1]-tri[0],tri[2]-tri[0])[2]>0
    assert fixed.report['approved_notch']['area_m2']==pytest.approx(.0030915)
    assert fixed.report['approved_notch']['approval_reference']=='Artem #371 2026-10-21 16:58'
    curtain=gc.add_skirt(fixed)
    for i,t in enumerate(curtain.verts[curtain.faces]):
        axis=abs(np.cross(t[1]-t[0],t[2]-t[0])).argmax();axes=[j for j in range(3) if j!=axis]
        curtain.uv[i]=t[:,axes]/4
    q=pair_triangles(curtain)
    r=part_report('closed-notch',PolyMesh(q.verts,q.faces),XviewTolerance())
    assert not r.vertex_pairs and not r.face_pairs

@pytest.mark.parametrize('kind',['empty','partial','nan','inf','unknown','duplicate','no_approval','mixed_slots','already_closed'])
def test_notch_refuses_unbound_or_unsupported_closure_without_mutation(kind):
    m=fixture();xy=XY.copy();approval='Artem #371'
    if kind=='empty':xy=np.empty((0,2))
    if kind=='partial':xy=xy[:2]
    if kind in ('nan','inf'):xy[0,0]=float(kind)
    if kind=='unknown':xy[0,0]+=.001
    if kind=='duplicate':xy[0]=xy[1]
    if kind=='no_approval':approval=' '
    if kind=='mixed_slots':m.slot[1]='Lawn'
    if kind=='already_closed':m=gc.close_base_notch(m,xy,approval_reference=approval)
    before=m.verts.copy();faces=m.faces.copy()
    with pytest.raises(ValueError):gc.close_base_notch(m,xy,approval_reference=approval)
    assert np.array_equal(m.verts,before) and np.array_equal(m.faces,faces)
