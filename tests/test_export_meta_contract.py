"""new-case: strict shared export metadata contract (#1361)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def tool():
    path = ROOT / 'tools/derive/export_meta.py'
    assert path.is_file(), 'shared export_meta validator is missing'
    spec = importlib.util.spec_from_file_location('export_meta_1361', path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_npm_export_emits_contract_on_real_master_copy(tmp_path):
    import hashlib
    import os
    import shutil
    import subprocess
    import sys
    import json
    blender = Path('C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    cold = Path('G:/Мой диск/AGR-evidence/1313-kpp1-cold-run-3')
    source = cold / 'packet-copy-v001/master-r1-v001.blend'
    if not blender.is_file() or not source.is_file():
        pytest.skip('optional real KPP1 master / Blender unavailable')
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    master = inputs / 'master.blend'
    shutil.copyfile(source, master)
    before = hashlib.sha256(master.read_bytes()).hexdigest()
    shutil.copyfile(cold / 'packet-copy-v001/spec.json', inputs / 'spec.json')
    shutil.copytree(cold / 'derive-v001/atlas', inputs / 'atlas')
    # #1505: the evidence atlas predates the master binding; bind the private copy to the copied master
    sys.path.insert(0, str(ROOT))
    from adapters.max.agr_tools import build_manifest as bm
    atlas_json = inputs / 'atlas' / 'npm_atlas.json'
    layout = json.loads(atlas_json.read_text(encoding='utf-8'))
    layout['master'] = bm.atlas_master_binding(master, layout['finishes'])
    atlas_json.write_text(json.dumps(layout), encoding='utf-8')
    output = tmp_path / 'new-export/fbx'
    cmd = [str(blender), '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1',
           '--python', str(ROOT / 'tools/derive/export_npm.py'), '--', str(master), str(inputs / 'spec.json'),
           str(inputs / 'atlas'), str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=180, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    assert (output / 'export_meta.json').is_file(), 'shared NPM export did not emit its metadata contract'
    meta = tool().load_meta(output / 'export_meta.json')
    assert meta['profile'] == 'npm' and meta['address'] == 'Kpp_1'
    assert meta['h_otn_model_max_z_m'] == pytest.approx(8.65, abs=0.00001)
    assert meta['thumbnail'] == 'unknown'
    assert hashlib.sha256(master.read_bytes()).hexdigest() == before
    assert all((output / name).is_file() for name in meta['exported_files'])
    assert meta['master_sha256'] == before
    rec = bm.check_derivation(bm.strict_json(
        (tmp_path / 'new-export/derivation' / (meta['exported_files'][0] + '.derivation.json')).read_bytes()))
    assert rec['master_sha256'] == before


def test_record_export_infers_only_filename_facts_and_preserves_unknowns(tmp_path):
    module = tool()
    fbx = tmp_path / 'SM_Synthetic.fbx'
    fbx.write_bytes(b'synthetic fbx')
    assert hasattr(module, 'record_export'), 'shared exporter metadata producer missing'
    path = module.record_export(fbx, source='synthetic test master', top=3.5)
    data = module.load_meta(path)
    assert data['address'] == 'Synthetic' and data['profile'] == 'vpm'
    assert data['thumbnail'] == 'unknown'
    assert 'question:' in data['provenance']['thumbnail']
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        module.record_export(fbx, source='synthetic', top=3.5)
    assert path.read_bytes() == before and fbx.read_bytes() == b'synthetic fbx'


@pytest.mark.parametrize('top', [float('nan'), float('inf'), -float('inf'), True, None, [], {}])
def test_metadata_nonfinite_or_wrong_top_named(top):
    with pytest.raises(ValueError, match='h_otn_model_max_z_m'):
        tool().validate_meta({'address': 'Synthetic', 'h_otn_model_max_z_m': top, 'thumbnail': 'unknown'})


@pytest.mark.parametrize('field', ['address', 'h_otn_model_max_z_m', 'thumbnail'])
def test_each_required_field_is_named(field):
    data = {'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown'}
    del data[field]
    with pytest.raises(ValueError, match=field):
        tool().validate_meta(data)


def test_explicit_export_naming_facts_for_generic_filename(tmp_path):
    fbx = tmp_path / 'technical.fbx'
    fbx.write_bytes(b'synthetic')
    data = tool().load_meta(tool().record_export(fbx, source='synthetic spec', address='Synthetic_Ground', profile='vpm', top=4.0))
    assert (data['address'], data['profile']) == ('Synthetic_Ground', 'vpm')


def test_legacy_vpm_producer_record_remains_readable():
    data = {'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5, 'thumbnail': 'thumb.jpg',
            'fbx': 'SM_Synthetic.fbx', 'pivot_revit_internal_m': [0, 0, 0],
            'bbox_after_pivot': [[-1, -1, 0], [1, 1, 3.5]],
            'main_tris': 12, 'glass_tris': 0, 'ucx': 0, 'ucx_tris': 0}
    assert tool().validate_meta(data) == data


def test_json_schema_accepts_current_record_and_names_shape_errors():
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT / 'schemas/ExportMeta.schema.json').read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    valid = {'address':'Synthetic', 'h_otn_model_max_z_m':3.5, 'thumbnail':'unknown'}
    assert not list(validator.iter_errors(valid))
    for field in valid:
        broken = dict(valid)
        del broken[field]
        assert any(field in error.message for error in validator.iter_errors(broken))
    assert any('typo' in error.message for error in validator.iter_errors(dict(valid, typo=1)))


@pytest.mark.parametrize('text,field', [
    ('{}','address'), ('null','object'), ('[]','object'),
    ('{"address":"A","address":"B","h_otn_model_max_z_m":1,"thumbnail":"unknown"}', 'address'),
    ('{"address":"A","h_otn_model_max_z_m":NaN,"thumbnail":"unknown"}', 'h_otn_model_max_z_m'),
    ('{"address":"A","h_otn_model_max_z_m":1,"thumbnail":"unknown","profile":"unsupported"}', 'profile'),
])
def test_generated_invalid_metadata_is_never_accepted(tmp_path, text, field):
    path = tmp_path / 'metadata.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match=field):
        tool().load_meta(path)
    assert path.read_text(encoding='utf-8') == text


def test_metadata_unknown_key_is_named():
    with pytest.raises(ValueError, match='h_otn_typo'):
        tool().validate_meta({'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5,
                              'thumbnail': 'unknown', 'h_otn_typo': 3.5})


def test_metadata_missing_field_is_named():
    with pytest.raises(ValueError, match='address'):
        tool().validate_meta({'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown'})
