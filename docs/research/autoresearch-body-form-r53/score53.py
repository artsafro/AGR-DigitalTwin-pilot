"""Standing #53 OBSERVE overlay on the frozen t_563a40f7 scorer (score_heldout.py is imported read-only, never edited).
usage: python score53.py <key.json> <candidate.extract.json> <frozen vs_key.json> <out.json> [R_face_json]
For each key opening: rim loop = frozen match (band loop within 0.5 m of the gap mid); only if none, fallback = band
loops with centroid t inside the frozen gap and 0.02 < |d| <= 1.5 m (t closest to mid). Items:
  sill_head_c   frozen formula on the rim loop (frozen measured statuses must stay identical)
  depth_rim     |d| of the rim loop centroid (D037: facade -> back polygon)
  depth_vs_key  |depth_rim - key reveal_depth_m| <= frozen reveal_depth tolerance
  depth_vs_face |depth_rim - R_face| <= same tolerance (only when an R_face file is given)"""
import json
import math
import os
import sys

sys.path.insert(0, "C:/x/t_563a40f7/detector")
import score_heldout as S  # noqa: E402

FALLBACK_MAX_D = 1.5


def overlay(kp, cp, fp, op, rface_path=None):
    key = json.load(open(kp, encoding="utf-8"))
    cand = json.load(open(cp, encoding="utf-8"))
    frozen = json.load(open(fp, encoding="utf-8"))["items"]
    rface = json.load(open(rface_path, encoding="utf-8")) if rface_path else None
    ring = {r["ring_index"]: r["xy"] for r in key["contour_vertices_in_box"]}
    box = key["box_xy_m"]
    ksec = json.load(open(os.path.join(os.path.dirname(kp), "heldout-sections-v001.json")))
    csec = {z: [s for s in cand["sections"].get(z, []) if S.inbox(s[0], box, 0.5) or S.inbox(s[1], box, 0.5)]
            for z in ksec}
    loops = [lp for lp in cand.get("loops", []) if S.inbox(lp["c"], box) and 17.0 <= lp["z"][0] <= 17.6]
    tol_d, tol_s = S.TOL["reveal_depth_m"], S.TOL["sill_head_m"]
    out = {}
    for o in key["openings"]:
        pid = f"opening:{o['id']}"
        i, j = o["contour_segment"]
        a, u, _ = S.frame(ring, i, j)
        e0, e1 = o["edge_s_m"]
        found = []
        for z in S.OPENING_Z:
            g = [gp for gp in S.gaps(S.wall_intervals(csec[z], a, u), e0 - 0.6, e1 + 0.6) if gp[0] < (e0 + e1) / 2 < gp[1]]
            found.append(g[0] if g else None)
        rec = {"frozen_sill_head": frozen[pid + ":sill_head"]["status"],
               "frozen_reveal_depth": frozen[pid + ":reveal_depth"]["status"]}
        if not all(found):
            rec |= {"rim": None, "source": "opening missing", "sill_head_c": "not_measured", "depth_rim": None,
                    "depth_vs_key": "not_measured", "depth_vs_face": "not_measured" if rface else "not_applicable"}
            out[pid] = rec
            continue
        g = found[1]
        mid = (a[0] + u[0] * (g[0] + g[1]) / 2, a[1] + u[1] * (g[0] + g[1]) / 2)
        lp = [x for x in loops if math.hypot(x["c"][0] - mid[0], x["c"][1] - mid[1]) < 0.5]
        src = "frozen_match"
        if not lp:
            mt = (g[0] + g[1]) / 2
            fb = [(abs(S.local(x["c"], a, u)[0] - mt), x) for x in loops
                  if g[0] <= S.local(x["c"], a, u)[0] <= g[1] and 0.02 < abs(S.local(x["c"], a, u)[1]) <= FALLBACK_MAX_D]
            lp = [min(fb, key=lambda r: r[0])[1]] if fb else []
            src = "fallback" if lp else "none"
        if not lp:
            rec |= {"rim": None, "source": src, "sill_head_c": "not_measured", "depth_rim": None,
                    "depth_vs_key": "not_measured", "depth_vs_face": "not_measured" if rface else "not_applicable"}
            out[pid] = rec
            continue
        rim = lp[0]
        dz = max(abs(rim["z"][0] - o["sill_head_z_m"][0]), abs(rim["z"][1] - o["sill_head_z_m"][1]))
        dr = abs(S.local(rim["c"], a, u)[1])
        rec |= {"rim": {"c": rim["c"], "z": rim["z"]}, "source": src,
                "sill_head_c": "pass" if dz <= tol_s else "fail", "sill_dz": round(dz, 4),
                "depth_rim": round(dr, 4), "key_depth": o["reveal_depth_m"],
                "depth_vs_key": "pass" if abs(dr - o["reveal_depth_m"]) <= tol_d else "fail"}
        if rface:
            rf = rface[o["id"]]
            rec |= {"face_depth": rf, "depth_vs_face": "pass" if abs(dr - rf) <= tol_d else "fail"}
        else:
            rec["depth_vs_face"] = "not_applicable"
        out[pid] = rec
    parity = [p for p, r in out.items() if r["frozen_sill_head"] in ("pass", "fail")
              and r["sill_head_c"] != r["frozen_sill_head"]]
    res = {"openings": out, "frozen_measured_changed": parity,
           "nm": sum((r["sill_head_c"] == "not_measured") + (r["depth_rim"] is None) for r in out.values()),
           "frozen_sill_nm": sum(r["frozen_sill_head"] == "not_measured" for r in out.values()),
           "fails_vs_key": sum(r["depth_vs_key"] == "fail" for r in out.values()),
           "fails_vs_face": sum(r["depth_vs_face"] == "fail" for r in out.values()),
           "fallback_used": sum(r["source"] == "fallback" for r in out.values())}
    json.dump(res, open(op, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return res


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in overlay(*sys.argv[1:6]).items() if k != "openings"}))
