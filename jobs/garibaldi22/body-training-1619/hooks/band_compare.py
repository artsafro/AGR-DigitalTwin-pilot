"""Hook `after` stage `body` (#1619 training polygon): crop a dump to the typical band and count its grid.

Pattern: n/a | new-case: typical-band crop + grid census for body vs etalon comparison (feeds #1616 metric).

uv run python band_compare.py DUMP.npz ZMIN ZMAX OUT_PREFIX [--step 3.0]

DUMP.npz = docs/research/body-modelling-1618/dump_mesh.py output (rejoined quads `jverts/jn/ji`). Keeps faces
whose every vertex lies in [ZMIN, ZMAX] (1 cm slack). Writes OUT_PREFIX.mq.json (input of
tools/qa/mesh_quality_score.py) and OUT_PREFIX.band.json: facade quad share and slivers (tri min angle < 5 deg,
as #1618), horizontal loops per floor (z levels holding >= 20 % of the vertices of the busiest level), vertices per
loop level (module repeat, BM-10), valence >= 6 share, faces with a side > 3.8 m, shells. Fails closed on an empty
crop or non-finite vertices; refuses outputs equal to the input.
"""
import argparse
import collections
import json
import math
import os
import sys

import numpy as np


def faces_of(d):
    out, k, ji = [], 0, d["ji"]
    for c in d["jn"]:
        out.append([int(i) for i in ji[k:k + c]])
        k += c
    return out


def min_angle(p):
    angs = []
    n = len(p)
    for i in range(n):
        a, b, c = p[i - 1], p[i], p[(i + 1) % n]
        u, v = a - b, c - b
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if nu < 1e-9 or nv < 1e-9:
            return 0.0
        angs.append(math.degrees(math.acos(max(-1.0, min(1.0, float(u @ v / nu / nv))))))
    return min(angs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("zmin", type=float)
    ap.add_argument("zmax", type=float)
    ap.add_argument("out_prefix")
    ap.add_argument("--step", type=float, default=3.0)
    a = ap.parse_args(argv)
    outs = [a.out_prefix + ".mq.json", a.out_prefix + ".band.json"]
    if any(os.path.realpath(o) == os.path.realpath(a.dump) for o in outs) or not a.zmax > a.zmin:
        sys.exit("refused: outputs equal the input or empty z range")
    d = np.load(a.dump)
    v = d["jverts"]
    if not np.isfinite(v).all():
        sys.exit("non-finite vertices")
    faces = [f for f in faces_of(d) if all(a.zmin - 0.01 <= v[i, 2] <= a.zmax + 0.01 for i in f)]
    if not faces:
        sys.exit("empty crop")
    used = sorted({i for f in faces for i in f})
    remap = {o: n for n, o in enumerate(used)}
    vv = v[used]
    ff = [[remap[i] for i in f] for f in faces]
    with open(outs[0], "x", encoding="utf-8") as fh:
        json.dump({"objects": [{"name": "band", "verts": vv.round(6).tolist(), "faces": ff,
                                "materials": ["M"] * len(ff)}], "dropped": []}, fh)
    fac, fac_tri, sliv, long_side = 0, 0, 0, 0
    edges = collections.Counter()
    for f in ff:
        p = vv[f]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        if np.linalg.norm(n) < 1e-12:
            continue
        n = n / np.linalg.norm(n)
        if abs(n[2]) >= 0.2:
            continue
        fac += 1
        if len(f) == 3:
            fac_tri += 1
            if min_angle(p) < 5:
                sliv += 1
        if max(np.linalg.norm(p[i] - p[i - 1]) for i in range(len(f))) > 3.8:
            long_side += 1
        for i in range(len(f)):
            edges[tuple(sorted((f[i - 1], f[i])))] += 1
    val = collections.Counter()
    for e in edges:
        val[e[0]] += 1
        val[e[1]] += 1
    zc = collections.Counter(np.round(vv[:, 2], 2).tolist())
    busiest = max(zc.values())
    loop_levels = sorted(z for z, c in zc.items() if c >= 0.2 * busiest)
    floors = max(1, round((a.zmax - a.zmin) / a.step))
    # shells (connected components by shared vertices)
    par = list(range(len(vv)))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for f in ff:
        for i in f[1:]:
            par[find(i)] = find(f[0])
    shells = len({find(i) for f in ff for i in f})
    rep = {"dump": os.path.basename(a.dump), "zmin": a.zmin, "zmax": a.zmax, "floors": floors,
           "faces": len(ff), "verts": len(vv), "facade_faces": fac, "facade_tris": fac_tri,
           "facade_quad_share": round(1 - fac_tri / fac, 4) if fac else None,
           "facade_slivers_lt5": sliv, "facade_sliver_share": round(sliv / fac, 4) if fac else None,
           "facade_faces_side_gt_3_8m": long_side,
           "valence_ge6_share": round(sum(1 for c in val.values() if c >= 6) / max(1, len(val)), 4),
           "loop_levels": len(loop_levels), "loops_per_floor": round(len(loop_levels) / floors, 2),
           "verts_per_loop_level": sorted(collections.Counter(zc[z] for z in loop_levels).items()),
           "shells": shells}
    with open(outs[1], "x", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print(json.dumps(rep))


if __name__ == "__main__":
    main()
