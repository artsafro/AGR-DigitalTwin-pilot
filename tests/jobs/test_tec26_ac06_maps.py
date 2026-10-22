"""new-case: Synthetic probes for AC06 shared-profile recolouring; no real source quantities."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH = Path(__file__).resolve().parents[2] / 'jobs/TEC26-OKS/AC06/make_maps.py'


def module():
    s = importlib.util.spec_from_file_location('ac06_maps', PATH)
    assert s is not None and s.loader is not None
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def test_same_profile_recoloured_and_vertical_only():
    src = np.full((20, 600, 3), [34, 113, 179], dtype=np.uint8)
    src[:, 266:274] = [8, 25, 39]
    blue = module().sandwich(src, [34, 113, 179], size=20, period=10, joint=[266, 274])
    grey = module().sandwich(src, [208, 208, 208], size=20, period=10, joint=[266, 274])
    assert np.array_equal(blue[0], blue[19])
    assert np.array_equal(grey[0], grey[19])
    assert np.array_equal(blue.mean(2) < 50, grey.mean(2) < 100)
    assert np.any(np.all(grey == 208, axis=2))


def test_crisp_joint_contrast_survives_npm_scale():
    from PIL import Image
    src=np.full((1000,600,3),[34,113,179],np.uint8)
    src[:,266:274]=[8,25,39]
    for rgb,minimum in [([34,113,179],81.7724),([208,208,208],168.0)]:
        tile=module().sandwich(src,rgb,1000,200,[266,274],joint_width=32)
        img=np.asarray(Image.fromarray(tile).resize((100,100),Image.Resampling.LANCZOS))
        lum=img@np.array([.2126,.7152,.0722])
        assert np.median(lum)-np.min(lum)>=minimum


@pytest.mark.parametrize('period', [0, -1, float('nan'), float('inf'), 8])
def test_invalid_or_all_joint_period_refused(period):
    with pytest.raises(ValueError):
        module().sandwich(np.zeros((20, 600, 3), np.uint8), [34, 113, 179], size=20, period=period, joint=[266, 274])
