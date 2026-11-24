"""Revit-FBX route into the lattice openings list (#1784): object dump -> per-facade openings/zones spec.

Pattern: n/a | new-case: shared openings step for Revit FBX exports without Revit (windows/doors/curtain panels as
separate objects with baked world vertices) -> the `plan_adapter_dwg.py lines` spec of the #1736 lattice core.

uv run python tools/methods/body/openings_from_revit_fbx.py DUMP.json CONFIG.json NEW_OUT.json
DUMP = revit_fbx_dump_blender.py output (schema revit-fbx-dump/1). CONFIG::

    {"rules": [["WB_Окно_", "surrounds"], ["Базовая стена ADSK_Наружная", "wall"],
               ["Базовая стена ADSK_Внутренняя", "drop", "interior wall"]],
     "interior": ["Базовая стена ADSK_Внутренняя"], "flip": [],
     "angle_tol_deg": 3.0, "line_tol_m": 0.8, "gap_m": 3.0, "curtain_merge_m": 0.15, "min_facade_m": 1.0,
     "probe_m": 10.0}

Rule = [name prefix, class(, reason)]; the first matching prefix wins. Classes: `wall` (exterior wall: builds the
facade lines, never cut, D341 outer envelope), `surrounds` (window), `doors`, `curtain` (curtain-wall panels,
merged into one opening rectangle per connected run), `features` (finish-zone object), `grilles` (niche),
`inset` (separate element D336: listed, no lines) and `drop` (reason required). Optional `crop` [xmin, ymin,
xmax, ymax] keeps one building of a site export (hull centroid inside; others dropped as "outside crop"). An object no rule matches is an
error naming its prefix; nothing defaults (a `["*", "drop", reason]` catch-all must be written explicitly). Every object ends in exactly one of `elements`, `insets`, `dropped`.

Geometry: each object's XY hull -> minimum-area rectangle (direction, length, depth). Facades = clusters of walls and
opening elements with the same direction (mod 180 deg, angle_tol_deg), the same line offset (line_tol_m) and
u-intervals closer than gap_m (a line needs exterior walls or, for glazed fronts, curtain panels). The outward side
of a facade = the side whose probe point (0.5 m off the face) has fewer of 12 rays with an odd crossing count
against the other facade lines at mid height (point-in-envelope parity); a margin < 4 rays is reported as
`side_tie` and `flip` in CONFIG (facade ids) overrides the side.
u runs left -> right seen from outside, from the facade's first element; z is world z. Lines are NOT built here: the
spec goes to `plan_adapter_dwg.lines_from_facades` ([D373]: lines only from the openings/zones list).
NEW_OUT.json must not exist and must not be an input.
"""
from __future__ import annotations

import json
import math
import os
import sys

CLASSES = {"wall", "surrounds", "doors", "curtain", "features", "grilles", "inset", "drop"}
SPEC_KEY = {"surrounds": "surrounds", "doors": "doors", "curtain": "surrounds", "features": "features",
            "grilles": "grilles"}
DEFAULTS = {"angle_tol_deg": 3.0, "line_tol_m": 0.8, "gap_m": 3.0, "curtain_merge_m": 0.15, "min_facade_m": 1.0,
            "probe_m": 10.0}


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def min_rect(hull):
    """Minimum-area rectangle of a CCW/CW convex hull: (angle_rad in [0, pi), (cx, cy), length, depth).

    length >= depth; angle is the direction of the long side. Refuses < 2 points or non-finite numbers."""
    pts = [tuple(p) for p in hull]
    if len(pts) < 2 or not all(len(p) == 2 and _finite(p[0]) and _finite(p[1]) for p in pts):
        raise ValueError("hull needs >= 2 finite points, got %r" % (hull,))
    best = None
    for a, b in zip(pts, pts[1:] + pts[:1]):
        ex, ey = b[0] - a[0], b[1] - a[1]
        el = math.hypot(ex, ey)
        if el < 1e-9:
            continue
        ux, uy = ex / el, ey / el
        us = [p[0] * ux + p[1] * uy for p in pts]
        vs = [-p[0] * uy + p[1] * ux for p in pts]
        area = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or area < best[0] - 1e-12:
            best = (area, ux, uy, min(us), max(us), min(vs), max(vs))
    if best is None:
        raise ValueError("hull is a single point: %r" % (hull,))
    _, ux, uy, u0, u1, v0, v1 = best
    if (u1 - u0) < (v1 - v0):  # long side along v
        ux, uy = -uy, ux
        u0, u1, v0, v1 = v0, v1, -u1, -u0
    ang = math.atan2(uy, ux) % math.pi
    if abs(ang - math.pi) < 1e-9:
        ang = 0.0
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    cx, cy = cu * ux - cv * uy, cu * uy + cv * ux
    return ang, (cx, cy), u1 - u0, v1 - v0


def classify(name, rules):
    for r in rules:
        if r[0] == "*" or name.startswith(r[0]):
            return r[1], (r[2] if len(r) > 2 else None)
    return None, None


def _prefix(name):
    """Revit FBX names are 'Category Family_Type' truncated to ~31 chars + '_hash'; drop the hash."""
    head, _, tail = name.rpartition("_")
    return head if head and len(tail) == 7 and all(c in "0123456789abcdef" for c in tail) else name


def _validate_cfg(cfg):
    rules = cfg.get("rules")
    if not (isinstance(rules, list) and rules):
        raise ValueError("config needs a non-empty rules list")
    for r in rules:
        if not (isinstance(r, list) and len(r) in (2, 3) and isinstance(r[0], str) and r[0] and r[1] in CLASSES):
            raise ValueError("rule %r must be [prefix, class(, reason)] with class in %s" % (r, sorted(CLASSES)))
        if r[1] == "drop" and not (len(r) == 3 and isinstance(r[2], str) and r[2]):
            raise ValueError("drop rule %r needs a reason" % (r,))
    opt = dict(DEFAULTS)
    for k in DEFAULTS:
        if k in cfg:
            if not (_finite(cfg[k]) and cfg[k] > 0):
                raise ValueError("config %s must be finite > 0, got %r" % (k, cfg[k]))
            opt[k] = float(cfg[k])
    interior = cfg.get("interior")
    if not (isinstance(interior, list) and interior and all(isinstance(p, str) and p for p in interior)):
        raise ValueError("config needs interior: non-empty list of name prefixes of interior elements (side test)")
    crop = cfg.get("crop")
    if crop is not None and not (isinstance(crop, list) and len(crop) == 4 and all(_finite(v) for v in crop)
                                 and crop[0] < crop[2] and crop[1] < crop[3]):
        raise ValueError("config crop must be [xmin, ymin, xmax, ymax] finite with min < max, got %r" % (crop,))
    opt["crop"] = crop
    flip = cfg.get("flip", [])
    if not (isinstance(flip, list) and all(isinstance(f, str) for f in flip)):
        raise ValueError("config flip must be a list of facade ids")
    return rules, opt, set(flip), tuple(interior)


def extract(dump, cfg):
    """Return the openings document (pure). Raises ValueError on a bad dump/config or unmapped object prefixes."""
    if not isinstance(dump, dict) or dump.get("schema") != "revit-fbx-dump/1":
        raise ValueError("dump schema must be revit-fbx-dump/1, got %r"
                         % (dump.get("schema") if isinstance(dump, dict) else dump,))
    objs = dump.get("objects")
    if not (isinstance(objs, list) and objs):
        raise ValueError("dump has no objects")
    rules, opt, flip, inner = _validate_cfg(cfg)
    names = [o.get("name") for o in objs]
    dup = sorted({n for n in names if names.count(n) > 1}) if len(set(names)) != len(names) else []
    if dup:
        raise ValueError("dump has duplicate object names %s" % dup[:5])
    unmapped = sorted({_prefix(o["name"]) for o in objs if classify(o["name"], rules)[0] is None})
    if unmapped:
        raise ValueError("no rule for %d object prefixes: %s" % (len(unmapped), unmapped[:20]))
    tol_a = math.radians(opt["angle_tol_deg"])
    items, insets, dropped = [], [], []
    interior = [(sum(p[0] for p in o["hull"]) / len(o["hull"]), sum(p[1] for p in o["hull"]) / len(o["hull"]),
                 o["z"][0], o["z"][1]) for o in objs if o["name"].startswith(inner) and o.get("hull") and o.get("z")]
    if not interior:
        raise ValueError("no object matches the interior prefixes %s: the outward side cannot be decided" % (inner,))
    crop = opt["crop"]
    for o in objs:
        cls, why = classify(o["name"], rules)
        if crop and o.get("hull"):
            cx = sum(p[0] for p in o["hull"]) / len(o["hull"])
            cy = sum(p[1] for p in o["hull"]) / len(o["hull"])
            if not (crop[0] <= cx <= crop[2] and crop[1] <= cy <= crop[3]):
                dropped.append({"name": o["name"], "why": "outside crop"})
                continue
        if cls == "drop":
            dropped.append({"name": o["name"], "why": why})
            continue
        z, hull = o.get("z"), o.get("hull") or []
        if z is None and not hull:
            dropped.append({"name": o["name"], "why": "no geometry (mesh without vertices)"})
            continue
        if not (isinstance(z, list) and len(z) == 2 and all(_finite(v) for v in z) and z[0] <= z[1]) or len(hull) < 2:
            raise ValueError("object %r: z must be finite [zmin <= zmax] and hull >= 2 points, got z=%r, %d hull points"
                             % (o["name"], z, len(hull)))
            continue
        ang, c, ln, dp = min_rect(hull)
        rec = {"name": o["name"], "cls": cls, "ang": ang, "c": c, "len": ln, "dep": dp, "z": z, "hull": hull}
        if cls == "inset":
            insets.append({"name": o["name"], "why": why or "separate element (D336)", "z": z,
                           "rect": [round(c[0], 4), round(c[1], 4), round(ln, 4), round(dp, 4),
                                    round(math.degrees(ang), 3)]})
            continue
        if cls == "wall" and dp > ln * 0.5 and ln > 2.0:
            dropped.append({"name": o["name"], "why": "wall hull is not a straight run (depth %.2f of length %.2f): "
                            "corner/L wall, its straight neighbours carry the facade" % (dp, ln)})
            continue
        items.append(rec)
    # ---- facade clusters -------------------------------------------------------------------------------
    def adiff(a, b):
        d = abs(a - b) % math.pi
        return min(d, math.pi - d)

    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def key(r, ang):
        ux, uy = math.cos(ang), math.sin(ang)
        cu = r["c"][0] * ux + r["c"][1] * uy
        cv = -r["c"][0] * uy + r["c"][1] * ux
        return cu - r["len"] / 2, cu + r["len"] / 2, cv

    for ai, a in enumerate(items):
        for bi in range(ai + 1, len(items)):
            b = items[bi]
            if adiff(a["ang"], b["ang"]) > tol_a:
                continue
            ka, kb = key(a, a["ang"]), key(b, a["ang"])
            if abs(ka[2] - kb[2]) > opt["line_tol_m"]:
                continue
            if kb[0] > ka[1] + opt["gap_m"] or ka[0] > kb[1] + opt["gap_m"]:
                continue
            parent[find(ai)] = find(bi)
    groups = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(items[i])
    lines = []  # (group, ang, u0, u1, cv, dep, z0, z1)
    for g in sorted(groups.values(), key=lambda g: (-sum(r["len"] for r in g if r["cls"] in ("wall", "curtain")),
                                                    min(r["name"] for r in g))):
        base = [r for r in g if r["cls"] == "wall"] or [r for r in g if r["cls"] == "curtain"]
        if not base:
            for r in g:
                dropped.append({"name": r["name"], "why": "no exterior wall or curtain wall on its facade line "
                                "(free-standing %s)" % r["cls"]})
            continue
        ang = _mean_angle([r["ang"] for r in base], [r["len"] for r in base])
        ks = [key(r, ang) for r in g]
        u0, u1 = min(k[0] for k in ks), max(k[1] for k in ks)
        if u1 - u0 < opt["min_facade_m"]:
            for r in g:
                dropped.append({"name": r["name"], "why": "facade shorter than min_facade_m"})
            continue
        wl = sum(r["len"] for r in base)
        cv = sum(key(r, ang)[2] * r["len"] for r in base) / wl
        lines.append((g, ang, u0, u1, cv, max(r["dep"] for r in base),
                      min(r["z"][0] for r in g), max(r["z"][1] for r in g)))
    facades, spec = [], {}
    for g, ang, u0, u1, cv, dep, z0, z1 in lines:
        walls = [r for r in g if r["cls"] == "wall"]
        ux, uy = math.cos(ang), math.sin(ang)
        mid = ((u0 + u1) / 2 * ux - cv * uy, (u0 + u1) / 2 * uy + cv * ux)
        score = {1: 0, -1: 0}
        for px, py, pz0, pz1 in interior:
            if pz1 <= z0 or pz0 >= z1:
                continue
            pu, pv = px * ux + py * uy, -px * uy + py * ux
            if u0 <= pu <= u1 and dep / 2 < abs(pv - cv) <= opt["probe_m"]:
                score[1 if pv > cv else -1] += 1  # interior elements on that side: inside the building
        fid = "F%02d" % (len(facades) + 1)
        side = 1 if score[1] < score[-1] else -1
        tie = score[1] == score[-1] or min(score.values()) * 3 > max(score.values())
        if fid in flip:
            side = -side
        # seen from outside (normal n), u runs left -> right when the facade direction is -side * (ux, uy)
        dx, dy = (ux, uy) if side == -1 else (-ux, -uy)
        p0 = mid[0] - dx * (u1 - u0) / 2, mid[1] - dy * (u1 - u0) / 2
        n = (-uy * side, ux * side)

        def to_u(r):
            k = key(r, ang)
            a_ = (k[0] - u0) if side == -1 else (u1 - k[1])
            return a_, a_ + r["len"]

        comp = math.degrees(math.atan2(n[1], n[0])) % 360
        rec = {"id": fid, "normal_deg": round(comp, 2), "origin": [round(p0[0], 4), round(p0[1], 4)],
               "dir": [round(dx, 6), round(dy, 6)], "length": round(u1 - u0, 4),
               "line_offset": round(cv, 4), "interior_count": {"+": score[1], "-": score[-1]},
               "side_tie": tie, "flipped": fid in flip,
               "z": [z0, z1], "base": "wall" if walls else "curtain",
               "walls": [{"name": r["name"], "u": [round(v, 4) for v in to_u(r)], "z": r["z"]} for r in walls],
               "counts": {}}
        fs = {}
        curt = []
        for r in g:
            if r["cls"] == "wall":
                continue
            ua, ub = to_u(r)
            rect = [round(ua, 4), round(ub, 4), round(r["z"][0], 4), round(r["z"][1], 4)]
            if r["cls"] == "curtain":
                curt.append((rect, r["name"]))
                continue
            fs.setdefault(SPEC_KEY[r["cls"]], []).append({"rect": rect, "name": r["name"]})
        for rect, members in _merge(curt, opt["curtain_merge_m"]):
            fs.setdefault("surrounds", []).append({"rect": rect, "name": "curtain[%d] %s" % (len(members), members[0]),
                                                   "members": members})
        rec["counts"] = {k: len(v) for k, v in fs.items()}
        facades.append(rec)
        if fs:
            spec[fid] = fs
    counts = {"objects": len(objs),
              "in_spec": sum(len(r.get("members", [1])) for fs in spec.values() for v in fs.values() for r in v),
              "walls": sum(len(f["walls"]) for f in facades), "insets": len(insets), "dropped": len(dropped)}
    placed = [r.get("members", [r.get("name")]) for fs in spec.values() for v in fs.values() for r in v]
    seen = [n for m in placed for n in m] + [w["name"] for f in facades for w in f["walls"]]         + [i["name"] for i in insets] + [d["name"] for d in dropped]
    if sorted(seen) != sorted(names):
        raise ValueError("accounting: %d objects in, %d placed/dropped (every object must end in exactly one list)"
                         % (len(names), len(seen)))
    return {"schema": "revit-openings/1", "source": dump.get("source"), "source_sha256": dump.get("sha256"),
            "options": opt, "facades": facades, "spec": spec, "insets": insets, "dropped": dropped,
            "counts": counts}


def _mean_angle(angs, w):
    sx = sum(math.cos(2 * a) * k for a, k in zip(angs, w))
    sy = sum(math.sin(2 * a) * k for a, k in zip(angs, w))
    return (math.atan2(sy, sx) / 2) % math.pi


def _merge(rects, tol):
    """Union-merge (u0, u1, z0, z1) rectangles that touch within tol; returns [(bbox, [names])]."""
    out = [([*r], [n]) for r, n in rects]
    changed = True
    while changed:
        changed = False
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i][0], out[j][0]
                if a[0] <= b[1] + tol and b[0] <= a[1] + tol and a[2] <= b[3] + tol and b[2] <= a[3] + tol:
                    out[i] = ([min(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3])],
                              out[i][1] + out[j][1])
                    out.pop(j)
                    changed = True
                    break
            if changed:
                break
    return [([round(v, 4) for v in r], sorted(n)) for r, n in out]


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 3:
        print("usage: openings_from_revit_fbx.py DUMP.json CONFIG.json NEW_OUT.json", file=sys.stderr)
        return 2
    dp, cp, out = args
    ro = os.path.realpath(out)
    if os.path.exists(out) or ro in (os.path.realpath(dp), os.path.realpath(cp)):
        print("refused: NEW_OUT.json exists or is an input", file=sys.stderr)
        return 2
    try:
        with open(dp, encoding="utf-8") as fh:
            dump = json.load(fh)
        with open(cp, encoding="utf-8") as fh:
            cfg = json.load(fh)
        doc = extract(dump, cfg)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as e:
        print("refused: %s" % e, file=sys.stderr)
        return 2
    doc["config"] = os.path.realpath(cp)
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    print("OPENINGS", json.dumps({"facades": len(doc["facades"]), "spec_facades": len(doc["spec"]),
                                  **doc["counts"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
