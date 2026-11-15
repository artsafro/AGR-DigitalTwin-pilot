"""new-case: shared openings source readers and fail-closed manual CLI (#1511).

All generated fixtures are synthetic, not a real building.
"""
import copy
import importlib.util
from pathlib import Path

from adapters.max.agr_tools import openings_core as core

ROOT = Path(__file__).resolve().parents[1]


def test_revit_reader_keeps_latin_c_glass_without_mutating_input(tmp_path):
    path = ROOT / 'tests/jobs/test_kpp1_extract_openings.py'
    spec = importlib.util.spec_from_file_location('kpp1_fixture_1511', path)
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    src, cen = fixture._write(tmp_path, [fixture._glass('Cтеклопакет', 0)])
    import json
    side = json.loads((src / 'curtain.export.json').read_text(encoding='utf-8'))
    groups = {g: json.loads((cen / (g + '.objects.json')).read_text(encoding='utf-8'))
              for g in ('curtain', 'openings')}
    original = copy.deepcopy((side, groups))
    result, dropped = core.read_revit_openings(side, groups, profile='KPP1')
    assert result['S']['surrounds'][0]['bays'][0]['glass'] == [[1.2, 1.6, 0.2, 1.5]]
    assert dropped == []
    assert (side, groups) == original
