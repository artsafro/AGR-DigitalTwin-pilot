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


def test_legacy_patterned_identity_is_shared_not_plain_panel():
    assert REPLAY["tile_binding"]("v007", "PanelVJ30_RAL5015") == ("PanelVJ_RAL5015", 1001)
    assert REPLAY["tile_binding"]("v007", "PanelVJ12_RAL5015") == ("PanelVJ_RAL5015", 1001)
    assert REPLAY["tile_binding"]("v010", "PanelVJ12_RAL5015") == ("PanelVJ12_RAL5015", 1002)


def test_no_joint_witness_is_not_measured():
    with pytest.raises(ValueError, match="not measured"):
        pitch(np.full((64, 64, 3), 180, dtype=np.uint8), RUNS)
