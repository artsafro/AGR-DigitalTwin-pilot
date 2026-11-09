"""elv-tc-vpm v006 = build_full_v004.py with every attachment STANDING OFF its receiving surface by G = 6 mm instead of
the 10 mm constructive embeds (V004 self-intersections, reg p.29 §3.11: <= 100 per mesh at 0.002 m). G > 2 mm (V004
tolerance and xView vertices) and > 5 mm (xView faces) for caps parallel to the receiving face; 6 mm = the agreed
overlap shift of D174. Open ends that only touch a surface still count in V004 when a triangle edge of that surface
passes under them, so contact is replaced by the gap everywhere. Changes (all <= 1 cm unless stated):
- roof boxes / cups / curbs / skylight walls / screens / railing posts: bottom Z_ROOF - 0.01 -> Z_ROOF + G; stair and
  pit glazing bottoms Z_PIT - 0.01 -> Z_PIT + G; curb A starts G off the west parapet; the shaft at the pit wall
  stops G before it and gets its east face (was open, 21 cm hole above the pit wall top);
- railings: posts end G under the top rail; rail ends G off the screens / walls;
- new lamellas, canopies, downpipes, Arktos: G off the facade / canopy soffit / flashing top; canopies and Arktos
  closed at the back;
- fire ladders: rungs end G short of the stringers, brackets run from G off the wall to G short of the stringer;
- dock shelters: 1 cm INSIDE the gate opening on each side (v004: 3 cm outside, through the plinth) = 4 cm narrower
  per side, bottoms G above the sill, backs G off the facade;
- pilot (accepted) P18 canopy and P19 lamellas rebuilt in place with the same outer dimensions: back G off the
  metal base and, below the flashing top, G in front of the flashing (L profile, no longer through the plinth);
  P06 / P07 frame tops G under the soffit, P07 frame bottoms G over the niche plinth.
v004 header follows.

elv-tc-vpm: build the WHOLE building VPM geometry (v004) = build_full_v003.py + (1) the 3 single doors placed from
the library types ELV-18 / ELV-19 / ELV-20 (In-1H 900 / 1100 / 1100 tall), (2) facade light housings from
parts/lighting_layout_v001.json (lights_geom.py, part P42_Lights; housings ID27, glow faces ID28-ID33).

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b --factory-startup --python build_full_v004.py -- <out.blend> <lights.json>
v003 header kept below for the unchanged parts.

Inputs: outputs/build-v001/elv_pilot_IA_v001.blend (accepted pilot geometry, read only, appended);
  parts/elv_full_parts_v001.json; library/windows/window_types.json (ELV-01..13); measurements from the clean reference
  (outputs/ref-v002/ref_objects_full_v001.json, ref_sections_full_v001.json; scripts inv_query.py, sec_lines.py,
  roof_clusters.py) and booklet sheet 19 (fire ladders, added north door). All numbers below: metres, FBX world.
Outputs: SM_Elevatornaya_1A_Main (slots ID01..ID27, ID = slot index + 1, face attribute part_idx) and
  SM_Elevatornaya_1A_MainGlass. No UV for the new parts (texture stage follows).
Pilot handling: pilot faces imported 1:1 (vertices welded on a 0.1 mm grid); removed only the 11 end caps of plinth /
  base flashing at the two joints (x 41.88 south, x 59.43 north) that the new plinth continues; joint faces added
  (P41_Joints). T-junctions healed over the whole mesh (vertices inserted into pilot edges at the joints).
"""
import bpy, bmesh, sys, os, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pilot_geom import Poly, Cell, relief, splits, box, heal_t  # noqa: E402
from full_geom import MB4, wall, hrect, hgrid, obox, lin  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
LIGHTS_OUT = os.path.abspath(argv[1])
ADD_OUT = os.path.abspath(argv[2])            # v007: capsules + cover strips report
for _p in (OUT, LIGHTS_OUT, ADD_OUT):
    if os.path.exists(_p):
        raise SystemExit("output exists: " + _p)
JOB = os.path.abspath(os.path.join(HERE, ".."))
PILOT = os.path.join(JOB, "outputs", "build-v001", "elv_pilot_IA_v001.blend")
PARTS = json.load(open(os.path.join(JOB, "parts", "elv_full_parts_v002.json"), encoding="utf-8"))
LAYOUT = json.load(open(os.path.join(JOB, "parts", "lighting_layout_v001.json"), encoding="utf-8"))
PART_IDS = [p["id"] for p in PARTS["parts"]]
STEM = "SM_Elevatornaya_1A"                 # pilot objects (build-v001) are read under the old stem
STEM_OUT = "SM_Elevatornaya_Vl_1_A_001"      # v007: customer stem (user 2026-11-05)
PART_IDS += ["P43_InteriorCapsules", "P44_CoverStrips"]
TYPES = {t["id"]: t for t in json.load(open(os.path.join(JOB, "..", "..", "library", "windows", "window_types.json"),
                                            encoding="utf-8"))["types"]}

SLOTS = {1: "ID01_Sandwich_7021", 2: "ID02_MetalCassette_7021", 3: "ID03_WoodCassette_1001", 4: "ID04_Plinth_7021",
         5: "ID05_TPAnnexPaint_7021", 6: "ID06_Reveal_7021", 7: "ID07_Reveal_1001", 8: "ID08_unused",
         9: "ID09_unused", 10: "ID10_unused", 11: "ID11_WindowW72_7021", 12: "ID12_FrameF50_7021",
         13: "ID13_Stemalit_5024", 14: "ID14_MetalDoor_7021", 15: "ID15_Gate_7040", 16: "ID16_SignFrame_7021",
         17: "ID17_Ribs_1001", 18: "ID18_Flashing_Zone", 19: "ID19_Canopy_1001", 20: "ID20_Metal_7021",
         21: "ID21_Roof", 22: "ID22_RoofStructures_7021", 23: "ID23_TerraceDeck", 24: "ID24_unused",
         25: "ID25_unused", 26: "ID26_DockShelter_9005", 27: "ID27_LightHousing_7021",
         28: "ID28_Glow_Purple", 29: "ID29_Glow_2700K", 30: "ID30_Glow_2000K", 31: "ID31_Glow_4000K",
         32: "ID32_Glow_RGBwarm", 33: "ID33_Glow_3000K", 34: "ID34_InteriorCapsule_Dark"}
COL = {1: "#2F3234", 2: "#2F3234", 3: "#C2B078", 4: "#2F3234", 5: "#2F3234", 6: "#2F3234", 7: "#C2B078",
       11: "#2F3234", 12: "#2F3234", 13: "#5D9B9B", 14: "#2F3234", 15: "#9DA1AA", 16: "#2F3234", 17: "#C2B078",
       18: "#6E7F80", 19: "#C2B078", 20: "#2F3234", 21: "#8C8C88", 22: "#45494B", 23: "#7A6F63", 26: "#0A0A0A",
       27: "#2F3234", 28: "#CD06BD", 29: "#FFA957", 30: "#FF890E", 31: "#FFD1A3", 32: "#FFF4BE", 33: "#FFB46B",
       34: "#1E1E1E"}

main, glass = MB4(), MB4()
Z_DROP, Z_TOP, Z_CAP, Z_ROOF, Z_PIT = -1.0, 13.92, 14.04, 12.45, 11.46
Z_T1, Z_T2 = 15.42, 16.22
T_PAR, CAP_OUT = 0.40, 0.05
G = 0.006                     # stand-off of every attachment from its receiving surface (see header)
PILOT_REBUILT = ("P18_SouthCanopy", "P19_SouthLamellas")
# (moving part, receiving part, plane z, shift): vertices of the moving part on that plane that are not vertices of
# the receiving part (frame protrusions ending on the soffit / niche plinth) move by the shift
PILOT_SHIFT = [("P06_CW_Lower", "P04_Soffit_Canopy", 4.70, -G), ("P07_EntranceNiche", "P04_Soffit_Canopy", 4.70, -G),
               ("P07_EntranceNiche", "P03_Plinth", 0.22, G)]
PILOT_LOG = {"faces_dropped_rebuilt": 0, "verts_shifted": 0, "p19_x": [], "door25_leaf_faces_dropped": 0}


def _k(q):
    return (round(q[0], 4), round(q[1], 4), round(q[2], 4))


# ================================================================= 1. pilot (accepted, build-v001) -> MB
def import_pilot():
    with bpy.data.libraries.load(PILOT, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(STEM)]
    removed = []
    pverts = {}
    for ob in dst.objects:
        if ob.name.endswith("_Main"):
            ids = json.loads(ob["part_ids"])
            att = ob.data.attributes.get("part_idx")
            for p in ob.data.polygons:
                s = pverts.setdefault(ids[att.data[p.index].value], set())
                s.update(_k(tuple(ob.data.vertices[i].co)) for i in p.vertices)
    p19x = sorted({round(k[0], 3) for k in pverts.get("P19_SouthLamellas", ())})
    PILOT_LOG["p19_x"] = [(a, b) for a, b in zip(p19x, p19x[1:]) if abs(b - a - 0.05) < 1e-3]
    shifted = set()
    for ob in dst.objects:
        mb = main if ob.name.endswith("_Main") else glass
        ids = json.loads(ob["part_ids"])
        me = ob.data
        att = me.attributes.get("part_idx")
        for p in me.polygons:
            pts = [tuple(me.vertices[i].co) for i in p.vertices]
            n = p.normal
            part = ids[att.data[p.index].value]
            if mb is main and part in PILOT_REBUILT:
                PILOT_LOG["faces_dropped_rebuilt"] += 1
                continue
            # v007: leaf plate of the pilot door No 25 (ELV-08, x 59.74..61.54, plate y 2.94) is rebuilt as ELV-21
            if mb is main and part == "P17_MetalDoors_N" and n.y > 0.9 and all(
                    abs(q[1] - 2.94) < 1e-3 and 59.74 - 1e-3 <= q[0] <= 61.54 + 1e-3 for q in pts):
                PILOT_LOG["door25_leaf_faces_dropped"] += 1
                continue
            if mb is main:
                for mv, rc, zp, dz in PILOT_SHIFT:
                    if part != mv:
                        continue
                    new = []
                    for q in pts:
                        if abs(q[2] - zp) < 1e-4 and _k(q) not in pverts.get(rc, ()):
                            shifted.add(_k(q))
                            q = (q[0], q[1], zp + dz)
                        new.append(q)
                    pts = new
            # joint end caps of plinth / base flashing (continued by the new plinth): x 41.88 S and x 59.43 N
            if mb is main and n.x < -0.9 and (
                    (all(abs(q[0] - 41.88) < 2e-3 and -50.70 < q[1] < -50.60 for q in pts) and max(q[2] for q in pts) < 0.41) or
                    (all(abs(q[0] - 59.43) < 2e-3 and 3.13 < q[1] < 3.23 for q in pts) and max(q[2] for q in pts) < 0.41)):
                removed.append([[round(c, 3) for c in q] for q in pts])
                continue
            mb.face(pts, p.material_index + 1 if mb is main else 1, ids[att.data[p.index].value])
        bpy.data.objects.remove(ob)
    PILOT_LOG["verts_shifted"] = len(shifted)
    return removed


def lbox(x0, x1, yf, yl, yu, zb, zs, zt, mat, part, top=True):
    """L-profile fin along x (outward = -y): front yf < yl (back below zs, in front of the flashing) < yu (back above
    zs, off the facade); bottom zb, step zs, top zt; back face above zs open. Quads only, no T-vertices."""
    def q(ya, yb, za, zb_, x, nrm):
        main.face([(x, ya, za), (x, yb, za), (x, yb, zb_), (x, ya, zb_)], mat, part, nrm)
    for x, nx in ((x0, -1), (x1, 1)):
        q(yf, yl, zb, zs, x, (nx, 0, 0))
        q(yf, yl, zs, zt, x, (nx, 0, 0))
        q(yl, yu, zs, zt, x, (nx, 0, 0))
    for za, zb_ in ((zb, zs), (zs, zt)):
        main.face([(x0, yf, za), (x1, yf, za), (x1, yf, zb_), (x0, yf, zb_)], mat, part, (0, -1, 0))
    main.face([(x0, yf, zb), (x1, yf, zb), (x1, yl, zb), (x0, yl, zb)], mat, part, (0, 0, -1))
    main.face([(x0, yl, zb), (x1, yl, zb), (x1, yl, zs), (x0, yl, zs)], mat, part, (0, 1, 0))
    main.face([(x0, yl, zs), (x1, yl, zs), (x1, yu, zs), (x0, yu, zs)], mat, part, (0, 0, -1))
    if top:
        for ya, yb in ((yf, yl), (yl, yu)):
            main.face([(x0, ya, zt), (x1, ya, zt), (x1, yb, zt), (x0, yb, zt)], mat, part, (0, 0, 1))


REMOVED = import_pilot()
assert len(REMOVED) == 11, len(REMOVED)   # 5 south + 6 north end caps
assert len(PILOT_LOG["p19_x"]) == 28, PILOT_LOG["p19_x"]
assert PILOT_LOG["door25_leaf_faces_dropped"] >= 1, PILOT_LOG
# v007: pilot door No 25 = library ELV-21 (ELV-08 + vision panel, booklet sheet 19); plate y 2.94, glass y 2.925 (as the
# pilot ELV-09 door); outside = +y, so the left leaf seen from outside is at +x: pane x from X1 - x1 to X1 - x0
_X0, _X1, _YP, _YG, _ZT = 59.74, 61.54, 2.94, 2.925, 2.05
_px0, _pz0, _px1, _pz1 = TYPES["ELV-21"]["panes_m"][0]
_ga, _gb = _X1 - _px1, _X1 - _px0
_P17 = "P17_MetalDoors_N"
for _q in ([(_X0, _YP, 0.0), (_X1, _YP, 0.0), (_X1, _YP, _pz0), (_X0, _YP, _pz0)],
           [(_X0, _YP, _pz1), (_X1, _YP, _pz1), (_X1, _YP, _ZT), (_X0, _YP, _ZT)],
           [(_X0, _YP, _pz0), (_ga, _YP, _pz0), (_ga, _YP, _pz1), (_X0, _YP, _pz1)],
           [(_gb, _YP, _pz0), (_X1, _YP, _pz0), (_X1, _YP, _pz1), (_gb, _YP, _pz1)]):
    main.face(_q, 14, _P17, (0, 1, 0))
main.face([(_ga, _YP, _pz0), (_gb, _YP, _pz0), (_gb, _YG, _pz0), (_ga, _YG, _pz0)], 14, _P17, (0, 0, 1))
main.face([(_ga, _YP, _pz1), (_gb, _YP, _pz1), (_gb, _YG, _pz1), (_ga, _YG, _pz1)], 14, _P17, (0, 0, -1))
main.face([(_ga, _YP, _pz0), (_ga, _YG, _pz0), (_ga, _YG, _pz1), (_ga, _YP, _pz1)], 14, _P17, (1, 0, 0))
main.face([(_gb, _YP, _pz0), (_gb, _YG, _pz0), (_gb, _YG, _pz1), (_gb, _YP, _pz1)], 14, _P17, (-1, 0, 0))
glass.face([(_ga, _YG, _pz0), (_gb, _YG, _pz0), (_gb, _YG, _pz1), (_ga, _YG, _pz1)], 1, _P17, (0, 1, 0))
# pilot P18 / P19 rebuilt (build_pilot_ia.py l.360-366 dimensions): metal base face y -50.606, flashing front -50.686,
# flashing top +0.40
Y_MB, Y_FL, Z_FL = -50.606, -50.686, 0.40
for x0, x1 in PILOT_LOG["p19_x"]:
    lbox(x0, x1, -50.807, Y_FL - G, Y_MB - G, 0.20, Z_FL + G, 2.70, 17, "P19_SouthLamellas")
box(main, 53.15, 63.08, -51.08, Y_MB - G, 2.88, 2.93, 19, "P18_SouthCanopy")
lbox(53.18, 53.34, -51.02, Y_FL - G, Y_MB - G, 0.10, Z_FL + G, 2.88 - G, 19, "P18_SouthCanopy")

# ================================================================= 2. outer outline of the new facades (CCW, outward = right)
SK0, SKD = (-8.496, -2.427), (49.907, 5.388)          # skewed north wall, outer face (section z 8.0)
x_nc = SK0[0] + SKD[0] * (2.99 - SK0[1]) / SKD[1]     # skew x north straight y 2.99
y_wc = SK0[1] + SKD[1] * (-8.82 - SK0[0]) / SKD[0]    # skew x annex west x -8.82
W_pts = [(59.43, 2.99), (x_nc, 2.99), (-8.82, y_wc), (-8.82, -11.13), (-4.42, -11.13), (-4.42, -19.95),
         (-0.42, -19.95), (-0.42, -50.46), (41.88, -50.46)]
W = Poly(W_pts)
uv = W.cum                                             # vertex u's
L_W = W.length
u_n0 = 0.03                                            # x 59.40: wood end / sliver void above 4.70
u_s1 = L_W - 0.03                                      # x 41.85


def U(p):
    return W.project(p)


# ----------------------------------------------------------------- openings (library types, measured positions)
def panes(u0, z0, width, tid, hand, h, part, frame_mat):
    out = []
    for x0, y0, x1, y1 in TYPES[tid]["panes_m"] or []:
        if hand == "R":
            x0, x1 = width - x1, width - x0
        out.append((u0 + x0, u0 + x1, z0 + y0, z0 + y1, Cell(h, None, frame_mat, part, glass=True)))
    return out


def window(regs, c, z0, tid, part="P26_Windows_New"):
    w, h = TYPES[tid]["width_m"], TYPES[tid]["height_m"]
    u0 = U(c) - w / 2
    regs.append((u0, u0 + w, z0, z0 + h, Cell(-0.11, 11, 6, part)))
    regs += panes(u0, z0, w, tid, "L", -0.125, part, 11)


def door(regs, c, z0, tid=None, w=None, h=None, part="P27_Doors_New", depth=0.20, mat=14):
    if tid:
        w, h = TYPES[tid]["width_m"], TYPES[tid]["height_m"]
    u0 = U(c) - w / 2
    regs.append((u0, u0 + w, z0, z0 + h, Cell(-depth, mat, 6, part)))
    if tid:
        regs += panes(u0, z0, w, tid, "L", -depth - 0.015, part, mat)


def ulines_clear(us, regs, tol=0.005):
    """v007: drop split lines within 5 mm of a region edge (the ELV-21 pane edge at x 34.832 met a split at 34.830,
    2 mm vertex pairs in xView); the region edges are lines of the relief anyway, the ends are kept"""
    edges = [e for r in regs for e in (r[0], r[1])]
    return [u for k, u in enumerate(us) if k in (0, len(us) - 1) or not any(0 < abs(u - e) < tol for e in edges)]


def plinth_regs(u0, u1, part_p="P25_Plinth_Flashing_New"):
    return [(u0, u1, Z_DROP, 0.40, Cell(0.20, 4, 4, part_p)), (u0, u1, 0.13, 0.40, Cell(0.23, 18, 18, part_p))]


VOID = Cell(0.0, None, None, None)

# ----------------------------------------------------------------- G_N: north straight x 59.43 -> x_nc (to +15.42)
u_a, u_b = 0.0, uv[1]
regs = [(u_a, u_b, Z_DROP, Z_T1, Cell(0.0, 1, 1, "P24_N_Facade"))]
regs += plinth_regs(u_a, u_b)
regs.append((0.0, u_n0, 4.70, Z_T1, VOID))
door(regs, (51.728, 2.99), 0.0, "ELV-21")                               # v007: No 21, vision panel (booklet)
for z0 in (2.85, 6.90, 10.50):
    window(regs, (57.793, 2.99), z0, "ELV-01")
relief(main, glass, W, u_a, u_b, [Z_DROP, 0.13, 0.40, 2.55, 4.70, 7.78, 10.84, Z_TOP, Z_T1], regs, Cell(0.0, 1, 1, "P24_N_Facade"),
       ulines=ulines_clear(splits(W, u_a, u_b, 3.6), regs), omit=("left", "right", "bottom", "top"))

# ----------------------------------------------------------------- G_W: skew + TP annex + step + west (to +13.92)
u_a, u_b = uv[1], uv[7]
regs = [(uv[1], uv[2], Z_DROP, Z_TOP, Cell(0.0, 1, 1, "P24_N_Facade")),
        (uv[2], uv[4], Z_DROP, Z_TOP, Cell(0.0, 5, 5, "P23_TP_Annex")),
        (uv[4], uv[7], Z_DROP, Z_TOP, Cell(0.0, 1, 1, "P22_W_Facade"))]
regs += plinth_regs(uv[1], uv[2]) + plinth_regs(uv[4], uv[7])
regs.append((uv[2], uv[4], Z_DROP, 0.0, Cell(0.45, 4, 4, "P25_Plinth_Flashing_New")))   # TP brick plinth 640
# skew (north 6-1): ELV-08 x 27.25, added door x 38.4 (D14), ELV-03 x 2.10 / 5.65, single door x -2.04 (no type)
for cx in (27.256, 38.40):
    y = SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0]
    door(regs, (cx, y), 0.0, "ELV-08", part="P27_Doors_New")
for cx in (2.10, 5.649):
    y = SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0]
    window(regs, (cx, y), 0.90, "ELV-03")
y = SK0[1] + SKD[1] * (-2.0385 - SK0[0]) / SKD[0]
door(regs, (-2.0385, y), 0.30, "ELV-19")                               # FBX In-1H 1100x2050 (library ELV-19)
# TP annex x -8.82: ELV-11 x2 (z 0.30), single door 1.25 x 2.25 (no ELV type)
for cy in (-7.187, -4.322):
    door(regs, (-8.82, cy), 0.30, "ELV-11", part="P23_TP_Annex")
door(regs, (-8.82, -9.647), 0.30, "ELV-20", part="P23_TP_Annex")      # FBX In-1H 1100, frame 2250 (ELV-20)
# step x -4.42: ELV-05 two windows
for z0 in (3.367, 7.28):
    window(regs, (-4.42, -17.997), z0, "ELV-05")
# west main x -0.42: gates ELV-12 / ELV-13 (RAL 7040, D10), ELV-08 door, single door 1.05 (no type)
GATES = [(-38.253, "ELV-12"), (-34.153, "ELV-13"), (-30.003, "ELV-13"), (-25.856, "ELV-13")]
for cy, tid in GATES:
    w = TYPES[tid]["width_m"]
    u0 = U((-0.42, cy)) - w / 2
    regs.append((u0, u0 + w, 0.0, 4.0, Cell(-0.10, 15, 6, "P28_Gates_DockShelters")))
door(regs, (-0.42, -21.272), 0.0, "ELV-08", part="P27_Doors_New")
door(regs, (-4.42, -12.362), 0.0, "ELV-08")                             # v007: No 30, FBX opening (batten gap y -13.272..-11.452)
door(regs, (-0.42, -40.542), 0.0, "ELV-18")                             # FBX In-1H 900x2050 (library ELV-18)
relief(main, glass, W, u_a, u_b, [Z_DROP, 0.0, 0.13, 0.40, 2.55, 4.70, 7.78, 10.84, Z_TOP], regs, Cell(0.0, 1, 1, "P22_W_Facade"),
       ulines=ulines_clear(splits(W, u_a, u_b, 3.6), regs), omit=("left", "right", "bottom", "top"))

# ----------------------------------------------------------------- G_S: south 1-12 rest, x -0.42 -> 41.88
u_a, u_b = uv[7], L_W
regs = [(u_a, u_b, Z_DROP, Z_TOP, Cell(0.0, 1, 1, "P21_S_Facade"))]
regs += plinth_regs(u_a, u_b)
regs.append((u_s1, L_W, 4.70, Z_TOP, VOID))
for cx in (4.289, 13.189, 34.929):
    door(regs, (cx, -50.46), 0.0, "ELV-21")                           # v007: No 1, 4, 11, vision panel (booklet)
for cx in (15.789, 24.049):
    door(regs, (cx, -50.46), 0.0, "ELV-09")
door(regs, (27.099, -50.46), 0.0, "ELV-10")
window(regs, (18.469, -50.46), 0.90, "ELV-02")
for z0 in (2.85, 6.90):
    window(regs, (7.159, -50.46), z0, "ELV-01")
    window(regs, (40.464, -50.46), z0, "ELV-01")
window(regs, (18.469, -50.46), 6.90, "ELV-02")
window(regs, (20.849, -50.46), 6.90, "ELV-02")
relief(main, glass, W, u_a, u_b, [Z_DROP, 0.13, 0.40, 2.55, 4.70, 7.78, 10.84, Z_TOP], regs, Cell(0.0, 1, 1, "P21_S_Facade"),
       ulines=ulines_clear(splits(W, u_a, u_b, 3.6), regs), omit=("left", "right", "bottom", "top"))

# ================================================================= 3. parapets: caps + inner faces, high north wall
us = splits(W, uv[1], u_s1, 3.6)
B = [W.base(u) for u in us]
O = W.offset_pts(us, CAP_OUT)
I = W.offset_pts(us, -T_PAR)
for k in range(len(us) - 1):
    n = W.n[W.seg(0.5 * (us[k] + us[k + 1]))]
    out, inn = (n[0], n[1], 0), (-n[0], -n[1], 0)
    P = "P31_Parapets_New"
    main.face([(B[k][0], B[k][1], Z_TOP), (B[k + 1][0], B[k + 1][1], Z_TOP), (O[k + 1][0], O[k + 1][1], Z_TOP),
               (O[k][0], O[k][1], Z_TOP)], 18, P, (0, 0, -1))
    main.face([(O[k][0], O[k][1], Z_TOP), (O[k + 1][0], O[k + 1][1], Z_TOP), (O[k + 1][0], O[k + 1][1], Z_CAP),
               (O[k][0], O[k][1], Z_CAP)], 18, P, out)
    main.face([(O[k][0], O[k][1], Z_CAP), (O[k + 1][0], O[k + 1][1], Z_CAP), (I[k + 1][0], I[k + 1][1], Z_CAP),
               (I[k][0], I[k][1], Z_CAP)], 18, P, (0, 0, 1))
    main.face([(I[k][0], I[k][1], Z_TOP), (I[k + 1][0], I[k + 1][1], Z_TOP), (I[k + 1][0], I[k + 1][1], Z_CAP),
               (I[k][0], I[k][1], Z_CAP)], 18, P, inn)
    main.face([(I[k][0], I[k][1], Z_ROOF), (I[k + 1][0], I[k + 1][1], Z_ROOF), (I[k + 1][0], I[k + 1][1], Z_TOP),
               (I[k][0], I[k][1], Z_TOP)], 1, P, inn)
INNER_RING = I                                    # (x_nc+, 2.59) ... (41.85, -50.06)
IC = I[0]                                         # inner corner of the north straight / skew
# cap start (north): only the overhang strip shows beside the high wall
main.face([(B[0][0], B[0][1], Z_TOP), (O[0][0], O[0][1], Z_TOP), (O[0][0], O[0][1], Z_CAP),
           (B[0][0], B[0][1], Z_CAP)], 18, "P31_Parapets_New", (1, 0, 0))
# high north wall (x_nc .. 47.8 top face; end face at the corner above the cap)
P = "P36_Superstructures"
main.face([(B[0][0], B[0][1], Z_CAP), (IC[0], IC[1], Z_CAP), (IC[0], IC[1], Z_T1), (B[0][0], B[0][1], Z_T1)], 1, P,
          (-1, 0, 0))
YI = 2.99 - T_PAR                                 # 2.59
assert abs(IC[1] - YI) < 1e-6, IC
XS_HI = lin(IC[0], 47.8)
for k, (a, b) in enumerate(zip(XS_HI, XS_HI[1:])):
    a_out = B[0][0] if k == 0 else a
    main.face([(a, YI, Z_T1), (b, YI, Z_T1), (b, 2.99, Z_T1), (a_out, 2.99, Z_T1)], 18, P, (0, 0, 1))
wall(main, (IC[0], YI), (42.0, YI), Z_ROOF, Z_T1, 1, P, (0, -1))
wall(main, (42.0, YI), (42.25, YI), Z_TOP, Z_T1, 1, P, (0, -1))
wall(main, (42.25, YI), (47.8, YI), Z_PIT, Z_T1, 1, P, (0, -1))

# ================================================================= 4. joints with the pilot (P41_Joints)
J = "P41_Joints"
wall(main, (41.88, -50.46), (41.88, -50.61), 0.40, 4.70, 2, J, (-1, 0))          # J1 metal return S
wall(main, (41.85, -50.46), (41.85, -50.76), 4.70, Z_TOP, 3, J, (-1, 0))         # J2 wood end S
main.face([(41.85, -50.76, 4.70), (41.88, -50.61, 4.70), (41.88, -50.46, 4.70), (41.85, -50.46, 4.70)], 19, J,
          (0, 0, -1))                                                            # J3 soffit gap S
wall(main, (41.85, -50.24), (41.85, -50.06), Z_ROOF, Z_TOP, 1, J, (1, 0))         # J4 new parapet end (east)
wall(main, (41.85, -50.24), (41.85, -50.06), Z_TOP, Z_CAP, 18, J, (1, 0))
wall(main, (41.85, -50.51), (41.85, -50.92), Z_TOP, Z_CAP, 18, J, (-1, 0))        # J5 pilot cap end (west)
wall(main, (59.43, 2.99), (59.43, 3.14), 0.40, 4.70, 2, J, (-1, 0))              # J6 metal return N
wall(main, (59.40, 2.99), (59.40, 3.29), 4.70, Z_TOP, 3, J, (-1, 0))             # J7 wood end N
wall(main, (59.40, 2.99), (59.40, 3.45), Z_TOP, Z_CAP, 18, J, (-1, 0))           # J8 pilot cap end N
main.face([(59.40, 3.29, 4.70), (59.43, 3.14, 4.70), (59.43, 2.99, 4.70), (59.40, 2.99, 4.70)], 19, J,
          (0, 0, -1))                                                            # J9 soffit gap N

# ================================================================= 5. superstructures T1 / T2, pit walls (P36)
P = "P36_Superstructures"
# T1 (stair-lift block on the north wall, x 47.8 .. 59.40; east face moved 59.2 -> 59.40 to meet the pilot end)
wall(main, (59.40, -1.5), (59.40, 2.77), Z_ROOF, Z_CAP, 1, P, (1, 0))              # T1E quad A
wall(main, (59.40, -1.5), (59.40, 2.99), Z_CAP, Z_T1, 1, P, (1, 0))                # T1E quad B
wall(main, (58.7, -1.5), (59.40, -1.5), Z_ROOF, Z_T1, 1, P, (0, -1))
wall(main, (50.3, -1.5), (58.7, -1.5), Z_PIT, Z_T1, 1, P, (0, -1))
wall(main, (50.3, 0.0), (50.3, -1.5), Z_PIT, Z_T1, 1, P, (-1, 0))
# T1 south face y 0 with the glazed exit door (ELV-06), x 47.8 .. 50.3
pl = Poly([(47.8, 0.0), (50.3, 0.0)])               # outward = -y (the pit)
regs = []
u0 = 49.15 - 47.8 - 0.85
regs.append((u0, u0 + 1.70, Z_PIT, Z_PIT + 2.05, Cell(-0.10, 12, 6, P)))
regs += panes(u0, Z_PIT, 1.70, "ELV-06", "L", -0.115, P, 12)
relief(main, glass, pl, 0.0, pl.length, [Z_PIT, Z_T1], regs, Cell(0.0, 1, 1, P), ulines=splits(pl, 0, pl.length),
       omit=("left", "right", "bottom", "top"))


def glaze(p0, p1, z0, z_gl, z1, part, door_at=None, bay=1.25):
    """F50 glazing p0->p1 (outward = right of the direction) from z0 to z_gl, sandwich above to z1"""
    z0 += G                        # v006: bottoms G over the pit floor (v004: 1 cm under it)
    pl = Poly([p0, p1])
    Lg = pl.length
    nb = max(1, math.ceil((Lg - 0.05) / bay))
    cols = [0.025 + (Lg - 0.05) * i / nb for i in range(nb + 1)]
    regs = [(0.0, Lg, z_gl, z1, Cell(0.0, 1, 1, part))]
    for a, b in zip(cols, cols[1:]):
        for za, zb in ((z0 + 0.05, z0 + 2.10), (z0 + 2.15, z_gl - 0.05)):
            regs.append((a + 0.025, b - 0.025, za, zb, Cell(-0.015, None, 12, part, glass=True)))
    if door_at is not None:
        d0 = door_at - 0.85
        regs.append((d0, d0 + 1.70, z0, z0 + 2.10, Cell(-0.05, 12, 6, part)))
        regs += panes(d0, z0, 1.70, "ELV-06", "L", -0.065, part, 12)
    relief(main, glass, pl, 0.0, Lg, [z0, z_gl, z1], regs, Cell(0.02, 12, 12, part), ulines=splits(pl, 0, Lg),
           omit=("left", "right", "bottom", "top"))


glaze((47.8, YI - G), (47.8, 0.0), Z_PIT, 14.05, Z_T1, P)                           # T1 west glazing (faces the pit)
# T1 top 15.42 (incl. the north wall thickness for x >= 47.8)
hgrid(main, [(47.8, 0.0), (50.3, 0.0), (50.3, -1.5), (59.40, -1.5), (59.40, 2.99), (47.8, 2.99)], Z_T1,
      lambda x, y: 21, P)
# T2 (glazed stair-lift tower in the pit, x 47.8..53.0, y -11.45..-6.2, top +16.22)
wall(main, (47.8, -11.45), (53.0, -11.45), Z_ROOF, Z_T2, 1, P, (0, -1))
wall(main, (47.8, -6.45), (47.8, -11.45), Z_ROOF, Z_T2, 1, P, (-1, 0))
wall(main, (47.8, -6.2), (47.8, -6.45), Z_TOP, Z_T2, 1, P, (-1, 0))
wall(main, (53.0, -11.45), (53.0, -11.2), Z_TOP, Z_T2, 1, P, (1, 0))
wall(main, (47.8, -6.2), (48.3, -6.2), Z_PIT, Z_T2, 1, P, (0, 1))
glaze((53.0, -6.2), (48.3, -6.2), Z_PIT, 14.05, Z_T2, P)                       # north glazing (faces the pit)
glaze((53.0, -11.2 + G), (53.0, -6.2), Z_PIT, 14.05, Z_T2, P, door_at=-9.014 + 11.2 - G)  # east glazing + ELV-06
hrect(main, 47.8, 53.0, -11.45, -6.2, Z_T2, 21, P)
# pit walls: west x 42.0..42.25 / south y -6.45..-6.2 (top 13.92), south-east y -11.45..-11.2 (x 53..58.7)
wall(main, (42.0, -6.45), (42.0, YI), Z_ROOF, Z_TOP, 1, P, (-1, 0))
wall(main, (42.25, YI), (42.25, -6.2), Z_PIT, Z_TOP, 1, P, (1, 0))
wall(main, (47.8, -6.45), (42.0, -6.45), Z_ROOF, Z_TOP, 1, P, (0, -1))
wall(main, (42.25, -6.2), (47.8, -6.2), Z_PIT, Z_TOP, 1, P, (0, 1))
hrect(main, 42.0, 42.25, -6.45, YI, Z_TOP, 18, P)
hrect(main, 42.25, 47.8, -6.45, -6.2, Z_TOP, 18, P)
wall(main, (53.0, -11.2), (58.7, -11.2), Z_PIT, Z_TOP, 1, P, (0, 1))
wall(main, (58.7, -11.45), (53.0, -11.45), Z_ROOF, Z_TOP, 1, P, (0, -1))
wall(main, (58.7, -11.2), (58.7, -11.45), Z_ROOF, Z_TOP, 1, P, (1, 0))
hrect(main, 53.0, 58.7, -11.45, -11.2, Z_TOP, 18, P)
# pit drop face x 58.7 (terrace +12.45 -> pit +11.46), the stair fills y -11.0 .. -8.51
wall(main, (58.7, -11.0), (58.7, -11.2), Z_PIT, Z_ROOF, 1, P, (-1, 0))
wall(main, (58.7, -1.5), (58.7, -8.51), Z_PIT, Z_ROOF, 1, P, (-1, 0))
# stair 6 steps x 56.90..58.70, y -11.0..-8.51 (FBX stair 56.94..58.74, +11.40..+12.30)
S = "P37_RoofBoxes"
xs = lin(56.90, 58.70, 0.30)
zs = [Z_PIT + (Z_ROOF - Z_PIT) * (i + 1) / 6 for i in range(6)]
for i in range(6):
    hrect(main, xs[i], xs[i + 1], -11.0, -8.51, zs[i], 22, S)
    zlo = Z_PIT + G if i == 0 else zs[i - 1]
    wall(main, (xs[i], -8.51), (xs[i], -11.0), zlo, zs[i], 22, S, (-1, 0))
    wall(main, (xs[i], -11.0), (xs[i + 1], -11.0), Z_PIT + G, zs[i], 22, S, (0, -1))
    wall(main, (xs[i + 1], -8.51), (xs[i], -8.51), Z_PIT + G, zs[i], 22, S, (0, 1))
# pit floor (exploited terrace, lower level +11.46)
PIT = [(42.25, -6.2), (53.0, -6.2), (53.0, -11.2), (58.7, -11.2), (58.7, -1.5), (50.3, -1.5), (50.3, 0.0),
       (47.8, 0.0), (47.8, YI), (42.25, YI)]
hgrid(main, PIT, Z_PIT, lambda x, y: 23, "P33_Terrace")

# ================================================================= 6. roof +12.45 (ID21) and terrace deck (ID23)
ROOF = [(41.85, -47.24), (72.0, -47.24), (72.0, -0.23), (59.40, -0.23), (59.40, -1.5), (58.7, -1.5),
        (58.7, -11.45), (47.8, -11.45), (47.8, -6.45), (42.0, -6.45), (42.0, YI)]
ROOF += [(p[0], p[1]) for p in INNER_RING]          # inner corner .. (41.85, -50.06)
X_TER, Y_TER = 50.65, -19.17


def roof_mat(x, y):
    return 23 if (x > X_TER and y > Y_TER) else 21


n_roof = hgrid(main, ROOF, Z_ROOF, roof_mat, "P32_Roof_Main", extra_x=[X_TER], extra_y=[Y_TER])

# ================================================================= 7. skylight 25.12 x 8.36 hipped (P35)
K = "P35_Skylight"
SX0, SX1, SY0, SY1 = 37.84, 62.96, -27.94, -19.58
OX0, OX1, OY0, OY1 = 37.615, 63.185, -28.102, -19.382
Z_EAVE, Z_RIDGE = 12.75, 13.65
YR = 0.5 * (SY0 + SY1)
HW = 0.5 * (SY1 - SY0)
RX0, RX1 = SX0 + HW, SX1 - HW
wall(main, (OX0, OY0), (OX1, OY0), Z_ROOF + G, Z_EAVE, 12, K, (0, -1))
wall(main, (OX1, OY0), (OX1, OY1), Z_ROOF + G, Z_EAVE, 12, K, (1, 0))
wall(main, (OX1, OY1), (OX0, OY1), Z_ROOF + G, Z_EAVE, 12, K, (0, 1))
wall(main, (OX0, OY1), (OX0, OY0), Z_ROOF + G, Z_EAVE, 12, K, (-1, 0))
wall(main, (SX1, SY0), (SX0, SY0), Z_ROOF + G, Z_EAVE, 12, K, (0, 1))
wall(main, (SX0, SY0), (SX0, SY1), Z_ROOF + G, Z_EAVE, 12, K, (1, 0))
wall(main, (SX0, SY1), (SX1, SY1), Z_ROOF + G, Z_EAVE, 12, K, (0, -1))
wall(main, (SX1, SY1), (SX1, SY0), Z_ROOF + G, Z_EAVE, 12, K, (-1, 0))
for (a, b, c, d) in ((OX0, OX1, OY0, SY0), (OX0, OX1, SY1, OY1), (OX0, SX0, SY0, SY1), (SX1, OX1, SY0, SY1)):
    hrect(main, a, b, c, d, Z_EAVE, 12, K)
# glass: middle bays between rafters (module ~1.4 m) and hip triangles
nb = math.ceil((RX1 - RX0) / 1.45)
RXS = [RX0 + (RX1 - RX0) * i / nb for i in range(nb + 1)]
ZM, YM0, YM1 = 0.5 * (Z_EAVE + Z_RIDGE), 0.5 * (SY0 + YR), 0.5 * (SY1 + YR)
for a, b in zip(RXS, RXS[1:]):
    glass.face([(a, SY0, Z_EAVE), (b, SY0, Z_EAVE), (b, YM0, ZM), (a, YM0, ZM)], 1, K, (0, -1, 2))
    glass.face([(a, YM0, ZM), (b, YM0, ZM), (b, YR, Z_RIDGE), (a, YR, Z_RIDGE)], 1, K, (0, -1, 2))
    glass.face([(a, SY1, Z_EAVE), (a, YM1, ZM), (b, YM1, ZM), (b, SY1, Z_EAVE)], 1, K, (0, 1, 2))
    glass.face([(a, YM1, ZM), (a, YR, Z_RIDGE), (b, YR, Z_RIDGE), (b, YM1, ZM)], 1, K, (0, 1, 2))
for xe, xr, sgn in ((SX0, RX0, -1), (SX1, RX1, 1)):
    xm = 0.5 * (xe + xr)
    k = math.ceil((SY1 - SY0) / 1.45)
    ye_ = [SY0 + (SY1 - SY0) * i / k for i in range(k + 1)]
    ym_ = [YM0 + (YM1 - YM0) * i / k for i in range(k + 1)]
    for i in range(k):                                       # hip end: lower row quads, upper row fan
        glass.face([(xe, ye_[i], Z_EAVE), (xe, ye_[i + 1], Z_EAVE), (xm, ym_[i + 1], ZM), (xm, ym_[i], ZM)], 1, K,
                   (sgn, 0, 2))
        glass.face([(xm, ym_[i], ZM), (xm, ym_[i + 1], ZM), (xr, YR, Z_RIDGE)], 1, K, (sgn, 0, 2))
    # corner wedges of the long slopes (eave x .. ridge end), two rows
    glass.face([(xe, SY0, Z_EAVE), (xm, SY0, Z_EAVE), (xm, YM0, ZM)], 1, K, (0, -1, 2))
    glass.face([(xm, SY0, Z_EAVE), (xr, SY0, Z_EAVE), (xr, YM0, ZM), (xm, YM0, ZM)], 1, K, (0, -1, 2))
    glass.face([(xm, YM0, ZM), (xr, YM0, ZM), (xr, YR, Z_RIDGE)], 1, K, (0, -1, 2))
    glass.face([(xe, SY1, Z_EAVE), (xm, YM1, ZM), (xm, SY1, Z_EAVE)], 1, K, (0, 1, 2))
    glass.face([(xm, SY1, Z_EAVE), (xm, YM1, ZM), (xr, YM1, ZM), (xr, SY1, Z_EAVE)], 1, K, (0, 1, 2))
    glass.face([(xm, YM1, ZM), (xr, YR, Z_RIDGE), (xr, YM1, ZM)], 1, K, (0, 1, 2))
# frame on the glass: ridge, 4 hips, rafters (60 x 60, bottom faces dropped, 5 mm above the glass)
FR = 0.06
lift = 0.005


def on_slope(p, n):
    L = math.sqrt(sum(c * c for c in n))
    return tuple(p[i] + n[i] / L * (lift + FR / 2) for i in range(3))


ridge0, ridge1 = (RX0, YR, Z_RIDGE), (RX1, YR, Z_RIDGE)
obox(main, on_slope(ridge0, (0, 0, 1)), on_slope(ridge1, (0, 0, 1)), (0, 1, 0), FR, FR, 12, K, skip=("-u",))
HIP_CUT = (G + FR / 2 * math.sqrt(0.5)) / math.sqrt(0.5)   # plan length cut at the ridge end (hips at 45 deg in plan)
for xe, xr, ye in ((SX0, RX0, SY0), (SX0, RX0, SY1), (SX1, RX1, SY0), (SX1, RX1, SY1)):
    p0, p1 = (xe, ye, Z_EAVE), (xr, YR, Z_RIDGE)
    ax = (p1[0] - p0[0], p1[1] - p0[1], 0.0)
    side = (-ax[1], ax[0], 0.0)
    f = 1.0 - HIP_CUT / math.hypot(ax[0], ax[1])            # v006: hips end G before the ridge beam / each other
    p1 = tuple(p0[i] + (p1[i] - p0[i]) * f for i in range(3))
    obox(main, on_slope(p0, (0, 0, 1)), on_slope(p1, (0, 0, 1)), side, FR, FR, 12, K, skip=("-u",))
RAF_CUT = FR / 2 + G + 0.001                                 # rafter top end G short of the ridge beam side face
for x in RXS[1:-1]:
    # v006: true slope normals (v004 used (0, -HW, dZ), not perpendicular: rafters sat 15 mm into the glass / eave)
    for ye, nrm, sy in ((SY0, (0, -(Z_RIDGE - Z_EAVE), HW), -1), (SY1, (0, Z_RIDGE - Z_EAVE, HW), 1)):
        yr = YR + sy * RAF_CUT
        zr = Z_RIDGE - RAF_CUT * (Z_RIDGE - Z_EAVE) / HW
        p0, p1 = on_slope((x, ye, Z_EAVE), nrm), on_slope((x, yr, zr), nrm)
        # up = axis x (1,0,0) points down on the south slope, up on the north slope: drop the face on the glass
        obox(main, p0, p1, (1, 0, 0), FR, FR, 12, K, skip=("+u", "end") if ye == SY0 else ("-u", "end"))

# ================================================================= 8. roof structures: curbs, shafts, cups (P37)
S = "P37_RoofBoxes"
CURB = 12.85


def curb_ring(x0, x1, y0, y1, w=0.32, open_west=False):
    """curb ring (outer rect, width w) as faces only: tops, outer and inner walls; G over the roof (v004: 1 cm into it)"""
    zb = Z_ROOF + G
    xi0, xi1, yi0, yi1 = x0 + w, x1 - w, y0 + w, y1 - w
    if open_west:
        xi0 = x0
    hrect(main, xi0, xi1, y0, yi0, CURB, 22, S)
    hrect(main, xi0, xi1, yi1, y1, CURB, 22, S)
    hrect(main, xi1, x1, y0, yi0, CURB, 22, S)
    hrect(main, xi1, x1, yi1, y1, CURB, 22, S)
    hrect(main, xi1, x1, yi0, yi1, CURB, 22, S)
    wall(main, (x1, y0), (x1, y1), zb, CURB, 22, S, (1, 0))
    wall(main, (xi1, yi0), (xi1, yi1), zb, CURB, 22, S, (-1, 0))
    if open_west:
        wall(main, (x0, y0), (x1, y0), zb, CURB, 22, S, (0, -1))
        wall(main, (x0, y1), (x1, y1), zb, CURB, 22, S, (0, 1))
        wall(main, (x0, yi0), (xi1, yi0), zb, CURB, 22, S, (0, 1))
        wall(main, (x0, yi1), (xi1, yi1), zb, CURB, 22, S, (0, -1))
        return
    hrect(main, x0, xi0, y0, yi0, CURB, 22, S)
    hrect(main, x0, xi0, yi1, y1, CURB, 22, S)
    hrect(main, x0, xi0, yi0, yi1, CURB, 22, S)
    wall(main, (x0, y0), (x1, y0), zb, CURB, 22, S, (0, -1))
    wall(main, (x0, y1), (x1, y1), zb, CURB, 22, S, (0, 1))
    wall(main, (x0, y0), (x0, y1), zb, CURB, 22, S, (-1, 0))
    wall(main, (xi0, yi0), (xi1, yi0), zb, CURB, 22, S, (0, 1))
    wall(main, (xi0, yi1), (xi1, yi1), zb, CURB, 22, S, (0, -1))
    wall(main, (xi0, yi0), (xi0, yi1), zb, CURB, 22, S, (1, 0))


XW = -0.02                                           # west parapet inner face


def curb_region(bands, holes, w=0.32, maxlen=3.9):
    """v006: curb = union of band rectangles minus holes, on one cell grid (all band / hole edges + <= maxlen
    splits); tops at CURB, walls zb..CURB on every region boundary; G over the roof"""
    zb = Z_ROOF + G
    def coords(i0, i1):
        cs = sorted({round(c, 6) for b in bands for c in (b[i0], b[i1])} |
                    {round(c, 6) for h in holes for c in (h[i0], h[i1])
                     if min(b[i0] for b in bands) < c < max(b[i1] for b in bands)})
        out = [cs[0]]
        for a, b in zip(cs, cs[1:]):
            out += lin(a, b, maxlen)[1:]
        return out
    X, Y = coords(0, 1), coords(2, 3)
    def inside(x, y):
        return any(b[0] < x < b[1] and b[2] < y < b[3] for b in bands) and \
            not any(h[0] < x < h[1] and h[2] < y < h[3] for h in holes)
    cell = {(i, j): inside(0.5 * (X[i] + X[i + 1]), 0.5 * (Y[j] + Y[j + 1]))
            for i in range(len(X) - 1) for j in range(len(Y) - 1)}
    n = 0
    for (i, j), ok in cell.items():
        if not ok:
            continue
        x0, x1, y0, y1 = X[i], X[i + 1], Y[j], Y[j + 1]
        main.face([(x0, y0, CURB), (x1, y0, CURB), (x1, y1, CURB), (x0, y1, CURB)], 22, S, (0, 0, 1))
        n += 1
        if not cell.get((i - 1, j), False):
            wall(main, (x0, y1), (x0, y0), zb, CURB, 22, S, (-1, 0))
        if not cell.get((i + 1, j), False):
            wall(main, (x1, y0), (x1, y1), zb, CURB, 22, S, (1, 0))
        if not cell.get((i, j - 1), False):
            wall(main, (x0, y0), (x1, y0), zb, CURB, 22, S, (0, -1))
        if not cell.get((i, j + 1), False):
            wall(main, (x1, y1), (x0, y1), zb, CURB, 22, S, (0, 1))
    return n


SHAFTS = [(0.06, 0.94, -15.05, -12.52, 14.22), (0.56, 3.37, -42.43, -40.96, 13.14), (4.24, 5.58, -24.22, -22.91, 13.73),
          (6.59, 10.18, -22.74, -19.27, 13.61), (10.61, 12.69, -19.25, -18.15, 14.82),
          (11.50, 12.85, -21.63, -20.38, 13.73), (15.27, 16.67, -42.16, -41.01, 13.62),
          (16.18, 17.83, -9.56, -7.91, 12.97), (18.33, 20.37, -23.30, -19.25, 13.03),
          (18.50, 20.09, -42.40, -40.81, 13.14), (21.65, 22.75, -42.21, -41.26, 13.72),
          (30.43, 31.50, -8.16, -6.74, 14.53), (30.90, 32.63, -6.39, -4.67, 13.07), (32.22, 35.83, -32.84, -27.78, 14.90),
          (37.87, 40.18, -10.26, -7.96, 13.05), (39.60, 41.50, -12.81, -10.91, 13.05), (40.82, 42.01, -5.58, -1.59, 14.13),
          (42.72, 44.98, -44.34, -42.78, 13.83), (43.41, 47.23, -42.42, -40.24, 14.33),
          (47.14, 49.21, -16.98, -13.80, 15.93), (47.19, 48.96, -48.27, -46.51, 12.84),
          (47.30, 49.00, -13.48, -11.78, 13.05), (51.69, 55.68, -38.80, -33.49, 14.60),
          (67.00, 68.71, -42.48, -38.87, 14.63), (68.66, 73.21, -29.38, -27.73, 14.53),
          (68.95, 70.41, -39.71, -37.86, 14.04)]
# zone A (x 0..33.6, y -44.73..-27.94): its west side is the parapet (curb starts G off it); zone B: closed ring
CW_ = 0.32
HOLES = [(x0 - G, x1 + G, y0 - G, y1 + G) for x0, x1, y0, y1, zt in SHAFTS]
XA0, XA1, YA0, YA1 = XW + G, 33.595, -44.727, -27.937
XB0, XB1, YB0, YB1 = -0.22, 33.595, -19.527, -2.737
N_CURB = curb_region([(XA0, XA1, YA0, YA0 + CW_), (XA0, XA1, YA1 - CW_, YA1), (XA1 - CW_, XA1, YA0, YA1)], HOLES)
N_CURB += curb_region([(XB0, XB1, YB0, YB0 + CW_), (XB0, XB1, YB1 - CW_, YB1), (XB1 - CW_, XB1, YB0, YB1),
                       (XB0, XB0 + CW_, YB0, YB1)], HOLES)
for x0, x1, y0, y1, zt in SHAFTS:
    if x1 > 42.0 and x0 < 42.0:                                   # the box at the pit wall: G off it, east face closed
        x1 = 42.0 - G
    box(main, x0, x1, y0, y1, Z_ROOF + G, zt, 22, S, skip=("z0",))
CUPS = [(36.61, 37.20, -41.54, -40.95), (37.60, 38.19, -41.54, -40.95), (40.76, 41.35, -41.42, -40.83),
        (41.75, 42.34, -41.42, -40.83), (44.98, 45.84, -47.20, -46.35), (46.53, 47.12, -47.07, -46.48),
        (50.48, 51.34, -47.20, -46.35), (52.03, 52.62, -47.07, -46.48), (54.51, 55.36, -47.20, -46.35),
        (56.06, 56.65, -47.07, -46.48), (58.88, 59.73, -47.20, -46.35), (60.44, 61.02, -47.07, -46.48),
        (63.41, 64.26, -47.20, -46.35), (64.96, 65.55, -47.07, -46.48), (67.66, 68.85, -47.52, -46.33),
        (67.96, 68.55, -48.81, -48.22)]
for x0, x1, y0, y1 in CUPS:
    box(main, x0, x1, y0, y1, Z_ROOF + G, 12.76, 22, S, skip=("z0",))

# ================================================================= 9. terrace: screens (ID1) and railings (ID20)
T = "P33_Terrace"
R = "P34_Railings"
Z_FENCE = 13.85
box(main, 62.65, 74.62, -19.215, -19.115, Z_ROOF + G, Z_FENCE, 1, T, skip=("z0",))
box(main, 50.605, 50.705, -19.215, -15.60, Z_ROOF + G, Z_FENCE, 1, T, skip=("z0",))


def railing(p0, p1, z0, ztop, post=0.04, step=1.5, skip_start=False, skip_end=False, posts_at_ends=True):
    """SIMPLE railing: square posts + one top rail, no infill (user decides geometry vs alpha later)"""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    t = (dx / L, dy / L)
    side = (-t[1], t[0], 0.0)
    n = max(1, math.ceil(L / step))
    for i in range(n + 1):
        if not posts_at_ends and i in (0, n):
            continue
        f = (i / n) * (L - 2 * post) + post
        x, y = p0[0] + t[0] * f, p0[1] + t[1] * f
        obox(main, (x, y, z0 + G), (x, y, ztop - 0.04 - G), side, post, post, 20, R, skip=("start", "end"))
    zr = ztop - 0.02
    sk = tuple(k for k, f in (("start", skip_start), ("end", skip_end)) if f)
    obox(main, (p0[0], p0[1], zr), (p1[0], p1[1], zr), (0, 0, 1), 0.04, post + 0.02, 20, R, skip=sk)


railing((50.705 + G, -19.165), (62.65 - G, -19.165), Z_ROOF, Z_FENCE - 0.03, post=0.06, skip_start=True, skip_end=True)  # Rabitz fence
railing((50.655, -15.60 + G), (50.655, -11.45 - G), Z_ROOF, Z_FENCE - 0.03, post=0.06, skip_start=True, skip_end=True)
railing((58.74, -8.45), (58.74, -1.50 - G), Z_ROOF, Z_ROOF + 1.10, skip_end=True)                          # pit edge

# ================================================================= 10. canopies (ID19), lamellas (ID17), downpipes (ID20)
C = "P29_Canopies_New"
YS = -50.46                                                                     # south facade face
box(main, 10.33, 17.42, -51.707, YS - G, 2.71, 3.09, 19, C)                      # D14: slab missing in FBX
box(main, 25.227, 29.015, -51.957, YS - G, 2.50, 3.09, 19, C)
box(main, 33.557, 36.545, -51.707, YS - G, 2.71, 3.09, 19, C)                    # D14: slab missing in FBX
box(main, -1.645, -0.42 - G, -23.452, -19.95 - G, 2.70, 2.75, 19, C)             # west door canopy
LM = "P30_Lamellas_New"
for x in (10.654, 10.904, 11.154, 11.404, 11.654, 11.904, 12.154, 14.174, 14.424, 14.674, 14.924, 16.604, 16.854,
          17.104, 17.354, 33.623, 33.894, 35.915, 36.165, 36.415):
    box(main, x, x + 0.05, -50.657, YS - G, 0.40 + G, 2.71 - G, 17, LM, skip=("y1", "z1"))   # on the flashing top
for x in (25.764, 28.385, 28.635, 28.885):
    box(main, x, x + 0.05, -50.657, YS - G, 0.40 + G, 2.50 - G, 17, LM, skip=("y1", "z1"))
for y in (-23.130, -22.880, -22.631, -22.381, -20.247):
    box(main, -0.575, -0.42 - G, y, y + 0.05, 0.40 + G, 2.70 - G, 17, LM, skip=("x1", "z1"))
D = "P39_Downpipes"
for x, ztop in ((10.455, 2.71), (25.51, 2.50), (33.64, 2.71)):                  # ztop = canopy soffit
    box(main, x - 0.05, x + 0.05, -51.00, -50.90, 0.10, ztop - G, 20, D, skip=("z1",))
box(main, -0.82, -0.72, -23.38, -23.28, 0.10, 2.70 - G, 20, D, skip=("z1",))

# ================================================================= 11. sign frame SW (ID16), Arktos boxes (ID27)
SF = Cell(0.06, 16, 16, "P21_S_Facade")
pl = Poly([(-0.025, -50.478), (1.975, -50.478)])
relief(main, None, pl, 0.0, pl.length, [3.0, 3.5], [(0.06, pl.length - 0.06, 3.06, 3.44, Cell(0.0, None, 16,
       "P21_S_Facade"))], SF, ulines=splits(pl, 0, pl.length))
A = "P40_Arktos"
for x0, x1, z0, z1 in ((20.862, 21.462, 4.75, 5.22), (24.163, 24.763, 4.75, 5.22), (25.625, 26.225, 4.75, 5.22),
                       (32.563, 33.263, 4.70, 5.27)):
    box(main, x0, x1, -50.62, YS - G, z0, z1, 27, A)
skn = W.n[1]
skt = W.t[1]
for cx in (-2.966, -1.134):
    b = (SK0[0] + SKD[0] * (cx - SK0[0]) / SKD[0], SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0])
    for zc in (4.90,):
        oc = 0.05 + G                                       # back face G off the wall (v004: 1 cm into it)
        p0 = (b[0] - skt[0] * 0.25 + skn[0] * oc, b[1] - skt[1] * 0.25 + skn[1] * oc, zc)
        p1 = (b[0] + skt[0] * 0.25 + skn[0] * oc, b[1] + skt[1] * 0.25 + skn[1] * oc, zc)
        obox(main, p0, p1, (skn[0], skn[1], 0), 0.10, 0.40, 27, A)

# ================================================================= 12. fire ladders (simplified, ID20)
LD = "P38_FireLadders"


def ladder(base, t, n, z0=1.40, z1=15.00, half=0.40, off=0.20):
    """two stringers 60x60 at +-half along t, 'off' from the wall face, rungs 30x30 every 0.35, 4 bracket pairs"""
    for s in (-1, 1):
        c = (base[0] + t[0] * s * half + n[0] * (off + 0.03), base[1] + t[1] * s * half + n[1] * (off + 0.03))
        obox(main, (c[0], c[1], z0), (c[0], c[1], z1), (t[0], t[1], 0), 0.06, 0.06, 20, LD)
        for zb in (3.0, 6.0, 9.0, 12.0):
            p0 = (base[0] + t[0] * s * half + n[0] * G, base[1] + t[1] * s * half + n[1] * G, zb)
            p1 = (base[0] + t[0] * s * half + n[0] * (off - G), base[1] + t[1] * s * half + n[1] * (off - G), zb)
            obox(main, p0, p1, (0, 0, 1), 0.04, 0.04, 20, LD, skip=("start", "end"))
    z = z0 + 0.35
    while z < z1 - 0.2:
        hr = half - 0.03 - G                                 # rung ends G short of the stringer faces
        c0 = (base[0] - t[0] * hr + n[0] * (off + 0.03), base[1] - t[1] * hr + n[1] * (off + 0.03), z)
        c1 = (base[0] + t[0] * hr + n[0] * (off + 0.03), base[1] + t[1] * hr + n[1] * (off + 0.03), z)
        obox(main, c0, c1, (0, 0, 1), 0.03, 0.03, 20, LD, skip=("start", "end"))
        z += 0.35


for cx in (33.70, 8.40):                                   # north 6-1 at axes 7 and 4 (sheet 19)
    b = (cx, SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0])
    ladder(b, (-skt[0], -skt[1]), skn)
ladder((-0.42, -47.233), (0.0, 1.0), (-1.0, 0.0))          # west near Ж-И (parapet gap y -47.75..-46.71 in FBX)

# ================================================================= 13. dock shelters DS_403M simplified (ID26)
GD = "P28_Gates_DockShelters"
# v006: 1 cm INSIDE the gate opening each side (v004: 3 cm outside it, through the plinth), back G off the facade,
# bottoms G over the sill; 5 cm higher than the opening as before
XF, XB, WP, ZG, ZD, Z0 = -0.925, -0.42 - G, 0.25, 4.05, 4.5, G
XL, ZS = -0.65 - G, 0.40 + G                       # in front of / over the plinth flashing (x -0.65, top +0.40)
SHELTERS = []
for (y0, y1), (cy, tid) in zip(((-39.907, -36.607), (-35.957, -32.457), (-31.807, -28.307), (-27.607, -24.107)),
                               GATES):
    y0, y1 = y0 - 0.03, y1 + 0.03                   # v004 extents (3 cm wider than the FBX shelter)
    wg = TYPES[tid]["width_m"]
    yo0, yo1 = cy - wg / 2, cy + wg / 2              # gate opening
    ya, yb = y0 + WP, y1 - WP
    assert yo0 < ya and yb < yo1, (ya, yb, yo0, yo1)
    steps = {"y0": y0 < yo0 - 1e-6, "y1": y1 > yo1 + 1e-6}
    SHELTERS.append({"y": [round(y0, 3), round(y1, 3)], "opening": [round(yo0, 3), round(yo1, 3)], "stepped": steps})
    zs_ = [Z0, ZS, ZG] if any(steps.values()) else [Z0, ZG]
    for p, q in ((y0, ya), (yb, y1)):
        for za, zb in zip(zs_, zs_[1:]):
            wall(main, (XF, p), (XF, q), za, zb, 26, GD, (-1, 0))
    for p, q in ((y0, ya), (ya, yb), (yb, y1)):
        wall(main, (XF, p), (XF, q), ZG, ZD, 26, GD, (-1, 0))
    for yw, nrm, key, yo in ((y0, (0, -1), "y0", yo0), (y1, (0, 1), "y1", yo1)):
        if not steps[key]:
            for za, zb in zip(zs_ + [ZD], zs_[1:] + [ZD]):
                if zb > za:
                    wall(main, (XF, yw), (XB, yw), za, zb, 26, GD, nrm)
            continue
        wall(main, (XF, yw), (XL, yw), Z0, ZS, 26, GD, nrm)          # below the flashing top: stop in front of it
        for za, zb in ((ZS, ZG), (ZG, ZD)):
            wall(main, (XF, yw), (XL, yw), za, zb, 26, GD, nrm)
            wall(main, (XL, yw), (XB, yw), za, zb, 26, GD, nrm)
        lo, hi = sorted((yw, yo))
        hrect(main, XL, XB, lo, hi, ZS, 26, GD, up=False)           # pad underside over the flashing
        wall(main, (XL, lo), (XL, hi), Z0, ZS, 26, GD, (1, 0))       # pad riser in front of the flashing
    for yw, nrm in ((ya, (0, 1)), (yb, (0, -1))):
        for za, zb in zip(zs_, zs_[1:]):
            wall(main, (XF, yw), (XB, yw), za, zb, 26, GD, nrm)
    hrect(main, XF, XB, ya, yb, ZG, 26, GD, up=False)
    hrect(main, XF, XB, y0, y1, ZD, 26, GD)


# ================================================================= 14. to Blender
def srgb_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def material(name, hexcol, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    lin_ = srgb_lin(hexcol)
    m.diffuse_color = (*lin_, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*lin_, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.6
        if alpha < 1.0:
            bsdf.inputs["Alpha"].default_value = alpha
    if alpha < 1.0:
        try:
            m.surface_render_method = "BLENDED"
        except Exception:
            pass
    return m


def to_object(mb, name, slots):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in mb.verts]
    bm.verts.ensure_lookup_table()
    lay = bm.faces.layers.int.new("part_idx")
    bad = []
    for idx, mat, part, kind in mb.faces:
        try:
            f = bm.faces.new([vs[i] for i in idx])
        except ValueError:
            bad.append((part, [mb.verts[i] for i in idx][:4]))
            continue
        f.material_index = mat - 1
        f[lay] = PART_IDS.index(part)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for i in sorted(slots):
        me.materials.append(slots[i])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["part_ids"] = json.dumps(PART_IDS)
    ob["build"] = ("jobs/elv-tc-vpm/scripts/build_full_v007.py (v006 + capsules P43, cover strips P44, doors ELV-21 / No 30); pilot build-v001 (accepted) + new parts "
                   "parts/elv_full_parts_v002.json (Gate 1 pending) + doors ELV-18/19/20 + light housings P42")
    return ob, bad


HEALED = heal_t(main, tol=2e-4)
HEALED_G = heal_t(glass, tol=2e-4)
# ================================================================= 15. light housings (after healing: separate islands)
from mathutils.bvhtree import BVHTree  # noqa: E402
from lights_geom import build as build_lights  # noqa: E402
from light_paths import W as W_L  # noqa: E402
assert abs(W_L.length - L_W) < 1e-9
_bvh = BVHTree.FromPolygons([tuple(v) for v in main.verts], [list(f[0]) for f in main.faces])
n_before = len(main.faces)
LREP = build_lights(main, LAYOUT, _bvh, {"W": (0.05, L_W - 0.10)})
LREP["faces_added"] = len(main.faces) - n_before
json.dump(LREP, open(LIGHTS_OUT, "w", encoding="utf-8"), indent=1)

# ================================================================= 16. v007: cover strips P44 and interior capsules P43
import capsules_v007 as CAP  # noqa: E402
from mathutils import Vector  # noqa: E402
from pilot_outlines import U as U_P, uA as uA_P, uB as uB_P  # noqa: E402
OFF = (35.1000, -24.2535)        # delivered = build - OFF (delivery v002 pivot, kept for v003)
P43, P44, ID_CAP, ID_STRIP = "P43_InteriorCapsules", "P44_CoverStrips", 34, 20
_mv = [tuple(v) for v in main.verts]
_mp = [list(f[0]) for f in main.faces]
_mmat = [f[1] for f in main.faces]
_gv0 = len(_mv)
SCN = CAP.Scene(_mv + [tuple(v) for v in glass.verts], _mp + [[i + _gv0 for i in f[0]] for f in glass.faces])
_bvh_m = BVHTree.FromPolygons([Vector(v) for v in _mv], _mp)
ADD = {"strips": [], "strips_dropped": [], "capsules": [], "capsules_skipped": [], "glass_inside_capsule": []}

# ---- 16a. 24 horizontal joint cover strips (Batten_FS-8P 165 x 22 mm), G = 6 mm off the facade [D197], ID20 7021
STRIPS = json.load(open(os.path.join(JOB, "outputs", "build-v007", "strips_selected_v007.json"), encoding="utf-8"))
T_STRIP, STEP = 0.022, 0.05
FACADE_IDS = {1, 5}               # sandwich / TP annex paint: the receiving facades of the strips


def _ray_face(o, d, dist):
    loc, nrm, fi, dd = _bvh_m.ray_cast(Vector(o), Vector(d), dist)
    if loc is None:
        return None
    return loc, fi, dd, Vector(nrm).dot(Vector(d)) < 0


for st in STRIPS:
    vs = [(v[0] + OFF[0], v[1] + OFF[1], v[2]) for v in st["verts"]]
    z0, z1 = min(v[2] for v in vs), max(v[2] for v in vs)
    bot = sorted([v for v in vs if abs(v[2] - z0) < 1e-3])[:2]
    p0, p1 = bot[0], bot[-1]
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    a = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L)
    perp = (-a[1], a[0])
    zm = 0.5 * (z0 + z1)
    mid = (0.5 * (p0[0] + p1[0]), 0.5 * (p0[1] + p1[1]))
    out = None
    for sg in (1, -1):              # outward = the side from which a ray hits a facade front face within 0.6 m
        o = (mid[0] + sg * perp[0] * 0.4, mid[1] + sg * perp[1] * 0.4, zm)
        h = _ray_face(o, (-sg * perp[0], -sg * perp[1], 0.0), 0.9)
        if h and h[3] and _mmat[h[1]] in FACADE_IDS:
            out = (sg * perp[0], sg * perp[1])
            break
    if out is None:                 # try along the strip at a few stations
        for f in (0.1, 0.3, 0.7, 0.9):
            q = (p0[0] + a[0] * L * f, p0[1] + a[1] * L * f)
            for sg in (1, -1):
                o = (q[0] + sg * perp[0] * 0.4, q[1] + sg * perp[1] * 0.4, zm)
                h = _ray_face(o, (-sg * perp[0], -sg * perp[1], 0.0), 0.9)
                if h and h[3] and _mmat[h[1]] in FACADE_IDS:
                    out = (sg * perp[0], sg * perp[1])
                    break
            if out:
                break
    if out is None:
        ADD["strips_dropped"].append({"name": st["name"], "why": "no sandwich facade found within 0.5 m"})
        continue
    # samples every 5 cm: facade (ID01/05 front face) behind the outline within 0.15 m of the median offset
    ns = max(1, int(L / STEP))
    samples = []
    for k in range(ns):
        s = (k + 0.5) * L / ns
        q = (p0[0] + a[0] * s, p0[1] + a[1] * s)
        o = (q[0] + out[0] * 0.3, q[1] + out[1] * 0.3, zm)
        h = _ray_face(o, (-out[0], -out[1], 0.0), 0.75)
        ok = bool(h and h[3] and _mmat[h[1]] in FACADE_IDS)
        samples.append((s, (h[0].x * out[0] + h[0].y * out[1]) if ok else None))
    offs = sorted(d for _, d in samples if d is not None)
    if not offs:
        ADD["strips_dropped"].append({"name": st["name"], "why": "no facade samples"})
        continue
    dmed = offs[len(offs) // 2]
    free = [d is not None and abs(d - dmed) < 0.15 for _, d in samples]
    # runs of facade samples -> fitted facade line (least squares d(s)) -> blocked intervals by other geometry
    runs, cur = [], []
    for k, f in enumerate(free):
        if f:
            cur.append(k)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    pieces = []
    for run in runs:
        ss = [samples[k][0] for k in run]
        ds = [samples[k][1] for k in run]
        n_ = len(ss)
        sm, dm = sum(ss) / n_, sum(ds) / n_
        var = sum((s - sm) ** 2 for s in ss)
        b = (sum((s - sm) * (d - dm) for s, d in zip(ss, ds)) / var) if var > 1e-9 else 0.0
        dfit = lambda s: dm + b * (s - sm)  # noqa: E731
        sa, sb = ss[0] - 0.5 * L / ns, ss[-1] + 0.5 * L / ns

        def B(s):
            q = (p0[0] + a[0] * s, p0[1] + a[1] * s)
            d0 = q[0] * out[0] + q[1] * out[1]
            return (q[0] + out[0] * (dfit(s) - d0), q[1] + out[1] * (dfit(s) - d0))
        # blocked intervals: polygons overlapping the strip box grown by NEAR (the facade stays G - NEAR = 1 mm away)
        e = CAP.NEAR
        grow = CAP.strip_box(B(sa - e), B(sb + e), out, z0 - e, z1 + e, G - e, T_STRIP + 2 * e)
        gv, gp = [], []
        for pts, _ in grow:
            gp.append(list(range(len(gv), len(gv) + len(pts))))
            gv += [Vector(p) for p in pts]
        hits = {i for i, _ in _bvh_m.overlap(BVHTree.FromPolygons(gv, gp))}
        blocked = []
        for fi in hits:
            sv = [(main.verts[i][0] - p0[0]) * a[0] + (main.verts[i][1] - p0[1]) * a[1] for i in main.faces[fi][0]]
            blocked.append((min(sv) - G, max(sv) + G, fi))
        cuts = [(sa, sb)]
        for lo, hi, _ in sorted(blocked):
            nxt = []
            for c0, c1 in cuts:
                if hi <= c0 or lo >= c1:
                    nxt.append((c0, c1))
                    continue
                if lo > c0:
                    nxt.append((c0, lo))
                if hi < c1:
                    nxt.append((hi, c1))
            cuts = nxt
        blk_parts = sorted({PART_IDS[main.faces[fi][2]] if isinstance(main.faces[fi][2], int) else main.faces[fi][2]
                            for _, _, fi in blocked})
        for c0, c1 in cuts:
            if c1 - c0 < 0.10:
                continue
            fs = CAP.strip_box(B(c0), B(c1), out, z0, z1, G, T_STRIP)
            chk = SCN.conflicts(fs)
            if chk["overlap"] or chk["near"] or chk["added"]:
                ADD["strips_dropped"].append({"name": st["name"], "piece": [round(c0, 3), round(c1, 3)], "why": chk})
                continue
            for pts, nrm in fs:
                main.face(pts, ID_STRIP, P44, nrm)
            SCN.accept(fs)
            pieces.append({"s": [round(c0, 3), round(c1, 3)], "len_m": round(c1 - c0, 3),
                           "facade_slope_mm_per_m": round(b * 1000, 2)})
        if blk_parts:
            pieces.append({"blocked_by_parts": blk_parts, "blocked_intervals": len(blocked)})
    ADD["strips"].append({"name": st["name"], "z": [round(z0, 4), round(z1, 4)], "outline_len_m": round(L, 3),
                          "out": [round(out[0], 4), round(out[1], 4)], "facade_offset_from_outline_mm":
                          round((dmed - (p0[0] * out[0] + p0[1] * out[1])) * 1000, 1), "pieces": pieces,
                          "built_len_m": round(sum(p.get("len_m", 0) for p in pieces), 3)})

# ---- 16b. interior capsules behind every window / glazed door / curtain wall
D_STD, D_SKEW = 0.80, 0.92
SK_N = (SKD[1] / math.hypot(*SKD), -SKD[0] / math.hypot(*SKD))   # skew wall normal (either sign)
caps = []


def try_capsule(name, rim, zb, zt, depths, extra=None):
    last = None
    for D in depths:
        c = CAP.Capsule(rim, zb, zt, D, name)
        fs = c.faces()
        chk = SCN.conflicts(fs)
        last = (D, chk)
        if not (chk["overlap"] or chk["near"] or chk["added"]):
            for pts, nrm in fs:
                main.face(pts, ID_CAP, P43, nrm)
            SCN.accept(fs)
            caps.append(c)
            rec = c.record(OFF)
            rec.update({"faces": len(fs), "depth_wanted_m": depths[0]})
            if extra:
                rec.update(extra)
            ADD["capsules"].append(rec)
            return c
    ADD["capsules_skipped"].append({"name": name, "rim_build": [list(map(lambda x: round(x, 3), p)) for p in rim],
                                    "z": [zb, zt], "last_depth": last[0], "last_check": last[1]})
    return None


def fallback(D):
    return [D] + [d for d in (0.6, 0.45, 0.3, 0.2, 0.12) if d < D]


# specials (pilot И-А and the roof superstructure T2), numbers from build_pilot_ia.py / this script
_us = [uA_P + 0.025] + [c for c in U_P.cum if uA_P + 0.025 < c < uB_P - 0.025] + [uB_P - 0.025]
_rimU = [(b[0] - CAP.RIM * m[0], b[1] - CAP.RIM * m[1]) for b, m in ((U_P.base(u), U_P.normal(u)) for u in _us)]
try_capsule("P05 upper curtain wall (F50, glass rows 6.015-10.875)", _rimU, 6.015 - 0.025, 10.875 + 0.025, fallback(D_STD),
            {"rim_rule": "U outline - 7.5 mm (base 0 / glass 0.015)"})
for nm, ya, yb in (("P06 lower curtain wall S", -44.477, -33.487), ("P06 lower curtain wall N", -14.027, -2.937)):
    try_capsule(nm + " (with ELV-06 doors inset 0.33)", [(76.36 - CAP.RIM, ya + 0.025), (76.36 - CAP.RIM, yb - 0.025)],
                -G, 3.975 + 0.025, fallback(D_STD), {"rim_rule": "x 76.36 - 7.5 mm; floor G under the door thresholds"})
try_capsule("P07 entrance niche (ELV-16 + ELV-07 doors + revolving door ELV-17)",
            [(73.13 - CAP.RIM, -27.36 + 0.025), (73.13 - CAP.RIM, -20.11 - 0.025)], -G, 3.35 + 0.025, [2.30, 2.20],
            {"rim_rule": "x 73.13 - 7.5 mm; floor G under the drum glass; depth 2.30 > drum radius 2.06 (deviation)"})
_z0T2 = Z_PIT + G
try_capsule("P36 T2 glazed tower N + E (F50, ELV-06 door in E)",
            [(53.0 - CAP.RIM, -11.2 + G + 0.05 - 0.025), (53.0 - CAP.RIM, -6.2 - CAP.RIM), (48.3 + 0.05 - 0.025, -6.2 - CAP.RIM)],
            _z0T2 - G, 14.05 - 0.05 + 0.025, fallback(D_STD), {"rim_rule": "glazing - 7.5 mm, L-shaped rim"})

# every other glass cluster (new facades, pilot windows / doors, T1)
CL = CAP.glass_clusters(glass, part_ids_skip=("P35_Skylight", "P08_RevolvingDoor"))
for cl in sorted(CL, key=lambda c: c["area"]):
    probe = (cl["c"][0] - cl["n"][0] * 0.02, cl["c"][1] - cl["n"][1] * 0.02, cl["c"][2])
    host = next((c for c in caps if c.inside(probe)), None)
    if host is not None:
        ADD["glass_inside_capsule"].append({"glass_centre_delivered": [round(cl["c"][0] - OFF[0], 3),
                                                                       round(cl["c"][1] - OFF[1], 3), round(cl["c"][2], 3)],
                                            "capsule": host.name})
        continue
for cl in sorted(CL, key=lambda c: c["area"]):
    probe = (cl["c"][0] - cl["n"][0] * 0.02, cl["c"][1] - cl["n"][1] * 0.02, cl["c"][2])
    if any(c.inside(probe) for c in caps):
        continue
    skew = abs(cl["n"][0] * SK_N[0] + cl["n"][1] * SK_N[1]) > 0.9995
    D = D_SKEW if skew else D_STD
    c0 = (round(cl["c"][0] - OFF[0], 2), round(cl["c"][1] - OFF[1], 2), round(cl["c"][2], 2))
    try_capsule("glass %s n(%.2f,%.2f) %s" % (c0, cl["n"][0], cl["n"][1], "/".join(cl["parts"])), CAP.straight_rim(cl),
                cl["z"][0] - CAP.MARGIN, cl["z"][1] + CAP.MARGIN, fallback(D),
                {"glass_area_m2": cl["area"], "glass_faces": cl["faces"], "skew_wall": skew})
ADD["summary"] = {"strips_built": sum(1 for s in ADD["strips"] if s["built_len_m"] > 0),
                  "strips_len_m": round(sum(s["built_len_m"] for s in ADD["strips"]), 2),
                  "capsules": len(ADD["capsules"]), "capsules_skipped": len(ADD["capsules_skipped"]),
                  "capsules_short": [c["name"] for c in ADD["capsules"] if c["depth_m"] < c["depth_wanted_m"]]}
json.dump(ADD, open(ADD_OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ADD", json.dumps(ADD["summary"], ensure_ascii=False))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 1.0
mats = {i: material(n, COL.get(i, "#FF00FF")) for i, n in SLOTS.items()}
ob_main, bad_m = to_object(main, STEM_OUT + "_Main", mats)
ob_glass, bad_g = to_object(glass, STEM_OUT + "_MainGlass", {1: material("Glass_Clear", "#BFD9EE", 0.35)})
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("BUILD", json.dumps({"main_faces": len(ob_main.data.polygons), "glass_faces": len(ob_glass.data.polygons),
                           "rejected_faces": [len(bad_m), len(bad_g)], "rejected_sample": bad_m[:8],
                           "t_healed_faces": [HEALED, HEALED_G], "pilot_faces_removed": len(REMOVED),
                           "roof_cells": n_roof, "lights_faces": LREP["faces_added"], "lights_skipped": LREP["skipped"],
                           "lights_moved": LREP["moved"], "pilot": PILOT_LOG, "shelters": SHELTERS, "out": OUT}))
