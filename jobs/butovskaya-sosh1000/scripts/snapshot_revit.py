"""Step 0 of #118: a read-only snapshot of the Butovskaya school's envelope from the user's open Revit.

Only read-only commands of the in-Revit MCP add-in are sent (the command list comes from
hermes_kanban/scripts/revit_exec.py; anything else is refused before the call). The model is never
changed, synced or saved. The add-in's geometry read (`get_element_geometry`) returns the element's
axis-aligned bounding box, volume, surface area and face count - no tessellation - so the snapshot is one box
per element, plus the fill ratio volume / box volume that says how well the box stands for the element.

Output (git-ignored, outside the repo): <out>/elements.json (every element: id, category, type, function,
box in metres, volume, area, faces), <out>/levels.json, <out>/snapshot_dump.json (a mesh dump readable by
twinqa.geometry.mesh.from_dump: one box mesh per category, LEVEL_<name> helpers), <out>/hashes.json.

    python jobs/butovskaya-sosh1000/scripts/snapshot_revit.py --out C:/x/butovskaya-snapshot
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "C:/Users/artsafro/hermes_kanban/scripts")
import revit_exec as rx  # noqa: E402

FT = 0.3048
CARD = "t_20f3c6f7"
CATEGORIES = ["OST_Walls", "OST_CurtainWallPanels", "OST_CurtainWallMullions", "OST_Roofs", "OST_Floors",
              "OST_Windows", "OST_Doors"]
READ_ONLY, _ = rx.commands()


def call(cmd, params=None, timeout=120):
    if cmd not in READ_ONLY:
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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="C:/x/butovskaya-snapshot")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    doc = call("get_document_info")
    levels = call("list_levels")["levels"]
    elements, failed = [], []
    for cat in CATEGORIES:
        for e in listing(cat):
            try:
                g = call("get_element_geometry", {"id": e["id"]})
            except RuntimeError as err:
                failed.append({"id": e["id"], "category": cat, "error": str(err)[:200]})
                continue
            bb = g.get("boundingBox")
            f = e.get("fields", {})
            row = {"id": e["id"], "category": cat, "name": e.get("name"),
                   "type": f.get("Семейство и типоразмер_display"), "function": f.get("Функция_display"),
                   "solids": g.get("solidCount"), "faces": g.get("faceCount"),
                   "volume_m3": round((g.get("volumeCubicFeet") or 0) * FT ** 3, 6),
                   "area_m2": round((g.get("surfaceAreaSqFeet") or 0) * FT ** 2, 6), "box": None}
            if bb:
                lo = [round(bb["min"][k] * FT, 6) for k in "xyz"]
                hi = [round(bb["max"][k] * FT, 6) for k in "xyz"]
                row["box"] = [lo, hi]
            elements.append(row)
    secs = time.time() - t0
    meshes = []
    for cat in CATEGORIES:
        verts, tris = [], []
        for r in elements:
            if r["category"] != cat or not r["box"]:
                continue
            v, t = box_mesh(*r["box"])
            tris += [[i + len(verts) for i in tr] for tr in t]
            verts += v
        if tris:
            meshes.append({"name": cat, "vertices": verts, "triangles": tris,
                           "polygon_sizes": [3] * len(tris)})
    helpers = [{"name": f"LEVEL_{lv['name']}", "location": [0.0, 0.0, round(lv["elevationMeters"], 6)]} for lv in levels]
    (out / "elements.json").write_text(json.dumps({"document": doc, "elements": elements, "failed": failed,
                                                   "seconds": round(secs, 1)}, ensure_ascii=False, indent=0),
                                       encoding="utf-8")
    (out / "levels.json").write_text(json.dumps(levels, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "snapshot_dump.json").write_text(json.dumps({"meshes": meshes, "helpers": helpers}), encoding="utf-8")
    counts = {}
    for r in elements:
        counts[r["category"]] = counts.get(r["category"], 0) + 1
    hashes = {p: sha(out / p) for p in ("elements.json", "levels.json", "snapshot_dump.json")}
    (out / "hashes.json").write_text(json.dumps({"counts": counts, "failed": len(failed), "seconds": round(secs, 1),
                                                 "elements_per_s": round(len(elements) / max(secs, 1e-9), 1),
                                                 "sha256": hashes}, indent=1), encoding="utf-8")
    print(json.dumps({"counts": counts, "failed": len(failed), "seconds": round(secs, 1), "sha256": hashes}, indent=1))


if __name__ == "__main__":
    main()
