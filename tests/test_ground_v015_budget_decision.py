"""Scope controls for the authorized v015-only surface-budget exception (#371)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v015_surface_exception_does_not_raise_npm_triangle_budget():
    rows = [line for line in (ROOT / 'docs/decisions.md').read_text(encoding='utf-8').splitlines()
            if line.startswith('| D156 |')]
    assert len(rows) == 1, 'record the authorized v015-only exception once'
    row = rows[0]
    for required in ('Vatutino Ground v015 only', '90,000 surface quads', 'D097',
                     '10 mm', '180,000', 'unchanged', '#371'):
        assert required in row, required
    sheet = (ROOT / 'docs/domain/areas/ground-surface.md').read_text(encoding='utf-8')
    assert '[D156]' in sheet
    assert 'Ground surface ≤ 50 000 polygons' in sheet, 'the general surface cap must remain'
    assert 'Ground + GroundEl + Flora ≤ 180 000 triangles' in sheet
