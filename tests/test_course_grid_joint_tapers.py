"""new-case: raster joint endpoints keep measured taper, not rectangular extensions."""
import pytest
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from tools.materials.course_grid_native import vectorize_joint_footprint


def test_tapered_source_joint_is_not_extended_to_full_width_at_its_tip():
    # Analytic 10-mm stripe with a 30-mm tapered end, independent of PNG oracle.
    expected=Polygon([(0,0),(.01,0),(.01,.97),(.002,1),(0,1)])
    fitted=vectorize_joint_footprint(expected,face=box(-.01,-.01,.02,1.01))
    assert expected.difference(fitted.buffer(.005)).area==0
    assert fitted.difference(expected.buffer(.005)).area==0
    assert fitted.area==pytest.approx(expected.area)
    assert not fitted.covers(Polygon([(.009,.998),(.01,.998),(.01,1)]))
