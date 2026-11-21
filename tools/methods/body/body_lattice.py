"""Shared stage-1 body builder core (#1736): cut lattice + depth field, BM-00..BM-14.

Pattern: n/a | new-case: one body core for every job (lattice of ring stations x shared floor levels; opening =
removed cell + reveal tube on the same vertices), generalised from the #1619 module_build that built every accepted
stage-1 body (G22 k1/k2/k3, 63A v005, 63C v002, 63B v007; census in docs/research/body-mesh-method.md).

Pure Python (no bpy): `build_module(plan)` returns the typical-floor module as vertices + faces (material name and
per-loop UV), `replicate(module, plan)` copies it by the floor step and welds the shared level (BM-10). The Blender
writer `body_lattice_blender.py` and the `agr body` command only turn that into module.blend / body.blend / body.fbx.

Input = the plan format «contour + levels + openings» (`schemas/BodyPlan.schema.json`; Revit route:
`jobs/garibaldi22/body-training-1619/hooks/floor_from_dump.py`, DWG route: `plan_adapter_dwg.py`). The core reads
nothing else. Rules applied by construction (BM-00 [D372]): the body is built ONLY from the lattice, never by
repairing a mesh; vertical stations = ring corners + `cuts` (jambs, zone joints) + optional max-side splits (BM-11);
horizontal lines = `loops` (BM-02); a window with reveal r > 0 removes its cells and adds jambs / sill / head quads on
the same vertices (back open for the stage-2 window, D336); r = 0 keeps the cell with the WINDOW material; insets are
separate closed boxes, the wall under them is not cut (BM-04). Corner vertices of an offset run are the intersection
of both sides' offset lines at their own depths (lesson r2 of #1742 §5.7b), never a bisector at one depth.
Every refusal is a ValueError naming the offending key; nothing defaults silently. Overlapping finish zones are an
error unless the plan declares `"zone_overlap": "first_listed"` (the first listed zone wins; 63B v007 was built so).
"""
from __future__ import annotations

import json
import math

EPS_S = 1e-4  # perimeter / level tolerance, metres (module_build)
REQUIRED = ("step", "z0", "floors", "loops", "rings", "materials")


# ---- plan --------------------------------------------------------------------------------------------------
def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def load_plan(path):
    def no_dup(pairs):
        keys = [k for k, _ in pairs]
        dup = sorted({k for k in keys if keys.count(k) > 1})
        if dup:
            raise ValueError("plan has duplicate keys %s" % dup)
        return dict(pairs)

    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh, object_pairs_hook=no_dup)
    validate_plan(plan)
    return plan


def validate_plan(plan):
    """Fail-closed check of the plan format; returns the plan. Extra keys (provenance) are allowed and ignored."""
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    missing = [k for k in REQUIRED if k not in plan]
    if missing:
        raise ValueError("plan misses %s" % missing)
    step, z0, floors, loops = plan["step"], plan["z0"], plan["floors"], plan["loops"]
    if not (_finite(step) and step > 0 and _finite(z0)):
        raise ValueError("step must be finite > 0 and z0 finite, got step=%r z0=%r" % (step, z0))
    if not (isinstance(floors, int) and not isinstance(floors, bool) and floors >= 1):
        raise ValueError("floors must be an integer >= 1, got %r" % (floors,))
    if not (isinstance(loops, list) and loops and all(_finite(z) for z in loops)):
        raise ValueError("loops must be a non-empty list of finite numbers")
    if not (loops[0] == 0.0 and all(a < b for a, b in zip(loops, list(loops[1:]) + [step]))):
        raise ValueError("loops must start at 0 and rise strictly inside the step, got %r" % (loops,))
    mats = plan["materials"]
    if not (isinstance(mats, dict) and mats):
        raise ValueError("materials must be a non-empty object name -> rgb")
    for n, rgb in mats.items():
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(_finite(c) for c in rgb)):
            raise ValueError("material %r needs 3 finite rgb numbers" % n)
    rings = plan["rings"]
    if not (isinstance(rings, list) and rings):
        raise ValueError("rings must be a non-empty list")
    nlev = len(loops) + 1
    for ri, ring in enumerate(rings):
        xy = ring.get("xy") if isinstance(ring, dict) else None
        if not (isinstance(xy, list) and len(xy) >= 3
                and all(isinstance(p, list) and len(p) == 2 and all(_finite(c) for c in p) for p in xy)):
            raise ValueError("ring %d: xy needs >= 3 finite [x, y] points" % ri)
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(xy, xy[1:] + xy[:1])) / 2
        if area <= 0:
            raise ValueError("ring %d must be counter-clockwise (outward = tangent x up), area %.4f" % (ri, area))
        if any(math.dist(a, b) < 1e-6 for a, b in zip(xy, xy[1:] + xy[:1])):
            raise ValueError("ring %d has a zero-length side" % ri)
        perim = sum(math.dist(a, b) for a, b in zip(xy, xy[1:] + xy[:1]))
        cuts = ring.get("cuts", [])
        if not all(_finite(s) and -EPS_S <= s <= perim + EPS_S for s in cuts):
            raise ValueError("ring %d: cuts must be finite perimeter positions in [0, %.3f]" % (ri, perim))
        zl = ring.get("zones", [[0.0, perim, "WALL_A"]])
        for z in zl:
            if not (isinstance(z, list) and len(z) == 3 and _finite(z[0]) and _finite(z[1]) and z[0] < z[1]):
                raise ValueError("ring %d: zone %r must be [s0, s1, material] with s0 < s1" % (ri, z))
            if z[2] not in mats:
                raise ValueError("zone material %r is not in materials" % (z[2],))
        zs = sorted(zl)
        for a, b in zip(zs, zs[1:]):
            if b[0] < a[1] - EPS_S and plan.get("zone_overlap") != "first_listed":
                raise ValueError("ring %d: zones %r and %r overlap (a face would get two materials)" % (ri, a, b))
    seen = []
    for w in plan.get("windows", []):
        if not (isinstance(w, list) and 3 <= len(w) <= 6 and all(_finite(v) for v in w)):
            raise ValueError("window %r must be [ring, s0, s1, wl, wh, r] of finite numbers" % (w,))
        if not (int(w[0]) == w[0] and 0 <= w[0] < len(rings)):
            raise ValueError("window %r: ring index outside rings" % (w,))
        wl, wh, r = (w[3] if len(w) > 3 else 0), (w[4] if len(w) > 4 else 1), (w[5] if len(w) > 5 else 0.0)
        if not (w[1] < w[2] and 0 <= wl < wh < nlev and int(wl) == wl and int(wh) == wh and 0.0 <= r < 1.0):
            raise ValueError("window %r: reveal must be finite in [0, 1) m and loops inside the module" % (w,))
        if "WINDOW" not in mats and r == 0:
            raise ValueError("window %r keeps its cell but materials has no WINDOW" % (w,))
        for o in seen:  # duplicated / overlapping openings would cut one cell twice and build two reveals
            if o[0] == w[0] and w[1] < o[2] - EPS_S and o[1] < w[2] - EPS_S and wl < o[4] and o[3] < wh:
                raise ValueError("windows %r and %r overlap" % (o[:6], w))
        seen.append((w[0], w[1], w[2], wl, wh, r))
    for ins in plan.get("insets", []):
        box_corners(*ins["box"])
        if "INSET" not in mats:
            raise ValueError("insets need an INSET material")
    if plan.get("zone_overlap", "error") not in ("error", "first_listed"):
        raise ValueError("zone_overlap must be 'error' or 'first_listed', got %r" % (plan["zone_overlap"],))
    if "wall_tile_m" in plan and not (_finite(plan["wall_tile_m"]) and plan["wall_tile_m"] > 0):
        raise ValueError("wall_tile_m must be finite > 0")
    return plan


# ---- pure geometry helpers (moved from module_build, same behaviour) ----------------------------------------
def box_corners(cx, cy, z0, w, d, h, rot):
    """8 corners: bottom ring then top ring, each (-w/2,0) (w/2,0) (w/2,d) (-w/2,d) in (tangent, outward).

    Box [cx, cy, z0, w, d, h, rot]: foot on the contour, rot = tangent angle of the CCW ring, d along the OUTWARD
    normal (tangent rotated -90 deg)."""
    vals = (cx, cy, z0, w, d, h, rot)
    if not all(_finite(v) for v in vals):
        raise ValueError("inset box needs 7 finite numbers, got %r" % (vals,))
    if w <= 0 or d <= 0 or h <= 0:
        raise ValueError("inset box needs w, d, h > 0, got %r" % (vals,))
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    nx, ny = s, -c
    out = []
    for dz in (0.0, h):
        for du, dv in ((-w / 2, 0.0), (w / 2, 0.0), (w / 2, d), (-w / 2, d)):
            out.append((cx + c * du + nx * dv, cy + s * du + ny * dv, z0 + dz))
    return out


def offset_run(xy, depths):
    """Points of an open run of a CCW ring moved INTO the body, segment i by depths[i] (depth field).

    Every inner point is the intersection of the two neighbouring segments' offset lines, each at ITS depth (#1742
    §5.7b: a bisector at one depth puts the corner off the other side's plane -> self-intersections at a sharp
    concave corner with different depths). Ends use their own segment. Equal depths = the module_build mitre.
    Refuses depth outside (0, 1) m, non-finite points, < 2 points, zero segments and parallel fold-backs."""
    pts = [(float(x), float(y)) for x, y in xy]
    if len(pts) < 2 or not all(math.isfinite(v) for p in pts for v in p):
        raise ValueError("opening run needs >= 2 finite points, got %r" % (xy,))
    if len(depths) != len(pts) - 1:
        raise ValueError("offset_run needs one depth per segment (%d), got %d" % (len(pts) - 1, len(depths)))
    for r in depths:
        if not (_finite(r) and 0 < r < 1.0):
            raise ValueError("reveal depth must be finite in (0, 1) m, got %r" % (r,))
    nrm = []
    for p, q in zip(pts, pts[1:]):
        L = math.dist(p, q)
        if L < 1e-6:
            raise ValueError("zero-length segment in the opening run at %r" % (p,))
        nrm.append((-(q[1] - p[1]) / L, (q[0] - p[0]) / L))  # left normal of a CCW ring = into the body
    out = []
    for i, (x, y) in enumerate(pts):
        a, b = max(0, i - 1), min(len(nrm) - 1, i)
        n1, n2, d1, d2 = nrm[a], nrm[b], depths[a], depths[b]
        if a == b:
            out.append((x + n1[0] * d1, y + n1[1] * d1))
            continue
        cross = n1[0] * n2[1] - n1[1] * n2[0]
        dot = n1[0] * n2[0] + n1[1] * n2[1]
        if abs(cross) < 1e-9:
            if dot < 0 or abs(d1 - d2) > 1e-9:
                raise ValueError("opening run folds back on itself at %r" % ((x, y),))
            out.append((x + n1[0] * d1, y + n1[1] * d1))
            continue
        # solve o . n1 = d1, o . n2 = d2 for the offset o
        ox = (d1 * n2[1] - d2 * n1[1]) / cross
        oy = (n1[0] * d2 - n2[0] * d1) / cross
        out.append((x + ox, y + oy))
    return out


def inner_offset(xy, r):
    """offset_run at one depth r (module_build stage-1 reveal back edge)."""
    if not (_finite(r) and 0 < r < 1.0):
        raise ValueError("reveal depth must be finite in (0, 1) m, got %r" % (r,))
    return offset_run(xy, [r] * (len(xy) - 1))


def jamb_uv(co, outer, inner, tex_m):
    """UV of a point on a jamb: u = distance along the jamb's plan direction / tex_m, v = z / tex_m (UV/geo = 1)."""
    vals = (co[0], co[1], co[2], outer[0], outer[1], inner[0], inner[1], tex_m)
    if not all(_finite(v) for v in vals):
        raise ValueError("jamb UV needs finite numbers, got %r" % (vals,))
    if tex_m <= 0:
        raise ValueError("jamb UV needs tex_m > 0, got %r" % (tex_m,))
    dx, dy = inner[0] - outer[0], inner[1] - outer[1]
    L = math.hypot(dx, dy)
    if L < 1e-6:
        raise ValueError("jamb UV: zero-length jamb at %r" % (tuple(outer),))
    return (((co[0] - outer[0]) * dx + (co[1] - outer[1]) * dy) / L / tex_m, co[2] / tex_m)


def ring_points(ring, cuts, max_side=0.0):
    """Stations of one ring: (s, x, y, side) for corners + cuts, then even max-side splits (BM-11)."""
    pts, s_acc = [], 0.0
    n = len(ring)
    cuts = sorted(cuts)
    ci = 0
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        L = math.dist(a, b)
        pts.append((s_acc, a[0], a[1], i))
        while ci < len(cuts) and cuts[ci] < s_acc + L - EPS_S:
            if cuts[ci] > s_acc + EPS_S:
                t = (cuts[ci] - s_acc) / L
                pts.append((cuts[ci], a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]), i))
            ci += 1
        s_acc += L
    if max_side > 0:
        dense = []
        for k, p in enumerate(pts):
            dense.append(p)
            q = pts[k + 1] if k + 1 < len(pts) else (s_acc, pts[0][1], pts[0][2], p[3])
            gap = q[0] - p[0]
            parts = math.ceil(gap / max_side - 1e-9)
            for j in range(1, parts):
                t = j / parts
                dense.append((p[0] + t * gap, p[1] + t * (q[1] - p[1]), p[2] + t * (q[2] - p[2]), p[3]))
        pts = dense
    return pts, s_acc


def _newell(co):
    nx = ny = nz = 0.0
    for a, b in zip(co, co[1:] + co[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    return nx, ny, nz


# ---- module -------------------------------------------------------------------------------------------------
def build_module(plan, max_side=None):
    """Typical-floor module: {"verts": [(x,y,z)], "faces": [{"v": (i..), "mat": name, "uv": [(u,v)..]}],
    "materials": [used names in plan order], "report": {...}}. Local z (0 = module base); world z = plan z0."""
    validate_plan(plan)
    if max_side is None:
        max_side = plan.get("max_side_m", 0.0)  # BM-11 split of long sides, job config (G22 k2: 3.6 m)
    if not (_finite(max_side) and max_side >= 0):
        raise ValueError("max_side must be finite >= 0, got %r" % (max_side,))
    step, loops = float(plan["step"]), [float(z) for z in plan["loops"]]
    tex = float(plan.get("wall_tile_m", 3.0))
    mat_names = list(plan["materials"])
    levels = loops + [step]
    verts, faces = [], []
    report = {"rings": [], "insets": 0}

    def vnew(p):
        verts.append(tuple(float(c) for c in p))
        return len(verts) - 1

    def face(idx, mat, uv_of, want=None):
        idx = tuple(idx)
        if want is not None:
            n = _newell([verts[i] for i in idx])
            if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
                idx = (idx[0],) + tuple(reversed(idx[1:]))
        faces.append({"v": idx, "mat": mat, "uv": [tuple(uv_of(i, j)) for j, i in enumerate(idx)]})

    for ri, ring in enumerate(plan["rings"]):
        pts, perim = ring_points(ring["xy"], ring.get("cuts", []), max_side)
        wins = [(w[1], w[2], int(w[3]) if len(w) > 3 else 0, int(w[4]) if len(w) > 4 else 1,
                 float(w[5]) if len(w) > 5 else 0.0) for w in plan.get("windows", []) if w[0] == ri]
        zones = ring.get("zones", [[0.0, perim, "WALL_A"]])
        n = len(pts)
        grid = [[vnew((x, y, z)) for (_, x, y, _) in pts] for z in levels]
        for li in range(len(levels) - 1):
            for k in range(n):
                s0 = pts[k][0]
                s1 = pts[k + 1][0] if k + 1 < n else perim
                sm = (s0 + s1) / 2
                hit = [w for w in wins if w[0] - EPS_S <= sm <= w[1] + EPS_S and w[2] <= li < w[3]]
                zone = next((z[2] for z in zones if z[0] - EPS_S <= sm <= z[1] + EPS_S), None)
                if zone is None:
                    raise ValueError("ring %d face at s=%.3f is in no finish zone" % (ri, sm))
                if hit and hit[0][4] > 0:
                    continue  # opening cell removed; reveal built below
                z0, z1 = levels[li], levels[li + 1]
                if hit:
                    a, b = next((w[0], w[1]) for w in wins if w[0] - EPS_S <= sm <= w[1] + EPS_S)
                    us = ((s0 - a) / (b - a), (s1 - a) / (b - a))
                    vs = ((z0 - levels[0]) / (levels[1] - levels[0]), (z1 - levels[0]) / (levels[1] - levels[0]))
                else:
                    us, vs = (s0 / tex, s1 / tex), (z0 / tex, z1 / tex)
                quv = ((us[0], vs[0]), (us[1], vs[0]), (us[1], vs[1]), (us[0], vs[1]))
                face((grid[li][k], grid[li][(k + 1) % n], grid[li + 1][(k + 1) % n], grid[li + 1][k]),
                     "WINDOW" if hit else zone, lambda i, j, q=quv: q[j])
        for a, b, wl, wh, r in wins:
            if r <= 0:
                continue
            ks = [k for k in range(n) if a - EPS_S <= pts[k][0] <= b + EPS_S]
            if len(ks) < 2 or ks != list(range(ks[0], ks[-1] + 1)):
                raise ValueError("window [%.3f, %.3f] is not a run of ring points" % (a, b))
            inner = inner_offset([(pts[k][1], pts[k][2]) for k in ks], r)
            zone = next(z[2] for z in zones if z[0] - EPS_S <= (a + b) / 2 <= z[1] + EPS_S)
            iv = {}

            def ivert(j, li, inner=inner, iv=iv):
                if (j, li) not in iv:
                    iv[(j, li)] = vnew((inner[j][0], inner[j][1], levels[li]))
                return iv[(j, li)]

            def unit(dx, dy):
                L = math.hypot(dx, dy)
                return (dx / L, dy / L, 0.0)

            t0 = unit(pts[ks[1]][1] - pts[ks[0]][1], pts[ks[1]][2] - pts[ks[0]][2])
            t1 = unit(pts[ks[-1]][1] - pts[ks[-2]][1], pts[ks[-1]][2] - pts[ks[-2]][2])
            j = len(ks) - 1
            o0, o1 = (pts[ks[0]][1], pts[ks[0]][2]), (pts[ks[-1]][1], pts[ks[-1]][2])
            for li in range(wl, wh):
                q = (grid[li][ks[0]], ivert(0, li), ivert(0, li + 1), grid[li + 1][ks[0]])
                face(q, zone, lambda i, _j, o=o0, n_=inner[0]: jamb_uv(verts[i], o, n_, tex), t0)
                q = (grid[li][ks[-1]], grid[li + 1][ks[-1]], ivert(j, li + 1), ivert(j, li))
                face(q, zone, lambda i, _j, o=o1, n_=inner[j]: jamb_uv(verts[i], o, n_, tex), (-t1[0], -t1[1], 0.0))
            flat = lambda i, _j: (verts[i][0] / tex, verts[i][1] / tex)  # noqa: E731
            for jj in range(len(ks) - 1):
                k0, k1 = ks[jj], ks[jj + 1]
                face((grid[wl][k0], grid[wl][k1], ivert(jj + 1, wl), ivert(jj, wl)), zone, flat, (0, 0, 1))
                face((grid[wh][k0], ivert(jj, wh), ivert(jj + 1, wh), grid[wh][k1]), zone, flat, (0, 0, -1))
            report["reveal_faces"] = report.get("reveal_faces", 0) + 2 * (wh - wl) + 2 * (len(ks) - 1)
            report["openings"] = report.get("openings", 0) + 1
        report["rings"].append({"points": n, "perimeter_m": round(perim, 3)})

    for ins in plan.get("insets", []):
        c = box_corners(*ins["box"])
        base = [vnew(p) for p in c]
        cen = tuple(sum(p[i] for p in c) / 8 for i in range(3))
        for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
            idx = [base[i] for i in q]
            fc = tuple(sum(verts[i][k] for i in idx) / 4 for k in range(3))
            face(idx, "INSET", lambda i, j: (0.5, 0.5), tuple(fc[k] - cen[k] for k in range(3)))
        report["insets"] += 1
    used = [m for m in mat_names if any(f["mat"] == m for f in faces)]
    report["materials"] = used
    report["module"] = {"verts": len(verts), "faces": len(faces), "tris": sum(1 for f in faces if len(f["v"]) == 3)}
    return {"verts": verts, "faces": faces, "materials": used, "report": report}


def replicate(module, plan):
    """Copy the module `floors` times by `step` along z and weld each copy's base level onto the previous copy's
    top level (Array merge of module_build, BM-10). Local coordinates; world z = plan z0."""
    step, floors = float(plan["step"]), int(plan["floors"])
    mv = module["verts"]
    top = {}
    for i, p in enumerate(mv):
        if abs(p[2] - step) < EPS_S:
            top[(round(p[0], 4), round(p[1], 4))] = i
    verts, faces, prev = [], [], None
    for k in range(floors):
        remap = {}
        for i, p in enumerate(mv):
            if prev is not None and abs(p[2]) < EPS_S:
                key = (round(p[0], 4), round(p[1], 4))
                j = top.get(key)
                if j is not None and math.dist(mv[j][:2], p[:2]) < EPS_S:
                    remap[i] = prev[j]
                    continue
            verts.append((p[0], p[1], p[2] + k * step))
            remap[i] = len(verts) - 1
        for f in module["faces"]:
            faces.append({"v": tuple(remap[i] for i in f["v"]), "mat": f["mat"],
                          "uv": [(u, v + 0.0) for u, v in f["uv"]]})
        prev = remap
    rep = dict(module["report"])
    rep["body"] = {"verts": len(verts), "faces": len(faces), "floors": floors}
    return {"verts": verts, "faces": faces, "materials": module["materials"], "report": rep}


# ---- lines from the openings / zones list [D372] ---------------------------------------------------
def snap(v, grid=0.10):
    """Snap a level or station to the grid (10 cm by default); refuses non-finite input."""
    if not (_finite(v) and _finite(grid) and grid > 0):
        raise ValueError("snap needs finite value and grid > 0, got %r, %r" % (v, grid))
    return round(round(v / grid) * grid, 6)


def keep_lines(candidates, min_reason=1.5):
    """Filter candidate lines [{"at": z_or_s, "reason": kind, "length": m, "width": m|None}] [D372].

    A line is kept when the cell class changes along it over >= min_reason in ONE element (lengths of separate
    elements on the same line are not added: four 0.4 m grilles are texture), or over the full width of the opening
    that causes it (an opening bottom/top is always a reason). Shorter changes are texture. Returns (kept sorted
    unique positions, dropped [{"at", "reason", "why"}]). Unknown reasons and non-finite numbers are errors."""
    kinds = {"opening", "zone", "niche", "plinth", "belt", "floor", "break"}
    total, width_ok, why = {}, set(), {}
    for c in candidates:
        if c.get("reason") not in kinds:
            raise ValueError("line reason %r is not one of %s" % (c.get("reason"), sorted(kinds)))
        if not (_finite(c.get("at")) and _finite(c.get("length")) and c["length"] >= 0):
            raise ValueError("line %r needs finite at and length >= 0" % (c,))
        at = round(c["at"], 6)
        total[at] = max(total.get(at, 0.0), c["length"])  # one run must reach the threshold; pieces do not add
        w = c.get("width")
        if c["reason"] == "opening" and _finite(w) and c["length"] >= w - EPS_S:
            width_ok.add(at)
        why.setdefault(at, c["reason"])
    kept, dropped = [], []
    for at in sorted(total):
        if total[at] >= min_reason - 1e-9 or at in width_ok:
            kept.append(at)
        else:
            dropped.append({"at": at, "reason": why[at], "why": "longest class change %.3f m < %.2f m: texture"
                            % (total[at], min_reason)})
    return kept, dropped
