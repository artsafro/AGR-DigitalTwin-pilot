"""Metric and guard of the #118 autoresearch loop (fixed after step 0; the loop never edits this file).

Etalon: the step-0 snapshot (one box per Revit element of the envelope categories, scripts/snapshot_revit.py),
elements whose box lies outside the building zone left out (listed). Model: the dump of scripts/build_npm.py.

Metric `silhouette_err_m2` (lower is better): the mismatch area between model and etalon silhouettes in the five
orthographic views (four facades + top), the rule of twinqa.geometry.checks.check_silhouettes with its own
measure.silhouette, read as an area: area(model XOR etalon) per view. Facades are mirror pairs in an orthographic
projection (measure.VIEWS), so err = 2 * err_x + 2 * err_y + err_top.

Guard (keep only when every item holds), all with the repo's checkers, unchanged:
- check_mesh (whole model and every mesh alone, decor included): non-manifold edges 0, non-manifold vertices 0,
  open loops outside the allowed kinds 0, overlaps 0, n-gons 0 (tolerances of bench-b01-box, weld 3 mm);
- winding_bad_edges: 0 on every mesh;
- check_budget: triangles <= 150 000;
- check_levels: every snapshot level as LEVEL_<name> within 0.02 m;
- delivery_passed is always false (no delivery gate is judged here).
The non-DCC pytest suite is run at the baseline and at the end (the loop edits only build_npm.py, which no test
imports).

    uv run python jobs/butovskaya-sosh1000/scripts/evaluate.py --model C:/x/butovskaya-npm/model_dump.json
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import shapely

from twinqa.geometry import measure
from twinqa.geometry.checks import check_budget, check_levels, check_mesh, load_ranges, winding_bad_edges
from twinqa.geometry.mesh import Soup, from_dump

REPO = Path(__file__).resolve().parents[3]
SNAP = Path("C:/x/butovskaya-snapshot")
TOL_FILE = REPO / "benchmark" / "bench-b01-box" / "tolerances.json"
WELD_M = 0.003
LEVEL_TOL_M = 0.02
VIEWS = {"x": 2, "y": 2, "top": 1}       # view -> how many of the five views it stands for
# building zone (step 0, from the plan render): the school's body; boxes reaching past it are site pieces
ZONE = ((-67.0, -30.5), (60.0, 29.5))


def etalon_boxes(snap: Path = SNAP):
    rows = json.loads((snap / "elements.json").read_text(encoding="utf-8"))["elements"]
    (x0, y0), (x1, y1) = ZONE
    keep, dropped = [], []
    for r in rows:
        if not r["box"]:
            continue
        (a, b, _), (c, d, _) = r["box"]
        (keep if a >= x0 and b >= y0 and c <= x1 and d <= y1 else dropped).append(r)
    return keep, dropped


def boxes_soup(boxes) -> Soup:
    q = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tri = np.array([t for a, b, c, d in q for t in ((a, b, c), (a, c, d))])
    verts, tris = [], []
    for k, (lo, hi) in enumerate(boxes):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        verts.append([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                      [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]])
        tris.append(tri + 8 * k)
    v, t = np.concatenate(verts).astype(float), np.concatenate(tris)
    return Soup(v, t, np.zeros(len(t), int), None, {})


def etalon_silhouettes(snap: Path = SNAP):
    """Silhouettes of the etalon, cached next to the snapshot (keyed by the elements.json hash)."""
    h = hashlib.sha256((snap / "elements.json").read_bytes()).hexdigest()[:16]
    cache = snap / f"etalon_silhouettes_{h}.json"
    if cache.exists():
        d = json.loads(cache.read_text())
        return {v: shapely.from_wkb(bytes.fromhex(w)) for v, w in d.items()}
    keep, _ = etalon_boxes(snap)
    soup = boxes_soup([r["box"] for r in keep])
    sil = {v: measure.silhouette(soup.corners(), v) for v in VIEWS}
    cache.write_text(json.dumps({v: shapely.to_wkb(g).hex() for v, g in sil.items()}))
    return sil


def snapshot_levels(snap: Path = SNAP) -> dict:
    return {lv["name"]: float(lv["elevationMeters"]) for lv in json.loads((snap / "levels.json").read_text(encoding="utf-8"))}


def metric(model: Soup, sil: dict) -> dict:
    per = {}
    for v in VIEWS:
        m = measure.silhouette(model.corners(), v)
        per[v] = float(shapely.symmetric_difference(m, sil[v]).area)
    total = sum(VIEWS[v] * per[v] for v in VIEWS)
    return {"silhouette_err_m2": round(total, 3), "per_view_m2": {v: round(a, 3) for v, a in per.items()},
            "iou": {v: round(measure.iou(measure.silhouette(model.corners(), v), sil[v]), 4) for v in VIEWS}}


def guard(model: Soup, snap: Path = SNAP) -> dict:
    tol = {**json.loads(TOL_FILE.read_text(encoding="utf-8"))["geometry"], "weld_m": WELD_M}
    ranges = load_ranges()
    meshes = {}
    whole = check_mesh(model, tol, ranges)
    for i, name in enumerate(model.mesh_names):
        keep = model.mesh_index == i
        if keep.all():                      # the only mesh is the whole model: same check, same result
            meshes[name] = {"status": whole["status"], "value": whole["value"]}
            continue
        sizes = None
        if model.polygon_sizes is not None and (model.polygon_sizes == 3).all():
            sizes = model.polygon_sizes[keep]
        sub = Soup(model.vertices, model.triangles[keep], model.material_ids[keep], sizes, model.levels, 0,
                   (name,), np.zeros(int(keep.sum()), int))
        r = check_mesh(sub, tol, ranges)
        meshes[name] = {"status": r["status"], "value": r["value"]}
    wind = winding_bad_edges(model, WELD_M)
    budget = check_budget(model, tol)
    ref = snapshot_levels(snap)
    etalon = Soup(np.zeros((0, 3)), np.zeros((0, 3), int), np.zeros(0, int), None, ref)
    levels = check_levels(model, etalon, None, {"level_elev_m": LEVEL_TOL_M})
    ok = (whole["status"] == "pass" and all(m["status"] == "pass" for m in meshes.values())
          and int(wind.sum()) == 0 and budget["status"] == "pass" and levels["status"] == "pass")
    return {"guard_passed": ok, "delivery_passed": False,
            "mesh": {"status": whole["status"], "value": whole["value"],
                     "open_loops_other": [lp for lp in whole["details"].get("open_loops", []) if not lp["allowed"]][:5]},
            "mesh_per_mesh": meshes, "winding_bad_edges": dict(zip(model.mesh_names, wind.tolist())),
            "triangles": budget["value"], "budget_status": budget["status"],
            "levels": {"status": levels["status"], "worst_m": levels["value"],
                       "missing": levels["details"]["missing_in_model"]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="C:/x/butovskaya-npm/model_dump.json")
    ap.add_argument("--out")
    a = ap.parse_args()
    t = time.time()
    sil = etalon_silhouettes()
    model = from_dump(json.loads(Path(a.model).read_text(encoding="utf-8")))
    res = {**metric(model, sil), **guard(model), "seconds": None}
    res["seconds"] = round(time.time() - t, 1)
    text = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    print(f"silhouette_err_m2={res['silhouette_err_m2']} guard_passed={res['guard_passed']}")
    return 0 if res["guard_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
