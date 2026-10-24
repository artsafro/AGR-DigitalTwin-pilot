"""Hypothesis #626: finite UV preflight vs unchanged face_diff label walk. Pure stdlib, label-only replay."""
import hashlib, json, math, os, shutil, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tow02-hand-finish-face-diff"))
import face_diff as fd

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
class NumericError(ValueError): pass

def walk(polys, V, uv, uvi, atlas, candidate):
    """Existing per-face arithmetic (same order). candidate=True adds finite checks before classify."""
    out, k = [], 0
    if candidate:
        for j, c in enumerate(uv):
            pass
        for i, u in enumerate(uvi):
            for o in (0, 1):
                if not math.isfinite(uv[2 * u + o]): raise NumericError("referenced UV component non-finite: corner %d comp %d" % (i, o))
    for fi, p in enumerate(polys):
        su = sum(uv[2 * uvi[k + i]] for i in range(len(p))); sv = sum(uv[2 * uvi[k + i] + 1] for i in range(len(p)))
        uvc = (su / len(p), sv / len(p)); k += len(p)
        z = sum(V[i][2] for i in p) / len(p)
        if candidate:
            S = atlas["size"]
            for name, val in (("sum_u", su), ("sum_v", sv), ("cu", uvc[0]), ("cv", uvc[1]), ("z", z),
                              ("px", uvc[0] * S), ("py", (1 - uvc[1]) * S)):
                if not math.isfinite(val): raise NumericError("face %d: %s non-finite" % (fi, name))
        out.append((fi, fd.classify(uvc, z, atlas)))
    return out, k

def real(tmp):
    d = os.path.join(tmp, "real"); os.makedirs(d, exist_ok=True)
    srcs = {"fbx": fd.V5, "atlas": fd.ATLAS}; cp = {}; rec = {}
    for n, s in srcs.items():
        cp[n] = os.path.join(d, os.path.basename(s)); shutil.copyfile(s, cp[n])
        rec[n] = dict(path=s, sha_orig=sha(s), sha_copy=sha(cp[n]))
    runs = []
    for r in range(2):
        atlas = json.load(open(cp["atlas"], encoding="utf-8"))
        V, P, UV, UI = fd.mesh(cp["fbx"], fd.OBJ); fd.check_uv(cp["fbx"], P, UV, UI)
        b, kb = walk(P, V, UV, UI, atlas, False)
        try: c, kc = walk(P, V, UV, UI, atlas, True); err = None
        except NumericError as e: c, kc, err = [], 0, str(e)
        runs.append(dict(faces=len(P), corners=sum(map(len, P)), uv_pairs=len(UV) // 2, uv_nonfinite=sum(not math.isfinite(x) for x in UV),
                         uv_outside_unit=sum(1 for x in UV if math.isfinite(x) and not 0 <= x <= 1),
                         consumed_base=kb, consumed_cand=kc, rejected=err, changed=sum(x != y for x, y in zip(b, c)) if not err else None,
                         len_eq=len(b) == len(c), seq_hash=hashlib.sha256(repr(b).encode()).hexdigest()[:16],
                         parts={p: sum(1 for _, q in b if q == p) for p in sorted({q for _, q in b})}))
    for n in cp: rec[n]["sha_after"] = sha(cp[n]); rec[n]["unchanged"] = rec[n]["sha_after"] == rec[n]["sha_orig"] == rec[n]["sha_copy"]
    return dict(files=rec, runs=runs, repeat_identical=runs[0] == runs[1])

ATL = dict(size=100, swatches={"wall": dict(rect=[40, 40, 20, 20])}, strips=[])
def case(uvs, uvi=(0, 1, 2)):
    return dict(V=[(0, 0, 0), (1, 0, 0), (0, 1, 1)], P=[[0, 1, 2]], UV=list(uvs), UI=list(uvi))
def synth(tmp):
    nan, inf, B, C = float("nan"), float("inf"), 1e308, 1e307
    mal = {"nan_u": [nan, .5] + [.5, .5] * 2, "nan_v": [.5, nan] + [.5, .5] * 2, "inf_u": [inf, .5] + [.5, .5] * 2,
           "inf_v": [.5, inf] + [.5, .5] * 2, "-inf_u": [-inf, .5] + [.5, .5] * 2, "-inf_v": [.5, -inf] + [.5, .5] * 2,
           "sum_overflow_u": [B, .5] * 3, "sum_overflow_v": [.5, B] * 3, "pixel_overflow_u": [C, .5] * 3, "pixel_overflow_v": [.5, C] * 3}
    ctl = {"in_swatch": [.5, .5] * 3, "zeros": [0.0] * 6, "twos": [2.0] * 6, "unreferenced_nan": [.5, .5] * 3 + [nan, nan]}
    res = {}
    for n, uv in {**mal, **ctl}.items():
        c = case(uv); b, _ = walk(c["P"], c["V"], c["UV"], c["UI"], ATL, False)
        od = os.path.join(tmp, "out_" + n); os.makedirs(od)
        try:
            cand, _ = walk(c["P"], c["V"], c["UV"], c["UI"], ATL, True)
            open(os.path.join(od, "labels.tsv"), "w").write("%s\n" % cand)  # artifact only after preflight
            e = None
        except NumericError as x: cand, e = None, str(x)
        res[n] = dict(kind="malformed" if n in mal else "control", baseline=b, candidate=cand, error=e, artifacts=os.listdir(od),
                      ok=(e is not None and not os.listdir(od)) if n in mal else (e is None and cand == b))
    return res

if __name__ == "__main__":
    tmp = os.path.join(tempfile.gettempdir(), "agr-hyp-t_797e39f8"); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    out = dict(real=real(tmp), synthetic=synth(tmp)); json.dump(out, open(os.path.join(tmp, "result.json"), "w"), indent=1)
    print(json.dumps(out["real"], indent=1)); print({k: (v["kind"], v["ok"], v["error"]) for k, v in out["synthetic"].items()})
    print("tmp", tmp)
