"""new-case: synthetic fixed-density, full-repeat tile-fit API regressions."""
import copy
import pytest

from tools.materials.course_grid_fit import fold_chart


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
