"""new-case: one master per package role (#1525, [D324]): OKS artifacts from the OKS master, Ground from its own source.

Build manifest schema v2 keeps `masters` keyed by role; two revisions of one role are refused; `--master role=path`.
The real Ground producer (tools/blender/ground_json_to_fbx.py) runs in tests/qa/test_ground_master_1525_blender.py.
"""
import random
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402
from adapters.max.agr_tools import package_core as pc  # noqa: E402
from tools.derive import build_manifest as cli  # noqa: E402

OKS = {'0000_Syn_01.fbx': b'Kaydara FBX Binary  \x00 oks 01', '0000_Syn_02.fbx': b'Kaydara FBX Binary  \x00 oks 02'}
GROUND = {'0000_Syn_Ground.fbx': b'Kaydara FBX Binary  \x00 ground'}


def good_rb(path):
    """Readback stand-in (as tests/qa/test_build_manifest_1423.py): a visual mesh, its UCX, materials, one UV set."""
    stem = Path(path).stem
    meshes = [{'name': 'SM_' + stem, 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
               'materials': ['M_' + stem], 'uv_channels': 1, 'triangles': 12},
              {'name': 'UCX_SM_' + stem + '_01', 'bounds_m': [[0, 0, 0], [1, 2, 3]], 'location': [10, 20, 0],
               'materials': [], 'uv_channels': 0, 'triangles': 12}]
    return {'readback_ok': True, 'blender': 'stub', 'meshes': meshes}


def masters(tmp):
    tmp.mkdir(parents=True, exist_ok=True)
    oks, ground = tmp / 'Syn_master.blend', tmp / 'ground_mesh.json'
    oks.write_bytes(b'synthetic OKS master revision A')
    ground.write_bytes(b'{"synthetic": "ground source revision A"}')
    return oks, ground


def export(tmp, files, master, role):
    """One export of `files` from `master`; the producer hook writes its record into the export's store."""
    out = tmp / ('export-' + next(iter(files))[:-4]) / 'fbx'
    out.mkdir(parents=True)
    for n, d in files.items():
        (out / n).write_bytes(d)
    store = bm.derivation_store(out)
    sha = bm.sha256_file(master)
    for n in files:
        bm.write_export_derivation([out / n], master, store, 'abc1234', master_sha256=sha, role=role)
    return store


def package(tmp, files, name='0000_Syn.zip'):
    p = tmp / name
    with zipfile.ZipFile(p, 'w') as z:
        for n, d in files.items():
            z.writestr(n, d)
    return p


def mixed(tmp):
    oks, ground = masters(tmp / 'in')
    stores = [export(tmp, OKS, oks, 'oks'), export(tmp, GROUND, ground, 'ground')]
    return package(tmp, {**OKS, **GROUND}), oks, ground, stores


def build(pkg, master_args, stores):
    argv = ['build', str(pkg), *[x for m in master_args for x in ('--master', m)], '--derivation',
            *map(str, stores), '--transform-name', 'identity', '--builder-commit', 'abc1234']
    return cli.main(argv, reader=good_rb)


def findings(pkg, current):
    with zipfile.ZipFile(pkg) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    raw = Path(bm.manifest_path(pkg)).read_bytes()
    return [(s, c) for s, c, _ in bm.manifest_findings(raw, members, pkg.name, bm.sha256_file(pkg), current,
                                                         str(pkg.parent))]


def details(pkg, current):
    with zipfile.ZipFile(pkg) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    raw = Path(bm.manifest_path(pkg)).read_bytes()
    return bm.manifest_findings(raw, members, pkg.name, bm.sha256_file(pkg), current, str(pkg.parent))


def shas(oks, ground):
    return {'oks': bm.sha256_file(oks), 'ground': bm.sha256_file(ground)}


# ---- acceptance: OKS + Ground from the producers' record hooks -> manifest_ok ----------------------------------
def test_oks_plus_ground_package_from_producer_records_gets_manifest_ok(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    m = bm.parse_manifest(Path(bm.manifest_path(pkg)).read_bytes())
    assert m['schema'] == 'agr.build_manifest/2'
    assert m['masters']['oks']['sha256'] == bm.sha256_file(oks)
    assert m['masters']['ground']['sha256'] == bm.sha256_file(ground)
    assert m['masters']['ground']['name'] == 'ground_mesh.json'
    assert {a['name']: a['role'] for a in m['artifacts']} == {
        '0000_Syn_01.fbx': 'oks', '0000_Syn_02.fbx': 'oks', '0000_Syn_Ground.fbx': 'ground'}
    assert findings(pkg, shas(oks, ground)) == [('pass', 'manifest_ok')]


def test_missing_ground_record_is_refused_naming_the_member(tmp_path, capsys):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores[:1]) == 2
    assert '0000_Syn_Ground.fbx' in capsys.readouterr().err
    assert not Path(bm.manifest_path(pkg)).exists()


def test_ground_record_naming_the_oks_master_is_refused(tmp_path, capsys):
    """Option B of the #1525 question (false provenance): a Ground member recorded as derived from the OKS master."""
    oks, ground = masters(tmp_path / 'in')
    stores = [export(tmp_path, OKS, oks, 'oks'), export(tmp_path, GROUND, oks, 'oks')]
    pkg = package(tmp_path, {**OKS, **GROUND})
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 2
    err = capsys.readouterr().err
    assert '0000_Syn_Ground.fbx' in err and 'role' in err
    assert not Path(bm.manifest_path(pkg)).exists()


def test_oks_member_recorded_as_ground_is_refused(tmp_path, capsys):
    oks, ground = masters(tmp_path / 'in')
    stores = [export(tmp_path, OKS, ground, 'ground'), export(tmp_path / 'g', GROUND, ground, 'ground')]
    pkg = package(tmp_path, {**OKS, **GROUND})
    assert build(pkg, ['ground=' + str(ground)], stores) == 2
    assert '0000_Syn_01.fbx' in capsys.readouterr().err


# ---- masters per role ----------------------------------------------------------------------------------------
def test_master_missing_for_a_role_refuses_the_build(tmp_path, capsys):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks)], stores) == 2
    assert 'ground' in capsys.readouterr().err
    assert not Path(bm.manifest_path(pkg)).exists()


def test_master_for_a_role_without_artifact_refuses_the_build(tmp_path, capsys):
    oks, ground = masters(tmp_path / 'in')
    stores = [export(tmp_path, OKS, oks, 'oks')]
    pkg = package(tmp_path, OKS)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 2
    assert 'ground' in capsys.readouterr().err


def test_single_unkeyed_master_on_a_mixed_package_is_refused(tmp_path, capsys):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, [str(oks)], stores) == 2
    assert 'role' in capsys.readouterr().err
    assert not Path(bm.manifest_path(pkg)).exists()


def test_single_unkeyed_master_on_a_one_role_package_still_builds(tmp_path):
    oks, _ = masters(tmp_path / 'in')
    stores = [export(tmp_path, OKS, oks, 'oks')]
    pkg = package(tmp_path, OKS)
    assert build(pkg, [str(oks)], stores) == 0
    assert findings(pkg, bm.sha256_file(oks)) == [('pass', 'manifest_ok')]


@pytest.mark.parametrize('args, word', [
    (['flora=X'], 'flora'), (['oks=A', 'oks=B'], 'twice'), (['oks='], 'empty'), (['A', 'oks=B'], 'mix'),
    (['A', 'B'], 'twice'), ([], 'master')])
def test_master_arguments_fail_closed(args, word):
    with pytest.raises(ValueError, match=word):
        bm.master_args(args)


def test_windows_drive_path_is_an_unkeyed_master():
    assert bm.master_args(['C:/x/m=1.blend']) == 'C:/x/m=1.blend'
    assert bm.master_args(['oks=C:/x/m.blend', 'ground=C:/x/g.json']) == {'oks': 'C:/x/m.blend',
                                                                           'ground': 'C:/x/g.json'}


def test_two_revisions_of_one_role_are_refused(tmp_path):
    oks, ground = masters(tmp_path / 'in')
    s1 = export(tmp_path, {'0000_Syn_01.fbx': OKS['0000_Syn_01.fbx']}, oks, 'oks')
    oks.write_bytes(b'synthetic OKS master revision B')
    s2 = export(tmp_path / 'b', {'0000_Syn_02.fbx': OKS['0000_Syn_02.fbx']}, oks, 'oks')
    s3 = export(tmp_path, GROUND, ground, 'ground')
    pkg = package(tmp_path, {**OKS, **GROUND})
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], [s1, s2, s3]) == 0
    rows = details(pkg, shas(oks, ground))
    assert ('fail', 'manifest_master_mismatch') in [(s, c) for s, c, _ in rows]
    detail = [d for s, c, d in rows if c == 'manifest_master_mismatch'][0]
    assert 'oks' in detail and '0000_Syn_01.fbx' in detail and 'Ground' not in detail
    assert 'pass' not in {s for s, _, _ in rows}


def test_ground_source_edited_after_build_is_stale_for_ground_only(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    ground.write_bytes(b'{"synthetic": "ground source revision B"}')
    rows = details(pkg, shas(oks, ground))
    assert [(s, c) for s, c, _ in rows] == [('fail', 'manifest_master_stale')]
    assert 'ground' in rows[0][2] and 'oks' not in rows[0][2]


def test_validation_without_the_ground_master_is_not_run_naming_ground(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    for current in ({'oks': bm.sha256_file(oks)}, bm.sha256_file(oks), None):
        rows = details(pkg, current)
        assert ('not_run', 'manifest_master_unchecked') in [(s, c) for s, c, _ in rows], current
        assert any('ground' in d for _, c, d in rows if c == 'manifest_master_unchecked')
        assert 'pass' not in {s for s, _, _ in rows}


def test_validation_master_for_an_absent_role_fails(tmp_path):
    oks, ground = masters(tmp_path / 'in')
    pkg = package(tmp_path, OKS)
    assert build(pkg, ['oks=' + str(oks)], [export(tmp_path, OKS, oks, 'oks')]) == 0
    rows = details(pkg, shas(oks, ground))
    assert [(s, c) for s, c, _ in rows] == [('fail', 'manifest_master_role')]


def test_validation_unknown_role_is_refused(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    rows = details(pkg, {**shas(oks, ground), 'flora': '0' * 64})
    assert ('fail', 'manifest_master_role') in [(s, c) for s, c, _ in rows]


# ---- manifest v2 parse: fail-closed --------------------------------------------------------------------------
def built(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    return bm.parse_manifest(Path(bm.manifest_path(pkg)).read_bytes())


@pytest.mark.parametrize('mutate, word', [
    (lambda m: m['artifacts'][2].__setitem__('role', 'oks'), 'role'),
    (lambda m: m['artifacts'][0].__setitem__('role', 'flora'), 'role'),
    (lambda m: m['artifacts'][0].pop('role'), 'missing'),
    (lambda m: m['masters'].pop('ground'), 'ground'),
    (lambda m: m['masters'].__setitem__('flora', dict(m['masters']['oks'])), 'flora'),
    (lambda m: m['masters'].clear(), 'masters'),
    (lambda m: m['masters']['oks'].__setitem__('sha256', 'x'), 'sha256'),
    (lambda m: m.__setitem__('master', m['masters']['oks']), 'unknown'),
])
def test_v2_manifest_mutations_are_unreadable(tmp_path, mutate, word):
    m = built(tmp_path)
    mutate(m)
    with pytest.raises(ValueError, match=word):
        bm.parse_manifest(bm.dumps(m))


def test_v1_manifest_still_parses_as_one_master_for_every_role(tmp_path):
    m = built(tmp_path)
    v1 = {k: v for k, v in m.items() if k != 'masters'}
    v1['schema'] = 'agr.build_manifest/1'
    v1['master'] = m['masters']['oks']
    v1['artifacts'] = [{k: v for k, v in a.items() if k != 'role'} for a in m['artifacts']]
    p = bm.parse_manifest(bm.dumps(v1))
    assert p['masters'] == {'oks': m['masters']['oks'], 'ground': m['masters']['oks']}
    assert [a['role'] for a in p['artifacts']] == ['oks', 'oks', 'ground']


# ---- derivation record role ----------------------------------------------------------------------------------
def test_role_of_follows_the_delivery_name_grammar():
    assert [bm.role_of(n) for n in ('0000_Syn_Ground.fbx', 'SM_Syn_Ground.fbx', 'SM_Syn_Ground_Light.fbx',
                                    '0000_Syn_Ground_1001.png', '0000_Syn_01.fbx', 'SM_Groundfloor_01.fbx',
                                    'UCX_SM_Syn_01.fbx', '0000_Syn.geojson')] == [
        'ground', 'ground', 'ground', 'ground', 'oks', 'oks', 'oks', 'oks']


def test_record_role_is_written_and_unknown_role_is_refused(tmp_path):
    oks, ground = masters(tmp_path / 'in')
    store = export(tmp_path, GROUND, ground, 'ground')
    rec = bm.check_derivation(bm.strict_json((Path(store) / '0000_Syn_Ground.fbx.derivation.json').read_bytes()))
    assert rec['role'] == 'ground' and rec['master_name'] == 'ground_mesh.json'
    with pytest.raises(ValueError, match='role'):
        bm.check_derivation(dict(rec, role='flora'))
    with pytest.raises(ValueError, match='role'):
        bm.write_export_derivation([tmp_path / 'export-0000_Syn_Ground' / 'fbx' / '0000_Syn_Ground.fbx'], ground,
                                   tmp_path / 'other', 'abc1234', role='Ground')
    assert not (tmp_path / 'other').exists()


def test_record_without_role_takes_it_from_the_names_and_refuses_mixed_roles(tmp_path):
    oks, _ = masters(tmp_path / 'in')
    out = tmp_path / 'x'
    out.mkdir()
    for n, d in {**OKS, **GROUND}.items():
        (out / n).write_bytes(d)
    assert bm.derivation_record([out / '0000_Syn_01.fbx'], oks, 'abc1234')['role'] == 'oks'
    with pytest.raises(ValueError, match='role'):
        bm.derivation_record([out / '0000_Syn_01.fbx', out / '0000_Syn_Ground.fbx'], oks, 'abc1234')


def test_old_record_without_role_key_is_read_by_member_name(tmp_path):
    oks, ground = masters(tmp_path / 'in')
    stores = [export(tmp_path, OKS, oks, 'oks'), export(tmp_path, GROUND, ground, 'ground')]
    for s in stores:
        for p in Path(s).iterdir():
            rec = bm.strict_json(p.read_bytes())
            rec.pop('role')
            p.write_bytes(bm.dumps(rec))
    pkg = package(tmp_path, {**OKS, **GROUND})
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    assert findings(pkg, shas(oks, ground)) == [('pass', 'manifest_ok')]


# ---- cross-package check per role ----------------------------------------------------------------------------
def two_packages(tmp, ground_b=False, oks_b=False):
    zips = []
    for i, part in enumerate(('a', 'b')):
        d = tmp / part
        oks, ground = masters(d / 'in')
        if (oks_b and part == 'b'):
            oks.write_bytes(b'synthetic OKS master revision B')
        if (ground_b and part == 'b'):
            ground.write_bytes(b'{"synthetic": "ground source revision B"}')
        stores = [export(d, OKS, oks, 'oks'), export(d, GROUND, ground, 'ground')]
        pkg = package(d, {**OKS, **GROUND}, '000{}_Syn.zip'.format(i))
        assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
        zips.append(str(pkg))
    return zips


def test_cross_masters_compares_per_role(tmp_path):
    assert pc.cross_masters(two_packages(tmp_path / 's')) == {}
    rows = pc.cross_masters(two_packages(tmp_path / 'g', ground_b=True))
    assert rows
    detail = [d for r in rows.values() for _, d in r][0]
    assert 'role ground' in detail and 'role oks' not in detail
    rows = pc.cross_masters(two_packages(tmp_path / 'o', oks_b=True))
    detail = [d for r in rows.values() for _, d in r][0]
    assert 'role oks' in detail and 'role ground' not in detail


def test_cross_masters_oks_package_beside_ground_package_is_not_a_conflict(tmp_path):
    oks, ground = masters(tmp_path / 'in')
    a, b = tmp_path / 'oks', tmp_path / 'gnd'
    pa = a / '0000_Syn.zip'
    pg = b / '0000_Syn_Ground.zip'
    a.mkdir()
    b.mkdir()
    with zipfile.ZipFile(pa, 'w') as z:
        for n, d in OKS.items():
            z.writestr(n, d)
    with zipfile.ZipFile(pg, 'w') as z:
        for n, d in GROUND.items():
            z.writestr(n, d)
    assert build(pa, ['oks=' + str(oks)], [export(a, OKS, oks, 'oks')]) == 0
    assert build(pg, ['ground=' + str(ground)], [export(b, GROUND, ground, 'ground')]) == 0
    assert pc.cross_masters([str(pa), str(pg)]) == {}


# ---- generated probe: any byte flip of any one master is named for that role only -----------------------------
def test_generated_probe_master_byte_flip_is_stale_for_its_role_only(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    rng = random.Random(1525)
    base = {'oks': oks.read_bytes(), 'ground': ground.read_bytes()}
    n = 0
    for _ in range(40):
        role = rng.choice(['oks', 'ground'])
        path = oks if role == 'oks' else ground
        data = bytearray(base[role])
        data[rng.randrange(len(data))] ^= 1 << rng.randrange(8)
        path.write_bytes(bytes(data))
        rows = details(pkg, shas(oks, ground))
        assert [(s, c) for s, c, _ in rows] == [('fail', 'manifest_master_stale')]
        assert role in rows[0][2] and ({'oks', 'ground'} - {role}).pop() not in rows[0][2]
        path.write_bytes(base[role])
        n += 1
    assert findings(pkg, shas(oks, ground)) == [('pass', 'manifest_ok')]
    assert n == 40


# ---- validate_package CLI: --master role=path ----------------------------------------------------------------
def test_validate_package_cli_takes_masters_per_role(tmp_path):
    pkg, oks, ground, stores = mixed(tmp_path)
    assert build(pkg, ['oks=' + str(oks), 'ground=' + str(ground)], stores) == 0
    vp = ROOT / 'tools/qa/validate_package.py'
    r = subprocess.run([sys.executable, str(vp), str(pkg), '--json', '--master', 'oks=' + str(oks),
                        '--master', 'ground=' + str(ground)], capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert 'manifest_master' not in r.stdout, r.stdout[-2000:]
    assert 'manifest_ok' in r.stdout or 'build manifest' in r.stdout, (r.returncode, r.stdout[-2000:], r.stderr)
    bad = subprocess.run([sys.executable, str(vp), str(pkg), '--json', '--master', 'flora=' + str(oks)],
                         capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert bad.returncode != 0 and 'flora' in bad.stderr
