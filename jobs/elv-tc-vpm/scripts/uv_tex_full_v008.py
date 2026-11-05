"""v008 (rework after the Max review of v004, item 1: texture joints must meet everywhere) = uv_tex_full_v007.py +
- CAUSE of the shifted joints (v004): the joint phase was chosen PER FACE — from the FBX joints near that face, or, on a
  face without FBX joints (e.g. the upper row under the parapet, rows above the FBX joint objects), «kept clear» at
  min(u) - 3 cm, i.e. an arbitrary phase per face. Neighbouring faces of one facade therefore had different lattice
  phases and the joint lines broke at every face border (checker joint_continuity_v008.py: v004 work FBX 423 unmatched
  crossings on 95 edges, 31 facade planes with several phases). Horizontal faces took u along the NEAREST outline per
  face, so neighbouring deck / soffit faces could have rotated lattices.
- FIX: (1) horizontal faces: one frame per connected coplanar component of a tile (frame of its largest face);
  (2) harmonisation per full tile and lattice axis: constraints «the joint lines meet» on every shared edge (crossing
  axes with equal rate along the edge, and parallel axes of coplanar neighbours) and «one lattice per facade plane»
  (vertical faces of one plane), solved as an affine union-find mod P_tex (a_B = s * a_A + c); per component the phase
  is the one that matches the most FBX panel joints (12 mm), so the joints still sit on the FBX panels wherever the
  FBX layout is regular; conflicting constraints are dropped and counted;
  (3) ID01 sandwich horizontal joints (rows are not periodic): the FBX row set is shared by the faces connected over
  vertical edges, so a row continues across face borders instead of stopping at the face without its own row object.
Faces are still shifted by whole texture periods only; 683 px/m unchanged.
v007 header follows.
v007 copy (stem SM_Elevatornaya_Vl_1_A_001, tex_stage text); otherwise identical to uv_tex_full.py.
elv-tc-vpm WHOLE building: VPM UV (one channel 'UV', UDIM) + materials on the build-v004 geometry (unchanged).
Same method and parameters as the accepted pilot (uv_tex_pilot.py, tex-v001); changes for the whole building:
- horizontal faces take u along the NEAREST of the outlines U / L / W (light_paths.py), not only U;
- ID18 zones: P13 base flashing and P25 new plinth flashing -> 5024 (continuation of the accepted base flashing),
  P12 caps by the U zone (pilot rule), P41 joint faces at the pilot cap ends -> 1001, any other ID18 -> 7021;
- tiles with 'h_joints' (ID01 sandwich): per-face v phase from the FBX row boundaries (cassette_joints_v002.json
  'sandwich_h'); a face without a row joint is kept clear of horizontal joints;
- full tiles with a 'z_joint' but no joint source (ID15 gates) get the global z phase on vertical faces;
- the material wires ERM R into the emission (Emission Color = Diffuse, Strength = R x EMIT_K) for the Blender preview.

v008: blender -b --factory-startup --disable-autoexec <build-v008 blend> --python uv_tex_full_v008.py -- layout|apply ... (same arguments)
Pass 1:  blender -b build-v004/elv_full_v004.blend --python uv_tex_full.py -- layout <spec> <joints> <layout.json>
Pass 2:  ... -- apply <spec> <joints> <layout.json> <tex_dir> <out.blend> <uv_qa.json>

Rules (docs/domain/uv-textures.md, materials.md; precedent jobs/KPP1/scripts/vpm_uv.py):
- one UV layer 'UV'; one UDIM tile per working texture ID (spec), tiles renumbered 1001.. without gaps after empty
  tiles are dropped; MainGlass UVs in 1001, no maps;
- full maps: rigid planar projection in world metres (u = viewer's right, v = up; horizontal faces: u along the
  nearest outline tangent), so density = 4096 / S everywhere; faces are shifted by whole texture periods only (phase
  kept); joint phase per face from the FBX panel joints (cassette_joints_v001.json), z phase from the FBX rows; the
  texture phase phi inside the tile is chosen over all faces of the tile so every face fits with the margin;
- placeholders (density-exempt): islands scaled into the tile with a 5 % margin, stacked (identical colour);
- winding: u x v follows the face normal (no mirrored islands), checked;
- Main gets ONE material M_Elevatornaya_1A_Main_1 (reg p.30 §4.3-4.4: < 100 UDIM maps); the working ID survives as the
  face attribute 'mat_id' (1-35 reading scheme), the tile as 'udim'.
"""
import bpy, bmesh, sys, os, json, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "KPP1", "scripts"))
from pilot_outlines import U, uA, uB  # noqa: E402
from light_paths import POLYS  # noqa: E402
EMIT_K = 6.0

argv = sys.argv[sys.argv.index("--") + 1:]
MODE, SPEC_P, JOINTS_P, LAYOUT_P = argv[:4]
SPEC = json.load(open(SPEC_P, encoding="utf-8"))
JOINTS = json.load(open(JOINTS_P, encoding="utf-8"))
S, PAD, NF, NP = SPEC["S"], SPEC["pad_m"], SPEC["size_full"], SPEC["size_placeholder"]
TILES = {t["key"]: dict(t) for t in SPEC["tiles"]}
STEM = "SM_Elevatornaya_Vl_1_A_001"   # v007: customer stem (user 2026-11-05)
ob = bpy.data.objects[STEM + "_Main"]
og = bpy.data.objects[STEM + "_MainGlass"]
PART_IDS = json.loads(ob["part_ids"])
SLOT_IDS = [int(m.name[2:4]) for m in ob.data.materials]  # ID01_... -> 1 (build: ID = slot index + 1)
assert SLOT_IDS == list(range(1, len(SLOT_IDS) + 1)), SLOT_IDS


def tile_key(wid, part, c):
    if wid == 18:
        if part in ("P13_BaseFlashing", "P25_Plinth_Flashing_New"):
            return "ID18_5024"          # Gate 1: base flashing RAL 5024 (continued by the new plinth flashing)
        if part == "P41_Joints":
            return "ID18_1001" if (c.y < -50.48 or c.y > 3.0) else "ID18_7021"   # J5 / J8 = pilot wood-zone cap ends
        if part == "P12_ParapetCaps":
            u = U.project((c.x, c.y))
            return "ID18_5024" if uA - 1e-6 <= u <= uB + 1e-6 else "ID18_1001"
        return "ID18_7021"
    return "ID%02d" % wid


def frame(f):
    n = f.normal
    if abs(n.z) < 0.7:
        r = Vector((-n.y, n.x, 0.0))
    else:
        c = f.calc_center_median()
        best = None
        for P in POLYS.values():
            u = P.project((c.x, c.y))
            b = P.base(u)
            d = math.hypot(b[0] - c.x, b[1] - c.y)
            if best is None or d < best[0]:
                best = (d, P.t[P.seg(u)])
        t = best[1]
        r = Vector((t[0], t[1], 0.0))
        r = r - n * r.dot(n)
    r.normalize()
    up = n.cross(r)
    up.normalize()
    return r, up


def signed_area(pts):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])) / 2


# ------------------------------------------------------------------ FBX joints per source
JS = {}
for k in ("wood_cassette", "metal_cassette", "sandwich"):
    JS[k] = [(Vector((j[0], j[1], 0.0)), j[2], j[3], Vector((j[4], j[5], 0.0))) for j in JOINTS[k]["joints_xyz"]]
HJ = [(Vector((h[0], h[1], 0.0)), Vector((h[2], h[3], 0.0)), h[5] - h[4], h[6]) for h in JOINTS.get("sandwich_h", [])]


def h_joints(f, r, umin, umax, vmin, vmax):
    """FBX row-boundary z values inside this vertical face (same plane within 0.6 m, overlapping along r)"""
    n = Vector((f.normal.x, f.normal.y, 0.0))
    n.normalize()
    p0 = f.verts[0].co
    out = set()
    for co, jn, ln, z in HJ:
        if abs(jn.dot(n)) < 0.95 or not (vmin + 0.01 < z < vmax - 0.01):
            continue
        if abs((co - Vector((p0.x, p0.y, 0.0))).dot(n)) > 0.6:
            continue
        c = co.dot(r)
        if min(umax, c + ln / 2) - max(umin, c - ln / 2) > 0.05:
            out.add(round(z, 3))
    return sorted(out)


def joint_phase(f, src, P, r, umin, umax, vmin, vmax):
    """lattice phase (mod P) of the FBX joints on this face; returns (phase, inside_total, inside_matched)"""
    n = Vector((f.normal.x, f.normal.y, 0.0))
    if n.length < 0.5:
        return None, 0, 0, []
    n.normalize()
    p0 = f.verts[0].co
    near = abs if src == "sandwich" else (lambda x: x)
    dmax = 0.6 if src == "sandwich" else 0.1
    cand = []
    for co, z0, z1, jn in JS[src]:
        if near(jn.dot(n)) < 0.95 or z1 < vmin + 0.01 or z0 > vmax - 0.01:
            continue
        if abs((co - Vector((p0.x, p0.y, 0.0))).dot(n)) > dmax:
            continue
        cand.append(co.dot(r))
    cand = sorted(set(round(c, 4) for c in cand))
    inside = [c for c in cand if umin + 0.005 < c < umax - 0.005]
    pool = inside or [c for c in cand if umin - P < c < umax + P]
    if not pool:
        return None, 0, 0, []
    res = lambda c, a: abs(((c - a + P / 2) % P) - P / 2)  # noqa: E731
    mid = (umin + umax) / 2
    best = max(pool, key=lambda a: (sum(2 if c in inside else 1 for c in pool if res(c, a) < 0.012), -abs(a - mid)))
    ph = best % P
    return ph, len(inside), sum(1 for c in inside if res(c, ph) < 0.012), inside


# ------------------------------------------------------------------ pass: collect islands
bm = bmesh.new()
bm.from_mesh(ob.data)
lay = bm.faces.layers.int["part_idx"]
bm.faces.ensure_lookup_table()
faces = []
jstat = {}
FR = {}
for f in bm.faces:
    wid = SLOT_IDS[f.material_index]
    part = PART_IDS[f[lay]]
    key = tile_key(wid, part, f.calc_center_median())
    FR[f.index] = (key, wid, part, frame(f))

# v008 (1): horizontal faces of a full tile — one frame per connected coplanar component (largest face's frame)
HSTAT = {"components": 0, "faces_reframed": 0}
seen = set()
for f in bm.faces:
    key = FR[f.index][0]
    if f.index in seen or abs(f.normal.z) < 0.7 or TILES[key]["kind"] != "full" or not TILES[key].get("joint_mm"):
        continue                      # only tiles with drawn joints (no-joint roof / soffit keep the v007 frames)
    comp, stack = [], [f]
    seen.add(f.index)
    while stack:
        g = stack.pop()
        comp.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen and FR[h.index][0] == key and h.normal.dot(g.normal) > 0.9999:
                    seen.add(h.index)
                    stack.append(h)
    big = max(comp, key=lambda g: g.calc_area())
    r0 = FR[big.index][3][0]
    HSTAT["components"] += 1

    def _long_edge(g):
        e = max(g.edges, key=lambda e: e.calc_length())
        d = e.verts[1].co - e.verts[0].co
        return d.normalized(), e.calc_length(), g.calc_area() / max(e.calc_length(), 1e-6)
    # thin tops (wall / parapet crowns, every face < 0.35 m wide): u along each face's long edge, so the vertical
    # joints of the wall below run on across the crown; otherwise the component frame
    thin = all(_long_edge(g)[2] < 0.35 for g in comp)
    if thin:
        HSTAT["thin_components"] = HSTAT.get("thin_components", 0) + 1
    for g in comp:
        if g is big and not thin:
            continue
        if thin:
            d = _long_edge(g)[0]
            r0 = d if d.dot(FR[g.index][3][0]) >= 0 else -d
        r = r0 - g.normal * r0.dot(g.normal)
        r.normalize()
        up = g.normal.cross(r)
        up.normalize()
        if (FR[g.index][3][0] - r).length > 1e-6:
            HSTAT["faces_reframed"] += 1
        FR[g.index] = FR[g.index][:3] + ((r, up),)

for f in bm.faces:
    key, wid, part, (r, up) = FR[f.index]
    t = TILES[key]
    uv = [(l.vert.co.dot(r), l.vert.co.dot(up)) for l in f.loops]
    rec = {"f": f, "fi": f.index, "key": key, "uv": uv, "au": 0.0, "av": 0.0, "wid": wid, "part": part,
           "ax": (r, up), "vote": [None, None], "inside": [], "hz": []}
    if t["kind"] == "full" and t.get("joints") and abs(f.normal.z) < 0.7:
        us, vs = [p[0] for p in uv], [p[1] for p in uv]
        ph, ni, nm, ins = joint_phase(f, t["joints"], t["P_lat"][0], r, min(us), max(us), min(vs), max(vs))
        js = jstat.setdefault(key, {"faces": 0, "faces_no_joint": 0, "fbx_joints_inside": 0, "matched_12mm": 0})
        js["faces"] += 1
        if ph is None:
            js["faces_no_joint"] += 1
            P0 = t["P_lat"][0]
            if max(us) - min(us) < P0 - 0.06:   # v007 rule, overridden by the harmonisation when the face has neighbours
                rec["au"] = (min(us) - 0.03) % P0
                js["no_joint_kept_clear"] = js.get("no_joint_kept_clear", 0) + 1
            c = f.calc_center_median()
            js.setdefault("no_joint_faces", []).append([part, [round(c.x, 2), round(c.y, 2), round(c.z, 2)],
                                                        round(max(us) - min(us), 2), round(max(vs) - min(vs), 2)])
        else:
            rec["au"] = ph
            rec["vote"][0] = (ph, max(1, ni))
            rec["inside"] = ins
            js["fbx_joints_inside"] += ni
            js["matched_12mm"] += nm
        rec["av"] = t["z_joint"] % t["P_lat"][1]
        rec["vote"][1] = (rec["av"], 1.0)
        if t.get("h_joints"):
            vs = [p[1] for p in uv]
            rec["hz"] = h_joints(f, r, min(us), max(us), min(vs), max(vs))
            rec["av"] = (rec["hz"][0] if rec["hz"] else (min(vs) - 0.03)) % t["P_lat"][1]
    elif t["kind"] == "full" and "z_joint" in t and abs(f.normal.z) < 0.7:
        rec["av"] = t["z_joint"] % t["P_lat"][1]
        rec["vote"][1] = (rec["av"], 1.0)
    faces.append(rec)
BYF = {r["fi"]: r for r in faces}


# ------------------------------------------------------------------ v008 (2)(3): harmonise the lattice phases
class AUF:
    """affine union-find mod P over faces: a_x = s * a_parent + c"""

    def __init__(self, P):
        self.P, self.par = P, {}

    def find(self, x):
        chain = []
        while True:
            p = self.par.setdefault(x, (x, 1, 0.0))
            if p[0] == x:
                break
            chain.append((x, p))
            x = p[0]
        root, s, c = x, 1, 0.0
        for y, p in reversed(chain):       # nearest-to-root first: compose a_y = p.s * a_parent + p.c
            s, c = p[1] * s, (p[1] * c + p[2]) % self.P
            self.par[y] = (root, s, c)
        if not chain:
            return root, 1, 0.0
        return root, s, c

    def union(self, a, b, s, c):
        """constraint a_b = s * a_a + c (mod P); returns False on a conflicting cycle (constraint dropped)"""
        ra, sa, ca = self.find(a)
        rb, sb, cb = self.find(b)
        if ra == rb:
            d = (cb - (s * ca + c)) % self.P
            return s * sa == sb and min(d, self.P - d) < 2e-4
        self.par[rb] = (ra, sb * s * sa, (sb * (s * ca + c - cb)) % self.P)
        return True


def _wrap(x, P):
    return abs(((x + P / 2) % P) - P / 2)


CONS = {}          # (key, axis) -> [(A, B, s, c, kind)]
for e in bm.edges:
    lf = [BYF[g.index] for g in e.link_faces if TILES[BYF[g.index]["key"]]["kind"] == "full"]
    if len(lf) < 2:
        continue
    v0, v1 = e.verts
    if (v1.co - v0.co).length < 1e-4:
        continue
    ed = (v1.co - v0.co).normalized()
    p0 = v0.co
    for i in range(len(lf)):
        for j in range(i + 1, len(lf)):
            A, B = lf[i], lf[j]
            if A["key"] != B["key"]:
                continue
            cop = A["f"].normal.dot(B["f"].normal) > 0.9999
            for k in (0, 1):
                xa, xb = A["ax"][k], B["ax"][k]
                ca, cb = xa.dot(ed), xb.dot(ed)
                if abs(ca) > 0.2 and abs(cb) > 0.2 and abs(abs(ca) - abs(cb)) < 0.01:
                    s, kind = (1 if ca * cb > 0 else -1), "edge_cross"
                elif cop and abs(xa.dot(xb)) > 0.9999:
                    s, kind = (1 if xa.dot(xb) > 0 else -1), "edge_parallel"
                else:
                    continue
                CONS.setdefault((A["key"], k), []).append((A["fi"], B["fi"], s, p0.dot(xb) - s * p0.dot(xa), kind))
# one lattice per facade plane: vertical faces of one tile, greedy plane clusters around the largest face
# (normal within 1e-4 rad, offset within 2 cm); constraint at the midpoint of the two centres (error < 2.5 mm at 50 m)
PLANES = {}
for r in sorted(faces, key=lambda r: -r["f"].calc_area()):
    f = r["f"]
    if TILES[r["key"]]["kind"] != "full" or abs(f.normal.z) > 0.01:
        continue
    n = Vector((f.normal.x, f.normal.y, 0.0)).normalized()
    d = f.verts[0].co.dot(n)
    for (key, n0, d0), lst in PLANES.items():
        if key == r["key"] and n.dot(n0) > math.cos(1e-4) and abs(d - d0) < 0.02:
            lst.append(r)
            break
    else:
        PLANES[(r["key"], n.freeze(), d)] = [r]
for (key, _, _), lst in PLANES.items():
    ref = lst[0]
    cA = ref["f"].calc_center_median()
    for r in lst[1:]:
        for k in (0, 1):
            xa, xb = ref["ax"][k], r["ax"][k]
            if xa.cross(xb).length > 1e-4 or xa.dot(xb) < 0:
                continue
            p0 = (cA + r["f"].calc_center_median()) / 2
            CONS.setdefault((key, k), []).append((ref["fi"], r["fi"], 1, p0.dot(xb) - p0.dot(xa), "plane"))

HARM = {}
for (key, k), cons in sorted(CONS.items()):
    t = TILES[key]
    P, Pl = t["P_tex"][k], t["P_lat"][k]
    st = HARM.setdefault("%s_%s" % (key, "uv"[k]), {"constraints": {}, "conflicts": {}, "components": 0,
                                                   "faces_changed": 0})
    rows_mode = k == 1 and bool(t.get("h_joints"))
    uf = AUF(P)
    for kind in ("edge_cross", "edge_parallel", "plane"):
        for A, B, s, c, kd in cons:
            if kd != kind:
                continue
            if kd == "plane" and os.environ.get("V008_PLANES", "1") == "0":
                continue
            if rows_mode and kd == "plane":
                continue                      # rows: only faces connected over edges share their row set
            st["constraints"][kd] = st["constraints"].get(kd, 0) + 1
            if not uf.union(A, B, s, c % P):
                st["conflicts"][kd] = st["conflicts"].get(kd, 0) + 1
    comps = {}
    for x in list(uf.par):
        rt, s, c = uf.find(x)
        comps.setdefault(rt, []).append((x, s, c))
    st["components"] = len(comps)
    for rt, mem in comps.items():
        if rows_mode:
            rows = sorted({z for x, _, _ in mem for z in BYF[x]["hz"]})
            for x, _, _ in mem:
                r = BYF[x]
                if abs(r["f"].normal.z) >= 0.7:
                    continue
                vs = [p[1] for p in r["uv"]]
                inside = [z for z in rows if min(vs) + 0.01 < z < max(vs) - 0.01]
                new = (inside[0] if inside else (min(vs) - 0.03)) % P
                if inside and not r["hz"]:
                    st["faces_changed"] += 1
                if len(inside) > 1:
                    st.setdefault("faces_multi_row", []).append([r["part"], inside])
                r["av"] = new
            continue
        votes = [(x, s, c, BYF[x]["vote"][k]) for x, s, c in mem if BYF[x]["vote"][k] is not None]
        if votes:
            cands = sorted({round((s * (v[0] - c)) % Pl, 4) for x, s, c, v in votes})
            best = max(cands, key=lambda R: (sum(v[1] for x, s, c, v in votes if _wrap(s * R + c - v[0], Pl) < 0.012), -R))
        else:
            big = max(mem, key=lambda m: BYF[m[0]]["f"].calc_area())
            cur = BYF[big[0]]["au" if k == 0 else "av"]
            best = (big[1] * (cur - big[2])) % P
        for x, s, c in mem:
            r = BYF[x]
            new = (s * best + c) % P
            old = r["au" if k == 0 else "av"]
            if _wrap(new - old, Pl) > 1e-4:
                st["faces_changed"] += 1
            r["au" if k == 0 else "av"] = new
    if "faces_multi_row" in st:
        st["faces_multi_row_n"] = len(st["faces_multi_row"])
        st["faces_multi_row"] = st["faces_multi_row"][:20]
# FBX panel joints still matched after the harmonisation (12 mm)
for key, js in jstat.items():
    P0 = TILES[key]["P_lat"][0]
    js["matched_12mm_after_harmonisation"] = sum(
        1 for r in faces if r["key"] == key for c in r["inside"] if _wrap(c - r["au"], P0) < 0.012)
HARM["horizontal_frames"] = HSTAT
for k, v in jstat.items():
    if "no_joint_faces" in v:
        v["no_joint_faces"] = len(v["no_joint_faces"])

# drop empty tiles, renumber 1001.. in spec order
used = {r["key"] for r in faces}
order = [t["key"] for t in SPEC["tiles"] if t["key"] in used]
for i, k in enumerate(order):
    TILES[k]["udim"] = 1001 + i
dropped = [t["key"] for t in SPEC["tiles"] if t["key"] not in used]


def best_phase(spans, Pt):
    """phi in [0, Pt) minimising (overflow count, max end) for spans (xmin - a, length)"""
    best = None
    steps = max(1, int(round(Pt / 0.005)))
    for k in range(steps):
        phi = k * Pt / steps
        ends = []
        for x0, ln in spans:
            s0 = ((x0 + phi - PAD) % Pt) + PAD
            ends.append(s0 + ln)
        over = sum(1 for e in ends if e > S - PAD + 1e-9)
        sc = (over, max(ends))
        if best is None or sc < best[0]:
            best = (sc, phi)
    return best[1], best[0]


layout = {"address": SPEC["address"], "slot": SPEC["slot"], "S": S, "pad_m": PAD, "tiles": {}, "dropped_tiles": dropped,
          "joint_phase_stats": jstat, "harmonisation_v008": HARM, "zone_rule_ID18": "P13 base flashing -> 5024 (Gate 1); P12 caps: U arc length in "
          "[uA, uB] (curtain-wall zone) -> 5024, else wood zone -> 1001; any other ID18 part -> 7021"}
for k in order:
    t = TILES[k]
    fs = [r for r in faces if r["key"] == k]
    ent = {"udim": t["udim"], "kind": t["kind"], "ids": t["ids"], "faces": len(fs), "ral": t.get("ral")}
    if t["kind"] == "full":
        Pt = t["P_tex"]
        phis = []
        for ax in (0, 1):
            spans = [(min(p[ax] for p in r["uv"]) - (r["au"] if ax == 0 else r["av"]),
                      max(p[ax] for p in r["uv"]) - min(p[ax] for p in r["uv"])) for r in fs]
            phi, sc = best_phase(spans, Pt[ax])
            phis.append(round(phi, 4))
            ent["overflow_axis%d" % ax] = sc[0]
            ent["max_end_axis%d_m" % ax] = round(sc[1], 4)
        ent["phi"] = phis
        ent["px_per_m"] = round(NF / S, 2)
    layout["tiles"][k] = ent

# ------------------------------------------------------------------ UV write (both modes compute it for the QA)
uvl = bm.loops.layers.uv.new("UV")
qa = {k: {"udim": TILES[k]["udim"], "faces": 0, "out_of_tile": 0, "fallback_no_phase": 0, "flipped": 0, "zero_uv": 0,
          "min_margin_px": 1e9, "density_min": None, "density_max": None} for k in order}
ext = {}
for r in faces:
    if TILES[r["key"]]["kind"] == "placeholder":
        us, vs = [p[0] for p in r["uv"]], [p[1] for p in r["uv"]]
        ext[r["key"]] = max(ext.get(r["key"], 0.0), max(us) - min(us), max(vs) - min(vs))
for r in faces:
    k, t, f = r["key"], TILES[r["key"]], r["f"]
    off = Vector((((t["udim"] - 1001) % 10), ((t["udim"] - 1001) // 10)))
    q = qa[k]
    q["faces"] += 1
    us, vs = [p[0] for p in r["uv"]], [p[1] for p in r["uv"]]
    if t["kind"] == "full":
        Pt, phi = t["P_tex"], layout["tiles"][k]["phi"]
        loc = []
        sh = []
        for ax, a in ((0, r["au"]), (1, r["av"])):
            x0 = min(p[ax] for p in r["uv"]) - a + phi[ax]
            n = math.floor((x0 - PAD) / Pt[ax])
            sh.append(-a + phi[ax] - n * Pt[ax])
        loc = [((p[0] + sh[0]) / S, (p[1] + sh[1]) / S) for p in r["uv"]]
        if max(max(p) for p in loc) > 1 - PAD / S + 1e-9:   # fallback: keep scale, drop the phase
            q["fallback_no_phase"] += 1
            loc = [((p[0] - min(us) + PAD) / S, (p[1] - min(vs) + PAD) / S) for p in r["uv"]]
        size = NF
    else:
        Sp = ext[k] / 0.9 if ext[k] > 0 else 1.0
        loc = [((p[0] - min(us)) / Sp + 0.05, (p[1] - min(vs)) / Sp + 0.05) for p in r["uv"]]
        size = NP
    lo = min(min(p) for p in loc)
    hi = max(max(p) for p in loc)
    q["min_margin_px"] = min(q["min_margin_px"], round(min(lo, 1 - hi) * size, 1))
    if lo < 0 or hi > 1:
        q["out_of_tile"] += 1
    sa = signed_area(loc)
    if sa <= 0:
        q["flipped" if sa < 0 else "zero_uv"] += 1
    for l, p in zip(f.loops, loc):
        l[uvl].uv = (p[0] + off.x, p[1] + off.y)
    if t["kind"] == "full" and f.calc_area() > 1e-4:
        d = math.sqrt(abs(sa) * size * size / f.calc_area())
        q["density_min"] = round(d, 2) if q["density_min"] is None else min(q["density_min"], round(d, 2))
        q["density_max"] = round(d, 2) if q["density_max"] is None else max(q["density_max"], round(d, 2))
layout["uv_qa"] = qa

# glass: tile 1001 of its own UV channel, scaled in with a margin, overlaps allowed (reg p.31 §2.2)
bg = bmesh.new()
bg.from_mesh(og.data)
gl = bg.loops.layers.uv.new("UV")
gp, gext = [], 0.0
for f in bg.faces:
    n = f.normal
    r = Vector((-n.y, n.x, 0.0)) if abs(n.z) < 0.7 else Vector((1, 0, 0))
    r.normalize()
    up = n.cross(r)
    up.normalize()
    uv = [(l.vert.co.dot(r), l.vert.co.dot(up)) for l in f.loops]
    us, vs = [p[0] for p in uv], [p[1] for p in uv]
    gext = max(gext, max(us) - min(us), max(vs) - min(vs))
    gp.append((f, uv))
gq = {"udim": 1001, "faces": 0, "out_of_tile": 0, "flipped": 0}
for f, uv in gp:
    us, vs = [p[0] for p in uv], [p[1] for p in uv]
    loc = [((p[0] - min(us)) / (gext / 0.9) + 0.05, (p[1] - min(vs)) / (gext / 0.9) + 0.05) for p in uv]
    gq["faces"] += 1
    gq["out_of_tile"] += any(c < 0 or c > 1 for p in loc for c in p)
    gq["flipped"] += signed_area(loc) <= 0
    for l, p in zip(f.loops, loc):
        l[gl].uv = p
layout["glass_uv_qa"] = gq

if MODE == "layout":
    if os.path.exists(LAYOUT_P):
        raise SystemExit("output exists: " + LAYOUT_P)
    json.dump(layout, open(LAYOUT_P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("LAYOUT", json.dumps({k: (v["udim"], v.get("phi"), v.get("overflow_axis0"), v.get("overflow_axis1"))
                                for k, v in layout["tiles"].items()}))
    print("QA", json.dumps(qa))
    print("JOINTS", json.dumps(jstat), "DROPPED", dropped)
    print("HARM", json.dumps(HARM))
    raise SystemExit(0)

# ------------------------------------------------------------------ apply: materials, attributes, save new blend
TEX_DIR, OUT, QA_P = argv[4:7]
for p in (OUT, QA_P):
    if os.path.exists(p):
        raise SystemExit("output exists: " + p)
prev = json.load(open(LAYOUT_P, encoding="utf-8"))
assert {k: v["udim"] for k, v in prev["tiles"].items()} == {k: v["udim"] for k, v in layout["tiles"].items()}
assert all(prev["tiles"][k].get("phi") == layout["tiles"][k].get("phi") for k in order), "layout differs from pass 1"
import vpm_uv  # noqa: E402  (jobs/KPP1/scripts: main_material / glass_material, KPP1 precedent)

mid = bm.faces.layers.int.new("mat_id")
udl = bm.faces.layers.int.new("udim")
bm.faces.ensure_lookup_table()
for r in faces:
    fb = bm.faces[r["fi"]]
    fb[mid] = r["wid"]
    fb[udl] = TILES[r["key"]]["udim"]
    fb.material_index = 0
me = ob.data
for u in list(me.uv_layers):
    me.uv_layers.remove(u)
bm.to_mesh(me)
bm.free()
me.materials.clear()
mat = vpm_uv.main_material(bpy, {"address": SPEC["address"]}, TEX_DIR)
# emission preview: ERM R (glow strength) x EMIT_K, colour = Diffuse (colour in Diffuse, strength in ERM R)
_nt = mat.node_tree
_bsdf = _nt.nodes["Principled BSDF"]
_dif = _bsdf.inputs["Base Color"].links[0].from_node
_sep = _bsdf.inputs["Roughness"].links[0].from_node          # Separate Color of the ERM map
_mul = _nt.nodes.new("ShaderNodeMath")
_mul.operation = "MULTIPLY"
_mul.inputs[1].default_value = EMIT_K
_nt.links.new(_sep.outputs["Red"], _mul.inputs[0])
_nt.links.new(_mul.outputs["Value"], _bsdf.inputs["Emission Strength"])
_nt.links.new(_dif.outputs["Color"], _bsdf.inputs["Emission Color"])
me.materials.append(mat)
gme = og.data
for u in list(gme.uv_layers):
    gme.uv_layers.remove(u)
bg.to_mesh(gme)
bg.free()
gme.materials.clear()
gme.materials.append(vpm_uv.glass_material(bpy, {"address": SPEC["address"]}))
for m in list(bpy.data.materials):
    if m.users == 0:
        bpy.data.materials.remove(m)
for o in (ob, og):
    o.data.uv_layers.active = o.data.uv_layers["UV"]
    o.data.uv_layers["UV"].active_render = True
ob["working_id_to_udim"] = json.dumps({k: v["udim"] for k, v in layout["tiles"].items()})
ob["tex_stage"] = "jobs/elv-tc-vpm/scripts/uv_tex_full_v008.py tex-v006 (spec tex_spec_v005.json, joints harmonised) on build-v008 geometry"
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
rep = {"blend": os.path.abspath(OUT), "layout": layout, "main_materials": [m.name for m in me.materials],
       "glass_materials": [m.name for m in gme.materials],
       "uv_layers": {o.name: [u.name for u in o.data.uv_layers] for o in (ob, og)},
       "images": sorted(i.filepath for i in bpy.data.images if i.source == "TILED")}
json.dump(rep, open(QA_P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("SAVED", OUT, rep["main_materials"], rep["glass_materials"], rep["uv_layers"])
