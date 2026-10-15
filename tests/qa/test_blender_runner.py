"""Headless process contract; all inputs and outputs are synthetic."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from twinqa.scene import readback
from dt_ai.core.blender import BlenderError, DEFAULT_BLENDER, executable, run_blender


@pytest.mark.parametrize("timeout", [1, 45, 600])
def test_readback_isolated_and_log_retained(monkeypatch, tmp_path, timeout):
    source = tmp_path / "synthetic.fbx"
    calls = []

    def process(cmd, **kwargs):
        calls.append((cmd, kwargs))
        Path(cmd[-1]).write_text('{}', encoding='utf-8')
        return subprocess.CompletedProcess(cmd, 0, 'synthetic log', '')

    monkeypatch.setattr(subprocess, 'run', process)
    assert readback(source, blender='synthetic-blender', timeout=timeout) == {}
    assert len(calls) == 1
    cmd, options = calls[0]
    assert '--disable-autoexec' in cmd
    assert '--factory-startup' in cmd
    assert options['timeout'] == timeout
    assert (tmp_path / 'synthetic.fbx.readback.log').read_text(encoding='utf-8') == 'synthetic log'


@pytest.mark.parametrize('failure', ['missing_output', 'stale_output', 'nonzero_exit', 'exception', 'timeout', 'invalid_json'])
@pytest.mark.parametrize('existing', [False, True])
def test_process_failures_have_one_envelope_and_saved_log(monkeypatch, tmp_path, failure, existing):
    out, log = tmp_path / 'evidence.json', tmp_path / 'blender.log'
    if existing or failure == 'stale_output':
        out.write_text('{}', encoding='utf-8')
        os.utime(out, (1, 1))
    calls = []

    def process(cmd, **kwargs):
        calls.append(cmd)
        if failure == 'exception':
            raise OSError('synthetic launch failure')
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(cmd, kwargs['timeout'], output=b'partial log')
        if failure == 'missing_output':
            out.unlink(missing_ok=True)
        if failure in ('nonzero_exit', 'invalid_json'):
            out.write_text('{}' if failure == 'nonzero_exit' else '{', encoding='utf-8')
        return subprocess.CompletedProcess(cmd, 7 if failure == 'nonzero_exit' else 0, 'stdout', 'stderr')

    monkeypatch.setattr(subprocess, 'run', process)
    with pytest.raises(BlenderError) as caught:
        run_blender('synthetic.py', [out], outputs=[out], log=log, timeout=12)
    envelope = caught.value.envelope
    assert envelope['code'] == failure
    assert envelope['log'] == str(log)
    assert envelope['timeout'] == 12
    assert log.is_file() and log.stat().st_size > 0
    assert len(calls) == 1
    assert '--factory-startup' in calls[0] and '--disable-autoexec' in calls[0]


@pytest.mark.parametrize('override,environment,expected', [
    (None, None, DEFAULT_BLENDER),
    (None, 'environment-blender', 'environment-blender'),
    ('explicit-blender', 'environment-blender', 'explicit-blender'),
])
def test_executable_precedence(monkeypatch, override, environment, expected):
    monkeypatch.delenv('TWINQA_BLENDER', raising=False)
    if environment:
        monkeypatch.setenv('TWINQA_BLENDER', environment)
    assert executable(override) == expected


@pytest.mark.parametrize('entry', ['benchmark_measure', 'benchmark_export', 'build', 'clearance', 'scene', 'profile'])
def test_entry_points_keep_scope_and_arguments(monkeypatch, tmp_path, entry):
    import run_benchmark
    import check_clearance
    from dt_ai.core.build import run_blender as build_blender
    from tools.run_profile_checks import run_blender_stage

    calls = []
    source = tmp_path / 'synthetic.fbx'
    out = tmp_path / 'result.json'
    script = tmp_path / 'synthetic.py'

    def process(cmd, **options):
        calls.append((cmd, options))
        if entry == 'build':
            request = json.loads(Path(cmd[-1]).read_text(encoding='utf-8'))
            Path(request['result']).write_text('{}', encoding='utf-8')
        elif entry == 'benchmark_export':
            for name in cmd[-2:]:
                Path(name).write_bytes(b'synthetic')
        else:
            Path(cmd[-1]).write_text('{}', encoding='utf-8')
        return subprocess.CompletedProcess(cmd, 0, 'scoped log', '')

    monkeypatch.setattr(subprocess, 'run', process)
    monkeypatch.setenv('TWINQA_BLENDER', 'synthetic-blender')
    if entry == 'benchmark_measure':
        run_benchmark.blender_run('synthetic-blender', run_benchmark.MEASURE, source, out)
        expected_script, expected_args, timeout = run_benchmark.MEASURE, [source, out], 900
    elif entry == 'benchmark_export':
        blend, fbx = tmp_path / 'model.blend', tmp_path / 'model.fbx'
        run_benchmark.blender_run('synthetic-blender', run_benchmark.EXPORT, out, blend, fbx)
        expected_script, expected_args, timeout = run_benchmark.EXPORT, [out, blend, fbx], 900
    elif entry == 'build':
        assert build_blender('synthetic-blender', tmp_path, {'result': str(out)}, tmp_path / 'work') == {}
        expected_script = tmp_path / 'adapters/blender/bridge.py'
        expected_args, timeout = [(tmp_path / 'work/request.json').resolve()], 180
    elif entry == 'clearance':
        assert check_clearance.faces_from_fbx(source) == {}
        expected_script, expected_args, timeout = check_clearance.EXPORT_FACES, None, 900
    elif entry == 'scene':
        assert readback(source, blender='synthetic-blender') == {}
        from twinqa.scene import READBACK
        expected_script, expected_args, timeout = READBACK, None, 600
    else:
        class Record:
            def run_stage(self, name, command, outputs, **options):
                assert name == 'scale' and outputs == {'evidence': out}
                assert options['resources'] == [tmp_path]
                process(command, timeout=options['timeout'])
                stdout, stderr = tmp_path / 'stdout.log', tmp_path / 'stderr.log'
                stdout.write_text('ledger log', encoding='utf-8')
                stderr.write_text('', encoding='utf-8')
                return dict(status='produced', returncode=0, stdout=str(stdout), stderr=str(stderr))
        run_blender_stage(Record(), 'scale', script, out, {'evidence': out}, tmp_path, 'synthetic-blender', 240)
        expected_script, expected_args, timeout = script, [out], 240
    assert len(calls) == 1
    command, options = calls[0]
    assert command[:6] == ['synthetic-blender', '--background', '--factory-startup', '--disable-autoexec', '--python-exit-code', '1']
    assert command[6:9] == ['--python', str(expected_script), '--']
    assert options['timeout'] == timeout
    if expected_args is not None:
        assert command[9:] == list(map(str, expected_args))
    else:
        assert command[9] == str(source)


@pytest.mark.parametrize('suffix', ['.json', '.fbx', '.blend', '.png'])
@pytest.mark.parametrize('rewrite', [False, True])
def test_stale_evidence_is_never_accepted(monkeypatch, tmp_path, suffix, rewrite):
    out, log = tmp_path / ('synthetic' + suffix), tmp_path / 'process.log'
    out.write_text('{}', encoding='utf-8')
    os.utime(out, (1, 1))
    calls = []

    def process(command, **options):
        calls.append(command)
        if rewrite:
            out.write_text('{"synthetic": true}', encoding='utf-8')
            os.utime(out, (1, 1))
        return subprocess.CompletedProcess(command, 0, 'saved stdout', 'saved stderr')

    monkeypatch.setattr(subprocess, 'run', process)
    with pytest.raises(BlenderError) as caught:
        run_blender('synthetic.py', outputs=[out], log=log)
    assert caught.value.envelope['code'] == 'stale_output'
    assert len(calls) == 1
    assert 'saved stdoutsaved stderr' in log.read_text(encoding='utf-8')


def test_success_validates_all_outputs_and_returns_only_json(monkeypatch, tmp_path):
    outputs = [tmp_path / ('synthetic' + suffix) for suffix in ('.json', '.fbx', '.blend', '.png')]

    def process(command, **options):
        for out in outputs:
            out.write_text('{"synthetic": true}', encoding='utf-8')
        return subprocess.CompletedProcess(command, 0, 'saved stdout', 'saved stderr')

    monkeypatch.setattr(subprocess, 'run', process)
    log = tmp_path / 'process.log'
    assert run_blender('synthetic.py', outputs=outputs, log=log) == {outputs[0]: {'synthetic': True}}
    assert log.read_text(encoding='utf-8') == 'saved stdoutsaved stderr'


@pytest.mark.blender
@pytest.mark.skipif(os.environ.get('RUN_BLENDER_SMOKE') != '1', reason='opt in with RUN_BLENDER_SMOKE=1')
def test_native_blender_smoke(tmp_path):
    script, out = tmp_path / 'smoke.py', tmp_path / 'smoke.json'
    script.write_text("import bpy, json, pathlib, sys\nassert bpy.app.version[:3] == (5, 1, 2)\npathlib.Path(sys.argv[-1]).write_text(json.dumps({'synthetic': True}))\n", encoding='utf-8')
    assert run_blender(script, [out], outputs=[out], log=tmp_path / 'smoke.log')[out] == {'synthetic': True}
