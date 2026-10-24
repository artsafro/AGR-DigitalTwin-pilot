"""Hypothesis #638: proper-edge crossing veto vs unchanged match_source_faces.

Usage (from the worktree root):
  uv run python experiments/hyp-638/run_hyp638.py freeze <workdir>   # copy real inputs, hash, write predictions
  uv run python experiments/hyp-638/run_hyp638.py run <workdir>      # two repetitions, writes results.json

Reads only the copies in <workdir>. Production code is imported, never edited. Synthetic corpus = the literal
outlines/triangles of docs/research/source-face-concave-containment.md ("Frozen single triangles").
"""
import copy
import hashlib
import inspect
import json
import os
import shutil
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "jobs", "TEC26-OKS", "scripts"))
import qa_packages as q  # noqa: E402

REAL = {
    "dump": os.path.join(ROOT, "jobs", "TEC26-OKS", "AC08", "max-dump-008.json"),
    "vpm": "C:/x/tec26-oks/AC08/pilot-v010/readback/vpm.readback.json",
    "npm": "C:/x/tec26-oks/AC08/pilot-v010/readback/npm.readback.json",
}
ADDRESS = "Nku_1"  # spec address of AC08 (tests/jobs/test_tec26_ac08_pilot.py: SM_Nku_1_Main)


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------- candidate (experiment-local copy + veto only)
def _cross(r, s):
    return r[0] * s[1] - r[1] * s[0]


def _proper_crossings(t2, p2):
    """All (tri_edge, poly_edge, t, u) with den != 0 and 0 < t < 1 and 0 < u < 1 (strict, no epsilon)."""
    out = []
    for i in range(3):
        a, b = t2[i], t2[(i + 1) % 3]
        r = b - a
        for j in range(len(p2)):
            c, d = p2[j], p2[(j + 1) % len(p2)]
            s = d - c
            den = _cross(r, s)
            if den == 0:
                continue
            ca = c - a
            t = _cross(ca, s) / den
            u = _cross(ca, r) / den
            if 0 < t < 1 and 0 < u < 1:
                out.append((i, j, float(t), float(u)))
    return out


def match_source_faces_veto(src_v, src_faces, out_v, out_faces, shift, tol=2e-4, log=None):
    """Identical to qa_packages.match_source_faces except the proper-edge veto before appending a hit."""
    geo = q._poly_geo(src_v, src_faces)
    ov = np.asarray(out_v, float) + np.asarray(shift, float)
    owners = []
    for ti, f in enumerate(out_faces):
        qq = ov[list(f)]
        c = qq.mean(0)
        qlo, qhi = qq.min(0), qq.max(0)
        hits = []
        for pi, g in enumerate(geo):
            if g is None or (qlo < g["lo"] - tol).any() or (qhi > g["hi"] + tol).any():
                continue
            if np.abs(qq @ g["n"] - g["d"]).max() > tol:
                continue
            if all(q._inside2d(x[g["keep"]], g["p2"], tol) for x in qq) and q._inside2d(c[g["keep"]], g["p2"], -1):
                x = _proper_crossings(qq[:, g["keep"]], g["p2"])
                if x:
                    if log is not None:
                        log.append({"tri": ti, "source": pi, "crossings": x[:4], "n_crossings": len(x)})
                    continue
                hits.append(pi)
        owners.append(tuple(hits))
    return owners


# ---------------------------------------------------------------- synthetic corpus (literal, from the report)
T3 = (12.0, 3.0, -7.5)
L = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6)]
U = [(0, 0), (8, 0), (8, 6), (5, 6), (5, 2), (3, 2), (3, 6), (0, 6)]
N = [(0, 0), (10, 0), (10, 4), (5.5, 4), (5.5, 1), (4.5, 1), (4.5, 4), (0, 4)]
CV = [(0, 0), (4, 0), (4, 3), (0, 3)]
CASES = [  # id, outline, triangle, expected owner (independent clip/proper-intersection oracle of the report)
    ("conv_in", CV, [(0.5, 0.5), (3.5, 0.5), (2, 2.5)], (0,)),
    ("conv_out", CV, [(5, 1), (7, 1), (6, 2)], ()),
    ("L_contained", L, [(0.4, 0.4), (5.5, 0.4), (3, 1.5)], (0,)),
    ("L_cross", L, [(0.5, 0.5), (0.5, 4.5), (4.5, 0.5)], ()),
    ("L_outside", L, [(7, 7), (9, 7), (8, 9)], ()),
    ("L_boundary", L, [(0, 1), (0, 5), (5, 0)], ()),
    ("U_contained", U, [(1, 0.5), (7, 0.5), (4, 1.5)], (0,)),
    ("U_cross", U, [(1, 2.5), (7, 2.5), (4, 0.5)], ()),
    ("N_contained", N, [(1, 0.25), (9, 0.25), (5, 0.75)], (0,)),
    ("N_cross", N, [(1, 1.25), (9, 1.25), (5, 0.25)], ()),
]
CROSSING = {"L_cross", "L_boundary", "U_cross", "N_cross"}


def embed(pts, mode, trans):
    return [[x + trans[0], y + trans[1], 0.0 + trans[2]] if mode == "xy" else [x + trans[0], 0.0 + trans[1], y + trans[2]]
            for x, y in pts]


def prep(poly, tri, winding, cyclic, mode, shift_mode):
    trans = T3 if shift_mode in ("both", "undo") else (0.0, 0.0, 0.0)
    src_trans = trans if shift_mode == "both" else (0.0, 0.0, 0.0)
    shift = [-(trans[i] if shift_mode == "undo" else 0.0) for i in range(3)]
    pts = list(poly[cyclic:]) + list(poly[:cyclic])
    if winding == "cw":
        pts = list(reversed(pts))
    return embed(pts, mode, src_trans), embed(tri, mode, trans), shift


def _snap(x):
    return json.dumps(x, default=lambda a: ["ndarray", a.dtype.str, a.tolist()])


def call(fn, args):
    before = _snap(args)
    try:
        res, err = fn(*args), None
    except Exception as e:  # recorded, never swallowed silently
        res, err = None, f"{type(e).__name__}: {e}"
    return res, err, before == _snap(args)


def synthetic():
    rows, n, errors, exc, mut, changed_ctrl = [], 0, [], 0, 0, []
    for cid, poly, tri, want in CASES:
        lab = {}
        for cyclic in range(len(poly)):
            for winding in ("ccw", "cw"):
                for mode in ("xy", "xz"):
                    for sm in ("zero", "both", "undo"):
                        src, out, shift = prep(poly, tri, winding, cyclic, mode, sm)
                        args = (src, [list(range(len(src)))], out, [[0, 1, 2]], shift)
                        b, eb, sb = call(q.match_source_faces, args)
                        c, ec, sc = call(match_source_faces_veto, args)
                        n += 1
                        exc += (eb is not None) + (ec is not None)
                        mut += (not sb) + (not sc)
                        key = f"{cyclic}/{winding}/{mode}/{sm}"
                        got = c[0] if c else None
                        lab[str(got)] = lab.get(str(got), 0) + 1
                        if got != want:
                            errors.append({"case": cid, "variant": key, "got": got, "want": want, "baseline": b})
                        if cid not in CROSSING and b != c:
                            changed_ctrl.append({"case": cid, "variant": key, "baseline": b, "candidate": c})
        rows.append({"case": cid, "want": str(want), "labels": lab})
    return {"variants": n, "label_errors": len(errors), "error_examples": errors[:5], "exceptions": exc,
            "mutations": mut, "noncrossing_changed": len(changed_ctrl), "rows": rows}


# ---------------------------------------------------------------- real arms
def real(wd):
    dump = q.load(os.path.join(wd, "max-dump-008.json"))
    body = next(n for n in dump["nodes"] if n["multisub"])
    sv = np.asarray(body["vertices"], float)
    # qa_packages.main, jobs/TEC26-OKS/scripts/qa_packages.py:309-310 (exact copy)
    shift = np.array([(sv[:, 0].min() + sv[:, 0].max()) / 2, (sv[:, 1].min() + sv[:, 1].max()) / 2, 0.0])
    arms = {}
    for tag, fn, name in (("vpm", "vpm.readback.json", f"SM_{ADDRESS}_Main"),
                          ("npm", "npm.readback.json", f"SM_{ADDRESS}_001_Main")):
        rb = q.load(os.path.join(wd, fn))
        o = {x["name"]: x for x in rb["objects"]}[name]  # qa_packages.main lines 280-281 selection
        args = (body["vertices"], body["faces"], o["vertices"], o["faces"], shift)
        t0 = time.perf_counter()
        b, eb, sb = call(q.match_source_faces, args)
        t1 = time.perf_counter()
        log = []
        c, ec, sc = call(lambda *a: match_source_faces_veto(*a, log=log), args)
        t2 = time.perf_counter()
        diff = [i for i in range(len(o["faces"])) if b is None or c is None or b[i] != c[i]]
        first = []
        for i in diff[:5]:
            first.append({"tri": i, "baseline": b[i], "candidate": c[i],
                          "veto": [v for v in log if v["tri"] == i][:2]})
        tu = [x for v in log for x in v["crossings"]]
        arms[tag] = {
            "object": name, "tris": len(o["faces"]), "baseline_len": None if b is None else len(b),
            "candidate_len": None if c is None else len(c),
            "baseline_unmatched": sum(1 for x in b if not x) if b else None,
            "baseline_multi": sum(1 for x in b if len(x) > 1) if b else None,
            "changed_tuples": len(diff), "first_changed": first, "vetoes": len(log),
            "veto_min_margin": min((min(t, 1 - t, u, 1 - u) for _, _, t, u in tu), default=None),
            "veto_max_margin": max((min(t, 1 - t, u, 1 - u) for _, _, t, u in tu), default=None),
            "exceptions": [e for e in (eb, ec) if e], "mutated": (not sb) or (not sc),
            "sec_baseline": round(t1 - t0, 3), "sec_candidate": round(t2 - t1, 3),
            "owners_sha": hashlib.sha256(json.dumps([b, c]).encode()).hexdigest()}
    return {"shift": shift.tolist(), "source_faces": len(body["faces"]), "arms": arms}


def freeze(wd):
    os.makedirs(wd, exist_ok=False)
    h = {}
    for k, p in REAL.items():
        dst = os.path.join(wd, os.path.basename(p))
        shutil.copyfile(p, dst)
        h[k] = {"original": p, "copy": dst, "sha256": sha(p)}
        assert sha(dst) == h[k]["sha256"]
    pred = {"tol_default": inspect.signature(q.match_source_faces).parameters["tol"].default,
            "inputs": h,
            "prediction": {"real_changed_tuples": 0, "real_omitted": 0, "exceptions": 0, "mutations": 0,
                           "synthetic_label_errors": 0, "noncrossing_changed": 0, "repeats_identical": True}}
    with open(os.path.join(wd, "predictions.json"), "w", encoding="utf-8") as fh:
        json.dump(pred, fh, indent=1)
    print(json.dumps(pred, indent=1))


def run(wd):
    pred = json.load(open(os.path.join(wd, "predictions.json"), encoding="utf-8"))
    reps = []
    for _ in range(2):
        reps.append({"real": real(wd), "synthetic": synthetic()})
    norm = []
    for r in reps:
        r2 = copy.deepcopy(r)
        for a in r2["real"]["arms"].values():
            a.pop("sec_baseline"), a.pop("sec_candidate")
        norm.append(json.dumps(r2, sort_keys=True, default=str))
    hashes_after = {k: sha(v["copy"]) == v["sha256"] for k, v in pred["inputs"].items()}
    res = {"repeats_identical": norm[0] == norm[1], "inputs_unchanged": hashes_after, "rep": reps}
    with open(os.path.join(wd, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    r = reps[0]
    print(json.dumps({"repeats_identical": res["repeats_identical"], "inputs_unchanged": hashes_after,
                      "real": {k: {x: v[x] for x in v if x not in ("first_changed",)}
                               for k, v in r["real"]["arms"].items()},
                      "first_changed": {k: v["first_changed"][:2] for k, v in r["real"]["arms"].items()},
                      "synthetic": {k: v for k, v in r["synthetic"].items() if k != "rows"},
                      "synthetic_rows": r["synthetic"]["rows"]}, default=str, indent=1))


if __name__ == "__main__":
    {"freeze": freeze, "run": run}[sys.argv[1]](sys.argv[2])
