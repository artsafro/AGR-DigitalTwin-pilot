"""new-case: synthetic witnesses at the shared railing mesh/CLI seams."""
import math
import subprocess
import sys
from collections import Counter

import pytest


def build(points, kind='glass_posts', profile='vpm', representation='geometry', **extra):
    from adapters.max.agr_tools.railing_core import build_railing

    dims = dict(height=1.0, max_step=1.1, post_width=.04, post_depth=.08)
    if kind != 'glass_posts':
        dims.update(rail_width=.06, rail_height=.04)
    if kind != 'posts_handrail':
        dims.update(panel_bottom=.1, panel_top=.9, panel_depth=.012, clearance=.005)
    dims.update(extra.pop('dimensions', {}))
    return build_railing(dict(points=points, closed=False, dimensions=dims) | extra,
                         kind, profile, representation)


def test_open_corner_end_and_collinear_spacing():
    r = build([[0, 0, 0], [.4, 0, 0], [3, 0, 0], [3, 1.6, 0]])
    assert [tuple(p) for p in r['posts']] == [(0, 0, 0), (1, 0, 0), (2, 0, 0),
                                               (3, 0, 0), (3, .8, 0), (3, 1.6, 0)]
    assert r['run_steps_m'] == pytest.approx([1, .8])


def test_closed_no_duplicate_seam_post_or_rail_cap():
    r = build([[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]], 'posts_handrail', closed=True)
    assert len(r['posts']) == len(set(map(tuple, r['posts']))) == 8
    rail = next(m for m in r['meshes'] if m['role'] == 'top_rail')
    assert len(rail['faces']) == 16


@pytest.mark.parametrize('length_cm', range(20, 601, 19))
def test_generated_even_spacing(length_cm):
    length = length_cm / 100
    r = build([[0, 0, 0], [length, 0, 0]])
    distances = [math.dist(a, b) for a, b in zip(r['posts'], r['posts'][1:])]
    assert len(distances) == math.ceil(length / 1.1)
    assert max(distances) <= 1.1 + 1e-12
    assert distances == pytest.approx([distances[0]] * len(distances))
    assert r['posts'][-1] == (length, 0, 0)


@pytest.mark.parametrize('profile', ['vpm', 'npm'])
@pytest.mark.parametrize(('kind', 'roles'), [('glass_posts', {'post', 'glass'}),
    ('posts_handrail', {'post', 'top_rail'}), ('posts_handrail_infill', {'post', 'top_rail', 'infill'})])
def test_geometry_quads_and_material_slots(kind, roles, profile):
    r = build([[0, 0, 0], [2, 0, 0], [2, 2, 0]], kind, profile)
    assert set(r['materials'].values()) == roles
    assert set(m['material_id'] for m in r['meshes']) == set(r['materials'])
    for mesh in r['meshes']:
        verts, faces = mesh['vertices'], mesh['faces']
        assert len(set(verts)) == len(verts)
        edges = Counter()
        for f in faces:
            assert len(f) == len(set(f)) == 4
            for a, b in zip(f, (*f[1:], f[0])):
                assert math.dist(verts[a], verts[b]) > 0
                edges[a, b] += 1
        assert all(n == edges[b, a] == 1 for (a, b), n in edges.items())
        assert set(i for f in faces for i in f) == set(range(len(verts)))


@pytest.mark.parametrize('kind', ['glass_posts', 'posts_handrail', 'posts_handrail_infill'])
def test_opacity_is_one_sided_and_cheaper(kind):
    points = [[0, 0, 0], [2.8, 0, 0], [2.8, 2, 0]]
    r = build(points, kind, 'npm', 'opacity')
    assert r['triangle_count'] < build(points, kind, 'npm')['triangle_count']
    assert r['materials'] == {5: 'opacity'}
    for mesh in r['meshes']:
        assert mesh['faces'] == [(0, 1, 2, 3)]
        assert mesh['mask_rects']
    with pytest.raises(ValueError, match='opacity'):
        build(points, kind, 'vpm', 'opacity')


@pytest.mark.parametrize('points', [[], [[0, 0, 0]], [[0, 0, 0], [1, 0]],
    [[0, 0, 0], [math.nan, 0, 0]], [[0, 0, 0], [math.inf, 0, 0]],
    [[0, 0, 0], [.00001, 0, 0]], [[0, 0, 0], [1, 0, .1]],
    [[0, 0, 0], [1, 0, 0], [0, 0, 0]], [[0, 0, 0], [2, 2, 0], [0, 2, 0], [2, 0, 0]]])
def test_invalid_path(points):
    with pytest.raises(ValueError):
        build(points)


def test_reject_unknown_and_unusable_dimensions():
    pts = [[0, 0, 0], [1, 0, 0]]
    for dims in ({'post_width': 0}, {'post_depth': math.inf}, {'panel_top': .1},
                 {'missing_slot': 2}, {'max_step': .0000001}):
        with pytest.raises(ValueError):
            build(pts, dimensions=dims)


def test_sampled_curve_corners_are_explicit():
    pts = [[0, 0, 0], [.5, 0, 0], [1, .1, 0], [1.5, .3, 0], [2, .6, 0]]
    r = build(pts, corners=[0, 4])
    assert len(r['posts']) == 3
    assert len(r['run_steps_m']) == 1
    assert r['run_steps_m'][0] == pytest.approx(sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) / 2)


def test_fresh_cli_help_and_preserve_aliased_input(tmp_path):
    cmd = [sys.executable, '-m', 'dt_ai.cli.agr', 'railing']
    help_run = subprocess.run([*cmd, '--help'], capture_output=True, text=True)
    assert help_run.returncode == 0 and 'glass_posts' in help_run.stdout
    path = tmp_path / 'source.blend'
    path.write_bytes(b'original')
    alt = tmp_path / 'alias.blend'
    alt.hardlink_to(path)
    for out in (path, alt):
        run = subprocess.run([*cmd, str(path), '--type', 'glass_posts', '--out', str(out)],
                             capture_output=True, text=True)
        assert run.returncode != 0 and 'output' in run.stderr.lower()
        assert path.read_bytes() == alt.read_bytes() == b'original'
    assert set(tmp_path.iterdir()) == {path, alt}
