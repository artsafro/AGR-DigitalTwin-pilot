"""Pure-Python native-resolution ROI and binding regressions (#369)."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/flora'))
from measure_sprite_coverage import compact_measure, slot_material, classify_pixels


def quad(lo=.05,hi=.95):
    return {'uv':[[lo,lo],[hi,lo],[hi,hi],[lo,hi]],'uvfaces':[[0,1,2],[0,2,3]]}


def test_native_bbox_metric_uses_continuous_polygon_area():
    a=np.zeros((100,100),bool);a[10:90,10:90]=True
    r,offset,box=compact_measure(quad(0,1),[0,1],a,[(10,10,90,90)],'VPM')
    assert r['score']==1 and r['pass'] and r['clipped_opaque_px_tolerance_1']==0
    assert r['island_area_px']==10000 and offset==[0,0]
    r,_,_=compact_measure(quad(0,1),[0,1],a,[(10,10,90,90)],'NPM')
    assert r['score']==.64 and not r['pass']


def test_roi_npm_one_pixel_tolerance_and_whole_map_bbox():
    a=np.zeros((100,100),bool);a[5:95,5:95]=True
    r,_,_=compact_measure(quad(0,1),[0,1],a,[(5,5,95,95)],'NPM')
    assert r['score']==.81 and r['pass']
    r,_,_=compact_measure(quad(.08,.92),[0,1],a,[(5,5,95,95)],'NPM')
    assert r['clipped_opaque_px_tolerance_1']>0 and not r['pass']


def test_integer_tiling_does_not_flip_an_island():
    r=quad(.1,.9);r['uv']=[[u+7,v+2] for u,v in r['uv']]
    a=np.ones((100,100),bool)
    score,offset,_=compact_measure(r,[0,1],a,[(0,0,100,100)],'VPM')
    assert offset==[7,2] and score['score']==pytest.approx(.64)


def test_native_cell_selection_rejects_empty_or_tied_overlap():
    a=np.zeros((100,100),bool);a[10:20,10:20]=True;a[70:80,70:80]=True
    with pytest.raises(ValueError,match='ambiguous'):
        compact_measure(quad(0,1),[0,1],a,[(10,10,20,20),(70,70,80,80)],'VPM')
    with pytest.raises(ValueError,match='no opaque'):
        compact_measure(quad(.3,.4),[0,1],a,[(10,10,20,20),(70,70,80,80)],'VPM')


def test_material_id_mapping_is_explicit_not_first_entry():
    mat={'class':'Multimaterial','submaterial_ids':[4,9],'submaterials':[{'name':'a'},{'name':'b'}]}
    assert slot_material({'material':mat},[9])['name']=='b'
    for ids in ([1],[4,9],[]):
        with pytest.raises(ValueError):slot_material({'material':mat},ids)
    mat['submaterial_ids']=[4,4]
    with pytest.raises(ValueError):slot_material({'material':mat},[4])


def test_unknown_opaque_pixel_class_is_not_silently_bark():
    rgb=np.array([[[120,120,120],[40,180,30],[180,100,40],[0,0,0]]],np.uint8)
    _,counts=classify_pixels(rgb,np.array([[True,True,True,False]]))
    assert counts=={'foliage_candidate':1,'bark_candidate':1,'unknown_opaque':1,'empty':1}


def test_original_atlas_plant_cell_not_unrelated_neighbour_bbox():
    a=np.zeros((100,100),bool);a[10:50,10:50]=True;a[60:80,70:90]=True
    record=quad(.05,.55)
    local,_,_=compact_measure(record,[0,1],a,[(10,10,50,50),(70,60,90,80)],'NPM',whole_texture=False)
    whole,_,_=compact_measure(record,[0,1],a,[(10,10,50,50),(70,60,90,80)],'NPM',whole_texture=True)
    assert local['sprite_bbox_area_px']==1600 and whole['sprite_bbox_area_px']==5600


def test_real_original_bark_triangle_calibration_does_not_fake_a_pass():
    # Actual #369 face 332 UVs; the synthetic solid strip isolates the geometric issue.
    record={'uv':[[.9279804229736328,.3927140235900879],[.9257583618164062,.5372509956359863],[.9214391708374023,.3927288055419922]],'uvfaces':[[0,1,2]]}
    a=np.zeros((4096,4096),bool);a[:,3304:4096]=True
    result,_,_=compact_measure(record,[0],a,[(3304,0,4096,4096)],'VPM')
    assert result['score']==pytest.approx(.0024447222451933408)
    assert result['opaque_density']==1 and not result['pass']


@pytest.mark.parametrize('profile',['',None,'unsupported'])
def test_compact_metric_rejects_unsupported_profiles(profile):
    with pytest.raises(ValueError,match='unsupported profile'):
        compact_measure(quad(),[0,1],np.ones((100,100),bool),[(0,0,100,100)],profile)


def test_original_gate_fails_closed_for_missing_failed_unknown_and_nonfinite():
    from measure_sprite_coverage import original_gate
    import copy
    rows=[{'object':str(i),'islands':[{'island':0,'role':'foliage','pass':True,'score':1.0}]} for i in range(99)]
    original_gate(rows)
    for bad in ([],rows[:-1],rows+[rows[0]]):
        with pytest.raises(ValueError):original_gate(bad)
    for key,value in [('pass',False),('pass','true'),('role','unknown'),('score',float('nan')),('score',float('inf'))]:
        bad=copy.deepcopy(rows);bad[0]['islands'][0][key]=value
        with pytest.raises(ValueError):original_gate(bad)
    bad=copy.deepcopy(rows);bad[0]['islands']=[]
    with pytest.raises(ValueError):original_gate(bad)
