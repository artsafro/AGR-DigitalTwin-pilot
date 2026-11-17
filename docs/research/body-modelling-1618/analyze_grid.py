"""Grid census of the body etalon dumps (#1618). new-case: read-only body-grid metrics for the research doc.

Usage: uv run python analyze_grid.py DUMP_DIR [DUMP_DIR...] --out REPORT.json
Reads the npz written by dump_mesh.py; writes one JSON report (never into a DUMP_DIR input file).
Metrics (definitions also in docs/research/body-modelling.md, section "Измерения"):
  quad_share       rejoined quads / rejoined faces (coplanar 1 deg pairs only, see dump_mesh.py)
  residual_tris    triangles left after rejoin = diagonals the grid needs
  slivers          triangles with min angle < 5 deg or longest/shortest-height aspect > 20
  ngons            rejoined faces with > 4 sides (only coplanar rejoin -> should be 0)
  z_levels         vertex Z clustered at 1 cm with >= 1 % of vertices: the horizontal loops
  azimuth_families facade normal azimuths (1 deg bins) -> main walls vs curved (rounded) sets
  components       connected shells (inset elements vs body)
  max_side_m       longest edge per face, share over 3.8 m (4096 tile, #1616)
"""
import argparse
import json
import math
import os
import sys

import numpy as np


def unpack(n, i):
    out, k = [], 0
    for c in n:
        out.append(i[k:k + c].tolist())
        k += c
    return out


def tri_angles(p):
    a, b, c = p
    def ang(x, y, z):
        u, v = y - x, z - x
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if nu == 0 or nv == 0:
            return 0.0
        return math.degrees(math.acos(max(-1.0, min(1.0, float(u @ v / nu / nv)))))
    return ang(a, b, c), ang(b, c, a), ang(c, a, b)


def components(nverts, faces):
    parent = list(range(nverts))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for f in faces:
        r = find(f[0])
        for v in f[1:]:
            s = find(v)
            if s != r:
                parent[s] = r
    roots = {}
    for f in faces:
        roots.setdefault(find(f[0]), []).append(f)
    return list(roots.values())


def analyse(path):
    d = np.load(path)
    V, JV = d["verts"], d["jverts"]
    jf = unpack(d["jn"], d["ji"])
    if not jf:
        raise SystemExit(f"{path}: empty mesh")
    sizes = np.array([len(f) for f in jf])
    res = {"object": os.path.basename(path)[:-4], "tris_exported": int(len(d["fn"])), "verts": int(len(V)),
           "rejoined_faces": int(len(jf)), "quads": int((sizes == 4).sum()),
           "residual_tris": int((sizes == 3).sum()), "ngons": int((sizes > 4).sum())}
    res["quad_share"] = round(res["quads"] / len(jf), 4)
    # normals / areas of rejoined faces
    normals, areas, maxside, cent = [], [], [], []
    slivers, sliver_cent = 0, []
    for f in jf:
        P = JV[f]
        n = np.zeros(3)
        for k in range(len(P)):
            n += np.cross(P[k], P[(k + 1) % len(P)])
        a = np.linalg.norm(n) / 2
        normals.append(n / (2 * a) if a > 0 else n)
        areas.append(a)
        sides = [np.linalg.norm(P[k] - P[(k + 1) % len(P)]) for k in range(len(P))]
        maxside.append(max(sides))
        cent.append(P.mean(0))
        if len(f) == 3:
            mn = min(tri_angles(P))
            h = 2 * a / max(sides) if max(sides) > 0 else 0
            if mn < 5 or (h > 0 and max(sides) / h > 20) or h == 0:
                slivers += 1
                sliver_cent.append(P.mean(0))
    N, A, MS, C = np.array(normals), np.array(areas), np.array(maxside), np.array(cent)
    res["area_m2"] = round(float(A.sum()), 1)
    res["slivers"] = slivers
    res["max_side_m"] = round(float(MS.max()), 2)
    res["faces_side_over_3_8m"] = int((MS > 3.8).sum())
    res["edge_len_p50_p90_m"] = [round(float(np.percentile(MS, q)), 2) for q in (50, 90)]
    # orientation classes
    nz = N[:, 2]
    facade = np.abs(nz) < 0.2
    res["faces_facade"] = int(facade.sum())
    res["faces_up"] = int((nz > 0.8).sum())
    res["faces_down"] = int((nz < -0.8).sum())
    res["faces_sloped"] = int(len(N) - facade.sum() - (np.abs(nz) > 0.8).sum())
    # residual triangles by class
    tri = sizes == 3
    res["residual_tris_facade"] = int((tri & facade).sum())
    res["residual_tris_up"] = int((tri & (nz > 0.8)).sum())
    res["residual_tris_down"] = int((tri & (nz < -0.8)).sum())
    # azimuth families on facades (area weighted)
    az = (np.degrees(np.arctan2(N[facade, 1], N[facade, 0])) + 360) % 360
    hist = np.bincount(np.round(az).astype(int) % 360, weights=A[facade], minlength=360)
    fam = [(int(i), round(float(hist[i]), 1)) for i in np.argsort(hist)[::-1] if hist[i] > 0]
    total = hist.sum()
    main = [f for f in fam if f[1] >= 0.02 * total]
    res["facade_azimuth_main"] = main[:12]
    res["facade_azimuths_nonzero_bins"] = len(fam)
    res["facade_area_off_main_share"] = round(1 - sum(f[1] for f in main) / total, 4) if total else None
    # Z levels (vertex clustering 1 cm)
    z = np.round(V[:, 2] / 0.01).astype(int)
    vals, cnt = np.unique(z, return_counts=True)
    lv = [(round(v * 0.01, 2), int(c)) for v, c in zip(vals, cnt) if c >= 0.01 * len(V)]
    res["z_levels_1pct"] = lv
    res["z_distinct_1cm"] = int(len(vals))
    # components
    comps = components(len(JV), jf)
    csz = sorted((len(c) for c in comps), reverse=True)
    res["components"] = len(comps)
    res["component_faces_top5"] = csz[:5]
    res["components_le_12_faces"] = int(sum(1 for c in csz if c <= 12))
    # valence of rejoined mesh
    edges = {}
    for f in jf:
        for k in range(len(f)):
            e = tuple(sorted((f[k], f[(k + 1) % len(f)])))
            edges[e] = edges.get(e, 0) + 1
    val = np.zeros(len(JV), dtype=int)
    for a, b in edges:
        val[a] += 1
        val[b] += 1
    vv, vc = np.unique(val[val > 0], return_counts=True)
    res["valence_hist"] = {int(a): int(b) for a, b in zip(vv, vc)}
    res["open_edges"] = int(sum(1 for c in edges.values() if c == 1))
    res["nonmanifold_edges"] = int(sum(1 for c in edges.values() if c > 2))
    res["bbox"] = [[round(float(x), 2) for x in V.min(0)], [round(float(x), 2) for x in V.max(0)]]
    # UV: share of faces in [0,1] and distinct UV cells of 1/8 (atlas modules)
    uvf = d["uvf"]
    if len(uvf):
        res["uv_out_of_0_1"] = int(((uvf < -1e-4) | (uvf > 1 + 1e-4)).any(1).sum())
    if sliver_cent:
        res["sliver_centres_sample"] = [[round(float(x), 2) for x in c] for c in sliver_cent[:20]]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    outp = os.path.abspath(a.out)
    for dd in a.dirs:
        if outp.startswith(os.path.abspath(dd) + os.sep) and outp.endswith(".npz"):
            sys.exit("output must not be an input file")
    rep = []
    for dd in a.dirs:
        files = sorted(f for f in os.listdir(dd) if f.endswith(".npz"))
        if not files:
            sys.exit(f"{dd}: no npz dumps")
        for f in files:
            rep.append(analyse(os.path.join(dd, f)))
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    for r in rep:
        print(json.dumps({k: r[k] for k in r if k not in ("z_levels_1pct", "sliver_centres_sample")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
