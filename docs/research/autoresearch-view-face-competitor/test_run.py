import runpy
from pathlib import Path

require_competitor = runpy.run_path(str(Path(__file__).with_name('run.py')))['require_competitor']


def test_singleton_is_not_a_competitor():
    assert require_competitor('W19', ['W19']) is None
    assert require_competitor('W19', ['W19', 'W19']) is None


def test_real_competitor_preserves_answer():
    eligible = ['W01', 'W19']
    assert require_competitor('W19', eligible) == 'W19'
    assert require_competitor('W19', eligible[::-1]) == 'W19'
    assert eligible == ['W01', 'W19']


def test_preexisting_abstention():
    assert require_competitor(None, []) is None
    assert require_competitor(None, ['W01', 'W19']) is None
