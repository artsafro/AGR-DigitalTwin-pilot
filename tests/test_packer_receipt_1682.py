"""new-case: NPM/VPM packer receipt beside the archive; V001 honours the packer status (#1682)."""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import package_core as pc
from adapters.max.agr_tools.export_meta import record_export

NOTE = 'Delivered file: byte control, not model acceptance.'


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', *map(str, args)],
                          cwd=ROOT, capture_output=True, encoding='utf-8')


def sidecar(target):
    return Path(str(target) + '.delivery.json')


def npm_pkg(root, parts=('01', 'Ground'), stem='0000_Synthetic'):
    root.mkdir(parents=True)
    for part in parts:
        fbx = root / f'{stem}_{part}.fbx'
        fbx.write_bytes(b'synthetic ' + part.encode())
        record_export(fbx, source='synthetic fixture', top=3.5)
    return root


def vpm_pkg(parent, name='fbx_vpm'):
    pkg, tex = parent / name, parent / (name + '_tex')
    pkg.mkdir()
    tex.mkdir()
    fbx = pkg / 'SM_Synthetic.fbx'
    fbx.write_bytes(b'synthetic VPM')
    record_export(fbx, source='synthetic fixture', top=3.5)
    for role in ('Diffuse', 'ERM', 'Normal'):
        (tex / f'T_Synthetic_{role}_1.1001.png').write_bytes(role.encode())
    return pkg, tex


def v001(target):
    result = cli('validate', target, '--profile', 'npm', '--json')
    body = json.loads(result.stdout)
    checks = [f for s in body['stages'] for f in s['findings'] if f['name'] == 'delivered file']
    return result, body, checks


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_npm_and_vpm_share_a_parent_without_a_shared_report(tmp_path):
    """Acceptance 1: each packer writes <zip>.delivery.json; no parent-wide package_report.json."""
    npm_pkg(tmp_path / 'fbx_npm')
    pkg, tex = vpm_pkg(tmp_path)
    first = cli('package-npm', tmp_path / 'fbx_npm')
    second = cli('package-vpm', pkg, tex, '--no-geojson')
    assert first.returncode == 0 and second.returncode == 0, first.stderr + second.stderr
    assert not (tmp_path / 'package_report.json').exists()
    for name, status in (('0000_Synthetic.zip', 'packaged_not_validated'),
                         ('SM_Synthetic.zip', 'packaged_not_validated')):
        report = json.loads(sidecar(tmp_path / name).read_text(encoding='utf-8'))
        assert report['status'] == status and report['delivered']['file'] == name
        assert not Path(str(sidecar(tmp_path / name)) + '.partial').exists()


def test_complete_npm_package_passes_v001_with_separate_note(tmp_path):
    """Acceptance 2 (complete side) and 4: note is its own element before the delivered: line."""
    npm_pkg(tmp_path / 'fbx')
    assert cli('package-npm', tmp_path / 'fbx').returncode == 0
    target = tmp_path / '0000_Synthetic.zip'
    _, body, checks = v001(target)
    assert [(c['status'], c['data']['code']) for c in checks] == [('pass', 'delivered_match')]
    line = json.loads(sidecar(target).read_text(encoding='utf-8'))['summary_ru'].splitlines()[-1]
    assert body['notes'].count(NOTE) == 1 and body['notes'].count(line) == 1
    assert body['notes'].index(NOTE) + 1 == body['notes'].index(line)
    assert body['passed'] is False


def test_allow_incomplete_npm_archive_never_attested(tmp_path):
    """Acceptance 2: --allow-incomplete diagnostic archive -> V001 fail naming the incomplete status."""
    npm_pkg(tmp_path / 'fbx', parts=('01',))
    run = cli('package-npm', tmp_path / 'fbx', '--allow-incomplete')
    assert run.returncode == 1, run.stderr
    target = tmp_path / '0000_Synthetic.zip'
    assert json.loads(sidecar(target).read_text(encoding='utf-8'))['status'] == 'incomplete'
    result, body, checks = v001(target)
    assert result.returncode == 1
    assert [(c['status'], c['data']['code']) for c in checks] == [('fail', 'delivered_incomplete')]
    assert 'incomplete' in checks[0]['observed']
    assert not any(n.startswith('delivered: ') for n in body['notes'])


def synthetic_zip(tmp_path):
    target = tmp_path / '0000_Synthetic.zip'
    with zipfile.ZipFile(target, 'w') as archive:
        archive.writestr('0000_Synthetic_01.fbx', b'synthetic')
        archive.writestr('0000_Synthetic_Ground.fbx', b'synthetic')
    return target


MISSING = object()
STATUS_CASES = [
    ('packaged_not_validated', 'pass', 'delivered_match'),
    (MISSING, 'pass', 'delivered_match'),
    ('incomplete', 'fail', 'delivered_incomplete'),
    ('INCOMPLETE', 'not_run', 'delivery_status_unknown'),
    ('passed', 'not_run', 'delivery_status_unknown'),
    ('', 'not_run', 'delivery_status_unknown'),
    (None, 'not_run', 'delivery_status_unknown'),
    (True, 'not_run', 'delivery_status_unknown'),
    (['incomplete'], 'not_run', 'delivery_status_unknown'),
]


@pytest.mark.parametrize('report_name', ['sidecar', 'package_report.json'])
@pytest.mark.parametrize('swapped', [False, True])
@pytest.mark.parametrize('status,expected,code', STATUS_CASES)
def test_v001_branches_on_report_status(tmp_path, report_name, swapped, status, expected, code):
    """Acceptance 3: status enumeration for the new sidecar and the historical report alike;
    changed bytes are a fail whatever the status (fail-closed, never not_run)."""
    target = synthetic_zip(tmp_path)
    report = pc.delivery_receipt(target)
    if status is not MISSING:
        report['status'] = status
    path = sidecar(target) if report_name == 'sidecar' else tmp_path / report_name
    path.write_text(json.dumps(report), encoding='utf-8')
    if swapped:
        data = target.read_bytes()
        target.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        expected, code = 'fail', 'delivered_mismatch'
    _, body, checks = v001(target)
    assert [(c['status'], c['data']['code']) for c in checks] == [(expected, code)]
    attested = any(n.startswith('delivered: ') for n in body['notes'])
    assert attested is (expected == 'pass')
    assert (NOTE in body['notes']) is (expected == 'pass')


def test_historical_report_without_delivered_unchanged_whatever_status(tmp_path):
    """Acceptance 3: a pre-#1645 report keeps not_run delivered_not_attested, even with status."""
    target = synthetic_zip(tmp_path)
    for status in ('incomplete', 'unknown-value'):
        (tmp_path / 'package_report.json').write_text(json.dumps({'zip': 'x', 'status': status}),
                                                      encoding='utf-8')
        _, _, checks = v001(target)
        assert [(c['status'], c['data']['code']) for c in checks] == [('not_run', 'delivered_not_attested')]


def test_sidecar_is_authoritative_over_a_sibling_package_report(tmp_path):
    """A parent-wide package_report.json of another package (old packers) no longer collides."""
    target = synthetic_zip(tmp_path)
    other = tmp_path / '0001_Other.zip'
    other.write_bytes(b'PK other archive')
    (tmp_path / 'package_report.json').write_text(json.dumps(pc.delivery_receipt(other)), encoding='utf-8')
    sidecar(target).write_text(json.dumps(pc.delivery_receipt(target)), encoding='utf-8')
    _, _, checks = v001(target)
    assert [(c['status'], c['data']['code']) for c in checks] == [('pass', 'delivered_match')]


def test_write_delivery_report_is_atomic_and_no_clobber(tmp_path, monkeypatch):
    """Spec 5: temp + rename; a failed dump leaves neither report nor .partial; never overwrites."""
    target = synthetic_zip(tmp_path)
    receipt = pc.delivery_receipt(target)
    assert pc.write_delivery_report(target, receipt) == str(sidecar(target))
    assert json.loads(sidecar(target).read_text(encoding='utf-8')) == receipt
    before = snapshot(tmp_path)
    with pytest.raises(FileExistsError):
        pc.write_delivery_report(target, {**receipt, 'status': 'incomplete'})
    assert snapshot(tmp_path) == before
    sidecar(target).unlink()

    def broken(*args, **kwargs):
        raise OSError('disk full (synthetic)')

    monkeypatch.setattr(pc.json, 'dump', broken)
    with pytest.raises(OSError, match='synthetic'):
        pc.write_delivery_report(target, receipt)
    assert sorted(p.name for p in tmp_path.iterdir()) == [target.name]
    with pytest.raises(ValueError):
        pc.write_delivery_report(target, {'status': 'packaged_not_validated'})


@pytest.mark.parametrize('blocker', ['report', 'report_partial', 'report_input_alias'])
def test_npm_refuses_existing_or_aliased_report_paths(tmp_path, blocker):
    """Output paths that exist or alias an input: exit nonzero, nothing written, nothing deleted."""
    pkg = npm_pkg(tmp_path / 'fbx')
    target = tmp_path / '0000_Synthetic.zip'
    path = {'report': sidecar(target), 'report_partial': Path(str(sidecar(target)) + '.partial'),
            'report_input_alias': sidecar(target)}[blocker]
    if blocker == 'report_input_alias':
        os.link(pkg / '0000_Synthetic_01.fbx', path)
    else:
        path.write_text('{}', encoding='utf-8')
    before = snapshot(tmp_path)
    run = cli('package-npm', pkg)
    assert run.returncode != 0 and 'already exists' in run.stderr, run.stderr
    assert snapshot(tmp_path) == before
