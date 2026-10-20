"""Ground cleanup regressions combine source coverage, relief, slot and UV preservation."""
import numpy as np
import pytest
from dt_ai.geometry import ground_cake as gc
from twinqa.geometry.topology import count_defects


def test_cleanup_welds_near_vertices_dissolves_slivers_and_connects_single_faces():
    v=np.array([[0,0,100],[4,0,100],[4,4,100],[0,4,100],[.001,0,100],[10,0,100],[14,0,100],[10,4,100]],float)
    f=np.array([[0,1,2],[4,2,3],[0,4,3],[5,6,7]])
    uv=v[f][:,:,:2]/4
    m=gc.Mesh(v,f,['Tile']*4,np.zeros(4,int),uv,4)
    clean=gc.clean_topology(m)
    defects=count_defects(clean.verts,clean.faces)
    assert all(defects[k]==0 for k in ('duplicate_vertices','duplicate_edges','duplicate_polygons','isolated_polygons','zero_length_edges'))
    assert set(clean.slot)=={'Tile'} and (clean.level==0).all()
    assert np.allclose(clean.uv,clean.verts[clean.faces][:,:,:2]/4)
    before=sum(p.area for p in gc.face_polys(m)); after=sum(p.area for p in gc.face_polys(clean))
    assert abs(before-after)<.005
    assert np.allclose(clean.verts[:,2],100)


def test_cleanup_welded_slivers_keep_surface_and_uv_winding_up():
    v=np.array([[0,0,100],[4,0,100],[2,-.0005,100],[2,.001,100],[0,-4,100]],float)
    f=np.array([[0,1,3],[1,4,2]])
    # Second face is a control; source generator emits CCW.
    for i in range(len(f)):
        p=v[f[i]]
        if np.cross(p[1]-p[0],p[2]-p[0])[2]<0:f[i]=f[i,::-1]
    m=gc.Mesh(v,f,['T']*2,np.zeros(2,int),v[f][:,:,:2]/4,4)
    c=gc.clean_topology(m);p=c.verts[c.faces]
    assert (np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])[:,2]>0).all()
    uv=c.uv;e1=uv[:,1]-uv[:,0];e2=uv[:,2]-uv[:,0]
    assert (e1[:,0]*e2[:,1]-e1[:,1]*e2[:,0]>0).all()


def test_cleanup_collinear_face_retriangulates_long_edge_without_internal_crack():
    from shapely.geometry import Polygon
    v=np.array([[0,0,100],[4,0,100],[2,0,100],[0,-4,100],[0,4,100]],float)
    f=np.array([[0,1,2],[1,0,3],[0,2,4],[2,1,4]])
    m=gc.Mesh(v,f,['T']*4,np.zeros(4,int),v[f][:,:,:2]/4,4)
    clean=gc.clean_topology(m)
    boundary=Polygon([(0,-4),(4,0),(0,4)])
    plan=gc.plan_layers(boundary,{'t':[boundary]},'t',{'t':'T'})
    assert gc.measure_open_edges(clean,plan)['open_edges_off_outline']==0


def test_side_projection_recovers_vertical_surface_with_zero_topdown_uv():
    v=np.array([[0,0,0],[0,1,0],[0,1,1]],float);f=np.array([[0,1,2]])
    uv=v[f][:,:,:2]/4
    new,ids=gc.side_project_uv(v,f,uv,4096,520,4,True)
    assert ids.tolist()==[0]
    assert gc.texel_density(v,f,new,4096)[0]==pytest.approx(1024)
    assert gc.uv_tile_report(new)['straddling']==0


def test_cleanup_rejects_invalid_geometry():
    m=gc.Mesh(np.array([[0,0,float('nan')],[1,0,0],[0,1,0]]),np.array([[0,1,2]]),['T'],np.array([0]),np.zeros((1,3,2)),4)
    with pytest.raises(ValueError,match='finite'):
        gc.clean_topology(m)
