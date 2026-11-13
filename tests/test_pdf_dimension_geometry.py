"""new-case: geometry-only dimension research must not manufacture semantics."""
from importlib.util import find_spec


def test_three_independent_dimensions_required():
    name = 'tools.research.pdf_album.dimension_geometry'
    assert find_spec(name) is not None, 'geometry reconstruction prototype missing'
    from tools.research.pdf_album.dimension_geometry import consensus_scale
    seeds = [dict(pair=['1', '2'], length=100., value=5000.),
             dict(pair=['2', '3'], length=80., value=4000.),
             dict(pair=['1', '3'], length=180., value=9000.)]
    assert consensus_scale(seeds)['status'] == 'unknown'  # dependent sum
    seeds.append(dict(pair=['3', '4'], length=60., value=3000.))
    result = consensus_scale(seeds)
    assert result['status'] == 'supported'
    assert result['mm_per_pt'] == 50.
    assert result['independent'] == 3
