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
