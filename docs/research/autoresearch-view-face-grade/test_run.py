import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location('grade_trial', Path(__file__).with_name('run.py'))
assert spec is not None and spec.loader is not None
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


def test_native_misses_and_below_datum_do_not_expand_extent():
    labels = np.array([[0, 0, 0], [0, 7, 0], [4, 0, 0]])
    assert trial.extent(labels > 0, 1.0) == (2.0, 2.0)
    hit, counts = trial.above(labels, 2.0, 1.0, 0.0)
    assert trial.extent(hit, 1.0) == (1.0, 1.0)
    assert counts == {'below_hits': 1, 'injected_below': 2, 'changed_above': 0}
    assert trial.extent(labels * 0 > 0, 1.0) is None


def test_centre_on_datum_is_kept():
    hit, _ = trial.above(np.array([[1], [1]]), 0.5, 1.0, 0.0)
    assert hit.tolist() == [[True], [False]]


def test_size_only_cannot_choose_two_near_faces_or_assign_fragments():
    models = {0: (10.0, 10.0), 180: (11.8, 10.0), 90: (18.0, 10.0)}
    assert trial.propose((10.0, 10.0), models, True) == (None, [0], [0, 180])
    assert trial.propose((18.0, 10.0), models, True) == (90, [90], [90])
    assert trial.propose((18.0, 10.0), models, False) == (None, [90], [90])
