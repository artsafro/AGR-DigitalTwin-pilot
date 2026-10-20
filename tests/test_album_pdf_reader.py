"""Album reader (#317, kernel C5): vector PDF page -> axes, dimensions, level marks, legend, scale.

All PDFs here are SYNTHETIC, generated at test time with PyMuPDF (no committed PDF, no user album).
Run: env -u PYTHONPATH -u VIRTUAL_ENV uv run -q --extra pdf-review pytest -q tests/test_album_pdf_reader.py
"""

from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

pymupdf = pytest.importorskip(
    "pymupdf",
    reason="PyMuPDF is the optional extra 'pdf-review': uv run --extra pdf-review pytest ...",
)

from dt_ai.album import (  # noqa: E402
    AlbumExtraMissing,
    AlbumReadError,
    check_dimension,
    check_level_pair,
    parse_level_text,
    read_page,
    reading_to_json,
)
from dt_ai.album.synthetic import LEGEND_ROWS, SCALE_1_100_MM_PER_PT, make_facade_pdf  # noqa: E402

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def facade(tmp_path: Path) -> tuple[Path, dict]:
    path = tmp_path / "facade.pdf"
    truth = make_facade_pdf(path)
    return path, truth


def _xy(p) -> tuple[float, float]:
    return (float(p[0]), float(p[1]))


def test_synthetic_page_is_vector_with_text(facade) -> None:
    path, _ = facade
    reading = read_page(path)
    assert reading.status == "ok"
    assert reading.lines and reading.spans and reading.paths


def test_axes_labels_orientation_positions(facade) -> None:
    path, truth = facade
    axes = read_page(path).axes
    got = {(a.label, a.orientation): a.position for a in axes}
    assert len(axes) == 5
    for want in truth["axes"]:
        assert got[(want["label"], want["orientation"])] == pytest.approx(
            want["position"], abs=0.01
        )
    for a in axes:  # the axis line starts on the bubble edge
        start = a.line_p0
        dist = math.dist(start, a.bubble_center)
        assert dist == pytest.approx(a.bubble_radius, abs=0.05)


def test_dimensions_values_and_endpoints(facade) -> None:
    path, truth = facade
    dims = read_page(path).dimensions
    assert [d.value_mm for d in dims] == [6000.0, 4500.0]
    for got, want in zip(dims, truth["dimensions"], strict=True):
        assert got.text == want["text"]
        assert got.axes == tuple(want["axes"])
        assert _xy(got.p0) == pytest.approx(want["p0"], abs=0.01)
        assert _xy(got.p1) == pytest.approx(want["p1"], abs=0.01)


def test_level_marks_values_metres_and_page_y(facade) -> None:
    path, truth = facade
    marks = read_page(path).level_marks
    assert [m.text for m in marks] == ["±0.000", "+3.000", "+6.000"]
    for got, want in zip(marks, truth["levels"], strict=True):
        assert got.value_m == want["value_m"]
        assert got.y == pytest.approx(want["y"], abs=0.01)


def test_legend_swatch_rgb_and_exact_cyrillic_label(facade) -> None:
    path, _ = facade
    legend = read_page(path).legend
    assert [item.label for item in legend] == [label for _, label in LEGEND_ROWS]
    for item, (rgb, _) in zip(legend, LEGEND_ROWS, strict=True):
        for got, want in zip(item.rgb, rgb, strict=True):
            assert abs(got - want / 255.0) <= 1 / 255.0
        assert list(item.rgb255) == list(rgb)
    assert "Условные обозначения" not in [item.label for item in legend]


def test_scale_from_axis_dimension_1_2(facade) -> None:
    path, truth = facade
    reading = read_page(path)
    scale = reading.scale
    assert scale.status == "derived"
    assert scale.reference_axes == ("1", "2") and scale.reference_mm == 6000.0
    assert abs(scale.mm_per_pt / truth["mm_per_pt"] - 1.0) < 0.001
    checks = {c.axes: c for c in reading.dimension_checks}
    assert checks[("1", "2")].status == "reference"
    second = checks[("2", "3")]
    assert second.status == "ok"
    assert abs(second.measured_mm - 4500.0) <= second.tolerance_mm
    assert not [f for f in reading.findings if f.code == "dimension_mismatch"]


def test_wrong_dimension_text_is_mismatch_and_never_changes_scale(
    tmp_path: Path,
) -> None:
    good, bad = tmp_path / "good.pdf", tmp_path / "bad.pdf"
    make_facade_pdf(good)
    make_facade_pdf(bad, dim_texts=("6000", "5000"))
    ref, probe = read_page(good), read_page(bad)
    assert probe.scale.mm_per_pt == ref.scale.mm_per_pt
    mismatches = [f for f in probe.findings if f.code == "dimension_mismatch"]
    assert len(mismatches) == 1
    data = mismatches[0].data
    assert data["axes"] == ["2", "3"] and data["written_mm"] == 5000.0
    assert data["measured_mm"] == pytest.approx(4500.0, abs=1.0)
    assert {c.axes: c.status for c in probe.dimension_checks}[
        ("2", "3")
    ] == "dimension_mismatch"


def test_level_marks_consistency_per_pair(tmp_path: Path) -> None:
    good, bad = tmp_path / "good.pdf", tmp_path / "bad.pdf"
    make_facade_pdf(good)
    make_facade_pdf(bad, level_texts=("±0.000", "+3.300", "+6.000"))
    checks = read_page(good).level_checks
    assert [(c.lower, c.upper, c.status) for c in checks] == [
        ("±0.000", "+3.000", "ok"),
        ("+3.000", "+6.000", "ok"),
    ]
    for c in checks:
        assert abs(c.measured_m - c.written_m) <= c.tolerance_m
    probe = read_page(bad)
    assert [c.status for c in probe.level_checks] == [
        "level_mismatch",
        "level_mismatch",
    ]
    pairs = [f.data["pair"] for f in probe.findings if f.code == "level_mismatch"]
    assert pairs == [["±0.000", "+3.300"], ["+3.300", "+6.000"]]


def test_raster_page_is_not_vector(tmp_path: Path, facade) -> None:
    path, _ = facade
    src = pymupdf.open(path)
    pix = src[0].get_pixmap(dpi=50)
    doc = pymupdf.open()
    page = doc.new_page(width=src[0].rect.width, height=src[0].rect.height)
    page.insert_image(page.rect, stream=pix.tobytes("png"))
    raster = tmp_path / "raster.pdf"
    doc.save(raster)
    reading = read_page(raster)
    assert reading.status == "not_vector"
    assert (reading.axes, reading.dimensions, reading.level_marks, reading.legend) == (
        [],
        [],
        [],
        [],
    )
    assert reading.scale.status == "unknown" and reading.scale.mm_per_pt is None
    assert "not_vector" in [f.code for f in reading.findings]


def test_text_as_outlines_is_no_text_layer(tmp_path: Path) -> None:
    path = tmp_path / "outlines.pdf"
    make_facade_pdf(path, with_text=False)
    reading = read_page(path)
    assert reading.status == "no_text_layer"
    assert reading.lines and not reading.spans
    assert (reading.axes, reading.dimensions, reading.level_marks, reading.legend) == (
        [],
        [],
        [],
        [],
    )
    assert reading.scale.status == "unknown"


def test_empty_page_is_empty(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page()
    path = tmp_path / "empty.pdf"
    doc.save(path)
    reading = read_page(path)
    assert reading.status == "empty" and reading.scale.status == "unknown"


def test_no_axis_dimension_scale_unknown_not_guessed(tmp_path: Path) -> None:
    path = tmp_path / "nodim.pdf"
    make_facade_pdf(path, with_dimensions=False)
    reading = read_page(path)
    assert (
        reading.status == "ok" and len(reading.axes) == 5 and reading.dimensions == []
    )
    assert reading.scale.status == "unknown" and reading.scale.mm_per_pt is None
    assert [c.status for c in reading.level_checks] == ["not_checked", "not_checked"]
    assert all(c.measured_m is None for c in reading.level_checks)
    assert "scale_unknown" in [f.code for f in reading.findings]


def test_requested_reference_axes_absent_scale_unknown(facade) -> None:
    path, _ = facade
    reading = read_page(path, scale_axes=("1", "3"))
    assert reading.scale.status == "unknown" and reading.scale.mm_per_pt is None
    assert "1-3" in reading.scale.reason
    assert [c.status for c in reading.dimension_checks] == [
        "not_checked",
        "not_checked",
    ]
    ok = read_page(path, scale_axes=("2", "3"))
    assert ok.scale.reference_axes == ("2", "3")
    assert abs(ok.scale.mm_per_pt / SCALE_1_100_MM_PER_PT - 1.0) < 0.001


@pytest.mark.parametrize("number", [0, 2, -1, 99])
def test_page_out_of_range_is_error(facade, number: int) -> None:
    path, _ = facade
    with pytest.raises(AlbumReadError, match="out of range") as err:
        read_page(path, number)
    assert err.value.reason == "page_out_of_range"


@pytest.mark.parametrize("number", [True, 1.0, "1", None])
def test_page_number_must_be_int(facade, number) -> None:
    path, _ = facade
    with pytest.raises(AlbumReadError) as err:
        read_page(path, number)
    assert err.value.reason == "bad_page_number"


def test_encrypted_file_is_error(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "x")
    path = tmp_path / "enc.pdf"
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="o", user_pw="u")
    with pytest.raises(AlbumReadError, match="encrypted") as err:
        read_page(path)
    assert err.value.reason == "encrypted"


@pytest.mark.parametrize(
    ("content", "reason"),
    [(b"this is not a pdf at all", "corrupt"), (b"", "corrupt"), (None, "not_found")],
)
def test_corrupt_empty_or_missing_file_is_error(
    tmp_path: Path, content, reason: str
) -> None:
    path = tmp_path / "broken.pdf"
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(AlbumReadError) as err:
        read_page(path)
    assert err.value.reason == reason
    assert str(err.value)


def test_missing_pymupdf_names_the_extra(monkeypatch, facade) -> None:
    path, _ = facade
    monkeypatch.setitem(sys.modules, "pymupdf", None)
    with pytest.raises(AlbumExtraMissing, match=r"uv run --extra pdf-review"):
        read_page(path)


def test_import_dt_ai_album_does_not_need_pymupdf() -> None:
    code = (
        "import sys; sys.modules['pymupdf'] = None; sys.modules['fitz'] = None\n"
        "import dt_ai, dt_ai.album\n"
        "try:\n    dt_ai.album.read_page('x.pdf')\n"
        "except dt_ai.album.AlbumExtraMissing as e:\n    print('EXTRA', e)\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=True,
    )
    assert "EXTRA" in out.stdout and "--extra pdf-review" in out.stdout
    assert "Traceback" not in out.stderr


def test_json_deterministic_and_provenance(tmp_path: Path) -> None:
    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    make_facade_pdf(a)
    make_facade_pdf(b)
    assert a.read_bytes() == b.read_bytes()
    one, two, other = (
        reading_to_json(read_page(a)),
        reading_to_json(read_page(a)),
        reading_to_json(read_page(b)),
    )
    assert one == two == other
    data = json.loads(one)
    import hashlib

    assert data["source"]["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()
    assert data["source"]["page_number"] == 1
    assert data["source"]["pymupdf_version"] == pymupdf.__version__ == "1.28.2"
    assert "Плитка светлая RAL 9010" in one  # Cyrillic kept, not \\u-escaped
    (tmp_path / "reading.json").write_text(one, encoding="utf-8")


def test_probe_generated_scales_and_spans(tmp_path: Path) -> None:
    """Invariant: scale within 0.1 %, true dimensions pass, a wrong text is flagged and never moves the scale."""
    rng = random.Random(317)
    for i in range(12):
        mm_per_pt = (
            rng.choice([50.0, 100.0, 200.0]) * 25.4 / 72.0 * rng.uniform(0.9, 1.1)
        )
        spans = (
            float(rng.randrange(3000, 7200, 300)),
            float(rng.randrange(1200, 6000, 300)),
        )
        good = tmp_path / f"g{i}.pdf"
        make_facade_pdf(good, mm_per_pt=mm_per_pt, spans_mm=spans)
        r = read_page(good)
        assert abs(r.scale.mm_per_pt / mm_per_pt - 1.0) < 0.001, (i, mm_per_pt, spans)
        assert [c.status for c in r.dimension_checks] == ["reference", "ok"]
        wrong = spans[1] + rng.choice([-1, 1]) * rng.choice([300.0, 600.0, 1500.0])
        bad = tmp_path / f"b{i}.pdf"
        make_facade_pdf(
            bad,
            mm_per_pt=mm_per_pt,
            spans_mm=spans,
            dim_texts=(f"{spans[0]:.0f}", f"{wrong:.0f}"),
        )
        rb = read_page(bad)
        assert rb.scale.mm_per_pt == r.scale.mm_per_pt
        assert [c.status for c in rb.dimension_checks] == [
            "reference",
            "dimension_mismatch",
        ]


def test_threshold_and_non_finite_checks_fail_closed() -> None:
    # tolerance for 4500 mm is max(10, 0.5 %) = 22.5 mm; exactly at it is a mismatch
    assert check_dimension(4500.0 + 22.5, 4500.0)[0] == "dimension_mismatch"
    assert check_dimension(4500.0 + 22.4, 4500.0)[0] == "ok"
    assert check_dimension(1000.0 + 10.0, 1000.0)[0] == "dimension_mismatch"
    for bad in (math.nan, math.inf, -math.inf):
        assert check_dimension(bad, 4500.0)[0] == "dimension_mismatch"
        assert check_dimension(4500.0, bad)[0] == "dimension_mismatch"
        assert check_level_pair(bad, 3.0)[0] == "level_mismatch"
    assert (
        check_level_pair(3.0 + 0.015, 3.0)[0] == "level_mismatch"
    )  # tol = max(0.010, 0.5 %) = 0.015
    assert check_level_pair(3.0 + 0.014, 3.0)[0] == "ok"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("±0.000", 0.0),
        ("+3.000", 3.0),
        ("-0.450", -0.45),
        ("\u22120.450", -0.45),
        ("+46.500", 46.5),
        ("+3,000", 3.0),
    ],
)
def test_level_text_parsing(text: str, value: float) -> None:
    assert parse_level_text(text) == value


@pytest.mark.parametrize(
    "text", ["±1.000", "3.0", "6000", "+3.00", "abc", "", "+3.000м"]
)
def test_level_text_rejects_non_marks(text: str) -> None:
    assert parse_level_text(text) is None


# --- review round 1 (P1): every dimension span is accounted for, independently of its text ---------------------

_COVERAGE_CODES = {
    "dimension_text_missing",
    "dimension_text_invalid",
    "dimension_text_unsupported",
}


def _move_text_below_line(src: Path, dst: Path, value: str = "4500") -> None:
    doc = pymupdf.open(src)
    page = doc[0]
    box = page.search_for(value)[0]
    page.add_redact_annot(box)
    page.apply_redactions(graphics=0)  # remove the text only, keep the line work
    page.insert_text((box.x0, 735), value)  # dimension line at y = 715: text below it
    doc.save(dst)
    doc.close()


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("NaN", "dimension_text_invalid"),
        ("4500.0", "dimension_text_invalid"),
        ("", "dimension_text_missing"),
        ("below", None),
    ],
)
def test_unread_dimension_span_is_a_typed_finding_and_keeps_scale(
    tmp_path: Path, text: str, code: str | None
) -> None:
    """Invariant: a dimension span (line + 2 ticks) whose value is not read is a finding with its endpoints."""
    good = tmp_path / "good.pdf"
    truth = make_facade_pdf(good)
    ref = read_page(good)
    probe = tmp_path / "probe.pdf"
    if text == "below":
        _move_text_below_line(good, probe)
    else:
        make_facade_pdf(probe, dim_texts=("6000", text))
    r = read_page(probe, scale_axes=("1", "2"))
    assert r.scale.status == "derived" and r.scale.mm_per_pt == ref.scale.mm_per_pt
    found = [f for f in r.findings if f.code in _COVERAGE_CODES]
    if text == "below":
        assert [d.axes for d in r.dimensions] == [("1", "2"), ("2", "3")]
        assert [d.value_mm for d in r.dimensions] == [6000.0, 4500.0]
        assert found == []
        return
    assert [d.axes for d in r.dimensions] == [("1", "2")]
    assert [f.code for f in found] == [code], r.findings
    data = found[0].data
    span = truth["dimensions"][1]
    assert _xy(data["p0"]) == pytest.approx(span["p0"], abs=0.01)
    assert _xy(data["p1"]) == pytest.approx(span["p1"], abs=0.01)
    assert data["axes"] == ["2", "3"]
    expected_text = {"": None, "below": "4500"}.get(text, text)
    assert data["text"] == expected_text


def test_clean_page_and_mismatch_control_have_no_coverage_findings(
    tmp_path: Path,
) -> None:
    """Control: a fully read page and a written-but-wrong value give no coverage finding."""
    good, bad = tmp_path / "good.pdf", tmp_path / "bad.pdf"
    make_facade_pdf(good)
    make_facade_pdf(bad, dim_texts=("6000", "5000"))
    r, rb = read_page(good), read_page(bad)
    assert len(r.dimensions) == 2 and r.findings == []
    assert [f.code for f in rb.findings] == ["dimension_mismatch"]
    assert rb.scale.mm_per_pt == r.scale.mm_per_pt


def test_unread_reference_span_leaves_scale_unknown(tmp_path: Path) -> None:
    """Invariant: when the reference span's value is unreadable the scale is unknown, not taken from another span."""
    path = tmp_path / "p.pdf"
    make_facade_pdf(path, dim_texts=("6000.0", "4500"))
    r = read_page(path, scale_axes=("1", "2"))
    assert r.scale.status == "unknown" and r.scale.mm_per_pt is None
    codes = [f.code for f in r.findings]
    assert "dimension_text_invalid" in codes and "scale_unknown" in codes
