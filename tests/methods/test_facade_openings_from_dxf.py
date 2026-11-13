"""Pattern: new-case: explicit facade-DXF schedule regression and synthetic adversarial probes."""
import importlib.util
import json
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/methods/body/facade_openings_from_dxf.py'


def load():
    assert TOOL.exists(), 'F16: no reusable facade DXF opening schedule tool'
    spec = importlib.util.spec_from_file_location('facade_schedule', TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(tmp_path):
    doc = ezdxf.new()
    doc.units = 4
    ent = doc.modelspace().add_lwpolyline([(1000, 2000), (2200, 2000), (2200, 3500), (1000, 3500)], close=True)
    note = doc.modelspace().add_text('synthetic')
    source = tmp_path / 'facade.dxf'
    doc.saveas(source)
    config = {'facades': {'north': {'origin_mm': [1000, 1000], 'direction': 1, 'datum_m': 0.5}},
              'openings': [{'id': 'W1', 'kind': 'window', 'facade': 'north', 'handles': [ent.dxf.handle]}],
              'drop': {note.dxf.handle: 'annotation'}}
    mapping = tmp_path / 'map.json'
    mapping.write_text(json.dumps(config), encoding='utf-8')
    return source, mapping, config, doc


def test_facade_schedule(tmp_path):
    source, mapping, config, doc = fixture(tmp_path)
    tool = load()
    result = tool.extract(source, mapping)
    row = result['openings'][0]
    assert {k: row[k] for k in ('id', 'kind', 'facade', 'left_m', 'right_m', 'sill_m', 'head_m', 'width_m', 'height_m')} == {
        'id': 'W1', 'kind': 'window', 'facade': 'north', 'left_m': 0, 'right_m': 1.2,
        'sill_m': 1.5, 'head_m': 3, 'width_m': 1.2, 'height_m': 1.5}
    assert len(result['entities']) == len(doc.modelspace()) == 2
    assert [r['status'] for r in result['entities']] == ['used', 'dropped']
    assert len(result['source']['sha256']) == len(result['mapping']['sha256']) == 64
    assert result['status'] == 'measured' and 'passed' not in result
