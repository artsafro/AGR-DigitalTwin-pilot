"""new-case: fresh-process and input-race boundaries for review textures (#1365)."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/review/review_textures.py'


def load():
    spec = importlib.util.spec_from_file_location('review_textures_boundary', SCRIPT)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def test_generated_joint_thresholds():
    gate = load()
    for limit in range(1, 257):
        for texels in (1, 2, 3):
            result = gate.joint_sampling({'joint_m': texels / limit, 'tile_m': 1}, limit)
            assert result['status'] == ('pass' if texels > 2 else 'review')


@pytest.mark.parametrize('changed', ['scene', 'scope'])
def test_input_change_refuses_report(tmp_path, monkeypatch, changed):
    gate = load()
    scene, scope, report = [tmp_path / name for name in ('scene.blend', 'scope.json', 'report.json')]
    scene.write_bytes(b'scene')
    scope.write_text(json.dumps({'ids': [{'object': 'Brick', 'id': 1}]}))
    def opening(**kwargs):
        (scene if changed == 'scene' else scope).write_bytes(b'changed')
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace(
        app=SimpleNamespace(version=(5, 1, 2), version_string='synthetic'),
        ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=opening)),
        context=SimpleNamespace(scene=SimpleNamespace(unit_settings=SimpleNamespace(system='METRIC')))))
    monkeypatch.setattr(gate, 'check_blender', lambda *args: {'status': 'pass', 'ids': []})
    with pytest.raises(ValueError, match='input changed'):
        gate.main(['--scene', str(scene), '--scope', str(scope), '--report', str(report)])
    assert not report.exists()


def test_fresh_process_alias_and_stale_report(tmp_path):
    # Synthetic bpy stub: CLI protection executes before any scene opening.
    (tmp_path / 'bpy.py').write_text('app = type("App", (), {"version": (5, 1, 2)})()\n')
    scene = tmp_path / 'scene.blend'
    scene.write_bytes(b'unchanged scene')
    scope = tmp_path / 'scope.json'
    scope.write_bytes(b'unchanged scope')
    occupied = tmp_path / 'report.json'
    occupied.write_bytes(b'foreign report')
    alias = tmp_path / 'hardlink.json'
    alias.hardlink_to(scene)
    partial = tmp_path / 'report.json.partial'
    partial.write_bytes(b'foreign partial')
    for target in (scene, scope, alias, occupied):
        code = f'import sys,runpy;sys.path.insert(0,{str(tmp_path)!r});runpy.run_path({str(SCRIPT)!r},run_name="__main__")'
        result = subprocess.run([sys.executable, '-c', code, '--scene', str(scene), '--scope', str(scope),
                                 '--report', str(target)], capture_output=True, text=True)
        assert result.returncode != 0
        assert 'report must be a new path' in result.stderr
    assert scene.read_bytes() == b'unchanged scene'
    assert scope.read_bytes() == b'unchanged scope'
    assert occupied.read_bytes() == b'foreign report'
    assert partial.read_bytes() == b'foreign partial'


@pytest.mark.parametrize('status', ['fail', 'review', 'not_run', 'unknown'])
def test_cli_nonpass_never_returns_success(tmp_path, monkeypatch, status):
    gate = load()
    scene, scope, report = [tmp_path / name for name in ('scene.blend', 'scope.json', 'report.json')]
    scene.write_bytes(b'synthetic')
    scope.write_text(json.dumps({'ids': [{'object': 'Brick', 'id': 1}]}))
    monkeypatch.setitem(sys.modules, 'bpy', SimpleNamespace(
        app=SimpleNamespace(version=(5, 1, 2), version_string='synthetic'),
        ops=SimpleNamespace(wm=SimpleNamespace(open_mainfile=lambda **kwargs: None)),
        context=SimpleNamespace(scene=SimpleNamespace(unit_settings=SimpleNamespace(system='METRIC')))))
    monkeypatch.setattr(gate, 'check_blender', lambda *args: {'status': status, 'ids': []})
    with pytest.raises(RuntimeError, match='review textures: ' + status):
        gate.main(['--scene', str(scene), '--scope', str(scope), '--report', str(report)])
    assert json.loads(report.read_text())['status'] == status
