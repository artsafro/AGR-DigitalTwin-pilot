"""Page-referenced schedule/legend normalization and typed CSV export (#1235).

Pattern: n/a | new-case: route album index schedule regions to two table engines, keep every cell typed
with its disagreement / merge provenance, and bind RAL / finish codes to their source rows or legend lines
without any default material.

``export_schedules(pdf, output, album_index=None, pages=None)`` writes into a NEW directory:

- ``schedules/<table_id>.csv``: one line per cell (long format, columns :data:`CSV_COLUMNS`), exact cell text of
  the primary engine, the second engine's text, row type, column unit, merge provenance and page/sheet/bbox.
  :func:`validate_schedule_csv` checks the typed schema.
- ``schedules/<table_id>.json``: sidecar (``schemas/AlbumSchedule.schema.json``): columns, row types, embedded
  measures, suspect-cell list, merged cells, engines, source hash, CSV hash.
- ``schedules.json``: page accounting (routed / not routed with the reason) and the table list.
- ``materials.json`` (``schemas/AlbumMaterials.schema.json``).

Rules (each has a test in ``tests/test_album_schedules.py``):

- Routing: with ``album_index`` (from :mod:`dt_ai.album.intake`, same source SHA-256 or an error) only pages
  with a ``table_extraction`` region are extracted; the ROI is the region ``schedule_context_candidate_unverified``
  (else the union of the table regions). Tables are detected on the routed page and kept when they touch the ROI
  (a text-envelope ROI may cut a table); tables outside it are listed in ``outside_roi``. Other pages are
  ``not_routed`` with the reason. Explicit ``pages`` use the whole page. Legends (RAL/NCS codes in text) are
  scanned on every page in scope. pdfplumber boxes are shifted by its page origin (cropbox offset) into PyMuPDF
  coordinates; a rotated page gets no second engine (``second_engine_coordinates_differ``).
- Two engines: PyMuPDF ``find_tables`` (primary) and pdfplumber ``find_tables`` (secondary, optional:
  ``uv run --with pdfplumber==0.11.10``). Tables pair by bbox IoU >= 0.8. Equal text -> ``agree``; different
  text (whitespace included) or None vs text -> ``suspect`` with both strings; a different grid -> every cell
  ``suspect`` ``shape_mismatch``; no second table / engine -> every cell ``single_engine``. The CSV ``text`` is
  the primary string only as a record: every non-agreeing cell is in ``suspect_cells`` - nothing is picked
  silently. A table only the second engine found is exported with its own cells, all ``single_engine``.
- Merged cells: a None cell stays empty (never copied); ``merged_from`` names the covering cell left or above
  (from the engine's cell boxes) or the cell is ``merged_unresolved`` and suspect.
- Row types (heuristic, ``row_type_status = heuristic_unapproved``): ``total`` (starts with итого/всего/total),
  ``empty``, ``header`` (single-cell title rows before the column header, the non-numeric column header rows and
  a 1..N column-numbering row before the first data row), ``category`` (one non-numeric cell after the header),
  ``data`` (otherwise).
- Units from the column header: kind (quantity / length / area / volume / mass / text) and unit
  (pcs / m / mm / m2 / m3 / kg). A unit that contradicts the kind -> ``unknown``; a kind without a unit keeps
  ``unit = ''`` (never guessed). Measures written inside a cell (``5 505 метров``) are listed per row, raw.
- Materials: a column whose header names a finish/material/colour gives one entry per data row: ``present``
  (own text and its codes), ``missing`` (empty cell) or ``merged_unresolved`` (None cell) - the last two have
  no label and no code; a neighbour row or another job never supplies one. Codes elsewhere in a table bind to
  their row; codes outside tables are legend lines with the swatch found left of the text (or none) and
  binding ``unbound`` ``region_application_requires_review``. ``default_material`` is always null.
- Fail-closed: ``passed`` is always false (row typing, unit, binding and approval stay open); bad pages, a
  non-finite ROI, a foreign index, an existing output or an output equal to an input raise and write nothing;
  the source hash is checked before and after extraction.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from dt_ai.album.reader import EXTRA_HINT, AlbumExtraMissing, AlbumReadError

SCHEMA = "album-schedule/1"
MATERIALS_SCHEMA = "album-materials/1"
MANIFEST_SCHEMA = "album-schedules/1"
IOU_PAIR = 0.8
OPEN_GATES = ["row_type_review", "unit_review", "region_binding", "ground_truth", "approval"]

ROW_TYPES = ("header", "category", "data", "total", "empty")
CELL_STATUSES = ("agree", "empty", "suspect", "single_engine", "merged", "merged_unresolved")
VALUE_KINDS = ("quantity", "length", "area", "volume", "mass", "text", "unknown")
UNITS = ("", "pcs", "m", "mm", "m2", "m3", "kg")

#: Typed CSV schema: (column, type). Types: str, int>=1, enum:<name>, float|'' (finite).
CSV_COLUMNS: tuple[tuple[str, str], ...] = (
    ("table_id", "str"), ("row", "int"), ("col", "int"), ("row_type", "enum:row_type"),
    ("cell_status", "enum:cell_status"), ("text", "str"), ("text_alt", "str"), ("merged_from", "str"),
    ("column_label", "str"), ("value_kind", "enum:value_kind"), ("unit", "enum:unit"), ("page", "int"),
    ("sheet", "str"), ("x0", "float"), ("y0", "float"), ("x1", "float"), ("y1", "float"),
)
CSV_NAMES = [name for name, _ in CSV_COLUMNS]
_ENUMS = {"row_type": ROW_TYPES, "cell_status": CELL_STATUSES, "value_kind": VALUE_KINDS, "unit": UNITS}

_NUM = re.compile(r"^[+\-\u2212]?\d[\d \u00a0\u202f]*(?:[.,]\d+)?$")
_TOTAL = re.compile(r"^\s*(итого|всего|total)\b", re.I)
_RAL = re.compile(r"\b(?:RAL|РАЛ)[ \u00a0]?(\d{4})\b", re.I)
_NCS = re.compile(r"\bNCS[ \u00a0]?(S[ \u00a0]?\d{4}-[A-Z]\d{0,2}[A-Z]?)\b")
_FINISH_HEADER = re.compile(r"отделк|материал|цвет|покрыт|finish|material|colou?r|\bral\b", re.I)
_KINDS = [(re.compile(p, re.I), k) for p, k in [
    (r"кол-?во|количеств|\bqty\b|quantity", "quantity"), (r"площад|\barea\b", "area"),
    (r"объ[её]м|volume", "volume"), (r"длин|length|высот|ширин|толщин|размер|сечени", "length"),
    (r"масс|\bвес\b|weight|mass", "mass")]]
_UNITS = [(re.compile(p, re.I), u) for p, u in [
    (r"(?:м|m)\s*(?:2|²)|кв\.?\s*м", "m2"), (r"(?:м|m)\s*(?:3|³)|куб\.?\s*м", "m3"),
    (r"(?<![а-яa-z])(?:мм|mm)(?![а-яa-z])", "mm"), (r"п\.?\s*м\b|м\.?\s*п\b|пог\.?\s*м", "m"),
    (r"(?<![а-яa-z])(?:шт|pcs)(?![а-яa-z])", "pcs"), (r"(?<![а-яa-z])(?:кг|kg)(?![а-яa-z])", "kg"),
    (r"(?<![а-яa-z.])(?:м|m)(?![а-яa-z2-3²³.])", "m")]]
_UNIT_KIND = {"m2": "area", "m3": "volume", "mm": "length", "m": "length", "pcs": "quantity", "kg": "mass"}
_MEASURE = re.compile(r"(\d[\d \u00a0]*(?:[.,]\d+)?(?:\s?[xх×]\s?\d+(?:[.,]\d+)?)*)\s?"
                      r"(метр(?:ов|а)?|мм|mm|м2|м²|м3|м³|м|m|шт|кг)(?![а-яa-z])", re.I)
_MEASURE_UNIT = {"метр": "m", "метров": "m", "метра": "m", "мм": "mm", "mm": "mm", "м2": "m2", "м²": "m2",
                 "м3": "m3", "м³": "m3", "м": "m", "m": "m", "шт": "pcs", "кг": "kg"}


# ------------------------------------------------------------------ pure helpers


def _numeric(text: str | None) -> bool:
    return bool(text) and bool(_NUM.match(text.strip()))


def row_types(cells: list[list[str | None]], boxes: list[list[Any]] | None = None) -> list[str]:
    """Heuristic header/category/data/total/empty type of every row (see module rules).

    A row is "spanned" (title/category) when one cell is filled and every other cell is None; with cell boxes
    the filled cell must also reach the table's right edge, so a vertically merged cell does not make a data
    row look like a category.
    """
    right = max((b[2] for line in boxes or [] for b in line if b is not None), default=None)
    out: list[str] = []
    multi_header = data = False
    spanned_header = False  # the last header row has a covered (None) cell: a multi-level header may follow
    for r, row in enumerate(cells):
        filled = [c.strip() for c in row if c is not None and c.strip()]
        spanned = len(filled) == 1 and sum(c is None for c in row) == len(row) - 1
        if spanned and right is not None and r < len(boxes):  # type: ignore[arg-type]
            own = [b for b, c in zip(boxes[r], row) if c is not None and c.strip()]  # type: ignore[index]
            spanned = bool(own) and own[0] is not None and own[0][2] >= right - 1.0
        if any(_TOTAL.match(c) for c in filled):
            out.append("total")
        elif not filled:
            out.append("empty")
        elif spanned and not _numeric(filled[0]):
            out.append("category" if multi_header or data else "header")
        elif not data and (not multi_header or spanned_header) and not any(_numeric(c) for c in filled):
            multi_header, spanned_header = True, any(c is None for c in row)
            out.append("header")
        elif not data and multi_header and filled == [str(i + 1) for i in range(len(filled))]:
            out.append("header")  # 1..N column numbering under the header
        else:
            data = True
            out.append("data")
    return out


def column_unit(label: str | None) -> tuple[str, str]:
    """(value_kind, unit) from a column header; a contradiction gives ``unknown``, a missing unit ''."""
    text = (label or "").replace("\n", " ").strip()
    if not text:
        return "unknown", ""
    kind = next((k for rx, k in _KINDS if rx.search(text)), None)
    unit = next((u for rx, u in _UNITS if rx.search(text)), "")
    if unit and kind and _UNIT_KIND[unit] != kind:
        return "unknown", ""
    if unit:
        return _UNIT_KIND[unit], unit
    return (kind, "") if kind else ("text", "")


def cell_measures(text: str | None) -> list[dict[str, str]]:
    """Numbers with a unit word written inside a cell, raw; nothing is converted or summed."""
    out = []
    for m in _MEASURE.finditer(text or ""):
        unit = _MEASURE_UNIT[m.group(2).casefold()]
        out.append(dict(raw=m.group(0).strip(), value_text=m.group(1).strip(), unit=unit, kind=_UNIT_KIND[unit]))
    return out


def material_codes(text: str | None) -> list[str]:
    """RAL / NCS codes in reading order, normalised as ``RAL 7021`` / ``NCS S 2010-Y30R``."""
    found = [(m.start(), "RAL " + m.group(1)) for m in _RAL.finditer(text or "")]
    found += [(m.start(), "NCS " + re.sub(r"^S[ \u00a0]?", "S ", m.group(1))) for m in _NCS.finditer(text or "")]
    return [code for _, code in sorted(found)]


def _iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _ref(r: int, c: int) -> str:
    return f"r{r + 1}c{c + 1}"


def _merge_source(cells: list[list[str | None]], boxes: list[list[Any]] | None, r: int, c: int) -> str | None:
    """Covering cell of a None slot from the engine's cell boxes: left in the row, else above in the column."""
    if not boxes:
        return None
    xs = [b[c][0] for b in boxes if c < len(b) and b[c] is not None]
    ys = [b[k][1] for b in boxes[r:r + 1] for k in range(len(b)) if b[k] is not None]
    for k in range(c - 1, -1, -1):
        box = boxes[r][k]
        if box is not None:
            if xs and box[2] > min(xs) + 1.0:
                return _ref(r, k)
            break
    for k in range(r - 1, -1, -1):
        box = boxes[k][c] if c < len(boxes[k]) else None
        if box is not None:
            if ys and box[3] > min(ys) + 1.0:
                return _ref(k, c)
            break
    return None


def build_table(table_id: str, page: int, sheet: str | None, primary: dict[str, Any] | None,
                secondary: dict[str, Any] | None, *, secondary_status: str = "ok",
                engines: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reconcile one table of two engines into typed rows/columns/cells (see module rules)."""
    base = primary if primary is not None else secondary
    if base is None:
        raise ValueError("table needs at least one engine")
    cells, boxes = base["cells"], base.get("cell_boxes")
    n_rows, n_cols = len(cells), max((len(r) for r in cells), default=0)
    if not n_rows or not n_cols or any(len(r) != n_cols for r in cells):
        raise ValueError(f"ragged or empty table {table_id}")
    other = secondary if primary is not None else None
    if other is None:
        mode = "single"
        reason = secondary_status if primary is not None else "primary_engine_missed_table"
    elif len(other["cells"]) != n_rows or any(len(r) != n_cols for r in other["cells"]):
        mode, reason = "shape", "shape_mismatch"
    else:
        mode, reason = "pair", "engines_disagree"
    types = row_types(cells, boxes)
    # Column label: the column's own non-numeric texts of the multi-cell header rows, joined top-down.
    head_rows = [r for r in range(n_rows) if types[r] == "header"
                 and sum(1 for x in cells[r] if x is not None and x.strip()) > 1]
    columns = []
    for c in range(n_cols):
        label = " | ".join(cells[r][c].strip() for r in head_rows
                           if cells[r][c] and cells[r][c].strip() and not _numeric(cells[r][c]))
        kind, unit = column_unit(label)
        columns.append(dict(col=c + 1, label=label, value_kind=kind, unit=unit))
    grid, suspects, merged = [], [], []
    for r in range(n_rows):
        line = []
        for c in range(n_cols):
            text = cells[r][c]
            alt = other["cells"][r][c] if mode == "pair" else None
            box = boxes[r][c] if boxes and r < len(boxes) and c < len(boxes[r]) else None
            cell = dict(text=text or "", text_alt="", status="agree", merged_from="",
                        bbox=None if box is None else [float(v) for v in box])
            if mode == "pair":
                if text != alt:
                    cell.update(status="suspect", text_alt=alt or "")
                    suspects.append(dict(row=r + 1, col=c + 1, reason=reason, primary=text, secondary=alt))
            else:
                cell["status"] = "suspect" if mode == "shape" else "single_engine"
                suspects.append(dict(row=r + 1, col=c + 1, reason=reason, primary=text, secondary=None))
            if text is None:
                src = _merge_source(cells, boxes, r, c)
                cell["merged_from"] = src or ""
                if src:
                    merged.append(dict(row=r + 1, col=c + 1, merged_from=src))
                if cell["status"] == "agree":
                    cell["status"] = "merged" if src else "merged_unresolved"
                    if not src:
                        suspects.append(dict(row=r + 1, col=c + 1, reason="merged_source_unresolved",
                                             primary=None, secondary=alt))
            elif cell["status"] == "agree" and not text.strip():
                cell["status"] = "empty"
            line.append(cell)
        grid.append(line)
    rows = [dict(row=r + 1, row_type=types[r],
                 measures=[dict(col=c + 1, **m) for c in range(n_cols) for m in cell_measures(cells[r][c])])
            for r in range(n_rows)]
    return dict(table_id=table_id, page=page, sheet=sheet,
                bbox=[float(v) for v in base["bbox"]], n_rows=n_rows, n_cols=n_cols, columns=columns,
                rows=rows, cells=grid, suspect_cells=suspects, merged_cells=merged,
                engines=engines or {}, row_type_status="heuristic_unapproved")


def table_csv_rows(table: dict[str, Any]) -> list[list[str]]:
    out = []
    for r, line in enumerate(table["cells"]):
        rtype = table["rows"][r]["row_type"]
        for c, cell in enumerate(line):
            col = table["columns"][c]
            typed = rtype in ("data", "total")
            box = cell["bbox"] or ["", "", "", ""]
            out.append([table["table_id"], str(r + 1), str(c + 1), rtype, cell["status"], cell["text"],
                        cell["text_alt"], cell["merged_from"], col["label"],
                        col["value_kind"] if typed else "text", col["unit"] if typed else "",
                        str(table["page"]), table["sheet"] or ""] + [b if b == "" else repr(float(b)) for b in box])
    return out


def _csv_bytes(table: dict[str, Any]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_NAMES)
    writer.writerows(table_csv_rows(table))
    return buf.getvalue().encode("utf-8")


def write_table_csv(table: dict[str, Any], path: str | Path) -> None:
    with Path(path).open("xb") as fh:
        fh.write(_csv_bytes(table))


def validate_schedule_csv(path: str | Path) -> list[str]:
    """Errors of a schedule CSV against :data:`CSV_COLUMNS`; [] when valid. Empty file is an error."""
    try:
        with Path(path).open(encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
    except (OSError, UnicodeDecodeError) as exc:
        return [f"unreadable: {exc}"]
    if not rows:
        return ["empty file: no header"]
    if rows[0] != CSV_NAMES:
        return [f"header mismatch: {rows[0]}"]
    if len(rows) == 1:
        return ["no cell rows"]
    errors = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) != len(CSV_NAMES):
            errors.append(f"line {i}: {len(row)} fields")
            continue
        for (name, kind), value in zip(CSV_COLUMNS, row):
            if kind == "int":
                ok = value.isdigit() and int(value) >= 1
            elif kind == "float":
                try:
                    ok = value == "" or math.isfinite(float(value))
                except ValueError:
                    ok = False
            elif kind.startswith("enum:"):
                ok = value in _ENUMS[kind[5:]]
            else:
                ok = True
            if not ok:
                errors.append(f"line {i}: {name}={value!r}")
    return errors


def _material(source_kind: str, label: str | None, code: str | None, status: str, binding: dict[str, Any],
              page: int, sheet: str | None, bbox: list[float] | None, **extra: Any) -> dict[str, Any]:
    return dict(source_kind=source_kind, original_label=label, code=code,
                code_system=None if code is None else code.split()[0], status=status, binding=binding,
                legend_symbol=extra.pop("legend_symbol", None), merged_from=extra.pop("merged_from", None),
                page=page, sheet=sheet, bbox=bbox, authority="pdf_album_unapproved", default_material=None,
                conflicts=[], **extra)


def finish_materials(table: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per data row and finish column; missing/merged rows stay without label and code."""
    out = []
    for col in table["columns"]:
        if not _FINISH_HEADER.search(col["label"]):
            continue
        c = col["col"] - 1
        for row in table["rows"]:
            if row["row_type"] != "data":
                continue
            r = row["row"] - 1
            cell = table["cells"][r][c]
            binding = dict(kind="schedule_row", table_id=table["table_id"], row=r + 1, col=c + 1)
            base = dict(page=table["page"], sheet=table["sheet"], bbox=cell["bbox"])
            if cell["status"] in ("merged", "merged_unresolved") or (cell["merged_from"] and not cell["text"]):
                out.append(_material("schedule_finish_cell", None, None, "merged_unresolved", binding,
                                     merged_from=cell["merged_from"] or None, **base))
            elif not cell["text"].strip():
                out.append(_material("schedule_finish_cell", None, None, "missing", binding, **base))
            else:
                codes = material_codes(cell["text"]) or [None]
                for code in codes:
                    out.append(_material("schedule_finish_cell", cell["text"], code, "present", binding, **base))
    return out


# ------------------------------------------------------------------ PDF side


def _fitz() -> Any:
    try:
        import pymupdf
    except ImportError as exc:
        raise AlbumExtraMissing(EXTRA_HINT) from exc
    return pymupdf


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _finite_box(box: Any, what: str) -> list[float]:
    if (not isinstance(box, (list, tuple)) or len(box) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in box)
            or box[2] <= box[0] or box[3] <= box[1]):
        raise ValueError(f"invalid bbox {what}: {box!r}")
    return [float(v) for v in box]


def _engine_table(t: Any, dx: float = 0.0, dy: float = 0.0) -> dict[str, Any]:
    """Engine table -> plain dict in PyMuPDF page coordinates (pdfplumber boxes are shifted by its page origin)."""
    def shift(b: Any) -> list[float]:
        return [float(b[0]) + dx, float(b[1]) + dy, float(b[2]) + dx, float(b[3]) + dy]
    cells = [[None if v is None else str(v) for v in row] for row in t.extract()]
    boxes = [[None if b is None else shift(b) for b in row.cells] for row in t.rows]
    return dict(bbox=shift(t.bbox), cells=cells, cell_boxes=boxes)


def _overlaps(box: list[float], roi: list[float]) -> bool:
    return min(box[2], roi[2]) > max(box[0], roi[0]) and min(box[3], roi[3]) > max(box[1], roi[1])


def _route(index: dict[str, Any] | None, count: int, pages: list[int] | None) -> list[dict[str, Any]]:
    if index is None:
        return [dict(pdf_page=p, sheet=None, route="table_extraction", reason="explicit_page_request", roi=None)
                for p in pages]  # type: ignore[union-attr]
    listed = [p.get("pdf_page") for p in index.get("pages", [])]
    if len(set(listed)) != len(listed):
        raise ValueError(f"album_index_duplicate_page: {sorted(n for n in set(listed) if listed.count(n) > 1)}")
    by_page = {p.get("pdf_page"): p for p in index.get("pages", [])}
    wanted = pages if pages is not None else list(range(1, count + 1))
    out = []
    for n in wanted:
        page = by_page.get(n)
        if page is None:
            out.append(dict(pdf_page=n, sheet=None, route="not_routed", reason="page_missing_from_index", roi=None))
            continue
        sheet = page.get("printed_sheet")
        regions = [r for r in page.get("regions", []) if r.get("route") == "table_extraction"]
        boxes = [(r.get("reason"), _finite_box(r.get("bbox"), r.get("region_id", "?"))) for r in regions]
        if not boxes:
            out.append(dict(pdf_page=n, sheet=sheet, route="not_routed", reason="no_table_region_in_index", roi=None))
            continue
        ctx = [b for reason, b in boxes if reason == "schedule_context_candidate_unverified"]
        roi = ctx[0] if ctx else [min(b[0] for _, b in boxes), min(b[1] for _, b in boxes),
                                  max(b[2] for _, b in boxes), max(b[3] for _, b in boxes)]
        out.append(dict(pdf_page=n, sheet=sheet, route="table_extraction",
                        reason="index_" + ("schedule_context" if ctx else "table_region_union"), roi=roi))
    return out


def _swatch(page: Any, log: list[Any] | None, word_box: list[float]) -> dict[str, Any] | None:
    """Filled box left of the legend text on its line; colour sampled from a 1-pixel render of its centre."""
    if not log:
        return None
    x0, y0, x1, y1 = word_box
    best = None
    for op, box, *_ in log:
        if op != "fill-path":
            continue
        bx0, by0, bx1, by1 = box
        w, h = bx1 - bx0, by1 - by0
        cy = (by0 + by1) / 2
        if 3 <= w <= 80 and 3 <= h <= 60 and y0 - 4 <= cy <= y1 + 4 and bx1 <= x0 + 1 and bx0 >= x0 - 160:
            gap = x0 - bx1
            if best is None or gap < best[0]:
                best = (gap, [float(v) for v in box])
    if best is None:
        return None
    box = best[1]
    fitz = _fitz()
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    pix = page.get_pixmap(clip=fitz.Rect(cx - 0.5, cy - 0.5, cx + 0.5, cy + 0.5), dpi=72, alpha=False)
    rgb = list(pix.pixel(0, 0))[:3]
    return dict(kind="filled_swatch", bbox=box, rgb=rgb)


def _inside(box: list[float], cell: list[float] | None) -> bool:
    if cell is None:
        return False
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return cell[0] <= cx <= cell[2] and cell[1] <= cy <= cell[3]


def _page_materials(page: Any, number: int, sheet: str | None, tables: list[dict[str, Any]],
                    claimed: set[tuple[str, int, int]]) -> list[dict[str, Any]]:
    out = []
    lines: dict[tuple[int, int], list[Any]] = {}
    for w in page.get_text("words", sort=True):
        lines.setdefault((w[5], w[6]), []).append(w)
    # original label of a legend line = its whole text block (multi-line finish descriptions stay whole)
    blocks: dict[int, list[str]] = {}
    for key in sorted(lines):
        blocks.setdefault(key[0], []).append(" ".join(w[4] for w in lines[key]))
    log = None
    for key in sorted(lines, key=lambda k: (lines[k][0][1], lines[k][0][0], k)):
        words = lines[key]
        text = " ".join(w[4] for w in words)
        codes = material_codes(text)
        if not codes:
            continue
        box = [float(min(w[0] for w in words)), float(min(w[1] for w in words)),
               float(max(w[2] for w in words)), float(max(w[3] for w in words))]
        hit = None
        for t in tables:
            for r, line in enumerate(t["cells"]):
                for c, cell in enumerate(line):
                    if _inside(box, cell["bbox"]):
                        hit = (t, r, c)
        if hit is not None:
            t, r, c = hit
            if (t["table_id"], r + 1, c + 1) in claimed:
                continue
            claimed.add((t["table_id"], r + 1, c + 1))
            cell = t["cells"][r][c]
            binding = dict(kind="schedule_row", table_id=t["table_id"], row=r + 1, col=c + 1)
            for code in material_codes(cell["text"]) or codes:
                out.append(_material("schedule_cell", cell["text"], code, "present", binding, number, sheet,
                                     cell["bbox"]))
            continue
        if log is None:
            log = page.get_bboxlog()
        symbol = _swatch(page, log, box)
        for code in codes:
            out.append(_material("legend_text", "\n".join(blocks[key[0]]), code, "present",
                                 dict(kind="unbound", reason="region_application_requires_review"), number, sheet,
                                 box, legend_symbol=symbol,
                                 symbol_status="found" if symbol else "not_found"))
    return out


def _link_conflicts(materials: list[dict[str, Any]]) -> None:
    labels: dict[str, set[str]] = {}
    for i, m in enumerate(materials):
        m["material_id"] = f"m{i + 1}"
        if m["code"]:
            labels.setdefault(m["code"], set()).add(m["original_label"] or "")
    for m in materials:
        if m["code"] and len(labels[m["code"]]) > 1:
            m["conflicts"] = [o["material_id"] for o in materials
                              if o is not m and o["code"] == m["code"] and o["original_label"] != m["original_label"]]


def _load_index(path: str | Path | None, sha: str) -> dict[str, Any] | None:
    if path is None:
        return None
    index = json.loads(Path(path).read_text("utf-8"))
    if not isinstance(index, dict) or (index.get("source") or {}).get("sha256") != sha:
        raise ValueError(f"album_index_source_mismatch: {path}")
    return index


def export_schedules(pdf: str | Path, output: str | Path, *, album_index: str | Path | None = None,
                     pages: list[int] | None = None, secondary: bool = True) -> dict[str, Any]:
    """Export schedules/legends of one album into a NEW directory; return the ``schedules.json`` manifest."""
    pdf, out = Path(pdf).resolve(), Path(output).resolve()
    inputs = [pdf] + ([Path(album_index).resolve()] if album_index is not None else [])
    if out in inputs or any(out in p.parents for p in inputs):
        raise ValueError(f"output_is_input: {out}")
    if out.exists():
        raise FileExistsError(f"output must be a new directory: {out}")
    if not pdf.is_file():
        raise AlbumReadError("not_found", str(pdf))
    sha = _sha(pdf)
    index = _load_index(album_index, sha)
    fitz = _fitz()
    try:
        plumber = None
        if secondary:
            import pdfplumber as plumber  # type: ignore[no-redef]
    except ImportError:
        plumber = None
    with fitz.open(pdf) as doc:
        if doc.needs_pass:
            raise AlbumReadError("encrypted", str(pdf))
        count = len(doc)
        if pages is not None:
            if (not isinstance(pages, list) or not pages
                    or any(isinstance(p, bool) or not isinstance(p, int) or not 1 <= p <= count for p in pages)
                    or len(set(pages)) != len(pages)):
                raise ValueError(f"pages must be distinct 1..{count}: {pages!r}")
        if index is None and pages is None:
            raise ValueError("pass album_index or explicit pages; table detection is not run on every page")
        routes = _route(index, count, pages)
        engines = dict(primary=f"pymupdf {fitz.VersionBind} find_tables",
                       secondary=None if plumber is None else f"pdfplumber {plumber.__version__} find_tables")
        sec_status = "ok" if plumber is not None else (
            "second_engine_disabled" if not secondary else "second_engine_unavailable")
        tables: list[dict[str, Any]] = []
        materials: list[dict[str, Any]] = []
        pl_doc = plumber.open(str(pdf)) if plumber is not None else None
        try:
            for route in routes:
                n = route["pdf_page"]
                page = doc[n - 1]
                route["tables"] = []
                page_tables: list[dict[str, Any]] = []
                if route["route"] == "table_extraction":
                    # Detect on the routed page and keep every table touching the ROI: an index ROI is a
                    # text envelope and may cut a table; a table outside the ROI is reported, not dropped.
                    roi = route["roi"] or [float(v) for v in page.rect]
                    prim = [_engine_table(t) for t in page.find_tables().tables]
                    sec, status = [], sec_status
                    if pl_doc is not None:
                        pl_page = pl_doc.pages[n - 1]
                        if page.rotation or pl_page.rotation:
                            status = "second_engine_coordinates_differ"
                        else:
                            # PyMuPDF coordinates start at the cropbox corner; pdfplumber's are mediabox-based
                            origin = getattr(pl_page, "cropbox", pl_page.bbox)
                            sec = [_engine_table(t, -float(origin[0]), -float(origin[1]))
                                   for t in pl_page.find_tables()]
                    route["outside_roi"] = [dict(engine=e, bbox=t["bbox"]) for e, ts in (("primary", prim),
                                                                                       ("secondary", sec))
                                            for t in ts if not _overlaps(t["bbox"], roi)]
                    prim = [t for t in prim if _overlaps(t["bbox"], roi)]
                    sec = [t for t in sec if _overlaps(t["bbox"], roi)]
                    used: set[int] = set()
                    pairs = []
                    for t in prim:
                        scores = [(_iou(t["bbox"], s["bbox"]), j) for j, s in enumerate(sec) if j not in used]
                        best = max(scores, default=(0.0, -1))
                        if best[0] >= IOU_PAIR:
                            used.add(best[1])
                            pairs.append((t, sec[best[1]], "ok"))
                        else:
                            pairs.append((t, None, status if status != "ok" else "no_second_engine_table"))
                    pairs += [(None, s, "ok") for j, s in enumerate(sec) if j not in used]
                    for k, (p, s, st) in enumerate(pairs):
                        tid = f"p{n}-t{k + 1}"
                        page_tables.append(build_table(tid, n, route["sheet"], p, s, secondary_status=st,
                                                       engines=dict(engines, found_by=[
                                                           e for e, x in (("primary", p), ("secondary", s)) if x])))
                        route["tables"].append(tid)
                tables += page_tables
                claimed: set[tuple[str, int, int]] = set()
                for t in page_tables:
                    fm = finish_materials(t)
                    claimed |= {(t["table_id"], m["binding"]["row"], m["binding"]["col"]) for m in fm}
                    materials += fm
                materials += _page_materials(page, n, route["sheet"], page_tables, claimed)
        finally:
            if pl_doc is not None:
                pl_doc.close()
    if _sha(pdf) != sha:
        raise AlbumReadError("source_changed", str(pdf))
    _link_conflicts(materials)
    source = dict(sha256=sha, bytes=pdf.stat().st_size, pages=count)
    files: list[tuple[str, bytes]] = []
    summary_tables = []
    for t in tables:
        data = _csv_bytes(t)
        side = {k: v for k, v in t.items() if k != "cells"}
        side.update(schema=SCHEMA, source=source, csv=f"{t['table_id']}.csv",
                    csv_sha256=hashlib.sha256(data).hexdigest(), passed=False, open_gates=OPEN_GATES)
        files += [(f"schedules/{t['table_id']}.csv", data), (f"schedules/{t['table_id']}.json", _json_bytes(side))]
        summary_tables.append(dict(table_id=t["table_id"], page=t["page"], sheet=t["sheet"], n_rows=t["n_rows"],
                                   n_cols=t["n_cols"], suspect_cells=len(t["suspect_cells"]),
                                   found_by=t["engines"].get("found_by", [])))
    mats = dict(schema=MATERIALS_SCHEMA, source=source, passed=False, default_material=None,
                open_gates=OPEN_GATES, materials=materials,
                summary=dict(entries=len(materials), present=sum(m["status"] == "present" for m in materials),
                             missing=sum(m["status"] == "missing" for m in materials),
                             merged_unresolved=sum(m["status"] == "merged_unresolved" for m in materials),
                             unbound=sum(m["binding"]["kind"] == "unbound" for m in materials)))
    manifest = dict(schema=MANIFEST_SCHEMA, source=source, engines=engines, secondary_status=sec_status,
                    pages=routes, tables=summary_tables, passed=False, open_gates=OPEN_GATES,
                    summary=dict(tables=len(tables), cells=sum(t["n_rows"] * t["n_cols"] for t in tables),
                                 suspect_cells=sum(len(t["suspect_cells"]) for t in tables),
                                 materials=len(materials)))
    files += [("materials.json", _json_bytes(mats)), ("schedules.json", _json_bytes(manifest))]
    out.mkdir(parents=True, exist_ok=False)
    (out / "schedules").mkdir()
    for name, data in files:
        with (out / name).open("xb") as fh:
            fh.write(data)
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Album schedules/legends -> typed CSV + materials.json (#1235)")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--album-index", type=Path, default=None)
    ap.add_argument("--pages", type=str, default=None, help="comma list of 1-based pages")
    ap.add_argument("--no-secondary", action="store_true", help="skip pdfplumber (every cell single_engine)")
    args = ap.parse_args(argv)
    try:
        pages = None if args.pages is None else [int(x) for x in args.pages.split(",") if x.strip()]
        manifest = export_schedules(args.pdf, args.output, album_index=args.album_index, pages=pages,
                                    secondary=not args.no_secondary)
    except (ValueError, OSError, AlbumExtraMissing) as exc:
        print(str(exc))
        return 2
    print(json.dumps({"passed": False, **manifest["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
