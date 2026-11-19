"""new-case: source-bound colour splits for mixed NPM atlas cells."""
from itertools import permutations

import pytest
from PIL import Image, ImageDraw
from shapely.geometry import Polygon
from shapely.ops import unary_union


@pytest.mark.parametrize('order', list(permutations(range(3))))
def test_two_colour_nonrectangular_cell_splits_crossing_triangle(tmp_path, order):
    from tools.library.npm_ids import recover_regions

    image = Image.new('RGB', (64, 64), (20, 20, 20))
    ImageDraw.Draw(image).rectangle((16, 16, 47, 47), fill=(220, 220, 220))
    atlas = tmp_path / 'two.png'
    image.save(atlas)
    uv = [(0., 1.), (1., 1.), (0., 0.)]
    result = recover_regions(atlas, [[uv[i] for i in order]])
    assert result['status'] == 'ok'
    assert not result['residual']
    pieces = result['pieces'][0]
    assert len({piece['id'] for piece in pieces}) == 2
    assert {row['color'].lower() for row in result['table']} == {'#141414', '#dcdcdc'}
    # An independent area oracle: the diagonal bisects the inner square exactly.
    shapes = [Polygon(piece['uv']) for piece in pieces]
    union = unary_union(shapes)
    assert union.symmetric_difference(Polygon(uv)).area < 1e-12
    assert sum(p.area for p in shapes) == pytest.approx(union.area)
    by_id = {i: sum(p.area for p, r in zip(shapes, pieces) if r['id'] == i)
             for i in {r['id'] for r in pieces}}
    assert sorted(by_id.values()) == pytest.approx([.125, .375])
    for piece in pieces:
        assert Polygon(piece['uv']).exterior.is_ccw == Polygon([uv[i] for i in order]).exterior.is_ccw


@pytest.mark.parametrize('width,seam', [(8, 4), (12, 6), (14, 7), (30, 6)])
def test_metric_seam_plan_cuts_oversize_but_preserves_surface(width, seam):
    from adapters.max.agr_tools.npm2vpm_core import fit_metric_region

    source = [((0., 0., 0.), (float(width), 0., 0.), (0., 2., 0.))]
    result = fit_metric_region(3, source, [((0., 0.), (float(width), 0.), (0., 2.))],
                               preferred_seams=[(0, seam)])
    assert result['status'] == 'ok'
    assert result['cuts'][0]['at_m'] == seam
    assert result['cuts'][0]['kind'] == 'panel_or_zone'
    assert len(result['pieces']) >= 2
    assert len({p['piece'] for p in result['pieces']}) == result['piece_count']
    polys = []
    for p in result['pieces']:
        assert p['source_triangle'] == 0
        assert all(0 < u < 1 and 0 < v < 1 for u, v in p['uv'])
        poly = Polygon([(x, y) for x, y, _ in p['xyz']])
        assert Polygon(p['uv']).area / poly.area == pytest.approx((512/4096)**2)
        polys.append(poly)
    assert sum(p.area for p in polys) == pytest.approx(width)
    assert unary_union(polys).symmetric_difference(Polygon([(0, 0), (width, 0), (0, 2)])).area < 1e-10


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 0, 128, True])
def test_colour_tolerance_rejects_bad_input(value):
    from tools.library.npm_ids import recover_regions

    with pytest.raises(ValueError, match='tolerance'):
        recover_regions('not_read.png', [], colour_tolerance=value)


def test_colour_exact_tolerance_strip_is_not_guessed(tmp_path):
    from tools.library.npm_ids import recover_regions

    image = Image.new('RGB', (64, 64), (20, 20, 20))
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 47, 47), fill=(220, 220, 220))
    draw.rectangle((16, 20, 16, 25), fill=(214, 214, 214))
    atlas = tmp_path / 'two.png'
    image.save(atlas)
    result = recover_regions(atlas, [[(0., 1.), (1., 1.), (0., 0.)]])
    assert result['status'] == 'manual_required'
    assert result['residual'] == [0]
    assert result['pieces'] == [[]]


@pytest.mark.parametrize('case', ['empty', 'partial', 'unmapped', 'unsupported', 'nan', 'inf', 'mirror', 'shear'])
def test_seam_plan_refuses_unusable_charts(case):
    from adapters.max.agr_tools.npm2vpm_core import fit_metric_region

    xyz = [[(0., 0., 0.), (10., 0., 0.), (0., 2., 0.)]]
    uv = [[(0., 0.), (10., 0.), (0., 2.)]]
    if case == 'empty': xyz, uv = [], []
    if case == 'partial': uv = []
    if case == 'unsupported': uv[0].append((1., 1.))
    if case in ('nan', 'inf'): uv[0][0] = (float(case), 0.)
    if case == 'mirror': uv[0][2] = (0., -2.)
    if case == 'shear': uv[0][2] = (1., 2.)
    with pytest.raises(ValueError):
        fit_metric_region(0 if case == 'unmapped' else 7, xyz, uv)


def test_exact_padded_tile_extent_cannot_fit_uncut():
    from adapters.max.agr_tools.npm2vpm_core import fit_metric_region

    size = (4096 - 64) / 512
    blocked = fit_metric_region(1, [[(0., 0., 0.), (size, 0., 0.), (0., 2., 0.)]],
                                [[(0., 0.), (size, 0.), (0., 2.)]], piece_budget=1)
    assert blocked['status'] == 'blocked'
    assert blocked['reason'] == 'tile_budget'
    assert blocked['source_triangles'] == [0]
    assert blocked['pieces'] == blocked['cuts'] == []
