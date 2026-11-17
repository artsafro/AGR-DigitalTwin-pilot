"""#1637: the NPM ZIP is bound to export_meta both ways; NPM validate with a build manifest and no --master fails.

Synthetic fixtures only (no 3ds Max, no delivered files).
"""
import hashlib
import importlib.util
import json
import random
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OKS, GROUND = '0000_Synthetic_01.fbx', '0000_Synthetic_Ground.fbx'
CMD = [sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm']


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def make_pkg(tmp, files=None, recorded=None, key='fbx_records'):
    """Package dir with FBX files and a canonical export_meta.json recording `recorded` (default: the files)."""
    files = {OKS: b'synthetic OKS', GROUND: b'synthetic Ground'} if files is None else files
    recorded = dict(files) if recorded is None else recorded
    pkg = tmp / 'fbx'
    pkg.mkdir()
    for name, data in files.items():
        (pkg / name).write_bytes(data)
    meta = {'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown'}
    if key == 'fbx_records':
        meta['fbx_records'] = {n: {'bounds_m': [[0, 0, 0], [1, 1, 1]], 'fbx_sha256': _sha(d)}
                               for n, d in recorded.items()}
    elif key == 'exported_files':
        meta['exported_files'] = sorted(recorded)
    elif key == 'exported_sha256':
        meta['exported_files'] = sorted(recorded)
        meta['exported_sha256'] = {n: _sha(d) for n, d in recorded.items()}
    (pkg / 'export_meta.json').write_text(json.dumps(meta), encoding='utf-8')
    return pkg


def run(pkg, *extra):
    return subprocess.run(CMD + [str(pkg), *extra], capture_output=True, text=True, cwd=ROOT)


def outputs(tmp):
    return sorted(p.name for p in tmp.iterdir() if p.is_file())


def test_clean_package_binds_every_member_and_reports_hashes(tmp_path):
    pkg = make_pkg(tmp_path)
    r = run(pkg)
    assert r.returncode == 0, r.stderr
    with zipfile.ZipFile(tmp_path / '0000_Synthetic.zip') as z:
        assert sorted(z.namelist()) == [OKS, GROUND]
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert report['passed'] is False and report['status'] == 'packaged_not_validated' and report['problems'] == []
    binding = report['export_binding']
    assert binding['records'] == ['export_meta.json']
    assert sorted(binding['members'], key=lambda m: m['name']) == [
        {'name': OKS, 'recorded_sha256': _sha(b'synthetic OKS'), 'zip_sha256': _sha(b'synthetic OKS'), 'status': 'match',
         'recorded_in': ['export_meta.json']},
        {'name': GROUND, 'recorded_sha256': _sha(b'synthetic Ground'), 'zip_sha256': _sha(b'synthetic Ground'),
         'status': 'match', 'recorded_in': ['export_meta.json']}]


def test_foreign_fbx_added_after_export_is_refused(tmp_path):
    pkg = make_pkg(tmp_path)
    (pkg / '0000_Synthetic_02.fbx').write_bytes(b'foreign FBX dropped in after export')
    r = run(pkg)
    assert r.returncode == 1
    assert 'refused:' in r.stderr and '0000_Synthetic_02.fbx' in r.stderr and 'not recorded' in r.stderr
    assert outputs(tmp_path) == []


def test_recorded_fbx_missing_is_refused(tmp_path):
    pkg = make_pkg(tmp_path, files={OKS: b'synthetic OKS'},
                   recorded={OKS: b'synthetic OKS', GROUND: b'synthetic Ground'})
    r = run(pkg)
    assert r.returncode == 1 and GROUND in r.stderr and 'missing from the package' in r.stderr
    assert outputs(tmp_path) == []


def test_changed_hash_is_refused(tmp_path):
    pkg = make_pkg(tmp_path)
    (pkg / OKS).write_bytes(b'synthetic OKS edited after export')
    r = run(pkg)
    assert r.returncode == 1 and OKS in r.stderr and 'SHA-256' in r.stderr
    assert outputs(tmp_path) == []


def test_allow_incomplete_is_diagnostic_and_reports_the_mismatch(tmp_path):
    pkg = make_pkg(tmp_path)
    (pkg / OKS).write_bytes(b'edited')
    r = run(pkg, '--allow-incomplete')
    assert r.returncode == 1, r.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert report['passed'] is False and report['status'] == 'incomplete'
    assert any(OKS in p and 'SHA-256' in p for p in report['problems'])
    row = next(m for m in report['export_binding']['members'] if m['name'] == OKS)
    assert row['status'] == 'hash_mismatch' and row['zip_sha256'] == _sha(b'edited')


def test_meta_without_any_export_record_is_refused(tmp_path):
    pkg = make_pkg(tmp_path, key=None)
    r = run(pkg)
    assert r.returncode == 1 and 'records no exported FBX' in r.stderr
    assert outputs(tmp_path) == []


def test_exported_files_without_hash_is_refused(tmp_path):
    """r1 P1-2: a recorded FBX without any recorded SHA-256 is never packed with exit 0."""
    pkg = make_pkg(tmp_path, key='exported_files')
    r = run(pkg)
    assert r.returncode == 1 and OKS in r.stderr and 'no recorded SHA-256' in r.stderr
    assert outputs(tmp_path) == []
    r = run(pkg, '--allow-incomplete')
    assert r.returncode == 1
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert report['passed'] is False and report['status'] == 'incomplete'
    assert {m['status'] for m in report['export_binding']['members']} == {'hash_not_recorded'}


def test_exported_sha256_binds_names_and_hashes(tmp_path):
    pkg = make_pkg(tmp_path, key='exported_sha256')
    r = run(pkg)
    assert r.returncode == 0, r.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert {m['status'] for m in report['export_binding']['members']} == {'match'}
    (tmp_path / 'b').mkdir()
    pkg2 = make_pkg(tmp_path / 'b', key='exported_sha256', recorded={OKS: b'synthetic OKS'})
    r2 = run(pkg2)  # Ground is on disk but recorded nowhere
    assert r2.returncode == 1 and GROUND in r2.stderr and 'not recorded' in r2.stderr


# ---- real producer shapes: record_export as export_npm.py / ground_json_to_fbx.py / export_core.py call it ----
def _producer_pkg(tmp, shape):
    """shape 'A': export_npm.py canonical export_meta.json for _01 + Ground from its own route (sidecar);
    shape 'B': per-FBX sidecars for _01 and Ground (Max export_core / package_max)."""
    from adapters.max.agr_tools.export_meta import record_export
    pkg = tmp / 'fbx'
    pkg.mkdir()
    (pkg / OKS).write_bytes(b'synthetic OKS')
    (pkg / GROUND).write_bytes(b'synthetic Ground')
    master = tmp / 'master.blend'
    master.write_bytes(b'synthetic master')
    if shape == 'A':
        record_export(pkg / OKS, source=str(master), top=3.5, metadata_path=pkg / 'export_meta.json', master=master)
    else:
        record_export(pkg / OKS, source='synthetic max scene', top=3.5)
    record_export(pkg / GROUND, source='synthetic ground.json', top=0.2, address='Synthetic_Ground', profile='vpm')
    return pkg


@pytest.mark.parametrize('shape', ['A', 'B'])
def test_real_producer_package_passes(tmp_path, shape):
    """r1 P1-1: OKS and Ground recorded by their own exporters bind both members; exit 0 as on main."""
    pkg = _producer_pkg(tmp_path, shape)
    r = run(pkg)
    assert r.returncode == 0, r.stderr
    with zipfile.ZipFile(tmp_path / '0000_Synthetic.zip') as z:
        assert sorted(z.namelist()) == [OKS, GROUND]
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert report['problems'] == [] and {m['status'] for m in report['export_binding']['members']} == {'match'}
    assert sorted(report['export_binding']['records']) == sorted(
        ['export_meta.json', GROUND + '.export_meta.json'] if shape == 'A'
        else [OKS + '.export_meta.json', GROUND + '.export_meta.json'])


@pytest.mark.parametrize('shape', ['A', 'B'])
def test_real_producer_package_with_foreign_02_is_refused(tmp_path, shape):
    pkg = _producer_pkg(tmp_path, shape)
    (pkg / '0000_Synthetic_02.fbx').write_bytes(b'foreign FBX dropped in after export')
    r = run(pkg)
    assert r.returncode == 1 and '0000_Synthetic_02.fbx' in r.stderr and 'not recorded' in r.stderr
    assert outputs(tmp_path) == ['master.blend']


@pytest.mark.parametrize('shape', ['A', 'B'])
@pytest.mark.parametrize('victim', [OKS, GROUND])
def test_real_producer_fbx_edited_after_export_is_refused(tmp_path, shape, victim):
    """r1 P1-2: exported_files records from record_export carry the hash; an edited FBX is refused by name."""
    pkg = _producer_pkg(tmp_path, shape)
    (pkg / victim).write_bytes(b'edited after export')
    r = run(pkg)
    assert r.returncode == 1 and victim in r.stderr and 'SHA-256' in r.stderr, r.stderr
    assert outputs(tmp_path) == ['master.blend']


def test_one_fbx_recorded_twice_with_different_hashes_is_refused(tmp_path):
    pkg = _producer_pkg(tmp_path, 'A')
    meta = json.loads((pkg / 'export_meta.json').read_text(encoding='utf-8'))
    meta['exported_sha256'][OKS] = '0' * 64
    (pkg / (OKS + '.export_meta.json')).write_text(json.dumps(meta), encoding='utf-8')
    r = run(pkg)
    assert r.returncode == 1 and OKS in r.stderr and 'recorded twice' in r.stderr
    assert outputs(tmp_path) == ['master.blend']


def test_record_export_writes_the_fbx_hash(tmp_path):
    from adapters.max.agr_tools.export_meta import load_meta, record_export, validate_meta
    fbx = tmp_path / OKS
    fbx.write_bytes(b'bytes')
    meta = load_meta(record_export(fbx, source='synthetic'))
    assert meta['exported_sha256'] == {OKS: _sha(b'bytes')} and meta['exported_files'] == [OKS]
    for bad in ({OKS: 'X' * 64}, {GROUND: _sha(b'bytes')}, {}, [OKS]):
        with pytest.raises(ValueError, match='exported_sha256'):
            validate_meta({**meta, 'exported_sha256': bad})
    lone = {k: v for k, v in meta.items() if k != 'exported_files'}
    lone['provenance'] = {k: v for k, v in meta['provenance'].items() if k != 'exported_files'}
    with pytest.raises(ValueError, match='exported_sha256'):
        validate_meta(lone)


def test_case_variant_record_is_not_a_match(tmp_path):
    """Path alias: a record spelled with another case does not bind the member; both names are refused."""
    pkg = make_pkg(tmp_path, recorded={OKS.lower(): b'synthetic OKS', GROUND: b'synthetic Ground'})
    r = run(pkg)
    assert r.returncode == 1 and OKS in r.stderr and OKS.lower() in r.stderr
    assert outputs(tmp_path) == []


def test_file_changed_between_check_and_zip_is_refused(tmp_path, monkeypatch):
    """State changing during the run: the written ZIP is read back and compared with the recorded hashes."""
    sys.path.insert(0, str(ROOT / 'tools/derive'))
    pn = _load(ROOT / 'tools/derive/package_npm.py', 'package_npm_1637')
    pkg = make_pkg(tmp_path)
    write = pn.package_core._write_zip

    def swap(folder, archive, target, **kwargs):
        (pkg / OKS).write_bytes(b'swapped after the binding check')
        return write(folder, archive, target, **kwargs)
    monkeypatch.setattr(pn.package_core, '_write_zip', swap)
    with pytest.raises(ValueError, match=OKS):
        pn.main([str(pkg)])
    assert outputs(tmp_path) == []


def test_generated_mismatches_are_always_refused(tmp_path):
    """Probe: random subsets of foreign / missing / edited FBX never produce a clean package (seed 1637, 40 cases)."""
    rng = random.Random(1637)
    names = [f'0000_Synthetic_{i:02d}.fbx' for i in range(1, 6)] + [GROUND]
    for case in range(40):
        files = {n: f'{n} bytes {case}'.encode() for n in names}
        recorded = dict(files)
        kind = rng.choice(['foreign', 'missing', 'edited'])
        victim = rng.choice(names)
        if kind == 'foreign':
            recorded.pop(victim)
        elif kind == 'missing':
            files.pop(victim)
        base = tmp_path / str(case)
        base.mkdir()
        pkg = make_pkg(base, files=files, recorded=recorded, key=rng.choice(['fbx_records', 'exported_sha256']))
        if kind == 'edited':
            (pkg / victim).write_bytes(b'edited')
        r = run(pkg)
        assert r.returncode == 1 and victim in r.stderr, (case, kind, victim, r.stderr)
        assert outputs(base) == [], (case, kind)


# ---- validate --profile npm with a build manifest ---------------------------------------------------------
bm_tests = _load(ROOT / 'tests/qa/test_build_manifest_1423.py', 'build_manifest_tests_1637')
vp = bm_tests.vp


def _v001_manifest(rep):
    return bm_tests._v001_manifest(rep)


def test_npm_manifest_without_master_fails(tmp_path, capsys):
    _, _, package, _ = bm_tests.good(tmp_path)
    rep = vp.validate(package, 'npm', vp.load_profiles())
    assert _v001_manifest(rep) == [('fail', 'manifest_master_missing')] and rep.exit_code == 1
    capsys.readouterr()
    assert vp.main([str(package), '--profile', 'npm', '--json']) == 1
    out = json.loads(capsys.readouterr().out)
    (v001,) = [s for s in out['stages'] if s['id'] == 'V001']
    (row,) = [f for f in v001['findings'] if f['name'] == 'build manifest']
    assert row['status'] == 'fail' and 'no --master' in row['observed'] and package.stem + '.build.json' in row['observed']


def test_npm_without_manifest_keeps_old_behaviour(tmp_path):
    _, _, package = bm_tests.make_set(tmp_path)
    rows = _v001_manifest(vp.validate(package, 'npm', vp.load_profiles()))
    assert rows and all(s == 'not_run' for s, _ in rows)


def test_npm_only_direct_blend_master_passes_with_master(tmp_path):
    """npm-only-direct: the master is the NPM .blend; with --master the build manifest check passes."""
    master, export, package = bm_tests.make_set(tmp_path)
    blend = tmp_path / '0000_Kpp_1.blend'
    blend.write_bytes(master.read_bytes())
    master.unlink()
    rec = bm_tests.record(tmp_path, blend, export, sorted(bm_tests.NPM))
    assert bm_tests.build(package, blend, [rec]) == 0
    assert _v001_manifest(vp.validate(package, 'npm', vp.load_profiles(), master=blend)) == [('pass', None)]
    assert _v001_manifest(vp.validate(package, 'npm', vp.load_profiles())) == [('fail', 'manifest_master_missing')]
