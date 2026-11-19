"""new-case: D288 attribute-only KPP1 VPM package v008 from the delivered customer GeoJSON."""
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'jobs/KPP1/delivered-1371/build_v008.py'
GEOJSON = ROOT / 'jobs/KPP1/package-1278/latest/SM_Kpp_1.geojson'
FIELDS = {'FNO_code': '013 006 005', 'FNO_name': 'Объект электроснабжения иного типа',
          's_obsh': 27124.36, 's_naz': 27124.36, 'spp_gns': 28480.58}


def load():
    assert SCRIPT.is_file(), 'v008 builder missing'
    spec = importlib.util.spec_from_file_location('kpp1_delivered1371', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def zip_bytes(members):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, data in members.items():
            info = zipfile.ZipInfo(name, (2026, 11, 13, 3, 33, 58))
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, data)
    return stream.getvalue()


def delivered_geojson(**override):
    props = {'name': 'whole project', 'FNO_code': '013 006 005',
             'FNO_name': 'Объект электроснабжения иного типа', 'h_relief': 0.26, 'h_otn': 8.95,
             'h_abs': 178.6, 's_obsh': 27124.36, 's_naz': 27124.36, 's_podz': '', 'spp_gns': 28480.58}
    props.update(override)
    doc = {'type': 'FeatureCollection', 'features': [{'type': 'ObjectFeature', 'properties': props}]}
    return json.dumps(doc, ensure_ascii=False, indent=4).encode('utf-8')


def fixture(tmp_path, **override):
    # Synthetic containers for builder tests only; not real delivery fixtures.
    base = tmp_path / 'SM_Kpp_1.zip'
    base.write_bytes(zip_bytes({'SM_Kpp_1.fbx': b'synthetic fbx', 'T_Kpp_1_Diffuse_1.1001.png': b'png',
                                'SM_Kpp_1.geojson': GEOJSON.read_bytes()}))
    delivered = tmp_path / 'SM_77_05_0009005_117_002.zip'
    delivered.write_bytes(zip_bytes({'SM_77_05_0009005_117_002.fbx': b'x',
                                     'SM_77_05_0009005_117_002.geojson': delivered_geojson(**override)}))
    return base, delivered


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(module, base, delivered, out):
    return module.build(base, delivered, out, base_sha=sha(base), delivered_sha=sha(delivered))


def test_only_five_fields_change_and_heights_stay_r1(tmp_path):
    module = load()
    base, delivered = fixture(tmp_path)
    out = tmp_path / 'package-v008'
    run(module, base, delivered, out)
    old, new = zipfile.ZipFile(base), zipfile.ZipFile(out / 'SM_Kpp_1.zip')
    assert old.namelist() == new.namelist()
    for name in old.namelist():
        if name != 'SM_Kpp_1.geojson':
            assert old.read(name) == new.read(name), name
            assert old.getinfo(name).date_time == new.getinfo(name).date_time
    before = json.loads(old.read('SM_Kpp_1.geojson'))['features'][0]['properties']
    after = json.loads(new.read('SM_Kpp_1.geojson'))['features'][0]['properties']
    assert list(before) == list(after)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == set(FIELDS)
    assert {k: after[k] for k in FIELDS} == FIELDS
    assert (after['h_relief'], after['h_otn'], after['h_abs']) == (171.05, 8.65, 179.7)
    assert after['s_podz'] == '' and after['name'] == before['name']
    assert (out / 'SM_Kpp_1.geojson').read_bytes() == new.read('SM_Kpp_1.geojson')
    assert b'\r\n' in new.read('SM_Kpp_1.geojson')
    sums = (out / 'SHA256SUMS.txt').read_text(encoding='utf-8')
    assert sha(out / 'SM_Kpp_1.zip') in sums


@pytest.mark.parametrize('override, needle', [
    ({'FNO_code': ''}, 'FNO_code'),
    ({'s_obsh': ''}, 's_obsh'),
    ({'s_naz': float('nan')}, 's_naz'),
    ({'spp_gns': float('inf')}, 'spp_gns'),
    ({'s_obsh': 27124.365}, 's_obsh'),
    ({'s_obsh': -1.0}, 's_obsh'),
    ({'s_podz': 12.5}, 's_podz'),
    ({'FNO_code': '013 006 004'}, 'FNO'),
])
def test_bad_delivered_values_fail_closed(tmp_path, override, needle):
    module = load()
    base, delivered = fixture(tmp_path, **override)
    out = tmp_path / 'package-v008'
    with pytest.raises(ValueError, match=needle):
        run(module, base, delivered, out)
    assert not out.exists() and not Path(str(out) + '.partial').exists()


def test_missing_delivered_key_is_named(tmp_path):
    module = load()
    base, delivered = fixture(tmp_path)
    doc = json.loads(zipfile.ZipFile(delivered).read('SM_77_05_0009005_117_002.geojson'))
    del doc['features'][0]['properties']['spp_gns']
    delivered.write_bytes(zip_bytes({'SM_77_05_0009005_117_002.geojson':
                                     json.dumps(doc, ensure_ascii=False).encode()}))
    with pytest.raises(ValueError, match='spp_gns'):
        run(module, base, delivered, tmp_path / 'out')


def test_base_already_filled_or_hash_mismatch_fails(tmp_path):
    module = load()
    base, delivered = fixture(tmp_path)
    with pytest.raises(ValueError, match='sha256'):
        module.build(base, delivered, tmp_path / 'o1', base_sha='0' * 64, delivered_sha=sha(delivered))
    with pytest.raises(ValueError, match='sha256'):
        module.build(base, delivered, tmp_path / 'o2', base_sha=sha(base), delivered_sha='0' * 64)
    out = tmp_path / 'v008'
    run(module, base, delivered, out)
    with pytest.raises(ValueError, match='FNO_code'):
        run(module, out / 'SM_Kpp_1.zip', delivered, tmp_path / 'v009')
    assert not (tmp_path / 'v009').exists()


def test_output_aliases_and_existing_output_refused(tmp_path):
    module = load()
    base, delivered = fixture(tmp_path)
    before = (sha(base), sha(delivered))
    for out in (tmp_path, base, delivered, base.parent / '.' / base.name):
        with pytest.raises(ValueError):
            run(module, base, delivered, out)
    existing = tmp_path / 'exists'
    existing.mkdir()
    with pytest.raises(ValueError, match='exists'):
        run(module, base, delivered, existing)
    partial = tmp_path / 'clobber.partial'
    partial.mkdir()
    with pytest.raises(ValueError, match='partial'):
        run(module, base, delivered, tmp_path / 'clobber')
    assert (sha(base), sha(delivered)) == before


def test_cli_fresh_process(tmp_path):
    base, delivered = fixture(tmp_path)
    out = tmp_path / 'cli'
    cmd = [sys.executable, str(SCRIPT), str(base), str(delivered), str(out),
           '--base-sha', sha(base), '--delivered-sha', sha(delivered)]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    assert (out / 'SM_Kpp_1.zip').is_file()
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode != 0 and 'exists' in again.stderr


def test_pinned_defaults_match_real_sources():
    module = load()
    assert module.BASE_SHA256 == '6c6b03b4e12c942eda4bbae4d2a543efc6319f6af770da5a9854ac56e2a0947d'
    assert module.DELIVERED_SHA256.startswith('caef3a21')
    assert not math.isnan(FIELDS['s_obsh'])
