"""new-case: synthetic project-interpreter stubs bound Max export subprocess time.

No DCC is loaded: AGR_PYTHON selects the project interpreter, which executes a
minimal export_core stub from a synthetic AGR_TOOLS_REPO.
"""
import importlib.util
import sys
from pathlib import Path

import pytest


RUNTIME = Path(__file__).resolve().parents[2] / 'adapters/max/agr_tools/runtime.py'


@pytest.fixture
def export_stub(tmp_path, monkeypatch):
    core = tmp_path / 'adapters/max/agr_tools/export_core.py'
    core.parent.mkdir(parents=True)
    monkeypatch.setenv('AGR_PYTHON', sys.executable)
    monkeypatch.setenv('AGR_TOOLS_REPO', str(tmp_path))
    monkeypatch.setenv('AGR_EXPORT_TIMEOUT_S', '1')
    spec = importlib.util.spec_from_file_location('agr_export_timeout_runtime', RUNTIME)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    return runtime, core


@pytest.mark.parametrize('method', ['dry_run', 'readback', 'finish'])
def test_subprocess_export_timeout_names_method_and_seconds(export_stub, tmp_path, method):
    runtime, core = export_stub
    core.write_text(
        'import time\n'
        'def response(*args, **kwargs):\n'
        '    time.sleep(3)\n'
        '    return {}\n'
        'dry_run = readback = finish = response\n', encoding='utf-8')
    target = tmp_path / 'synthetic.fbx'
    target.write_bytes(b'synthetic')
    with pytest.raises(RuntimeError, match=rf'{method}.*1(?:\.0)? s'):
        runtime._subprocess_export({'method': method, 'scene': {}, 'preview': {}, 'target': str(target)})
