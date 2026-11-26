"""new-case: eliminate near-source-boundary cutter wedges without shrinking relief.

Owner of the course_grid_native boundary-support tests; #1960 merged five files into it.
"""
import copy
import math
import numpy as np
import pytest
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
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


# --- merged from tests/test_course_grid_backtracks.py (#1960)
# new-case: zero-area backtracking excursions are not native surface corners.

def test_native_collinear_excursion_is_reported_not_triangulated_as_surface():
    points=[[113.17613908900599,-4.4947340428829206],
        [112.15949021057821,-4.4947339984230865],
        [112.16412190342311,-4.494733998625638],
        [112.1643546315201,-4.618919085795084],
        [113.17613908900599,-4.618919606879355]]
    result=native.remove_native_backtracks(points)
    assert result['indices']==[0,2,3,4]
    assert result['removed']==[1]
    assert result['signed_area_change_m2']<=1e-12


def test_real_notch_and_forward_conforming_node_are_retained():
    points=[[0,0],[1,0],[2,0],[2,1],[1,1],[1,.99],[.9,.99],[.9,1],[0,1]]
    result=native.remove_native_backtracks(points)
    assert result['indices']==list(range(len(points)))
    assert result['removed']==[]


@pytest.mark.parametrize('points', [[],[[0,0]],[[0,0],[1,0],[float('nan'),1]],
    [[0,0],[1,0],[float('inf'),1]]])
def test_backtrack_cleanup_refuses_invalid_input(points):
    with pytest.raises(ValueError):native.remove_native_backtracks(points)


# --- merged from tests/test_course_grid_finalize.py (#1960)
# new-case: explicit fixed-node finalization plans, never implicit welds.

def row():
    return dict(object='synthetic',face=2,source_face=7,material_id=4,
      local_xyz=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],
      vertices=[0,1,2,3],uv=[[0,0],[1,0],[1,1],[0,1]])


def test_explicit_boundary_plan_preserves_corner_associations_and_input():
    r=row();before=copy.deepcopy(r)
    result=native.plan_boundary_finalization([r],[dict(object='synthetic',source_face=7,material_id=4)])
    assert len(result)==1 and len(result[0]['triangles'])==2
    assert result[0]['local_xyz']==r['local_xyz']
    assert result[0]['uv']==r['uv']
    assert r==before


@pytest.mark.parametrize('targets', [[],[dict(object='synthetic',source_face=8,material_id=4)],
 [dict(object='synthetic',source_face=7,material_id=1)],
 [dict(object='synthetic',source_face=7,material_id=4)]*2,
 [dict(object='synthetic',source_face=True,material_id=4)]])
def test_boundary_plan_refuses_missing_duplicate_or_stale_targets(targets):
    with pytest.raises(ValueError):native.plan_boundary_finalization([row()],targets)


# --- merged from tests/test_course_grid_footprint_union.py (#1960)
# new-case: explicit sub-nanometre measurement precision, not wider gates.

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


# --- merged from tests/test_course_grid_outward_support.py (#1960)
# new-case: remove raster notches outward before making any native cut cells.

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


# --- merged from tests/test_course_grid_raster_coverage.py (#1960)
# new-case: conservative source pixel-cell coverage survives rotated subpixel traces.

def test_thin_source_cell_is_not_lost_between_target_pixel_centres():
    mask=np.zeros((5,5),dtype=bool);mask[2,2]=True
    centres=[[1.99,2.5],[3.01,2.5],[.5,.5]]
    result=native.raster_cell_intersections(mask,centres,[[1.1,0],[0,1.1]])
    assert result.tolist()==[True,True,False]


def test_touching_only_does_not_paint_a_neighbour():
    mask=np.zeros((3,3),dtype=bool);mask[1,1]=True
    assert native.raster_cell_intersections(mask,[[.5,1.5]],[[1,0],[0,1]]).tolist()==[False]


def test_generated_rotated_cells_match_independent_polygon_overlap():
    rng=np.random.default_rng(1326);mask=rng.random((9,9))<.12
    dark=[box(x,y,x+1,y+1) for y,x in zip(*np.where(mask))]
    for _ in range(20):
        angle=rng.uniform(-np.pi,np.pi);c,s=np.cos(angle),np.sin(angle)
        axes=np.array([[c,s],[-s,c]])*rng.uniform(.5,1.5)
        centres=rng.uniform(.5,8.5,(30,2))
        actual=native.raster_cell_intersections(mask,centres.tolist(),axes.tolist())
        expected=[]
        for point in centres:
            poly=Polygon([point+a*axes[0]/2+b*axes[1]/2 for a,b in [(1,1),(-1,1),(-1,-1),(1,-1)]])
            expected.append(any(poly.intersection(cell).area>1e-12 for cell in dark))
        assert actual.tolist()==expected


@pytest.mark.parametrize('centres,axes', [([],[[1,0],[0,1]]),([[float('nan'),1]],[[1,0],[0,1]]),
    ([[1,1]],[[1,0],[1,0]]),([[1,1]],[[float('inf'),0],[0,1]]),([[1,1]],[[50,0],[0,50]])])
def test_raster_coverage_refuses_invalid_or_unbounded_sampling(centres,axes):
    with pytest.raises(ValueError):
        native.raster_cell_intersections(np.zeros((3,3),bool),centres,axes)
