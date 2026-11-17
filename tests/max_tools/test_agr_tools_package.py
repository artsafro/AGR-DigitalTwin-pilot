"""new-case: AGR Tools 0.8 branch D (#908): qa.package, export.zip (and the package grammar), plain pytest, no pymxs.

Every named lab defect (docs/experiments/qa.package.md, export.zip.md) has a regression test that is RED on a small
model of the source behaviour (`geoagr_*` below: the behaviour measured in lab L04, not GeoAGR code, #853) and GREEN
on package_core. The models run as strict xfail, so a model that stops failing is itself an error.
The validator runs for real (tools/qa/validate_package.py in this interpreter, as the button runs it via AGR_PYTHON).
"""
import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / 'adapters/max/agr_tools'
sys.path.insert(0, str(ROOT / 'tests' / 'qa'))
from test_validator import geojson as good_geojson  # noqa: E402
from test_validator_corpus_979 import light_fbx  # noqa: E402

sys.path.pop(0)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ec = _load(PKG / 'edit_core.py', 'agr_tools_edit_core_pkg')
pc = _load(PKG / 'package_core.py', 'agr_tools_package_core_t')
FBX = b'Kaydara FBX Binary  \x00\x1a\x00' + struct.pack('<I', 7400) + b'\x00' * 64
PY, RUN = sys.executable, pc.subprocess_runner
LIGHT = light_fbx()
GROUND_LIGHT = light_fbx(root='SM_X_Ground_Root', lights=[('SM_X_Ground_Omni_001', 0)])


def _png(colour):
    b = BytesIO()
    Image.new('RGB', (256, 256), colour).save(b, 'PNG')
    return b.getvalue()


MAPS = {'Diffuse': (120, 110, 100), 'ERM': (0, 170, 0), 'Normal': (128, 128, 255)}


def acceptance_folder(tmp_path):
    """export.zip.md minimal acceptance: NPM (2 parts + Ground), VPM OKS (fbx, _Light, geojson, 3 PNG), VPM Ground
    (same) and decoys SM_X_0011.*, 0123_Other_01.fbx, notes.txt."""
    d = tmp_path / 'delivery'
    d.mkdir()
    files = {'0123_X_01.fbx': FBX, '0123_X_02.fbx': FBX, '0123_X_Ground.fbx': FBX,
             'SM_X.fbx': FBX, 'SM_X_Light.fbx': LIGHT, 'SM_X.geojson': good_geojson(),
             'SM_X_Ground.fbx': FBX, 'SM_X_Ground_Light.fbx': GROUND_LIGHT, 'SM_X_Ground.geojson': good_geojson(),
             'SM_X_0011.fbx': FBX, 'SM_X_0011.geojson': good_geojson(), 'T_X_0011_Diffuse_1.1001.png': _png((1, 2, 3)),
             '0123_Other_01.fbx': FBX, 'notes.txt': b'decoy'}
    for m, c in MAPS.items():
        files['T_X_{}_1.1001.png'.format(m)] = _png(c)
        files['T_X_Ground_{}_1.1001.png'.format(m)] = _png(c)
    for n, data in files.items():
        (d / n).write_bytes(data)
    # Export records are a prerequisite of NPM packaging (#1650). Keep the fixture
    # record outside the delivery inventory so existing decoy assertions stay exact.
    (tmp_path / 'export_meta.json').write_text(json.dumps({
        'address': 'X', 'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown',
        'exported_files': ['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx'],
        'exported_sha256': {n: _sha(d / n) for n in ('0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx')}
    }), encoding='utf-8')
    return d


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate(target):
    return pc.validate(target, RUN, PY, ROOT, profile=None, scene=False)


def _stage(table, sid):
    return next(s for s in table['stages'] if s['id'] == sid)


# ---- source behaviour models (lab L04 measurements; no GeoAGR code) ------------------------------------------
def geoagr_members(names, stem):
    """GeoAGR Archivate All picks VPM members by substring of the set stem (GeoAGR.ms:66292-66305)."""
    return sorted(n for n in names if stem in n and not n.endswith('_Light.fbx'))  # _Light never matches (66307)


def geoagr_npm_archive(names):
    """All NPM FBX of the folder in one archive named after the last _Ground FBX (GeoAGR.ms:66246-66253)."""
    fbx = sorted(n for n in names if n[:4].isdigit() and n.endswith('.fbx'))
    ground = [n for n in fbx if '_Ground' in n]
    return ground[-1].replace('_Ground.fbx', '.zip'), fbx


def geoagr_ground_vpm_ok(size):
    return size < 500 * pc.MIB  # GeoAGR.ms:66340: 500 MiB for Ground too, and exactly 500 MiB fails


def core_members(names, stem):
    plan = pc.classify_folder(names)['vpm'][stem]
    return sorted([plan['fbx']] + ([plan['light']] if plan['light'] else []) + [plan['geojson']] + plan['png'])


def core_npm_archive(names):
    cls = pc.classify_folder(names)
    addr = pc.delivery_address(cls)
    (code,) = [c for c, a in cls['npm'] if a == addr]
    parts = cls['npm'][(code, addr)]
    return '{}_{}.zip'.format(code, addr), sorted(parts.values())


def core_ground_vpm_ok(size):
    return pc.size_status(size, pc.LIMITS['vpm_ground']) == 'pass'


NAMES = sorted(['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx', '0123_Other_01.fbx', 'SM_X_001.fbx',
                'SM_X_001_Light.fbx', 'SM_X_001.geojson', 'SM_X_0011.fbx', 'SM_X_0011.geojson',
                'T_X_001_Diffuse_1.1001.png', 'T_X_0011_Diffuse_1.1001.png', 'T_X_001_ERM_1.1001.png',
                'T_X_001_Normal_1.1001.png'])
MODEL = pytest.param('geoagr', marks=pytest.mark.xfail(strict=True, reason='source behaviour (lab L04)'))


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_members_by_exact_stem_not_substring(impl):
    """export.zip defect 3: SM_X_001 also took SM_X_0011.fbx and its textures."""
    got = (geoagr_members if impl == 'geoagr' else core_members)(NAMES, 'SM_X_001' if impl == 'geoagr' else 'X_001')
    assert not any('0011' in n for n in got)


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_vpm_oks_archive_keeps_its_light_fbx(impl):
    """export.zip defect 2: the extra-FBX filter never matched, so `_Light` was missing from the OKS archive."""
    got = (geoagr_members if impl == 'geoagr' else core_members)(NAMES, 'SM_X_001' if impl == 'geoagr' else 'X_001')
    assert 'SM_X_001_Light.fbx' in got


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_npm_archive_per_address_not_every_fbx_of_the_folder(impl):
    """export.zip defect 4: all NPM FBX of the folder went into one archive (0123_Other_01.fbx too)."""
    name, members = (geoagr_npm_archive if impl == 'geoagr' else core_npm_archive)(NAMES)
    assert name == '0123_X.zip' and '0123_Other_01.fbx' not in members


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_vpm_ground_limit_is_1_gib_and_inclusive(impl):
    """export.zip defect 5: the Ground VPM archive was limited to 500 MiB and exactly 500 MiB failed."""
    ok = geoagr_ground_vpm_ok if impl == 'geoagr' else core_ground_vpm_ok
    assert ok(500 * pc.MIB) and ok(1024 * pc.MIB) and not ok(1024 * pc.MIB + 1)


def test_limits_match_the_standards_in_binary_units():
    import yaml
    npm = yaml.safe_load((ROOT / 'standards/NPM_STANDARD.yaml').read_text(encoding='utf-8'))['archive']
    vpm = yaml.safe_load((ROOT / 'standards/VPM_STANDARD.yaml').read_text(encoding='utf-8'))['archive']
    assert pc.LIMITS == {'npm': npm['max_bytes'], 'vpm_oks': vpm['oks_max_bytes'], 'vpm_ground': vpm['ground_max_bytes']}
    for limit in pc.LIMITS.values():
        assert [pc.size_status(n, limit) for n in (limit - 1, limit, limit + 1)] == ['pass', 'pass', 'fail']


def test_writer_is_in_process_without_an_external_archiver():
    """export.zip defect 1: the bundled 7-Zip without its codec library created nothing and its exit code was unread."""
    src = (PKG / 'package_core.py').read_text(encoding='utf-8')
    assert 'import zipfile' in src and '7z' not in src.replace('7-Zip', '') and 'Popen' not in src


# ---- export.zip acceptance (export.zip.md "Minimal acceptance test") -----------------------------------------
def test_export_zip_acceptance(tmp_path):
    d = acceptance_folder(tmp_path)
    before = {p.name: _sha(p) for p in d.iterdir()}
    p = pc.zip_preview(ec, d)
    assert p['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip'] and p['status'] == 'pass'
    assert sorted(os.listdir(d)) == sorted(before)  # preview writes nothing
    skipped = {s['item']: s['reason'] for s in p['plan']['skipped']}
    assert set(skipped) == {'SM_X_0011.fbx', 'SM_X_0011.geojson', 'T_X_0011_Diffuse_1.1001.png',
                            '0123_Other_01.fbx', 'notes.txt'}
    assert '3 digits' in skipped['SM_X_0011.fbx'] and 'not the delivery address X' in skipped['0123_Other_01.fbx']

    ec.check_preview('export.zip', p)
    r = pc.zip_apply(ec, p, _validate, stamp='20261105_120000')
    assert r['status'] == 'pass', r['objects']
    assert r['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip']
    run = Path(r['plan']['run_folder'])
    assert run.parent == d and run.name == 'Сборка_20261105_120000' and r['plan']['marker'] == pc.MARK_FAIL
    assert sorted(set(os.listdir(d)) - set(before)) == [run.name]  # the delivery folder gets only the run folder
    assert sorted(os.listdir(run)) == sorted(
        r['plan']['done'] + [n + suffix for n in r['plan']['done']
                            for suffix in ('.validation.json', '.delivery.json')] + ['report.json', pc.MARK_FAIL])
    assert json.loads((run / 'report.json').read_text(encoding='utf-8')) == r
    with zipfile.ZipFile(run / 'SM_X.zip') as z:
        names = z.namelist()
    assert 'SM_X_Light.fbx' in names and not any('0011' in n for n in names)
    with zipfile.ZipFile(run / 'SM_X_Ground.zip') as z:
        assert sorted(z.namelist()) == sorted(['SM_X_Ground.fbx', 'SM_X_Ground_Light.fbx', 'SM_X_Ground.geojson'] +
                                              ['T_X_Ground_{}_1.1001.png'.format(m) for m in MAPS])
    with zipfile.ZipFile(run / '0123_X.zip') as z:
        assert sorted(z.namelist()) == ['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx']
    assert {n: _sha(d / n) for n in before} == before  # decoys and sources untouched
    for table in r['plan']['reports']:
        v001 = _stage(table, 'V001')  # #1423: no build manifest beside these ZIPs -> not_run, nothing else open
        assert v001['status'] == 'not_run' and v001['non_pass'] and all(
            f.startswith('not_run: build manifest:') for f in v001['non_pass']), table
        assert _stage(table, 'V012')['status'] != 'fail', table  # VPM OKS name is review (conflict #20)

    # a second run never touches the first: a new run folder, the earlier one is reported as a folder, not packed
    stamp = {p_.name: _sha(p_) for p_ in run.iterdir()}
    p2 = pc.zip_preview(ec, d)
    assert p2['plan']['done'] == p['plan']['done']
    assert any(s['item'] == run.name and 'never packed' in s['reason'] for s in p2['plan']['skipped'])
    r2 = pc.zip_apply(ec, p2, _validate, stamp='20261105_120000')
    assert Path(r2['plan']['run_folder']).name == 'Сборка_20261105_120000_2'
    assert {p_.name: _sha(p_) for p_ in run.iterdir()} == stamp


def _complete_validator_table(table, target):
    """Synthetic complete report; literal profile inventory independent of package_core."""
    import copy
    profile = 'npm' if Path(target).name.startswith('0123_') else 'vpm'
    numbers = ([1, 2, 3, 4, 5, 6, 12, 14, 15, 17] if profile == 'npm'
               else [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17])
    overrides = {s['id']: s for s in table['stages']}
    stages = []
    for number in numbers:
        sid = 'V{:03d}'.format(number)
        stage = copy.deepcopy(overrides.get(sid, {
            'id': sid, 'check': sid, 'gate': 'blocking', 'status': 'pass'}))
        stage['findings'] = [
            {'status': stage['status'], 'name': 'synthetic', 'observed': code, 'data': {'code': code}}
            for code in stage.get('codes', []) + stage.get('open_codes', [])]
        stages.append(stage)
    full = {'profile': profile, 'target': str(target), 'exit_code': table['exit_code'],
            'target_sha256': _sha(Path(target)) if Path(target).is_file() else '0' * 64,
            'stages': stages, 'notes': ['Synthetic marker-policy fixture, not measured validation.']}
    result = pc.stage_table(full)
    result['validation_report'] = full
    return result


@pytest.mark.parametrize('defect', ['missing_report', 'partial_stages'])
def test_ready_requires_full_report_and_stage_inventory(tmp_path, defect):
    d = acceptance_folder(tmp_path)

    def validator(target):
        table = _complete_validator_table({'exit_code': 0, 'stages': []}, target)
        if defect == 'missing_report':
            del table['validation_report']
        else:
            table['exit_code'] = 2
            table['stages'] = [{'id': 'V015', 'check': 'review', 'gate': 'manual_review',
                                'status': 'review', 'non_pass': [], 'codes': [], 'open_codes': []}]
        return table

    try:
        pc.zip_apply(ec, pc.zip_preview(ec, d), validator)
    except ValueError:
        pass
    (run,) = d.glob(pc.RUN_PREFIX + '*')
    assert not (run / pc.MARK_OK).exists()
    text = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    assert '0123_X.zip' in text
    assert ('validation_report' if defect == 'missing_report' else 'V001') in text


@pytest.mark.parametrize('profile', ['npm', 'vpm'])
@pytest.mark.parametrize('number', range(1, 18))
def test_every_missing_or_wrong_profile_stage_refuses_ready(tmp_path, profile, number):
    d = acceptance_folder(tmp_path)
    # Select one profile so both independent profile inventories are attacked.
    for path in list(d.iterdir()):
        if path.name.startswith('0123_') != (profile == 'npm'):
            path.unlink()
    before = {path.name: path.read_bytes() for path in d.iterdir()}
    sid = 'V{:03d}'.format(number)

    def validator(target):
        table = _complete_validator_table({'exit_code': 0, 'stages': []}, target)
        ids = [stage['id'] for stage in table['stages']]
        if sid in ids:
            table['stages'] = [stage for stage in table['stages'] if stage['id'] != sid]
        else:
            table['stages'].append({'id': sid, 'check': sid, 'gate': 'blocking', 'status': 'pass'})
        return table

    with pytest.raises(ValueError, match='stage inventory'):
        pc.zip_apply(ec, pc.zip_preview(ec, d), validator)
    (run,) = d.glob(pc.RUN_PREFIX + '*')
    assert not (run / pc.MARK_OK).exists()
    text = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    assert 'stage inventory' in text
    assert ('0123_X.zip' if profile == 'npm' else 'SM_X.zip') in text
    assert {path.name: path.read_bytes() for path in d.iterdir() if path.is_file()} == before


@pytest.mark.parametrize('defect', ['duplicate', 'unknown', 'wrong_report_profile', 'report_stages',
                                   'report_status', 'empty_report', 'unwritable_report'])
def test_validator_evidence_counterexamples_fail_closed(tmp_path, monkeypatch, defect):
    import builtins
    import copy
    d = acceptance_folder(tmp_path)
    original_open = builtins.open

    def guarded_open(path, *args, **kwargs):
        if str(path).endswith('.validation.json'):
            raise OSError('synthetic sidecar write failure')
        return original_open(path, *args, **kwargs)

    if defect == 'unwritable_report':
        monkeypatch.setattr(builtins, 'open', guarded_open)

    def validator(target):
        table = _complete_validator_table({'exit_code': 0, 'stages': []}, target)
        if defect == 'duplicate':
            table['stages'].append(copy.deepcopy(table['stages'][0]))
        elif defect == 'unknown':
            table['stages'][0]['id'] = 'V999'
        elif defect == 'wrong_report_profile':
            table['validation_report']['profile'] = 'vpm'
        elif defect == 'report_stages':
            table['validation_report']['stages'].pop()
        elif defect == 'report_status':
            table['validation_report']['stages'][0]['status'] = 'fail'
        elif defect == 'empty_report':
            table['validation_report'] = {}
        return table

    with pytest.raises((ValueError, OSError)):
        pc.zip_apply(ec, pc.zip_preview(ec, d), validator)
    (run,) = d.glob(pc.RUN_PREFIX + '*')
    assert not (run / pc.MARK_OK).exists()
    assert (run / pc.MARK_FAIL).exists()


def test_synthetic_profile_inventories_match_locked_validator():
    from twinqa.profiles import expected_stages, read_snapshot, snapshot_validator
    spec = snapshot_validator(read_snapshot())
    for profile, target in [('npm', '0123_X.zip'), ('vpm', 'SM_X.zip')]:
        table = _complete_validator_table({'exit_code': 0, 'stages': []}, target)
        assert [stage['id'] for stage in table['stages']] == [sid for sid, _, _ in expected_stages(spec, profile)]


def test_exit_two_never_writes_ready_and_names_open_codes(tmp_path):
    d = acceptance_folder(tmp_path)
    table = {'exit_code': 2, 'stages': [
        {'id': 'V001', 'check': 'manifest', 'gate': 'blocking', 'status': 'not_run',
         'non_pass': ['not_run: build manifest: missing'], 'codes': [], 'open_codes': ['manifest_missing']} ]}
    r = pc.zip_apply(ec, pc.zip_preview(ec, d), lambda target: _complete_validator_table(table, target))
    run = Path(r['plan']['run_folder'])
    assert not (run / pc.MARK_OK).exists()
    assert 'manifest_missing' in (run / pc.MARK_FAIL).read_text(encoding='utf-8')


@pytest.mark.parametrize('exit_code', [0, 2])
def test_manual_reviews_only_ready_with_explicit_pending_line(tmp_path, exit_code):
    table = {'exit_code': exit_code, 'stages': [
        {'id': sid, 'check': 'review', 'gate': 'manual_review', 'status': 'review',
         'non_pass': ['review: acceptance: pending'], 'codes': [], 'open_codes': []}
        for sid in ('V015', 'V016', 'V017')]}
    r = pc.zip_apply(ec, pc.zip_preview(ec, acceptance_folder(tmp_path)), lambda target: _complete_validator_table(table, target))
    text = (Path(r['plan']['run_folder']) / pc.MARK_OK).read_text(encoding='utf-8')
    assert 'ждут ручной приёмки Артёма: V015, V016, V017' in text


def test_full_validator_report_next_to_every_zip(tmp_path):
    from twinqa.report import read_stored_report
    r = pc.zip_apply(ec, pc.zip_preview(ec, acceptance_folder(tmp_path)), _validate)
    run = Path(r['plan']['run_folder'])
    for name in r['plan']['done']:
        stored = read_stored_report((run / (name + '.validation.json')).read_bytes())
        assert stored['target_sha256'] == _sha(run / name)
        assert stored['target'] == str(run / name)
        assert 'manifest_missing' in _stage(pc.stage_table(stored), 'V001')['open_codes']
    source = run / r['plan']['done'][0]
    copy = tmp_path / 'modified-copy.zip'
    copy.write_bytes(source.read_bytes() + b'modified copy')
    output = tmp_path / 'rechecked.json'
    proc = subprocess.run([PY, str(ROOT / 'tools/qa/validate_package.py'), '--recheck',
                           str(source) + '.validation.json', '--recheck-target', str(copy),
                           '--output', str(output), '--json'], capture_output=True)
    assert proc.returncode == 4, proc.stderr.decode('utf-8', errors='replace')
    checked = json.loads(output.read_bytes())
    assert checked['target'] == str(copy) and checked['status'] == 'evidence_missing'
    assert checked['target_sha256_now'] == _sha(copy) != checked['target_sha256_then']


def test_no_validator_writes_error(tmp_path):
    r = pc.zip_apply(ec, pc.zip_preview(ec, acceptance_folder(tmp_path)))
    run = Path(r['plan']['run_folder'])
    assert not (run / pc.MARK_OK).exists()
    assert 'validate_fn=None' in (run / pc.MARK_FAIL).read_text(encoding='utf-8')


def test_second_zip_exit_two_named_in_error(tmp_path):
    d = acceptance_folder(tmp_path)
    for f in d.glob('SM_X_Ground*'):
        f.unlink()
    for f in d.glob('T_X_Ground*'):
        f.unlink()
    calls = []

    def validator(target):
        calls.append(Path(target).name)
        status = 'pass' if len(calls) == 1 else 'not_run'
        return _complete_validator_table({'exit_code': 0 if status == 'pass' else 2, 'stages': [
            {'id': 'V001', 'check': 'manifest', 'gate': 'blocking', 'status': status,
             'non_pass': [], 'codes': [], 'open_codes': ['manifest_missing'] if status == 'not_run' else []}]}, target)

    r = pc.zip_apply(ec, pc.zip_preview(ec, d), validator)
    assert calls == ['0123_X.zip', 'SM_X.zip']
    run = Path(r['plan']['run_folder'])
    assert not (run / pc.MARK_OK).exists()
    text = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    assert 'SM_X.zip: validator exit 2 (V001 [manifest_missing])' in text


@pytest.mark.parametrize('exit_code', [0, 1, 2])
@pytest.mark.parametrize('auto_status', ['pass', 'not_run', 'review', 'fail', 'unsupported'])
@pytest.mark.parametrize('manual_status', ['pass', 'not_run', 'review', 'fail'])
def test_marker_generated_status_matrix(tmp_path, exit_code, auto_status, manual_status):
    # Independent 60-case oracle: fail/unknown/automatic-open never becomes ready.
    table = {'exit_code': exit_code, 'stages': [
        {'id': sid, 'check': sid, 'gate': gate, 'status': status,
         'non_pass': [], 'codes': ['bad'] if status == 'fail' else [],
         'open_codes': ['pending'] if status in ('review', 'not_run') else []}
        for sid, gate, status in [('V001', 'blocking', auto_status), ('V015', 'manual_review', manual_status)]]}
    d = acceptance_folder(tmp_path)
    before = {f.name: f.read_bytes() for f in d.iterdir()}
    r = pc.zip_apply(ec, pc.zip_preview(ec, d), lambda target: _complete_validator_table(table, target))
    run = Path(r['plan']['run_folder'])
    expected = (auto_status == 'pass' and manual_status != 'fail' and
                (exit_code == 0 or (exit_code == 2 and manual_status in ('review', 'not_run'))))
    assert (run / pc.MARK_OK).exists() is expected
    assert (run / pc.MARK_FAIL).exists() is not expected
    assert {f.name: f.read_bytes() for f in d.iterdir() if f.is_file()} == before


@pytest.mark.parametrize('table', [None, {}, {'exit_code': 0, 'stages': []},
    {'exit_code': False, 'stages': [{'id': 'V001', 'status': 'pass'}]},
    {'exit_code': float('nan'), 'stages': []}, {'exit_code': float('inf'), 'stages': []},
    {'exit_code': 0, 'stages': [{'id': 'V001', 'status': 'pass'}]}])
def test_invalid_validator_result_cannot_write_ready(tmp_path, table):
    d = acceptance_folder(tmp_path)
    try:
        pc.zip_apply(ec, pc.zip_preview(ec, d), lambda _: table)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    (run,) = d.glob(pc.RUN_PREFIX + '*')
    assert not (run / pc.MARK_OK).exists()
    assert (run / pc.MARK_FAIL).exists()


def test_stale_preview_writes_nothing(tmp_path):
    d = acceptance_folder(tmp_path)
    p = pc.zip_preview(ec, d)
    (d / 'SM_X_Light.fbx').write_bytes(FBX + b'\x01')
    with pytest.raises(ec.StalePreview):
        pc.zip_apply(ec, p, _validate)
    assert not list(d.rglob('*.zip')) and not list(d.rglob('*.partial')) and not list(d.glob('Сборка_*'))


def test_over_limit_archives_are_flagged_and_not_written(tmp_path):
    """500 MiB + 1 B OKS and 1 GiB + 1 B Ground: the limits are scaled down here, the comparison is the same.
    The run folder then gets ОШИБКА.txt, never ГОТОВО.txt (AGR_Arxiv contract)."""
    d = acceptance_folder(tmp_path)
    limits = {'vpm_oks': 200, 'vpm_ground': 300}
    p = pc.zip_preview(ec, d, limits=limits)
    r = pc.zip_apply(ec, p, _validate, limits=limits)
    assert r['plan']['done'] == ['0123_X.zip'] and r['status'] == 'fail'
    flagged = {o['name']: o['findings'][0]['code'] for o in r['objects'] if o['findings']}
    assert flagged == {'SM_X.zip': 'size', 'SM_X_Ground.zip': 'size'}
    run = Path(r['plan']['run_folder'])
    assert sorted(x.name for x in run.glob('*.zip')) == ['0123_X.zip'] and not list(d.rglob('*.partial'))
    assert r['plan']['marker'] == 'ОШИБКА.txt' and (run / 'ОШИБКА.txt').is_file()
    assert not (run / 'ГОТОВО.txt').exists()
    assert 'SM_X.zip' in (run / 'ОШИБКА.txt').read_text(encoding='utf-8')


# ---- export.zip rework (#979): AGR Zipper v2.1 / AGR_Arxiv 1.5 -------------------------------------------------
DECOYS = ['../SM_X.geojson', 'C:/abs/SM_X_Light.fbx', 'SM_X.fbx\x00../escape', 'SM_X_sub/SM_X.fbx']


def zipper_member_ok(name):
    """AGR Zipper v2.1 (T06/agr_zipper_2506, measured): members judged by basename; zipfile cuts a NUL name."""
    return bool(pc.VPM_FILE.match(os.path.basename(name.split('\x00')[0])))


def core_member_ok(name):
    return pc.member_problem(name) is None


@pytest.mark.parametrize('impl', [pytest.param('zipper', marks=pytest.mark.xfail(
    strict=True, reason='source behaviour (T06/agr_zipper_2506)')), 'core'])
def test_unsafe_member_names_are_refused(impl):
    """export.zip T06 defects: `../`, absolute names, NUL and nested VPM folders passed the Zipper."""
    ok = zipper_member_ok if impl == 'zipper' else core_member_ok
    assert not any(ok(n) for n in DECOYS)


def test_each_unsafe_member_has_its_own_code():
    assert [pc.member_problem(n)[0] for n in DECOYS] == ['member_traversal', 'member_absolute', 'member_nul',
                                                         'member_nested']
    assert pc.member_problem('SM_X.fbx') is None and pc.member_problem('')[0] == 'member_empty'


def test_unsafe_members_refused_before_any_write(tmp_path, monkeypatch):
    """A plan that still carries an unsafe member (any route) is refused before the run folder or a ZIP exists."""
    d = acceptance_folder(tmp_path)
    p = pc.zip_preview(ec, d)
    real = pc.zip_plan

    def poisoned(*a, **k):
        plan = real(*a, **k)
        plan['archives'][1]['members'].append({'name': '../SM_X.geojson', 'bytes': 1, 'mtime_ns': 0})
        return plan
    monkeypatch.setattr(pc, 'zip_plan', poisoned)
    monkeypatch.setattr(ec, 'require_current', lambda preview, state: None)
    with pytest.raises(ValueError, match='member_traversal'):
        pc.zip_apply(ec, p, _validate)
    assert not list(d.glob('Сборка_*')) and not list(d.rglob('*.zip'))


def test_nested_vpm_folder_is_reported_not_packed(tmp_path):
    d = acceptance_folder(tmp_path)
    (d / 'SM_X_sub').mkdir()
    (d / 'SM_X_sub' / 'SM_X.fbx').write_bytes(FBX)
    p = pc.zip_preview(ec, d)
    assert any(s['item'] == 'SM_X_sub' and 'nested VPM folders' in s['reason'] for s in p['plan']['skipped'])
    r = pc.zip_apply(ec, p, _validate)
    for z in Path(r['plan']['run_folder']).glob('*.zip'):
        with zipfile.ZipFile(z) as f:
            assert all('/' not in n and '\\' not in n for n in f.namelist())


def test_existing_zip_in_the_delivery_folder_is_untouched(tmp_path):
    d = acceptance_folder(tmp_path)
    (d / 'SM_X.zip').write_bytes(b'old archive')
    p = pc.zip_preview(ec, d)
    assert any(s['item'] == 'SM_X.zip' for s in p['plan']['skipped'])
    r = pc.zip_apply(ec, p, _validate, stamp='20261105_130000')
    assert (d / 'SM_X.zip').read_bytes() == b'old archive'
    assert (Path(r['plan']['run_folder']) / 'SM_X.zip').read_bytes() != b'old archive'


def test_marker_is_error_when_a_run_stops(tmp_path, monkeypatch):
    d = acceptance_folder(tmp_path)
    p = pc.zip_preview(ec, d)

    def boom(target):
        raise RuntimeError('validator crashed')
    with pytest.raises(RuntimeError, match='validator crashed'):
        pc.zip_apply(ec, p, boom, stamp='20261105_140000')
    run = d / 'Сборка_20261105_140000'
    assert (run / 'ОШИБКА.txt').is_file() and not (run / 'ГОТОВО.txt').exists()
    assert 'validator crashed' in (run / 'ОШИБКА.txt').read_text(encoding='utf-8')


def test_run_folder_goes_to_options_out(tmp_path):
    d = acceptance_folder(tmp_path)
    out = tmp_path / 'out'
    out.mkdir()
    p = pc.zip_preview(ec, d, options={'out': str(out)})
    r = pc.zip_apply(ec, p, _validate)
    assert Path(r['plan']['run_folder']).parent == out and (Path(r['plan']['run_folder']) / pc.MARK_FAIL).is_file()
    with pytest.raises(ValueError, match='no such output folder'):
        pc.zip_apply(ec, pc.zip_preview(ec, d, options={'out': str(tmp_path / 'nope')}), _validate)


@pytest.mark.parametrize('missing_records', [False, True])
def test_npm_binding_failure_does_not_change_vpm_outputs(tmp_path, missing_records):
    d = acceptance_folder(tmp_path)
    if missing_records:
        (tmp_path / 'export_meta.json').unlink()
    else:
        (d / '0123_X_03.fbx').write_bytes(b'synthetic foreign FBX')
    rep = pc.zip_apply(ec, pc.zip_preview(ec, d))
    run = Path(rep['plan']['run_folder'])
    assert sorted(p.name for p in run.glob('*.zip')) == ['SM_X.zip', 'SM_X_Ground.zip']
    error = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    assert ('0123_X_01.fbx' if missing_records else '0123_X_03.fbx') in error
    assert not list(run.glob('*.partial')) and not (run / pc.MARK_OK).exists()


@pytest.mark.parametrize('vpm_mask', range(4))
@pytest.mark.parametrize('records', ['sidecars', 'aggregate'])
@pytest.mark.parametrize('mode', ['clean', 'foreign', 'edited', 'drift'])
def test_mixed_profile_records_bind_only_npm(tmp_path, monkeypatch, records, mode, vpm_mask):
    """Synthetic review regression: VPM records never enter the NPM binding."""
    from adapters.max.agr_tools.export_meta import record_export
    d = acceptance_folder(tmp_path)
    npm = ['0123_X_01.fbx', '0123_X_02.fbx', '0123_X_Ground.fbx']
    vpm = ['SM_X.fbx', 'SM_X_Ground.fbx']
    for name in npm:
        record_export(d / name, source='synthetic mixed-profile fixture')
    for bit, name in enumerate(vpm):
        if vpm_mask & (1 << bit):
            record_export(d / name, source='synthetic mixed-profile fixture', profile='unknown')
    # A VPM-profile record outside this run's planned archives is not an NPM claim.
    record_export(d / 'SM_X_0011.fbx', source='synthetic VPM decoy', profile='vpm')
    address = tmp_path / 'export_meta.json'
    if records == 'sidecars':
        address.unlink()  # exercise address discovery, not just record filtering
    else:
        meta = json.loads(address.read_text(encoding='utf-8'))
        meta['exported_files'] += vpm
        meta['exported_sha256'].update({n: _sha(d / n) for n in vpm})
        (d / 'export_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    if mode == 'foreign':
        (d / '0123_X_03.fbx').write_bytes(b'synthetic foreign')
    elif mode == 'edited':
        (d / npm[0]).write_bytes(b'synthetic edited')
    preview = pc.zip_preview(ec, d)
    expected = {a['name']: {m['name']: (d / m['name']).read_bytes() for m in a['members']}
                for a in preview['plan']['archives']}
    write = pc._write_zip
    def drift(folder, archive, target, **kwargs):
        if archive['role'] == 'npm':
            (d / npm[0]).write_bytes(b'synthetic changed after binding')
        return write(folder, archive, target, **kwargs)
    if mode == 'drift':
        monkeypatch.setattr(pc, '_write_zip', drift)
        with pytest.raises(ValueError, match=npm[0]):
            pc.zip_apply(ec, preview)
        run = next(d.glob('Сборка_*'))
    else:
        rep = pc.zip_apply(ec, preview)
        run = Path(rep['plan']['run_folder'])
        assert sorted(p.name for p in run.glob('*.zip')) == sorted(
            ['SM_X.zip', 'SM_X_Ground.zip'] + (['0123_X.zip'] if mode == 'clean' else []))
    for target in run.glob('*.zip'):
        with zipfile.ZipFile(target) as z:
            assert {n: z.read(n) for n in z.namelist()} == expected[target.name]
    error = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    if mode != 'clean':
        assert ('0123_X_03.fbx' if mode == 'foreign' else npm[0]) in error
        assert not (run / '0123_X.zip').exists()
    assert not list(run.glob('*.partial')) and not (run / pc.MARK_OK).exists()


@pytest.mark.parametrize('failure', ['loader', 'malformed'])
def test_npm_metadata_errors_are_archive_problems(tmp_path, monkeypatch, failure):
    d = acceptance_folder(tmp_path)
    if failure == 'loader':
        import importlib.util
        original = importlib.util.spec_from_file_location
        def broken(name, *args, **kwargs):
            if name == 'agr_tools_export_meta':
                raise ImportError('synthetic unavailable export_meta.py')
            return original(name, *args, **kwargs)
        monkeypatch.setattr(importlib.util, 'spec_from_file_location', broken)
    else:
        meta = json.loads((tmp_path / 'export_meta.json').read_text(encoding='utf-8'))
        meta['profile'] = []  # unsupported value must be reported, not escape to caller
        (tmp_path / 'export_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    rep = pc.zip_apply(ec, pc.zip_preview(ec, d))
    run = Path(rep['plan']['run_folder'])
    assert sorted(p.name for p in run.glob('*.zip')) == ['SM_X.zip', 'SM_X_Ground.zip']
    text = (run / pc.MARK_FAIL).read_text(encoding='utf-8')
    assert '0123_X_01.fbx' in text and 'metadata unavailable or invalid' in text
    assert not list(run.glob('*.partial')) and not (run / pc.MARK_OK).exists()


def test_npm_archive_holds_only_fbx_and_one_address(tmp_path):
    """Zipper 25.06 rules: «в НПМ только FBX» and one Address across the files of an archive."""
    d = acceptance_folder(tmp_path)
    (d / '0123_X_preview.png').write_bytes(_png((1, 1, 1)))
    p = pc.zip_preview(ec, d)
    npm = next(a for a in p['plan']['archives'] if a['role'] == 'npm')
    assert all(m['name'].endswith('.fbx') and '_X_' in m['name'] for m in npm['members'])
    assert any(s['item'] == '0123_X_preview.png' for s in p['plan']['skipped'])


def test_no_pickle_ipc_or_network_in_the_packer():
    """Zipper defect: a localhost listener unpickled any bytes (code execution). The packer has no IPC at all."""
    src = (PKG / 'package_core.py').read_text(encoding='utf-8')
    assert 'pickle' not in src and 'socket' not in src


def test_mixed_addresses_and_codes_are_refused(tmp_path):
    d = tmp_path / 'mixed'
    d.mkdir()
    for n in ('0123_X_01.fbx', '0123_X_Ground.fbx', '0123_Y_01.fbx', '0123_Y_Ground.fbx'):
        (d / n).write_bytes(FBX)
    with pytest.raises(ValueError, match='mixed addresses'):
        pc.zip_preview(ec, d)
    assert pc.zip_preview(ec, d, address='Y')['plan']['done'] == ['0123_Y.zip']
    (d / '0124_X_Ground.fbx').write_bytes(FBX)
    p = pc.zip_preview(ec, d, address='X')
    assert p['plan']['done'] == [] and any('mixed territory codes' in s['reason'] for s in p['plan']['skipped'])


def test_npm_parts_need_ground_and_no_gaps(tmp_path):
    d = tmp_path / 'gaps'
    d.mkdir()
    for n in ('0123_X_01.fbx', '0123_X_03.fbx', '0123_X_Ground.fbx', '0123_X__Ground.fbx'):
        (d / n).write_bytes(FBX)
    p = pc.zip_preview(ec, d)
    (obj,) = p['objects']
    assert 'without gaps' in obj['findings'][0]['detail'] and p['plan']['done'] == []
    assert any(s['item'] == '0123_X__Ground.fbx' for s in p['plan']['skipped'])  # A101 double underscore


def test_address_with_underscores_and_digits(tmp_path):
    d = tmp_path / 'nansena'
    d.mkdir()
    for n in ('0313_ProezdNansena_ZU_8_01.fbx', '0313_ProezdNansena_ZU_8_Ground.fbx'):
        (d / n).write_bytes(FBX)
    p = pc.zip_preview(ec, d)
    assert p['plan']['address'] == 'ProezdNansena_ZU_8' and p['plan']['done'] == ['0313_ProezdNansena_ZU_8.zip']


# ---- qa.package ----------------------------------------------------------------------------------------------
def _npm_zip(folder, name, members):
    path = folder / name
    with zipfile.ZipFile(path, 'w') as z:
        for n, data in members:
            z.writestr(n, data)
    return path


def test_qa_package_default_scene_and_stage_table(tmp_path):
    argv = pc.validator_argv(PY, ROOT, tmp_path / '0127_X.zip')
    assert argv[-2:] == ['--json', '--scene'] and '--profile' not in argv
    assert pc.validator_argv(PY, ROOT, 'a.zip', 'npm', scene=False)[-2:] == ['--profile', 'npm']


def test_qa_package_stray_png_report(tmp_path):
    """qa.package acceptance: 0127_X.zip + stray PNG without --profile -> NPM, V001 'foreign files: preview.png';
    exit code and the V001-V017 stage table in the report."""
    z = _npm_zip(tmp_path, '0127_X.zip', [('0127_X_01.fbx', FBX), ('0127_X_Ground.fbx', FBX),
                                          ('preview.png', _png((1, 1, 1)))])
    r = pc.qa_package(ec, z, RUN, PY, ROOT, scene=False)
    (table,) = r['plan']['reports']
    assert table['profile'] == 'npm' and table['exit_code'] == 1 == r['plan']['exit_code']
    assert [s['id'] for s in table['stages']][0] == 'V001' and len(table['stages']) >= 10
    assert any('foreign files: preview.png' in f for f in _stage(table, 'V001')['non_pass'])
    (obj,) = r['objects']
    assert obj['name'] == '0127_X.zip' and 'V001' in [f['code'] for f in obj['findings']] and r['status'] == 'fail'
    assert r['plan']['mode'] == 'preview' and ec.check_preview('qa.package', r)


def test_qa_package_folder_checks_every_zip(tmp_path):
    _npm_zip(tmp_path, '0123_X.zip', [('0123_X_01.fbx', FBX), ('0123_X_Ground.fbx', FBX)])
    _npm_zip(tmp_path, '0124_X.zip', [('0124_X_01.fbx', FBX)])
    r = pc.qa_package(ec, tmp_path, RUN, PY, ROOT, scene=False)
    assert [o['name'] for o in r['objects']] == ['0123_X.zip', '0124_X.zip']
    assert [t['exit_code'] for t in r['plan']['reports']] == [2, 1] and r['plan']['exit_code'] == 1
    assert r['objects'][0]['findings'] == [] and r['objects'][1]['findings']
    with pytest.raises(ValueError, match='no ZIP'):
        (tmp_path / 'empty').mkdir()
        pc.qa_package(ec, tmp_path / 'empty', RUN, PY, ROOT)


def _vpm_zip(folder, stem, **props):
    files = [(stem + '.fbx', FBX), (stem + '.geojson', good_geojson(**props))]
    prefix = 'T_' + stem[3:]
    files += [('{}_{}_1.1001.png'.format(prefix, m), _png(c)) for m, c in MAPS.items()]
    return _npm_zip(folder, stem + '.zip', files)


def pilot081_cross(paths):
    """0.8.1 qa.package: each ZIP on its own, the OKS and Ground passports are never compared (T04/agr_checker)."""
    return {}


@pytest.mark.parametrize('impl', [pytest.param('pilot081', marks=pytest.mark.xfail(
    strict=True, reason='0.8.1 behaviour: one target at a time')), 'core'])
def test_oks_and_ground_passports_must_agree(tmp_path, impl):
    oks = _vpm_zip(tmp_path, 'SM_X', developer='A', cadNum='77:01:1')
    ground = _vpm_zip(tmp_path, 'SM_X_Ground', developer='B', cadNum='77:01:1')
    got = (pilot081_cross if impl == 'pilot081' else pc.cross_passports)([oks, ground])
    assert [c for c, _d in got.get('SM_X.zip', [])] == ['geojson_cross'] and 'developer' in got['SM_X_Ground.zip'][0][1]


def test_cross_check_in_the_button_report(tmp_path):
    _vpm_zip(tmp_path, 'SM_X', developer='A')
    _vpm_zip(tmp_path, 'SM_X_Ground', developer='B')
    r = pc.qa_package(ec, tmp_path, RUN, PY, ROOT, scene=False)
    assert all('geojson_cross' in [f['code'] for f in o['findings']] for o in r['objects'])
    assert r['plan']['exit_code'] == 1 and r['status'] == 'fail'
    # a single OKS ZIP is still compared with the Ground archive beside it (read only)
    one = pc.qa_package(ec, tmp_path / 'SM_X.zip', RUN, PY, ROOT, scene=False)
    assert one['plan']['cross_checked'] == ['SM_X_Ground.zip']
    assert 'geojson_cross' in [f['code'] for f in one['objects'][0]['findings']]
    agree = tmp_path / 'agree'
    agree.mkdir()
    _vpm_zip(agree, 'SM_X')
    _vpm_zip(agree, 'SM_X_Ground')
    assert pc.cross_passports(sorted(agree.glob('*.zip'))) == {}


def test_cross_check_never_crashes_on_a_broken_passport(tmp_path):
    oks = _vpm_zip(tmp_path, 'SM_X')
    bad = _npm_zip(tmp_path, 'SM_X_Ground.zip', [('SM_X_Ground.geojson', b'\xff not json')])
    got = pc.cross_passports([oks, bad])
    assert got['SM_X_Ground.zip'][0][0] == 'geojson_cross_unread'


def test_corpus_codes_reach_the_button_report(tmp_path):
    """qa.package acceptance: each corrupt case keeps its own code in the stage table and the finding detail."""
    z = _npm_zip(tmp_path, 'SM_X.zip', [('../SM_X_Light.fbx', FBX), ('SM_X.fbx', FBX)])
    r = pc.qa_package(ec, z, RUN, PY, ROOT, scene=False)
    (table,) = r['plan']['reports']
    assert _stage(table, 'V001')['codes'] == ['zip_traversal']
    assert '[zip_traversal]' in r['objects'][0]['findings'][0]['detail']


def test_validator_errors_are_named_not_a_pass(tmp_path):
    def broken(argv):
        return 0, 'not json'
    with pytest.raises(ValueError):
        pc.validate(tmp_path / 'a.zip', broken, PY, ROOT)

    def lying(argv):
        return 0, json.dumps({'stages': [], 'exit_code': 1})
    with pytest.raises(RuntimeError, match='exit'):
        pc.validate(tmp_path / 'a.zip', lying, PY, ROOT)
    with pytest.raises(RuntimeError, match='validator failed'):
        pc.subprocess_runner([PY, '-c', 'import sys; sys.exit(3)'])


# ---- through the dispatcher (runtime.edits_080, glue package_max) -------------------------------------------
def test_dispatcher_runs_the_package_glue(tmp_path, monkeypatch):
    rt = _load(PKG / 'runtime.py', 'agr_runtime_pkg')
    monkeypatch.setenv('AGR_PYTHON', PY)
    d = acceptance_folder(tmp_path)
    z = _npm_zip(tmp_path, '0123_X.zip', [('0123_X_01.fbx', FBX), ('0123_X_Ground.fbx', FBX)])
    q = rt.edits_080('qa.package', 'preview', options={'path': str(z), 'scene': False})
    assert q['tool'] == 'qa.package' and q['plan']['options']['scene'] is False
    p = rt.edits_080('export.zip', 'preview', options={'folder': str(d)})
    assert p['plan']['done'] == ['0123_X.zip', 'SM_X.zip', 'SM_X_Ground.zip']
    r = rt.edits_080('export.zip', 'apply', p)
    assert r['status'] == 'pass' and r['plan']['done'] == p['plan']['done']
    assert rt.parse_report(json.dumps(r)) == r
    with pytest.raises(ValueError, match='read-only'):
        rt.edits_080('qa.package', 'apply', q)


# ---- export.ground_fbx (export.ground_fbx.md) ---------------------------------------------------------------
ACCEPT = ['SM_X_GroundGlass', 'SM_X_Ground', 'SM_X_GroundEl', 'SM_X_GroundElGlass', 'SM_X_Flora', 'SM_X_001_Main']


def _facts(names, **over):
    return [dict({'handle': i, 'name': n, 'geometry': True, 'material': 'Standardmaterial', 'pivot_m': 2.0e6,
                  'hidden': False}, **over.get(n, {})) for i, n in enumerate(names, 1)]


def geoagr_ground_split(names, code):
    """Lab L04 measurement of Export LowPoly: lowercase 'ground' substring split (GeoAGR.ms:66611), the Ground file
    named from the first selected ground object (66617-66622), all OKS into one `_01` file."""
    ground = [n for n in names if 'ground' in n.lower()]
    oks = [n for n in names if 'ground' not in n.lower()]
    out = {}
    if ground:
        nam = ground[0].replace('SM_', '').replace('_GroundEl', '').replace('_Ground', '')
        out['{}_{}_Ground.fbx'.format(code, nam)] = sorted(ground)
    if oks:
        out['{}_X_01.fbx'.format(code)] = sorted(oks)
    return out


def core_ground_split(names, code):
    plan = pc.ground_plan(_facts(names), code)
    return {f['name']: f['nodes'] for f in plan['files']}


EXPECTED_SPLIT = {'0123_X_Ground.fbx': sorted(ACCEPT[:5]), '0123_X_01.fbx': ['SM_X_001_Main']}


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_flora_goes_into_the_ground_file(impl):
    """export.ground_fbx defect 1: Flora landed in the OKS `_01.fbx`."""
    got = (geoagr_ground_split if impl == 'geoagr' else core_ground_split)(ACCEPT, '0123')
    assert 'SM_X_Flora' in got.get('0123_X_Ground.fbx', [])


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_ground_file_name_from_the_address_not_the_first_selected(impl):
    """export.ground_fbx defect 2: GroundGlass first -> `0123_XGlass_Ground.fbx`; `SM_X_Ground_001` -> `_001_Ground`."""
    split = geoagr_ground_split if impl == 'geoagr' else core_ground_split
    assert split(ACCEPT, '0123') == EXPECTED_SPLIT


@pytest.mark.parametrize('impl', [MODEL, 'core'])
def test_export_triangulates(impl):
    """export.ground_fbx defect 3: Triangulate off (GeoAGR.ms:66583); NPM requires triangulation on export."""
    params = dict([('Triangulate', False), ('FileVersion', 'FBX201400')]) if impl == 'geoagr' \
        else dict(pc.GROUND_FBX_PARAMS)
    assert params['Triangulate'] is True and params['FileVersion'] == 'FBX201400'


def test_ground_split_is_independent_of_selection_order():
    import random
    rng = random.Random(7)
    for _ in range(20):
        names = ACCEPT[:]
        rng.shuffle(names)
        assert core_ground_split(names, '0123') == EXPECTED_SPLIT


def test_ground_fbx_keeps_the_right_fbx_settings():
    """Lab L04 'correct': binary FBX 7400, 1 unit = 1 m, scale 1; textures embedded (NPM reg p.9 §5.1)."""
    p = dict(pc.GROUND_FBX_PARAMS)
    assert (p['ASCII'], p['FileVersion'], p['ConvertUnit'], p['ScaleFactor'], p['EmbedTextures']) == \
        (False, 'FBX201400', 'm', 1.0, True)
    assert p['Animation'] is False and p['Cameras'] is False and p['Lights'] is False


def test_ground_plan_refuses_mixed_addresses_bad_code_and_names_skips():
    with pytest.raises(ValueError, match='mixed addresses'):
        pc.ground_plan(_facts(['SM_X_Ground', 'SM_Y_Ground']), '0123')
    assert [f['name'] for f in pc.ground_plan(_facts(['SM_X_Ground', 'SM_Y_Ground']), '0123', 'Y')['files']] == \
        ['0123_Y_Ground.fbx']
    for bad in (None, '123', '01234', 'abcd'):
        with pytest.raises(ValueError, match='4 digits'):
            pc.ground_plan(_facts(ACCEPT), bad)
    plan = pc.ground_plan(_facts(ACCEPT + ['SM_X_Ground_001', 'UCX_SM_X_001_Main_001', 'Box001']), '0123')
    assert {n for n, _ in plan['skipped']} == {'SM_X_Ground_001', 'UCX_SM_X_001_Main_001', 'Box001'}


def test_ground_plan_guards_and_oks_parts(tmp_path):
    names = ACCEPT + ['SM_X_001_MainGlass', 'SM_X_003_Main']
    facts = _facts(names, **{'SM_X_Flora': {'pivot_m': 3.0}, 'SM_X_Ground': {'material': 'PhysicalMaterial'},
                             'SM_X_GroundEl': {'hidden': True}})
    (tmp_path / '0123_X_02.fbx').write_bytes(b'x')
    plan = pc.ground_plan(facts, '0123', folder=str(tmp_path))
    assert [(f['name'], f['nodes'], f['exists']) for f in plan['files']] == [
        ('0123_X_Ground.fbx', sorted(ACCEPT[:5]), False), ('0123_X_01.fbx', ['SM_X_001_Main', 'SM_X_001_MainGlass'], False),
        ('0123_X_02.fbx', ['SM_X_003_Main'], True)]
    codes = {facts[h - 1]['name']: [c for c, _ in v] for h, v in plan['findings'].items()}
    assert codes == {'SM_X_Flora': ['placement'], 'SM_X_Ground': ['material'], 'SM_X_GroundEl': ['hidden']}
    r = pc.ground_report(ec, 'preview', plan, facts, state={'s': 1}, extra={'options': {}})
    assert r['status'] == 'fail' and r['plan']['done'] == ['0123_X_Ground.fbx', '0123_X_01.fbx']
    assert {'item': '0123_X_02.fbx', 'reason': 'exists; refusing to overwrite'} in r['plan']['skipped']
    ec.check_preview('export.ground_fbx', r)

# ---- export.geojson_write (issue #908 section 10; lab: buttons GeoAGR.ms:64642-64644 have no handler) ----------
def _jpeg(size=256):
    b = BytesIO()
    Image.new('RGB', (size, size), (90, 120, 80)).save(b, 'JPEG')
    return b.getvalue()


PROPS = {'address': 'г. Москва, ул. Тестовая, д. 1', 'okrug': 'ЦАО', 'rajon': 'Арбат', 'name': 'Жилой дом',
         'developer': 'ООО Застройщик', 'designer': 'ООО Проектировщик', 'cadNum': '77:01:0001001:1',
         'FNO_code': '010 004', 'FNO_name': 'Общежитие', 'ZU_area': 1200.5, 'h_relief': 150.0, 'h_otn': 45.0,
         'h_abs': 195.0, 's_obsh': 9000.0, 's_naz': 8000.0, 's_podz': 1000.0, 'spp_gns': 9500.0, 'act_AGR': '',
         'other': ''}


def pivot_preview(x=12345.67849, y=-6789.01251, status='pass'):
    """Shape of branch A's export.pivot_place preview plan (pivot_value = [centre X, centre Y, floor])."""
    return {'schema': 1, 'tool': 'export.pivot_place', 'status': status, 'objects': [],
            'plan': {'mode': 'preview', 'pivot_value': [x, y, 150.0], 'floor': {'z': '150.0000', 'source': 'explicit'}}}


GLASS = [{'name': 'M_X_MainGlass_1', 'diffuse': [200.0, 220.0, 255.0], 'opacity': 50.0, 'ior': 1.52, 'glossiness': 90.0}]


def _checker(data, ground=False, glass=None):
    from twinqa.geojson import geojson_findings
    from twinqa.profiles import load_profiles
    return geojson_findings(data, load_profiles().vpm, ground, glass_names=glass, source_name='x.geojson')


def test_geojson_document_passes_the_twinqa_checker(tmp_path):
    plan = pc.geojson_plan(['SM_X_Main', 'SM_X_MainGlass'], PROPS, _jpeg(), pivot_preview(), GLASS, str(tmp_path))
    assert plan['findings'] == [] and plan['stem'] == 'SM_X' and plan['target'].endswith('SM_X.geojson')
    found = _checker(plan['data'], glass={'M_X_MainGlass_1'})
    assert all(f.status == 'pass' for f in found), [(f.name, f.status, f.observed) for f in found]
    doc = json.loads(plan['data'].decode('utf-8'))
    feat = doc['features'][0]
    assert feat['geometry']['coordinates'] == [12345.678, -6789.013]  # MSK-77, 3 decimals (reg p.55)
    assert list(feat['properties']) == list(pc.PROPERTY_KEYS)
    assert feat['properties']['address'] == PROPS['address']  # UTF-8, not escaped away


def test_preview_base64_decodes_to_the_same_jpeg():
    import base64
    data = _jpeg()
    b64, problems = pc.preview_image(data)
    assert problems == [] and base64.b64decode(b64, validate=True) == data
    assert Image.open(BytesIO(base64.b64decode(b64))).size == (256, 256)
    assert pc.preview_image(_jpeg(128))[1] and pc.preview_image(b'\x89PNG....')[1]
    assert pc.jpeg_size(_jpeg(300)) == (300, 300)


def test_missing_values_are_findings_never_invented(tmp_path):
    props = dict(PROPS, FNO_code='', developer=None)
    del props['cadNum']
    plan = pc.geojson_plan(['SM_X_Main'], props, None, pivot_preview(), [], str(tmp_path))
    text = ' '.join(d for _, d in plan['findings'])
    assert 'FNO_code is empty' in text and 'developer is empty' in text and 'cadNum is empty' in text
    assert 'no picture' in text
    doc = json.loads(plan['data'])['features'][0]['properties']
    assert doc['cadNum'] is None and doc['FNO_code'] == ''  # written as given; the checker fails it, nothing invented
    with pytest.raises(ValueError, match='unknown or reserved'):
        pc.geojson_plan(['SM_X_Main'], dict(PROPS, color='red'), None, pivot_preview(), [], str(tmp_path))


def test_ground_passport_allows_its_nullable_fields(tmp_path):
    props = dict({k: v for k, v in PROPS.items() if k not in pc.GROUND_NULLABLE}, act_AGR='01-01-2026')
    plan = pc.geojson_plan(['SM_X_Ground', 'SM_X_Flora', 'SM_X_GroundEl'], props, _jpeg(), pivot_preview(), [],
                           str(tmp_path))
    assert plan['findings'] == [] and plan['stem'] == 'SM_X_Ground' and plan['ground']
    found = _checker(plan['data'], ground=True, glass=set())
    assert all(f.status == 'pass' for f in found), [(f.name, f.status, f.observed) for f in found]


def test_point_only_from_the_pivot_place_preview(tmp_path):
    stub = {'schema': 1, 'tool': 'export.pivot_place', 'status': 'not_implemented', 'objects': [], 'plan': {}}
    with pytest.raises(ValueError, match='branch A'):
        pc.geojson_plan(['SM_X_Main'], PROPS, _jpeg(), stub, [], str(tmp_path))
    with pytest.raises(ValueError, match='without a pivot'):
        pc.geojson_plan(['SM_X_Main'], PROPS, _jpeg(), pivot_preview(status='fail'), [], str(tmp_path))
    src = (PKG / 'package_core.py').read_text(encoding='utf-8') + (PKG / 'package_max.py').read_text(encoding='utf-8')
    assert 'geom_core' not in src.replace("'geom_core'", '') and 'import geom' not in src
    assert "edits_080('export.pivot_place', 'preview'" in src


def test_one_set_and_one_address_per_passport(tmp_path):
    for names, word in ((['SM_X_Main', 'SM_X_Ground'], 'OKS and Ground'), (['SM_X_Main', 'SM_Y_Main'], 'one address'),
                        (['Box001'], 'one address')):
        with pytest.raises(ValueError, match=word):
            pc.geojson_stem(names)
    assert pc.geojson_stem(['SM_X_Main', 'UCX_SM_X_Main_001', 'SM_X_MainGlass'])[:2] == ('SM_X', False)


def test_glasses_empty_or_one_object_keyed_by_material():
    assert pc.glasses_entry([]) == []
    (entry,) = pc.glasses_entry(GLASS + [dict(GLASS[0], name='M_X_MainGlass_2', opacity=30.0)])
    assert sorted(entry) == ['M_X_MainGlass_1', 'M_X_MainGlass_2']
    assert entry['M_X_MainGlass_1'] == {'color_RGB': {'Red': 200, 'Green': 220, 'Blue': 255}, 'transparency': 0.5,
                                        'refraction': 1.52, 'roughness': 0.1, 'metallicity': 0.0}


def test_geojson_property_keys_match_the_standard():
    import yaml
    vpm = yaml.safe_load((ROOT / 'standards/VPM_STANDARD.yaml').read_text(encoding='utf-8'))['geojson']
    assert list(pc.PROPERTY_KEYS) == vpm['properties_keys']
    assert list(pc.GROUND_NULLABLE) == vpm['ground_nullable_as_empty_string']