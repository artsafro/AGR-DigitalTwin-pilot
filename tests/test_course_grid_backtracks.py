"""new-case: zero-area backtracking excursions are not native surface corners."""
import pytest
from tools.materials import course_grid_native as native


def test_native_collinear_excursion_is_reported_not_triangulated_as_surface():
    points=[[113.17613908900599,-4.4947340428829206],
        [112.15949021057821,-4.4947339984230865],
        [112.16412190342311,-4.494733998625638],
        [112.1643546315201,-4.618919085795084],
        [113.17613908900599,-4.618919606879355]]
    result=native.remove_native_backtracks(points)
    assert result['indices']==[0,2,3,4]
    assert result['removed']==[1]
    assert result['signed_area_change_m2']<=1e-12


def test_real_notch_and_forward_conforming_node_are_retained():
    points=[[0,0],[1,0],[2,0],[2,1],[1,1],[1,.99],[.9,.99],[.9,1],[0,1]]
    result=native.remove_native_backtracks(points)
    assert result['indices']==list(range(len(points)))
    assert result['removed']==[]


@pytest.mark.parametrize('points', [[],[[0,0]],[[0,0],[1,0],[float('nan'),1]],
    [[0,0],[1,0],[float('inf'),1]]])
def test_backtrack_cleanup_refuses_invalid_input(points):
    with pytest.raises(ValueError):native.remove_native_backtracks(points)
