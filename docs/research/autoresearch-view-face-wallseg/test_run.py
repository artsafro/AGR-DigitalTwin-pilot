import importlib.util
from pathlib import Path

import numpy as np

SPEC = importlib.util.spec_from_file_location('wallseg163', Path(__file__).with_name('run.py'))
assert SPEC is not None and SPEC.loader is not None
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)


class Api:
    @staticmethod
    def best_offset(v, m, p):
        a = v.ravel()[: m.size] - v.mean(); b = m.ravel()[: v.size] - m.mean()
        d = np.sqrt((a * a).sum() * (b * b).sum())
        return (float((a * b).sum() / d) if d else 0.0, 0)


PRM = dict(min_overlap=0.8, fit_tol=0.10, tau=0.30, delta=0.10)


def test_block_shuffle_keeps_content_and_changes_order():
    g = np.tile(np.arange(40, dtype=float), (3, 1))
    s = RUN.block_shuffle(g, 0.25)
    assert s.shape == g.shape and s.sum() == g.sum()
    assert not np.array_equal(s, g)
    np.testing.assert_array_equal(RUN.block_shuffle(g, 0.25), s)  # seeded


def test_view_wider_than_every_wall_abstains():
    g = np.eye(4)
    walls = [dict(id='W00', render_w_m=5.0)]
    d = RUN.decide(10.0, g, walls, {'W00': g}, PRM, Api)
    assert d['answer'] is None and d['eligible'] == []


def test_single_eligible_wall_needs_score_and_margin_vs_null():
    g = np.eye(4)
    walls = [dict(id='W00', render_w_m=5.0), dict(id='W01', render_w_m=1.0)]
    d = RUN.decide(5.0, g, walls, {'W00': g, 'W01': g}, PRM, Api)
    assert d['eligible'] == ['W00'] and d['answer'] == 'W00'
    d = RUN.decide(5.0, np.zeros((4, 4)), walls, {'W00': g, 'W01': g}, PRM, Api)
    assert d['answer'] is None


def test_two_equal_eligible_walls_abstain():
    g = np.eye(4)
    walls = [dict(id='W00', render_w_m=5.0), dict(id='W01', render_w_m=5.0)]
    d = RUN.decide(4.0, g, walls, {'W00': g, 'W01': g.copy()}, PRM, Api)
    assert d['answer'] is None and d['margin'] == 0.0


def test_outcome_labels():
    assert RUN.outcome(None, ['W19'], 'x') == 'abstain'
    assert RUN.outcome('W19', ['W19'], 'x') == 'correct'
    assert RUN.outcome('W17', None, 'x') == 'wrong'
    assert RUN.outcome('W17', None, 'p15 K-A') == 'diagnostic'
