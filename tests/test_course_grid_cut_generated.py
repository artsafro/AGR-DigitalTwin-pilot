"""new-case: generated exact-edge strip footprints on rotated source charts."""
import math
import numpy as np
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import partition_joint_zones


def test_generated_exact_edge_endpoints_no_micro_holes_or_surface_motion():
    for angle in np.linspace(0,2*math.pi,100,endpoint=False):
        rotation=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
        base=np.array([[0.,0.],[2.,0.],[2.,1.],[0.,1.]])
        points=base@rotation.T+np.array([80.,-6.])
        xyz=np.c_[base[:,0],np.zeros(4),base[:,1]]
        row=dict(object='synthetic',face=0,material_id=1,chart_m=points.tolist(),xyz=xyz.tolist())
        a,b=points[:2]; n=np.array([-math.sin(angle),math.cos(angle)])
        strip=np.array([a,b,b+n*.01,a+n*.01])
        result=partition_joint_zones(row,[strip.tolist()])
        assert sum(Polygon(p['chart_m']).area for p in result['pieces'])==pytest.approx(2,abs=1e-11)
        assert result['joint_area_m2']==pytest.approx(.02,abs=1e-11)
        assert all(not Polygon(p['chart_m']).interiors for p in result['pieces'])
