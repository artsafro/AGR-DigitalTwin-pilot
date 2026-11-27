"""Unit checks for the #145 research harness (pure functions; no Blender, no PDF)."""
import json
import runpy
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.argv = ['run.py']
RUN = runpy.run_path(str(HERE / 'run.py'))
POSTHOC = runpy.run_path(str(HERE / 'posthoc.py'))


def test_cases_full_view_has_full_mirror_and_nine_crops():
    kinds = [k for k, _, _ in RUN['cases']('full', 100, {'fractions': [0.25, 0.4, 0.6], 'positions': [0.0, 0.5, 1.0]})]
    assert kinds[:2] == ['full', 'mirror'] and len(kinds) == 11


def test_cases_fragment_is_single_real_case():
    assert list(RUN['cases']('fragment', 40, {'fractions': [0.5], 'positions': [0.0]})) == [('fragment', 0, 40)]


def test_raster_view_top_row_is_highest_segment():
    img = RUN['raster_view'](np.array([[0.0, 0.0, 1.0, 0.0], [0.0, 2.0, 1.0, 2.0]]), 0.1)
    assert img.shape == (21, 11) and img[0].all() and img[-1].all() and not img[10].any()


def test_posthoc_normalisation_removes_a_dense_attractor(tmp_path, capsys):
    rows = []
    for view, gt in (('a', 270), ('b', 90), ('c', 180)):
        scores = {'0': 0.75, '90': 0.40, '180': 0.40, '270': 0.40}
        scores[str(gt)] = 0.70  # the true face is below the attractor in raw score
        rows.append(dict(view=view, case='full', gt_az=gt, scores=scores))
    path = tmp_path / 'r.json'
    path.write_text(json.dumps({'rows': rows}), encoding='utf-8')
    POSTHOC['main'](str(path))
    out = capsys.readouterr().out
    assert '"full.correct", 3' in out and 'wrong' not in out
