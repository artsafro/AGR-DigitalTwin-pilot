"""new-case: eliminate near-source-boundary cutter wedges without shrinking relief."""
import math
import pytest
from shapely.geometry import Polygon, box
from tools.materials import course_grid_native as native


def test_boundary_support_extension_fills_tapered_tip_not_the_source_surface():
    face = box(0, 0, 1.6, .37)
    support = Polygon([[0,0],[.015,.000024],[.019,.362], [.017,.369],[0,.37]])
    result = native.extend_support_to_boundary(support, face, maximum_m=.0021)
    assert result.is_valid
    assert support.difference(result).area <= 1e-14
    assert result.difference(face).is_empty
    assert result.covers(Polygon([[0,0],[.015,0],[.015,.000024]]))
    assert result.covers(Polygon([[0,.37],[.017,.37],[.017,.369]]))
    assert result.difference(support.buffer(.0021)).area <= 1e-14
    assert native.extend_support_to_boundary(result, face, maximum_m=.0021).equals(result)


def test_slanted_source_boundary_emits_only_surface_not_roundoff_contact_lines():
    face = Polygon([[62.02808325545378,81.89753222484573],
        [62.027949549637334,79.71736675333496],[62.05795274966022,79.71736248837597],
        [62.058084581327314,81.89753178467706]])
    support = Polygon([[62.05795274966,79.717362488376],[62.058084581327,81.897531784677],
        [62.047491353032,81.897531940097],[62.047360292817,79.729910862811],
        [62.027950319023,79.729912116139],[62.027949549637,79.717366753335]])
    result = native.extend_support_to_boundary(support, face, maximum_m=.0021)
    assert result.geom_type in ('Polygon', 'MultiPolygon')
    assert support.difference(result).area <= 1e-12


def test_boundary_extension_does_not_move_interior_support_or_cross_empty_face():
    face = box(0,0,1,1); support = box(.2,.2,.3,.3)
    assert native.extend_support_to_boundary(support,face,maximum_m=.0021).equals(support)
    assert native.extend_support_to_boundary(Polygon(),face,maximum_m=.0021).is_empty


@pytest.mark.parametrize('maximum', [0, -.1, .0021001, True, math.nan, math.inf])
def test_boundary_extension_refuses_invalid_envelope(maximum):
    with pytest.raises(ValueError,match='maximum_m'):
        native.extend_support_to_boundary(box(0,0,.01,1),box(0,0,1,1),maximum_m=maximum)


@pytest.mark.parametrize('face,support', [
    (Polygon(),box(0,0,1,1)),
    (box(0,0,1,1),box(-.01,0,.1,.1)),
    (box(0,0,1,1),Polygon([[0,0],[1,1],[1,0],[0,1]])),
])
def test_boundary_extension_refuses_invalid_or_outside_surface(face,support):
    with pytest.raises(ValueError):
        native.extend_support_to_boundary(support,face,maximum_m=.0021)
