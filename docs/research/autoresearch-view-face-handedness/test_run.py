from pathlib import Path
import runpy
import subprocess
import sys
from time import monotonic
from types import FunctionType, SimpleNamespace

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


def test_native_subprocess_namespace_preserves_stdout_constant(tmp_path):
    def original(out, n, fixture, reader):
        with (out / 'native.log').open('wb') as log:
            subprocess.run([sys.executable, '-c', 'print("native")'], stdout=log,
                           stderr=subprocess.STDOUT, check=True, timeout=15)
        return [], None

    scorer = SimpleNamespace(face_score=None, decide=None, majority=None)
    measure = FunctionType(original.__code__, {**globals(), 'S': scorer})
    paired = runpy.run_path(str(RUN))['paired_measure']
    assert paired({'measure': measure}, tmp_path, 1, {}, {}, monotonic() + 20) == ([], [])
    assert (tmp_path / 'native.log').read_text().strip() == 'native'
    assert measure.__globals__['subprocess'] is subprocess
