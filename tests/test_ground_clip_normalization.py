"""new-case: synthetic COD mixed-dimensional clip regression, no site assets."""
import pytest
from shapely.geometry import Polygon, box
from dt_ai.geometry import ground_cake as gc


def test_precision_collapse_is_explicitly_reported():
    boundary = box(0, 0, 10, 10)
    # Above the pre-snap 1e-6 m2 area cutoff, narrower than half the 1 um grid.
    strip = box(1, 1, 1.0000004, 5)
    assert strip.area > 1e-6
    plan = gc.plan_layers(boundary, {'base': [boundary], 'strip': [strip]},
                          'base', {'base': 'Base', 'strip': 'Strip'}, normalize_clips=True)
    assert not any(l.slot == 'Strip' for l in plan.layers)
    assert any(d['covering'] == 'strip' and d['reason'] == 'precision_collapse'
               and d['area_m2'] == pytest.approx(strip.area)
               for d in plan.report['clip_dispositions'])


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
