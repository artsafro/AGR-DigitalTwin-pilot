"""Dimension / level / opening binding across drawing views with anchor-calibrated scale (#1234).

Pattern: n/a | new-case: bind album dimension, level and opening values to view + axis pair / opening /
level and calibrate each view's scale only from >= 2 independent model anchors with residuals.

``bind_album(pdf, pages, anchors=None, album_index=None)`` reads vector PDF pages with the PyMuPDF primitives of
:mod:`dt_ai.album.reader` and returns the ``dimensions.json`` document of the artifact contract in
``docs/research/pdf-album-pipeline.md`` (schema ``schemas/AlbumDimensions.schema.json``).

Rules (each has a test in ``tests/test_album_binding.py``):

- Views: the page line work is rasterised on a 6 pt grid (sheet-frame lines longer than half the page are
  skipped), dilated by 2 cells; every connected component that holds a dimension chain, an axis bubble or a
  level mark is one view ``p<page>-v<n>`` (numbered top-left first). An item outside every view keeps
  ``view: null`` and is unresolved.
- Chains: horizontal AND vertical dimension lines with short ~45 deg ticks. A tick is any short diagonal
  segment that crosses or touches the line (a tick drawn as two half-strokes is one tick). Every span between
  two consecutive ticks is a dimension candidate; its value is the integer mm text written along the line
  (horizontal text above / below a horizontal line, text rotated 90 deg left / right of a vertical line).
  A span without readable text is a finding, never a silent omission.
- Binding, in order: ``axis_pair`` (both span ends on axes of the same view, within 1 pt), ``opening`` (both
  ends on the edges of one closed rectangle of the view that faces the chain), ``level_pair`` (a vertical
  span whose ends sit on the level lines of two level marks of the view), else ``unbound`` with the reason.
- Level marks: the level line is found ONLY through the mark symbol: a shelf under (or over) the text covering
  >= half of it, and an arrow/triangle tip (two ~45 deg arms pointing back to the text) at a shelf end, either
  within 1.5 text heights or reached by one vertical stem (Revit, either direction).
  Tip arms are bounded relative to text size as well as the legacy 15 pt minimum budget.
  A tight closed rectangle containing exactly one level text is a plan ``spot_level``:
  its ``spot_bbox`` locates the tag, ``level_y`` stays null, and it NEVER feeds
  ``level_pair`` or elevation-line consistency. No tip/box -> ``unbound no_level_line``; two
  distinct tips, or one tip claimed by two marks -> ``level_line_ambiguous``; never the nearest line. Bound marks
  of one view (>= 3 distinct values) must fit one linear value(y) (Theil-Sen); an outlier beyond 1 pt is
  ``unbound level_value_inconsistent`` with a D112 finding, its drawn line kept as ``level_y_drawn``. Only bound
  marks bind as ``level`` and feed ``level_pair``; the absolute elevation written under a mark is kept raw.
  Every dimension-like text token (>= 3 digits) that no span claims is a value with ``unbound`` /
  ``no_dimension_line``; nothing is dropped.
- Axes: a stroked circle holding exactly one axis-label run (including closed polygon
  loops inside compound paths and two native semicircle strokes). PyMuPDF applies nested
  XObject transforms before recognition; non-circular or open loops are not bubbles. A bubble with a radial line takes the line
  orientation; otherwise >= 2 bubbles on one row are vertical axes (x), on one column horizontal axes (y).
- Scale: per view, ONLY from model anchors ``{page, axes:[a, b], model_mm}`` taken from an independent
  DWG/BIM source whose SHA-256 differs from the PDF. >= 2 independent anchors (different axis pairs, different
  spans) are fitted by least squares through the origin; every anchor residual must be below
  max(10 mm, 0.5 %) (equal is a failure). Otherwise ``scale.status = unknown`` with the reason. Nominal
  print-scale text (``М 1:200``) is recorded and never used; neither is any CAD ``$INSUNITS``.
- Fail-closed: unknown scale or an unbound value is ``unresolved`` and has no measured geometry; a mismatch
  between the written value and the calibrated measurement is a finding kept for the architect (D112), the
  written value is never corrected. ``passed`` is always false: binding review, ground truth and approval
  stay open (``open_gates``).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dt_ai.album import reader as R

SCHEMA = "album-dimensions/1"
GRID_PT = 6.0
DILATE = 1
END_SNAP_PT = 1.0
TICK_MIN, TICK_MAX = 1.5, 20.0
_LONG_DIM = re.compile(r"^(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d{3,})$")
_NOMINAL = re.compile(r"[МM]\s*1\s*:\s*\d+")
_ABS_ELEV = re.compile(r"^\d{2,3}[.,]\d{1,3}$")


class BindingError(ValueError):
    """Bad anchors / index input; ``reason`` is a stable code."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(f"{reason}: {message}")
        self.reason = reason


# ---------------------------------------------------------------- geometry helpers


def _horiz(s: R.Segment) -> bool:
    return abs(s.p0[1] - s.p1[1]) <= 0.05


def _vert(s: R.Segment) -> bool:
    return abs(s.p0[0] - s.p1[0]) <= 0.05


def _level_tips(segs: list[R.Segment], max_arm: float = 15.0) -> list[tuple[float, float, int]]:
    """Arrow/triangle apexes of level marks: >= 2 short ~45 deg strokes ending in one point, one going left and
    one going right, both to the same side (``side`` = +1 arms below the apex, -1 above). A dimension tick
    drawn as two half-strokes leaves to opposite sides and is not a tip."""
    ends: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
    for s in segs:
        dx, dy = s.p1[0] - s.p0[0], s.p1[1] - s.p0[1]
        if _horiz(s) or _vert(s) or not 1.0 <= math.hypot(dx, dy) <= max_arm or not 0.4 <= abs(dy) / abs(dx) <= 2.5:
            continue
        for (px, py), (qx, qy) in ((s.p0, s.p1), (s.p1, s.p0)):
            ends.setdefault((round(px / 0.3), round(py / 0.3)), []).append((px, py, qx - px, qy - py))
    tips = []
    for arms in ends.values():
        for side in (1, -1):
            sel = [a for a in arms if a[3] * side > 0]
            if any(a[2] < 0 for a in sel) and any(a[2] > 0 for a in sel):
                tips.append((round(sel[0][0], 2), round(sel[0][1], 2), side))
    return tips


def _level_line(r: R.TextRun, segs: list[R.Segment], tips: list[tuple[float, float, int]]) -> list[tuple[float, float]]:
    """Distinct level-line points of one level mark text. The shelf is a horizontal line under (or over) the text
    covering >= half of it; the line is the tip at a shelf end (+-0.6 pt) whose arms point back to the text,
    either within 1.5 text heights of the shelf or reached by one vertical stem from that shelf end."""
    x0, y0, x1, y1 = r.bbox
    s_ = r.size
    shelves = []
    for s in segs:
        if not _horiz(s):
            continue
        lo, hi = sorted((s.p0[0], s.p1[0]))
        if min(hi, x1) - max(lo, x0) < 0.5 * (x1 - x0):
            continue
        y = s.p0[1]
        if y1 - 0.35 * s_ <= y <= y1 + 0.6 * s_:
            shelves.append((y, lo, hi, 1))  # text above the shelf: the line is below
        if y0 - 0.6 * s_ <= y <= y0 + 0.35 * s_:
            shelves.append((y, lo, hi, -1))
    found: set[tuple[float, float]] = set()
    for y, lo, hi, away in shelves:
        for e in (lo, hi):
            for tx, ty, side in tips:
                if abs(tx - e) > 0.6:
                    continue
                d = (ty - y) * away
                direct = side == -away and -0.5 <= d <= 1.5 * s_
                stem = (0 < abs(ty - y) <= 6.0 * s_ and side * (y - ty) > 0
                        and any(
                            _vert(v) and abs(v.p0[0] - e) <= 0.6
                            and abs(min(v.p0[1], v.p1[1]) - min(y, ty)) <= 0.6
                            and abs(max(v.p0[1], v.p1[1]) - max(y, ty)) <= 0.6 for v in segs))
                if direct or stem:
                    found.add((tx, ty))
    ys: dict[float, tuple[float, float]] = {}
    for p in sorted(found):
        ys.setdefault(round(p[1] * 2) / 2, p)  # tips on one line (+-0.25 pt) are one level line
    return list(ys.values())


def _spot_box(r: R.TextRun, segs: list[R.Segment], runs: list[R.TextRun]) -> R.Box | None:
    """A tight, closed four-sided plan-height tag, never an elevation line."""
    x0, y0, x1, y1 = r.bbox
    hs = [s for s in segs if _horiz(s) and x0 - r.size <= min(s.p0[0], s.p1[0]) <= x0
          and x1 <= max(s.p0[0], s.p1[0]) <= x1 + r.size
          and y0 - r.size <= s.p0[1] <= y1 + r.size]
    boxes = set()
    for top in hs:
        for bottom in hs:
            lo, hi = sorted((top.p0[0], top.p1[0]))
            by = bottom.p0[1]
            ty = top.p0[1]
            if not (ty <= y0 and by >= y1 and by - ty <= 2.5 * r.size
                    and abs(min(bottom.p0[0], bottom.p1[0]) - lo) <= 0.3
                    and abs(max(bottom.p0[0], bottom.p1[0]) - hi) <= 0.3):
                continue
            if all(any(_vert(v) and abs(v.p0[0] - x) <= 0.3
                       and abs(min(v.p0[1], v.p1[1]) - ty) <= 0.3
                       and abs(max(v.p0[1], v.p1[1]) - by) <= 0.3 for v in segs) for x in (lo, hi)):
                inside = [o for o in runs if lo < R._center(o.bbox)[0] < hi and ty < R._center(o.bbox)[1] < by]
                if len(inside) == 1 and inside[0] is r:
                    boxes.add((lo, ty, hi, by))
    return next(iter(boxes)) if len(boxes) == 1 else None


def _level_outliers(levels: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], float]]:
    """Scale-free consistency of the bound level marks of one view: the written values must be one linear
    function of the drawn line y (Theil-Sen fit, >= 3 marks with >= 3 distinct values, values rising upwards).
    A mark more than END_SNAP_PT off the fit is ``level_value_inconsistent``; the written value is kept."""
    out = []
    by_view: dict[str, list[dict[str, Any]]] = {}
    for lv in levels:
        if lv["view"] and lv["level_y"] is not None:
            by_view.setdefault(lv["view"], []).append(lv)
    for group in by_view.values():
        if len({lv["value_m"] for lv in group}) < 3:
            continue
        slopes = sorted((b["value_m"] - a["value_m"]) / (b["level_y"] - a["level_y"])
                        for i, a in enumerate(group) for b in group[i + 1:] if abs(b["level_y"] - a["level_y"]) > END_SNAP_PT)
        if not slopes:
            continue
        k = slopes[len(slopes) // 2]
        if not k < 0:
            continue
        cs = sorted(lv["value_m"] - k * lv["level_y"] for lv in group)
        c = cs[len(cs) // 2]
        for lv in group:
            expected = (lv["value_m"] - c) / k
            if abs(expected - lv["level_y"]) > END_SNAP_PT:
                out.append(("level_value_inconsistent", lv, round(expected, 2)))
    return out


def _ticks(segs: list[R.Segment]) -> list[R.Segment]:
    out = []
    for s in segs:
        dx, dy = abs(s.p1[0] - s.p0[0]), abs(s.p1[1] - s.p0[1])
        length = math.hypot(dx, dy)
        if TICK_MIN <= length <= TICK_MAX and abs(dx - dy) <= 0.25 * length:
            out.append(s)
    return out


def _merge(values: list[float], tol: float = 0.5) -> list[float]:
    out: list[float] = []
    for v in sorted(values):
        if out and v - out[-1] <= tol:
            continue
        out.append(v)
    return out


def _chains(segs: list[R.Segment], runs: Sequence[R.TextRun] = ()) -> list[dict[str, Any]]:
    """Ticked lines; join inline numeric-text interruptions, never unexplained gaps.

    Native CAD plots suppress the line under an inline label. Both retained ends
    must meet the same uniquely identified, parallel numeric text box (<1/8 em,
    capped at 1 pt).
    This recovers paper spans only: endpoint identity and calibration still refuse
    independently. Text outside the span never licenses extrapolation.
    """
    ticks = _ticks(segs)
    groups: dict[tuple[str, float], list[tuple[float, float]]] = {}
    for s in segs:
        if _horiz(s) and abs(s.p1[0] - s.p0[0]) > 0.05:
            key, rng = ("horizontal", round((s.p0[1] + s.p1[1]) / 2.0, 1)), sorted((s.p0[0], s.p1[0]))
        elif _vert(s) and abs(s.p1[1] - s.p0[1]) > 0.05:
            key, rng = ("vertical", round((s.p0[0] + s.p1[0]) / 2.0, 1)), sorted((s.p0[1], s.p1[1]))
        else:
            continue
        groups.setdefault(key, []).append((rng[0], rng[1]))
    chains = []
    for (orient, c), ranges in groups.items():
        ranges.sort()
        merged: list[list[float]] = []
        bridges: list[tuple[float, float, int]] = []
        for a, b in ranges:
            inline = []
            if merged and a > merged[-1][1] + 0.5:
                end = merged[-1][1]
                for run_index, run in enumerate(runs):
                    if not all(math.isfinite(v) for v in (*run.bbox, *run.dir, run.size)):
                        continue
                    if orient == "horizontal":
                        lo, hi, across0, across1 = run.bbox[0], run.bbox[2], run.bbox[1], run.bbox[3]
                        parallel = abs(run.dir[1]) <= 1e-6 and run.dir[0] > .99
                    else:
                        lo, hi, across0, across1 = run.bbox[1], run.bbox[3], run.bbox[0], run.bbox[2]
                        parallel = abs(run.dir[0]) <= 1e-6 and abs(run.dir[1]) > .99
                    # CAD knockout extents differ from font ink bounds. Allow
                    # <1/8 em, capped at 1 pt; exact limits still refuse.
                    margin = min(1.0, run.size / 8)
                    if parallel and across0 < c < across1 and abs(lo - end) < margin and abs(hi - a) < margin:
                        inline.append(run_index)
            bridge = len(inline) == 1 and R.check_dimension_text(runs[inline[0]].text) is not None
            if merged and (a <= merged[-1][1] + 0.5 or bridge):
                if bridge:
                    bridges.append((merged[-1][1], a, inline[0]))
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            pos = []
            for t in ticks:
                (x0, y0), (x1, y1) = t.p0, t.p1
                if orient == "horizontal":
                    lo, hi = sorted((y0, y1))
                    if lo - 0.3 <= c <= hi + 0.3:
                        x = x0 if abs(y1 - y0) < 1e-9 else x0 + (c - y0) * (x1 - x0) / (y1 - y0)
                        x = min(max(x, min(x0, x1)), max(x0, x1))
                        if a - 0.6 <= x <= b + 0.6:
                            pos.append(x)
                else:
                    lo, hi = sorted((x0, x1))
                    if lo - 0.3 <= c <= hi + 0.3:
                        y = y0 if abs(x1 - x0) < 1e-9 else y0 + (c - x0) * (y1 - y0) / (x1 - x0)
                        y = min(max(y, min(y0, y1)), max(y0, y1))
                        if a - 0.6 <= y <= b + 0.6:
                            pos.append(y)
            pos = _merge(pos)
            if len(pos) >= 2:
                chains.append({"orientation": orient, "coord": c, "ticks": pos,
                               "bridges": [g for g in bridges if a <= g[0] and g[1] <= b]})
    chains.sort(key=lambda ch: (ch["orientation"], ch["coord"], ch["ticks"][0]))
    return chains


def _bubbles(runs: list[R.TextRun], segs: list[R.Segment], raw: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], set[int]]:
    """Axis candidates: circle + one label run; orientation from a radial line or the bubble row/column."""
    found = []
    used: set[int] = set()
    for center, radius, _ in R._circles(raw):
        inside = [i for i, r in enumerate(runs)
                  if math.dist(R._center(r.bbox), center) < radius and R._AXIS_LABEL.match(r.text)]
        if len(inside) != 1:
            continue
        orient = None
        for s in segs:
            for a, b in ((s.p0, s.p1), (s.p1, s.p0)):
                if abs(math.dist(a, center) - radius) > R.AXIS_SNAP_PT or math.dist(a, b) <= 2 * radius:
                    continue
                if abs(a[0] - b[0]) <= 0.05 and abs(a[0] - center[0]) <= R.AXIS_SNAP_PT:
                    orient = "vertical"
                elif abs(a[1] - b[1]) <= 0.05 and abs(a[1] - center[1]) <= R.AXIS_SNAP_PT:
                    orient = "horizontal"
        used.add(inside[0])
        found.append({"label": runs[inside[0]].text, "center": center, "radius": radius, "orientation": orient})
    for b in found:
        if b["orientation"]:
            continue
        row = [o for o in found if o is not b and abs(o["center"][1] - b["center"][1]) <= b["radius"] * 0.5]
        col = [o for o in found if o is not b and abs(o["center"][0] - b["center"][0]) <= b["radius"] * 0.5]
        if row and not col:
            b["orientation"] = "vertical"
        elif col and not row:
            b["orientation"] = "horizontal"
    for b in found:
        b["position"] = None if b["orientation"] is None else (
            b["center"][0] if b["orientation"] == "vertical" else b["center"][1])
    return found, used


def _rects(raw: list[dict[str, Any]]) -> list[R.Box]:
    out = []
    for d in raw:
        items = d["items"]
        box = None
        for it in items:  # every rectangle item, also several in one path
            if it[0] == "re":
                r = it[1]
                if 3.0 <= r.width <= 400 and 3.0 <= r.height <= 400:
                    out.append((r.x0, r.y0, r.x1, r.y1))
        if len(items) in (3, 4) and all(it[0] == "l" for it in items) and (d["closed"] or len(items) == 4):
            pts = {(round(p[0], 2), round(p[1], 2)) for it in items for p in (it[1], it[2])}
            xs, ys = {p[0] for p in pts}, {p[1] for p in pts}
            if len(pts) == 4 and len(xs) == 2 and len(ys) == 2:
                box = (min(xs), min(ys), max(xs), max(ys))
        if box and 3.0 <= box[2] - box[0] <= 400 and 3.0 <= box[3] - box[1] <= 400:
            out.append(box)
    return sorted(set(out))


def _views(page_rect: tuple[float, float], segs: list[R.Segment], paths: list[R.DrawnPath]) -> tuple[list[list[int]], int, int]:
    w, h = page_rect
    nx, ny = int(w // GRID_PT) + 1, int(h // GRID_PT) + 1
    grid = [[0] * nx for _ in range(ny)]

    def mark(x: float, y: float) -> None:
        i, j = int(y // GRID_PT), int(x // GRID_PT)
        if 0 <= i < ny and 0 <= j < nx:
            grid[i][j] = 1

    def line(p0: R.Point, p1: R.Point) -> None:
        length = math.dist(p0, p1)
        if abs(p1[0] - p0[0]) > 0.85 * w or abs(p1[1] - p0[1]) > 0.85 * h:
            return  # sheet frame
        n = max(1, int(length // (GRID_PT / 2)))
        for k in range(n + 1):
            t = k / n
            mark(p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))

    for s in segs:
        line(s.p0, s.p1)
    for p in paths:
        if set(p.kinds) == {"l"}:
            continue  # already rasterised as segments
        x0, y0, x1, y1 = p.bbox
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            line(a, b)
    dil = [[0] * nx for _ in range(ny)]
    for i in range(ny):
        for j in range(nx):
            if grid[i][j]:
                for a in range(max(0, i - DILATE), min(ny, i + DILATE + 1)):
                    for b in range(max(0, j - DILATE), min(nx, j + DILATE + 1)):
                        dil[a][b] = 1
    label = [[0] * nx for _ in range(ny)]
    current = 0
    for i in range(ny):
        for j in range(nx):
            if dil[i][j] and not label[i][j]:
                current += 1
                stack = [(i, j)]
                label[i][j] = current
                while stack:
                    a, b = stack.pop()
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        c, d = a + da, b + db
                        if 0 <= c < ny and 0 <= d < nx and dil[c][d] and not label[c][d]:
                            label[c][d] = current
                            stack.append((c, d))
    return label, nx, ny


def _component(label: list[list[int]], x: float, y: float) -> int:
    i, j = int(y // GRID_PT), int(x // GRID_PT)
    best = 0
    for r in range(0, 4):
        for a in range(i - r, i + r + 1):
            for b in range(j - r, j + r + 1):
                if 0 <= a < len(label) and 0 <= b < len(label[0]) and label[a][b]:
                    return label[a][b]
    return best


# ---------------------------------------------------------------- page binding


def _bind_page(pymupdf: Any, page: Any, number: int, sheet: str | None) -> dict[str, Any]:
    paths, segs, raw = R._primitives(page)
    runs = R._text_runs(pymupdf, page)
    findings: list[dict[str, Any]] = []
    loc = {"page": number, "sheet": sheet}
    if not paths or not runs:
        status = "empty" if not paths and not runs else ("not_vector" if not paths else "no_text_layer")
        findings.append({"code": status, "page": number, "message": "nothing bound; OCR/vision route required"})
        return {"status": status, "views": [], "values": [], "openings": [], "findings": findings,
                "nominal_print_scale_text": []}
    bubbles, label_runs = _bubbles(runs, segs, raw)
    chains = _chains(segs, runs)
    rects = _rects(raw)
    label, _, _ = _views((page.rect.width, page.rect.height), segs, paths)
    nominal = [{"text": r.text, "bbox": list(r.bbox), "used_for_calibration": False}
               for r in runs if _NOMINAL.search(r.text)]

    # level marks: written value + its level line, found ONLY through the mark symbol (shelf under/over the
    # text -> arrow/triangle tip at a shelf end, directly or through a vertical stem). No tip or more than one
    # distinct tip -> unbound (never the nearest line); + raw absolute elevation below the mark
    levels = []
    level_runs: set[int] = set()
    tips = _level_tips(segs, max([15.0] + [2.0 * r.size for r in runs if R.parse_level_text(r.text) is not None]))
    spot_segs = list(segs)
    for box in rects:
        x0_, y0_, x1_, y1_ = box
        spot_segs.extend(R.Segment(a, b, 0.0, None, -1) for a, b in (
            ((x0_, y0_), (x1_, y0_)), ((x1_, y0_), (x1_, y1_)),
            ((x1_, y1_), (x0_, y1_)), ((x0_, y1_), (x0_, y0_))))
    for i, r in enumerate(runs):
        v = R.parse_level_text(r.text)
        if v is None:
            continue
        level_runs.add(i)
        absolute = None
        for k, o in enumerate(runs):
            if _ABS_ELEV.match(o.text) and 0 <= o.bbox[1] - r.bbox[1] <= 2.5 * r.size and abs(o.bbox[0] - r.bbox[0]) <= 3 * r.size:
                absolute = o.text
                level_runs.add(k)
                break
        spot = _spot_box(r, spot_segs, runs)
        found = [] if spot else _level_line(r, segs, tips)
        levels.append({"run": i, "text": r.text, "value_m": v, "absolute_text": absolute, "spot_bbox": spot,
                       "level_y": found[0][1] if len(found) == 1 else None,
                       "tip": found[0] if len(found) == 1 else None,
                       "line_reason": None if len(found) == 1 else ("no_level_line" if not found else "level_line_ambiguous")})
    shared: dict[tuple[float, float], int] = {}
    for lv in levels:
        if lv["tip"] is not None:
            shared[lv["tip"]] = shared.get(lv["tip"], 0) + 1
    for lv in levels:  # one tip claimed by two marks: neither is trusted
        if lv["tip"] is not None and shared[lv["tip"]] > 1:
            lv["level_y"], lv["line_reason"] = None, "level_line_ambiguous"

    # text along each span
    usable = [(i, r) for i, r in enumerate(runs) if i not in label_runs and i not in level_runs]
    claimed: set[int] = set()
    # A label that licenses missing geometry cannot be replaced or stolen by
    # another span's proximity heuristic. Retain source-run identity, not text
    # equality: repeated numeric labels are distinct evidence.
    authorizers = {i for ch in chains for _, _, i in ch["bridges"]}
    spans = []
    for ch in chains:
        for a, b in zip(ch["ticks"], ch["ticks"][1:]):
            spans.append({"orientation": ch["orientation"], "coord": ch["coord"], "a": a, "b": b,
                          "bridges": [g for g in ch["bridges"] if g[0] < b and a < g[1]]})

    def candidates(sp: dict[str, Any], near_side: bool) -> list[tuple[float, int]]:
        if sp["bridges"]:
            # Multiple labels or an interruption crossing a tick cannot prove
            # one span value. Never fall back to unrelated nearby annotation.
            if len(sp["bridges"]) != 1:
                return []
            lo, hi, index = sp["bridges"][0]
            if sp["a"] <= lo and hi <= sp["b"] and any(i == index for i, _ in usable):
                return [(0.0, index)]
            return []
        hits = []
        for i, r in usable:
            if i in authorizers:
                continue
            cx, cy = R._center(r.bbox)
            if sp["orientation"] == "horizontal":
                if not (abs(r.dir[1]) <= 1e-6 and r.dir[0] > 0 and sp["a"] < cx < sp["b"]):
                    continue
                gap = sp["coord"] - cy if near_side else cy - sp["coord"]
            else:
                if not (abs(r.dir[0]) <= 1e-6 and abs(r.dir[1]) > 0.99 and sp["a"] < cy < sp["b"]):
                    continue
                gap = sp["coord"] - cx if near_side else cx - sp["coord"]
            if 0 < gap <= 2.5 * r.size:
                hits.append((gap, i))
        return sorted(hits)

    first = [candidates(sp, True) for sp in spans]
    reserved = {h[0][1] for h in first if h}
    for sp, hits in zip(spans, first):
        if not hits:
            hits = [h for h in candidates(sp, False) if h[1] not in reserved and h[1] not in claimed]
        hits = [h for h in hits if h[1] not in claimed]
        sp["run"] = hits[0][1] if hits else None
        if sp["run"] is not None:
            claimed.add(sp["run"])

    # views
    comp_ids: dict[int, str] = {}
    anchors_pts = []
    for sp in spans:
        mid = (sp["a"] + sp["b"]) / 2.0
        anchors_pts.append((mid, sp["coord"]) if sp["orientation"] == "horizontal" else (sp["coord"], mid))
    anchors_pts += [b["center"] for b in bubbles]
    anchors_pts += [R._center(runs[lv["run"]].bbox) for lv in levels]
    comps = sorted({c for c in (_component(label, *p) for p in anchors_pts) if c},
                   key=lambda c: min((p[1], p[0]) for p in anchors_pts if _component(label, *p) == c))
    for n, c in enumerate(comps, 1):
        comp_ids[c] = f"p{number}-v{n}"

    def view_of(x: float, y: float) -> str | None:
        return comp_ids.get(_component(label, x, y))

    for b in bubbles:
        b["view"] = view_of(*b["center"])
        if b["orientation"] is None:
            findings.append({"code": "axis_orientation_unknown", "page": number, "label": b["label"],
                             "message": "lone bubble without a radial line; axis not used for binding"})
    for lv in levels:
        lv["view"] = view_of(*R._center(runs[lv["run"]].bbox))
    for code, lv, expected_y in _level_outliers(levels):  # value vs drawn line disagree: architect (D112)
        lv["level_y_drawn"], lv["level_y"], lv["line_reason"] = lv["level_y"], None, code
        findings.append({"code": code, "page": number, "text": lv["text"], "view": lv["view"],
                         "drawn_y_pt": lv["level_y_drawn"], "expected_y_pt": expected_y,
                         "message": "written level disagrees with the other marks of the view; kept as written (D112)"})

    values: list[dict[str, Any]] = []
    openings: dict[R.Box, str] = {}
    counter = 0

    def axis_at(view: str | None, orient: str, pos: float) -> str | None:
        want = "vertical" if orient == "horizontal" else "horizontal"
        hits = [b["label"] for b in bubbles if b["view"] == view and b["orientation"] == want
                and abs(b["position"] - pos) <= END_SNAP_PT]
        return hits[0] if len(hits) == 1 else None

    untexted: dict[str, int] = {}
    for sp in spans:
        counter += 1
        orient, c, a, b = sp["orientation"], sp["coord"], sp["a"], sp["b"]
        p0, p1 = ((a, c), (b, c)) if orient == "horizontal" else ((c, a), (c, b))
        mid = ((p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0)
        view = view_of(*mid)
        run = runs[sp["run"]] if sp["run"] is not None else None
        value = R.check_dimension_text(run.text) if run is not None else None
        rec = {"id": f"p{number}-d{counter:04d}", "kind": "dimension", **loc, "view": view,
               "raw": run.text if run else None, "value": value, "unit": "mm" if value is not None else None,
               "orientation": orient, "bbox": list(run.bbox) if run else None,
               "span": {"p0": list(p0), "p1": list(p1), "length_pt": b - a}, "method": "pdf-vector-text+ticks"}
        if run is None:
            untexted[orient] = untexted.get(orient, 0) + 1
            counter -= 1
            continue
        if value is None:
            code = "dimension_text_invalid"
            findings.append({"code": code, "page": number, "id": rec["id"], "text": rec["raw"]})
            rec["binding"] = {"type": "unbound", "reason": code}
            values.append(rec)
            continue
        if view is None:
            rec["binding"] = {"type": "unbound", "reason": "no_view"}
        else:
            la, lb = axis_at(view, orient, a), axis_at(view, orient, b)
            if la and lb and la != lb:
                rec["binding"] = {"type": "axis_pair", "axes": [la, lb]}
            else:
                best = None
                for r in rects:
                    if view_of(r[0], r[1]) != view:  # a corner: the interior may be empty
                        continue
                    lo, hi = (r[0], r[2]) if orient == "horizontal" else (r[1], r[3])
                    across = (r[1], r[3]) if orient == "horizontal" else (r[0], r[2])
                    dist = min(abs(c - across[0]), abs(c - across[1]))
                    if abs(lo - a) <= END_SNAP_PT and abs(hi - b) <= END_SNAP_PT and dist <= 80.0:
                        if best is None or dist < best[0]:
                            best = (dist, r)
                if best is not None:
                    oid = openings.setdefault(best[1], f"{view}-o{len(openings) + 1}")
                    rec["binding"] = {"type": "opening", "opening": oid}
                elif orient == "vertical":
                    la_ = [lv["text"] for lv in levels if lv["view"] == view and lv["level_y"] is not None and abs(lv["level_y"] - a) <= END_SNAP_PT]
                    lb_ = [lv["text"] for lv in levels if lv["view"] == view and lv["level_y"] is not None and abs(lv["level_y"] - b) <= END_SNAP_PT]
                    if len(set(la_)) == 1 and len(set(lb_)) == 1:
                        rec["binding"] = {"type": "level_pair", "levels": [lb_[0], la_[0]]}
                if "binding" not in rec:
                    reason = "ends_not_on_axes_openings_or_levels" if not (la or lb) else "one_end_on_axis_only"
                    rec["binding"] = {"type": "unbound", "reason": reason}
        values.append(rec)

    for lv in levels:
        counter += 1
        r = runs[lv["run"]]
        values.append({"id": f"p{number}-l{counter:04d}", "kind": "level", **loc, "view": lv["view"],
                       "raw": r.text, "value": lv["value_m"], "unit": "m", "orientation": None,
                       "bbox": list(r.bbox), "span": None, "method": "pdf-vector-text",
                       "level_y": lv["level_y"], "level_y_drawn": lv.get("level_y_drawn"), "absolute_text": lv["absolute_text"],
                       "binding": ({"type": "unbound", "reason": "no_view"} if not lv["view"]
                                   else {"type": "spot_level", "level": r.text, "spot_bbox": list(lv["spot_bbox"])} if lv["spot_bbox"]
                                   else {"type": "unbound", "reason": lv["line_reason"]} if lv["level_y"] is None
                                   else {"type": "level", "level": r.text, "level_y": lv["level_y"]})})
    for i, r in usable:
        if i in claimed or not _LONG_DIM.match(r.text) or _NOMINAL.search(r.text):
            continue
        counter += 1
        values.append({"id": f"p{number}-t{counter:04d}", "kind": "dimension", **loc,
                       "view": view_of(*R._center(r.bbox)), "raw": r.text,
                       "value": R.check_dimension_text(r.text), "unit": "mm", "orientation": None,
                       "bbox": list(r.bbox), "span": None, "method": "pdf-vector-text",
                       "binding": {"type": "unbound", "reason": "no_dimension_line"}})

    views = []
    for c in comps:
        vid = comp_ids[c]
        cells = [(i, j) for i, row in enumerate(label) for j, v in enumerate(row) if v == c]
        ys, xs = [i for i, _ in cells], [j for _, j in cells]
        views.append({"id": vid, **loc, "bbox": [min(xs) * GRID_PT, min(ys) * GRID_PT, (max(xs) + 1) * GRID_PT, (max(ys) + 1) * GRID_PT],
                      "axes": sorted(({"label": b["label"], "orientation": b["orientation"], "position": b["position"]}
                                      for b in bubbles if b["view"] == vid and b["orientation"]),
                                     key=lambda x: (x["orientation"], x["position"]))})
    opening_list = [{"id": oid, "view": oid.rsplit("-o", 1)[0], **loc, "bbox": list(box),
                     "identity": "unverified closed rectangle at both span ends; vision/human check required"} for box, oid in openings.items()]
    if untexted:
        findings.append({"code": "tick_spans_without_text", "page": number, "count_by_orientation": untexted,
                         "message": "tick-to-tick spans with no value text (hatching, extension ticks); not values"})
    return {"status": "ok", "views": views, "values": values, "openings": opening_list,
            "findings": findings, "nominal_print_scale_text": nominal}


# ---------------------------------------------------------------- calibration


def calibrate_view(spans: list[dict[str, Any]], anchors: list[dict[str, Any]]) -> dict[str, Any]:
    """Fit mm/pt from >= 2 independent anchors; spans are axis-bound values of ONE view."""
    used = []
    seen_pairs: set[frozenset[str]] = set()
    seen_spans: set[tuple[float, ...]] = set()
    for an in anchors:
        pair = frozenset(an["axes"])
        model = an["model_mm"]
        hits = [v for v in spans if v["binding"]["type"] == "axis_pair" and frozenset(v["binding"]["axes"]) == pair]
        if not hits or pair in seen_pairs:
            continue
        v = hits[0]
        key = tuple(round(t, 2) for t in v["span"]["p0"] + v["span"]["p1"])
        if key in seen_spans:
            continue
        length = v["span"]["length_pt"]
        if not (R._finite(length, model) and length > 0 and model > 0):
            continue
        seen_pairs.add(pair)
        seen_spans.add(key)
        used.append({"axes": list(an["axes"]), "model_mm": model, "measured_pt": length, "value_id": v["id"],
                     "source": an.get("source")})
    if len(used) < 2:
        return {"status": "unknown", "mm_per_pt": None, "anchors": used,
                "reason": f"{len(used)} independent model anchor(s) matched; >= 2 required"}
    s = sum(u["model_mm"] * u["measured_pt"] for u in used) / sum(u["measured_pt"] ** 2 for u in used)
    ok = True
    for u in used:
        u["residual_mm"] = s * u["measured_pt"] - u["model_mm"]
        u["tolerance_mm"] = max(R.DIM_ABS_TOL_MM, R.DIM_REL_TOL * u["model_mm"])
        u["residual_ok"] = R._finite(u["residual_mm"]) and abs(u["residual_mm"]) < u["tolerance_mm"]
        ok = ok and u["residual_ok"]
    if not ok:
        return {"status": "unknown", "mm_per_pt": None, "anchors": used,
                "reason": "anchor residuals reach the tolerance max(10 mm, 0.5 %); scale not derived"}
    return {"status": "calibrated", "mm_per_pt": s, "anchors": used,
            "reason": f"least-squares fit through origin of {len(used)} independent model anchors"}


def _load_anchors(path: str | Path | None, pdf_sha: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if path is None:
        return None, []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BindingError("anchors_unreadable", str(exc)) from None
    src = data.get("source") if isinstance(data, dict) else None
    if not isinstance(src, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(src.get("sha256", ""))):
        raise BindingError("anchors_source_missing", "anchors need source.sha256 of the independent model")
    if src["sha256"] == pdf_sha:
        raise BindingError("anchors_not_independent", "anchor source is the PDF itself")
    if src.get("kind") not in ("dwg", "bim", "ifc", "survey"):
        raise BindingError("anchors_source_kind", f"source.kind {src.get('kind')!r} is not dwg/bim/ifc/survey")
    out = []
    for k, an in enumerate(data.get("anchors") or []):
        axes, mm, page = an.get("axes"), an.get("model_mm"), an.get("page")
        if (not isinstance(axes, list) or len(axes) != 2 or axes[0] == axes[1]
                or not all(isinstance(a, str) and a for a in axes)):
            raise BindingError("anchor_axes", f"anchor {k}: axes must be two different labels")
        if isinstance(mm, bool) or not isinstance(mm, (int, float)) or not math.isfinite(mm) or mm <= 0:
            raise BindingError("anchor_value", f"anchor {k}: model_mm must be finite and positive, got {mm!r}")
        if isinstance(page, bool) or not isinstance(page, int):
            raise BindingError("anchor_page", f"anchor {k}: page must be an int")
        out.append({"axes": axes, "model_mm": float(mm), "page": page, "view": an.get("view"),
                    "source": src.get("sha256")})
    return src, out


# ---------------------------------------------------------------- album


def bind_album(pdf: str | Path, pages: list[int] | None = None, *, anchors: str | Path | None = None,
               album_index: str | Path | None = None) -> dict[str, Any]:
    pymupdf = R._import_pymupdf()
    p = Path(pdf)
    if not p.is_file():
        raise R.AlbumReadError("not_found", str(p))
    data = p.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    anchor_src, anchor_list = _load_anchors(anchors, sha)
    sheets: dict[int, str | None] = {}
    if album_index is not None:
        idx = json.loads(Path(album_index).read_text(encoding="utf-8"))
        if (idx.get("source") or {}).get("sha256") != sha:
            raise BindingError("album_index_mismatch", "album_index.json describes another source")
        sheets = {int(pg["pdf_page"]): pg.get("printed_sheet") for pg in idx.get("pages", [])}
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        raise R.AlbumReadError("corrupt", f"{p.name}: {exc}") from None
    try:
        if doc.needs_pass:
            raise R.AlbumReadError("encrypted", p.name)
        count = doc.page_count
        wanted = list(range(1, count + 1)) if pages is None else list(pages)
        if not wanted or len(set(wanted)) != len(wanted):
            raise R.AlbumReadError("bad_page_number", f"pages must be non-empty and distinct: {wanted}")
        for n in wanted:
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= count:
                raise R.AlbumReadError("page_out_of_range", f"page {n!r} not in 1..{count}")
        bad = [a for a in anchor_list if a["page"] not in wanted]
        if bad:
            raise BindingError("anchor_page", f"anchor page {bad[0]['page']} is not read")
        out_pages, views, values, openings, findings, nominal = [], [], [], [], [], []
        for n in sorted(wanted):
            res = _bind_page(pymupdf, doc[n - 1], n, sheets.get(n))
            out_pages.append({"page": n, "sheet": sheets.get(n), "status": res["status"]})
            views += res["views"]
            values += res["values"]
            openings += res["openings"]
            findings += res["findings"]
            nominal += [{**t, "page": n} for t in res["nominal_print_scale_text"]]
    finally:
        doc.close()

    for view in views:
        mine = [a for a in anchor_list if a["page"] == view["page"] and a["view"] in (None, view["id"])]
        spans = [v for v in values if v["view"] == view["id"] and v["span"] is not None]
        view["scale"] = calibrate_view(spans, mine) if mine else {
            "status": "unknown", "mm_per_pt": None, "anchors": [],
            "reason": "no independent model anchors supplied; nominal print scale and $INSUNITS are never used"}
        scale = view["scale"]["mm_per_pt"]
        anchor_ids = {u["value_id"] for u in view["scale"]["anchors"]} if scale else set()
        for v in values:
            if v["view"] != view["id"]:
                continue
            if v["kind"] != "dimension" or v["span"] is None or v["binding"]["type"] == "unbound" or scale is None:
                continue
            measured = v["span"]["length_pt"] * scale
            v["measured_mm"] = measured
            if v["id"] in anchor_ids:
                v["check"] = "anchor"
                continue
            status, tol = R.check_dimension(measured, v["value"])
            v["check"], v["tolerance_mm"] = ("ok" if status == "ok" else "mismatch"), tol
            if status != "ok":
                findings.append({"code": "dimension_mismatch", "page": v["page"], "id": v["id"], "written_mm": v["value"],
                                 "measured_mm": measured, "message": "kept as written; architect question (D112)"})
    for a in anchor_list:
        if not any(u for vw in views for u in vw["scale"]["anchors"] if vw["page"] == a["page"] and set(u["axes"]) == set(a["axes"])):
            findings.append({"code": "anchor_unmatched", "page": a["page"], "axes": a["axes"],
                             "message": "no axis-bound span for this anchor in any view"})
    for v in values:
        v.setdefault("measured_mm", None)
        v.setdefault("check", "not_checked")
        bound = v["binding"]["type"] != "unbound"
        scaled = v["kind"] == "level" or v.get("measured_mm") is not None
        v["status"] = "bound" if bound and scaled else "unresolved"
    counts: dict[str, int] = {}
    for v in values:
        counts[v["binding"]["type"]] = counts.get(v["binding"]["type"], 0) + 1
    gates = ["binding_review", "ground_truth", "approval"]
    if any(vw["scale"]["status"] != "calibrated" for vw in views) or not views:
        gates.insert(0, "calibration")
    return {"schema": SCHEMA, "source": {"name": p.name, "sha256": sha, "page_count": count},
            "anchors_source": anchor_src, "pages": out_pages, "views": views, "openings": openings,
            "values": values, "nominal_print_scale_text": nominal, "findings": findings,
            "summary": {"values": len(values), "by_binding": dict(sorted(counts.items())),
                        "vertical_dimensions": sum(1 for v in values if v["orientation"] == "vertical" and v["value"] is not None),
                        "views": len(views),
                        "calibrated_views": sum(1 for vw in views if vw["scale"]["status"] == "calibrated"),
                        "unresolved": sum(1 for v in values if v["status"] == "unresolved")},
            "passed": False, "open_gates": gates,
            "note": "technical extraction only; not measured geometry unless a view is calibrated, not acceptance"}


def dimensions_to_json(doc: dict[str, Any]) -> str:
    return json.dumps(R._normalise(doc), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Bind album dimensions/levels/openings -> dimensions.json (#1234)")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--pages", type=str, default=None, help="comma list of 1-based pages (default all)")
    ap.add_argument("--anchors", type=Path, default=None)
    ap.add_argument("--album-index", type=Path, default=None)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    out = args.output.resolve()
    inputs = [x.resolve() for x in (args.pdf, args.anchors, args.album_index) if x is not None]
    if out in inputs:
        print(f"output_is_input: {out}")
        return 2
    if out.exists():
        print(f"output_exists: {out}")
        return 2
    try:
        pages = None if args.pages is None else [int(x) for x in args.pages.split(",") if x.strip()]
        doc = bind_album(args.pdf, pages, anchors=args.anchors, album_index=args.album_index)
    except (ValueError, OSError, R.AlbumExtraMissing) as exc:
        print(str(exc))
        return 2
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(dimensions_to_json(doc))
    print(json.dumps({"passed": False, **doc["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
