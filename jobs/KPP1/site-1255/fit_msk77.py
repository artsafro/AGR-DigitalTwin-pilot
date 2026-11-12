"""new-case: KPP1 MSK-77 placement by rigid fit to the customer's NPM 0607_77_05_0009005_117_02 (#1255).

uv run python jobs/KPP1/site-1255/fit_msk77.py <dump-theirs.npz> <dump-ours.npz> <zero_abs> <out.json>

Inputs: dumps from dump_vertices.py (Blender Z-up; for the customer FBX X = MSK y east, Y = MSK x north, as in
jobs/elv-tc-vpm/scripts/package_vpm_v006.py). Ours is local (0.000 at z = 0). The vertical offset is FIXED by the
user decision (zero mark 171.050 from Revit); only the plan transform is fitted:
    p_msk_blender = R(theta) p_ours + t,   z_abs = z_ours + zero_abs.
Method: plan sections of both meshes at heights where both have walls (SECTIONS, ours above 0.000); each section is
rasterised at RES m, flooded from outside, and its OUTER contour kept (the customer's NPM is an outer shell, ours
has inner faces and glazing, so only the outer contour is comparable). 2D ICP (trimmed, SVD; contours subsampled
to 0.10 / 0.05 m) from the 4 axis-aligned orientations of the min-area rectangles; every start is reported, so a
second solution is visible. Residual (`best.full`) = exact nearest distance of ALL our outer contour points to
theirs after the fit (median / p90 / share <= 0.05 m); distances below RES are not resolved.
Fail-closed: empty section, NaN/inf input, non-finite zero, an existing output or output == input -> SystemExit.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SECTIONS = (1.5, 2.3)       # m above 0.000 (ours): walls and glazing, below the canopy / roof edges
RES = 0.02                  # raster cell, m (residuals below RES are not resolved)
CLOSE_M = 1.5               # closing half-width, m: door gaps up to 3 m are bridged (both models alike)
STARTS = (0.0, 90.0, 180.0, 270.0)
TOL = 0.05                  # user decision: a fit residual above 0.05 m is ambiguous -> stop


class NN:
    """Exact nearest neighbour without scipy: grid buckets (cell CELL m), rings searched until the bound holds."""

    CELL = 0.25

    def __init__(self, pts):
        self.pts = np.asarray(pts, float)
        self.lo = self.pts.min(0)
        keys = np.floor((self.pts - self.lo) / self.CELL).astype(np.int64)
        buckets = {}
        for i, k in enumerate(map(tuple, keys.tolist())):
            buckets.setdefault(k, []).append(i)
        self.buckets = {k: np.array(v) for k, v in buckets.items()}
        self.extent = int(np.ceil(np.ptp(self.pts, 0).max() / self.CELL)) + 2

    def _one(self, q):
        c = np.floor((q - self.lo) / self.CELL).astype(np.int64).tolist()
        best_d, best_i, ring = math.inf, -1, 0
        while ring <= self.extent + max(abs(c[0]), abs(c[1])):
            cand = [self.buckets[(c[0] + dx, c[1] + dy)]
                    for dx in range(-ring, ring + 1) for dy in range(-ring, ring + 1)
                    if max(abs(dx), abs(dy)) == ring and (c[0] + dx, c[1] + dy) in self.buckets]
            if cand:
                idx = np.concatenate(cand)
                d = np.hypot(*(self.pts[idx] - q).T)
                k = int(d.argmin())
                if d[k] < best_d:
                    best_d, best_i = float(d[k]), int(idx[k])
            if best_d <= ring * self.CELL:      # every unvisited cell is farther than ring * CELL
                break
            ring += 1
        return best_d, best_i

    def query(self, q):
        res = [self._one(p) for p in np.asarray(q, float)]
        return np.array([r[0] for r in res]), np.array([r[1] for r in res], int)


def subsample(pts, step):
    """Points of one STEP-metre grid cell collapse to the first one (deterministic)."""
    _, first = np.unique(np.floor(pts / step).astype(np.int64), axis=0, return_index=True)
    return pts[np.sort(first)]


def rot(theta_deg):
    a = math.radians(theta_deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def load(npz):
    z = np.load(npz)
    meshes = [(z[k], z["t" + k[1:]]) for k in z.files if k.startswith("o") and "t" + k[1:] in z.files]
    for v, _ in meshes:
        if not np.isfinite(v).all():
            raise SystemExit(f"non-finite vertex in {npz}")
    if not meshes:
        raise SystemExit(f"no meshes in {npz}")
    return meshes


def section(meshes, h):
    segs = []
    for v, f in meshes:
        p = v[f]
        d = p[:, :, 2] - h
        s = np.where(d >= 0, 1, -1)
        cross = ~((s[:, 0] == s[:, 1]) & (s[:, 1] == s[:, 2]))
        for tri, dd in zip(p[cross], d[cross]):
            pts = [tri[a, :2] + dd[a] / (dd[a] - dd[b]) * (tri[b, :2] - tri[a, :2])
                   for a, b in ((0, 1), (1, 2), (2, 0)) if (dd[a] < 0) != (dd[b] < 0)]
            if len(pts) == 2:
                segs.append(pts)
    if not segs:
        raise SystemExit(f"empty section at z = {h}")
    return np.array(segs)


def _box_any(a, r, axis):
    """1-D running OR of half-width r cells along axis (cumulative sum, O(n))."""
    c = np.cumsum(np.pad(a.astype(np.int32), [(r + 1, r) if ax == axis else (0, 0) for ax in range(2)]), axis=axis)
    hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
    return (hi - lo) > 0


def close(a, r):
    """Morphological closing with a (2r+1)^2 square: door gaps up to 2r cells are bridged in both models."""
    dil = _box_any(_box_any(a, r, 0), r, 1)
    return ~_box_any(_box_any(~dil, r, 0), r, 1)


def outer_contour(segs):
    """Outer boundary points (cell centres, metres) of the closed section seen from outside."""
    r = int(round(CLOSE_M / RES))
    pad = CLOSE_M + 1.0
    lo = segs.reshape(-1, 2).min(0) - pad
    hi = segs.reshape(-1, 2).max(0) + pad
    w, h = (np.ceil((hi - lo) / RES).astype(int) + 1)
    img = Image.new("L", (int(w), int(h)), 0)
    dr = ImageDraw.Draw(img)
    for a, b in segs:
        dr.line([tuple((a - lo) / RES), tuple((b - lo) / RES)], fill=255, width=2)
    solid = close(np.array(img) == 255, r)
    # .copy(): PIL floodfill silently does nothing on a fromarray() image that shares the numpy buffer
    img = Image.fromarray(np.where(solid, 255, 0).astype(np.uint8)).copy()
    ImageDraw.floodfill(img, (0, 0), 128)
    a = np.array(img)
    outside = a == 128
    near = np.zeros_like(outside)
    near[1:, :] |= outside[:-1, :]
    near[:-1, :] |= outside[1:, :]
    near[:, 1:] |= outside[:, :-1]
    near[:, :-1] |= outside[:, 1:]
    ys, xs = np.nonzero((a != 128) & near)
    if not len(xs) or outside.all() or not outside.any():
        raise SystemExit("no outer contour (empty section or flood fill failed)")
    return np.column_stack([xs, ys]) * RES + lo


def min_rect_angle(xy):
    pts = sorted(map(tuple, np.unique(np.round(xy, 3), axis=0)))

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out[:-1]
    hull = np.array(half(pts) + half(pts[::-1]))
    best = (math.inf, 0.0, 0.0, 0.0)
    for i in range(len(hull)):
        e = hull[(i + 1) % len(hull)] - hull[i]
        ang = math.degrees(math.atan2(e[1], e[0]))
        r = hull @ rot(-ang).T
        area = np.ptp(r[:, 0]) * np.ptp(r[:, 1])
        if area < best[0]:
            best = (area, ang % 90.0, float(np.ptp(r[:, 0])), float(np.ptp(r[:, 1])))
    return best


def icp(src, nn, theta, t, iters=100):
    dst = nn.pts
    for _ in range(iters):
        d, j = nn.query(src @ rot(theta).T + t)
        keep = d <= max(np.percentile(d, 80), 0.02)    # trim parts only one model has
        a, b = src[keep], dst[j[keep]]
        ca, cb = a.mean(0), b.mean(0)
        u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
        r = (u @ vt).T
        if np.linalg.det(r) < 0:
            vt[-1] *= -1
            r = (u @ vt).T
        new_theta = math.degrees(math.atan2(r[1, 0], r[0, 0]))
        new_t = cb - ca @ r.T
        done = abs(new_theta - theta) < 1e-6 and np.allclose(new_t, t, atol=1e-6)
        theta, t = new_theta, new_t
        if done:
            break
    d, _ = nn.query(src @ rot(theta).T + t)
    return theta, t, d


def stats(d):
    return {"n": int(len(d)), "median_m": float(np.median(d)), "p90_m": float(np.percentile(d, 90)),
            "share_le_tol": float(np.mean(d <= TOL)), "max_m": float(d.max())}


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    theirs_p, ours_p, out = Path(argv[0]), Path(argv[1]), Path(argv[3])
    zero = float(argv[2])
    if not math.isfinite(zero):
        raise SystemExit(f"zero mark not finite: {argv[2]}")
    if out.exists() or out.resolve() in (theirs_p.resolve(), ours_p.resolve()):
        raise SystemExit(f"refusing to write {out}")
    theirs, ours = load(theirs_p), load(ours_p)
    origin = np.concatenate([v for v, _ in theirs])[:, :2].mean(0)      # numeric conditioning only
    src_by, dst_by = {}, {}
    for h in SECTIONS:
        src_by[h] = outer_contour(section(ours, h))
        dst_by[h] = outer_contour(section(theirs, h + zero) - origin)
    src, dst = np.concatenate(list(src_by.values())), np.concatenate(list(dst_by.values()))
    nn, src_s = NN(subsample(dst, 0.05)), subsample(src, 0.10)
    rt, rn = min_rect_angle(dst), min_rect_angle(src)
    runs = []
    for s in STARTS:
        th0 = rt[1] - rn[1] + s
        t0 = dst.mean(0) - src.mean(0) @ rot(th0).T
        th, t, d = icp(src_s, nn, th0, t0)
        runs.append({"start_deg": th0, "theta_deg": th, "t_msk_blender": (t + origin).tolist(), **stats(d)})
    runs.sort(key=lambda r: r["median_m"])
    best = runs[0]
    th, t = best["theta_deg"], np.array(best["t_msk_blender"]) - origin
    best["full"] = stats(NN(dst).query(src @ rot(th).T + t)[0])     # exact, every contour point
    per = {str(h): stats(NN(dst_by[h]).query(src_by[h] @ rot(th).T + t)[0]) for h in SECTIONS}
    allv_t = np.concatenate([v for v, _ in theirs])
    allv_o = np.concatenate([v for v, _ in ours])
    distinct = [r for r in runs[1:] if abs(((r["theta_deg"] - th + 180) % 360) - 180) > 1.0
                or np.hypot(*(np.array(r["t_msk_blender"]) - best["t_msk_blender"])) > 0.1]
    unique = all(r["median_m"] > 3 * max(best["median_m"], RES) for r in distinct)
    report = {
        "theirs": str(theirs_p), "ours": str(ours_p), "zero_abs": zero, "sections_z_ours": list(SECTIONS),
        "raster_res_m": RES, "tol_m": TOL,
        "rect_theirs": {"angle_deg": rt[1], "a_m": rt[2], "b_m": rt[3]},
        "rect_ours": {"angle_deg": rn[1], "a_m": rn[2], "b_m": rn[3]},
        "runs": runs, "best": best, "per_section": per, "unique": unique,
        "fit_ok": bool(unique and best["full"]["median_m"] <= TOL),
        "z": {"theirs_min": float(allv_t[:, 2].min()), "theirs_max": float(allv_t[:, 2].max()),
              "ours_top_abs": float(allv_o[:, 2].max()) + zero,
              "top_diff_m": float(allv_t[:, 2].max() - allv_o[:, 2].max() - zero)},
        "origin_msk_blender_xy": best["t_msk_blender"],
        "theta_deg": th,
    }
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("rect_theirs", "rect_ours", "best", "per_section", "unique", "fit_ok",
                                             "z")}, indent=1))
    for r in runs:
        print("run", round(r["start_deg"], 2), round(r["theta_deg"], 4), [round(x, 3) for x in r["t_msk_blender"]],
              round(r["median_m"], 4), round(r["p90_m"], 4))


if __name__ == "__main__":
    main(sys.argv[1:])
