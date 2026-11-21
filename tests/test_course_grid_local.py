"""new-case: source-local barycentric storage before native world readback."""
import pytest
from tools.materials.course_grid_native import interpolate_source_chart


def test_source_local_interpolation_preserves_corners_and_warped_fan():
    chart=[[0,0],[2,0],[2,1],[0,1]]
    xyz=[[1,2,3],[3,2,3],[3,2.001,4],[1,2,4]]
    got=interpolate_source_chart(chart+[[1,.25],[1,.75]],chart,xyz)
    assert got[:4]==xyz
    assert got[4]==pytest.approx([2,2.00025,3.25])
    assert got[5]==pytest.approx([2,2.0005,3.75])


@pytest.mark.parametrize('point', [[float('nan'),0],[float('inf'),0],[3,1]])
def test_bad_or_outside_source_local_point_refuses(point):
    with pytest.raises(ValueError):
        interpolate_source_chart([point],[[0,0],[1,0],[0,1]],[[0,0,0],[1,0,0],[0,0,1]])
