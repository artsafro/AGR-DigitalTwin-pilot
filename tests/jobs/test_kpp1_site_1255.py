"""new-case: approved approximate KPP1 placement, not survey-grade acceptance."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'jobs/KPP1/site-1255/place_package.py'


def load():
    assert SCRIPT.is_file(), 'KPP1 R1 placement and GeoJSON producer missing'
    spec = importlib.util.spec_from_file_location('kpp1_site1255', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_approved_transform_keeps_vpm_local_and_npm_absolute():
    m = load()
    fit = json.loads((SCRIPT.parent / 'fit-npm-r1-v002.json').read_text())
    point = [11., -3., 8.65]
    local = m.transform_point(point, fit, 'vpm')
    absolute = m.transform_point(point, fit, 'npm')
    assert absolute == pytest.approx([local[0] + 8056.143933445407,
                                     local[1] - 9581.26989822931, 179.70])
    assert m.transform_point([0., 0., 0.], fit, 'vpm') == [0., 0., 0.]
    assert local[0] > 0 and local[1] < 0  # no 180-degree alternative
    assert fit['fit_ok'] is False and fit['unique'] is False
