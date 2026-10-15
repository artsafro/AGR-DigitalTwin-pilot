"""Each entry point must preserve its script protocol through the shared policy."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_target(relative):
    spec = importlib.util.spec_from_file_location('issue59_target', ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('entry', ['build', 'scene', 'clearance', 'benchmark'])
def test_entrypoint_keeps_protocol_and_applies_policy(monkeypatch, tmp_path, entry):
    paths = {'build': 'src/dt_ai/core/build.py', 'scene': 'src/twinqa/scene.py',
             'clearance': 'tools/qa/check_clearance.py', 'benchmark': 'tools/qa/run_benchmark.py'}
    module = load_target(paths[entry])
    source, out = tmp_path / 'selected source.fbx', tmp_path / 'result.json'
    observed = []
    monkeypatch.setenv('TWINQA_BLENDER', 'configured.exe')
    # Compatibility discovery in the unchanged baseline must not need an install.
    if hasattr(module, 'find_blender'):
        monkeypatch.setattr(module, 'find_blender', lambda: 'configured.exe')
    def fake(cmd, **kw):
        observed.append((cmd, kw))
        args = cmd[cmd.index('--') + 1:]
        destination = Path(json.loads(Path(args[0]).read_text())['result']) if entry == 'build' else Path(args[-1])
        destination.write_text('{"synthetic":true}')
        return subprocess.CompletedProcess(cmd, 0, 'retained stdout', 'retained stderr')
    monkeypatch.setattr(subprocess, 'run', fake)
    if entry == 'build':
        module.run_blender('configured.exe', ROOT, {'result': str(out)}, tmp_path / 'work')
        script, expected, timeout = ROOT / 'adapters/blender/bridge.py', [str((tmp_path / 'work/request.json').resolve())], 180
    elif entry == 'scene':
        module.readback(source, blender='configured.exe', timeout=37)
        script, expected, timeout = module.READBACK, None, 37
    elif entry == 'clearance':
        module.faces_from_fbx(source)
        script, expected, timeout = module.EXPORT_FACES, None, 900
    else:
        module.blender_run('configured.exe', module.MEASURE, source, out, timeout=38)
        script, expected, timeout = module.MEASURE, [str(source), str(out)], 38
    assert len(observed) == 1
    cmd, kw = observed[0]
    assert cmd[:6] == ['configured.exe', '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1']
    assert cmd[6:9] == ['--python', str(script), '--']
    actual = cmd[9:]
    if expected is None:
        assert actual[0] == str(source) and Path(actual[-1]).name in ('faces.json', 'readback.json')
    else:
        assert actual == expected
    assert kw['timeout'] == timeout
    assert 'BLENDER_USER_CONFIG' in kw['env']


def test_benchmark_native_export_preserves_all_three_arguments(monkeypatch, tmp_path):
    module = load_target('tools/qa/run_benchmark.py')
    args = [tmp_path / 'dump.json', tmp_path / 'model.blend', tmp_path / 'model.fbx']
    def fake(cmd, **kw):
        assert cmd[cmd.index('--') + 1:] == list(map(str, args))
        for p in args[1:]:
            p.write_bytes(b'synthetic')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    module.blender_run('override.exe', module.EXPORT, *args)
    assert args[1].with_suffix('.blender.log').is_file()


def test_profile_cli_preserves_ledger_scope_and_inner_timeout(monkeypatch, tmp_path):
    """Exercise profile's real nested command factory and runner CLI, no DCC."""
    import ast
    from types import SimpleNamespace
    from dt_ai.core import blender_runner
    module = load_target('tools/run_profile_checks.py')
    tree = ast.parse(Path(module.__file__).read_text())
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    factory = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'blender')
    scope = dict(vars(module), args=SimpleNamespace(blender=tmp_path / 'override.exe', timeout=17))
    exec(compile(ast.Module(body=[factory], type_ignores=[]), module.__file__, 'exec'), scope)
    for script, cfg in [('render_profile_comparison.py', 'render.json'), ('check_npm_vpm_scale.py', 'scale-folder'),
                        ('check_profile_agr.py', 'agr.json'), ('reverse-check.py', 'reverse.json')]:
        out = tmp_path / (script + '.json')
        command = scope['blender'](ROOT / 'tools' / script, tmp_path / cfg, out)
        assert command[:2] == [sys.executable, str(Path(blender_runner.__file__).resolve())]
        def fake(cmd, **kw):
            assert cmd[0] == str((tmp_path / 'override.exe').resolve())
            assert cmd[cmd.index('--') + 1:] == [str(tmp_path / cfg)]
            assert cmd[cmd.index('--python') + 1] == str(ROOT / 'tools' / script)
            assert '--factory-startup' in cmd and '--disable-autoexec' in cmd
            assert kw['timeout'] == 17
            out.write_text('{"synthetic":true}')
            return subprocess.CompletedProcess(cmd, 0, '', '')
        monkeypatch.setattr(subprocess, 'run', fake)
        assert blender_runner.main(command[2:]) == 0
        assert out.with_suffix('.blender.log').is_file()


def test_from_source_modules_export_is_native_not_json(monkeypatch, tmp_path):
    module = load_target('tools/qa/run_from_source.py')
    script = ROOT / 'tools/export/export_modules_blender.py'
    source, out = tmp_path / 'modules-scene.json', tmp_path / 'modules.blend'
    def fake(cmd, **kw):
        assert cmd[cmd.index('--') + 1:] == [str(source), str(out)]
        assert kw['timeout'] == 3600
        out.write_bytes(b'synthetic blend, not JSON')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    module.blender_run('override.exe', script, source, out, timeout=3600)
    assert out.with_suffix('.blender.log').is_file()


@pytest.mark.parametrize('entry', ['scene', 'clearance'])
def test_temporary_readback_cleanup_does_not_delete_error_log(monkeypatch, tmp_path, entry):
    from dt_ai.core.blender_runner import BlenderRunError
    module = load_target('src/twinqa/scene.py' if entry == 'scene' else 'tools/qa/check_clearance.py')
    monkeypatch.setattr(subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 7, 'saved stdout', 'saved stderr'))
    with pytest.raises(BlenderRunError) as caught:
        if entry == 'scene':
            module.readback(tmp_path / 'synthetic.fbx')
        else:
            module.faces_from_fbx(tmp_path / 'synthetic.fbx')
    envelope = caught.value.envelope
    assert envelope['code'] == 'nonzero_exit'
    assert 'saved stdout' in Path(envelope['log']).read_text()
    assert not Path(envelope['command'][-1]).exists()


def test_runner_cli_reports_same_error_envelope(monkeypatch, tmp_path, capsys):
    from dt_ai.core import blender_runner
    monkeypatch.setattr(subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 7, '', 'failure'))
    log = tmp_path / 'cli.log'
    assert blender_runner.main(['--script', 'scope.py', '--output-json', str(tmp_path / 'missing.json'),
                                '--log', str(log), '--timeout', '13', '--', 'original argument']) == 1
    envelope = json.loads(capsys.readouterr().err)
    assert envelope['code'] == 'nonzero_exit' and envelope['returncode'] == 7
    assert envelope['timeout'] == 13
    assert envelope['command'][-1] == 'original argument' and log.is_file()
