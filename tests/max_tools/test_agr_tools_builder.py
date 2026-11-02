"""new-case: reproducible AGR Tools distribution public builder seam."""
import importlib.util
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def builder():
    path = ROOT / 'tools/max/build_agr_tools.py'
    assert path.is_file(), 'AGR Tools builder is missing'
    spec = importlib.util.spec_from_file_location('agr_builder', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_reproducible_installable_archive(tmp_path):
    mod = builder()
    a, b = tmp_path / 'one.mzp', tmp_path / 'two.mzp'
    mod.build(a)
    mod.build(b)
    assert a.read_bytes() == b.read_bytes()
    with zipfile.ZipFile(a) as z:
        assert z.testzip() is None
        assert {'mzp.run', 'install.ms', 'agr_tools/agr_tools.mcr',
                'agr_tools/startup.ms', 'agr_tools/runtime.py',
                'agr_tools/hygiene_core.py'} <= set(z.namelist())
        assert b'run "install.ms"' in z.read('mzp.run')
        assert b'0.002' in z.read('agr_tools/runtime.py')
        assert b'0.005' in z.read('agr_tools/runtime.py')


def test_builder_rejects_changed_inputs_without_publication(tmp_path, monkeypatch):
    import shutil
    mod = builder()
    source = tmp_path / 'source'
    shutil.copytree(mod.PACKAGE, source)
    monkeypatch.setattr(mod, 'PACKAGE', source)
    original = Path.read_bytes
    reads = []

    def changing(path):
        data = original(path)
        if path == source / 'runtime.py':
            reads.append(1)
            if len(reads) == 1:
                path.write_bytes(data + b'\n# concurrent edit\n')
        return data
    monkeypatch.setattr(Path, 'read_bytes', changing)
    output = tmp_path / 'never.mzp'
    import pytest
    with pytest.raises(ValueError, match='changed'):
        mod.build(output)
    assert not output.exists()


def test_aliases_and_stale_outputs_are_never_overwritten(tmp_path):
    import os
    import pytest
    mod = builder()
    source = mod.PACKAGE / 'README.md'
    before = source.read_bytes()
    hardlink = tmp_path / 'alias.mzp'
    os.link(source, hardlink)
    for path in (source, hardlink, source.parent / '..' / source.parent.name / source.name):
        with pytest.raises(FileExistsError):
            mod.build(path)
        assert source.read_bytes() == before
    existing = tmp_path / 'stale.mzp'
    existing.write_bytes(b'stale')
    partial = tmp_path / 'stale.mzp.partial'
    partial.write_bytes(b'not ours')
    with pytest.raises(FileExistsError):
        mod.build(existing)
    assert existing.read_bytes() == b'stale' and partial.read_bytes() == b'not ours'


def test_fresh_cli_and_generated_hygiene_parity(tmp_path):
    import subprocess
    import sys
    import itertools
    from twinqa.export_hygiene import repair_plan
    result = subprocess.run([sys.executable, str(ROOT / 'tools/max/build_agr_tools.py'),
                             str(tmp_path / 'cli.mzp')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    with zipfile.ZipFile(tmp_path / 'cli.mzp') as z:
        namespace = {}
        exec(z.read('agr_tools/hygiene_core.py'), namespace)
    for ca, udp, wrong, extra in itertools.product((False, True), repeat=4):
        obj = {'name': 'synthetic', 'custom_attributes': {'node': ['planted'] if ca else [],
               'base': [], 'modifiers': [], 'materials': []},
               'user_props': ('note=planted\n' if udp else '') + 'MapChannel:1 = ' +
                             ('wrong' if wrong else 'UV') + '\n',
               'map_channels': [1, 2] if extra else [1]}
        assert namespace['repair_plan']([obj]) == repair_plan([obj])
