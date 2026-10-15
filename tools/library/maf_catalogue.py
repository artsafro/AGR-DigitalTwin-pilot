"""Plan and catalogue a MAF library from a Max elements dump (issue #183).

Pure Python: cluster mesh elements into one MAF entry each, match them to an NPM
Blender inventory, and render a markdown catalogue plus a preview contact sheet.
New case: retain preview override provenance, so neutral shape-only rerenders
cannot be mistaken for validation of the source material appearance.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Cyrillic -> ASCII. Soft/hard signs drop out; everything else is a short latin stem.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_LEADING_PREFIX = re.compile(r"^(?:crp_|c_)")
_BLEND_SUFFIX = re.compile(r"\.\d+$")
_COLLAPSE_SEP = re.compile(r"[\s_.]+")
_MULTI_US = re.compile(r"_+")

_SLUG_MAX = 60
_HELPER_TRIS = 12
_HELPER_HEIGHT_M = 0.005
_LABEL_PX = 16
_SPEC_TOL_EPS = 1e-6

# Longer keys first so "Длина" is not read as the short form "Д".
_SPEC_NUM = r"\d(?:[\d \u00a0\u202f]*\d)?(?:[.,]\d+)?"
_SPEC_DIM = re.compile(
    rf"(?iu)\b(?P<key>диаметр|длина|ширина|высота|д|ш|в)\s*:\s*"
    rf"(?P<num>{_SPEC_NUM})"
    rf"\s*(?P<unit>мм|м\b)?"
)
# First "A x B x C" when the named keys above are absent. Separators: Latin x,
# Cyrillic х, ×, *. Unit is optional (мм default).
_SPEC_TRIPLE = re.compile(
    rf"(?iu)(?P<a>{_SPEC_NUM})\s*[xх×*]\s*(?P<b>{_SPEC_NUM})\s*[xх×*]\s*(?P<c>{_SPEC_NUM})"
    rf"\s*(?P<unit>мм|см|м\b)?"
)
# "D 150-230 мм" / "Ø …" / "H …": upper bound. Radius (R) is not an axis.
_SPEC_LETTER_AXIS = re.compile(
    rf"(?iu)(?<!\w)(?P<key>[dhø⌀])(?=\s|\d)\s*"
    rf"(?P<lo>{_SPEC_NUM})(?:\s*[-–—−]\s*(?P<hi>{_SPEC_NUM}))?"
    rf"\s*(?P<unit>мм|см|м\b)?"
)


def _lo_hi(box):
    if hasattr(box, "lo") and hasattr(box, "hi"):
        lo, hi = box.lo, box.hi
    else:
        lo, hi = box[0], box[1]
    return lo, hi


def box_gap(a, b) -> float:
    """Chebyshev separation of two AABB. 0 when they touch or overlap."""
    alo, ahi = _lo_hi(a)
    blo, bhi = _lo_hi(b)
    sep = 0.0
    for i in range(3):
        d = float(alo[i]) - float(bhi[i])
        if d > sep:
            sep = d
        d = float(blo[i]) - float(ahi[i])
        if d > sep:
            sep = d
    return sep


def _as_arrays(boxes):
    n = len(boxes)
    lo = np.empty((n, 3), dtype=np.float64)
    hi = np.empty((n, 3), dtype=np.float64)
    for i, box in enumerate(boxes):
        a, b = _lo_hi(box)
        lo[i, 0], lo[i, 1], lo[i, 2] = float(a[0]), float(a[1]), float(a[2])
        hi[i, 0], hi[i, 1], hi[i, 2] = float(b[0]), float(b[1]), float(b[2])
    return lo, hi


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        parent = self.parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        rank = self.rank
        if rank[ra] < rank[rb]:
            self.parent[ra] = rb
        elif rank[ra] > rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            rank[ra] += 1


def _groups_from(uf: _UnionFind, n: int) -> list[list[int]]:
    buckets: dict[int, list[int]] = {}
    for i in range(n):
        buckets.setdefault(uf.find(i), []).append(i)
    groups = [sorted(members) for members in buckets.values()]
    groups.sort(key=lambda group: group[0])
    return groups


def cluster_boxes(boxes, gap_m) -> list[list[int]]:
    """Transitive clusters of boxes whose Chebyshev gap is <= gap_m.

    Sweep on lo.x: a later box is compared only while its lo.x is within
    hi.x + gap of an earlier box still in the window. Empty input returns [].
    """
    n = len(boxes)
    if n == 0:
        return []
    lo, hi = _as_arrays(boxes)
    gap = float(gap_m)
    order = np.argsort(lo[:, 0], kind="mergesort")
    hi_x = hi[:, 0]
    uf = _UnionFind(n)
    # Left edge of the x-window. It only moves forward, so a long box can keep
    # a few already-expired boxes in the slice; the gap test rejects them.
    left = 0
    for right in range(n):
        idx = int(order[right])
        limit = float(lo[idx, 0]) - gap - 1e-9
        while left < right and float(hi_x[int(order[left])]) < limit:
            left += 1
        if left == right:
            continue
        window = order[left:right]
        sep = np.maximum(lo[idx] - hi[window], lo[window] - hi[idx]).max(axis=1)
        linked = window[sep <= gap]
        if linked.size == 0:
            continue
        root = uf.find(idx)
        for other in linked.tolist():
            other = int(other)
            if uf.find(other) != root:
                uf.union(idx, other)
                root = uf.find(idx)
    return _groups_from(uf, n)


def _z_extent(obj) -> float | None:
    bbox = obj.get("bbox")
    if not bbox or len(bbox) < 2:
        return None
    return float(bbox[1][2]) - float(bbox[0][2])


def classify(obj) -> str:
    """maf_candidate, helper_plane, or non_geometry.

    A flat plate (tris <= 12 and z extent < 5 mm) is a helper even when the
    elements dump attached a face group to it. Those plates are background, not MAF.
    """
    tris = obj.get("tris")
    if tris is not None:
        height = _z_extent(obj)
        if tris <= _HELPER_TRIS and height is not None and height < _HELPER_HEIGHT_M:
            return "helper_plane"
        elements = obj.get("elements")
        if tris > 0 and elements:
            return "maf_candidate"
    return "non_geometry"


def _round(value, places: int) -> float:
    rounded = round(float(value), places)
    if rounded == 0:
        return 0.0
    return rounded


def _union_bbox(boxes) -> list[list[float]]:
    lo = [min(float(b[0][i]) for b in boxes) for i in range(3)]
    hi = [max(float(b[1][i]) for b in boxes) for i in range(3)]
    return [[_round(v, 4) for v in lo], [_round(v, 4) for v in hi]]


def _slug(maf_id: str, name: str) -> str:
    parts: list[str] = []
    for ch in name:
        mapped = _CYR.get(ch.casefold())
        if mapped is not None:
            if mapped and ch.isupper():
                mapped = mapped[0].upper() + mapped[1:]
            parts.append(mapped)
        elif ch.isascii() and ch.isalnum():
            parts.append(ch)
        else:
            parts.append("_")
    body = _MULTI_US.sub("_", "".join(parts)).strip("_")
    slug = f"{maf_id}_{body}" if body else maf_id
    if len(slug) > _SLUG_MAX:
        slug = slug[:_SLUG_MAX].rstrip("_")
    return slug


def plan_library(elements_doc, gap_m=0.5) -> dict:
    """One MAF entry per element cluster of each maf_candidate, in scene order."""
    gap = float(gap_m)
    objects = elements_doc.get("objects") or []
    counts = {
        "objects": len(objects),
        "maf_candidate": 0,
        "helper_plane": 0,
        "non_geometry": 0,
        "split_objects": 0,
        "maf_entries": 0,
        "tris_total": 0,
    }
    excluded = []
    entries = []
    serial = 0
    for obj in objects:
        kind = classify(obj)
        counts[kind] += 1
        if kind != "maf_candidate":
            excluded.append({
                "name": obj.get("name"),
                "handle": obj.get("handle"),
                "class": obj.get("class"),
                "reason": kind,
            })
            continue
        elements = obj["elements"]
        groups = cluster_boxes([el["bbox"] for el in elements], gap)
        cluster_count = len(groups)
        if cluster_count > 1:
            counts["split_objects"] += 1
        for cluster_index, group in enumerate(groups):
            serial += 1
            chosen = [elements[i] for i in group]
            bbox = _union_bbox([el["bbox"] for el in chosen])
            tris = sum(int(el["tris"]) for el in chosen)
            maf_id = f"MAF_{serial:04d}"
            counts["tris_total"] += tris
            entries.append({
                "id": maf_id,
                "source_object": obj.get("name"),
                "source_handle": obj.get("handle"),
                "source_class": obj.get("class"),
                "layer": obj.get("layer"),
                "material": obj.get("material"),
                "cluster_index": cluster_index,
                "cluster_count": cluster_count,
                "split": cluster_count > 1,
                "element_first_faces": sorted(int(el["first_face"]) for el in chosen),
                "element_count": len(chosen),
                "tris": tris,
                "bbox": bbox,
                "dims_m": [_round(bbox[1][i] - bbox[0][i], 3) for i in range(3)],
                "mat_ids_object": list(obj.get("mat_ids") or []),
                "slug": _slug(maf_id, str(obj.get("name") or "")),
            })
    counts["maf_entries"] = len(entries)
    return {
        "gap_m": gap,
        "scene": elements_doc.get("scene"),
        "unit_to_m": elements_doc.get("unit_to_m"),
        "counts": counts,
        "excluded": excluded,
        "entries": entries,
    }


def _dim_score(a, b) -> float:
    """Max abs delta after sorting the two horizontal sizes. Z is compared directly."""
    ah = sorted((float(a[0]), float(a[1])))
    bh = sorted((float(b[0]), float(b[1])))
    return max(abs(ah[0] - bh[0]), abs(ah[1] - bh[1]), abs(float(a[2]) - float(b[2])))


def find_duplicates(entries, tol_m=0.01) -> list[list[str]]:
    """Groups of entry ids with equal tris and dims equal within tol, Z-rotation ignored."""
    by_tris: dict[int, list] = {}
    for entry in entries:
        by_tris.setdefault(int(entry["tris"]), []).append(entry)
    groups: list[list[str]] = []
    tol = float(tol_m)
    for tris in sorted(by_tris):
        items = by_tris[tris]
        m = len(items)
        if m < 2:
            continue
        uf = _UnionFind(m)
        for i in range(m):
            for j in range(i + 1, m):
                if _dim_score(items[i]["dims_m"], items[j]["dims_m"]) <= tol:
                    uf.union(i, j)
        for members in _groups_from(uf, m):
            if len(members) < 2:
                continue
            groups.append(sorted(items[i]["id"] for i in members))
    groups.sort(key=lambda group: group[0])
    return groups


def _positive_volume(a_lo, a_hi, b_lo, b_hi) -> bool:
    for i in range(3):
        lo = a_lo[i] if a_lo[i] > b_lo[i] else b_lo[i]
        hi = a_hi[i] if a_hi[i] < b_hi[i] else b_hi[i]
        if not (lo < hi):
            return False
    return True


def _same_source(a, b) -> bool:
    ha, hb = a.get("source_handle"), b.get("source_handle")
    if ha is not None and hb is not None:
        return ha == hb
    return a.get("source_object") == b.get("source_object")


def find_overlaps(entries) -> list[list[str]]:
    """Pairs from different source objects whose bboxes overlap with positive volume.

    Touching faces (zero volume) are not pairs. Sweep on lo.x.
    """
    n = len(entries)
    if n < 2:
        return []
    lo, hi = _as_arrays([entry["bbox"] for entry in entries])
    order = np.argsort(lo[:, 0], kind="mergesort")
    active: list[int] = []
    pairs: set[tuple[str, str]] = set()
    for idx in order.tolist():
        x0 = float(lo[idx, 0])
        if active:
            active = [a for a in active if float(hi[a, 0]) > x0]
        for other in active:
            if _same_source(entries[idx], entries[other]):
                continue
            if _positive_volume(lo[idx], hi[idx], lo[other], hi[other]):
                id_a = entries[idx]["id"]
                id_b = entries[other]["id"]
                pairs.add((id_a, id_b) if id_a < id_b else (id_b, id_a))
        active.append(idx)
    return [list(pair) for pair in sorted(pairs)]


def normalize_name(s: str) -> str:
    """Casefold, drop a leading C_/crp_ and a trailing Blender .NNN, collapse separators."""
    text = str(s).casefold().strip()
    text = _LEADING_PREFIX.sub("", text, count=1)
    text = _BLEND_SUFFIX.sub("", text)
    text = _COLLAPSE_SEP.sub(" ", text)
    return text.strip()


def _names_related(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return a == b or a in b or b in a


def match_npm(entries, blend_doc, tol_m=0.10) -> list[dict]:
    """Match every Blender MESH to a MAF entry by dims, preferring a related name."""
    tol = float(tol_m)
    rows = []
    meshes = [obj for obj in (blend_doc.get("objects") or []) if obj.get("type") == "MESH"]
    prepared = [(entry, entry["dims_m"]) for entry in entries]
    for obj in meshes:
        blend_dims = obj.get("dims") or [0, 0, 0]
        blend_name = obj.get("name") or ""
        norm_blend = normalize_name(blend_name)
        scored = []
        for entry, dims in prepared:
            score = _dim_score(blend_dims, dims)
            if score <= tol:
                scored.append((score, entry))
        row = {
            "blend_name": blend_name,
            "collections": list(obj.get("collections") or []),
            "blend_tris": obj.get("tris"),
            "blend_dims": list(blend_dims),
            "maf_id": None,
            "source_object": None,
            "maf_tris": None,
            "score_m": None,
            "method": "none",
            "n_candidates": len(scored),
            "light_pair": False,
        }
        if scored:
            named = [
                (score, entry) for score, entry in scored
                if _names_related(norm_blend, normalize_name(entry.get("source_object") or ""))
            ]
            pool = named or scored
            score, entry = min(pool, key=lambda item: (item[0], item[1]["id"]))
            maf_tris = entry.get("tris")
            blend_tris = obj.get("tris")
            row.update({
                "maf_id": entry["id"],
                "source_object": entry.get("source_object"),
                "maf_tris": maf_tris,
                "score_m": score,
                "method": "name+dims" if named else "dims",
                "light_pair": blend_tris is not None and maf_tris is not None and blend_tris < maf_tris,
            })
        rows.append(row)
    return rows


def _number_to_m(num: str, unit: str | None) -> float:
    text = re.sub(r"\s", "", num).replace(",", ".")
    value = float(text)
    if unit is not None:
        folded = unit.casefold()
        if folded == "м":
            return value
        if folded == "см":
            return value / 100.0
    return value / 1000.0


def _fill_spec_found(found, key: str, value: float) -> None:
    if key == "диаметр":
        found["d"] = value
    elif key in ("длина", "д"):
        found["l"] = value
    elif key in ("ширина", "ш"):
        found["w"] = value
    elif key in ("высота", "в"):
        found["h"] = value


def parse_spec_dims(text) -> dict | None:
    """Overall size in metres from a specification name cell, or None.

    Keys: Длина, Ширина, Высота, Диаметр, and the short forms Д/Ш/В.
    When those keys are absent, the first "A x B x C" triple is length, width
    and height. Otherwise a D/Ø range is the diameter and an H range is the
    height; a range uses its upper bound. Radius alone is ignored.
    Millimetres are the default unit; "см" is centimetres; a trailing "м"
    keeps the value in metres.
    Diameter fills both horizontal sizes. Missing axes stay None.
    """
    if text is None:
        return None
    raw = str(text)
    found = {"l": None, "w": None, "h": None, "d": None}
    keyed = list(_SPEC_DIM.finditer(raw))
    if keyed:
        for match in keyed:
            _fill_spec_found(
                found,
                match.group("key").casefold(),
                _number_to_m(match.group("num"), match.group("unit")),
            )
    else:
        triple = _SPEC_TRIPLE.search(raw)
        if triple is not None:
            unit = triple.group("unit")
            found["l"] = _number_to_m(triple.group("a"), unit)
            found["w"] = _number_to_m(triple.group("b"), unit)
            found["h"] = _number_to_m(triple.group("c"), unit)
        else:
            for match in _SPEC_LETTER_AXIS.finditer(raw):
                key = match.group("key").casefold()
                value = _number_to_m(match.group("hi") or match.group("lo"), match.group("unit"))
                if key in ("d", "ø", "⌀"):
                    found["d"] = value
                elif key == "h":
                    found["h"] = value
    length = found["l"] if found["l"] is not None else found["d"]
    width = found["w"] if found["w"] is not None else found["d"]
    height = found["h"]
    if height is None and length is None and width is None:
        return None
    return {"l_m": length, "w_m": width, "h_m": height}


def _spec_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _spec_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:
            return None
        return int(round(value))
    text = _spec_text(value)
    if text is None:
        return None
    text = re.sub(r"\s", "", text).replace(",", ".")
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def _spec_name(text: str) -> str:
    for line in str(text).splitlines():
        line = line.strip()
        if line:
            return line
    return str(text).strip()


def _spec_max_names(value) -> list[str]:
    text = _spec_text(value)
    if text is None:
        return []
    return [part.strip() for part in re.split(r"\r\n|\n|\r", text) if part.strip()]


def read_spec_xlsx(path) -> list[dict]:
    """One dict per data row of sheet 'Ведомость' whose name cell is non-empty.

    Header is row 1. Columns, 0-based: 1 type, 2 availability, 3 name and
    dimensions, 4 URL, 6 .max object names, 8 tris VPM, 9 tris NPM.
    """
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb["Ведомость"]
        rows = []
        for index, raw in enumerate(ws.iter_rows(values_only=True), start=1):
            if index == 1:
                continue
            cells = tuple(raw)
            label = cells[3] if len(cells) > 3 else None
            if _spec_text(label) is None:
                continue
            body = str(label)

            def cell(col):
                return cells[col] if len(cells) > col else None

            rows.append({
                "row": index,
                "type": _spec_text(cell(1)),
                "availability": _spec_text(cell(2)),
                "name": _spec_name(body),
                "dims": parse_spec_dims(body),
                "url": _spec_text(cell(4)),
                "max_names": _spec_max_names(cell(6)),
                "tris_vpm": _spec_int(cell(8)),
                "tris_npm": _spec_int(cell(9)),
            })
        return rows
    finally:
        wb.close()


def _usable_spec_dims(dims) -> bool:
    if not isinstance(dims, dict):
        return False
    return any(dims.get(key) is not None for key in ("l_m", "w_m", "h_m"))


def _spec_dim_score(entry_dims, spec_dims) -> float | None:
    """Max abs delta of the axes the specification actually states.

    Horizontal sizes are sorted, so a Z rotation still matches. Height is Z.
    A diameter-only or height-only row compares just those axes.
    """
    horiz = [float(spec_dims[key]) for key in ("l_m", "w_m") if spec_dims.get(key) is not None]
    diffs = []
    if len(horiz) >= 2:
        eh = sorted((float(entry_dims[0]), float(entry_dims[1])))
        sh = sorted(horiz[:2])
        diffs.append(abs(eh[0] - sh[0]))
        diffs.append(abs(eh[1] - sh[1]))
    elif len(horiz) == 1:
        side = horiz[0]
        diffs.append(min(abs(float(entry_dims[0]) - side), abs(float(entry_dims[1]) - side)))
    height = spec_dims.get("h_m")
    if height is not None:
        diffs.append(abs(float(entry_dims[2]) - float(height)))
    if not diffs:
        return None
    return max(diffs)


def _spec_name_hit(entries, max_names) -> bool:
    wanted = {name for name in max_names if name}
    if not wanted:
        return False
    for entry in entries:
        if entry.get("source_object") in wanted or entry.get("slug") in wanted:
            return True
    return False


def match_spec(entries, spec_rows, tol_m=0.10) -> list[dict]:
    """Candidate entries for each specification row. Pure; no identification."""
    tol = float(tol_m)
    indexed = [
        entry for entry in entries
        if entry.get("dims_m") and len(entry["dims_m"]) >= 3 and entry.get("id")
    ]
    out = []
    for spec in spec_rows:
        max_names = list(spec.get("max_names") or [])
        dims = spec.get("dims")
        usable = _usable_spec_dims(dims)
        row = {
            "spec_row": spec.get("row"),
            "spec_name": spec.get("name"),
            "type": spec.get("type"),
            "availability": spec.get("availability"),
            "spec_dims": dims if usable else None,
            "max_names": max_names,
            "name_hit": _spec_name_hit(entries, max_names),
        }
        if not usable:
            row["n_candidates"] = 0
            row["best"] = []
            row["reason"] = "no dims"
            out.append(row)
            continue
        scored = []
        for entry in indexed:
            score = _spec_dim_score(entry["dims_m"], dims)
            if score is not None and score <= tol + _SPEC_TOL_EPS:
                scored.append({"id": entry["id"], "score_m": score})
        scored.sort(key=lambda item: (item["score_m"], item["id"]))
        row["n_candidates"] = len(scored)
        row["best"] = scored[:5]
        out.append(row)
    return out


def build_catalogue(plan, built_rows, matches, duplicates, overlaps, spec_matches=None) -> dict:
    """Merge pass-B rows, NPM matches, duplicate groups and overlaps into the plan."""
    built: dict = {}
    for row in built_rows or []:
        if row.get("id"):
            built[row["id"]] = row
    dup_index = {}
    for index, group in enumerate(duplicates or []):
        for eid in group:
            dup_index[eid] = index
    overlap_map: dict[str, list[str]] = {}
    for pair in overlaps or []:
        if len(pair) != 2:
            continue
        a, b = pair
        overlap_map.setdefault(a, []).append(b)
        overlap_map.setdefault(b, []).append(a)
    npm_map: dict[str, list[str]] = {}
    for match in matches or []:
        maf_id = match.get("maf_id")
        if maf_id:
            npm_map.setdefault(maf_id, []).append(match["blend_name"])
    spec_rows = list(spec_matches or [])
    spec_by_id: dict[str, list] = {}
    for spec_row in spec_rows:
        seen = set()
        for item in spec_row.get("best") or []:
            eid = item.get("id") if isinstance(item, dict) else item
            if not eid or eid in seen:
                continue
            seen.add(eid)
            spec_by_id.setdefault(eid, []).append(spec_row.get("spec_row"))

    entries = []
    built_ok = 0
    built_failed = 0
    for src in plan.get("entries") or []:
        entry = dict(src)
        row = built.get(entry["id"])
        if row is None:
            entry.update({
                "max_path": None,
                "fbx_path": None,
                "preview_path": None,
                "mat_ids": None,
                "tris_built": None,
                "ok": False,
                "error": "not built",
            })
        else:
            entry.update({
                "max_path": row.get("max_path"),
                "fbx_path": row.get("fbx_path"),
                "preview_path": row.get("preview_path"),
                "preview_style": row.get("preview_style", "source-material"),
                "preview_original_path": row.get("preview_original_path"),
                "mat_ids": row.get("mat_ids"),
                "tris_built": row.get("tris_built"),
                "ok": bool(row.get("ok")),
                "error": row.get("error"),
            })
        if entry["ok"]:
            built_ok += 1
        else:
            built_failed += 1
        entry["npm_matches"] = list(npm_map.get(entry["id"], []))
        entry["dup_group"] = dup_index.get(entry["id"])
        entry["overlaps_with"] = sorted(set(overlap_map.get(entry["id"], [])))
        entry["spec_candidates"] = list(spec_by_id.get(entry["id"], []))
        entries.append(entry)

    counts = dict(plan.get("counts") or {})
    counts.update({
        "built_ok": built_ok,
        "built_failed": built_failed,
        "duplicates_groups": len(duplicates or []),
        "duplicate_entries": sum(len(group) for group in (duplicates or [])),
        "npm_rows": len(matches or []),
        "npm_matched_name": sum(1 for m in (matches or []) if m.get("method") == "name+dims"),
        "npm_matched_dims": sum(1 for m in (matches or []) if m.get("method") == "dims"),
        "npm_unmatched": sum(1 for m in (matches or []) if m.get("method") == "none"),
        "spec_rows": len(spec_rows),
        "spec_with_dims": sum(1 for row in spec_rows if row.get("spec_dims")),
        "spec_rows_with_candidates": sum(1 for row in spec_rows if row.get("n_candidates")),
        "spec_name_hits": sum(1 for row in spec_rows if row.get("name_hit")),
    })
    return {
        "gap_m": plan.get("gap_m"),
        "scene": plan.get("scene"),
        "unit_to_m": plan.get("unit_to_m"),
        "counts": counts,
        "excluded": list(plan.get("excluded") or []),
        "entries": entries,
        "duplicates": list(duplicates or []),
        "overlaps": [list(pair) for pair in (overlaps or [])],
        "spec_matches": spec_rows,
    }


def _md_cell(value) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def render_markdown(catalogue, limit=None) -> str:
    """Header of counts plus one table row per entry. Preview cells are paths."""
    counts = catalogue.get("counts") or {}
    lines = ["# MAF catalogue", ""]
    for key in (
        "objects", "maf_candidate", "helper_plane", "non_geometry", "split_objects",
        "maf_entries", "tris_total", "built_ok", "built_failed", "duplicates_groups",
        "duplicate_entries", "npm_rows", "npm_matched_name", "npm_matched_dims",
        "npm_unmatched", "spec_rows", "spec_with_dims", "spec_rows_with_candidates",
        "spec_name_hits",
    ):
        if key in counts:
            lines.append(f"- {key}: {counts[key]}")
    lines.append("")
    lines.append("| id | source object | split | dims m | tris | mat IDs | dup | NPM match | preview |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    entries = catalogue.get("entries") or []
    if limit is not None:
        entries = entries[:limit]
    for entry in entries:
        dims = entry.get("dims_m") or []
        dim_txt = " ".join(f"{float(v):.3f}" for v in dims)
        mats = entry.get("mat_ids")
        if mats is None:
            mats = entry.get("mat_ids_object") or []
        dup = entry.get("dup_group")
        npm = ", ".join(entry.get("npm_matches") or [])
        preview = entry.get("preview_path") or ""
        cells = [
            entry["id"],
            _md_cell(entry.get("source_object") or ""),
            "yes" if entry.get("split") else "no",
            dim_txt,
            str(entry.get("tris", "")),
            ",".join(str(m) for m in mats),
            "" if dup is None else str(dup),
            _md_cell(npm),
            _md_cell(preview),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    spec_lines = []
    for spec_row in catalogue.get("spec_matches") or []:
        if not spec_row.get("n_candidates"):
            continue
        dims = spec_row.get("spec_dims") or {}
        dim_txt = " ".join(
            "-" if dims.get(key) is None else f"{float(dims[key]):.3f}"
            for key in ("l_m", "w_m", "h_m")
        )
        best_ids = ", ".join(
            item["id"] if isinstance(item, dict) else str(item)
            for item in (spec_row.get("best") or [])
        )
        spec_lines.append(" | ".join((
            str(spec_row.get("spec_row")),
            _md_cell(spec_row.get("spec_name") or ""),
            dim_txt,
            best_ids,
        )))
    if spec_lines:
        lines.append("## Specification candidates (dimension-only, not identification)")
        lines.append("")
        for line in spec_lines:
            lines.append(f"- {line}")
        lines.append("")
    return "\n".join(lines)


def contact_sheet(entries, out_png, thumb=160, cols=16) -> int:
    """Write a grid of preview PNGs with the entry id under each thumb.

    Missing files are skipped. Returns how many thumbs were drawn; writes nothing
    and returns 0 when none can be drawn.
    """
    usable = []
    for entry in entries or []:
        path = entry.get("preview_path")
        if path and Path(path).is_file():
            usable.append(entry)
    if not usable:
        return 0
    columns = max(1, min(int(cols), len(usable)))
    rows = (len(usable) + columns - 1) // columns
    thumb = int(thumb)
    cell_h = thumb + _LABEL_PX
    sheet = Image.new("RGB", (columns * thumb, rows * cell_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, entry in enumerate(usable):
        col = index % columns
        row = index // columns
        x = col * thumb
        y = row * cell_h
        with Image.open(entry["preview_path"]) as src:
            image = src.convert("RGB").resize((thumb, thumb), Image.Resampling.LANCZOS)
        sheet.paste(image, (x, y))
        draw.text((x + 2, y + thumb), str(entry.get("id") or ""), fill=(0, 0, 0), font=font)
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return len(usable)


def _write_json(path, payload) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    dest.write_text(text, encoding="utf-8")


def _read_jsonl(path) -> list[dict]:
    src = Path(path)
    if not src.is_file():
        return []
    rows = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _cmd_plan(args) -> dict:
    doc = json.loads(Path(args.elements).read_text(encoding="utf-8"))
    plan = plan_library(doc, gap_m=args.gap)
    _write_json(args.out, plan)
    return plan


def _cmd_catalogue(args) -> dict:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    blend = json.loads(Path(args.blend).read_text(encoding="utf-8"))
    duplicates = find_duplicates(plan.get("entries") or [])
    overlaps = find_overlaps(plan.get("entries") or [])
    entries = plan.get("entries") or []
    matches = match_npm(entries, blend)
    spec_matches = None
    if args.spec:
        spec_matches = match_spec(entries, read_spec_xlsx(args.spec))
        if args.spec_json:
            _write_json(args.spec_json, spec_matches)
    catalogue = build_catalogue(
        plan, _read_jsonl(args.built), matches, duplicates, overlaps, spec_matches,
    )
    _write_json(args.out_json, catalogue)
    md_path = Path(args.out_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(catalogue), encoding="utf-8")
    if args.contact_sheet:
        contact_sheet(catalogue["entries"], args.contact_sheet)
    return catalogue


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maf_catalogue", description="MAF library plan and catalogue")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="cluster an elements file into MAF entries")
    plan.add_argument("--elements", required=True, help="elements JSON from the Max dump")
    plan.add_argument("--out", required=True, help="plan JSON path")
    plan.add_argument("--gap", type=float, default=0.5, help="cluster gap in metres")

    catalogue = sub.add_parser("catalogue", help="merge plan, built rows and NPM matches")
    catalogue.add_argument("--plan", required=True, help="plan JSON")
    catalogue.add_argument("--built", required=True, help="pass-B JSONL; missing file means no rows")
    catalogue.add_argument("--blend", required=True, help="Blender inventory JSON")
    catalogue.add_argument("--out-json", required=True, help="catalogue JSON path")
    catalogue.add_argument("--out-md", required=True, help="catalogue markdown path")
    catalogue.add_argument("--contact-sheet", default=None, help="optional preview grid PNG")
    catalogue.add_argument("--spec", default=None, help="optional specification xlsx, sheet Ведомость")
    catalogue.add_argument("--spec-json", default=None, help="optional JSON dump of specification matches")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "plan":
        result = _cmd_plan(args)
    else:
        result = _cmd_catalogue(args)
    print(json.dumps(result["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
