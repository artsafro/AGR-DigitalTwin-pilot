"""#141 OBSERVE run: OBR22 K02 raster elevations (PDF p14-15) -> accepted NPM v012 faces.

Usage (repo root): uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-raster/run.py <out_dir>
<out_dir> [R1|R2] ; <out_dir> must not exist. Writes result.json (+ rays.npz) there. Fresh Blender ray cast and PDF read every run.
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score  # noqa: E402
import sheet  # noqa: E402

FIX = json.loads((HERE / "fixture.json").read_text(encoding="utf-8"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def preflight():
    got = {k: sha(FIX["inputs"][k]["path"]) for k in FIX["inputs"]}
    bad = {k: v for k, v in got.items() if v != FIX["inputs"][k]["sha256"]}
    if bad:
        raise SystemExit(f"preflight hash mismatch: {bad}")
    return got


def model_faces(npz):
    z = np.load(npz)
    faces = {}
    for az in FIX["faces_az"]:
        hit = z[f"az{az:03d}_hit"]
        rows = (hit > 0).any(axis=1)
        faces[az] = {"profile": (hit[rows] == 2).mean(axis=0), "width_m": round(hit.shape[1] * sheet.RES, 2),
                     "window_px": int((hit == 2).sum())}
    return faces


VARIANT = {"R1": {"max_run_px": None, "min_density": None},
           "R2": {"max_run_px": 25, "min_density": 0.02}}  # R2 frozen after R1 (post-hoc, in-sample)
RV = VARIANT["R1"]


def judge(profile, width_m, faces, gt):
    if RV["min_density"] is not None and float(np.mean(profile)) < RV["min_density"]:
        c = {"answer": None, "outcome": "abstain", "reason": "low_window_evidence",
             "density": round(float(np.mean(profile)), 4)}
        v0 = score.decide_width(width_m, {az: f["width_m"] for az, f in faces.items()}, gt)
        return {"C": c, "V0": v0}
    per = {az: score.slide(profile, f["profile"]) for az, f in faces.items()}
    c = score.decide({az: s for az, (s, _) in per.items()}, gt)
    c["scores"] = {str(az): round(s, 4) for az, (s, _) in per.items()}
    c["offset_px"] = {str(az): o for az, (_, o) in per.items()}
    v0 = score.decide_width(width_m, {az: f["width_m"] for az, f in faces.items()}, gt)
    return {"C": c, "V0": v0}


def main():
    global RV
    out = Path(sys.argv[1])
    variant = sys.argv[2] if len(sys.argv) > 2 else "R1"
    RV = VARIANT[variant]
    if out.exists():
        raise SystemExit(f"{out} exists")
    out.mkdir(parents=True)
    t0 = time.time()
    hashes = preflight()
    npz = out / "rays.npz"
    cmd = [FIX["blender"]["path"], "-b", "--factory-startup", FIX["inputs"]["model"]["path"], "-P",
           str(HERE / "rays_win.py"), "--", str(npz), str(sheet.RES), ",".join(str(a) for a in FIX["faces_az"])]
    t1 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    t_rays = time.time() - t1
    if r.returncode != 0 or not npz.exists():
        raise SystemExit(f"blender failed rc={r.returncode}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    log = [ln for ln in r.stdout.splitlines() if ln.startswith("RAYS")]
    faces = model_faces(npz)
    cases, sheets = [], {}
    for pg in FIX["pages"]:
        s = sheet.read_sheet(FIX["inputs"]["pdf"]["path"], pg["index"], FIX["clip_pt"], RV["max_run_px"])
        sheets[pg["index"]] = {"m_per_pt": round(s["m_per_pt"], 6), "level_marks": s["level_marks"],
                               "views": [{k: v[k] for k in ("box_px", "width_m", "height_m", "body_rows")} for v in s["views"]]}
        if len(s["views"]) != len(pg["views"]):
            raise SystemExit(f"page {pg['index']}: {len(s['views'])} views, expected {len(pg['views'])}")
        for v, meta in zip(s["views"], pg["views"]):
            gt, vid = meta["gt_az"], meta["id"]
            crop = v["crop"]
            cases.append({"id": f"{vid}/full", "kind": "full", "view": vid, "gt": gt, "width_m": v["width_m"],
                          **judge(v["profile"], v["width_m"], faces, gt)})
            w = crop.shape[1]
            for frac in FIX["partials"]["fractions"]:
                cw = int(round(w * frac))
                for pos in FIX["partials"]["positions"]:
                    a = int(round((w - cw) * pos))
                    prof, _ = sheet.view_profile(crop[:, a:a + cw], RV["max_run_px"])
                    cases.append({"id": f"{vid}/crop{frac}@{pos}", "kind": "crop", "view": vid, "gt": gt,
                                  "width_m": round(cw * sheet.RES, 2), **judge(prof, cw * sheet.RES, faces, gt)})
            flipped = crop[:, ::-1]
            changed = int((flipped != crop).sum())
            prof, _ = sheet.view_profile(flipped, RV["max_run_px"])
            row = {"id": f"{vid}/mirror", "kind": "mirror", "view": vid, "gt": gt, "changed_px": changed,
                   "width_m": v["width_m"]}
            row.update(judge(prof, v["width_m"], faces, gt) if changed else {"status": "not_exercised"})
            cases.append(row)
    summary = {}
    for var in ("C", "V0"):
        for kind in ("full", "crop", "mirror"):
            for grp, views in (("long", FIX["long_views"]), ("short", FIX["short_views"])):
                sel = [c for c in cases if c["kind"] == kind and c["view"] in views and var in c]
                k = f"{var}/{kind}/{grp}"
                summary[k] = {o: sum(c[var]["outcome"] == o for c in sel) for o in ("correct", "wrong", "abstain")}
                summary[k]["n"] = len(sel)
    res = {"schema": "view-face-raster-run/1", "variant": variant, "variant_params": RV, "hashes": hashes, "rays_log": log,
           "faces": {str(a): {k: f[k] for k in ("width_m", "window_px")} for a, f in faces.items()},
           "sheets": sheets, "summary": summary, "cases": cases,
           "wall_s": {"rays": round(t_rays, 3), "total": round(time.time() - t0, 3)},
           "postflight": {k: sha(FIX["inputs"][k]["path"]) for k in FIX["inputs"]}}
    if res["postflight"] != hashes:
        raise SystemExit("postflight hash mismatch")
    (out / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"summary": summary, "wall_s": res["wall_s"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
