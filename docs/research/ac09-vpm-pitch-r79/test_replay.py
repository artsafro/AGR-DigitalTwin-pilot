"""Synthetic unit tests for the #79 replay logic (no Drive access; all data synthetic)."""
import importlib.util
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("r79", Path(__file__).with_name("replay.py"))
assert spec is not None and spec.loader is not None
r79 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r79)


def runs(mask):
    out, start = [], None
    for i, v in enumerate(mask):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i))
            start = None
    return out


def pitch(tile, runs_fn):
    lum = tile[tile.shape[0] // 2, :, :3].astype(int).sum(axis=1)
    centres = [(a + b - 1) / 2 for a, b in runs_fn(lum < 0.8 * np.median(lum)) if a > 0 and b < len(lum)]
    if len(centres) < 3:
        raise ValueError("too few runs")
    return float(np.median(np.diff(centres))), [len(centres)]


def synthetic_tile(period, size=256):
    tile = np.full((size, size, 3), 150, np.uint8)
    tile[:, period // 2::period] = 20
    return tile


def test_score_tile_matches_period_and_witnesses():
    row = r79.score_tile(synthetic_tile(16), 16.0, pitch, runs)
    assert row["E"] == 0 and not row["flagged"]
    assert row["half_pitch"]["in_bound"] and row["brightness_plus8"]["in_bound"]


def test_score_tile_flags_wrong_period():
    row = r79.score_tile(synthetic_tile(48), 16.0, pitch, runs)
    assert row["flagged"] and row["E"] == 2.0


def _round(e, flagged=(), fires=True, measured=4):
    return {"control": {"fires": fires, "parity_vs_r78": True},
            "ac09": {"E79": e, "flagged": list(flagged), "measured_udims": list(range(measured)), "rows": []}}


def test_verdict_rules():
    assert r79.verdict("complete", [_round(0.002)] * 3) == "confirmed"
    assert r79.verdict("complete", [_round(0.8, flagged=[1001])] * 3) == "refuted"
    assert r79.verdict("complete", [_round(0.002, fires=False)] * 3) == "inconclusive"
    assert r79.verdict("budget_stop", [_round(0.002)]) == "inconclusive"
    assert r79.verdict("complete", [_round(0.002, measured=2)] * 3) == "inconclusive"
