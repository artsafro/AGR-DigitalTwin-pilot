"""new-case: raster joint endpoints keep measured taper, not rectangular extensions."""
import pytest
from shapely.geometry import Polygon,box
from shapely.ops import unary_union
from tools.materials.course_grid_native import vectorize_joint_footprint


def test_cut_node_can_anchor_to_one_unchanged_original_corner():
    from tools.materials.course_grid_native import coalesce_cut_nodes
    vertices=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[.001,0.,0.]]
    out=coalesce_cut_nodes(vertices,[[3,1,2]],[7],original_vertex_count=3,allow_original_anchor=True,
                          groups=[dict(vertices=[0,3],position=[0.,0.,0.])])
    assert out['vertices'][:3]==vertices[:3]
    assert out['faces']==[[0,1,2]] and out['lineage']==[7]
    with pytest.raises(ValueError,match='original'):
        coalesce_cut_nodes(vertices,[[3,1,2]],[7],original_vertex_count=3,allow_original_anchor=True,
                           groups=[dict(vertices=[0,3],position=[.001,0.,0.])])


def test_cut_node_motion_does_not_become_an_unapproved_half_pixel_brick_phase():
    from tools.materials.course_grid_native import restore_repeat_translation
    # 32-px border, fixed rho512.1; previous first UV was inherited before a
    # one-mm cut-node motion. Recover the known full-repeat field, not that drift.
    shift=restore_repeat_translation([32/4096,32/4096],[.001,0.],
                                    repeat_m=4.,texel_px_m=512.1,tile_px=4096,border_px=32)
    assert shift==pytest.approx([32/512.1,32/512.1])


def test_raster_joint_tip_near_source_corner_uses_the_corner_not_a_micro_edge():
    face=Polygon([(0.,0.),(.2,0.),(.2,1.),(0.,1.)])
    expected=Polygon([(0.,0.),(.01,0.),(.01,.97),(.001,.999),(0.,.999)])
    fitted=vectorize_joint_footprint(expected,face=face)
    assert (0.,1.) in fitted.exterior.coords
    assert expected.difference(fitted.buffer(.005)).area==0
    assert fitted.difference(expected.buffer(.005)).area==0


def test_tapered_source_joint_is_not_extended_to_full_width_at_its_tip():
    # Analytic 10-mm stripe with a 30-mm tapered end, independent of PNG oracle.
    expected=Polygon([(0,0),(.01,0),(.01,.97),(.002,1),(0,1)])
    fitted=vectorize_joint_footprint(expected,face=box(-.01,-.01,.02,1.01))
    assert expected.difference(fitted.buffer(.005)).area==0
    assert fitted.difference(expected.buffer(.005)).area==0
    assert fitted.area==pytest.approx(expected.area)
    assert not fitted.covers(Polygon([(.009,.998),(.01,.998),(.01,1)]))
