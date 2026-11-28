"""H168 fusion contract witnesses independent of the native runtime."""

from pathlib import Path
from runpy import run_path

import numpy as np
import pytest

probe = run_path(str(Path(__file__).with_name('run.py')))
compact, fuse, inject, verdict = [probe[n] for n in ('compact', 'fuse', 'inject', 'verdict')]


@pytest.mark.parametrize(('glass', 'finish', 'answer', 'route'), [
    (None, None, None, 'neither'), ('W01', None, 'W01', 'glass_only'),
    (None, 'W02', 'W02', 'finish_only'), ('W01', 'W01', 'W01', 'agree'),
    ('W01', 'W02', None, 'conflict'),  # even if both walls share an azimuth
])
def test_fusion(glass, finish, answer, route):
    assert fuse(glass, finish) == (answer, route)


def test_changed_channel_counts_distinguish_empty_and_symmetric():
    glass = np.array([[0., 1., 0.]])
    finish = np.array([[12, 0, 0], [44, 0, 44]])
    _, _, changed = inject('mirror', glass, finish)
    assert changed == {'glass': 0, 'finish': 2}
    _, _, changed = inject('blank', glass, finish)
    assert changed == {'glass': 1, 'finish': 3}
    assert inject('clean', glass, finish)[2] == {'glass': 0, 'finish': 0}


def test_compaction_reserves_zero_even_if_no_misses():
    assert compact(np.array([[27, 99, 27]])).tolist() == [[1, 2, 1]]
    assert compact(np.array([[7, 0, 9]])).tolist() == [[1, 0, 2]]


def test_mirror_cannot_hide_behind_clean_recovery():
    rows = []
    for i, name in enumerate(('p18 I-A', 'p19 A-I', 'p19 10-1', 'other')):
        rows.append(dict(name=name, kind='full', clean=dict(a='W08' if not i else None, f='W08',
                        a_outcome='correct' if not i else 'abstain', f_outcome='correct',
                        route='glass_only' if not i else 'finish_only'), blank=dict(f=None),
                        mirror=dict(f_outcome='abstain', changed={'glass': 0, 'finish': 2})))
    assert all(verdict(rows).values())
    rows[2]['mirror']['f_outcome'] = 'wrong'
    assert not verdict(rows)['mirror_safety']
    rows[2]['mirror']['changed']['finish'] = 0
    assert verdict(rows)['mirror_safety']
    assert not verdict(rows)['negative_witness']
