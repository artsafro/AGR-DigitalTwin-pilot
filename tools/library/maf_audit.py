"""Pattern: verify actual artifacts, not exporter return codes | new-case: reproducible MAF catalogue finalisation and audit (#227)

Versioned preview manifests merge by id. The base manifest defines the entry
set and order. Override manifests apply in the order given; each override row
updates the matching base row field by field (later manifest wins). An override
id absent from the base is an error: an override never creates an entry.

Independent FBX readback and the blank-preview report are consumed as given.
Missing QA is recorded as "not measured". preview_blank is never false unless
that entry id is in a preview-check report. When source integrity is not measured
(no --hash-before manifest supplied), source_hashes is recorded as
{"status": "not measured"} rather than an empty list (which is reserved for an
explicitly empty measured manifest); source preservation is never inferred when
not measured.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

_CATALOGUE_SPEC = importlib.util.spec_from_file_location(
    "maf_catalogue", Path(__file__).parent / "maf_catalogue.py"
)
_catalogue = importlib.util.module_from_spec(_CATALOGUE_SPEC)
_CATALOGUE_SPEC.loader.exec_module(_catalogue)
match_npm = _catalogue.match_npm

_SCOPE = "internal library audit, not NPM/VPM delivery or user acceptance"
_READBACK_TAIL = (
    "preview_blank",
    "fbx_readback_tris",
    "fbx_readback_dims_m",
    "fbx_readback_triangle_delta",
    "fbx_readback_loose_vertices",
    "fbx_readback_status",
)
_DROP_ENTRY_KEYS = set(_READBACK_TAIL) | {"fbx_readback_error", "element_first_faces"}
_LIST_KEYS = ("entries", "excluded", "spec_matches")
_DIM_TOLERANCE_M = 0.005


def _sha256_file(path) -> str:
    with open(path, "rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _write_text(path, text: str) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _require_writable(path, overwrite: bool) -> None:
    if path is None:
        return
    if Path(path).exists() and not overwrite:
        raise SystemExit(f"refusing to overwrite existing output: {path}")


def _entry_id(row, label: str) -> str:
    eid = row.get("id") if isinstance(row, dict) else None
    if not isinstance(eid, str) or not eid:
        raise ValueError(f"{label} missing non-empty string id")
    return eid


def read_jsonl_unique(path) -> list[dict]:
    """JSONL rows with a unique non-empty string id. Blank lines are skipped."""
    file_path = Path(path)
    rows = []
    seen = set()
    for line in file_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        eid = _entry_id(row, f"JSONL row in {file_path}")
        if eid in seen:
            raise ValueError(f"duplicate id {eid!r} in {file_path}")
        seen.add(eid)
        rows.append(row)
    return rows


def merge_manifests(base_rows, overrides: list[tuple[str, list[dict]]]) -> tuple[list[dict], dict]:
    """Merge override manifests onto the base entry set.

    Rows are keyed by id. The base defines which ids exist and their order.
    Each override list is applied in order; a row replaces fields with
    ``{**base_row, **override_row}``, so a later manifest wins. An override id
    that is not in the base raises ValueError.
    """
    by_id: dict[str, dict] = {}
    order: list[str] = []
    for row in base_rows:
        eid = _entry_id(row, "base manifest row")
        if eid in by_id:
            raise ValueError(f"duplicate id {eid!r} in base manifest")
        by_id[eid] = dict(row)
        order.append(eid)

    provenance_overrides = []
    for name, rows in overrides:
        manifest = name if isinstance(name, str) else Path(name).as_posix()
        ids: list[str] = []
        fields: set[str] = set()
        seen: set[str] = set()
        for row in rows:
            eid = _entry_id(row, f"override row in {manifest}")
            if eid in seen:
                raise ValueError(f"duplicate id {eid!r} in {manifest}")
            seen.add(eid)
            if eid not in by_id:
                raise ValueError(f"override id {eid!r} absent from base manifest {manifest}")
            by_id[eid] = {**by_id[eid], **row}
            ids.append(eid)
            fields.update(row.keys())
        provenance_overrides.append({
            "manifest": manifest,
            "ids": sorted(ids),
            "fields": sorted(fields),
        })
    merged = [by_id[eid] for eid in order]
    return merged, {"base_rows": len(base_rows), "overrides": provenance_overrides}


def index_readback(readback_doc) -> dict[str, dict]:
    """Index a Blender FBX readback document by file name (not directory)."""
    if not isinstance(readback_doc, dict) or not isinstance(readback_doc.get("files"), list):
        raise ValueError("readback document must be an object with a files list")
    indexed: dict[str, dict] = {}
    for row in readback_doc["files"]:
        fbx = row.get("fbx") if isinstance(row, dict) else None
        if not isinstance(fbx, str) or not fbx:
            raise ValueError("readback file row missing fbx path")
        name = Path(fbx).name
        if name in indexed:
            raise ValueError(f"duplicate readback file name {name!r}")
        indexed[name] = row
    return indexed


def _blank_flag(entry_id, preview_report):
    if preview_report is None:
        return None
    blank = set(preview_report.get("blank") or [])
    checked = set(preview_report.get("checked") or [])
    if entry_id in blank:
        return True
    if entry_id in checked:
        return False
    return None


def finalize_catalogue(catalogue, readback_doc=None, preview_check=None, contact_sheet=None, provenance=None) -> dict:
    """Attach readback and preview-blank fields. Does not mutate ``catalogue``.

    Without a readback document every entry is "not measured". Without a
    preview-check report every ``preview_blank`` is null, never false.
    """
    if not isinstance(catalogue, dict) or not isinstance(catalogue.get("entries"), list):
        raise ValueError("catalogue must be an object with an entries list")
    out = copy.deepcopy(catalogue)
    indexed = index_readback(readback_doc) if readback_doc is not None else {}
    seen = set()
    entries = []
    for entry in out["entries"]:
        eid = _entry_id(entry, "catalogue entry")
        if eid in seen:
            raise ValueError(f"duplicate catalogue entry id {eid!r}")
        seen.add(eid)
        rebuilt = {key: value for key, value in entry.items() if key not in _DROP_ENTRY_KEYS}
        fbx_path = entry.get("fbx_path")
        name = Path(fbx_path).name if isinstance(fbx_path, str) and fbx_path else None
        row = indexed.get(name) if name else None
        error_text = None
        if row is None:
            status = "not measured"
            tris = dims = delta = loose = None
        elif row.get("error"):
            status = "error"
            tris = dims = delta = loose = None
            error_text = row["error"]
        else:
            reason = _readback_invalid_reason(row)
            if reason is not None:
                status = "invalid"
                tris = dims = delta = loose = None
                error_text = reason
            else:
                if _triangle_count(entry.get("tris")) is None:
                    raise ValueError(f"catalogue entry {eid!r} tris is not a non-negative integer")
                status = "measured"
                tris = row["tris"]
                dims = list(row["referenced_vertices"]["dims_m"])
                delta = row["tris"] - entry["tris"]
                loose = sum(obj["loose_vertices"] for obj in row["objects"])
        rebuilt["preview_blank"] = _blank_flag(eid, preview_check)
        rebuilt["fbx_readback_tris"] = tris
        rebuilt["fbx_readback_dims_m"] = dims
        rebuilt["fbx_readback_triangle_delta"] = delta
        rebuilt["fbx_readback_loose_vertices"] = loose
        rebuilt["fbx_readback_status"] = status
        if status in {"error", "invalid"}:
            rebuilt["fbx_readback_error"] = error_text
        entries.append(rebuilt)

    any_checked = any(entry["preview_blank"] is not None for entry in entries)
    counts = dict(out.get("counts") or {})
    counts["preview_blank"] = (
        sum(entry["preview_blank"] is True for entry in entries) if any_checked else None
    )
    counts["preview_not_checked"] = sum(entry["preview_blank"] is None for entry in entries)
    counts["preview_neutral_override"] = sum(
        entry.get("preview_style") == "neutral-shape-only" for entry in entries
    )
    counts["fbx_readback_measured"] = sum(entry["fbx_readback_status"] == "measured" for entry in entries)
    counts["fbx_readback_not_measured"] = sum(
        entry["fbx_readback_status"] == "not measured" for entry in entries
    )
    counts["fbx_readback_errors"] = sum(entry["fbx_readback_status"] == "error" for entry in entries)
    counts["fbx_readback_invalid"] = sum(entry["fbx_readback_status"] == "invalid" for entry in entries)
    out["entries"] = entries
    out["counts"] = counts
    out.pop("contact_sheet", None)
    out.pop("provenance", None)
    out["contact_sheet"] = contact_sheet
    out["provenance"] = provenance
    return out


def file_provenance(role, path) -> dict:
    file_path = Path(path)
    return {
        "role": role,
        "path": file_path.as_posix(),
        "sha256": _sha256_file(file_path),
        "bytes": file_path.stat().st_size,
    }


def dump_catalogue_json(catalogue) -> str:
    """One top-level key per line; entries, excluded and spec_matches one item per line."""
    lines = ["{"]
    for key, value in catalogue.items():
        rendered_key = json.dumps(key, ensure_ascii=False)
        if key in _LIST_KEYS:
            lines.append(" %s: [" % rendered_key)
            lines.append(",\n".join("  " + json.dumps(item, ensure_ascii=False) for item in value))
            lines.append(" ],")
        else:
            lines.append(" %s: %s," % (rendered_key, json.dumps(value, ensure_ascii=False)))
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_contact_sheet_html(entries, title="MAF library audit") -> str:
    """Local preview grid. Counts in the heading and the neutral sentence come from ``entries``."""
    items = []
    shown = 0
    neutral = 0
    for entry in entries:
        if entry.get("preview_style") == "neutral-shape-only":
            neutral += 1
        preview = entry.get("preview_path")
        if not preview:
            continue
        shown += 1
        uri = html.escape(Path(preview).as_uri(), quote=True)
        eid = html.escape(str(entry.get("id", "")), quote=True)
        source = html.escape(str(entry.get("source_object") or ""), quote=True)
        image = f'<img loading="lazy" src="{uri}" alt="{eid}">'
        if entry.get("max_path"):
            href = html.escape(Path(entry["max_path"]).as_uri(), quote=True)
            body = f'<a href="{href}">{image}</a>'
        else:
            body = image
        note = "<br>neutral shape only" if entry.get("preview_style") == "neutral-shape-only" else ""
        items.append(f"<figure>{body}<figcaption>{eid}<br>{source}{note}</figcaption></figure>")
    safe_title = html.escape(title, quote=True)
    head = (
        "<!doctype html><meta charset=\"utf-8\">"
        f"<title>{safe_title}</title>"
        "<style>body{font:13px sans-serif;background:#eee}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr))}"
        "figure{margin:6px;padding:6px;background:white}"
        "img{width:160px;height:160px;object-fit:contain}"
        "figcaption{overflow-wrap:anywhere}</style>"
        f"<h1>{shown} MAF audit previews</h1>"
        "<p>Local previews remain outside Git. Open this file locally on the audit workstation. "
        f"{neutral} previews use neutral materials; not appearance/delivery approval. "
        "Click a preview to open its Max asset.</p><main>\n"
    )
    return head + "\n".join(items) + "\n</main>\n"


def preview_check(entries, threshold=12, min_fg=8) -> dict:
    """Flag near-uniform preview images. Missing files are reported, not treated as blank."""
    from PIL import Image

    checked = []
    blank = []
    missing = []
    for entry in entries:
        preview = entry.get("preview_path")
        if not preview:
            continue
        eid = entry["id"]
        path = Path(preview)
        if not path.is_file():
            missing.append(eid)
            continue
        with Image.open(path) as image:
            rgb = image.convert("RGB").resize((64, 64))
            pixels = list(rgb.get_flattened_data())
        background = pixels[0]
        foreground = 0
        for pixel in pixels:
            distance = (
                abs(pixel[0] - background[0])
                + abs(pixel[1] - background[1])
                + abs(pixel[2] - background[2])
            )
            if distance > threshold:
                foreground += 1
        checked.append(eid)
        if foreground < min_fg:
            blank.append(eid)
    return {
        "checked": checked,
        "blank": blank,
        "missing": missing,
        "threshold": threshold,
        "min_fg": min_fg,
    }


def _dims3(value):
    """Three finite numbers as floats, or None. Bool is not a number."""
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            return None
        numbers.append(float(item))
    return numbers


def _triangle_count(value):
    """Non-negative int triangle count, or None. Bool is not a count."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _readback_invalid_reason(row) -> str | None:
    """Why a non-error readback row is not measurable evidence, or None when it is."""
    if _triangle_count(row.get("tris")) is None:
        return "tris is not a non-negative integer"
    referenced = row.get("referenced_vertices")
    ref_dims = referenced.get("dims_m") if isinstance(referenced, dict) else None
    if _dims3(ref_dims) is None:
        return "referenced_vertices.dims_m is not 3 finite numbers"
    all_vertices = row.get("all_vertices")
    all_dims = all_vertices.get("dims_m") if isinstance(all_vertices, dict) else None
    if _dims3(all_dims) is None:
        return "all_vertices.dims_m is not 3 finite numbers"
    if not isinstance(row.get("objects"), list):
        return "objects is not a list"
    return None


def _max_abs_delta(left, right) -> float:
    left3 = _dims3(left)
    right3 = _dims3(right)
    if left3 is None or right3 is None:
        raise ValueError("both arguments must be 3 finite numbers")
    return max(abs(a - b) for a, b in zip(left3, right3))


def _check_plan_and_built(plan, built_rows) -> set[str]:
    if not isinstance(plan, dict) or not isinstance(plan.get("entries"), list):
        raise ValueError("plan must be an object with an entries list")
    plan_ids: set[str] = set()
    for entry in plan["entries"]:
        eid = _entry_id(entry, "plan entry")
        if eid in plan_ids:
            raise ValueError(f"duplicate plan id {eid!r}")
        plan_ids.add(eid)
    seen = set()
    for row in built_rows:
        eid = _entry_id(row, "built row")
        if eid in seen:
            raise ValueError(f"duplicate built id {eid!r}")
        if eid not in plan_ids:
            raise ValueError(f"built id {eid!r} not in plan")
        seen.add(eid)
    return plan_ids


def _fbx_readback_section(plan, readback_doc, readback_path):
    if readback_doc is None:
        return {"status": "not measured"}
    by_stem: dict[str, dict] = {}
    for filename, row in index_readback(readback_doc).items():
        stem = Path(filename).stem
        if stem in by_stem:
            raise ValueError(f"duplicate readback stem {stem!r}")
        by_stem[stem] = row

    not_measured = []
    errors = []
    invalid = []
    not_one_mesh = []
    tri_diff = []
    dims_diff = []
    loose_bounds = []
    measured_rows = []
    matched = 0
    for entry in plan["entries"]:
        eid = _entry_id(entry, "plan entry")
        if _dims3(entry.get("dims_m")) is None or _triangle_count(entry.get("tris")) is None:
            raise ValueError(
                f"plan entry {eid!r} dims_m must be 3 finite numbers and tris a non-negative integer"
            )
        slug = entry.get("slug")
        row = by_stem.get(slug) if isinstance(slug, str) else None
        if row is None:
            not_measured.append(eid)
            continue
        matched += 1
        if row.get("error"):
            errors.append({"id": eid, "error": row["error"]})
            continue
        reason = _readback_invalid_reason(row)
        if reason is not None:
            invalid.append({"id": eid, "reason": reason})
            continue
        measured_rows.append(row)
        if row.get("meshes") != 1:
            not_one_mesh.append(eid)
        delta = row["tris"] - entry["tris"]
        referenced = row["referenced_vertices"]["dims_m"]
        dim_delta = _max_abs_delta(entry["dims_m"], referenced)
        if delta:
            tri_diff.append({
                "id": eid,
                "expected_tris": entry["tris"],
                "readback_tris": row["tris"],
                "delta": delta,
            })
        if dim_delta > _DIM_TOLERANCE_M:
            dims_diff.append({"id": eid, "delta_m": dim_delta})
        all_delta = _max_abs_delta(entry["dims_m"], row["all_vertices"]["dims_m"])
        if all_delta > _DIM_TOLERANCE_M:
            loose_bounds.append({
                "id": eid,
                "all_vertex_delta_m": all_delta,
                "referenced_vertex_delta_m": dim_delta,
                "loose_vertices": sum(obj["loose_vertices"] for obj in row["objects"]),
            })

    objects = [obj for row in measured_rows for obj in row["objects"]]
    measured = len(measured_rows)
    section = {
        "blender": readback_doc.get("blender"),
        "seconds": readback_doc.get("seconds"),
        "files": matched,
        "one_mesh": sum(row.get("meshes") == 1 for row in measured_rows),
        "tris_exact": measured - len(tri_diff),
        "tris_differences": tri_diff,
        "referenced_dims_within_5mm": measured - len(dims_diff),
        "dims_differences": dims_diff,
        "loose_vertex_bounds": loose_bounds,
        "non_triangle_faces": sum(obj["non_triangle_faces"] for obj in objects),
        "zero_area_triangles": sum(obj["zero_area_triangles"] for obj in objects),
        "meshes_without_uv": sum(not obj["uv_layers"] for obj in objects),
        "meshes_without_materials": sum(not obj["materials"] for obj in objects),
        "unassigned_faces": sum(obj["unassigned_faces"] for obj in objects),
        "details_path": None if not readback_path else Path(readback_path).as_posix(),
    }
    if not_one_mesh:
        section["not_one_mesh"] = not_one_mesh
    if not_measured:
        section["not_measured"] = not_measured
    if errors:
        section["errors"] = errors
    if invalid:
        section["invalid"] = invalid
    return section


def _blend_section(plan, blend_doc):
    if blend_doc is None:
        return {"status": "not measured"}, None
    matches = match_npm(plan["entries"], blend_doc)
    section = {}
    for group in ("all", "НПМ", "ВПМ"):
        if group == "all":
            subset = list(matches)
        else:
            subset = [row for row in matches if group in (row.get("collections") or [])]
        section[group] = {
            "rows": len(subset),
            "methods": dict(Counter(row.get("method") for row in subset)),
            "lower_triangle_candidates": sum(bool(row.get("light_pair")) for row in subset),
        }
    return section, matches


def _preview_repair_section(override_manifests, blank_before, preview_report, preview_repair_run):
    if not override_manifests:
        return {"count": 0}
    ids = []
    styles = []
    manifests = []
    for path, rows in override_manifests:
        manifests.append(Path(path).as_posix())
        for row in rows:
            ids.append(_entry_id(row, "override row"))
            if "preview_style" in row and row["preview_style"] is not None:
                styles.append(row["preview_style"])
    distinct = sorted(set(styles))
    if len(distinct) == 1:
        style = distinct[0]
    elif not distinct:
        style = None
    else:
        style = distinct
    if preview_repair_run is not None and "seconds" in preview_repair_run:
        wrapper_seconds = preview_repair_run["seconds"]
    else:
        wrapper_seconds = "not measured"
    coverage = {}
    if preview_report is None:
        blank_after = "not measured"
        verified_by = "not measured"
    else:
        checked_list = preview_report.get("checked") or []
        checked = set(checked_list)
        blank = set(preview_report.get("blank") or [])
        missing = set(preview_report.get("missing") or [])
        stray_blank = sorted(blank - checked)
        if stray_blank:
            raise ValueError(f"preview report blank id not in checked: {stray_blank[0]}")
        overlap = sorted(checked & missing)
        if overlap:
            raise ValueError(f"preview report id in both checked and missing: {overlap[0]}")
        override_ids = set(ids)
        verified_by = f"maf_audit.py preview-check over {len(checked_list)} preview paths"
        if override_ids <= checked:
            blank_after = len(override_ids & blank)
        else:
            blank_after = "not measured"
            coverage = {
                "blank_after_not_measured": sorted(override_ids - checked),
                "blank_after_measured_blank": sorted(override_ids & blank),
            }
    section = {
        "count": len(set(ids)),
        "style": style,
        "manifest": manifests[0] if len(manifests) == 1 else manifests,
        "wrapper_seconds": wrapper_seconds,
        "blank_before": len(blank_before) if blank_before is not None else "not measured",
        "blank_after": blank_after,
        "verified_by": verified_by,
    }
    section.update(coverage)
    return section


def build_audit(
    *,
    plan,
    built_rows,
    library_dir,
    readback_doc=None,
    blend_doc=None,
    source_hashes=None,
    override_manifests=None,
    blank_before=None,
    preview_check=None,
    native_probe=None,
    preview_repair_run=None,
    contact_sheet=None,
    readback_path=None,
):
    """Assemble audit.json from measured inputs. Returns ``(audit, npm_matches)``."""
    _check_plan_and_built(plan, built_rows)
    if override_manifests is None:
        override_manifests = []
    files = {}
    root = Path(library_dir)
    for ext in ("max", "fbx"):
        paths = [path for path in (root / ext).glob("*." + ext) if path.is_file()]
        files[ext] = {
            "count": len(paths),
            "bytes": sum(path.stat().st_size for path in paths),
        }
    seconds = [row["seconds"] for row in built_rows]
    if source_hashes is None:
        hashes_section = {"status": "not measured"}
    elif isinstance(source_hashes, dict):
        hashes_section = dict(source_hashes)
    else:
        hashes_section = list(source_hashes)
    audit = {
        "scope": _SCOPE,
        "source_hashes": hashes_section,
        "files": files,
        "build": {
            "entries": len(plan["entries"]),
            "ok": sum(row["ok"] for row in built_rows),
            "sum_entry_seconds": round(sum(seconds), 2),
            "slowest_entry_seconds": max(seconds) if seconds else None,
        },
        "fbx_readback": _fbx_readback_section(plan, readback_doc, readback_path),
    }
    blend_section, matches = _blend_section(plan, blend_doc)
    audit["blend_matching"] = blend_section
    audit["preview_repair"] = _preview_repair_section(
        override_manifests, blank_before, preview_check, preview_repair_run
    )
    if native_probe is None:
        audit["native_sample_readback"] = {"status": "not measured"}
    else:
        native = dict(native_probe)
        covered = len(native.get("entries") or [])
        native["coverage"] = (
            f"{covered}/{len(plan['entries'])} files; not an all-file native Max readback"
        )
        audit["native_sample_readback"] = native
    audit["contact_sheet"] = contact_sheet
    return audit, matches


def hash_sources(hash_before_path, copies: list[str]) -> list[dict]:
    """Replay a ``sha256 *path`` manifest against current files and suffix-matched copies.

    A missing original is ``sha256_after = "not measured"``. A hash mismatch on a
    file that still exists, or a copy whose hash differs from the recorded
    before-hash, raises ValueError.
    """
    by_suffix: dict[str, str] = {}
    for copy in copies:
        suffix = Path(copy).suffix.lower()
        if not suffix:
            raise ValueError(f"copy has no suffix: {copy}")
        if suffix in by_suffix:
            raise ValueError(f"exactly one copy per suffix required, duplicate {suffix}")
        by_suffix[suffix] = copy

    rows = []
    text = Path(hash_before_path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        if " *" not in line:
            raise ValueError(f"bad hash line: {line!r}")
        before, original = line.split(" *", 1)
        suffix = Path(original).suffix.lower()
        if suffix not in by_suffix:
            raise ValueError(f"exactly one copy per suffix required, missing {suffix}")
        copy = by_suffix[suffix]
        original_path = Path(original)
        if original_path.exists():
            after = _sha256_file(original_path)
        else:
            after = "not measured"
        copy_sha = _sha256_file(copy)
        if after != "not measured" and before != after:
            raise ValueError(f"source changed: {original}")
        if before != copy_sha:
            raise ValueError(f"source changed: copy {copy} does not match {original}")
        rows.append({
            "path": original,
            "sha256_before": before,
            "sha256_after": after,
            "copy": Path(copy).as_posix(),
            "copy_sha256": copy_sha,
        })
    return rows


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_id_list(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, dict) and "id" in item for item in value)


def _values_equal(left, right) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if _is_number(left) and _is_number(right):
        return abs(float(left) - float(right)) <= 1e-9
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            return False
        return all(_values_equal(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_values_equal(a, b) for a, b in zip(left, right))
    return left == right


def semantic_diff(old, new, max_examples=5) -> dict:
    """Diff two JSON documents. Id-bearing lists of objects are maps; floats match within 1e-9."""
    paths: dict[str, dict] = {}
    missing_ids: dict[str, list] = {}
    extra_ids: dict[str, list] = {}

    def record(path, kind, example):
        slot = paths.get(path)
        if slot is None:
            slot = {"kind": kind, "count": 0, "examples": []}
            paths[path] = slot
        elif slot["kind"] != kind:
            slot["kind"] = "changed"
        slot["count"] += 1
        if len(slot["examples"]) < max_examples:
            slot["examples"].append(example)

    def walk(left, right, path, locator):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in list(dict.fromkeys([*left.keys(), *right.keys()])):
                child = f"{path}.{key}" if path else str(key)
                if key not in right:
                    record(child, "removed", {**locator, "old": left[key], "new": None})
                elif key not in left:
                    record(child, "added", {**locator, "old": None, "new": right[key]})
                else:
                    walk(left[key], right[key], child, locator)
            return
        if isinstance(left, list) and isinstance(right, list) and _is_id_list(left) and _is_id_list(right):
            left_map = {}
            right_map = {}
            for item in left:
                eid = item["id"]
                if eid in left_map:
                    raise ValueError(f"duplicate id {eid!r} under {path or '$'}")
                left_map[eid] = item
            for item in right:
                eid = item["id"]
                if eid in right_map:
                    raise ValueError(f"duplicate id {eid!r} under {path or '$'}")
                right_map[eid] = item
            missing = [eid for eid in left_map if eid not in right_map]
            extra = [eid for eid in right_map if eid not in left_map]
            if missing:
                missing_ids.setdefault(path, []).extend(missing)
            if extra:
                extra_ids.setdefault(path, []).extend(extra)
            child_path = f"{path}[*]" if path else "[*]"
            for eid in left_map:
                if eid in right_map:
                    walk(left_map[eid], right_map[eid], child_path, {"id": eid})
            return
        if isinstance(left, list) and isinstance(right, list):
            child_path = f"{path}[*]" if path else "[*]"
            shared = min(len(left), len(right))
            for index in range(shared):
                walk(left[index], right[index], child_path, {"index": index})
            for index in range(shared, len(left)):
                record(child_path, "removed", {"index": index, "old": left[index], "new": None})
            for index in range(shared, len(right)):
                record(child_path, "added", {"index": index, "old": None, "new": right[index]})
            return
        if not _values_equal(left, right):
            record(path or "$", "changed", {**locator, "old": left, "new": right})

    walk(old, new, "", {})
    return {
        "equal": not paths and not missing_ids and not extra_ids,
        "paths": paths,
        "missing_ids": missing_ids,
        "extra_ids": extra_ids,
    }


def _provenance_for(pairs) -> list[dict]:
    return [file_provenance(role, path) for role, path in pairs if path]


def _cmd_merge(args) -> int:
    _require_writable(args.out, args.overwrite)
    _require_writable(args.provenance_out, args.overwrite)
    base = read_jsonl_unique(args.base)
    overrides = [(path, read_jsonl_unique(path)) for path in (args.override or [])]
    merged, provenance = merge_manifests(base, overrides)
    _write_text(args.out, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in merged))
    if args.provenance_out:
        _write_text(args.provenance_out, json.dumps(provenance, ensure_ascii=False, indent=2) + "\n")
    return 0


def _cmd_preview(args) -> int:
    _require_writable(args.out, args.overwrite)
    catalogue = _read_json(args.catalogue)
    report = preview_check(catalogue.get("entries") or [])
    _write_text(args.out, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


def _cmd_compare(args) -> int:
    _require_writable(args.out, args.overwrite)
    diff = semantic_diff(_read_json(args.old), _read_json(args.new))
    _write_text(args.out, json.dumps(diff, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(diff['paths'])} differing paths")
    return 0


def _cmd_finalize(args) -> int:
    _require_writable(args.out_json, args.overwrite)
    _require_writable(args.out_html, args.overwrite)
    catalogue = _read_json(args.catalogue)
    readback = _read_json(args.readback) if args.readback else None
    preview = _read_json(args.preview_check) if args.preview_check else None
    pairs = [("catalogue", args.catalogue)]
    if args.readback:
        pairs.append(("readback", args.readback))
    if args.preview_check:
        pairs.append(("preview-check", args.preview_check))
    contact = Path(args.contact_sheet_png).as_posix() if args.contact_sheet_png else None
    final = finalize_catalogue(
        catalogue,
        readback_doc=readback,
        preview_check=preview,
        contact_sheet=contact,
        provenance=_provenance_for(pairs),
    )
    if args.out_json:
        _write_text(args.out_json, dump_catalogue_json(final))
    if args.out_html:
        _write_text(args.out_html, render_contact_sheet_html(final["entries"]))
    print(json.dumps(final["counts"], ensure_ascii=False))
    return 0


def _cmd_audit(args) -> int:
    _require_writable(args.out, args.overwrite)
    _require_writable(args.npm_matches_out, args.overwrite)
    plan = _read_json(args.plan)
    built_rows = read_jsonl_unique(args.built)
    readback = _read_json(args.readback) if args.readback else None
    blend = _read_json(args.blend) if args.blend else None
    preview = _read_json(args.preview_check) if args.preview_check else None
    native = _read_json(args.native_probe) if args.native_probe else None
    repair_run = _read_json(args.preview_repair_run) if args.preview_repair_run else None
    blank_before = None
    if args.blank_before:
        blank_before = _read_json(args.blank_before)
        if not isinstance(blank_before, list):
            raise ValueError("blank-before file must be a JSON list of ids")
    overrides = [(path, read_jsonl_unique(path)) for path in (args.override or [])]
    source_hashes = (
        hash_sources(args.hash_before, list(args.copy or []))
        if args.hash_before is not None
        else None
    )
    contact = Path(args.contact_sheet_png).as_posix() if args.contact_sheet_png else None
    audit, matches = build_audit(
        plan=plan,
        built_rows=built_rows,
        library_dir=args.library,
        readback_doc=readback,
        blend_doc=blend,
        source_hashes=source_hashes,
        override_manifests=overrides,
        blank_before=blank_before,
        preview_check=preview,
        native_probe=native,
        preview_repair_run=repair_run,
        contact_sheet=contact,
        readback_path=args.readback,
    )
    pairs = [("plan", args.plan), ("built", args.built)]
    if args.readback:
        pairs.append(("readback", args.readback))
    if args.blend:
        pairs.append(("blend", args.blend))
    if args.hash_before:
        pairs.append(("hash-before", args.hash_before))
    for copy in args.copy or []:
        pairs.append(("copy", copy))
    for path in args.override or []:
        pairs.append(("override", path))
    if args.blank_before:
        pairs.append(("blank-before", args.blank_before))
    if args.preview_check:
        pairs.append(("preview-check", args.preview_check))
    if args.native_probe:
        pairs.append(("native-probe", args.native_probe))
    if args.preview_repair_run:
        pairs.append(("preview-repair-run", args.preview_repair_run))
    audit["provenance"] = _provenance_for(pairs)
    _write_text(args.out, json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    if args.npm_matches_out:
        payload = matches if matches is not None else []
        _write_text(args.npm_matches_out, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maf_audit", description="MAF catalogue finalisation and audit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    merge = sub.add_parser("merge-manifests", help="merge versioned JSONL manifests by id")
    merge.add_argument("--base", required=True)
    merge.add_argument("--override", action="append", default=[])
    merge.add_argument("--out", required=True)
    merge.add_argument("--provenance-out", default=None)
    merge.add_argument("--overwrite", action="store_true")

    preview = sub.add_parser("preview-check", help="flag blank preview images")
    preview.add_argument("--catalogue", required=True)
    preview.add_argument("--out", required=True)
    preview.add_argument("--overwrite", action="store_true")

    compare = sub.add_parser("compare", help="semantic diff of two JSON documents")
    compare.add_argument("--old", required=True)
    compare.add_argument("--new", required=True)
    compare.add_argument("--out", required=True)
    compare.add_argument("--overwrite", action="store_true")

    finalize = sub.add_parser("finalize", help="attach readback fields and write catalogue outputs")
    finalize.add_argument("--catalogue", required=True)
    finalize.add_argument("--readback", default=None)
    finalize.add_argument("--preview-check", default=None)
    finalize.add_argument("--contact-sheet-png", default=None)
    finalize.add_argument("--out-json", default=None)
    finalize.add_argument("--out-html", default=None)
    finalize.add_argument("--overwrite", action="store_true")

    audit = sub.add_parser("audit", help="write audit.json from plan, build rows and QA reports")
    audit.add_argument("--plan", required=True)
    audit.add_argument("--built", required=True)
    audit.add_argument("--library", required=True)
    audit.add_argument("--readback", default=None)
    audit.add_argument("--blend", default=None)
    audit.add_argument("--hash-before", default=None)
    audit.add_argument("--copy", action="append", default=[])
    audit.add_argument("--override", action="append", default=[])
    audit.add_argument("--blank-before", default=None)
    audit.add_argument("--preview-check", default=None)
    audit.add_argument("--native-probe", default=None)
    audit.add_argument("--preview-repair-run", default=None)
    audit.add_argument("--contact-sheet-png", default=None)
    audit.add_argument("--npm-matches-out", default=None)
    audit.add_argument("--out", required=True)
    audit.add_argument("--overwrite", action="store_true")
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "merge-manifests":
        return _cmd_merge(args)
    if args.cmd == "preview-check":
        return _cmd_preview(args)
    if args.cmd == "compare":
        return _cmd_compare(args)
    if args.cmd == "finalize":
        return _cmd_finalize(args)
    if args.cmd == "audit":
        return _cmd_audit(args)
    raise ValueError(f"unknown command {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
