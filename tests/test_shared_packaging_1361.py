"""new-case: shared archive publication and NPM facade (#1361)."""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from adapters.max.agr_tools import package_core


def test_shared_npm_max_emits_metadata_without_inventing_height(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from adapters.max.agr_tools import package_max
    def export(path, *args, **kwargs):
        Path(path).write_bytes(b'synthetic Max FBX')
        return True
    rt = SimpleNamespace(clearSelection=lambda: None, select=lambda nodes: None,
                         exportFile=export, Name=lambda text: text, FBXEXP=object())
    monkeypatch.setattr(package_max, '_rt', lambda: rt)
    target = tmp_path / '0000_Synthetic_01.fbx'
    package_max._export_selected(rt, [object()], str(target))
    import json
    meta = json.loads(Path(str(target) + '.export_meta.json').read_text(encoding='utf-8'))
    assert meta['profile'] == 'npm' and meta['h_otn_model_max_z_m'] == 'unknown'
    assert 'question:' in meta['provenance']['h_otn_model_max_z_m']


def test_shared_writer_rejects_source_change_during_zip(tmp_path, monkeypatch):
    import zipfile
    source = tmp_path / 'a.fbx'
    source.write_bytes(b'original synthetic')
    target = tmp_path / 'a.zip'
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}], 'limit': 10000}
    write = zipfile.ZipFile.write
    def mutate(self, *args, **kwargs):
        result = write(self, *args, **kwargs)
        source.write_bytes(b'changed by another writer')
        return result
    monkeypatch.setattr(zipfile.ZipFile, 'write', mutate)
    with pytest.raises(ValueError, match='changed'):
        package_core._write_zip(str(tmp_path), archive, str(target))
    assert not target.exists() and not Path(str(target) + '.partial').exists()
    assert source.read_bytes() == b'changed by another writer'


def test_shared_writer_rejects_duplicated_input_hardlinks(tmp_path):
    import os
    source = tmp_path / 'a.fbx'
    source.write_bytes(b'synthetic')
    os.link(source, tmp_path / 'b.fbx')
    target = tmp_path / 'a.zip'
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}, {'name': 'b.fbx'}], 'limit': 10000}
    with pytest.raises(ValueError, match='duplicat'):
        package_core._write_zip(str(tmp_path), archive, str(target))
    assert not target.exists()
    assert source.read_bytes() == (tmp_path / 'b.fbx').read_bytes() == b'synthetic'


def test_shared_writer_preserves_foreign_partial(tmp_path):
    (tmp_path / 'a.fbx').write_bytes(b'synthetic')
    target = tmp_path / 'a.zip'
    partial = tmp_path / 'a.zip.partial'
    partial.write_bytes(b'foreign input')
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}], 'limit': 10000}
    with pytest.raises(FileExistsError):
        package_core._write_zip(str(tmp_path), archive, str(target))
    assert partial.read_bytes() == b'foreign input'
    assert not target.exists()


def test_npm_uses_exporter_sidecar_and_never_packs_it(tmp_path):
    import json
    import zipfile
    from adapters.max.agr_tools.export_meta import record_export
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    fbx = pkg / '0000_Synthetic_01.fbx'
    fbx.write_bytes(b'synthetic OKS')
    (pkg / '0000_Synthetic_Ground.fbx').write_bytes(b'synthetic Ground')
    record_export(fbx, source='synthetic fixture', top=3.5)
    record_export(pkg / '0000_Synthetic_Ground.fbx', source='synthetic ground route', top=0.2,
                  address='Synthetic_Ground', profile='vpm')  # #1637: Ground recorded by its own route
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm', str(pkg)],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(tmp_path / '0000_Synthetic.zip') as archive:
        assert sorted(archive.namelist()) == ['0000_Synthetic_01.fbx', '0000_Synthetic_Ground.fbx']
    report = json.loads((tmp_path / 'package_report.json').read_text())
    assert report['passed'] is False and report['status'] == 'packaged_not_validated'
    assert any('export_meta.json' in row['item'] for row in report['skipped'])


def test_npm_packages_missing_ground_only_in_explicit_diagnostic_mode(tmp_path):
    import json
    import zipfile
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    (pkg / '0000_Synthetic_01.fbx').write_bytes(b'FBX synthetic')
    (tmp_path / 'export_meta.json').write_text(json.dumps({
        'address': 'Synthetic', 'h_otn_model_max_z_m': 3.5, 'thumbnail': 'unknown'}))
    cmd = [sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm', str(pkg)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode != 0
    assert not (tmp_path / '0000_Synthetic.zip').exists()
    result = subprocess.run(cmd + ['--allow-incomplete'], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 1, result.stderr
    with zipfile.ZipFile(tmp_path / '0000_Synthetic.zip') as archive:
        assert archive.namelist() == ['0000_Synthetic_01.fbx']
    report = json.loads((tmp_path / 'package_report.json').read_text())
    assert report['passed'] is False
    assert any('Ground' in p for p in report['problems'])


def test_vpm_partial_collision_writes_nothing(tmp_path):
    import json
    pkg, tex = tmp_path / 'version/pkg', tmp_path / 'textures'
    pkg.mkdir(parents=True)
    tex.mkdir()
    (pkg / 'SM_Synthetic.fbx').write_bytes(b'synthetic FBX')
    (pkg.parent / 'export_meta.json').write_text(json.dumps({'address':'Synthetic', 'h_otn_model_max_z_m':3.5, 'thumbnail':'unknown'}))
    for role in ('Diffuse', 'ERM', 'Normal'):
        (tex / f'T_Synthetic_{role}_1.1001.png').write_bytes(role.encode())
    (pkg.parent / 'SM_Synthetic.zip.partial').write_bytes(b'foreign input')
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    run = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'package-vpm', str(pkg), str(tex), '--no-geojson'],
                         cwd=ROOT, capture_output=True, text=True)
    assert run.returncode != 0
    assert {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('spelling', ['direct', 'hardlink', 'case', 'relative'])
def test_generated_archive_output_aliases_preserve_inputs(tmp_path, monkeypatch, spelling):
    import os
    source = tmp_path / 'a.fbx'
    source.write_bytes(b'synthetic input')
    target = source
    if spelling == 'hardlink':
        target = tmp_path / 'a.zip'
        os.link(source, target)
    elif spelling == 'case':
        if os.name != 'nt':
            pytest.skip('Windows case alias')
        target = Path(str(source).upper())
    elif spelling == 'relative':
        monkeypatch.chdir(tmp_path)
        target = Path('./a.fbx')
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}], 'limit': 10000}
    with pytest.raises(FileExistsError):
        package_core._write_zip(str(tmp_path), archive, str(target))
    assert source.read_bytes() == b'synthetic input'
    assert not Path(str(target) + '.partial').exists()


@pytest.mark.parametrize('case', range(12))
def test_expected_hash_refuses_before_publication(tmp_path, monkeypatch, case):
    import hashlib
    import os
    original = bytes([case + 1]) * (case + 1)
    source = tmp_path / 'a.fbx'
    source.write_bytes(original + b'changed')
    target = tmp_path / 'a.zip'
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}], 'limit': 10000}
    published = []
    link = os.link
    def observe(src, dst):
        published.append(dst)
        return link(src, dst)
    monkeypatch.setattr(os, 'link', observe)
    with pytest.raises(ValueError, match='a.fbx'):
        package_core._write_zip(str(tmp_path), archive, str(target),
                                expected_sha256={'a.fbx': hashlib.sha256(original).hexdigest()})
    assert published == []
    assert not target.exists() and not Path(str(target) + '.partial').exists()
    assert source.read_bytes() == original + b'changed'


@pytest.mark.parametrize('mode', ['clean', 'foreign', 'edited', 'unrecorded', 'stale_during_write'])
@pytest.mark.parametrize('path', ['cli', 'max'])
def test_binding_before_publication_on_both_paths(tmp_path, monkeypatch, mode, path):
    from adapters.max.agr_tools import edit_core
    from adapters.max.agr_tools.export_meta import record_export
    from tools.derive import package_npm
    import os
    import zipfile
    pkg = tmp_path / 'fbx'
    pkg.mkdir()
    for part in ('01', 'Ground'):
        fbx = pkg / f'0000_Synthetic_{part}.fbx'
        fbx.write_bytes(b'synthetic ' + part.encode())
        if mode != 'unrecorded':
            record_export(fbx, source='synthetic fixture')
    if mode == 'foreign':
        (pkg / '0000_Synthetic_02.fbx').write_bytes(b'foreign')
    if mode == 'edited':
        (pkg / '0000_Synthetic_01.fbx').write_bytes(b'edited')
    published = []
    link, write = os.link, package_core._write_zip
    def observe(src, dst):
        published.append(dst)
        return link(src, dst)
    def swap(folder, archive, target, **kwargs):
        if mode == 'stale_during_write':
            (pkg / '0000_Synthetic_01.fbx').write_bytes(b'changed after binding')
        return write(folder, archive, target, **kwargs)
    monkeypatch.setattr(os, 'link', observe)
    monkeypatch.setattr(package_core, '_write_zip', swap)
    if path == 'cli':
        if mode == 'clean':
            assert package_npm.main([str(pkg)]) == 0
        else:
            with pytest.raises((ValueError, OSError)):
                package_npm.main([str(pkg)])
        targets = list(tmp_path.glob('*.zip'))
    else:
        preview = package_core.zip_preview(edit_core, str(pkg))
        if mode == 'stale_during_write':
            with pytest.raises((ValueError, OSError)):
                package_core.zip_apply(edit_core, preview)
        else:
            package_core.zip_apply(edit_core, preview)
        run = next(pkg.glob('Сборка_*'))
        text = (run / package_core.MARK_FAIL).read_text(encoding='utf-8')
        assert not (run / package_core.MARK_OK).exists()  # validator deliberately absent
        if mode in ('foreign', 'edited', 'stale_during_write'):
            assert ('0000_Synthetic_02.fbx' if mode == 'foreign' else '0000_Synthetic_01.fbx') in text
        targets = list(run.glob('*.zip'))
    assert len(published) == len(targets) == (1 if mode == 'clean' else 0)
    assert not list(tmp_path.rglob('*.partial'))
    if targets:
        with zipfile.ZipFile(targets[0]) as z:
            assert {n: z.read(n) for n in z.namelist()} == {
                '0000_Synthetic_01.fbx': b'synthetic 01',
                '0000_Synthetic_Ground.fbx': b'synthetic Ground'}


@pytest.mark.parametrize('expected', [{'unknown.fbx': '0' * 64}, {'a.fbx': ''}, {'a.fbx': None},
                                      {'a.fbx': float('nan')}, {'a.fbx': float('inf')}, {'a.fbx': '0' * 63}])
def test_expected_hash_contract_fails_closed(tmp_path, expected):
    (tmp_path / 'a.fbx').write_bytes(b'synthetic')
    archive = {'name': 'a.zip', 'members': [{'name': 'a.fbx'}], 'limit': 10000}
    with pytest.raises(ValueError, match='member'):
        package_core._write_zip(str(tmp_path), archive, str(tmp_path / 'a.zip'), expected_sha256=expected)
    assert sorted(p.name for p in tmp_path.iterdir()) == ['a.fbx']


def test_embedded_sibling_binding_fresh_process(tmp_path):
    """Installed Max siblings must not need repository/tools namespaces."""
    script = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import package_core, edit_core, export_meta
folder = Path(sys.argv[2])
for part in ('01', 'Ground'):
    fbx = folder / ('0000_Synthetic_' + part + '.fbx')
    fbx.write_bytes(b'synthetic')
    export_meta.record_export(fbx, source='synthetic fixture')
rep = package_core.zip_apply(edit_core, package_core.zip_preview(edit_core, str(folder)))
run = Path(rep['plan']['run_folder'])
assert len(list(run.glob('*.zip'))) == 1
assert (run / package_core.MARK_FAIL).exists()
(folder / '0000_Synthetic_02.fbx').write_bytes(b'foreign')
rep = package_core.zip_apply(edit_core, package_core.zip_preview(edit_core, str(folder)))
run = Path(rep['plan']['run_folder'])
assert not list(run.glob('*.zip'))
assert '0000_Synthetic_02.fbx' in (run / package_core.MARK_FAIL).read_text(encoding='utf-8')
'''
    result = subprocess.run([sys.executable, '-I', '-c', script, str(ROOT / 'adapters/max/agr_tools'), str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_package_npm_cli_exists():
    result = subprocess.run([sys.executable, '-m', 'dt_ai.cli.agr', 'package-npm', '--help'],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert 'package_dir' in result.stdout
