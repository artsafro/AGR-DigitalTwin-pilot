"""new-case: synthetic authorized planar joint-strip partition regressions."""
import copy
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import partition_joint_zones


def face():
    return dict(object='synthetic',face=0,chart_m=[[0,0],[2,0],[2,1],[0,1]],
                xyz=[[0,0,0],[2,0,0],[2,0,1],[0,0,1]],material_id=1)


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
