"""new-case: package uses explicit project datum, not hand-entered h_relief."""
import json
import sys
import pytest
from test_shared_tools_1106 import make_pkg, make_tex, run, PKG_TOOL


def datum():
    s = {'file': 'R1.rvt', 'locator': 'Level ±0.000 [D262]'}
    return dict(coordinate_system='MSK-77', project_zero_m=171.05, height_system='unknown',
                height_source=s, project_zero_fbx_z_m=-0.3, project_zero_fbx_source=s,
                source={'kind': 'model', 'reference': 'R1.rvt'}, status='proposed')


def test_package_uses_project_datum(tmp_path):
    tex = make_tex(tmp_path / 'tex')
    pkg = make_pkg(tmp_path / 'p')
    meta_path = pkg.parent / 'export_meta.json'
    meta = json.loads(meta_path.read_text())
    meta['h_otn_model_max_z_m'] = 8.35
    meta_path.write_text(json.dumps(meta))
    obj = tmp_path / 'object.json'
    obj.write_text(json.dumps({'name': 'KPP1', 'placement': datum()}))
    result = run([sys.executable, PKG_TOOL, pkg, tex, '--object', obj])
    assert result.returncode == 0, result.stderr
    props = json.loads((pkg / 'SM_Nku_1.geojson').read_text())['features'][0]['properties']
    assert (props['h_relief'], props['h_otn'], props['h_abs']) == (171.05, 8.65, 179.7)


def test_legacy_package_names_missing_datum(tmp_path):
    tex = make_tex(tmp_path / 'tex')
    pkg = make_pkg(tmp_path / 'p')
    obj = tmp_path / 'legacy-object.json'
    obj.write_text(json.dumps({'name': 'KPP1', 'h_relief': 171.05}))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = run([sys.executable, PKG_TOOL, pkg, tex, '--object', obj])
    assert result.returncode != 0
    assert 'legacy-object.json' in result.stderr and 'placement' in result.stderr
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('collision', ['texture', 'geojson'])
def test_package_existing_destination_preserved(tmp_path, collision):
    import os
    tex = make_tex(tmp_path / 'tex')
    pkg = make_pkg(tmp_path / 'p')
    obj = tmp_path / 'object.json'
    obj.write_text(json.dumps({'name': 'KPP1', 'placement': datum()}))
    dest = pkg / ('T_Nku_1_Diffuse_1.1001.png' if collision == 'texture' else 'SM_Nku_1.geojson')
    os.link(obj, dest)
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = run([sys.executable, PKG_TOOL, pkg, tex, '--object', obj])
    assert result.returncode != 0
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_package_duplicate_datum_key(tmp_path):
    tex = make_tex(tmp_path / 'tex')
    pkg = make_pkg(tmp_path / 'p')
    obj = tmp_path / 'object.json'
    raw = json.dumps({'name': 'KPP1', 'placement': datum()})
    obj.write_text(raw.replace('"project_zero_m": 171.05', '"project_zero_m": 169.65, "project_zero_m": 171.05'))
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = run([sys.executable, PKG_TOOL, pkg, tex, '--object', obj])
    assert result.returncode != 0 and 'project_zero_m' in result.stderr
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
