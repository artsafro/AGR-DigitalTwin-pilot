"""Focused witnesses for the frozen #154 corroboration treatment."""
import runpy
from pathlib import Path

import numpy as np

RUN = runpy.run_path(str(Path(__file__).with_name('run.py')))
agree, profile, roof_pick = (RUN[name] for name in ('agree', 'profile', 'roof_pick'))


def test_asymmetric_profile():
    v = np.repeat([0., 0., 3., 5., 5., 7., 7., 7.], 25)
    pick, costs = roof_pick(v, {90: v, 270: v[::-1], 180: v[:5]})
    assert pick == 90 and costs[90] == 0 and costs[180] is None


def test_profile_abstains():
    raster = np.zeros((30, 5), dtype=bool)
    raster[1, 1] = raster[5, 3] = raster[-1, 4] = True
    v = profile(raster)
    np.testing.assert_equal(v, [0., np.nan, .4])
    assert roof_pick(v, {0: v, 180: v})[0] is None
    assert roof_pick(profile(np.zeros_like(raster)), {0: v})[0] is None


def test_agreement():
    assert agree(0, 0) == 0
    assert agree(90, 90) == 90
    for mark, roof in [(90, 270), (None, 90), (90, None), (None, None)]:
        assert agree(mark, roof) is None
