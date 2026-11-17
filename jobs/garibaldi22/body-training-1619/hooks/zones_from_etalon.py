"""Hook `before` stage `body` (#1619 training polygon): finish zones (dark/light cladding) for a floor spec.

Pattern: n/a | new-case: finish-zone material IDs read from a delivered etalon's texture, projected on a floor spec.

uv run python zones_from_etalon.py FLOOR.json ETALON.npz DIFFUSE.png OUT.json --dz DZ [--mirror-x]
    [--palette palette.json] [--census] [--min-run 0.6] [--snap 0.15] [--max-dist 0.6] [--max-rms 0.35]

Why: D344 asks for dark/light cladding IDs "from the Revit materials", but the Revit FBX exports of G22 and site 63
carry no Material nodes (LayerElementMaterial only); the finish layout exists in Artem's delivered NPM texture.
ETALON.npz = docs/research/body-modelling-1618/dump_mesh.py output (verts, fn, fi, uvn, uvf). The etalon is cut at
the spandrel height of FLOOR.json (`contour_section_z` + DZ), every cut segment takes the texel colour at its UV;
the floor contour (x mirrored with --mirror-x) is registered to the cut by rotation search + ICP (fails above
--max-rms). Each 0.1 m of the contour takes the class of the nearest cut segment (palette nearest colour; a colour
farther than `tol` from every palette entry is an error naming it). Runs shorter than --min-run join their
neighbour (a panel joint is texture, D344); a zone border within --snap of an existing cut reuses that cut (BM-09).
Writes OUT.json = FLOOR.json + ring zones + materials + `zones_report`; --census prints the colour clusters only.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image
from shapely.geometry import LineString, Point

PALETTE = {"tol": 40, "classes": {}}


def etalon_cut(d, z, img):
    v = d["verts"]
    fi = d["fi"].reshape(-1, 3) if (d["fn"] == 3).all() else None
    if fi is None:
        sys.exit("refused: etalon must be triangulated (fn == 3)")
    uv = d["uvf"].reshape(-1, 3, 2)
    # drop small closed shells (AC baskets, canopies: inset elements, BM-04) - their faces are not cladding
    par = np.arange(len(v))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for f in fi:
        r0 = find(f[0])
        for j in f[1:]:
            rj = find(j)
            if rj != r0:
                par[rj] = r0
    roots = np.array([find(i) for i in range(len(v))])
    comp = roots[fi[:, 0]]
    lo = np.full((len(v), 3), np.inf)
    hi = np.full((len(v), 3), -np.inf)
    vr = roots
    np.minimum.at(lo, vr, v)
    np.maximum.at(hi, vr, v)
    span = hi[comp] - lo[comp]
    small = (span[:, 0] < 2.5) & (span[:, 1] < 2.5) & (span[:, 2] < 3.0)
    d_small = int(small.sum())
    t = v[fi]
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    vert = (np.abs(n[:, 2]) < 0.3 * np.linalg.norm(n, axis=1)) & ~small
    dz = t[:, :, 2] - z
    hit = vert & (dz.min(1) < 0) & (dz.max(1) > 0)
    W, H = img.size
    px = np.asarray(img.convert("RGB"))
    segs = []
    for k in np.nonzero(hit)[0]:
        pts, uvs = [], []
        for i in range(3):
            j = (i + 1) % 3
            a, b = dz[k, i], dz[k, j]
            if (a < 0) != (b < 0):
                u = a / (a - b)
                pts.append(t[k, i, :2] + u * (t[k, j, :2] - t[k, i, :2]))
                uvs.append(uv[k, i] + u * (uv[k, j] - uv[k, i]))
        if len(pts) != 2 or np.linalg.norm(pts[1] - pts[0]) < 1e-3:
            continue
        um = (uvs[0] + uvs[1]) / 2
        x = min(W - 1, int((um[0] % 1.0) * W))
        y = min(H - 1, int((1 - (um[1] % 1.0)) * H))
        segs.append((pts[0], pts[1], px[y, x].astype(int)))
    return segs, d_small


def register(src, dst, max_rms):
    """Rigid 2D registration src -> dst (rotation search on centroids, then ICP)."""
    cs, cd = src.mean(0), dst.mean(0)
    best = None
    for deg in np.arange(0, 360, 1.0):
        r = math.radians(deg)
        R = np.array([[math.cos(r), -math.sin(r)], [math.sin(r), math.cos(r)]])
        p = (src - cs) @ R.T + cd
        e = np.sqrt(((p[:, None, :] - dst[None, ::3, :]) ** 2).sum(-1)).min(1).mean()
        if best is None or e < best[0]:
            best = (e, R, cd - cs @ R.T)
    _, R, T = best
    for _ in range(40):
        p = src @ R.T + T
        dd = ((p[:, None, :] - dst[None, :, :]) ** 2).sum(-1)
        q = dst[dd.argmin(1)]
        keep = dd.min(1) < np.percentile(dd.min(1), 90)
        a, b = src[keep], q[keep]
        ma, mb = a.mean(0), b.mean(0)
        U, _, Vt = np.linalg.svd((a - ma).T @ (b - mb))
        R = (U @ Vt).T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = (U @ Vt).T
        T = mb - ma @ R.T
    p = src @ R.T + T
    rms = float(np.median(np.sqrt(((p[:, None, :] - dst[None, :, :]) ** 2).sum(-1).min(1))))
    if not math.isfinite(rms) or rms > max_rms:
        sys.exit("refused: contour does not register to the etalon cut (median %.3f m > %.3f)" % (rms, max_rms))
    return R, T, rms


def _plot(path, p, segs, zones_xy=None):
    from PIL import ImageDraw
    allp = np.concatenate([p] + [np.array([s[0], s[1]]) for s in segs])
    lo, hi = allp.min(0) - 2, allp.max(0) + 2
    S = 8.0
    W, H = int((hi[0] - lo[0]) * S), int((hi[1] - lo[1]) * S)
    im = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    f = lambda q: ((q[0] - lo[0]) * S, H - (q[1] - lo[1]) * S)
    for s in segs:
        dr.line([f(s[0]), f(s[1])], fill=tuple(int(c) for c in s[2]), width=5)
    dr.line([f(q) for q in p], fill=(255, 0, 0), width=1)
    im.save(path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("floor")
    ap.add_argument("etalon")
    ap.add_argument("diffuse")
    ap.add_argument("out")
    ap.add_argument("--dz", type=float, required=True, help="etalon z = source z + dz")
    ap.add_argument("--mirror-x", action="store_true")
    ap.add_argument("--palette")
    ap.add_argument("--census", action="store_true")
    ap.add_argument("--min-run", type=float, default=0.6)
    ap.add_argument("--snap", type=float, default=0.15)
    ap.add_argument("--max-dist", type=float, default=0.6)
    ap.add_argument("--max-rms", type=float, default=0.35, help="max median registration distance, m")
    ap.add_argument("--debug", help="PNG: registered contour (red) over the coloured etalon cut")
    a = ap.parse_args(argv)
    ins = {os.path.realpath(p) for p in (a.floor, a.etalon, a.diffuse)}
    if os.path.realpath(a.out) in ins or not a.out.endswith(".json"):
        sys.exit("refused: output must be a new .json, not an input")
    spec = json.load(open(a.floor, encoding="utf-8"))
    d = np.load(a.etalon)
    segs, inset_tris = etalon_cut(d, float(spec["contour_section_z"]) + a.dz, Image.open(a.diffuse))
    if len(segs) < 10:
        sys.exit("refused: etalon cut at z=%.2f has %d segments" % (spec["contour_section_z"] + a.dz, len(segs)))
    cols = np.array([s[2] for s in segs])
    lens = np.array([np.linalg.norm(s[1] - s[0]) for s in segs])
    if a.census:
        q = (cols // 16) * 16
        keys, inv = np.unique(q, axis=0, return_inverse=True)
        w = np.bincount(inv.ravel(), weights=lens)
        for i in np.argsort(-w)[:12]:
            print("colour~", keys[i].tolist(), "m", round(float(w[i]), 1))
        return
    pal = json.load(open(a.palette, encoding="utf-8")) if a.palette else PALETTE
    names = list(pal["classes"])
    if not names:
        sys.exit("refused: empty palette (run --census, then pass --palette)")
    pc = np.array([pal["classes"][n] for n in names], dtype=float)
    dist = np.linalg.norm(cols[:, None, :] - pc[None], axis=2)
    seg_cls = dist.argmin(1)
    bad = dist.min(1) > pal["tol"]
    if (lens[bad].sum() > 0.02 * lens.sum()):
        worst = cols[bad][np.argmax(lens[bad])].tolist()
        sys.exit("refused: unmapped colour %s on %.1f m of the cut (palette tol %s)" % (worst, lens[bad].sum(), pal["tol"]))
    ring = spec["rings"][0]
    xy = np.array(ring["xy"], dtype=float)
    if len(xy) < 3 or not np.isfinite(xy).all():
        sys.exit("refused: ring 0 contour needs >= 3 finite vertices")
    ext = LineString(list(map(tuple, xy)) + [tuple(xy[0])])
    perim = ext.length
    ss = np.arange(0.05, perim, 0.1)
    pts = np.array([ext.interpolate(s).coords[0] for s in ss])
    src = pts * np.array([-1.0, 1.0]) if a.mirror_x else pts
    # uniform 0.25 m samples along the cut (the centroid must weight metres, not triangles)
    dense = np.concatenate([np.array(s[0])[None] + np.linspace(0, 1, max(2, int(np.linalg.norm(s[1] - s[0]) / 0.25) + 1))[:, None]
                            * (np.array(s[1]) - np.array(s[0]))[None] for s in segs]).reshape(-1, 2)
    step = max(1, len(dense) // 3000)
    R, T, rms = register(src[::5], dense[::step], a.max_rms)
    p = src @ R.T + T
    if a.debug:
        _plot(a.debug, p, segs)
    # point-to-segment distance (a long etalon triangle's midpoint can be farther than a short neighbour's)
    A = np.array([s[0] for s in segs])[None]
    B = np.array([s[1] for s in segs])[None]
    AB = B - A
    tt = np.clip((((p[:, None, :] - A) * AB).sum(-1)) / np.maximum((AB ** 2).sum(-1), 1e-12), 0, 1)
    dd = np.sqrt(((p[:, None, :] - (A + tt[..., None] * AB)) ** 2).sum(-1))
    near = dd.argmin(1)
    cls = np.where(dd.min(1) <= a.max_dist, seg_cls[near], -1)
    # fill unknown samples from the neighbour (recesses not on the etalon cut), then merge short runs
    known = np.nonzero(cls >= 0)[0]
    if not len(known):
        sys.exit("refused: no contour sample within %.2f m of the etalon cut" % a.max_dist)
    unknown_m = float((cls < 0).sum() * 0.1)
    for i in np.nonzero(cls < 0)[0]:
        cls[i] = cls[known[np.abs(known - i).argmin()]]
    runs = []
    for i, c in enumerate(cls):
        if runs and runs[-1][2] == c:
            runs[-1][1] = i + 1
        else:
            runs.append([i, i + 1, int(c)])
    changed = True
    while changed and len(runs) > 1:
        changed = False
        k = min(range(len(runs)), key=lambda j: runs[j][1] - runs[j][0])
        if (runs[k][1] - runs[k][0]) * 0.1 < a.min_run:
            nb = runs[k - 1] if k > 0 else runs[k + 1]
            if k > 0:
                runs[k - 1][1] = runs[k][1]
            else:
                runs[k + 1][0] = runs[k][0]
            del runs[k]
            merged = []
            for r in runs:
                if merged and merged[-1][2] == r[2]:
                    merged[-1][1] = r[1]
                else:
                    merged.append(r)
            runs = merged
            changed = True
    cuts = list(ring.get("cuts", []))
    corner_s = [ext.project(Point(c)) for c in xy]
    zones, new_cuts, snapped = [], 0, 0
    bounds = [0.0] + [r[0] * 0.1 for r in runs[1:]] + [perim]
    for k, r in enumerate(runs):
        s0, s1 = bounds[k], bounds[k + 1]
        zones.append([round(s0, 4), round(s1, 4), "WALL_" + names[r[2]]])
    for k in range(1, len(bounds) - 1):
        b = bounds[k]
        cand = [c for c in cuts + corner_s if abs(c - b) <= a.snap]
        if cand:
            nb = min(cand, key=lambda c: abs(c - b))
            zones[k - 1][1] = zones[k][0] = round(nb, 4)
            snapped += 1
        else:
            cuts.append(round(b, 4))
            new_cuts += 1
    ring["cuts"] = sorted(set(round(c, 4) for c in cuts))
    ring["zones"] = zones
    mats = dict(spec["materials"])
    mats.pop("WALL_A", None)
    for n in names:
        mats["WALL_" + n] = [round(c / 255.0, 3) for c in pal["classes"][n]]
    spec["materials"] = mats
    spec["zones_report"] = {
        "source": "etalon texture (Revit FBX has no materials)", "etalon": os.path.basename(a.etalon),
        "diffuse": os.path.basename(a.diffuse), "dz": a.dz, "mirror_x": a.mirror_x, "register_rms_m": round(rms, 3),
        "cut_segments": len(segs), "etalon_inset_tris_skipped": inset_tris, "unknown_m_filled": round(unknown_m, 1), "zones": len(zones),
        "zone_m": {("WALL_" + n): round(sum(z[1] - z[0] for z in zones if z[2] == "WALL_" + n), 1) for n in names},
        "borders_snapped_to_existing_cut": snapped, "borders_new_cut": new_cuts,
    }
    with open(a.out, "x", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=1)
    print(json.dumps(spec["zones_report"], ensure_ascii=False))


if __name__ == "__main__":
    main()
