"""Pure-Python diagnosis guards and measurement regression probes (#369)."""
import importlib.util
import math
from pathlib import Path
import pytest

SPEC = importlib.util.spec_from_file_location('flora_diag', Path(__file__).parents[1]/'tools/flora/diagnose_texture.py')
diag = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diag)


@pytest.mark.parametrize('u,v,expected', [(0,0,(0,99)),(1,1,(99,0)),(.25,.75,(25,25))])
def test_uv_image_origin(u,v,expected):
    assert diag.uv_pixel((u,v),100)==expected


@pytest.mark.parametrize('uv', [(),(0,), (math.nan,0),(0,math.inf),(-.01,0),(1.01,0)])
def test_uv_invalid_fail_closed(uv):
    with pytest.raises(ValueError): diag.uv_pixel(uv,100)


def test_bitmap_basename_not_map_name(tmp_path):
    image=tmp_path/'Maps_Bereza_01.png'; image.write_bytes(b'original')
    assert diag.resolve_bitmap(r'G:\old\Maps_Bereza_01.png',tmp_path)==image
    with pytest.raises(ValueError,match='absent'):diag.resolve_bitmap('absent.png',tmp_path)


def test_no_input_output_aliases(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'original')
    alias=tmp_path/'alias';alias.hardlink_to(source)
    with pytest.raises(ValueError):diag.guard_outputs([source],[alias])
    assert source.read_bytes()==b'original'
    with pytest.raises(ValueError):diag.guard_outputs([source],[source])
    with pytest.raises(ValueError):diag.guard_outputs([source],[tmp_path/'new',tmp_path/'new'])
    diag.guard_outputs([source],[tmp_path/'fresh'])


def test_measure_requires_complete_mapping():
    source={'oak':{'uv_sha256':'abc','triangles':10}}
    ours={'oak':{'uv_sha256':'abc','triangles':10}}
    assert diag.compare_inventory(source,ours)=={'total':1,'uv_identical':['oak'],'uv_changed':[]}
    with pytest.raises(ValueError,match='oak'):diag.compare_inventory({},ours)
    with pytest.raises(ValueError):diag.compare_inventory({}, {})


def test_generated_accounting():
    source={str(i):{'uv_sha256':str(i),'triangles':i+1} for i in range(99)}
    ours={k:dict(v) for k,v in source.items()}
    for i in range(0,99,3):ours[str(i)]['uv_sha256']='changed'
    result=diag.compare_inventory(source,ours)
    assert len(result['uv_identical'])==66
    assert len(result['uv_changed'])==33
    assert set(result['uv_identical']+result['uv_changed'])==set(source)
