"""new-case: exports write derivation records; the NPM atlas is bound to the master hash (#1505).

Pure-python half: the stdlib owner (adapters/max/agr_tools/build_manifest.py) that both exporters call, the
export_meta master hash, the atlas generator binding and a synthetic complete NPM set from export-time records to
a manifest pass. The real exporters run on a synthetic master in tests/qa/test_export_derivation_1505_blender.py.
"""
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm  # noqa: E402
from adapters.max.agr_tools import export_meta as em  # noqa: E402

from test_build_manifest_1423 import cli, good_rb  # noqa: E402  same CLI + readback stand-in

NPM_SET = {'0000_Syn_01.fbx': b'Kaydara FBX Binary  \x00 oks 01', '0000_Syn_02.fbx': b'Kaydara FBX Binary  \x00 oks 02',
           '0000_Syn_Ground.fbx': b'Kaydara FBX Binary  \x00 ground'}


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in Path(root).rglob('*') if p.is_file()}


def master_file(tmp, data=b'synthetic master revision A'):
    tmp.mkdir(parents=True, exist_ok=True)
    m = tmp / 'master.blend'
    m.write_bytes(data)
    return m


# ---- derivation record written at export time --------------------------------------------------------------
def test_export_writes_derivation_record_into_the_store(tmp_path):
    master = master_file(tmp_path / 'in')
    fbx = tmp_path / 'export' / 'fbx' / '0000_Syn_01.fbx'
    fbx.parent.mkdir(parents=True)
    fbx.write_bytes(NPM_SET[fbx.name])
    store = bm.derivation_store(fbx.parent)
    path = bm.write_export_derivation([fbx], master, store, 'abc1234', master_sha256=bm.sha256_file(master))
    assert Path(path) == tmp_path / 'export' / 'derivation' / '0000_Syn_01.fbx.derivation.json'
    rec = bm.check_derivation(bm.strict_json(Path(path).read_bytes()))
    assert rec['master_path'] == os.path.abspath(master)
    assert rec['master_name'] == 'master.blend'
    assert rec['master_sha256'] == bm.sha256_file(master)
    assert rec['artifacts'] == {'0000_Syn_01.fbx': {'kind': 'npm_fbx', 'sha256': bm.sha256_file(fbx)}}
    assert rec['builder_commit'] == 'abc1234'
    assert not list(Path(store).glob('*.partial'))


def test_master_changed_during_the_export_is_refused_and_writes_nothing(tmp_path):
    master = master_file(tmp_path / 'in')
    before = bm.sha256_file(master)
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    master.write_bytes(b'synthetic master revision B (edited while exporting)')
    with pytest.raises(ValueError, match='master_changed_during_export'):
        bm.write_export_derivation([fbx], master, bm.derivation_store(fbx.parent), 'abc1234', master_sha256=before)
    assert not (tmp_path / 'derivation').exists()


def test_existing_record_is_never_overwritten(tmp_path):
    master = master_file(tmp_path / 'in')
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    store = bm.derivation_store(fbx.parent)
    first = bm.write_export_derivation([fbx], master, store, 'abc1234')
    data = Path(first).read_bytes()
    with pytest.raises(FileExistsError):
        bm.write_export_derivation([fbx], master, store, 'abc1234')
    assert Path(first).read_bytes() == data


def test_record_store_aliasing_an_input_is_refused(tmp_path):
    master = master_file(tmp_path / 'in')
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    alias = tmp_path / 'out' / ('0000_Syn_01.fbx' + bm.DERIVATION_SUFFIX)
    with pytest.raises(ValueError, match='is an input'):
        bm.write_export_derivation([fbx], master, fbx.parent, 'abc1234', inputs=[alias])
    assert not alias.exists()


@pytest.mark.parametrize('sha', ['', 'ABC', 'g' * 64, 65 * '0', True, 0])
def test_malformed_expected_master_hash_is_refused(tmp_path, sha):
    master = master_file(tmp_path / 'in')
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    with pytest.raises(ValueError):
        bm.write_export_derivation([fbx], master, tmp_path / 'store', 'abc1234', master_sha256=sha)
    assert not (tmp_path / 'store').exists()


def test_store_directory_expands_to_its_records_in_name_order(tmp_path):
    store = tmp_path / 'derivation'
    store.mkdir()
    for n in ('b.fbx.derivation.json', 'a.fbx.derivation.json', 'notes.txt', 'c.json'):
        (store / n).write_text('{}')
    assert [Path(p).name for p in bm.derivation_files([store])] == ['a.fbx.derivation.json', 'b.fbx.derivation.json']
    single = tmp_path / 'x.json'
    single.write_text('{}')
    assert bm.derivation_files([single]) == [str(single)]


def test_empty_store_directory_is_refused(tmp_path):
    (tmp_path / 'derivation').mkdir()
    with pytest.raises(ValueError, match='no derivation record'):
        bm.derivation_files([tmp_path / 'derivation'])


# ---- export_meta stores the master hash ---------------------------------------------------------------------
def test_export_meta_stores_the_master_hash(tmp_path):
    master = master_file(tmp_path / 'in')
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    path = em.record_export(fbx, source=str(master), top=3.0, master=master)
    meta = em.load_meta(path)
    assert meta['master_sha256'] == bm.sha256_file(master)
    assert 'master_sha256' in meta['provenance'] and str(master) in meta['provenance']['master_sha256']


def test_export_meta_refuses_a_master_that_changed_since_the_export_started(tmp_path):
    master = master_file(tmp_path / 'in')
    before = bm.sha256_file(master)
    master.write_bytes(b'edited')
    fbx = tmp_path / 'out' / '0000_Syn_01.fbx'
    fbx.parent.mkdir()
    fbx.write_bytes(b'x')
    with pytest.raises(ValueError, match='master_changed_during_export'):
        em.record_export(fbx, source=str(master), master=master, master_sha256=before)
    assert sorted(p.name for p in fbx.parent.iterdir()) == ['0000_Syn_01.fbx']


@pytest.mark.parametrize('value', ['', 'A' * 64, '0' * 63, 7, None])
def test_export_meta_malformed_master_hash_is_named(value):
    meta = {'address': 'Syn', 'h_otn_model_max_z_m': 'unknown', 'thumbnail': 'unknown', 'master_sha256': value}
    with pytest.raises(ValueError, match='master_sha256'):
        em.validate_meta(meta)


def test_export_meta_schema_accepts_master_hash():
    from jsonschema import Draft202012Validator
    schema = json.loads((ROOT / 'schemas/ExportMeta.schema.json').read_text())
    v = Draft202012Validator(schema)
    good = {'address': 'Syn', 'h_otn_model_max_z_m': 1.0, 'thumbnail': 'unknown', 'master_sha256': '0' * 64,
            'provenance': {'address': 'a', 'h_otn_model_max_z_m': 'b', 'thumbnail': 'c', 'master_sha256': 'd'}}
    assert not list(v.iter_errors(good))
    assert list(v.iter_errors(dict(good, master_sha256='0' * 63)))


# ---- atlas bound to the master --------------------------------------------------------------------------------
FINISHES = {'Brick': {'udim': 1001, 'u0': 0.0, 'v0': 0.5, 'size': 0.25},
            'Plaster': {'udim': 1002, 'u0': 0.5, 'v0': 0.5, 'size': 0.25}}


def bound_atlas(master, finishes=FINISHES):
    return {'atlas': 2048, 'finishes': finishes, 'master': bm.atlas_master_binding(master, finishes)}


def test_atlas_binding_names_master_hash_and_udims(tmp_path):
    master = master_file(tmp_path)
    b = bm.atlas_master_binding(master, FINISHES)
    assert b == {'name': 'master.blend', 'sha256': bm.sha256_file(master), 'udims': [1001, 1002]}
    assert bm.check_atlas_master(bound_atlas(master), bm.sha256_file(master)) == b


def test_atlas_master_mismatch_is_refused_with_a_named_reason(tmp_path):
    master = master_file(tmp_path)
    atlas = bound_atlas(master)
    master.write_bytes(b'synthetic master revision B')
    with pytest.raises(bm.AtlasBindingError) as exc:
        bm.check_atlas_master(atlas, bm.sha256_file(master))
    assert exc.value.reason == 'atlas_master_mismatch'
    assert str(exc.value).startswith('atlas_master_mismatch: ')


@pytest.mark.parametrize('mutate,reason', [
    (lambda a: a.pop('master'), 'atlas_unbound'),
    (lambda a: a.update(master=None), 'atlas_unbound'),
    (lambda a: a.update(master='0' * 64), 'atlas_unbound'),
    (lambda a: a['master'].pop('sha256'), 'atlas_unbound'),
    (lambda a: a['master'].update(sha256='0' * 63), 'atlas_unbound'),
    (lambda a: a['master'].update(sha256=a['master']['sha256'].upper()), 'atlas_unbound'),
    (lambda a: a['master'].update(extra=1), 'atlas_unbound'),
    (lambda a: a['master'].update(udims=[1001]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[1001, 1002, 1003]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[1002, 1001]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[1001, 1001, 1002]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[1001.0, 1002]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims=[True, 1002]), 'atlas_udim_mismatch'),
    (lambda a: a['master'].update(udims='1001,1002'), 'atlas_udim_mismatch'),
    (lambda a: a['finishes']['Plaster'].update(udim=1003), 'atlas_udim_mismatch'),
    (lambda a: a.update(finishes={}), 'atlas_udim_mismatch'),
])
def test_atlas_binding_fails_closed(tmp_path, mutate, reason):
    import copy
    master = master_file(tmp_path)
    atlas = copy.deepcopy(bound_atlas(master))
    mutate(atlas)
    with pytest.raises(bm.AtlasBindingError) as exc:
        bm.check_atlas_master(atlas, bm.sha256_file(master))
    assert exc.value.reason == reason, str(exc.value)


def test_atlas_binding_generated_probe_any_byte_flip_is_a_mismatch(tmp_path):
    """Invariant: the atlas is accepted only for the exact master bytes it was bound to (64 seeded flips)."""
    import random
    rng = random.Random(1505)
    data = bytearray(rng.randbytes(512))
    master = tmp_path / 'm.blend'
    master.write_bytes(bytes(data))
    atlas = bound_atlas(master)
    refused = 0
    for _ in range(64):
        flipped = bytearray(data)
        i = rng.randrange(len(flipped))
        flipped[i] ^= 1 << rng.randrange(8)
        master.write_bytes(bytes(flipped))
        try:
            bm.check_atlas_master(atlas, bm.sha256_file(master))
        except bm.AtlasBindingError as exc:
            refused += exc.reason == 'atlas_master_mismatch'
    assert refused == 64
    master.write_bytes(bytes(data))
    assert bm.check_atlas_master(atlas, bm.sha256_file(master))['sha256'] == bm.sha256_file(master)


# ---- synthetic complete NPM set: export-time records -> manifest ------------------------------------------------
def ground_source(master):
    """[D328]: the Ground FBX keeps its own master (its source), not the OKS master."""
    src = Path(master).parent / 'ground_mesh.json'
    if not src.exists():
        src.write_bytes(b'{"synthetic": "ground source"}')
    return src


def npm_set(tmp, master):
    """Three exports (two OKS + Ground); OKS records name the OKS master, the Ground record its own source ([D328])."""
    stores = []
    for name, data in NPM_SET.items():
        out = tmp / ('export-' + name[:-4]) / 'fbx'
        out.mkdir(parents=True)
        (out / name).write_bytes(data)
        store = bm.derivation_store(out)
        src = ground_source(master) if bm.role_of(name) == 'ground' else master
        bm.write_export_derivation([out / name], src, store, 'abc1234', master_sha256=bm.sha256_file(src))
        stores.append(store)
    package = tmp / '0000_Syn.zip'
    with zipfile.ZipFile(package, 'w') as z:
        for name, data in NPM_SET.items():
            z.writestr(name, data)
    return package, stores


def build_and_find(package, master, stores):
    argv = ['build', str(package), '--master', 'oks=' + str(master), '--master', 'ground=' + str(ground_source(master)),
            '--derivation', *map(str, stores), '--transform-name', 'identity', '--builder-commit', 'abc1234']
    assert cli.main(argv, reader=good_rb) == 0
    with zipfile.ZipFile(package) as z:
        members = {n: bm.sha256_bytes(z.read(n)) for n in z.namelist()}
    raw = Path(bm.manifest_path(package)).read_bytes()
    return lambda: bm.manifest_findings(raw, members, package.name, bm.sha256_file(package),
                                        {'oks': bm.sha256_file(master),
                                         'ground': bm.sha256_file(ground_source(master))}, str(package.parent))


def test_synthetic_complete_npm_set_from_export_records_gets_manifest_pass(tmp_path):
    master = master_file(tmp_path / 'in')
    package, stores = npm_set(tmp_path, master)
    rows = build_and_find(package, master, stores)()
    assert [(s, c) for s, c, _ in rows] == [('pass', 'manifest_ok')], rows


def test_master_changed_after_export_gives_a_manifest_finding_not_pass(tmp_path):
    master = master_file(tmp_path / 'in')
    package, stores = npm_set(tmp_path, master)
    find = build_and_find(package, master, stores)
    master.write_bytes(b'synthetic master revision B')
    rows = find()
    assert ('fail', 'manifest_master_stale') in [(s, c) for s, c, _ in rows]
    assert 'pass' not in {s for s, _, _ in rows}


def test_master_changed_between_export_and_build_names_both_revisions(tmp_path):
    master = master_file(tmp_path / 'in')
    package, stores = npm_set(tmp_path, master)
    master.write_bytes(b'synthetic master revision B')  # edited after export, before the manifest build
    rows = build_and_find(package, master, stores)()
    assert ('fail', 'manifest_master_mismatch') in [(s, c) for s, c, _ in rows]
    assert 'pass' not in {s for s, _, _ in rows}


def test_partial_store_one_export_without_record_refuses_the_build(tmp_path):
    master = master_file(tmp_path / 'in')
    package, stores = npm_set(tmp_path, master)
    for p in Path(stores[0]).iterdir():
        p.unlink()
    Path(stores[0]).rmdir()
    argv = ['build', str(package), '--master', str(master), '--derivation', *map(str, stores[1:]),
            '--transform-name', 'identity', '--builder-commit', 'abc1234']
    assert cli.main(argv, reader=good_rb) == 2
    assert not Path(bm.manifest_path(package)).exists()


def test_fresh_process_cli_build_reads_the_store_directory(tmp_path):
    master = master_file(tmp_path / 'in')
    package, stores = npm_set(tmp_path, master)
    r = subprocess.run([sys.executable, str(ROOT / 'tools/derive/build_manifest.py'), 'build', str(package),
                        '--master', 'oks=' + str(master), '--master', 'ground=' + str(ground_source(master)),
                        '--derivation', *map(str, stores), '--transform-name', 'identity',
                        '--builder-commit', 'abc1234', '--no-readback'], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    m = bm.parse_manifest(Path(bm.manifest_path(package)).read_bytes())
    assert {a['name'] for a in m['artifacts']} == set(NPM_SET)
    assert {a['role']: a['master_sha256'] for a in m['artifacts']} == {
        'oks': bm.sha256_file(master), 'ground': bm.sha256_file(ground_source(master))}


# ---- atlas generator writes the binding ------------------------------------------------------------------------
ATLAS_TOOL = ROOT / 'tools/derive/npm_atlas.py'
AC08_SPEC = ROOT / 'jobs/TEC26-OKS/AC08/vpm_textures.json'


def test_atlas_generation_without_master_is_refused_and_writes_nothing(tmp_path):
    spec = tmp_path / 'spec.json'
    spec.write_bytes(AC08_SPEC.read_bytes())
    before = snapshot(tmp_path)
    r = subprocess.run([sys.executable, str(ATLAS_TOOL), str(spec), str(tmp_path / 'out')],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode != 0 and '--master' in r.stderr, r.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('case', ['missing', 'is_spec', 'empty'])
def test_atlas_generation_with_a_bad_master_is_refused_and_writes_nothing(tmp_path, case):
    spec = tmp_path / 'spec.json'
    spec.write_bytes(AC08_SPEC.read_bytes())
    master = {'missing': tmp_path / 'nope.blend', 'is_spec': spec, 'empty': tmp_path / 'empty.blend'}[case]
    if case == 'empty':
        master.write_bytes(b'')
    before = snapshot(tmp_path)
    r = subprocess.run([sys.executable, str(ATLAS_TOOL), str(spec), str(tmp_path / 'out'), '--master', str(master)],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode != 0 and 'refused' in r.stderr, (r.stdout, r.stderr)
    assert snapshot(tmp_path) == before
