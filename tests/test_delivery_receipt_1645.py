"""new-case: delivered ZIP/Max byte identity through existing delivery writers (#1645)."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_review_publish import FakeAdapter, _publish, review  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import package_core as pc
from adapters.max.agr_tools.export_meta import record_export


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', *map(str, args)],
                          cwd=ROOT, capture_output=True, encoding='utf-8')


def assert_receipt(report, target):
    expected = {'file': target.name, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                'size': target.stat().st_size}
    assert report['delivered'] == expected
    line = f'delivered: {target.name} sha256={expected["sha256"]} size={expected["size"]}'
    assert report['summary_ru'].splitlines().count(line) == 1


def assert_package_recheck(target):
    current = cli('validate', target, '--json')
    assert 'delivered_match' in current.stdout, current.stderr
    # Trailing ZIP bytes do not affect member CRCs: only the final-artifact binding catches them.
    with target.open('ab') as fh:
        fh.write(b'synthetic swap')
    changed = cli('validate', target, '--json')
    assert changed.returncode == 1
    assert 'delivered_mismatch' in changed.stdout


def test_npm_cli_records_final_zip(tmp_path):
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    for part in ('01', 'Ground'):
        fbx = pkg / f'0000_Synthetic_{part}.fbx'
        fbx.write_bytes(b'synthetic ' + part.encode())
        record_export(fbx, source='synthetic fixture', top=3.5)
    run = cli('package-npm', pkg)
    assert run.returncode == 0, run.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert_receipt(report, tmp_path / '0000_Synthetic.zip')
    assert_package_recheck(tmp_path / '0000_Synthetic.zip')


def test_vpm_cli_records_final_zip(tmp_path):
    pkg, tex = tmp_path / 'fbx', tmp_path / 'textures'
    pkg.mkdir()
    tex.mkdir()
    fbx = pkg / 'SM_Synthetic.fbx'
    fbx.write_bytes(b'synthetic VPM')
    record_export(fbx, source='synthetic fixture', top=3.5)
    for role in ('Diffuse', 'ERM', 'Normal'):
        (tex / f'T_Synthetic_{role}_1.1001.png').write_bytes(role.encode())
    run = cli('package-vpm', pkg, tex, '--no-geojson')
    assert run.returncode == 0, run.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert_receipt(report, tmp_path / 'SM_Synthetic.zip')
    assert_package_recheck(tmp_path / 'SM_Synthetic.zip')


def test_max_publish_records_final_scene(review, tmp_path):
    assert _publish(review, tmp_path, FakeAdapter()) == 0
    scene = next((tmp_path / 'review').rglob('*.max'))
    report = json.loads(Path(str(scene) + '.delivery.json').read_text(encoding='utf-8'))
    assert_receipt(report, scene)
    assert (scene.parent / 'README.txt').read_text(encoding='utf-8').count(report['summary_ru']) == 1
    plain = cli('validate', scene, '--json')
    assert plain.returncode == 2, plain.stderr  # no profile needed; unmeasured native checks stay open
    assert 'delivered_match' in plain.stdout


def test_max_publish_fresh_isolated_process(tmp_path):
    """No pytest/root pythonpath may be needed to find the shared packaging owner."""
    script = '''
import json, runpy, sys
from datetime import date
from pathlib import Path
root, repo = map(Path, sys.argv[1:])
source = root / 'synthetic.max'
source.write_bytes(b'synthetic source')
common = runpy.run_path(str(repo / 'tools/review/common.py'))
class Adapter:
    def build(self, source, output, preview):
        output.write_bytes(b'synthetic published Max')
        preview.write_bytes(b'synthetic preview')
        return {'version': 'synthetic', 'cameras': 1, 'materials': 1}
common['publish'](task='1645', slug='synthetic', source=source, what='synthetic fixture', pngs=[],
                  review_root=root / 'review', adapter=Adapter(), today=date(2026, 11, 17))
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(tmp_path), str(ROOT)],
                            cwd=tmp_path, capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    scene = next((tmp_path / 'review').rglob('*.max'))
    report = json.loads(Path(str(scene) + '.delivery.json').read_text(encoding='utf-8'))
    assert_receipt(report, scene)


def test_stale_validator_receipt_cannot_publish_ready(tmp_path):
    from adapters.max.agr_tools import edit_core
    from tools.qa import validate_package as vp
    from twinqa.profiles import load_profiles
    for part in ('01', 'Ground'):
        fbx = tmp_path / f'0000_Synthetic_{part}.fbx'
        fbx.write_bytes(b'synthetic')
        record_export(fbx, source='synthetic fixture')
    def stale(target):
        full = vp.validate(Path(target), 'npm', load_profiles()).to_dict()
        full['target_sha256'] = '0' * 64
        table = pc.stage_table(full)
        table['validation_report'] = full
        return table
    with pytest.raises(ValueError, match='delivered.*hash'):
        pc.zip_apply(edit_core, pc.zip_preview(edit_core, str(tmp_path)), stale)
    run = next(tmp_path.glob('Сборка_*'))
    assert (run / pc.MARK_FAIL).exists() and not (run / pc.MARK_OK).exists()


@pytest.mark.parametrize('suffix', ['.zip', '.max'])
@pytest.mark.parametrize('edit', [False, True])
def test_validate_rehashes_delivery_receipt(tmp_path, suffix, edit):
    import zipfile
    target = tmp_path / ('0000_Synthetic' + suffix)
    if suffix == '.zip':
        with zipfile.ZipFile(target, 'w') as z:
            z.writestr('0000_Synthetic_01.fbx', b'synthetic')
    else:
        target.write_bytes(b'synthetic Max scene')
    receipt = pc.delivery_receipt(target)
    Path(str(target) + '.delivery.json').write_text(json.dumps(receipt), encoding='utf-8')
    if edit:
        # Same size: the size check alone must not accept a swapped file.
        data = target.read_bytes()
        target.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    result = cli('validate', target, '--profile', 'npm', '--json')
    body = json.loads(result.stdout)
    checks = [f for s in body['stages'] for f in s['findings'] if f['name'] == 'delivered file']
    assert len(checks) == 1
    assert checks[0]['status'] == ('fail' if edit else 'pass')
    if edit:
        assert result.returncode == 1
        assert checks[0]['data']['code'] == 'delivered_mismatch'
        assert target.name in checks[0]['observed']
    else:
        assert body['passed'] is False  # byte identity is NOT model acceptance
        assert receipt['summary_ru'].splitlines()[-1] in body['notes']


@pytest.mark.parametrize('has_delivery', [False, True])
@pytest.mark.parametrize('swapped', [False, True])
def test_historical_package_report_is_not_delivery_attestation(tmp_path, has_delivery, swapped):
    """Synthetic pre-#1645 reports remain readable; explicit receipts still bind ZIP bytes."""
    import zipfile
    target = tmp_path / '0000_Synthetic.zip'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('0000_Synthetic_01.fbx', b'synthetic')
        archive.writestr('0000_Synthetic_Ground.fbx', b'synthetic')
        archive.comment = b'synthetic comment'
    report = {'zip': str(target), 'files': ['0000_Synthetic_01.fbx', '0000_Synthetic_Ground.fbx']}
    if has_delivery:
        report.update(pc.delivery_receipt(target))
    (tmp_path / 'package_report.json').write_text(json.dumps(report), encoding='utf-8')
    if swapped:
        # Keep the ZIP readable and its size unchanged; only receipt binding can detect this.
        data = target.read_bytes()
        target.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    result = cli('validate', target, '--profile', 'npm', '--json')
    body = json.loads(result.stdout)
    checks = [f for s in body['stages'] if s['id'] == 'V001'
              for f in s['findings'] if f['name'] == 'delivered file']
    assert len(checks) == 1
    if not has_delivery:
        assert checks[0]['status'] == 'not_run'
        assert any('no delivery attestation' in note for note in body['notes'])
        assert checks[0]['data']['code'] == 'delivered_not_attested'
        assert all(f['status'] != 'fail' for s in body['stages'] if s['id'] == 'V001'
                   for f in s['findings'])
        assert not any(f['status'] == 'fail' and f.get('data', {}).get('code') == 'delivered_mismatch'
                       for s in body['stages'] for f in s['findings'])
        assert not any(note.startswith('delivered:') for note in body['notes'])
    else:
        assert checks[0]['status'] == ('fail' if swapped else 'pass')
        assert checks[0]['data']['code'] == ('delivered_mismatch' if swapped else 'delivered_match')
        if swapped:
            assert result.returncode == 1


@pytest.mark.parametrize('swapped', [False, True])
def test_historical_report_does_not_override_explicit_sidecar(tmp_path, swapped):
    import zipfile
    target = tmp_path / '0000_Synthetic.zip'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('0000_Synthetic_Ground.fbx', b'synthetic')
        archive.comment = b'synthetic comment'
    Path(str(target) + '.delivery.json').write_text(
        json.dumps(pc.delivery_receipt(target)), encoding='utf-8')
    (tmp_path / 'package_report.json').write_text('{"zip": "historical"}', encoding='utf-8')
    if swapped:
        data = target.read_bytes()
        target.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    result = cli('validate', target, '--profile', 'npm', '--json')
    body = json.loads(result.stdout)
    checks = [f for s in body['stages'] for f in s['findings'] if f['name'] == 'delivered file']
    assert len(checks) == 1
    assert checks[0]['data']['code'] == ('delivered_mismatch' if swapped else 'delivered_match')
    assert checks[0]['status'] == ('fail' if swapped else 'pass')


@pytest.mark.parametrize('filename,payload', [
    ('package_report.json', 'null'), ('package_report.json', '[]'),
    ('package_report.json', '{'), ('package_report.json', '{"zip":1,"zip":2}'),
    ('package_report.json', '{"delivered":null}'),
    ('0000_Synthetic.zip.delivery.json', '{}')])
def test_only_legacy_report_mapping_can_omit_delivered(tmp_path, filename, payload):
    import zipfile
    target = tmp_path / '0000_Synthetic.zip'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('0000_Synthetic_Ground.fbx', b'synthetic')
    (tmp_path / filename).write_text(payload, encoding='utf-8')
    result = cli('validate', target, '--profile', 'npm', '--json')
    assert result.returncode == 1, result.stderr
    body = json.loads(result.stdout)
    assert any(f['status'] == 'fail' and f.get('data', {}).get('code') == 'delivered_mismatch'
               for s in body['stages'] for f in s['findings'])


def test_pack_deliver_summary_keeps_archive_receipt(tmp_path):
    from adapters.max.agr_tools import deliver_core as dc
    target = tmp_path / 'synthetic.zip'
    target.write_bytes(b'synthetic archive')
    receipt = pc.delivery_receipt(target)
    body = dc.summary([], [], [], {}, {}, delivery=receipt)
    assert_receipt(body, target)


@pytest.mark.parametrize('mutate', [False, True])
def test_zip_apply_binds_report_and_marker_to_checked_bytes(tmp_path, mutate):
    from adapters.max.agr_tools import edit_core
    from tools.qa import validate_package as vp
    from twinqa.profiles import load_profiles
    for part in ('01', 'Ground'):
        fbx = tmp_path / f'0000_Synthetic_{part}.fbx'
        fbx.write_bytes(b'synthetic')
        record_export(fbx, source='synthetic fixture')

    def validate(target):
        full = vp.validate(Path(target), 'npm', load_profiles()).to_dict()
        table = pc.stage_table(full)
        table['validation_report'] = full
        if mutate:
            with open(target, 'ab') as fh:
                fh.write(b'swapped after check')
        return table

    preview = pc.zip_preview(edit_core, str(tmp_path))
    if mutate:
        with pytest.raises(ValueError, match='delivered'):
            pc.zip_apply(edit_core, preview, validate)
        run = next(tmp_path.glob('Сборка_*'))
        assert (run / pc.MARK_FAIL).exists() and not (run / pc.MARK_OK).exists()
    else:
        report = pc.zip_apply(edit_core, preview, validate)
        target = next(Path(report['plan']['run_folder']).glob('*.zip'))
        body = json.loads(Path(str(target) + '.delivery.json').read_text(encoding='utf-8'))
        assert_receipt(body, target)
        assert report['plan']['delivered'] == [body['delivered']]
        marker = (target.parent / pc.MARK_FAIL).read_text(encoding='utf-8')
        assert marker.count(body['summary_ru'].splitlines()[-1]) == 1


@pytest.mark.parametrize('bad', [None, {}, [], {'file': 'x.max'},
    {'file': 'x.max', 'sha256': '0' * 64, 'size': 0},
    {'file': 'x.max', 'sha256': '0' * 64, 'size': True},
    {'file': 'x.max', 'sha256': '0' * 64, 'size': float('nan')},
    {'file': 'x.max', 'sha256': '0' * 64, 'size': float('inf')},
    {'file': 'x.max', 'sha256': '0' * 64 + '\n', 'size': 1},
    {'file': 'x.max', 'sha256': '0' * 64, 'size': 1, 'unknown': 3}])
def test_partial_and_invalid_receipts_fail_closed(tmp_path, bad):
    target = tmp_path / 'x.max'
    target.write_bytes(b'x')
    before = target.read_bytes()
    with pytest.raises(ValueError):
        pc.check_delivery_receipt(target, bad)
    assert target.read_bytes() == before


@pytest.mark.parametrize('payload', ['', '{}', 'null', '{"delivered":{}}',
    '{"delivered":null,"delivered":null}'])
def test_fresh_validator_refuses_broken_report(tmp_path, payload):
    target = tmp_path / 'x.max'
    target.write_bytes(b'synthetic')
    report = Path(str(target) + '.delivery.json')
    report.write_text(payload, encoding='utf-8')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = cli('validate', target, '--profile', 'vpm', '--json')
    assert result.returncode == 1, result.stderr
    body = json.loads(result.stdout)
    assert any(f['data'].get('code') == 'delivered_mismatch'
               for s in body['stages'] for f in s['findings'])
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize('suffix', ['.zip', '.max'])
def test_generated_single_byte_swaps_all_fail_and_reset(tmp_path, suffix):
    target = tmp_path / ('synthetic' + suffix)
    for length in (1, 17, 65):
        original = bytes(range(length))
        target.write_bytes(original)
        receipt = pc.delivery_receipt(target)
        for offset in range(length):
            swapped = bytearray(original)
            swapped[offset] ^= 1
            target.write_bytes(swapped)
            with pytest.raises(ValueError, match='differs'):
                pc.check_delivery_receipt(target, receipt['delivered'])
        target.write_bytes(original)
        assert pc.check_delivery_receipt(target, receipt['delivered']) == receipt


@pytest.mark.parametrize('name,payload', [('empty.max', b''), ('bad.fbx', b'x'), ('line\nbreak.max', b'x')])
def test_unsupported_delivery_records_write_nothing(tmp_path, name, payload):
    # Windows cannot create a newline filename; rejection can be tested before opening it.
    target = tmp_path / name
    if '\n' not in name:
        target.write_bytes(payload)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        pc.delivery_receipt(target)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_missing_scene_and_report_are_not_a_pass(tmp_path):
    target = tmp_path / 'missing.max'
    with pytest.raises(OSError):
        pc.check_delivery_receipt(target, {'file': target.name, 'sha256': '0' * 64, 'size': 1})
    target.write_bytes(b'synthetic')
    result = cli('validate', target, '--profile', 'npm', '--json')
    assert result.returncode == 1
    assert 'missing delivery report' in result.stdout


def test_delivery_record_rejects_replacement_during_hash(tmp_path, monkeypatch):
    target = tmp_path / 'x.max'
    target.write_bytes(b'synthetic')
    stat = pc.os.stat
    def replaced(path, *args, **kwargs):
        if str(path) == str(target):
            target.write_bytes(b'different-sized synthetic')
        return stat(path, *args, **kwargs)
    monkeypatch.setattr(pc.os, 'stat', replaced)
    with pytest.raises(ValueError, match='changed'):
        pc.delivery_receipt(target)
