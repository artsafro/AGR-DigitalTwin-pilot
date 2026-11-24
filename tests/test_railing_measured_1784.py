"""Synthetic source-section witnesses through the public railing core."""
from collections import Counter

import pytest

from adapters.max.agr_tools.railing_core import build_railing


def flight():
    # Vertical end sections, measured at three distinct flight/landing stations.
    rim = [[0, -.02, -.03], [0, .02, -.03], [0, .02, .03], [0, -.02, .03]]
    return {'measured_members': [{'role': 'top_rail', 'sections': [
        {'center': p, 'offsets': rim} for p in [[0, 0, 1], [2, 0, 2], [3, 0, 2]]
    ]}]}


def test_measured_flight_preserves_axes_height_profile_and_winding():
    result = build_railing(flight(), 'posts_handrail', 'npm')
    mesh, = result['meshes']
    assert result['triangle_count'] == 20
    assert result['measured_members'][0]['axis_m'] == [(0, 0, 1), (2, 0, 2), (3, 0, 2)]
    assert mesh['vertices'][0] == pytest.approx((0, -.02, .97))
    assert mesh['vertices'][4] == pytest.approx((2, -.02, 1.97))
    assert mesh['vertices'][10] == pytest.approx((3, .02, 2.03))
    edges = Counter((a, b) for face in mesh['faces'] for a, b in zip(face, face[1:] + face[:1]))
    assert all(n == edges[b, a] == 1 for (a, b), n in edges.items())


def test_measured_flight_rejects_backward_station_and_opacity():
    spec = flight()
    with pytest.raises(ValueError, match='measured.*geometry'):
        build_railing(spec, 'posts_handrail', 'npm', 'opacity')
    spec['measured_members'][0]['sections'][-1]['center'] = [1, 0, 2]
    with pytest.raises(ValueError, match='forward'):
        build_railing(spec, 'posts_handrail')


def test_measured_flight_rejects_misaligned_profile_phase():
    spec = flight()
    section = spec['measured_members'][0]['sections'][1]
    rim = section['offsets']
    section['offsets'] = rim[2:] + rim[:2]
    with pytest.raises(ValueError, match='profile correspondence'):
        build_railing(spec, 'posts_handrail')