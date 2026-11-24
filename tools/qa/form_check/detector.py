"""Form check v1 - scene readback detector (OBSERVE, report only; never a delivery gate).

Assembled from autoresearch rounds, without retuning anything:
* frozen held-out scorer of t_563a40f7 (`score_heldout.py`, tolerances `TOL` verbatim): contour at the contour
  sections, opening presence / edges / sill-head / reveal depth at the opening sections, extra wall gaps;
* C1 of #43: the same 0.05 m two-sided contour tolerance also at the opening sections ("band contour");
* rim-loop fallback of #53: when no back-rim loop lies within 0.5 m of the gap mid, take the band loop whose
  centroid is inside the observed gap and 0.02 < |d| <= 1.5 m (closest to mid);
* reveal-flank depth selector of #54-#56: depth = |rim offset - median offset of the wall flanks touching the
  OBSERVED gap edges|, i.e. relative to the candidate's own facade, not the key line; flanks spread > 0.015 m
  -> `noncoplanar`, a missing flank -> `flank_missing` (fail-closed, never a guessed depth).

Statuses: pass / fail / not_measured / not_applicable. Only `pass` counts as success. Artem's rules
(`rules.py`) are applied afterwards and only relabel a fail as `expected`, with the cited basis.

Inputs are plain JSON: the key (`heldout-key/1`, as written by t_563a40f7 `make_key.py`), its sections
(`{z_label: [[p, q], ...]}`) and a candidate extract (`extract_blender.py`: `sections`, `loops`, `objects`).
An optional key `profile` overrides the section labels for fragments whose floor is not the G22 one.
"""
from __future__ import annotations

import math
import statistics

TOL = {"contour_max_dev_m": 0.05, "opening_edge_m": 0.03, "reveal_depth_m": 0.015, "sill_head_m": 0.02,
       "wall_line_search_m": 0.12, "parallel_cos": 0.98, "gap_min_m": 0.20, "basket_out_m": 0.03, "sample_m": 0.05}
RIM_MATCH_M = 0.5          # frozen: rim loop within 0.5 m of the gap mid
GAP_SEARCH_M = 0.6         # frozen: gap search window beyond the key edges
FALLBACK_MAX_D = 1.5       # #53
DEFAULT_PROFILE = {"contour_z": ["16.85", "19.8"], "opening_z": ["17.8", "18.2"], "rim_z0": [17.0, 17.6]}


def inbox(p, box, m=0.0):
    return box[0] - m <= p[0] <= box[2] + m and box[1] - m <= p[1] <= box[3] + m


def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = dx * dx + dy * dy
    t = 0.0 if den == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / den))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def samples(segs, box, step):
    out = []
    for a, b in segs:
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        for k in range(n + 1):
            p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
            if inbox(p, box):
                out.append(p)
    return out


def hausdorff(cs, ks, box, mask=None):
    """Two-sided max deviation inside the box: (dev, [x, y], side) or None when one side is empty.
    `mask(p)` -> True excludes a sample point (reference known wrong there, see `score`)."""
    worst = (0.0, None, None)
    for src, dst, side in ((cs, ks, "candidate->key"), (ks, cs, "key->candidate")):
        if not dst:
            return None
        for p in samples(src, box, TOL["sample_m"]):
            if mask and mask(p):
                continue
            d = min(seg_d(p, a, b) for a, b in dst)
            if d > worst[0]:
                worst = (d, [round(p[0], 3), round(p[1], 3)], side)
    return worst


def frame(ring, i, j):
    a, b = ring[i], ring[j]
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    return a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L), L


def local(p, a, u):
    dx, dy = p[0] - a[0], p[1] - a[1]
    return dx * u[0] + dy * u[1], dx * u[1] - dy * u[0]  # t along, d signed across


def wall_intervals(segs, a, u):
    iv = []
    for p, q in segs:
        (t0, d0), (t1, d1) = local(p, a, u), local(q, a, u)
        ln = math.hypot(q[0] - p[0], q[1] - p[1])
        if ln < 1e-6:
            continue
        cos = abs((q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1]) / ln
        if cos >= TOL["parallel_cos"] and abs(d0) < TOL["wall_line_search_m"] and abs(d1) < TOL["wall_line_search_m"]:
            iv.append((min(t0, t1), max(t0, t1)))
    iv.sort()
    merged = []
    for s, e in iv:
        if merged and s <= merged[-1][1] + 1e-3:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def gaps(merged, lo, hi):
    out, cur = [], lo
    for s, e in merged:
        if e <= lo or s >= hi:
            continue
        if s > cur + TOL["gap_min_m"]:
            out.append((cur, s))
        cur = max(cur, e)
    if hi > cur + TOL["gap_min_m"]:
        out.append((cur, hi))
    return out


def st(ok, basis, **extra):
    return {"status": "pass" if ok else "fail", "basis": basis, **extra}


def nm(basis, **extra):
    return {"status": "not_measured", "basis": basis, **extra}


def flank_depth(segs, a, u, gap, rim_d):
    """#54 selector: wall flanks parallel to the facade within the search band whose end touches the OBSERVED gap
    edge (#56); returns (status, depth, flank_line, spread)."""
    edge, band = TOL["opening_edge_m"], TOL["wall_line_search_m"]
    sides = ([], [])
    for p, q in segs:
        (t0, d0), (t1, d1) = sorted((local(p, a, u), local(q, a, u)))
        length = math.dist(p, q)
        if length < 1e-6 or (t1 - t0) / length < TOL["parallel_cos"] or max(abs(d0), abs(d1)) >= band:
            continue
        if t0 < gap[0] - edge and abs(t1 - gap[0]) <= edge:
            sides[0].append((d0, d1))
        if t1 > gap[1] + edge and abs(t0 - gap[1]) <= edge:
            sides[1].append((d0, d1))
    if not (sides[0] and sides[1]):
        return "flank_missing", None, None, None
    ds = [d for side in sides for pair in side for d in pair]
    spread = max(ds) - min(ds)
    line = statistics.median(ds)
    if spread > TOL["reveal_depth_m"]:
        return "noncoplanar", None, line, spread
    return "measured", abs(rim_d - line), line, spread


def score(key, ksec, cand, profile=None):
    """Return {'items': {...}, 'extra_openings': [...], 'openings_obs': {...}} for one candidate."""
    prof = {**DEFAULT_PROFILE, **(key.get("profile") or {}), **(profile or {})}
    cz, oz, (rz0, rz1) = prof["contour_z"], prof["opening_z"], prof["rim_z0"]
    ring = {r["ring_index"]: r["xy"] for r in key["contour_vertices_in_box"]}
    box = key["box_xy_m"]
    zs = sorted(set(cz) | set(oz))
    csec = {z: [s for s in cand["sections"].get(z, []) if inbox(s[0], box, 0.5) or inbox(s[1], box, 0.5)]
            for z in zs}
    items, obs = {}, {}
    # key amendments (#52): the key ring bridges a gap that the SOURCE outer wall has; the key is wrong there, so
    # the contour is not compared inside that span and the gap is measured against the source wall line instead.
    amend = (key.get("amend") or {})
    src_gaps = amend.get("source_wall_gaps", [])
    depth_ref = amend.get("reveal_depth_reference")  # e.g. {"status": "open", "basis": "..."}

    def masked(p):
        for sg in src_gaps:
            a, u, _ = frame(ring, *sg["ring_seg"])
            t, d = local(p, a, u)
            if sg["span_m"][0] - 0.05 <= t <= sg["span_m"][1] + 0.05 and abs(d) <= sg.get("depth_m", 1.5):
                return True
        return False

    # contour (frozen) + band contour (C1 #43)
    for z, kind in [(z, "contour") for z in cz] + [(z, "band_contour") for z in oz if z not in cz]:
        name = f"{kind}@{z}"
        if z not in ksec:
            items[name] = nm("key has no section at this level")
            continue
        if kind == "band_contour" and any(ksec[z] == ksec[c] for c in cz if c in ksec):
            items[name] = nm("key band section is the bare ring (no openings/reveals), C1 needs a faithful band key")
            continue
        h = hausdorff(csec[z], ksec[z], box, masked if src_gaps else None)
        if h is None:
            items[name] = nm("no section geometry in box")
        else:
            note = f"; masked source-wall gaps {[g['id'] for g in src_gaps]}" if src_gaps else ""
            items[name] = st(h[0] <= TOL["contour_max_dev_m"], f"two-sided max {h[0]:.3f} m at {h[1]} ({h[2]}){note}",
                             dev_m=round(h[0], 4), at=h[1])
    for sg in src_gaps:
        a, u, _ = frame(ring, *sg["ring_seg"])
        s0, s1 = sg["span_m"]
        lo, hi = s0 - GAP_SEARCH_M, s1 + GAP_SEARCH_M
        worst = 0.0
        for z in cz:
            walls = [(max(lo, s), min(hi, e)) for s, e in wall_intervals(csec[z], a, u) if e > lo and s < hi]
            covered_in = sum(max(0.0, min(e, s1) - max(s, s0)) for s, e in walls)
            covered_out = sum(max(0.0, e - s) for s, e in walls) - covered_in
            worst = max(worst, covered_in + ((hi - lo) - (s1 - s0) - covered_out))
        items[f"source_gap:{sg['id']}"] = st(worst <= TOL["contour_max_dev_m"],
                                             f"wall-line disagreement {worst:.3f} m vs source gap {s0:.3f}..{s1:.3f} "
                                             f"on seg {sg['ring_seg']} ({sg['basis']})", dev_m=round(worst, 4))
    matched = []
    loops = [lp for lp in cand.get("loops", []) if inbox(lp["c"], box) and rz0 <= lp["z"][0] <= rz1]
    for o in key["openings"]:
        pid = f"opening:{o['id']}"
        i, j = o["contour_segment"]
        a, u, _ = frame(ring, i, j)
        e0, e1 = o["edge_s_m"]
        found = []
        for z in oz:
            g = [gp for gp in gaps(wall_intervals(csec[z], a, u), e0 - GAP_SEARCH_M, e1 + GAP_SEARCH_M)
                 if gp[0] < (e0 + e1) / 2 < gp[1]]
            found.append(g[0] if g else None)
        if not all(found):
            items[pid + ":present"] = {"status": "fail", "basis": f"no wall gap at mid-span on ring seg {i}-{j} in {oz}"}
            for k in ("edges", "reveal_depth", "sill_head"):
                items[f"{pid}:{k}"] = nm("opening missing")
            continue
        g = found[-1]
        matched.append((i, g))
        obs[o["id"]] = {"gap_m": [[round(f[0], 4), round(f[1], 4)] for f in found], "key_edges_m": [e0, e1]}
        items[pid + ":present"] = st(True, f"gap {g[0]:.3f}..{g[1]:.3f} m on seg {i}-{j}")
        de = max(max(abs(f[0] - e0), abs(f[1] - e1)) for f in found)
        items[pid + ":edges"] = st(de <= TOL["opening_edge_m"], f"max edge delta {de:.3f} m (key {e0:.3f}..{e1:.3f})",
                                   observed=[[round(f[0], 4), round(f[1], 4)] for f in found], key=[e0, e1])
        mid = (a[0] + u[0] * (g[0] + g[1]) / 2, a[1] + u[1] * (g[0] + g[1]) / 2)
        lp = [x for x in loops if math.hypot(x["c"][0] - mid[0], x["c"][1] - mid[1]) < RIM_MATCH_M]
        src = "frozen_match"
        if not lp:  # #53 fallback
            mt = (g[0] + g[1]) / 2
            fb = [(abs(local(x["c"], a, u)[0] - mt), x) for x in loops
                  if g[0] <= local(x["c"], a, u)[0] <= g[1] and 0.02 < abs(local(x["c"], a, u)[1]) <= FALLBACK_MAX_D]
            lp = [min(fb, key=lambda r: r[0])[1]] if fb else []
            src = "fallback" if lp else "none"
        if lp:
            rim = lp[0]
            dz = max(abs(rim["z"][0] - o["sill_head_z_m"][0]), abs(rim["z"][1] - o["sill_head_z_m"][1]))
            items[pid + ":sill_head"] = st(dz <= TOL["sill_head_m"], f"rim z {rim['z']} vs key {o['sill_head_z_m']}",
                                           rim_source=src)
            fs, depth, line, spread = flank_depth(csec[oz[-1]], a, u, g, local(rim["c"], a, u)[1])
            obs[o["id"]] |= {"rim_source": src, "flank_status": fs, "depth_m": None if depth is None else round(depth, 4)}
            ref = o.get("reveal_depth_m")
            if fs != "measured" or depth is None:
                items[pid + ":reveal_depth"] = nm(f"flank selector: {fs}")
            elif depth_ref and depth_ref.get("status") == "open":
                items[pid + ":reveal_depth"] = nm(f"reference undecided: {depth_ref['basis']}; measured {depth:.3f}",
                                                  depth_m=round(depth, 4))
            elif ref is None:
                items[pid + ":reveal_depth"] = nm("key carries no reveal depth", depth_m=round(depth, 4))
            else:
                items[pid + ":reveal_depth"] = st(abs(depth - ref) <= TOL["reveal_depth_m"],
                                                  f"depth {depth:.3f} (own facade -> back rim) vs key {ref:.3f}",
                                                  depth_m=round(depth, 4), key_m=ref)
        else:
            items[pid + ":sill_head"] = nm("no back rim loop (closed or filled back)")
            items[pid + ":reveal_depth"] = nm("no back rim loop")
    extras = []
    zx = oz[-1]
    for i in sorted(ring):
        if i + 1 not in ring:
            continue
        a, u, L = frame(ring, i, i + 1)
        for gp in gaps(wall_intervals(csec[zx], a, u), 0.05, L - 0.05):
            mp = (a[0] + u[0] * (gp[0] + gp[1]) / 2, a[1] + u[1] * (gp[0] + gp[1]) / 2)
            if not inbox(mp, box) or any(mi == i and mg[0] < (gp[0] + gp[1]) / 2 < mg[1] for mi, mg in matched):
                continue
            if any(list(sg["ring_seg"]) == [i, i + 1] and sg["span_m"][0] - GAP_SEARCH_M < (gp[0] + gp[1]) / 2
                   < sg["span_m"][1] + GAP_SEARCH_M for sg in src_gaps):
                continue  # the source wall has this gap (#52), measured by `source_gap:*`
            extras.append({"ring_seg": [i, i + 1], "gap_m": [round(gp[0], 3), round(gp[1], 3)],
                           "at": [round(mp[0], 3), round(mp[1], 3)]})
    if not extras:
        items["openings:no_extra_in_box"] = st(True, f"no extra wall gaps at {zx}")
    for ex in extras:  # one item per extra gap, so an accepted one can be matched by location
        items[f"extra_gap:{ex['ring_seg'][0]}-{ex['ring_seg'][1]}@{ex['gap_m'][0]:.2f}"] = st(
            False, f"extra wall gap at {zx}: seg {ex['ring_seg']} {ex['gap_m']} m", at=ex["at"],
            dev_m=round(ex["gap_m"][1] - ex["gap_m"][0], 3))
    return {"items": items, "extra_openings": extras, "openings_obs": obs, "profile": prof}


def summarize(items):
    out = {s: 0 for s in ("pass", "fail", "expected", "not_measured", "not_applicable")}
    for v in items.values():
        out[v["status"]] = out.get(v["status"], 0) + 1
    return out


def verdict(items):
    """Form verdict of one candidate: 'defect' if any fail is left after Artem's rules, else 'ok' when at least one
    item was measured, else 'not_measured'."""
    s = summarize(items)
    if s["fail"]:
        return "defect"
    return "ok" if s["pass"] + s["expected"] else "not_measured"
