"""Pure-Python native-resolution ROI and binding regressions (#369)."""
import json
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/flora'))
import measure_sprite_coverage as coverage
from measure_sprite_coverage import (
    BARK_STRIP_PROVENANCE, MEASURE_CACHE, REVIEWED_BARK_PROVENANCE, analyze, bark_strip_candidates,
    brown_candidate_mask, compact_measure, classify_pixels, images, main, reviewed_bark_region,
    reviewed_bark_union, slot_material,
)


def quad(lo=.05,hi=.95):
    return {'uv':[[lo,lo],[hi,lo],[hi,hi],[lo,hi]],'uvfaces':[[0,1,2],[0,2,3]]}


def bark_triangle():
    # Actual #369 face 332 UVs.
    return {'uv':[[.9279804229736328,.3927140235900879],[.9257583618164062,.5372509956359863],[.9214391708374023,.3927288055419922]],'uvfaces':[[0,1,2]]}


def _coords():
    return {'mapChannel':1,'U_Tiling':1.0,'V_Tiling':1.0,'U_Offset':0.0,'V_Offset':0.0,'U_Angle':0.0,'V_Angle':0.0,'W_Angle':0.0,'U_Mirror':False,'V_Mirror':False}


def _material(diffuse='d.png', opacity='o.png'):
    return {'class':'Standardmaterial','name':'M','bindings':{'opacityMapEnable':True},
            'slot_paths':{'diffuseMap':diffuse,'opacityMap':opacity},
            'slot_settings':{'opacityMap':{'monoOutput':0}},
            'textures':[{'name':'d','coords':_coords()},{'name':'o','coords':_coords()}]}


def _trunk_record():
    return {'name':'Tilia_VPM',
            'vertices':[[0,0,0],[.2,0,0],[.1,.02,1],[.1,-.02,1]],
            'faces':[[0,1,2],[0,1,3]],
            'uv':[[.15,.1],[.35,.1],[.35,.9],[.15,.9]],
            'uvfaces':[[0,1,2],[0,2,3]],
            'face_material_ids':[1,1],'triangles':2,'material':_material()}


def _foliage_record():
    return {'name':'Card_VPM',
            'vertices':[[0,0,0],[1,0,0],[1,0,1],[0,0,1]],
            'faces':[[0,1,2],[0,2,3]],
            'uv':[[.1,.1],[.4,.1],[.4,.5],[.1,.5]],
            'uvfaces':[[0,1,2],[0,2,3]],
            'face_material_ids':[1,1],'triangles':2,'material':_material()}


def _save_maps(folder, diffuse, opacity):
    folder.mkdir(parents=True, exist_ok=True)
    Image.fromarray(diffuse).save(folder/'d.png')
    Image.fromarray(opacity).save(folder/'o.png')


def _bare_record():
    return {'name':'N','vertices':[[0,0,0],[1,0,0],[0,0,1]],'faces':[[0,1,2]],
            'uv':[[0,0],[1,0],[0,1]],'uvfaces':[[0,1,2]],'face_material_ids':[1],'triangles':1,
            'material':{'class':'Standardmaterial','name':'M','bindings':{}}}


@pytest.mark.parametrize('flag',[None,1,'true',[],{},float('nan')])
def test_geometry_parts_flag_rejects_unsupported_values(flag):
    with pytest.raises(ValueError,match='geometry_parts must be bool'):
        analyze(_foliage_record(),'Card_VPM','original',{'geometry_parts':flag})


def test_geometry_parts_flag_joins_duplicate_map_indices(tmp_path):
    folder=tmp_path/'maps'
    opaque=np.zeros((100,100),np.uint8);opaque[50:90,10:40]=255
    diffuse=np.zeros((100,100,3),np.uint8);diffuse[...,1]=180
    _save_maps(folder,diffuse,opaque)
    record=_foliage_record()
    record['uv']=[[.1,.1],[.4,.1],[.4,.5],[.1,.1],[.4,.5],[.1,.5]]
    record['uvfaces']=[[0,1,2],[3,4,5]]
    job={'scenes':[{'tag':'original','maps':str(folder)}],'bitmap_copies':{},'species':[],
         'geometry_parts':True}
    result=analyze(record,'Card_VPM','original',job)
    assert len(result['islands'])==1
    assert result['islands'][0]['faces']==[0,1]
    assert result['islands'][0]['role']=='foliage'
    assert result['role_method']=='geometry_parts'
    star=analyze(record,'Card_NPM','original',job)['islands'][0]
    assert star['role']=='star_plane'


def test_real_narrow_bark_triangle_passes_with_explicit_solid_strip():
    record=bark_triangle();alpha=np.zeros((4096,4096),bool);alpha[:,3304:4096]=True
    result,_,_=compact_measure(record,[0],alpha,[(3304,0,4096,4096)],'VPM',role='trunk',bark_mask=alpha.copy())
    assert result['metric']=='bark_containment' and result['pass'] and result['score']==pytest.approx(1)


def test_real_narrow_bark_triangle_fails_with_displaced_bark():
    record=bark_triangle();alpha=np.zeros((4096,4096),bool);alpha[:,3304:4096]=True
    bark=np.zeros_like(alpha);bark[:,:100]=True
    result,_,_=compact_measure(record,[0],alpha,[(3304,0,4096,4096)],'VPM',role='trunk',bark_mask=bark)
    assert result['metric']=='bark_containment' and result['score']==0 and not result['pass']


def test_trunk_missing_bark_mask_is_error():
    alpha=np.ones((32,32),bool)
    for mask in (None,):
        with pytest.raises(ValueError,match='explicit bark mask'):
            compact_measure(quad(),[0,1],alpha,[(0,0,32,32)],'VPM',role='trunk',bark_mask=mask)
    with pytest.raises(ValueError,match='opacity'):
        compact_measure(quad(),[0,1],alpha,[(0,0,32,32)],'VPM',role='trunk')


def test_bark_mask_must_be_finite_bool_and_same_size():
    alpha=np.ones((20,30),bool);cells=[(0,0,30,20)]
    bad=[np.ones((20,30),np.float64),np.full((20,30),np.nan),np.ones((20,30),np.uint8),
         np.ones((19,30),bool),np.ones((20,31),bool),np.ones((20,30,1),bool)]
    for mask in bad:
        with pytest.raises(ValueError,match='finite bool same-size'):
            compact_measure(quad(),[0,1],alpha,cells,'VPM',role='trunk',bark_mask=mask)


def test_bark_containment_passes_at_95_percent_and_fails_below():
    from fractions import Fraction
    from measure_sprite_coverage import island_mask
    record=quad(0,1);alpha=np.ones((100,100),bool)
    m,_,roi,_=island_mask(record,[0,1],alpha.shape);x,y,X,Y=roi
    area=int(m.sum());assert area>=20
    keep=(area*19+19)//20
    assert Fraction(keep,area)>=Fraction(19,20) and Fraction(keep-1,area)<Fraction(19,20)
    def mask(count):
        local=np.zeros(m.shape,bool);local.reshape(-1)[np.flatnonzero(m)[:count]]=True
        bark=np.zeros(alpha.shape,bool);bark[y:Y,x:X]=local;return bark
    passed=compact_measure(record,[0,1],alpha,[(0,0,100,100)],'VPM',role='trunk',bark_mask=mask(keep))[0]
    failed=compact_measure(record,[0,1],alpha,[(0,0,100,100)],'VPM',role='trunk',bark_mask=mask(keep-1))[0]
    assert passed['metric']=='bark_containment' and passed['pass'] and passed['score']==pytest.approx(keep/area)
    assert failed['metric']=='bark_containment' and not failed['pass'] and failed['score']==pytest.approx((keep-1)/area)


def test_non_trunk_keeps_sprite_metric_even_if_bark_mask_passed():
    alpha=np.zeros((100,100),bool);alpha[10:90,10:90]=True
    result,_,_=compact_measure(quad(0,1),[0,1],alpha,[(10,10,90,90)],'VPM',role='foliage',bark_mask=np.zeros_like(alpha))
    assert result['score']==1 and result['pass'] and 'metric' not in result


def test_source_bark_strip_candidates_use_aspect_and_occupancy():
    solid=np.ones((30,10),bool)
    assert len(bark_strip_candidates(solid,[(0,0,10,30)]))==1
    short=np.ones((29,10),bool)
    assert bark_strip_candidates(short,[(0,0,10,29)])==[]
    occupied=np.zeros((40,10),bool);occupied[:38,:]=True
    found=bark_strip_candidates(occupied,[(0,0,10,40)])
    assert len(found)==1 and found[0]['opaque_occupancy']==pytest.approx(.95) and found[0]['aspect_height_over_width']==4
    occupied[37,0]=False
    assert bark_strip_candidates(occupied,[(0,0,10,40)])==[]


def test_source_trunk_candidate_is_annotation_and_ambiguous_stays_unknown(tmp_path):
    MEASURE_CACHE.clear()
    folder=tmp_path/'maps'
    opaque=np.zeros((200,200),np.uint8);opaque[:,10:30]=255
    diffuse=np.zeros((200,200,3),np.uint8);diffuse[...,1]=180
    _save_maps(folder,diffuse,opaque)
    job={'scenes':[{'tag':'original','maps':str(folder)}],'bitmap_copies':{},'species':[]}
    result=analyze(_trunk_record(),'Tilia_VPM','original',job)
    row=result['islands'][0]
    assert row['role']=='trunk' and row['status']=='candidate_only' and row['pass'] is False
    assert row['semantic_pass'] is False and 'score' not in row and 'metric' not in row
    assert len(row['bark_strip_candidates'])==1 and row['bark_strip_provenance']==BARK_STRIP_PROVENANCE
    assert result['bark_strip_annotations'][0]['provenance']==BARK_STRIP_PROVENANCE
    assert result['bark_strip_annotations'][0]['candidates'][0]['bbox']==[10,0,30,200]
    ambiguous=np.zeros((200,200),np.uint8);ambiguous[:,10:30]=255;ambiguous[:,80:100]=255
    _save_maps(folder,diffuse,ambiguous)
    from measure_sprite_coverage import images
    images.cache_clear()
    both=analyze(_trunk_record(),'Tilia_VPM','original',job)
    unknown=both['islands'][0]
    assert unknown['status']=='unknown' and unknown['pass'] is False and len(unknown['bark_strip_candidates'])==2
    assert 'ambiguous or missing' in unknown['error'] and 'score' not in unknown
    missing=np.zeros((200,200),np.uint8);missing[10:60,10:60]=255
    _save_maps(folder,diffuse,missing);images.cache_clear()
    none=analyze(_trunk_record(),'Tilia_VPM','original',job)['islands'][0]
    assert none['status']=='unknown' and none['bark_strip_candidates']==[] and 'score' not in none
    _save_maps(folder,diffuse,ambiguous);images.cache_clear()
    foliage_record=_foliage_record();foliage_record['uv']=[[.06,.2],[.12,.2],[.12,.8],[.06,.8]]
    foliage=analyze(foliage_record,'Card_VPM','original',job)['islands'][0]
    assert foliage['role']=='foliage' and 'score' in foliage and foliage.get('metric')!='bark_containment'


def _reviewed_job(folder, entry):
    key=str(folder/'d.png').replace('/','\\').lower()
    return {'scenes':[{'tag':'original','maps':str(folder)}],'bitmap_copies':{},'species':[],
            'bark_annotations':{key:entry}}


def test_reviewed_bark_annotation_scores_npm_and_vpm_containment(tmp_path):
    folder=tmp_path/'maps'
    diffuse=np.zeros((200,200,3),np.uint8);diffuse[...,1]=180
    _save_maps(folder,diffuse,np.full((200,200),255,np.uint8))
    entry={'bbox':[20,10,80,190],'reviewed':True,'note':'continuous bark'}
    job=_reviewed_job(folder,entry)
    pictures=tmp_path/'panels';pictures.mkdir()
    for profile in ('NPM','VPM'):
        MEASURE_CACHE.clear();images.cache_clear()
        result=analyze(_trunk_record(),f'Tilia_{profile}','original',job,pictures)
        row=result['islands'][0]
        assert row['role']=='trunk' and row['bark_strip_candidates']==[] and row['metric']=='bark_containment'
        assert row['score']==pytest.approx(1) and row['pass'] is True and row['geometric_pass'] is True
        assert row['policy_applicable'] is True and row['semantic_confidence']=='reviewed_region'
        assert row['semantic_pass'] is False and row['containment_provenance']==REVIEWED_BARK_PROVENANCE
        assert row['reviewed_bbox']==[20,10,80,190] and row['reviewed_note']=='continuous bark'
        assert row['measurement_scope']=='reviewed_region' and 'status' not in row
        assert result['class_masks'][0]['islands']==[0]
        mask=np.asarray(Image.open(pictures/f'Tilia_{profile}-original-semantic-0-mask.png'))
        overlay=np.asarray(Image.open(pictures/f'Tilia_{profile}-original-semantic-0-overlay.png'))
        assert mask.shape==overlay.shape and np.any(mask!=overlay)
    rgb,alpha,_=images(str(folder/'d.png'),str(folder/'o.png'),False)
    assert int(brown_candidate_mask(rgb,alpha).sum())==0


def test_missing_bark_annotation_stays_candidate_only(tmp_path):
    MEASURE_CACHE.clear()
    folder=tmp_path/'maps'
    opaque=np.zeros((200,200),np.uint8);opaque[:,10:30]=255
    diffuse=np.zeros((200,200,3),np.uint8);diffuse[...,1]=180
    _save_maps(folder,diffuse,opaque)
    elsewhere={'bbox':[10,0,30,200],'reviewed':True,'note':'other atlas'}
    job=_reviewed_job(folder,elsewhere)
    job['bark_annotations']={'c:/other/d.png':elsewhere}
    missing=analyze(_trunk_record(),'Tilia_VPM','original',job)['islands'][0]
    assert missing['status']=='candidate_only' and missing['pass'] is False and 'score' not in missing
    job=_reviewed_job(folder,{'bbox':[10,0,30,200],'reviewed':False,'note':'not certified'})
    images.cache_clear()
    declined=analyze(_trunk_record(),'Tilia_VPM','original',job)['islands'][0]
    assert declined['status']=='candidate_only' and declined['semantic_pass'] is False and 'score' not in declined


def test_malformed_reviewed_bbox_does_not_score(tmp_path):
    shape=(200,200);key='c:/maps/d.png'
    def job(entry):
        return {'bark_annotations':{key:entry}}
    bad=[[0,0,10],[0,0,10.0,20],[-1,0,4,4],[10,10,4,20],[0,0,500,10],[0,0,10,500],[True,0,2,2]]
    for bbox in bad:
        with pytest.raises(ValueError,match='malformed'):
            reviewed_bark_region(job({'bbox':bbox,'reviewed':True,'note':'n'}),key,shape)
    with pytest.raises(ValueError,match='malformed'):
        reviewed_bark_region(job({'bbox':[0,0,10,20],'reviewed':True}),key,shape)
    folder=tmp_path/'maps'
    opaque=np.zeros((200,200),np.uint8);opaque[:,10:30]=255
    _save_maps(folder,np.zeros((200,200,3),np.uint8),opaque)
    images.cache_clear();MEASURE_CACHE.clear()
    broken=_reviewed_job(folder,{'bbox':[0,0,10],'reviewed':True,'note':'bad'})
    row=analyze(_trunk_record(),'Tilia_VPM','original',broken)['islands'][0]
    assert row['status']=='unknown' and row['pass'] is False and 'score' not in row and 'malformed' in row['error']
    images.cache_clear()
    missed=_reviewed_job(folder,{'bbox':[0,0,4,4],'reviewed':True,'note':'misses the island'})
    wrong=analyze(_trunk_record(),'Tilia_VPM','original',missed)['islands'][0]
    assert wrong['metric']=='bark_containment' and wrong['score']==0 and wrong['pass'] is False
    assert wrong['semantic_pass'] is False and wrong['semantic_confidence']=='reviewed_region' and 'status' not in wrong


def test_reviewed_region_is_not_a_heuristic_semantic_pass(tmp_path):
    folder=tmp_path/'maps'
    diffuse=np.zeros((64,64,3),np.uint8);diffuse[...,0]=180;diffuse[...,1]=100;diffuse[...,2]=40
    _save_maps(folder,diffuse,np.full((64,64),255,np.uint8))
    key=str(folder/'d.png').replace('\\','/').lower()
    note='brown pixels are not a semantic pass'
    job={'scenes':[{'tag':'original','maps':str(folder)}],'bitmap_copies':{},'species':[],
         'bark_annotations':{key:{'bbox':[0,0,4,4],'reviewed':True,'note':note}}}
    MEASURE_CACHE.clear();images.cache_clear()
    row=analyze(_trunk_record(),'Tilia_VPM','original',job)['islands'][0]
    assert row['score']==0 and row['pass'] is False and row['semantic_pass'] is False
    assert row['semantic_confidence']=='reviewed_region' and row['containment_provenance']==REVIEWED_BARK_PROVENANCE
    rgb,alpha,_=images(str(folder/'d.png'),str(folder/'o.png'),False)
    assert int(brown_candidate_mask(rgb,alpha).sum())==alpha.size
    ours={'scenes':[],'bitmap_copies':{'d.png':str(folder/'d.png'),'o.png':str(folder/'o.png')},'species':[],
          'bark_annotations':job['bark_annotations']}
    MEASURE_CACHE.clear()
    replacement=analyze(_trunk_record(),'Tilia_VPM','ours',ours)['islands'][0]
    assert replacement['semantic_confidence']=='unverified' and replacement['semantic_pass'] is False
    assert replacement['pass'] is False and replacement['geometric_pass'] is True


def test_replacement_bark_is_geometric_only_with_unverified_semantics(tmp_path):
    MEASURE_CACHE.clear()
    folder=tmp_path/'ours'
    diffuse=np.zeros((64,64,3),np.uint8);diffuse[...,0]=180;diffuse[...,1]=100;diffuse[...,2]=40
    _save_maps(folder,diffuse,np.full((64,64),255,np.uint8))
    job={'scenes':[],'bitmap_copies':{'d.png':str(folder/'d.png'),'o.png':str(folder/'o.png')},'species':[]}
    pictures=tmp_path/'panels';pictures.mkdir()
    result=analyze(_trunk_record(),'Tilia_VPM','ours',job,pictures)
    row=result['islands'][0]
    assert row['metric']=='bark_containment' and row['geometric_pass'] is True and row['score']==pytest.approx(1)
    assert row['semantic_confidence']=='unverified' and row['semantic_pass'] is False and row['pass'] is False
    assert row['measurement_scope']=='geometric_only'
    overlay=np.asarray(Image.open(pictures/'Tilia_VPM-ours-semantic-0-overlay.png'))
    assert (overlay==np.array([255,30,30])).all(axis=-1).any()
    assert not (overlay==np.array([0,220,40])).all(axis=-1).any()
    assert any(isinstance(key,tuple) and 'trunk' in key for key in MEASURE_CACHE)
    foliage=analyze(_foliage_record(),'Card_VPM','ours',job)
    assert any(isinstance(key,tuple) and 'foliage' in key for key in MEASURE_CACHE)
    assert foliage['islands'][0].get('metric')!='bark_containment'
    assert 'bark_strip_annotations' not in result


def test_sources_only_writes_complete_source_counts_without_original_gate(monkeypatch,tmp_path):
    inventory={'failures':[],'light':{'Boom_light':{}},'scenes':{
        'original':{'records':{'Plant_VPM':_bare_record()}},
        'florio':{'records':{'Bush_NPM':_bare_record()}},
        'ours':{'records':{'Bad_VPM':None}}}}
    (tmp_path/'inventory.json').write_text(json.dumps(inventory),encoding='utf-8')
    job=tmp_path/'job.json';job.write_text(json.dumps({'work':str(tmp_path),'inventory':'inventory.json','species':[]}),encoding='utf-8')
    out=tmp_path/'calibration.json'
    monkeypatch.setattr(sys,'argv',['measure','--job',str(job),'--output',str(out),'--sources-only'])
    main()
    payload=json.loads(out.read_text(encoding='utf-8'))
    assert payload['sources_only'] is True and payload['complete'] is True and payload['original_gate']=='not_required'
    assert [row['tag'] for row in payload['objects']]==['original','florio']
    assert payload['counts']['original']['objects']==1 and payload['counts']['florio']['objects']==1
    assert payload['counts']['ours']['objects']==0 and payload['counts']['light']['objects']==0
    blocked=tmp_path/'blocked.json'
    monkeypatch.setattr(sys,'argv',['measure','--job',str(job),'--output',str(blocked)])
    with pytest.raises(ValueError,match='99'):
        main()


def test_native_bbox_metric_uses_continuous_polygon_area():
    a=np.zeros((100,100),bool);a[10:90,10:90]=True
    r,offset,box=compact_measure(quad(0,1),[0,1],a,[(10,10,90,90)],'VPM')
    assert r['score']==1 and r['pass'] and r['clipped_opaque_px_tolerance_1']==0
    assert r['island_area_px']==10000 and offset==[0,0]
    assert 'bbox_area_over_island_area' not in r
    r,_,_=compact_measure(quad(0,1),[0,1],a,[(10,10,90,90)],'NPM')
    assert r['score']==.64 and not r['pass']
    assert r['bbox_area_over_island_area']==pytest.approx(.64)
    assert r['island_intersect_target_bbox_over_target_bbox']==pytest.approx(1)
    assert r['ratio_labels']['bbox_area_over_island_area']=='area(target bbox)/area(island)'
    assert r['ratio_labels']['island_intersect_target_bbox_over_target_bbox']=='area(island intersect target bbox)/area(target bbox)'


def test_roi_npm_one_pixel_tolerance_and_whole_map_bbox():
    a=np.zeros((100,100),bool);a[5:95,5:95]=True
    r,_,_=compact_measure(quad(0,1),[0,1],a,[(5,5,95,95)],'NPM')
    assert r['score']==.81 and r['pass']
    assert r['bbox_area_over_island_area']==pytest.approx(.81)
    assert r['island_intersect_target_bbox_over_target_bbox']==pytest.approx(1)
    assert r['clipped_opaque_px_tolerance_1']==0
    r,_,_=compact_measure(quad(.08,.92),[0,1],a,[(5,5,95,95)],'NPM')
    assert r['clipped_opaque_px_tolerance_1']>0 and not r['pass']
    assert r['bbox_area_over_island_area']==pytest.approx(r['score'])
    assert r['island_intersect_target_bbox_over_target_bbox']<r['bbox_area_over_island_area']


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
    for key,value in [('pass',False),('pass','true'),('role','unknown'),('role','unmapped'),('score',True),('status','failed'),('status','unknown'),('status','review'),('score',float('nan')),('score',float('inf'))]:
        bad=copy.deepcopy(rows);bad[0]['islands'][0][key]=value
        with pytest.raises(ValueError):original_gate(bad)
    bad=copy.deepcopy(rows);bad[0]['islands']=[]
    with pytest.raises(ValueError):original_gate(bad)


def _two_island_trunk():
    record=_trunk_record()
    record['uv']=[[.15,.1],[.35,.1],[.35,.9],[.15,.9],[.55,.1],[.75,.1],[.75,.9],[.55,.9]]
    record['uvfaces']=[[0,1,2],[0,2,3],[4,5,6],[4,6,7]]
    record['faces']=[[0,1,2],[0,1,3],[0,1,2],[0,1,3]]
    record['face_material_ids']=[1,1,1,1]
    record['triangles']=4
    return record


def test_image_masks_are_cached_for_every_island_of_one_bitmap(tmp_path, monkeypatch):
    calls={'strips':0,'brown':0,'reviewed':0}
    real_strips,real_brown,real_reviewed=coverage.bark_strip_candidates,coverage.brown_candidate_mask,coverage.reviewed_bark_mask
    monkeypatch.setattr(coverage,'bark_strip_candidates',lambda *a,**k: calls.__setitem__('strips',calls['strips']+1) or real_strips(*a,**k))
    monkeypatch.setattr(coverage,'brown_candidate_mask',lambda *a,**k: calls.__setitem__('brown',calls['brown']+1) or real_brown(*a,**k))
    monkeypatch.setattr(coverage,'reviewed_bark_mask',lambda *a,**k: calls.__setitem__('reviewed',calls['reviewed']+1) or real_reviewed(*a,**k))
    folder=tmp_path/'maps'
    diffuse=np.zeros((200,200,3),np.uint8);diffuse[...,0]=180;diffuse[...,1]=100;diffuse[...,2]=40
    opaque=np.zeros((200,200),np.uint8);opaque[:,10:30]=255
    _save_maps(folder,diffuse,opaque)
    images.cache_clear();MEASURE_CACHE.clear()
    source={'scenes':[{'tag':'original','maps':str(folder)}],'bitmap_copies':{},'species':[]}
    both=analyze(_two_island_trunk(),'Tilia_VPM','original',source)
    assert calls['strips']==1 and calls['brown']==0 and calls['reviewed']==0
    assert [row['status'] for row in both['islands']]==['candidate_only','candidate_only']
    images.cache_clear();MEASURE_CACHE.clear();calls['brown']=0
    _save_maps(folder,diffuse,np.full((200,200),255,np.uint8))
    ours={'scenes':[],'bitmap_copies':{'d.png':str(folder/'d.png'),'o.png':str(folder/'o.png')},'species':[]}
    scored=analyze(_two_island_trunk(),'Tilia_VPM','ours',ours)
    assert calls['brown']==1 and all(row['pass'] is False and row['geometric_pass'] is True for row in scored['islands'])
    images.cache_clear();MEASURE_CACHE.clear();calls['reviewed']=0
    entry={'bboxes':[[0,0,100,200],[100,0,200,200]],'reviewed':True,'note':'two rectangles'}
    reviewed=analyze(_two_island_trunk(),'Tilia_VPM','original',_reviewed_job(folder,entry))
    assert calls['reviewed']==2
    assert all(row['metric']=='bark_containment' and row['score']==pytest.approx(1) for row in reviewed['islands'])


def test_florio_l_shaped_bark_union_excludes_grass_and_brown_corner(tmp_path):
    alpha=np.ones((200,200),bool)
    boxes=[[0,0,80,200],[0,120,200,200]]
    mask=reviewed_bark_union(alpha,boxes)
    assert mask[10,10] and mask[180,20] and not mask[30,150]
    assert alpha[30,150] and not mask[30,150]
    folder=tmp_path/'maps'
    diffuse=np.zeros((200,200,3),np.uint8);diffuse[...,1]=220
    diffuse[20:60,140:180]=(180,100,40)
    _save_maps(folder,diffuse,np.full((200,200),255,np.uint8))
    entry={'bboxes':boxes,'reviewed':True,'note':'FLORIO continuous bark'}
    job=_reviewed_job(folder,entry)
    images.cache_clear();MEASURE_CACHE.clear()
    arm=analyze(_trunk_record(),'Tilia_VPM','original',job)['islands'][0]
    assert arm['reviewed_bboxes']==boxes and 'reviewed_bbox' not in arm
    assert arm['metric']=='bark_containment' and arm['score']==pytest.approx(1) and arm['pass'] is True
    assert arm['semantic_pass'] is False
    corner=_trunk_record()
    corner['uv']=[[.70,.70],[.90,.70],[.90,.90],[.70,.90]]
    images.cache_clear();MEASURE_CACHE.clear()
    missed=analyze(corner,'Tilia_VPM','original',job)['islands'][0]
    assert missed['score']==0 and missed['pass'] is False and missed['semantic_confidence']=='reviewed_region'
    shape=(200,200);key=str(folder/'d.png').replace('/','\\').lower()
    def job_for(entry):
        return {'bark_annotations':{key:entry}}
    assert reviewed_bark_region(job_for({'bboxes':boxes,'reviewed':'true','note':'n'}),key,shape) is None
    assert reviewed_bark_region(job_for({'bboxes':boxes,'reviewed':1,'note':'n'}),key,shape) is None
    bad=[{'bboxes':[],'reviewed':True,'note':'n'},
         {'bboxes':[[0,0,10,20],[0,0,np.int64(4),8]],'reviewed':True,'note':'n'},
         {'bbox':[0,0,10,20],'bboxes':[[0,0,10,20]],'reviewed':True,'note':'n'},
         {'bboxes':[[0,0,10]],'reviewed':True,'note':'n'},
         {'bboxes':[[-1,0,4,8],[0,0,2,2]],'reviewed':True,'note':'n'}]
    for entry in bad:
        with pytest.raises(ValueError,match='malformed'):
            reviewed_bark_region(job_for(entry),key,shape)
    images.cache_clear();MEASURE_CACHE.clear()
    broken=analyze(_trunk_record(),'Tilia_VPM','original',_reviewed_job(folder,{'bboxes':[[0,0,10]],'reviewed':True,'note':'bad'}))
    assert broken['islands'][0]['status']=='unknown' and broken['islands'][0]['pass'] is False and 'score' not in broken['islands'][0]
