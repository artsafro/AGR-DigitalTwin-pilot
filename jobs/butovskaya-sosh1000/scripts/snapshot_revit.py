"""Step 0 of #118: a read-only snapshot of the Butovskaya school's envelope from the user's open Revit.

Only read-only commands of the in-Revit MCP add-in are sent (the command list comes from
hermes_kanban/scripts/revit_exec.py; anything else is refused before the call). The model is never
changed, synced or saved.

Fail closed (review round 1, P1-1). The program needs element MESHES; the snapshot is written only when every
listed element returns a tessellated mesh (`mesh: {vertices (feet), triangles}`) in its geometry read. The run
stops at the first element that does not (a bounding-box-only answer, a malformed mesh, a failed call), and
also on an empty listing or no levels: it then writes only <out>/blocked.json (reason, elements done / listed,
seconds, elements/s, the failure) and exits with code 2. No elements.json, snapshot_dump.json or hashes.json
is published, so the loop has nothing to consume. Files are staged in <out>.partial and moved in place only
after success, hashes.json last. Step 0 runs once: an <out> that already holds hashes.json is refused before
any Revit call.

The add-in of 2026-10-15 answers `get_element_geometry` with a bounding box, volume, area and face count only,
so against it this script blocks (reason unsupported_export). The box snapshot of the first attempt is kept
only as non-conforming exploration (docs/experiments/autoresearch-butovskaya-npm.md).

Output (git-ignored, outside the repo): <out>/elements.json (every element: id, category, type, function,
box in metres from its mesh, volume, area, faces), <out>/levels.json, <out>/snapshot_dump.json (a mesh dump
readable by twinqa.geometry.mesh.from_dump: one mesh per element `<category>/<id>`, LEVEL_<name> helpers),
<out>/hashes.json (reference "mesh", complete true, counts, sha256).

    python jobs/butovskaya-sosh1000/scripts/snapshot_revit.py --out C:/x/butovskaya-snapshot-mesh
"""
import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, "C:/Users/artsafro/hermes_kanban/scripts")
try:
    import revit_exec as rx  # noqa: E402
    READ_ONLY, _ = rx.commands()
except ImportError:              # no add-in client on this machine: every call is refused
    rx, READ_ONLY = None, set()

FT = 0.3048
CARD = "t_20f3c6f7"
CATEGORIES = ["OST_Walls", "OST_CurtainWallPanels", "OST_CurtainWallMullions", "OST_Roofs", "OST_Floors",
              "OST_Windows", "OST_Doors"]
BLOCKED_EXIT = 2
FILES = ("elements.json", "levels.json", "snapshot_dump.json")


class Blocked(Exception):
    def __init__(self, reason, detail):
        super().__init__(f"{reason}: {detail}")
        self.reason, self.detail = reason, detail


def call(cmd, params=None, timeout=120):
    if rx is None or cmd not in READ_ONLY:
        raise SystemExit(f"refused: {cmd} is not a read-only command")
    if not rx._lock(CARD, timeout):
        raise RuntimeError("Revit busy (lock held by another card)")
    try:
        code, data = rx.http("POST", "/mcp", {"command": cmd, "params": params or {}}, timeout)
    finally:
        rx._unlock(CARD)
    if code != 200 or not data.get("ok", True):
        raise RuntimeError(f"{cmd}: http {code} {str(data)[:300]}")
    return data.get("data", data)


def listing(cat):
    out, off = [], 0
    while True:
        d = call("find_elements", {"category": cat, "limit": 2000, "offset": off,
                                   "fields": ["Функция", "Семейство и типоразмер"]})
        out += d["elements"]
        if not d.get("hasMore"):
            return out
        off = d["nextOffset"]


def box_mesh(lo, hi):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]   # outward
    t = [tri for a, b, c, d in q for tri in ((a, b, c), (a, c, d))]
    return v, t


def element_mesh(g):
    """(vertices in metres, triangles) of a geometry answer; Blocked unless it holds a valid tessellation."""
    m = g.get("mesh") if isinstance(g, dict) else None
    if not isinstance(m, dict):
        keys = sorted(g) if isinstance(g, dict) else type(g).__name__
        raise Blocked("unsupported_export", f"no tessellated mesh in the geometry answer (keys {keys})")
    try:
        verts = [[round(float(c) * FT, 6) for c in p] for p in m.get("vertices")]
        tris = [[int(i) for i in tr] for tr in m.get("triangles")]
    except (TypeError, ValueError) as err:
        raise Blocked("unsupported_export", f"malformed mesh: {err}") from None
    if not verts or not tris or any(len(p) != 3 for p in verts) or any(len(tr) != 3 for tr in tris) \
            or any(i < 0 or i >= len(verts) for tr in tris for i in tr):
        raise Blocked("unsupported_export", "malformed mesh: empty, not 3D, not triangles or index out of range")
    return verts, tris


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def acquire(state):
    """Every listed element with its mesh, or Blocked at the first one that cannot be read."""
    state["document"] = call("get_document_info")
    levels = call("list_levels").get("levels") or []
    if not levels:
        raise Blocked("no_levels", "list_levels returned no level")
    state["levels"] = levels
    todo = [(cat, e) for cat in CATEGORIES for e in listing(cat)]
    state["listed"] = len(todo)
    if not todo:
        raise Blocked("no_elements", f"no element in {CATEGORIES}")
    for cat, e in todo:
        try:
            g = call("get_element_geometry", {"id": e["id"]})
        except RuntimeError as err:
            state["failed"].append({"id": e["id"], "category": cat, "error": str(err)[:200]})
            raise Blocked("geometry_failed", f"element {e['id']}: {str(err)[:200]}") from None
        try:
            verts, tris = element_mesh(g)
        except Blocked as b:
            state["failed"].append({"id": e["id"], "category": cat, "error": b.detail[:200]})
            raise
        f = e.get("fields", {})
        lo = [min(p[k] for p in verts) for k in range(3)]
        hi = [max(p[k] for p in verts) for k in range(3)]
        state["elements"].append({
            "id": e["id"], "category": cat, "name": e.get("name"),
            "type": f.get("Семейство и типоразмер_display"), "function": f.get("Функция_display"),
            "solids": g.get("solidCount"), "faces": g.get("faceCount"),
            "volume_m3": round((g.get("volumeCubicFeet") or 0) * FT ** 3, 6),
            "area_m2": round((g.get("surfaceAreaSqFeet") or 0) * FT ** 2, 6), "box": [lo, hi],
            "mesh": {"vertices": verts, "triangles": tris}})


def write(stage: Path, state, secs):
    elements, levels = state["elements"], state["levels"]
    meshes = [{"name": f"{r['category']}/{r['id']}", "vertices": r["mesh"]["vertices"],
               "triangles": r["mesh"]["triangles"], "polygon_sizes": [3] * len(r["mesh"]["triangles"])}
              for r in elements]
    rows = [{k: v for k, v in r.items() if k != "mesh"} for r in elements]
    helpers = [{"name": f"LEVEL_{lv['name']}", "location": [0.0, 0.0, round(lv["elevationMeters"], 6)]} for lv in levels]
    (stage / "elements.json").write_text(json.dumps({"document": state["document"], "elements": rows, "failed": [],
                                                     "seconds": round(secs, 1)}, ensure_ascii=False, indent=0),
                                         encoding="utf-8")
    (stage / "levels.json").write_text(json.dumps(levels, ensure_ascii=False, indent=1), encoding="utf-8")
    (stage / "snapshot_dump.json").write_text(json.dumps({"meshes": meshes, "helpers": helpers}), encoding="utf-8")
    counts = {}
    for r in elements:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    summary = {"reference": "mesh", "complete": True, "counts": counts, "failed": 0, "seconds": round(secs, 1),
               "elements_per_s": round(len(elements) / max(secs, 1e-9), 1),
               "pieces": len(meshes), "triangles_total": sum(len(m["triangles"]) for m in meshes),
               "sha256": {p: sha(stage / p) for p in FILES}}
    (stage / "hashes.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C:/x/butovskaya-snapshot-mesh")
    a = ap.parse_args()
    out = Path(a.out)
    if (out / "hashes.json").exists():
        print(f"refused: {out} already holds a snapshot (step 0 runs once)", file=sys.stderr)
        raise SystemExit(BLOCKED_EXIT)
    stage = out.with_name(out.name + ".partial")
    shutil.rmtree(stage, ignore_errors=True)
    t0 = time.time()
    state = {"document": None, "levels": [], "listed": 0, "elements": [], "failed": []}
    try:
        acquire(state)
    except Blocked as b:
        secs = time.time() - t0
        done = len(state["elements"])
        rep = {"complete": False, "reason": b.reason, "detail": b.detail, "elements_done": done,
               "elements_listed": state["listed"], "seconds": round(secs, 1),
               "elements_per_s": round(done / max(secs, 1e-9), 1), "failed": state["failed"]}
        out.mkdir(parents=True, exist_ok=True)
        for name in FILES:                      # never leave consumable snapshot files next to a blocked report
            (out / name).unlink(missing_ok=True)
        (out / "blocked.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        print(f"BLOCKED: {b}", file=sys.stderr)
        raise SystemExit(BLOCKED_EXIT) from None
    secs = time.time() - t0
    stage.mkdir(parents=True)
    summary = write(stage, state, secs)
    out.mkdir(parents=True, exist_ok=True)
    (out / "blocked.json").unlink(missing_ok=True)
    for name in (*FILES, "hashes.json"):     # hashes.json last: it is what marks the snapshot complete
        (stage / name).replace(out / name)
    shutil.rmtree(stage, ignore_errors=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
