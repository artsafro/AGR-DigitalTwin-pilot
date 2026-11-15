"""new-case: accepted geometry CLI regressions; fixtures are synthetic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.state import accepted_set as gate

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/state/accepted_set.py'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup_job(tmp_path):
    folder = tmp_path / 'jobs' / 'synthetic'
    folder.mkdir(parents=True)
    accepted = tmp_path / 'body_A_v004.blend'
    accepted.write_bytes(b'synthetic accepted body A v004')
    later = tmp_path / 'body_A_v008e.blend'
    later.write_bytes(b'synthetic unauthorized body A v008e')
    record = folder / 'accepted.json'
    record.write_text(json.dumps({'schema': 'accepted-set/1', 'job': 'synthetic',
        'accepted': [{'part': 'body_A', 'version': 'v004', 'path': str(accepted),
                      'sha256': digest(accepted)}]}), encoding='utf-8')
    return record, accepted, later


def cli(root, *args):
    return subprocess.run([sys.executable, str(SCRIPT), '--root', str(root),
                           '--job', 'synthetic', *map(str, args)],
                          capture_output=True, text=True, encoding='utf-8')


def make_brief(tmp_path, record, *, stage='geometry', version='v005'):
    brief = tmp_path / 'brief.json'
    brief.write_text(json.dumps({'schema': 'accepted-brief/1', 'job': 'synthetic',
        'accepted_set_sha256': digest(record),
        'actions': [{'part': 'body_A', 'stage': stage, 'version': version}]}), encoding='utf-8')
    return brief


def test_incident1_brief(tmp_path):
    record, _, _ = setup_job(tmp_path)
    brief = make_brief(tmp_path, record)
    bad = cli(tmp_path, '--brief', brief)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert 'user decision' in bad.stdout
    assert json.loads(bad.stdout)['actions'][0]['status'] == 'rejected'


def test_incident4_cli(tmp_path):
    _, accepted, later = setup_job(tmp_path)
    good = cli(tmp_path, '--part', 'body_A', '--inputs', accepted)
    assert good.returncode == 0, good.stdout + good.stderr
    assert json.loads(good.stdout)['inputs'][0]['status'] == 'accepted'
    bad = cli(tmp_path, '--part', 'body_A', '--inputs', later)
    assert bad.returncode == 1, bad.stdout + bad.stderr
    assert 'sha256' in bad.stdout and 'body_A' in bad.stdout


def store(path, payload):
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_generated_mutations(tmp_path):
    record, accepted, later = setup_job(tmp_path)
    original = accepted.read_bytes()
    for index in range(32):
        later.write_bytes(original + bytes([index]))
        result = gate.check(record, 'synthetic', [str(later)], part='body_A')
        assert result['passed'] is False
        assert result['inputs'][0]['status'] == 'rejected'
    assert accepted.read_bytes() == original


def test_generated_geometry_briefs(tmp_path):
    record, _, _ = setup_job(tmp_path)
    for index in range(4, 36):
        brief = make_brief(tmp_path, record, version=f'v{index:03d}')
        result = gate.check_brief(record, 'synthetic', brief)
        assert result['passed'] is False
        assert result['actions'][0]['status'] == 'rejected'


def test_reset_and_repeats(tmp_path):
    record, accepted, later = setup_job(tmp_path)
    for path, expected in [(accepted, True), (later, False), (later, False),
                           (later, False), (accepted, True)]:
        assert gate.check(record, 'synthetic', [str(path)], part='body_A')['passed'] is expected


def test_input_accounting(tmp_path):
    record, accepted, later = setup_job(tmp_path)
    payload = json.loads(record.read_text())
    body_b = tmp_path / 'body_B_v004.blend'
    body_b.write_bytes(b'synthetic body B')
    payload['accepted'].append({'part': 'body_B', 'version': 'v004',
                               'path': str(body_b), 'sha256': digest(body_b)})
    store(record, payload)
    result = gate.check(record, 'synthetic', [f'body_A={accepted}', f'body_A={body_b}', f'body_B={later}'])
    assert result['passed'] is False
    assert [r['status'] for r in result['inputs']] == ['accepted', 'rejected', 'rejected']
    with pytest.raises(ValueError, match='unknown accepted part.*unmapped'):
        gate.check(record, 'synthetic', [f'unmapped={accepted}'])
    with pytest.raises(ValueError, match='unknown accepted part'):
        gate.check(record, 'synthetic', [str(accepted)])


@pytest.mark.parametrize('alias_kind', ['relative', 'hardlink'])
def test_duplicate_aliases(tmp_path, alias_kind, monkeypatch):
    record, accepted, _ = setup_job(tmp_path)
    if alias_kind == 'hardlink':
        alias = tmp_path / 'alias.blend'
        alias.hardlink_to(accepted)
    else:
        monkeypatch.chdir(tmp_path)
        alias = Path('./body_A_v004.blend')
    before = accepted.read_bytes()
    with pytest.raises(ValueError, match='duplicate input'):
        gate.check(record, 'synthetic', [str(accepted), str(alias)], part='body_A')
    assert accepted.read_bytes() == before


@pytest.mark.parametrize('mode', ['inputs', 'accepted', 'actions'])
def test_empty_inputs(tmp_path, mode):
    record, accepted, _ = setup_job(tmp_path)
    if mode == 'inputs':
        with pytest.raises(ValueError, match='nonempty list'):
            gate.check(record, 'synthetic', [], part='body_A')
    elif mode == 'accepted':
        payload = json.loads(record.read_text())
        payload['accepted'] = []
        store(record, payload)
        with pytest.raises(ValueError, match='nonempty list'):
            gate.check(record, 'synthetic', [str(accepted)], part='body_A')
    else:
        brief = make_brief(tmp_path, record)
        payload = json.loads(brief.read_text())
        payload['actions'] = []
        store(brief, payload)
        with pytest.raises(ValueError, match='nonempty list'):
            gate.check_brief(record, 'synthetic', brief)


@pytest.mark.parametrize('case', ['partial', 'unsupported', 'nan', 'inf', 'duplicate',
                                 'hash63', 'hash65', 'hashnewline', 'duplicate_part',
                                 'missing_path', 'wrong_job', 'unknown_key', 'empty_file'])
def test_malformed_records(tmp_path, case):
    record, accepted, _ = setup_job(tmp_path)
    payload = json.loads(record.read_text())
    row = payload['accepted'][0]
    if case == 'partial': del row['sha256']
    elif case == 'unsupported': payload['schema'] = 'accepted-set/2'
    elif case == 'nan': row['sha256'] = float('nan')
    elif case == 'inf': row['sha256'] = float('inf')
    elif case == 'hash63': row['sha256'] = '0' * 63
    elif case == 'hash65': row['sha256'] = '0' * 65
    elif case == 'hashnewline': row['sha256'] += '\n'
    elif case == 'duplicate_part': payload['accepted'].append(dict(row))
    elif case == 'missing_path': row['path'] = str(tmp_path / 'missing.blend')
    elif case == 'wrong_job': payload['job'] = 'other'
    elif case == 'unknown_key': row['latest'] = True
    elif case == 'empty_file':
        accepted.write_bytes(b'')
        row['sha256'] = digest(accepted)
    store(record, payload)
    if case == 'duplicate':
        record.write_text(record.read_text().replace('"job": "synthetic"', '"job": "synthetic", "job": "synthetic"'))
    result = cli(tmp_path, '--part', 'body_A', '--inputs', accepted)
    assert result.returncode == 1, result.stdout + result.stderr
    assert json.loads(result.stdout)['passed'] is False


@pytest.mark.parametrize('stage', ['uv', 'textures', 'ucx', 'export', 'review'])
def test_later_stage_briefs(tmp_path, stage):
    record, _, _ = setup_job(tmp_path)
    brief = make_brief(tmp_path, record, stage=stage, version='v004')
    assert gate.check_brief(record, 'synthetic', brief)['passed'] is True
    make_brief(tmp_path, record, stage=stage, version='v008e')
    assert gate.check_brief(record, 'synthetic', brief)['passed'] is False


@pytest.mark.parametrize('case', ['correct', 'wrong_hash', 'wrong_part', 'denied', 'agent', 'missing_ref', 'repeated', 'stale'])
def test_change_decision_binding(tmp_path, case):
    record, _, _ = setup_job(tmp_path)
    payload = json.loads(record.read_text())
    decision = {'part': 'body_A', 'from_sha256': payload['accepted'][0]['sha256'],
                'to_version': 'v005', 'actor_role': 'user', 'decision': 'approved',
                'ref': 'synthetic:user-answer-2'}
    payload['change_decisions'] = [decision]
    if case == 'wrong_hash': decision['from_sha256'] = '0' * 64
    elif case == 'wrong_part': decision['part'] = 'body_B'
    elif case == 'denied': decision['decision'] = 'rejected'
    elif case == 'agent': decision['actor_role'] = 'agent'
    elif case == 'missing_ref': decision['ref'] = ''
    elif case == 'repeated': payload['change_decisions'].append(dict(decision))
    store(record, payload)
    brief = make_brief(tmp_path, record)
    if case == 'stale':
        payload['evidence'] = 'changed record'
        store(record, payload)
    if case == 'correct':
        assert gate.check_brief(record, 'synthetic', brief)['passed'] is True
        make_brief(tmp_path, record, stage='textures')
        assert gate.check_brief(record, 'synthetic', brief)['passed'] is False
    else:
        with pytest.raises(ValueError):
            gate.check_brief(record, 'synthetic', brief)


@pytest.mark.parametrize('target', ['input', 'manifest', 'earlier_source'])
def test_snapshot_changes(tmp_path, target, monkeypatch):
    record, accepted, later = setup_job(tmp_path)
    copied = tmp_path / 'copy.blend'
    copied.write_bytes(accepted.read_bytes())
    real_hash = gate._hash
    calls = 0
    def changing_hash(path):
        nonlocal calls
        calls += 1
        result = real_hash(path)
        if calls == 2:
            changed = record if target == 'manifest' else (accepted if target == 'earlier_source' else copied)
            changed.write_bytes(changed.read_bytes() + b' mutation')
        return result
    monkeypatch.setattr(gate, '_hash', changing_hash)
    with pytest.raises(ValueError, match='changed during check'):
        gate.check(record, 'synthetic', [str(copied)], part='body_A')


def test_no_output_surface(tmp_path):
    _, accepted, _ = setup_job(tmp_path)
    partial = tmp_path / 'foreign.partial'
    partial.write_bytes(b'foreign')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    result = cli(tmp_path, '--part', 'body_A', '--inputs', accepted, '--output', accepted)
    assert result.returncode != 0
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_freeze_documents():
    root = SCRIPT.parents[2]
    for path in ['docs/agents/WORKFLOW.md', 'docs/procedure/TASK_TO_MODEL.md']:
        text = (root / path).read_text(encoding='utf-8')
        assert 'accepted.json' in text and 'frozen' in text
        assert 'helpers' in text and '4bk-k3' in text


def test_earlier_source_changes_during_later_input(tmp_path, monkeypatch):
    record, accepted, later = setup_job(tmp_path)
    copied = tmp_path / 'copy.blend'
    copied.write_bytes(accepted.read_bytes())
    payload = json.loads(record.read_text())
    payload['accepted'].append({'part': 'body_B', 'version': 'v004',
                               'path': str(later), 'sha256': digest(later)})
    store(record, payload)
    real_hash = gate._hash
    def change_earlier(path):
        result = real_hash(path)
        if path == later:
            accepted.write_bytes(b'changed after first part was verified')
        return result
    monkeypatch.setattr(gate, '_hash', change_earlier)
    with pytest.raises(ValueError, match='changed during check'):
        gate.check(record, 'synthetic', [f'body_A={copied}', f'body_B={later}'])


@pytest.mark.parametrize('case', ['empty', 'unknown_stage', 'unknown_part', 'duplicate_action',
                                 'unsupported', 'nan', 'partial', 'unbound_override'])
def test_malformed_briefs(tmp_path, case):
    record, _, _ = setup_job(tmp_path)
    brief = make_brief(tmp_path, record, stage='textures', version='v004')
    payload = json.loads(brief.read_text())
    action = payload['actions'][0]
    if case == 'empty': payload = {}
    elif case == 'unknown_stage': action['stage'] = 'repair-magic'
    elif case == 'unknown_part': action['part'] = 'missing'
    elif case == 'duplicate_action': payload['actions'].append(dict(action))
    elif case == 'unsupported': payload['schema'] = 'accepted-brief/2'
    elif case == 'nan': action['version'] = float('nan')
    elif case == 'partial': del action['version']
    elif case == 'unbound_override': action['user_decision'] = 'approved'
    store(brief, payload)
    with pytest.raises(ValueError):
        gate.check_brief(record, 'synthetic', brief)


def test_same_bytes_copy_and_relative_record(tmp_path):
    record, accepted, _ = setup_job(tmp_path)
    payload = json.loads(record.read_text())
    payload['accepted'][0]['path'] = '../../body_A_v004.blend'
    store(record, payload)
    copied = tmp_path / 'unrelated_filename.blend'
    copied.write_bytes(accepted.read_bytes())
    assert gate.check(record, 'synthetic', [str(copied)], part='body_A')['passed'] is True
    # A successful brief cannot mask rejected actual bytes in a combined CLI call.
    brief = make_brief(tmp_path, record, stage='textures', version='v004')
    copied.write_bytes(b'changed candidate')
    result = cli(tmp_path, '--part', 'body_A', '--inputs', copied, '--brief', brief)
    assert result.returncode == 1
    assert json.loads(result.stdout)['passed'] is False
