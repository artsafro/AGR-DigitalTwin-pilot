"""new-case: local PR evidence and closed-ticket capability replay contracts."""
import json
from pathlib import Path

from twinqa.evals.pr_graders import TRACE_FIELDS, pr_agent_trace, pr_numeric_literals


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
