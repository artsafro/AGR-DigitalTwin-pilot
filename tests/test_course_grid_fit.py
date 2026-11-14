"""new-case: synthetic fixed-density, full-repeat tile-fit API regressions."""
import copy
import pytest

from tools.materials.course_grid_fit import fold_chart, fit_mask_samples


def face(points, index=0):
    return {'object': 'synthetic', 'face': index, 'chart_m': points}


def test_fold_preserves_offsets_and_full_repeat_not_bbox_phase_reset():
    rows = [face([[9, -1], [11, -1], [11, 0], [9, 0]])]
    before = copy.deepcopy(rows)
    report = fold_chart(rows, repeat_m=4, texel_px_m=512, tile_px=4096, border_px=32)
    placed = report['faces'][0]
    assert placed['translation_m'] == [-8, 4]
    assert placed['uv'][0] == pytest.approx([544/4096, 1568/4096])
    assert placed['uv'][1][0] - placed['uv'][0][0] == pytest.approx(.25)
    assert report['status'] == 'fold_contained_masks_unchecked'
    assert report['passed'] is False
    assert report['dropped_faces'] == []
    assert rows == before


def test_overflow_reports_every_face_without_scale_or_drop():
    rows = [face([[0, 0], [8, 0], [8, 1], [0, 1]])]
    report = fold_chart(rows, repeat_m=4, texel_px_m=512, tile_px=4096, border_px=32)
    assert report['status'] == 'fold_overflow'
    assert report['unplaced'] == [['synthetic', 0]]
    assert len(report['faces']) == 1
    assert report['faces'][0]['required_extent_px'] == [4096, 512]
    assert report['passed'] is False


@pytest.mark.parametrize('rows', [[], [face([])], [face([[0,0],[1,0],[0,float('nan')]])],
    [face([[0,0],[1,0],[0,1]])]*2])
def test_bad_faces_fail_closed(rows):
    with pytest.raises(ValueError):
        fold_chart(rows, repeat_m=4, texel_px_m=512, tile_px=4096, border_px=32)


@pytest.mark.parametrize('name,value', [('repeat_m',0),('repeat_m',float('inf')),
    ('texel_px_m',511.99),('texel_px_m',1706.01),('texel_px_m',True),
    ('border_px',0),('tile_px',1024),('border_px',2048)])
def test_bad_options_fail_closed(name,value):
    opts=dict(repeat_m=4, texel_px_m=512, tile_px=4096, border_px=32)
    opts[name]=value
    with pytest.raises(ValueError):
        fold_chart([face([[0,0],[1,0],[0,1]])], **opts)


def test_legal_density_and_containment_boundaries_are_inclusive():
    for density in [512,1706]:
        r=fold_chart([face([[0,0],[4032/density,0],[0,1]])],repeat_m=8,
                     texel_px_m=density,tile_px=4096,border_px=32)
        assert r['unplaced']==[]
        assert r['passed'] is False


def test_mask_conflict_uses_another_full_repeat_copy_never_overwrites():
    a=face([[0,0],[1,0],[1,1],[0,1]])
    b=dict(a,face=1)
    # Same lattice phase, incompatible panel-mask samples: two copies required.
    samples=[{'object':'synthetic','face':0,'samples':[[.5,.5,True]]},
             {'object':'synthetic','face':1,'samples':[[.5,.5,False]]}]
    result=fit_mask_samples([a,b],samples,repeat_m=4,texel_px_m=512,
                           tile_px=4096,border_px=32,seed=0)
    assert result['unplaced']==[]
    assert result['faces'][0]['translation_m'] != result['faces'][1]['translation_m']
    assert result['passed'] is False
    # With a 7 m repeat only one copy of this phase fits. It must report a drop.
    failed=fit_mask_samples([a,b],samples,repeat_m=7,texel_px_m=512,
                           tile_px=4096,border_px=32,seed=0)
    assert len(failed['unplaced'])==1
    assert failed['status']=='sample_fit_exhausted'
    assert len(failed['faces'])+len(failed['unplaced'])==2
    assert failed['witnesses'][0]['conflict_pixels']>=1
    assert failed['witnesses'][0]['existing_face'] == ['synthetic',0]


@pytest.mark.parametrize('samples', [[[1.1,.5,True]],[[.5,.5,True],[.5,.5,False]]])
def test_outside_or_self_contradictory_mask_samples_are_never_success(samples):
    rows=[face([[0,0],[1,0],[1,1],[0,1]])]
    mask=[{'object':'synthetic','face':0,'samples':samples}]
    if samples[0][0]>1:
        with pytest.raises(ValueError,match='outside'):
            fit_mask_samples(rows,mask,repeat_m=7,texel_px_m=512,tile_px=4096,border_px=32,seed=0)
    else:
        r=fit_mask_samples(rows,mask,repeat_m=7,texel_px_m=512,tile_px=4096,border_px=32,seed=0)
        assert r['unplaced']==[['synthetic',0]]
        assert r['passed'] is False


def test_generated_translation_only_preservation_and_accounting():
    import random
    rng=random.Random(1326)
    rows=[]
    for i in range(100):
        x,y=rng.uniform(-100,100),rng.uniform(-100,100)
        w,h=rng.uniform(.05,1),rng.uniform(.05,1)
        rows.append(face([[x,y],[x+w,y],[x+w,y+h],[x,y+h]],i))
    before=copy.deepcopy(rows)
    r=fold_chart(rows,repeat_m=4,texel_px_m=512,tile_px=4096,border_px=32)
    assert len(r['faces'])==100 and r['unplaced']==[] and r['dropped_faces']==[]
    for original,out in zip(rows,r['faces']):
        for k in (0,1):
            assert out['translation_m'][k]/4 == round(out['translation_m'][k]/4)
            for p,q in zip(original['chart_m'],out['uv']):
                assert q[k]*4096-32 == pytest.approx((p[k]+out['translation_m'][k])*512,abs=1e-9)
    assert rows==before


@pytest.mark.parametrize('bad', [[],[{'object':'unknown','face':0,'samples':[[0,0,True]]}],
    [{'object':'synthetic','face':0,'samples':[]}],
    [{'object':'synthetic','face':0,'samples':[[float('nan'),0,True]]}],
    [{'object':'synthetic','face':0,'samples':[[0,0,1]]}]])
def test_mask_mapping_must_be_complete_and_valid(bad):
    with pytest.raises(ValueError):
        fit_mask_samples([face([[0,0],[1,0],[0,1]])],bad,repeat_m=4,
                         texel_px_m=512,tile_px=4096,border_px=32,seed=0)

