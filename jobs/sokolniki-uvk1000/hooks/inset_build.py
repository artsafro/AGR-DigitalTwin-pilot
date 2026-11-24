"""#1784 step 3 hook (stage `body`, point `after`): inset elements on the accepted body v005 [D378].

Pattern: n/a | new-case: quad inset families from Revit oriented boxes (inset_obb_blender.py output) - roof steel
cage, roof mesh, glass canopies, lamellas (accent panels RAL 8023) and the F05 outer glazing with its own ends
closing the gap to the body face. The body is not read for geometry except the D06/D07 face line and the F05 mouth
(body_config_v005.json `contour_cut` rectangles); nothing of the body is written.

    uv run python jobs/sokolniki-uvk1000/hooks/inset_build.py REVIT_OBB.json VOLUME_LINES.json NEW_OUT_DIR \
        [--config jobs/sokolniki-uvk1000/insets_config.json] [--body-config jobs/sokolniki-uvk1000/body_config_v005.json]

Writes NEW_OUT_DIR/insets_meshes.json ({object: {"verts", "faces": [{"v", "mat", "uv"}]}}, the
volume_body_blender.py mesh format) and NEW_OUT_DIR/insets_report.json (per family: Revit members, faces, tris,
non-quad faces, decisions). Exit 0 ok, 2 bad input / output exists.
"""
import argparse
import json
import math
import os
import sys

JOB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _add(*vs):
    return [sum(v[i] for v in vs) for i in range(3)]


def _mul(a, k):
    return [x * k for x in a]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return [x / n for x in a]


class Mesh:
    def __init__(self):
        self.verts, self.faces, self._idx = [], [], {}

    def v(self, p):
        k = tuple(round(x, 4) for x in p)
        if k not in self._idx:
            self._idx[k] = len(self.verts)
            self.verts.append([round(x, 5) for x in p])
        return self._idx[k]

    def face(self, pts, mat, tile=1.0, want=None):
        """Planar face; UV = metric projection on the face plane (u along the first edge) / tile. `want` turns the
        winding so the normal points along that vector."""
        if want is not None:
            nn = [0.0, 0.0, 0.0]
            for i in range(len(pts)):  # Newell normal
                p, q = pts[i], pts[(i + 1) % len(pts)]
                nn = _add(nn, [(p[1] - q[1]) * (p[2] + q[2]), (p[2] - q[2]) * (p[0] + q[0]),
                               (p[0] - q[0]) * (p[1] + q[1])])
            if _dot(nn, want) < 0:
                pts = pts[::-1]
        ids = [self.v(p) for p in pts]
        if len(set(ids)) < 3:
            return False
        e = _unit(_sub(pts[1], pts[0]))
        n = _unit(_cross(_sub(pts[1], pts[0]), _sub(pts[-1], pts[0])))
        f = _cross(n, e)
        uv = [(round(_dot(_sub(p, pts[0]), e) / tile, 5), round(_dot(_sub(p, pts[0]), f) / tile, 5)) for p in pts]
        self.faces.append({"v": ids, "mat": mat, "uv": uv})
        return True

    def as_dict(self):
        return {"verts": self.verts, "faces": self.faces}

    def begin_element(self):
        """Separate element: its vertices are never welded to an earlier element's (no cross-member weld)."""
        self._idx = {}


def _column_at(e, columns, reach, zr):
    for col in columns:
        c, h = col["center"], col["half"]
        if abs(e[0] - c[0]) <= h[1] + reach and abs(e[1] - c[1]) <= h[2] + reach \
                and c[2] - h[0] - zr <= e[2] <= c[2] + h[0] + zr:
            return c
    return None


def snap_ends(center, u, half, r, columns, reach):
    """A horizontal beam end inside a column footprint (+ `reach`; in z its span + the beam radius, a beam resting on
    the column top) moves along the beam to the column axis.
    Returns (center, half_length)."""
    ends = []
    for sg in (-1, 1):
        e = _add(center, _mul(u, sg * half))
        hit = _column_at(e, columns, reach, r + 0.01)
        if hit is not None and abs(u[2]) < 0.9:
            k = ((hit[0] - e[0]) * u[0] + (hit[1] - e[1]) * u[1]) / (u[0] * u[0] + u[1] * u[1])
            e = _add(e, _mul(u, k))
        ends.append(e)
    return _mul(_add(ends[0], ends[1]), 0.5), math.sqrt(_dot(_sub(ends[1], ends[0]), _sub(ends[1], ends[0]))) / 2.0


def finish_ends(center, u, half, r, k):
    """Every beam end runs on by k x its own radius into the column / beam it meets: two beams meeting on a column
    axis never share an end corner, and collinear beams of different sections never end in one plane.
    Returns (center, half_length)."""
    ends = [_add(center, _mul(u, sg * (half + k * r))) for sg in (-1, 1)]
    return _mul(_add(ends[0], ends[1]), 0.5), math.sqrt(_dot(_sub(ends[1], ends[0]), _sub(ends[1], ends[0]))) / 2.0


def diamond(o, run_on):
    """Beam as a diamond tube (square turned 45 deg about its axis, faces at the tube radius): no beam face is
    parallel to a column face or to a crossing beam, so nothing is coplanar where they meet."""
    u = _unit(o["axes"][0])
    r = (o["half"][1] + o["half"][2]) / 2.0
    c, hl = finish_ends(o["center"], u, o["half"][0], r, run_on)
    w = _unit(_cross(u, [0.0, 0.0, 1.0])) if abs(u[2]) < 0.9 else _unit(o["axes"][1])
    v = _cross(w, u)
    return {"c": c, "u": u, "hl": hl, "r": r, "d1": _unit(_add(v, w)), "d2": _unit(_sub(v, w))}


def separate_parallel(beams, cc):
    """Two parallel beams side by side whose diamond faces lie within `parallel_gap_m` of one plane (Revit rails
    a few mm apart): the thinner one loses `thin_m` of radius until no face pair is that close. Returns the count."""
    thinned = 0
    for _ in range(4):
        changed = False
        for i, a in enumerate(beams):
            for b in beams[i + 1:]:
                if abs(_dot(a["u"], b["u"])) < cc["beam_cos_min"]:
                    continue
                d = _sub(b["c"], a["c"])
                along = _dot(d, a["u"])
                if abs(along) > a["hl"] + b["hl"]:
                    continue  # spans apart
                if math.sqrt(max(_dot(d, d) - along * along, 0.0)) > a["r"] + b["r"] + 0.05:
                    continue
                close = False
                lo, hi = max(-a["hl"], along - b["hl"]), min(a["hl"], along + b["hl"])
                cu = _dot(a["u"], b["u"])
                for dv in (a["d1"], a["d2"]):
                    for sg in (-1, 1):  # face offsets at both ends of the shared span (a slope may cross them)
                        gaps = []
                        for tt in (lo, hi):
                            pa = _add(a["c"], _mul(a["u"], tt))
                            pb = _add(b["c"], _mul(b["u"], (tt - along) / cu))
                            gaps.append((sg * _dot(dv, pa) + a["r"]) - (sg * _dot(dv, pb) + b["r"]))
                        if min(abs(g) for g in gaps) < cc["parallel_gap_m"] or gaps[0] * gaps[1] < 0:
                            close = True
                if close:
                    thin = a if a["r"] <= b["r"] else b
                    thin["r"] -= cc["thin_m"]
                    thinned += 1
                    changed = True
        if not changed:
            break
    return thinned


def prepare_cage(objs, cc, report):
    """Roof steel cage: columns (vertical round tubes) and beams (horizontal tubes) as clean boxes. Returns
    (columns, beams); records every join/drop/thinning in report["merged_runs"]."""
    report["merged_runs"] = {}
    cols = [{k: o[k] for k in ("center", "axes", "half")} for o in objs if o["family"] == "cage_column"]
    n_cols = len(cols)
    cols, dup = merge_runs(cols, cc["merge_tol_m"])
    cols, joined = merge_columns(cols, cc["merge_tol_m"])
    report["merged_runs"]["cage_column"] = {"members": n_cols, "boxes": len(cols), "duplicates_dropped": dup,
                                            "touching_joined": joined}
    beams = [{k: o[k] for k in ("center", "axes", "half")} for o in objs if o["family"] == "cage_beam"]
    n_beams = len(beams)
    flattened = 0
    for b in beams:  # a near-level beam (Revit modelling slope < flatten_slope) is drawn level at its mid height
        u = _unit(b["axes"][0])
        if 0.0 < abs(u[2]) < cc["flatten_slope"]:
            b["axes"] = [_unit([u[0], u[1], 0.0])] + [list(a) for a in b["axes"][1:]]
            flattened += abs(u[2]) > 1e-3  # count real slopes, not PCA noise
    for b in beams:
        c, hl = snap_ends(b["center"], _unit(b["axes"][0]), b["half"][0], (b["half"][1] + b["half"][2]) / 2.0,
                          cols, cc["snap_reach_m"])
        b["center"], b["half"] = c, [hl, b["half"][1], b["half"][2]]
    beams, dup = merge_runs(beams, cc["merge_tol_m"], near=cc["beam_near_m"], cos_min=cc["beam_cos_min"])
    beams, inside = drop_contained(beams, cc["beam_cos_min"], cc["contained_slack_m"])
    beams = [diamond(o, cc["beam_end_run_on_r"]) for o in beams]
    lapped = lap_end_to_end(beams, cc)
    thinned = separate_parallel(beams, cc)
    raised = raise_column_tops(cols, beams)
    cleared = clear_end_faces(cols, beams, cc["parallel_gap_m"])
    report["merged_runs"]["cage_beam"] = {"members": n_beams, "boxes": len(beams), "duplicates_dropped": dup,
                                          "contained_dropped": inside, "end_to_end_lapped": lapped,
                                          "thinned_parallel": thinned, "ends_cleared_of_column_faces": cleared,
                                          "flattened_near_level": flattened}
    report["merged_runs"]["cage_column"]["tops_raised_into_beam"] = raised
    return cols, beams


def lap_end_to_end(beams, cc):
    """Two collinear beams of different sections meeting end to end: the thinner one runs 0.02 m past the thicker
    one's end face into it, so their end faces never share a plane. Returns the count."""
    lapped = 0
    for a in beams:
        for b in beams:
            if a is b or a["r"] > b["r"] or abs(_dot(a["u"], b["u"])) < cc["beam_cos_min"]:
                continue
            d = _sub(b["c"], a["c"])
            along = _dot(d, a["u"])
            if math.sqrt(max(_dot(d, d) - along * along, 0.0)) > b["r"]:
                continue
            for sg in (-1, 1):  # a's end on side sg against b's opposite end
                ea = sg * a["hl"]
                eb = along - sg * b["hl"] * (1 if _dot(a["u"], b["u"]) > 0 else 1)
                if abs(ea - eb) <= a["r"] + b["r"] and sg * (along - ea) > 0:
                    new_end = eb + sg * 0.02
                    other = -sg * a["hl"]
                    a["c"] = _add(a["c"], _mul(a["u"], (new_end + other) / 2.0))
                    a["hl"] = abs(new_end - other) / 2.0
                    lapped += 1
                    break
    return lapped


def raise_column_tops(cols, beams):
    """A column whose top stops just under a beam passing over it (the beam rests on it) runs up to the beam axis,
    so the column top is inside the beam - never touching its lower edge. Returns the count."""
    raised = 0
    for col in cols:
        c, h = col["center"], col["half"]
        top = c[2] + h[0]
        new_top = top
        for b in beams:
            if abs(b["u"][2]) > 0.2:
                continue
            uxy = math.hypot(b["u"][0], b["u"][1])
            t = ((c[0] - b["c"][0]) * b["u"][0] + (c[1] - b["c"][1]) * b["u"][1]) / (uxy * uxy)
            if abs(t) > b["hl"]:
                continue
            px, py = b["c"][0] + b["u"][0] * t, b["c"][1] + b["u"][1] * t
            if math.hypot(px - c[0], py - c[1]) > b["r"] + max(h[1], h[2]):
                continue
            zb = b["c"][2] + b["u"][2] * t
            if 0.0 <= zb - top <= math.sqrt(2.0) * b["r"] + 0.02:
                new_top = max(new_top, zb)
        if new_top > top:
            bottom = c[2] - h[0]
            col["center"] = [c[0], c[1], (bottom + new_top) / 2.0]
            col["half"] = [(new_top - bottom) / 2.0, h[1], h[2]]
            raised += 1
    return raised


def clear_end_faces(cols, beams, gap):
    """Last pass: a beam end face lying within `gap` of a parallel column face it touches moves 1.5 gap further
    into the column (both directions are checked, at most 3 rounds). Returns the number of moved ends."""
    moved = 0
    for _ in range(3):
        changed = False
        for b in beams:
            for sg in (-1, 1):
                e = _add(b["c"], _mul(b["u"], sg * b["hl"]))
                for col in cols:
                    c, h = col["center"], col["half"]
                    reach = math.sqrt(2.0) * b["r"]
                    if not (abs(e[0] - c[0]) <= h[1] + reach and abs(e[1] - c[1]) <= h[2] + reach
                            and c[2] - h[0] - reach <= e[2] <= c[2] + h[0] + reach):
                        continue
                    for ax, hh in ((0, h[1]), (1, h[2])):
                        if abs(b["u"][ax]) < 0.9999:
                            continue
                        for face in (c[ax] - hh, c[ax] + hh):
                            if abs(e[ax] - face) < gap:
                                step = 1.5 * gap
                                b["c"] = _add(b["c"], _mul(b["u"], sg * step / 2.0))
                                b["hl"] += step / 2.0
                                e = _add(b["c"], _mul(b["u"], sg * b["hl"]))
                                moved += 1
                                changed = True
        if not changed:
            break
    return moved


def drop_contained(boxes, cos_min, slack):
    """Drop a tube lying inside a bigger parallel tube (a Revit stub along a rail): parallel axes, its span within
    the other's, axis offset + its radius <= the other's radius + `slack`. Returns (boxes, dropped)."""
    keep = []
    order = sorted(boxes, key=lambda b: -(b["half"][1] + b["half"][2]))
    for b in order:
        u = _unit(b["axes"][0])
        rb = (b["half"][1] + b["half"][2]) / 2.0
        inside = False
        for a in keep:
            ua = _unit(a["axes"][0])
            if abs(_dot(u, ua)) < cos_min:
                continue
            ra = (a["half"][1] + a["half"][2]) / 2.0
            d = _sub(b["center"], a["center"])
            along = _dot(d, ua)
            lat = math.sqrt(max(_dot(d, d) - along * along, 0.0))
            if lat + rb <= ra + slack and abs(along) + b["half"][0] <= a["half"][0] + slack:
                inside = True
                break
        if not inside:
            keep.append(b)
    return keep, len(boxes) - len(keep)


def merge_columns(boxes, tol):
    """Vertical round tubes: section turned to world X/Y (a round tube has no own section axes), then columns whose
    footprints and spans touch or overlap (stacked segments, twin or near-duplicate posts) become one box over
    their union. Returns (boxes, joined)."""
    aabb = []
    for b in boxes:
        r = (b["half"][1] + b["half"][2]) / 2.0
        c, h = b["center"], b["half"][0]
        aabb.append([c[0] - r, c[0] + r, c[1] - r, c[1] + r, c[2] - h, c[2] + h])
    parent = list(range(len(aabb)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(aabb)):
        for j in range(i + 1, len(aabb)):
            a, b = aabb[i], aabb[j]
            if all(a[2 * k] <= b[2 * k + 1] + tol and b[2 * k] <= a[2 * k + 1] + tol for k in range(3)):
                parent[root(j)] = root(i)
    groups = {}
    for i in range(len(aabb)):
        groups.setdefault(root(i), []).append(aabb[i])
    out = []
    for g in groups.values():
        u = [min(b[0] for b in g), max(b[1] for b in g), min(b[2] for b in g), max(b[3] for b in g),
             min(b[4] for b in g), max(b[5] for b in g)]
        out.append({"center": [(u[0] + u[1]) / 2, (u[2] + u[3]) / 2, (u[4] + u[5]) / 2],
                    "axes": [[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    "half": [(u[5] - u[4]) / 2, (u[1] - u[0]) / 2, (u[3] - u[2]) / 2]})
    return out, len(boxes) - len(out)


def merge_runs(boxes, tol, near=None, cos_min=1 - 1e-5):
    """Join boxes lying on one axis line with the same section whose spans touch or overlap (stacked column
    segments, chained beams, adjacent canopy sheets): one box per run, so no two end faces are coplanar.
    `near` (default tol) is the allowed lateral offset of the two axis lines (near-duplicate tubes).
    Exact duplicates collapse into one. Returns (boxes, duplicates_dropped)."""
    near = tol if near is None else near
    items = [{"center": list(b["center"]), "axes": [list(a) for a in b["axes"]], "half": list(b["half"])}
             for b in boxes]
    dup = 0
    i = 0
    while i < len(items):
        j = i + 1
        while j < len(items):
            a, b = items[i], items[j]
            u = _unit(a["axes"][0])
            ok = abs(_dot(u, _unit(b["axes"][0]))) >= cos_min and abs(a["half"][1] - b["half"][1]) <= tol \
                and abs(a["half"][2] - b["half"][2]) <= tol
            if ok:
                d = _sub(b["center"], a["center"])
                along = _dot(d, u)
                lo = min(-a["half"][0], along - b["half"][0])
                hi = max(a["half"][0], along + b["half"][0])
                ok = math.sqrt(max(_dot(d, d) - along * along, 0.0)) <= near \
                    and (hi - lo) - 2.0 * (a["half"][0] + b["half"][0]) <= tol  # spans touch or overlap
            if not ok:
                j += 1
                continue
            if abs(along) <= tol and abs(a["half"][0] - b["half"][0]) <= tol:
                dup += 1
            a["center"] = _add(a["center"], _mul(u, (lo + hi) / 2.0))
            a["half"][0] = (hi - lo) / 2.0
            a["axes"][0] = u
            items.pop(j)
            j = i + 1  # the grown box may now reach an earlier-skipped one
        i += 1
    return items, dup


def box(mesh, center, axes, half, mat, embed_down=0.0):
    """Closed box of 6 outward quads; `embed_down` lowers the bottom face by that many metres (seat embedded in the
    roof below, never coplanar with it [D199])."""
    a = [_mul(_unit(axes[i]), half[i]) for i in range(3)]
    corners = {}
    for i in (-1, 1):
        for j in (-1, 1):
            for k in (-1, 1):
                corners[(i, j, k)] = _add(center, _mul(a[0], i), _mul(a[1], j), _mul(a[2], k))
    if embed_down:
        down = max(range(3), key=lambda i: abs(a[i][2]))  # the most vertical axis
        sgn = -1 if a[down][2] > 0 else 1
        for key in corners:
            if key[down] == sgn:
                corners[key] = _add(corners[key], [0.0, 0.0, -embed_down])
    for ax in range(3):
        for sg in (-1, 1):
            o1, o2 = [i for i in range(3) if i != ax]
            q = []
            for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                key = [0, 0, 0]
                key[ax], key[o1], key[o2] = sg, u, v
                q.append(corners[tuple(key)])
            mesh.face(q, mat, want=_mul(a[ax], sg))


def plane_quad(mesh, center, axes, half, mat, outward_xy=None):
    """One quad in the mid-plane of a thin element (mesh fence): spans the two largest axes; the normal is turned
    toward `outward_xy` for a vertical sheet, up for a horizontal one."""
    a0, a1 = _mul(_unit(axes[0]), half[0]), _mul(_unit(axes[1]), half[1])
    pts = [_add(center, _mul(a0, -1), _mul(a1, -1)), _add(center, a0, _mul(a1, -1)), _add(center, a0, a1),
           _add(center, _mul(a0, -1), a1)]
    n = _cross(a0, a1)
    want = [0.0, 0.0, 1.0] if abs(_unit(n)[2]) > 0.7 else [outward_xy[0], outward_xy[1], 0.0]
    mesh.face(pts, mat, want=want)


def _ring_ccw(xy):
    a = sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1] for i in range(len(xy)))
    return a > 0


def f05_frame(vl, edges):
    """Face line of the F05 mouth: start of the first edge, unit direction, outward unit normal (XY)."""
    e0, e1 = vl["edges"][edges[0]], vl["edges"][edges[-1]]
    a, b = e0["xy"][0], e1["xy"][1]
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    t = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    ccw = _ring_ccw(vl["volumes"][e0["volume"]]["ring"][:-1] if vl["volumes"][e0["volume"]]["ring"][0] ==
                    vl["volumes"][e0["volume"]]["ring"][-1] else vl["volumes"][e0["volume"]]["ring"])
    n = (t[1], -t[0]) if ccw else (-t[1], t[0])  # outward of a CCW ring is the right normal
    for e in edges:  # the mouth runs over collinear edges only
        p = vl["edges"][e]["xy"]
        for q in p:
            off = (q[0] - a[0]) * n[0] + (q[1] - a[1]) * n[1]
            if abs(off) > 0.02:
                raise ValueError("F05 edges %s are not collinear (%s off by %.3f m)" % (edges, e, off))
    return a, t, n, length


def glass_polyline(objs, a, t, n, s_max, z_min, cfg):
    """Plan polyline (s, out) of the outer glass from the Revit panels in front of the face line.

    Panels: vertical, normal within `normal_tol` of the face normal, centre 0..`max_out` m outside, z >= z_min.
    Facets = straight runs of panels (least-squares line, panel ends within `step_tol`, gaps < `mullion_gap`);
    two facets meet at the mid station; an out jump larger than `step_tol` there is a return (two points)."""
    segs = []
    for o in objs:
        if o["family"] != "curtain_glass" or o["zmin"] < z_min - 0.1:
            continue
        ax = o["axes"]
        hz = [i for i in range(3) if abs(ax[i][2]) < 0.3]
        nrm = [i for i in hz if abs(ax[i][0] * n[0] + ax[i][1] * n[1]) > 1 - cfg["normal_tol"]]
        run = [i for i in hz if abs(ax[i][0] * t[0] + ax[i][1] * t[1]) > 1 - cfg["normal_tol"]]
        if not nrm or not run:
            continue
        c = o["center"]
        out_c = (c[0] - a[0]) * n[0] + (c[1] - a[1]) * n[1]
        if not (-0.02 <= out_c <= cfg["max_out"]):
            continue
        ends = []
        for sg in (-1, 1):
            p = (c[0] + sg * ax[run[0]][0] * o["half"][run[0]], c[1] + sg * ax[run[0]][1] * o["half"][run[0]])
            ends.append(((p[0] - a[0]) * t[0] + (p[1] - a[1]) * t[1], (p[0] - a[0]) * n[0] + (p[1] - a[1]) * n[1]))
        ends.sort()
        if ends[1][0] < -0.5 or ends[0][0] > s_max + 0.5:
            continue
        segs.append((ends[0][0], ends[0][1], ends[1][0], ends[1][1]))
    if not segs:
        raise ValueError("no F05 glass panels in front of the face line")
    segs.sort()
    facets = []  # straight runs of panels: a panel joins the last facet if it lies on its line within step_tol

    def line(fc, s):
        return fc["k"] * s + fc["b"]
    for s0, o0, s1, o1 in segs:
        fc = facets[-1] if facets else None
        if fc and s0 <= fc["hi"] + cfg["mullion_gap"] and abs(line(fc, s0) - o0) <= cfg["step_tol"] \
                and abs(line(fc, s1) - o1) <= cfg["step_tol"]:
            fc["pts"] += [(s0, o0), (s1, o1)]
            fc["hi"] = max(fc["hi"], s1)
        else:
            fc = {"lo": s0, "hi": s1, "pts": [(s0, o0), (s1, o1)]}
            facets.append(fc)
        ps = fc["pts"]  # least-squares line out = k s + b over the facet's panel ends
        ms, mo = sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)
        var = sum((p[0] - ms) ** 2 for p in ps)
        fc["k"] = sum((p[0] - ms) * (p[1] - mo) for p in ps) / var if var > 1e-9 else 0.0
        fc["b"] = mo - fc["k"] * ms
    pts = [(facets[0]["lo"], line(facets[0], facets[0]["lo"]))]
    for f0, f1 in zip(facets, facets[1:]):
        sm = (f0["hi"] + f1["lo"]) / 2.0
        a0, a1 = line(f0, sm), line(f1, sm)
        if abs(a0 - a1) <= cfg["step_tol"]:
            pts.append((sm, (a0 + a1) / 2.0))
        else:  # a step: the return spans the mullion gap (>= return_min_m), so every closure stays a quad
            h = max(f1["lo"] - f0["hi"], cfg["return_min_m"]) / 2.0
            pts += [(sm - h, line(f0, sm - h)), (sm + h, line(f1, sm + h))]
    pts.append((facets[-1]["hi"], line(facets[-1], facets[-1]["hi"])))
    return _clip(pts, 0.0, s_max), len(segs)


def _out_at(pts, s, side):
    """Out at station s; on a return station `side` picks the left (-1) or right (+1) value."""
    at = [p for p in pts if abs(p[0] - s) < 1e-6]
    if at:
        return at[0][1] if side < 0 else at[-1][1]
    for p, q in zip(pts, pts[1:]):
        if p[0] <= s <= q[0] and q[0] > p[0]:
            return p[1] + (q[1] - p[1]) * (s - p[0]) / (q[0] - p[0])
    raise ValueError("station %.3f outside the glass polyline %.3f..%.3f" % (s, pts[0][0], pts[-1][0]))


def _clip(pts, s0, s1):
    if pts[0][0] > s0 + 0.3 or pts[-1][0] < s1 - 0.3:
        raise ValueError("glass covers %.3f..%.3f, mouth %.3f..%.3f" % (pts[0][0], pts[-1][0], s0, s1))
    if pts[0][0] > s0:  # extend the first facet to the mouth end (< 0.3 m)
        pts = [(s0, pts[0][1])] + pts
    if pts[-1][0] < s1:
        pts = pts + [(s1, pts[-1][1])]
    lo, hi = _out_at(pts, s0, 1), _out_at(pts, s1, -1)
    inner = [p for p in pts if s0 + 1e-6 < p[0] < s1 - 1e-6]
    return [(s0, lo)] + inner + [(s1, hi)]


def f05_glazing(mesh, pts, a, t, n, bands, mats):
    """Glass faces over the polyline per z band + own ends: top/bottom closures to the face line, end quads at the
    mouth ends and at the station where the mouth bottom steps. `bands` = [(s0, s1, zb, zt), ...] (mouth rects)."""
    def w(s, out, z):
        return [a[0] + t[0] * s + n[0] * out, a[1] + t[1] * s + n[1] * out, z]
    stations = sorted({round(b[0], 6) for b in bands} | {round(b[1], 6) for b in bands})
    for st in stations:  # every mouth corner station is a polyline vertex
        if not any(abs(p[0] - st) < 1e-6 for p in pts):
            o = _out_at(pts, st, 1)
            pts = sorted(pts + [(st, o)], key=lambda p: p[0])
    levels = sorted({b[2] for b in bands} | {b[3] for b in bands})

    def zr(s_mid):  # the z levels the mouth covers at s_mid
        zs = [(b[2], b[3]) for b in bands if b[0] - 1e-6 <= s_mid <= b[1] + 1e-6]
        lo, hi = min(z[0] for z in zs), max(z[1] for z in zs)
        return [z for z in levels if lo - 1e-6 <= z <= hi + 1e-6]
    glass = mats["glass"]
    end = mats["end"]
    n3, t3 = [n[0], n[1], 0.0], [t[0], t[1], 0.0]
    for p, q in zip(pts, pts[1:]):
        zl = zr((p[0] + q[0]) / 2.0) if q[0] > p[0] else zr(p[0])
        ds, do = q[0] - p[0], q[1] - p[1]
        ret = abs(do) > ds  # a return between two facets (steeper than 45 deg in plan)
        want = _add(_mul(t3, -do), _mul(n3, ds))  # outward: away from the face line
        for zb, zt in zip(zl, zl[1:]):
            mesh.face([w(p[0], p[1], zb), w(q[0], q[1], zb), w(q[0], q[1], zt), w(p[0], p[1], zt)],
                      end if ret else glass, want=want)
        for z, up in ((zl[0], False), (zl[-1], True)):  # closures between face line and glass (always quads)
            ring = [w(p[0], 0.0, z), w(q[0], 0.0, z), w(q[0], q[1], z), w(p[0], p[1], z)]
            mesh.face(ring, end, want=[0.0, 0.0, 1.0 if up else -1.0])
    # ends: the mouth end stations and the station where the bottom level changes
    for st in stations:
        left = [b for b in bands if b[0] - 1e-6 <= st - 1e-4 and st - 1e-4 <= b[1]]
        right = [b for b in bands if b[0] <= st + 1e-4 <= b[1] + 1e-6]
        zl = sorted({b[2] for b in left} | {b[3] for b in left})
        zr_ = sorted({b[2] for b in right} | {b[3] for b in right})
        span_l = (min(zl), max(zl)) if zl else None
        span_r = (min(zr_), max(zr_)) if zr_ else None
        segs = []
        if span_l is None or span_r is None:
            span = span_l or span_r
            segs.append((span[0], span[1], 1 if span_r is None else -1))
        else:
            if span_l[0] != span_r[0]:
                lo, hi = sorted((span_l[0], span_r[0]))
                segs.append((lo, hi, 1 if span_l[0] < span_r[0] else -1))
            if span_l[1] != span_r[1]:
                lo, hi = sorted((span_l[1], span_r[1]))
                segs.append((lo, hi, 1 if span_l[1] > span_r[1] else -1))
        out = _out_at(pts, st, -1 if st > pts[0][0] + 1e-6 else 1)
        for lo, hi, facing in segs:
            zs = [z for z in levels if lo - 1e-6 <= z <= hi + 1e-6]
            for zb, zt in zip(zs, zs[1:]):
                quad = [w(st, 0.0, zb), w(st, out, zb), w(st, out, zt), w(st, 0.0, zt)]
                mesh.face(quad, end, want=_mul(t3, facing))
    return pts


def _line_x(p, d, q, e):
    """Plan intersection of the lines p + a d and q + b e (None when parallel)."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    a = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + a * d[0], p[1] + a * d[1])


def mitre_ends(reliefs, joint, reach=0.6, cos_max=0.9, z_min=0.1):
    """[D384] Corner panels: Revit runs two non-parallel panels into the same corner (their rim boxes overlap). Each
    such end gets a mitre - the end v at the back plane and at the rim front from the intersections of the two
    panels' back lines and front lines - pulled back by joint / 2 along the panel, so the two end faces stay apart.
    Returns per panel {"vb": [v0, v1], "vf": [v0, v1]} (back / front v of both ends) and the mitre count."""
    ends = [{"vb": list(r["v"]), "vf": list(r["v"])} for r in reliefs]
    h, count = joint / 2.0, 0

    def line(r, t):
        o, N = r["origin"], r["N"]
        return (o[0] + t * N[0], o[1] + t * N[1]), (r["V"][0], r["V"][1])

    def vcoord(r, p):
        return (p[0] - r["origin"][0]) * r["V"][0] + (p[1] - r["origin"][1]) * r["V"][1]
    for i, a in enumerate(reliefs):
        for j in range(i + 1, len(reliefs)):
            b = reliefs[j]
            if abs(a["N"][0] * b["N"][0] + a["N"][1] * b["N"][1]) > cos_max:
                continue
            if min(a["z"][1], b["z"][1]) - max(a["z"][0], b["z"][0]) < z_min:
                continue
            pb = _line_x(*line(a, a["t_back"]), *line(b, b["t_back"]))
            pf = _line_x(*line(a, a["t_front"]), *line(b, b["t_front"]))
            if pb is None or pf is None:
                continue
            sides = []
            for r in (a, b):
                vb, vf = vcoord(r, pb), vcoord(r, pf)
                k = 0 if abs(vb - r["v"][0]) < abs(vb - r["v"][1]) else 1
                if abs(vb - r["v"][k]) > reach or abs(vf - r["v"][k]) > reach:
                    break
                sides.append((k, vb, vf))
            if len(sides) < 2:
                continue
            for e, (k, vb, vf) in zip((ends[i], ends[j]), sides):
                sg = 1.0 if k == 0 else -1.0
                e["vb"][k], e["vf"][k] = vb + sg * h, vf + sg * h
            count += 1
    return ends, count


def relief_panel(mesh, r, mat, top_min=0.05, margin=0.02, joint=0.0, ends=None):
    """[D384] Closed pyramid relief solid of one decor panel (10 quads, all planar): back quad, 4 rim quads from the
    back plane to the front rim, 4 facets from the rim to the apex truncated by a homothety about the apex (top side
    `top_min`), and the top quad. The rect shrinks by `joint` / 2 per side (abutting panels never share a face);
    `ends` (mitre_ends) gives the mitred back / front v of a corner end. Raises if the apex is not inside the rim by
    `margin`."""
    o, N, V = r["origin"], r["N"], r["V"]
    h = joint / 2.0
    e = ends or {"vb": list(r["v"]), "vf": list(r["v"])}
    vb = [e["vb"][0] + (h if e["vb"][0] == r["v"][0] else 0.0), e["vb"][1] - (h if e["vb"][1] == r["v"][1] else 0.0)]
    vf = [e["vf"][0] + (h if e["vf"][0] == r["v"][0] else 0.0), e["vf"][1] - (h if e["vf"][1] == r["v"][1] else 0.0)]
    (v0, v1), (z0, z1) = vf, (r["z"][0] + h, r["z"][1] - h)
    if not (v0 + margin < r["apex_v"] < v1 - margin and z0 + margin < r["apex_z"] < z1 - margin):
        raise ValueError("relief apex (%.3f, %.3f) outside the panel rim" % (r["apex_v"], r["apex_z"]))
    if not r["t_back"] < r["t_front"] < r["t_apex"]:
        raise ValueError("relief depths must rise back < rim < apex, got %r" % ([r["t_back"], r["t_front"], r["t_apex"]],))

    def P(v, z, t):
        return [o[0] + v * V[0] + t * N[0], o[1] + v * V[1] + t * N[1], z]
    k = top_min / min(v1 - v0, z1 - z0)
    av, az, at = r["apex_v"], r["apex_z"], r["t_apex"]
    rect = [(v0, z0), (v1, z0), (v1, z1), (v0, z1)]
    back = [P(vb[0] if v == v0 else vb[1], z, r["t_back"]) for v, z in rect]
    rim = [P(v, z, r["t_front"]) for v, z in rect]
    top = [P(av + k * (v - av), az + k * (z - az), at + k * (r["t_front"] - at)) for v, z in rect]
    c = P((v0 + v1) / 2.0, (z0 + z1) / 2.0, (r["t_back"] + r["t_front"]) / 2.0)
    mesh.face(back, mat, want=_mul(N, -1))
    mesh.face(top, mat, want=N)
    for i in range(4):
        j = (i + 1) % 4
        mid = _mul(_add(rim[i], rim[j]), 0.5)
        out = _sub(mid, c)
        mesh.face([back[i], back[j], rim[j], rim[i]], mat, want=_sub(out, _mul(N, _dot(out, N))))
        fm = _mul(_add(rim[i], rim[j], top[j], top[i]), 0.25)
        mesh.face([rim[i], rim[j], top[j], top[i]], mat, want=_add(_sub(fm, P(av, az, r["t_front"])), _mul(N, 0.05)))
    return at - (at + k * (r["t_front"] - at))


def flashing_quad(mesh, center, axes, half, mat):
    """[D384] One quad on the upper face of a thin sloped sheet (window flashing), normal up."""
    a = [_mul(_unit(axes[i]), half[i]) for i in range(3)]
    up = a[2] if a[2][2] >= 0 else _mul(a[2], -1)
    c = _add(center, up)
    pts = [_add(c, _mul(a[0], -1), _mul(a[1], -1)), _add(c, a[0], _mul(a[1], -1)), _add(c, a[0], a[1]),
           _add(c, _mul(a[0], -1), a[1])]
    mesh.face(pts, mat, want=[0.0, 0.0, 1.0])


def _box_sz(obj, a, t, n):
    """Plan extent of an OBB in the (s along t, out along n) frame of a face line starting at a."""
    ss, oo = [], []
    ax, hf, c = obj["axes"], obj["half"], obj["center"]
    for i in (-1, 1):
        for j in (-1, 1):
            for k in (-1, 1):
                p = _add(c, _mul(ax[0], i * hf[0]), _mul(ax[1], j * hf[1]), _mul(ax[2], k * hf[2]))
                ss.append((p[0] - a[0]) * t[0] + (p[1] - a[1]) * t[1])
                oo.append((p[0] - a[0]) * n[0] + (p[1] - a[1]) * n[1])
    return min(ss), max(ss), min(oo), max(oo)


def f05_ground(objs, vl, g, sill):
    """[D384] F05 ground floor: piers (columns) and the glazing between them, in the frame of the body face `edge`.

    Piers = exterior-wall pieces standing 0..7.5 m within `pier_out` of the face line, grouped by station (gap <
    `pier_gap_m`); one box per pier: Revit station range and front, back `embed_m` behind the face. Glazing = Revit
    curtain panels under `glass_zmax` behind the face; one quad per bay (glass station range minus the piers),
    `glass_out_m` in front of the face, from the base 0.0 to `sill` (the F05 mouth sill). Returns two meshes + report."""
    a, t, n, length = f05_frame(vl, [g["edge"]])
    pieces = []
    for o in objs:
        if o["family"] != "pier" or not (g["pier_z"][0] <= o["zmin"] and g["pier_zmax_min"] <= o["zmax"] <= g["pier_z"][1]):
            continue
        s0, s1, o0, o1 = _box_sz(o, a, t, n)
        if s1 < 0 or s0 > length or o1 < g["pier_out"][0] or o0 > g["pier_out"][1]:
            continue
        if max(s1 - s0, o1 - o0) > g["pier_piece_max_m"]:
            continue
        pieces.append([s0, s1, o0, o1, o["zmin"], o["zmax"], o["name"]])
    pieces.sort()
    piers = []
    for p in pieces:
        if piers and p[0] <= piers[-1]["s"][1] + g["pier_gap_m"]:
            q = piers[-1]
            q["s"] = [min(q["s"][0], p[0]), max(q["s"][1], p[1])]
            q["out"] = [min(q["out"][0], p[2]), max(q["out"][1], p[3])]
            q["z"] = [min(q["z"][0], p[4]), max(q["z"][1], p[5])]
            q["names"].append(p[6])
        else:
            piers.append({"s": [p[0], p[1]], "out": [p[2], p[3]], "z": [p[4], p[5]], "names": [p[6]]})

    def w(s, out, z):
        return [a[0] + t[0] * s + n[0] * out, a[1] + t[1] * s + n[1] * out, z]
    pm = Mesh()
    t3, n3 = [t[0], t[1], 0.0], [n[0], n[1], 0.0]
    for q in piers:
        if q["out"][1] <= g["embed_m"]:
            raise ValueError("pier %s does not stand in front of the face" % q["names"][0])
        pm.begin_element()
        s0, s1 = q["s"]
        ob, of = -g["embed_m"], q["out"][1]
        zb, zt = max(0.0, q["z"][0]), q["z"][1]
        c = w((s0 + s1) / 2.0, (ob + of) / 2.0, (zb + zt) / 2.0)
        box(pm, c, [t3, n3, [0.0, 0.0, 1.0]], [(s1 - s0) / 2.0, (of - ob) / 2.0, (zt - zb) / 2.0], g["pier_material"])
    glass = [o for o in objs if o["family"] == "curtain_glass" and o["zmax"] <= g["glass_zmax"]]
    runs = []
    for o in glass:
        s0, s1, o0, o1 = _box_sz(o, a, t, n)
        if s1 < 0 or s0 > length or o1 < g["glass_out"][0] or o0 > g["glass_out"][1]:
            continue
        runs.append((max(0.0, s0), min(length, s1), (o0 + o1) / 2.0))
    if not runs:
        raise ValueError("no F05 ground-floor glass panels behind %s" % g["edge"])
    lo, hi = min(r[0] for r in runs), max(r[1] for r in runs)
    bays, cur = [], lo
    for q in sorted(piers, key=lambda q: q["s"][0]):
        if q["s"][1] <= lo or q["s"][0] >= hi:
            continue
        if q["s"][0] > cur + 1e-3:
            bays.append((cur, q["s"][0]))
        cur = max(cur, q["s"][1])
    if hi > cur + 1e-3:
        bays.append((cur, hi))
    gm = Mesh()
    for s0, s1 in bays:
        gm.face([w(s0, g["glass_out_m"], 0.0), w(s1, g["glass_out_m"], 0.0), w(s1, g["glass_out_m"], sill),
                 w(s0, g["glass_out_m"], sill)], g["glass_material"], want=n3)
    rep = {"piers": [{"s": [round(x, 3) for x in q["s"]], "revit_out": [round(x, 3) for x in q["out"]],
                      "z": q["z"], "revit_pieces": len(q["names"])} for q in piers],
           "glass_panels": len(runs), "glass_out_revit_m": [round(min(r[2] for r in runs), 3),
                                                            round(max(r[2] for r in runs), 3)],
           "bays": [[round(s0, 3), round(s1, 3)] for s0, s1 in bays], "sill_z": sill}
    return pm, gm, rep


def build(obb, vl, cfg, body_cfg):
    fams = cfg["families"]
    meshes, report = {}, {"families": {}, "decisions": []}
    objs = obb["objects"]
    cx = sum(o["center"][0] for o in objs) / len(objs)
    cy = sum(o["center"][1] for o in objs) / len(objs)
    cc = cfg["cage"]
    columns, beams = prepare_cage(objs, cc, report)
    for fam, spec in fams.items():
        if not spec.get("object") or fam == "curtain_glass":
            continue
        mesh = meshes.setdefault(spec["object"], Mesh())
        before = len(mesh.faces)
        members = [o for o in objs if o["family"] == fam]
        if fam == "cage_column":
            boxes = columns
        elif fam == "cage_beam":
            boxes = beams
        else:
            boxes = [dict(o["pane"]) if fam == "canopy" else {k: o[k] for k in ("center", "axes", "half")}
                     for o in members]
        if fam == "canopy":
            boxes, dup = merge_runs(boxes, cc["merge_tol_m"])
            report["merged_runs"][fam] = {"members": len(members), "boxes": len(boxes), "duplicates_dropped": dup}
        depth_lost = []
        if fam == "decor_panel":
            mends, n_mitre = mitre_ends([m["relief"] for m in members], cfg["relief"].get("joint_m", 0.0))
            report.setdefault("relief_mitres", n_mitre)
            mend = iter(mends)
        for o, m in zip(boxes, members if fam in ("decor_panel", "flashing", "hatch") else [None] * len(boxes)):
            mesh.begin_element()
            if fam in ("cage_column", "lamella", "canopy", "hatch"):
                box(mesh, o["center"], o["axes"], o["half"], spec["material"],
                    embed_down=cfg["cage"]["column_embed_m"] if fam == "cage_column" else 0.0)
            elif fam == "decor_panel":
                rc = cfg["relief"]
                assert m is not None
                depth_lost.append(relief_panel(mesh, m["relief"], spec["material"], rc["top_min_m"],
                                               rc["apex_margin_m"], rc.get("joint_m", 0.0), next(mend)))
            elif fam == "flashing":
                flashing_quad(mesh, o["center"], o["axes"], o["half"], spec["material"])
            elif fam == "cage_beam":
                box(mesh, o["c"], [o["u"], o["d1"], o["d2"]], [o["hl"], o["r"], o["r"]], spec["material"])
            elif fam == "mesh":
                plane_quad(mesh, o["center"], o["axes"], o["half"], spec["material"],
                           outward_xy=(o["center"][0] - cx, o["center"][1] - cy))
            else:
                raise ValueError("no builder for family %r" % fam)
        report["families"][fam] = {"revit_members": len(members), "revit_tris": sum(o["tris"] for o in members),
                                   "object": spec["object"], "material": spec["material"],
                                   "faces": len(mesh.faces) - before}
        if depth_lost:
            report["families"][fam]["relief_depth_lost_max_m"] = round(max(depth_lost), 4)
    f = cfg["f05"]
    a, t, n, length = f05_frame(vl, f["edges"])
    bands = [tuple(r["projected_rect"]) for r in body_cfg["extra_rectangles"]
             if r.get("facade") == "F05" and r.get("state") == "contour_cut"]
    if not bands:
        raise ValueError("no F05 contour_cut rectangles in the body config")
    s_max = max(b[1] for b in bands)
    pts, ncols = glass_polyline(objs, a, t, n, s_max, min(b[2] for b in bands), f)
    gm = Mesh()
    pts = f05_glazing(gm, pts, a, t, n, bands, {"glass": f["material"], "end": f["end_material"]})
    meshes[f["object"]] = gm
    report["families"]["f05_glazing"] = {
        "revit_panels": ncols, "object": f["object"], "material": [f["material"], f["end_material"]],
        "faces": len(gm.faces), "polyline": [[round(s, 3), round(o, 3)] for s, o in pts],
        "out_min_m": round(min(o for _, o in pts), 3), "out_max_m": round(max(o for _, o in pts), 3),
        "returns": sum(1 for p, q in zip(pts, pts[1:]) if abs(q[1] - p[1]) > q[0] - p[0]),
        "mouth_bands": [list(b) for b in bands]}
    if cfg.get("f05_ground"):
        g = cfg["f05_ground"]
        pm, gg, grep_ = f05_ground(objs, vl, g, min(b[2] for b in bands))
        meshes[g["pier_object"]], meshes[g["glass_object"]] = pm, gg
        report["families"]["f05_ground"] = dict(grep_, objects=[g["pier_object"], g["glass_object"]],
                                                faces=len(pm.faces) + len(gg.faces))
    out = {k: m.as_dict() for k, m in meshes.items()}
    tot = {"faces": 0, "tris": 0, "non_quads": 0}
    for k, m in out.items():
        nq = sum(1 for fc in m["faces"] if len(fc["v"]) != 4)
        tr = sum(len(fc["v"]) - 2 for fc in m["faces"])
        report.setdefault("objects", {})[k] = {"verts": len(m["verts"]), "faces": len(m["faces"]), "tris": tr,
                                               "non_quads": nq}
        tot["faces"] += len(m["faces"])
        tot["tris"] += tr
        tot["non_quads"] += nq
    report["total"] = tot
    report["decisions"] = cfg.get("decisions", [])
    return out, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("obb")
    ap.add_argument("volume_lines")
    ap.add_argument("out")
    ap.add_argument("--config", default=os.path.join(JOB, "insets_config.json"))
    ap.add_argument("--body-config", default=os.path.join(JOB, "body_config_v005.json"))
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "insets_meshes.json")):
        print("refused: %s already has insets_meshes.json" % a.out, file=sys.stderr)
        return 2
    try:
        with open(a.obb, encoding="utf-8") as fh:
            obb = json.load(fh)
        with open(a.volume_lines, encoding="utf-8") as fh:
            vl = json.load(fh)
        with open(a.config, encoding="utf-8") as fh:
            cfg = json.load(fh)
        with open(a.body_config, encoding="utf-8") as fh:
            body_cfg = json.load(fh)
        meshes, report = build(obb, vl, cfg, body_cfg)
    except (OSError, ValueError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    report["inputs"] = {"obb": os.path.realpath(a.obb), "obb_sha256": obb.get("sha256"),
                        "volume_lines": os.path.realpath(a.volume_lines)}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "insets_meshes.json"), "w", encoding="utf-8") as fh:
        json.dump(meshes, fh)
    with open(os.path.join(a.out, "insets_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    print(json.dumps(report["total"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
