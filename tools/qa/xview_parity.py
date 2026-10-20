"""Compare 3ds Max xView OverlappingVertices / OverlappingFaces results with dt_ai.ops.inv_xview (#370).

Input: the JSON written by `tools/qa/xview_dump.ms` (headless Max via dcc_batch.py on a COPY of an FBX):
per node the Max result ids (1-based), vertices in metres and faces (1-based vertex ids).
Output: one JSON line per node with counts on both sides and every id that differs.

  uv run python tools/qa/xview_parity.py <dump.json> [--out parity.json]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

from dt_ai.ops.inv_quads import PolyMesh
from dt_ai.ops.inv_xview import XviewTolerance, part_report


def compare(dump: dict) -> list[dict]:
    rows = []
    tol = XviewTolerance(vertex_m=float(dump["tol_v_units"]) * float(dump["m_per_unit"]),
                         face_m=float(dump["tol_f_units"]) * float(dump["m_per_unit"])).validate()
    for node in dump["nodes"]:
        mesh = PolyMesh(np.asarray(node["vertices"], dtype=float), tuple(tuple(i - 1 for i in f) for f in node["faces"]))
        r = part_report(node["name"], mesh, tol)
        mv, mf = set(node["overlap_vertices"]), set(node["overlap_faces"])
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
    if a.out and a.out.resolve() == a.dump.resolve():
        print("--out must not be the input dump", file=sys.stderr)
        return 2
    rows = compare(json.loads(a.dump.read_text(encoding="utf-8")))
    text = json.dumps(rows, indent=1)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    for row in rows:
        print(json.dumps({k: (v if not isinstance(v, list) or len(v) <= 12 else v[:12] + ["..."]) for k, v in row.items()}))
    return 0 if all(r["equal"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
