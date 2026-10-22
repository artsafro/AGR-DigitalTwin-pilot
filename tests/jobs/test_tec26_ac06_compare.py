"""new-case: pixel-count/contrast regression for source-bound AC06 comparisons."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

PATH=Path(__file__).resolve().parents[2]/'jobs/TEC26-OKS/AC06/compare_ac06.py'


def load():
    s=importlib.util.spec_from_file_location('ac06_compare',PATH)
    assert s and s.loader
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m


def test_counter_measures_ribs_and_does_not_invent_a_missing_line():
    a=np.full((40,100,3),[34,113,179],np.uint8)
    for x in range(10,100,10):a[:,x:x+2]=[0,0,32]
    assert load().count_blue(a,50)['ribs']==10
    a[:,50:52]=[34,113,179]
    assert load().count_blue(a,50)['ribs']==9


def test_crop_outside_render_is_white_not_a_fake_black_border():
    from PIL import Image
    out=load().white_crop(Image.new('RGB',(2,2),'red'),(-1,-1,3,3))
    assert out.size==(4,4)
    assert out.getpixel((0,0))==(255,255,255)
    assert out.getpixel((1,1))==(255,0,0)
    assert out.getpixel((3,3))==(255,255,255)


@pytest.mark.parametrize('a',[np.empty((0,0,3)),np.full((10,10,3),np.nan),np.zeros((10,10,4))])
def test_empty_nonfinite_unsupported_pixels_refused(a):
    with pytest.raises(ValueError):load().count_blue(a,50)
