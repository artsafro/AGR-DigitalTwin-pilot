"""new-case: synthetic stable source identity and complete source-use accounting (#1589)."""
import copy
import itertools
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm
from tools.derive import build_manifest as cli


def bundle(tmp_path, unused=False):
    sources, records = [], []
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        for name, filename in [('0000_Syn_Ground.fbx', 'ground_mesh_v1.json'),
                               ('T_Syn_Ground_d_1.png', 'ground_mesh_v2.json')]:
            source = tmp_path / filename
            source.write_bytes(('synthetic ' + filename).encode())
            artifact = tmp_path / name
            artifact.write_bytes(('synthetic ' + name).encode())
            rec = bm.derivation_record([artifact], source, 'unknown', role='ground')
            rec['source_id'] = 'site.mesh'
            records.append(rec)
            sources.append(source)
            z.write(artifact, name)
    if unused:
        records = records[:1]
        with zipfile.ZipFile(pkg, 'w') as z:
            z.write(tmp_path / '0000_Syn_Ground.fbx', '0000_Syn_Ground.fbx')
    return pkg, [str(p) for p in sources], records


def test_two_revisions_refused(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    with pytest.raises(ValueError, match='two revisions.*site.mesh'):
        bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))


@pytest.mark.parametrize('legacy', [False, True])
def test_unused_source_refused(tmp_path, legacy):
    pkg, sources, records = bundle(tmp_path, unused=True)
    if legacy:
        records[0].pop('source_id')
    with pytest.raises(ValueError, match='unused.*ground_mesh_v2.json'):
        bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))


def independent_manifest(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    records[1]['source_id'] = 'site.recipe'
    manifest = bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))
    return pkg, sources, records, manifest


@pytest.mark.parametrize('value', [None, '', ' ', ' mesh', 0, False, [], {}, float('nan'), float('inf')])
def test_v3_identity_mutations(tmp_path, value):
    pkg, sources, records, good = independent_manifest(tmp_path)
    for position in range(3):
        manifest = copy.deepcopy(good)
        target = [manifest['masters']['ground'], manifest['masters']['ground']['sources'][0],
                  manifest['artifacts'][0]][position]
        if value is None:
            target.pop('source_id')
        else:
            target['source_id'] = value
        try:
            raw = bm.dumps(manifest)
        except ValueError:
            assert isinstance(value, float)
        else:
            assert bm.manifest_findings(raw, bm.zip_members(pkg), pkg.name)[0][0] == 'fail'
    bm.parse_manifest(bm.dumps(good))


def test_identity_reset(tmp_path, capsys):
    pkg, sources, records = bundle(tmp_path)
    paths = [tmp_path / ('rec%d.json' % i) for i in range(2)]
    args = ['build', str(pkg), '--derivation', *map(str, paths), '--transform-name', 'identity', '--no-readback']
    for source in sources:
        args += ['--master', 'ground=' + source]
    before = {p: p.read_bytes() for p in [pkg] + list(map(Path, sources))}
    for _ in range(2):
        for path, rec in zip(paths, records):
            path.write_bytes(bm.dumps(rec))
        assert cli.main(args) == 2
        assert 'two revisions' in capsys.readouterr().err
        assert not Path(bm.manifest_path(pkg)).exists()
        assert not Path(bm.readback_path(pkg)).exists()
    records[1]['source_id'] = 'site.recipe'
    paths[1].write_bytes(bm.dumps(records[1]))
    assert cli.main(args) == 0
    raw = Path(bm.manifest_path(pkg)).read_bytes()
    assert all(s != 'pass' for s, _, _ in bm.manifest_findings(raw, bm.zip_members(pkg), pkg.name))
    assert before == {p: p.read_bytes() for p in before}


def test_original_probe_without_ids_refused_in_fresh_process(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    paths = []
    for i, rec in enumerate(records):
        rec.pop('source_id')
        path = tmp_path / ('rec%d.json' % i)
        path.write_bytes(bm.dumps(rec))
        paths.append(str(path))
    args = [sys.executable, str(ROOT / 'tools/derive/build_manifest.py'), 'build', str(pkg),
            '--derivation', *paths, '--transform-name', 'identity', '--no-readback']
    for source in sources:
        args += ['--master', 'ground=' + source]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    assert result.returncode == 2
    assert 'source_id' in result.stderr
    assert not Path(bm.manifest_path(pkg)).exists()


def test_generated_id_revision_and_source_use_matrix(tmp_path):
    pkg, sources, records, good = independent_manifest(tmp_path)
    for ids, reverse_records, reverse_sources in itertools.product(
            [('mesh', 'mesh'), ('mesh', 'recipe'), ('recipe', 'mesh')], [False, True], [False, True]):
        rows = copy.deepcopy(records)
        for rec, sid in zip(rows, ids):
            rec['source_id'] = sid
        if reverse_records:
            rows.reverse()
        paths = list(reversed(sources)) if reverse_sources else sources
        if ids[0] == ids[1]:
            with pytest.raises(ValueError, match='two revisions'):
                bm.make_manifest(pkg, {'ground': paths}, 'unknown', rows, bm.transform_entry('identity'))
        else:
            bm.parse_manifest(bm.dumps(bm.make_manifest(pkg, {'ground': paths}, 'unknown', rows,
                                                      bm.transform_entry('identity'))))
    for name in ['extra.json', 'extra_v2.json', 'recipe-copy.json']:
        source = tmp_path / name
        source.write_bytes(b'synthetic unused')
        with pytest.raises(ValueError, match='unused.*' + name):
            bm.make_manifest(pkg, {'ground': sources + [str(source)]}, 'unknown', records,
                             bm.transform_entry('identity'))
    for mutate in ['revision', 'unused', 'artifact_id', 'duplicate_record']:
        manifest = copy.deepcopy(good)
        if mutate == 'revision':
            manifest['masters']['ground']['sources'][1]['source_id'] = 'site.mesh'
            manifest['artifacts'][1]['source_id'] = 'site.mesh'
        elif mutate == 'unused':
            manifest['masters']['ground']['sources'].append(
                dict(manifest['masters']['ground']['sources'][1], name='extra.json', source_id='extra'))
        elif mutate == 'artifact_id':
            manifest['artifacts'][0]['source_id'] = 'undeclared'
        else:
            manifest['artifacts'].append(copy.deepcopy(manifest['artifacts'][0]))
        assert bm.manifest_findings(bm.dumps(manifest), bm.zip_members(pkg), pkg.name)[0][0] == 'fail'


@pytest.mark.parametrize('target', ['manifest', 'partial', 'readback'])
def test_input_alias_and_foreign_temp_preserved(tmp_path, target):
    pkg, sources, records, manifest = independent_manifest(tmp_path)
    paths = []
    for i, rec in enumerate(records):
        path = tmp_path / ('rec%d.json' % i)
        path.write_bytes(bm.dumps(rec))
        paths.append(str(path))
    out = bm.manifest_path(pkg)
    if target == 'partial':
        out += '.partial'
    elif target == 'readback':
        out = bm.readback_path(pkg)
    os.link(sources[0], out)
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    assert cli.main(['build', str(pkg), '--derivation', *paths, '--master', 'ground=' + sources[0],
                     '--master', 'ground=' + sources[1], '--transform-name', 'identity', '--no-readback']) == 2
    assert before == {p: p.read_bytes() for p in before}


def test_component_identity_is_global_and_required(tmp_path):
    pkg, sources, records, manifest = independent_manifest(tmp_path)
    source = dict(manifest['masters']['ground']['sources'][1])
    manifest['masters']['flora'] = source
    dep = {'role': 'flora', 'master_name': source['name'], 'master_sha256': source['sha256'],
           'source_id': source['source_id'], 'parts': ['SM_Syn_Flora']}
    manifest['artifacts'][0]['dependencies'] = [dep]
    bm.check_source_bindings(manifest['masters'], manifest['artifacts'])
    for value in [None, 'site.mesh']:
        bad = copy.deepcopy(manifest)
        if value is None:
            del bad['artifacts'][0]['dependencies'][0]['source_id']
        else:
            bad['masters']['flora']['source_id'] = value
            bad['artifacts'][0]['dependencies'][0]['source_id'] = value
        with pytest.raises(ValueError, match='source_id|two revisions'):
            bm.check_source_bindings(bad['masters'], bad['artifacts'])


def test_source_changes_during_readback_refused_before_outputs(tmp_path):
    pkg, sources, records, manifest = independent_manifest(tmp_path)
    paths = []
    for i, rec in enumerate(records):
        path = tmp_path / ('rec%d.json' % i)
        path.write_bytes(bm.dumps(rec))
        paths.append(str(path))
    def reader(path):
        Path(sources[0]).write_bytes(b'synthetic changed source')
        return {'readback_ok': True, 'meshes': []}
    assert cli.main(['build', str(pkg), '--derivation', *paths, '--master', 'ground=' + sources[0],
                     '--master', 'ground=' + sources[1], '--transform-name', 'identity'], reader=reader) == 2
    assert not Path(bm.manifest_path(pkg)).exists()
    assert not Path(bm.readback_path(pkg)).exists()


def test_record_cli_retains_explicit_id_in_fresh_process(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    output = tmp_path / 'new-record.json'
    result = subprocess.run([sys.executable, str(ROOT / 'tools/derive/build_manifest.py'), 'record',
        str(tmp_path / '0000_Syn_Ground.fbx'), '--master', sources[0], '--source-id', 'site.mesh',
        '--out', str(output)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert bm.check_derivation(bm.strict_json(output.read_bytes()))['source_id'] == 'site.mesh'
