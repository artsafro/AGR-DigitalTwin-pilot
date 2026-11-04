"""Turn ground.json (build_ground.py) into a MAXScript that builds the scene and saves a new .max.

Ground: one Editable Poly, Multi/Sub (PhysicalMaterial placeholders), UV channel 1 = local metres.
Paint: one SplineShape, exact bezier arcs (<= 90 deg per piece), small tangent kinks (< KINK_MAX deg)
aligned so the line runs smoothly, renderable rectangular section. Curbs: renderable splines per type.

Usage: python -I write_ms.py <ground.json> <out.ms> <save.max> [--max-version 2024]
"""
from __future__ import annotations

import json
import math
import sys

PAINT_W, PAINT_H, PAINT_Z = 0.05, 0.003, 0.0005  # bottom 1 mm below the surface
KINK_MAX = 20.0  # deg: smaller tangent breaks are smoothed
KINK_MIN = 0.3


def f(x):
    return f"{x:.5f}".rstrip("0").rstrip(".") if abs(x) > 1e-9 else "0"


def p3(p, z):
    return f"[{f(p[0])},{f(p[1])},{f(z)}]"


def bulge_pieces(p0, p1, b):
    """Cubic bezier pieces (a, c1, c2, b) for a bulge segment, <= 90 deg each."""
    theta = 4 * math.atan(b)  # signed sweep, ccw positive
    chord = math.dist(p0, p1)
    r = chord / (2 * math.sin(abs(theta) / 2))
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = (p1[0] - p0[0]) / chord, (p1[1] - p0[1]) / chord
    h = r * math.cos(abs(theta) / 2)  # centre distance from the chord midpoint
    s = 1 if theta > 0 else -1
    cx, cy = mx - s * dy * h, my + s * dx * h
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    n = max(1, math.ceil(abs(theta) / (math.pi / 2) - 1e-9))
    step = theta / n
    k = 4 / 3 * math.tan(step / 4) * r
    out = []
    for i in range(n):
        t0, t1 = a0 + i * step, a0 + (i + 1) * step
        A = (cx + r * math.cos(t0), cy + r * math.sin(t0))
        B = (cx + r * math.cos(t1), cy + r * math.sin(t1))
        C1 = (A[0] - k * math.sin(t0), A[1] + k * math.cos(t0))
        C2 = (B[0] + k * math.sin(t1), B[1] - k * math.cos(t1))
        out.append((A, C1, C2, B))
    out[0] = ((p0[0], p0[1]),) + out[0][1:]
    out[-1] = out[-1][:3] + ((p1[0], p1[1]),)
    return out


def poly_knots(v, closed):
    """Knots [pt, in, out] for a bulged polyline; straight pieces get handles at 1/3."""
    pieces = []
    n = len(v)
    for i in range(n if closed else n - 1):
        a, b = v[i], v[(i + 1) % n]
        if math.dist(a[:2], b[:2]) < 1e-6:
            continue
        if abs(a[2]) < 1e-9:
            A, B = a[:2], b[:2]
            pieces.append((A, (A[0] + (B[0] - A[0]) / 3, A[1] + (B[1] - A[1]) / 3),
                           (B[0] - (B[0] - A[0]) / 3, B[1] - (B[1] - A[1]) / 3), B))
        else:
            pieces.extend(bulge_pieces(a[:2], b[:2], a[2]))
    if not pieces:
        return [], 0
    knots = []
    for i, (A, C1, C2, B) in enumerate(pieces):
        prev_in = pieces[i - 1][2] if (i > 0 or closed) else A
        knots.append([A, prev_in, C1])
    if not closed:
        knots.append([pieces[-1][3], pieces[-1][2], pieces[-1][3]])
    smoothed = 0
    for k in knots:  # align near-tangent breaks
        P, I, O = k
        vi = (P[0] - I[0], P[1] - I[1])
        vo = (O[0] - P[0], O[1] - P[1])
        li, lo = math.hypot(*vi), math.hypot(*vo)
        if li < 1e-9 or lo < 1e-9:
            continue
        ang = math.degrees(math.acos(max(-1, min(1, (vi[0] * vo[0] + vi[1] * vo[1]) / (li * lo)))))
        if KINK_MIN < ang < KINK_MAX:
            d = (vi[0] / li + vo[0] / lo, vi[1] / li + vo[1] / lo)
            dl = math.hypot(*d)
            d = (d[0] / dl, d[1] / dl)
            k[1] = (P[0] - d[0] * li, P[1] - d[1] * li)
            k[2] = (P[0] + d[0] * lo, P[1] + d[1] * lo)
            smoothed += 1
    return knots, smoothed


def pts_knots(pts, closed):
    """Knots through sampled points: smooth (Catmull-Rom handles) where the turn is < KINK_MAX deg."""
    n = len(pts)
    knots = []
    for i, P in enumerate(pts):
        prev = pts[i - 1] if (i > 0 or closed) else None
        nxt = pts[(i + 1) % n] if (i < n - 1 or closed) else None
        li = math.dist(prev, P) / 3 if prev else 0.0
        lo = math.dist(P, nxt) / 3 if nxt else 0.0
        di = ((P[0] - prev[0]) / (3 * li), (P[1] - prev[1]) / (3 * li)) if prev and li > 0 else None
        do = ((nxt[0] - P[0]) / (3 * lo), (nxt[1] - P[1]) / (3 * lo)) if nxt and lo > 0 else None
        if di and do and math.degrees(math.acos(max(-1, min(1, di[0] * do[0] + di[1] * do[1])))) < KINK_MAX:
            d = (di[0] + do[0], di[1] + do[1])
            dl = math.hypot(*d)
            di = do = (d[0] / dl, d[1] / dl)
        di = di or do
        do = do or di
        knots.append([P, (P[0] - di[0] * li, P[1] - di[1] * li), (P[0] + do[0] * lo, P[1] + do[1] * lo)])
    return knots


def circle_knots(c, r):
    k = 4 / 3 * math.tan(math.pi / 8) * r
    out = []
    for i in range(4):
        t = i * math.pi / 2
        P = (c[0] + r * math.cos(t), c[1] + r * math.sin(t))
        T = (-math.sin(t), math.cos(t))
        out.append([P, (P[0] - k * T[0], P[1] - k * T[1]), (P[0] + k * T[0], P[1] + k * T[1])])
    return out


def spline_ms(var, knots, closed, z):
    lines = [f"si = addNewSpline {var}"]
    for P, I, O in knots:
        lines.append(f"addKnot {var} si #bezierCorner #curve {p3(P, z)} {p3(I, z)} {p3(O, z)}")
    if closed:
        lines.append(f"close {var} si")
    return lines


def main(src, out_ms, save_path, max_version=None, renderer="corona"):
    d = json.load(open(src, encoding="utf-8"))
    ox, oy, _ = d["origin"]
    L = ["resetMaxFile #noPrompt",
         "units.SystemType = #meters; units.DisplayType = #metric; units.MetricType = #meters",
         "fn agrlog s = (format \"AGR %\\n\" s)",
         "global g, pt, cb, vs, fs, ids, mm, si, bb, r",
         "undo off ("]
    # ---- ground mesh
    L.append("vs = #(" + ",".join(p3(v, 0) for v in d["verts"]) + ")")
    L.append("fs = #(" + ",".join(f"[{a + 1},{b + 1},{c + 1}]" for a, b, c in d["faces"]) + ")")
    L.append("ids = #(" + ",".join(str(i) for i in d["matid"]) + ")")
    L += ["g = mesh vertices:vs faces:fs materialIDs:ids", 'g.name = "PZU_Ground"',
          "for i = 1 to g.numfaces do (setFaceSmoothGroup g i 1)",
          "meshop.setMapSupport g 1 true", "meshop.setNumMapVerts g 1 vs.count",
          "for i = 1 to vs.count do meshop.setMapVert g 1 i vs[i]",
          "for i = 1 to fs.count do meshop.setMapFace g 1 i fs[i]",
          "update g", f"g.position = [{f(ox)},{f(oy)},0]"]
    mats = d["materials"]
    mid = {m["name"]: m["id"] for m in mats}
    L.append(f'mm = Multimaterial numsubs:{len(mats)} name:"PZU_Multi"')
    for m in mats:
        r, gg, b = m["rgb"]
        rough = 0.3 if m["name"] == "Paint_White" else 0.8
        if renderer == "corona":
            mtl = f'CoronaPhysicalMtl name:"{m["name"]}" baseColor:(color {r} {gg} {b}) baseRoughness:{rough}'
        else:
            mtl = f'PhysicalMaterial name:"{m["name"]}" base_color:(color {r} {gg} {b}) roughness:{rough}'
        L += [f'mm.materialIDList[{m["id"]}] = {m["id"]}', f'mm.materialList[{m["id"]}] = {mtl}',
              f'mm.names[{m["id"]}] = "{m["name"]}"']
    L += ["g.material = mm", "convertTo g Editable_Poly"]
    # ---- paint
    L += ["pt = SplineShape name:\"PZU_Paint\"", "pt.wirecolor = white"]
    smoothed = 0
    for it in d["paint"]:
        if it["kind"] == "poly":
            kn, s = poly_knots(it["v"], it["closed"])
            smoothed += s
            if kn:
                L += spline_ms("pt", kn, it["closed"], PAINT_Z)
        elif it["kind"] == "pts":
            L += spline_ms("pt", pts_knots(it["pts"], it["closed"]), it["closed"], PAINT_Z)
        elif it["kind"] == "circle":
            L += spline_ms("pt", circle_knots(it["c"], it["r"]), True, PAINT_Z)
        elif it["kind"] == "arc":
            a0, a1 = math.radians(it["a0"]), math.radians(it["a1"])
            c, r = it["c"], it["r"]
            P0 = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
            P1 = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
            sweep = (a1 - a0) % (2 * math.pi)
            kn, _ = poly_knots([(P0[0], P0[1], math.tan(sweep / 4)), (P1[0], P1[1], 0)], False)
            L += spline_ms("pt", kn, False, PAINT_Z)
    L += ["updateShape pt", f"pt.position = pt.position + [{f(ox)},{f(oy)},0]",
          "pt.material = mm",
          f"for s = 1 to numSplines pt do for k = 1 to numSegments pt s do setMaterialID pt s k {mid['Paint_White']}",
          "pt.steps = 12; pt.optimize = true",
          "pt.render_renderable = true; pt.render_displayRenderMesh = true; pt.render_rectangular = true",
          f"pt.render_length = {f(PAINT_H)}; pt.render_width = {f(PAINT_W)}; pt.render_angle = 0",
          f"pt.render_viewport_rectangular = true; pt.render_viewport_length = {f(PAINT_H)}; pt.render_viewport_width = {f(PAINT_W)}"]
    # ---- curbs
    by_name = {}
    for c in d["curbs"]:
        by_name.setdefault(c["name"], []).append(c)
    for name, items in by_name.items():
        w, h = items[0]["width"], items[0]["height"]
        var = "cb"
        L += [f'{var} = SplineShape name:"PZU_{name}"', f"{var}.wirecolor = (color 160 160 160)"]
        for c in items:
            kn, _ = poly_knots(c["v"], c["closed"])
            if kn:
                L += spline_ms(var, kn, c["closed"], 0)
        L += [f"updateShape {var}", f"{var}.position = {var}.position + [{f(ox)},{f(oy)},0]", f"{var}.material = mm",
              f"for s = 1 to numSplines {var} do for k = 1 to numSegments {var} s do setMaterialID {var} s k {mid['Curb_Concrete']}",
              f"{var}.steps = 12; {var}.optimize = true",
              f"{var}.render_renderable = true; {var}.render_displayRenderMesh = true; {var}.render_rectangular = true",
              f"{var}.render_length = {f(2 * h)}; {var}.render_width = {f(w)}; {var}.render_angle = 0",
              f"{var}.render_viewport_rectangular = true; {var}.render_viewport_length = {f(2 * h)}; {var}.render_viewport_width = {f(w)}"]
    L.append(")")  # undo off
    # ---- readback evidence
    L += ['bb = nodeGetBoundingBox pt (matrix3 1)', 'agrlog ("paint_bbox_z " + (bb[1].z as string) + " " + (bb[2].z as string))',
          'agrlog ("ground faces=" + (polyop.getNumFaces g) as string + " verts=" + (polyop.getNumVerts g) as string + " openEdges=" + ((polyop.getOpenEdges g).numberSet as string))',
          'agrlog ("paint splines=" + (numSplines pt) as string)']
    if renderer == "corona":
        L.append('try (renderers.current = Corona()) catch (agrlog "no Corona renderer")')
    ver = f" saveAsVersion:{max_version}" if max_version else ""
    L.append(f'r = saveMaxFile @"{save_path}" quiet:true{ver}')
    L.append('agrlog ("saved=" + r as string)')
    with open(out_ms, "w", encoding="utf-8-sig") as fh:
        fh.write("\n".join(L) + "\n")
    print(json.dumps({"lines": len(L), "paint_kinks_smoothed": smoothed}))


if __name__ == "__main__":
    a = sys.argv[1:]
    mv = None
    if "--max-version" in a:
        i = a.index("--max-version")
        mv = a[i + 1]
        a = a[:i] + a[i + 2:]
    rd = "corona"
    if "--renderer" in a:
        i = a.index("--renderer")
        rd = a[i + 1]
        a = a[:i] + a[i + 2:]
    main(*a[:3], max_version=mv, renderer=rd)
