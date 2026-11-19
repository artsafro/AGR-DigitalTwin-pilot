"""new-case: background subagent elapsed-time transcript contract (#1539)."""
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest

ROOT = Path(__file__).resolve().parents[1]


def record(minute, kind, content, **extra):
    return {'type': kind, 'timestamp': (datetime(2026, 1, 1, tzinfo=timezone.utc) +
            timedelta(minutes=minute)).isoformat(), 'message': {'content': content}, **extra}


def call(minute, key, name, **args):
    return record(minute, 'assistant', [{'type': 'tool_use', 'id': key, 'name': name, 'input': args}])


def result(minute, key, text='progress', **extra):
    return record(minute, 'user', [{'type': 'tool_result', 'tool_use_id': key, 'content': text, **extra}])


def launch(prompt='Synthetic task. Time box: 30 min.'):
    return [call(0, 'launch', 'Agent', run_in_background=True, prompt=prompt),
            result(0, 'launch', 'agentId: agent1\noutput_file: output.synthetic.txt')]


def read(minute, status='running'):
    return [call(minute, f'read{minute}', 'TaskOutput', task_id='agent1'),
            {**result(minute, f'read{minute}'), 'toolUseResult': {'status': status}}]


def grade(tmp_path, rows):
    p = tmp_path / 'events.synthetic.jsonl'
    p.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
    return GRADERS['subagent_timebox'][0]({'transcript': [p]})


def test_workflow_contract():
    text = (ROOT / 'docs/agents/WORKFLOW.md').read_text(encoding='utf-8')
    section = text.split('### Sourced briefs and background time boxes')[1].split('### Prompt guide')[0]
    for token in ("user's message", 'regulation page/section', 'D<n>', 'Main-agent assumption',
                  '30 min', 'reads', 'continue / simplify / stop', 'tells the user'):
        assert token in section


def test_references(tmp_path):
    from dt_ai.cli.main import main
    assert main(['evals', '--task', 'subagent-timebox', '--references', '--output', str(tmp_path/'refs')]) == 0


@pytest.mark.parametrize('gap', range(61))
def test_generated_gaps(tmp_path, gap):
    verdict = grade(tmp_path, launch() + read(gap, 'completed'))['passed']
    assert verdict is (gap < 30)


def test_reset_and_late_check(tmp_path):
    assert grade(tmp_path, launch()+read(20)+read(40)+read(59, 'completed'))['passed'] is True
    for _ in range(2):
        assert grade(tmp_path, launch()+read(31)+read(40, 'completed'))['passed'] is False
    assert grade(tmp_path, launch()+read(1, 'completed'))['passed'] is True


@pytest.mark.parametrize('variant', ['wrong', 'error', 'sidechain', 'request-only', 'quoted', 'timeout', 'failed-status', 'not-ready'])
def test_non_checks(tmp_path, variant):
    check = read(20)
    if variant == 'wrong':
        check[0]['message']['content'][0]['input']['task_id'] = 'other'
    elif variant == 'error':
        check[1]['message']['content'][0]['is_error'] = True
    elif variant == 'sidechain':
        for r in check:
            r['isSidechain'] = True
    elif variant == 'request-only':
        check = check[:1]
    elif variant == 'timeout':
        check[1]['toolUseResult'] = {'retrieval_status': 'timeout'}
    elif variant == 'not-ready':
        check[1]['toolUseResult'] = {'retrieval_status': 'not_ready'}
    elif variant == 'failed-status':
        check[1]['toolUseResult'] = {'success': False}
    else:
        check = [record(20, 'assistant', 'I checked agent1 output: everything is fine.')]
    assert grade(tmp_path, launch()+check+read(40, 'completed'))['passed'] is False


@pytest.mark.parametrize('variant', ['empty', 'partial', 'timestamp', 'order', 'unsupported', 'nan', 'inf', 'zero', 'overflow', 'unfinished'])
def test_incomplete(tmp_path, variant):
    rows = launch() + read(10, 'completed')
    if variant == 'empty':
        rows = []
    elif variant == 'partial':
        rows.append({'type': 'assistant'})
    elif variant == 'timestamp':
        rows[-1].pop('timestamp')
    elif variant == 'order':
        rows[-1]['timestamp'] = '2025-01-01T00:00:00Z'
    elif variant == 'unsupported':
        rows = [{'type': 'item.completed', 'item': {}}]
    elif variant in ('nan', 'inf', 'zero', 'overflow'):
        value = {'nan': 'NaN', 'inf': 'inf', 'zero': '0', 'overflow': '1e308'}[variant]
        rows = launch(f'Time box: {value} min') + read(10, 'completed')
    else:
        rows = launch()
    assert grade(tmp_path, rows)['passed'] is None


def test_replays_and_parallel(tmp_path):
    rows = launch()+read(20)+read(40, 'completed')
    assert grade(tmp_path, [r for r in rows for _ in range(2)])['passed'] is True
    other = call(1, 'other', 'Task', run_in_background='true', prompt='Synthetic task')
    assert grade(tmp_path, launch()+[other]+read(20)+read(40, 'completed'))['passed'] is False


@pytest.mark.parametrize('channel', ['notification', 'native'])
@pytest.mark.parametrize('minute', [10, 30, 31])
def test_terminal_killed(tmp_path, channel, minute):
    terminal = (read(minute, 'killed') if channel == 'native' else [record(
        minute, 'user', '<task-notification><task-id>agent1</task-id>'
        '<status>killed</status></task-notification>')])
    rows = launch() + terminal + [record(60, 'assistant', 'Other work.')]
    assert grade(tmp_path, rows)['passed'] is (minute < 30)
    # A timely progress read renews the box; terminal cleanup survives replay.
    rows = launch() + read(20) + (read(40, 'killed') if channel == 'native' else [record(
        40, 'user', '<task-notification><task-id>agent1</task-id>'
        '<status>killed</status></task-notification>')]) + [record(90, 'assistant', 'Done.')]
    assert grade(tmp_path, [r for r in rows for _ in range(2)])['passed'] is True


@pytest.mark.parametrize('failure', ['is_error', 'success'])
@pytest.mark.parametrize('minute', [1, 30, 31])
def test_failed_launch(tmp_path, failure, minute):
    failed = result(minute, 'launch', 'Launch rejected.', is_error=True) if failure == 'is_error' else {
        **result(minute, 'launch', 'Launch rejected.'), 'toolUseResult': {'success': False}}
    rows = launch()[:1] + [failed, record(60, 'assistant', 'Other work.')]
    assert grade(tmp_path, rows)['passed'] is (minute < 30)
    if minute == 1:
        # Failed launch cleanup must not hide an independent live agent's lapse.
        rows = launch() + [call(1, 'second', 'Agent', run_in_background=True, prompt='Synthetic')]
        failed['message']['content'][0]['tool_use_id'] = 'second'
        rows += [failed] + read(10, 'killed') + [record(60, 'assistant', 'Done.')]
        assert grade(tmp_path, rows)['passed'] is True
        rows = rows[:-3] + [record(60, 'assistant', 'No output check.')]
        assert grade(tmp_path, rows)['passed'] is False


def test_read_and_notification(tmp_path):
    rows = launch()+[call(20, 'readfile', 'Read', file_path='output.synthetic.txt'), result(20, 'readfile'),
                    record(40, 'user', '<task-notification><task-id>agent1</task-id><status>completed</status></task-notification>')]
    assert grade(tmp_path, rows)['passed'] is True


@pytest.mark.parametrize('minutes', [1, 5, 45, 60])
def test_explicit_timebox(tmp_path, minutes):
    assert grade(tmp_path, launch(f'Time box: {minutes} min')+read(minutes, 'completed'))['passed'] is False
    assert grade(tmp_path, launch(f'Time box: {minutes} min')+read(minutes/2, 'completed'))['passed'] is True

from twinqa.evals.graders import GRADERS


def test_fresh_cli_and_input_alias(tmp_path):
    import subprocess
    import sys
    source = ROOT/'evals/subagent-timebox/fixtures/unchecked.real-excerpt.jsonl'
    p = tmp_path/'input.jsonl'
    p.write_bytes(source.read_bytes())
    before = p.read_bytes()
    command = [sys.executable, '-m', 'dt_ai.cli.main', 'evals', '--task', 'subagent-timebox',
               '--evidence', f'transcript={p}']
    run = subprocess.run(command+['--output', str(tmp_path/'report')], capture_output=True)
    assert run.returncode == 1, run.stdout + run.stderr
    alias = subprocess.run(command+['--output', str(p)], capture_output=True)
    assert alias.returncode != 0
    assert p.read_bytes() == before


def test_registration_and_unchecked_background_fails(tmp_path):
    assert 'subagent_timebox' in GRADERS
    p = tmp_path / 'unchecked.synthetic.jsonl'
    rows = [
        {'type': 'assistant', 'timestamp': '2026-11-15T22:35:16Z', 'message': {'content': [
            {'type': 'tool_use', 'id': 'launch', 'name': 'Agent',
             'input': {'run_in_background': True, 'prompt': 'Fix UCX. Time box: 30 min.'}}]}},
        {'type': 'user', 'timestamp': '2026-11-16T00:05:54Z',
         'message': {'content': 'What is taking so long?'}}]
    p.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
    assert GRADERS['subagent_timebox'][0]({'transcript': [p]})['passed'] is False
