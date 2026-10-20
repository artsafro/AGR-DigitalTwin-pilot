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
