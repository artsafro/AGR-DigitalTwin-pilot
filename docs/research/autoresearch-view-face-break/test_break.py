"""Tests for the #158 OBSERVE predicate (not product behavior)."""

import pymupdf

from run import break_marks


def glyph(x=0, y=50):
    P, R = pymupdf.Point, pymupdf.Rect
    return [
        {'type': 's', 'color': (0, 0, 0), 'items': [('l', P(x, y+3), P(x-6, y+1))]},
        {'type': 's', 'color': (0, 0, 0), 'items': [('l', P(x+6, y-2), P(x-6, y+1))]},
        {'type': 's', 'color': (0, 0, 0), 'items': [('l', P(x, y-4), P(x+6, y-2))]},
        {'type': 'f', 'fill': (1, 1, 1), 'fill_opacity': 1, 'items': [('re', R(x-6, y-2, x+6, y+2), -1)]},
        {'type': 'f', 'fill': (1, 1, 1), 'fill_opacity': 1, 'items': [('re', R(x-6, y-3, x+6, y+1), -1)]},
    ]


def test_mark_requires_boundary_and_knockout_and_is_order_independent():
    box = (0, 0, 100, 100)
    drawing = glyph()
    marks = break_marks(drawing, box)
    assert len(marks) == 1
    assert marks == break_marks(drawing[::-1], box)
    assert not break_marks(drawing[:3], box)
    assert not break_marks(drawing[:4], box)
    assert not break_marks(glyph(50), box)
    assert not break_marks(glyph(0, 5), box)


def test_top_edge_rotation_and_disconnected_arms():
    drawing = glyph(0, 50)
    P, R = pymupdf.Point, pymupdf.Rect
    for d in drawing:
        tag, a, b = d['items'][0]
        transformed = ('l', P(a.y, a.x), P(b.y, b.x)) if tag == 'l' else ('re', R(a.y0, a.x0, a.y1, a.x1), b)
        d['items'] = [transformed]
    assert len(break_marks(drawing, (0, 0, 100, 100))) == 1
    drawing[0]['items'] = [('l', P(53, 0), P(51, -7))]
    assert not break_marks(drawing, (0, 0, 100, 100))
