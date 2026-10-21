"""Compare 3ds Max xView OverlappingVertices / OverlappingFaces results with dt_ai.ops.inv_xview (#370).

Input: the JSON written by `tools/qa/xview_dump.ms` (headless Max via dcc_batch.py on a COPY of an FBX):
per node the Max result ids (1-based), vertices in metres and faces (1-based vertex ids).
Output: one JSON line per node with counts on both sides and every id that differs.

  uv run python tools/qa/xview_parity.py <dump.json> [--out parity.json]
  uv run python tools/qa/xview_parity.py --keep <xview_check.keep> --npz <arrays.npz> [--out parity.json]

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
import json
import math
import os
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
    v = np.asarray(arrays["vertices"], dtype=float)
    st, tot, lv = (np.asarray(arrays[k]) for k in ("loop_start", "loop_total", "loop_vert"))
    nv, nf = len(v), len(tot)
    if not nv or not nf or len(st) != nf:
        raise DumpError("arrays: no vertices or no faces, or loop_start / loop_total lengths differ")
    if keep.get("faces") != nf or keep.get("verts") != nv:
        raise DumpError(f"keep has {keep.get('faces')} faces / {keep.get('verts')} verts, arrays {nf} / {nv}: "
                        "not the same mesh")
    tol = XviewTolerance(vertex_m=_num(keep, "tolVerts"), face_m=_num(keep, "tolFaces")).validate()
    mf = {_int(i[0] if isinstance(i, list) else i, "facesCheck item", 1, nf) for i in checks["facesCheck"]["items"]}
    mv = {_int(i[0] if isinstance(i, list) else i, "verticesCheck item", 1, nv)
          for i in checks["verticesCheck"]["items"]}
    try:
        faces = tuple(tuple(int(x) for x in lv[s:s + t]) for s, t in zip(st, tot))
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", type=Path, nargs="?")
    ap.add_argument("--keep", type=Path)
    ap.add_argument("--npz", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    inputs = [x for x in (a.dump, a.keep, a.npz) if x]
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
