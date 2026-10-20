"""new-case: repository-only capability session and benchmark evidence contracts."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from twinqa.evals.graders import GRADERS

IDS = ('bbox', 'levels', 'floor_areas', 'silhouettes', 'mesh', 'triangle_budget',
       'opening_planes', 'material_ids', 'decor', 'orientation')


def report():
    return {'passed': True, 'failed': [], 'not_measured': [],
            'checks': [{'id': name, 'status': 'pass', 'value': 0, 'limit': 0} for name in IDS]}


def test_complete_benchmark_reports(tmp_path):
    paths = []
    for name in ('report', 'etalon-self'):
        path = tmp_path / f'{name}.json'
        path.write_text(json.dumps(report()), encoding='utf-8')
        paths.append(path)
    assert 'capability_b01' in GRADERS
    row = GRADERS['capability_b01'][0]({'benchmark': [paths[0]], 'self_check': [paths[1]]})
    assert row['passed'] is True
    assert row['measured'] == '20/20'


@pytest.fixture(autouse=True)
def synthetic_agent_home(tmp_path, monkeypatch):
    home = tmp_path / 'synthetic-home'
    home.mkdir()
    (home / 'AGENTS.md').write_text('SYNTHETIC forbidden inherited context')
    (home / 'auth.json').write_text('{"synthetic": true}')
    monkeypatch.setenv('CODEX_HOME', str(home))


@pytest.fixture
def repository(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    for folder in ('benchmark', 'jobs'):
        (repo / folder).mkdir()
        (repo / folder / 'sentinel').write_text('source', encoding='utf-8')
    for args in (('init', '-b', 'main'), ('add', '.'),
                 ('-c', 'user.email=a@example.invalid', '-c', 'user.name=Synthetic', 'commit', '-m', 'synthetic')):
        subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
    return repo


def test_launch_lifecycle(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    import hashlib
    (tmp_path / 'inputs').mkdir()
    etalon = tmp_path / 'inputs/etalon.fbx'
    etalon.write_bytes(b'synthetic FBX; not a real etalon')
    digest = hashlib.sha256(etalon.read_bytes()).hexdigest()
    # Synthetic subprocess explicitly produces test-only reports, never the reference.
    code = ("import pathlib,json,os; home=pathlib.Path(os.environ['CODEX_HOME']); "
            "assert not (home/'AGENTS.md').exists(); "
            "assert json.loads((home/'auth.json').read_text()) == {'synthetic': True}; "
            "out=pathlib.Path(__import__('sys').argv[1]); "
            "out.mkdir(); data=" + repr(report()) + "; "
            "[(out/n).write_text(json.dumps(data)) for n in ('report.json','etalon-self.json')]; "
            "print('synthetic transcript')")
    run_dir = tmp_path / 'runs' / 'one'
    result = launch(repository, run_dir, etalon, agent='codex', expected_sha=digest,
                    command=[sys.executable, '-c', code, '{output}'], timeout=20)
    assert not (run_dir / 'worktree').exists()
    assert (run_dir / 'transcript.jsonl').read_text().strip() == 'synthetic transcript'
    assert result['benchmark']['passed'] == 1
    assert result['procedural']['passed'] == 0
    assert result['procedural']['not_measured'] > 0
    assert result['passed'] is False
    assert result['cleanup'] is True
    for folder in ('benchmark', 'jobs'):
        assert (repository / folder / 'sentinel').read_text() == 'source'
    assert subprocess.run(['git', 'status', '--porcelain'], cwd=repository,
                          capture_output=True, text=True).stdout == ''


@pytest.mark.parametrize('mutation', ['empty', 'partial', 'duplicate', 'unknown', 'nan', 'inf',
                                      'fail', 'review', 'not_run', 'not_measured', 'aggregate', 'key'])
def test_report_matrix(tmp_path, mutation):
    data = report()
    if mutation == 'empty':
        data = {}
    elif mutation == 'partial':
        data['checks'].pop()
    elif mutation == 'duplicate':
        data['checks'][-1] = data['checks'][0]
    elif mutation == 'unknown':
        data['checks'][-1]['id'] = 'unmapped'
    elif mutation in ('nan', 'inf'):
        data['checks'][0]['value'] = float(mutation)
    elif mutation in ('fail', 'review', 'not_run', 'not_measured'):
        data['checks'][0]['status'] = mutation
    elif mutation == 'aggregate':
        data['passed'] = False
    raw = json.dumps(data)
    if mutation == 'key':
        raw = raw.replace('"passed": true', '"passed": false, "passed": true')
    path = tmp_path / 'report.json'
    path.write_text(raw, encoding='utf-8')
    row = GRADERS['capability_b01'][0]({'benchmark': [path], 'self_check': [path]})
    assert row['passed'] is False


def test_all_check_subsets(tmp_path):
    path = tmp_path / 'subset.json'
    for mask in range(1 << len(IDS)):
        data = report()
        data['checks'] = [r for i, r in enumerate(data['checks']) if mask & (1 << i)]
        path.write_text(json.dumps(data), encoding='utf-8')
        row = GRADERS['capability_b01'][0]({'benchmark': [path], 'self_check': [path]})
        assert row['passed'] is (mask == (1 << len(IDS)) - 1), mask


def test_reordered_checks(tmp_path):
    data = report()
    data['checks'].reverse()
    path = tmp_path / 'report.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    assert GRADERS['capability_b01'][0]({'benchmark': [path], 'self_check': [path]})['passed'] is True


def test_task_registered():
    from twinqa.evals.runner import load_tasks
    root = Path(__file__).resolve().parents[1]
    tasks = load_tasks(root / 'evals', suite='capability')
    assert [(p.name, problem) for p, _, problem in tasks] == [('capability-b01', None)]


@pytest.mark.parametrize('location', ['repo', 'jobs', 'benchmark', 'etalon', 'parent', 'existing', 'hardlink'])
def test_output_guards(repository, tmp_path, location):
    from tools.qa.capability_b01 import launch
    import hashlib
    import os
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    etalon = inputs / 'etalon.fbx'
    etalon.write_bytes(b'synthetic')
    output = {'repo': repository / 'new', 'jobs': repository / 'jobs/new',
              'benchmark': repository / 'benchmark/new', 'etalon': inputs / 'new',
              'parent': tmp_path, 'existing': inputs, 'hardlink': tmp_path / 'alias'}[location]
    if location == 'hardlink':
        os.link(etalon, output)
    before = etalon.read_bytes()
    with pytest.raises(ValueError):
        launch(repository, output, etalon, expected_sha=hashlib.sha256(before).hexdigest(),
               command=[sys.executable, '-c', 'raise RuntimeError("must not run")'])
    assert etalon.read_bytes() == before
    assert not (repository / 'jobs/new').exists()
    assert not (repository / 'benchmark/new').exists()


@pytest.mark.parametrize('kind', ['exit', 'timeout'])
def test_session_failure(repository, tmp_path, kind):
    from tools.qa.capability_b01 import launch
    import hashlib
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    etalon = inputs / 'etalon.fbx'
    etalon.write_bytes(b'synthetic')
    code = 'import sys; print("synthetic failure",file=sys.stderr); sys.exit(7)' if kind == 'exit' else 'import time; time.sleep(30)'
    out = tmp_path / 'runs/failed'
    result = launch(repository, out, etalon, expected_sha=hashlib.sha256(etalon.read_bytes()).hexdigest(),
                    command=[sys.executable, '-c', code], timeout=0.2 if kind == 'timeout' else 10)
    assert result['session_exit'] == (7 if kind == 'exit' else 124)
    assert result['passed'] is False
    assert result['cleanup'] is True
    assert not (out / 'worktree').exists()
    assert (out / 'stderr.log').is_file()


def test_bad_etalon(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    etalon = tmp_path / 'inputs/etalon.fbx'
    etalon.parent.mkdir()
    etalon.write_bytes(b'synthetic')
    out = tmp_path / 'runs/bad'
    with pytest.raises(ValueError, match='SHA256'):
        launch(repository, out, etalon, expected_sha='0' * 64, command=[sys.executable, '-c', 'pass'])
    assert not out.exists()


def test_existing_run(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    out = tmp_path / 'existing'
    out.mkdir()
    (out / 'keep').write_text('keep')
    with pytest.raises(ValueError, match='exists'):
        launch(repository, out, tmp_path / 'absent.fbx')
    assert (out / 'keep').read_text() == 'keep'


def test_state_reference(tmp_path):
    from tools.state.project_state import generate
    import tools.state.project_state as state
    reference = tmp_path / 'evals/capability-b01/reference.json'
    reference.parent.mkdir(parents=True)
    reference.write_text(json.dumps({'schema': 1, 'agent': 'codex', 'passed': False,
                                    'benchmark': {'passed': 1, 'failed': 0, 'not_measured': 0},
                                    'procedural': {'passed': 0, 'failed': 0, 'not_measured': 10},
                                    'context': 'repository + user skills'}))
    from unittest.mock import patch
    def capture(argv, cwd):
        if argv[:2] == ['git', 'log']:
            return 'abcdef1\tMerge pull request #1 synthetic'
        if argv[:3] == ['git', 'remote', 'get-url']:
            return 'https://github.com/example/synthetic'
        return '[]'
    with patch.object(state, '_capture', capture):
        text = generate(tmp_path, tmp_path / 'state.md', 12, 12)
    assert 'Capability A (`capability-b01`, codex)' in text
    assert 'benchmark 1 passed / 0 failed / 0 not measured' in text
    assert 'procedural 0 passed / 0 failed / 10 not measured' in text
    assert 'not ready' in text
    assert 'repository + user skills' in text


@pytest.mark.parametrize('mutation', ['duplicate', 'missing_value', 'extra_key'])
def test_incomplete_report_fields(tmp_path, mutation):
    data = report()
    if mutation == 'missing_value':
        del data['checks'][0]['value']
    elif mutation == 'extra_key':
        data['unmapped_key'] = True
    raw = json.dumps(data)
    if mutation == 'duplicate':
        raw = raw.replace('"status": "pass"', '"status": "fail", "status": "pass"', 1)
    path = tmp_path / 'bad.json'
    path.write_text(raw)
    assert GRADERS['capability_b01'][0]({'benchmark': [path], 'self_check': [path]})['passed'] is False


def test_linked_worktree_output_guard(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    import hashlib
    linked = tmp_path / 'linked'
    subprocess.run(['git', 'worktree', 'add', '--detach', str(linked), 'main'],
                   cwd=repository, check=True, capture_output=True)
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    etalon = inputs / 'etalon.fbx'
    etalon.write_bytes(b'synthetic')
    try:
        with pytest.raises(ValueError, match='overlaps'):
            launch(linked, repository / 'new-output', etalon,
                   expected_sha=hashlib.sha256(etalon.read_bytes()).hexdigest(), command=[sys.executable, '-V'])
        assert not (repository / 'new-output').exists()
    finally:
        subprocess.run(['git', 'worktree', 'remove', str(linked)], cwd=repository, check=True, capture_output=True)


@pytest.mark.parametrize('change', ['protected', 'etalon', 'head'])
def test_changing_inputs_fail_closed(repository, tmp_path, change):
    from tools.qa.capability_b01 import launch
    import hashlib
    etalon = tmp_path / 'input/etalon.fbx'
    etalon.parent.mkdir()
    etalon.write_bytes(b'synthetic')
    actions = {
        'protected': "pathlib.Path('jobs/sentinel').write_text('changed')",
        'etalon': "pathlib.Path(sys.argv[1]).write_bytes(b'changed')",
        'head': "subprocess.run(['git','-c','user.email=a@example.invalid','-c','user.name=Synthetic','commit','--allow-empty','-m','change'],check=True)",
    }
    result = launch(repository, tmp_path / 'runs/change', etalon,
                    expected_sha=hashlib.sha256(etalon.read_bytes()).hexdigest(),
                    command=[sys.executable, '-c', 'import pathlib,sys,subprocess; ' + actions[change], str(etalon)])
    assert result['passed'] is False
    assert result['cleanup'] is True
    assert result['head_unchanged' if change == 'head' else 'protected_inputs_unchanged'] is False
    assert (repository / 'jobs/sentinel').read_text() == 'source'


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf'), True])
def test_invalid_timeout_writes_nothing(repository, tmp_path, timeout):
    from tools.qa.capability_b01 import launch
    out = tmp_path / 'new'
    with pytest.raises(ValueError, match='timeout'):
        launch(repository, out, tmp_path / 'absent.fbx', timeout=timeout)
    assert not out.exists()


def test_prepared_home_cannot_overlap_run(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    import hashlib
    etalon = tmp_path / 'inputs/etalon.fbx'
    etalon.parent.mkdir()
    etalon.write_bytes(b'synthetic')
    out = tmp_path / 'new'
    with pytest.raises(ValueError, match='home'):
        launch(repository, out, etalon, codex_home=out / 'agent-home',
               command=[sys.executable, '-V'], expected_sha=hashlib.sha256(etalon.read_bytes()).hexdigest())
    assert not out.exists()


def test_prepared_home_and_closed_stdin(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    import hashlib
    home = tmp_path / 'operator-home'
    home.mkdir()
    (home / 'config.toml').write_text('synthetic operator configuration')
    etalon = tmp_path / 'input/etalon.fbx'
    etalon.parent.mkdir()
    etalon.write_bytes(b'synthetic')
    code = ("import os,sys,pathlib; assert sys.stdin.read() == ''; "
            "assert pathlib.Path(os.environ['CODEX_HOME']) == pathlib.Path(sys.argv[1]); "
            "print('prepared context')")
    result = launch(repository, tmp_path / 'runs/prepared', etalon,
                    expected_sha=hashlib.sha256(etalon.read_bytes()).hexdigest(),
                    command=[sys.executable, '-c', code, str(home)], codex_home=home,
                    isolation='context-only; no OS sandbox', timeout=10)
    assert result['session_exit'] == 0
    assert result['isolation'] == 'context-only; no OS sandbox'
    assert result['cleanup'] is True
    assert (home / 'config.toml').read_text() == 'synthetic operator configuration'


def test_codex_default_excludes_host_skills():
    from tools.qa.capability_b01 import agent_command
    argv = agent_command('codex')
    assert argv[argv.index('--enable') + 1] == 'skip_host_skill_discovery'
    assert 'memories' in argv and 'plugins' in argv


def test_fresh_cli_rejects_input_alias(repository, tmp_path):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'tools/qa/capability_b01.py'),
                             '--repo', str(repository), '--run-dir', str(repository / 'jobs/new'),
                             '--etalon', str(tmp_path / 'missing.fbx')],
                            capture_output=True, text=True)
    assert result.returncode == 2
    assert 'overlaps input' in result.stderr
    assert not (repository / 'jobs/new').exists()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows directory junction probe')
def test_junction_output_alias(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    junction = tmp_path / 'alias'
    subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(repository)],
                   capture_output=True, check=True)
    try:
        with pytest.raises(ValueError, match='overlaps input'):
            launch(repository, junction / 'jobs/new', tmp_path / 'missing.fbx')
        assert not (repository / 'jobs/new').exists()
    finally:
        junction.rmdir()


def test_native_transcript_not_measured(tmp_path):
    from twinqa.evals.graders import no_hook_denial
    path = tmp_path / 'native.jsonl'
    path.write_text('{"type":"thread.started","thread_id":"synthetic"}\n'
                    '{"type":"turn.completed","usage":{"input_tokens":1}}\n')
    assert no_hook_denial({'transcript': [path]})['passed'] is None
