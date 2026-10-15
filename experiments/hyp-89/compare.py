"""Hypothesis #89, step 3: compare the matrix against the frozen prediction table.

    python experiments/hyp-89/compare.py <work dir>      -> <work>/compare.json + a printed table

Excluded from JSON comparisons (issue #89): source path, source sha256, collection order (lists of
meshes / helpers / other objects / images are sorted by name). Everything else is compared: discrete
values exactly, floats with the frozen thresholds by field:
  measure dumps: vertices, helper location            -> max |d| <= 1e-5 m
  readback: location, scale                           -> max |d| <= 1e-6
  readback: rotation_euler_deg                        -> max |d| <= 1e-4 deg
  readback: bounds_m                                  -> max |d| <= 1e-5 m (geometry)
Any other float differing at all is reported as 'other'. Order of vertices/triangles is NOT normalised.
"""
import json
import sys
from pathlib import Path

work = Path(sys.argv[1]).resolve()
MODELS, LANES = ("B01", "B02", "B02t"), ("exe", "whl")
EXCLUDE = {"source", "sha256"}
LIMIT = {"geom": 1e-5, "locscale": 1e-6, "rot": 1e-4, "other": 0.0}
CAT = {"vertices": "geom", "bounds_m": "geom", "location": "locscale", "scale": "locscale",
       "rotation_euler_deg": "rot"}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in x.items() if k not in EXCLUDE}
    if isinstance(x, list):
        x = [norm(v) for v in x]
        if x and all(isinstance(v, dict) and "name" in v for v in x):
            x = sorted(x, key=lambda v: v["name"])
        return x
    return x


def diff(a, b, path="", cat="other", acc=None):
    """acc = {'max': {cat: float}, 'discrete': [paths]}"""
    acc = acc if acc is not None else {"max": {}, "discrete": []}
    if isinstance(a, bool) or isinstance(b, bool) or isinstance(a, str) or a is None or b is None:
        if a != b:
            acc["discrete"].append(f"{path}: {str(a)[:60]} != {str(b)[:60]}")
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            if a != b:
                acc["discrete"].append(f"{path}: {a} != {b}")
        else:
            d = abs(a - b)
            acc["max"][cat] = max(acc["max"].get(cat, 0.0), d)
    elif isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            acc["discrete"].append(f"{path}: keys {sorted(set(a) ^ set(b))}")
        for k in set(a) & set(b):
            diff(a[k], b[k], f"{path}.{k}", CAT.get(k, cat), acc)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            acc["discrete"].append(f"{path}: len {len(a)} != {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                diff(x, y, f"{path}[{i}]", cat, acc)
    else:
        acc["discrete"].append(f"{path}: type {type(a).__name__} != {type(b).__name__}")
    return acc


def verdict(acc):
    bad = [f"{c} {m:.3g}>{LIMIT[c]:g}" for c, m in acc["max"].items() if m > LIMIT[c]]
    return {"ok": not bad and not acc["discrete"], "max": {c: m for c, m in acc["max"].items()},
            "over": bad, "discrete": acc["discrete"][:5], "n_discrete": len(acc["discrete"])}


def engine_view(dump):
    """The common dump reduced to the fields measure_spec_blender emits (helpers, meshes)."""
    return {"meshes": [{k: m[k] for k in ("name", "vertices", "triangles", "material_ids", "polygon_sizes")}
                       for m in dump["meshes"]], "helpers": dump.get("helpers", [])}


rows, rejected = [], []
runs = load(work / "runs.json")
completion_fail = [r for r in runs if r["exit"] != 0]
for rep in (1, 2):
    for model in MODELS:
        common = norm(engine_view(load(work / "common" / f"{model}-dump.json")))
        base = work / f"rep{rep}" / model
        ref_rb = norm(load(base / "exe" / "rb-exe.json"))
        ref_ms = norm(load(base / "exe" / "ms-fbx-exe.json"))
        for e in LANES:
            for f in ("model.blend", "model.fbx"):
                if not (base / e / f).is_file() or (base / e / f).stat().st_size == 0:
                    completion_fail.append({"missing": str(base / e / f)})
            ms_blend = norm(load(base / e / "ms-blend.json"))
            ms_blend_view = {"meshes": [{k: v for k, v in m.items() if k != "udim_tiles"}
                                        for m in ms_blend["meshes"]], "helpers": ms_blend["helpers"]}
            ms_blend_view = norm(ms_blend_view)
            rows.append((rep, model, e, "-", "blend vs engine dump",
                         verdict(diff(common, ms_blend_view))))
            rows.append((rep, model, e, "-", "blend vs exe blend",
                         verdict(diff(norm(load(base / "exe" / "ms-blend.json")), ms_blend))))
            for r in LANES:
                rb = norm(load(base / e / f"rb-{r}.json"))
                if not rb.get("readback_ok") or not rb.get("meshes"):
                    completion_fail.append({"readback": str(base / e / f"rb-{r}.json")})
                ms = norm(load(base / e / f"ms-fbx-{r}.json"))
                rows.append((rep, model, e, r, "readback vs exe/exe", verdict(diff(ref_rb, rb))))
                rows.append((rep, model, e, r, "fbx measure vs exe/exe", verdict(diff(ref_ms, ms))))
                ms_view = norm({"meshes": [{k: v for k, v in m.items() if k != "udim_tiles"}
                                           for m in ms["meshes"]], "helpers": ms["helpers"]})
                rows.append((rep, model, e, r, "fbx measure vs engine dump", verdict(diff(common, ms_view))))
                if rep == 2:
                    r1 = work / "rep1" / model / e
                    rows.append((rep, model, e, r, "readback rep2 vs rep1",
                                 verdict(diff(norm(load(r1 / f"rb-{r}.json")), rb))))
                    rows.append((rep, model, e, r, "fbx measure rep2 vs rep1",
                                 verdict(diff(norm(load(r1 / f"ms-fbx-{r}.json")), ms))))
                    if e == "exe" and r == "exe":
                        continue

out = [{"rep": a, "model": b, "exporter": c, "reader": d, "check": k, **v} for a, b, c, d, k, v in rows]
(work / "compare.json").write_text(json.dumps({"completion_fail": completion_fail, "rows": out}, indent=1),
                                   encoding="utf-8")
print("completion failures:", len(completion_fail))
agg = {}
for o in out:
    a = agg.setdefault(o["check"], {"n": 0, "fail": 0, "max": {}})
    a["n"] += 1
    a["fail"] += not o["ok"]
    for c, m in o["max"].items():
        a["max"][c] = max(a["max"].get(c, 0.0), m)
for k, a in agg.items():
    print(f"{k:28s} n={a['n']:3d} fail={a['fail']:3d} max={ {c: f'{m:.3g}' for c, m in a['max'].items()} }")
for o in out:
    if not o["ok"]:
        print("FAIL", o["rep"], o["model"], o["exporter"], o["reader"], o["check"], o["over"], o["discrete"][:2])
