"""new-case: saved-mesh fixed-frame chart projection regressions.

Owner of the course_grid_native tests; #1960 merged twelve single-topic files into it.
"""
import numpy as np
import pytest
from shapely.geometry import Polygon, box
from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import face_pairs, tolerance_for
from tools.materials import course_grid_native as native
from tools.materials.course_grid_native import project_saved_points, rigid_triangle_uv, encode_triangle_uv
from tools.materials.course_grid_native import (
    coalesce_cut_nodes, conform_source_mesh, interpolate_source_chart, joint_cross_section,
    plan_boundary_finalization, split_native_loop, triangulate_conforming_polygon, vectorize_joint_footprint)


def test_saved_points_use_source_plane_frame_not_old_precast_offsets():
    ref=[[0.,0.,0.],[2.,0.,0.],[2.,0.,1.],[0.,0.,1.]]
    chart=[[10.,-4.],[12.,-4.],[12.,-3.],[10.,-3.]]
    points=[[.010002,.000004,.5],[1.997999,-.000004,.75]]
    out=project_saved_points(points,ref,chart)
    assert out[0]==pytest.approx([10.010002,-3.5])
    assert out[1]==pytest.approx([11.997999,-3.25])


def test_rigid_triangle_preserves_long_edge_heading_and_frozen_density():
    import numpy as np
    xyz=[[0,0,0],[1,0,0],[.99,.00001,.000002]]
    old=[[.3,.4],[.425,.4],[.42375,.40000125]]
    uv=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    e=np.array(xyz)[1:]-xyz[0];q=(np.array(uv)[1:]-uv[0])*4096
    a=e[0]/np.linalg.norm(e[0]);n=np.cross(e[0],e[1]);n/=np.linalg.norm(n);b=np.cross(n,a)
    singular=np.linalg.svd(np.linalg.solve(np.c_[e@a,e@b],q),compute_uv=False)
    assert singular==pytest.approx([512.1,512.1],abs=1e-5)
    assert uv[0]==old[0] and uv[1][1]==uv[0][1]


def test_float32_encoding_keeps_legal_band_with_subpixel_quantization_only():
    import numpy as np
    xyz=[[104.9970932006836,56.44607162475586,.15000119805336],
         [104.25457763671875,55.141239166259766,.14409610629081726],
         [104.25953674316406,55.149932861328125,.14409610629081726]]
    old=[[.6429628133773804,.4401338994503021],[.45526301860809326,.43939563632011414],
         [.4565143287181854,.43939563632011414]]
    ideal=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    out=encode_triangle_uv(xyz,ideal,tile_px=4096)
    assert min(out['singular_px_m'])>=512
    assert max(out['singular_px_m'])<=1706
    assert max(out['singular_px_m'])/min(out['singular_px_m'])<=1.02
    assert out['max_encoding_error_px']<.01
    assert np.asarray(out['uv'],dtype=np.float32).astype(float).tolist()==out['uv']


def test_unrepresentable_skinny_triangle_refuses_instead_of_lowering_gate():
    xyz=[[0,0,0],[1,0,0],[.99,.00001,.000002]]
    old=[[.3,.4],[.425,.4],[.42375,.40000125]]
    ideal=rigid_triangle_uv(xyz,old,texel_px_m=512.1,tile_px=4096)
    with pytest.raises(ValueError,match='encoding exceeds'):
        encode_triangle_uv(xyz,ideal,tile_px=4096)


@pytest.mark.parametrize('value',[float('nan'),float('inf')])
def test_saved_projection_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        project_saved_points([[value,0,0]],[[0,0,0],[1,0,0],[0,0,1]],[[0,0],[1,0],[0,1]])


# --- merged from tests/test_course_grid_coalesce.py (#1960)
# new-case: explicitly bounded cut-node coalescing, never a global weld.

def test_coalescing_reports_collapsed_cells_and_preserves_source_accounting():
    vertices=[[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.],[.5,0.,0.],[.5005,0.,0.]]
    faces=[[0,4,3],[4,5,3],[5,2,3],[5,1,2]]
    result=coalesce_cut_nodes(vertices,faces,[10]*4,original_vertex_count=4,groups=[{'vertices':[4,5],'position':[.50025,0.,0.]}])
    assert result['vertices'][:4]==vertices[:4]
    assert result['faces']==[[0,4,3],[4,2,3],[4,1,2]]
    assert result['lineage']==[10,10,10]
    assert result['dropped']==[{'face':1,'source':10,'reason':'explicit cut-node coalescence; collapsed connectivity cell'}]
    assert result['max_displacement_m']==pytest.approx(.00025)


@pytest.mark.parametrize('groups',[
    [{'vertices':[0,3],'position':[0,0,0]}],
    [{'vertices':[3,4],'position':[.01,0,0]}],
    [{'vertices':[3,4],'position':[float('nan'),0,0]}],
    [{'vertices':[3,4],'position':[0,0,0]},{'vertices':[4,5],'position':[0,0,0]}],
])
def test_original_vertices_excess_motion_nonfinite_and_duplicate_groups_refuse(groups):
    with pytest.raises(ValueError):
        coalesce_cut_nodes([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[.0001,0,0],[.0002,0,0],[.0003,0,0]],[[0,1,2],[3,4,2]],[10,10],original_vertex_count=3,groups=groups)


# --- merged from tests/test_course_grid_conform.py (#1960)
# new-case: source-proven cut mesh endpoint identity and conforming boundaries.

def test_conforming_polygon_retains_all_boundary_nodes_without_singular_native_fans():
    from tools.materials.course_grid_native import triangulate_conforming_polygon
    points=[[0.,0.],[1.,0.],[1.,.25],[1.,.5],[1.,1.],[0.,1.]]
    triangles=triangulate_conforming_polygon(points)
    assert len(triangles)==4
    assert {i for t in triangles for i in t}==set(range(6))
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys=[Polygon([points[i] for i in t]) for t in triangles]
    assert min(p.area for p in polys)>=.125
    assert unary_union(polys).area==pytest.approx(1.)
    assert sum(p.area for p in polys)==pytest.approx(1.)


def test_source_endpoint_identity_and_t_junction_are_repaired_without_blind_weld():
    source=[[0.,0.,0.],[1.,0.,0.],[1.,1.,0.],[0.,1.,0.],[2.,0.,0.],[2.,1.,0.]]
    # Left face was split halfway along the shared edge; right still spans it.
    vertices=source+[[1.000004,0.,0.],[1.,.5,0.],[0.,.5,0.]]
    faces=[[0,6,7,8],[8,7,2,3],[1,4,5,2]]
    uv=[[[0,0],[1,0],[1,.5],[0,.5]],[[0,.5],[1,.5],[1,1],[0,1]],[[0,0],[1,0],[1,1],[0,1]]]
    out=conform_source_mesh(vertices,faces,[10,10,11],uv,source,{10:[0,1,2,3],11:[1,4,5,2]})
    assert out['vertices'][:len(source)]==source
    assert out['faces']==[[0,1,7,8],[8,7,2,3],[1,4,5,2,7]]
    assert out['uv'][2][-1]==pytest.approx([0,.5])
    assert out['remap'][6]==1
    assert out['insertions']==[{'face':2,'edge':[2,1],'vertex':7}]


def test_triangulation_avoids_skinny_diagonal_when_same_area_has_a_compact_ear():
    from tools.materials.course_grid_native import triangulate_conforming_polygon
    import math
    points=[[0.,0.],[1.,0.],[1.01,0.],[1.,.01],[0.,.01]]
    triangles=triangulate_conforming_polygon(points)
    def quality(t):
        from shapely.geometry import Polygon
        return Polygon([points[i] for i in t]).area/max(math.dist(points[a],points[b])**2 for a in t for b in t)
    assert min(map(quality,triangles))>.004


def test_explicit_minor_scope_reports_sub_native_collapsed_cell_without_losing_source():
    source=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]]
    vertices=source+[[.000004,0.,0.]]
    faces=[[0,1,2],[0,3,2]];coords=[[[0,0],[1,0],[0,1]],[[0,0],[.000004,0],[0,1]]]
    out=conform_source_mesh(vertices,faces,[10,10],coords,source,{10:[0,1,2]},collapsed_sources=[10])
    assert out['faces']==[[0,1,2]] and out['input_face']==[0]
    assert out['dropped_faces'][0]['face']==1
    assert out['dropped_faces'][0]['source']==10
    with pytest.raises(ValueError,match='collapse'):
        conform_source_mesh(vertices,faces,[10,10],coords,source,{10:[0,1,2]})


def test_nearby_parallel_edges_do_not_insert_the_same_node_twice():
    source=[[0.,0.,0.],[1.,0.,0.],[1.,.00001,0.],[0.,.00001,0.]]
    vertices=source+[[.5,0.,0.]];faces=[[0,1,2,3],[0,4,3]]
    uv=[[[0,0],[1,0],[1,.00001],[0,.00001]],[[0,0],[.5,0],[0,.00001]]]
    out=conform_source_mesh(vertices,faces,[10,10],uv,source,{10:[0,1,2,3]})
    assert out['faces'][0]==[0,4,1,2,3]
    assert out['insertions']==[{'face':0,'edge':[0,1],'vertex':4}]


def test_close_disconnected_surface_is_not_welded():
    source=[[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,.00001],[1.,0.,.00001],[0.,1.,.00001]]
    faces=[[0,1,2],[3,4,5]];uv=[[[0,0],[1,0],[0,1]]]*2
    out=conform_source_mesh(source,faces,[10,11],uv,source,{10:faces[0],11:faces[1]})
    assert out['faces']==faces and out['insertions']==[]


@pytest.mark.parametrize('bad',[[],[[float('nan'),0,0]],[[float('inf'),0,0]]])
def test_invalid_conform_input_fails_closed(bad):
    with pytest.raises(ValueError):
        conform_source_mesh(bad,[[0,1,2]],[0],[[[0,0],[1,0],[0,1]]],bad,{0:[0,1,2]})


# --- merged from tests/test_course_grid_finalize_identifiers.py (#1960)
# new-case: hostile ambiguous identifiers may not alias a real native source.

def test_boolean_source_id_cannot_alias_source_one():
    row=dict(object='synthetic',face=0,source_face=1,material_id=4,
      local_xyz=[[0,0,0],[1,0,0],[0,1,0]],vertices=[0,1,2],uv=[[0,0],[1,0],[0,1]])
    with pytest.raises(ValueError):
        plan_boundary_finalization([row],[dict(object='synthetic',source_face=True,material_id=4)])


# --- merged from tests/test_course_grid_joint_interval_noding.py (#1960)
# new-case: connected 1D cross sections of corner-touching 2D cells.

def test_cross_section_merges_touching_intervals_not_shapely_component_count():
    domain=[[-1,0],[1,0],[1,.02],[-1,.02]]
    expected=[[[-.1,0],[.1,0],[.1,.01],[-.1,.01]]]
    # Along x=0 these meet at y=.005, although their 2D interiors do not.
    observed=[[[0,0],[.1,0],[.1,.005],[0,.005]],
              [[-.1,.005],[0,.005],[0,.01],[-.1,.01]]]
    report=joint_cross_section(domain,expected,observed,[0,0],[0,1])
    assert report['observed_intervals_m']==[[0,.01]]
    assert report['passed']
    assert report['false_intervals']==report['missing_intervals']==0


def test_cross_section_retains_real_separated_intervals():
    domain=[[-1,0],[1,0],[1,.02],[-1,.02]]
    expected=[[[-.1,0],[.1,0],[.1,.01],[-.1,.01]]]
    observed=[[[0,0],[.1,0],[.1,.004],[0,.004]],
              [[-.1,.006],[0,.006],[0,.01],[-.1,.01]]]
    report=joint_cross_section(domain,expected,observed,[0,0],[0,1])
    assert len(report['observed_intervals_m'])==2
    assert not report['passed']


# --- merged from tests/test_course_grid_joint_tapers.py (#1960)
# new-case: raster joint endpoints keep measured taper, not rectangular extensions.

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


def test_generated_taper_and_phase_recovery_probes():
    import random
    from tools.materials.course_grid_native import restore_repeat_translation
    rng=random.Random(1326)
    for _ in range(100):
        height=rng.uniform(.1,2.)
        taper=rng.uniform(.005,.04)
        expected=Polygon([(0,0),(.01,0),(.01,height-taper),(.002,height),(0,height)])
        face=box(-.01,-.01,.02,height+.01)
        fitted=vectorize_joint_footprint(expected,face=face)
        assert expected.difference(fitted.buffer(.005)).area<=1e-12
        assert fitted.difference(expected.buffer(.005)).area<=1e-12
        dx,dy=rng.uniform(-.001,.001),rng.uniform(-.001,.001)
        shift=restore_repeat_translation([32/4096,32/4096],[dx,dy],
                                        repeat_m=4.,texel_px_m=512.1,tile_px=4096,border_px=32)
        assert shift==pytest.approx([32/512.1,32/512.1])


@pytest.mark.parametrize('point',[[float('nan'),0.],[float('inf'),0.],[],[True,0.]])
def test_phase_nonfinite_partial_and_boolean_refuse(point):
    from tools.materials.course_grid_native import restore_repeat_translation
    with pytest.raises(ValueError):
        restore_repeat_translation(point,[0.,0.],repeat_m=4.,texel_px_m=512.1,tile_px=4096,border_px=32)


def test_unsupported_broad_joint_and_unrecognized_phase_refuse():
    from tools.materials.course_grid_native import restore_repeat_translation
    with pytest.raises(ValueError,match='broad'):
        vectorize_joint_footprint(box(0,0,.2,.2),face=box(0,0,1,1))
    with pytest.raises(ValueError,match='outside'):
        vectorize_joint_footprint(box(2,2,2.01,3),face=box(0,0,1,1))
    with pytest.raises(ValueError,match='phase class'):
        restore_repeat_translation([.1,.1],[0.,0.],repeat_m=4.,texel_px_m=512.1,tile_px=4096,border_px=32)


def test_tapered_source_joint_is_not_extended_to_full_width_at_its_tip():
    # Analytic 10-mm stripe with a 30-mm tapered end, independent of PNG oracle.
    expected=Polygon([(0,0),(.01,0),(.01,.97),(.002,1),(0,1)])
    fitted=vectorize_joint_footprint(expected,face=box(-.01,-.01,.02,1.01))
    assert expected.difference(fitted.buffer(.005)).area==0
    assert fitted.difference(expected.buffer(.005)).area==0
    assert fitted.area==pytest.approx(expected.area)
    assert not fitted.covers(Polygon([(.009,.998),(.01,.998),(.01,1)]))


# --- merged from tests/test_course_grid_joints.py (#1960)
# new-case: clipped/junction-aware joint measurements never require an outside centre.

def test_source_pixel_footprint_keeps_longitudinal_ends_and_empty_is_explicit():
    from tools.materials.course_grid_native import source_joint_footprint
    import numpy as np
    image=np.full((16,16,3),255,dtype=np.uint8);image[:,4]=[40,32,32]
    uv=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    shape=source_joint_footprint(image,uv,uv)
    assert shape.bounds==pytest.approx((.25,0,.3125,1))
    assert shape.area==pytest.approx(.0625)
    blank=np.full((16,16,3),255,dtype=np.uint8)
    assert source_joint_footprint(blank,uv,uv).is_empty


def test_axis_vector_fit_removes_pixel_stairs_without_changing_nominal_width():
    from tools.materials.course_grid_native import rectify_axis_joint_footprint
    from shapely.geometry import box
    from shapely.ops import unary_union
    footprint=unary_union([box(0,0,.01,1),box(.01,.1,.012,.104),box(-.002,.6,0,.604)])
    fitted=rectify_axis_joint_footprint(footprint)
    assert fitted.area==pytest.approx(.01)
    assert fitted.bounds[2]-fitted.bounds[0]==pytest.approx(.01)
    assert len(fitted.exterior.coords)==5
    assert footprint.difference(fitted.buffer(.005)).area==0
    assert fitted.difference(footprint.buffer(.005)).area==0


def test_broad_joint_reference_refuses_instead_of_guessing_lines():
    from tools.materials.course_grid_native import rectify_axis_joint_footprint
    from shapely.geometry import box
    with pytest.raises(ValueError,match='unsupported'):
        rectify_axis_joint_footprint(box(0,0,.2,.2))


def test_clipped_thin_face_has_a_measurable_joint_not_a_missing_5mm_centre():
    face=[[0.,0.],[.003,0.],[.003,1.],[0.,1.]]
    zone=[[0.,0.],[.01,0.],[.01,1.],[0.,1.]]
    out=joint_cross_section(face,[zone],[face],[0.,.5],[1.,0.])
    assert out['passed'] and out['classification']=='clipped'
    assert out['expected_width_mm']==pytest.approx(3.)
    assert out['max_centre_error_mm']==pytest.approx(0.)
    assert out['nominal_centre_outside_face']


def test_crossing_joint_union_is_not_mislabeled_as_a_15mm_centre_error():
    face=[[0.,0.],[.04,0.],[.04,1.],[0.,1.]]
    out=joint_cross_section(face,[face],[face],[0.,.5],[1.,0.])
    assert out['passed'] and out['classification']=='junction'
    assert out['expected_width_mm']==pytest.approx(40.)
    assert out['max_centre_error_mm']==0


def test_missing_and_false_extra_joint_fail_with_complete_intervals():
    face=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]];zone=[[0.,0.],[.01,0.],[.01,1.],[0.,1.]]
    far=[[.1,0.],[.11,0.],[.11,1.],[.1,1.]]
    out=joint_cross_section(face,[zone],[far],[0.,.5],[1.,0.])
    assert not out['passed'] and out['missing_intervals']==1 and out['false_intervals']==1


@pytest.mark.parametrize('point',[[float('nan'),0],[float('inf'),0],[]])
def test_nonfinite_partial_probe_is_error(point):
    face=[[0.,0.],[1.,0.],[1.,1.],[0.,1.]]
    with pytest.raises(ValueError):joint_cross_section(face,[face],[face],point,[1,0])


# --- merged from tests/test_course_grid_local.py (#1960)
# new-case: source-local barycentric storage before native world readback.

def test_source_local_interpolation_preserves_corners_and_warped_fan():
    chart=[[0,0],[2,0],[2,1],[0,1]]
    xyz=[[1,2,3],[3,2,3],[3,2.001,4],[1,2,4]]
    got=interpolate_source_chart(chart+[[1,.25],[1,.75]],chart,xyz)
    assert got[:4]==xyz
    assert got[4]==pytest.approx([2,2.00025,3.25])
    assert got[5]==pytest.approx([2,2.0005,3.75])


@pytest.mark.parametrize('point', [[float('nan'),0],[float('inf'),0],[3,1]])
def test_bad_or_outside_source_local_point_refuses(point):
    with pytest.raises(ValueError):
        interpolate_source_chart([point],[[0,0],[1,0],[0,1]],[[0,0,0],[1,0,0],[0,0,1]])


# --- merged from tests/test_course_grid_loops.py (#1960)
# new-case: retain both lobes of an exactly pinched native boundary.

def test_exact_pinched_boundary_keeps_both_lobes_and_all_edges():
    ids=[0,1,2,3,4,2,5,6]
    result=split_native_loop(ids)
    assert len(result['loops'])==2 and not result['collapsed']
    expected={(ids[i],ids[(i+1)%len(ids)]) for i in range(len(ids))}
    actual={(ids[loop[i]],ids[loop[(i+1)%len(loop)]]) for loop in result['loops'] for i in range(len(loop))}
    assert actual==expected
    assert all(len({ids[i] for i in loop})==len(loop) for loop in result['loops'])


def test_exact_zero_length_edge_reported_not_silently_removed():
    result=split_native_loop([0,1,1,2,3])
    assert len(result['loops'])==1 and result['collapsed']


# --- merged from tests/test_course_grid_native_anchor.py (#1960)
# new-case: protected cyclic anchors without adding any diagonal.

def test_native_cyclic_anchor_preserves_exact_protected_polygon():
    indices=native.canonical_native_boundary(POINTS)
    assert len(indices)==6
    assert sorted(indices)==list(range(6))
    assert all(indices[(k+1)%6]==(indices[k]+1)%6 for k in range(6))
    mesh=PolyMesh(np.array(POINTS+[OTHER]),(tuple(indices),(6,2,1)))
    assert face_pairs(mesh,tolerance_for('VPM'))==[]
    # No source/protected vertex, UV association, boundary edge or face is added.
    assert {(indices[i],indices[(i+1)%6]) for i in range(6)}=={(i,(i+1)%6) for i in range(6)}


# --- merged from tests/test_course_grid_native_constraint.py (#1960)
# new-case: constrained triangulation must consider native UV representability.

def test_native_constraint_selects_another_complete_diagonal_not_partial_output():
    points = [[0,0],[2,0],[2,1],[0,1]]
    triangles = triangulate_conforming_polygon(points, triangle_allowed=lambda t: t != [0,1,2])
    assert {tuple(t) for t in triangles} == {(0,1,3),(1,2,3)}
    assert {i for t in triangles for i in t} == {0,1,2,3}


def test_native_constraint_refuses_when_no_complete_diagonal_is_encodable():
    with pytest.raises(ValueError, match='unrepresentable'):
        triangulate_conforming_polygon([[0,0],[2,0],[2,1],[0,1]], triangle_allowed=lambda t: False)


@pytest.mark.parametrize('value', [None, 0, 1, 'yes', float('nan')])
def test_native_constraint_requires_literal_bool_result(value):
    with pytest.raises(ValueError, match='triangle_allowed'):
        triangulate_conforming_polygon([[0,0],[2,0],[0,1]], triangle_allowed=lambda t: value)


# --- merged from tests/test_course_grid_protected_tessellation.py (#1960)
# new-case: real native-boundary regression retains every protected node.

POINTS = [[1.3104900121688843,-1.2631808519363403,0.0],
 [1.2987421751022339,-1.2631808519363403,0.0],
 [-0.27053582668304443,-1.2631810903549194,0.0],
 [-0.28951549530029297,-1.2631810903549194,0.0],
 [-0.28951549530029297,-1.2631810903549194,-0.10999999940395355],
 [1.3104900121688843,-1.2631808519363403,-0.10999999940395355]]


OTHER = [1.2987425327301025,-1.2131811380386353,0.0]


@pytest.mark.parametrize('reverse', [False, True])
def test_native_protected_boundary_avoids_singular_newell_fan(reverse):
    points = list(reversed(POINTS)) if reverse else POINTS
    vertices = np.array(points + [OTHER])
    other = (6, points.index(POINTS[2]), points.index(POINTS[1]))
    before = face_pairs(PolyMesh(vertices,(tuple(range(6)),other)),tolerance_for('VPM'))
    assert [p[2] for p in before] == ([] if reverse else ['area'])
    triangles = native.triangulate_native_boundary(points)
    assert len(triangles) == 4
    assert set(i for t in triangles for i in t) == set(range(6))
    assert face_pairs(PolyMesh(vertices,tuple(map(tuple,triangles))+(other,)),tolerance_for('VPM')) == []
    areas = [np.cross(vertices[t[1]]-vertices[t[0]], vertices[t[2]]-vertices[t[0]]) for t in triangles]
    boundary_normal = sum((np.cross(a,b) for a,b in zip(vertices[:6],np.roll(vertices[:6],-1,axis=0))),np.zeros(3))
    assert all(np.dot(a,boundary_normal) > 0 for a in areas)


@pytest.mark.parametrize('points', [[], [[0,0,0]]*3, [[0,0,0],[1,0,0],[2,0,0]],
 [[0,0,0],[1,0,0],[1,float('nan'),0]]])
def test_native_boundary_refuses_missing_or_degenerate_surface(points):
    with pytest.raises(ValueError):
        native.triangulate_native_boundary(points)


# --- merged from tests/test_course_grid_udim_encoding.py (#1960)
# new-case: quantify UV encoding AFTER the absolute UDIM offset is applied.

def singular(xyz, uv):
    e = np.asarray(xyz)[1:] - xyz[0]
    a = e[0] / np.linalg.norm(e[0])
    n = np.cross(*e); n /= np.linalg.norm(n)
    return np.linalg.svd(np.linalg.solve(np.c_[e @ a, e @ np.cross(n, a)],
        (np.asarray(uv)[1:] - uv[0]) * 4096), compute_uv=False)


@pytest.mark.parametrize('tile_u', [0, 1, 9])
def test_absolute_tile_encoding_is_native_and_measured_at_final_coordinates(tile_u):
    xyz = [[0., 0., 0.], [1., 0., 0.], [0., .01, 0.]]
    ideal = [[tile_u + .3, .4], [tile_u + .3 + 512.1/4096, .4],
             [tile_u + .3, .4 + .01*512.1/4096]]
    out = encode_triangle_uv(xyz, ideal, tile_px=4096, tile_u=tile_u)
    assert np.asarray(out['uv'], dtype=np.float32).astype(float).tolist() == out['uv']
    measured = singular(xyz, out['uv'])
    assert measured == pytest.approx(out['singular_px_m'], abs=1e-8)
    assert 512 <= min(measured) <= max(measured) <= 1706
    assert max(measured)/min(measured) <= 1.02
    assert np.max(np.linalg.norm(np.asarray(out['uv'])-ideal, axis=1))*4096 <= .01
    assert all(tile_u <= p[0] <= tile_u+1 and 0 <= p[1] <= 1 for p in out['uv'])


@pytest.mark.parametrize('tile_u', [True, -1, 10, 1., float('nan'), float('inf')])
def test_absolute_tile_encoding_rejects_unsupported_tile(tile_u):
    with pytest.raises(ValueError, match='tile_u'):
        encode_triangle_uv([[0,0,0],[1,0,0],[0,1,0]],
            [[.2,.2],[.4,.2],[.2,.4]], tile_px=4096, tile_u=tile_u)


def test_absolute_tile_encoding_cannot_move_into_another_tile():
    with pytest.raises(ValueError, match='encoding exceeds'):
        encode_triangle_uv([[0,0,0],[1,0,0],[0,1,0]],
            [[.2,.2],[.325,.2],[.2,.325]], tile_px=4096, tile_u=1)
