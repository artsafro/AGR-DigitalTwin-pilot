"""new-case: reusable Ground site data; flat datum retains method-C spacing."""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box, mapping

spec = importlib.util.spec_from_file_location('ground_site_builder', Path(__file__).parents[1] / 'jobs/VATUTINO-SITE/build_ground.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def fixture():
    # Synthetic: asphalt at left, a 16 m2 approved large gap, 4 m2 lawn remainder.
    return {'boundary': mapping(box(0, 0, 10, 4)), 'base_covering': 'asphalt',
            'coverings': {'asphalt': {'geometry': mapping(box(0, 0, 5, 4))}},
            'elevations': []}


def settings():
    return {'slots': {'asphalt': 'Asphalt', 'lawn': 'Lawn'},
            'uncovered_covering': 'lawn', 'flat_datum_m': 0.0}


def test_second_site_flat_plan_uses_config_not_vatutino_slots():
    d = fixture()
    # Separate the unhatched hole (16 m2) from the small lawn region (4 m2).
    d['coverings']['asphalt']['geometry'] = mapping(box(1, 0, 6, 4))
    old = copy.deepcopy(d)
    plan, points = builder.site_plan(d, settings(), footprint_min=10)
    assert d == old
    assert sum(p.area for p in plan.holes) == pytest.approx(16)
    lawn = [l for l in plan.layers if l.covering == 'lawn']
    assert len(lawn) == 1 and lawn[0].geom.area == pytest.approx(4)
    assert lawn[0].slot == 'Lawn' and lawn[0].level == 1
    assert plan.layers[0].slot == 'Asphalt' and plan.step == .006
    assert np.asarray(points)[:, 2].tolist() == [0., 0., 0., 0.]
    sampler = builder.gc.ReliefSampler(builder.gc.build_tin(points))
    flat = builder.gc.build_flat(plan, cell=4, chord=0, sampler=sampler)
    projected, misses = builder.gc.project_z(flat, sampler, .006)
    assert not misses
    assert set(np.round(projected.verts[:, 2], 6)) == {0., .006}


@pytest.mark.parametrize('mutate,match', [
    (lambda s: s.update(flat_datum_m=float('nan')), 'flat_datum_m'),
    (lambda s: s.update(flat_datum_m=float('inf')), 'flat_datum_m'),
    (lambda s: s.update(flat_datum_m=True), 'flat_datum_m'),
    (lambda s: s['slots'].pop('asphalt'), 'asphalt'),
    (lambda s: s['slots'].update(unknown='Unknown'), 'unknown'),
    (lambda s: s['slots'].update(lawn=''), 'lawn'),
    (lambda s: s.update(uncovered_covering='asphalt'), 'uncovered_covering'),
    (lambda s: s.update(typo=0), 'typo'),
])
def test_site_settings_fail_closed(mutate, match):
    s = settings()
    mutate(s)
    with pytest.raises(ValueError, match=match):
        builder.site_plan(fixture(), s, footprint_min=10)
