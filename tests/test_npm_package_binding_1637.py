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
    assert binding['source'] == 'fbx_records'
    assert sorted(binding['members'], key=lambda m: m['name']) == [
        {'name': OKS, 'recorded_sha256': _sha(b'synthetic OKS'), 'zip_sha256': _sha(b'synthetic OKS'), 'status': 'match'},
        {'name': GROUND, 'recorded_sha256': _sha(b'synthetic Ground'), 'zip_sha256': _sha(b'synthetic Ground'),
         'status': 'match'}]


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


def test_exported_files_binds_names_both_ways(tmp_path):
    pkg = make_pkg(tmp_path, key='exported_files')
    r = run(pkg)
    assert r.returncode == 0, r.stderr
    report = json.loads((tmp_path / 'package_report.json').read_text(encoding='utf-8'))
    assert report['export_binding']['source'] == 'exported_files'
    assert {m['status'] for m in report['export_binding']['members']} == {'hash_not_recorded'}
    assert all(m['recorded_sha256'] is None and len(m['zip_sha256']) == 64 for m in report['export_binding']['members'])
    (tmp_path / 'b').mkdir()
    pkg2 = make_pkg(tmp_path / 'b', key='exported_files', recorded={OKS: b''})
    r2 = run(pkg2)  # Ground is on disk but not in exported_files
    assert r2.returncode == 1 and GROUND in r2.stderr and 'not recorded' in r2.stderr


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

    def swap(folder, archive, target):
        (pkg / OKS).write_bytes(b'swapped after the binding check')
        return write(folder, archive, target)
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
        pkg = make_pkg(base, files=files, recorded=recorded)
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
