"""new-case: synthetic authorized planar joint-strip partition regressions."""
import copy
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import partition_joint_zones, layout_joint_partition


def face():
    return dict(object='synthetic',face=0,chart_m=[[0,0],[2,0],[2,1],[0,1]],
                xyz=[[0,0,0],[2,0,0],[2,0,1],[0,0,1]],material_id=1)


def test_empty_explicit_zones_preserves_unjointed_face():
    out=partition_joint_zones(face(),[])
    assert len(out['pieces'])==1
    assert not out['pieces'][0]['joint']
    assert out['new_segments']==[]


def test_interior_closed_joint_zone_preserves_hole_without_lost_surface():
    row=face()
    out=partition_joint_zones(row,[[[.5,.2],[.51,.2],[.51,.8],[.5,.8]]])
    polygons=[Polygon(p['chart_m']) for p in out['pieces']]
    from shapely.ops import unary_union
    assert sum(p.area for p in polygons)==pytest.approx(2)
    assert unary_union(polygons).area==pytest.approx(2)
    assert out['joint_area_m2']==pytest.approx(.006)
    assert all(len(p.interiors)==0 for p in polygons)
    assert len(polygons)<=4  # Do not serialize a full triangulation of a flat panel.


def test_nonplanar_quad_retains_original_fan_surface_not_best_fit_plane():
    row=face(); row['xyz'][2][1]=.001
    out=partition_joint_zones(row,[[[0,0],[.01,0],[.01,1],[0,1]]])
    assert sum(Polygon(p['chart_m']).area for p in out['pieces'])==pytest.approx(2)
    for p in out['pieces']:
        for (u,v),(_,y,_) in zip(p['chart_m'],p['xyz']):
            assert y==pytest.approx(.001*min(u/2,v),abs=1e-12)


def test_subpicometre_overlay_sliver_is_canonicalized_not_serialized():
    out=partition_joint_zones(face(),[[[1e-14,0],[.01,0],[.01,1],[1e-14,1]]])
    assert len(out['pieces'])==2
    assert out['overlay_grid_m']==1e-12
    assert all(Polygon(p['chart_m']).area>1e-12 for p in out['pieces'])


def test_joint_only_constant_field_has_full_gap_from_periodic_brick():
    r=partition_joint_zones(face(),[[[0,0],[.01,0],[.01,1],[0,1]]])
    out=layout_joint_partition([r],repeat_m=4,texel_px_m=512,tile_px=4096,border_px=32,gap_px=32)
    assert len(out['faces'])==len(r['pieces'])
    assert out['unplaced']==[] and not out['passed']
    b=[Polygon(p['uv']) for p in out['faces'] if not p['joint']][0]
    j=[Polygon(p['uv']) for p in out['faces'] if p['joint']][0]
    assert b.distance(j)*4096>=32
    for f in out['faces']:
        for p,q in zip(f['chart_m'],f['uv']):
            assert q==pytest.approx([(p[k]+f['translation_m'][k])*512/4096 for k in (0,1)])


def test_exact_ten_mm_inset_keeps_area_surface_winding_and_lineage():
    row=face(); before=copy.deepcopy(row)
    zones=[[[0,0],[.01,0],[.01,1],[0,1]]]
    out=partition_joint_zones(row,zones)
    assert row==before
    assert len(out['pieces'])==2
    assert sum(Polygon(p['chart_m']).area for p in out['pieces'])==pytest.approx(2)
    assert sum(Polygon(p['chart_m']).area for p in out['pieces'] if p['joint'])==pytest.approx(.01)
    for p in out['pieces']:
        assert p['source']==['synthetic',0]
        assert Polygon(p['chart_m']).exterior.is_ccw
        for (u,v),(x,y,z) in zip(p['chart_m'],p['xyz']):
            assert [x,y,z]==pytest.approx([u,0,v])
    assert len(out['new_segments'])==1
    assert sorted(out['new_segments'][0])==[[.01,0],[.01,1]]
