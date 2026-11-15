"""new-case: #1397 non-NPM UDIM owner routing and old-formula parity.

Synthetic UVs only; no scene or delivery acceptance is inferred.
"""
import ast
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest

from tools.architecture import duplicate_guard as guard
from tools.architecture import mini_yaml

ROOT = Path(__file__).resolve().parents[1]
LIVE = [
    "src/dt_ai/geometry/ground_cake.py",
    "tools/blender/ground_json_to_fbx.py",
    "tools/flora/build_flora_star.py",
    "tools/methods/methods_metrics.py",
    "tools/methods/windows/windows_variants.py",
    "tools/experiments/dreamsim_ac08.py",
]


@pytest.mark.parametrize("rel", LIVE)
def test_live_copy_routes_to_owner(rel):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert [f for f in guard.scan_text(text, rel) if f.rule == "udim-tile"] == []
    assert "udimtile_core.py" in text
    allowed = guard.allowlist(mini_yaml.load(ROOT / "docs/architecture/contexts.yaml"))
    assert not [k for k in allowed if k[1] == rel]


def test_source_raw_tile_exception_is_explicit():
    text = (ROOT / "tools/source/measure_spec_blender.py").read_text(encoding="utf-8")
    assert "not a delivery UDIM" in text
    contexts = (ROOT / "docs/architecture/contexts.yaml").read_text(encoding="utf-8")
    assert "raw tile" in contexts
