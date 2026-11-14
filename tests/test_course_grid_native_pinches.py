"""new-case: native pinch closure below the existing 20um storage envelope."""
import pytest
from shapely.geometry import Polygon
from tools.materials.course_grid_cut import native_piece_cells


def test_native_tessellation_reports_and_omits_sub_overlay_collinear_cell():
    xy=[[106.779152441312,-4.872884263696],[106.768364321559,-4.872884267569],
        [109.176082668445,-4.872883403301],[108.702272247068,-4.865310649323],
        [108.694454686826,-4.865310651355],[108.694454489249,-4.757958233974],
        [108.702272049491,-4.757958231942],[109.176082668445,-4.74870070219],
        [106.779152212759,-4.748701087886]]
    piece=dict(source=['synthetic',1],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy])
    cells=native_piece_cells(piece)
    assert all(Polygon(c['chart_m']).area>1e-12 for c in cells)
    assert sum(Polygon(c['chart_m']).area for c in cells)==pytest.approx(Polygon(xy).area,abs=1e-10)
    assert any(c.get('native_collapsed_cells') for c in cells)


def test_native_almost_closed_slit_retains_surface_without_ambiguous_corners():
    # Synthetic affine-plane reduction of the real source-1499 overlay witness.
    xy=[[112.588943724691,-4.872886696458],[114.979522951001,-4.872887083888],
        [114.523786263829,-4.507899927305],[114.52378633566,-4.86476729482],
        [114.514014403442,-4.864767294959],[114.514014394013,-4.817922546574],
        [114.51206000757,-4.817922546602],[114.512060006784,-4.81401881757],
        [114.514014393227,-4.814018817542],[114.514014360619,-4.652014062711],
        [114.512059974175,-4.652014062739],[114.512059973389,-4.648110333707],
        [114.514014359833,-4.648110333679],[114.514014331939,-4.50952795304],
        [114.515968718382,-4.509527953012],[114.515968716811,-4.501720494948],
        [114.523786263802,-4.507899927284],[114.513917905127,-4.499996626377],
        [112.600670001776,-4.499996226497],[112.600670076769,-4.87257478023],
        [112.588943758108,-4.872574780397],[112.588943724691,-4.499996224046]]
    piece=dict(source=['synthetic',0],joint=False,chart_m=xy,xyz=[[x,y,0.] for x,y in xy])
    cells=native_piece_cells(piece)
    assert cells
    assert all(Polygon(c['chart_m']).is_valid for c in cells)
    assert all(len(set(map(tuple,c['xyz'])))==len(c['xyz']) for c in cells)
    assert sum(Polygon(c['chart_m']).area for c in cells)==pytest.approx(Polygon(xy).area,abs=1e-9)
