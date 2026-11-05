"""elv-tc-vpm: build the WHOLE building VPM geometry (v003) = accepted pilot И-А (build-v001, unchanged) + new parts.

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b --factory-startup --python build_full_v003.py -- <out.blend>

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
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
JOB = os.path.abspath(os.path.join(HERE, ".."))
PILOT = os.path.join(JOB, "outputs", "build-v001", "elv_pilot_IA_v001.blend")
PARTS = json.load(open(os.path.join(JOB, "parts", "elv_full_parts_v001.json"), encoding="utf-8"))
PART_IDS = [p["id"] for p in PARTS["parts"]]
STEM = "SM_Elevatornaya_1A"
TYPES = {t["id"]: t for t in json.load(open(os.path.join(JOB, "..", "..", "library", "windows", "window_types.json"),
                                            encoding="utf-8"))["types"]}

SLOTS = {1: "ID01_Sandwich_7021", 2: "ID02_MetalCassette_7021", 3: "ID03_WoodCassette_1001", 4: "ID04_Plinth_7021",
         5: "ID05_TPAnnexPaint_7021", 6: "ID06_Reveal_7021", 7: "ID07_Reveal_1001", 8: "ID08_unused",
         9: "ID09_unused", 10: "ID10_unused", 11: "ID11_WindowW72_7021", 12: "ID12_FrameF50_7021",
         13: "ID13_Stemalit_5024", 14: "ID14_MetalDoor_7021", 15: "ID15_Gate_7040", 16: "ID16_SignFrame_7021",
         17: "ID17_Ribs_1001", 18: "ID18_Flashing_Zone", 19: "ID19_Canopy_1001", 20: "ID20_Metal_7021",
         21: "ID21_Roof", 22: "ID22_RoofStructures_7021", 23: "ID23_TerraceDeck", 24: "ID24_unused",
         25: "ID25_unused", 26: "ID26_DockShelter_9005", 27: "ID27_Light_Arktos"}
COL = {1: "#2F3234", 2: "#2F3234", 3: "#C2B078", 4: "#2F3234", 5: "#2F3234", 6: "#2F3234", 7: "#C2B078",
       11: "#2F3234", 12: "#2F3234", 13: "#5D9B9B", 14: "#2F3234", 15: "#9DA1AA", 16: "#2F3234", 17: "#C2B078",
       18: "#6E7F80", 19: "#C2B078", 20: "#2F3234", 21: "#8C8C88", 22: "#45494B", 23: "#7A6F63", 26: "#0A0A0A",
       27: "#E8E8E0"}

main, glass = MB4(), MB4()
Z_DROP, Z_TOP, Z_CAP, Z_ROOF, Z_PIT = -1.0, 13.92, 14.04, 12.45, 11.46
Z_T1, Z_T2 = 15.42, 16.22
T_PAR, CAP_OUT = 0.40, 0.05


# ================================================================= 1. pilot (accepted, build-v001) -> MB
def import_pilot():
    with bpy.data.libraries.load(PILOT, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(STEM)]
    removed = []
    for ob in dst.objects:
        mb = main if ob.name.endswith("_Main") else glass
        ids = json.loads(ob["part_ids"])
        me = ob.data
        att = me.attributes.get("part_idx")
        for p in me.polygons:
            pts = [tuple(me.vertices[i].co) for i in p.vertices]
            n = p.normal
            # joint end caps of plinth / base flashing (continued by the new plinth): x 41.88 S and x 59.43 N
            if mb is main and n.x < -0.9 and (
                    (all(abs(q[0] - 41.88) < 2e-3 and -50.70 < q[1] < -50.60 for q in pts) and max(q[2] for q in pts) < 0.41) or
                    (all(abs(q[0] - 59.43) < 2e-3 and 3.13 < q[1] < 3.23 for q in pts) and max(q[2] for q in pts) < 0.41)):
                removed.append([[round(c, 3) for c in q] for q in pts])
                continue
            mb.face(pts, p.material_index + 1 if mb is main else 1, ids[att.data[p.index].value])
        bpy.data.objects.remove(ob)
    return removed


REMOVED = import_pilot()
assert len(REMOVED) == 11, len(REMOVED)   # 5 south + 6 north end caps

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


def plinth_regs(u0, u1, part_p="P25_Plinth_Flashing_New"):
    return [(u0, u1, Z_DROP, 0.40, Cell(0.20, 4, 4, part_p)), (u0, u1, 0.13, 0.40, Cell(0.23, 18, 18, part_p))]


VOID = Cell(0.0, None, None, None)

# ----------------------------------------------------------------- G_N: north straight x 59.43 -> x_nc (to +15.42)
u_a, u_b = 0.0, uv[1]
regs = [(u_a, u_b, Z_DROP, Z_T1, Cell(0.0, 1, 1, "P24_N_Facade"))]
regs += plinth_regs(u_a, u_b)
regs.append((0.0, u_n0, 4.70, Z_T1, VOID))
door(regs, (51.728, 2.99), 0.0, "ELV-08")
for z0 in (2.85, 6.90, 10.50):
    window(regs, (57.793, 2.99), z0, "ELV-01")
relief(main, glass, W, u_a, u_b, [Z_DROP, 0.13, 0.40, 2.55, 4.70, 7.78, 10.84, Z_TOP, Z_T1], regs, Cell(0.0, 1, 1, "P24_N_Facade"),
       ulines=splits(W, u_a, u_b, 3.6), omit=("left", "right", "bottom", "top"))

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
door(regs, (-2.0385, y), 0.30, w=1.26, h=2.05)                          # FBX In-1H 1100x2050, no ELV type yet
# TP annex x -8.82: ELV-11 x2 (z 0.30), single door 1.25 x 2.25 (no ELV type)
for cy in (-7.187, -4.322):
    door(regs, (-8.82, cy), 0.30, "ELV-11", part="P23_TP_Annex")
door(regs, (-8.82, -9.647), 0.30, w=1.25, h=2.25, part="P23_TP_Annex")
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
door(regs, (-0.42, -40.542), 0.0, w=1.05, h=2.05)
relief(main, glass, W, u_a, u_b, [Z_DROP, 0.0, 0.13, 0.40, 2.55, 4.70, 7.78, 10.84, Z_TOP], regs, Cell(0.0, 1, 1, "P22_W_Facade"),
       ulines=splits(W, u_a, u_b, 3.6), omit=("left", "right", "bottom", "top"))

# ----------------------------------------------------------------- G_S: south 1-12 rest, x -0.42 -> 41.88
u_a, u_b = uv[7], L_W
regs = [(u_a, u_b, Z_DROP, Z_TOP, Cell(0.0, 1, 1, "P21_S_Facade"))]
regs += plinth_regs(u_a, u_b)
regs.append((u_s1, L_W, 4.70, Z_TOP, VOID))
for cx in (4.289, 13.189, 34.929):
    door(regs, (cx, -50.46), 0.0, "ELV-08")
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
       ulines=splits(W, u_a, u_b, 3.6), omit=("left", "right", "bottom", "top"))

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
    z0 -= 0.01                     # frame/glass/door bottoms 1 cm under the pit floor (no coplanar / bow-ties)
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


glaze((47.8, YI), (47.8, 0.0), Z_PIT, 14.05, Z_T1, P)                           # T1 west glazing (faces the pit)
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
glaze((53.0, -11.2), (53.0, -6.2), Z_PIT, 14.05, Z_T2, P, door_at=-9.014 + 11.2)  # east glazing + ELV-06 door
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
    zlo = Z_PIT - 0.01 if i == 0 else zs[i - 1]
    wall(main, (xs[i], -8.51), (xs[i], -11.0), zlo, zs[i], 22, S, (-1, 0))
    wall(main, (xs[i], -11.0), (xs[i + 1], -11.0), Z_PIT - 0.01, zs[i], 22, S, (0, -1))
    wall(main, (xs[i + 1], -8.51), (xs[i], -8.51), Z_PIT - 0.01, zs[i], 22, S, (0, 1))
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
wall(main, (OX0, OY0), (OX1, OY0), Z_ROOF - 0.01, Z_EAVE, 12, K, (0, -1))
wall(main, (OX1, OY0), (OX1, OY1), Z_ROOF - 0.01, Z_EAVE, 12, K, (1, 0))
wall(main, (OX1, OY1), (OX0, OY1), Z_ROOF - 0.01, Z_EAVE, 12, K, (0, 1))
wall(main, (OX0, OY1), (OX0, OY0), Z_ROOF - 0.01, Z_EAVE, 12, K, (-1, 0))
wall(main, (SX1, SY0), (SX0, SY0), Z_ROOF - 0.01, Z_EAVE, 12, K, (0, 1))
wall(main, (SX0, SY0), (SX0, SY1), Z_ROOF - 0.01, Z_EAVE, 12, K, (1, 0))
wall(main, (SX0, SY1), (SX1, SY1), Z_ROOF - 0.01, Z_EAVE, 12, K, (0, -1))
wall(main, (SX1, SY1), (SX1, SY0), Z_ROOF - 0.01, Z_EAVE, 12, K, (-1, 0))
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
for xe, xr, ye in ((SX0, RX0, SY0), (SX0, RX0, SY1), (SX1, RX1, SY0), (SX1, RX1, SY1)):
    p0, p1 = (xe, ye, Z_EAVE), (xr, YR, Z_RIDGE)
    ax = (p1[0] - p0[0], p1[1] - p0[1], 0.0)
    side = (-ax[1], ax[0], 0.0)
    obox(main, on_slope(p0, (0, 0, 1)), on_slope(p1, (0, 0, 1)), side, FR, FR, 12, K, skip=("-u",))
for x in RXS[1:-1]:
    for ye, nrm in ((SY0, (0, -HW, Z_RIDGE - Z_EAVE)), (SY1, (0, HW, Z_RIDGE - Z_EAVE))):
        p0, p1 = on_slope((x, ye, Z_EAVE), nrm), on_slope((x, YR, Z_RIDGE), nrm)
        # up = axis x (1,0,0) points down on the south slope, up on the north slope: drop the face on the glass
        obox(main, p0, p1, (1, 0, 0), FR, FR, 12, K, skip=("+u", "end") if ye == SY0 else ("-u", "end"))

# ================================================================= 8. roof structures: curbs, shafts, cups (P37)
S = "P37_RoofBoxes"
CURB = 12.85


def curb_ring(x0, x1, y0, y1, w=0.32, open_west=False):
    """curb ring (outer rect, width w) as faces only: tops, outer and inner walls; embedded 1 cm into the roof"""
    zb = Z_ROOF - 0.01
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
# zone A (x 0..33.6, y -44.73..-27.94): its west side is the parapet; zone B (x -0.22..33.6, y -19.53..-2.74): ring
curb_ring(XW, 33.595, -44.727, -27.937, open_west=True)
curb_ring(-0.22, 33.595, -19.527, -2.737)
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
for x0, x1, y0, y1, zt in SHAFTS:
    sk = ("z0", "x1") if x1 > 42.0 and x0 < 42.0 else ("z0",)    # the box at the pit wall is embedded 1 cm
    box(main, x0, x1, y0, y1, Z_ROOF - 0.01, zt, 22, S, skip=sk)
CUPS = [(36.61, 37.20, -41.54, -40.95), (37.60, 38.19, -41.54, -40.95), (40.76, 41.35, -41.42, -40.83),
        (41.75, 42.34, -41.42, -40.83), (44.98, 45.84, -47.20, -46.35), (46.53, 47.12, -47.07, -46.48),
        (50.48, 51.34, -47.20, -46.35), (52.03, 52.62, -47.07, -46.48), (54.51, 55.36, -47.20, -46.35),
        (56.06, 56.65, -47.07, -46.48), (58.88, 59.73, -47.20, -46.35), (60.44, 61.02, -47.07, -46.48),
        (63.41, 64.26, -47.20, -46.35), (64.96, 65.55, -47.07, -46.48), (67.66, 68.85, -47.52, -46.33),
        (67.96, 68.55, -48.81, -48.22)]
for x0, x1, y0, y1 in CUPS:
    box(main, x0, x1, y0, y1, Z_ROOF - 0.01, 12.76, 22, S, skip=("z0",))

# ================================================================= 9. terrace: screens (ID1) and railings (ID20)
T = "P33_Terrace"
R = "P34_Railings"
Z_FENCE = 13.85
box(main, 62.65, 74.62, -19.215, -19.115, Z_ROOF - 0.01, Z_FENCE, 1, T, skip=("z0",))
box(main, 50.605, 50.705, -19.215, -15.60, Z_ROOF - 0.01, Z_FENCE, 1, T, skip=("z0",))


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
        obox(main, (x, y, z0 - 0.01), (x, y, ztop - 0.02), side, post, post, 20, R, skip=("start", "end"))
    zr = ztop - 0.02
    sk = tuple(k for k, f in (("start", skip_start), ("end", skip_end)) if f)
    obox(main, (p0[0], p0[1], zr), (p1[0], p1[1], zr), (0, 0, 1), 0.04, post + 0.02, 20, R, skip=sk)


railing((50.695, -19.165), (62.66, -19.165), Z_ROOF, Z_FENCE - 0.03, post=0.06, skip_start=True, skip_end=True)  # Rabitz fence
railing((50.655, -15.61), (50.655, -11.44), Z_ROOF, Z_FENCE - 0.03, post=0.06, skip_start=True, skip_end=True)
railing((58.74, -8.45), (58.74, -1.49), Z_ROOF, Z_ROOF + 1.10, skip_end=True)                          # pit edge

# ================================================================= 10. canopies (ID19), lamellas (ID17), downpipes (ID20)
C = "P29_Canopies_New"
box(main, 10.33, 17.42, -51.707, -50.45, 2.71, 3.09, 19, C, skip=("y1",))      # D14: slab missing in FBX
box(main, 25.227, 29.015, -51.957, -50.45, 2.50, 3.09, 19, C, skip=("y1",))
box(main, 33.557, 36.545, -51.707, -50.45, 2.71, 3.09, 19, C, skip=("y1",))     # D14: slab missing in FBX
box(main, -1.645, -0.41, -23.452, -19.94, 2.70, 2.75, 19, C, skip=("x1", "y1"))  # west door canopy
LM = "P30_Lamellas_New"
for x in (10.654, 10.904, 11.154, 11.404, 11.654, 11.904, 12.154, 14.174, 14.424, 14.674, 14.924, 16.604, 16.854,
          17.104, 17.354, 33.623, 33.894, 35.915, 36.165, 36.415):
    box(main, x, x + 0.05, -50.657, -50.45, 0.20, 2.72, 17, LM, skip=("y1", "z1"))
for x in (25.764, 28.385, 28.635, 28.885):
    box(main, x, x + 0.05, -50.657, -50.45, 0.20, 2.51, 17, LM, skip=("y1", "z1"))
for y in (-23.130, -22.880, -22.631, -22.381, -20.247):
    box(main, -0.575, -0.41, y, y + 0.05, 0.20, 2.71, 17, LM, skip=("x1", "z1"))
D = "P39_Downpipes"
for x, ztop in ((10.455, 2.72), (25.51, 2.51), (33.64, 2.72)):
    box(main, x - 0.05, x + 0.05, -51.00, -50.90, 0.10, ztop, 20, D, skip=("z1",))
box(main, -0.82, -0.72, -23.38, -23.28, 0.10, 2.71, 20, D, skip=("z1",))

# ================================================================= 11. sign frame SW (ID16), Arktos boxes (ID27)
SF = Cell(0.06, 16, 16, "P21_S_Facade")
pl = Poly([(-0.025, -50.478), (1.975, -50.478)])
relief(main, None, pl, 0.0, pl.length, [3.0, 3.5], [(0.06, pl.length - 0.06, 3.06, 3.44, Cell(0.0, None, 16,
       "P21_S_Facade"))], SF, ulines=splits(pl, 0, pl.length))
A = "P40_Arktos"
for x0, x1, z0, z1 in ((20.862, 21.462, 4.75, 5.22), (24.163, 24.763, 4.75, 5.22), (25.625, 26.225, 4.75, 5.22),
                       (32.563, 33.263, 4.70, 5.27)):
    box(main, x0, x1, -50.62, -50.45, z0, z1, 27, A, skip=("y1",))
skn = W.n[1]
skt = W.t[1]
for cx in (-2.966, -1.134):
    b = (SK0[0] + SKD[0] * (cx - SK0[0]) / SKD[0], SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0])
    for zc in (4.90,):
        p0 = (b[0] - skt[0] * 0.25 + skn[0] * 0.04, b[1] - skt[1] * 0.25 + skn[1] * 0.04, zc)
        p1 = (b[0] + skt[0] * 0.25 + skn[0] * 0.04, b[1] + skt[1] * 0.25 + skn[1] * 0.04, zc)
        obox(main, p0, p1, (skn[0], skn[1], 0), 0.10, 0.40, 27, A, skip=("-s",))

# ================================================================= 12. fire ladders (simplified, ID20)
LD = "P38_FireLadders"


def ladder(base, t, n, z0=1.40, z1=15.00, half=0.40, off=0.20):
    """two stringers 60x60 at +-half along t, 'off' from the wall face, rungs 30x30 every 0.35, 4 bracket pairs"""
    for s in (-1, 1):
        c = (base[0] + t[0] * s * half + n[0] * (off + 0.03), base[1] + t[1] * s * half + n[1] * (off + 0.03))
        obox(main, (c[0], c[1], z0), (c[0], c[1], z1), (t[0], t[1], 0), 0.06, 0.06, 20, LD)
        for zb in (3.0, 6.0, 9.0, 12.0):
            p0 = (base[0] + t[0] * s * half - n[0] * 0.01, base[1] + t[1] * s * half - n[1] * 0.01, zb)
            p1 = (base[0] + t[0] * s * half + n[0] * (off + 0.01), base[1] + t[1] * s * half + n[1] * (off + 0.01), zb)
            obox(main, p0, p1, (0, 0, 1), 0.04, 0.04, 20, LD, skip=("start", "end"))
    z = z0 + 0.35
    while z < z1 - 0.2:
        c0 = (base[0] - t[0] * (half - 0.02) + n[0] * (off + 0.03), base[1] - t[1] * (half - 0.02) + n[1] * (off + 0.03), z)
        c1 = (base[0] + t[0] * (half - 0.02) + n[0] * (off + 0.03), base[1] + t[1] * (half - 0.02) + n[1] * (off + 0.03), z)
        obox(main, c0, c1, (0, 0, 1), 0.03, 0.03, 20, LD, skip=("start", "end"))
        z += 0.35


for cx in (33.70, 8.40):                                   # north 6-1 at axes 7 and 4 (sheet 19)
    b = (cx, SK0[1] + SKD[1] * (cx - SK0[0]) / SKD[0])
    ladder(b, (-skt[0], -skt[1]), skn)
ladder((-0.42, -47.233), (0.0, 1.0), (-1.0, 0.0))          # west near Ж-И (parapet gap y -47.75..-46.71 in FBX)

# ================================================================= 13. dock shelters DS_403M simplified (ID26)
G = "P28_Gates_DockShelters"
XF, XB, WP, ZG, ZD = -0.925, -0.41, 0.25, 4.05, 4.5   # 3 cm wider / 5 cm higher than the gate opening (no coplanar reveals)
for y0, y1 in ((-39.907, -36.607), (-35.957, -32.457), (-31.807, -28.307), (-27.607, -24.107)):
    y0, y1 = y0 - 0.03, y1 + 0.03
    ya, yb = y0 + WP, y1 - WP
    for p, q, za, zb in ((y0, ya, 0.0, ZG), (yb, y1, 0.0, ZG), (y0, ya, ZG, ZD), (ya, yb, ZG, ZD), (yb, y1, ZG, ZD)):
        wall(main, (XF, p), (XF, q), za, zb, 26, G, (-1, 0))
    wall(main, (XF, y0), (XB, y0), 0.0, ZD, 26, G, (0, -1))
    wall(main, (XF, y1), (XB, y1), 0.0, ZD, 26, G, (0, 1))
    wall(main, (XF, ya), (XB, ya), 0.0, ZG, 26, G, (0, 1))
    wall(main, (XF, yb), (XB, yb), 0.0, ZG, 26, G, (0, -1))
    hrect(main, XF, XB, ya, yb, ZG, 26, G, up=False)
    hrect(main, XF, XB, y0, y1, ZD, 26, G)


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
    ob["build"] = ("jobs/elv-tc-vpm/scripts/build_full_v003.py; pilot build-v001 (accepted) + new parts "
                   "parts/elv_full_parts_v001.json (Gate 1 pending, pattern of the accepted pilot)")
    return ob, bad


HEALED = heal_t(main, tol=2e-4)
HEALED_G = heal_t(glass, tol=2e-4)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 1.0
mats = {i: material(n, COL.get(i, "#FF00FF")) for i, n in SLOTS.items()}
ob_main, bad_m = to_object(main, STEM + "_Main", mats)
ob_glass, bad_g = to_object(glass, STEM + "_MainGlass", {1: material("Glass_Clear", "#BFD9EE", 0.35)})
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("BUILD", json.dumps({"main_faces": len(ob_main.data.polygons), "glass_faces": len(ob_glass.data.polygons),
                           "rejected_faces": [len(bad_m), len(bad_g)], "rejected_sample": bad_m[:8],
                           "t_healed_faces": [HEALED, HEALED_G], "pilot_faces_removed": len(REMOVED),
                           "roof_cells": n_roof, "out": OUT}))
