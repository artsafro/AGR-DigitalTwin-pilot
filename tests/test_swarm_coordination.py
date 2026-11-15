"""new-case: synthetic swarm ownership and output-root hook contracts (#1450)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / '.claude/hooks/guard.py'
HELPER = ROOT / 'tools/hooks/swarm.py'


@pytest.fixture
def build(tmp_path):
    root = tmp_path / 'build'
    (root / '_swarm').mkdir(parents=True)
    save(root)
    return root


def save(root, kind='background', part='L2', status='active'):
    data = {'output_root': str(root), 'writers': [
        {'part': part, 'agent_id': 'l2', 'kind': kind, 'status': status}]}
    (root / '_swarm/writers.json').write_text(json.dumps(data), encoding='utf-8')


def invoke(build, tool='SendMessage', args=None, script=GUARD, swarm=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('AGR_SWARM_')}
    if swarm:
        env.update(AGR_SWARM_BUILD_ROOT=str(build), AGR_SWARM_AGENT_ID='l2')
    payload = {'tool_name': tool, 'tool_input': args if args is not None else {
        'recipient': 'l2', 'content': 'Part: L2\nContinue the assigned part.'}, 'cwd': str(build)}
    run = subprocess.run([sys.executable, str(script)], input=json.dumps(payload),
                         text=True, capture_output=True, env=env, cwd=ROOT)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout) if run.stdout.strip() else {}


def decision(result):
    return result.get('hookSpecificOutput', {}).get('permissionDecision', 'allow')


@pytest.mark.parametrize('case', ['workflow', 'wrong-part', 'matching'])
def test_sendmessage_ownership(build, case):
    save(build, kind='workflow' if case == 'workflow' else 'background',
         part='windows-B' if case == 'wrong-part' else 'L2')
    result = invoke(build)
    assert decision(result) == ('allow' if case == 'matching' else 'deny')
    if case != 'matching':
        assert 'swarm' in json.dumps(result).lower()


@pytest.mark.parametrize('case', ['outside', 'inside'])
def test_write_warning(build, case):
    target = r'C:\png_v003\x.png' if case == 'outside' else str(build / 'parts/x.txt')
    out = invoke(build, 'Write', {'file_path': target, 'content': 'synthetic'})
    assert ('swarm warning' in json.dumps(out).lower()) == (case == 'outside')


def test_registry_reload_and_reset(build):
    assert decision(invoke(build)) == 'allow'
    save(build, status='failed')
    assert decision(invoke(build)) == 'deny'
    save(build)
    assert decision(invoke(build)) == 'allow'


def test_repeated_denial(build):
    save(build, kind='workflow')
    for _ in range(2):
        assert decision(invoke(build)) == 'deny'


@pytest.mark.parametrize('bad', ['missing', '', '{}', '[]', 'NaN', 'Infinity',
                                'duplicate', 'kind', 'status', 'partial', 'root'])
def test_invalid_registry(build, bad):
    path = build / '_swarm/writers.json'
    data = json.loads(path.read_text())
    if bad == 'missing':
        path.unlink()
    elif bad in ('duplicate', 'kind', 'status', 'partial', 'root'):
        if bad == 'duplicate':
            data['writers'].append(dict(data['writers'][0]))
        elif bad in ('kind', 'status'):
            data['writers'][0][bad] = 'unsupported'
        elif bad == 'partial':
            del data['writers'][0]['part']
        else:
            data['output_root'] = str(build.parent)
        path.write_text(json.dumps(data))
    else:
        path.write_text(bad)
    assert decision(invoke(build)) == 'deny'


@pytest.mark.parametrize('args,swarm', [({}, True), ({'recipient': 'l2'}, True),
    ({'recipient': 'unknown', 'content': 'Part: L2'}, True),
    ({'recipient': 'l2', 'content': 'Part: L2'}, False),
    ({'recipient': 'l2', 'part': 'windows-B', 'content': 'Part: L2'}, True)])
def test_missing_message_scope(build, args, swarm):
    assert decision(invoke(build, args=args, swarm=swarm)) == 'deny'


def test_non_swarm_read(build):
    assert invoke(build, 'Read', {'file_path': 'unrelated'}, swarm=False) == {}


@pytest.mark.parametrize('suffix,outside', [('x.txt', False), ('sub/../x.txt', False),
    ('../build-other/x.txt', True), ('../x.txt', True), ('', False)])
def test_path_matrix(build, suffix, outside):
    out = invoke(build, 'Edit', {'file_path': str(build / suffix), 'old_string': 'x', 'new_string': 'y'})
    assert ('swarm warning' in json.dumps(out).lower()) == outside


def test_shell_write_warning(build):
    out = invoke(build, 'Bash', {'command': r'mkdir C:\dbg'})
    assert 'swarm warning' in json.dumps(out).lower()


def test_dispatcher_sendmessage(build):
    save(build, kind='workflow')
    assert decision(invoke(build, script=ROOT / '.claude/hooks/pretool.py')) == 'deny'
    settings = json.loads((ROOT / '.claude/settings.json').read_text())
    assert any('SendMessage' in item.get('matcher', '') for item in settings['hooks']['PreToolUse'])


def cli(*args):
    return subprocess.run([sys.executable, str(HELPER), *map(str, args)],
                          text=True, capture_output=True, cwd=ROOT)


def test_register_cli(tmp_path):
    root = tmp_path / 'fresh-build'
    command = ('register', '--root', root, '--part', 'L2', '--agent-id', 'l2', '--kind', 'background')
    first = cli(*command)
    assert first.returncode == 0, first.stderr
    assert f'Output root: {root}' in first.stdout
    assert 'AGR_SWARM_BUILD_ROOT' in first.stdout
    registry = root / '_swarm/writers.json'
    before = registry.read_bytes()
    duplicate = cli(*command[:-3], 'other', '--kind', 'background')
    assert duplicate.returncode != 0
    assert registry.read_bytes() == before
    for bad_root in ('relative', 'C:\\', 'C:relative'):
        assert cli('register', '--root', bad_root, '--part', 'L2', '--agent-id', 'x',
                   '--kind', 'background').returncode != 0


def test_documented_sample():
    text = (ROOT / 'docs/agents/WORKFLOW.md').read_text(encoding='utf-8')
    assert '## Swarm coordination' in text
    sample = json.loads((ROOT / 'docs/agents/examples/swarm/writers.json').read_text())
    assert Path(sample['output_root']).is_absolute()
    assert sample['writers'][0]['kind'] in ('workflow', 'background')
