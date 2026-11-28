import pymupdf

from run_keyplan import decide, perturb, segments

BOX = (50, 50, 150, 110)
FRAME = {"top": 90, "bottom": 270, "left": 180, "right": 0}


def strokes():
    with pymupdf.open() as doc:
        page = doc.new_page(width=240, height=200)
        for x in (50, 70, 90, 110, 130, 130):
            page.draw_line((x, 42), (x + 12, 42), color=(1, 0, 0))
        page.draw_line((50, 116), (150, 116), color=(0, 1, 0))
        return segments(page.get_cdrawings())


def test_registered_vector_mark():
    lines = strokes()
    assert decide(lines, BOX, FRAME) == decide(list(reversed(lines)), BOX, FRAME)
    assert decide(lines, BOX, FRAME)[0] == 90


def test_duplicate_short_stroke_is_not_coverage():
    assert decide([(50, 42, 62, 42)] * 20, BOX, FRAME)[0] is None


def test_ablation_and_altered_mark():
    variants = perturb(strokes(), BOX, FRAME)
    assert {k: decide(v, BOX, FRAME)[0] for k, v in variants.items()} == {
        "masked": None, "interior": None, "ambiguous": None, "opposite_only": 270,
    }


def test_unregistered():
    assert decide(strokes(), None, None) == (None, {})
