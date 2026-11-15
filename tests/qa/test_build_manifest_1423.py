"""#1423 delivery set consistency: build manifest + FBX export owner readback, refusal in validate_package."""
import importlib.util
import json
import math
import os
import random
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load(ROOT / 'tools/derive/build_manifest.py', 'build_manifest_cli_1423')
vp = _load(ROOT / 'tools/qa/validate_package.py', 'validate_package_1423')
pc = _load(ROOT / 'adapters/max/agr_tools/package_core.py', 'package_core_1423')
ec = _load(ROOT / 'adapters/max/agr_tools/edit_core.py', 'edit_core_1423')

NPM = {'0000_Kpp_1_01.fbx': b'Kaydara FBX Binary  \x00 oks part 01', '0000_Kpp_1_Ground.fbx': b'Kaydara FBX Binary  \x00 ground'}


def good_rb(path):
    """Readback stand-in: a visual mesh, its UCX, materials and one UV channel."""
    stem = Path(path).stem
    meshes = [{'name': 'SM_' + stem, 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
               'materials': ['M_' + stem], 'uv_channels': 1, 'triangles': 12},
              {'name': 'UCX_SM_' + stem + '_01', 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
               'materials': [], 'uv_channels': 0, 'triangles': 12}]
    return {'readback_ok': True, 'blender': 'stub', 'meshes': meshes}


def make_set(tmp, files=NPM, master_bytes=b'master revision A', name='0000_Kpp_1.zip'):
    tmp.mkdir(parents=True, exist_ok=True)
    master = tmp / 'master.fbx'
    master.write_bytes(master_bytes)
    export = tmp / 'export'
    export.mkdir()
    for n, d in files.items():
        (export / n).write_bytes(d)
    package = tmp / name
    with zipfile.ZipFile(package, 'w') as z:
        for n, d in files.items():
            z.writestr(n, d)
    return master, export, package


def record(tmp, master, export, names, out='rec.json'):
    argv = ['record', *[str(export / n) for n in names], '--master', str(master), '--out', str(tmp / out),
            '--builder-commit', 'abc1234']
    assert cli.main(argv) == 0
    return tmp / out


def build(package, master, recs, *extra, reader=good_rb):
    argv = ['build', str(package), '--master', str(master), '--derivation', *map(str, recs),
            '--transform-name', 'identity', '--builder-commit', 'abc1234', *extra]
    return cli.main(argv, reader=reader)


def findings(package, master=None):
    data = package.read_bytes()
    with zipfile.ZipFile(package) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    mp = Path(bm.manifest_path(package))
    raw = mp.read_bytes() if mp.is_file() else None
    return bm.manifest_findings(raw, members, package.name, bm.sha256_bytes(data),
                                bm.sha256_file(master) if master else None, str(package.parent))


def codes(rows):
    return sorted({c for s, c, _ in rows if s != 'pass'})


def good(tmp):
    master, export, package = make_set(tmp)
    rec = record(tmp, master, export, sorted(NPM))
    assert build(package, master, [rec]) == 0
    return master, export, package, rec


# ---- acceptance point 1: manifest content and refusals ---------------------------------------------------
def test_good_build_manifest_passes_and_names_every_artifact(tmp_path):
    master, _, package, _ = good(tmp_path)
    assert [(s, c) for s, c, _ in findings(package, master)] == [('pass', 'manifest_ok')]
    m = json.loads(Path(bm.manifest_path(package)).read_text(encoding='utf-8'))
    assert m['master'] == {'name': 'master.fbx', 'sha256': bm.sha256_file(master), 'builder_commit': 'abc1234'}
    assert [a['name'] for a in m['artifacts']] == sorted(NPM)
    assert m['artifacts'][0]['parts'] == ['SM_0000_Kpp_1_01', 'UCX_SM_0000_Kpp_1_01_01']
    assert m['transform'] == {'name': 'identity', 'file': None, 'sha256': None}
    check = m['checks'][0]
    assert check['id'] == 'fbx_readback' and check['status'] == 'pass' and check['finished'] is True
    assert check['subjects'] == {n: bm.sha256_bytes(d) for n, d in NPM.items()}
    assert check['report_sha256'] == bm.sha256_file(bm.readback_path(package))


def test_stale_npm_after_master_edit_is_refused(tmp_path):
    """Master edited after the OKS FBX export, Ground re-exported from the new master: two revisions -> refused."""
    master, export, package = make_set(tmp_path)
    rec_old = record(tmp_path, master, export, ['0000_Kpp_1_01.fbx'], 'rec-old.json')
    master.write_bytes(b'master revision B: one roof part moved')
    rec_new = record(tmp_path, master, export, ['0000_Kpp_1_Ground.fbx'], 'rec-new.json')
    assert build(package, master, [rec_old, rec_new]) == 0
    rows = findings(package, master)
    assert codes(rows) == ['manifest_master_mismatch']
    assert '0000_Kpp_1_01.fbx' in [d for s, c, d in rows if c == 'manifest_master_mismatch'][0]


def test_master_changed_after_build_is_stale(tmp_path):
    master, _, package, _ = good(tmp_path)
    master.write_bytes(b'master revision B')
    assert codes(findings(package, master)) == ['manifest_master_stale']


def test_zipped_bytes_differ_from_manifest(tmp_path):
    master, _, package, _ = good(tmp_path)
    with zipfile.ZipFile(package, 'w') as z:
        for n, d in NPM.items():
            z.writestr(n, d + (b'!' if n.endswith('01.fbx') else b''))
    assert {'manifest_hash_mismatch', 'manifest_package', 'manifest_report_hash'} <= set(codes(findings(package)))


def test_artifact_changed_after_its_export_record(tmp_path):
    master, export, package = make_set(tmp_path)
    rec = record(tmp_path, master, export, sorted(NPM))
    data = json.loads(rec.read_text(encoding='utf-8'))
    data['artifacts']['0000_Kpp_1_01.fbx']['sha256'] = '0' * 64
    rec2 = tmp_path / 'rec2.json'
    rec2.write_text(json.dumps(data), encoding='utf-8')
    assert build(package, master, [rec2]) == 0
    assert codes(findings(package, master)) == ['manifest_derived_changed']


@pytest.mark.parametrize('status,finished', [('skipped', True), ('not_run', True), ('running', False),
                                             ('pass', False), ('fail', True)])
def test_required_check_not_finished_or_skipped_is_not_ready(tmp_path, status, finished):
    master, _, package, _ = good(tmp_path)
    mp = Path(bm.manifest_path(package))
    m = json.loads(mp.read_text(encoding='utf-8'))
    m['checks'][0]['status'], m['checks'][0]['finished'] = status, finished
    mp.write_bytes(bm.dumps(m))
    assert codes(findings(package, master)) == ['manifest_check_not_ready']


def test_no_readback_means_required_check_did_not_run(tmp_path):
    master, export, package = make_set(tmp_path)
    rec = record(tmp_path, master, export, sorted(NPM))
    assert build(package, master, [rec], '--no-readback') == 0
    assert codes(findings(package, master)) == ['manifest_check_not_ready']


def test_report_file_changed_or_missing(tmp_path):
    master, _, package, _ = good(tmp_path)
    rp = Path(bm.readback_path(package))
    rp.write_bytes(rp.read_bytes() + b' ')
    assert codes(findings(package, master)) == ['manifest_report_hash']
    rp.unlink()
    assert codes(findings(package, master)) == ['manifest_report_hash']


def test_readback_ran_on_other_bytes(tmp_path):
    master, _, package, _ = good(tmp_path)
    mp = Path(bm.manifest_path(package))
    m = json.loads(mp.read_text(encoding='utf-8'))
    m['checks'][0]['subjects']['0000_Kpp_1_Ground.fbx'] = '1' * 64
    del m['checks'][0]['subjects']['0000_Kpp_1_01.fbx']
    mp.write_bytes(bm.dumps(m))
    rows = findings(package, master)
    assert codes(rows) == ['manifest_report_hash']
    detail = [d for s, c, d in rows if c == 'manifest_report_hash'][0]
    assert "uncovered ['0000_Kpp_1_01.fbx']" in detail and '0000_Kpp_1_Ground.fbx' in detail


def test_unlisted_and_missing_members(tmp_path):
    master, _, package, _ = good(tmp_path)
    mp = Path(bm.manifest_path(package))
    m = json.loads(mp.read_text(encoding='utf-8'))
    m['artifacts'][0]['name'] = '0000_Kpp_1_02.fbx'
    mp.write_bytes(bm.dumps(m))
    assert {'manifest_member_unlisted', 'manifest_member_missing'} <= set(codes(findings(package, master)))


def test_no_manifest_is_not_run_never_pass(tmp_path):
    _, _, package = make_set(tmp_path)
    assert [(s, c) for s, c, _ in findings(package)] == [('not_run', 'manifest_missing')]


@pytest.mark.parametrize('mutate', [
    lambda m: m.update({'extra': 1}),
    lambda m: m['master'].update({'path': 'x'}),
    lambda m: m.update({'schema': 'agr.build_manifest/0'}),
    lambda m: m['artifacts'][0].update({'kind': 'mystery'}),
    lambda m: m['artifacts'].append(dict(m['artifacts'][0])),
    lambda m: m.update({'artifacts': []}),
    lambda m: m['master'].update({'sha256': 'ABC'}),
    lambda m: m['transform'].update({'name': ''}),
    lambda m: m['transform'].update({'file': 'bridge.json'}),
])
def test_malformed_manifest_is_refused(tmp_path, mutate):
    master, _, package, _ = good(tmp_path)
    mp = Path(bm.manifest_path(package))
    m = json.loads(mp.read_text(encoding='utf-8'))
    mutate(m)
    mp.write_text(json.dumps(m), encoding='utf-8')
    assert codes(findings(package, master)) == ['manifest_unreadable']


@pytest.mark.parametrize('text', ['', '[]', '{"schema": 1, "schema": 2}', '{"a": NaN}', '{"a": Infinity}', '\xff'])
def test_unparsable_manifest_bytes(text):
    raw = text.encode('latin-1')
    assert codes(bm.manifest_findings(raw, {'a.fbx': '0' * 64}, 'x.zip')) == ['manifest_unreadable']


def test_empty_member_set_is_refused():
    assert codes(bm.manifest_findings(b'{}', {}, 'x.zip')) == ['manifest_unreadable']


# ---- writer refusals: nothing written --------------------------------------------------------------------
def _outputs(package):
    return [p for p in (bm.manifest_path(package), bm.readback_path(package)) if os.path.exists(p)]


def test_unrecorded_member_refused_nothing_written(tmp_path):
    master, export, package = make_set(tmp_path)
    rec = record(tmp_path, master, export, ['0000_Kpp_1_01.fbx'])
    assert build(package, master, [rec]) == 2
    assert _outputs(package) == []


def test_existing_output_is_never_overwritten(tmp_path):
    master, _, package, rec = good(tmp_path)
    before = Path(bm.manifest_path(package)).read_bytes()
    assert build(package, master, [rec]) == 2
    assert Path(bm.manifest_path(package)).read_bytes() == before


def test_output_alias_of_an_input_is_refused(tmp_path):
    master, export, package = make_set(tmp_path)
    rec = record(tmp_path, master, export, sorted(NPM))
    alias = Path(bm.manifest_path(package))
    alias.write_text('{"transform": 1}', encoding='utf-8')
    before = alias.read_bytes()
    assert build(package, master, [rec], '--transform-file', str(alias)) == 2
    assert alias.read_bytes() == before and not os.path.exists(bm.readback_path(package))


def test_record_refuses_master_as_artifact_and_empty_artifact(tmp_path):
    master, export, _ = make_set(tmp_path)
    assert cli.main(['record', str(master), '--master', str(master), '--out', str(tmp_path / 'r.json')]) == 2
    (export / 'empty.fbx').write_bytes(b'')
    assert cli.main(['record', str(export / 'empty.fbx'), '--master', str(master),
                     '--out', str(tmp_path / 'r.json')]) == 2
    (export / 'notes.txt').write_bytes(b'x')
    assert cli.main(['record', str(export / 'notes.txt'), '--master', str(master),
                     '--out', str(tmp_path / 'r.json')]) == 2  # unmapped kind: an error naming it
    assert not (tmp_path / 'r.json').exists()


def test_two_records_naming_different_masters_for_one_artifact_refused(tmp_path):
    master, export, package = make_set(tmp_path)
    a = record(tmp_path, master, export, sorted(NPM), 'a.json')
    master.write_bytes(b'B')
    b = record(tmp_path, master, export, sorted(NPM), 'b.json')
    assert build(package, master, [a, b]) == 2 and _outputs(package) == []


# ---- acceptance point 2: export owner readback ---------------------------------------------------------
def test_readback_summary_binds_ucx_and_reads_materials_uv():
    s = bm.readback_summary('a.fbx', '0' * 64, good_rb('C:/x/a.fbx'))
    assert s['status'] == 'pass' and s['ucx_binding'] == {'UCX_SM_a_01': 'SM_a'}
    assert s['meshes'][0]['dimensions_m'] == [1, 2, 3] and s['meshes'][0]['location'] == [10, 20, 0]


@pytest.mark.parametrize('edit,needle', [
    (lambda rb: rb['meshes'][1].update({'name': 'UCX_SM_other_01'}), 'UCX_SM_other_01: no visual mesh'),
    (lambda rb: rb['meshes'][0].update({'materials': []}), 'empty material slot'),
    (lambda rb: rb['meshes'][0].update({'materials': [None]}), 'empty material slot'),
    (lambda rb: rb['meshes'][0].update({'uv_channels': 0}), 'no UV channel'),
    (lambda rb: rb['meshes'][0].update({'bounds_m': [[0, 0, math.nan], [1, 2, 3]]}), 'dimensions not read'),
    (lambda rb: rb.update({'readback_ok': False}), 'readback not ok'),
    (lambda rb: rb.update({'meshes': []}), 'no mesh read back'),
])
def test_readback_summary_fails_closed(edit, needle):
    rb = good_rb('a.fbx')
    edit(rb)
    s = bm.readback_summary('a.fbx', '0' * 64, rb)
    assert s['status'] == 'fail' and any(needle in p for p in s['problems']), s['problems']


def test_readback_exception_is_a_failed_check(tmp_path):
    master, export, package = make_set(tmp_path)
    rec = record(tmp_path, master, export, sorted(NPM))

    def boom(path):
        raise TimeoutError('blender hung')
    assert build(package, master, [rec], reader=boom) == 0
    assert codes(findings(package, master)) == ['manifest_check_not_ready']


# ---- validate_package / package_core integration ----------------------------------------------------------
def _v001_manifest(report):
    st = {s.id: s for s in report.stages}
    return [(f.status, f.data.get('code')) for f in st['V001'].findings if f.name == 'build manifest']


def test_validate_package_reads_manifest_beside_zip(tmp_path):
    master, _, package, _ = good(tmp_path)
    assert _v001_manifest(vp.validate(package, 'npm', vp.load_profiles(), master=master)) == [('pass', None)]
    master.write_bytes(b'edited')
    rep = vp.validate(package, 'npm', vp.load_profiles(), master=master)
    assert ('fail', 'manifest_master_stale') in _v001_manifest(rep) and rep.exit_code == 1


def test_valid_manifest_without_master_is_never_pass(tmp_path, capsys):
    """r1 P1: no master given -> the stale check did not run -> V001 not_run manifest_master_unchecked, no pass;
    via the core, validate_package.main and package_core.qa_package (Max qa.package passes no master)."""
    master, _, package, _ = good(tmp_path)
    assert [(s, c) for s, c, _ in findings(package)] == [('not_run', 'manifest_master_unchecked')]
    capsys.readouterr()  # drop the build CLI output
    assert vp.main([str(package), '--profile', 'npm', '--json']) != 0
    rep = json.loads(capsys.readouterr().out)
    (v001,) = [s for s in rep['stages'] if s['id'] == 'V001']
    rows = [(f['status'], (f.get('data') or {}).get('code')) for f in v001['findings'] if f['name'] == 'build manifest']
    assert rows == [('not_run', 'manifest_master_unchecked')] and v001['status'] != 'pass'
    r = pc.qa_package(ec, package, pc.subprocess_runner, sys.executable, ROOT, profile='npm', scene=False)
    (table,) = r['plan']['reports']
    (st,) = [s for s in table['stages'] if s['id'] == 'V001']
    assert st['status'] != 'pass' and any(x.startswith('not_run: build manifest:') and 'manifest_master_unchecked' in x
                                          for x in st['non_pass'])
    assert r['plan']['exit_code'] != 0
    master.write_bytes(b'edited')  # with the master given the stale check still refuses
    assert codes(findings(package, master)) == ['manifest_master_stale']


def test_validate_package_cli_fresh_process_refuses_stale(tmp_path):
    master, export, package = make_set(tmp_path)
    rec_old = record(tmp_path, master, export, ['0000_Kpp_1_01.fbx'], 'o.json')
    master.write_bytes(b'B')
    rec_new = record(tmp_path, master, export, ['0000_Kpp_1_Ground.fbx'], 'n.json')
    assert build(package, master, [rec_old, rec_new]) == 0
    proc = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'validate', str(package), '--profile', 'npm',
                           '--json'], capture_output=True, cwd=str(ROOT))
    assert proc.returncode == 1, proc.stderr[-500:]
    rep = json.loads(proc.stdout.decode('utf-8'))
    v001 = [s for s in rep['stages'] if s['id'] == 'V001'][0]
    assert any(f['name'] == 'build manifest' and f['data'].get('code') == 'manifest_master_mismatch'
               for f in v001['findings'])


def test_validate_package_build_manifest_flag_missing_file_exits_2(tmp_path):
    _, _, package = make_set(tmp_path)
    assert vp.main([str(package), '--build-manifest', str(tmp_path / 'none.build.json')]) == 2
    assert vp.main([str(package), '--build-manifest', str(package)]) == 2  # the package itself


def test_package_core_cross_masters_refuses_two_revisions(tmp_path):
    m1, _, p1, _ = good(tmp_path / 'a')
    (tmp_path / 'a' / 'b').mkdir()
    m2, _, p2, _ = good(tmp_path / 'a' / 'b')
    assert pc.cross_masters([str(p1)]) == {}
    dst = tmp_path / 'a' / 'SM_Kpp_1.zip'
    os.link(p2, dst)
    Path(bm.manifest_path(dst)).write_bytes(Path(bm.manifest_path(p2)).read_bytes())
    assert pc.cross_masters([str(p1), str(dst)]) == {}  # same master bytes -> one revision
    m = json.loads(Path(bm.manifest_path(dst)).read_text(encoding='utf-8'))
    m['master']['sha256'] = 'f' * 64
    Path(bm.manifest_path(dst)).write_bytes(bm.dumps(m))
    out = pc.cross_masters([str(p1), str(dst)])
    assert sorted(out) == ['0000_Kpp_1.zip', 'SM_Kpp_1.zip']
    assert out['SM_Kpp_1.zip'][0][0] == 'manifest_cross_master'


# ---- generated probe: any single inconsistency is never pass -----------------------------------------------
def test_probe_random_single_mutation_never_passes(tmp_path):
    rng = random.Random(1423)
    master, _, package, _ = good(tmp_path)
    mp = Path(bm.manifest_path(package))
    base = json.loads(mp.read_text(encoding='utf-8'))
    with zipfile.ZipFile(package) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    pkg_sha, master_sha = bm.sha256_file(package), bm.sha256_file(master)
    run = lambda m: bm.manifest_findings(bm.dumps(m), members, package.name, pkg_sha, master_sha, str(tmp_path))
    assert codes(run(base)) == []
    mutations = [
        lambda m, i: m['artifacts'][i].update({'sha256': rng.choice('0123456789abcdef') * 64}),
        lambda m, i: m['artifacts'][i].update({'master_sha256': 'e' * 64}),
        lambda m, i: m['artifacts'][i].update({'derived_sha256': 'd' * 64}),
        lambda m, i: m['master'].update({'sha256': 'c' * 64}),
        lambda m, i: m['checks'][0].update({'status': rng.choice(['skipped', 'not_run', 'fail', 'review', ''])}),
        lambda m, i: m['checks'][0].update({'finished': rng.choice([False, None, 0, 'true'])}),
        lambda m, i: m['checks'][0].update({'report_sha256': 'b' * 64}),
        lambda m, i: m['checks'][0]['subjects'].pop(m['artifacts'][i]['name']),
        lambda m, i: m.update({'checks': []}),
        lambda m, i: m['package'].update({'sha256': 'a' * 64}),
        lambda m, i: m['artifacts'].pop(i),
    ]
    n = 0
    for _ in range(300):
        m = json.loads(json.dumps(base))
        rng.choice(mutations)(m, rng.randrange(len(m['artifacts'])))
        if m == base:
            continue
        n += 1
        rows = run(m)
        assert not any(s == 'pass' for s, _, _ in rows) and any(s == 'fail' for s, _, _ in rows), m
        no_master = bm.manifest_findings(bm.dumps(m), members, package.name, pkg_sha, None, str(tmp_path))
        assert not any(s == 'pass' for s, _, _ in no_master), m  # r1 P1: without the master never pass
    assert n >= 250
