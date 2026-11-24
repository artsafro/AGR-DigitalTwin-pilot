"""Standing #57 (OBSERVE): source-mesh wall hole as aperture-edge reference on 63B.

usage: python -X utf8 docs/research/autoresearch-body-form-r57/measure.py <fresh out dir>
       (internal: measure.py --once <out.json>)
Reads pinned inputs only (fail closed on any SHA-256 mismatch); writes only into <out dir>.
The detector functions are imported unchanged from score_heldout.py (t_563a40f7)."""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, time

import numpy as np

NPZ = "C:/x/ev_poly63b7/b63B_src.npz"
KEY = "C:/x/t_fb3a0b98-r51/key/heldout-key-v001.json"
KSEC = "C:/x/t_fb3a0b98-r51/key/heldout-sections-v001.json"
DET = "C:/x/t_563a40f7/detector/score_heldout.py"
EXTRACT = "C:/x/t_fb3a0b98-r51/run1/{v}/rep1/candidate.extract.json"
VARIANTS = {"v007": "accepted 2026-11-20", "v002": "rejected", "v003": "rejected", "v004": "rejected 2026-11-17",
            "v005": "rejected 2026-11-18", "v006": "rejected 2026-11-18"}
PINS = {NPZ: "b5cdbf394e4a10c55db391c13d15096c71e5a4c085be30e0edb595610cd04aea",
        KEY: "67a1ae5b88beec6eefc51d51ccdab496daa256709ec484793caee4097f6b6b14",
        KSEC: "07ce9a5bff8a9e4e82bf8346daef191ca5e0ba626ccd900aaca290a29fb698b6",
        DET: "e9d6f65b6373a4fc",  # prefix; full hash recorded in receipt
        EXTRACT.format(v="v002"): "5828266d5e694c1f", EXTRACT.format(v="v003"): "c035a44fe2dafb43",
        EXTRACT.format(v="v004"): "3b29cb977acf28cf", EXTRACT.format(v="v005"): "34b323ffa148dd23",
        EXTRACT.format(v="v006"): "4d381329b1e17162", EXTRACT.format(v="v007"): "a883a32978a7242d"}
# accepted v007 observed edges at both sections (r56 REPORT, clean readback of #54 replay)
O7 = {"рт О_194b464": (1.224342, 3.368707)}
NON_WALL = ("Окн", "Витр", "Двер")
TARGET = "рт О_194b464"
TOL_EDGE = 0.03


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def preflight():
    out = {}
    for p, want in PINS.items():
        h = sha(p)
        out[p] = {"sha256": h, "ok": h.startswith(want)}
    return out


def load_det():
    spec = importlib.util.spec_from_file_location("score_heldout", DET)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def slice_tris(tri, z):
    """Plane z cut of triangles -> list of ((x,y),(x,y)) segments (one per crossing triangle)."""
    zs = tri[:, :, 2] - z
    above = zs > 0
    cross = above.any(1) & (~above).any(1)
    segs = []
    for t, d in zip(tri[cross], zs[cross]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if (d[i] > 0) != (d[j] > 0):
                f = d[i] / (d[i] - d[j])
                pts.append((float(t[i, 0] + f * (t[j, 0] - t[i, 0])), float(t[i, 1] + f * (t[j, 1] - t[i, 1]))))
        if len(pts) == 2:
            segs.append((pts[0], pts[1]))
    return segs


def hole(det, segs, a, u, e0, e1):
    g = [gp for gp in det.gaps(det.wall_intervals(segs, a, u), e0 - 0.6, e1 + 0.6) if gp[0] < (e0 + e1) / 2 < gp[1]]
    return (round(g[0][0], 6), round(g[0][1], 6)) if len(g) == 1 else None


def move_endpoints(det, segs, a, u, pick, dt):
    out, n = [], 0
    for p, q in segs:
        np_ = []
        for pt in (p, q):
            t, _ = det.local(pt, a, u)
            if pick(t):
                pt = (pt[0] + dt * u[0], pt[1] + dt * u[1])
                n += 1
            np_.append(pt)
        out.append(tuple(np_))
    return out, n


def once(out_json):
    det = load_det()
    key = json.load(open(KEY, encoding="utf-8"))
    ring = {r["ring_index"]: r["xy"] for r in key["contour_vertices_in_box"]}
    bx = key["box_xy_m"]
    d = np.load(NPZ)
    tri, obj, names = d["tri"], d["obj"], d["names"]
    c = tri.mean(1)
    m = (c[:, 0] > bx[0] - 1) & (c[:, 0] < bx[2] + 1) & (c[:, 1] > bx[1] - 1) & (c[:, 1] < bx[3] + 1)
    wall_names = np.array([not str(n).startswith(NON_WALL) for n in names])
    wm = m & wall_names[obj]
    win = m & ~wall_names[obj]
    res = {"tri_in_box": int(m.sum()), "wall_tri": int(wm.sum()), "nonwall_tri": int(win.sum()), "openings": {}}
    for zl in det.OPENING_Z:
        z = float(zl) - key["z_shift_m"]
        wsegs = slice_tris(tri[wm], z)
        osegs = slice_tris(tri[win], z)
        for o in key["openings"]:
            i, j = o["contour_segment"]
            a, u, L = det.frame(ring, i, j)
            e0, e1 = o["edge_s_m"]
            S = hole(det, wsegs, a, u, e0, e1)
            # window-object extent near the key line (record only)
            ts = [det.local(pt, a, u) for s in osegs for pt in s]
            ts = [t for t, dd in ts if abs(dd) < 0.8 and e0 - 0.6 < t < e1 + 0.6]
            r = {"z_label": zl, "z_real": round(z, 3), "key": [e0, e1], "S": S,
                 "window_obj_extent": [round(min(ts), 6), round(max(ts), 6)] if ts else None}
            if S:
                r["dK"] = round(max(abs(S[0] - e0), abs(S[1] - e1)), 6)
                if o["id"] in O7:
                    r["dO7"] = round(max(abs(S[0] - O7[o["id"]][0]), abs(S[1] - O7[o["id"]][1])), 6)
                # positive witness and negative perturbation (section data only)
                pw, npos = move_endpoints(det, wsegs, a, u, lambda t: abs(t - S[0]) <= 0.05, 0.05)
                Sp = hole(det, pw, a, u, e0, e1)
                nw, nneg = move_endpoints(det, wsegs, a, u,
                                          lambda t: t < e0 - 0.6 - 1.0 or t > e1 + 0.6 + 1.0, 0.05)
                Sn = hole(det, nw, a, u, e0, e1)
                r["witness_pos"] = {"moved_endpoints": npos, "S": Sp,
                                    "dL": round(Sp[0] - S[0], 6) if Sp else None, "dR": round(Sp[1] - S[1], 6) if Sp else None}
                r["witness_neg"] = {"moved_endpoints": nneg, "S": Sn,
                                    "d": round(max(abs(Sn[0] - S[0]), abs(Sn[1] - S[1])), 6) if Sn else None}
            res["openings"].setdefault(o["id"], []).append(r)
    json.dump(res, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def rescore(out, S_ref):
    det = load_det()
    key = json.load(open(KEY, encoding="utf-8"))
    for o in key["openings"]:
        o["edge_s_m"] = list(S_ref[o["id"]])
    key["schema"] += " | r57 derived: edge_s_m = source wall hole (section 18.2), rescoring only"
    kd = os.path.join(out, "key_wallhole")
    os.makedirs(kd, exist_ok=True)
    kp = os.path.join(kd, "heldout-key-v001.json")
    json.dump(key, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copy(KSEC, os.path.join(kd, "heldout-sections-v001.json"))
    sp = os.path.join(kd, "SHA256SUMS.txt")
    open(sp, "w", encoding="utf-8").write(f"{sha(kp)} *heldout-key-v001.json\n")
    rows = {}
    for v, verdict in VARIANTS.items():
        row = {"verdict": verdict}
        for tag, (k, s) in {"key_v001": (KEY, os.path.join(os.path.dirname(KEY), "SHA256SUMS.txt")),
                            "wallhole": (kp, sp)}.items():
            op = os.path.join(out, f"rescore_{v}_{tag}.json")
            det.main(k, s, EXTRACT.format(v=v), op)
            items = json.load(open(op, encoding="utf-8"))["items"]
            ef = sorted(n for n, x in items.items() if n.endswith(":edges") and x["status"] == "fail")
            nm = [n for n, x in items.items() if n.endswith(":edges") and x["status"] == "not_measured"]
            row[tag] = {"edges_fail": ef, "edges_not_measured": nm,
                        "fail_total": sum(1 for x in items.values() if x.get("status") == "fail")}
        rows[v] = row
    return {"key_wallhole_sha256": sha(kp), "variants": rows}


def main(out):
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"refused: {out} is not a fresh directory")
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    pre = preflight()
    rec = {"card": "t_04ced2e2", "round": 57, "preflight": pre, "runs": []}
    if not all(x["ok"] for x in pre.values()):
        rec["status"] = "pin_mismatch"
        json.dump(rec, open(os.path.join(out, "receipt57.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        sys.exit("pin mismatch")
    for k in range(3):
        rj = os.path.join(out, f"run{k + 1}.json")
        ts = time.time()
        subprocess.run([sys.executable, "-X", "utf8", __file__, "--once", rj], check=True)
        rec["runs"].append({"file": os.path.basename(rj), "sha256": sha(rj), "wall_s": round(time.time() - ts, 3)})
    runs = [json.load(open(os.path.join(out, r["file"]), encoding="utf-8")) for r in rec["runs"]]
    rec["runs_identical"] = len({r["sha256"] for r in rec["runs"]}) == 1
    r1 = runs[0]["openings"]
    t = r1[TARGET]
    dO7 = [x.get("dO7") for x in t]
    dK = [x.get("dK") for x in t]
    if None in dO7 or None in dK or not rec["runs_identical"]:
        h = "inconclusive"
    elif max(dO7) <= TOL_EDGE and min(dK) > TOL_EDGE:
        h = "confirmed"
    elif max(dK) <= TOL_EDGE and min(dO7) > TOL_EDGE:
        h = "refuted"
    else:
        h = "inconclusive"
    rec["E57_per_run"] = [max(x.get("dO7") or 9 for x in r["openings"][TARGET]) for r in runs]
    rec["D57_per_run"] = [max(x.get("dK") or 9 for x in r["openings"][TARGET]) for r in runs]
    rec["H57"] = h
    rec["controls"] = {oid: [x.get("dK") for x in rows] for oid, rows in r1.items() if oid != TARGET}
    S_ref = {oid: rows[1]["S"] or rows[0]["S"] for oid, rows in r1.items()}
    if all(S_ref.values()):
        rec["rescore_frozen_51"] = rescore(out, S_ref)
    else:
        rec["rescore_frozen_51"] = "not_measured: missing source hole for " + ",".join(k for k, v in S_ref.items() if not v)
    rec["postflight"] = {p: sha(p).startswith(w) for p, w in PINS.items()}
    rec["status"] = "complete"
    rec["wall_s_total"] = round(time.time() - t0, 3)
    json.dump(rec, open(os.path.join(out, "receipt57.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: rec[k] for k in ("H57", "E57_per_run", "D57_per_run", "runs_identical", "controls",
                                          "wall_s_total")}, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "--once":
        once(sys.argv[2])
    else:
        main(sys.argv[1])
