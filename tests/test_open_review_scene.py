"""new-case: versioned acceptance copies opened in independent DCC processes."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/open_review_scene.py'


def load():
    assert SCRIPT.exists(), 'safe scene opener is missing'
    spec = importlib.util.spec_from_file_location('open_review_scene', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('app,suffix,header', [('blender','.blend',b'BLENDER-v501'),('max','.max',bytes.fromhex('d0cf11e0a1b11ae1'))])
def test_open_copy(tmp_path, monkeypatch, app, suffix, header):
    module = load()
    source = tmp_path / ('source' + suffix)
    source.write_bytes(header + b'synthetic test payload')
    output = tmp_path / ('review_v002' + suffix)
    executable = tmp_path / 'app.exe'
    executable.write_bytes(b'fixture')
    calls = []
    monkeypatch.setattr(module.subprocess, 'Popen', lambda args, **kw: calls.append((args, kw)) or SimpleNamespace(pid=42))
    result = module.open_scene(app, source, output, approved=True, executable=executable)
    assert result['status'] == 'launched' and result['pid'] == 42
    assert result['path'] == str(output.resolve())
    assert source.read_bytes() == output.read_bytes()
    assert len(calls) == 1 and calls[0][0][0] == str(executable.resolve())
    assert calls[0][0][-1] == str(output.resolve())
    assert not calls[0][1].get('shell', False)
    if app == 'blender':
        assert '--disable-autoexec' in calls[0][0]
    else:
        assert '-sceneFile' in calls[0][0]


@pytest.mark.parametrize('kind', ['missing','empty','partial','unsupported','wrong-header','no-consent'])
def test_reject_invalid(tmp_path, monkeypatch, kind):
    module = load()
    source = tmp_path / ('source.txt' if kind == 'unsupported' else 'source.blend')
    if kind != 'missing':
        source.write_bytes({'empty':b'', 'partial':b'BLEN', 'wrong-header':b'not a native file'}.get(kind,b'BLENDER-v501 payload'))
    output = tmp_path / 'review_v002.blend'
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('invalid input launched'))
    with pytest.raises((ValueError, OSError)):
        module.open_scene('blender', source, output, approved=kind != 'no-consent')
    assert not output.exists()


@pytest.mark.parametrize('alias', ['same','relative','hardlink','occupied','repeat'])
def test_no_clobber(tmp_path, monkeypatch, alias):
    module = load()
    source = tmp_path / 'source.blend'
    source.write_bytes(b'BLENDER-v501 synthetic payload')
    output = tmp_path / 'review_v002.blend'
    if alias == 'same':
        output = source
    elif alias == 'relative':
        output = tmp_path / '.' / 'source.blend'
    elif alias == 'hardlink':
        output.hardlink_to(source)
    else:
        output.write_bytes(b'foreign or previous stage')
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir()}
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('occupied output launched'))
    with pytest.raises((ValueError, OSError)):
        module.open_scene('blender', source, output, approved=True)
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()} == before


def test_cli():
    assert SCRIPT.exists()
    help_run = subprocess.run([sys.executable, str(SCRIPT), '--help'], capture_output=True, text=True)
    assert help_run.returncode == 0 and '--open-approved' in help_run.stdout
    bad = subprocess.run([sys.executable, str(SCRIPT), '--app','unknown'], capture_output=True, text=True)
    assert bad.returncode != 0


def test_launch_failure(tmp_path, monkeypatch):
    module = load()
    source = tmp_path / 'source.blend'
    source.write_bytes(b'BLENDER-v501 synthetic payload')
    output = tmp_path / 'review_v002.blend'
    exe = tmp_path / 'app.exe'
    exe.write_bytes(b'fixture')
    def fail(*args, **kwargs):
        raise OSError('launch refused')
    monkeypatch.setattr(module.subprocess, 'Popen', fail)
    with pytest.raises(OSError, match='launch refused'):
        module.open_scene('blender', source, output, approved=True, executable=exe)
    assert source.read_bytes() == output.read_bytes()  # keep the saved copy; do not claim opened
