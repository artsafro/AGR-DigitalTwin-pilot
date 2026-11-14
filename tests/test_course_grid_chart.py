"""Source-face public adapter tests; all geometry here is synthetic."""
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
    assert result['seams'][0]['horizontal_residual_px'] == pytest.approx(1024)
    assert result['passed'] is False  # chart construction is never delivery QA
    a = result['faces'][0]['chart_m']
    assert a[1][0] - a[0][0] == pytest.approx(2)
    assert a[2][1] - a[1][1] == pytest.approx(1)
