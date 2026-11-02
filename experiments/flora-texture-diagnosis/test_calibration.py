"""Calibration is a bound, not an approved semantic score."""
import importlib.util
from pathlib import Path
import pytest
from PIL import Image

SPEC=importlib.util.spec_from_file_location('calibrate_uv_area',Path(__file__).with_name('calibrate_uv_area.py'))
cal=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(cal)


def test_uv_connectivity_preserves_stacked_separate_cards():
    assert cal.components([[0,1,2],[0,2,3],[4,5,6],[4,6,7]],8)==[[0,1],[2,3]]


@pytest.mark.parametrize('face',[[-1,1,2],[0,1,3],[0,1],[0,float('nan'),2]])
def test_bad_uv_topology_fails(face):
    with pytest.raises(ValueError):cal.components([face],3)


def test_background_and_128_boundary_are_explicit(tmp_path):
    image=Image.new('RGBA',(2,2));image.putdata([(0,200,0,a) for a in (0,127,128,255)])
    path=tmp_path/'original.png';image.save(path)
    record={'uv':[[0,0],[1,0],[1,1],[0,1]],'uvfaces':[[0,1,2],[0,2,3]]}
    score=cal.measure(record,path,0,2)
    assert score['uv_area_pixels']==4 and score['opaque_pixels']==2
    assert score['matching_class_upper_bound']==.5
    assert not score['acceptance_metric_approved']
    assert not score['semantic_roles_classified']
    with pytest.raises(ValueError):cal.measure(record,path,5,2)
