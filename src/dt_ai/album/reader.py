"""Vector PDF album page reader (#317, kernel C5; decisions D127, D112, D125, D108).

Pattern: n/a | new-case: read one vector PDF album page (axes, dimensions, level marks, legend, scale) with PyMuPDF.

``read_page`` reads ONE page of a vector PDF with PyMuPDF (optional extra ``pdf-review``) and returns a typed,
JSON-serialisable :class:`PageReading`: the drawn paths and line segments, the text runs with page coordinates
(PDF points, origin top-left, y down, as PyMuPDF reports them) and the items extracted from them. PyMuPDF is
imported lazily; without it ``read_page`` raises :class:`AlbumExtraMissing` naming
``uv run --extra pdf-review ...`` and ``import dt_ai.album`` still works.

Fail-closed (D108): a page without vector line work is ``not_vector`` (raster / scan), vector line work without
any text is ``no_text_layer`` (text as outlines), a blank page is ``empty``; for these no item is extracted and
the scale is ``unknown``. A missing file, an empty / corrupt / encrypted file and a page number out of range
raise :class:`AlbumReadError` with ``reason``. The scale is never guessed: without a dimension between two named
axes it is ``unknown`` and no dimension or level check runs (status ``not_checked``). A dimension or level that
disagrees with the drawing is a finding (``dimension_mismatch`` / ``level_mismatch``); per D112 the album value is
kept and the discrepancy is reported, never corrected, and a mismatching dimension never changes the scale.

Assumptions (Russian album conventions, stated per #317):
- Axes: a stroked circle (bubble, Bezier curves) holding exactly one label run, with a straight horizontal or
  vertical line starting on the bubble edge and running radially away from it. Labels are digits (``1``,
  ``1.2``) for vertical axis lines and Cyrillic capitals without Ё, З, Й, О, Х, Ъ, Ы, Ь (optionally with a
  number, ``А1``) for horizontal ones; a break of that convention or a forbidden letter is a finding, not an error.
- Dimensions: horizontal dimension lines (chains allowed) with slanted ~45 deg ticks; the value is an integer in
  mm (``6000`` or ``26 369``) written above the line between two consecutive ticks; the endpoints are the tick
  centres. Vertical dimension chains and values written below the line are not read in this version.
- Level marks: values in metres with exactly three decimals (``±0.000``, ``+3.000``, ``-0.450``, comma or
  Unicode minus accepted; ``±`` only for zero) next to a triangle symbol; the mark's page Y is the triangle apex.
  Level checks assume one elevation per page (all marks share one vertical scale).
- Legend: a filled axis-aligned rectangle (swatch, 4-60 x 3-30 pt) with a text run starting to its right on the
  same row; the label is the whole run (words split by normal spaces stay together).
- Scale: model mm per PDF point = written value / measured tick distance of one axis dimension (``scale_axes``
  or, by default, the left-most dimension whose both ends sit on named vertical axes, within 0.5 pt). The same
  scale is used for heights (level marks). Tolerances: dimension max(10 mm, 0.5 %), level max(0.010 m, 0.5 %);
  a difference equal to the tolerance or a non-finite value is a mismatch.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EXTRA_HINT = (
    "PyMuPDF is not installed: the album reader needs the optional extra 'pdf-review'; "
    "run it with `uv run --extra pdf-review ...`"
)

DIM_ABS_TOL_MM = 10.0
DIM_REL_TOL = 0.005
LEVEL_ABS_TOL_M = 0.010
LEVEL_REL_TOL = 0.005
AXIS_SNAP_PT = 0.5

Point = tuple[float, float]
Box = tuple[float, float, float, float]

_FORBIDDEN_AXIS_LETTERS = set("ЁЗЙОХЪЫЬ")
_AXIS_LABEL = re.compile(r"^(?:\d+(?:[./]\d+)?|[А-ЯЁ](?:[./]?\d+)?)$")
_DIM_TEXT = re.compile(r"^(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)$")
_LEVEL_TEXT = re.compile(r"^([±+\-\u2212]?)(\d+)[.,](\d{3})$")


class AlbumReadError(ValueError):
    """The page cannot be read; ``reason`` is a stable code (not_found, corrupt, encrypted, page_out_of_range...)."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason


class AlbumExtraMissing(RuntimeError):
    """PyMuPDF (extra ``pdf-review``) is not installed."""


@dataclass(frozen=True)
class TextRun:
    text: str
    bbox: Box
    origin: Point
    size: float
    font: str
    dir: Point


@dataclass(frozen=True)
class Segment:
    p0: Point
    p1: Point
    width: float
    stroke: tuple[float, ...] | None
    path: int


@dataclass(frozen=True)
class DrawnPath:
    index: int
    kinds: str
    bbox: Box
    stroke: tuple[float, ...] | None
    fill: tuple[float, ...] | None
    width: float
    closed: bool
    dashes: str


@dataclass(frozen=True)
class Axis:
    label: str
    orientation: str  # "vertical" (x = position) or "horizontal" (y = position)
    position: float
    bubble_center: Point
    bubble_radius: float
    line_p0: Point  # on the bubble edge
    line_p1: Point


@dataclass(frozen=True)
class Dimension:
    text: str
    value_mm: float
    p0: Point
    p1: Point
    measured_pt: float
    axes: tuple[str, str] | None
    text_bbox: Box


@dataclass(frozen=True)
class LevelMark:
    text: str
    value_m: float
    y: float
    apex: Point
    symbol_bbox: Box
    text_bbox: Box


@dataclass(frozen=True)
class LegendItem:
    label: str
    rgb: tuple[float, float, float]
    rgb255: tuple[int, int, int]
    swatch: Box


@dataclass(frozen=True)
class Scale:
    status: str  # "derived" | "unknown"
    mm_per_pt: float | None
    reference_axes: tuple[str, str] | None
    reference_mm: float | None
    reason: str


@dataclass(frozen=True)
class DimensionCheck:
    text: str
    axes: tuple[str, str] | None
    written_mm: float
    measured_mm: float | None
    tolerance_mm: float | None
    status: str  # reference | ok | dimension_mismatch | not_checked


@dataclass(frozen=True)
class LevelCheck:
    lower: str
    upper: str
    written_m: float
    measured_m: float | None
    tolerance_m: float | None
    status: str  # ok | level_mismatch | not_checked


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Source:
    sha256: str
    page_number: int
    page_count: int
    page_size: Point
    pymupdf_version: str


@dataclass(frozen=True)
class PageReading:
    source: Source
    status: str  # ok | not_vector | no_text_layer | empty
    paths: list[DrawnPath]
    lines: list[Segment]
    spans: list[TextRun]
    axes: list[Axis]
    dimensions: list[Dimension]
    level_marks: list[LevelMark]
    legend: list[LegendItem]
    scale: Scale
    dimension_checks: list[DimensionCheck]
    level_checks: list[LevelCheck]
    findings: list[Finding]
    synthetic_note: str = (
        "reading of a PDF page; technical extraction only, not acceptance"
    )

    def to_dict(self) -> dict[str, Any]:
        return _normalise(asdict(self))


# ---------------------------------------------------------------- pure checks


def _finite(*values: float | None) -> bool:
    return all(
        v is not None and isinstance(v, (int, float)) and math.isfinite(v)
        for v in values
    )


def check_dimension(measured_mm: float, written_mm: float) -> tuple[str, float | None]:
    """Return (status, tolerance_mm); tolerance max(10 mm, 0.5 %); |diff| >= tolerance or non-finite -> mismatch."""
    if not _finite(measured_mm, written_mm):
        return "dimension_mismatch", None
    tol = max(DIM_ABS_TOL_MM, DIM_REL_TOL * abs(written_mm))
    return ("ok" if abs(measured_mm - written_mm) < tol else "dimension_mismatch"), tol


def check_level_pair(measured_m: float, written_m: float) -> tuple[str, float | None]:
    """Return (status, tolerance_m); tolerance max(0.010 m, 0.5 %); |diff| >= tolerance or non-finite -> mismatch."""
    if not _finite(measured_m, written_m):
        return "level_mismatch", None
    tol = max(LEVEL_ABS_TOL_M, LEVEL_REL_TOL * abs(written_m))
    return (
        "ok" if abs(measured_m - written_m) < tol - 1e-12 else "level_mismatch"
    ), tol


def parse_level_text(text: str) -> float | None:
    """``±0.000`` / ``+3.000`` / ``-0.450`` (``,`` and U+2212 accepted) -> metres; anything else -> None."""
    m = _LEVEL_TEXT.match(text.strip()) if isinstance(text, str) else None
    if not m:
        return None
    sign, whole, frac = m.groups()
    value = float(f"{whole}.{frac}")
    if sign == "±":
        return 0.0 if value == 0.0 else None
    return -value if sign in ("-", "\u2212") and value else value


def check_dimension_text(text: str) -> float | None:
    return float(re.sub(r"\D", "", text)) if _DIM_TEXT.match(text) else None


# ---------------------------------------------------------------- reading


def _import_pymupdf() -> Any:
    try:
        import pymupdf
    except ImportError:
        raise AlbumExtraMissing(EXTRA_HINT) from None
    return pymupdf


def read_page(
    path: str | Path, page_number: int = 1, *, scale_axes: tuple[str, str] | None = None
) -> PageReading:
    """Read page ``page_number`` (1-based) of the PDF at ``path``; see the module docstring for the rules."""
    pymupdf = _import_pymupdf()
    if isinstance(page_number, bool) or not isinstance(page_number, int):
        raise AlbumReadError(
            "bad_page_number", f"page number must be an int, got {page_number!r}"
        )
    p = Path(path)
    if not p.is_file():
        raise AlbumReadError("not_found", f"no such file: {p}")
    data = p.read_bytes()
    if not data:
        raise AlbumReadError("corrupt", f"empty file: {p.name}")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - every open failure is a typed error
        raise AlbumReadError("corrupt", f"cannot open {p.name} as PDF: {exc}") from None
    try:
        if doc.needs_pass or doc.is_encrypted:
            raise AlbumReadError(
                "encrypted", f"{p.name} is encrypted (password required)"
            )
        if doc.page_count < 1:
            raise AlbumReadError("corrupt", f"{p.name} has no pages")
        if not 1 <= page_number <= doc.page_count:
            raise AlbumReadError(
                "page_out_of_range",
                f"page {page_number} out of range: document has {doc.page_count} page(s)",
            )
        page = doc[page_number - 1]
        source = Source(
            sha256=hashlib.sha256(data).hexdigest(),
            page_number=page_number,
            page_count=doc.page_count,
            page_size=(page.rect.width, page.rect.height),
            pymupdf_version=str(pymupdf.__version__),
        )
        findings: list[Finding] = []
        if doc.is_repaired:
            findings.append(
                Finding(
                    "pdf_repaired",
                    "MuPDF had to repair the file; coordinates may be unreliable",
                )
            )
        return _read(pymupdf, page, source, scale_axes, findings)
    finally:
        doc.close()


def _rgb(value: Any) -> tuple[float, ...] | None:
    if not value:
        return None
    return tuple(float(c) for c in value)


def _pt(p: Any) -> Point:
    return (float(p[0]), float(p[1]))


def _primitives(
    page: Any,
) -> tuple[list[DrawnPath], list[Segment], list[dict[str, Any]]]:
    paths: list[DrawnPath] = []
    segs: list[Segment] = []
    raw: list[dict[str, Any]] = []
    for i, d in enumerate(page.get_drawings()):
        items = d.get("items") or []
        if not items:
            continue
        r = d["rect"]
        stroke, fill = _rgb(d.get("color")), _rgb(d.get("fill"))
        width = float(d.get("width") or 0.0)
        paths.append(
            DrawnPath(
                index=i,
                kinds="".join(it[0][0] for it in items),
                bbox=(r.x0, r.y0, r.x1, r.y1),
                stroke=stroke,
                fill=fill,
                width=width,
                closed=bool(d.get("closePath")),
                dashes=str(d.get("dashes") or ""),
            )
        )
        seen: set[tuple[Point, Point]] = set()
        for it in items:
            if it[0] != "l":
                continue
            a, b = _pt(it[1]), _pt(it[2])
            key = (a, b) if a <= b else (b, a)
            if key in seen or a == b:
                continue
            seen.add(key)
            segs.append(Segment(key[0], key[1], width, stroke, i))
        raw.append(
            {
                "index": i,
                "items": items,
                "fill": fill,
                "rect": r,
                "closed": bool(d.get("closePath")),
            }
        )
    return paths, segs, raw


def _text_runs(pymupdf: Any, page: Any) -> list[TextRun]:
    flags = pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES
    runs: list[TextRun] = []
    for block in page.get_text("rawdict", flags=flags)["blocks"]:
        for line in block.get("lines", []):
            direction = _pt(line["dir"])
            horizontal = abs(direction[1]) < 1e-6 and direction[0] > 0
            current: list[tuple[dict[str, Any], dict[str, Any]]] = []
            last_x1: float | None = None

            def flush() -> None:
                text = "".join(ch["c"] for ch, _ in current).strip()
                ink = [(ch, sp) for ch, sp in current if ch["c"].strip()]
                if text and ink:
                    xs0, ys0, xs1, ys1 = zip(
                        *(ch["bbox"] for ch, _ in ink), strict=True
                    )
                    first_ch, first_sp = ink[0]
                    runs.append(
                        TextRun(
                            text=text,
                            bbox=(min(xs0), min(ys0), max(xs1), max(ys1)),
                            origin=_pt(first_ch["origin"]),
                            size=float(first_sp["size"]),
                            font=str(first_sp["font"]),
                            dir=direction,
                        )
                    )
                current.clear()

            for span in line["spans"]:
                for ch in span["chars"]:
                    if not ch["c"].strip():
                        current.append((ch, span))
                        continue
                    if (
                        horizontal
                        and last_x1 is not None
                        and ch["bbox"][0] - last_x1 > 1.5 * float(span["size"])
                    ):
                        flush()
                    current.append((ch, span))
                    last_x1 = ch["bbox"][2]
            flush()
    return runs


def _center(b: Box) -> Point:
    return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)


def _circles(raw: list[dict[str, Any]]) -> list[tuple[Point, float, int]]:
    out = []
    for d in raw:
        kinds = [it[0] for it in d["items"]]
        r = d["rect"]
        if (
            len(kinds) >= 4
            and all(k == "c" for k in kinds)
            and r.width > 1
            and abs(r.width - r.height) <= 0.02 * r.width
        ):
            out.append(
                (((r.x0 + r.x1) / 2.0, (r.y0 + r.y1) / 2.0), r.width / 2.0, d["index"])
            )
    return out


def _triangles(raw: list[dict[str, Any]]) -> list[tuple[Point, Box, int]]:
    out = []
    for d in raw:
        items = d["items"]
        if not items or any(it[0] != "l" for it in items) or len(items) not in (2, 3):
            continue
        verts = sorted(
            {
                (round(p[0], 3), round(p[1], 3))
                for it in items
                for p in (_pt(it[1]), _pt(it[2]))
            }
        )
        if len(verts) != 3 or (len(items) == 2 and not d["closed"]):
            continue
        r = d["rect"]
        if max(r.width, r.height) > 30 or min(r.width, r.height) < 1:
            continue
        apex = None
        for i, v in enumerate(verts):
            others = [w for j, w in enumerate(verts) if j != i]
            if (
                abs(others[0][1] - others[1][1]) <= 0.05
                and abs(v[1] - others[0][1]) > 0.5
            ):
                apex = v
        if apex is not None:
            out.append((apex, (r.x0, r.y0, r.x1, r.y1), d["index"]))
    return out


def _axes(
    runs: list[TextRun],
    segs: list[Segment],
    circles: list[tuple[Point, float, int]],
    findings: list[Finding],
) -> tuple[list[Axis], set[int]]:
    axes: list[Axis] = []
    label_runs: set[int] = set()
    for center, radius, _ in circles:
        inside = [
            i
            for i, r in enumerate(runs)
            if math.dist(_center(r.bbox), center) < radius and _AXIS_LABEL.match(r.text)
        ]
        best: tuple[float, Point, Point, str] | None = None
        for s in segs:
            for a, b in ((s.p0, s.p1), (s.p1, s.p0)):
                if abs(math.dist(a, center) - radius) > AXIS_SNAP_PT:
                    continue
                if abs(a[0] - b[0]) <= 0.05 and abs(a[0] - center[0]) <= AXIS_SNAP_PT:
                    orient = "vertical"
                elif abs(a[1] - b[1]) <= 0.05 and abs(a[1] - center[1]) <= AXIS_SNAP_PT:
                    orient = "horizontal"
                else:
                    continue
                length = math.dist(a, b)
                if math.dist(b, center) <= radius or length <= 3 * radius:
                    continue
                if best is None or length > best[0]:
                    best = (length, a, b, orient)
        if len(inside) != 1:
            if best is not None:
                findings.append(
                    Finding(
                        "axis_line_without_label",
                        f"axis bubble with {len(inside)} label runs; axis not extracted",
                        {"bubble_center": list(center)},
                    )
                )
            continue
        run = runs[inside[0]]
        if best is None:
            findings.append(
                Finding(
                    "axis_bubble_without_line",
                    f"bubble '{run.text}' has no axis line",
                    {"label": run.text},
                )
            )
            continue
        _, a, b, orient = best
        label_runs.add(inside[0])
        axes.append(
            Axis(
                label=run.text,
                orientation=orient,
                position=(a[0] + b[0]) / 2.0
                if orient == "vertical"
                else (a[1] + b[1]) / 2.0,
                bubble_center=center,
                bubble_radius=radius,
                line_p0=a,
                line_p1=b,
            )
        )
    axes.sort(key=lambda ax: (ax.orientation != "vertical", ax.position, ax.label))
    seen: dict[str, int] = {}
    for ax in axes:
        seen[ax.label] = seen.get(ax.label, 0) + 1
        is_digit = ax.label[0].isdigit()
        if is_digit != (ax.orientation == "vertical"):
            findings.append(
                Finding(
                    "axis_label_convention",
                    f"axis '{ax.label}': digits mark vertical axis lines, letters horizontal ones",
                    {"label": ax.label, "orientation": ax.orientation},
                )
            )
        if ax.label[0] in _FORBIDDEN_AXIS_LETTERS:
            findings.append(
                Finding(
                    "axis_label_not_allowed",
                    f"axis '{ax.label}' uses a letter not used for axes",
                    {"label": ax.label},
                )
            )
    for label, count in sorted(seen.items()):
        if count > 1:
            findings.append(
                Finding(
                    "duplicate_axis_label",
                    f"axis '{label}' appears {count} times",
                    {"label": label},
                )
            )
    return axes, label_runs


def _dimensions(
    runs: list[TextRun],
    segs: list[Segment],
    skip: set[int],
    axes: list[Axis],
    tri_paths: set[int],
) -> list[Dimension]:
    ticks = [
        s
        for s in segs
        if s.path not in tri_paths
        and 2.0 <= math.dist(s.p0, s.p1) <= 20.0
        and abs(abs(s.p1[0] - s.p0[0]) - abs(s.p1[1] - s.p0[1]))
        <= 0.25 * math.dist(s.p0, s.p1)
    ]
    dim_lines = []
    for s in segs:
        if abs(s.p0[1] - s.p1[1]) > 0.05 or abs(s.p1[0] - s.p0[0]) <= 20.0:
            continue
        y = (s.p0[1] + s.p1[1]) / 2.0
        x0, x1 = sorted((s.p0[0], s.p1[0]))
        xs = sorted(
            {
                round((t.p0[0] + t.p1[0]) / 2.0, 3)
                for t in ticks
                if abs((t.p0[1] + t.p1[1]) / 2.0 - y) <= 0.5
                and x0 - 0.5 <= (t.p0[0] + t.p1[0]) / 2.0 <= x1 + 0.5
            }
        )
        if len(xs) >= 2:
            dim_lines.append((y, xs))
    unique = {}
    for ax in axes:
        if ax.orientation == "vertical":
            unique.setdefault(ax.label, []).append(ax.position)
    vertical = [(lab, pos[0]) for lab, pos in unique.items() if len(pos) == 1]

    def axis_at(x: float) -> str | None:
        hits = [lab for lab, pos in vertical if abs(pos - x) <= AXIS_SNAP_PT]
        return hits[0] if len(hits) == 1 else None

    out: list[Dimension] = []
    for i, run in enumerate(runs):
        if i in skip or abs(run.dir[1]) > 1e-6 or run.dir[0] <= 0:
            continue
        value = check_dimension_text(run.text)
        if value is None:
            continue
        cx, cy = _center(run.bbox)
        best = None
        for y, xs in dim_lines:
            if not 0 < y - cy <= 2.5 * run.size:
                continue
            pair = [(a, b) for a, b in zip(xs, xs[1:], strict=False) if a < cx < b]
            if pair and (best is None or y - cy < best[0]):
                best = (y - cy, y, pair[0])
        if best is None:
            continue
        _, y, (a, b) = best
        la, lb = axis_at(a), axis_at(b)
        out.append(
            Dimension(
                text=run.text,
                value_mm=value,
                p0=(a, y),
                p1=(b, y),
                measured_pt=b - a,
                axes=(la, lb) if la and lb else None,
                text_bbox=run.bbox,
            )
        )
    out.sort(key=lambda d: (d.p0[1], d.p0[0], d.text))
    return out


def _level_marks(
    runs: list[TextRun],
    triangles: list[tuple[Point, Box, int]],
    findings: list[Finding],
) -> list[LevelMark]:
    texts = [(i, r, parse_level_text(r.text)) for i, r in enumerate(runs)]
    texts = [(i, r, v) for i, r, v in texts if v is not None]
    pairs = []
    for ti, run, _ in texts:
        for k, (_, box, _) in enumerate(triangles):
            size = max(box[2] - box[0], box[3] - box[1])
            dist = math.dist(_center(run.bbox), _center(box))
            if dist <= 6.0 * size:
                pairs.append((dist, ti, k))
    pairs.sort()
    used_t: set[int] = set()
    used_k: set[int] = set()
    marks: list[LevelMark] = []
    for _, ti, k in pairs:
        if ti in used_t or k in used_k:
            continue
        used_t.add(ti)
        used_k.add(k)
        run = runs[ti]
        apex, box, _ = triangles[k]
        marks.append(
            LevelMark(
                run.text, parse_level_text(run.text), apex[1], apex, box, run.bbox
            )
        )  # type: ignore[arg-type]
    for ti, run, _ in texts:
        if ti not in used_t:
            findings.append(
                Finding(
                    "level_text_without_symbol",
                    f"level text '{run.text}' has no mark symbol",
                    {"text": run.text},
                )
            )
    marks.sort(key=lambda m: (m.value_m, -m.y, m.apex[0]))
    return marks


def _legend(
    runs: list[TextRun], raw: list[dict[str, Any]], skip: set[int]
) -> list[LegendItem]:
    swatches = []
    for d in raw:
        items = d["items"]
        if d["fill"] is None or len(items) != 1 or items[0][0] != "re":
            continue
        r = items[0][1]
        if 4 <= r.width <= 60 and 3 <= r.height <= 30:
            swatches.append((r, d["fill"]))
    claims: dict[int, tuple[float, int]] = {}
    for k, (r, _) in enumerate(swatches):
        best = None
        for i, run in enumerate(runs):
            if i in skip:
                continue
            gap = run.bbox[0] - r.x1
            cy = _center(run.bbox)[1]
            if (
                0 <= gap <= 2.5 * r.width
                and r.y0 - 0.25 * r.height <= cy <= r.y1 + 0.25 * r.height
            ):
                if best is None or gap < best[0]:
                    best = (gap, i)
        if best is not None and (best[1] not in claims or best[0] < claims[best[1]][0]):
            claims[best[1]] = (best[0], k)
    out = []
    for i, (_, k) in claims.items():
        r, fill = swatches[k]
        rgb = (tuple(fill) + (0.0, 0.0, 0.0))[:3] if len(fill) >= 3 else (fill[0],) * 3
        out.append(
            LegendItem(
                label=runs[i].text,
                rgb=rgb,  # type: ignore[arg-type]
                rgb255=tuple(int(round(c * 255)) for c in rgb),  # type: ignore[arg-type]
                swatch=(r.x0, r.y0, r.x1, r.y1),
            )
        )
    out.sort(key=lambda it: (it.swatch[1], it.swatch[0]))
    return out


def _scale(
    dims: list[Dimension], scale_axes: tuple[str, str] | None
) -> tuple[Scale, Dimension | None]:
    named = sorted((d for d in dims if d.axes), key=lambda d: (d.p0[0], d.p0[1]))
    if scale_axes is not None:
        want = {tuple(scale_axes), tuple(reversed(scale_axes))}
        named = [d for d in named if d.axes in want]
        label = "-".join(scale_axes)
        if not named:
            return Scale(
                "unknown",
                None,
                None,
                None,
                f"no dimension between axes {label} on the page",
            ), None
    if not named:
        return Scale(
            "unknown",
            None,
            None,
            None,
            "no dimension between two named axes; scale not guessed",
        ), None
    ref = named[0]
    if not (
        _finite(ref.measured_pt, ref.value_mm)
        and ref.measured_pt > 0
        and ref.value_mm > 0
    ):
        return Scale(
            "unknown", None, None, None, f"reference dimension {ref.text} is degenerate"
        ), None
    return (
        Scale(
            "derived",
            ref.value_mm / ref.measured_pt,
            ref.axes,
            ref.value_mm,
            f"axis dimension {'-'.join(ref.axes or ())} = {ref.text} mm over {ref.measured_pt:.3f} pt",
        ),
        ref,
    )


def _read(
    pymupdf: Any,
    page: Any,
    source: Source,
    scale_axes: tuple[str, str] | None,
    findings: list[Finding],
) -> PageReading:
    paths, segs, raw = _primitives(page)
    runs = _text_runs(pymupdf, page)
    images = len(page.get_images(full=False))
    if images:
        findings.append(
            Finding(
                "raster_images_present",
                f"{images} raster image(s) on the page",
                {"count": images},
            )
        )
    if not paths and not runs and not images:
        status = "empty"
    elif not paths:
        status = "not_vector"
    elif not runs:
        status = "no_text_layer"
    else:
        status = "ok"
    if status != "ok":
        messages = {
            "empty": "blank page: no vector paths, text or images",
            "not_vector": "no vector line work: a raster/scanned page; OCR and PDFIMPORT are out of scope",
            "no_text_layer": "vector line work without a text layer (text as outlines); nothing extracted",
        }
        findings.append(Finding(status, messages[status]))
        unknown = Scale("unknown", None, None, None, f"page status {status}")
        findings.append(Finding("scale_unknown", unknown.reason))
        return PageReading(
            source, status, paths, segs, runs, [], [], [], [], unknown, [], [], findings
        )

    circles = _circles(raw)
    triangles = _triangles(raw)
    axes, label_runs = _axes(runs, segs, circles, findings)
    tri_paths = {t[2] for t in triangles}
    level_marks = _level_marks(runs, triangles, findings)
    level_runs = {i for i, r in enumerate(runs) if parse_level_text(r.text) is not None}
    dims = _dimensions(runs, segs, label_runs | level_runs, axes, tri_paths)
    dim_runs = {
        i for i, r in enumerate(runs) if any(d.text_bbox == r.bbox for d in dims)
    }
    legend = _legend(runs, raw, label_runs | level_runs | dim_runs)
    scale, ref = _scale(dims, scale_axes)
    if scale.status == "unknown":
        findings.append(Finding("scale_unknown", scale.reason))

    dim_checks: list[DimensionCheck] = []
    for d in dims:
        if scale.mm_per_pt is None:
            dim_checks.append(
                DimensionCheck(d.text, d.axes, d.value_mm, None, None, "not_checked")
            )
            continue
        measured = d.measured_pt * scale.mm_per_pt
        if d is ref:
            dim_checks.append(
                DimensionCheck(d.text, d.axes, d.value_mm, measured, None, "reference")
            )
            continue
        status_d, tol = check_dimension(measured, d.value_mm)
        dim_checks.append(
            DimensionCheck(d.text, d.axes, d.value_mm, measured, tol, status_d)
        )
        if status_d != "ok":
            findings.append(
                Finding(
                    "dimension_mismatch",
                    f"dimension '{d.text}' measures {measured:.1f} mm at the derived scale",
                    {
                        "text": d.text,
                        "axes": list(d.axes) if d.axes else None,
                        "written_mm": d.value_mm,
                        "measured_mm": measured,
                        "tolerance_mm": tol,
                        "p0": list(d.p0),
                        "p1": list(d.p1),
                    },
                )
            )

    level_checks: list[LevelCheck] = []
    for lo, hi in zip(level_marks, level_marks[1:], strict=False):
        written = hi.value_m - lo.value_m
        if scale.mm_per_pt is None:
            level_checks.append(
                LevelCheck(lo.text, hi.text, written, None, None, "not_checked")
            )
            continue
        measured = (lo.y - hi.y) * scale.mm_per_pt / 1000.0
        status_l, tol = check_level_pair(measured, written)
        level_checks.append(
            LevelCheck(lo.text, hi.text, written, measured, tol, status_l)
        )
        if status_l != "ok":
            findings.append(
                Finding(
                    "level_mismatch",
                    f"levels {lo.text} -> {hi.text}: written {written:.3f} m, measured {measured:.3f} m",
                    {
                        "pair": [lo.text, hi.text],
                        "written_m": written,
                        "measured_m": measured,
                        "tolerance_m": tol,
                    },
                )
            )
    return PageReading(
        source,
        status,
        paths,
        segs,
        runs,
        axes,
        dims,
        level_marks,
        legend,
        scale,
        dim_checks,
        level_checks,
        findings,
    )


# ---------------------------------------------------------------- JSON


def _normalise(value: Any) -> Any:
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        r = round(value, 4)
        return 0.0 if r == 0 else r
    if isinstance(value, dict):
        return {str(k): _normalise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    return value


def reading_to_json(reading: PageReading) -> str:
    """Deterministic JSON: sorted keys, floats rounded to 4 decimals, UTF-8 text kept (no \\u escapes)."""
    return (
        json.dumps(reading.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
