"""elv-tc-vpm: texture JOINT CONTINUITY checker (rework after the Max review of v004, item 1).

Reads a mesh with the VPM UDIM channel 'UV' (a textured master .blend or a delivered / work FBX) and measures, over the
whole Main object, whether the texture joint lines meet across face borders:

1. shared-edge crossings: for every mesh edge shared by two faces of the same full UDIM tile that has joints
   (spec 'joint_mm'), the joint lines of each face that cross the edge are located along it (lattice x - phi = k * P_lat
   per joint axis, phi = layout tile phase); a crossing without a partner on the other face within TOL is UNMATCHED
   (shifted joint = 2 unmatched, joint ending at the border = 1). Crossings within END_SKIP of an edge end are ignored;
2. coplanar parallel phase: for coplanar neighbours with parallel lattice axes, the lattice offset of the joint lines
   that run parallel to the edge when BOTH faces show such a line (wrong panel width at the border); not for the ID01
   rows (FBX row heights, not a lattice) — reported separately;
3. per facade plane: vertical faces of a joint tile grouped by plane (normal 0.05 deg, offset 1 cm); number of
   distinct u lattice phases (world metres along the plane, TOL) and the face-area share off the dominant phase;
4. texel density of every full-tile face (px/m from UV vs 3D area).

blender -b --factory-startup --disable-autoexec --python-exit-code 1 --python joint_continuity_v008.py -- \
    <mesh.blend|mesh.fbx> <tex_spec.json> <uv_layout.json> <out.json> [label]
"""
import json
import math
import os
import sys
from collections import defaultdict

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, SPEC_P, LAY_P, OUT = argv[:4]
LABEL = argv[4] if len(argv) > 4 else os.path.basename(SRC)
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
TOL, END_SKIP = 0.0015, 0.003
SPEC = json.load(open(SPEC_P, encoding="utf-8"))
LAY = json.load(open(LAY_P, encoding="utf-8"))
S, NF = SPEC["S"], SPEC["size_full"]
FULL = {}
for t in SPEC["tiles"]:
    if t["kind"] != "full" or t["key"] not in LAY["tiles"]:
        continue
    lt = LAY["tiles"][t["key"]]
    FULL[lt["udim"]] = {"key": t["key"], "Pl": t["P_lat"], "phi": lt["phi"], "joints": bool(t.get("joint_mm")),
                        "axes": t.get("joint_axes", "uv"), "rows": bool(t.get("h_joints"))}

if SRC.lower().endswith(".fbx"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=SRC)
else:
    bpy.ops.wm.open_mainfile(filepath=SRC)
ob = next(o for o in bpy.data.objects if o.type == "MESH" and o.name.endswith("_Main"))
bm = bmesh.new()
bm.from_mesh(ob.data)
bm.transform(ob.matrix_world)
bm.normal_update()
uvl = bm.loops.layers.uv["UV"]
bm.faces.ensure_lookup_table()


def _load_udimtile():
    """The one shared UDIM function (#1337): adapters/max/agr_tools/udimtile_core.py of this checkout."""
    import importlib.util
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    path = os.path.join(root, "adapters", "max", "agr_tools", "udimtile_core.py")
    spec = importlib.util.spec_from_file_location("agr_tools_udimtile_core_joint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UDIMTILE = _load_udimtile()


def udim_of(f):
    """(UDIM, (u_tile, v_tile)) of the face centroid. A centroid off the UDIM grid (u outside [0, 10), v < 0, NaN)
    stops the checker naming the face (#1337; before it gave a wrong number and the face was skipped)."""
    uvs = [(l[uvl].uv.x, l[uvl].uv.y) for l in f.loops]
    try:
        tile = UDIMTILE.face_tile(uvs, strict=False)
    except UDIMTILE.UdimDomainError as exc:
        raise SystemExit("face %d: %s" % (f.index, exc))
    return tile, UDIMTILE.tile_origin(tile)


FT = {}
for f in bm.faces:
    ud, off = udim_of(f)
    if ud in FULL:
        FT[f.index] = (ud, off)


def m_at(f, vert):
    """tile metres of the face's UV at that vertex"""
    off = FT[f.index][1]
    for l in f.loops:
        if l.vert is vert:
            return ((l[uvl].uv.x - off[0]) * S, (l[uvl].uv.y - off[1]) * S)
    raise KeyError


def crossings(f, v0, v1, L):
    """positions (m from v0) along the edge where a joint line of face f crosses it"""
    t = FULL[FT[f.index][0]]
    a, b = m_at(f, v0), m_at(f, v1)
    out = []
    for k in (0, 1):
        if "uv"[k] not in t["axes"]:
            continue
        d = b[k] - a[k]
        if abs(d) < 0.2 * L:
            continue
        P, ph = t["Pl"][k], t["phi"][k]
        x0, x1 = a[k] - ph, b[k] - ph
        lo, hi = min(x0, x1), max(x0, x1)
        for n in range(math.ceil(lo / P), math.floor(hi / P) + 1):
            s = (n * P - x0) / d * L
            if END_SKIP < s < L - END_SKIP:
                out.append(s)
    return out


def has_line(f, k, t):
    """a joint line of axis k lies inside the face (visible)"""
    off = FT[f.index][1]
    xs = [(l[uvl].uv[k] - off[k]) * S - t["phi"][k] for l in f.loops]
    P = t["Pl"][k]
    return math.floor((max(xs) - END_SKIP) / P) >= math.ceil((min(xs) + END_SKIP) / P)


def wrap(x, P):
    return abs(((x + P / 2) % P) - P / 2)


tiles = defaultdict(lambda: {"edges_checked": 0, "edges_len_m": 0.0, "edges_with_unmatched": 0,
                             "edges_unmatched_len_m": 0.0, "crossings": 0, "unmatched_crossings": 0,
                             "shift_max_mm": 0.0, "coplanar_pairs": 0, "coplanar_parallel_mismatch": 0,
                             "coplanar_parallel_max_mm": 0.0})
worst = []
for e in bm.edges:
    lf = [f for f in e.link_faces if f.index in FT]
    if len(lf) < 2:
        continue
    v0, v1 = e.verts
    L = e.calc_length()
    if L < 0.01:
        continue
    for i in range(len(lf)):
        for j in range(i + 1, len(lf)):
            A, B = lf[i], lf[j]
            if FT[A.index][0] != FT[B.index][0]:
                continue
            t = FULL[FT[A.index][0]]
            if not t["joints"]:
                continue
            q = tiles[t["key"]]
            q["edges_checked"] += 1
            q["edges_len_m"] += L
            ca, cb = crossings(A, v0, v1, L), crossings(B, v0, v1, L)
            q["crossings"] += len(ca) + len(cb)
            un = [s for s in ca if not any(abs(s - x) < TOL for x in cb)] + \
                 [s for s in cb if not any(abs(s - x) < TOL for x in ca)]
            if un:
                q["edges_with_unmatched"] += 1
                q["edges_unmatched_len_m"] += L
                q["unmatched_crossings"] += len(un)
                sh = 0.0
                for s in ca:
                    if cb:
                        d = min(abs(s - x) for x in cb)
                        if d >= TOL:
                            sh = max(sh, d)
                q["shift_max_mm"] = max(q["shift_max_mm"], round(sh * 1000, 1))
                mid = (v0.co + v1.co) / 2
                worst.append({"tile": t["key"], "mid": [round(c, 3) for c in mid], "edge_len_m": round(L, 3),
                              "unmatched": len(un), "shift_mm": round(sh * 1000, 1),
                              "normals": [[round(c, 3) for c in A.normal], [round(c, 3) for c in B.normal]]})
            # coplanar neighbours: lattice lines parallel to the edge must keep the panel width
            if A.normal.dot(B.normal) > 0.9999:
                q["coplanar_pairs"] += 1
                a, b = m_at(A, v0), m_at(B, v0)
                a1, b1 = m_at(A, v1), m_at(B, v1)
                for k in (0, 1):
                    if "uv"[k] not in t["axes"]:
                        continue
                    if abs(a1[k] - a[k]) >= 0.2 * L:
                        continue          # crossing axis: counted above
                    if k == 1 and t["rows"]:
                        continue          # ID01 rows are the FBX row heights, not a lattice
                    d = wrap(a[k] - b[k], t["Pl"][k])
                    if d >= TOL and has_line(A, k, t) and has_line(B, k, t):
                        q["coplanar_parallel_mismatch"] += 1
                        q["coplanar_parallel_max_mm"] = max(q["coplanar_parallel_max_mm"], round(d * 1000, 1))

# per facade plane: distinct u lattice phases (vertical faces)
planes = defaultdict(list)
dens = defaultdict(lambda: [1e9, 0.0])
for f in bm.faces:
    if f.index not in FT:
        continue
    t = FULL[FT[f.index][0]]
    area = f.calc_area()
    if area > 1e-4:
        uvs = [((l[uvl].uv.x) * NF, (l[uvl].uv.y) * NF) for l in f.loops]
        sa = abs(sum(p[0] * q2[1] - q2[0] * p[1] for p, q2 in zip(uvs, uvs[1:] + uvs[:1]))) / 2
        d = math.sqrt(sa / area)
        dd = dens[t["key"]]
        dd[0], dd[1] = min(dd[0], d), max(dd[1], d)
    if not t["joints"] or "u" not in t["axes"] or abs(f.normal.z) > 0.1 or area < 1e-4:
        continue
    n = Vector((f.normal.x, f.normal.y, 0.0)).normalized()
    r = Vector((-n.y, n.x, 0.0))
    ang = round(math.degrees(math.atan2(n.y, n.x)) / 0.05) * 0.05
    off = round(f.verts[0].co.dot(n) / 0.01) * 0.01
    l0 = f.loops[0]
    mu = (l0[uvl].uv.x - FT[f.index][1][0]) * S - t["phi"][0]
    # world position along r of the lattice line through this face: co.r - mu (mod P)
    sgn = 1.0
    l1 = f.loops[1]
    dm = (l1[uvl].uv.x - l0[uvl].uv.x) * S
    dw = (l1.vert.co - l0.vert.co).dot(r)
    if abs(dw) > 1e-4:
        sgn = 1.0 if dm * dw > 0 else -1.0
    ph = (l0.vert.co.dot(r) - sgn * mu) % t["Pl"][0]
    planes[(t["key"], ang, off)].append((ph, area, sgn))
pl_rep = {}
for (key, ang, off), lst in planes.items():
    P = FULL[[u for u, x in FULL.items() if x["key"] == key][0]]["Pl"][0]
    groups = []
    for ph, a, sg in sorted(lst):
        for g in groups:
            if wrap(ph - g[0], P) < TOL and g[2] == sg:
                g[1] += a
                break
        else:
            groups.append([ph, a, sg])
    tot = sum(g[1] for g in groups)
    dom = max(g[1] for g in groups)
    r = pl_rep.setdefault(key, {"planes": 0, "planes_multi_phase": 0, "area_m2": 0.0, "area_off_dominant_m2": 0.0,
                                "worst": []})
    r["planes"] += 1
    r["area_m2"] += tot
    if len(groups) > 1:
        r["planes_multi_phase"] += 1
        r["area_off_dominant_m2"] += tot - dom
        r["worst"].append({"normal_deg": ang, "offset_m": off, "phases": len(groups), "area_m2": round(tot, 2),
                           "off_dominant_m2": round(tot - dom, 2)})
for r in pl_rep.values():
    r["area_m2"] = round(r["area_m2"], 1)
    r["area_off_dominant_m2"] = round(r["area_off_dominant_m2"], 2)
    r["worst"] = sorted(r["worst"], key=lambda w: -w["off_dominant_m2"])[:10]

tot = {k: sum(q[k] for q in tiles.values()) for k in ("edges_checked", "edges_with_unmatched", "crossings",
                                                        "unmatched_crossings", "coplanar_parallel_mismatch")}
tot["edges_unmatched_len_m"] = round(sum(q["edges_unmatched_len_m"] for q in tiles.values()), 2)
tot["planes_multi_phase"] = sum(r["planes_multi_phase"] for r in pl_rep.values())
tot["area_off_dominant_m2"] = round(sum(r["area_off_dominant_m2"] for r in pl_rep.values()), 2)
for q in tiles.values():
    q["edges_len_m"] = round(q["edges_len_m"], 2)
    q["edges_unmatched_len_m"] = round(q["edges_unmatched_len_m"], 2)
rep = {"label": LABEL, "source": os.path.abspath(SRC), "object": ob.name, "tol_mm": TOL * 1000,
       "end_skip_mm": END_SKIP * 1000, "totals": tot, "per_tile_edges": dict(tiles), "per_tile_planes": pl_rep,
       "texel_px_per_m": {k: [round(v[0], 2), round(v[1], 2)] for k, v in dens.items()},
       "worst_edges": sorted(worst, key=lambda w: (-w["unmatched"], -w["shift_mm"]))[:40]}
json.dump(rep, open(OUT, "w", encoding="utf-8"), indent=1)
print("JOINT_CONTINUITY", LABEL, json.dumps(tot))
