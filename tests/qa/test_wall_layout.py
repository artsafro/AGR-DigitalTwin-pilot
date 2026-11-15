"""new-case: report-only BODY wall layout, synthetic fixtures (#1446)."""
import pytest

from twinqa import look


def body_a():
    # Synthetic wall strip below openings: three triangles meeting at vertex 0,
    # then a disconnected 4 cm x 1 m wall sliver. Coordinates are metres, Z up.
    return dict(name='body_A', face_geometry=dict(
        vertices=[[0, 0, 0], [3, 0, 0], [3, 0, 1], [2, 0, 1], [0, 0, 1],
                  [4, 0, 0], [4.04, 0, 0], [4.04, 0, 1], [4, 0, 1]],
        polygons=[[0, 1, 2], [0, 2, 3], [0, 3, 4], [5, 6, 7, 8]]))


def test_body_a_patterns():
    report = look.part_layout_report([body_a()], 'VPM-OKS')
    wall = report['parts'][0]['wall_layout']
    assert wall['counts'] == dict(diagonals=2, slivers=1, fans=1)
    assert wall['slivers'][0]['face_id'] == 3
    assert wall['slivers'][0]['position_m'] == pytest.approx([4.02, 0, 0.5])
    assert wall['fans'] == [dict(vertex_id=0, face_ids=[0, 1, 2], position_m=[0, 0, 0])]
    assert wall['status'] == 'review'
    assert wall['report_only'] is True
    assert wall['blocking'] is False
    assert report['parts'][0]['quad_dominance']['passed'] is False
