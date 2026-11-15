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


def rectangle(width=1.0, height=1.0):
    return dict(name='loops', face_geometry=dict(
        vertices=[[0, 0, 0], [width, 0, 0], [width, 0, height], [0, 0, height]],
        polygons=[[0, 1, 2, 3]]))


def test_loops_and_allowed_diagonal():
    clean = look.part_layout_report([rectangle()], 'VPM-OKS')['parts'][0]
    assert clean['wall_layout']['counts'] == dict(diagonals=0, slivers=0, fans=0)
    assert clean['quad_dominance']['passed'] is True
    # Same wall with a single diagonal between opening corners (explicitly allowed).
    diagonal = rectangle()
    diagonal['face_geometry']['polygons'] = [[0, 1, 2], [0, 2, 3]]
    report = look.part_layout_report([diagonal], 'VPM-OKS')['parts'][0]
    wall = report['wall_layout']
    assert wall['counts'] == dict(diagonals=1, slivers=0, fans=0)
    assert wall['diagonals'] == [dict(vertex_ids=[0, 2], face_ids=[0, 1],
        position_m=[0.5, 0, 0.5], endpoints_m=[[0, 0, 0], [1, 0, 1]])]
    assert wall['status'] == 'review' and not wall['blocking']
    # quad_dominance still reports its own mergeable triangles: D227 does not waive it.
    assert report['quad_dominance']['passed'] is False


@pytest.mark.parametrize('width,height,slivers', [(0.049, 0.501, 1), (0.05, 1, 0), (0.04, 0.5, 0)])
def test_scope_and_thresholds(width, height, slivers):
    wall = look.part_layout_report([rectangle(width, height)], 'NPM')['parts'][0]['wall_layout']
    assert wall['counts']['slivers'] == slivers
    assert wall['wall_face_ids'] == [0] and wall['skipped_face_ids'] == []
    assert wall['threshold_policy'] == 'orchestrator default, user may change'


@pytest.mark.parametrize('degrees', range(0, 360, 15))
def test_rotated_translated_walls(degrees):
    import math
    row = body_a()
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    row['face_geometry']['vertices'] = [[100+x*c-y*s, -200+x*s+y*c, z+30]
                                       for x, y, z in row['face_geometry']['vertices']]
    wall = look.part_layout_report([row], 'VPM')['parts'][0]['wall_layout']
    assert wall['counts'] == dict(diagonals=2, slivers=1, fans=1)
    assert wall['report_only'] is True and wall['blocking'] is False
    assert sorted(wall['wall_face_ids'] + wall['skipped_face_ids']) == [0, 1, 2, 3]


def test_horizontal_faces_accounted_not_wall_fans():
    row = body_a()
    row['face_geometry']['vertices'] = [[x, z, y] for x, y, z in row['face_geometry']['vertices']]
    wall = look.part_layout_report([row], 'NPM')['parts'][0]['wall_layout']
    assert wall['status'] == 'not_measured'
    assert wall['skipped_face_ids'] == [0, 1, 2, 3]
    assert wall['wall_face_ids'] == []
    assert wall['counts'] == dict(diagonals=0, slivers=0, fans=0)


@pytest.mark.parametrize('change', ['empty', 'partial', 'nan', 'inf', 'index', 'repeated', 'degenerate', 'overflow'])
def test_invalid_geometry(change):
    row = rectangle()
    shape = row['face_geometry']
    if change == 'empty': shape['polygons'] = []
    if change == 'partial': del shape['vertices']
    if change in ('nan', 'inf'): shape['vertices'][0][0] = float(change)
    if change == 'index': shape['polygons'][0][0] = 99
    if change == 'repeated': shape['polygons'][0][0] = 1
    if change == 'degenerate': shape['vertices'] = [[i, 0, 0] for i in range(4)]
    if change == 'overflow': shape['vertices'][2][2] = 1e308
    with pytest.raises(ValueError): look.part_layout_report([row], 'VPM')


@pytest.mark.parametrize('thresholds', [dict(axis_tol_deg=float('nan')), dict(axis_tol_deg=45),
    dict(normal_z_max=1), dict(sliver_short_m=0), dict(fan_min_triangles=2), dict(fan_min_triangles=True)])
def test_invalid_thresholds(thresholds):
    with pytest.raises(ValueError): look.part_layout_report([rectangle()], 'VPM', **thresholds)


def test_pre_show_report():
    rows = [rectangle(), body_a()]
    report = look.part_layout_report(rows, 'VPM')
    assert [p['part'] for p in report['parts']] == ['loops', 'body_A']
    assert [p['quad_dominance']['passed'] for p in report['parts']] == [True, False]
    assert [p['wall_layout']['status'] for p in report['parts']] == ['clean', 'review']
    for bad in ([], [rows[0], rows[0]], [rows[0], {'name': 'partial'}]):
        with pytest.raises(ValueError): look.part_layout_report(bad, 'VPM')
    with pytest.raises(ValueError, match='profile'): look.part_layout_report(rows, 'unsupported')
    assert look.part_layout_report([rectangle()], 'VPM')['parts'][0]['wall_layout']['status'] == 'clean'


def test_custom_defaults_and_source_face_identity():
    import copy
    row = body_a()
    # Source face order changes; ids must remain source-local, not filtered ids.
    row['face_geometry']['polygons'] = [row['face_geometry']['polygons'][i] for i in [3, 0, 2, 1]]
    before = copy.deepcopy(row)
    wall = look.part_layout_report([row], 'VPM', fan_min_triangles=4)['parts'][0]['wall_layout']
    assert wall['slivers'][0]['face_id'] == 0
    assert wall['counts'] == dict(diagonals=2, slivers=1, fans=0)
    assert wall['thresholds']['fan_min_triangles'] == 4
    assert row == before
    wall = look.part_layout_report([row], 'VPM', sliver_short_m=0.03)['parts'][0]['wall_layout']
    assert wall['counts']['slivers'] == 0
