"""Per-polygon detail charts; surface charts and source identity stay unchanged."""
import numpy as np
import pytest
from dt_ai.geometry import ground_quads as gq


def sample(width=6.):
    v=np.array([(0,0,0),(4,0,0),(4,4,0),(0,4,0),
                (0,0,1),(width,0,1),(width,0,3),(0,0,3)],float)
    return gq.QuadMesh(v,((0,1,2,3),(4,5,6,7)),['TileLight','Stairs'],np.array([0,-2]),
                       (np.array([(0,0),(1,0),(1,1),(0,1)],float),np.zeros((4,2))),((0,1),(2,3)),4.)


@pytest.mark.parametrize('profile,px,expected',[('npm',2048,30),('vpm',4096,4096/6)])
def test_detail_charts_are_metric_and_tile_contained_without_changing_surface(profile,px,expected):
    q=sample();r=gq.detail_polygon_uv(q,profile)
    np.testing.assert_array_equal(r.verts,q.verts)
    assert r.faces==q.faces and r.slot==q.slot and r.source_faces==q.source_faces
    np.testing.assert_array_equal(r.uv[0],q.uv[0])
    for tri in ((0,1,2),(0,2,3),(1,2,3),(1,3,0)):
        p=r.verts[np.array(r.faces[1])[list(tri)]];uv=r.uv[1][list(tri)]
        ua=np.linalg.det((uv[1:]-uv[0]))/2;ga=np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))/2
        assert ua>0
        assert px*np.sqrt(ua/ga)==pytest.approx(expected)
    if profile=='vpm':assert np.min(r.uv[1])>=0 and np.max(r.uv[1])<=1
    assert not np.any(q.uv[1])


@pytest.mark.parametrize('bad',['profile','empty','nan','partial_uv','oversize','at_limit'])
def test_detail_charts_fail_closed(bad):
    q=sample();profile='vpm'
    if bad=='profile':profile='VMP'
    elif bad=='empty':q.faces=()
    elif bad=='nan':q.verts[0,0]=np.nan
    elif bad=='partial_uv':q.uv=q.uv[:1]
    elif bad=='oversize':q=sample(9.)
    else:q=sample(8.)
    with pytest.raises(ValueError):gq.detail_polygon_uv(q,profile)
