from pathlib import Path
import runpy

import pytest


RUN = Path(__file__).with_name('run.py')


@pytest.mark.parametrize(('pick', 'score', 'reflected', 'want'), [
    (270, .440286675, .43, None),
    (0, .555504567, .20, 0),
    (0, .4, .3, 0),
    (0, .399999999, .3, None),
    (None, None, None, None),
])
def test_veto_never_promotes_or_weakens_d(pick, score, reflected, want):
    veto = runpy.run_path(str(RUN))['veto']
    assert veto(pick, score, reflected) == want


def test_base_parity_checks_scores_not_only_verdict():
    parity = runpy.run_path(str(RUN))['check_baseline']
    row = {'view': 'a', 'case': 'full', 'scores': {'0': .35}, 'pick': 0}
    parity([row], [{**row, 'C': 'correct', 'E': 'correct'}])
    with pytest.raises(ValueError, match='row 0'):
        parity([row], [{**row, 'scores': {'0': .34}}])
