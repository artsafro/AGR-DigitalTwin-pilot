"""Joint masks use a declared sub-nanometre measurement precision, not wider gates."""
import pytest
from shapely.geometry import box, LineString
from shapely.ops import unary_union
from tools.materials import course_grid_native as native


def test_measurement_union_closes_only_arithmetic_chart_seams():
    pieces=[box(0,0,.005,.01),box(.005+1e-14,0,.01,.01)]
    ray=LineString([(.005+5e-15,-.1),(.005+5e-15,.1)])
    assert unary_union(pieces).intersection(ray).is_empty
    joined=native.union_joint_footprints(pieces,precision_m=1e-10)
    assert joined.intersection(ray).length==pytest.approx(.01)
    assert joined.area==pytest.approx(.0001)


def test_measurement_union_does_not_bridge_real_pixel_or_geometry_gaps():
    joined=native.union_joint_footprints([box(0,0,.004,.01),box(.006,0,.01,.01)],precision_m=1e-10)
    assert joined.geom_type=='MultiPolygon'
    assert joined.intersection(LineString([(.005,-.1),(.005,.1)])).is_empty


@pytest.mark.parametrize('precision', [0,1e-5,float('nan'),True])
def test_measurement_union_refuses_physical_scale_snapping(precision):
    with pytest.raises(ValueError):native.union_joint_footprints([box(0,0,.01,.01)],precision_m=precision)
