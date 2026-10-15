"""Step 0 of #118, mesh route: the Butovskaya school's element meshes from the TwinPack export of the open Revit.

User decision 2026-10-15 (option a, agent exports via MCP): the reference is the TwinPack export of the revit-http
add-in, `node tools/source/measure_spec_revit_twin.mjs <new folder>` (docs/agents/CAPABILITIES.md, "Revit path,
wall lines"). It writes per storey band `band-<n>/reference.obj` (the real tessellated geometry of every element
of the band, clipped to the band, objects `<kind>_<revitId>`) + `floor.json`, and `twin-data.json` (bands, the
document's levels and roofs, the document's modified flag before and after). The model is never changed, synced
or saved; `--export` runs that script once under the Revit lock of hermes_kanban/scripts/revit_exec.py.

This script turns such an export into the snapshot the loop reads (same layout as scripts/snapshot_revit.py, so
scripts/evaluate.py takes it unchanged): <out>/elements.json (one row per band piece of an element: id, kind,
category, band, type, function, box in metres from its mesh, triangles), <out>/levels.json, <out>/snapshot_dump.json
(one mesh per piece `band-<n>/<kind>_<id>`, LEVEL_<name> helpers), <out>/hashes.json (reference "mesh", complete
true, counts, sha256 of the snapshot files and of every source file).

Fail closed (review round 1, P1-1): the snapshot is published only when the export is complete and the document
stayed unmodified. Any of these writes only <out>/blocked.json and exits 2, with no snapshot file next to it:
no twin-data.json, a document modified before or after, no band, no level, a band without reference.obj or
floor.json, an OBJ face that is not a triangle of valid 1-based vertex indices, an object without a triangle, a
band whose triangle count differs from its floor.json, clip fallbacks. Files are staged in <out>.partial and moved
in place hashes.json last. Step 0 runs once: an <out> that already holds hashes.json is refused.

    uv run python jobs/butovskaya-sosh1000/scripts/snapshot_twin.py --src C:/x/butovskaya/twin-v001 \
        --out C:/x/butovskaya-snapshot-twin [--export]
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
CARD = "t_20f3c6f7"
BLOCKED_EXIT = 2
FILES = ("elements.json", "levels.json", "snapshot_dump.json")
KIND_CATEGORY = {"wall": "OST_Walls", "panel": "OST_CurtainWallPanels", "mullion": "OST_CurtainWallMullions",
                 "roof": "OST_Roofs", "floor": "OST_Floors", "window": "OST_Windows", "door": "OST_Doors",
                 "cornice": "OST_Cornices"}
RECORDS = ("walls", "openings", "curtainPanels", "mullions", "slabs", "others")


class Blocked(Exception):
    def __init__(self, reason, detail):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_obj(path: Path):
    """[(object name, vertices (n, 3) float, triangles (m, 3) int local)] of a TwinPack reference.obj.

    Blocked on a face that is not a triangle of positive in-range indices, a face before any object, or an object
    without a face."""
    verts, objects, cur = [], [], None
    for ln, line in enumerate(path.open(encoding="utf-8"), 1):
        if line.startswith("v "):
            p = line.split()
            if len(p) != 4:
                raise Blocked("malformed_obj", f"{path}:{ln}: vertex is not 3D")
            verts.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("o "):
            cur = [line[2:].strip(), []]
            objects.append(cur)
        elif line.startswith("f "):
            p = line.split()[1:]
            if cur is None:
                raise Blocked("malformed_obj", f"{path}:{ln}: face before any object")
            try:
                idx = [int(q.split("/")[0]) for q in p]
            except ValueError:
                raise Blocked("malformed_obj", f"{path}:{ln}: face index is not an integer") from None
            if len(idx) != 3:
                raise Blocked("malformed_obj", f"{path}:{ln}: face with {len(idx)} corners, not a triangle")
            cur[1].append(idx)
    v = np.asarray(verts, float).reshape(-1, 3)
    out = []
    for name, faces in objects:
        if not faces:
            raise Blocked("empty_object", f"{path}: object {name} has no triangle")
        f = np.asarray(faces, int)
        if f.min() < 1 or f.max() > len(v):
            raise Blocked("malformed_obj", f"{path}: object {name} has a vertex index out of 1..{len(v)}")
        used, local = np.unique(f - 1, return_inverse=True)
        out.append((name, v[used], local.reshape(-1, 3)))
    return out


def records(floor: dict) -> dict:
    """revit id -> its record of floor.json (type, function, category)."""
    out = {}
    for key in RECORDS:
        for r in floor.get(key) or []:
            out[(r.get("kind"), r.get("id"))] = r
    return out


def acquire(src: Path, state):
    tf = src / "twin-data.json"
    if not tf.exists():
        raise Blocked("no_export", f"{tf} is missing (the TwinPack export did not run or did not finish)")
    twin = json.loads(tf.read_text(encoding="utf-8"))
    state["twin"] = twin
    if twin.get("modified_before") is not False or twin.get("modified_after") is not False:
        raise Blocked("document_modified", f"modified before {twin.get('modified_before')!r}, "
                                           f"after {twin.get('modified_after')!r}; must be false, false")
    levels = twin.get("revit_levels") or []
    if not levels:
        raise Blocked("no_levels", "twin-data.json holds no revit_levels")
    state["levels"] = [{"name": lv["name"], "elevationMeters": round(float(lv["elevation_m"]), 6), "id": lv["id"]}
                       for lv in levels]
    bands = twin.get("bands") or []
    if not bands:
        raise Blocked("no_bands", "twin-data.json holds no band")
    state["sources"]["twin-data.json"] = sha(tf)
    for b in bands:
        d = src / b["dir"]
        obj, fj = d / "reference.obj", d / "floor.json"
        if not obj.exists() or not fj.exists():
            raise Blocked("band_incomplete", f"band {b['band']}: reference.obj or floor.json is missing in {d}")
        floor = json.loads(fj.read_text(encoding="utf-8"))
        rec = records(floor)
        pieces = read_obj(obj)
        tris = sum(len(t) for _, _, t in pieces)
        mesh = floor.get("mesh") or {}
        if mesh.get("triangles") != tris:
            raise Blocked("band_incomplete", f"band {b['band']}: {tris} triangles in reference.obj, "
                                             f"floor.json says {mesh.get('triangles')}")
        if mesh.get("clipFallbacks"):
            raise Blocked("clip_fallback", f"band {b['band']}: {mesh['clipFallbacks']} clip fallbacks")
        state["sources"][f"{b['dir']}/reference.obj"] = sha(obj)
        state["sources"][f"{b['dir']}/floor.json"] = sha(fj)
        for name, v, t in pieces:
            kind, _, rid = name.partition("_")
            r = rec.get((kind, int(rid))) if rid.isdigit() else None
            state["pieces"].append({
                "id": int(rid) if rid.isdigit() else rid, "kind": kind,
                "category": KIND_CATEGORY.get(kind, f"other:{kind}"), "band": b["band"],
                "name": f"band-{b['band']}/{name}", "type": (r or {}).get("type"),
                "function": (r or {}).get("function"), "triangles": int(len(t)),
                "box": [v.min(0).round(6).tolist(), v.max(0).round(6).tolist()],
                "mesh": (v.round(6), t)})


def write(stage: Path, state, src: Path, secs):
    pieces, levels = state["pieces"], state["levels"]
    meshes = [{"name": p["name"], "vertices": p["mesh"][0].tolist(), "triangles": p["mesh"][1].tolist(),
               "polygon_sizes": [3] * len(p["mesh"][1])} for p in pieces]
    rows = [{k: v for k, v in p.items() if k != "mesh"} for p in pieces]
    helpers = [{"name": f"LEVEL_{lv['name']}", "location": [0.0, 0.0, lv["elevationMeters"]]} for lv in levels]
    twin = state["twin"]
    doc = {"title": twin.get("document"), "path": twin.get("path"), "modified_before": twin.get("modified_before"),
           "modified_after": twin.get("modified_after")}
    (stage / "elements.json").write_text(json.dumps({"document": doc, "source": str(src), "elements": rows,
                                                     "failed": []}, ensure_ascii=False, indent=0), encoding="utf-8")
    (stage / "levels.json").write_text(json.dumps(levels, ensure_ascii=False, indent=1), encoding="utf-8")
    (stage / "snapshot_dump.json").write_text(json.dumps({"meshes": meshes, "helpers": helpers}), encoding="utf-8")
    counts, elements, tris = {}, {}, {}
    for p in pieces:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
        elements.setdefault(p["category"], set()).add(p["id"])
        tris[p["category"]] = tris.get(p["category"], 0) + p["triangles"]
    summary = {"reference": "mesh", "route": "twinpack", "complete": True, "failed": 0,
               "counts": counts, "elements": {k: len(v) for k, v in elements.items()}, "triangles": tris,
               "pieces": len(pieces), "triangles_total": sum(tris.values()), "bands": len(twin["bands"]),
               "seconds": round(secs, 1), "sha256": {p: sha(stage / p) for p in FILES},
               "source_sha256": state["sources"]}
    (stage / "hashes.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def export(src: Path):
    """Run the TwinPack export once into the new folder src, under the Revit lock of revit_exec.py."""
    sys.path.insert(0, "C:/Users/artsafro/hermes_kanban/scripts")
    import revit_exec as rx
    if src.exists():
        raise SystemExit(f"refused: {src} exists; the export writes only into a new folder")
    if not rx._lock(CARD, 3600):
        raise SystemExit("Revit busy (lock held by another card)")
    try:
        r = subprocess.run(["node", str(REPO / "tools/source/measure_spec_revit_twin.mjs"), str(src)])
    finally:
        rx._unlock(CARD)
    if r.returncode:
        raise SystemExit(f"export failed with code {r.returncode}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="C:/x/butovskaya/twin-v001")
    ap.add_argument("--out", default="C:/x/butovskaya-snapshot-twin")
    ap.add_argument("--export", action="store_true", help="run the TwinPack export into --src first")
    a = ap.parse_args(argv)
    src, out = Path(a.src), Path(a.out)
    if (out / "hashes.json").exists():
        print(f"refused: {out} already holds a snapshot (step 0 runs once)", file=sys.stderr)
        raise SystemExit(BLOCKED_EXIT)
    t0 = time.time()
    if a.export:
        export(src)
    stage = out.with_name(out.name + ".partial")
    shutil.rmtree(stage, ignore_errors=True)
    state = {"twin": None, "levels": [], "pieces": [], "sources": {}}
    try:
        acquire(src, state)
    except Blocked as b:
        rep = {"complete": False, "reason": b.reason, "detail": b.detail, "source": str(src),
               "pieces_read": len(state["pieces"]), "seconds": round(time.time() - t0, 1)}
        out.mkdir(parents=True, exist_ok=True)
        for name in FILES:                      # never leave consumable snapshot files next to a blocked report
            (out / name).unlink(missing_ok=True)
        (out / "blocked.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        print(f"BLOCKED: {b}", file=sys.stderr)
        raise SystemExit(BLOCKED_EXIT) from None
    stage.mkdir(parents=True)
    summary = write(stage, state, src, time.time() - t0)
    out.mkdir(parents=True, exist_ok=True)
    (out / "blocked.json").unlink(missing_ok=True)
    for name in (*FILES, "hashes.json"):         # hashes.json last: it is what marks the snapshot complete
        (stage / name).replace(out / name)
    shutil.rmtree(stage, ignore_errors=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "source_sha256"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
