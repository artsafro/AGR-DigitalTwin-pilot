"""DWG route into the body plan format (#1736): plan_from_dxf contours + facade openings -> BodyPlan per band.

Pattern: n/a | new-case: DWG adapter of the shared body core (plan_from_dxf bands, facade_openings_from_dxf openings
placed by an explicit facade->ring map; lines from the openings list, snapped 10 cm, kept by class change >= 1.5 m).

uv run python tools/methods/body/plan_adapter_dwg.py CONTOURS.json CONFIG.json NEW_OUT_DIR [--openings OPEN.json]
CONTOURS = plan_from_dxf.py output (schema body-contours/1, bands of polygons, metres). OPEN = facade_openings_from_dxf
output (left_m/right_m/sill_m/head_m per opening, facade name). CONFIG::

    {"materials": {"WALL_A": [0.8, 0.8, 0.8]}, "zone": "WALL_A", "snap_m": 0.10, "min_reason_m": 1.5,
     "collinear_deg": 0.5, "facades": {"west": {"ring_s0_m": 12.0, "direction": 1, "reveal_m": 0.25}},
     "lines": [{"band": 0, "at": 0.9, "reason": "plinth", "length": 40.0}]}

Nothing is inferred: an opening's facade must be in `facades` (placement along the CCW outer ring: s = ring_s0_m +
direction * left_m), else it is an error naming it; an opening outside or across its band is reported in `dropped`.
Lines come only from the openings list and `lines` (decision 2, Artem 2026-11-21: never from mesh vertices), snapped
to snap_m; a line is kept only by keep_lines (decision 3). Each band -> NEW_OUT_DIR/plan_band<k>.json (one module,
floors 1, step = band height) + NEW_OUT_DIR/adapter_report.json (kept / dropped with reasons). Holes of the plan
polygons are dropped with a reason (outer envelope, D341); collinear ring points (< collinear_deg) are dropped.
NEW_OUT_DIR must not exist and must not contain an input.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import body_lattice as core  # noqa: E402


def _ccw(xy):
    pts = [tuple(map(float, p)) for p in xy]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-9:
        pts = pts[:-1]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2
    return pts if area > 0 else pts[::-1]


def simplify(xy, collinear_deg=0.5):
    """Drop ring points whose turn is below collinear_deg (BM-01: vertices only at breaks). Returns (pts, dropped)."""
    pts, dropped = list(xy), []
    changed = True
    while changed and len(pts) > 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            if lu < 1e-6 or lv < 1e-6:
                dropped.append({"xy": b, "why": "duplicate point"})
                pts.pop(i)
                changed = True
                break
            turn = math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
            if abs(turn) < collinear_deg:
                dropped.append({"xy": b, "why": "collinear (turn %.3f deg < %.2f)" % (turn, collinear_deg)})
                pts.pop(i)
                changed = True
                break
    return pts, dropped


def adapt(contours, cfg, openings=None):
    """Return ([plan per band], report). Pure; raises ValueError on unmapped facades or bad numbers."""
    if contours.get("schema") != "body-contours/1":
        raise ValueError("contours schema must be body-contours/1, got %r" % (contours.get("schema"),))
    mats, zone = cfg.get("materials"), cfg.get("zone")
    if not isinstance(mats, dict) or zone not in mats:
        raise ValueError("config needs materials and a zone material that is in them, got zone %r" % (zone,))
    grid, min_reason = cfg.get("snap_m", 0.10), cfg.get("min_reason_m", 1.5)
    facades = cfg.get("facades", {})
    ops = list((openings or {}).get("openings", []))
    for o in ops:
        if o.get("facade") not in facades:
            raise ValueError("opening %r: facade %r has no placement in config.facades"
                             % (o.get("id"), o.get("facade")))
        for k in ("left_m", "right_m", "sill_m", "head_m"):
            if not core._finite(o.get(k)):
                raise ValueError("opening %r: %s must be finite" % (o.get("id"), k))
    plans, report = [], {"bands": [], "dropped": []}
    used = set()
    for bi, band in enumerate(contours.get("bands", [])):
        z0, z1 = float(band["z0"]), float(band["z1"])
        polys = band.get("polygons", [])
        if len(polys) != 1:
            raise ValueError("band %d has %d polygons; the core needs one outer ring per band" % (bi, len(polys)))
        for h in polys[0].get("holes", []):
            report["dropped"].append({"band": bi, "what": "hole (%d pts)" % len(h), "why": "outer envelope D341"})
        ring, dpts = simplify(_ccw(polys[0]["exterior"]), cfg.get("collinear_deg", 0.5))
        report["dropped"] += [dict(d, band=bi, what="ring point") for d in dpts]
        perim = sum(math.dist(a, b) for a, b in zip(ring, ring[1:] + ring[:1]))
        step = round(z1 - z0, 6)
        cands, wins, cuts = [], [], set()
        for o in ops:
            if o["sill_m"] < z0 - 1e-6 or o["head_m"] > z1 + 1e-6:
                if o["head_m"] > z0 and o["sill_m"] < z1:
                    report["dropped"].append({"band": bi, "what": o.get("id"), "why": "opening crosses the band"})
                continue
            used.add(o.get("id"))
            f = facades[o["facade"]]
            if f.get("direction") not in (1, -1) or not core._finite(f.get("ring_s0_m")):
                raise ValueError("facade %r needs direction +-1 and finite ring_s0_m" % o["facade"])
            sa = (f["ring_s0_m"] + f["direction"] * o["left_m"]) % perim
            sb = (f["ring_s0_m"] + f["direction"] * o["right_m"]) % perim
            if abs(abs(sb - sa) - (o["right_m"] - o["left_m"])) > 1e-6:
                raise ValueError("opening %r crosses the ring start s=0; move ring_s0_m" % (o.get("id"),))
            s0, s1 = core.snap(min(sa, sb), grid), core.snap(max(sa, sb), grid)
            w = s1 - s0
            lo, hi = core.snap(o["sill_m"] - z0, grid), core.snap(o["head_m"] - z0, grid)
            cands += [{"at": lo, "reason": "opening", "length": w, "width": w},
                      {"at": hi, "reason": "opening", "length": w, "width": w}]
            cuts |= {s0, s1}
            wins.append((o.get("id"), s0, s1, lo, hi, float(f.get("reveal_m", 0.0))))
        for ln in cfg.get("lines", []):
            if ln.get("band") == bi:
                cands.append({"at": core.snap(ln["at"], grid), "reason": ln["reason"], "length": ln["length"]})
        kept, drop = core.keep_lines(cands, min_reason)
        report["dropped"] += [dict(d, band=bi, what="line") for d in drop]
        loops = [0.0] + [z for z in kept if 1e-6 < z < step - 1e-6]
        windows = []
        for oid, s0, s1, lo, hi, r in wins:
            if lo not in loops + [step] or hi not in loops + [step]:
                report["dropped"].append({"band": bi, "what": oid, "why": "opening line dropped as texture"})
                continue
            lv = loops + [step]
            windows.append([0, s0, s1, lv.index(lo), lv.index(hi), r])
        plan = {"step": step, "z0": z0, "floors": 1, "loops": loops,
                "rings": [{"xy": [list(p) for p in ring], "cuts": sorted(cuts), "zones": [[0.0, perim, zone]]}],
                "windows": windows, "materials": mats, "source": "dwg", "band": bi}
        if any(w[5] == 0 for w in windows) and "WINDOW" not in mats:
            raise ValueError("openings with reveal_m 0 keep the cell; materials need WINDOW")
        core.validate_plan(plan)
        plans.append(plan)
        report["bands"].append({"band": bi, "z0": z0, "z1": z1, "ring_points": len(ring), "loops": loops,
                                "openings": len(windows)})
    for o in ops:
        if o.get("id") not in used and not any(d.get("what") == o.get("id") for d in report["dropped"]):
            report["dropped"].append({"what": o.get("id"), "why": "opening in no band"})
    return plans, report


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    op = None
    if "--openings" in args:
        i = args.index("--openings")
        op = args[i + 1]
        del args[i:i + 2]
    if len(args) != 3:
        print((__doc__ or "").split("\n\n")[2], file=sys.stderr)
        return 2
    cont, cfgp, out = args
    out = os.path.realpath(out)
    ins = [os.path.realpath(p) for p in (cont, cfgp) + ((op,) if op else ())]
    if os.path.exists(out) or any(p == out or p.startswith(out + os.sep) for p in ins):
        print("refused: NEW_OUT_DIR exists or holds an input", file=sys.stderr)
        return 2
    try:
        rd = lambda p: json.load(open(p, encoding="utf-8"))  # noqa: E731
        plans, rep = adapt(rd(cont), rd(cfgp), rd(op) if op else None)
    except (ValueError, KeyError, OSError) as e:
        print("refused: %s" % e, file=sys.stderr)
        return 2
    os.makedirs(out)
    for p in plans:
        with open(os.path.join(out, "plan_band%d.json" % p["band"]), "x", encoding="utf-8") as fh:
            json.dump(p, fh, indent=1)
    with open(os.path.join(out, "adapter_report.json"), "x", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=1)
    print("PLANS", json.dumps(rep["bands"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
