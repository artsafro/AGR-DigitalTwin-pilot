"""Body v006 openings (#1784, [D408]): Revit windows / doors / curtain glass with no body opening -> lattice rects.

The accepted body (v005 lattice + [D384] wells) is blind where Revit has fill (F01: three rows vs a plain wall). This hook
projects every planned inset window / door / curtain-glass object of the split (plus the stemalit spandrels of the same
curtain walls, plan: texture on the opening plane) onto the facade edges of the volume-lines, keeps the ones in the
facade plane (depth <= max_depth_m) that no built rectangle covers, joins touching curtain panels into one opening and
writes them as `extra_rectangles` of a new body config (state `contour_cut`: the core snaps an edge to a level within
its level_snap_m, else a local sill / head [D375]; reveal = the Revit glass depth). The body itself is then built by the
shared lattice core `tools/methods/body/volume_body.py` (no mesh repair). Pure Python, no DCC.

    python body_openings.py <dump.json> <modelling_plan.json> <volume-lines.json> <body_config_in.json> <cfg_out.json> <report.json>
"""
import argparse
import json
import math
import sys

DEFAULTS = {
    "max_depth_m": 1.0,      # deeper glass = a recess / loggia (not a facade opening): listed, not cut
    "recess_max_m": 5.0,     # an entrance niche (doors + glass from the ground) up to this deep is cut with a capped reveal
    "entrance_z_max": 0.30,
    "min_out_m": -0.3,       # glass more than this in front of the face is not on this edge
    "cluster_gap_m": 0.25,   # curtain panels closer than this (mullion / transom) are one opening
    "cover_tol_m": 0.10,
    "snap_m": 0.10,          # local sill / head values on a 10 cm grid (Artem 2026-11-25)
    "reveal_min_m": 0.08,     # a shallower reveal is a < 5 cm sliver for the defect check (min_side 0.05)
    "reveal_max_m": 0.95,
    "skip_facades": {"F05": "F05 glazing = [D378] contour cut + ground inset (v007/v008), not re-cut"},
    "built_states": ["cut", "level_conflict", "crosses_visible_band", "contour_cut"],
    "top_keep_m": 0.25,      # the head stays this far below the volume top (parapet / roof edge stays closed)
    "min_width_m": 0.30,     # narrower clusters (a panel edge on a corner) are slivers, not openings
    "min_height_m": 0.50,
    "min_kept_frac": 0.5,    # an opening trimmed below half its Revit height is not cut (a door stub)
    "corner_pier_m": 0.30,   # an opening ends at least this far from the edge ends
    "station_merge_m": 0.10,  # = volume_body.py DEFAULT_CFG
    "level_snap_m": 0.20,     # = volume_body.py DEFAULT_CFG
}


def _area(ring):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def plan_classes(plan):
    """{object name: win | door | glass | stem} for the planned inset windows, doors, curtain glass and stemalit."""
    out = {}
    for r in plan["rows"]:
        lay, fam, rep = r["layer"][:2], r["family"], r["representation"]
        if lay == "02" and "Окно" in fam and rep == "inset":
            c = "win"
        elif lay == "03" and rep == "inset":
            c = "door"
        elif lay == "04" and rep == "inset":
            c = "glass"
        elif lay == "04" and "темалит" in fam:
            c = "stem"
        else:
            continue
        for n in r["objects"]:
            out[n] = c
    return out


def edge_frames(vl, base_by_volume=None):
    """Per edge: origin, unit, outward normal, length, z range of its volume and the band hidden by a seam mate."""
    base_by_volume = base_by_volume or {}
    vols = {}
    for vn, v in vl["volumes"].items():
        ring = v["ring"][:-1] if v["ring"][0] == v["ring"][-1] else v["ring"]
        lv = [float(z) for z in v["levels"]]
        if vn in base_by_volume:
            lv[0] = float(base_by_volume[vn])
        vols[vn] = {"ccw": _area(ring) > 0, "levels": lv}
    out = {}
    acc: dict = {}
    for k, e in vl["edges"].items():
        (ax, ay), (bx, by) = e["xy"]
        ln = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / ln, (by - ay) / ln
        V = vols[e["volume"]]
        nx, ny = (uy, -ux) if V["ccw"] else (-uy, ux)
        hid = None
        if e.get("mate"):
            M = vols[vl["edges"][e["mate"]]["volume"]]
            hid = (max(V["levels"][0], M["levels"][0]), min(V["levels"][-1], M["levels"][-1]))
        off = acc.get(e["volume"], 0.0)
        acc[e["volume"]] = off + ln
        out[k] = {"off": off, "a": (ax, ay), "u": (ux, uy), "n": (nx, ny), "L": ln, "volume": e["volume"],
                  "facade": e.get("facade"), "levels": V["levels"], "hidden": hid}
    return out


def project(o, f):
    ax, ay = f["a"]
    ss = [(x - ax) * f["u"][0] + (y - ay) * f["u"][1] for x, y in o["hull"]]
    nn = [(x - ax) * f["n"][0] + (y - ay) * f["n"][1] for x, y in o["hull"]]
    return min(ss), max(ss), min(nn), max(nn)


def assign(o, frames, cfg):
    """Best edge of an object: its s range lies on the edge, its z centre on the visible part of the volume, the
    smallest depth. Returns (edge, s0, s1, depth) or (None, reason)."""
    z0, z1 = o["z"]
    zc = (z0 + z1) / 2
    best = None
    for k, f in frames.items():
        s0, s1, n0, n1 = project(o, f)
        if min(s1, f["L"]) - max(s0, 0.0) < 0.5 * max(s1 - s0, 1e-6):
            continue
        if not (f["levels"][0] - 0.1 <= zc <= f["levels"][-1] + 0.1):
            continue
        depth = -(n0 + n1) / 2  # glass centre behind the face (+) or in front (-)
        if depth < cfg["min_out_m"]:
            continue
        if best is None or abs(depth) < abs(best[3]):
            best = (k, s0, s1, depth)
    if best is None:
        return None, "no_edge"
    return best, None


def covered(k, s0, s1, z0, z1, rects, tol):
    sc, zc = (s0 + s1) / 2, (z0 + z1) / 2
    for r in rects:
        if r.get("edge") != k:
            continue
        a, b, za, zb = r.get("snapped_rect") or r["projected_rect"]
        if a - tol <= sc <= b + tol and za - tol <= zc <= zb + tol:
            return r["name"]
    return None


def _gap(a0, a1, b0, b1):
    return max(0.0, a0 - b1, b0 - a1)


def clusters(items, g):
    """Union-find of rects [s0, s1, z0, z1] touching within g in s and z."""
    par = list(range(len(items)))

    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i, a in enumerate(items):
        for j in range(i + 1, len(items)):
            b = items[j]
            if _gap(a["s"][0], a["s"][1], b["s"][0], b["s"][1]) <= g and _gap(a["z"][0], a["z"][1], b["z"][0], b["z"][1]) <= g:
                par[root(i)] = root(j)
    out: dict = {}
    for i, it in enumerate(items):
        out.setdefault(root(i), []).append(it)
    return list(out.values())


def cells(levels, z0, z1, snap):
    """(wl, wh, zs, zt) the way volume_body.py reads a contour_cut rect: an edge within `snap` of a level sits on it,
    else a local sill / head inside the cell."""
    def near(z):
        i = min(range(len(levels)), key=lambda k: abs(levels[k] - z))
        return i if abs(levels[i] - z) <= snap + 1e-9 else None
    wl, zs = near(z0), None
    if wl is None:
        wl, zs = max((k for k, z in enumerate(levels) if z < z0), default=0), z0
    wh, zt = near(z1), None
    if wh is None:
        wh, zt = min((k for k, z in enumerate(levels) if z > z1), default=len(levels) - 1), z1
    return wl, wh, zs, zt


def resolve(k, s0, s1, z0, z1, levels, others, cfg, frames):
    """Trim a new opening so that it shares no lattice cell with another opening of different levels on the same edge
    (the core refuses that; compared on the volume perimeter, so a neighbour across a corner counts): a conflict below lifts the sill to its head level, one above lowers the head to its
    sill level. Returns (z0, z1, None) or (z0, z1, reason) when nothing is left."""
    tol, snap = cfg["station_merge_m"] + 1e-6, cfg["level_snap_m"]
    for _ in range(20):
        me = cells(levels, z0, z1, snap)
        if me[1] <= me[0]:
            return z0, z1, "empty after trimming"
        hit = None
        fk = frames[k]
        for r in others:
            fr = frames.get(r.get("edge"))
            if fr is None or fr["volume"] != fk["volume"]:
                continue
            a, b, za, zb = r.get("snapped_rect") or r["projected_rect"]
            a, b = a + fr["off"] - fk["off"], b + fr["off"] - fk["off"]
            if r.get("state") == "crosses_visible_band":
                za = max(za, cfg["visible_from"].get(k, za))
            if not (a <= s1 + tol and s0 <= b + tol):
                continue
            ot = cells(levels, za, zb, snap)
            if ot[0] < me[1] and me[0] < ot[1] and ot != me:
                hit = (ot, (za + zb) / 2, r["name"])
                break
        if hit is None:
            return z0, z1, None
        ot, mid, nm = hit
        if mid < (z0 + z1) / 2:
            z0 = levels[ot[1]]
        else:
            z1 = levels[ot[0]]
        if z1 - z0 < cfg["min_height_m"]:
            return z0, z1, "conflict with %s" % nm
    return z0, z1, "unresolved"


def _grid(z, step):
    return round(round(z / step) * step, 3)


def derive(dump_objs, plan, vl, body_cfg, cfg=None):
    """(new extra rectangles, reveal_m_by_name, report)."""
    cfg = dict(DEFAULTS, **(cfg or {}))
    cls = plan_classes(plan)
    cfg["visible_from"] = {k: float(e.get("visible_from") or 0.0) for k, e in vl["edges"].items()}
    frames = edge_frames(vl, body_cfg.get("base_by_volume"))
    built = [r for r in list(vl["rectangles"]) + list(body_cfg.get("extra_rectangles", []))
             if r.get("state") in cfg["built_states"]]
    rep: dict = {"objects": {}, "by_status": {}, "rects": [], "not_cut": []}
    per_edge: dict = {}

    def note(c, status, name, extra=None):
        rep["by_status"].setdefault(c, {}).setdefault(status, 0)
        rep["by_status"][c][status] += 1
        rep["objects"][name] = dict(extra or {}, cls=c, status=status)
    for o in dump_objs:
        c = cls.get(o["name"])
        if c is None:
            continue
        hit, why = assign(o, frames, cfg)
        if hit is None:
            note(c, why, o["name"])
            continue
        k, s0, s1, depth = hit
        f = frames[k]
        z0, z1 = o["z"]
        info = {"edge": k, "facade": f["facade"], "s": [round(s0, 3), round(s1, 3)], "z": [z0, z1],
                "depth": round(depth, 3)}
        if f["hidden"] and z1 <= f["hidden"][1] + 0.05 and z0 >= f["hidden"][0] - 0.05:
            note(c, "hidden_by_seam", o["name"], info)
            continue
        if f["facade"] in cfg["skip_facades"]:
            note(c, "skip_facade", o["name"], info)
            continue
        cov = covered(k, s0, s1, z0, z1, built, cfg["cover_tol_m"])
        if cov:
            note(c, "in_body_opening", o["name"], dict(info, opening=cov))
            continue
        if depth > cfg["recess_max_m"]:
            note(c, "interior", o["name"], info)  # far behind any face: an inner glass wall, not facade fill
            continue
        if depth > cfg["max_depth_m"] and not (c in ("door", "glass") and z0 <= cfg["entrance_z_max"]):
            note(c, "recessed", o["name"], info)
            continue
        z0c = max(z0, f["hidden"][1]) if f["hidden"] and z0 < f["hidden"][1] < z1 else z0
        per_edge.setdefault(k, []).append({"name": o["name"], "cls": c, "s": [s0, s1], "z": [z0c, z1],
                                           "depth": depth})
        note(c, "new_opening", o["name"], info)
    rects, reveals = [], {}
    wells = body_cfg.get("roof_wells", {})
    for k in sorted(per_edge):
        f = frames[k]
        for grp in sorted(clusters(per_edge[k], cfg["cluster_gap_m"]), key=lambda g: min(i["s"][0] for i in g)):
            if all(i["cls"] == "stem" for i in grp):
                for i in grp:
                    rep["objects"][i["name"]]["status"] = "stemalit_alone"
                continue
            s0 = max(cfg["corner_pier_m"], min(i["s"][0] for i in grp))  # a corner keeps a pier (no sliver cell)
            s1 = min(f["L"] - cfg["corner_pier_m"], max(i["s"][1] for i in grp))
            z0 = _grid(min(i["z"][0] for i in grp), cfg["snap_m"])
            z1 = _grid(max(i["z"][1] for i in grp), cfg["snap_m"])
            lv = f["levels"]
            if z1 > lv[-1] - cfg["top_keep_m"]:  # never open the top band (parapet / roof edge)
                z1 = math.floor((lv[-1] - cfg["top_keep_m"]) / cfg["snap_m"] + 1e-9) * cfg["snap_m"]
            glass = [i for i in grp if i["cls"] != "stem"] or grp
            dep = sorted(i["depth"] for i in glass)[len(glass) // 2]
            rv = round(min(cfg["reveal_max_m"], max(cfg["reveal_min_m"], dep)), 2)
            well = wells.get(f["volume"])
            if well and z1 > well["deck_z"]:  # [D384] a window plane above the deck must stay in front of the well wall
                par = float(well.get("parapet_m_by_edge", {}).get(k, well["parapet_m"]))
                if rv >= par - 0.05:
                    z1 = math.floor(well["deck_z"] / cfg["snap_m"] + 1e-9) * cfg["snap_m"]
            z1 = round(z1, 3)
            why = None
            if s1 - s0 < cfg["min_width_m"]:
                why = "sliver %.3f m" % (s1 - s0)
            else:
                h0 = z1 - z0
                z0, z1, why = resolve(k, s0, s1, z0, z1, lv, built + rects, cfg, frames)
                if not why and z1 - z0 < cfg["min_kept_frac"] * h0:
                    why = "trimmed to %.2f of %.2f m by its neighbours" % (z1 - z0, h0)
            if why:
                rep["not_cut"].append({"edge": k, "facade": f["facade"], "rect": [round(s0, 3), round(s1, 3), z0, z1],
                                       "members": [i["name"] for i in grp], "reason": why})
                for i in grp:
                    rep["objects"][i["name"]]["status"] = "not_cut_conflict"
                continue
            fill = sum((i["s"][1] - i["s"][0]) * (i["z"][1] - i["z"][0]) for i in grp) / ((s1 - s0) * (z1 - z0))
            name = "B006-%s-%02d" % (k, len(rects) + 1)
            kinds = sorted({i["cls"] for i in grp})
            rects.append({"name": name, "facade": f["facade"], "kind": "+".join(kinds), "edge": k,
                          "projected_rect": [round(s0, 4), round(s1, 4), z0, z1], "state": "contour_cut",
                          "source": "Revit split v004 %d objects (%s), body v006 #1784 [D408]" % (len(grp), ",".join(kinds)),
                          "members": [i["name"] for i in grp]})
            reveals[name] = rv
            rep["rects"].append({"name": name, "edge": k, "facade": f["facade"], "rect": [round(s0, 3), round(s1, 3), z0, z1],
                                 "members": len(grp), "kinds": kinds, "fill": round(fill, 3), "reveal_m": rv})
            for i in grp:
                rep["objects"][i["name"]]["opening"] = name
    rep["counts"] = {"rects": len(rects)}
    # placed = the object's centre lies in a body opening (accepted or new) of its edge after trimming
    for name, x in rep["objects"].items():
        if x["status"] in ("new_opening", "not_cut_conflict"):
            hit = covered(x["edge"], x["s"][0], x["s"][1], x["z"][0], x["z"][1], built + rects, cfg["cover_tol_m"])
            x["status"] = "new_opening" if hit else ("trimmed_out" if x["status"] == "new_opening" else x["status"])
            if hit:
                x["opening"] = hit
    tab: dict = {}
    for x in rep["objects"].values():
        tab.setdefault(x["cls"], {}).setdefault(x["status"], 0)
        tab[x["cls"]][x["status"]] += 1
    rep["by_status"] = tab
    return rects, reveals, rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dump")
    ap.add_argument("plan")
    ap.add_argument("volume_lines")
    ap.add_argument("body_config_in")
    ap.add_argument("cfg_out")
    ap.add_argument("report")
    a = ap.parse_args(argv)
    rd = lambda p: json.load(open(p, encoding="utf-8"))  # noqa: E731
    dump, plan, vl, bc = rd(a.dump), rd(a.plan), rd(a.volume_lines), rd(a.body_config_in)
    rects, reveals, rep = derive(dump["objects"], plan, vl, bc)
    out = dict(bc)
    out["_comment_body_v006"] = ("#1784 body v006 [D408]: the v007 config + openings for the Revit fill the "
                                 "accepted body had no opening for, generated by hooks/body_openings.py")
    out["extra_rectangles"] = list(bc.get("extra_rectangles", [])) + [{k: v for k, v in r.items() if k != "members"}
                                                                     for r in rects]
    out["reveal_m_by_name"] = dict(bc.get("reveal_m_by_name", {}), **reveals)
    with open(a.cfg_out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    with open(a.report, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({"rects": len(rects), "by_status": rep["by_status"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
