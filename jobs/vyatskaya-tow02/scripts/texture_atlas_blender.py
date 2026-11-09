"""TOW02 texturing: one 2048 module atlas (window strips as in the source + solid swatches) and UV for every TOW02_*
object (runs inside Blender, headless).

Engine gap: EG4 (UV / atlas, docs/backlog.md). OKS 013 of 0200_Vyatskaya_Vl_47_49 [D156] (names as the accepted
reference SM_Vyatskaya_Vl_47_49_013_Main; layout: walls and all other parts solid colour, only windows drawn on the
atlas as dark frame + white glass, glass polygons laid on them).

Usage:
  blender -b outputs/build-v016/tow02_master.blend --python scripts/texture_atlas_blender.py -- <out_dir> [--runs <json>]
Writes <out>/tow02_tex.blend, <out>/textures/T_Vyatskaya_Vl_47_49_013_Main_{d,m,r}_1.png, <out>/atlas_layout.json,
<out>/face_mapping.json. The input .blend is never saved.

Windows (user 2026-10-21 "ленты как в источнике" = plan A2 of outputs/review-v001/windows):
Input = the measured source window layout `outputs/review-v001/windows/runs_typed_xy.json` (ray-cast of RC_TOW_02 in
front of every glass face of build-v013): per glass run (faces joined by shared vertical edges) its panes along the
run (u0, u1, fixed / sash), the run length and face widths, centroid xy, z0, height, normal azimuth of the first face.
The strips are drawn procedurally from these numbers (no ray-cast image is copied):
- body family (faces 2.72 m from slab top - 0.01; top storeys 65.38 / 68.78 have 2.74 m faces with the profile 1 cm
  higher), strip 2.74 m: fixed pane = frame 0.01-0.06, vision 0.06-2.16, transom 2.16-2.21, fanlight 2.21-2.66,
  frame 2.66-2.71 (z above a 2.72 face bottom); sash pane = sash frame inside the mullions at its measured width
  (0.045-0.065 m per side, from the vision-band glass), vision 0.11-2.11, fanlight 2.21-2.66 over the full pane width. Mullions, run-end jambs, double mullions and corner joints (jamb + jamb,
  no glass in the source) are frame colour at their measured widths; no uniform pitch.
- ring family (top ring 65.40-68.90, closed loop 48 m; our faces split at 68.1 are not a transom): strip 3.5 m from
  65.40, full-height panes (and the 2 cm glass slit inside each 0.21 m double mullion), frames 0.05 top / bottom;
  v from 65.40 so the 2.7 + 0.7 m faces read as one window.
- super family (superstructure 1 glass 72.20-75.70): strip 3.5 m, full-height panes, frames 0.05 top / bottom.
- 0.1 m slivers (68.8-68.9 above the ring) take the frame swatch.
Library (plan A2): runs in order of type frequency; a face is laid on any strip region of its family whose
frame / glass sequence matches the face's own u-range (interior boundaries and edge fit within MATCH_TOL_M); a run
whose face finds no match adds its own strip. Each face keeps its real width (px/m identical for all strips).
Glass elements (faces joined by shared vertical edges; after the glass cleanup of build-v017 usually one quad per flat
run, two quads per 90-degree corner run, one face per segment of a bend) are keyed to the measured runs by geometry,
not by face index: object, z range (a 3.5 m ring face carries the 2.7 + 0.7 m measured runs), run length, every element
vertex on a measured face boundary (<= 1 cm) and the measured face-corner centroid predicted on the element (<= 6 cm).
Each face gets its range in measured-run u: from the run start; on a corner run whose sliver was removed and whose legs
were stitched at their plan intersection (run length changed), faces after that corner are measured from the run end,
so both legs keep their true position and the corner joint (jamb + jamb) stays on frame colour. A face that spans a
whole run needs a strip holding the whole run pattern; the greedy library adds the run's own strip when none matches.
Strips longer than the atlas are cut at face boundaries. px/m = the highest that fits (shelf packing, PAD between
rects, edge-extended by PAD / 2 so mip levels do not bleed). Diffuse is box-filtered coverage (4x4 supersampling);
m / r binary (glass m1 r0, everything else m0 r1).
Everything else: solid swatches, one per finish, the face planar-projected into the swatch's inset square.
Palette from the accepted atlas_2048_1 (wall #303031, roof #a3a3a3, glass #fafaff). Unknown materials fail loudly.
"""
import json
import math
import os
import sys
from collections import Counter, defaultdict

import bpy
import numpy as np
from mathutils import Vector

SIZE = 2048
PAD = 8
EXT = PAD // 2                 # edge-extension of every rect (two neighbours meet in the middle of PAD)
SS = 4                         # supersampling per axis for coverage
PX_MAX, PX_STEP = 140.0, 0.25
SWATCH_PX = 32
SWATCH_INSET_PX = 4
MATCH_TOL_M = 0.010            # max frame misalignment of a face on a library strip
SASH_FRAME_M = 0.05
STRIP_MARGIN_M = 0.05          # frame colour added before / after every run on its strip
SLIVER_H_M = 0.2
HTOL = 0.006

WALL, ROOF, GLASS = "#303031", "#a3a3a3", "#fafaff"
FRAME = WALL
SWATCHES = [  # finish, colour, is_glass (order = tow02_finish id; append only)
    ("wall", WALL, False), ("reveal", WALL, False), ("band199", WALL, False), ("soffit", WALL, False),
    ("fin_main", WALL, False), ("fin_narrow_dark", WALL, False), ("fin_narrow_light", ROOF, False),
    ("louvre", WALL, False), ("roof", ROOF, False), ("coping", ROOF, False), ("ac_perforated", ROOF, False),
    ("ac_floor", ROOF, False), ("glass_solid", GLASS, True),
    ("glass_frame", FRAME, False), ("ac_coping", WALL, False), ("shaft_cap", ROOF, False), ("ledge_dark", WALL, False),
]
WINDOW_OBJECTS = ("TOW02_body_glass", "TOW02_top_glass")
FACADE_MATERIAL = "TOW02_facade"   # wall / roof / soffit by normal
MATERIAL_FINISH = {
    "TOW02_reveal": "reveal", "TOW02_band199": "band199", "TOW02_coping": "coping", "TOW02_louvre": "louvre",
    "TOW02_ac_perforated": "ac_perforated", "TOW02_ac_floor": "ac_floor", "TOW02_glass": "glass_solid",
    "TOW02_ac_coping": "ac_coping", "TOW02_shaft_cap": "shaft_cap", "TOW02_ledge_dark": "ledge_dark",
    "Material_219.001": "fin_main", "Material_220.001": "fin_main",
    "Material_221.001": "fin_narrow_dark", "Material_204.001": "fin_narrow_light",
}
# Strip families: height (m) and glass rows per column class, v in metres from the strip bottom.
BODY_V0 = 0.01                 # strip bottom = 1 cm below a 2.72 face bottom
FAMILIES = {
    "body": dict(height=2.74, id=100, profiles={
        "P": [(0.06 + BODY_V0, 2.16 + BODY_V0), (2.21 + BODY_V0, 2.66 + BODY_V0)],     # fixed pane
        "S": [(0.11 + BODY_V0, 2.11 + BODY_V0), (2.21 + BODY_V0, 2.66 + BODY_V0)],     # sash vision
        "R": [(2.21 + BODY_V0, 2.66 + BODY_V0)],                                        # sash frame column
        "D": []}),
    "ring": dict(height=3.5, id=101, base_z=65.40, profiles={"H": [(0.05, 3.45)], "D": []}),
    "super": dict(height=3.5, id=102, profiles={"H": [(0.05, 3.45)], "D": []}),
}
CLASS_NAME = {"D": "frame", "P": "fixed", "S": "sash", "R": "sash_frame", "H": "pane"}
OKS = "Vyatskaya_Vl_47_49_013_Main"
MAT_NAME = f"M_{OKS}_1"
UV_NAME = "UV"
JOB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS_JSON = os.path.join(JOB_DIR, "outputs", "review-v001", "windows", "runs_typed_xy.json")


def hex_rgb(h):
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)], np.float32)


# ---------------------------------------------------------------- geometry: glass runs keyed to the measurements

def world_verts(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(obj.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def glass_faces(obj):
    """Per face: verts, z0, h, the two vertical edges (frozensets of vertex ids) with their xy."""
    V = world_verts(obj)
    out = {}
    for p in obj.data.polygons:
        ids = list(p.vertices)
        P = V[ids]
        z0, z1 = P[:, 2].min(), P[:, 2].max()
        h = z1 - z0
        vert = []
        for k in range(len(ids)):
            a, b = ids[k], ids[(k + 1) % len(ids)]
            if np.linalg.norm(V[a, :2] - V[b, :2]) < 0.005 and abs(V[a, 2] - V[b, 2]) > 0.5 * h:
                vert.append((frozenset((a, b)), (V[a, :2] + V[b, :2]) / 2))
        if h > 0.05 and len(vert) != 2:
            raise RuntimeError(f"{obj.name} face {p.index}: {len(vert)} vertical edges, expected 2")
        out[p.index] = dict(ids=ids, P=P, z0=z0, h=h, edges=vert)
    return out


def chains(F):
    """Faces joined by shared vertical edges -> list of (face list in walk order, is_cycle)."""
    by_edge = defaultdict(list)
    for f, d in F.items():
        for e, _ in d["edges"]:
            by_edge[e].append(f)
    nb = defaultdict(list)
    for e, fs in by_edge.items():
        if len(fs) > 2:
            raise RuntimeError(f"vertical edge shared by {len(fs)} glass faces: {fs}")
        if len(fs) == 2:
            nb[fs[0]].append(fs[1])
            nb[fs[1]].append(fs[0])
    seen, out = set(), []
    for f in sorted(F):
        if f in seen:
            continue
        comp, stack = [], [f]
        while stack:
            g = stack.pop()
            if g in seen:
                continue
            seen.add(g)
            comp.append(g)
            stack.extend(nb[g])
        ends = [g for g in comp if len(nb[g]) < 2]
        start = min(ends) if ends else min(comp)
        order, prev = [start], None
        while True:
            nxt = [g for g in nb[order[-1]] if g != prev and g not in order]
            if not nxt:
                break
            prev = order[-1]
            order.append(nxt[0])
        if len(order) != len(comp):
            raise RuntimeError(f"glass run is not a simple chain: {sorted(comp)[:10]}")
        out.append((order, not ends))
    return out


def lay_out(F, order, cycle, t_az):
    """Faces in run order -> per face (left xy, tangent, width) or None if the direction contradicts t_az."""
    n = len(order)
    res = []
    for i, f in enumerate(order):
        (ea, pa), (eb, pb) = F[f]["edges"]
        if n == 1:
            left, right = (pa, pb) if np.dot(pb - pa, t_az) > 0 else (pb, pa)
        else:
            prev = order[i - 1] if (i > 0 or cycle) else None
            nxt = order[(i + 1) % n] if (i < n - 1 or cycle) else None
            prev_e = {e for e, _ in F[prev]["edges"]} if prev is not None else set()
            next_e = {e for e, _ in F[nxt]["edges"]} if nxt is not None else set()
            if ea in prev_e or eb in next_e:
                left, right = pa, pb
            elif eb in prev_e or ea in next_e:
                left, right = pb, pa
            else:
                raise RuntimeError(f"face {f}: no shared edge with its neighbours")
        w = float(np.linalg.norm(right - left))
        res.append((left, (right - left) / max(w, 1e-9), w))
    if n > 1 and np.dot(res[0][1], t_az) < 0.5:
        return None
    return res


def anchor(lay, fu, L):
    """Element faces (left, t, w) in run order -> measured-run u of each face start, or None.
    Unchanged runs: from the run start. A run whose length changed (cleanup removed a corner sliver and stitched the
    two legs at their plan intersection) has exactly one such corner, at a measured sliver (< 0.07 m): faces before
    it from the run start, faces after it from the run end (both legs keep their outer ends)."""
    c = np.concatenate([[0.0], np.cumsum([w for _, _, w in lay])])
    dL = L - c[-1]
    if abs(dL) < 0.005:
        return list(c[:-1]), None
    corners = [i for i in range(1, len(lay)) if np.dot(lay[i - 1][1], lay[i][1]) < math.cos(math.radians(45))]
    slivers = [(fu[k], fu[k + 1]) for k in range(len(fu) - 1) if fu[k + 1] - fu[k] < 0.07]
    st = [i for i in corners if any(x0 - 0.08 < c[i] < x1 + 0.08 for x0, x1 in slivers)]
    if len(st) != 1:
        return None
    j = st[0]
    return [c[i] if i < j else c[i] + dL for i in range(len(lay))], j


def match_runs(obj, F, measured):
    """Glass elements (faces joined by shared vertical edges; after cleanup often one quad per run) of one object ->
    list of dict(run=primary measured run, runs=all measured runs on it, faces=[(face, m0, left, t, w)], fit).
    Keyed by geometry: object, z range, run length, the run's measured face boundaries (every element vertex must sit
    on one, within 1 cm) and the centroid of the measured face corners predicted on the element (within 6 cm)."""
    elems = []
    for order, cycle in chains(F):
        elems.append(dict(order=order, cycle=cycle, z0=min(F[f]["z0"] for f in order),
                          z1=max(F[f]["z0"] + F[f]["h"] for f in order), claims=[]))
    for a in (a for a in measured if a["obj"] == obj.name):
        az = math.radians(a["az"])
        t_az = np.array([-math.sin(az), math.cos(az)])
        fu, L, xy = np.array(a["face_u"]), a["length"], np.array(a["xy"])
        best = None
        for ei, e in enumerate(elems):
            if not (e["z0"] - 0.015 < a["z0"] and a["z0"] + a["h"] < e["z1"] + 0.015):
                continue
            o = e["order"]
            options = [o, o[::-1]]
            if e["cycle"]:
                options = [q[k:] + q[:k] for q in options for k in range(len(q))]
            for q in options:
                lay = lay_out(F, q, e["cycle"], t_az)
                if lay is None or abs(sum(w for _, _, w in lay) - L) > 0.15:
                    continue
                anc = anchor(lay, fu, L)
                if anc is None:
                    continue
                m, j = anc
                ends = [m[i] for i in range(1, len(lay)) if i != j] + [m[-1] + lay[-1][2]]
                fit = max(float(np.min(np.abs(fu - x))) for x in ends)

                def at(u):
                    i = max(0, min(len(lay) - 1, int(np.searchsorted(m, u, side="right")) - 1))
                    left, t, w = lay[i]
                    return left + t * min(max(u - m[i], 0.0), w)
                cen = np.mean([(at(fu[k]) + at(fu[k + 1])) / 2 for k in range(len(fu) - 1)], axis=0)
                cerr = float(np.linalg.norm(cen - xy))
                if best is None or fit + cerr < best[0]:
                    best = (fit + cerr, fit, cerr, ei, [(f, mi, left, t, w) for f, mi, (left, t, w) in zip(q, m, lay)], j)
        if best is None or best[1] > 0.01 or best[2] > 0.06:
            raise RuntimeError(f"{obj.name}: measured run {a['run']} (z {a['z0']}, {L} m) matches no glass element"
                               + (f" (best fit {best[1]:.3f}, centroid {best[2]:.3f})" if best else ""))
        elems[best[3]]["claims"].append(dict(run=a, fit=best[1], cerr=best[2], faces=best[4], stitched=best[5]))
    out = []
    for e in elems:
        cl = sorted(e["claims"], key=lambda c: c["run"]["z0"])
        if not cl:
            raise RuntimeError(f"{obj.name}: glass element at z {e['z0']:.2f} ({len(e['order'])} faces) has no measured run")
        for c0, c1 in zip(cl, cl[1:]):
            if c1["run"]["z0"] < c0["run"]["z0"] + c0["run"]["h"] - 0.015:
                raise RuntimeError(f"{obj.name}: runs {c0['run']['run']} and {c1['run']['run']} overlap on one element")
        if sum(c["run"]["h"] for c in cl) < e["z1"] - e["z0"] - 0.11:
            raise RuntimeError(f"{obj.name}: element at z {e['z0']:.2f} is only partly covered by measured runs")
        prim = max(cl, key=lambda c: c["run"]["h"])
        out.append(dict(run=prim["run"], runs=[c["run"]["run"] for c in cl], faces=prim["faces"],
                        width_err=max(c["fit"] for c in cl), cerr=max(c["cerr"] for c in cl),
                        stitched=prim["stitched"] is not None))
    return out, set()


# ---------------------------------------------------------------- strips (from the measured panes)

def family_of(a):
    h = a["h"]
    if h < SLIVER_H_M:
        return "sliver"
    if abs(h - 2.72) < HTOL or abs(h - 2.74) < HTOL:
        return "body"
    if abs(h - 3.5) < HTOL:
        return "super"
    if a["obj"] == "TOW02_top_glass" and (abs(h - 2.7) < HTOL or abs(h - 0.7) < HTOL) and \
            a["z0"] > FAMILIES["ring"]["base_z"] - 0.01 and a["z0"] + h < FAMILIES["ring"]["base_z"] + 3.5 + 0.01:
        return "ring"
    raise RuntimeError(f"run {a['run']}: height {h} at z {a['z0']} fits no window family")


def v_offset(a, fam):
    """Strip v of z = z - z0 + offset."""
    if fam == "body":
        return BODY_V0 - (a["h"] - 2.72) / 2      # 2.72 face: +0.01; 2.74 face: 0 (its profile sits 1 cm higher)
    if fam == "ring":
        return a["z0"] - FAMILIES["ring"]["base_z"]
    return 0.0


def check_profile(a, fam):
    """Measured vertical glass intervals of every pane must agree with the family profile within 1.5 cm."""
    off = v_offset(a, fam)
    H = FAMILIES[fam]["height"]
    for p in a["panes"]:
        gz = [(z0 + off, z1 + off) for z0, z1 in p["glass_z"]]
        if fam == "body":
            want = FAMILIES["body"]["profiles"]["S" if p["sash"] else "P"]
        else:
            want = [(max(0.05, off), min(H - 0.05, off + a["h"]))]
        if len(gz) != len(want) or any(abs(x - y) > 0.015 for g, w in zip(gz, want) for x, y in zip(g, w)):
            raise RuntimeError(f"run {a['run']}: pane {p['u0']}-{p['u1']} glass {p['glass_z']} != {fam} profile")


def run_segments(a, fam):
    """Measured run -> [(cls, x0, x1)] over [0, length] in run u (metres).
    body: panes from the fanlight band; a sash pane's vision glass = its measured vision-band glass (sash frame
    0.045-0.065 m per side), SASH_FRAME_M if not measured. ring / super: every fanlight-band glass segment >= 1 cm
    (incl. the 2 cm glass slit inside the 0.21 m double mullions)."""
    if fam != "body":
        glass = [(x0, x1) for c, x0, x1 in a["fan"] if c == "G" and x1 - x0 >= 0.01]
        segs, x = [], 0.0
        for x0, x1 in glass:
            if x0 > x + 1e-6:
                segs.append(["D", x, x0])
            segs.append(["H", x0, x1])
            x = x1
        if a["length"] > x + 1e-6:
            segs.append(["D", x, a["length"]])
        return segs
    segs, x = [], 0.0
    for p in a["panes"]:
        u0, u1 = p["u0"], p["u1"]
        if u0 > x + 1e-6:
            segs.append(["D", x, u0])
        if p["sash"]:
            vg = [(max(x0, u0), min(x1, u1)) for c, x0, x1 in a["vis"] if c == "G" and min(x1, u1) - max(x0, u0) > 0.1]
            s0, s1 = (vg[0][0], vg[-1][1]) if vg else (u0 + SASH_FRAME_M, u1 - SASH_FRAME_M)
            if not (0.02 <= s0 - u0 <= 0.1 and 0.02 <= u1 - s1 <= 0.1):
                s0, s1 = u0 + SASH_FRAME_M, u1 - SASH_FRAME_M
            segs += [["R", u0, s0], ["S", s0, s1], ["R", s1, u1]]
        else:
            segs.append(["P", u0, u1])
        x = u1
    if a["length"] > x + 1e-6:
        segs.append(["D", x, a["length"]])
    return segs


def clip(segs, a, b):
    out = []
    for c, x0, x1 in segs:
        lo, hi = max(x0, a), min(x1, b)
        if hi - lo > 1e-3:
            if out and out[-1][0] == c:
                out[-1][2] = hi
            else:
                out.append([c, lo, hi])
    return out


def match_face(fs, lib):
    """Face segments [(cls, x0, x1)] -> (err, offset) of the best placement on library segments, or None."""
    k, best = len(fs), None
    a, b = fs[0][1], fs[-1][2]
    for s in range(len(lib) - k + 1):
        if any(fs[j][0] != lib[s + j][0] for j in range(k)):
            continue
        if k == 1:
            L0, L1 = lib[s][1], lib[s][2]
            o = (L0 + L1) / 2 - (a + b) / 2
            err = max(0.0, ((b - a) - (L1 - L0)) / 2)
        else:
            d = [lib[s + j][1] - fs[j][1] for j in range(1, k)]
            o = (min(d) + max(d)) / 2
            err = max((max(d) - min(d)) / 2, lib[s][1] - (a + o), (b + o) - lib[s + k - 1][2], 0.0)
        if best is None or err < best[0] - 1e-9:
            best = (err, o)
    return best


def build_library(runs):
    """Greedy plan A2 per family. runs: matched runs with seg / fam. Returns strips and per face (strip, offset, err)."""
    strips, placed = [], {}
    by_fam = defaultdict(list)
    for r in runs:
        by_fam[r["fam"]].append(r)
    for fam in ("body", "ring", "super"):
        rs = by_fam.get(fam, [])
        freq = Counter(r["run"]["type"] for r in rs)
        rs = sorted(rs, key=lambda r: (-freq[r["run"]["type"]], -r["run"]["length"], r["run"]["run"]))
        lib = []
        for r in rs:
            for fi, u0, _, _, w in r["faces"]:
                fsegs = clip(r["seg"], u0, u0 + w)
                hit = min(((m[0], m[1], k) for k, st in enumerate(lib) for m in [match_face(fsegs, st["segs"])] if m),
                          default=None)
                if hit is None or hit[0] > MATCH_TOL_M:
                    segs = [list(s) for s in r["seg"]]
                    if segs[0][0] == "D":
                        segs[0][1] -= STRIP_MARGIN_M
                    else:
                        segs.insert(0, ["D", -STRIP_MARGIN_M, segs[0][1]])
                    if segs[-1][0] == "D":
                        segs[-1][2] += STRIP_MARGIN_M
                    else:
                        segs.append(["D", segs[-1][2], segs[-1][2] + STRIP_MARGIN_M])
                    lib.append(dict(id=f"{fam}_{len(lib):02d}", family=fam, run=r["run"]["run"],
                                    type=r["run"]["type"], segs=segs, x0=segs[0][1], x1=segs[-1][2]))
        # final pass: every face on its best strip of the family
        for r in rs:
            for fi, u0, _, _, w in r["faces"]:
                fsegs = clip(r["seg"], u0, u0 + w)
                hits = [(m[0], k, m[1]) for k, st in enumerate(lib) for m in [match_face(fsegs, st["segs"])] if m]
                if not hits:
                    raise RuntimeError(f"run {r['run']['run']} face {fi}: no strip region matches")
                err, k, o = min(hits)
                placed[(r["obj"], fi)] = (len(strips) + k, o, err)
        strips += lib
    return strips, placed


# ---------------------------------------------------------------- atlas layout and painting

def pieces_for(strips, intervals, p):
    """Split strips longer than the atlas into windows of <= maxlen; every mapped face interval lies whole in one
    window (the next window starts at the first face that does not fit the current one, so windows may overlap)."""
    maxlen = (SIZE - 2 * PAD) / p
    out = []
    for k, st in enumerate(strips):
        ivs = intervals.get(k, [])
        pos = st["x0"]
        while True:
            end = pos + maxlen
            if st["x1"] <= end:
                out.append((k, pos, st["x1"]))
                break
            rest = [x0 for x0, x1 in ivs if x1 > end + 1e-6]
            out.append((k, pos, end))
            if not rest:
                break
            if min(rest) <= pos + 1e-6:
                raise RuntimeError(f"{st['id']}: a face longer than {maxlen:.1f} m")
            pos = min(rest)
    return out


def pack(strips, intervals):
    """Highest px/m whose shelf packing fits one atlas with the swatch row. Returns p, pieces with rects, swatches."""
    p = PX_MAX
    while p > 10:
        pcs = pieces_for(strips, intervals, p)
        items = sorted(((math.ceil(FAMILIES[strips[k]["family"]]["height"] * p), math.ceil((x1 - x0) * p), k, x0, x1)
                        for k, x0, x1 in pcs), key=lambda t: (-t[0], -t[1]))
        shelves, y, placed = [], PAD, []
        for h, w, k, x0, x1 in items:
            for sh in shelves:
                if h <= sh["h"] and sh["x"] + w + PAD <= SIZE:
                    placed.append(dict(strip=k, x0=x0, x1=x1, rect=(sh["x"], sh["y"], w, h)))
                    sh["x"] += w + PAD
                    break
            else:
                shelves.append(dict(h=h, y=y, x=PAD + w + PAD))
                placed.append(dict(strip=k, x0=x0, x1=x1, rect=(PAD, y, w, h)))
                y += h + PAD
        if y + SWATCH_PX + PAD <= SIZE:
            swatches, x = {}, PAD
            for finish, _, _ in SWATCHES:
                swatches[finish] = (x, y, SWATCH_PX, SWATCH_PX)
                x += SWATCH_PX + PAD
            assert x <= SIZE
            return p, placed, swatches
        p -= PX_STEP
    raise RuntimeError("strips do not fit one atlas")


def coverage(st, x0, x1, w, h, p):
    """Glass coverage (0..1) of a strip window [x0, x1] painted into w x h px, row 0 = top."""
    prof = FAMILIES[st["family"]]["profiles"]
    H = FAMILIES[st["family"]]["height"]
    classes = sorted(prof)
    xs = x0 + (np.arange(w * SS) + 0.5) / (SS * p)
    vs = H - (np.arange(h * SS) + 0.5) / (SS * p)
    col = np.full(xs.shape, classes.index("D"))
    for c, a, b in st["segs"]:
        col[(xs >= a) & (xs < b)] = classes.index(c)
    rows = np.zeros((len(classes), vs.size), bool)
    for i, c in enumerate(classes):
        for a, b in prof[c]:
            rows[i] |= (vs >= a) & (vs < b)
    g = rows[col].T                                   # (rows, cols)
    return g.reshape(h, SS, w, SS).mean(axis=(1, 3)).astype(np.float32)


def blit(dst, x, y, tile):
    """Write tile at (x, y) and edge-extend it by EXT px on every side (clipped to the atlas)."""
    t = np.pad(tile, ((EXT, EXT), (EXT, EXT)) + ((0, 0),) * (tile.ndim - 2), mode="edge")
    y0, x0 = y - EXT, x - EXT
    ys, xs = max(0, -y0), max(0, -x0)
    ye, xe = min(t.shape[0], SIZE - y0), min(t.shape[1], SIZE - x0)
    dst[y0 + ys:y0 + ye, x0 + xs:x0 + xe] = t[ys:ye, xs:xe]


def paint(strips, placed, swatches, p):
    """d (sRGB), m, r as float arrays SIZE x SIZE x 4, row 0 = top."""
    frame, glass = hex_rgb(FRAME), hex_rgb(GLASS)
    d = np.zeros((SIZE, SIZE, 3), np.float32)
    d[:] = frame
    cov = np.zeros((SIZE, SIZE), np.float32)
    for pc in placed:
        x, y, w, h = pc["rect"]
        c = coverage(strips[pc["strip"]], pc["x0"], pc["x1"], w, h, p)
        blit(cov, x, y, c)
        blit(d, x, y, frame + (glass - frame) * c[..., None])
    for finish, colour, is_glass in SWATCHES:
        x, y, w, h = swatches[finish]
        blit(d, x, y, np.broadcast_to(hex_rgb(colour), (h, w, 3)).copy())
        blit(cov, x, y, np.full((h, w), 1.0 if is_glass else 0.0, np.float32))
    is_glass = cov >= 0.5
    out = []
    for arr in (d, is_glass[..., None].repeat(3, 2), (~is_glass)[..., None].repeat(3, 2)):
        a = np.ones((SIZE, SIZE, 4), np.float32)
        a[..., :3] = arr
        out.append(a)
    return out


def save_png(arr, path, non_color):
    img = bpy.data.images.new(os.path.basename(path)[:-4], SIZE, SIZE, alpha=False)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    img.pixels.foreach_set(np.ascontiguousarray(arr[::-1]).ravel())  # Blender rows start at the bottom
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    if not os.path.isfile(path):
        raise RuntimeError(f"texture not written: {path}")
    img.filepath = path
    return img


def px_uv(px, py):
    """Atlas pixel coordinates (origin top-left) -> Blender UV."""
    return px / SIZE, 1.0 - py / SIZE


# ---------------------------------------------------------------- non-window parts

def face_frame(mw, verts, normal):
    """Horizontal tangent (left -> right seen from outside) and the face's local (u, z) coordinates."""
    n = (mw.to_3x3() @ normal).normalized()
    t = Vector((-n.y, n.x, 0.0))
    if t.length < 1e-6:                               # horizontal face: project on world XY
        return n, [(v.x, v.y) for v in verts]
    t.normalize()
    return n, [(v.dot(t), v.z) for v in verts]


def finish_of(obj, mat_name, n):
    if mat_name in MATERIAL_FINISH:
        return MATERIAL_FINISH[mat_name]
    if mat_name == FACADE_MATERIAL:
        if n.z > 0.7:
            return "roof"
        return "soffit" if n.z < -0.7 else "wall"
    raise RuntimeError(f"{obj.name}: material {mat_name!r} has no finish (add it to MATERIAL_FINISH)")


# ---------------------------------------------------------------- main

def main(out_dir, runs_json):
    out_dir = os.path.abspath(out_dir)
    with open(runs_json, encoding="utf-8") as f:
        measured = json.load(f)
    measured = measured["runs"] if isinstance(measured, dict) else measured

    # 1. glass runs from the geometry, keyed to the measured runs
    geo, runs, sliver_faces, missing = {}, [], {}, set()
    for name in WINDOW_OBJECTS:
        obj = bpy.data.objects[name]
        F = glass_faces(obj)
        sliver_faces[name] = {f for f, d in F.items() if d["h"] < SLIVER_H_M}
        Fw = {f: d for f, d in F.items() if d["h"] >= SLIVER_H_M}
        mr, miss = match_runs(obj, Fw, [a for a in measured if a["h"] >= SLIVER_H_M])
        missing |= miss
        geo[name] = F
        for r in mr:
            r["obj"] = name
            r["fam"] = family_of(r["run"])
            check_profile(r["run"], r["fam"])
            r["seg"] = run_segments(r["run"], r["fam"])
            r["voff"] = v_offset(r["run"], r["fam"])
            runs.append(r)
    if missing:
        raise RuntimeError(f"measured runs without geometry: {sorted(missing)}")

    # 2. plan A2 library and face placement
    strips, placed = build_library(runs)
    intervals = defaultdict(list)
    for r in runs:
        for fi, u0, _, _, w in r["faces"]:
            k, o, _ = placed[(r["obj"], fi)]
            intervals[k].append((u0 + o, u0 + w + o))
    p, pieces, swatches = pack(strips, intervals)

    # 3. textures and material
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    d, m, r_ = paint(strips, pieces, swatches, p)
    imgs = {c: save_png(a, os.path.join(tex_dir, f"T_{OKS}_{c}_1.png"), c != "d") for c, a in zip("dmr", (d, m, r_))}
    mat = bpy.data.materials.get(MAT_NAME) or bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    for i, (c, socket) in enumerate((("d", "Base Color"), ("m", "Metallic"), ("r", "Roughness"))):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image, node.interpolation, node.location = imgs[c], "Closest" if c != "d" else "Linear", (-400, 300 - 300 * i)
        nt.links.new(node.outputs["Color"], bsdf.inputs[socket])
        if c == "d":
            nt.nodes.active = node

    # 4. UV: window faces on their strip pieces
    piece_of = defaultdict(list)
    for pc in pieces:
        piece_of[pc["strip"]].append(pc)
    win_uv, fmap = {}, []
    errs = defaultdict(list)
    for r in runs:
        a, fam = r["run"], r["fam"]
        H = FAMILIES[fam]["height"]
        for fi, u0, left, t, w in r["faces"]:
            k, o, err = placed[(r["obj"], fi)]
            x0, x1 = u0 + o, u0 + w + o
            pc = next((q for q in piece_of[k] if q["x0"] - 1e-4 <= x0 and x1 <= q["x1"] + 1e-4), None)
            if pc is None:
                raise RuntimeError(f"{r['obj']} face {fi}: [{x0:.3f}, {x1:.3f}] on {strips[k]['id']} crosses a cut")
            rx, ry, _, _ = pc["rect"]
            F = geo[r["obj"]][fi]
            uvs = []
            for P in F["P"]:
                x = u0 + float(np.dot(P[:2] - left, t)) + o
                v = P[2] - a["z0"] + r["voff"]
                uvs.append(px_uv(rx + (x - pc["x0"]) * p, ry + (H - v) * p))
            win_uv[(r["obj"], fi)] = (uvs, fam)
            errs[strips[k]["id"]].append(err)
            fmap.append(dict(obj=r["obj"], face=fi, run=a["run"], type=a["type"], strip=strips[k]["id"],
                             x0=round(x0, 4), x1=round(x1, 4), err_m=round(err, 4)))

    # 5. every TOW02 object: UV, finish attribute, one material
    stats, finish_ids = {}, {f: i for i, (f, _, _) in enumerate(SWATCHES)}
    finish_ids.update({f"window_{fam}": FAMILIES[fam]["id"] for fam in FAMILIES})
    for obj in sorted((o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("TOW02_")), key=lambda o: o.name):
        me, mw = obj.data, obj.matrix_world
        mats = [s.name if s else None for s in me.materials]
        uv = me.uv_layers.get(UV_NAME) or me.uv_layers.new(name=UV_NAME)
        me.uv_layers.active = uv
        fin_attr = me.attributes.get("tow02_finish") or me.attributes.new("tow02_finish", "INT", "FACE")
        for p_ in me.polygons:
            key = (obj.name, p_.index)
            if key in win_uv:
                uvs, fam = win_uv[key]
                kind = f"window_{fam}"
                for li, uvv in zip(p_.loop_indices, uvs):
                    uv.data[li].uv = uvv
            else:
                if obj.name in WINDOW_OBJECTS:
                    if p_.index not in sliver_faces[obj.name]:
                        raise RuntimeError(f"{obj.name} face {p_.index}: glass face in no measured run")
                    kind = "glass_frame"
                else:
                    if not mats or mats[p_.material_index] is None:
                        raise RuntimeError(f"{obj.name} face {p_.index}: no material")
                    kind = None
                verts = [mw @ me.vertices[i].co for i in p_.vertices]
                n, uz = face_frame(mw, verts, p_.normal)
                kind = kind or finish_of(obj, mats[p_.material_index], n)
                us, zs = [a for a, _ in uz], [b for _, b in uz]
                u0, z0 = min(us), min(zs)
                span = max(max(us) - u0, max(zs) - z0, 1e-6)   # keep the aspect, fit the longer side
                x, y, sw, sh = swatches[kind]
                rx, ry, rw, rh = x + SWATCH_INSET_PX, y + SWATCH_INSET_PX, sw - 2 * SWATCH_INSET_PX, sh - 2 * SWATCH_INSET_PX
                for li, (a, b) in zip(p_.loop_indices, uz):
                    uv.data[li].uv = px_uv(rx + (a - u0) / span * rw, ry + rh - (b - z0) / span * rh)
            fin_attr.data[p_.index].value = finish_ids[kind]
            stats.setdefault(obj.name, Counter())[kind] += 1
        me.materials.clear()
        me.materials.append(mat)

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "tow02_tex.blend"), copy=False)

    # 6. layout report
    def seq(st):
        return [[CLASS_NAME[c], round(x1 - x0, 3)] for c, x0, x1 in st["segs"]]
    all_err = [e for v in errs.values() for e in v]
    layout = dict(
        size=SIZE, px_per_m=p, pad_px=PAD, edge_extend_px=EXT, supersampling=SS, match_tol_m=MATCH_TOL_M,
        source=os.path.relpath(runs_json, JOB_DIR).replace("\\", "/"),
        families={k: dict(height_m=v["height"], finish_id=v["id"], base_z=v.get("base_z"),
                          glass_rows_m={CLASS_NAME[c]: rows for c, rows in v["profiles"].items()})
                  for k, v in FAMILIES.items()},
        strips=[dict(id=st["id"], family=st["family"], source_run=st["run"], source_type=st["type"],
                     length_m=round(st["x1"] - st["x0"], 3), sequence=seq(st),
                     pieces=[dict(x0=round(pc["x0"], 3), x1=round(pc["x1"], 3), rect=pc["rect"]) for pc in pieces
                             if pc["strip"] == k],
                     faces=len(errs[st["id"]]), max_err_m=round(max(errs[st["id"]], default=0), 4))
                for k, st in enumerate(strips)],
        swatches={k: dict(rect=swatches[k], colour=c, glass=g) for k, c, g in SWATCHES},
        finish_ids=finish_ids, material=MAT_NAME, uv=UV_NAME,
        mapping=dict(window_faces=len(all_err), max_err_m=round(max(all_err), 4),
                     faces_err_over_5mm=sum(e > 0.005 for e in all_err),
                     runs=len(runs), runs_per_family=dict(Counter(r["fam"] for r in runs)),
                     strips_per_family=dict(Counter(st["family"] for st in strips)),
                     elements=len(runs), stitched_corner_elements=sum(r["stitched"] for r in runs),
                     max_element_vertex_vs_measured_boundary_m=round(max(r["width_err"] for r in runs), 4),
                     max_centroid_err_m=round(max(r["cerr"] for r in runs), 4),
                     sliver_faces={k: len(v) for k, v in sliver_faces.items()}),
        faces={k: dict(v) for k, v in stats.items()})
    with open(os.path.join(out_dir, "atlas_layout.json"), "w", encoding="utf-8") as f:
        json.dump(layout, f, indent=1)
    with open(os.path.join(out_dir, "face_mapping.json"), "w", encoding="utf-8") as f:
        json.dump(fmap, f)
    print("TEXTURE_DONE " + json.dumps(dict(px_per_m=p, strips=len(strips), mapping=layout["mapping"])))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    runs_path = argv[argv.index("--runs") + 1] if "--runs" in argv else RUNS_JSON
    main(argv[0], runs_path)
