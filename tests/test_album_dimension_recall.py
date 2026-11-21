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


def inline_dimension(path, *, rotation=90, gap_extra=0, decoy=False,
                     nearby_decoy=False, text_offset=0):
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    if rotation == 90:
        page.insert_text((103 + text_offset, 164), '6000', fontsize=8, rotate=90)
    else:
        page.insert_text((135, 153 + text_offset), '6000', fontsize=8)
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
        if rotation == 90:
            page.insert_text((103 + text_offset, 164), '7000', fontsize=8, rotate=90)
        else:
            page.insert_text((135, 153 + text_offset), '7000', fontsize=8)
    if nearby_decoy:
        # Separate annotation wins the legacy near-side heuristic but did not
        # authorize the inline gap. It must never inherit that span's endpoints.
        if rotation == 90:
            page.insert_text((91, 164), '9000', fontsize=8, rotate=90)
        else:
            page.insert_text((135, 143), '9000', fontsize=8)
    shape.commit()
    doc.save(path)
    return path


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('nearby_decoy', [False, True])
def test_inline_gap_authorizer_cannot_be_replaced_by_nearby_annotation(
    tmp_path, rotation, nearby_decoy,
):
    result = bind_album(inline_dimension(
        tmp_path / 'synthetic-authorizer.pdf', rotation=rotation,
        text_offset=2, nearby_decoy=nearby_decoy,
    ))
    (value,) = [v for v in result['values'] if v['raw'] == '6000']
    assert value['binding'] == {'type': 'axis_pair', 'axes': ['1', '2']}
    assert value['span'] is not None
    if nearby_decoy:
        (annotation,) = [v for v in result['values'] if v['raw'] == '9000']
        assert annotation['binding'] == {'type': 'unbound', 'reason': 'no_dimension_line'}
        assert annotation['span'] is None
    assert all(v['measured_mm'] is None for v in result['values'])
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])
    assert result['passed'] is False


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
    # Count is not a correctness oracle: additional native pairs are welcome,
    # but every positive must match value AND physical line/extension ends.
    import json
    from tools.research.pdf_album.dimension_autoresearch import (
        CORPUS, geometry_matches, precision_guard, score,
    )
    corpus = json.loads(CORPUS.read_text(encoding='utf8'))
    truth = next(s['truth'] for s in corpus['sheets'] if s['name'] == 'KNS')
    scored = score(result['values'], truth)
    assert precision_guard(scored['metrics']) == 'pass'
    assert scored['wrong_ids'] == []
    expected = {
        '3414': ('axis_pair', ['1/1', '1']),
        '3415': ('axis_pair', ['1', '2']),
        '3416': ('axis_pair', ['2', '2/1']),
        '3417': ('axis_pair', ['1/1', '2/1']),
        '3418': ('level_pair', ['-13,320', '-12,720']),
        '3419': ('level_pair', ['-12,720', '-8,200']),
        '341A': ('level_pair', ['-8,200', '-8,000']),
        '341B': ('level_pair', ['-8,000', '-0,350']),
        '341C': ('level_pair', ['-0,350', '-0,100']),
        '341D': ('level_pair', ['-0,100', '+4,600']),
    }
    for handle, (kind, pair) in expected.items():
        native = next(t for t in truth if t['handle'] == handle)
        matches = [v for v in bound if geometry_matches(v, native)
                   and abs(v['value'] - native['measurement']) < .5]
        assert len(matches) == 1, handle
        key = 'axes' if kind == 'axis_pair' else 'levels'
        assert matches[0]['binding'] == {'type': kind, key: pair}, handle
    # The unresolved bottom pairs still need proven endpoint identity.
    assert {r['handle'] for r in scored['handles'] if r['class'] != 'correct_semantic_binding'} == {'341E', '341F'}


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('length', [10, 16, 20])
@pytest.mark.parametrize('offset', [1, 15.9, 16, 16.1])
def test_short_displaced_labels_keep_strict_two_em_bounds(tmp_path, rotation, length, offset):
    # Synthetic vector witness: only short spans may search beyond their ticks.
    # Exact two-em span lengths and text-center limits must remain excluded.
    path = tmp_path / 'synthetic-displaced.pdf'
    with fitz.open() as source, fitz.open() as doc:
        page = source.new_page(width=300, height=300)
        end = 100 + length
        page.draw_line((98, 150), (end + 2, 150), width=.3)
        for x in (100, end):
            page.draw_line((x - 2, 152), (x + 2, 148), width=.3)
        half_width = fitz.get_text_length('200', fontsize=8) / 2
        page.insert_text((end + offset - half_width, 143), '200', fontsize=8)
        target = doc.new_page(width=300, height=300)
        target.show_pdf_page(target.rect, source, 0, rotate=rotation)
        doc.save(path)
    result = bind_album(path)
    (value,) = [v for v in result['values'] if v['raw'] == '200']
    assert (value['span'] is not None) == (length < 16 and offset < 16)
    assert value['binding']['type'] == 'unbound'  # no semantic endpoints invented
    assert value['measured_mm'] is None
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])
    assert result['passed'] is False


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('length', [8, 10, 12])
@pytest.mark.parametrize('order', ['11first', '22first'])
@pytest.mark.parametrize('lift', [0, 1.5])
def test_adjacent_short_spans_keep_own_labels_under_padding(tmp_path, rotation, length, order, lift):
    # Review P1 on #1332: R1 padding must never let a label centred inside its
    # own span be taken by the neighbouring short span of the same chain.
    path = tmp_path / 'synthetic-adjacent.pdf'
    ticks = [100, 100 + length, 100 + 2 * length]
    with fitz.open() as source, fitz.open() as doc:
        page = source.new_page(width=300, height=300)
        page.draw_line((98, 150), (ticks[-1] + 2, 150), width=.3)
        for x in ticks:
            page.draw_line((x - 2, 152), (x + 2, 148), width=.3)
        half_width = fitz.get_text_length('11', fontsize=8) / 2
        labels = [('11', (ticks[0] + ticks[1]) / 2, 143 - lift), ('22', (ticks[1] + ticks[2]) / 2, 143)]
        if order == '22first':
            labels.reverse()
        for text, cx, y in labels:
            page.insert_text((cx - half_width, y), text, fontsize=8)
        target = doc.new_page(width=300, height=300)
        target.show_pdf_page(target.rect, source, 0, rotate=rotation)
        doc.save(path)
    result = bind_album(path)
    found = {v['raw']: v for v in result['values'] if v['raw'] in ('11', '22')}
    if order == '11first':
        # The extractor joins the two stream-adjacent runs into one ('1122' /
        # '11 22'); that run is not a numeric span label and stays unbound.
        assert not found
        assert all(v['binding']['type'] == 'unbound' for v in result['values'])
    else:
        assert set(found) == {'11', '22'}
    spans = {}
    for raw, value in found.items():
        span = value['span']
        assert span is not None, raw  # strict in-span hit is always available
        axis = 0 if span['p0'][1] == span['p1'][1] else 1
        lo, hi = sorted((span['p0'][axis], span['p1'][axis]))
        centre = (value['bbox'][axis] + value['bbox'][axis + 2]) / 2
        assert lo < centre < hi, (raw, span, value['bbox'])  # own span, never the neighbour
        assert value['binding']['type'] == 'unbound'
        assert value['measured_mm'] is None
        spans[raw] = (lo, hi)
    assert len(set(spans.values())) == len(spans)
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])
    assert result['passed'] is False


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


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('text_offset', [0, 1, 2])
@pytest.mark.parametrize('factor', [.75, 1, 1.25])
def test_transformed_gap_authorizer_identity_survives_nearby_decoy(
    tmp_path, rotation, text_offset, factor,
):
    source = inline_dimension(tmp_path / 'synthetic-source.pdf', rotation=rotation,
                              nearby_decoy=True, text_offset=text_offset)
    with fitz.open(source) as original, fitz.open() as nested:
        page = nested.new_page(width=300 * factor + 80, height=300 * factor + 80)
        page.show_pdf_page(fitz.Rect(40, 40, 300 * factor + 40, 300 * factor + 40), original, 0)
        path = tmp_path / 'synthetic-transformed.pdf'
        nested.save(path)
    result = bind_album(path)
    (value,) = [v for v in result['values'] if v['raw'] == '6000']
    (decoy,) = [v for v in result['values'] if v['raw'] == '9000']
    assert value['span'] is not None
    assert value['binding']['type'] in ('axis_pair', 'unbound')
    if value['binding']['type'] == 'axis_pair':
        assert value['binding']['axes'] == ['1', '2']
    assert decoy['span'] is None
    assert decoy['binding'] == {'type': 'unbound', 'reason': 'no_dimension_line'}
    assert all(v['measured_mm'] is None for v in result['values'])
    assert all(v['scale']['status'] == 'unknown' for v in result['views'])
    assert result['passed'] is False


@pytest.mark.parametrize('rotation', [0, 90])
@pytest.mark.parametrize('gap_extra,duplicate', [(2, False), (0, True)])
def test_nearby_decoy_does_not_rescue_invalid_inline_gap(
    tmp_path, rotation, gap_extra, duplicate,
):
    result = bind_album(inline_dimension(
        tmp_path / 'synthetic-invalid.pdf', rotation=rotation, text_offset=2,
        nearby_decoy=True, gap_extra=gap_extra, decoy=duplicate,
    ))
    assert all(v['binding']['type'] == 'unbound' for v in result['values']
               if v['kind'] == 'dimension')
    assert result['passed'] is False


@pytest.mark.parametrize('ticks', [(60, 160, 260), (60, 260), (60, 105, 260)])
@pytest.mark.parametrize('second_raw', ['7000', '6000'])
def test_multiple_inline_gaps_keep_per_span_run_identity(tmp_path, ticks, second_raw):
    # Synthetic chain: two independent inline text runs, plus nearby decoys.
    # Missing middle tick leaves two authorizers for one span; a tick through
    # text leaves an interruption crossing spans. Both configurations refuse.
    path = tmp_path / 'synthetic-chain.pdf'
    with fitz.open() as doc:
        page = doc.new_page(width=320, height=300)
        for x, raw in [(95, '6000'), (195, second_raw)]:
            page.insert_text((x, 155), raw, fontsize=8)
        boxes = [line['spans'][0]['bbox'] for block in page.get_text('dict')['blocks']
                 for line in block['lines']]
        shape = page.new_shape()
        previous = 56
        for box in boxes:
            shape.draw_line((previous, 150), (box[0], 150))
            previous = box[2]
        shape.draw_line((previous, 150), (264, 150))
        for t in ticks:
            shape.draw_line((t - 2, 152), (t + 2, 148))
        shape.finish(color=(0, 0, 0), width=.3)
        for t in ticks:
            shape.draw_circle((t, 170), 6)
            shape.finish(color=(0, 0, 0), width=.3)
            page.insert_text((t - 2, 172), str(ticks.index(t) + 1), fontsize=6)
        shape.commit()
        for x in (95, 195):
            page.insert_text((x, 143), '9000', fontsize=8)
        doc.save(path)
    result = bind_album(path)
    dimensions = [v for v in result['values'] if v['kind'] == 'dimension']
    decoys = [v for v in dimensions if v['raw'] == '9000']
    assert len(decoys) == 2
    assert all(v['span'] is None and v['binding']['type'] == 'unbound' for v in decoys)
    bound = [v for v in dimensions if v['binding']['type'] != 'unbound']
    if ticks == (60, 160, 260):
        assert [(v['raw'], v['binding']) for v in bound] == [
            ('6000', {'type': 'axis_pair', 'axes': ['1', '2']}),
            (second_raw, {'type': 'axis_pair', 'axes': ['2', '3']}),
        ]
    else:
        assert bound == []
    assert result['passed'] is False
