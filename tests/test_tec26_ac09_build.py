"""new-case: AC09 glass/Interior production adapter regression probes."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'jobs/TEC26-OKS/AC09'


@pytest.fixture
def adapter(monkeypatch):
    path = BUILD / 'recipe_adapter.py'
    spec = importlib.util.spec_from_file_location('ac09_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.fm.validate_legend
    monkeypatch.setattr(module.fm, 'validate_legend', original)
    module.install_interior()
    return module


def test_ac09_approved_interior_is_not_fabricated_ral(adapter):
    data = json.loads((BUILD / 'vpm_textures.json').read_text(encoding='utf-8'))
    assert adapter.fm.validate_spec(data, adapter.fm.load_kpp())
    assert data['glass']['source_id'] == 6
    assert sorted(f['ribs'] for f in data['facades'].values()) == [11, 12, 14, 14]


@pytest.mark.parametrize('value', [[0, 0, 0], [], [float('nan'), 25, 28], [25, 25, float('inf')]])
def test_ac09_rejects_invented_interior(adapter, value):
    data = json.loads((BUILD / 'vpm_textures.json').read_text(encoding='utf-8'))
    data['finishes']['Interior']['rgb'] = value
    with pytest.raises(ValueError):
        adapter.fm.validate_spec(data, adapter.fm.load_kpp())


def test_ac09_missing_finish_is_error(adapter):
    data = json.loads((BUILD / 'vpm_textures.json').read_text(encoding='utf-8'))
    data['source_ids']['7']['finish'] = 'unmapped'
    with pytest.raises(ValueError, match='unmapped'):
        adapter.fm.validate_spec(data, adapter.fm.load_kpp())


def test_ac09_unknown_stage_is_error(adapter):
    with pytest.raises(ValueError, match='unsupported'):
        adapter.execute('unknown.py', [])
