"""OBSERVE harness #139: elevation view -> model face assignment with abstain (research, not production).

Model side: Blender ortho ray-cast depth/normal per candidate outward normal (rays.py).
View side: DXF vectors inside each view, annotation layers removed, rasterised at fixture res.
Signals along the facade: roofline (top profile relative to max) and vertical-edge rhythm.
Usage:
  uv run --offline --extra cad python docs/research/autoresearch-view-face-harness/view_face.py --out C:/x/ev/r1
  [--blender <exe>] [--rounds 1]
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import ezdxf
from ezdxf import recover, path as ezpath

HERE = Path(__file__).resolve().parent
BLENDER = "C:/Program Files/Blender Foundation/Blender 4.4/blender.exe"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_dxf(p):
    try:
        return ezdxf.readfile(p)
    except ezdxf.DXFStructureError:
        doc, _ = recover.readfile(p)
        return doc


def segments(doc, layout, excl, unit):
    space = doc.modelspace() if layout == "Model" else doc.layouts.get(layout)
    rx = re.compile(excl, re.I)
    out = []

    def walk(ents, depth):
        for e in ents:
            lay = e.dxf.get("layer", "0")
            if rx.search(lay):
                continue
            t = e.dxftype()
            if t == "INSERT":
                if depth < 6:
                    try:
                        walk(list(e.virtual_entities()), depth + 1)
                    except Exception:
                        pass
            elif t in ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"):
                try:
                    pts = list(ezpath.make_path(e).flattening(distance=0.005 / unit))
                except Exception:
                    continue
                for a, b in zip(pts, pts[1:]):
                    out.append((a.x * unit, a.y * unit, b.x * unit, b.y * unit))
    walk(space, 0)
    return np.array(out, float).reshape(-1, 4)


def views_auto_gap_x(seg, gap):
    lo = np.minimum(seg[:, 0], seg[:, 2])
    hi = np.maximum(seg[:, 0], seg[:, 2])
    order = np.argsort(lo)
    groups, cur, cur_hi = [], [order[0]], hi[order[0]]
    for i in order[1:]:
        if lo[i] > cur_hi + gap:
            groups.append(cur)
            cur, cur_hi = [i], hi[i]
        else:
            cur.append(i)
            cur_hi = max(cur_hi, hi[i])
    groups.append(cur)
    return [seg[g] for g in groups if hi[g].max() - lo[g].min() > 3.0]


def raster_view(seg, res):
    x0, y0 = seg[:, [0, 2]].min(), seg[:, [1, 3]].min()
    x1, y1 = seg[:, [0, 2]].max(), seg[:, [1, 3]].max()
    W, H = int(math.ceil((x1 - x0) / res)) + 1, int(math.ceil((y1 - y0) / res)) + 1
    img = np.zeros((H, W), bool)
    vimg = np.zeros((H, W), bool)
    for xa, ya, xb, yb in seg:
        n = max(2, int(math.hypot(xb - xa, yb - ya) / (res / 2)) + 1)
        xs = ((np.linspace(xa, xb, n) - x0) / res).astype(int).clip(0, W - 1)
        ys = (H - 1 - ((np.linspace(ya, yb, n) - y0) / res).astype(int)).clip(0, H - 1)
        img[ys, xs] = True
        if abs(yb - ya) > 2 * abs(xb - xa):
            vimg[ys, xs] = True
    return img, vimg, (x0, x1)


def signals_from_masks(occ, vedge, res, tall_m=2.0):
    H = occ.shape[0]
    rows = np.where(occ.any(0), occ.argmax(0), H)
    top = (H - rows) * res  # height above raster bottom, 0 where empty
    rhythm = vedge.sum(0).astype(float)
    if TRIM:  # R1: span = first..last column whose top is >= tall_m above the raster bottom (drops ground lines)
        cols = np.where(top >= tall_m)[0]
        if len(cols):
            top, rhythm = top[cols[0]:cols[-1] + 1], rhythm[cols[0]:cols[-1] + 1]
    return top, rhythm


TRIM = True       # R1 (False = R0)
DEPTH_JUMP = 0.03  # R1 (R0 = 0.15)
FULL_BONUS = 0.15  # R2 (V4 only)


def model_signals(npz, az, res):
    key = f"az{int(round(az)) % 360:03d}"
    d = npz[key + "_depth"]
    nrm = npz[key + "_normal"]
    occ = np.isfinite(d)
    dd = np.where(occ, d, 1e6)
    jump = np.abs(np.diff(dd, axis=1)) > DEPTH_JUMP
    dot = (nrm[:, 1:] * nrm[:, :-1]).sum(-1)
    crease = (dot < math.cos(math.radians(30))) & occ[:, 1:] & occ[:, :-1]
    ve = np.zeros_like(occ)
    ve[:, 1:] |= jump | crease
    cols = np.where(occ.any(0))[0]
    occ, ve = occ[:, cols[0]:cols[-1] + 1], ve[:, cols[0]:cols[-1] + 1]
    return signals_from_masks(occ, ve, res)


def smooth(a, s=1.5):
    r = int(3 * s)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2)
    return np.convolve(a, k / k.sum(), mode="same")


def ncc(a, b):
    a, b = a - a.mean(), b - b.mean()
    den = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 1e-9 else 0.0


def slide(vt, vp, ft, fp, slack):
    Lv, Lf = len(vt), len(ft)
    if Lv > Lf + 2 * slack:
        return {"V1": -1.0, "V2": -1.0, "V3": -1.0, "off": None}
    pad = slack
    ftp = np.concatenate([np.zeros(pad), ft, np.zeros(pad)])
    fpp = np.concatenate([np.zeros(pad), fp, np.zeros(pad)])
    vt_rel = vt - vt.max()
    best = {"V1": -2.0, "V2": -2.0, "V3": -2.0, "off": None}
    offs = {}
    for o in range(0, Lf + 2 * pad - Lv + 1):
        wt = ftp[o:o + Lv]
        s1 = ncc(vt_rel, wt - wt.max())
        s2 = ncc(smooth(vp), smooth(fpp[o:o + Lv]))
        for k, s in (("V1", s1), ("V2", s2), ("V3", 0.5 * (s1 + s2))):
            if s > best[k]:
                best[k] = s
                offs[k] = o - pad
    best["off"] = offs
    return best


def decide(scores, gt, tau, smin, forbidden_pair=None):
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    (b, sb), (_, s2) = ranked[0], ranked[1]
    if sb < smin or sb - s2 < tau:
        return {"answer": None, "best": b, "score": round(sb, 4), "margin": round(sb - s2, 4), "outcome": "abstain"}
    return {"answer": b, "best": b, "score": round(sb, 4), "margin": round(sb - s2, 4),
            "outcome": "correct" if b == gt else "wrong"}


def decide_width(wv, widths, gt):
    e = {f: abs(wv - w) / w for f, w in widths.items()}
    r = sorted(e.items(), key=lambda kv: kv[1])
    if r[0][1] > 0.15 or r[1][1] - r[0][1] < 0.03:
        return {"answer": None, "best": r[0][0], "outcome": "abstain", "err": round(r[0][1], 4)}
    return {"answer": r[0][0], "best": r[0][0], "err": round(r[0][1], 4),
            "outcome": "correct" if r[0][0] == gt else "wrong"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender", default=BLENDER)
    ap.add_argument("--fixture", default=str(HERE / "fixture.json"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    fx = json.loads(Path(a.fixture).read_text(encoding="utf-8"))
    res, dec = fx["res_m"], fx["decision"]
    t0 = time.time()
    report = {"fixture_sha256": sha256(a.fixture), "inputs": {}, "views": [], "timing_s": {}}
    for name, f in fx["fixtures"].items():
        for k in ("dxf", "model"):
            h = sha256(f[k])
            if h != f[k + "_sha256"]:
                raise SystemExit(f"preflight: {name} {k} hash {h} != frozen {f[k + '_sha256']}")
            report["inputs"][f"{name}.{k}"] = {"path": f[k], "sha256": h}
        npz_path = out / f"{name}_rays.npz"
        t1 = time.time()
        r = subprocess.run([a.blender, "-b", "--factory-startup", "-P", str(HERE / "rays.py"), "--", f["model"],
                            str(npz_path), str(res), ",".join(str(z) for z in f["faces_az"])],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not npz_path.exists():
            raise SystemExit(f"rays failed for {name}: {r.stdout[-800:]} {r.stderr[-800:]}")
        report["timing_s"][f"{name}.rays"] = round(time.time() - t1, 2)
        npz = np.load(npz_path)
        faces = {az: model_signals(npz, az, res) for az in f["faces_az"]}
        widths = {az: len(s[0]) * res for az, s in faces.items()}
        t1 = time.time()
        doc = load_dxf(f["dxf"])
        seg = segments(doc, f["layout"], f["exclude_layers"], f["unit_m"])
        views = []
        if f["views"] == "auto_gap_x":
            for vs in views_auto_gap_x(seg, f["gap_mm"] * f["unit_m"]):
                xm = vs[:, [0, 2]].mean()
                gt = [(t, g[2]) for t, g in f["gt_by_axis_x_mm"].items()
                      if min(vs[:, [0, 2]].min(), 1e9) <= (g[0] + g[1]) / 2 * f["unit_m"] <= vs[:, [0, 2]].max()]
                views.append((gt[0][0] if len(gt) == 1 else f"unmatched@{xm:.1f}", gt[0][1] if len(gt) == 1 else None, vs))
        else:
            m = f["box_margin_mm"] * f["unit_m"]
            for t, (bx, by, bw, bh) in f["boxes_mm"].items():
                x0, y0, x1, y1 = bx * f["unit_m"] - m, by * f["unit_m"] - m, (bx + bw) * f["unit_m"] + m, (by + bh) * f["unit_m"] + m
                ins = ((seg[:, [0, 2]] >= x0) & (seg[:, [0, 2]] <= x1) & (seg[:, [1, 3]] >= y0) & (seg[:, [1, 3]] <= y1)).all(1)
                views.append((t, f["gt_az"][t], seg[ins]))
        report["timing_s"][f"{name}.dxf"] = round(time.time() - t1, 2)
        slack = int(round(dec["width_slack_m"] / res))
        pair = {0: 180, 180: 0, 90: 270, 270: 90}
        for title, gt, vs in views:
            if gt is None or len(vs) == 0:
                report["views"].append({"fixture": name, "title": title, "status": "not_measured", "segments": len(vs)})
                continue
            img, vimg, (vx0, vx1) = raster_view(vs, res)
            vt, vp = signals_from_masks(img, vimg, res)
            W = len(vt)
            cases = [("full", 0, W, False), ("mirror", 0, W, True)]
            for fr in fx["partials"]["fractions"]:
                L = max(5, int(round(fr * W)))
                for pos in fx["partials"]["positions"]:
                    a0 = int(round(pos * (W - L)))
                    cases.append((f"partial{int(fr * 100)}@{pos}", a0, L, False))
            for kind, a0, L, mir in cases:
                ct, cp = vt[a0:a0 + L], vp[a0:a0 + L]
                if mir:
                    ct, cp = ct[::-1], cp[::-1]
                per = {az: slide(ct, cp, ft, fp, slack) for az, (ft, fp) in faces.items()}
                row = {"fixture": name, "title": title, "gt_az": gt, "case": kind, "synthetic": kind != "full",
                       "view_width_m": round(L * res, 2), "segments": int(len(vs)),
                       "scores": {v: {str(az): round(per[az][v], 4) for az in per} for v in ("V1", "V2", "V3")},
                       "offset_m": {str(az): {k: (o * res if o is not None else None) for k, o in (per[az]["off"] or {}).items()} for az in per}}
                for v in ("V1", "V2", "V3"):
                    row[v] = decide({az: per[az][v] for az in per}, gt, dec["tau_margin"], dec["min_score"])
                    if name == "ac08" and row[v]["outcome"] == "wrong" and row[v]["answer"] == pair[gt]:
                        row[v]["outcome"] = "wrong_within_pair"
                # R2 / V4: full-face hypothesis - V3 + FULL_BONUS for faces whose width equals the view width (<= 5 %)
                s4 = {az: per[az]["V3"] + (FULL_BONUS if abs(L * res - widths[az]) / widths[az] <= 0.05 else 0.0) for az in per}
                row["scores"]["V4"] = {str(az): round(s, 4) for az, s in s4.items()}
                row["V4"] = decide(s4, gt, dec["tau_margin"], dec["min_score"])
                if name == "ac08" and row["V4"]["outcome"] == "wrong" and row["V4"]["answer"] == pair[gt]:
                    row["V4"]["outcome"] = "wrong_within_pair"
                row["V0"] = decide_width(L * res, widths, gt)
                report["views"].append(row)
    summ = {}
    for v in ("V0", "V1", "V2", "V3", "V4"):
        for cls in ("full", "partial", "mirror"):
            rows = [r for r in report["views"] if r.get("case", "").startswith(cls) and v in r]
            for fxn in sorted({r["fixture"] for r in rows}):
                rr = [r[v]["outcome"] for r in rows if r["fixture"] == fxn]
                n = len(rr)
                ans = [o for o in rr if o != "abstain"]
                summ[f"{v}.{cls}.{fxn}"] = {"n": n, "answered": len(ans), "correct": rr.count("correct"),
                                            "wrong": len(ans) - rr.count("correct"),
                                            "accuracy_answered": round(rr.count("correct") / len(ans), 4) if ans else None,
                                            "abstain_rate": round(1 - len(ans) / n, 4) if n else None}
    report["summary"] = summ
    report["widths_m"] = {}
    report["timing_s"]["total"] = round(time.time() - t0, 2)
    (out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, s in summ.items():
        print(k, s)
    print("RESULT", out / "result.json", "total_s", report["timing_s"]["total"])


if __name__ == "__main__":
    main()
