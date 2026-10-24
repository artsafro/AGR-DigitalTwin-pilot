"""SYNTHETIC PDF regressions: horizontal below-line integer-mm labels only.

Technical reading tests, not architectural or user acceptance. Oracles are the
synthetic generator's truth and the original page, captured before mutation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf", reason="requires the pdf-review extra")

from dt_ai.album import read_page  # noqa: E402
from dt_ai.album.synthetic import make_facade_pdf  # noqa: E402

COVERAGE = {
    "dimension_text_invalid",
    "dimension_text_missing",
    "dimension_text_unsupported",
}


def _move(src: Path, dst: Path, old: str, text: str, gap: float = 20) -> None:
    assert src.resolve() != dst.resolve()
    with pymupdf.open(src) as doc:
        page = doc[0]
        box = page.search_for(old)[0]
        page.add_redact_annot(box)
        page.apply_redactions(graphics=0)
        if text:
            page.insert_text((box.x0, 715 + gap), text)
        doc.save(dst)


def _assert_geometry(reading, truth) -> None:
    assert len(reading.dimensions) == 2
    for dim, want in zip(reading.dimensions, truth["dimensions"], strict=True):
        assert dim.p0 == pytest.approx(want["p0"], abs=0.01)
        assert dim.p1 == pytest.approx(want["p1"], abs=0.01)
        assert dim.axes == tuple(want["axes"])
        assert dim.measured_pt == pytest.approx(want["p1"][0] - want["p0"][0], abs=0.01)


@pytest.mark.parametrize("old", ["4500", "6000"])
@pytest.mark.parametrize("gap", [15, 20, 25])
def test_valid_below_recovers_original_geometry_scale_and_provenance(tmp_path, old, gap):
    src, dst = tmp_path / "original.pdf", tmp_path / "below.pdf"
    truth = make_facade_pdf(src)
    before = src.read_bytes()
    ref = read_page(src)
    _assert_geometry(ref, truth)
    assert [d.text for d in ref.dimensions] == ["6000", "4500"]
    assert ref.findings == []
    _move(src, dst, old, old, gap)
    got = read_page(dst)
    _assert_geometry(got, truth)
    assert [d.value_mm for d in got.dimensions] == [6000, 4500]
    assert got.axes == ref.axes
    assert got.scale == ref.scale
    assert got.scale.mm_per_pt == pytest.approx(truth["mm_per_pt"], rel=0.001)
    assert [c.status for c in got.dimension_checks] == ["reference", "ok"]
    assert got.findings == []
    moved = next(d for d in got.dimensions if d.text == old)
    assert moved.text_bbox[1] > 715
    assert any(r.text == old and r.bbox == moved.text_bbox for r in got.spans)
    assert got.source.sha256 == hashlib.sha256(dst.read_bytes()).hexdigest()
    assert got.source.page_number == ref.source.page_number == 1
    assert src.read_bytes() == before


@pytest.mark.parametrize("wrong", ["5000", "3900", "6000"])
def test_wrong_below_is_mismatch_without_moving_reference_scale(tmp_path, wrong):
    src, dst = tmp_path / "original.pdf", tmp_path / "below.pdf"
    truth = make_facade_pdf(src)
    ref = read_page(src)
    _move(src, dst, "4500", wrong)
    got = read_page(dst)
    _assert_geometry(got, truth)
    assert got.scale == ref.scale
    assert [c.status for c in got.dimension_checks] == ["reference", "dimension_mismatch"]
    assert [f.code for f in got.findings] == ["dimension_mismatch"]
    assert got.findings[0].data["written_mm"] == float(wrong)
    assert got.findings[0].data["axes"] == ["2", "3"]


@pytest.mark.parametrize("text", ["4500.0", "NaN", "inf", "-inf", "4500 mm", "450x", ""])
def test_below_invalid_or_missing_has_typed_endpoint_finding(tmp_path, text):
    src, dst = tmp_path / "original.pdf", tmp_path / "below.pdf"
    truth = make_facade_pdf(src)
    ref = read_page(src)
    _move(src, dst, "4500", text)
    got = read_page(dst)
    assert got.scale == ref.scale
    assert [d.axes for d in got.dimensions] == [("1", "2")]
    findings = [f for f in got.findings if f.code in COVERAGE]
    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == ("dimension_text_invalid" if text else "dimension_text_missing")
    assert finding.data["text"] == (text or None)
    assert finding.data["axes"] == ["2", "3"]
    for endpoint in ("p0", "p1"):
        assert finding.data[endpoint] == pytest.approx(truth["dimensions"][1][endpoint], abs=0.01)


def _chains(path, ys, labels, *, rotate=0):
    """Small independent vector fixture; label tuples are (text, center_y)."""
    with pymupdf.open() as doc:
        page = doc.new_page(width=300, height=250)
        for y in ys:
            page.draw_line((50, y), (250, y))
            for x in (50, 250):
                page.draw_line((x - 3, y + 3), (x + 3, y - 3))
        font = pymupdf.Font("helv")
        for text, cy in labels:
            baseline = cy + (font.ascender + font.descender) * 10 / 2
            page.insert_text((130, baseline), text, fontsize=10, rotate=rotate)
        doc.save(path)


@pytest.mark.parametrize("rotate", [90, 180, 270])
def test_rotated_or_negative_direction_below_is_not_read(tmp_path, rotate):
    path = tmp_path / "rotated.pdf"
    _chains(path, [100], [("4500", 115)], rotate=rotate)
    got = read_page(path)
    assert got.dimensions == []
    assert [f.code for f in got.findings if f.code in COVERAGE] == ["dimension_text_missing"]
    assert got.scale.status == "unknown"


@pytest.mark.parametrize("gap", [26, 30, 40])
def test_below_outside_existing_distance_limit_is_missing(tmp_path, gap):
    path = tmp_path / "distant.pdf"
    # Font size 10: the unchanged search limit is 25 pt from the text centre.
    _chains(path, [100], [("4500", 100 + gap)])
    got = read_page(path)
    assert got.dimensions == []
    assert [f.code for f in got.findings if f.code in COVERAGE] == ["dimension_text_missing"]
    assert got.scale.status == "unknown"


@pytest.mark.parametrize("spacing", [12, 20, 30])
def test_text_claimed_above_adjacent_chain_is_not_borrowed_below(tmp_path, spacing):
    path = tmp_path / "adjacent.pdf"
    # The upper line is visited first, but the lower line already owns the text above it.
    _chains(path, [100, 100 + spacing], [("4500", 100 + spacing / 2)])
    got = read_page(path)
    assert [(d.text, d.p0) for d in got.dimensions] == [("4500", (50, 100 + spacing))]
    findings = [f for f in got.findings if f.code in COVERAGE]
    assert len(findings) == 1 and findings[0].code == "dimension_text_missing"
    assert findings[0].data["p0"] == [50, 100]


@pytest.mark.parametrize("above", ["6000", "NaN"])
@pytest.mark.parametrize("gap", [5, 10, 20])
def test_above_priority_even_with_valid_below_label(tmp_path, above, gap):
    path = tmp_path / "priority.pdf"
    _chains(path, [100], [(above, 100 - gap), ("4500", 100 + gap)])
    got = read_page(path)
    if above == "6000":
        assert [d.text for d in got.dimensions] == ["6000"]
        assert not [f for f in got.findings if f.code in COVERAGE]
    else:
        assert got.dimensions == []
        assert [f.code for f in got.findings if f.code in COVERAGE] == ["dimension_text_invalid"]


@pytest.mark.parametrize("spacing", [5, 10, 15])
def test_below_label_is_used_at_most_once(tmp_path, spacing):
    path = tmp_path / "below_twice.pdf"
    _chains(path, [100, 100 + spacing], [("4500", 100 + spacing + 5)])
    got = read_page(path)
    assert len(got.dimensions) == 1
    assert got.dimensions[0].text == "4500"
    findings = [f for f in got.findings if f.code in COVERAGE]
    assert len(findings) == 1 and findings[0].code == "dimension_text_missing"
    assert len(got.dimensions) + len(findings) == 2
