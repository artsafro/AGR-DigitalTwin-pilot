"""new-case: approved approximate KPP1 placement, not survey-grade acceptance."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'jobs/KPP1/site-1255/place_package.py'


def load():
    assert SCRIPT.is_file(), 'KPP1 R1 placement and GeoJSON producer missing'
    spec = importlib.util.spec_from_file_location('kpp1_site1255', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_approved_transform_keeps_vpm_local_and_npm_absolute():
    m = load()
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    point = [11., -3., 8.65]
    local = m.transform_point(point, fit, 'vpm')
    absolute = m.transform_point(point, fit, 'npm')
    assert absolute == pytest.approx([local[0] + 8056.143933445407,
                                     local[1] - 9581.26989822931, 179.70])
    assert m.transform_point([0., 0., 0.], fit, 'vpm') == [0., 0., 0.]
    assert local[0] > 0 and local[1] < 0  # no 180-degree alternative
    assert fit['fit_ok'] is False and fit['unique'] is False


@pytest.mark.parametrize('profile', ['vpm', 'npm'])
def test_generated_rigid_distance_probe(profile):
    import math
    import random
    m = load()
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    rng = random.Random(1255)
    for _ in range(100):
        a, b = [[rng.uniform(-40, 40) for _ in range(3)] for _ in range(2)]
        aa, bb = m.transform_point(a, fit, profile), m.transform_point(b, fit, profile)
        assert math.dist(aa, bb) == pytest.approx(math.dist(a, b), abs=3e-12)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
@pytest.mark.parametrize('field', ['point', 'theta_deg', 'zero_abs', 'origin_msk_blender_xy'])
def test_nonfinite_transform_rejected(value, field):
    m = load()
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    point = [0, 0, 0]
    if field == 'point':
        point[0] = value
    elif field == 'origin_msk_blender_xy':
        fit[field][0] = value
    else:
        fit[field] = value
    with pytest.raises(ValueError):
        m.transform_point(point, fit, 'npm')


@pytest.mark.parametrize('point', [[], [1], [1, 2], [1, 2, 3, 4]])
def test_partial_point_rejected(point):
    m = load()
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    with pytest.raises(ValueError):
        m.transform_point(point, fit, 'npm')


def test_unsupported_profile_rejected():
    m = load()
    with pytest.raises(ValueError, match='unsupported'):
        m.transform_point([0, 0, 0], {}, 'ground')


@pytest.mark.parametrize('kind', ['empty', 'partial', 'wrong_hash', 'alias', 'existing', 'alternative'])
def test_preflight_fail_closed_no_writes(tmp_path, kind):
    m = load()
    src = tmp_path / 'src'
    src.mkdir()
    out = tmp_path / 'out'
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    if kind in ('partial', 'wrong_hash'):
        for name in (['SM_Kpp_1.fbx'] if kind == 'partial' else ['SM_Kpp_1.fbx', '0000_Kpp_1_01.fbx', 'SM_Kpp_1.zip']):
            (src / name).write_bytes(b'not approved source')
    if kind == 'alias':
        out = src / '..' / 'src' / 'same'
    if kind == 'existing':
        out.mkdir()
        (out / 'sentinel.partial').write_bytes(b'keep')
    if kind == 'alternative':
        fit['theta_deg'] += 180
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(ValueError):
        m.prepare(src, out, fit)
    after = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert after == before
    assert not out.exists() or kind == 'existing'


def test_fresh_process_alias_exits_nonzero_without_writes(tmp_path):
    import subprocess
    import sys
    src = tmp_path / 'src'
    src.mkdir()
    result = subprocess.run([sys.executable, str(SCRIPT), '--', str(src), str(src)], capture_output=True)
    assert result.returncode != 0
    assert b'aliases source' in result.stderr
    assert list(src.iterdir()) == []


def test_committed_geojson_and_validator_receipts_are_same_run():
    import hashlib
    folder = SCRIPT.parent
    geo_bytes = (folder / 'SM_Kpp_1.geojson').read_bytes()
    doc = json.loads(geo_bytes)
    feature = doc['features'][0]
    assert feature['geometry']['coordinates'] == [8056.144, -9581.270]
    props = feature['properties']
    assert props['FNO_code'] == props['FNO_name'] == ''
    assert (props['h_relief'], props['h_otn'], props['h_abs']) == (171.05, 8.65, 179.70)
    assert load().NOTE in props['other']
    manifest = dict((Path(line[66:]).name, line[:64]) for line in
                    (folder / 'evidence-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines())
    assert hashlib.sha256(geo_bytes).hexdigest() == manifest['SM_Kpp_1.geojson']
    expected = {
        'vpm': {'V003': 'not_run', 'V004': 'review', 'V010': 'not_run', 'V011': 'fail',
                'V012': 'review', 'V013': 'not_run', 'V015': 'not_run', 'V016': 'not_run', 'V017': 'not_run'},
        'npm': {'V001': 'fail', 'V003': 'not_run', 'V004': 'review', 'V014': 'not_run',
                'V015': 'not_run', 'V017': 'not_run'},
    }
    for profile in ('vpm', 'npm'):
        p = folder / f'{profile}-site-v003.validate.json'
        assert hashlib.sha256(p.read_bytes()).hexdigest() == manifest[p.name]
        receipt = json.loads(p.read_text(encoding='utf-8'))
        assert receipt['passed'] is False and receipt['exit_code'] == 1
        assert Path(receipt['target']).parent.name == 'site-v003'
        assert receipt['target_sha256'] == manifest[Path(receipt['target']).name]
        assert {s['id']: s['status'] for s in receipt['stages'] if s['status'] != 'pass'} == expected[profile]
    assert '0000_Kpp_1.zip' in manifest  # territorial placeholder remains explicit


@pytest.mark.parametrize('kind', ['same', 'resolved_alias', 'extension_alias', 'source_alias', 'existing'])
def test_dump_paths_fail_closed_before_blender_import(tmp_path, kind):
    import subprocess
    import sys
    src = tmp_path / 'source.fbx'
    src.write_bytes(b'immutable source')
    npz = tmp_path / 'dump.npz'
    report = tmp_path / 'dump.json'
    if kind == 'same':
        report = npz
    elif kind == 'resolved_alias':
        report = tmp_path / 'unused' / '..' / 'dump.npz'
    elif kind == 'extension_alias':
        npz = tmp_path / 'dump'  # numpy adds .npz to string/Path outputs
        report = tmp_path / 'dump.npz'
    elif kind == 'source_alias':
        report = src
    else:
        npz.write_bytes(b'keep existing dump')
    before = {str(p): p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result = subprocess.run([sys.executable, str(SCRIPT.parent / 'dump_vertices.py'),
                             '--', str(src), str(npz), str(report)], capture_output=True)
    assert result.returncode != 0
    assert b'refusing' in result.stderr
    assert b'No module named' not in result.stderr
    assert {str(p): p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_readback_accounts_for_all_objects_without_promoting_delivery():
    import math
    parity = json.loads((SCRIPT.parent / 'readback-parity.json').read_text())
    attributes = json.loads((SCRIPT.parent / 'readback-attributes.json').read_text())
    assert parity['delivery_passed'] is attributes['delivery_passed'] is False
    assert len(parity['objects']) == len(attributes['objects']) == 8
    assert [(o['profile'], o['name']) for o in parity['objects']] == [
        (o['profile'], o['name']) for o in attributes['objects']]
    assert len(set((o['profile'], o['name']) for o in parity['objects'])) == 8
    for obj in parity['objects']:
        assert math.isfinite(obj['max_export_error_m'])
        assert 0 <= obj['max_export_error_m'] < parity['tolerance_m'] == .002
        assert obj['vertices'] > 0 and obj['triangles'] > 0
    assert sum(o['profile'] == 'vpm' for o in parity['objects']) == 6
    assert sum(o['profile'] == 'npm' for o in parity['objects']) == 2
