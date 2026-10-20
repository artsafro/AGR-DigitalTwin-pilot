"""Compare 3ds Max xView OverlappingVertices / OverlappingFaces results with dt_ai.ops.inv_xview (#370).

Input: the JSON written by `tools/qa/xview_dump.ms` (headless Max via dcc_batch.py on a COPY of an FBX):
per node the Max result ids (1-based), vertices in metres and faces (1-based vertex ids).
Output: one JSON line per node with counts on both sides and every id that differs.

  uv run python tools/qa/xview_parity.py <dump.json> [--out parity.json]

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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dump", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    if a.out and (a.out.resolve() == a.dump.resolve() or (a.out.exists() and os.path.samefile(a.out, a.dump))):
        print("--out must not be the input dump (same path, link or hardlink)", file=sys.stderr)
        return 2
    try:
        rows = compare(json.loads(a.dump.read_text(encoding="utf-8")))
    except (DumpError, ValueError) as e:
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
