"""new-case: transformed compound axis loops and bidirectional level-symbol regression (#1254).

All documents in this module are synthetic.
"""

import math

import pytest

pymupdf = pytest.importorskip("pymupdf")
from dt_ai.album import binding as B


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_polygon_axis_in_nested_xobject(tmp_path, rotation):
    source = pymupdf.open()
    p = source.new_page(width=300, height=200)
    sh = p.new_shape()
    for x, label in [(80, "1"), (220, "4")]:
        pts = [
            (x + 10 * math.cos(k * math.pi / 8), 160 + 10 * math.sin(k * math.pi / 8))
            for k in range(17)
        ]
        sh.draw_polyline(pts)
        sh.draw_line((x, 150), (x, 70))
        p.insert_text((x - 3, 163), label, fontsize=8)
    # Both bubbles and lines deliberately share one path, as in the real DWG plot.
    sh.finish(color=(0, 0, 0))
    sh.commit()
    nested = pymupdf.open()
    page = nested.new_page(width=600, height=600)
    page.show_pdf_page(pymupdf.Rect(50, 50, 550, 550), source, 0, rotate=rotation)
    final = pymupdf.open()
    page = final.new_page(width=700, height=700)
    page.show_pdf_page(pymupdf.Rect(20, 20, 650, 650), nested, 0)
    path = tmp_path / "nested.pdf"
    final.save(path)
    result = B.bind_album(path)
    axes = [a for v in result["views"] for a in v["axes"]]
    assert sorted(a["label"] for a in axes) == ["1", "4"]
    assert all(
        a["orientation"] == ("vertical" if rotation % 180 == 0 else "horizontal")
        for a in axes
    )
    assert result["passed"] is False
    assert all(v["scale"]["status"] == "unknown" for v in result["views"])


@pytest.mark.parametrize("up", [False, True])
@pytest.mark.parametrize("factor", [0.6, 1, 2, 3])
def test_scaled_level_with_stem_in_either_direction(tmp_path, up, factor):
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=600)
    x, shelf = 120.0, 180.0
    y = shelf + (-14.6 if up else 14.6) * factor
    sh = page.new_shape()
    sh.draw_line((x - 38 * factor, shelf), (x, shelf))
    sh.draw_line((x, shelf), (x, y))
    arm_y = y + (6 if up else -6) * factor
    sh.draw_line((x - 6 * factor, arm_y), (x, y))
    sh.draw_line((x, y), (x + 6 * factor, arm_y))
    sh.draw_line((x - 9 * factor, y), (x + 80 * factor, y))
    sh.finish(color=(0, 0, 0))
    sh.commit()
    page.insert_text(
        (x - 32 * factor, shelf - 2 * factor), "+6.650", fontsize=9 * factor
    )
    path = tmp_path / "level.pdf"
    doc.save(path)
    result = B.bind_album(path)
    bound = [v for v in result["values"] if v["binding"]["type"] == "level"]
    assert len(bound) == 1
    assert bound[0]["level_y"] == pytest.approx(y, abs=0.02)


def test_dimension_short_connectors_keep_native_tick_endpoints(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page(width=500, height=300)
    sh = p.new_shape()
    for a, b in [
        (100, 103),
        (103, 197),
        (197, 200),
        (200, 203),
        (203, 347),
        (347, 350),
    ]:
        sh.draw_line((a, 200), (b, 200))
    for x in [100, 200, 350]:
        sh.draw_line((x - 2, 202), (x + 2, 198))
    sh.finish(color=(0, 0, 0))
    sh.commit()
    p.insert_text((140, 197), "2000", fontsize=8)
    p.insert_text((265, 197), "3000", fontsize=8)
    path = tmp_path / "connectors.pdf"
    doc.save(path)
    result = B.bind_album(path)
    dims = [v for v in result["values"] if v["kind"] == "dimension" and v["span"]]
    assert [(v["value"], v["span"]["length_pt"]) for v in dims] == [
        (2000, 100),
        (3000, 150),
    ]


@pytest.mark.parametrize("delta", [0, 5, 10, 20, 50, 100, -5, -20, -50])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_split_bezier_axis_arcs(tmp_path, delta, rotation):
    doc = pymupdf.open()
    p = doc.new_page(width=400, height=300)
    for cx, label in [(100, "1"), (300, "4")]:
        k = 5.522847498
        for sign in [1, -1]:
            sh = p.new_shape()
            sh.draw_bezier(
                (cx - 10, 200),
                (cx - 10 + delta, 200 + sign * k),
                (cx - k - delta, 200 + sign * 10),
                (cx, 200 + sign * 10),
            )
            sh.draw_bezier(
                (cx, 200 + sign * 10),
                (cx + k + delta, 200 + sign * 10),
                (cx + 10 - delta, 200 + sign * k),
                (cx + 10, 200),
            )
            sh.finish(color=(0, 0, 0), closePath=False)
            sh.commit()
        p.insert_text((cx - 3, 203), label, fontsize=8)
        p.draw_line((cx, 190), (cx, 100))
    # Opposite control shifts cancel at t=.5 and preserve every endpoint,
    # but not the curve. Exercise serialized paths, including Form transforms.
    if rotation:
        nested = pymupdf.open()
        page = nested.new_page(width=500, height=500)
        page.show_pdf_page(pymupdf.Rect(20, 20, 480, 480), doc, 0, rotate=rotation)
        doc = nested
    path = tmp_path / "split-arcs.pdf"
    doc.save(path)
    r = B.bind_album(path)
    assert sorted(a["label"] for v in r["views"] for a in v["axes"]) == (
        ["1", "4"] if delta == 0 else []
    )
    assert not r["passed"]
    assert all(v["scale"]["status"] == "unknown" for v in r["views"])


@pytest.mark.parametrize("mode", ["ellipse", "open", "two_labels"])
def test_non_bubbles_never_become_axes(tmp_path, mode):
    doc = pymupdf.open()
    p = doc.new_page(width=400, height=300)
    sh = p.new_shape()
    for x in [100, 300]:
        count = 16 if mode != "open" else 12
        pts = [
            (
                x + 10 * math.cos(k * math.pi / 8),
                200 + (16 if mode == "ellipse" else 10) * math.sin(k * math.pi / 8),
            )
            for k in range(count + 1)
        ]
        sh.draw_polyline(pts)
        p.insert_text((x - 3, 203), "1", fontsize=8)
        if mode == "two_labels":
            p.insert_text((x + 3, 203), "2", fontsize=8)
    sh.finish(color=(0, 0, 0), closePath=False)
    sh.commit()
    path = tmp_path / "not-bubbles.pdf"
    doc.save(path)
    r = B.bind_album(path)
    assert not [a for v in r["views"] for a in v["axes"]]
    assert not r["passed"]


def test_cubic_annulus_certificate_fail_closed():
    """Exercise numerical certificate boundaries independently of PDF encoding."""
    from dt_ai.album.reader import _cubic_in_annulus

    for value in [0.98, 1.02, float("nan"), float("inf"), -float("inf")]:
        assert not _cubic_in_annulus(("c", *((value, 0),) * 4), (0, 0), 1)
    assert _cubic_in_annulus(("c", *((1, 0),) * 4), (0, 0), 1)
    for radius in [0, -1, float("nan"), float("inf")]:
        assert not _cubic_in_annulus(("c", *((1, 0),) * 4), (0, 0), radius)
    # Endpoints are valid, but the entire interior cannot be certified.
    assert not _cubic_in_annulus(("c", (1, 0), (-1, 0), (-1, 0), (1, 0)), (0, 0), 1)


def test_generated_cubic_certificates_have_no_hidden_radial_excursions():
    import random
    from dt_ai.album.reader import _cubic_in_annulus

    rng = random.Random(1254)
    accepted = 0
    for _ in range(200):
        noise = rng.choice([0.001, 0.01, 0.2, 2.0])
        k = 0.5522847498
        pts = [(1, 0), (1, k), (k, 1), (0, 1)]
        pts[1:3] = [(x + rng.uniform(-noise, noise), y + rng.uniform(-noise, noise))
                    for x, y in pts[1:3]]
        if not _cubic_in_annulus(("c", *pts), (0, 0), 1):
            continue
        accepted += 1
        # Independent dense evaluation is a negative oracle, not the certificate.
        for step in range(1001):
            t = step / 1000
            weights = ((1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3)
            xy = [sum(w*p[j] for w, p in zip(weights, pts)) for j in (0, 1)]
            assert 0.98 < math.hypot(*xy) < 1.02
    assert accepted >= 50  # prevent an always-refuse implementation passing


def test_plan_boxed_spot_is_not_an_elevation_line(tmp_path):
    doc = pymupdf.open()
    p = doc.new_page(width=500, height=300)
    for x, y, text in [
        (80, 80, "+13.920"),
        (280, 150, "+12.070"),
        (160, 220, "+15.420"),
    ]:
        p.draw_rect(pymupdf.Rect(x - 4, y - 14, x + 45, y + 4), color=(0, 0, 0))
        p.insert_text((x, y), text, fontsize=10)
    p.insert_text((350, 250), "+99.999", fontsize=10)  # unboxed -> unresolved
    path = tmp_path / "roof.pdf"
    doc.save(path)
    r = B.bind_album(path)
    spots = [v for v in r["values"] if v["binding"]["type"] == "spot_level"]
    assert len(spots) == 3
    assert all(v["level_y"] is None and v["measured_mm"] is None for v in spots)
    assert all("spot_bbox" in v["binding"] for v in spots)
    assert (
        next(v for v in r["values"] if v["raw"] == "+99.999")["binding"]["type"]
        == "unbound"
    )
    assert not r["passed"]
