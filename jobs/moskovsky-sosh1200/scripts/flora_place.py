"""Job-local Flora placement input + run for moskovsky-sosh1200 (model-flora step 8 via dt_ai.placement.engine).

Pattern: n/a | new-case: A101 library objects (FLORIO_221.max, unchanged size) on SPOZU points and a seeded
scatter over bed / hedge polygons at the ledger rate. Only positions whose `status` is `place` are used; the
rest wait for the user's answer (flora_plan.json). Size: schedule band = the A101 model's own size (TASK
decision 8: unchanged size), D100 jitter +-10 % and random Z rotation by the engine.
Run: uv run python jobs/moskovsky-sosh1200/scripts/flora_place.py PLAN.json POINTS.json A101_DUMP.json GROUND.obj OUT_DIR
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

import dt_ai.placement.engine as engine
from dt_ai.placement.engine import place, report_json

SEED = 1200


def load_obj(path):
    V, T = [], []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            V.append([float(c) for c in line.split()[1:4]])
        elif line.startswith("f "):
            idx = [int(c.split("/")[0]) - 1 for c in line.split()[1:]]
            T += [[idx[0], idx[k], idx[k + 1]] for k in range(1, len(idx) - 1)]
    return V, T


def scatter(poly, n, key, min_d):
    """Seeded dart throwing: n points inside poly, pairwise >= min_d when possible (relaxed 10 % per 2000 misses)."""
    rng = np.random.default_rng(int(hashlib.sha256(f"{SEED}:{key}".encode()).hexdigest()[:12], 16))
    x0, y0, x1, y1 = poly.bounds
    pts, miss, d = [], 0, min_d
    while len(pts) < n:
        p = (rng.uniform(x0, x1), rng.uniform(y0, y1))
        if poly.contains(Point(p)) and all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= d * d for q in pts[-400:]):
            pts.append(p)
            miss = 0
        else:
            miss += 1
            if miss > 2000:
                d *= 0.9
                miss = 0
    return pts


def main(plan_p, points_p, dump_p, obj_p, out_dir):
    plan = json.loads(Path(plan_p).read_text(encoding="utf-8"))
    pts = json.loads(Path(points_p).read_text(encoding="utf-8"))
    dump = {o["name"]: o for o in json.loads(Path(dump_p).read_text(encoding="utf-8"))["objects"]}
    ox, oy = pts["origin_xy"]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    library, points, scat = [], [], []
    for row in plan["positions"]:
        if row.get("status") != "place":
            continue
        obj = row["a101_object"]
        o = dump[obj]
        piv = o["pivot"]
        lo = [o["bbmin"][k] - piv[k] for k in range(3)]
        hi = [o["bbmax"][k] - piv[k] for k in range(3)]
        lid = f"pos{row['pos']}_{obj}"
        library.append({"id": lid, "kind": "flora", "bbox_min": lo, "bbox_max": hi,
                        "schedule_height_m": hi[2] - lo[2], "schedule_crown_m": max(hi[0] - lo[0], hi[1] - lo[1])})
        if row["kind"] == "point":
            for p in pts["points"]:
                if p["pos"] == row["pos"] and p["inside"]:
                    points.append({"handle": p["handle"], "label": lid, "x": p["x"] - ox, "y": p["y"] - oy, "z": 0.0,
                                   "rotation": 0.0, "inside": True, "position": row["pos"]})
        else:
            rate = row["rate_per_m2"]
            for b in pts["beds"]:
                if b["pos"] != row["pos"]:
                    continue
                for k, g in enumerate(b["polygons_in_gpzu"]):
                    poly = Polygon([(x - ox, y - oy) for x, y in g["exterior"]],
                                   [[(x - ox, y - oy) for x, y in h] for h in g["holes"]])
                    n = max(1, round(poly.area * rate))
                    xy = scatter(poly, n, f"{b['handle']}:{k}", 0.8 / math.sqrt(rate))
                    scat.append({"bed": b["handle"], "part": k, "pos": row["pos"], "area_m2": round(poly.area, 2),
                                 "rate_per_m2": rate, "n": n})
                    for i, (x, y) in enumerate(xy):
                        points.append({"handle": f"{b['handle']}.{k}.{i}", "label": lid, "x": x, "y": y, "z": 0.0,
                                       "rotation": 0.0, "inside": True, "position": row["pos"]})
    V, T = load_obj(obj_p)
    inp = {"seed": SEED, "points": points, "library": library, "ground": {"vertices": V, "triangles": T}}
    (out / "placement_input.json").write_text(json.dumps(inp), encoding="utf-8")
    if plan.get("scale_rule", {}).get("jitter") == 0.0:
        engine.SCALE_JITTER = 0.0  # user deviation from D100 for this job (2026-11-26): scale exactly 1.0
    rep = place(points, V, T, library, SEED)
    rep["job_scatter"] = scat
    (out / "placement_report.json").write_text(report_json(rep), encoding="utf-8")
    print(json.dumps({"status": rep["status"], "totals": rep["totals"], "counts": rep["counts"],
                      "sinking": rep["sinking"], "findings": [f["code"] for f in rep["findings"]][:20]}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:6])
