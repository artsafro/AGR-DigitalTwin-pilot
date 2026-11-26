"""Regressions for the #105 storey-band replay decision rules (review r1 P1.1, P1.2)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'docs/research/trainer_storey_band_r105'


def _load():
    spec = importlib.util.spec_from_file_location('replay_r105', DIR / 'replay.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


replay = _load()


def _receipt_results():
    return json.loads((DIR / 'receipt.json').read_text(encoding='utf-8'))['results']


def test_stored_receipt_stays_refuted():
    assert replay.decide(_receipt_results(), 'complete') == 'refuted'


def test_failed_63a_control_makes_refuted_inconclusive():
    results = _receipt_results()
    assert [r['63B']['status'] for r in results] == ['fail'] * 3
    results[0]['63A'] = results[0]['63A'] | {'order_parity': False, 'status': 'inconclusive'}
    assert replay.decide(results, 'complete') == 'inconclusive'


@pytest.mark.parametrize('stop', ['budget stop', 'incomplete pair', 'calibration failed'])
def test_incomplete_series_is_inconclusive(stop):
    assert replay.decide(_receipt_results(), stop) == 'inconclusive'


@pytest.mark.parametrize('dev, ok', [(0.5267, True), (0.5, True), (0.45, False), (None, False),
                                     ('0.6', False), (float('nan'), False), (True, False)])
def test_positive_bound(dev, ok):
    assert replay.positive_bound_ok({'max_corner_dev_m': dev}) is ok


def test_positive_bound_missing_native():
    assert replay.positive_bound_ok(None) is False
    assert replay.positive_bound_ok({}) is False


def _tower_rows():
    rows, n = [], 0
    for k in range(4):
        z = 3.0 * k
        for i in range(replay.MIN_ROWS):
            rows.append((n, 'facade', [float(i), 0.0, z], [i + 0.5, 1.0, z + 3.0]))
            n += 1
    return rows


def _key_from_selection(rows, box, xmax_shift):
    sel = replay.select(replay.contained(rows, box))
    lo, hi = sel['bounds_m']
    return replay.as_readback({'bounds_m': [lo, [hi[0] + xmax_shift, hi[1], hi[2]]]})


BOX = {'min': [-10.0, -10.0, -10.0], 'max': [50.0, 10.0, 50.0]}


def test_positive_witness_control_passes_on_exact_key():
    rows = _tower_rows()
    key = _key_from_selection(rows, BOX, 0.0)
    out = replay.tower(rows, BOX, key, key)
    assert out['injected']['positive_native']['max_corner_dev_m'] == pytest.approx(0.5)
    assert out['injected']['positive_xy_pass'] is True
    assert out['status'] == 'pass'


def test_positive_witness_below_bound_is_inconclusive():
    """Reviewer input: key Xmax = selection Xmax + 0.05 m -> witness M105 0.45 m < 0.5 m."""
    rows = _tower_rows()
    key = _key_from_selection(rows, BOX, 0.05)
    out = replay.tower(rows, BOX, key, key)
    assert out['native']['max_corner_dev_m'] == pytest.approx(0.05)
    assert out['injected']['positive_native']['max_corner_dev_m'] == pytest.approx(0.45)
    assert out['injected']['positive_xy_pass'] is False
    assert out['status'] == 'inconclusive'
