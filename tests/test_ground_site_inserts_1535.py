"""new-case: synthetic INSERT placement regressions for the Ground DXF adapter (#1535)."""
import ezdxf
import pytest
from shapely.geometry import Polygon
from dt_ai.geometry import ground_site as gs


def fixture():
    doc = ezdxf.new()
    block = doc.blocks.new('COVER', base_point=(1, 2, 0))
    hatch = block.add_hatch()
    hatch.bgcolor = (10, 20, 30)
    hatch.paths.add_polyline_path([(1, 2), (4, 2), (4, 4), (1, 4)], is_closed=True)
    ins = doc.modelspace().add_blockref('COVER', (10, 20))
    return doc, hatch, ins


def row(hatch, chain):
    return {'id': 1, 'name': 'Paving', 'hatches': [
        {'handle': hatch.dxf.handle, 'insert_chain': chain}]}


@pytest.mark.parametrize('sx,sy,angle', [(1, 1, 0), (2, 2, 90), (-2, 2, 30), (2, -2, -45)])
def test_placed_hatch_full_transform(sx, sy, angle):
    doc, hatch, ins = fixture()
    ins.dxf.xscale, ins.dxf.yscale, ins.dxf.rotation = sx, sy, angle
    cover = gs.covers_from_dxf(doc, [row(hatch, [ins.dxf.handle])], .002)[0]
    # Independent oracle from analytic scale/rotation about the block base point.
    import math
    a = math.radians(angle)
    pts = [(10 + sx*x*math.cos(a) - sy*y*math.sin(a),
            20 + sx*x*math.sin(a) + sy*y*math.cos(a)) for x, y in [(0, 0), (3, 0), (3, 2), (0, 2)]]
    assert cover.polygons[0].symmetric_difference(Polygon(pts)).area < 1e-10
    assert sum(p.area for p in cover.polygons) == pytest.approx(6*abs(sx*sy))
    assert cover.colour == (10, 20, 30)
    assert cover.sources == row(hatch, [ins.dxf.handle])['hatches']
