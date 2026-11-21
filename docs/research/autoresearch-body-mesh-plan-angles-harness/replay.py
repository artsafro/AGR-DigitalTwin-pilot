"""Standing #30: replay #29, then try an additive 63B plan-angle allowance."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import runpy
from statistics import median
import subprocess
from tempfile import TemporaryDirectory
from time import monotonic
from types import FunctionType

ROOT = Path(__file__).resolve().parents[3]
REF29 = "8aa66dc6a402e394f357d1c10cc5c6732d86a6a1"
H29 = "docs/research/autoresearch-body-mesh-offgrid-quads-harness"
PLAN_REV = "ed4c418e087391cd453182c985a7a8b38a4fb601"
PLANS = tuple(f"tests/fixtures/poly63b/floor_{k}.json" for k in "AB")
POSES = ((0, (0, 0, 0)), (17, (3, -4, 7)), (-31, (-9, 6, -2)))
EPS = 1e-9


def blob(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)


def allowance(reader, grid, tol):
    def off_grid(a):
        return all(abs(a - g) > tol for g in grid)

    return FunctionType(reader.__code__, dict(reader.__globals__, off_grid=off_grid))


def plan_grid(doc, angles):
    if doc.get("units") != "m" or not doc["rings"]:
        raise ValueError("expected nonempty metre contours")
    grid = set()
    for ring in doc["rings"]:
        pts = [(x, y, 0) for x, y in ring["xy"]]
        if len(pts) < 3 or not all(math.isfinite(v) for p in pts for v in p):
            raise ValueError("invalid contour")
        grid.update(a for a in angles(pts) if 1 < a < 179)
    if not grid:
        raise ValueError("no usable plan angles")
    return grid


def pose(data, transform):
    if transform == POSES[0]:
        return data
    theta, (dx, dy, dz) = transform
    c, s = math.cos(math.radians(theta)), math.sin(math.radians(theta))
    return {"objects": [dict(obj, verts=[(c*x-s*y+dx, s*x+c*y+dy, z+dz)
                                        for x, y, z in obj["verts"]])
                        for obj in data["objects"]]}


def rhombus(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(0, 0, 0), (1, 0, 0), (1+c, s, 0), (c, s, 0)]


def extreme_margin(rows, key):
    reject = min((r[key], name) for name, r in rows.items() if r["label"] == "rejected")
    accept = max((r[key], name) for name, r in rows.items() if r["label"] == "accepted")
    return {"M": reject[0] - accept[0], "worst_rejected": reject, "worst_accepted": accept}


def measure(root, budget, start, prior, ref, r28, angles):
    base = prior["measure"](root, ref, r28, angles)
    # Compare the JSON values; the in-process #29 extremes are tuples.
    if json.loads(json.dumps(base, allow_nan=False)) != json.loads(blob(REF29, f"{H29}/r29.json")):
        raise ValueError("#29 full receipt mismatch")
    plans = {p: blob(PLAN_REV, p) for p in PLANS}
    fixed, tol = prior["GRID"], prior["TOL"]
    extra = set().union(*(plan_grid(json.loads(raw), angles) for raw in plans.values()))
    grid = sorted(set(fixed) | extra)
    reader = prior["read_quads"]
    candidate = allowance(reader, grid, tol)
    args = ref["newell"], angles, ref["COS1"]
    matched_plan = {"units": "m", "rings": [{"xy": [p[:2] for p in rhombus(48)]}]}
    synthetic = allowance(reader, sorted(set(fixed) | plan_grid(matched_plan, angles)), tol)
    witnesses = {}
    for deg, expected in ((90, [0, 0]), (48, [1, 0]), (72, [1, 1])):
        data = {"objects": [{"verts": rhombus(deg), "faces": [[0, 1, 2, 3]]}]}
        witnesses[str(deg)] = [f(data, *args)["Q"] for f in (reader, synthetic)]
        if witnesses[str(deg)] != expected:
            raise ValueError(f"synthetic witness failure: {deg}")

    rows = {name: {"label": label, "path": path, "sha256": sha, "pairs": []}
            for name, label, path, sha in ref["FIXTURE"]}
    pose_margins = []
    pair_seconds = None
    for i, transform in enumerate(POSES):
        pair_start = monotonic()
        for name, row in rows.items():
            if monotonic() - start >= budget:
                raise TimeoutError("frozen measurement budget exceeded")
            data = pose(prior["checked_dump"](root / row["path"], row["sha256"]), transform)
            b = reader(data, *args)
            a = candidate(data, *args) if name.startswith("63B-") else b
            if i == 0 and any(b[k] != base["rows"][name][k] for k in b):
                raise ValueError(f"identity parity failure: {name}")
            anchor = base["rows"][name]
            if not math.isclose(b["area"], anchor["area"], rel_tol=EPS) or any(
                    a[k] != b[k] or b[k] != anchor[k] for k in ("faces", "horizontal_quads")):
                raise ValueError(f"area or topology parity failure: {name}")
            if a["area"] != b["area"] or a["Q"] > b["Q"] + EPS or a["flagged_faces"] > b["flagged_faces"]:
                raise ValueError(f"non-additive candidate: {name}")
            row["pairs"].append({"base": b, "candidate": a, "delta": a["Q"] - b["Q"]})
        if i == 0:
            pair_seconds = monotonic() - pair_start
            if budget - (monotonic() - start) < 3 * pair_seconds:
                raise TimeoutError(f"cannot reserve 3x the measured identity pair ({pair_seconds:.2f}s)")
        pose_margins.append(extreme_margin({name: {"label": row["label"], "Q": row["pairs"][-1]["candidate"]["Q"]}
                                            for name, row in rows.items()}, "Q"))

    for name, row in rows.items():
        ref["require_hash"](root / row["path"], row["sha256"])
        for key in ("base", "candidate"):
            views = [p[key] for p in row["pairs"]]
            if any(abs(v["Q"] - views[0]["Q"]) > EPS or v["flagged_faces"] != views[0]["flagged_faces"]
                   for v in views):
                raise ValueError(f"pose stability failure: {name}, {key}")
        deltas = [p["delta"] for p in row["pairs"]]
        row["paired_spread"] = max(deltas) - min(deltas)
        if row["paired_spread"] > 2 * EPS:
            raise ValueError(f"paired spread failure: {name}")
        row["Q"] = median(p["candidate"]["Q"] for p in row["pairs"])
    if any(p["candidate"]["flagged_faces"] <= 0 for p in rows["63C-v001"]["pairs"]):
        raise ValueError("lost rejected sentinel")
    if monotonic() - start >= budget:
        raise TimeoutError("frozen measurement budget exceeded")
    trigger = all(p["delta"] < -EPS for p in rows["63B-v007"]["pairs"])
    result = extreme_margin(rows, "Q")
    separation = result["M"] > 0 and all(p["M"] > 0 for p in pose_margins)
    return {"variant": "#29 + all nondegenerate unsigned A/B source contour angles, 63B only",
            "baseline_revision": REF29, "baseline_M": base["M"], "poses": POSES,
            "plan_revision": PLAN_REV, "plan_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in plans.items()},
            "allowed_angles_63B": grid, "replay_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "budget_s": budget, "identity_pair_s": pair_seconds, "elapsed_s": monotonic() - start,
            **result, "pose_margins": pose_margins, "accepted_trigger": trigger,
            "hypothesis": "confirmed" if separation and trigger else "inconclusive" if separation else "refuted",
            "clean": {"r29_full_exact": True, "area_face_parity": True, "outside_63B_unchanged": True,
                      "rejected_63C_sentinel": True, "square": witnesses["90"], "input_hashes_verified": True},
            "injected": {"plan_matched_48": witnesses["48"], "unmatched_72": witnesses["72"],
                         "inherited_r29_witnesses": base["injected_checks"]},
            "not_measured": ["source CAD verification", "independent labels", "face/plan ownership",
                             "native rebuild/readback", "score change", "package QA"], "rows": rows}


def main(root, out, budget):
    start = monotonic()
    with TemporaryDirectory(prefix="ar30-ref-", dir=ROOT) as td:
        def load(name, raw):
            path = Path(td) / name
            path.write_bytes(raw)
            return runpy.run_path(str(path))

        prior = load("ar29.py", blob(REF29, f"{H29}/replay.py"))
        # Rebind the prior loader's repository root: its source is staged in a temporary directory.
        prior["blob"].__globals__["ROOT"] = ROOT
        ref = load("ar27.py", blob(prior["REF27"], f"{prior['H27']}/replay.py"))
        r28 = load("ar28.py", blob(prior["REF28"], f"{prior['H28']}/replay.py"))
        angles = load("core.py", blob(prior["BASE"], prior["CORE"]))["_angles"]
        result = measure(root, budget, start, prior, ref, r28, angles)
    with out.open("x", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, allow_nan=False)
        fh.write("\n")
    print(result["hypothesis"], result["M"], result["accepted_trigger"], result["elapsed_s"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--budget-s", type=float, default=180)
    options = parser.parse_args()
    if not 0 < options.budget_s <= 180:
        parser.error("budget must be in (0, 180] seconds")
    main(options.root, options.out, options.budget_s)
