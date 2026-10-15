"""E1 (reduced): same engine twin realized headless (Blender 5.1.2) vs live (Blender 4.4.0 live), then
fresh headless readback of the saved .blend and the FBX, parity + checks.run on both routes.

    uv run python experiments/bim-blender-agr/run.py <S dir> [reps]

S dir = %TEMP%/agr-exp-<card>; inputs are COPIES of benchmark/<bench>/{spec,object,tolerances}.json.
Geometry is engine-generated from spec.json (SYNTHETIC, not a native etalon: etalon.fbx is not on disk).
Variants: clean, flip1 (one facade polygon reversed), flipall (body inverted) from
experiments/blender-bpy-automation/make_fixtures.py.
"""
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments/blender-bpy-automation"))
from dt_ai.core.blender_runner import run_blender  # noqa: E402
from dt_ai.geometry.from_spec import BuildInputs, build  # noqa: E402
from dt_ai.spec.model import Spec  # noqa: E402
from twinqa.geometry import checks  # noqa: E402
from twinqa.geometry.mesh import from_dump  # noqa: E402
from make_fixtures import variants  # noqa: E402

B51 = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
LIVE = "C:/Users/artsafro/hermes_kanban/scripts/blender_exec.py"
EXPORT = ROOT / "tools/export/export_mesh_blender.py"
MEASURE = ROOT / "tools/source/measure_spec_blender.py"
PAYLOAD = Path(__file__).with_name("live_realize.py")
BENCHES = ["bench-b01-box", "bench-b02-corner-niche", "bench-b02t-terrace"]
VARIANTS = ["clean", "flip1", "flipall"]


def headless(dump, blend, fbx):
    t = time.perf_counter()
    run_blender(EXPORT, (dump, blend, fbx), executable=B51, outputs=(blend, fbx), timeout=300,
                log_path=blend.with_suffix(".log"))
    return {"wall_s": time.perf_counter() - t}


def live(dump, blend, fbx):
    cfg = {"dump": str(dump), "blend": str(blend), "fbx": str(fbx)}
    code = (f"CFG={json.dumps(cfg)}\n"
            f"exec(compile(open(r'{PAYLOAD}',encoding='utf-8').read(),r'{PAYLOAD}','exec'),globals())")
    t = time.perf_counter()
    p = subprocess.run(["python", LIVE, "--code", code, "--card", "t_c9185662"],
                       capture_output=True, text=True, timeout=300)
    wall = time.perf_counter() - t
    r = json.loads(p.stdout)
    if r.get("status") != "success" or not fbx.is_file():
        raise RuntimeError(f"live failed: {p.stdout[:400]} {p.stderr[:200]}")
    out = r["result"]
    out = out.get("result", out) if isinstance(out, dict) else out
    text = out if isinstance(out, str) else json.dumps(out)
    line = [ln for ln in text.splitlines() if ln.startswith("{")][-1]
    return {"wall_s": wall, **json.loads(line)}


def readback(src, out):
    t = time.perf_counter()
    run_blender(MEASURE, (src, out), executable=B51, output_json=out, timeout=300,
                log_path=out.with_suffix(".log"))
    return json.loads(out.read_text(encoding="utf-8")), time.perf_counter() - t


def facts(rb):
    f = {}
    for m in rb["meshes"]:
        mids = np.asarray(m.get("material_ids") or [0])
        f[m["name"]] = {"verts": len(m["vertices"]), "tris": len(m["triangles"]),
                        "mat_hist": {int(k): int(v) for k, v in zip(*np.unique(mids, return_counts=True))}}
    f["_helpers"] = {h["name"]: [round(c, 6) for c in h["location"]] for h in rb.get("helpers", [])}
    return f


def hausdorff_mm(a, b):
    """Symmetric vertex Hausdorff per mesh name, max over meshes, in mm."""
    worst = 0.0
    bm = {m["name"]: np.asarray(m["vertices"], float) for m in b["meshes"]}
    for m in a["meshes"]:
        va, vb = np.asarray(m["vertices"], float), bm.get(m["name"])
        if vb is None:
            return float("inf")
        d = np.linalg.norm(va[:, None, :] - vb[None, :, :], axis=2)
        worst = max(worst, d.min(1).max(), d.min(0).max())
    return worst * 1000


def tri_signature(rb):
    """Orientation-sensitive geometry signature: sorted (centroid, unit normal) rows rounded to 1e-5."""
    rows = []
    for m in rb["meshes"]:
        v = np.asarray(m["vertices"], float)
        t = np.asarray(m["triangles"], int)
        p = v[t]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True)
        rows.append(np.round(np.hstack([p.mean(1), n]), 5))
    a = np.vstack(rows)
    return a[np.lexsort(a.T[::-1])]


def main(S, reps=3):
    S = Path(S)
    res = []
    for bench in BENCHES:
        d = S / bench
        spec = Spec.model_validate(json.loads((d / "spec.json").read_text(encoding="utf-8")))
        obj = json.loads((d / "object.json").read_text(encoding="utf-8"))
        tol = json.loads((d / "tolerances.json").read_text(encoding="utf-8"))["geometry"]
        dump = build(spec, BuildInputs.from_object(obj))
        clean_soup = from_dump(dump)
        for name, v in variants(dump).items():
            if name not in VARIANTS:
                continue
            src = d / f"{name}.dump.json"
            src.write_text(json.dumps(v), encoding="utf-8")
            for route, fn in (("headless", headless), ("live", live)):
                for r in range(1, reps + 1):
                    o = d / f"{name}-{route}-r{r}"
                    o.mkdir()
                    run = fn(src, o / "model.blend", o / "model.fbx")
                    rb_fbx, t_fbx = readback(o / "model.fbx", o / "rb-fbx.json")
                    rb_blend, t_blend = readback(o / "model.blend", o / "rb-blend.json")
                    rep = checks.run(from_dump(rb_fbx), clean_soup, spec, tol)
                    bad = [c["id"] for c in rep["checks"] if c["status"] != "pass"]
                    sig_f, sig_b = tri_signature(rb_fbx), tri_signature(rb_blend)
                    rec = {"bench": bench, "variant": name, "route": route, "rep": r, **run,
                           "readback_fbx_s": t_fbx, "readback_blend_s": t_blend,
                           "facts_fbx": facts(rb_fbx), "facts_blend": facts(rb_blend),
                           "hd_fbx_vs_src_mm": hausdorff_mm(rb_fbx, v), "hd_blend_vs_src_mm": hausdorff_mm(rb_blend, v),
                           "blend_eq_fbx_sig": bool(sig_f.shape == sig_b.shape and np.abs(sig_f - sig_b).max() < 1e-4),
                           "checks_passed": rep["passed"], "checks_not_pass": bad}
                    np.save(o / "sig.npy", sig_f)
                    res.append(rec)
                    print(bench, name, route, r, f"wall={run['wall_s']:.2f}", rep["passed"], bad, flush=True)
    (S / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3)
