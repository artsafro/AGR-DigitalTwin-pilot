"""elv-tc-vpm: measurements of the pilot (east facade И-А with its south/north returns) from the clean-scene dump.

uv run python jobs/elv-tc-vpm/scripts/measure_pilot.py <ref_dump.json> <out.json>
Plain Python, read-only. Values in metres; anything within 1 cm is treated as equal (rounded to 0.01).
"""
import json, sys, math, collections, os

src, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
sys.stdout.reconfigure(encoding="utf-8")
D = json.load(open(src, encoding="utf-8"))
r2 = lambda v: round(v, 2)
X_S, X_N = 41.8, 59.3  # west ends of the wood/metal volumes on the south / north returns (measured, see 'extent')


def side(r):
    mn, mx = r["mn"], r["mx"]
    if mx[1] < -48.0 and mx[0] >= X_S:
        return "S"
    if mn[1] > 1.4 and mx[0] >= X_N:
        return "N"
    if mn[0] > 72.0:
        return "E"
    return None


P = [dict(r, side=side(r)) for r in D]
P = [r for r in P if r["side"]]
dims = lambda r: [r["mx"][i] - r["mn"][i] for i in range(3)]
M = {"pilot_objects": len(P), "pilot_tris_source": sum(r["t"] for r in P)}
M["by_category"] = {}
for r in P:
    k = M["by_category"].setdefault(r["cat"], {"objects": 0, "tris": 0})
    k["objects"] += 1; k["tris"] += r["t"]


def ext(L):
    return {"x": [r2(min(r["mn"][0] for r in L)), r2(max(r["mx"][0] for r in L))],
            "y": [r2(min(r["mn"][1] for r in L)), r2(max(r["mx"][1] for r in L))],
            "z": [r2(min(r["mn"][2] for r in L)), r2(max(r["mx"][2] for r in L))], "n": len(L)}


def hist(vals, top=6):
    return collections.Counter(v if isinstance(v, tuple) else r2(v) for v in vals).most_common(top)


def fit_circle(pts):
    # algebraic (Kasa) fit in plan
    n = len(pts); sx = sum(p[0] for p in pts) / n; sy = sum(p[1] for p in pts) / n
    u = [(p[0] - sx, p[1] - sy) for p in pts]
    suu = sum(a * a for a, b in u); svv = sum(b * b for a, b in u); suv = sum(a * b for a, b in u)
    suuu = sum(a ** 3 for a, b in u); svvv = sum(b ** 3 for a, b in u)
    suvv = sum(a * b * b for a, b in u); svuu = sum(b * a * a for a, b in u)
    det = suu * svv - suv * suv
    if abs(det) < 1e-12:
        return None
    uc = (0.5 * (suuu + suvv) * svv - 0.5 * (svvv + svuu) * suv) / det
    vc = (0.5 * (svvv + svuu) * suu - 0.5 * (suuu + suvv) * suv) / det
    R = math.sqrt(uc * uc + vc * vc + (suu + svv) / n)
    cx, cy = uc + sx, vc + sy
    res = max(abs(math.hypot(p[0] - cx, p[1] - cy) - R) for p in pts)
    return {"cx": r2(cx), "cy": r2(cy), "R": r2(R), "max_resid": round(res, 3), "pts": n}


def cassettes(cat, flat_e_test):
    L = [r for r in P if r["cat"] == cat]
    o = {"extent": {s: ext([r for r in L if r["side"] == s]) for s in "ESN" if any(r["side"] == s for r in L)}}
    flat = [r for r in L if flat_e_test(r)]
    o["module_along_facade"] = hist([max(dims(r)[0], dims(r)[1]) for r in flat])
    o["module_height"] = hist([dims(r)[2] for r in flat])
    o["thickness"] = hist([min(dims(r)[0], dims(r)[1]) for r in flat])
    zb = sorted(set(r2(r["mn"][2]) for r in flat)); zt = sorted(set(r2(r["mx"][2]) for r in flat))
    o["z_bottoms"] = zb; o["z_tops"] = zt
    o["joint_vertical"] = hist([b - t for t, b in zip(zt, zb[1:])])
    ys = sorted((r["mn"][1], r["mx"][1]) for r in flat if r["side"] == "E" and abs(r["mn"][2] - zb[0]) < 0.02)
    o["joint_along_E"] = hist([b[0] - a[1] for a, b in zip(ys, ys[1:]) if 0 <= b[0] - a[1] < 0.2])
    # corners: non-axis-aligned pieces (both plan dims > 2x thickness)
    th = o["thickness"][0][0] if o["thickness"] else 0.05
    curved = [r for r in L if min(dims(r)[0], dims(r)[1]) > 2.5 * th + 0.03]
    for name, test in (("corner_SE", lambda r: r["mn"][1] < -40), ("corner_NE", lambda r: r["mn"][1] > -10)):
        C = [r for r in curved if test(r)]
        if not C:
            continue
        pts = [];  # outer vertices: farthest from the building centre per piece
        for r in C:
            vs = r["v"]
            pts += [(v[0], v[1]) for v in vs]
        # keep the outer shell: points whose distance to a rough centre is in the top half
        f = fit_circle(pts)
        if f:
            outer = [p for p in pts if math.hypot(p[0] - f["cx"], p[1] - f["cy"]) >= f["R"]]
            f2 = fit_circle(outer) or f
            o[name] = {"pieces": len(C), "fit_all": f, "fit_outer": f2, "extent": ext(C)}
    return o


M["wood_cassette"] = cassettes("wood_cassette", lambda r: min(dims(r)[0], dims(r)[1]) < 0.07)
M["metal_cassette"] = cassettes("metal_cassette", lambda r: min(dims(r)[0], dims(r)[1]) < 0.07)

# curtain walls
G = [r for r in P if r["cat"] in ("glass", "stemalit") and r["side"] == "E"]
up = [r for r in G if r["mn"][0] > 78.8]
low = [r for r in G if 75.8 < r["mn"][0] < 76.5]
niche = [r for r in G if r["mn"][0] < 75.8]
other_g = [r for r in G if r not in up and r not in low and r not in niche]


def cw(L):
    o = {"extent": ext(L)}
    for cat in ("glass", "stemalit"):
        LL = [r for r in L if r["cat"] == cat]
        if not LL:
            continue
        bands = collections.Counter((r2(r["mn"][2]), r2(r["mx"][2])) for r in LL)
        o[cat] = {"n": len(LL), "z_bands": sorted(bands.items()), "widths": hist([max(dims(r)[0], dims(r)[1]) for r in LL]),
                  "thickness": hist([min(dims(r)[0], dims(r)[1]) for r in LL], 3), "x": hist([r["mn"][0] for r in LL], 4)}
    ys = sorted(set(r2(r["mn"][1]) for r in L))
    o["y_starts"] = ys
    o["y_steps"] = hist([b - a for a, b in zip(ys, ys[1:])])
    return o


M["cw_upper_E"] = cw(up); M["cw_lower_E"] = cw(low); M["cw_niche"] = cw(niche)
M["cw_other_E"] = [dict(name=r["name"], mn=[r2(v) for v in r["mn"]], mx=[r2(v) for v in r["mx"]]) for r in other_g][:20]
# lower CW segments along y (gap > 0.5 m splits)
segs = []
for r in sorted(low, key=lambda r: r["mn"][1]):
    if segs and r["mn"][1] - segs[-1][1] < 0.5:
        segs[-1][1] = max(segs[-1][1], r["mx"][1])
    else:
        segs.append([r["mn"][1], r["mx"][1]])
M["cw_lower_E"]["segments_y"] = [[r2(a), r2(b)] for a, b in segs]
segs = []
for r in sorted(up, key=lambda r: r["mn"][1]):
    if segs and r["mn"][1] - segs[-1][1] < 0.5:
        segs[-1][1] = max(segs[-1][1], r["mx"][1])
    else:
        segs.append([r["mn"][1], r["mx"][1]])
M["cw_upper_E"]["segments_y"] = [[r2(a), r2(b)] for a, b in segs]

# mullions by zone: F50 curtain-wall profiles vs 20 mm cassette joints
mz = collections.defaultdict(lambda: {"n": 0, "tris": 0, "sections": collections.Counter(), "proj_x": collections.Counter()})
for r in P:
    if r["cat"] != "mullion":
        continue
    d = sorted(dims(r))
    if d[1] <= 0.03:
        zone = "cassette_joint_20mm"
    elif r["mn"][0] > 78.7:
        zone = "cw_upper_profile"
    elif 75.8 < r["mn"][0] < 76.5 and r["mx"][2] < 4.8:
        zone = "cw_lower_profile"
    elif r["side"] == "E" and r["mn"][0] < 75.8:
        zone = "cw_niche_profile"
    else:
        zone = "cw_profile_returns"
    z = mz[zone]; z["n"] += 1; z["tris"] += r["t"]; z["sections"][(r2(d[0]), r2(d[1]))] += 1
    if r["side"] == "E":
        z["proj_x"][(r2(r["mn"][0]), r2(r["mx"][0]))] += 1
M["mullions"] = {k: {"n": v["n"], "tris": v["tris"], "sections": v["sections"].most_common(5),
                     "x_extent_E": v["proj_x"].most_common(4)} for k, v in mz.items()}

# ribs
R = [r for r in P if r["cat"] == "rib_lamella" and r["side"] == "E"]
ry = sorted(r2((r["mn"][1] + r["mx"][1]) / 2) for r in R if dims(r)[0] > dims(r)[1])
M["ribs_E"] = {"extent": ext(R), "count": len(R), "flat_ribs": len(ry),
               "section_xy": hist([(r2(dims(r)[0]), r2(dims(r)[1])) for r in R], 5),
               "centres_y": ry, "steps": hist([b - a for a, b in zip(ry, ry[1:])], 8),
               "curved_corner_ribs": len(R) - len(ry), "tris": sum(r["t"] for r in R)}

# sign frames: cluster members whose bboxes touch
SF = [r for r in P if r["cat"] == "sign_frame"]
groups = []
for r in SF:
    hit = None
    for g in groups:
        if all(r["mn"][i] <= g["mx"][i] + 0.02 and r["mx"][i] >= g["mn"][i] - 0.02 for i in range(3)):
            hit = g; break
    if hit:
        hit["mn"] = [min(hit["mn"][i], r["mn"][i]) for i in range(3)]; hit["mx"] = [max(hit["mx"][i], r["mx"][i]) for i in range(3)]
        hit["n"] += 1; hit["t"] += r["t"]
    else:
        groups.append({"mn": list(r["mn"]), "mx": list(r["mx"]), "n": 1, "t": r["t"], "side": r["side"]})
M["sign_frames"] = sorted([{"side": g["side"], "w": r2(max(g["mx"][0] - g["mn"][0], g["mx"][1] - g["mn"][1])),
                            "h": r2(g["mx"][2] - g["mn"][2]), "z": [r2(g["mn"][2]), r2(g["mx"][2])],
                            "x": [r2(g["mn"][0]), r2(g["mx"][0])], "y": [r2(g["mn"][1]), r2(g["mx"][1])], "members": g["n"], "tris": g["t"]}
                           for g in groups], key=lambda g: (g["side"], g["y"][0], g["x"][0], g["z"][0]))


def listing(cat):
    return [{"name": r["name"], "side": r["side"], "x": [r2(r["mn"][0]), r2(r["mx"][0])], "y": [r2(r["mn"][1]), r2(r["mx"][1])],
             "z": [r2(r["mn"][2]), r2(r["mx"][2])], "tris": r["t"]} for r in sorted(P, key=lambda r: (r["side"], r["mn"][1], r["mn"][0])) if r["cat"] == cat]


for cat in ("parapet_flashing", "door", "plinth", "wall_ext", "sandwich", "canopy", "roof", "window", "equipment", "lights_arktos", "gate", "other"):
    M[cat] = listing(cat)
# canopy over the entrance: anything above the doors (z 2.2-4.7) in front of the niche, not CW / cassette
M["entrance_canopy_candidates"] = [x for x in sum((listing(c) for c in M["by_category"]), [])
                                   if x["side"] == "E" and x["x"][0] > 73.2 and -28.5 < x["y"][0] < -18.5 and x["z"][0] > 2.2
                                   and x["z"][1] < 4.8 and x["name"] and not x["name"].startswith(("Прямоуг", "Системная"))]
json.dump(M, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("pilot objects", M["pilot_objects"], "source tris", M["pilot_tris_source"])
