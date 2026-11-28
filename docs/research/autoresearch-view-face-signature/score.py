"""#157 scoring: window counts per wall, signature uniqueness (A, B, R), risk at 2 tau, perturbed queries.

new-case: docs/research/autoresearch-view-face-signature/score.py - #157 signature scoring (frozen numbers)
"""
import math

TAU_W, TAU_H, TAU_R = 1.2, 1.0, 0.05
WIN_DEPTH, WIN_GAP = 0.8, 0.6


def clusters(vals, gap=WIN_GAP):
    vals = sorted(vals)
    n = 0
    for i, v in enumerate(vals):
        if i == 0 or v - vals[i - 1] > gap:
            n += 1
    return n


def attach_windows(walls, windows):
    for w in walls:
        a = math.radians(w["az"])
        s, t = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        us, zs = [], []
        for p in windows:
            d = s[0] * p[0] + s[1] * p[1]
            u = t[0] * p[0] + t[1] * p[1]
            if w["d0"] - WIN_DEPTH <= d <= w["d1"] + WIN_DEPTH and w["u0"] <= u <= w["u1"] and w["z0"] <= p[2] <= w["z1"]:
                us.append(u)
                zs.append(p[2])
        w["ncol"], w["nrow"] = clusters(us), clusters(zs)


def match(q, w, kind, k=1.0):
    if kind in ("B", "R") and (q["ncol"], q["nrow"]) != (w["ncol"], w["nrow"]):
        return False
    if kind == "R":
        return abs(math.log(q["W"] / q["H"]) - math.log(w["W"] / w["H"])) <= TAU_R * k
    return abs(q["W"] - w["W"]) <= TAU_W * k and abs(q["H"] - w["H"]) <= TAU_H * k


def score_model(walls, windows=None):
    if windows is not None:
        attach_windows(walls, windows)
    n = len(walls)
    rows = []
    for i, w in enumerate(walls):
        others = [j for j in range(n) if j != i]
        r = {"i": i, "cls": w["cls"], "az": w["az"], "W": w["W"], "H": w["H"], "ncol": w["ncol"], "nrow": w["nrow"]}
        for kind in ("A", "B", "R"):
            r[f"unique_{kind}"] = not any(match(w, walls[j], kind) for j in others)
        r["risk2_B"] = any(match(w, walls[j], "B", 2.0) for j in others)
        outs = []
        queries = [dict(w, W=w["W"] * k, H=w["H"] * k) for k in (0.95, 1.05)]
        if w["ncol"] >= 2:
            queries.append(dict(w, ncol=w["ncol"] - 1))
        for q in queries:
            cand = [j for j in range(n) if match(q, walls[j], "B")]
            outs.append("correct" if cand == [i] else "wrong" if len(cand) == 1 else "abstain")
        r["perturbed"] = outs
        rows.append(r)

    def frac(sel, key):
        return round(sum(r[key] for r in sel) / len(sel), 4) if sel else None

    inner = [r for r in rows if r["cls"] == "inner"]
    opn = [r for r in rows if r["cls"] == "open"]
    po = [o for r in rows for o in r["perturbed"]]
    summary = {
        "walls": n, "inner_walls": len(inner), "open_walls": len(opn),
        "walls_with_windows": sum(r["ncol"] > 0 for r in rows),
        "inner_unique_A": frac(inner, "unique_A"), "inner_unique_B": frac(inner, "unique_B"),
        "inner_unique_R": frac(inner, "unique_R"), "open_unique_B": frac(opn, "unique_B"),
        "all_unique_B": frac(rows, "unique_B"), "inner_risk2_B": frac(inner, "risk2_B"),
        "perturbed": {"queries": len(po), "correct": po.count("correct"), "wrong": po.count("wrong"),
                      "abstain": po.count("abstain"),
                      "wrong_rate": round(po.count("wrong") / len(po), 4) if po else None},
    }
    # Diagnostic (declared before scoring, not gated): inner walls standing on the ground (z0 <= lowest z0 + 1 m),
    # i.e. what an inner-corner partial elevation shows; rooftop structures and above-roof steps excluded.
    if walls:
        zmin = min(w["z0"] for w in walls)
        ground = [r for r, w in zip(rows, walls) if r["cls"] == "inner" and w["z0"] <= zmin + 1.0]
        summary["diag_inner_ground"] = {"n": len(ground), "unique_B": frac(ground, "unique_B"),
                                        "unique_R": frac(ground, "unique_R"), "risk2_B": frac(ground, "risk2_B")}
    return {"summary": summary, "rows": rows}
