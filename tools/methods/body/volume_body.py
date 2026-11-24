"""Volume body (#1784, [D375]): accepted per-volume lines -> one BodyPlan per volume -> body through the shared core.

Pattern: n/a | new-case: step-2 adapter from an accepted per-volume lines file (step-1 `volume-lines.json`: volumes
with their own ring + levels, edges, opening rectangles snapped to the levels) to the #1736 BodyPlan format, plus the
post-ops the core does not have: local cuts (an opening head between two levels, [D375] doors at +2.175 m), separate
window planes inside the reveals, top/bottom caps, and the topology metrics of the step-2 sheet.

Rules (Artem 2026-11-21/23, [D375]): every volume has its own closed rings (one plan per volume, floors = 1, loops =
the volume's levels); an opening is a removed lattice cell with a reveal (the core), the window is a separate plane
with no loops of its own; a local cut stops at the opening's jambs (the neighbouring wall cell gets the extra vertex,
no fourth ring). Body only from the lattice; nothing is read from the Revit mesh here.

Pure Python. The core (`body_lattice.py`, PR #1770) is loaded from a directory given by the caller
(`load_core`), so this module works with main once #1770 merges and with the read-only branch head before that.
Every rectangle of the input ends in a window, a local cut or the `dropped` list with its state as the reason.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
import sys

EPS = 1e-4
DEFAULT_CFG = {
    "reveal_m": 0.15,          # opening reveal depth (cell removed, reveal tube; the window plane sits at its back)
    "level_snap_m": 0.20,      # [D375] an opening edge snaps to a level within 20 cm
    "station_merge_m": 0.10,   # jamb positions closer than this are one station (no sliver cells)
    "wall_tile_m": 3.0,
    "materials": {"WALL": [0.82, 0.80, 0.76], "WINDOW": [0.25, 0.45, 0.65], "ROOF": [0.45, 0.45, 0.47]},
    "build_states": ["cut"],
    "local_states": ["level_conflict"],
    # [D376] (1): a window crossing the visible band of a seam side opens only above the joint (sill = visible_from)
    "partial_states": ["crosses_visible_band"],
    # [D376] (2): a contour cut agreed in sections (F05 glazing) may have a local sill and a local head
    "contour_states": ["contour_cut"],
    "extra_rectangles": [],     # job rectangles not in the volume-lines file (the F05 contour), same record format
    "reveal_m_by_name": {},     # [D376] (4): mouth depth = inset seat for named rectangles (F13 pairs)
    "agreed_edge_clamps": {},   # [D376] (3): name -> agreed narrowing at the edge end, m (22daf24 0.268)
    "edge_clamp_tol_m": 0.005,
    "seam_weld_m": 0.001,       # #1802: mate ends must coincide within 1 mm (was 5 cm -> silent slit)
}


def load_core(core_dir):
    """Import body_lattice.py from `core_dir` (main after #1770 merges, else the read-only branch head)."""
    path = os.path.join(core_dir, "body_lattice.py")
    if not os.path.isfile(path):
        raise FileNotFoundError("shared body core not found: %s" % path)
    spec = importlib.util.spec_from_file_location("body_lattice_core", path)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load the body core from %s" % path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _ring(xy):
    pts = [list(map(float, p)) for p in xy]
    if len(pts) > 1 and math.dist(pts[0], pts[-1]) < EPS:
        pts = pts[:-1]
    if len(pts) < 3 or not all(_finite(c) for p in pts for c in p):
        raise ValueError("volume ring needs >= 3 finite points")
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2
    if abs(area) < EPS:
        raise ValueError("volume ring has zero area")
    return pts, area < 0


def _level_index(levels, z, tol):
    i = min(range(len(levels)), key=lambda k: abs(levels[k] - z))
    return i if abs(levels[i] - z) <= tol + 1e-9 else None


def plans_from_volume_lines(vl, cfg=None):
    """{volume: {"plan", "local", "dropped", "edge_s"}} from an accepted volume-lines dict.

    plan: BodyPlan (floors 1, loops = the volume levels below its top, one ring CCW, cuts = merged jambs, windows
    [0, s0, s1, wl, wh, reveal]). local: [{"window": i, "zt": z}] openings whose head lies between levels wh-1 and
    wh ([D375] local cut). dropped: rectangles not built, with their state as the reason. Errors name the record."""
    cfg = dict(DEFAULT_CFG, **(cfg or {}))
    vols, edges, rects = vl.get("volumes"), vl.get("edges"), vl.get("rectangles")
    if not (isinstance(vols, dict) and vols and isinstance(edges, dict) and isinstance(rects, list)):
        raise ValueError("volume-lines needs non-empty volumes, edges and rectangles")
    out = {}
    for vn, v in vols.items():
        ring, reversed_ = _ring(v["ring"])
        levels = [float(z) for z in v["levels"]]
        if len(levels) < 2 or any(b <= a for a, b in zip(levels, levels[1:])):
            raise ValueError("volume %s: levels must rise strictly, got %r" % (vn, levels))
        src = [list(map(float, p)) for p in (v["ring"][:-1] if v["ring"][0] == v["ring"][-1] else v["ring"])]
        ves = [k for k, e in edges.items() if e.get("volume") == vn]
        if len(ves) != len(src):
            raise ValueError("volume %s: %d edges for %d ring sides" % (vn, len(ves), len(src)))
        off, acc = {}, 0.0
        for i, k in enumerate(ves):
            a, b = src[i], src[(i + 1) % len(src)]
            if math.dist(edges[k]["xy"][0], a) > 1e-6 or math.dist(edges[k]["xy"][1], b) > 1e-6:
                raise ValueError("edge %s is not ring side %d of volume %s" % (k, i, vn))
            off[k] = acc
            acc += math.dist(a, b)
        perim = acc
        if reversed_:
            ring = [ring[0]] + ring[:0:-1]  # same start point: s_ccw = perimeter - s_source
        out[vn] = {"ring": ring, "perim": perim, "levels": levels, "off": off, "reversed": reversed_,
                   "openings": [], "dropped": [], "seams": [], "agreed_edges": []}
    weld = cfg["seam_weld_m"]
    for vn, V in out.items():  # seam sides hidden by the mate volume over the band both volumes share (#1802)
        for k in V["off"]:
            e = edges[k]
            if not e.get("mate"):
                continue
            mate = edges.get(e["mate"])
            if mate is None or mate.get("volume") not in out:
                raise ValueError("seam edge %s: mate %r is not an edge of a known volume" % (k, e.get("mate")))
            same = math.dist(e["xy"][0], mate["xy"][0]) <= weld and math.dist(e["xy"][1], mate["xy"][1]) <= weld
            flip = math.dist(e["xy"][0], mate["xy"][1]) <= weld and math.dist(e["xy"][1], mate["xy"][0]) <= weld
            if not (same or flip):
                raise ValueError("seam edge %s and its mate %s do not share their ends within %.3f m (a slit or a "
                                 "lap, #1802)" % (k, e["mate"], weld))
            M = out[mate["volume"]]
            z_from = max(V["levels"][0], M["levels"][0])
            z_hid = min(V["levels"][-1], M["levels"][-1])
            V["seams"].append({"edge": k, "mate": e["mate"], "xy": e["xy"], "hidden_from": z_from,
                               "hidden_to": z_hid})
    local_sill = set(cfg["partial_states"]) | set(cfg["contour_states"])
    local_head = set(cfg["local_states"]) | set(cfg["contour_states"])
    built = set(cfg["build_states"]) | local_head | local_sill
    for r in list(rects) + list(cfg["extra_rectangles"]):
        e = edges.get(r.get("edge")) if r.get("edge") else None
        state = r.get("state")
        name = r.get("name", "?")
        if state not in built:
            out_v = out.get(e["volume"]) if e else None
            target = out_v["dropped"] if out_v else out.setdefault("_unbound", {"dropped": []})["dropped"]
            target.append({"name": name, "facade": r.get("facade"), "edge": r.get("edge"), "reason": state})
            continue
        if e is None or e.get("volume") not in out:
            raise ValueError("rectangle %s (%s) has no edge of a known volume" % (name, state))
        V = out[e["volume"]]
        rect = r.get("snapped_rect") or r.get("projected_rect")
        if not (isinstance(rect, list) and len(rect) == 4 and all(_finite(c) for c in rect)):
            raise ValueError("rectangle %s: rect must be 4 finite numbers, got %r" % (name, rect))
        s0, s1, z0, z1 = rect
        if not (s0 < s1 and z0 < z1):
            raise ValueError("rectangle %s: empty rect %r" % (name, rect))
        _check_edge_clamp(r, rect, V, cfg)
        partial_from = None
        if state in cfg["partial_states"]:  # [D376] (1): only the part above the joint is visible
            vis = float(e.get("visible_from") or 0.0)
            if z1 <= vis + cfg["level_snap_m"]:
                V["dropped"].append({"name": name, "facade": r.get("facade"), "edge": r.get("edge"),
                                     "reason": "hidden_below_visible_band"})
                continue
            if z0 < vis:
                z0 = partial_from = vis
        a, b = V["off"][r["edge"]] + s0, V["off"][r["edge"]] + s1
        if a < -EPS or b > V["perim"] + EPS:
            raise ValueError("rectangle %s: [%.3f, %.3f] leaves the ring perimeter %.3f" % (name, a, b, V["perim"]))
        if V["reversed"]:
            a, b = V["perim"] - b, V["perim"] - a
        wl = _level_index(V["levels"], z0, cfg["level_snap_m"])
        zs = None
        if wl is None:
            if state not in local_sill:
                raise ValueError("rectangle %s: bottom %.3f is not within %.2f m of a level" % (name, z0, cfg["level_snap_m"]))
            wl = max((k for k, z in enumerate(V["levels"]) if z < z0 - EPS), default=None)
            if wl is None:
                raise ValueError("rectangle %s: sill %.3f below the volume base" % (name, z0))
            zs = z0
        wh = _level_index(V["levels"], z1, cfg["level_snap_m"])
        zt = None
        if wh is None:
            if state not in local_head:
                raise ValueError("rectangle %s (%s): head %.3f is not on a level" % (name, state, z1))
            wh = next((k for k, z in enumerate(V["levels"]) if z > z1 + EPS), None)
            if wh is None:
                raise ValueError("rectangle %s: head %.3f above the volume top" % (name, z1))
            zt = z1
        if wh <= wl:
            raise ValueError("rectangle %s: head level %d not above sill level %d" % (name, wh, wl))
        if zs is not None and zt is not None and wh - wl == 1 and zt - zs < cfg["level_snap_m"]:
            raise ValueError("rectangle %s: local sill %.3f and head %.3f too close" % (name, zs, zt))
        rv = float(cfg["reveal_m_by_name"].get(name, cfg["reveal_m"]))
        V["openings"].append({"name": name, "facade": r.get("facade"), "edge": r["edge"], "s": [a, b],
                              "wl": wl, "wh": wh, "zt": zt, "zs": zs, "r": rv, "state": state,
                              "partial_from": partial_from})
    for name, rv in cfg["reveal_m_by_name"].items():
        if not (_finite(rv) and 0 < rv < 1.0):
            raise ValueError("reveal_m_by_name %s: reveal must be in (0, 1) m, got %r" % (name, rv))
    result = {}
    for vn, V in out.items():
        if vn == "_unbound":
            continue
        result[vn] = _plan_for_volume(vn, V, cfg)
    if "_unbound" in out:
        result["_unbound"] = {"dropped": out["_unbound"]["dropped"]}
    return result


def _check_edge_clamp(r, rect, V, cfg):
    """[D376] (3): an opening narrower than its source rect (cut at the edge end) is built only as an agreed edge."""
    src, name, tol = r.get("source_rect"), r.get("name", "?"), cfg["edge_clamp_tol_m"]
    if not (isinstance(src, list) and len(src) == 4 and all(_finite(c) for c in src)):
        return
    d = (src[1] - src[0]) - (rect[1] - rect[0])
    agreed = cfg["agreed_edge_clamps"].get(name)
    if d <= tol:
        if agreed is not None:
            raise ValueError("rectangle %s: agreed edge clamp %.3f m but the rect is not narrowed" % (name, agreed))
        return
    if agreed is None:
        raise ValueError("rectangle %s is %.3f m narrower than its source at the edge end; list it in "
                         "agreed_edge_clamps [D376] or fix the lines" % (name, d))
    if abs(agreed - d) > tol:
        raise ValueError("rectangle %s narrowed by %.3f m, agreed %.3f m" % (name, d, agreed))
    V["agreed_edges"].append({"name": name, "edge": r.get("edge"), "clamp_m": round(d, 3), "agreed_m": agreed})


def _merge_stations(values, tol):
    vals = sorted(values)
    groups = []
    for x in vals:
        if groups and x - groups[-1][-1] <= tol:
            groups[-1].append(x)
        else:
            groups.append([x])
    rep = {}
    for g in groups:
        m = round(sum(g) / len(g), 4)
        for x in g:
            rep[x] = m
    return rep


def _plan_for_volume(vn, V, cfg):
    perim, levels = V["perim"], V["levels"]
    ends = [s for o in V["openings"] for s in o["s"]]
    rep = _merge_stations(ends, cfg["station_merge_m"])
    for o in V["openings"]:
        o["s"] = [min(max(rep[o["s"][0]], 0.0), perim), min(max(rep[o["s"][1]], 0.0), perim)]
        if o["s"][1] - o["s"][0] < EPS:
            raise ValueError("volume %s: opening %s collapses to zero width after station merge" % (vn, o["name"]))
    # merge openings that overlap or touch with the same levels (a zero pier would give coincident jambs)
    ops = sorted(V["openings"], key=lambda o: (o["wl"], o["wh"], o["zt"] or 0, o["zs"] or 0, o["r"], o["s"][0]))
    merged = []
    for o in ops:
        m = merged[-1] if merged else None
        if (m and m["wl"] == o["wl"] and m["wh"] == o["wh"] and m["zt"] == o["zt"] and m["zs"] == o["zs"]
                and m["r"] == o["r"] and o["s"][0] <= m["s"][1] + EPS):
            m["s"][1] = max(m["s"][1], o["s"][1])
            m["names"].append(o["name"])
            continue
        merged.append(dict(o, s=list(o["s"]), names=[o["name"]]))
    for i, a in enumerate(merged):  # different levels / seats sharing cells or a station = an error naming both
        for b in merged[i + 1:]:
            if a["s"][0] <= b["s"][1] + EPS and b["s"][0] <= a["s"][1] + EPS and a["wl"] < b["wh"] and b["wl"] < a["wh"]:
                raise ValueError("volume %s: openings %s and %s overlap or touch with different levels"
                                 % (vn, a["names"], b["names"]))
    merged.sort(key=lambda o: o["s"][0])
    z0 = levels[0]
    plan = {"step": round(levels[-1] - z0, 6), "z0": z0, "floors": 1,
            "loops": [round(z - z0, 6) for z in levels[:-1]],
            "rings": [{"xy": V["ring"], "cuts": sorted({s for o in merged for s in o["s"]})}],
            "windows": [[0, o["s"][0], o["s"][1], o["wl"], o["wh"], o["r"]] for o in merged],
            "materials": cfg["materials"], "wall_tile_m": cfg["wall_tile_m"],
            "provenance": {"volume": vn, "ring_reversed_from_source": V["reversed"]}}
    plan["rings"][0]["zones"] = [[0.0, perim, "WALL"]]
    local = []
    for i, o in enumerate(merged):
        if o["zt"] is None and o["zs"] is None:
            continue
        lc = {"window": i}
        if o["zt"] is not None:
            lc["zt"] = o["zt"]
        if o["zs"] is not None:
            lc["zs"] = o["zs"]
        local.append(lc)
    return {"plan": plan, "local": local, "openings": merged, "dropped": V["dropped"], "seams": V["seams"],
            "agreed_edges": V["agreed_edges"]}


# ---- post-ops on the core output {"verts": [(x,y,z)], "faces": [{"v", "mat", "uv"}]} --------------------------------
class _Index:
    def __init__(self, verts):
        self.map = {}
        for i, p in enumerate(verts):
            self.map.setdefault(self._k(p), []).append(i)

    @staticmethod
    def _k(p):
        return (round(p[0], 3), round(p[1], 3), round(p[2], 3))

    def one(self, p, what):
        hit = self.map.get(self._k(p), [])
        if len(hit) != 1:
            raise ValueError("%s: %d vertices at %r (expected 1)" % (what, len(hit), tuple(round(c, 3) for c in p)))
        return hit[0]


def _stations(core, plan, a, b):
    pts, perim = core.ring_points(plan["rings"][0]["xy"], plan["rings"][0]["cuts"], plan.get("max_side_m", 0.0))
    ks = [p for p in pts if a - EPS <= p[0] <= b + EPS]
    if len(ks) < 2:
        raise ValueError("opening [%.3f, %.3f] has < 2 stations" % (a, b))
    return ks


def apply_local_cuts(core, body, plan, local):
    """[D375] local cut: lower the head of opening `window` from level wh to zt between its own jambs.

    Moves the reveal head to zt, adds the wall cells zt..level(wh) above the opening and inserts the jamb vertex at
    zt into the neighbouring wall cell on each side (a 5-sided cell, no fourth ring). Works on world z."""
    verts, faces = body["verts"], body["faces"]
    z0 = plan["z0"]
    levels = [z0 + z for z in plan["loops"]] + [z0 + plan["step"]]
    tex = plan.get("wall_tile_m", 3.0)
    for lc in local:
        if lc.get("zt") is not None:
            _local_head(core, body, plan, levels, tex, plan["windows"][lc["window"]], lc["zt"])
        if lc.get("zs") is not None:
            _local_sill(core, body, plan, levels, tex, plan["windows"][lc["window"]], lc["zs"])
    return body


def _local_head(core, body, plan, levels, tex, w, zt):
    verts, faces = body["verts"], body["faces"]
    if True:
        a, b, wl, wh, r = w[1], w[2], int(w[3]), int(w[4]), w[5]
        if not (levels[wh - 1] + EPS < zt < levels[wh] - EPS):
            raise ValueError("local cut %r: zt %.3f not inside band %d" % (w, zt, wh - 1))
        idx = _Index(verts)
        ks = _stations(core, plan, a, b)
        inner = core.inner_offset([(p[1], p[2]) for p in ks], r)
        G = [idx.one((p[1], p[2], levels[wh]), "local cut %r outer head" % (w,)) for p in ks]
        Gl = {j: idx.one((ks[j][1], ks[j][2], levels[wh - 1]), "local cut %r outer below" % (w,))
              for j in (0, len(ks) - 1)}  # jamb ends only: grid points inside a multi-band opening are unused
        I = [idx.one((q[0], q[1], levels[wh]), "local cut %r inner head" % (w,)) for q in inner]
        P = []
        for p in ks:
            verts.append((p[1], p[2], zt))
            P.append(len(verts) - 1)
        gmap = dict(zip(G, P))
        iset = set(I)
        for f in faces:  # the door's own jambs and head: outer head vertices -> zt vertices
            if iset & set(f["v"]):
                f["v"] = tuple(gmap.get(i, i) for i in f["v"])
        for i in I:
            x, y, _ = verts[i]
            verts[i] = (x, y, zt)
        for f in faces:  # jamb / head UVs follow the moved vertices
            if iset & set(f["v"]) or set(P) & set(f["v"]):
                f["uv"] = _flat_uv(verts, f["v"], tex)
        for j in (0, len(ks) - 1):  # neighbour wall cell on each side gets the jamb vertex at zt
            e = {Gl[j], G[j]}
            hits = [f for f in faces if e <= set(f["v"]) and _has_edge(f["v"], Gl[j], G[j])]
            if len(hits) != 1:
                raise ValueError("local cut %r: %d faces on the jamb edge at s=%.3f" % (w, len(hits), ks[j][0]))
            f = hits[0]
            v = list(f["v"])
            n = len(v)
            for k in range(n):
                if {v[k], v[(k + 1) % n]} == e:
                    v.insert(k + 1, P[j])
                    break
            f["v"] = tuple(v)
            f["uv"] = _flat_uv(verts, f["v"], tex, ks[j][0])
        zone_mat = plan["rings"][0]["zones"][0][2]
        for j in range(len(ks) - 1):
            q = (P[j], P[j + 1], G[j + 1], G[j])
            faces.append({"v": q, "mat": zone_mat, "uv": [(ks[j + (1 if k in (1, 2) else 0)][0] / tex, verts[i][2] / tex)
                                                          for k, i in enumerate(q)]})
        body.setdefault("report", {}).setdefault("local_cuts", 0)
        body["report"]["local_cuts"] += 1
    return body


def _local_sill(core, body, plan, levels, tex, w, zs):
    """[D376] local sill: raise the sill of opening `w` from level wl to zs between its own jambs (mirror of the
    [D375] local head): the reveal bottom moves to zs, wall cells level(wl)..zs fill under the opening and the
    neighbour wall cell on each side gets the jamb vertex at zs (no new ring)."""
    verts, faces = body["verts"], body["faces"]
    a, b, wl, r = w[1], w[2], int(w[3]), w[5]
    if not (levels[wl] + EPS < zs < levels[wl + 1] - EPS):
        raise ValueError("local sill %r: zs %.3f not inside band %d" % (w, zs, wl))
    idx = _Index(verts)
    ks = _stations(core, plan, a, b)
    inner = core.inner_offset([(p[1], p[2]) for p in ks], r)
    Gb = [idx.one((p[1], p[2], levels[wl]), "local sill %r outer sill" % (w,)) for p in ks]
    S = [idx.one((q[0], q[1], levels[wl]), "local sill %r inner sill" % (w,)) for q in inner]
    P = []
    for p in ks:
        verts.append((p[1], p[2], zs))
        P.append(len(verts) - 1)
    gmap = dict(zip(Gb, P))
    sset = set(S)
    for f in faces:  # the opening's own jambs and sill: outer sill vertices -> zs vertices
        if sset & set(f["v"]):
            f["v"] = tuple(gmap.get(i, i) for i in f["v"])
    for i in S:
        x, y, _ = verts[i]
        verts[i] = (x, y, zs)
    for f in faces:
        if sset & set(f["v"]) or set(P) & set(f["v"]):
            f["uv"] = _flat_uv(verts, f["v"], tex)
    for j in (0, len(ks) - 1):  # neighbour wall cell: the edge from the sill corner straight up gets zs
        g = Gb[j]
        gx, gy, gz = verts[g]
        hits = []
        for f in faces:
            v = f["v"]
            n = len(v)
            for k in range(n):
                for u, t in ((v[k], v[(k + 1) % n]), (v[(k + 1) % n], v[k])):
                    if u == g:
                        q = verts[t]
                        if abs(q[0] - gx) < 1e-6 and abs(q[1] - gy) < 1e-6 and q[2] > zs + EPS:
                            hits.append((f, k))
        if len(hits) != 1:
            raise ValueError("local sill %r: %d faces on the jamb edge at s=%.3f" % (w, len(hits), ks[j][0]))
        f, k = hits[0]
        v = list(f["v"])
        v.insert(k + 1, P[j])
        f["v"] = tuple(v)
        f["uv"] = _flat_uv(verts, f["v"], tex, ks[j][0])
    zone_mat = plan["rings"][0]["zones"][0][2]
    for j in range(len(ks) - 1):
        q = (Gb[j], Gb[j + 1], P[j + 1], P[j])
        faces.append({"v": q, "mat": zone_mat, "uv": [(ks[j + (1 if k in (1, 2) else 0)][0] / tex, verts[i][2] / tex)
                                                      for k, i in enumerate(q)]})
    body.setdefault("report", {}).setdefault("local_sills", 0)
    body["report"]["local_sills"] += 1
    return body


def weld_stacked(body, grid=1e-3):
    """Weld vertices at one position (rounded to `grid`) and drop face pairs over the same vertex set.

    Two openings stacked over one level (the [D376] F05 glazing: a lower run with a local sill under a wider upper
    run) give the core two reveal faces at that level - the head of one and the sill of the other, a zero-thickness
    transom - and two vertex copies on it. After the weld both faces cover one vertex set and are removed together,
    leaving one mouth. Returns {"welded": n vertices, "faces_removed": n}."""
    key = {}
    remap = []
    welded = 0
    for i, p in enumerate(body["verts"]):
        k = (round(p[0] / grid), round(p[1] / grid), round(p[2] / grid))
        if k in key:
            remap.append(key[k])
            welded += 1
        else:
            key[k] = i
            remap.append(i)
    seen = {}
    for fi, f in enumerate(body["faces"]):
        f["v"] = tuple(remap[i] for i in f["v"])
        if len(set(f["v"])) != len(f["v"]):
            raise ValueError("weld collapsed face %d %r" % (fi, f["v"]))
        seen.setdefault(frozenset(f["v"]), []).append(fi)
    drop = set()
    for fs in seen.values():
        if len(fs) == 2:
            drop.update(fs)
        elif len(fs) > 2:
            raise ValueError("weld: %d faces over one vertex set" % len(fs))
    body["faces"] = [f for fi, f in enumerate(body["faces"]) if fi not in drop]
    compact(body)  # the welded copies and the transom-only vertices go, so position lookups stay unique
    return {"welded": welded, "faces_removed": len(drop)}


def _has_edge(v, a, b):
    n = len(v)
    return any({v[k], v[(k + 1) % n]} == {a, b} for k in range(n))


def _flat_uv(verts, v, tex, s_hint=None):
    """Planar UV of a face from its own plane (u along the horizontal tangent, v = z), metres / tex."""
    co = [verts[i] for i in v]
    nx = ny = 0.0
    for p, q in zip(co, co[1:] + co[:1]):
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
    L = math.hypot(nx, ny)
    if L < 1e-9:
        return [(p[0] / tex, p[1] / tex) for p in co]
    tx, ty = -ny / L, nx / L
    return [((p[0] * tx + p[1] * ty) / tex, p[2] / tex) for p in co]


def window_planes(core, plan, local):
    """Separate window planes at the back of every reveal: one quad per station segment, sill .. head (or zt)."""
    z0 = plan["z0"]
    levels = [z0 + z for z in plan["loops"]] + [z0 + plan["step"]]
    zt = {lc["window"]: lc["zt"] for lc in local if lc.get("zt") is not None}
    zsl = {lc["window"]: lc["zs"] for lc in local if lc.get("zs") is not None}
    verts, faces = [], []
    for wi, w in enumerate(plan["windows"]):
        a, b, wl, wh, r = w[1], w[2], int(w[3]), int(w[4]), w[5]
        ks = _stations(core, plan, a, b)
        inner = core.inner_offset([(p[1], p[2]) for p in ks], r)
        zb, zh = zsl.get(wi, levels[wl]), zt.get(wi, levels[wh])
        base = len(verts)  # one welded strip per opening: bottom row then top row (no duplicate vertices)
        verts += [(p[0], p[1], zb) for p in inner] + [(p[0], p[1], zh) for p in inner]
        m = len(inner)
        for j in range(m - 1):
            u0, u1 = (ks[j][0] - a) / (b - a), (ks[j + 1][0] - a) / (b - a)
            faces.append({"v": (base + j, base + j + 1, base + m + j + 1, base + m + j), "mat": "WINDOW",
                          "uv": [(u0, 0.0), (u1, 0.0), (u1, 1.0), (u0, 1.0)]})
    return {"verts": verts, "faces": faces}


def add_caps(core, body, plan, bottom=False):
    """Top cap (bottom only on request): one n-gon over the ring's stations, welded to the walls.

    No bottom cap by default: a door sill at the base level lies in the base plane and would overlap the cap (xView
    Overlapping Faces); the base ring stays an open boundary on the ground (reported as base_open_edges)."""
    pts, _ = core.ring_points(plan["rings"][0]["xy"], plan["rings"][0]["cuts"], plan.get("max_side_m", 0.0))
    idx = _Index(body["verts"])
    z0 = plan["z0"]
    tex = plan.get("wall_tile_m", 3.0)
    for z, up in ((z0 + plan["step"], True), (z0, False)):
        if not up and not bottom:
            continue
        ring = [idx.one((p[1], p[2], z), "cap at z=%.3f" % z) for p in pts]
        if not up:
            ring = ring[::-1]
        body["faces"].append({"v": tuple(ring), "mat": "ROOF",
                              "uv": [(body["verts"][i][0] / tex, body["verts"][i][1] / tex) for i in ring]})
    return body


def merge_planes(body, planes):
    """Weld the window planes into the body: every plane vertex is an existing reveal-back vertex (by position)."""
    idx = _Index(body["verts"])
    remap = [idx.one(p, "window plane vertex") for p in planes["verts"]]
    for f in planes["faces"]:
        body["faces"].append({"v": tuple(remap[i] for i in f["v"]), "mat": f["mat"], "uv": list(f["uv"])})
    return body


def remove_hidden_seam_cells(body, seams, tol=1e-3):
    """Drop the vertical faces of a seam side that the mate volume hides: all vertices on the seam segment and inside
    the band both volumes share, [`hidden_from`, `hidden_to`] (#1802: not below the mate's base). The volume's rings
    were proven closed on the full ring before; here the volumes meet along the seam ([D375]) instead of keeping two
    coincident walls (V004 co-directional clearance). Returns the count."""
    keep, dropped = [], 0
    for f in body["faces"]:
        co = [body["verts"][i] for i in f["v"]]
        hit = None
        for sm in seams:
            seg = ((sm["xy"][0][0], sm["xy"][0][1], 0.0), (sm["xy"][1][0], sm["xy"][1][1], 0.0))
            if (all(_on_segment((p[0], p[1], 0.0), seg, tol) for p in co)
                    and min(p[2] for p in co) >= sm.get("hidden_from", -math.inf) - tol
                    and max(p[2] for p in co) <= sm["hidden_to"] + tol and abs(_normal(co)[2]) < 0.1):
                hit = sm
                break
        if hit:
            dropped += 1
        else:
            keep.append(f)
    body["faces"] = keep
    return dropped


def compact(body):
    """Remove vertices no face uses (e.g. the core's grid vertex inside a multi-band opening); returns the count."""
    used = sorted({i for f in body["faces"] for i in f["v"]})
    remap = {o: n for n, o in enumerate(used)}
    gone = len(body["verts"]) - len(used)
    body["verts"] = [body["verts"][o] for o in used]
    for f in body["faces"]:
        f["v"] = tuple(remap[i] for i in f["v"])
    return gone


def classify_open_edges(body, base_z, seams, tol=1e-3):
    """Open edges by place: base ring (ground), seam (meets the mate volume), jamb_t (a door jamb back segment the
    welded window plane spans with one edge) and other (must be 0)."""
    cnt = {}
    for f in body["faces"]:
        v = f["v"]
        for a, b in zip(v, v[1:] + v[:1]):
            k = (min(a, b), max(a, b))
            cnt[k] = cnt.get(k, 0) + 1
    opens = [k for k, c in cnt.items() if c == 1]
    vv = body["verts"]
    win = []
    for f in body["faces"]:
        if f["mat"] == "WINDOW":
            v = f["v"]
            win += [(vv[a], vv[b]) for a, b in zip(v, v[1:] + v[:1])]
    out = {"base": 0, "seam": 0, "jamb_t": 0, "other": 0, "other_at": []}
    for a, b in opens:
        p, q = vv[a], vv[b]
        if abs(p[2] - base_z) < tol and abs(q[2] - base_z) < tol:
            out["base"] += 1
        elif any(_on_segment((p[0], p[1], 0.0), ((s["xy"][0][0], s["xy"][0][1], 0.0), (s["xy"][1][0], s["xy"][1][1],
                 0.0)), tol) and _on_segment((q[0], q[1], 0.0), ((s["xy"][0][0], s["xy"][0][1], 0.0),
                 (s["xy"][1][0], s["xy"][1][1], 0.0)), tol) for s in seams) or _on_seam_end(p, q, seams, tol):
            out["seam"] += 1
        elif any(_on_segment(p, w, tol) and _on_segment(q, w, tol) for w in win):
            out["jamb_t"] += 1
        else:
            out["other"] += 1
            if len(out["other_at"]) < 20:
                out["other_at"].append([[round(c, 3) for c in p], [round(c, 3) for c in q]])
    return out


def _on_seam_end(p, q, seams, tol):
    """A vertical edge standing on a seam end point (the corner the two volumes share)."""
    if math.hypot(p[0] - q[0], p[1] - q[1]) > tol:
        return False
    return any(math.hypot(p[0] - e[0], p[1] - e[1]) < tol for s in seams for e in s["xy"])


# ---- metrics ------------------------------------------------------------------------------------------------------
def _normal(co):
    nx = ny = nz = 0.0
    for a, b in zip(co, co[1:] + co[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    L = math.sqrt(nx * nx + ny * ny + nz * nz)
    return (nx / L, ny / L, nz / L, L / 2) if L > 0 else (0.0, 0.0, 0.0, 0.0)


def metrics(mesh, min_side=0.05, planar_tol=0.001):
    """Topology of one mesh: degrees, facade triangles / n-gons, open and non-manifold edges, defect cells.

    Facade = |nz| < 0.1. Defect cell = degenerate (area < 1e-4 m2), non-planar (> 1 mm) or with a side < min_side."""
    verts, faces = mesh["verts"], mesh["faces"]
    deg = {}
    edges = {}
    facade_tris = facade_ngons = 0
    defects = []
    for fi, f in enumerate(faces):
        v = f["v"]
        deg[len(v)] = deg.get(len(v), 0) + 1
        co = [verts[i] for i in v]
        nx, ny, nz, area = _normal(co)
        if abs(nz) < 0.1:
            if len(v) == 3:
                facade_tris += 1
            elif len(v) > 4:
                facade_ngons += 1
        why = None
        if area < 1e-4:
            why = "degenerate"
        else:
            d0 = sum(c * n for c, n in zip(co[0], (nx, ny, nz)))
            if max(abs(sum(c * n for c, n in zip(p, (nx, ny, nz))) - d0) for p in co) > planar_tol:
                why = "non_planar"
            else:
                sides = [math.dist(a, b) for a, b in zip(co, co[1:] + co[:1])]
                if min(sides) < min_side and len(v) <= 4:
                    why = "narrow"
        if why:
            defects.append({"face": fi, "why": why, "at": [round(c, 3) for c in co[0]]})
        for a, b in zip(v, v[1:] + v[:1]):
            k = (min(a, b), max(a, b))
            edges[k] = edges.get(k, 0) + 1
    tris = sum(n - 2 for n in (len(f["v"]) for f in faces))
    return {"verts": len(verts), "faces": len(faces), "degrees": {str(k): deg[k] for k in sorted(deg)},
            "tris_after_triangulation": tris, "facade_triangles": facade_tris, "facade_ngons": facade_ngons,
            "open_edges": sum(1 for c in edges.values() if c == 1),
            "non_manifold_edges": sum(1 for c in edges.values() if c > 2),
            "bowtie_vertices": bowtie_vertices(faces),
            "defect_cells": len(defects), "defects": defects[:50]}


def bowtie_vertices(faces):
    """Vertices whose faces form more than one edge-connected fan (xView 'bow-tie vertices')."""
    inc = {}
    for fi, f in enumerate(faces):
        for i in f["v"]:
            inc.setdefault(i, []).append(fi)
    bad = 0
    for i, fs in inc.items():
        if len(fs) < 2:
            continue
        nb = {}
        for fi in fs:  # the two edges of face fi at vertex i, as the far vertex of each
            v = faces[fi]["v"]
            k = v.index(i)
            for t in (v[k - 1], v[(k + 1) % len(v)]):
                nb.setdefault(t, []).append(fi)
        parent = {fi: fi for fi in fs}

        def root(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        for group in nb.values():
            for fi in group[1:]:
                parent[root(fi)] = root(group[0])
        if len({root(fi) for fi in fs}) > 1:
            bad += 1
    return bad


def merge_stacked_planes(body):
    """Join two WINDOW quads stacked over one shared horizontal edge into one quad (the [D376] F05 glazing seat).

    Without it the weld of stacked openings leaves the jamb fan and the window-plane fan meeting only at the jamb
    corner of the removed transom (an xView bow-tie vertex). Returns the number of joins."""
    vv = body["verts"]
    joins = 0
    while True:
        wins = [f for f in body["faces"] if f["mat"] == "WINDOW" and len(f["v"]) == 4]
        by_bottom = {}
        for f in wins:  # quads are (b0, b1, t1, t0): bottom edge = v[0], v[1]
            by_bottom[frozenset(f["v"][:2])] = f
        pair = None
        for f in wins:
            top = frozenset(f["v"][2:])
            g = by_bottom.get(top)
            if g is not None and g is not f and vv[g["v"][0]][2] > vv[f["v"][0]][2]:
                pair = (f, g)
                break
        if pair is None:
            return joins
        f, g = pair
        t1, t0 = (g["v"][2], g["v"][3]) if g["v"][1] == f["v"][2] else (g["v"][3], g["v"][2])
        others = [h for h in body["faces"] if h is not f and h is not g and h["mat"] == "WINDOW"]
        used = {i for h in others for i in h["v"]}
        # keep a shared corner another window plane uses (else a T-contact with it); drop it otherwise (bow-tie)
        q = [f["v"][0], f["v"][1]] + ([f["v"][2]] if f["v"][2] in used else []) + [t1, t0] \
            + ([f["v"][3]] if f["v"][3] in used else [])
        zb, zt = vv[f["v"][0]][2], vv[t0][2]
        ul, ur = f["uv"][0][0], f["uv"][1][0]
        right = {f["v"][1], f["v"][2], t1}
        uv = [(ur if i in right else ul, (vv[i][2] - zb) / (zt - zb)) for i in q]
        body["faces"] = [h for h in body["faces"] if h is not f and h is not g] + [
            {"v": tuple(q), "mat": "WINDOW", "uv": uv}]
        joins += 1


def _on_segment(p, s, tol=1e-3):
    a, b = s
    ab = [b[i] - a[i] for i in range(3)]
    ap = [p[i] - a[i] for i in range(3)]
    L2 = sum(c * c for c in ab)
    if L2 < 1e-12:
        return False
    t = sum(ab[i] * ap[i] for i in range(3)) / L2
    if t < -1e-6 or t > 1 + 1e-6:
        return False
    return math.dist(p, [a[i] + t * ab[i] for i in range(3)]) <= tol


def build_volume(core, entry):
    """Core body of one volume + local cuts + caps; returns {"body", "planes", "report"}."""
    plan = entry["plan"]
    module = core.build_module(plan)
    body = core.replicate(module, plan)
    body["verts"] = [(x, y, z + plan["z0"]) for x, y, z in body["verts"]]
    stacked = weld_stacked(body)
    apply_local_cuts(core, body, plan, entry["local"])
    add_caps(core, body, plan)
    planes = window_planes(core, plan, entry["local"])
    merge_planes(body, planes)
    plane_joins = merge_stacked_planes(body)
    seam_cells = remove_hidden_seam_cells(body, entry.get("seams", []))
    unused = compact(body)
    rep = {"closure": [r["closure"] for r in module["report"]["rings"]],
           "hidden_seam_cells_removed": seam_cells, "unused_vertices_removed": unused,
           "window_planes": len(planes["faces"]),
           "open_edges": classify_open_edges(body, plan["z0"], entry.get("seams", [])),
           "openings": len(plan["windows"]),
           "local_cuts": sum(1 for lc in entry["local"] if lc.get("zt") is not None),
           "local_sills": sum(1 for lc in entry["local"] if lc.get("zs") is not None),
           "stacked_faces_removed": stacked["faces_removed"], "stacked_plane_joins": plane_joins, "stacked_vertices_welded": stacked["welded"],
           "agreed_edges": entry.get("agreed_edges", []),
           "body": metrics(body)}
    return {"body": body, "report": rep}


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Volume body (#1784): volume-lines -> per-volume core body")
    ap.add_argument("volume_lines")
    ap.add_argument("out_dir")
    ap.add_argument("--core", required=True, help="directory holding body_lattice.py (#1736)")
    ap.add_argument("--config", help="JSON overrides of DEFAULT_CFG")
    a = ap.parse_args(argv)
    src = os.path.realpath(a.volume_lines)
    out = os.path.realpath(a.out_dir)
    if os.path.commonpath([src, out]) == out:
        print("error: out_dir contains the input", file=sys.stderr)
        return 2
    core = load_core(a.core)
    with open(src, encoding="utf-8") as fh:
        vl = json.load(fh)
    cfg = None
    if a.config:
        with open(a.config, encoding="utf-8") as fh:
            cfg = json.load(fh)
    entries = plans_from_volume_lines(vl, cfg)
    os.makedirs(out, exist_ok=True)
    report = {"input": src, "volumes": {}, "unbound_dropped": len(entries.get("_unbound", {}).get("dropped", []))}
    meshes = {}
    for vn, e in entries.items():
        if vn == "_unbound":
            continue
        r = build_volume(core, e)
        meshes[vn] = {"body": r["body"]}
        report["volumes"][vn] = dict(r["report"], dropped=len(e["dropped"]),
                                     dropped_by_reason=_count(d["reason"] for d in e["dropped"]),
                                     merged_openings=[o["names"] for o in e["openings"] if len(o["names"]) > 1])
        with open(os.path.join(out, "plan_%s.json" % vn), "w", encoding="utf-8") as fh:
            json.dump(e["plan"], fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "meshes.json"), "w", encoding="utf-8") as fh:
        json.dump({vn: {k: {"verts": m["verts"], "faces": m["faces"]} for k, m in d.items()}
                   for vn, d in meshes.items()}, fh)
    with open(os.path.join(out, "build_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps({vn: {"closure": v["closure"], "body": {k: v["body"][k] for k in (
        "faces", "facade_triangles", "facade_ngons", "open_edges", "non_manifold_edges", "defect_cells")},
        "open": v["open_edges"], "seam_cells": v["hidden_seam_cells_removed"], "local_cuts": v["local_cuts"], "openings": v["openings"]}
        for vn, v in report["volumes"].items()}, ensure_ascii=False))
    return 0


def _count(it):
    c = {}
    for x in it:
        c[x] = c.get(x, 0) + 1
    return c


if __name__ == "__main__":
    sys.exit(main())
