"""new-case: inline-text dimension gaps, source-bound KNS replay and refusal probes (#1302).

Synthetic PDFs are explicitly synthetic; the optional native replay uses immutable
#1290 copies and their hashes, never a generated substitute for real evidence.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

fitz = pytest.importorskip('pymupdf')
from dt_ai.album.binding import bind_album


def inline_dimension(path, *, rotation=90, gap_extra=0, decoy=False):
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    if rotation == 90:
        page.insert_text((103, 164), '6000', fontsize=8, rotate=90)
    else:
        page.insert_text((135, 153), '6000', fontsize=8)
    box = page.get_text('dict')['blocks'][0]['lines'][0]['spans'][0]['bbox']
    shape = page.new_shape()
    if rotation == 90:
        c, a, b = 100, 90, 210
        lo, hi = box[1], box[3]
        line = lambda t: (c, t)
        circles = [(80, a), (80, b)]
    else:
        c, a, b = 150, 90, 210
        lo, hi = box[0], box[2]
        line = lambda t: (t, c)
        circles = [(a, 170), (b, 170)]
    shape.draw_line(line(a - 4), line(lo - gap_extra))
    shape.draw_line(line(hi + gap_extra), line(b + 4))
    for t in (a, b):
        x, y = line(t)
        shape.draw_line((x - 2, y + 2), (x + 2, y - 2))
    shape.finish(color=(0, 0, 0), width=.3)
    for label, center in zip(('1', '2'), circles):
        shape.draw_circle(center, 6)
        shape.finish(color=(0, 0, 0), width=.3)
        page.insert_text((center[0] - 2, center[1] + 2), label, fontsize=6)
    if decoy:
        # A second numeric run in the same interruption must not license joining.
        page.insert_text((103, 164), '7000', fontsize=8, rotate=90)
    shape.commit()
    doc.save(path)
    return path


@pytest.mark.parametrize('rotation', [0, 90])
def test_inline_numeric_text_gap_recovers_span_without_calibration(tmp_path, rotation):
    result = bind_album(inline_dimension(tmp_path / 'synthetic.pdf', rotation=rotation))
    values = [v for v in result['values'] if v['raw'] == '6000']
    assert len(values) == 1
    assert values[0]['span'] is not None
    assert values[0]['binding'] == {'type': 'axis_pair', 'axes': ['1', '2']}
    assert values[0]['measured_mm'] is None
    assert result['passed'] is False
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])


@pytest.mark.parametrize('gap_extra,decoy', [(2, False), (0, True)])
def test_unexplained_or_ambiguous_gap_is_not_bridged(tmp_path, gap_extra, decoy):
    result = bind_album(inline_dimension(tmp_path / 'synthetic.pdf', gap_extra=gap_extra, decoy=decoy))
    assert all(v['binding']['type'] == 'unbound' for v in result['values'] if v['kind'] == 'dimension')
    assert result['passed'] is False


def test_native_kns_inline_rotated_text_gaps_keep_semantic_refusal():
    pdf = Path('C:/x/t_85bcc27a/native-v004/KNS-section.pdf')
    if not pdf.exists():
        pytest.skip('optional #1290 immutable native PDF not available')
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == '7ad80d8d79bf3355e451740ab82cf7d79b9975b0f4a95cd39191ef42580b93f1'
    result = bind_album(pdf)
    for raw in ('600', '4520', '7650', '4700', '680'):
        (value,) = [v for v in result['values'] if v['raw'] == raw]
        assert value['span'] is not None, raw
        assert value['binding']['type'] in ('unbound', 'level_pair')
        if value['binding']['type'] == 'level_pair':
            a, b = (float(t.replace(',', '.')) for t in value['binding']['levels'])
            assert abs(abs(a - b) * 1000 - value['value']) < .5
        assert value['measured_mm'] is None
    assert result['passed'] is False
    bound = [v for v in result['values'] if v['kind'] == 'dimension' and v['binding']['type'] != 'unbound']
    assert len(bound) == 8
    assert {v['raw'] for v in bound if v['binding']['type'] == 'level_pair'} == {'600', '4520', '7650', '4700'}


def test_generated_inline_pages_never_guess_scale_or_drop_labels(tmp_path):
    import random
    rng = random.Random(1302)
    for index in range(40):
        rotation = rng.choice([0, 90])
        source = inline_dimension(tmp_path / f'synthetic-source-{index}.pdf', rotation=rotation)
        original = fitz.open(source)
        nested = fitz.open()
        factor = rng.uniform(.65, 1.8)
        width = 300 * factor
        page = nested.new_page(width=width + 80, height=width + 80)
        page.show_pdf_page(fitz.Rect(40, 40, width + 40, width + 40), original, 0)
        path = tmp_path / f'synthetic-nested-{index}.pdf'
        nested.save(path)
        result = bind_album(path)
        (value,) = [v for v in result['values'] if v['raw'] == '6000']
        assert value['span'] is not None
        assert value['binding']['type'] in ('axis_pair', 'unbound')
        if value['binding']['type'] == 'axis_pair':
            assert value['binding']['axes'] == ['1', '2']
        assert value['measured_mm'] is None
        assert result['passed'] is False
        assert all(v['scale']['status'] == 'unknown' for v in result['views'])
