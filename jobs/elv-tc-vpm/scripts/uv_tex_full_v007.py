"""v007 copy (stem SM_Elevatornaya_Vl_1_A_001, tex_stage text); otherwise identical to uv_tex_full.py.
elv-tc-vpm WHOLE building: VPM UV (one channel 'UV', UDIM) + materials on the build-v004 geometry (unchanged).
Same method and parameters as the accepted pilot (uv_tex_pilot.py, tex-v001); changes for the whole building:
- horizontal faces take u along the NEAREST of the outlines U / L / W (light_paths.py), not only U;
- ID18 zones: P13 base flashing and P25 new plinth flashing -> 5024 (continuation of the accepted base flashing),
  P12 caps by the U zone (pilot rule), P41 joint faces at the pilot cap ends -> 1001, any other ID18 -> 7021;
- tiles with 'h_joints' (ID01 sandwich): per-face v phase from the FBX row boundaries (cassette_joints_v002.json
  'sandwich_h'); a face without a row joint is kept clear of horizontal joints;
- full tiles with a 'z_joint' but no joint source (ID15 gates) get the global z phase on vertical faces;
- the material wires ERM R into the emission (Emission Color = Diffuse, Strength = R x EMIT_K) for the Blender preview.

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
        return None, 0, 0
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
        return None, 0, 0
    res = lambda c, a: abs(((c - a + P / 2) % P) - P / 2)  # noqa: E731
    mid = (umin + umax) / 2
    best = max(pool, key=lambda a: (sum(2 if c in inside else 1 for c in pool if res(c, a) < 0.012), -abs(a - mid)))
    ph = best % P
    return ph, len(inside), sum(1 for c in inside if res(c, ph) < 0.012)


# ------------------------------------------------------------------ pass: collect islands
bm = bmesh.new()
bm.from_mesh(ob.data)
lay = bm.faces.layers.int["part_idx"]
faces = []
jstat = {}
for f in bm.faces:
    wid = SLOT_IDS[f.material_index]
    part = PART_IDS[f[lay]]
    key = tile_key(wid, part, f.calc_center_median())
    t = TILES[key]
    r, up = frame(f)
    uv = [(l.vert.co.dot(r), l.vert.co.dot(up)) for l in f.loops]
    rec = {"f": f, "fi": f.index, "key": key, "uv": uv, "au": 0.0, "av": 0.0, "wid": wid, "part": part}
    if t["kind"] == "full" and t.get("joints") and abs(f.normal.z) < 0.7:
        us, vs = [p[0] for p in uv], [p[1] for p in uv]
        ph, ni, nm = joint_phase(f, t["joints"], t["P_lat"][0], r, min(us), max(us), min(vs), max(vs))
        js = jstat.setdefault(key, {"faces": 0, "faces_no_joint": 0, "fbx_joints_inside": 0, "matched_12mm": 0})
        js["faces"] += 1
        if ph is None:
            js["faces_no_joint"] += 1
            P0 = t["P_lat"][0]
            if max(us) - min(us) < P0 - 0.06:   # no FBX joint on this narrow face: keep texture joints off it too
                rec["au"] = (min(us) - 0.03) % P0
                js["no_joint_kept_clear"] = js.get("no_joint_kept_clear", 0) + 1
            c = f.calc_center_median()
            js.setdefault("no_joint_faces", []).append([part, [round(c.x, 2), round(c.y, 2), round(c.z, 2)],
                                                        round(max(us) - min(us), 2), round(max(vs) - min(vs), 2)])
        else:
            rec["au"] = ph
            js["fbx_joints_inside"] += ni
            js["matched_12mm"] += nm
        rec["av"] = t["z_joint"] % t["P_lat"][1]
        if t.get("h_joints"):
            vs = [p[1] for p in uv]
            hz = h_joints(f, r, min(us), max(us), min(vs), max(vs))
            hs = jstat.setdefault(key + "_h", {"faces_with_row_joint": 0, "faces_clear": 0, "faces_multi": [],
                                               "faces_too_tall": 0})
            P1 = t["P_lat"][1]
            if hz:
                rec["av"] = hz[0] % P1
                hs["faces_with_row_joint"] += 1
                if len(hz) > 1:
                    hs["faces_multi"].append([part, hz])
            else:
                rec["av"] = (min(vs) - 0.03) % P1
                hs["faces_clear"] += 1
                if max(vs) - min(vs) > P1 - 0.06:
                    hs["faces_too_tall"] += 1
    elif t["kind"] == "full" and "z_joint" in t and abs(f.normal.z) < 0.7:
        rec["av"] = t["z_joint"] % t["P_lat"][1]
    faces.append(rec)

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
          "joint_phase_stats": jstat, "zone_rule_ID18": "P13 base flashing -> 5024 (Gate 1); P12 caps: U arc length in "
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
ob["tex_stage"] = "jobs/elv-tc-vpm/scripts/uv_tex_full_v007.py tex-v004 (spec tex_spec_v003.json) on build-v007 geometry"
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
rep = {"blend": os.path.abspath(OUT), "layout": layout, "main_materials": [m.name for m in me.materials],
       "glass_materials": [m.name for m in gme.materials],
       "uv_layers": {o.name: [u.name for u in o.data.uv_layers] for o in (ob, og)},
       "images": sorted(i.filepath for i in bpy.data.images if i.source == "TILED")}
json.dump(rep, open(QA_P, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("SAVED", OUT, rep["main_materials"], rep["glass_materials"], rep["uv_layers"])
