"""Scope controls for the authorized v015-only surface-budget exception (#371)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v015_surface_exception_does_not_raise_npm_triangle_budget():
    rows = [line for line in (ROOT / 'docs/decisions.md').read_text(encoding='utf-8').splitlines()
            if line.startswith('| D170 |')]
    assert len(rows) == 1, 'record the authorized v015-only exception once'
    row = rows[0]
    for required in ('Vatutino Ground v015 only', '90,000 surface quads', 'D097',
                     '10 mm', '180,000', 'unchanged', '#371'):
        assert required in row, required
    sheet = (ROOT / 'docs/domain/areas/ground-surface.md').read_text(encoding='utf-8')
    assert '[D170]' in sheet
    assert 'Ground surface ≤ 50 000 polygons' in sheet, 'the general surface cap must remain'
    assert 'Ground + GroundEl + Flora ≤ 180 000 triangles' in sheet


def test_pairing_decision_supersedes_90k_without_relaxing_other_gates():
    text = (ROOT / 'docs/decisions.md').read_text(encoding='utf-8')
    rows = [line for line in text.splitlines() if line.startswith('| D157 |')]
    assert len(rows) == 1
    for token in ('supersedes D170', '35 %', 'Ground NPM', '50,000', '180,000', '10 mm', 'D150', 'xView', 'VPM'):
        assert token in rows[0], token
    historical = next(line for line in text.splitlines() if line.startswith('| D170 |'))
    assert 'superseded by D157' in historical
    sheet = (ROOT / 'docs/domain/areas/ground-surface.md').read_text(encoding='utf-8')
    assert '[D157]' in sheet
    assert 'D170 is superseded' in sheet


def test_d157_extension_explicitly_covers_vpm_without_waiving_export_checks():
    text = (ROOT / 'docs/decisions.md').read_text(encoding='utf-8')
    row = next(line for line in text.splitlines() if line.startswith('| D157 |'))
    for token in ('2026-10-21', 'принимаю рекомендации', 'Ground v015 NPM and VPM',
                  'per-slot reasons', '35 %', 'export', '10 mm', '0.002/0.005 m'):
        assert token in row, token
    sheet = (ROOT / 'docs/domain/areas/ground-surface.md').read_text(encoding='utf-8')
    assert 'Ground v015 NPM and VPM pairing [D157]' in sheet
