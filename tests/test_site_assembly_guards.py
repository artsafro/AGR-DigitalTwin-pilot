"""Synthetic #298 guards; no workstation scene or DCC process required."""
import importlib.util
from pathlib import Path
import pytest


def rules():
    path = Path(__file__).parents[1] / 'jobs/VATUTINO-SITE/assembly_rules.py'
    assert path.is_file(), 'assembly guard module is missing'
    spec = importlib.util.spec_from_file_location('site_assembly_rules', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_new_output_refuses_input_alias_and_existing_directory(tmp_path):
    mod = rules()
    source = tmp_path / 'source.blend'
    source.write_bytes(b'protected')
    for output in (source, tmp_path):
        with pytest.raises(ValueError):
            mod.new_output(source, output)
    assert source.read_bytes() == b'protected'
    assert mod.new_output(source, tmp_path / 'fresh') == tmp_path / 'fresh'


def test_output_cannot_be_inside_protected_source_directory(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    with pytest.raises(ValueError, match='protected source'):
        rules().new_output(source, source / 'new-output')
    assert list(source.iterdir()) == []


@pytest.mark.parametrize('spelling', ['same', 'relative', 'hardlink'])
def test_existing_alias_never_changes_bytes(tmp_path, monkeypatch, spelling):
    source = tmp_path / 'source.blend'
    source.write_bytes(b'input')
    if spelling == 'hardlink':
        dest = tmp_path / 'other.blend'
        dest.hardlink_to(source)
    elif spelling == 'relative':
        monkeypatch.chdir(tmp_path)
        dest = Path('./source.blend')
    else:
        dest = source
    with pytest.raises(ValueError):
        rules().new_output(source, dest)
    assert source.read_bytes() == b'input'
