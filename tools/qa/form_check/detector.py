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
(`{z_label: [[p, q], ...]}`) and a candidate extract (`blender_scene.py extract`: `sections`, `loops`, `objects`).
An optional key `profile` overrides the section labels for fragments whose floor is not the G22 one.

new-case: tools/qa/form_check/detector.py - form check v1 scene detector
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

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


def _sub(a, b):
    return a[0] - b[0], a[1] - b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _angle(a, b):
    return math.degrees(math.atan2(abs(_cross(a, b)), _dot(a, b)))


def observe_corner(source, sections, *, interior_side):
    """OBSERVE an ordered source corner [previous, apex, next] in a native XY section.

    Match the two flanks at independent source stations, then require one connected,
    unbranched local trace. Never bridge missing geometry or decide acceptance here.
    Interior is left (+1) or right (-1) when following the source order.
    """
    a, o, b = source
    rays = [_sub(a, o), _sub(b, o)]
    source_angle = _angle(*rays)
    convex = -interior_side * _cross(*rays) > 0
    # Limit the probe to its own corner cell, including short adjacent envelope steps.
    station = min(0.35, math.dist(a, o) * 0.45, math.dist(b, o) * 0.45)
    evidence = {"source_xy": o, "source_angle_deg": source_angle,
                "source_interior_deg": source_angle if convex else 360 - source_angle,
                "probe_station_m": station}
    if station <= .002 or not 1 < source_angle < 179:
        return nm("no resolved source turn", **evidence)
    # A millimetre graph grid is smaller than the features under observation and
    # independent of the v1 50 mm detector tolerance.
    points, edges = {}, set()
    for edge in sections:
        snapped = []
        for p in edge:
            xy = tuple(p)
            grid = tuple(round(v, 3) for v in xy)
            points[grid] = min(points.get(grid, xy), xy)
            snapped.append(grid)
        if snapped[0] != snapped[1]:
            edges.add(tuple(sorted(snapped)))
    flanks = []
    for ray in rays:
        mag = math.hypot(*ray)
        u = (ray[0] / mag, ray[1] / mag)
        probe = (o[0] + u[0] * station, o[1] + u[1] * station)
        options = []
        for p, q in edges:
            direction = _sub(points[q], points[p])
            angle = _angle(u, direction)
            dist = seg_d(probe, points[p], points[q])
            if min(angle, 180 - angle) <= 25 and dist <= min(.14, station * .6):
                near, far = sorted((p, q), key=lambda xy: _dot(_sub(xy, o), u))
                options.append((dist, -math.dist(p, q), near, far))
        if not options:
            return nm("one or both source flank probes have no candidate support", **evidence)
        flanks.append(min(options)[2:])
    (start, far_a), (end, far_b) = flanks
    if {start, far_a} == {end, far_b}:
        return nm("both flank probes matched one edge", **evidence)
    adj = defaultdict(set)
    for p, q in edges - {tuple(sorted(f)) for f in flanks}:
        if max(math.dist(p, o), math.dist(q, o)) <= station * 2:
            adj[p].add(q)
            adj[q].add(p)
    path = [start]
    while path[-1] != end:
        options = adj[path[-1]] - set(path[-2:-1])
        if len(options) != 1 or (nxt := next(iter(options))) in path:
            return nm("local candidate trace is missing or branched", **evidence)
        path.append(nxt)
    if adj[end] - set(path[-2:-1]):
        return nm("local candidate trace is branched at the second flank", **evidence)

    trace = [points[p] for p in (far_a, *path, far_b)]
    bends = [(p, _angle(_sub(l, p), _sub(r, p)), _cross(_sub(p, l), _sub(r, p)))
             for l, p, r in zip(trace, trace[1:], trace[2:])]
    bends = [bend for bend in bends if bend[1] < 178]
    turns = [p for p, _, _ in bends]
    if not turns:
        return nm("no candidate turn in the local trace", **evidence)

    def depth(p):
        x = _sub(p, o)
        # For a convex corner the local interior is the intersection of the
        # two interior half-planes; for a reflex corner it is their union.
        pair = (-interior_side * _cross(rays[0], x) / math.hypot(*rays[0]),
                interior_side * _cross(rays[1], x) / math.hypot(*rays[1]))
        return (min if convex else max)(pair)

    # Each signed distance is affine on a connector edge; the only additional
    # extremum of min/max can occur at their crossing.
    witnesses = list(turns)
    def balance(p):
        x = _sub(p, o)
        return _cross(rays[0], x) / math.hypot(*rays[0]) + _cross(rays[1], x) / math.hypot(*rays[1])

    for p, q in zip(turns, turns[1:]):
        v, w = balance(p), balance(q)
        if v * w < 0:
            t = v / (v - w)
            witnesses.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    inward = max(0.0, *(depth(p) for p in witnesses))
    outward = max(0.0, *(-depth(p) for p in witnesses))
    same_turn = len(bends) == 2 and bends[0][2] * bends[1][2] > 0
    shape = ("direct" if len(turns) == 1 else "chamfer" if same_turn else
             "extra_recess" if inward > .002 else "multi_turn")
    angle = _angle(_sub(points[far_a], points[start]), _sub(points[far_b], points[end]))
    return {**evidence, "status": "observed", "shape": shape, "candidate_flank_angle_deg": angle,
            "delta_deg": angle - source_angle, "turns_xy": turns, "bend_angles_deg": [angle for _, angle, _ in bends],
            "candidate_flanks_xy_m": [[points[far_a], points[start]], [points[end], points[far_b]]],
            "corner_offset_m": min(math.dist(o, p) for p in turns) if len(turns) == 1 else
            min(seg_d(o, p, q) for p, q in zip(turns, turns[1:])),
            "inward_depth_m": inward, "outward_depth_m": outward,
            "connector_length_m": sum(math.dist(p, q) for p, q in zip(turns, turns[1:]))}


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
