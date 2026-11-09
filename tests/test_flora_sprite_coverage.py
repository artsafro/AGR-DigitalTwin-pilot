"""Synthetic geometry/opacity probes for #369; no production assets."""
import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools/flora'))
from sprite_coverage import coverage, sprite_cells, island_role, uv_components


def test_vpm_coverage_is_bbox_not_opaque_density():
    alpha=np.zeros((100,100),bool); alpha[10,10]=alpha[89,89]=True
    island=np.zeros_like(alpha); island[10:90,10:90]=True
    r=coverage(island,alpha,'VPM',(10,10,90,90))
    assert r['score']==1 and r['pass'] and r['opaque_density']<.001


@pytest.mark.parametrize('width,passed',[(79,False),(80,True),(95,True),(96,True)])
def test_vpm_boundaries(width,passed):
    a=np.ones((100,100),bool); m=np.zeros_like(a);m[:,:width]=True
    assert coverage(m,a,'VPM',(0,0,100,100))['pass'] is passed


def test_vpm_neighbour_contamination_is_not_tolerated_above_95():
    a=np.zeros((100,100),bool); a[10:50,10:50]=True;a[60:80,60:80]=True
    assert not coverage(np.ones_like(a),a,'VPM',(10,10,50,50))['pass']


def test_npm_bbox_margin_and_clipping():
    a=np.zeros((100,100),bool);a[5:95,5:95]=True
    assert coverage(np.ones_like(a),a,'NPM',(5,5,95,95))['score']==.81
    assert coverage(np.ones_like(a),a,'NPM',(5,5,95,95))['pass']
    m=np.ones_like(a);m[:,:8]=False
    assert not coverage(m,a,'NPM',(5,5,95,95))['pass']


@pytest.mark.parametrize('profile',['', 'X', None])
def test_unsupported_profile_fails(profile):
    with pytest.raises(ValueError):coverage(np.ones((2,2),bool),np.ones((2,2),bool),profile,(0,0,2,2))


def test_empty_and_nonfinite_fail_closed():
    for a in [np.zeros((2,2),bool), np.array([[np.nan,1],[1,1]])]:
        with pytest.raises(ValueError):coverage(np.ones((2,2),bool),a,'NPM',(0,0,2,2))
    with pytest.raises(ValueError):coverage(np.ones((2,2),bool),np.ones((2,2),bool),'VPM',(0,0,0,2))


def test_sprite_cells_split_only_wide_empty_gutters():
    a=np.zeros((100,100),bool);a[5:45,5:40]=True;a[55:95,5:40]=True;a[:,70:95]=True
    assert sorted(sprite_cells(a))==[(5,5,40,45),(5,55,40,95),(70,0,95,100)]


def test_roles_from_geometry_not_profile_name():
    v=np.array([[0,0,0],[1,0,0],[1,0,1],[0,0,1]],float)
    assert island_role(v,1,'NPM')[0]=='star_plane'
    assert island_role(v,10,'VPM')[0]=='foliage'
    assert island_role(np.zeros((4,3)),1,'VPM')[0]=='unknown'


def test_uv_components_do_not_merge_disconnected_stacked_cards():
    assert uv_components([[0,1,2],[0,2,3],[4,5,6]],7)==[[0,1],[2]]
    with pytest.raises(ValueError):uv_components([[0,1,9]],3)
