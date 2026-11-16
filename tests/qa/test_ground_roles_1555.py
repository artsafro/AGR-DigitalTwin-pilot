"""new-case: Ground-family provenance roles and independent producer sources (#1555)."""
import sys
import ast
import copy
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import build_manifest as bm, package_core as pc
from tools.derive import build_manifest as cli


@pytest.mark.parametrize('alias', ['repeat', 'resolved', 'hardlink', 'same_basename'])
def test_independent_sources_refuse_aliases_before_build_write(tmp_path, alias):
    source = tmp_path / 'mesh.json'
    source.write_bytes(b'synthetic mesh')
    artifact = tmp_path / 'SM_Syn_Ground.fbx'
    artifact.write_bytes(b'synthetic export')
    record = bm.write_export_derivation([artifact], source, tmp_path / 'records', role='ground')
    other = source
    if alias == 'resolved':
        (tmp_path / 'child').mkdir()
        other = tmp_path / 'child' / '..' / source.name
    elif alias == 'hardlink':
        other = tmp_path / 'link.json'
        os.link(source, other)
    elif alias == 'same_basename':
        other = tmp_path / 'elsewhere' / source.name
        other.parent.mkdir()
        other.write_bytes(b'different synthetic mesh')
    pkg = tmp_path / 'SM_Syn_Ground.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        z.write(artifact, artifact.name)
    assert cli.main(['build', str(pkg), '--master', 'ground=' + str(source), '--master', 'ground=' + str(other),
        '--derivation', record, '--transform-name', 'identity', '--no-readback']) == 2
    assert not Path(bm.manifest_path(pkg)).exists()
    assert not Path(bm.readback_path(pkg)).exists()
    assert source.read_bytes() == b'synthetic mesh'


def test_validator_multiple_oks_sources_never_guesses_quad_master(tmp_path):
    from tools.qa.validate_package import validate
    from twinqa.profiles import load_profiles
    a, b = tmp_path / 'geometry.blend', tmp_path / 'pixels.json'
    a.write_bytes(b'synthetic geometry')
    b.write_bytes(b'synthetic pixels')
    artifact = tmp_path / 'SM_Syn.fbx'
    artifact.write_bytes(b'synthetic FBX')
    result = validate(artifact, 'vpm', load_profiles(), master={'oks': [a, b]})
    assert any('multiple OKS sources' in note for note in result.notes)


def test_empty_master_is_refused_before_record_write(tmp_path):
    source = tmp_path / 'empty.json'
    source.write_bytes(b'')
    artifact = tmp_path / 'SM_Syn_Ground.fbx'
    artifact.write_bytes(b'synthetic')
    with pytest.raises(ValueError, match='empty'):
        bm.write_export_derivation([artifact], source, tmp_path / 'records', role='ground')
    assert not (tmp_path / 'records').exists()
    assert source.read_bytes() == b''


@pytest.mark.parametrize('mutation', ['empty', 'partial', 'unknown_role', 'nan', 'inf', 'wrong_part',
    'duplicate_part', 'self_dependency', 'hardlinked_self_dependency'])
def test_component_dependencies_fail_closed_before_write(tmp_path, mutation):
    source = tmp_path / 'mesh.json'
    source.write_bytes(b'synthetic source')
    artifact = tmp_path / 'SM_Syn_Ground.fbx'
    artifact.write_bytes(b'synthetic export')
    dep = {'role': 'flora', 'master': source, 'master_sha256': bm.sha256_file(source),
           'parts': ['SM_Syn_Flora']}
    deps = [dep]
    if mutation == 'empty':
        deps = []
    elif mutation == 'partial':
        del dep['master_sha256']
    elif mutation == 'unknown_role':
        dep['role'] = 'terrain'
    elif mutation in ('nan', 'inf'):
        dep['master_sha256'] = float(mutation)
    elif mutation == 'wrong_part':
        dep['parts'] = ['SM_Syn_GroundEl']
    elif mutation == 'duplicate_part':
        dep['parts'] *= 2
    else:
        dependency = artifact
        if mutation == 'hardlinked_self_dependency':
            dependency = tmp_path / 'self-link.fbx'
            os.link(artifact, dependency)
        dep['master'] = dependency
        dep['master_sha256'] = bm.sha256_file(dependency)
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError):
        bm.write_export_derivation([artifact], source, tmp_path / 'records', role='ground', dependencies=deps)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_kpp1_ground_export_records_all_component_sources(tmp_path):
    script = ROOT / 'jobs/KPP1/ground-budget-1416/derive_ground_v003.py'
    tree = ast.parse(script.read_text(encoding='utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'record_export']
    assert len(functions) == 1, 'KPP1 exporter must record its output before publication'
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = [n for n in ast.walk(main) if isinstance(n, ast.Call)]
    record_call = next(n for n in calls if isinstance(n.func, ast.Name) and n.func.id == 'record_export')
    publish_call = next(n for n in calls if isinstance(n.func, ast.Attribute) and n.func.attr == 'rename')
    assert record_call.lineno < publish_call.lineno
    namespace = {'bm': bm, 'os': __import__('os')}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(script), 'exec'), namespace)
    fbx = tmp_path / '0000_Syn_Ground.fbx'
    src, cust, mapping = [tmp_path / name for name in ('source.fbx', 'customer.fbx', 'bridge.json')]
    for p in (fbx, src, cust, mapping):
        p.write_bytes(('synthetic ' + p.name).encode())
    names = ['SM_Syn_Ground', 'SM_Syn_GroundEl', 'SM_Syn_Flora']
    record = namespace['record_export'](str(fbx), str(src), bm.sha256_file(src), str(cust),
        bm.sha256_file(cust), str(mapping), bm.sha256_file(mapping), names)
    rec = bm.check_derivation(bm.strict_json(Path(record).read_bytes()))
    assert rec['role'] == 'ground'
    deps = rec['dependencies']
    assert {(d['role'], d['master_name']) for d in deps} == {
        (r, p.name) for r in ('ground', 'groundel', 'flora') for p in (src, cust, mapping)}
    assert {p for d in deps for p in d['parts']} == set(names)



def test_combined_ground_records_component_sources(tmp_path):
    fbx = tmp_path / '0000_Syn_Ground.fbx'
    fbx.write_bytes(b'synthetic combined ground export')
    mesh, recipe, flora = [tmp_path / n for n in ('mesh.json', 'recipe.json', 'flora.fbx')]
    for p in (mesh, recipe, flora):
        p.write_bytes(('synthetic ' + p.name).encode())
    dependencies = [
        {'role': 'ground', 'master': recipe, 'source_id': 'site.recipe', 'master_sha256': bm.sha256_file(recipe),
         'parts': ['SM_Syn_Ground']},
        {'role': 'flora', 'master': flora, 'source_id': 'site.flora', 'master_sha256': bm.sha256_file(flora),
         'parts': ['SM_Syn_Flora']}]
    path = bm.write_export_derivation([fbx], mesh, tmp_path / 'records', role='ground',
                                      dependencies=dependencies, source_id='site.mesh')
    rec = bm.strict_json(Path(path).read_bytes())
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        z.write(fbx, fbx.name)
    def reader(path):
        rb = synthetic_readback(path)
        rb['meshes'].append(dict(rb['meshes'][0], name='SM_Syn_Flora'))
        return rb
    assert cli.main(['build', str(pkg), '--derivation', path, '--master', 'ground=' + str(mesh),
        '--master', 'ground=' + str(recipe), '--master', 'flora=' + str(flora),
        '--transform-name', 'identity'], reader=reader) == 0
    raw = Path(bm.manifest_path(pkg)).read_bytes()
    hashes = bm.master_hashes({'ground': [mesh, recipe], 'flora': flora})
    assert bm.manifest_findings(raw, bm.zip_members(pkg), pkg.name, bm.sha256_file(pkg), hashes,
        str(tmp_path))[0][:2] == ('pass', 'manifest_ok')
    # A missing producer dependency is refused before either build output is written, even on a v2-shaped request.
    rec.pop('dependencies')
    Path(path).write_bytes(bm.dumps(rec))
    missing_pkg = tmp_path / '0000_Syn_missing.zip'
    missing_pkg.write_bytes(pkg.read_bytes())
    assert cli.main(['build', str(missing_pkg), '--derivation', path, '--master', 'ground=' + str(mesh),
        '--transform-name', 'identity'], reader=reader) == 2
    assert not Path(bm.manifest_path(missing_pkg)).exists()
    assert not Path(bm.readback_path(missing_pkg)).exists()
    manifest = bm.strict_json(raw)
    manifest['artifacts'][0]['dependencies'].pop()
    assert 'pass' not in {s for s, _, _ in bm.manifest_findings(bm.dumps(manifest), bm.zip_members(pkg),
        pkg.name, bm.sha256_file(pkg), hashes, str(tmp_path))}
    # Removing both the component and its role cannot hide it from the bound export readback.
    manifest['artifacts'][0]['parts'].remove('SM_Syn_Flora')
    del manifest['masters']['flora']
    del hashes['flora']
    assert 'pass' not in {s for s, _, _ in bm.manifest_findings(bm.dumps(manifest), bm.zip_members(pkg),
        pkg.name, bm.sha256_file(pkg), hashes, str(tmp_path))}



def synthetic_readback(path):
    mesh_name = 'SM_Syn_Ground' if bm.role_of(path) == 'ground' else 'SM_Syn_001_Main'
    return {'readback_ok': True, 'meshes': [{'name': mesh_name,
        'bounds_m': [[0, 0, 0], [1, 1, 1]], 'location': [0, 0, 0],
        'materials': ['M_Syn_Ground_1'], 'uv_channels': 1, 'triangles': 2}]}


def test_independent_ground_sources_from_producer_records(tmp_path):
    sources, records, files = [], [], []
    for name, master_name, role in [('0000_Syn_01.fbx', 'oks.blend', 'oks'),
        ('0000_Syn_Ground.fbx', 'mesh.json', 'ground'),
        ('T_Syn_Ground_d_1.png', 'recipe.json', 'ground')]:
        master = tmp_path / master_name
        master.write_bytes(('synthetic ' + master_name).encode())
        artifact = tmp_path / name
        artifact.write_bytes(('synthetic ' + name).encode())
        records.append(bm.write_export_derivation([artifact], master, tmp_path / 'records', role=role,
                                                 source_id='site.' + master.stem))
        sources.append((role, master))
        files.append(artifact)
    pkg = tmp_path / '0000_Syn.zip'
    with zipfile.ZipFile(pkg, 'w') as z:
        for p in files:
            z.write(p, p.name)
    args = ['build', str(pkg), '--derivation', *records, '--transform-name', 'identity']
    for role, path in sources:
        args += ['--master', role + '=' + str(path)]
    assert cli.main(args, reader=synthetic_readback) == 0
    current = {'oks': bm.sha256_file(sources[0][1]),
               'ground': [bm.sha256_file(p) for r, p in sources if r == 'ground']}
    raw = Path(bm.manifest_path(pkg)).read_bytes()
    assert bm.manifest_findings(raw, bm.zip_members(pkg), pkg.name, bm.sha256_file(pkg),
        current, str(tmp_path))[0][:2] == ('pass', 'manifest_ok')
    manifest = bm.strict_json(raw)
    command = [sys.executable, str(ROOT / 'tools/qa/validate_package.py'), str(pkg), '--json']
    for role, path in sources:
        command += ['--master', role + '=' + str(path)]
    fresh = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert fresh.returncode == 1, fresh.stderr  # synthetic FBX/PNG are not delivery-ready
    report = json.loads(fresh.stdout)
    stage = next(s for s in report['stages'] if s['id'] == 'V001')
    assert any(f['name'] == 'build manifest' and f['status'] == 'pass' for f in stage['findings'])
    # A selected independent source is not permission to relabel a stale revision as its sibling source.
    swapped = copy.deepcopy(manifest)
    swapped['masters']['ground']['sources'][1]['name'] = 'unrelated.json'
    assert 'pass' not in {s for s, _, _ in bm.manifest_findings(bm.dumps(swapped), bm.zip_members(pkg),
        pkg.name, bm.sha256_file(pkg), current, str(tmp_path))}
    current['ground'].pop()
    assert 'pass' not in {s for s, _, _ in bm.manifest_findings(raw, bm.zip_members(pkg), pkg.name,
        bm.sha256_file(pkg), current, str(tmp_path))}



@pytest.mark.parametrize('suffix,role', [('Ground', 'ground'), ('GroundGlass', 'ground'),
    ('GroundEl', 'groundel'), ('GroundElGlass', 'groundel'), ('Flora', 'flora')])
@pytest.mark.parametrize('address', ['A', 'Syn_12', 'Underground_Floral'])
@pytest.mark.parametrize('template', ['SM_{}_{}.fbx', 'T_{}_{}_d_1.png',
    'T_{}_{}_Diffuse_1.1001.png', 'UCX_SM_{}_{}_001.fbx', 'SM_{}_{}_Light.fbx'])
def test_ground_family_role_is_shared(suffix, role, address, template):
    name = template.format(address, suffix)
    assert bm.role_of(name) == role
    assert pc.role_of(name) == role
    assert pc.classify_mesh('SM_' + address + '_' + suffix)[0] == 'ground'


@pytest.mark.parametrize('name', ['SM_Underground_Main.fbx', 'T_Floral_Diffuse_1.1001.png',
    'SM_A_GroundElse.fbx', '0000_A_01.fbx', 'SM_Ground_A_Main.fbx',
    'T_Flora_A_Diffuse_1.1001.png', 'SM_Ground_A_Light.fbx'])
def test_similar_words_are_not_ground_roles(name):
    assert bm.role_of(name) == pc.role_of(name) == 'oks'
