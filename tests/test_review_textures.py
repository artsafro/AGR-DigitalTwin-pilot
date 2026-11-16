"""new-case: review-texture gate contract and native saved-file regression (#1365)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/review/review_textures.py'


def load():
    spec = importlib.util.spec_from_file_location('review_textures', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('value', [0.25, 0.5, 1, 2])
def test_joint_sampling(value):
    gate = load()
    row = {'joint_m': 0.01, 'tile_m': 4}
    # 10mm joint over a 4m tile: at 512px it occupies 1.28 texels.
    result = gate.joint_sampling(row, int(512 * value))
    assert result['texels'] == pytest.approx(1.28 * value)
    assert result['status'] == ('pass' if value == 2 else 'review')
    assert gate.joint_sampling({'joint_m': 0.01, 'tile_m': 4}, 800)['status'] == 'review'


@pytest.mark.parametrize('value', [{}, {'ids': []}, {'ids': [{'object': 'Brick', 'id': 1, 'extra': 1}]},
                                  {'ids': [{'object': 'Brick', 'id': True}]},
                                  {'ids': [{'object': '', 'id': 1}]},
                                  {'ids': [{'object': 'Brick', 'id': 0}]},
                                  {'ids': [{'object': 'Brick', 'id': 1}] * 2},
                                  {'ids': [{'object': 'Brick', 'id': 1, 'joint_m': float('nan'), 'tile_m': 4}]},
                                  {'ids': [{'object': 'Brick', 'id': 1, 'joint_m': .01}]},
                                  {'ids': [{'object': 'Brick', 'id': 1}], 'unknown': 1}])
def test_invalid_contract(value):
    with pytest.raises(ValueError):
        load().validate_manifest(value)


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf'), True, '512'])
def test_invalid_viewport_limit(value):
    with pytest.raises(ValueError):
        load().joint_sampling({'joint_m': .01, 'tile_m': 4}, value)


def test_output_protection(tmp_path):
    gate = load()
    source = tmp_path / 'source.blend'
    source.write_bytes(b'source')
    manifest = tmp_path / 'scope.json'
    manifest.write_bytes(b'manifest')
    alias = tmp_path / 'alias.json'
    alias.hardlink_to(source)
    for target in (source, manifest, alias, tmp_path / '.' / 'source.blend'):
        with pytest.raises((ValueError, FileExistsError)):
            gate.write_report(target, {'status': 'pass'}, [source, manifest])
    target = tmp_path / 'report.json'
    target.write_bytes(b'foreign report')
    with pytest.raises(FileExistsError):
        gate.write_report(target, {'status': 'pass'}, [source, manifest])
    assert source.read_bytes() == b'source'
    assert manifest.read_bytes() == b'manifest'
    assert target.read_bytes() == b'foreign report'


@pytest.mark.blender
def test_native_blender_saved_file(tmp_path):
    from dt_ai.core.blender_runner import run_blender
    result = run_blender(ROOT / 'tests/blender/run_review_textures_1365.py',
                         [SCRIPT, tmp_path], output_json=tmp_path / 'native.json',
                         log_path=tmp_path / 'native.log')
    assert result['empty']['status'] == 'fail'
    assert result['linked']['status'] == 'pass'
    assert result['packed']['status'] == 'pass'
    for key in ('missing', 'unlinked', 'wrong_output', 'unknown_id', 'unused_id'):
        assert result[key]['status'] == 'fail', key
    assert result['repeated'] == result['linked']
    assert result['unchanged_sources'] is True
