"""Hypothesis #663: five-decimal rounding in qa_packages._new_vertices vs exact-row unique (diagnostic only).

Usage (from the worktree root):
  uv run python experiments/hyp-663/run_hyp663.py freeze <workdir>   # copy real inputs, hash, inventory, predictions
  uv run python experiments/hyp-663/run_hyp663.py run <workdir>      # two repetitions, writes results.json

Reads only the copies in <workdir>. Production code is imported, never edited. The comparator is a PRIVATE module
built from the unchanged qa_packages.py source with exactly one line replaced (BASE_LINE -> DIAG_LINE); it is not
an adoption candidate and not an acceptance oracle.
"""
import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import types

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "jobs", "TEC26-OKS", "scripts")
sys.path.insert(0, SCRIPTS)
import finish_map  # noqa: E402
import qa_packages as q  # noqa: E402  (baseline, unchanged)

REAL = {
    "dump": os.path.join(ROOT, "jobs", "TEC26-OKS", "AC08", "max-dump-008.json"),
    "spec": os.path.join(ROOT, "jobs", "TEC26-OKS", "AC08", "vpm_textures.json"),
    "vpm": "C:/x/tec26-oks/AC08/pilot-v010/readback/vpm.readback.json",
    "npm": "C:/x/tec26-oks/AC08/pilot-v010/readback/npm.readback.json",
}
PINNED = {  # docs/experiments/hyp-638.md Setup / issue #663 Inputs
    "dump": "f1fc27dc77d5d194ae25aebe8aeb23e71993ab0890cb08def97279bac3e45225",
    "vpm": "79195308ae9b70214f5d487880ed941298aee725f27a347c1f67485d3e095817",
    "npm": "336f0e73aedf9c035624ce2b44279a3c14979d258d96a06d2130c21ecd2ac5e0",
}
BASE_LINE = "    ov = np.unique(np.round(np.asarray(out_v, float) + np.asarray(shift, float), 5), axis=0)\n"
DIAG_LINE = "    ov = np.unique(np.asarray(out_v, float) + np.asarray(shift, float), axis=0)\n"
GEO = ("ok", "missing_source_vertices", "new_vertices", "cuts_allowed", "new_off_source_edges")
JNT = ("ok", "new_vertices", "checked_on_patterned_edges", "off_joint_count")


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def diag_module():
    """Private copy of qa_packages with ONLY the _new_vertices round+unique line replaced."""
    src = open(q.__file__, encoding="utf-8").read()
    assert src.count(BASE_LINE) == 1, "baseline line not found exactly once"
    new = src.replace(BASE_LINE, DIAG_LINE)
    a, b = src.splitlines(), new.splitlines()
    assert len(a) == len(b) and sum(x != y for x, y in zip(a, b)) == 1
    m = types.ModuleType("qa_packages_diag663")
    m.__file__ = "<diag663>"
    exec(compile(new, "<qa_packages_diag663>", "exec"), m.__dict__)
    assert m.finish_map is finish_map and q._new_vertices is not m._new_vertices
    return m


def _snap(x):
    return json.dumps(x, default=lambda a: ["ndarray", a.dtype.str, a.tolist()])


def call(fn, args):
    before = _snap(args)
    try:
        res, err = fn(*args), None
    except Exception as e:  # recorded, never swallowed silently
        res, err = None, f"{type(e).__name__}: {e}"
    return res, err, before == _snap(args)


def compare(D, src_v, src_faces, expected, spec, out_v, shift):
    """Baseline vs diagnostic on geometry_report (both flags) and cut_joint_report. Returns full dicts + diffs."""
    out = {"exceptions": [], "mutations": 0, "changed": [], "reports": {}}
    jobs = [("geo_cutsF", "geometry_report", (src_v, src_faces, out_v, shift, False), GEO),
            ("geo_cutsT", "geometry_report", (src_v, src_faces, out_v, shift, True), GEO),
            ("joint", "cut_joint_report", (src_v, src_faces, expected, spec, out_v, shift), JNT)]
    for key, fn, args, fields in jobs:
        b, eb, sb = call(getattr(q, fn), copy.deepcopy(args))
        c, ec, sc = call(getattr(D, fn), copy.deepcopy(args))
        out["exceptions"] += [e for e in (eb, ec) if e]
        out["mutations"] += (not sb) + (not sc)
        out["reports"][key] = {"baseline": b, "diagnostic": c}
        for f in fields:
            if b is None or c is None or b.get(f) != c.get(f):
                out["changed"].append({"report": key, "field": f, "baseline": None if b is None else b.get(f),
                                       "diagnostic": None if c is None else c.get(f)})
    # descriptive: new-vertex sets of both arms with raw / recovered / rounded coordinates
    nb, _ = q._new_vertices(src_v, out_v, shift)
    nd, _ = D._new_vertices(src_v, out_v, shift)
    rec = np.asarray(out_v, float) + np.asarray(shift, float)
    out["unique_rows"] = {"rounded": int(len(np.unique(np.round(rec, 5), axis=0))),
                          "exact": int(len(np.unique(rec, axis=0))), "raw_rows": int(len(rec))}
    out["new_rows"] = {"baseline": int(len(nb)), "diagnostic": int(len(nd))}
    sv = np.asarray(src_v, float)
    # margin of every recovered vertex to the tol=2e-4 Chebyshev source-match boundary (min over source), both arms
    d_exact = np.abs(rec[:, None, :] - sv[None, :, :]).max(2).min(1)
    d_round = np.abs(np.round(rec, 5)[:, None, :] - sv[None, :, :]).max(2).min(1)
    out["source_match_boundary"] = {
        "min_abs_margin_exact": float(np.abs(d_exact - 2e-4).min()),
        "min_abs_margin_rounded": float(np.abs(d_round - 2e-4).min()),
        "side_flips": int(((d_exact > 2e-4) != (d_round > 2e-4)).sum()),
        "max_round_move": float(np.abs(np.round(rec, 5) - rec).max())}
    if out["changed"]:
        first = [{"raw": list(map(float, np.asarray(out_v, float)[i])), "recovered": rec[i].tolist(),
                  "rounded": np.round(rec[i], 5).tolist(), "d_exact": float(d_exact[i]), "d_round": float(d_round[i])}
                 for i in np.flatnonzero((d_exact > 2e-4) != (d_round > 2e-4))[:5]]
        out["first_affected"] = first
    return out


# ---------------------------------------------------------------- synthetic controls (literal, issue Method 4)
QUAD = [(0.0, 0.0, 1.0), (4.0, 0.0, 1.0), (4.0, 0.0, 3.0), (0.0, 0.0, 3.0)]
MID = (2.0, 0.0, 1.0)
v0, v1, v2, v3 = QUAD
SCORED = {
    "source_only": QUAD,
    "added_midpoint": QUAD + [MID],
    "dup_perm_source": [v2, v0, v0, v3, v1, v2],
    "dup_perm_midpoint": [MID, v3, v1, MID, v0, v2, v0],
}
SENSITIVITY = {  # unscored known-defect witnesses: MUST differ, else the comparison is blind
    "add_0.004003_joint_flip": (QUAD + [(0.004003, 0.0, 1.0)], ("joint", "off_joint_count")),
    "replace_corner_0.000201": ([(0.000201, 0.0, 1.0), v1, v2, v3], ("geo_cutsF", "missing_source_vertices")),
}


def synthetic(D):
    spec = {"zero_m": 0, "facade_uv": ["F"], "finishes": {"F": {"P": [1, 1]}}}
    faces, expected, shift = [[0, 1, 2, 3]], ["F"], [0.0, 0.0, 0.0]
    src = [list(p) for p in QUAD]
    scored = {k: compare(D, src, faces, expected, spec, [list(p) for p in v], shift) for k, v in SCORED.items()}
    sens = {}
    for k, (v, (rep, field)) in SENSITIVITY.items():
        r = compare(D, src, faces, expected, spec, [list(p) for p in v], shift)
        sens[k] = {"changed": r["changed"], "exceptions": r["exceptions"], "mutations": r["mutations"],
                   "witness_exposed": any(c["report"] == rep and c["field"] == field for c in r["changed"])}
    return {"scored": scored, "sensitivity": sens}


# ---------------------------------------------------------------- real arms
def real(wd, D):
    dump = q.load(os.path.join(wd, "max-dump-008.json"))
    spec = q.load(os.path.join(wd, "vpm_textures.json"))
    A = spec["address"]
    body = next(n for n in dump["nodes"] if n["multisub"])  # qa_packages.main:307
    sv = np.asarray(body["vertices"], float)
    shift = np.array([(sv[:, 0].min() + sv[:, 0].max()) / 2, (sv[:, 1].min() + sv[:, 1].max()) / 2, 0.0])  # :310
    expected = finish_map.assign_finishes(body["vertices"], body["faces"], body["mat_ids"], spec)  # :402
    arms = {}
    for tag, fn, name in (("vpm", "vpm.readback.json", f"SM_{A}_Main"), ("npm", "npm.readback.json", f"SM_{A}_001_Main")):
        rb = q.load(os.path.join(wd, fn))
        objs = {x["name"]: x for x in rb["objects"]}
        if name not in objs:
            arms[tag] = {"object": name, "omitted": True}
            continue
        o = objs[name]
        r = compare(D, body["vertices"], body["faces"], expected, spec, o["vertices"], shift)
        r.update(object=name, omitted=False, vertices=len(o["vertices"]), faces=len(o["faces"]))
        arms[tag] = r
    return {"address": A, "shift": shift.tolist(), "source_vertices": len(sv), "source_faces": len(body["faces"]),
            "has_facades": bool(spec.get("facades")), "ring_cuts": bool(spec.get("ring_cuts")),
            "expected_sha": hashlib.sha256(json.dumps(expected).encode()).hexdigest(), "arms": arms}


def freeze(wd):
    os.makedirs(wd, exist_ok=False)
    h = {}
    for k, p in REAL.items():
        dst = os.path.join(wd, os.path.basename(p))
        shutil.copyfile(p, dst)
        h[k] = {"original": p, "copy": dst, "sha256": sha(p)}
        assert sha(dst) == h[k]["sha256"]
        if k in PINNED:
            assert h[k]["sha256"] == PINNED[k], f"provenance mismatch {k}"
    inv = {}
    d = q.load(h["dump"]["copy"])
    inv["dump"] = [{"name": n["name"], "multisub": bool(n["multisub"]), "v": len(n["vertices"]), "f": len(n["faces"])}
                   for n in d["nodes"]]
    for k in ("vpm", "npm"):
        inv[k] = [{"name": o["name"], "v": len(o["vertices"]), "f": len(o["faces"])} for o in q.load(h[k]["copy"])["objects"]]
    head = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    pred = {"source_sha": head, "qa_packages_sha256": sha(q.__file__), "finish_map_sha256": sha(finish_map.__file__),
            "driver_sha256": sha(__file__), "base_line": BASE_LINE, "diag_line": DIAG_LINE, "inputs": h,
            "inventory": inv, "numpy": np.__version__, "python": sys.version.split()[0],
            "prediction": {"real_changed_fields": 0, "scored_control_changed_fields": 0, "exceptions": 0,
                           "mutations": 0, "omitted": 0, "repeats_identical": True,
                           "sensitivity_witnesses_exposed": 2}}
    with open(os.path.join(wd, "predictions.json"), "w", encoding="utf-8") as fh:
        json.dump(pred, fh, indent=1)
    print(json.dumps({k: v for k, v in pred.items() if k != "inventory"}, indent=1))
    print(json.dumps({k: [x for x in v if x.get("multisub") or "Main" in x["name"]] for k, v in inv.items()}))


def scored_view(r):
    keep = {}
    for k, a in r["real"]["arms"].items():
        keep[k] = {x: a.get(x) for x in ("omitted", "changed", "exceptions", "mutations")}
        keep[k]["reports"] = {rk: {s: {f: (v[s] or {}).get(f) for f in (GEO if rk != "joint" else JNT)}
                                   for s in ("baseline", "diagnostic")} for rk, v in a.get("reports", {}).items()}
    keep["synthetic"] = {k: (v["changed"], v["exceptions"], v["mutations"]) for k, v in r["synthetic"]["scored"].items()}
    keep["sensitivity"] = {k: v["witness_exposed"] for k, v in r["synthetic"]["sensitivity"].items()}
    return json.dumps(keep, sort_keys=True, default=str)


def run(wd):
    pred = json.load(open(os.path.join(wd, "predictions.json"), encoding="utf-8"))
    assert sha(q.__file__) == pred["qa_packages_sha256"] and sha(__file__) == pred["driver_sha256"], "code changed"
    D = diag_module()
    reps = [{"real": real(wd, D), "synthetic": synthetic(D)} for _ in range(2)]
    after = {k: {"copy": sha(v["copy"]) == v["sha256"], "original": sha(v["original"]) == v["sha256"]}
             for k, v in pred["inputs"].items()}
    full_identical = json.dumps(reps[0], sort_keys=True, default=str) == json.dumps(reps[1], sort_keys=True, default=str)
    res = {"repeats_identical_scored": scored_view(reps[0]) == scored_view(reps[1]),
           "repeats_identical_full": full_identical, "inputs_unchanged": after, "rep": reps}
    with open(os.path.join(wd, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    r = reps[0]
    summ = {"repeats_identical_scored": res["repeats_identical_scored"], "repeats_identical_full": full_identical,
            "inputs_unchanged": after, "real": {}}
    for k, a in r["real"]["arms"].items():
        summ["real"][k] = {x: a.get(x) for x in ("object", "omitted", "vertices", "faces", "changed", "exceptions",
                                                 "mutations", "unique_rows", "new_rows", "source_match_boundary",
                                                 "first_affected")}
        summ["real"][k]["reports"] = {rk: v["baseline"] and {f: v["baseline"].get(f) for f in (GEO if rk != "joint"
                                                                                                else JNT)}
                                      for rk, v in a.get("reports", {}).items()}
    summ["real_meta"] = {x: r["real"][x] for x in ("address", "shift", "source_vertices", "source_faces",
                                                    "has_facades", "ring_cuts")}
    summ["synthetic_scored"] = {k: {"changed": v["changed"], "exc": v["exceptions"], "mut": v["mutations"],
                                    "unique_rows": v["unique_rows"],
                                    "geoF": {f: v["reports"]["geo_cutsF"]["baseline"][f] for f in GEO},
                                    "joint": {f: v["reports"]["joint"]["baseline"][f] for f in JNT}}
                                for k, v in r["synthetic"]["scored"].items()}
    summ["sensitivity"] = r["synthetic"]["sensitivity"]
    print(json.dumps(summ, default=str, indent=1))


if __name__ == "__main__":
    {"freeze": freeze, "run": run}[sys.argv[1]](sys.argv[2])
