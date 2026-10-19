"""Synthetic subprocess probes: no DCC installation or real model is used."""
import importlib
import itertools
import json
import os
from pathlib import Path
import subprocess

import pytest


@pytest.fixture
def runner():
    return importlib.import_module('dt_ai.core.blender_runner')


@pytest.mark.parametrize('override', [None, 'explicit blender.exe', Path('custom/blender.exe')])
@pytest.mark.parametrize('environment', [None, 'environment/blender.exe'])
def test_executable_policy(runner, monkeypatch, override, environment):
    monkeypatch.delenv('TWINQA_BLENDER', raising=False)
    monkeypatch.setenv('PATH', 'untrusted-blender')
    if environment:
        monkeypatch.setenv('TWINQA_BLENDER', environment)
    assert runner.blender_executable(override) == str(
        override or environment or 'C:/Program Files/Blender Foundation/Blender 5.1/blender.exe')
    assert runner.BLENDER_VERSION == '5.1.2'


@pytest.mark.parametrize('timeout', [1, 45, 900])
def test_isolation_arguments_timeout_and_success_log(runner, monkeypatch, tmp_path, timeout):
    out, log = tmp_path / 'report.json', tmp_path / 'saved.log'
    script = tmp_path / 'script with spaces.py'
    arguments = ['source with spaces.fbx', '--scope', 'selected only', str(out)]
    monkeypatch.setenv('BLENDER_USER_CONFIG', 'hostile/config')
    monkeypatch.setenv('BLENDER_USER_SCRIPTS', 'hostile/scripts')
    def fake(cmd, **kw):
        assert cmd == ['custom.exe', '--background', '--factory-startup', '--disable-autoexec',
                       '--python-exit-code', '1', '--python', str(script), '--', *arguments]
        assert kw['timeout'] == timeout
        assert kw['env']['BLENDER_USER_CONFIG'] != 'hostile/config'
        assert kw['env']['BLENDER_USER_SCRIPTS'] != 'hostile/scripts'
        assert Path(kw['env']['BLENDER_USER_CONFIG']).is_dir()
        out.write_text('{"synthetic": true}')
        return subprocess.CompletedProcess(cmd, 0, 'stdout marker', 'stderr marker')
    monkeypatch.setattr(subprocess, 'run', fake)
    assert runner.run_blender(script, arguments, executable='custom.exe', output_json=out,
                              log_path=log, timeout=timeout) == {'synthetic': True}
    assert 'stdout marker' in log.read_text() and 'stderr marker' in log.read_text()


@pytest.mark.parametrize('mode', ['missing_json', 'stale_json', 'nonzero_exit', 'exception', 'timeout', 'invalid_json'])
@pytest.mark.parametrize('preexisting', [False, True])
def test_failures_share_envelope_and_keep_log(runner, monkeypatch, tmp_path, mode, preexisting):
    out, log = tmp_path / 'report.json', tmp_path / 'saved.log'
    if preexisting:
        out.write_text('{"old":true}')
        os.utime(out, (1, 1))
    def fake(cmd, **kw):
        if mode == 'exception':
            raise OSError('spawn marker')
        if mode == 'timeout':
            raise subprocess.TimeoutExpired(cmd, kw['timeout'], output=b'partial stdout', stderr=b'partial stderr')
        if mode == 'stale_json':
            out.write_text('{"synthetic":true}')
            os.utime(out, (1, 1))
        elif mode == 'invalid_json':
            out.write_text('not json')
        elif mode == 'nonzero_exit':
            out.write_text('{"synthetic":true}')
        return subprocess.CompletedProcess(cmd, 7 if mode == 'nonzero_exit' else 0, 'stdout', 'stderr')
    monkeypatch.setattr(subprocess, 'run', fake)
    with pytest.raises(runner.BlenderRunError) as caught:
        runner.run_blender('script.py', [str(out)], output_json=out, log_path=log, timeout=12)
    envelope = caught.value.envelope
    assert set(envelope) == {'code', 'message', 'command', 'log', 'returncode', 'timeout'}
    expected = 'stale_json' if preexisting and mode == 'missing_json' else mode
    assert envelope['code'] == expected
    assert envelope['log'] == str(log.resolve())
    assert envelope['timeout'] == 12
    assert envelope['command'][-1] == str(out)
    assert envelope['returncode'] == (7 if mode == 'nonzero_exit' else None if mode in ('exception', 'timeout') else 0)
    assert expected in str(caught.value)
    assert log.is_file() and log.stat().st_size > 0
    if mode == 'timeout':
        assert 'partial stdout' in log.read_text() and 'partial stderr' in log.read_text()
    if mode in ('exception', 'timeout'):
        assert caught.value.__cause__ is not None


@pytest.mark.parametrize('kind', ['missing', 'stale', 'empty', 'fresh'])
def test_export_without_json_checks_native_artifacts(runner, monkeypatch, tmp_path, kind):
    outputs = [tmp_path / 'model.blend', tmp_path / 'model.fbx']
    def fake(cmd, **kw):
        for path in outputs:
            if kind != 'missing':
                path.write_bytes(b'' if kind == 'empty' else b'synthetic')
                if kind == 'stale':
                    os.utime(path, (1, 1))
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    kwargs = dict(outputs=outputs, log_path=tmp_path / 'export.log')
    if kind == 'fresh':
        assert runner.run_blender('export.py', [], **kwargs) is None
    else:
        with pytest.raises(runner.BlenderRunError):
            runner.run_blender('export.py', [], **kwargs)


def test_generated_failure_priority(runner, monkeypatch, tmp_path):
    """Brute force exit-code/report-state combinations: exit failure always wins."""
    for code, state in itertools.product([0, 1, 7, -9], ['missing', 'old', 'valid', 'malformed']):
        out = tmp_path / f'{code}-{state}.json'
        def fake(cmd, **kw):
            if state != 'missing':
                out.write_text('{' if state == 'malformed' else '{}')
                if state == 'old':
                    os.utime(out, (1, 1))
            return subprocess.CompletedProcess(cmd, code, '', '')
        monkeypatch.setattr(subprocess, 'run', fake)
        if code == 0 and state == 'valid':
            assert runner.run_blender('probe.py', [], output_json=out) == {}
        else:
            expected = 'nonzero_exit' if code else {'missing':'missing_json', 'old':'stale_json', 'malformed':'invalid_json'}[state]
            with pytest.raises(runner.BlenderRunError) as caught:
                runner.run_blender('probe.py', [], output_json=out)
            assert caught.value.envelope['code'] == expected


def test_config_is_unique_per_run_and_host_environment_is_unchanged(runner, monkeypatch, tmp_path):
    keys = ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES')
    for key in keys:
        monkeypatch.setenv(key, 'hostile/' + key)
    configs = []
    def fake(cmd, **kw):
        current = [Path(kw['env'][key]) for key in keys]
        assert len(set(current)) == 3
        assert all(path.is_dir() and not list(path.iterdir()) for path in current)
        assert all(kw['env'][key] != os.environ[key] for key in keys)
        configs.extend(current)
        out.write_text('{}')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    for index in range(2):
        out = tmp_path / f'isolation-{index}.json'
        runner.run_blender('probe.py', output_json=out, log_path=tmp_path / f'{index}.log')
    assert len(set(configs)) == 6
    assert all(not path.exists() for path in configs)
    assert all(os.environ[key] == 'hostile/' + key for key in keys)


@pytest.mark.parametrize('state', ['unchanged_future', 'deleted', 'empty', 'malformed'])
def test_preexisting_report_is_not_accepted_without_fresh_valid_evidence(runner, monkeypatch, tmp_path, state):
    out = tmp_path / 'old-report.json'
    out.write_text('{"old": true}')
    os.utime(out, (4_000_000_000, 4_000_000_000))
    def fake(cmd, **kw):
        if state == 'deleted':
            out.unlink()
        elif state in ('empty', 'malformed'):
            out.write_text('' if state == 'empty' else '{')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    with pytest.raises(runner.BlenderRunError) as caught:
        runner.run_blender('probe.py', output_json=out, log_path=tmp_path / 'old.log')
    assert caught.value.envelope['code'] == {
        'unchanged_future': 'stale_json', 'deleted': 'missing_json',
        'empty': 'invalid_json', 'malformed': 'invalid_json',
    }[state]


@pytest.mark.parametrize('timeout', [None, 0, -1, float('inf'), float('nan')])
def test_timeout_cannot_disable_the_process_deadline(runner, monkeypatch, tmp_path, timeout):
    """Every accepted run has a finite positive deadline, even through the CLI."""
    launched = []
    out, log = tmp_path / 'report.json', tmp_path / 'deadline.log'
    def fake(cmd, **kw):
        launched.append(cmd)
        out.write_text('{}')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    with pytest.raises(runner.BlenderRunError) as caught:
        runner.run_blender('probe.py', output_json=out, log_path=log, timeout=timeout)
    assert caught.value.envelope['code'] == 'exception'
    assert 'timeout' in caught.value.envelope['message'].lower()
    assert log.is_file()
    assert launched == []


def test_relative_evidence_is_resolved_in_child_cwd(runner, monkeypatch, tmp_path):
    child = tmp_path / 'child'
    child.mkdir()
    out = child / 'relative.json'
    def fake(cmd, **kw):
        assert Path(kw['cwd']) == child
        assert cmd[-1] == 'relative.json'
        out.write_text('{"synthetic": true}')
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr(subprocess, 'run', fake)
    assert runner.run_blender('probe.py', ['relative.json'], output_json='relative.json',
                              cwd=child, log_path=tmp_path / 'cwd.log') == {'synthetic': True}


def test_reading_future_dated_report_does_not_make_it_fresh(runner, monkeypatch, tmp_path):
    out = tmp_path / 'future.json'
    out.write_text('{"old": true}')
    future = 4_000_000_000_000_000_000
    os.utime(out, ns=(future, future))

    def fake(cmd, **kw):
        out.read_text()
        # Deterministically simulate read-access metadata updates even on
        # filesystems with lazy/disabled atime updates. No data was written.
        os.utime(out, ns=(1, future))
        return subprocess.CompletedProcess(cmd, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', fake)
    with pytest.raises(runner.BlenderRunError) as caught:
        runner.run_blender('probe.py', output_json=out, log_path=tmp_path / 'future.log')
    assert caught.value.envelope['code'] == 'stale_json'


@pytest.mark.parametrize('preexisting', [False, True])
def test_report_written_during_config_setup_is_still_stale(runner, monkeypatch, tmp_path, preexisting):
    """Evidence must be produced by the child, not during pre-launch setup."""
    out = tmp_path / 'report.json'
    if preexisting:
        out.write_text('{"old": true}')
        os.utime(out, (1, 1))
    temporary_directory = runner.tempfile.TemporaryDirectory

    class SetupWritesReport:
        def __init__(self, *args, **kwargs):
            self.directory = temporary_directory(*args, **kwargs)

        def __enter__(self):
            directory = self.directory.__enter__()
            out.write_text('{"synthetic": true}')
            return directory

        def __exit__(self, *args):
            return self.directory.__exit__(*args)

    monkeypatch.setattr(runner.tempfile, 'TemporaryDirectory', SetupWritesReport)
    monkeypatch.setattr(subprocess, 'run', lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, '', ''))
    with pytest.raises(runner.BlenderRunError) as caught:
        runner.run_blender('probe.py', output_json=out, log_path=tmp_path / 'setup.log')
    assert caught.value.envelope['code'] == 'stale_json'


@pytest.mark.blender
@pytest.mark.skipif(os.environ.get('RUN_BLENDER_SMOKE') != '1', reason='opt in with RUN_BLENDER_SMOKE=1 and -m blender')
def test_native_pinned_blender_smoke(runner, tmp_path):
    script, out = tmp_path / 'smoke.py', tmp_path / 'smoke.json'
    script.write_text("import bpy, json, sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text(json.dumps({'version': bpy.app.version_string}))\n")
    result = runner.run_blender(script, [str(out)], output_json=out, timeout=60,
                                log_path=out.with_suffix('.blender.log'))
    assert result['version'] == '5.1.2'
    assert out.with_suffix('.blender.log').is_file()


def test_timeout_retains_diagnostic_in_envelope_message(runner, monkeypatch, tmp_path):
    out = tmp_path / 'report.json'
    log = tmp_path / 'blender.log'
    precreated = subprocess.TimeoutExpired(cmd=['b'], timeout=1, stderr=b'IMPORTANT_TIMEOUT_DIAGNOSTIC')

    def fake_run(*args, **kwargs):
        raise precreated

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(runner.BlenderRunError) as exc_info:
        runner.run_blender('probe.py', output_json=out, log_path=log, timeout=1)

    error = exc_info.value
    assert error.envelope['code'] == 'timeout'
    assert 'IMPORTANT_TIMEOUT_DIAGNOSTIC' in error.envelope['message']
    assert 'IMPORTANT_TIMEOUT_DIAGNOSTIC' in str(error)
    assert error.__cause__ is precreated
    assert 'IMPORTANT_TIMEOUT_DIAGNOSTIC' in log.read_text(encoding='utf-8')


@pytest.mark.parametrize(
    ('stderr', 'stdout', 'expected_message', 'check_mode'),
    [
        (
            'stderr_priority',
            'stdout_ignored',
            'Blender timed out after 1 seconds: stderr_priority',
            'basic',
        ),
        (
            None,
            'partial',
            'Blender timed out after 1 seconds: partial',
            'basic',
        ),
        (
            None,
            b'partial',
            'Blender timed out after 1 seconds: partial',
            'basic',
        ),
        (
            None,
            None,
            'Blender timed out after 1 seconds',
            'basic',
        ),
        (
            '',
            'stdout_fallback',
            'Blender timed out after 1 seconds: stdout_fallback',
            'basic',
        ),
        (
            'PREFIX_' + ('x' * 5000) + '_FINAL_DIAGNOSTIC',
            'FULL_STDOUT',
            'Blender timed out after 1 seconds: ' + ('PREFIX_' + ('x' * 5000) + '_FINAL_DIAGNOSTIC')[-400:],
            'long_stderr',
        ),
        (
            ('а' * 50).encode('utf-8') + b'\xff' + ('б' * 399).encode('utf-8'),
            None,
            'Blender timed out after 1 seconds: \ufffd' + ('б' * 399),
            'unicode_invalid_utf8',
        ),
    ],
    ids=[
        'stderr_str_precedence_over_stdout',
        'stderr_none_stdout_str_partial',
        'stderr_none_stdout_bytes',
        'both_none_exact_message',
        'empty_stderr_fallback',
        'long_stderr_5000_x_last_400_chars',
        'invalid_utf8_replacement_and_unicode_slicing',
    ],
)
def test_timeout_diagnostic_edge_coverage(runner, monkeypatch, tmp_path, stderr, stdout, expected_message, check_mode):
    out = tmp_path / 'report.json'
    log = tmp_path / 'blender.log'
    precreated = subprocess.TimeoutExpired(cmd=['b'], timeout=1, output=stdout, stderr=stderr)

    def fake_run(*args, **kwargs):
        raise precreated

    monkeypatch.setattr(subprocess, 'run', fake_run)
    with pytest.raises(runner.BlenderRunError) as exc_info:
        runner.run_blender('probe.py', output_json=out, log_path=log, timeout=1)

    error = exc_info.value
    assert error.envelope['code'] == 'timeout'
    assert error.__cause__ is precreated
    assert error.envelope['message'] == expected_message
    assert expected_message in str(error)

    log_content = log.read_text(encoding='utf-8')
    if check_mode == 'long_stderr':
        assert 'PREFIX_' not in error.envelope['message']
        assert '_FINAL_DIAGNOSTIC' in error.envelope['message']
        assert len(error.envelope['message'].split(': ', 1)[1]) == 400
        assert ('PREFIX_' + ('x' * 5000) + '_FINAL_DIAGNOSTIC') in log_content
        assert 'FULL_STDOUT' in log_content
    elif check_mode == 'unicode_invalid_utf8':
        assert '\ufffd' in error.envelope['message']
        assert 'а' not in error.envelope['message']
        assert len(error.envelope['message'].split(': ', 1)[1]) == 400
        assert '\ufffd' in log_content
        assert ('а' * 50) in log_content
        assert ('б' * 399) in log_content
