"""new-case: source-bound corner feasibility before course-grid packing."""
import math

import pytest

from tools.materials.course_grid_audit import audit_corners, audit_vertical_cycles


def ring(side=2):
    # Synthetic outward-wound vertical walls: perimeter 8 m at side=2.
    plan = [(0, 0), (side, 0), (side, side), (0, side)]
    rows = []
    for i, (x, y) in enumerate(plan):
        j = (i + 1) % 4
        a, b = plan[j]
        rows.append({'object': 'synthetic-ring', 'face': i,
                     'vertices': [i, j, j+4, i+4],
                     'xyz': [[x,y,0], [a,b,0], [a,b,1], [x,y,1]]})
    return rows


def test_closed_vertical_ring_requires_repeat_closure_even_without_trihedral_fans():
    rows = ring()
    assert audit_corners(rows, anisotropy_limit=1.02)['corners'] == []
    result = audit_vertical_cycles(rows, repeat_m=3, texel_px_m=512)
    assert result['passed'] is False
    assert result['status'] == 'needs_seam_policy'
    witness = result['cycles'][0]
    assert set(witness['faces']) == {0, 1, 2, 3}
    assert abs(witness['circulation_m']) == pytest.approx(8)
    assert witness['wrapped_residual_px'] == pytest.approx(512)
    assert len(witness['edges']) == 4


def corner():
    # Synthetic three orthogonal quads sharing a trihedral corner.
    return [
        {'object': 'synthetic', 'face': 0, 'vertices': [0, 1, 2, 3],
         'xyz': [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]]},
        {'object': 'synthetic', 'face': 1, 'vertices': [0, 3, 4, 5],
         'xyz': [[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]]},
        {'object': 'synthetic', 'face': 2, 'vertices': [0, 5, 6, 1],
         'xyz': [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 0, 0]]},
    ]


def test_trihedral_requires_declared_chart_seam():
    result = audit_corners(corner(), anisotropy_limit=1.02)
    assert result['status'] == 'needs_seam_policy'
    assert result['corners'][0]['faces'] == [0, 1, 2]
    assert result['corners'][0]['angle_sum_deg'] == pytest.approx(270)
    assert result['corners'][0]['defect_deg'] == pytest.approx(90)
    assert result['corners'][0]['max_angle_change_deg'] < 4
    assert result['passed'] is False


@pytest.mark.parametrize('mutation', ['empty', 'duplicate', 'nan', 'inf', 'partial', 'degenerate', 'inconsistent_vertex'])
def test_bad_source_fails_closed(mutation):
    rows = corner()
    if mutation == 'empty': rows = []
    elif mutation == 'duplicate': rows.append(rows[0])
    elif mutation in ('nan', 'inf'): rows[0]['xyz'][0][0] = float(mutation)
    elif mutation == 'partial': rows[0]['xyz'].pop()
    elif mutation == 'degenerate': rows[0]['xyz'][1] = [0, 0, 0]
    elif mutation == 'inconsistent_vertex': rows[0]['xyz'][0][0] = 0.1
    with pytest.raises(ValueError):
        audit_corners(rows, anisotropy_limit=1.02)


@pytest.mark.parametrize('limit', [0, 0.99, math.nan, math.inf, True])
def test_invalid_anisotropy_errors(limit):
    with pytest.raises(ValueError):
        audit_corners(corner(), anisotropy_limit=limit)


def test_generated_rigid_transforms_keep_corner_defect():
    for seed in range(20):
        rows = corner()
        angle = seed * 0.37
        for r in rows:
            r['xyz'] = [[math.cos(angle)*x-math.sin(angle)*y+seed,
                         math.sin(angle)*x+math.cos(angle)*y-seed, z+2*seed]
                        for x, y, z in r['xyz']]
        result = audit_corners(rows, anisotropy_limit=1.02)
        assert result['corners'][0]['defect_deg'] == pytest.approx(90)
        assert result['passed'] is False


def test_cli_fresh_process_and_existing_output_safety(tmp_path):
    import json
    import subprocess
    import sys
    rows = corner()
    for r in rows: r['material_id'] = 1
    source = tmp_path / 'source.json'
    source.write_text(json.dumps(rows))
    report = tmp_path / 'report.json'
    cmd = [sys.executable, '-m', 'tools.materials.course_grid_audit', str(source), str(report), '--material-id', '1']
    run = subprocess.run(cmd, capture_output=True, text=True)
    assert run.returncode == 1, run.stdout + run.stderr
    payload = json.loads(report.read_text())
    assert payload['passed'] is False
    assert len(payload['covered_faces']) == 3
    assert payload['dropped_faces'] == []
    original = source.read_bytes()
    for target in [source, source.parent / '.' / source.name, report]:
        before = target.read_bytes()
        args = cmd.copy()
        args[4] = str(target)
        run = subprocess.run(args, capture_output=True, text=True)
        assert run.returncode == 2, run.stdout + run.stderr
        assert target.read_bytes() == before
        assert source.read_bytes() == original


def test_cli_hardlink_alias_writes_nothing(tmp_path):
    import os
    import subprocess
    import sys
    source = tmp_path / 'source.json'
    source.write_text('[]')
    alias = tmp_path / 'alias.json'
    os.link(source, alias)
    run = subprocess.run([sys.executable, '-m', 'tools.materials.course_grid_audit', str(source), str(alias), '--material-id', '1'], capture_output=True)
    assert run.returncode == 2
    assert source.read_bytes() == alias.read_bytes() == b'[]'


def test_corner_audit_is_not_a_complete_chart_certificate():
    result = audit_corners(corner()[:1], anisotropy_limit=1.02)
    assert result['corners'] == []
    assert result['status'] == 'incomplete'
    assert result['passed'] is False
