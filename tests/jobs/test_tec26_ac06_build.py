"""AC06 approved colours and colour-only build regression witnesses."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JOB = ROOT / 'jobs/TEC26-OKS/AC06'
SCRIPTS = ROOT / 'jobs/TEC26-OKS/scripts'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ac06_build_mapping():
    spec = json.loads((JOB / 'vpm_textures.json').read_text())
    fm = load_module('finish_map_ac06', SCRIPTS / 'finish_map.py')
    assert fm.validate_spec(spec, fm.load_kpp())
    gate = json.loads((JOB / 'materials.json').read_text())
    for material in gate['materials']:
        sid = str(material['id'])
        if sid == '12':
            assert spec['glass_handle'] == material['object_handle']
            continue
        rule = spec['source_ids'][sid]
        finish = rule.get('finish', rule.get('above'))
        assert spec['finishes'][finish]['rgb'] == material['swatch_rgb']
    assert spec['source_ids']['10']['below'] == spec['source_ids']['3']['finish']
    assert not spec.get('facade_uv')  # No approved blue wall panels in AC06.
    assert not spec.get('ring_cuts')
    assert set(spec['source_ids']) == {str(i) for i in range(1, 12)}


@pytest.mark.parametrize('sid', [0, 12, 13, 999])
def test_unmapped_id_refused(sid):
    spec = json.loads((JOB / 'vpm_textures.json').read_text())
    fm = load_module('finish_map_ac06', SCRIPTS / 'finish_map.py')
    with pytest.raises(ValueError, match=str(sid)):
        fm.assign_finishes([[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 1, 2]], [sid], spec)
