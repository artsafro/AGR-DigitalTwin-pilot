"""Compare 3ds Max xView OverlappingVertices / OverlappingFaces results with dt_ai.ops.inv_xview (#370).

Input: the JSON written by `tools/qa/xview_dump.ms` (headless Max via dcc_batch.py on a COPY of an FBX):
per node the Max result ids (1-based), vertices in metres and faces (1-based vertex ids).
Output: one JSON line per node with counts on both sides and every id that differs.

  uv run python tools/qa/xview_parity.py <dump.json> [--out parity.json]
  uv run python tools/qa/xview_parity.py --keep <xview_check.keep> --npz <arrays.npz> [--out parity.json]
  uv run python tools/qa/xview_parity.py <review.json> --validate-review [--out copy.json]
  uv run python tools/qa/xview_parity.py --check-run <out-dir> --labels a,b
  (jobs.txt must start with #nonce:<id>; done.txt and each result JSON must carry that nonce)

The second form (#535) compares the stored list of a Max xView run (`jobs/vyatskaya-tow02/scripts/xview_check.ms`
JSON: `verticesCheck` / `facesCheck` with `items` [id, ...] 1-based, `faces`, `verts`, `tolFaces`, `tolVerts`) with
the checker on the same mesh as Blender arrays (`vertices`, `loop_start`, `loop_total`, `loop_vert`; Max face id
- 1 = Blender polygon index). A face or vertex count that differs from the keep, a check count that differs from its
item list, or a tolerance that is not a finite number > 0 exits 2.

Fail-closed: a dump with no nodes, a node without vertices or faces, counts that disagree with the lists (partial
dump), a checker result that is not `#vertices` / `#faces` (xView failed), a missing result, an id out of range or not
an integer, or a bad tolerance exits 2 and writes nothing. `--out` that is the input (same path, symlink or hardlink)
exits 2 before any write. Exit 1: measured but not equal; 0: every node equal.
"""
import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import sys
from pathlib import Path

import numpy as np

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, part_report


class DumpError(ValueError):
    """The Max dump is empty, partial, failed or malformed: no parity can be claimed."""


def _int(x, what: str, lo: int, hi: int) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise DumpError(f"{what}: {x!r} is not an integer")
    if not lo <= x <= hi:
        raise DumpError(f"{what}: {x} outside {lo}..{hi}")
    return x


def _num(dump: dict, key: str) -> float:
    x = dump.get(key)
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
        raise DumpError(f"{key}: {x!r} is not a finite number > 0")
    return float(x)


def _node(node: dict) -> tuple:
    name = node.get("name", "?")
    for key, want in (("verts_type", "#vertices"), ("faces_type", "#faces")):
        if str(node.get(key, "")).lower() != want:
            raise DumpError(f"node {name}: xView {key} = {node.get(key)!r}, expected {want} (checker failed?)")
    for key in ("vertices", "faces", "overlap_vertices", "overlap_faces", "num_verts", "num_faces"):
        if key not in node:
            raise DumpError(f"node {name}: {key} missing")
    verts, faces = node["vertices"], node["faces"]
    if not verts or not faces:
        raise DumpError(f"node {name}: no vertices or no faces measured")
    nv, nf = len(verts), len(faces)
    if node["num_verts"] != nv or node["num_faces"] != nf:
        raise DumpError(f"node {name}: partial dump, {nv}/{node['num_verts']} vertices, {nf}/{node['num_faces']} faces")
    ids = tuple(tuple(_int(i, f"node {name} face {k}", 1, nv) - 1 for i in f) for k, f in enumerate(faces))
    mv = {_int(i, f"node {name} overlap_vertices", 1, nv) for i in node["overlap_vertices"]}
    mf = {_int(i, f"node {name} overlap_faces", 1, nf) for i in node["overlap_faces"]}
    try:
        mesh = PolyMesh(np.asarray(verts, dtype=float), ids)
    except (ValueError, TypeError) as e:
        raise DumpError(f"node {name}: {e}") from e
    return mesh, mv, mf


def compare(dump: dict) -> list[dict]:
    rows = []
    if not isinstance(dump, dict) or not isinstance(dump.get("nodes"), list) or not dump["nodes"]:
        raise DumpError("no nodes in the dump: nothing was measured")
    m = _num(dump, "m_per_unit")
    tol = XviewTolerance(vertex_m=_num(dump, "tol_v_units") * m, face_m=_num(dump, "tol_f_units") * m).validate()
    for node in dump["nodes"]:
        mesh, mv, mf = _node(node)
        r = part_report(node["name"], mesh, tol)
        ov, of, oa = set(r.vertices), set(r.xview_faces), set(r.faces)
        rows.append({"node": node["name"], "class": node["class"], "vertices": len(mesh.vertices),
                     "faces": len(mesh.faces), "thresholds_m": [tol.vertex_m, tol.face_m],
                     "max_vertices": len(mv), "ours_vertices": len(ov), "ours_vertex_pairs": len(r.vertex_pairs),
                     "vertices_only_max": sorted(mv - ov), "vertices_only_ours": sorted(ov - mv),
                     "max_faces": len(mf), "ours_contact_faces": len(of), "ours_all_faces": len(oa),
                     "ours_face_pairs": r.to_dict()["face_pairs_by_kind"],
                     "faces_only_max": sorted(mf - of), "faces_only_ours_contact": sorted(of - mf),
                     "faces_area_only": sorted(oa - of),
                     "equal": mv == ov and mf == of})
    return rows


def _loops(arrays) -> tuple:
    """Validated (vertices, loop_start, loop_total, loop_vert): no coercion, no ignored or shared loop.

    vertices: float (n, 3), n > 0; the loop arrays: 1-D, integer dtype (not bool, not float even if integral);
    loop_total >= 3; loop_start[0] == 0 and each face starts where the previous ends, so the faces cover loop_vert
    exactly (no overlap, gap or unused suffix); loop_vert in 0..n-1. Anything else -> DumpError naming the array.
    """
    v = np.asarray(arrays["vertices"])
    if v.ndim != 2 or v.shape[1] != 3 or not len(v) or not np.issubdtype(v.dtype, np.number) or v.dtype == bool:
        raise DumpError(f"arrays: vertices must be a non-empty numeric (n, 3) array, got {v.dtype} {v.shape}")
    out = [v.astype(float)]
    for key in ("loop_start", "loop_total", "loop_vert"):
        a = np.asarray(arrays[key])
        if a.ndim != 1 or not np.issubdtype(a.dtype, np.integer):
            raise DumpError(f"arrays: {key} must be a 1-D integer array, got {a.dtype} {a.shape}")
        out.append(a.astype(np.int64))
    v, st, tot, lv = out
    if not len(tot) or len(st) != len(tot):
        raise DumpError(f"arrays: loop_start ({len(st)}) / loop_total ({len(tot)}): no faces or lengths differ")
    if (tot < 3).any():
        raise DumpError(f"arrays: loop_total has {int((tot < 3).sum())} faces with fewer than 3 corners")
    ends = np.cumsum(tot)
    if st[0] != 0 or (st[1:] != ends[:-1]).any():
        raise DumpError("arrays: loop_start is not contiguous from 0 (overlapping or skipped loops)")
    if ends[-1] != len(lv):
        raise DumpError(f"arrays: loop_vert has {len(lv)} entries, the faces use {int(ends[-1])} (unused suffix?)")
    if lv.min() < 0 or lv.max() >= len(v):
        raise DumpError(f"arrays: loop_vert outside 0..{len(v) - 1}")
    return v, st, tot, lv


def compare_keep(keep: dict, arrays) -> list[dict]:
    """One row: Max xView keep (ids only) vs part_report on the Blender arrays of the same FBX."""
    if not isinstance(keep, dict):
        raise DumpError("keep is not a JSON object")
    checks = {}
    for key in ("verticesCheck", "facesCheck"):
        c = keep.get(key)
        if not isinstance(c, dict) or not isinstance(c.get("items"), list) or not isinstance(c.get("count"), int):
            raise DumpError(f"{key} missing or without count / items (xView failed?)")
        if c["count"] != len(c["items"]):
            raise DumpError(f"{key}: count {c['count']} != {len(c['items'])} items (partial keep)")
        checks[key] = c
    for key in ("vertices", "loop_start", "loop_total", "loop_vert"):
        if key not in arrays:
            raise DumpError(f"arrays: {key} missing")
    v, st, tot, lv = _loops(arrays)
    nv, nf = len(v), len(tot)
    if keep.get("faces") != nf or keep.get("verts") != nv:
        raise DumpError(f"keep has {keep.get('faces')} faces / {keep.get('verts')} verts, arrays {nf} / {nv}: "
                        "not the same mesh")
    tol = XviewTolerance(vertex_m=_num(keep, "tolVerts"), face_m=_num(keep, "tolFaces")).validate()
    mf = {_int(i[0] if isinstance(i, list) else i, "facesCheck item", 1, nf) for i in checks["facesCheck"]["items"]}
    mv = {_int(i[0] if isinstance(i, list) else i, "verticesCheck item", 1, nv)
          for i in checks["verticesCheck"]["items"]}
    try:
        faces = tuple(tuple(int(x) for x in lv[s:s + t]) for s, t in zip(st.tolist(), tot.tolist()))
        mesh = PolyMesh(v, faces)
    except (ValueError, TypeError) as e:
        raise DumpError(f"arrays: {e}") from e
    r = part_report(str(keep.get("node", "mesh")), mesh, tol)
    ov, of, oa = set(r.vertices), set(r.xview_faces), set(r.faces)
    return [{"node": str(keep.get("node", "mesh")), "vertices": nv, "faces": nf, "thresholds_m": [tol.vertex_m, tol.face_m],
             "max_vertices": len(mv), "ours_vertices": len(ov), "ours_vertex_pairs": len(r.vertex_pairs),
             "vertices_only_max": sorted(mv - ov), "vertices_only_ours": sorted(ov - mv),
             "max_faces": len(mf), "ours_contact_faces": len(of), "ours_all_faces": len(oa),
             "ours_face_pairs": r.to_dict()["face_pairs_by_kind"],
             "faces_only_max": sorted(mf - of), "faces_only_ours_contact": sorted(of - mf),
             "faces_area_only": sorted(oa - of), "equal": mv == ov and mf == of}]


# ---- #528 runner contract (no Max) -------------------------------------------------------------------------------

WELD_M = 0.002  # Editable Mesh weld, exactly units.decodeValue "2mm"; inclusive
_JOB_KEYS = {"label", "path", "node", "mode", "material", "slot"}
_MODES = {"", "plain", "weld", "weldpoly"}
_MESH_SUFFIXES = {".fbx", ".max"}
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
# Keys written by tools/qa/xview_dump.ms for one successful model, plus the run nonce.
NATIVE_KEYS = (
    "dump_version", "nonce", "label", "path", "saved", "sha256_before", "sha256_after",
    "units", "systemScale", "tolFaces", "tolVerts", "scene", "dropped", "node",
    "sourceClass", "weldedVerts", "faces", "verts", "tris", "ngons", "bbox",
    "verticesCheck", "facesCheck",
)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ascii_path(path: Path) -> bool:
    try:
        str(path).encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def stage_input(src, temp_dir) -> Path:
    """Copy a non-ASCII path to an ASCII file. SHA-256 of the copy equals the source. Never deletes src."""
    src = Path(src)
    if not src.is_file():
        raise DumpError(f"input missing: {src}")
    temp_dir = Path(temp_dir)
    digest = sha256_file(src)
    suffix = src.suffix if src.suffix.isascii() else ""
    dest = temp_dir / f"xv_{digest}{suffix}"
    if dest.exists() and (dest.resolve() == src.resolve() or os.path.samefile(dest, src)):
        raise DumpError(f"temp aliases input {src}")
    if _ascii_path(src):
        return src
    temp_dir.mkdir(parents=True, exist_ok=True)
    if not _ascii_path(temp_dir):
        raise DumpError(f"temp dir is not ASCII: {temp_dir}")
    if not _ascii_path(dest):
        raise DumpError(f"staged path is not ASCII: {dest}")
    if dest.exists() and os.path.samefile(dest, src):
        raise DumpError(f"temp aliases input {src}")
    if dest.resolve() == src.resolve():
        raise DumpError(f"temp aliases input {src}")
    if not dest.exists():
        shutil.copyfile(src, dest)
    if sha256_file(dest) != digest or sha256_file(src) != digest:
        raise DumpError(f"SHA-256 mismatch for {src}")
    return dest


def weld_includes(distance_m) -> bool:
    """True when a vertex pair is within the 2 mm weld, including exactly 2 mm. Non-finite is an error."""
    if isinstance(distance_m, bool) or not isinstance(distance_m, (int, float)) or not math.isfinite(distance_m):
        raise DumpError(f"weld distance {distance_m!r} is not a finite number")
    return float(distance_m) <= WELD_M


def require_unchanged(before: str, after: str) -> None:
    if before != after:
        raise DumpError("input bytes changed (the .max/.fbx must never be saved)")


def require_distinct(paths: dict) -> None:
    """input, output, report and temp must not be the same file (path or hardlink)."""
    items = [(role, Path(path)) for role, path in paths.items()]
    for i, (role, path) in enumerate(items):
        for role2, path2 in items[i + 1:]:
            same = path.resolve() == path2.resolve() or (path.exists() and path2.exists() and os.path.samefile(path, path2))
            if same:
                raise DumpError(f"{role} aliases {role2}")


def same_file(a, b) -> bool:
    """True when two paths are one file: case-folded path, samefile, or st_dev+st_ino.

    Hardlinks, symlinks and Windows case variants count. A path that does not exist yet
    matches only a case-folded absolute path (the file it would create).
    """
    a, b = Path(a), Path(b)
    if os.path.normcase(os.path.abspath(os.fspath(a))) == os.path.normcase(os.path.abspath(os.fspath(b))):
        return True
    try:
        both = a.exists() and b.exists()
    except OSError:
        return False
    if not both:
        return False
    try:
        if os.path.samefile(a, b):
            return True
    except OSError:
        pass
    try:
        sa = os.stat(a, follow_symlinks=True)
        sb = os.stat(b, follow_symlinks=True)
    except OSError:
        return False
    return sa.st_ino != 0 and sa.st_ino == sb.st_ino and sa.st_dev == sb.st_dev


def _planned_stage(src: Path, temp_dir: Path):
    """ASCII sources open in place. Anything else is the future xv_<sha> copy, not yet written."""
    if _ascii_path(src):
        return None
    if not _ascii_path(temp_dir):
        raise DumpError(f"temp dir is not ASCII: {temp_dir}")
    suffix = src.suffix if src.suffix.isascii() else ""
    dest = Path(temp_dir) / f"xv_{sha256_file(src)}{suffix}"
    if not _ascii_path(dest):
        raise DumpError(f"staged path is not ASCII: {dest}")
    return dest


def _conflicts(kind_a, kind_b, path_a, path_b) -> bool:
    if not same_file(path_a, path_b):
        return False
    if kind_a == "input" and kind_b == "input":
        return False
    if kind_a == "temp" and kind_b == "temp":
        return os.path.normcase(os.path.abspath(path_a)) != os.path.normcase(os.path.abspath(path_b))
    return True


def select_node(scene, node_name, material=None, materials=None, slot=None, slots=None):
    """Pick the named mesh, or the largest when the name is empty. Every other element is dropped with a reason."""
    if not isinstance(scene, list) or not scene:
        raise DumpError("no mesh")
    names = [n.get("name") for n in scene]
    if node_name:
        hits = [n for n in scene if n.get("name") == node_name]
        if len(hits) != 1:
            raise DumpError(f"unmapped node {node_name!r}")
        chosen = hits[0]
        if chosen.get("kind") != "mesh" or not chosen.get("faces"):
            raise DumpError(f"node {node_name!r}: empty mesh")
    else:
        meshes = [n for n in scene if n.get("kind") == "mesh" and n.get("faces")]
        if not meshes:
            raise DumpError("no mesh")
        chosen = max(meshes, key=lambda n: (n["faces"], names.index(n["name"]) * -1))
    dropped = []
    for n in scene:
        if n is chosen:
            continue
        if n.get("kind") != "mesh":
            reason = "not a mesh"
        elif not n.get("faces"):
            reason = "empty mesh"
        else:
            reason = "not selected"
        dropped.append({"name": n.get("name"), "reason": reason})
    if material is not None and material != "":
        if materials is None or material not in materials:
            raise DumpError(f"unmapped material {material!r}")
    if slot is not None and slot != "":
        slot_s = str(slot)
        known = {str(s) for s in (slots or [])}
        if slot_s not in known:
            raise DumpError(f"unmapped slot {slot_s!r}")
    return chosen, dropped


def _bad_field(value, what: str) -> str:
    text = "" if value is None else str(value)
    if any(ord(ch) < 32 or ch == "|" for ch in text):
        raise DumpError(f"bad field {what} {text!r}")
    return text


def bind_slot(slot, sub_count=None, present=None):
    """Empty slot is unset. Anything else must be a material id that is present when the map is known."""
    text = "" if slot is None else str(slot)
    if text == "":
        return ""
    if not text.isdigit() or text[0] == "0":
        raise DumpError(f"unmapped slot {text!r}")
    if sub_count is None:
        return text
    ident = int(text)
    if present is None or ident < 1 or ident > sub_count or ident > len(present) or not present[ident - 1]:
        raise DumpError(f"unmapped slot {text!r}")
    return text


def parse_job_line(line: str) -> dict:
    """One jobs.txt model line: exactly label|path|node|mode|material|slot."""
    parts = line.split("|")
    if len(parts) != 6:
        raise DumpError(f"jobs.txt line field count {len(parts)}")
    keys = ("label", "path", "node", "mode", "material", "slot")
    fields = {key: _bad_field(part, key) for key, part in zip(keys, parts)}
    label = fields["label"]
    if not label or label != Path(label).name or not _ascii_path(Path(label)):
        raise DumpError(f"unmapped label {label!r}")
    if fields["mode"] not in _MODES:
        raise DumpError(f"unmapped mode {fields['mode']!r}")
    fields["slot"] = bind_slot(fields["slot"])
    return fields


def _inventory(records, out_dir, temp_dir, jobs_file=None) -> None:
    """Raise when any managed path is the same file as an input or as another managed path."""
    out_dir = Path(out_dir)
    jobs_file = Path(jobs_file) if jobs_file is not None else out_dir / "jobs.txt"
    entries = []
    for rec in records:
        entries.append(("input", rec["src"], f"input {rec['src'].name}"))
        entries.append(("output", rec["out_file"], f"output {rec['label']!r}"))
        if rec.get("dest") is not None:
            entries.append(("temp", rec["dest"], f"temp {rec['dest'].name}"))
    entries.append(("jobs", jobs_file, "jobs.txt"))
    entries.append(("report", out_dir / "report.jsonl", "report.jsonl"))
    entries.append(("done", out_dir / "done.txt", "done.txt"))
    entries.append(("failed", out_dir / "failed.txt", "failed.txt"))
    if jobs_file.is_symlink():
        raise DumpError(f"jobs.txt aliases {os.path.realpath(jobs_file)}")
    for i, (kind_a, path_a, name_a) in enumerate(entries):
        for kind_b, path_b, name_b in entries[i + 1:]:
            if _conflicts(kind_a, kind_b, path_a, path_b):
                raise DumpError(f"{name_a} aliases {name_b}")


def _invalidate(out_dir, labels, inputs) -> None:
    """Drop this run's done receipt and result jsons. Never unlinks a path that is an input."""
    out_dir = Path(out_dir)
    if not out_dir.exists():
        return
    targets = [out_dir / "done.txt", out_dir / "report.jsonl", out_dir / "failed.txt"]
    targets += [out_dir / f"{label}.json" for label in labels]
    live = []
    seen_targets = set()
    for target in targets:
        if str(target) in seen_targets:
            continue
        seen_targets.add(str(target))
        if not (target.is_symlink() or target.exists()):
            continue
        for src in inputs:
            if same_file(target, src):
                raise DumpError(f"{target.name} aliases input {Path(src).name}")
        live.append(target)
    for target in live:
        target.unlink()


def _try_record(job, out_dir, temp_dir, scene):
    """Return (record or None, error or None). A record exists only when its paths can be checked."""
    if not isinstance(job, dict):
        return None, DumpError("job is not an object")
    unknown = sorted(set(job) - _JOB_KEYS)
    if unknown:
        return None, DumpError(f"unmapped key {unknown[0]!r}")
    try:
        label = _bad_field("" if job.get("label") is None else str(job.get("label")), "label")
        node = _bad_field("" if job.get("node") is None else str(job.get("node")), "node")
        mode = _bad_field("" if job.get("mode") is None else str(job.get("mode")), "mode")
        material = _bad_field("" if job.get("material") is None else str(job.get("material")), "material")
        slot = _bad_field("" if job.get("slot") is None else str(job.get("slot")), "slot")
        src = Path(job.get("path", ""))
        _bad_field(str(src), "path")
    except DumpError as exc:
        return None, exc
    if not label or label != Path(label).name or not _ascii_path(Path(label)):
        return None, DumpError(f"unmapped label {label!r}")
    error = None
    if mode not in _MODES:
        error = DumpError(f"unmapped mode {mode!r}")
    else:
        try:
            slot = bind_slot(slot)
        except DumpError as exc:
            error = exc
    if src.suffix.lower() not in _MESH_SUFFIXES:
        return None, error or DumpError(f"unsupported input {src.name!r}")
    if not src.is_file():
        return None, error or DumpError(f"input missing: {src}")
    try:
        dest = _planned_stage(src, temp_dir)
    except DumpError as exc:
        return None, error or exc
    if scene is not None and error is None:
        try:
            select_node(scene, node, material, None if "material" not in job else [], slot, None)
        except DumpError as exc:
            error = exc
    record = {"label": label, "src": src, "node": node, "mode": mode, "material": material, "slot": slot,
              "out_file": out_dir / f"{label}.json", "dest": dest}
    return record, error


def preflight_jobs_txt(jobs_file, out_dir, temp_dir) -> dict:
    """Read a manual or prepare_run jobs.txt the way the Max runner does. No writes.

    First line is ``#nonce:<id>``. Each other line has six fields. Duplicate labels, a bad
    slot token, and any output / report / done / failed / jobs / staging path that is the
    same file as an input (or as each other) raise before a directory is created.
    """
    jobs_file = Path(jobs_file)
    out_dir = Path(out_dir)
    temp_dir = Path(temp_dir)
    if not jobs_file.is_file():
        raise DumpError("jobs.txt missing")
    try:
        text = jobs_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DumpError(f"jobs.txt unreadable: {exc}") from exc
    lines = [ln for ln in text.splitlines() if ln != ""]
    if not lines or not lines[0].startswith("#nonce:"):
        raise DumpError("nonce missing")
    nonce = lines[0][len("#nonce:"):]
    if not _NONCE_RE.fullmatch(nonce):
        raise DumpError("nonce missing")
    if len(lines) < 2:
        raise DumpError("no inputs")
    parsed = [parse_job_line(ln) for ln in lines[1:]]
    seen = {}
    records = []
    for job in parsed:
        key = job["label"].casefold()
        if key in seen:
            raise DumpError(f"duplicate label {seen[key]!r} and {job['label']!r}")
        seen[key] = job["label"]
        src = Path(job["path"])
        if src.suffix.lower() not in _MESH_SUFFIXES:
            raise DumpError(f"unsupported input {src.name!r}")
        if not src.is_file():
            raise DumpError(f"input missing: {src}")
        records.append({"label": job["label"], "path": str(src), "node": job["node"], "mode": job["mode"],
                        "material": job["material"], "slot": job["slot"], "src": src,
                        "out_file": out_dir / f"{job['label']}.json", "dest": _planned_stage(src, temp_dir)})
    _inventory(records, out_dir, temp_dir, jobs_file)
    return {"nonce": nonce, "jobs": records}


def prepare_run(jobs, out_dir, temp_dir, scene=None) -> dict:
    """Stage inputs and write an ASCII jobs.txt whose first line is ``#nonce:<id>``.

    The whole inventory is checked before any directory is created or any byte is written.
    A duplicate label, a ``|`` / control character, or an unknown slot token is an error
    naming it. When the paths are not inputs, a failed preparation still removes this
    run's ``done.txt`` and ``<label>.json`` so an older success cannot be read back.
    An alias of an input is raised with nothing removed and nothing written.
    """
    if not isinstance(jobs, list) or not jobs:
        raise DumpError("no inputs")
    out_dir, temp_dir = Path(out_dir), Path(temp_dir)
    records = []
    errors = []
    for job in jobs:
        record, err = _try_record(job, out_dir, temp_dir, scene)
        if record is not None:
            records.append(record)
        if err is not None:
            errors.append(err)
    if records:
        _inventory(records, out_dir, temp_dir)
    seen = {}
    for record in records:
        key = record["label"].casefold()
        if key in seen:
            errors.append(DumpError(f"duplicate label {seen[key]!r} and {record['label']!r}"))
        else:
            seen[key] = record["label"]
    if errors:
        # Every rejection path (unknown key, malformed, missing, unsupported) drops the old success.
        labels = [record["label"] for record in records]
        inputs = [record["src"] for record in records]
        for job in jobs:
            if not isinstance(job, dict):
                continue
            raw = job.get("label")
            if isinstance(raw, str) and raw and raw == Path(raw).name and _ascii_path(Path(raw)):
                labels.append(raw)
            if isinstance(job.get("path"), (str, os.PathLike)) and str(job.get("path")):
                inputs.append(Path(job["path"]))
        _invalidate(out_dir, labels, inputs)
        raise errors[0]
    before = [(record["src"], sha256_file(record["src"])) for record in records]
    _invalidate(out_dir, [record["label"] for record in records], [record["src"] for record in records])
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    nonce = secrets.token_hex(16)
    jobs_file = out_dir / "jobs.txt"
    report = out_dir / "report.jsonl"
    done = out_dir / "done.txt"
    lines = []
    staged = []
    outputs = []
    for record in records:
        opened = stage_input(record["src"], temp_dir)
        digest = sha256_file(record["src"])
        if sha256_file(opened) != digest:
            raise DumpError(f"SHA-256 mismatch for {record['src']}")
        lines.append("|".join([record["label"], str(opened), record["node"], record["mode"],
                               record["material"], record["slot"]]))
        staged.append({"label": record["label"], "source": str(record["src"]), "opened": str(opened),
                       "sha256": digest, "output": str(record["out_file"])})
        outputs.append(record["out_file"])
    for row in staged:
        roles = {"input": Path(row["source"]), "output": Path(row["output"]), "report": report,
                 "jobs": jobs_file, "done": done}
        opened = Path(row["opened"])
        if not same_file(opened, row["source"]):
            roles["temp"] = opened
        require_distinct(roles)
    jobs_file.write_text("#nonce:" + nonce + "\n" + "\n".join(lines) + "\n", encoding="ascii")
    for src, digest in before:
        if sha256_file(src) != digest:
            raise DumpError("input bytes changed (the .max/.fbx must never be saved)")
    return {"jobs_file": jobs_file, "staged": staged, "outputs": outputs, "report": report, "nonce": nonce}


def _read_receipt(jobs_file):
    if not Path(jobs_file).is_file():
        raise DumpError("nonce missing")
    try:
        text = Path(jobs_file).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DumpError(f"jobs.txt unreadable: {exc}") from exc
    lines = [ln for ln in text.splitlines() if ln != ""]
    if not lines or not lines[0].startswith("#nonce:"):
        raise DumpError("nonce missing")
    nonce = lines[0][len("#nonce:"):]
    if not _NONCE_RE.fullmatch(nonce):
        raise DumpError("nonce missing")
    if len(lines) < 2:
        raise DumpError("no inputs")
    labels = [parse_job_line(ln)["label"] for ln in lines[1:]]
    return nonce, labels


def _bbox(value, what):
    if not isinstance(value, list) or len(value) != 2:
        raise DumpError(f"{what}: bbox must be two points")
    return [_xyz(value[0], what), _xyz(value[1], what)]


def _require_native(obj, label, nonce):
    if not isinstance(obj, dict):
        raise DumpError(f"{label}: result is not an object")
    if "error" in obj:
        raise DumpError(f"{label}: {obj.get('error')}")
    missing = [key for key in NATIVE_KEYS if key not in obj]
    if missing:
        raise DumpError(f"{label}: missing {missing[0]}")
    if obj.get("label") != label:
        raise DumpError(f"unmapped label {obj.get('label')!r}")
    if obj.get("nonce") != nonce:
        raise DumpError(f"{label}: stale nonce")
    validate_review(obj)
    if not isinstance(obj.get("path"), str) or not obj["path"]:
        raise DumpError(f"{label}: path missing")
    if not isinstance(obj.get("units"), str) or not obj["units"]:
        raise DumpError(f"{label}: units missing")
    _finite(obj.get("systemScale"), "systemScale")
    if not isinstance(obj.get("sourceClass"), str) or not obj["sourceClass"]:
        raise DumpError(f"{label}: sourceClass missing")
    welded = obj["weldedVerts"]
    if isinstance(welded, bool) or not isinstance(welded, int) or welded < -1:
        raise DumpError(f"{label}: weldedVerts {welded!r}")
    for key in ("faces", "verts", "tris", "ngons"):
        value = obj[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise DumpError(f"{label}: {key} {value!r}")
    _bbox(obj.get("bbox"), label)
    for check, kind in (("verticesCheck", "#Vertices"), ("facesCheck", "#Faces")):
        block = obj[check]
        for key in ("name", "type", "text", "seconds"):
            if key not in block:
                raise DumpError(f"{label}: {check} missing {key}")
        if block["type"] != kind:
            raise DumpError(f"{label}: {check} type {block['type']!r}")
        if not isinstance(block["name"], str) or not block["name"]:
            raise DumpError(f"{label}: {check} name")
        if not isinstance(block["text"], str):
            raise DumpError(f"{label}: {check} text")
        if _finite(block["seconds"], f"{check} seconds") < 0:
            raise DumpError(f"{label}: {check} seconds")
    return obj


def check_run(out_dir, expected_labels) -> dict:
    """Success is this invocation only: jobs.txt nonce, the same nonce in done.txt, no failed.txt,
    and every label json a complete native result carrying that nonce.

    ``{}``, an ``error`` key, null, a mismatched label, a partial schema, or a done receipt from
    another nonce is DumpError. quitMax does not publish a process exit code; this is the result.
    """
    out_dir = Path(out_dir)
    if not isinstance(expected_labels, (list, tuple)) or not list(expected_labels):
        raise DumpError("no inputs")
    nonce, job_labels = _read_receipt(out_dir / "jobs.txt")
    problems = []
    if list(expected_labels) != job_labels:
        problems.append("labels do not match jobs.txt")
    done = out_dir / "done.txt"
    if not done.is_file():
        problems.append("done.txt missing")
    else:
        try:
            done_text = done.read_text(encoding="ascii")
        except (OSError, UnicodeError) as exc:
            problems.append(f"stale done.txt: {exc}")
        else:
            if done_text.strip() != nonce:
                problems.append("stale done.txt")
    if (out_dir / "failed.txt").exists():
        problems.append("failed.txt present")
    parsed = {}
    missing = []
    unreadable = []
    for label in expected_labels:
        text = str(label)
        path = out_dir / f"{text}.json"
        if not path.is_file():
            missing.append(text)
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            unreadable.append(text)
            continue
        try:
            parsed[text] = _require_native(data, text, nonce)
        except DumpError as exc:
            problems.append(str(exc))
    if missing:
        problems.append("missing labels: " + ", ".join(missing))
    if unreadable:
        problems.append("unreadable labels: " + ", ".join(unreadable))
    if problems:
        raise DumpError("; ".join(problems))
    return parsed


def _finite(x, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise DumpError(f"{what}: {x!r} is not a finite number")
    return float(x)


def _xyz(x, what: str):
    if not isinstance(x, list) or len(x) != 3:
        raise DumpError(f"{what}: centre must be three numbers")
    return [_finite(c, what) for c in x]


def _items(check, what: str, width: int):
    if not isinstance(check, dict) or "count" not in check or "items" not in check:
        raise DumpError(f"{what} missing count or items")
    count = check["count"]
    items = check["items"]
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise DumpError(f"{what}: count {count!r} is not a whole number")
    if not isinstance(items, list) or len(items) != count:
        raise DumpError(f"{what}: count {count} != {len(items) if isinstance(items, list) else 'no'} items (partial)")
    parsed = []
    for i, item in enumerate(items):
        if not isinstance(item, list) or len(item) != width:
            raise DumpError(f"{what} item {i}: expected {width} fields")
        ident = item[0]
        if isinstance(ident, bool) or not isinstance(ident, int) or ident < 1:
            raise DumpError(f"{what} item {i}: id {ident!r} is not a Max index")
        parsed.append(item)
    return parsed


def validate_review(dump: dict) -> dict:
    """Fail closed on a #528 review JSON: partial lists, NaN, a saved file, a hash change, a dropped name."""
    if not isinstance(dump, dict):
        raise DumpError("review is not a JSON object")
    if dump.get("error"):
        raise DumpError(f"review error: {dump.get('error')}")
    if dump.get("dump_version") != 2:
        raise DumpError("dump_version must be 2")
    if dump.get("saved") is not False:
        raise DumpError(f"saved={dump.get('saved')!r}; a .max/.fbx load must not be saved")
    before, after = dump.get("sha256_before"), dump.get("sha256_after")
    if not isinstance(before, str) or not isinstance(after, str) or len(before) != 64 or len(after) != 64:
        raise DumpError("sha256_before / sha256_after missing")
    require_unchanged(before, after)
    _finite(dump.get("tolFaces"), "tolFaces")
    _finite(dump.get("tolVerts"), "tolVerts")
    if dump.get("tolFaces") <= 0 or dump.get("tolVerts") <= 0:
        raise DumpError("tolerance must be a finite number > 0")
    if not dump.get("node"):
        raise DumpError("no node measured")
    scene = dump.get("scene")
    dropped = dump.get("dropped")
    if not isinstance(scene, list) or not scene:
        raise DumpError("scene inventory missing")
    if not isinstance(dropped, list):
        raise DumpError("dropped list missing")
    scene_names = []
    for row in scene:
        if not isinstance(row, list) or len(row) < 1 or not isinstance(row[0], str):
            raise DumpError(f"scene row {row!r} is not [name, class, faces]")
        scene_names.append(row[0])
    if dump["node"] not in scene_names:
        raise DumpError(f"unmapped node {dump['node']!r}")
    dropped_names = []
    for row in dropped:
        if not isinstance(row, dict) or "name" not in row or "reason" not in row:
            raise DumpError(f"dropped row {row!r} needs name and reason")
        dropped_names.append(row["name"])
    if dump["node"] in dropped_names:
        raise DumpError(f"node {dump['node']!r} is both measured and dropped")
    missing = [name for name in scene_names if name != dump["node"] and name not in dropped_names]
    if missing:
        raise DumpError(f"not in output or dropped: {missing[0]}")
    verts = _items(dump.get("verticesCheck"), "verticesCheck", 2)
    faces = _items(dump.get("facesCheck"), "facesCheck", 4)
    for i, item in enumerate(verts):
        _xyz(item[1], f"vertex {item[0]}")
    for i, item in enumerate(faces):
        if isinstance(item[1], bool) or not isinstance(item[1], int):
            raise DumpError(f"face {item[0]}: material id {item[1]!r} is not an integer")
        _finite(item[2], f"face {item[0]} area")
        _xyz(item[3], f"face {item[0]}")
    return dump


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", type=Path, nargs="?")
    ap.add_argument("--keep", type=Path)
    ap.add_argument("--npz", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--validate-review", action="store_true")
    ap.add_argument("--check-run", type=Path, metavar="OUT")
    ap.add_argument("--labels", default="", help="comma-separated labels for --check-run")
    a = ap.parse_args(argv)
    if a.check_run:
        if a.dump or a.keep or a.npz or a.validate_review or a.out:
            print("give --check-run OUT --labels a,b", file=sys.stderr)
            return 2
        labels = [part.strip() for part in a.labels.split(",") if part.strip()]
        try:
            found = check_run(a.check_run, labels)
        except (DumpError, OSError) as e:
            print(f"xview_parity: {e}", file=sys.stderr)
            return 2
        print(json.dumps(found))
        return 0
    inputs = [x for x in (a.dump, a.keep, a.npz) if x]
    if a.validate_review:
        if not a.dump or a.keep or a.npz:
            print("give <review.json> --validate-review", file=sys.stderr)
            return 2
        if a.out and (a.out.resolve() == a.dump.resolve() or (a.out.exists() and os.path.samefile(a.out, a.dump))):
            print("--out must not be an input (same path, link or hardlink)", file=sys.stderr)
            return 2
        try:
            dump = validate_review(json.loads(a.dump.read_text(encoding="utf-8")))
        except (DumpError, ValueError, OSError) as e:
            print(f"xview_parity: {e}", file=sys.stderr)
            return 2
        if a.out:
            a.out.write_text(json.dumps(dump), encoding="utf-8")
        return 0
    if bool(a.dump) == bool(a.keep or a.npz) or bool(a.keep) != bool(a.npz):
        print("give either <dump.json> or both --keep and --npz", file=sys.stderr)
        return 2
    if a.out and any(a.out.resolve() == x.resolve() or (a.out.exists() and x.exists() and os.path.samefile(a.out, x))
                     for x in inputs):
        print("--out must not be an input (same path, link or hardlink)", file=sys.stderr)
        return 2
    try:
        if a.dump:
            rows = compare(json.loads(a.dump.read_text(encoding="utf-8")))
        else:
            raw = a.keep.read_bytes()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("cp1251")                     # Max writes the keep in the system code page
            with np.load(a.npz) as z:
                rows = compare_keep(json.loads(text), {k: z[k] for k in z.files})
    except (DumpError, ValueError, OSError) as e:
        print(f"xview_parity: {e}", file=sys.stderr)
        return 2
    text = json.dumps(rows, indent=1)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    for row in rows:
        print(json.dumps({k: (v if not isinstance(v, list) or len(v) <= 12 else v[:12] + ["..."]) for k, v in row.items()}))
    return 0 if all(r["equal"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
