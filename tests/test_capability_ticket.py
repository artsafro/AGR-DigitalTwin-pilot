"""new-case: local PR evidence and closed-ticket capability replay contracts."""
import json
from pathlib import Path

import subprocess
import sys
import pytest

from test_capability_b01 import repository, synthetic_agent_home  # noqa: F401
from twinqa.evals.pr_graders import TRACE_FIELDS, pr_agent_trace, pr_numeric_literals


def ticket():
    return {'number': 111, 'state': 'CLOSED', 'title': 'Synthetic documentation ticket',
            'body': 'Document the bounded synthetic diagnostic.',
            'labels': [{'name': 'documentation'}, {'name': 'ready-for-agent'}]}


def test_ticket_lifecycle(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    code = ("import pathlib,subprocess,sys; "
            "pathlib.Path('docs').mkdir(); pathlib.Path('docs/change.md').write_text('synthetic change'); "
            "subprocess.run(['git','add','.'],check=True); "
            "subprocess.run(['git','-c','user.name=Synthetic','-c','user.email=a@example.invalid',"
            "'commit','-m','synthetic'],check=True); "
            "pathlib.Path(sys.argv[1]).write_text(" + repr(body()) + ")")
    out = tmp_path / 'runs/ticket'
    result = launch(repository, out, ticket=ticket(), command=[sys.executable, '-c', code, '{body}'])
    assert result['session_exit'] == 0
    assert result['local_pr'] == {'passed': 1, 'failed': 0, 'not_measured': 0}
    assert result['procedural']['not_measured'] == 10
    assert result['passed'] is False
    assert result['cleanup'] is True
    assert (out / 'pr-body.md').read_text() == body()
    assert 'synthetic change' in (out / 'local.diff').read_text()
    assert result['branch'].startswith('harness/capability-ticket-111-')
    assert not (out / 'worktree').exists()
    assert subprocess.run(['git', 'status', '--porcelain'], cwd=repository,
                          capture_output=True, text=True).stdout == ''
    assert subprocess.run(['git', 'branch', '--list', result['branch']], cwd=repository,
                          capture_output=True, text=True).stdout == ''



def body():
    return ('## Author receipts\nPattern: new-case: synthetic control\n'
            'Regression evals: not measured (synthetic)\nProbe: synthetic\n'
            '## Agent trace\n' + ''.join(f'- {name}: synthetic\n' for name in TRACE_FIELDS))


def test_local_pr_evidence(tmp_path):
    text = tmp_path / 'body.md'
    text.write_text(body())
    diff = tmp_path / 'local.diff'
    diff.write_text('diff --git a/src/dt_ai/control.py b/src/dt_ai/control.py\n'
                    '--- a/src/dt_ai/control.py\n+++ b/src/dt_ai/control.py\n'
                    '@@ -0,0 +1 @@\n+LIMIT = 17\n')
    assert pr_agent_trace({'body': [text]})['passed'] is True
    assert pr_numeric_literals({'body': [text], 'diff': [diff]})['passed'] is False
    text.write_text(body() + '\n17 follows [D073]\n')
    assert pr_numeric_literals({'body': [text], 'diff': [diff]})['passed'] is True
    assert not (tmp_path / 'view.json').exists()


@pytest.mark.parametrize('mutation', ['empty', 'partial', 'open', 'number', 'zero', 'nan', 'inf',
                                      'label', 'area', 'duplicate', 'unsupported'])
def test_ticket_validation(repository, tmp_path, mutation):
    from tools.qa.capability_b01 import launch
    data = ticket()
    if mutation == 'empty':
        data = {}
    elif mutation == 'partial':
        del data['body']
    elif mutation == 'open':
        data['state'] = 'OPEN'
    elif mutation in ('number', 'zero', 'nan', 'inf'):
        data['number'] = {'number': True, 'zero': 0, 'nan': float('nan'), 'inf': float('inf')}[mutation]
    elif mutation == 'label':
        data['labels'].pop()
    elif mutation == 'area':
        data['labels'][0]['name'] = 'geometry'
    elif mutation == 'duplicate':
        data['labels'].append(data['labels'][0])
    else:
        data = []
    out = tmp_path / 'run'
    with pytest.raises(ValueError):
        launch(repository, out, ticket=data, command=[sys.executable, '-c', 'raise AssertionError'])
    assert not out.exists()


def local_artifacts(tmp_path):
    paths = {name: [tmp_path / filename] for name, filename in
             [('body', 'pr-body.md'), ('diff', 'local.diff'), ('branch', 'branch.txt')]}
    paths['body'][0].write_text(body())
    paths['branch'][0].write_text('harness/capability-ticket-synthetic')
    paths['diff'][0].write_text('diff --git a/docs/a.md b/docs/a.md\n'
                              '--- a/docs/a.md\n+++ b/docs/a.md\n@@ -0,0 +1 @@\n+synthetic\n')
    return paths


@pytest.mark.parametrize('mutation', ['empty_body', 'empty_diff', 'bad_diff', 'branch', 'receipt',
                                      'trace', 'duplicate', 'hardlink', 'unknown'])
def test_ticket_evidence_matrix(tmp_path, mutation):
    from twinqa.evals.capability import capability_ticket
    from twinqa.evals.graders import EvidenceError
    paths = local_artifacts(tmp_path)
    if mutation == 'empty_body':
        paths['body'][0].write_text('')
    elif mutation == 'empty_diff':
        paths['diff'][0].write_text('')
    elif mutation == 'bad_diff':
        paths['diff'][0].write_text('unsupported')
    elif mutation == 'branch':
        paths['branch'][0].write_text('claude/automatic-abcdef')
    elif mutation == 'receipt':
        paths['body'][0].write_text(body().replace('Regression evals:', 'omitted:'))
    elif mutation == 'trace':
        paths['body'][0].write_text(body().replace('- Duration:', '- Unknown:'))
    elif mutation == 'duplicate':
        paths['body'].append(paths['body'][0])
    elif mutation == 'hardlink':
        import os
        paths['branch'][0].unlink()
        os.link(paths['body'][0], paths['branch'][0])
    else:
        paths['unmapped'] = [paths['body'][0]]
    try:
        assert capability_ticket(paths)['passed'] is not True
    except EvidenceError:
        assert mutation == 'bad_diff'


def test_local_review_evidence(tmp_path):
    from twinqa.evals.pr_graders import pr_review_rounds
    path = tmp_path / 'body.md'
    path.write_text(body())
    assert pr_review_rounds({'body': [path]})['passed'] is None
    view = tmp_path / 'reviews.json'
    for order in ([1, 3, 2, 3], [3, 3, 1], [4, 1], [1, 4]):
        view.write_text(json.dumps({'comments': [{'body': f'Review round {n}'} for n in order]}))
        assert pr_review_rounds({'pr': [view]})['passed'] is (max(order) <= 3)


@pytest.mark.parametrize('location', ['same', 'nested', 'existing', 'home'])
def test_ticket_output_guards(repository, tmp_path, location):
    from tools.qa.capability_b01 import launch
    target = {'same': repository, 'nested': repository / 'new',
              'existing': tmp_path, 'home': tmp_path / 'synthetic-home'}[location]
    before = (repository / 'jobs/sentinel').read_bytes()
    with pytest.raises(ValueError):
        launch(repository, target, ticket=ticket(), command=[sys.executable, '-c', 'raise AssertionError'])
    assert (repository / 'jobs/sentinel').read_bytes() == before


def test_local_cli_in_fresh_process(tmp_path):
    paths = local_artifacts(tmp_path)
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, '-c', 'from dt_ai.cli.main import main; raise SystemExit(main())',
                             'evals', '--task', 'capability-ticket', '--main', str(tmp_path),
                             '--output', str(tmp_path / 'result')], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads((tmp_path / 'result/report.json').read_text())['passed'] == 1


def test_new_protected_inputs_fail_closed(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    code = ("import pathlib; p=pathlib.Path('src/twinqa/evals/new.py'); "
            "p.parent.mkdir(parents=True); p.write_text('tampered')")
    result = launch(repository, tmp_path / 'runs/changed', ticket=ticket(),
                    command=[sys.executable, '-c', code])
    assert result['changed_evaluation_inputs'] == ['src/twinqa/evals/new.py']
    assert result['protected_inputs_unchanged'] is False
    assert result['passed'] is False and result['cleanup'] is True


def test_ticket_state(tmp_path):
    from tools.state.project_state import generate
    import tools.state.project_state as state
    from unittest.mock import patch
    reference = tmp_path / 'evals/capability-ticket/reference.json'
    reference.parent.mkdir(parents=True)
    reference.write_text(json.dumps({'schema': 1, 'agent': 'codex', 'passed': False,
                                    'local_pr': {'passed': 0, 'failed': 1, 'not_measured': 0},
                                    'procedural': {'passed': 0, 'failed': 0, 'not_measured': 10},
                                    'context': 'repository + user skills'}))
    def capture(argv, cwd):
        if argv[:2] == ['git', 'log']:
            return 'abcdef1\tMerge pull request #1 synthetic'
        if argv[:3] == ['git', 'remote', 'get-url']:
            return 'https://github.com/example/synthetic'
        return '[]'
    with patch.object(state, '_capture', capture):
        text = generate(tmp_path, tmp_path / 'state.md', 12, 12)
    assert 'Capability B (`capability-ticket`, codex)' in text
    assert 'local_pr 0 passed / 1 failed / 0 not measured' in text
    assert 'procedural 0 passed / 0 failed / 10 not measured' in text
    assert 'not ready; repository + user skills' in text


def test_ticket_reference():
    import hashlib
    root = Path(__file__).resolve().parents[1] / 'evals/capability-ticket'
    data = json.loads((root / 'reference.json').read_text(encoding='utf-8'))
    assert data['ticket'] == 111 and data['context'] == 'repository + user skills'
    assert data['decision'] == 'D159'
    assert data['session_exit'] == 0 and data['committed'] and data['cleanup']
    assert data['passed'] is False
    assert data['local_pr'] == {'passed': 0, 'failed': 1, 'not_measured': 0}
    assert data['procedural'] == {'passed': 0, 'failed': 0, 'not_measured': 10}
    assert data['threshold']['local_checks'] == 4
    assert data['threshold']['selected_after_reference'] is True
    assert data['external_skills']['loaded'] == ['codex-work-review', 'codex-work-route']
    for name, digest in data['committed_evidence'].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
    from twinqa.evals.runner import run
    # Regrade the frozen native artifacts, not a hand-written replacement answer.
    import tempfile
    with tempfile.TemporaryDirectory() as output:
        _, report, _ = run(root.parent, task='capability-ticket', main=root / 'reference',
                           overrides={k: root / 'reference' / v for k, v in
                                      [('body', 'pr-body.md'), ('diff', 'local.diff'), ('branch', 'branch.txt')]},
                           output=Path(output) / 'eval', cwd=root)
    assert report['failed'] == 1 and report['not_measured'] == 0
    assert report['checks'][0]['measured'] == '3/4'


def test_generated_trace_subsets_and_review_rounds(tmp_path):
    from twinqa.evals.pr_graders import pr_review_rounds
    path = tmp_path / 'body.md'
    for mask in range(1 << len(TRACE_FIELDS)):
        path.write_text('## Agent trace\n' + ''.join(f'- {field}: synthetic\n' for i, field in
                                                   enumerate(TRACE_FIELDS) if mask & (1 << i)))
        assert pr_agent_trace({'body': [path]})['passed'] is (mask == 1023), mask
    path = tmp_path / 'reviews.json'
    for first in range(7):
        for second in range(7):
            path.write_text(json.dumps({'comments': [{'body': f'Review round {n}'} for n in
                                                    [first, second, first]]}))
            assert pr_review_rounds({'pr': [path]})['passed'] is (max(first, second) <= 3)


def test_publication_transport_guard(repository, tmp_path):
    from tools.qa.capability_b01 import launch
    code = ("import subprocess,os,pathlib; "
            "subprocess.run(['git','remote','add','origin','https://example.invalid/synthetic'],check=True); "
            "p=subprocess.run(['git','push','origin','HEAD'],capture_output=True,text=True); "
            "assert p.returncode != 0 and 'not allowed' in p.stderr; "
            "assert os.environ['GH_HOST']=='publication-disabled.invalid'")
    result = launch(repository, tmp_path / 'runs/publish', ticket=ticket(),
                    command=[sys.executable, '-c', code])
    assert result['session_exit'] == 0 and result['cleanup'] and not result['passed']
    # The synthetic child's remote config is shared Git metadata, restored here.
    subprocess.run(['git', 'remote', 'remove', 'origin'], cwd=repository, check=True)


@pytest.mark.parametrize('output', ['local.diff', 'reference.json'])
def test_child_cannot_make_launcher_overwrite_an_input(repository, tmp_path, output):
    from tools.qa.capability_b01 import launch
    source = repository / 'jobs/sentinel'
    code = ("import os,sys,pathlib; "
            "os.link(sys.argv[1], pathlib.Path(sys.argv[2])/sys.argv[3])")
    try:
        result = launch(repository, tmp_path / 'runs/alias', ticket=ticket(),
                        command=[sys.executable, '-c', code, str(source), '{run}', output])
        assert result['passed'] is False
    except FileExistsError:
        pass
    assert source.read_bytes() == b'source'
    assert not (tmp_path / 'runs/alias/worktree').exists()
