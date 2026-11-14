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


def _drawing():
    from dt_ai.album.reader import Segment, TextRun
    def s(a, b):
        return Segment(a, b, .1, (0.,), 0)
    # Synthetic: dimension, two ticks, two extensions and continuation leader.
    segs = [s((10., 50.), (130., 50.)), s((8., 48.), (12., 52.)),
            s((108., 48.), (112., 52.)), s((10., 20.), (10., 54.)),
            s((110., 20.), (110., 54.))]
    runs = [TextRun('5000', (115., 42., 135., 48.), (115., 48.), 8., '', (1., 0.))]
    seeds = [dict(pair=[str(i), str(i+1)], length=100., value=5000.) for i in range(3)]
    return segs, runs, seeds


def test_displaced_label_requires_complete_geometry_and_supported_scale():
    from tools.research.pdf_album.dimension_geometry import reconstruct
    segs, runs, seeds = _drawing()
    result = reconstruct(segs, runs, seeds)
    assert len(result['labels']) == 1
    row = result['labels'][0]
    assert row['status'] == 'geometry_bound'
    assert row['span'] == {'p0': [10., 50.], 'p1': [110., 50.]}
    assert row['semantic_binding'] == 'unbound'
    assert row['credited'] is False
    assert reconstruct(segs[:-1], runs, seeds)['labels'][0]['status'] == 'unbound'
    assert reconstruct(segs, runs, seeds[:2])['labels'][0]['status'] == 'unbound'
    assert reconstruct(segs[:1] + segs[2:], runs, seeds)['labels'][0]['status'] == 'unbound'


def test_generated_scale_and_unbound_probes():
    import itertools
    import math
    import pytest
    from dataclasses import replace
    from tools.research.pdf_album.dimension_geometry import consensus_scale, reconstruct
    segs, runs, seeds = _drawing()
    for count in range(3):
        assert consensus_scale(seeds[:count])['mm_per_pt'] is None
    for permutation in itertools.permutations(seeds):
        assert consensus_scale(permutation)['mm_per_pt'] == 50.
    for bad in (float('nan'), float('inf'), -1., 0.):
        for key in ('length', 'value'):
            with pytest.raises(ValueError):
                consensus_scale([dict(seeds[0], **{key: bad})])
        with pytest.raises(ValueError):
            reconstruct([replace(segs[0], p0=(bad, math.nan))], runs, seeds)
    for angle in ((0., 1.), (.707, .707)):
        assert reconstruct(segs, [replace(runs[0], dir=angle)], seeds)['labels'][0]['status'] == 'unbound'
    assert all(r['status'] == 'unbound' for r in reconstruct(segs, runs*2, seeds)['labels'])
    # Strict scale residual threshold, using the median of five independent seeds.
    many = [dict(pair=[str(i), str(i+1)], length=100., value=5000.) for i in range(5)]
    for value, expected in ((5024., 'supported'), (5025., 'unknown'), (5026., 'unknown')):
        # Threshold is 0.5% of written value: use length as the perturbation.
        probe = [dict(s) for s in many]
        probe[-1]['length'] = value/50.
        assert consensus_scale(probe)['status'] == expected
    assert reconstruct([], [], [])['passed'] is False


def test_native_replay_fresh_process_and_no_output_api(tmp_path):
    import json
    import subprocess
    import sys
    from tools.research.pdf_album import dimension_autoresearch as E
    if not all(__import__('pathlib').Path(s['files']['pdf']['path']).is_file()
               for s in json.loads(E.CORPUS.read_text())['sheets']):
        import pytest
        pytest.skip('workstation frozen corpus not mounted')
    p = subprocess.run([sys.executable, '-m', 'tools.research.pdf_album.dimension_geometry'],
                       capture_output=True, text=True, encoding='utf8', check=True)
    result = json.loads(p.stdout)
    assert result['guard'] is True and result['passed'] is False
    for sheet in result['sheets']:
        assert sheet['before']['metrics'] == sheet['after']['metrics']
        assert sheet['document_guard']
        assert all(r['credited'] is False for g in sheet['geometry'] for r in g['labels'])
    l03 = result['sheets'][0]
    assert l03['model_cross_check']['counts']['match'] == 0
    assert l03['model_cross_check']['counts']['needs manual check'] > 0
    assert len(l03['after']['handles']) == 82
    target = tmp_path / 'input.pdf'
    target.write_bytes(b'preserve me')
    p = subprocess.run([sys.executable, '-m', 'tools.research.pdf_album.dimension_geometry',
                        '--output', str(target)], capture_output=True)
    assert p.returncode != 0
    assert target.read_bytes() == b'preserve me'
