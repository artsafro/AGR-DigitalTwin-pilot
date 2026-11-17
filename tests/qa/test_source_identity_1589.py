"""new-case: synthetic stable source identity and complete source-use accounting (#1589)."""
import ast
import copy
import json
from types import SimpleNamespace

import numpy as np

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


def producer_record_call(path, namespace):
    """Execute the real export record call, without claiming DCC geometry/readback coverage."""
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == 'write_export_derivation']
    assert len(calls) == 1
    return eval(compile(ast.Expression(calls[0]), str(path), 'eval'), namespace)


@pytest.mark.parametrize('mesh', [False, True])
def test_real_recipe_with_legacy_oks_and_mesh_producer(tmp_path, monkeypatch, mesh):
    from tools.materials import ground_recipes as recipes
    recipe = json.loads((ROOT / 'tools/materials/ground_recipes.json').read_text())
    src = tmp_path / 'recipe.json'
    src.write_text(json.dumps(recipe))
    out = tmp_path / 'v001'
    monkeypatch.setattr(recipes, 'DELIVERY_DIR', out)
    monkeypatch.setattr(recipes, 'render_map', lambda recipe, slot, profile, **kw:
        np.zeros((recipe['profiles'][profile]['size'],) * 2 + (3,), dtype=np.uint8))
    recipes.write_delivery(src, out, address='Syn')
    records = [bm.strict_json(Path(p).read_bytes()) for p in
               bm.derivation_files([Path(bm.derivation_store(out)) / out.name])]
    oks = tmp_path / 'oks.blend'
    oks.write_bytes(b'synthetic OKS source')
    fbx = tmp_path / '0000_Syn_01.fbx'
    fbx.write_bytes(b'synthetic OKS FBX')
    records.append(bm.derivation_record([fbx], oks, 'unknown', role='oks'))
    masters = {'oks': str(oks), 'ground': [str(src)]}
    files = [fbx] + list(out.glob('*.png'))
    if mesh:
        ground = tmp_path / 'renamed_mesh_v7.json'
        ground.write_bytes(b'synthetic mesh source')
        gfbx = tmp_path / '0000_Syn_Ground.fbx'
        gfbx.write_bytes(b'synthetic Ground FBX')
        record = producer_record_call('tools/blender/ground_json_to_fbx.py',
            dict(bm=bm, out=str(gfbx), src=str(ground), os=os, root=str(ROOT),
                 src_sha=bm.sha256_file(ground), address='Syn', source_id=None))
        records.append(bm.strict_json(Path(record).read_bytes()))
        oks_record = producer_record_call('tools/derive/export_npm.py',
            dict(_bm=bm, fbx=str(fbx), store=str(tmp_path / 'oks-records'), os=os,
                 HERE=str(ROOT / 'tools/derive'), master_sha=bm.sha256_file(oks), A='Syn',
                 a=SimpleNamespace(master=str(oks), spec=str(src), atlas_dir=str(out), source_id=None, index=1)))
        records[-2] = bm.strict_json(Path(oks_record).read_bytes())
        masters['ground'].append(str(ground))
        files.append(gfbx)
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        for f in files:
            z.write(f, f.name)
    def reader(path):
        suffix = 'Ground' if bm.role_of(path) == 'ground' else '001_Main'
        return {'readback_ok': True, 'meshes': [{'name': 'SM_Syn_' + suffix,
            'bounds_m': [[0, 0, 0], [1, 1, 1]], 'location': [0, 0, 0],
            'materials': ['synthetic'], 'uv_channels': 1, 'triangles': 2}]}
    recfiles = []
    for i, record in enumerate(records):
        p = tmp_path / f'record-{i}.json'
        p.write_bytes(bm.dumps(record))
        recfiles.append(str(p))
    args = ['build', str(pkg), '--derivation', *recfiles, '--transform-name', 'identity']
    for role, paths in masters.items():
        for path in paths if isinstance(paths, list) else [paths]:
            args += ['--master', role + '=' + path]
    assert cli.main(args, reader=reader) == 0
    result = bm.manifest_findings(Path(bm.manifest_path(pkg)).read_bytes(), bm.zip_members(pkg),
        pkg.name, bm.sha256_file(pkg), bm.master_hashes(masters), str(tmp_path))
    assert [r[:2] for r in result] == [('pass', 'manifest_ok')]


@pytest.mark.parametrize('producer', ['npm', 'vpm', 'quad'])
def test_oks_producer_identity_survives_source_rename(tmp_path, producer):
    source = tmp_path / 'renamed_revision.blend'
    source.write_bytes(b'synthetic master')
    fbx = tmp_path / '0000_Syn_01.fbx'
    fbx.write_bytes(b'synthetic FBX')
    store = tmp_path / 'store'
    namespace = dict(_bm=bm, bm=bm, os=os, HERE=str(ROOT / 'tools/derive'),
        fbx=str(fbx), store=str(store), master_sha=bm.sha256_file(source),
        a=SimpleNamespace(master=str(source), spec=str(source), atlas_dir=str(tmp_path), source_id=None, index=1),
        A='Syn', address='Syn', master=str(source), STORE=str(store), MASTER_SHA=bm.sha256_file(source),
        packet=tmp_path, source=str(source), source_digest=bm.sha256_file(source), commit='unknown',
        outputs=[str(fbx)], plan_path=None)
    path = {'npm': 'tools/derive/export_npm.py', 'vpm': 'jobs/KPP1/scripts/export_vpm.py',
            'quad': 'jobs/KPP1/quad-1372/provenance-1563/hooks/quad_provenance.py'}[producer]
    namespace['__file__'] = str(ROOT / path)
    if producer == 'quad':
        namespace['fbx'] = [str(fbx)]
    record = producer_record_call(path, namespace)
    rec = bm.strict_json(Path(record).read_bytes())
    assert rec['source_id'] == ('Syn.oks.001.master' if producer == 'npm' else 'KPP1.oks.master')
    assert rec['master_name'] == source.name


def test_partial_identity_migration_does_not_hide_explicit_revision_conflict(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    records[0]['role'] = 'oks'
    records[0]['artifacts'] = {'0000_Syn_01.fbx': records[0]['artifacts']['0000_Syn_Ground.fbx']}
    flora = tmp_path / 'flora.json'
    flora.write_bytes(b'synthetic legacy Flora')
    artifact = tmp_path / 'T_Syn_Flora_Diffuse_1.png'
    artifact.write_bytes(b'synthetic legacy PNG')
    records.append(bm.derivation_record([artifact], flora, 'unknown', role='flora'))
    with zipfile.ZipFile(pkg, 'w') as z:
        for rec in records:
            for name in rec['artifacts']:
                data = b'synthetic ' + name.encode() if name != artifact.name else artifact.read_bytes()
                z.writestr(name, data)
                rec['artifacts'][name]['sha256'] = bm.sha256_bytes(data)
    with pytest.raises(ValueError, match='two revisions.*site.mesh'):
        bm.make_manifest(pkg, {'oks': sources[0], 'ground': sources[1], 'flora': str(flora)},
                         'unknown', records, bm.transform_entry('identity'))


def test_generated_partial_migration_subsets(tmp_path):
    names = ['0000_Syn_01.fbx', '0000_Syn_Ground.fbx', 'SM_Syn_Flora.fbx']
    roles = ['oks', 'ground', 'flora']
    masters, records = {}, []
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        for name, role in zip(names, roles):
            source = tmp_path / (role + '.json')
            source.write_bytes(('synthetic ' + role).encode())
            f = tmp_path / name
            f.write_bytes(('synthetic ' + name).encode())
            masters[role] = str(source)
            records.append(bm.derivation_record([f], source, 'unknown', role=role))
            z.write(f, name)
    for mask, reverse in itertools.product(range(8), [False, True]):
        rows = copy.deepcopy(records)
        for i, row in enumerate(rows):
            if mask & (1 << i):
                row['source_id'] = roles[i] + '.stable'
        if reverse:
            rows.reverse()
        manifest = bm.make_manifest(pkg, masters, 'unknown', rows, bm.transform_entry('identity'))
        assert manifest['schema'] == (bm.SCHEMA_MULTI if mask == 7 else bm.SCHEMA)
        bm.parse_manifest(bm.dumps(manifest))


def test_missing_identity_names_artifact(tmp_path):
    pkg, sources, records = bundle(tmp_path)
    records[1]['source_id'] = 'site.recipe'
    records[0].pop('source_id')
    with pytest.raises(ValueError, match='0000_Syn_Ground.fbx.*source_id'):
        bm.make_manifest(pkg, {'ground': sources}, 'unknown', records, bm.transform_entry('identity'))


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
