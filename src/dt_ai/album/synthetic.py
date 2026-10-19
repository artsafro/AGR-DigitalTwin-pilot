"""SYNTHETIC facade sheet generator for the album reader tests (#317).

Everything this module writes is synthetic test data, never a real album and never customer acceptance.
The page is drawn with PyMuPDF itself: 3 vertical axes ``1``-``3`` and 2 horizontal axes ``А``, ``Б`` in
bubbles, a horizontal dimension chain with ticks, level marks with a triangle symbol and a 4-row legend
(filled swatch + Cyrillic label). The function returns the ground truth the reader must recover.

Requires the optional extra: ``uv run --extra pdf-review ...``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

#: 1:100 drawing: one PDF point is 25.4/72 mm of paper, i.e. 35.2777... mm of the model.
SCALE_1_100_MM_PER_PT = 100.0 * 25.4 / 72.0

LEGEND_ROWS: tuple[tuple[tuple[int, int, int], str], ...] = (
    ((236, 228, 210), "Плитка светлая RAL 9010"),
    ((88, 72, 60), "Плитка тёмная RAL 8022"),
    ((201, 185, 154), "Штукатурка окрашенная"),
    ((150, 155, 160), "Профиль алюминиевый"),
)

_BLACK = (0.0, 0.0, 0.0)
_DASH_DOT = "[12 3 2 3] 0"


def _font(page: Any, pymupdf: Any) -> str:
    page.insert_font(fontname="F0", fontbuffer=pymupdf.Font("cjk").buffer)
    return "F0"


def make_facade_pdf(
    path: str | Path,
    *,
    mm_per_pt: float = SCALE_1_100_MM_PER_PT,
    spans_mm: tuple[float, float] = (6000.0, 4500.0),
    dim_texts: tuple[str, str] | None = None,
    levels_m: tuple[float, ...] = (0.0, 3.0, 6.0),
    level_texts: tuple[str, ...] | None = None,
    with_text: bool = True,
    with_dimensions: bool = True,
) -> dict[str, Any]:
    """Write a SYNTHETIC one-page facade sheet and return its ground truth (page coordinates in pt).

    ``dim_texts`` overrides the written dimension values (probe for ``dimension_mismatch``);
    ``level_texts`` overrides the written level values; ``with_text=False`` draws the same vector
    line work without any text layer (text as outlines probe).
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=1190, height=842)  # A3 landscape
    font = _font(page, pymupdf) if with_text else ""
    shape = page.new_shape()

    def text(point: tuple[float, float], value: str, size: float = 9.0) -> None:
        if with_text:
            page.insert_text(point, value, fontsize=size, fontname=font)
        else:  # outlines stand-in: a small stroked box where the glyphs would be
            shape.draw_rect(
                pymupdf.Rect(
                    point[0],
                    point[1] - size * 0.7,
                    point[0] + size * 0.6 * len(value),
                    point[1],
                )
            )
            shape.finish(color=_BLACK, width=0.2)

    radius = 12.0
    x1 = 200.0
    xs = [
        x1,
        x1 + spans_mm[0] / mm_per_pt,
        x1 + (spans_mm[0] + spans_mm[1]) / mm_per_pt,
    ]
    y_ground = 640.0
    level_ys = [y_ground - (v - levels_m[0]) * 1000.0 / mm_per_pt for v in levels_m]
    top = min(level_ys) - 60.0
    bubble_y = 780.0
    axes: list[dict[str, Any]] = []
    for label, x in zip(("1", "2", "3"), xs, strict=True):
        shape.draw_circle((x, bubble_y), radius)
        shape.finish(color=_BLACK, width=0.5)
        shape.draw_line((x, bubble_y - radius), (x, top))
        shape.finish(color=_BLACK, width=0.3, dashes=_DASH_DOT)
        text((x - 2.5, bubble_y + 3.2), label)
        axes.append({"label": label, "orientation": "vertical", "position": x})
    bubble_x = 110.0
    for label, y in zip(("А", "Б"), (300.0, 380.0), strict=True):
        shape.draw_circle((bubble_x, y), radius)
        shape.finish(color=_BLACK, width=0.5)
        shape.draw_line((bubble_x + radius, y), (xs[-1] + 40.0, y))
        shape.finish(color=_BLACK, width=0.3, dashes=_DASH_DOT)
        text((bubble_x - 3.0, y + 3.2), label)
        axes.append({"label": label, "orientation": "horizontal", "position": y})

    # facade outline (vector context, not an extracted item)
    shape.draw_rect(pymupdf.Rect(xs[0], min(level_ys) - 20.0, xs[-1], y_ground))
    shape.finish(color=_BLACK, width=0.7)

    dims: list[dict[str, Any]] = []
    if with_dimensions:
        y_dim = 715.0
        shape.draw_line((xs[0] - 10.0, y_dim), (xs[-1] + 10.0, y_dim))
        shape.finish(color=_BLACK, width=0.3)
        for x in xs:
            shape.draw_line((x - 3.0, y_dim + 3.0), (x + 3.0, y_dim - 3.0))
            shape.finish(color=_BLACK, width=0.6)
            shape.draw_line((x, y_dim - 8.0), (x, y_dim + 8.0))
            shape.finish(color=_BLACK, width=0.2)
        written = dim_texts or tuple(f"{v:.0f}" for v in spans_mm)
        for i, value in enumerate(written):
            mid = (xs[i] + xs[i + 1]) / 2.0
            text((mid - 2.5 * len(value), y_dim - 2.5), value)
            dims.append(
                {
                    "text": value,
                    "axes": [str(i + 1), str(i + 2)],
                    "p0": (xs[i], y_dim),
                    "p1": (xs[i + 1], y_dim),
                }
            )

    levels: list[dict[str, Any]] = []
    x_mark = xs[0] - 40.0
    texts = level_texts or tuple(
        ("±0.000" if v == 0 else f"{v:+.3f}") for v in levels_m
    )
    for value, y, label in zip(levels_m, level_ys, texts, strict=True):
        shape.draw_polyline(
            [(x_mark, y), (x_mark - 4.0, y - 7.0), (x_mark + 4.0, y - 7.0)]
        )
        shape.finish(color=_BLACK, width=0.4, closePath=True)
        shape.draw_line((x_mark - 4.0, y), (xs[0], y))  # leader to the facade
        shape.finish(color=_BLACK, width=0.2)
        shape.draw_line((x_mark + 4.0, y - 7.0), (x_mark + 34.0, y - 7.0))  # shelf
        shape.finish(color=_BLACK, width=0.2)
        text((x_mark + 5.0, y - 9.0), label, 8.0)
        levels.append({"text": label, "value_m": value, "y": y})

    legend: list[dict[str, Any]] = []
    lx, ly = 820.0, 140.0
    text((lx, ly - 15.0), "Условные обозначения", 10.0)
    for i, (rgb, label) in enumerate(LEGEND_ROWS):
        top_y = ly + i * 28.0
        rect = pymupdf.Rect(lx, top_y, lx + 30.0, top_y + 15.0)
        shape.draw_rect(rect)
        shape.finish(color=_BLACK, fill=tuple(c / 255.0 for c in rgb), width=0.4)
        text((lx + 40.0, top_y + 11.0), label)
        legend.append({"label": label, "rgb255": list(rgb), "rect": tuple(rect)})
    shape.commit()
    if with_text:
        doc.subset_fonts()
    doc.save(str(path), garbage=3, deflate=True, no_new_id=True)
    doc.close()
    return {
        "synthetic": True,
        "mm_per_pt": mm_per_pt,
        "axes": axes,
        "dimensions": dims,
        "levels": levels,
        "legend": legend,
    }
