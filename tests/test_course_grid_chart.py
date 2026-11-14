"""new-case: source-face public adapter tests; all geometry here is synthetic."""
import pytest

from tools.materials.course_grid_chart import build_chart


def ring():
    points = [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0],
              [0, 0, 1], [2, 0, 1], [2, 2, 1], [0, 2, 1]]
    return [{'object': 'synthetic', 'face': i, 'vertices': ids,
             'xyz': [points[v] for v in ids]} for i, ids in enumerate(
                 [[0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])]


def test_approved_ring_termination_keeps_other_edges_and_height():
    result = build_chart(ring(), seam_edges=[{'object': 'synthetic', 'vertices': [0, 4],
                                             'faces': [0, 3], 'mode': 'horizontal_phase'}],
                         repeat_m=3, texel_px_m=512, z0_m=0)
    assert len(result['faces']) == 4
    assert result['dropped_faces'] == []
    assert result['max_continuous_residual_px'] <= 0.1
    assert len(result['seams']) == 1
    assert result['seams'][0]['vertical_residual_px'] == 0
    # The 8 m perimeter differs from the nearest 3 m multiple (9 m) by 1 m.
    assert result['seams'][0]['horizontal_residual_px'] == pytest.approx(512)
    assert result['passed'] is False  # chart construction is never delivery QA
    a = result['faces'][0]['chart_m']
    assert a[1][0] - a[0][0] == pytest.approx(2)
    assert a[2][1] - a[1][1] == pytest.approx(1)


def test_missing_permission_reports_conflict_never_infers_a_cut():
    result = build_chart(ring(), seam_edges=[], repeat_m=3, texel_px_m=512, z0_m=0)
    assert result['status'] == 'chart_conflict'
    assert result['passed'] is False
    assert result['seams'] == []
    assert result['conflicts']
    assert len(result['faces']) == 4


@pytest.mark.parametrize('bad', [[], [dict(ring()[0], xyz=[])], ring()+ring()[:1]])
def test_bad_source_fails_closed(bad):
    with pytest.raises(ValueError):
        build_chart(bad, seam_edges=[], repeat_m=3, texel_px_m=512, z0_m=0)


@pytest.mark.parametrize('bad', [0, -1, float('nan'), float('inf'), True, '3'])
@pytest.mark.parametrize('name', ['repeat_m', 'texel_px_m', 'tolerance_px'])
def test_bad_chart_parameters_fail_closed(name, bad):
    options = dict(seam_edges=[], repeat_m=3, texel_px_m=512, z0_m=0)
    options[name] = bad
    with pytest.raises(ValueError, match=name):
        build_chart(ring(), **options)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, '0'])
def test_bad_origin_fails_closed(bad):
    with pytest.raises(ValueError, match='z0_m'):
        build_chart(ring(), seam_edges=[], repeat_m=3, texel_px_m=512, z0_m=bad)


@pytest.mark.parametrize('entry', [
    {'object': 'synthetic', 'vertices': [0, 9], 'faces': [0, 3], 'mode': 'all_phase'},
    {'object': 'synthetic', 'vertices': [0, 4], 'faces': [0, 2], 'mode': 'all_phase'},
    {'object': 'unknown', 'vertices': [0, 4], 'faces': [0, 3], 'mode': 'all_phase'},
    {'object': 'synthetic', 'vertices': [0, 4], 'faces': [0, 3], 'mode': 'guess'},
    {'object': 'synthetic', 'vertices': [False, 4], 'faces': [0, 3], 'mode': 'all_phase'},
])
def test_unknown_edge_face_object_or_policy_errors(entry):
    with pytest.raises(ValueError, match='seam'):
        build_chart(ring(), seam_edges=[entry], repeat_m=3, texel_px_m=512, z0_m=0)


def test_repeat_boundary_and_row_order_do_not_claim_a_pass_or_modify_source():
    import copy
    rows = ring()
    before = copy.deepcopy(rows)
    a = build_chart(rows, seam_edges=[], repeat_m=4, texel_px_m=512, z0_m=0)
    b = build_chart(list(reversed(rows)), seam_edges=[], repeat_m=4, texel_px_m=512, z0_m=0)
    assert a == b
    assert a['conflicts'] == []
    assert a['passed'] is False
    assert before == rows


def test_duplicate_seam_and_nonmanifold_edge_are_errors():
    s = {'object': 'synthetic', 'vertices': [0, 4], 'faces': [0, 3], 'mode': 'all_phase'}
    with pytest.raises(ValueError, match='duplicate seam'):
        build_chart(ring(), seam_edges=[s, s], repeat_m=3, texel_px_m=512, z0_m=0)
    with pytest.raises(ValueError, match='nonmanifold'):
        build_chart(ring()+[dict(ring()[0], face=9)], seam_edges=[], repeat_m=3, texel_px_m=512, z0_m=0)
