"""elv-tc-vpm: rigid 2D registration (trimmed ICP) of their plan sections onto ours + residual stats.

py -3 -I customer_register_v001.py <out_dir>   (reads sections_v001.npz; writes register_v001.json, new file only)
Result transform maps THEIR local coordinates (FBX minus their origin) to OUR delivered frame: p_ours = R p + t.
"""
import sys, os, json
import numpy as np
from scipy.spatial import cKDTree

out = sys.argv[1]
S = np.load(os.path.join(out, "sections_v001.npz"))


def sample(segs, step=0.05):
    pts = []
    for a, b in segs:
        n = max(1, int(np.linalg.norm(b - a) / step))
        t = np.linspace(0, 1, n + 1)[:, None]
        pts.append(a + t * (b - a))
    return np.concatenate(pts)


rep = {}
for hs in (["1_5"], ["6_0"], ["11_0"], ["1_5", "6_0", "11_0"]):
    P = np.concatenate([sample(S[f"theirs_{h}"]) for h in hs])
    Q = np.concatenate([sample(S[f"ours_{h}"]) for h in hs])
    tree = cKDTree(Q)
    R, t = np.eye(2), np.array([0.0, 0.48])
    for it, thr in enumerate([1.0] * 10 + [0.3] * 10 + [0.1] * 20):
        X = P @ R.T + t
        d, i = tree.query(X)
        m = d < thr
        A, B = P[m], Q[i[m]]
        ca, cb = A.mean(0), B.mean(0)
        H = (A - ca).T @ (B - cb)
        U, _, Vt = np.linalg.svd(H)
        Rn = Vt.T @ U.T
        if np.linalg.det(Rn) < 0:
            Vt[1] *= -1
            Rn = Vt.T @ U.T
        R, t = Rn, cb - Rn @ ca
    X = P @ R.T + t
    d, _ = tree.query(X)
    d2, _ = cKDTree(X).query(Q)
    ang = float(np.degrees(np.arctan2(R[1, 0], R[0, 0])))
    rep["+".join(hs)] = {"t_xy_m": [round(float(t[0]), 4), round(float(t[1]), 4)], "rot_deg": round(ang, 4),
                         "theirs_to_ours_dist_m": {"median": round(float(np.median(d)), 4), "p90": round(float(np.percentile(d, 90)), 3),
                                                   "share_lt_5cm": round(float((d < 0.05).mean()), 3), "share_gt_30cm": round(float((d > 0.3).mean()), 3)},
                         "ours_to_theirs_dist_m": {"median": round(float(np.median(d2)), 4), "p90": round(float(np.percentile(d2, 90)), 3),
                                                   "share_lt_5cm": round(float((d2 < 0.05).mean()), 3), "share_gt_30cm": round(float((d2 > 0.3).mean()), 3)},
                         "n_points": [len(P), len(Q)]}
# zero-transform stats for reference
for h in ("6_0",):
    P = sample(S[f"theirs_{h}"]); Q = sample(S[f"ours_{h}"])
    d, _ = cKDTree(Q).query(P)
    rep["identity_" + h] = {"median": round(float(np.median(d)), 4), "share_lt_5cm": round(float((d < 0.05).mean()), 3)}
json.dump(rep, open(os.path.join(out, "register_v001.json"), "x"), indent=1)
print(json.dumps(rep, indent=1))
