"""new-case: remove raster notches outward before making any native cut cells."""
import pytest
from shapely.geometry import Polygon,box
from tools.materials import course_grid_native as native


def test_outward_notch_cleanup_keeps_every_original_support_point():
    support=Polygon([[0,0],[.02,0],[.02,.1],[.018,.1],[.018,.104],[.02,.104],[.02,.2],[0,.2]])
    face=box(0,0,1,1)
    result=native.simplify_support_outward(support,face,maximum_m=.0021)
    assert result.is_valid
    assert support.difference(result).area<=1e-14
    assert result.difference(support.buffer(.0021)).area<=1e-14
    assert len(result.exterior.coords)<len(support.exterior.coords)
    assert result.difference(face).is_empty


def test_large_reentrant_source_feature_cannot_be_filled_by_cleanup():
    support=Polygon([[0,0],[1,0],[1,.3],[.5,.3],[.5,.7],[1,.7],[1,1],[0,1]])
    assert native.simplify_support_outward(support,box(0,0,1,1),maximum_m=.0021).equals(support)


@pytest.mark.parametrize('value',[0,-1,.0022,float('nan'),float('inf'),True])
def test_outward_cleanup_rejects_unsupported_envelope(value):
    with pytest.raises(ValueError,match='maximum_m'):
        native.simplify_support_outward(box(0,0,.02,.3),box(0,0,1,1),maximum_m=value)
