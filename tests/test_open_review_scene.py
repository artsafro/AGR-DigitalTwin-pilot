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


@pytest.mark.parametrize('magic', [bytes.fromhex('28b52ffd'), bytes.fromhex('1f8b0800')])
def test_compressed_blend_container(tmp_path, monkeypatch, magic):
    module = load()
    source = tmp_path / 'source.blend'
    source.write_bytes(magic + b'synthetic container payload')
    output = tmp_path / 'review_v002.blend'
    exe = tmp_path / 'app.exe'
    exe.write_bytes(b'fixture')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=42))
    assert module.open_scene('blender', source, output, approved=True, executable=exe)['status'] == 'launched'


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


@pytest.mark.parametrize('approved', [False, None, 0, 1, 'yes', 'no', '', float('nan'), float('inf')])
def test_consent_is_explicit(tmp_path, approved):
    module = load()
    with pytest.raises(ValueError, match='requires the task-start yes'):
        module.open_scene('blender', tmp_path/'missing.blend', tmp_path/'review_v002.blend', approved=approved)
    assert list(tmp_path.iterdir()) == []


def test_changed_source_during_copy(tmp_path, monkeypatch):
    module = load()
    source = tmp_path/'source.blend'
    source.write_bytes(b'BLENDER-v501 original payload')
    exe = tmp_path/'app.exe'
    exe.write_bytes(b'fixture')
    output = tmp_path/'review_v002.blend'
    copy = module.shutil.copyfile
    def mutate(src, dst):
        result = copy(src, dst)
        source.write_bytes(b'BLENDER-v501 changed payload')
        return result
    monkeypatch.setattr(module.shutil, 'copyfile', mutate)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('changed source launched'))
    with pytest.raises(ValueError, match='Source changed'):
        module.open_scene('blender', source, output, approved=True, executable=exe)
    assert not output.exists()


def test_atomic_publication_rejects_racing_output(tmp_path, monkeypatch):
    module = load()
    source = tmp_path/'source.blend'
    source.write_bytes(b'BLENDER-v501 source payload')
    exe = tmp_path/'app.exe'
    exe.write_bytes(b'fixture')
    output = tmp_path/'review_v002.blend'
    link = module.os.link
    def race(src, dst):
        link(source, dst)
        return link(src, dst)
    monkeypatch.setattr(module.os, 'link', race)
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: pytest.fail('racing output launched'))
    with pytest.raises(FileExistsError):
        module.open_scene('blender', source, output, approved=True, executable=exe)
    assert source.read_bytes() == output.read_bytes() == b'BLENDER-v501 source payload'
    assert not list(tmp_path.glob('.agr-review-*'))


@pytest.mark.parametrize('version', ['v000', 'v001', 'v999', 'v1000'])
def test_version_boundaries(tmp_path, monkeypatch, version):
    module = load()
    source = tmp_path/'source.blend'
    source.write_bytes(b'BLENDER-v501 source payload')
    exe = tmp_path/'app.exe'
    exe.write_bytes(b'fixture')
    monkeypatch.setattr(module.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=42))
    assert module.open_scene('blender', source, tmp_path/f'review_{version}.blend', approved=True, executable=exe)['status'] == 'launched'


@pytest.mark.parametrize('name', ['review.blend','review_v01.blend','review_v001.partial','NaN.blend','inf.blend'])
def test_reject_unversioned_or_partial_output(tmp_path, name):
    module = load()
    source = tmp_path/'source.blend'
    source.write_bytes(b'BLENDER-v501 source payload')
    with pytest.raises(ValueError):
        module.open_scene('blender', source, tmp_path/name, approved=True)
    assert [p.name for p in tmp_path.iterdir()] == ['source.blend']
