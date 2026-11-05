"""Identity-preserving under-band spacing witnesses for v015 diagonal repair."""
import numpy as np
import pytest
from dt_ai.geometry import ground_cake as gc


def plates(gap):
    v=np.array([(0,0,0),(2,0,0),(0,2,0),(0,0,gap),(2,0,gap),(0,2,gap)],float)
    f=np.array([(0,1,2),(3,4,5)])
    return gc.Mesh(v,f,['TileLight','Mulch'],np.array([0,1]),np.zeros((2,3,2)),4.)


def test_under_band_samples_name_every_original_face_and_corner():
    m=plates(.004)
    r=gc.measure_stack_gaps(m,.006,include_under_band_samples=True)
    rows=r['normal_gap_under_band_samples']
    assert {(s['kind'],s['upper_face'],s['lower_face'],s['vertex']) for s in rows}=={
        ('centroid',1,0,None),('corner',1,0,3),('corner',1,0,4),('corner',1,0,5)}
    assert all(s['gap_mm']==pytest.approx(4.) for s in rows)
    assert 'normal_gap_under_band_samples' not in gc.measure_stack_gaps(m,.006)
    np.testing.assert_array_equal(m.verts,plates(.004).verts)


@pytest.mark.parametrize('gap',[.006,.025])
def test_clean_and_upper_band_cases_do_not_invent_under_band_samples(gap):
    r=gc.measure_stack_gaps(plates(gap),.006,include_under_band_samples=True)
    assert r['normal_gap_under_band_samples']==[]
    if gap>.02:assert len(r['normal_gap_over_band_samples'])==4


@pytest.mark.parametrize('bad',['empty','nan','flag'])
def test_detailed_gap_samples_refuse_unmeasurable_input(bad):
    m=plates(.006);flag=True
    if bad=='empty':m.faces=np.empty((0,3),int);m.level=np.array([],int);m.slot=[];m.uv=np.zeros((0,3,2))
    elif bad=='nan':m.verts[0,0]=np.nan
    else:flag='yes'
    with pytest.raises(ValueError):gc.measure_stack_gaps(m,.006,include_under_band_samples=flag)
