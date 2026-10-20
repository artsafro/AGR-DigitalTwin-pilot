"""new-case: synthetic COD mixed-dimensional clip regression, no site assets."""
import pytest
from shapely.geometry import Polygon, box
from dt_ai.geometry import ground_cake as gc


def test_touching_clip_reports_non_area_parts_and_preserves_surface():
    # Connected outside the plot: clipping leaves one area and one isolated line.
    boundary = box(0, 0, 10, 10)
    touching = Polygon([(1, 1), (3, 1), (3, 11), (7, 11), (7, 10),
                        (9, 10), (9, 12), (1, 12)])
    assert touching.is_valid
    assert touching.intersection(boundary).geom_type == 'GeometryCollection'
    plan = gc.plan_layers(boundary, {'base': [boundary], 'top': [touching]},
                          'base', {'base': 'Base', 'top': 'Top'}, normalize_clips=True)
    assert plan.surface.area == 100
    assert sum(l.geom.area for l in plan.layers if l.slot == 'Top') == pytest.approx(18)
    dispositions = plan.report['clip_dispositions']
    assert any(d['covering'] == 'top' and d['reason'] == 'non_polygonal' for d in dispositions)
    assert all(l.geom.is_valid for l in plan.layers)
