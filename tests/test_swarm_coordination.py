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


def invoke(build, tool='SendMessage', args=None, script=GUARD, swarm: bool | str = True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('AGR_SWARM_')}
    if swarm == 'agent-only':
        env['AGR_SWARM_AGENT_ID'] = 'l2'
    elif swarm:
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


@pytest.mark.parametrize('script', [GUARD, ROOT / '.claude/hooks/pretool.py'])
@pytest.mark.parametrize('case,reason', [
    ('workflow', 'workflow recipient l2'),
    ('wrong-part', 'l2 is not the active background owner of L2'),
    ('matching', None)])
def test_real_sendmessage_schema(build, script, case, reason):
    save(build, kind='workflow' if case == 'workflow' else 'background',
         part='windows-B' if case == 'wrong-part' else 'L2')
    result = invoke(build, script=script, args={
        'to': 'l2', 'summary': 'Continue assigned part', 'message': 'Part: L2\nContinue.'})
    assert decision(result) == ('deny' if reason else 'allow')
    if reason:
        assert reason in result['hookSpecificOutput']['permissionDecisionReason']


@pytest.mark.parametrize('extra,reason', [
    ({'content': 'Part: windows-B'}, 'ambiguous/conflicting Part header'),
    ({'part': 'windows-B'}, 'ambiguous/conflicting Part header'),
    ({'message': 'Part: L2\nPart: windows-B'}, 'ambiguous/conflicting Part header'),
    ({'message': 42}, 'message must be a string')])
def test_real_message_conflicts(build, extra, reason):
    args = {'to': 'l2', 'summary': 'Continue', 'message': 'Part: L2', **extra}
    result = invoke(build, args=args)
    assert decision(result) == 'deny'
    assert reason in result['hookSpecificOutput']['permissionDecisionReason']


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

    ({'recipient': 'l2', 'part': 'windows-B', 'content': 'Part: L2'}, True)])
def test_missing_message_scope(build, args, swarm):
    assert decision(invoke(build, args=args, swarm=swarm)) == 'deny'


def test_non_swarm_read(build):
    assert invoke(build, 'Read', {'file_path': 'unrelated'}, swarm=False) == {}


@pytest.mark.parametrize('script', [GUARD, ROOT / '.claude/hooks/pretool.py'])
def test_non_swarm_sendmessage(build, script):
    result = invoke(build, script=script, swarm=False, args={
        'to': 'unregistered', 'summary': 'Ordinary session', 'message': 'Continue.'})
    assert decision(result) == 'allow'
    assert 'swarm' not in json.dumps(result).lower()


@pytest.mark.parametrize('script', [GUARD, ROOT / '.claude/hooks/pretool.py'])
def test_swarm_agent_without_root(build, script):
    result = invoke(build, script=script, swarm='agent-only', args={
        'to': 'l2', 'summary': 'Continue', 'message': 'Part: L2'})
    assert decision(result) == 'deny'
    assert 'output root must be an absolute' in result['hookSpecificOutput']['permissionDecisionReason']


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


def test_dispatcher_preserves_swarm_warning(build):
    out = invoke(build, 'Bash', {'command': r'mkdir C:\dbg'},
                 script=ROOT / '.claude/hooks/pretool.py')
    assert 'swarm warning' in out['hookSpecificOutput']['additionalContext'].lower()


@pytest.mark.parametrize('args', [['not-a-mapping'], {'recipient': 'l2', 'content': 42},
    {'recipient': 'l2', 'part': 'L2', 'content': 'Part: L2\nPart: windows-B'}])
def test_malformed_message_denied(build, args):
    assert decision(invoke(build, args=args)) == 'deny'


def test_generated_ownership_probe(build):
    import itertools
    import runpy
    check = runpy.run_path(str(HELPER))['check_message']
    measured = 0
    for kind, status, part, recipient in itertools.product(
            ('workflow', 'background'), ('active', 'failed', 'completed'),
            ('L2', 'windows-B'), ('l2', 'unknown')):
        save(build, kind=kind, status=status, part=part)
        denied = check({'recipient': recipient, 'content': 'Part: L2'}, str(build))
        allowed = kind == 'background' and status == 'active' and part == 'L2' and recipient == 'l2'
        assert (denied is None) == allowed
        measured += 1
    assert measured == 24


def test_registration_no_clobber_and_reset(build):
    path = build / '_swarm/writers.json'
    before = path.read_bytes()
    lock = build / '_swarm/writers.lock'
    lock.write_text('foreign owner')
    args = ('register', '--root', build, '--part', 'L2', '--agent-id', 'l2', '--kind', 'background')
    assert cli(*args).returncode != 0
    assert lock.read_text() == 'foreign owner'
    assert path.read_bytes() == before
    lock.unlink()
    foreign = build / '_swarm/writers-foreign.partial'
    foreign.write_text('foreign temporary')
    assert cli(*args, '--status', 'completed').returncode == 0
    assert cli(*args[:-3], 'replacement', '--kind', 'background').returncode == 0
    assert foreign.read_text() == 'foreign temporary'
    assert decision(invoke(build)) == 'deny'  # old id was removed, no stale authorization


def test_windows_path_aliases(build):
    target = str(build / 'folder/../x.txt').replace('\\', '/').upper()
    out = invoke(build, 'Edit', {'file_path': target})
    assert 'swarm warning' not in json.dumps(out).lower()


def test_symlink_outside_write_warns(build, tmp_path):
    # Windows directory junction works without developer-mode symlink privileges.
    if os.name != 'nt':
        (build / 'escape').symlink_to(tmp_path, target_is_directory=True)
    else:
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(build / 'escape'), str(tmp_path)],
                              capture_output=True, text=True, errors='replace')
        assert made.returncode == 0, made.stderr
    try:
        out = invoke(build, 'Edit', {'file_path': str(build / 'escape/x.txt')})
        assert 'swarm warning' in json.dumps(out).lower()
    finally:
        (build / 'escape').rmdir() if os.name == 'nt' else (build / 'escape').unlink()
