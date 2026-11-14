"""new-case: native pinch closure below the existing 20um storage envelope."""
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import native_piece_cells


def test_native_almost_closed_slit_retains_surface_without_ambiguous_corners():
    # Synthetic affine-plane reduction of the real source-1499 overlay witness.
    xy=[[0.,0.],[2.4,0.],[1.934842539138,.365],[1.9348425392,.008],
        [1.925,.008],[1.925,.363],[1.927,.363],[1.927,.371],
        [1.934842539111,.365000000021],[1.925,.373],[.012,.373],
        [.012,.0003],[0.,.0003],[0.,.373]]
    piece=dict(source=['synthetic',0],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy])
    cells=native_piece_cells(piece)
    assert cells
    assert all(Polygon(c['chart_m']).is_valid for c in cells)
    assert all(len(set(map(tuple,c['xyz'])))==len(c['xyz']) for c in cells)
    assert sum(Polygon(c['chart_m']).area for c in cells)==pytest.approx(Polygon(xy).area,abs=1e-9)
