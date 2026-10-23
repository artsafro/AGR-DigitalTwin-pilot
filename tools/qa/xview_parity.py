"""Compare 3ds Max xView OverlappingVertices / OverlappingFaces results with dt_ai.ops.inv_xview (#370).

Input: the JSON written by `tools/qa/xview_dump.ms` (headless Max via dcc_batch.py on a COPY of an FBX):
per node the Max result ids (1-based), vertices in metres and faces (1-based vertex ids).
Output: one JSON line per node with counts on both sides and every id that differs.

  uv run python tools/qa/xview_parity.py <dump.json> [--out parity.json]
  uv run python tools/qa/xview_parity.py --keep <xview_check.keep> --npz <arrays.npz> [--out parity.json]
  uv run python tools/qa/xview_parity.py <review.json> --validate-review [--out copy.json]

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


def prepare_run(jobs, out_dir, temp_dir, scene=None) -> dict:
    """Stage inputs and write an ASCII jobs.txt. Refuses before any write when a path, key or mode is wrong."""
    if not isinstance(jobs, list) or not jobs:
        raise DumpError("no inputs")
    out_dir, temp_dir = Path(out_dir), Path(temp_dir)
    staged_jobs = []
    outputs = []
    for job in jobs:
        if not isinstance(job, dict):
            raise DumpError("job is not an object")
        unknown = sorted(set(job) - _JOB_KEYS)
        if unknown:
            raise DumpError(f"unmapped key {unknown[0]!r}")
        mode = job.get("mode", "") or ""
        if mode not in _MODES:
            raise DumpError(f"unmapped mode {mode!r}")
        label = str(job.get("label", ""))
        if not label or label != Path(label).name or not _ascii_path(Path(label)):
            raise DumpError(f"unmapped label {label!r}")
        src = Path(job.get("path", ""))
        if src.suffix.lower() not in _MESH_SUFFIXES:
            raise DumpError(f"unsupported input {src.name!r}")
        if not src.is_file():
            raise DumpError(f"input missing: {src}")
        out_file = out_dir / f"{label}.json"
        report = out_dir / "report.jsonl"
        require_distinct({"input": src, "output": out_file, "report": report})
        if scene is not None:
            select_node(scene, job.get("node") or "", job.get("material"), None if "material" not in job else [],
                        job.get("slot"), None)
        staged_jobs.append((job, src, out_file))
        outputs.append(out_file)
    # writes happen only after every job has been accepted
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    staged = []
    for job, src, out_file in staged_jobs:
        opened = stage_input(src, temp_dir)
        digest = sha256_file(src)
        if sha256_file(opened) != digest:
            raise DumpError(f"SHA-256 mismatch for {src}")
        node = job.get("node") or ""
        mode = job.get("mode") or ""
        material = job.get("material") or ""
        slot = job.get("slot") or ""
        lines.append("|".join([job["label"], str(opened), node, mode, material, slot]))
        staged.append({"label": job["label"], "source": str(src), "opened": str(opened), "sha256": digest,
                       "output": str(out_file)})
    jobs_file = out_dir / "jobs.txt"
    report = out_dir / "report.jsonl"
    for row in staged:
        roles = {"input": Path(row["source"]), "output": Path(row["output"]), "report": report}
        opened = Path(row["opened"])
        if opened.resolve() != Path(row["source"]).resolve():
            roles["temp"] = opened
        require_distinct(roles)
    jobs_file.write_text("\n".join(lines) + "\n", encoding="ascii")
    return {"jobs_file": jobs_file, "staged": staged, "outputs": outputs, "report": report}


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
    a = ap.parse_args(argv)
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
