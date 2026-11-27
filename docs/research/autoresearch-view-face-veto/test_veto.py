"""Scorer-shape controls for the #147 disagreement veto (no native inputs needed).

new-case: docs/research/autoresearch-view-face-veto/test_veto.py - #147 veto unit controls
"""
from pathlib import Path
import runpy

API = runpy.run_path(str(Path(__file__).with_name('run.py')))
veto, verdict = API['veto'], API['verdict']


def test_veto_answers_only_on_agreement():
    assert veto(0, 0) == '0'
    assert veto({'answer': 270}, '270') == '270'
    assert veto(0, 90) is None
    assert veto(None, 90) is None
    assert veto({'answer': None}, None) is None


def test_verdict_labels_unchanged_mirror_not_exercised():
    assert verdict(None, '0', 'mirror', 0) == 'not_exercised'
    assert verdict('0', 0, 'full', None) == 'correct'
    assert verdict('90', '0', 'crop', None) == 'wrong'
    assert verdict(None, '0', 'crop', None) == 'abstain'
