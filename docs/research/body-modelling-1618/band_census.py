"""Per-band facade census of body dumps (#1618). new-case: read-only etalon numbers for docs/research/body-modelling.md.

Usage: uv run python band_census.py DUMP.npz [DUMP.npz ...] --rot DEG --out REPORT.json
Bands by face-centre height above the mesh bottom: ground < 6.5 m, top = last 4 m, typical = the rest.
Classes by unit normal z: facade |nz| < 0.2, up > 0.8, down < -0.8, else sloped. A sliver is a triangle
with min angle < 5 deg. For typical facade faces also: faces with a side > 3.8 m and vertices with
valence >= 6 (edges of typical facade faces only). For each of the four facade directions (after
rotating by -DEG about Z) on its largest-area plane: distinct vertical-line positions and the count of
neighbouring positions closer than 3 cm (near-duplicate verticals). Refuses an output that is an input.
"""
import argparse
import json
import math
import os
import sys

import numpy as np


def faces_of(d):
    out, k, ji = [], 0, d["ji"]
    for c in d["jn"]:
        out.append(ji[k:k + c])
        k += c
    return out


def census(path, rot):
    d = np.load(path)
    JV = d["jverts"]
    faces = faces_of(d)
    if not faces:
        raise SystemExit(f"{path}: empty mesh")
    z0 = float(d["verts"][:, 2].min())
    H = float(d["verts"][:, 2].max()) - z0
    t = math.radians(-rot)
    R = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
    RV = JV @ R.T
    bands, over, edges, planes = {}, 0, {}, {}
    for fc in faces:
        P = JV[fc]
        c = len(fc)
        n = np.zeros(3)
        for i in range(c):
            n += np.cross(P[i], P[(i + 1) % c])
        a = np.linalg.norm(n) / 2
        if a == 0:
            continue
        n = n / (2 * a)
        zc = P[:, 2].mean() - z0
        cls = "facade" if abs(n[2]) < 0.2 else ("up" if n[2] > 0.8 else ("down" if n[2] < -0.8 else "sloped"))
        band = "ground" if zc < 6.5 else ("top" if zc > H - 4 else "typical")
        sliver = False
        if c == 3:
            angs = []
            for i in range(3):
                u, v = P[(i + 1) % 3] - P[i], P[(i + 2) % 3] - P[i]
                angs.append(math.degrees(math.acos(max(-1.0, min(1.0, u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12))))))
            sliver = min(angs) < 5
        b = bands.setdefault(f"{cls}/{band}", {"faces": 0, "tris": 0, "slivers": 0, "area_m2": 0.0})
        b["faces"] += 1
        b["tris"] += int(c == 3)
        b["slivers"] += int(sliver)
        b["area_m2"] += a
        if cls == "facade" and band == "typical":
            if max(np.linalg.norm(P[i] - P[(i + 1) % c]) for i in range(c)) > 3.8:
                over += 1
            for i in range(c):
                e = tuple(sorted((int(fc[i]), int(fc[(i + 1) % c]))))
                edges[e] = 1
        if cls == "facade":
            rn = R @ n
            ax = 0 if abs(rn[0]) > abs(rn[1]) else 1
            if abs(rn[ax]) > 0.99:
                key = ("p" if rn[ax] > 0 else "n") + "xy"[ax]
                depth = round(float(RV[fc][:, ax].mean()), 2)
                planes.setdefault(key, {}).setdefault(depth, []).append((a, fc, 1 - ax))
    val = {}
    for x, y in edges:
        val[x] = val.get(x, 0) + 1
        val[y] = val.get(y, 0) + 1
    v = np.array(list(val.values())) if val else np.zeros(0)
    near = {}
    for key, byd in planes.items():
        depth = max(byd, key=lambda k: sum(e[0] for e in byd[k]))
        us = np.unique(np.round(np.concatenate([RV[fc][:, other] for _, fc, other in byd[depth]]), 3))
        du = np.diff(us)
        near[key] = {"plane_area_m2": round(sum(e[0] for e in byd[depth]), 1), "vertical_lines": int(len(us)),
                     "near_duplicate_lt_3cm": int(((du > 0) & (du < 0.03)).sum())}
    for b in bands.values():
        b["area_m2"] = round(b["area_m2"], 1)
        b["tri_share"] = round(b["tris"] / b["faces"], 4)
    ft = bands.get("facade/typical", {"faces": 0})
    return {"object": os.path.basename(path)[:-4], "bands": bands,
            "facade_typical_side_over_3_8m": over, "facade_typical_faces": ft["faces"],
            "facade_typical_valence_ge6": int((v >= 6).sum()), "facade_typical_verts": int(len(v)),
            "main_planes": near}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("npz", nargs="+")
    ap.add_argument("--rot", type=float, default=0.0)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if any(os.path.abspath(a.out) == os.path.abspath(p) for p in a.npz) or not a.out.endswith(".json"):
        sys.exit("output must be a new .json, not an input")
    rep = [census(p, a.rot) for p in a.npz]
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    for r in rep:
        ft = r["bands"].get("facade/typical", {})
        print(r["object"], "facade/typical", ft.get("faces"), ft.get("tris"), ft.get("slivers"),
              "over3.8", r["facade_typical_side_over_3_8m"], "val>=6", r["facade_typical_valence_ge6"],
              {k: v["near_duplicate_lt_3cm"] for k, v in r["main_planes"].items()})


if __name__ == "__main__":
    main()
