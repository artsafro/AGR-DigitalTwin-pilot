import runpy
from pathlib import Path

import numpy as np
import pytest

REPLAY = runpy.run_path(str(Path(__file__).with_name("replay.py")))
pitch = REPLAY["pitch"]
RUNS = REPLAY["git_source"](REPLAY["BASE"], REPLAY["JOINT"])["runs"]


def test_complete_runs_only_and_brightness_parity():
    tile = np.full((64, 64, 3), 180, dtype=np.uint8)
    tile[:, :2] = tile[:, -2:] = 20
    tile[:, 5::10] = 20
    assert pitch(tile, RUNS) == (10.0, [6, 6, 6])
    assert pitch(tile + 8, RUNS) == pitch(tile, RUNS)


def test_v007_shared_patterned_region_binds_both_targets():
    assert REPLAY["region_binding"]("v007", "PanelVJ30_RAL5015") == "PanelVJ_RAL5015"
    assert REPLAY["region_binding"]("v007", "PanelVJ12_RAL5015") == "PanelVJ_RAL5015"
    assert REPLAY["region_binding"]("v010", "PanelVJ12_RAL5015") == "PanelVJ12_RAL5015"


def test_no_joint_region_is_not_measured():
    with pytest.raises(ValueError, match="not measured"):
        pitch(np.full((397, 397, 3), 180, dtype=np.uint8), RUNS)


def test_incomplete_series_is_inconclusive_not_refuted():
    row = {"E73": {"clean": 0.0}}
    rounds = [{"rows": {"v007": row, "v010": row}, "witnesses_ok": True}]
    assert REPLAY["verdict"]("budget_stop", rounds)[0] == "inconclusive"


def test_half_pitch_witness_on_397_region_halves_period():
    region = np.full((397, 397, 3), 180, dtype=np.uint8)
    region[:, 9::19] = 20
    assert pitch(region, RUNS)[0] == 19.0
    assert abs(pitch(REPLAY["half_pitch"](region), RUNS)[0] / 19.0 - 0.5) < 0.03
