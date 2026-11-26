"""new-case: synthetic authorized planar joint-strip partition regressions.

Owner of the course_grid_cut tests; #1960 merged three files into it.
"""
import copy
import math
import numpy as np
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import partition_joint_zones, layout_joint_partition, edge_joint_zone, native_piece_cells
from tools.materials.course_grid_cut import assemble_support_pages


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


def test_edge_strip_reaches_slanted_end_without_micrometre_corner_spur():
    row=face();row['chart_m']=[[0,0],[2,0],[2,1],[0,1.000001]]
    row['xyz']=[[u,0,v] for u,v in row['chart_m']]
    zone=edge_joint_zone(row['chart_m'],[3,0],width_m=.01)
    out=partition_joint_zones(row,[zone])
    assert len(out['pieces'])==2
    assert all(len(p['chart_m'])==4 for p in out['pieces'])
    assert sum(Polygon(p['chart_m']).area for p in out['pieces'])==pytest.approx(2.000001)


def test_zero_area_tangent_zone_does_not_poison_polygon_boundary():
    zones=[[[0,0],[.01,0],[.01,1],[0,1]],[[2,0],[3,0],[3,1],[2,1]]]
    out=partition_joint_zones(face(),zones)
    assert len(out['pieces'])==2
    assert out['joint_area_m2']==pytest.approx(.01)


def test_overlay_polygon_plus_zero_area_line_has_a_measurable_boundary():
    xy=[[95.02184447629318,-4.399998330030216],[95.0218482493222,-4.4999963275340145],
        [95.25767282274347,-4.872886785864831],[95.25767282274347,-4.7487012314546675]]
    zones=[[[95.02186856485758,-5.038426550218211],[95.0218241607578,-3.8615681073460193],
            [95.03182416075069,-3.8615677300355618],[95.03186856485047,-5.038426172907753]],
           [[95.02242719668901,-4.857896561847707],[95.02242719510893,-4.508122291414429],
            [95.03243365955277,-4.507490720958548],[95.0324336611357,-4.8578965705457895]]]
    row=dict(object='synthetic',face=0,material_id=1,chart_m=xy,xyz=[[u,0,v] for u,v in xy])
    out=partition_joint_zones(row,zones)
    assert sum(Polygon(p['chart_m']).area for p in out['pieces'])==pytest.approx(Polygon(xy).area,abs=1e-10)
    assert out['new_segments']


def test_one_grid_wide_remainder_is_reported_with_bounded_coverage_error():
    out=partition_joint_zones(face(),[[[2e-12,0],[.01,0],[.01,1],[2e-12,1]]])
    assert len(out['pieces'])==2
    assert out['numerical_fragments']
    assert out['coverage_error_m2']<=out['overlay_area_bound_m2']
    assert sum(x['area_m2'] for x in out['numerical_fragments'])<=out['overlay_area_bound_m2']


def test_native_cells_keep_convex_quads_and_remove_concave_tessellation_ambiguity():
    row=face();piece=dict(source=['synthetic',0],joint=False,chart_m=row['chart_m'],xyz=row['xyz'])
    assert len(native_piece_cells(piece))==1
    xy=[[0,0],[2,0],[2,.01],[.01,.01],[.01,1],[0,1]]
    piece=dict(piece,chart_m=xy,xyz=[[u,0,v] for u,v in xy])
    cells=native_piece_cells(piece)
    assert sum(Polygon(p['chart_m']).area for p in cells)==pytest.approx(Polygon(xy).area)
    assert all(len(p['chart_m'])<=4 and Polygon(p['chart_m']).exterior.is_ccw for p in cells)
    assert all(v in piece['xyz'] for p in cells for v in p['xyz'])
    for cell in cells:
        if len(cell['chart_m'])==4:
            q=cell['chart_m']
            assert all(Polygon([q[i],q[(i+1)%4],q[(i+2)%4]]).area>1e-10 for i in range(4))


def test_native_cells_remove_only_sub_storage_collinear_boundary_corners():
    xy=[[0,0],[1,1e-8],[2,0],[2,1],[0,1]]
    p=dict(source=['synthetic',0],joint=False,chart_m=xy,xyz=[[u,0,v] for u,v in xy])
    cells=native_piece_cells(p)
    assert len(cells)==1 and len(cells[0]['chart_m'])==4
    assert cells[0]['native_corner_error_bound_m']==2e-5
    assert cells[0]['native_removed_corners']
    assert abs(sum(Polygon(c['chart_m']).area for c in cells)-Polygon(xy).area)<1e-7


def test_native_quad_merge_never_reintroduces_collinear_three_corner_fan():
    xy=[[-103.85266788427,-4.950617016757],[-103.85266788427,-4.505904016177],
        [-103.842661431064,-4.505904016527],[-102.351364937232,-4.499998801947],
        [-103.851378360964,-4.499998742342],[-104.032784842948,-4.965607339149],
        [-102.169958455248,-4.965607398733],[-102.341693450106,-4.524822212336],
        [-102.341693450106,-4.950617069694],[-102.351699903312,-4.950617069343],
        [-102.351699903312,-4.50749396134],[-103.842661431064,-4.950617017108]]
    piece=dict(source=['synthetic',0],joint=False,chart_m=xy,xyz=[[u,0,v] for u,v in xy])
    for p in native_piece_cells(piece):
        if len(p['chart_m'])==4:
            q=p['chart_m']
            assert all(Polygon([q[i],q[(i+1)%4],q[(i+2)%4]]).area>1e-9 for i in range(4))


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


# --- merged from tests/test_course_grid_cut_generated.py (#1960)
# new-case: generated exact-edge strip footprints on rotated source charts.

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


# --- merged from tests/test_course_grid_native_pinches.py (#1960)
# new-case: native pinch closure below the existing 20um storage envelope.

def test_native_tessellation_reports_and_omits_sub_overlay_collinear_cell():
    xy=[[106.779152441312,-4.872884263696],[106.768364321559,-4.872884267569],
        [109.176082668445,-4.872883403301],[108.702272247068,-4.865310649323],
        [108.694454686826,-4.865310651355],[108.694454489249,-4.757958233974],
        [108.702272049491,-4.757958231942],[109.176082668445,-4.74870070219],
        [106.779152212759,-4.748701087886]]
    piece=dict(source=['synthetic',1],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy])
    cells=native_piece_cells(piece)
    assert all(Polygon(c['chart_m']).area>1e-12 for c in cells)
    assert sum(Polygon(c['chart_m']).area for c in cells)==pytest.approx(Polygon(xy).area,abs=1e-10)
    assert any(c.get('native_collapsed_cells') for c in cells)


def test_native_fragment_accounting_closes_the_reported_area_balance():
    xy=[[101.236748525615,-4.446862021089],[99.249740785451,-4.446861946583],
        [99.249740785451,-4.571047024429],[99.443149966581,-4.571047031681],
        [99.443149966581,-4.457708205495],[99.453149966581,-4.457708205495],
        [99.453149966581,-4.571047032015],[99.452052539885,-4.571047032015],
        [101.042814210303,-4.571047091663],[101.042814210303,-4.45770826544],
        [101.052814210303,-4.45770826544],[101.052814210303,-4.571047092033],
        [101.052678420918,-4.571047092033],[101.236748525615,-4.571047098935]]
    cells=native_piece_cells(dict(source=['synthetic',2],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy]))
    dropped=sum(c['area_m2'] for c in cells[0]['native_collapsed_cells'])
    assert sum(Polygon(c['chart_m']).area for c in cells)+dropped==pytest.approx(Polygon(xy).area,abs=1e-10)


def test_native_almost_closed_slit_retains_surface_without_ambiguous_corners():
    # Synthetic affine-plane reduction of the real source-1499 overlay witness.
    xy=[[112.588943724691,-4.872886696458],[114.979522951001,-4.872887083888],
        [114.523786263829,-4.507899927305],[114.52378633566,-4.86476729482],
        [114.514014403442,-4.864767294959],[114.514014394013,-4.817922546574],
        [114.51206000757,-4.817922546602],[114.512060006784,-4.81401881757],
        [114.514014393227,-4.814018817542],[114.514014360619,-4.652014062711],
        [114.512059974175,-4.652014062739],[114.512059973389,-4.648110333707],
        [114.514014359833,-4.648110333679],[114.514014331939,-4.50952795304],
        [114.515968718382,-4.509527953012],[114.515968716811,-4.501720494948],
        [114.523786263802,-4.507899927284],[114.513917905127,-4.499996626377],
        [112.600670001776,-4.499996226497],[112.600670076769,-4.87257478023],
        [112.588943758108,-4.872574780397],[112.588943724691,-4.499996224046]]
    piece=dict(source=['synthetic',0],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy])
    cells=native_piece_cells(piece)
    assert cells
    assert all(Polygon(c['chart_m']).is_valid for c in cells)
    assert all(len(set(map(tuple,c['xyz'])))==len(c['xyz']) for c in cells)
    assert sum(Polygon(c['chart_m']).area for c in cells)==pytest.approx(Polygon(xy).area,abs=1e-9)


# --- merged from tests/test_course_grid_pages.py (#1960)
# new-case: explicit budget and exact source membership for multi-page support.

def inputs():
    piece = dict(source=['synthetic', 3], joint=True, patch=['synthetic', 3, 0],
                 chart_m=[[0, 0], [.02, 0], [.02, 1], [0, 1]],
                 xyz=[[0, 0, 0], [.02, 0, 0], [.02, 0, 1], [0, 0, 1]])
    parts = [dict(source=piece['source'], pieces=[piece], dropped_faces=[])]
    pages = [dict(key=piece['patch'], tile=1002, translation_m=[1, 1],
                  members=[dict(key=piece['patch'], fold_shift_m=[0, 0])])]
    return parts, dict(faces=[], unplaced=[], dropped_faces=[]), pages


def run(p=None, f=None, pages=None, **kw):
    a, b, c = inputs()
    return assemble_support_pages(a if p is None else p, b if f is None else f,
                                  c if pages is None else pages,
                                  texel_px_m=512.1, tile_px=4096,
                                  tile_budget=kw.get('tile_budget', 2))


def test_second_page_requires_explicit_budget_and_does_not_grant_qa():
    with pytest.raises(ValueError, match='budget'):
        run(tile_budget=1)
    out = run()
    assert out['passed'] is False and len(out['faces']) == 1
    assert out['faces'][0]['tile'] == 1002
    assert out['faces'][0]['uv'][0] == pytest.approx([1+512.1/4096, 512.1/4096])
    assert out['source_faces'] == 1 and not out['dropped_faces']


@pytest.mark.parametrize('mode', ['empty', 'duplicate_source', 'duplicate_member', 'unknown_member',
                                  'missing_member', 'nan', 'inf', 'unsupported_tile', 'boolean_tile',
                                  'missing_patch', 'extra_placement', 'dropped', 'unplaced', 'bad_uv'])
def test_partial_duplicate_unknown_nonfinite_inputs_refuse(mode):
    p, f, pages = inputs()
    if mode == 'empty': p = []
    elif mode == 'duplicate_source': p *= 2
    elif mode == 'duplicate_member': pages[0]['members'] *= 2
    elif mode == 'unknown_member': pages[0]['members'][0]['key'][1] = 999
    elif mode == 'missing_member': pages[0]['members'] = []
    elif mode == 'nan': pages[0]['translation_m'][0] = float('nan')
    elif mode == 'inf': pages[0]['members'][0]['fold_shift_m'][0] = float('inf')
    elif mode == 'unsupported_tile': pages[0]['tile'] = 1011
    elif mode == 'boolean_tile': pages[0]['tile'] = True
    elif mode == 'missing_patch': del p[0]['pieces'][0]['patch']
    elif mode == 'extra_placement': pages.append(copy.deepcopy(pages[0]))
    elif mode == 'dropped': p[0]['dropped_faces'] = [3]
    elif mode == 'unplaced': f['unplaced'] = [3]
    elif mode == 'bad_uv': p[0]['pieces'][0]['chart_m'][1][0] = float('nan')
    with pytest.raises(ValueError): run(p, f, pages)


def test_plain_fold_and_support_keep_every_piece_without_mutating_inputs():
    p, f, pages = inputs()
    brick = copy.deepcopy(p[0]['pieces'][0]);brick['joint'] = False;brick.pop('patch')
    brick['chart_m'] = [[2, 0], [3, 0], [3, 1], [2, 1]]
    brick['xyz'] = [[u, 0, v] for u, v in brick['chart_m']]
    p[0]['pieces'].append(brick)
    f['faces'] = [dict(object='synthetic', face=0, translation_m=[0, 1])]
    frozen = copy.deepcopy((p, f, pages))
    out = run(p, f, pages)
    assert len(out['faces']) == 2
    assert {r['tile'] for r in out['faces']} == {1001, 1002}
    assert (p, f, pages) == frozen


def test_unknown_fold_identity_names_key():
    p, f, pages = inputs()
    f['faces'] = [dict(object='ghost', face=7, translation_m=[0, 0])]
    with pytest.raises(ValueError, match='ghost'):
        run(p, f, pages)
