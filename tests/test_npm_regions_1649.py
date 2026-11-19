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
