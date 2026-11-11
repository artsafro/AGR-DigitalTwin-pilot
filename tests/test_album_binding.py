"""Album binding (#1234): views, horizontal/vertical chains, openings, levels, anchor calibration.

All PDFs here are SYNTHETIC, generated at test time with PyMuPDF (no committed PDF, no user album).
Run: env -u PYTHONPATH -u VIRTUAL_ENV uv run -q --extra pdf-review pytest -q tests/test_album_binding.py
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf", reason="optional extra 'pdf-review'")

from dt_ai.album import binding as B  # noqa: E402

PT = 0.05  # synthetic drawing: 1 pt = 20 mm (1:200 is NOT used by the binder)


def _font(page):
    page.insert_font(fontname="F0", fontbuffer=pymupdf.Font("cjk").buffer)
    return "F0"


def _bubble(shape, page, font, center, label, r=7.0, line_to=None):
    shape.draw_circle(center, r)
    shape.finish(color=(0, 0, 0), width=0.5)
    if line_to is not None:
        x, y = center
        if line_to[0] == x:
            start = (x, y - r) if line_to[1] < y else (x, y + r)
        else:
            start = (x - r, y) if line_to[0] < x else (x + r, y)
        shape.draw_line(start, line_to)
    shape.finish(color=(0, 0, 0), width=0.5)
    page.insert_text((center[0] - 2.5, center[1] + 3.0), label, fontsize=7, fontname=font)


def _hchain(shape, page, font, y, xs, texts):
    shape.draw_line((xs[0] - 6, y), (xs[-1] + 6, y))
    for x in xs:
        shape.draw_line((x - 1.5, y + 1.5), (x, y))  # tick drawn as two half strokes
        shape.draw_line((x, y), (x + 1.5, y - 1.5))
    shape.finish(color=(0, 0, 0), width=0.3)
    for (a, b), t in zip(zip(xs, xs[1:]), texts):
        if t is not None:
            page.insert_text(((a + b) / 2 - 8, y - 2.0), t, fontsize=6, fontname=font)


def _vchain(shape, page, font, x, ys, texts):
    shape.draw_line((x, ys[0] - 6), (x, ys[-1] + 6))
    for y in ys:
        shape.draw_line((x - 2, y + 2), (x + 2, y - 2))
    shape.finish(color=(0, 0, 0), width=0.3)
    for (a, b), t in zip(zip(ys, ys[1:]), texts):
        if t is not None:  # rotated 90 deg: reads bottom-to-top, left of the line
            page.insert_text((x - 2.0, (a + b) / 2 + 8), t, fontsize=6, fontname=font, rotate=90)


def make_pdf(path: Path, *, nominal=True, second_view=True, lone_number=True) -> Path:
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    font = _font(page)
    sh = page.new_shape()
    # facade view: axes 1,2,3 at x 100/220/400 (6000 mm/pt*0.05 -> 120 pt per 6000)
    xs = [100.0, 220.0, 400.0]
    sh.draw_rect(pymupdf.Rect(100, 100, 400, 250))
    sh.draw_rect(pymupdf.Rect(140, 150, 180, 230))  # opening (door) 40 pt = 800 mm wide, 80 pt high
    sh.finish(color=(0, 0, 0), width=0.5)
    for x, lab in zip(xs, "123"):
        sh.draw_line((x, 250), (x, 275))
    sh.finish(color=(0, 0, 0), width=0.3)
    _hchain(sh, page, font, 270.0, xs, ["6000", "9000"])
    _hchain(sh, page, font, 205.0 - 60, [140.0, 180.0], ["800"])  # opening width chain above the door top
    for x, lab in zip(xs, "123"):
        _bubble(sh, page, font, (x, 290.0), lab, line_to=(x, 276.0))
    # level marks on the right: +0.000 at y 250, +3.000 at y 190 (60 pt = 3000 mm)
    for y, t in ((250.0, "+0.000"), (190.0, "+3.000")):
        sh.draw_line((400, y), (470, y))
        sh.finish(color=(0, 0, 0), width=0.3)
        page.insert_text((448, y - 3.0), t, fontsize=6, fontname=font)
    _vchain(sh, page, font, 440.0, [190.0, 250.0], ["3000"])
    _vchain(sh, page, font, 120.0, [150.0, 230.0], ["1600"])  # opening height (door 80 pt = 1600 mm)
    if second_view:  # plan view far away with letter axes in a column
        ys = [380.0, 500.0]
        sh.draw_rect(pymupdf.Rect(620, 380, 760, 500))
        sh.finish(color=(0, 0, 0), width=0.5)
        for y, lab in zip(ys, "АБ"):
            _bubble(sh, page, font, (580.0, y), lab, line_to=(600.0, y))
        _vchain(sh, page, font, 610.0, ys, ["6000"])
    if nominal:
        page.insert_text((60, 40), "Фасад М 1:200", fontsize=8, fontname=font)
    if lone_number:
        page.insert_text((300, 560), "1685", fontsize=6, fontname=font)
    sh.commit()
    doc.save(path)
    return path


def _anchors(path: Path, anchors, sha="ab" * 32, kind="dwg") -> Path:
    path.write_text(json.dumps({"source": {"sha256": sha, "kind": kind, "path": "ref.dwg"}, "anchors": anchors}),
                    encoding="utf-8")
    return path


@pytest.fixture()
def pdf(tmp_path):
    return make_pdf(tmp_path / "album.pdf")


def _by(doc, raw, orient=None):
    return [v for v in doc["values"] if v["raw"] == raw and (orient is None or v["orientation"] == orient)]


def test_vertical_and_horizontal_chains_bind_to_axes_levels_openings(pdf):
    doc = B.bind_album(pdf)
    assert doc["schema"] == "album-dimensions/1" and doc["passed"] is False
    (h6000,) = _by(doc, "6000", "horizontal")
    assert h6000["binding"] == {"type": "axis_pair", "axes": ["1", "2"]}
    assert _by(doc, "9000")[0]["binding"]["axes"] == ["2", "3"]
    (v3000,) = _by(doc, "3000", "vertical")
    assert v3000["binding"] == {"type": "level_pair", "levels": ["+0.000", "+3.000"]}
    (v6000,) = _by(doc, "6000", "vertical")
    assert v6000["binding"] == {"type": "axis_pair", "axes": ["А", "Б"]}
    assert v6000["view"] != h6000["view"]  # two views on one page
    (w,) = _by(doc, "800")
    (hgt,) = _by(doc, "1600", "vertical")
    assert w["binding"]["type"] == "opening" and hgt["binding"] == w["binding"]
    assert doc["openings"][0]["id"] == w["binding"]["opening"]


def test_every_value_carries_view_page_bbox_and_binding_or_reason(pdf):
    doc = B.bind_album(pdf)
    assert doc["values"]
    for v in doc["values"]:
        assert v["page"] == 1 and "sheet" in v and len(v["bbox"]) == 4
        assert v["binding"]["type"] in {"axis_pair", "opening", "level_pair", "level", "unbound"}
        if v["binding"]["type"] == "unbound":
            assert v["binding"]["reason"] and v["status"] == "unresolved"
        else:
            assert v["view"]
    (lone,) = _by(doc, "1685")
    assert lone["binding"] == {"type": "unbound", "reason": "no_dimension_line"}


def test_without_anchors_scale_unknown_and_nominal_print_scale_never_used(pdf):
    doc = B.bind_album(pdf)
    assert all(vw["scale"]["status"] == "unknown" and vw["scale"]["mm_per_pt"] is None for vw in doc["views"])
    assert doc["nominal_print_scale_text"] and not any(t["used_for_calibration"] for t in doc["nominal_print_scale_text"])
    assert all(v["measured_mm"] is None for v in doc["values"])
    assert "calibration" in doc["open_gates"]
    assert all(v["status"] == "unresolved" for v in doc["values"] if v["kind"] == "dimension")


def test_two_independent_anchors_calibrate_with_residuals(pdf, tmp_path):
    a = _anchors(tmp_path / "a.json", [{"page": 1, "axes": ["1", "2"], "model_mm": 6000},
                                       {"page": 1, "axes": ["2", "3"], "model_mm": 9000}])
    doc = B.bind_album(pdf, anchors=a)
    (h6000,) = _by(doc, "6000", "horizontal")
    view = next(vw for vw in doc["views"] if vw["id"] == h6000["view"])
    sc = view["scale"]
    assert sc["status"] == "calibrated" and sc["mm_per_pt"] == pytest.approx(50.0, rel=1e-3)
    assert len(sc["anchors"]) == 2 and all("residual_mm" in u and u["residual_ok"] for u in sc["anchors"])
    other = next(vw for vw in doc["views"] if vw["id"] != h6000["view"] and vw["axes"])
    assert other["scale"]["status"] == "unknown"  # anchors are per view, never borrowed


def test_door_written_800_but_drawn_2000_is_a_kept_mismatch(pdf, tmp_path):
    a = _anchors(tmp_path / "a.json", [{"page": 1, "axes": ["1", "2"], "model_mm": 6000},
                                       {"page": 1, "axes": ["2", "3"], "model_mm": 9000}])
    doc = B.bind_album(pdf, anchors=a)
    (w,) = _by(doc, "800")
    assert w["check"] == "mismatch" and w["value"] == 800.0  # D112: written value kept, finding raised
    assert any(f["code"] == "dimension_mismatch" and f["id"] == w["id"] for f in doc["findings"])
    assert doc["passed"] is False


@pytest.mark.parametrize(
    "anchors,reason",
    [
        ([{"page": 1, "axes": ["1", "2"], "model_mm": 6000}], "1 independent"),
        ([{"page": 1, "axes": ["1", "2"], "model_mm": 6000}, {"page": 1, "axes": ["2", "1"], "model_mm": 6000}], "1 independent"),
        ([{"page": 1, "axes": ["1", "2"], "model_mm": 6000}, {"page": 1, "axes": ["2", "3"], "model_mm": 12000}], "residuals"),
    ],
)
def test_single_duplicate_or_disagreeing_anchors_leave_scale_unknown(pdf, tmp_path, anchors, reason):
    doc = B.bind_album(pdf, anchors=_anchors(tmp_path / "a.json", anchors))
    (h6000,) = _by(doc, "6000", "horizontal")
    sc = next(vw for vw in doc["views"] if vw["id"] == h6000["view"])["scale"]
    assert sc["status"] == "unknown" and reason in sc["reason"] and sc["mm_per_pt"] is None
    assert h6000["measured_mm"] is None and h6000["status"] == "unresolved"


def test_residual_exactly_at_tolerance_fails():
    spans = [
        {"id": "a", "binding": {"type": "axis_pair", "axes": ["1", "2"]}, "span": {"p0": [0, 0], "p1": [100, 0], "length_pt": 100.0}},
        {"id": "b", "binding": {"type": "axis_pair", "axes": ["2", "3"]}, "span": {"p0": [100, 0], "p1": [200, 0], "length_pt": 100.0}},
    ]
    # equal lengths: LS scale = mean, residuals = +-(m2 - m1) / 2; tolerance max(10 mm, 0.5 %)
    out = B.calibrate_view(spans, [{"axes": ["1", "2"], "model_mm": 1995.0}, {"axes": ["2", "3"], "model_mm": 2005.0}])
    assert out["status"] == "calibrated" and abs(out["anchors"][0]["residual_mm"]) == pytest.approx(5.0)
    out = B.calibrate_view(spans, [{"axes": ["1", "2"], "model_mm": 1980.0}, {"axes": ["2", "3"], "model_mm": 2000.0}])
    assert out["status"] == "unknown" and "residuals" in out["reason"]  # |residual| == 10 == tolerance
    nan = [dict(spans[0], span={**spans[0]["span"], "length_pt": float("nan")}), spans[1]]
    out = B.calibrate_view(nan, [{"axes": ["1", "2"], "model_mm": 2000.0}, {"axes": ["2", "3"], "model_mm": 2000.0}])
    assert out["status"] == "unknown"


@pytest.mark.parametrize(
    "payload,reason",
    [
        ({"source": {"sha256": "PDF", "kind": "dwg"}, "anchors": []}, "anchors_not_independent"),
        ({"source": {"kind": "dwg"}, "anchors": []}, "anchors_source_missing"),
        ({"source": {"sha256": "ab" * 32, "kind": "pdf"}, "anchors": []}, "anchors_source_kind"),
        ({"source": {"sha256": "ab" * 32, "kind": "dwg"}, "anchors": [{"page": 1, "axes": ["1", "2"], "model_mm": float("nan")}]}, "anchor_value"),
        ({"source": {"sha256": "ab" * 32, "kind": "dwg"}, "anchors": [{"page": 1, "axes": ["1", "2"], "model_mm": 0}]}, "anchor_value"),
        ({"source": {"sha256": "ab" * 32, "kind": "dwg"}, "anchors": [{"page": 1, "axes": ["1", "1"], "model_mm": 5}]}, "anchor_axes"),
        ({"source": {"sha256": "ab" * 32, "kind": "dwg"}, "anchors": [{"page": 9, "axes": ["1", "2"], "model_mm": 5}]}, "anchor_page"),
    ],
)
def test_bad_anchor_files_are_errors(pdf, tmp_path, payload, reason):
    if payload["source"].get("sha256") == "PDF":
        payload["source"]["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    p = tmp_path / "a.json"
    p.write_text(json.dumps(payload).replace("NaN", "NaN"), encoding="utf-8")
    with pytest.raises(B.BindingError) as exc:
        B.bind_album(pdf, anchors=p)
    assert exc.value.reason == reason


def test_bad_pages_and_missing_inputs(pdf, tmp_path):
    from dt_ai.album.reader import AlbumReadError

    for pages in ([], [1, 1], [2], [0], [True]):
        with pytest.raises(AlbumReadError):
            B.bind_album(pdf, pages)
    with pytest.raises(AlbumReadError):
        B.bind_album(tmp_path / "missing.pdf")
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(AlbumReadError):
        B.bind_album(bad)


def test_blank_page_is_not_bound(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    doc.save(tmp_path / "blank.pdf")
    out = B.bind_album(tmp_path / "blank.pdf")
    assert out["pages"][0]["status"] == "empty" and out["values"] == [] and out["passed"] is False
    assert "calibration" in out["open_gates"]


def test_cli_refuses_output_alias_and_existing_output_fresh_process(pdf, tmp_path):
    before = pdf.read_bytes()
    cmd = [sys.executable, "-m", "dt_ai.album.binding", str(pdf), "--output"]
    r = subprocess.run(cmd + [str(pdf)], capture_output=True, text=True)
    assert r.returncode == 2 and "output_is_input" in r.stdout and pdf.read_bytes() == before
    existing = tmp_path / "out.json"
    existing.write_text("keep", encoding="utf-8")
    r = subprocess.run(cmd + [str(existing)], capture_output=True, text=True)
    assert r.returncode == 2 and existing.read_text(encoding="utf-8") == "keep"
    out = tmp_path / "dimensions.json"
    r = subprocess.run(cmd + [str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["passed"] is False and data["summary"]["values"] == len(data["values"])


def test_generated_pages_never_pass_and_never_drop_number_tokens(tmp_path):
    """Probe: 40 random facades -> passed false, every >=3-digit token is a value, scale unknown w/o anchors."""
    rng = random.Random(1234)
    for k in range(40):
        doc = pymupdf.open()
        page = doc.new_page(width=842, height=595)
        font = _font(page)
        sh = page.new_shape()
        n = rng.randint(2, 6)
        xs = sorted(rng.sample(range(60, 780, 20), n))
        xs = [float(x) for x in xs]
        texts = [str(rng.randint(100, 99999)) if rng.random() > 0.2 else None for _ in xs[1:]]
        _hchain(sh, page, font, 300.0, xs, texts)
        ys = [float(y) for y in sorted(rng.sample(range(60, 280, 20), 3))]
        vt = [str(rng.randint(100, 9999)) for _ in ys[1:]]
        _vchain(sh, page, font, 40.0, ys, vt)
        sh.commit()
        path = tmp_path / f"g{k}.pdf"
        doc.save(path)
        out = B.bind_album(path)
        assert out["passed"] is False
        raws = [v["raw"] for v in out["values"]]
        for t in [t for t in texts if t] + vt:
            assert t in raws, (k, t)
        assert all(v["measured_mm"] is None for v in out["values"])
        assert all(vw["scale"]["status"] == "unknown" for vw in out["views"])
        assert sum(1 for v in out["values"] if v["orientation"] == "vertical") == len(vt)
        assert all(math.isfinite(v["value"]) for v in out["values"] if v["value"] is not None)
