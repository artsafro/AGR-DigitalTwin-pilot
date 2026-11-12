"""new-case: transformed compound axis loops and bidirectional level-symbol regression (#1254).

All documents in this module are synthetic.
"""
import math

import pytest

pymupdf = pytest.importorskip('pymupdf')
from dt_ai.album import binding as B, reader as R


@pytest.mark.parametrize('rotation', [0, 90, 180, 270])
def test_polygon_axis_in_nested_xobject(tmp_path, rotation):
    source = pymupdf.open()
    p = source.new_page(width=300, height=200)
    sh = p.new_shape()
    for x, label in [(80, '1'), (220, '4')]:
        pts = [(x + 10 * math.cos(k * math.pi / 8), 160 + 10 * math.sin(k * math.pi / 8)) for k in range(17)]
        sh.draw_polyline(pts)
        sh.draw_line((x, 150), (x, 70))
        p.insert_text((x-3, 163), label, fontsize=8)
    # Both bubbles and lines deliberately share one path, as in the real DWG plot.
    sh.finish(color=(0, 0, 0)); sh.commit()
    nested = pymupdf.open(); page = nested.new_page(width=600, height=600)
    page.show_pdf_page(pymupdf.Rect(50, 50, 550, 550), source, 0, rotate=rotation)
    final = pymupdf.open(); page = final.new_page(width=700, height=700)
    page.show_pdf_page(pymupdf.Rect(20, 20, 650, 650), nested, 0)
    path = tmp_path / 'nested.pdf'; final.save(path)
    result = B.bind_album(path)
    axes = [a for v in result['views'] for a in v['axes']]
    assert sorted(a['label'] for a in axes) == ['1', '4']
    assert all(a['orientation'] == ('vertical' if rotation % 180 == 0 else 'horizontal') for a in axes)
    assert result['passed'] is False
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])


@pytest.mark.parametrize('up', [False, True])
@pytest.mark.parametrize('factor', [0.6, 1, 2, 3])
def test_scaled_level_with_stem_in_either_direction(tmp_path, up, factor):
    doc = pymupdf.open(); page = doc.new_page(width=600, height=600)
    x, shelf = 120.0, 180.0
    y = shelf + (-14.6 if up else 14.6) * factor
    sh = page.new_shape()
    sh.draw_line((x-38*factor, shelf), (x, shelf))
    sh.draw_line((x, shelf), (x, y))
    arm_y = y + (6 if up else -6)*factor
    sh.draw_line((x-6*factor, arm_y), (x, y))
    sh.draw_line((x, y), (x+6*factor, arm_y))
    sh.draw_line((x-9*factor, y), (x+80*factor, y))
    sh.finish(color=(0, 0, 0)); sh.commit()
    page.insert_text((x-32*factor, shelf-2*factor), '+6.650', fontsize=9*factor)
    path=tmp_path/'level.pdf';doc.save(path)
    result=B.bind_album(path)
    bound=[v for v in result['values'] if v['binding']['type']=='level']
    assert len(bound)==1
    assert bound[0]['level_y']==pytest.approx(y,abs=.02)
