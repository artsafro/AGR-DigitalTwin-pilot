"""elv-tc-vpm: build the pilot И-А VPM geometry (east facade + S/N returns) from measurements.

"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" -b --factory-startup --python build_pilot_ia.py -- <out.blend>

Inputs (all numbers below are measured, metres, FBX world coordinates of elv_ref_clean_v001.blend):
  parts/pilot_IA_parts_v002.json (Gate 1 confirmed 2026-11-04, F50 caps = geometry);
  outputs/ref-v001/pilot_IA_measure_v001.json; outputs/build-v001/sections/ref_sections_v001.json (plan/vertical
  cuts: CW arc facets, mullion lines, door jambs, lamella positions); library/windows/window_types.json ELV-04/06/07/
  08/09/16/17.
Outputs: SM_Elevatornaya_1A_Main (material slots ID01..ID21, ID = slot index + 1, face attribute part_idx) and
  SM_Elevatornaya_1A_MainGlass (flat glass). No UV / textures (next stage).
Tolerance rule (user): deviations within 1 cm are ignored.
"""
import bpy, bmesh, sys, os, json, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pilot_geom import MB, Poly, Cell, relief, arc, splits, box, heal_t  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
if os.path.exists(OUT):
    raise SystemExit("output exists: " + OUT)
JOB = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PARTS = json.load(open(os.path.join(JOB, "parts", "pilot_IA_parts_v002.json"), encoding="utf-8"))
PART_IDS = [p["id"] for p in PARTS["parts"]]
STEM = "SM_Elevatornaya_1A"

# ---------------------------------------------------------------- material IDs (standards/material_id_ranges.yaml)
SLOTS = {1: "ID01_Sandwich_7021", 2: "ID02_MetalCassette_7021", 3: "ID03_WoodCassette_1001", 4: "ID04_Plinth_7021",
         5: "ID05_unused", 6: "ID06_Reveal_7021", 7: "ID07_Reveal_1001", 8: "ID08_unused", 9: "ID09_unused",
         10: "ID10_unused", 11: "ID11_WindowW72_7021", 12: "ID12_FrameF50_7021", 13: "ID13_Stemalit_5024",
         14: "ID14_MetalDoor_7021", 15: "ID15_unused", 16: "ID16_SignFrame_7021", 17: "ID17_Ribs_1001",
         18: "ID18_Flashing_Zone", 19: "ID19_Canopy_1001", 20: "ID20_unused", 21: "ID21_Roof"}
RAL = {"7021": "#2F3234", "1001": "#C2B078", "5024": "#5D9B9B", "roof": "#8C8C88", "unused": "#FF00FF",
       "flash": "#6E7F80"}
SLOT_COL = {1: "7021", 2: "7021", 3: "1001", 4: "7021", 6: "7021", 7: "1001", 11: "7021", 12: "7021", 13: "5024",
            14: "7021", 16: "7021", 17: "1001", 18: "flash", 19: "1001", 21: "roof"}

main, glass = MB(), MB()
Z_SOF, Z_TOP, Z_CAP, Z_ROOF, Z_DROP = 4.70, 13.92, 14.04, 12.45, -1.0
CAP_OUT, PARAPET_T = 0.16, 0.52

# ================================================================= upper outline U (wood + CW), walked S -> E -> N
ARC_ANG = [0, 4.9, 10.5, 16.0, 21.6, 27.2, 32.8, 38.3, 43.9, 49.5, 55.1, 60.7, 66.3, 71.8, 77.4, 83.0, 87.6]
U_pts = [(41.85, -50.76)]
U_pts += arc(75.88, -47.61, 3.15, -90, 0, n=10)                       # SE wood corner R 3.15, 10 facets
U_pts += arc(75.92, -30.33, 3.11, 0, 0, angles=ARC_ANG)               # S CW arc R 3.11 (source facets)
U_pts += arc(75.92, -17.13, 3.11, 0, 0, angles=[-a for a in reversed(ARC_ANG)])
U_pts += arc(75.88, 0.14, 3.15, 0, 90, n=10)                          # NE wood corner
U_pts += [(59.40, 3.29)]
U = Poly(U_pts)
uA, uB = U.project((79.03, -42.885)), U.project((79.03, -4.575))      # wood | CW | wood


def ucol(p):
    return U.project(p)


S_FLAT = [-42.86, -41.70, -40.51, -39.32, -38.13, -36.94, -35.75, -34.56, -33.37, -32.18, -31.41, -31.06, -30.71]
N_FLAT = [-16.75, -16.40, -16.05, -15.29, -14.10, -12.91, -11.72, -10.53, -9.34, -8.15, -6.96, -5.77, -4.60]
BAY = [-26.707, -25.517, -24.327, -23.137, -21.947, -20.757]
cols = []  # (u, rib?)
cols += [(ucol((79.03, y)), True) for y in S_FLAT]
ks = U.p.index(min(U.p, key=lambda q: math.hypot(q[0] - 79.03, q[1] + 30.33)))
kc1 = ks + len(ARC_ANG) - 1                                          # S bay corner vertex
cols += [(U.cum[k], True) for k in range(ks, kc1)] + [(U.cum[kc1], False)]
cols += [(ucol((76.05, y)), False) for y in BAY]
kc2 = kc1 + 1                                                        # N bay corner vertex
cols += [(U.cum[kc2], False)] + [(U.cum[k], True) for k in range(kc2 + 1, kc2 + len(ARC_ANG))]
cols += [(ucol((79.03, y)), True) for y in N_FLAT]
cols.sort()
assert abs(cols[0][0] - 0.025 - uA) < 1e-6 and abs(cols[-1][0] + 0.025 - uB) < 1e-6, (cols[0][0] - uA, uB - cols[-1][0])
W = 0.025
rib_dirs = [(u - W, u + W, U.unit_normal(u)) for u, r in cols if r]

ZU = [4.70, 4.75, 5.965, 6.015, 7.595, 7.645, 9.225, 9.275, 10.875, 10.925, 13.87, 13.90, 13.92]
STEM_CELLS = [(4.75, 5.965), (10.925, 13.87)]
GLASS_ROWS = [(6.015, 7.595), (7.645, 9.225), (9.275, 10.875)]
frame_up = Cell(0.02, 12, 12, "P05_CW_Upper")
regs = []
for (ua, _), (ub, _) in zip(cols, cols[1:]):
    a, b = ua + W, ub - W
    for z0, z1 in STEM_CELLS:
        regs.append((a, b, z0, z1, Cell(-0.01, 13, 12, "P05_CW_Upper")))
    for z0, z1 in GLASS_ROWS:
        regs.append((a, b, z0, z1, Cell(-0.015, None, 12, "P05_CW_Upper", glass=True)))
for u, r in cols:
    if r:
        regs.append((u - W, u + W, 4.70, 13.90, Cell(0.44, 17, 17, "P10_Ribs", rib=True)))
Ucw, _, _ = relief(main, glass, U, uA, uB, ZU, regs, frame_up, omit=("top",), rib_dirs=rib_dirs)

wood = Cell(0.0, 3, 3, "P01_WoodVolume")
ZW = [4.70, 7.78, 10.84, 13.92]
UwS, _, _ = relief(main, None, U, 0.0, uA, ZW, [], wood, ulines=splits(U, 0.0, uA))
UwN, _, _ = relief(main, None, U, uB, U.length, ZW, [], wood, ulines=splits(U, uB, U.length))

# ================================================================= lower outline L (metal / CW / niche)
L_pts = [(41.88, -50.61)]
L_pts += arc(74.40, -48.83, 1.77, -90, 0, n=8)
L_pts += [(76.17, -44.477), (76.36, -44.477), (76.36, -33.487), (76.17, -33.487)]
L_pts += arc(74.40, -29.13, 1.77, 0, 90, n=8)
L_pts += [(73.13, -27.36), (73.13, -20.11)]
L_pts += arc(74.40, -18.34, 1.77, -90, 0, n=8)
L_pts += [(76.17, -14.027), (76.36, -14.027), (76.36, -2.937), (76.17, -2.937)]
L_pts += arc(74.40, 1.37, 1.77, 0, 90, n=8)
L_pts += [(59.43, 3.14)]
L = Poly(L_pts)
lu = lambda p: L.project(p)  # noqa: E731

plinth = Cell(0.05, 4, 4, "P03_Plinth")
flash = Cell(0.08, 18, 18, "P13_BaseFlashing")
plinth_flat = Cell(0.0, 4, 4, "P03_Plinth")
ZM = [Z_DROP, 0.13, 0.40, 2.55, 4.70]
TYPES = {t["id"]: t for t in json.load(open(os.path.join(JOB, "..", "..", "library", "windows", "window_types.json"),
                                            encoding="utf-8"))["types"]}


def panes(u0, z0, width, tid, hand, h, part):
    """library panes (bottom-left of the frame) -> glass cells; hand 'R' mirrors the type"""
    out = []
    for x0, y0, x1, y1 in TYPES[tid]["panes_m"] or []:
        if hand == "R":
            x0, x1 = width - x1, width - x0
        out.append((u0 + x0, u0 + x1, z0 + y0, z0 + y1, Cell(h, None, 12 if part == "P09_GlassDoors" else
                                                             (11 if part == "P16_Windows" else 14), part, glass=True)))
    return out


def metal_regions(u0, u1, flash_from, flash_to, ret=(), niche=None, part_metal="P02_MetalBase"):
    r = [(u0, u1, Z_DROP, 0.22, plinth)]
    if flash_from is not None:
        r.append((flash_from, flash_to, 0.13, 0.40, flash))
    if niche:
        r.append((niche[0], niche[1], 0.22, 4.70, Cell(0.0, 2, 2, "P07_EntranceNiche")))
    for a, b in ret:
        r += [(a, b, Z_DROP, 0.22, plinth_flat), (a, b, 0.22, 4.70, Cell(0.0, 2, 2, part_metal))]
    return r


metal = Cell(0.0, 2, 2, "P02_MetalBase")
# M1: S return + SE arc + E to the CW-S return (windows ELV-04 on the south)
m1a, m1b, m1c = 0.0, lu((76.17, -44.477)), lu((76.36, -44.477))
regs = metal_regions(m1a, m1c, m1a, m1b, ret=[(m1b, m1c)])
for x0 in (54.12, 61.12):
    u0 = lu((x0, -50.61))
    regs.append((u0, u0 + 0.98, 0.81, 1.99, Cell(-0.11, 11, 6, "P16_Windows")))
    regs += panes(u0, 0.81, 0.98, "ELV-04", "L", -0.125, "P16_Windows")
Um1, _, _ = relief(main, glass, L, m1a, m1c, ZM, regs, metal, ulines=splits(L, m1a, m1c), omit=("bottom",))
# M2: return + E + niche S wall (no flashing in the niche)
m2a, m2b, m2c, m2d = lu((76.36, -33.487)), lu((76.17, -33.487)), lu((76.17, -29.13)), lu((73.13, -27.36))
regs = metal_regions(m2a, m2d, m2b, m2c, ret=[(m2a, m2b)], niche=(m2c, m2d))
Um2, _, _ = relief(main, None, L, m2a, m2d, ZM, regs, metal, ulines=splits(L, m2a, m2d), omit=("right", "bottom"))
# M3: niche N wall + E + return
m3a, m3b, m3c, m3d = lu((73.13, -20.11)), lu((76.17, -18.34)), lu((76.17, -14.027)), lu((76.36, -14.027))
regs = metal_regions(m3a, m3d, m3b, m3c, ret=[(m3c, m3d)], niche=(m3a, m3b))
Um3, _, _ = relief(main, None, L, m3a, m3d, ZM, regs, metal, ulines=splits(L, m3a, m3d), omit=("left", "bottom"))
# M4: return + E + NE arc + N return (doors ELV-08 / ELV-09)
m4a, m4b, m4c = lu((76.36, -2.937)), lu((76.17, -2.937)), L.length
regs = metal_regions(m4a, m4c, m4b, m4c, ret=[(m4a, m4b)])
for xl, xr, tid in ((61.54, 59.74, "ELV-08"), (69.00, 67.60, "ELV-09")):
    u0, w = lu((xl, 3.14)), xl - xr
    regs.append((u0, u0 + w, 0.0, 2.05, Cell(-0.20, 14, 6, "P17_MetalDoors_N")))
    regs += panes(u0, 0.0, w, tid, "L", -0.215, "P17_MetalDoors_N")
Um4, _, _ = relief(main, glass, L, m4a, m4c, ZM, regs, metal, ulines=splits(L, m4a, m4c), omit=("bottom",))


# ----------------------------------------------------------------- lower E curtain walls (ELV-15 + ELV-06 doors)
def cw_lower(ya, yb, bottom, upper, doors):
    u0, u1 = lu((76.36, ya)), lu((76.36, yb))
    y2u = lambda y: u0 + (y - ya)  # noqa: E731
    regs = []
    ZL = [0.0, 0.05, 2.075, 2.125, 3.975, 4.025, 4.645, 4.70]
    for (c0, c1) in zip(bottom, bottom[1:]):
        regs.append((y2u(c0[1]), y2u(c1[0]), 0.05, 2.075, Cell(-0.015, None, 12, "P06_CW_Lower", glass=True)))
    for (c0, c1) in zip(upper, upper[1:]):
        regs.append((y2u(c0[1]), y2u(c1[0]), 2.125, 3.975, Cell(-0.015, None, 12, "P06_CW_Lower", glass=True)))
        regs.append((y2u(c0[1]), y2u(c1[0]), 4.025, 4.645, Cell(-0.01, 13, 12, "P06_CW_Lower")))
    for da, db, hand in doors:
        a, b = y2u(da), y2u(db)
        regs.append((a, b, 0.0, 2.075, Cell(-0.33, 12, 6, "P09_GlassDoors")))
        regs += panes(a + 0.05, 0.0, 1.70, "ELV-06", hand, -0.345, "P09_GlassDoors")
    # 1 m perimeter drop under the CW in the CW base plane (as in the niche); the source plinth line x 76.22
    # behind the glass is not built (it would meet the returns with non-manifold edges)
    regs.insert(0, (u0, u1, Z_DROP, 0.0, Cell(0.0, 4, 4, "P03_Plinth")))
    relief(main, glass, L, u0, u1, [Z_DROP] + ZL, regs, Cell(0.02, 12, 12, "P06_CW_Lower"), omit=("top",))
    return [L.base(u0), L.base(u1)]


def mull(c, w=0.05):
    return (c - w / 2, c + w / 2)


# measured mullion lines (sections z=1.0 / z=3.0): bottom row has door jambs, upper rows the 1190 module
Lcw_S = cw_lower(-44.477, -33.487,
                 [(-44.477, -44.427)] + [mull(c) for c in (-44.077, -43.547, -41.697, -40.507, -39.317, -38.127,
                                                           -36.937, -35.747, -33.897)] + [(-33.537, -33.487)],
                 [(-44.477, -44.427)] + [mull(c) for c in (-44.077, -42.887, -41.697, -40.507, -39.317, -38.127,
                                                           -36.937, -35.747, -34.557)] + [(-33.537, -33.487)],
                 [(-43.522, -41.722, "L"), (-35.722, -33.922, "R")])
Lcw_N = cw_lower(-14.027, -2.937,
                 [(-14.027, -13.927)] + [mull(c) for c in (-13.567, -11.717, -10.527, -9.337, -8.147, -6.957,
                                                           -5.767, -3.917, -3.387)] + [(-3.037, -2.937)],
                 [(-14.027, -13.927)] + [mull(c) for c in (-12.907, -11.717, -10.527, -9.337, -8.147, -6.957,
                                                           -5.767, -4.577, -3.387)] + [(-3.037, -2.937)],
                 [(-13.542, -11.742, "L"), (-5.742, -3.942, "R")])

# ----------------------------------------------------------------- entrance niche CW (ELV-16) + ELV-07 + opening
n0, n1 = lu((73.13, -27.36)), lu((73.13, -20.11))
ue = lambda x: n0 + 0.05 + x  # noqa: E731  ELV-16 local u (from y -27.31)
regs = [(n0, n1, Z_DROP, 0.0, Cell(0.0, 4, 4, "P03_Plinth"))]
SEVEN = [(0, 1.42), (1.47, 1.685), (1.735, 2.955), (3.005, 4.145), (4.195, 5.421), (5.471, 5.68), (5.73, 7.15)]
for z0, z1 in ((2.2, 2.335), (2.385, 2.718)):
    for a, b in ((0, 1.42), (5.73, 7.15)):
        regs.append((ue(a), ue(b), z0, z1, Cell(-0.015, None, 12, "P07_EntranceNiche", glass=True)))
for a, b in SEVEN:
    regs.append((ue(a), ue(b), 2.768, 3.35, Cell(-0.015, None, 12, "P07_EntranceNiche", glass=True)))
    regs.append((ue(a), ue(b), 3.40, 4.00, Cell(-0.01, 2, 12, "P07_EntranceNiche")))
for a, b in ((0, 1.765), (1.815, 2.955), (3.005, 4.145), (4.195, 5.335), (5.385, 7.15)):
    regs.append((ue(a), ue(b), 4.05, 4.65, Cell(-0.01, 13, 12, "P07_EntranceNiche")))
for a, b, hand in ((0.0, 1.42, "L"), (5.73, 7.15, "R")):
    regs.append((ue(a), ue(b), 0.0, 2.15, Cell(-0.05, 12, 6, "P09_GlassDoors")))
    regs += panes(ue(a) + 0.01, 0.0, 1.40, "ELV-07", hand, -0.065, "P09_GlassDoors")
regs.append((ue(1.47), ue(5.68), 0.0, 2.718, Cell(-0.10, None, 6, "P07_EntranceNiche")))  # revolving door opening
ZN = [Z_DROP, 0.0, 2.15, 2.2, 2.335, 2.385, 2.718, 2.768, 3.35, 3.40, 4.00, 4.05, 4.65, 4.70]
relief(main, glass, L, n0, n1, ZN, regs, Cell(0.02, 12, 12, "P07_EntranceNiche"), omit=("top",))

# ----------------------------------------------------------------- revolving door ELV-17 (centre on the niche CW)
RC = (73.13, -20.11 - 0.05 - 7.15 + (1.735 + 5.421) / 2)   # = (73.13, -23.732)
R_OUT, R_IN, Z_DOOR, Z_CAN = 2.06, 1.84, 2.19, 2.71
ring = arc(RC[0], RC[1], R_OUT, 0, 360, n=32)[:-1]
for i in range(32):
    a, b = ring[i], ring[(i + 1) % 32]
    mid = ((a[0] + b[0]) / 2 - RC[0], (a[1] + b[1]) / 2 - RC[1], 0)
    main.face([(a[0], a[1], Z_DOOR), (b[0], b[1], Z_DOOR), (b[0], b[1], Z_CAN), (a[0], a[1], Z_CAN)], 14,
              "P08_RevolvingDoor", mid)
main.face([(p[0], p[1], Z_CAN) for p in ring], 14, "P08_RevolvingDoor", (0, 0, 1), kind="ngon")
main.face([(p[0], p[1], Z_DOOR) for p in ring], 14, "P08_RevolvingDoor", (0, 0, -1), kind="ngon")
post = arc(RC[0], RC[1], 0.06, 0, 360, n=8)[:-1]
for i in range(8):
    a, b = post[i], post[(i + 1) % 8]
    main.face([(a[0], a[1], 0.01), (b[0], b[1], 0.01), (b[0], b[1], Z_DOOR), (a[0], a[1], Z_DOOR)], 14,
              "P08_RevolvingDoor", ((a[0] + b[0]) / 2 - RC[0], (a[1] + b[1]) / 2 - RC[1], 0))
for a0, a1 in ((45, 135), (225, 315)):
    w = arc(RC[0], RC[1], R_OUT, a0, a1, n=8)
    for a, b in zip(w, w[1:]):
        glass.face([(a[0], a[1], 0.0), (b[0], b[1], 0.0), (b[0], b[1], Z_DOOR), (a[0], a[1], Z_DOOR)], 1,
                   "P08_RevolvingDoor", ((a[0] + b[0]) / 2 - RC[0], (a[1] + b[1]) / 2 - RC[1], 0))
for ang in (45, 135, 225, 315):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    p0, p1 = (RC[0] + 0.06 * c, RC[1] + 0.06 * s), (RC[0] + R_IN * c, RC[1] + R_IN * s)
    glass.face([(p0[0], p0[1], 0.01), (p1[0], p1[1], 0.01), (p1[0], p1[1], Z_DOOR), (p0[0], p0[1], Z_DOOR)], 1,
               "P08_RevolvingDoor", (-s, c, 0))

# ================================================================= soffit P04 (from the two outlines, at +4.70)
U_dense = [U.base(u) for u in UwS] + [U.base(u) for u in Ucw[1:]] + [U.base(u) for u in UwN[1:]]
L_dense = [L.base(u) for u in splits(L, 0.0, L.length)]  # <= 3.9 m also along the CW / niche tops
L_dense += [L.base(u) for u in Um1] + [L.base(u) for u in Um2] + [L.base(u) for u in Um3] + \
    [L.base(u) for u in Um4]
L_dense = sorted({(round(p[0], 6), round(p[1], 6)): L.project(p) for p in L_dense}.items(), key=lambda kv: kv[1])
L_dense = [k for k, _ in L_dense]
soffit = [(p[0], p[1], Z_SOF) for p in U_dense] + [(p[0], p[1], Z_SOF) for p in reversed(L_dense)]
main.face(soffit, 19, "P04_Soffit_Canopy", (0, 0, -1), kind="ngon")

# ================================================================= parapet, roof strip P15 and caps P12
us = sorted(set([round(u, 9) for u in UwS + splits(U, uA, uB) + UwN]))
B = [U.base(u) for u in us]
O = U.offset_pts(us, CAP_OUT)
I = U.offset_pts(us, -PARAPET_T)
for k in range(len(us) - 1):
    n = U.n[U.seg(0.5 * (us[k] + us[k + 1]))]
    out, inn = (n[0], n[1], 0), (-n[0], -n[1], 0)
    if us[k + 1] <= uA + 1e-9 or us[k] >= uB - 1e-9:   # wood zones: from the facade face
        main.face([(B[k][0], B[k][1], Z_TOP), (B[k + 1][0], B[k + 1][1], Z_TOP),
                   (O[k + 1][0], O[k + 1][1], Z_TOP), (O[k][0], O[k][1], Z_TOP)], 18, "P12_ParapetCaps", (0, 0, -1))
    main.face([(O[k][0], O[k][1], Z_TOP), (O[k + 1][0], O[k + 1][1], Z_TOP), (O[k + 1][0], O[k + 1][1], Z_CAP),
               (O[k][0], O[k][1], Z_CAP)], 18, "P12_ParapetCaps", out)
    main.face([(I[k][0], I[k][1], Z_ROOF), (I[k + 1][0], I[k + 1][1], Z_ROOF), (I[k + 1][0], I[k + 1][1], Z_TOP),
               (I[k][0], I[k][1], Z_TOP)], 1, "P15_RoofEdge", inn)
    main.face([(I[k][0], I[k][1], Z_TOP), (I[k + 1][0], I[k + 1][1], Z_TOP), (I[k + 1][0], I[k + 1][1], Z_CAP),
               (I[k][0], I[k][1], Z_CAP)], 18, "P12_ParapetCaps", inn)
main.face([(p[0], p[1], Z_CAP) for p in O] + [(p[0], p[1], Z_CAP) for p in reversed(I)], 18, "P12_ParapetCaps",
          (0, 0, 1), kind="ngon")
# CW zone: the cap bottom starts at the F50 cap face (h 0.02) of the CW top row, so the CW front faces and the cap
# share their edges (no bow-tie / non-manifold where the relief meets the cap)
cw_top = [U.base(u) for u in Ucw]
cw_top = [(b[0] + 0.02 * n[0], b[1] + 0.02 * n[1]) for b, n in zip(cw_top, [U.normal(u) for u in Ucw])]
o_cw = [O[k] for k in range(len(us)) if uA - 1e-9 <= us[k] <= uB + 1e-9]
main.face([(p[0], p[1], Z_TOP) for p in cw_top] + [(p[0], p[1], Z_TOP) for p in reversed(o_cw)], 18,
          "P12_ParapetCaps", (0, 0, -1), kind="ngon")


def subdiv(pts, maxlen=3.9):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        k = max(1, math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / maxlen))
        out += [(a[0] + (b[0] - a[0]) * i / k, a[1] + (b[1] - a[1]) * i / k) for i in range(1, k + 1)]
    return out


inner = subdiv([I[-1], (59.40, -0.23), (72.0, -0.23), (72.0, -47.24), (41.85, -47.24), I[0]])[1:-1]
# split along x = XR so no roof face spans more than ~3.9 m (east: parapet .. XR, west: XR .. 72 + the returns);
# x = XR crosses the roof outline exactly twice (south and north parapet lines)
XR = 75.25


def clip(poly, keep_right):
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ina, inb = (a[0] >= XR) == keep_right, (b[0] >= XR) == keep_right
        if ina:
            out.append(a)
        if ina != inb:
            t = (XR - a[0]) / (b[0] - a[0])
            out.append((XR, a[1] + t * (b[1] - a[1])))
    return out


roof = I + inner
for keep in (True, False):
    pc = clip(roof, keep)
    k = [i for i, p in enumerate(pc) if abs(p[0] - XR) < 1e-9]
    assert len(k) == 2, k
    i0, i1 = k
    ya, yb = pc[i0][1], pc[i1][1]
    mid = subdiv([(XR, ya), (XR, yb)])[1:-1]
    if i1 == i0 + 1:
        pc = pc[:i1] + mid + pc[i1:]
    else:  # the cut edge closes the loop (i1 -> i0)
        pc = pc + subdiv([(XR, yb), (XR, ya)])[1:-1]
    main.face([(p[0], p[1], Z_ROOF) for p in pc], 21, "P15_RoofEdge", (0, 0, 1), kind="ngon")

# ================================================================= sign frames P11 (60x60 rings, 20 mm off, no back)
SF = Cell(0.06, 16, 16, "P11_SignFrames")
VOID = Cell(0.0, None, 16, "P11_SignFrames")


def sign_group(p0, p1, xs, rows):
    """frames sharing vertical members; xs = member centre lines along the base (outer members flush)"""
    pl = Poly([p0, p1])
    ofs = [x - xs[0] for x in xs]
    for z0, z1 in rows:
        regs = []
        for k in range(len(ofs) - 1):
            a = ofs[k] + (0.06 if k == 0 else 0.03)
            b = ofs[k + 1] - (0.06 if k == len(ofs) - 2 else 0.03)
            regs.append((a, b, z0 + 0.06, z1 - 0.06, VOID))
        relief(main, None, pl, 0.0, pl.length, [z0, z1], regs, SF, ulines=splits(pl, 0.0, pl.length))


for ya in (-48.44, -4.03):                              # E upper 5.0 x 2.0 at x 79.05
    sign_group((79.05, ya), (79.05, ya + 5.0), [ya, ya + 5.0], [(5.70, 7.70), (8.20, 10.20), (10.70, 12.70)])
for ya in (-48.44, -2.53):                              # E lower 3.5 x 1.25 at x 76.20
    sign_group((76.20, ya), (76.20, ya + 3.5), [ya, ya + 3.5], [(1.45, 2.70), (2.85, 4.10)])
SROWS = [(5.2, 7.2), (7.3, 9.3), (9.4, 11.4), (11.5, 13.5)]
sign_group((60.75, -50.78), (68.75, -50.78), [60.75, 63.68, 68.75], SROWS)
sign_group((68.92, -50.78), (76.92, -50.78), [68.92, 73.99, 76.92], SROWS)
sign_group((71.19, -50.78), (74.69, -50.78), [71.19, 74.69], [(1.59, 2.84), (2.94, 4.19)])

# ================================================================= south canopy P18 and lamellas P19
box(main, 53.15, 63.08, -51.08, -50.595, 2.88, 2.93, 19, "P18_SouthCanopy", skip=("y1",))
box(main, 53.18, 53.34, -51.02, -50.60, 0.10, 2.88, 19, "P18_SouthCanopy", skip=("y1", "z1"))
# 55.10 -> 55.11: the source lamella side is coplanar with the window reveal x 55.10 (xView contact); 1 cm
LAM = [53.35, 53.6, 53.85, 54.1, 55.11, 55.35, 55.6, 55.85, 56.1, 57.075, 57.325, 57.575, 57.825, 58.075, 58.325,
       58.575, 58.825, 59.075, 60.08, 60.33, 60.58, 60.83, 61.08, 62.08, 62.33, 62.58, 62.83, 63.08]
for x in LAM:
    box(main, x, x + 0.05, -50.807, -50.597, 0.20, 2.70, 17, "P19_SouthLamellas", skip=("y1",))


# ================================================================= to Blender
def srgb_lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def material(name, hexcol, alpha=1.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    lin = srgb_lin(hexcol)
    m.diffuse_color = (*lin, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
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
    bad, tris = 0, []
    for idx, mat, part, kind in mb.faces:
        if kind == "ngon":
            # Blender's polyfill (bmesh.ops.triangulate) breaks on these long thin n-gons (cap ring: 1313 m2
            # filled for a 75 m2 polygon); scanfill (triangle_fill) on the boundary loop is exact.
            es = []
            for a, b in zip(idx, idx[1:] + idx[:1]):
                e = bm.edges.get((vs[a], vs[b])) or bm.edges.new((vs[a], vs[b]))
                es.append(e)
            pts = [mb.verts[i] for i in idx]
            nz = sum((p[0] - q[0]) * (p[1] + q[1]) for p, q in zip(pts, pts[1:] + pts[:1]))
            want = 1.0 if nz > 0 else -1.0   # newell z of the stored (already oriented) loop
            res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=es, normal=(0, 0, want))
            new = [g for g in res["geom"] if isinstance(g, bmesh.types.BMFace)]
            for f in new:
                f.material_index = mat - 1
                f[lay] = PART_IDS.index(part)
                f.normal_update()
                if f.normal.z * want < 0:
                    f.normal_flip()
            tris += new
            continue
        try:
            f = bm.faces.new([vs[i] for i in idx])
        except ValueError:
            bad += 1
            continue
        f.material_index = mat - 1
        f[lay] = PART_IDS.index(part)
    if tris:
        bmesh.ops.join_triangles(bm, faces=tris, angle_face_threshold=math.radians(1.0),
                                 angle_shape_threshold=math.radians(80.0), cmp_seam=False, cmp_sharp=False,
                                 cmp_uvs=False, cmp_vcols=False, cmp_materials=True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for i in sorted(slots):
        me.materials.append(slots[i])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob["part_ids"] = json.dumps(PART_IDS)
    ob["build"] = "jobs/elv-tc-vpm/scripts/build_pilot_ia.py v001; parts v002 (Gate 1 confirmed 2026-11-04)"
    return ob, bad


HEALED = heal_t(main)  # T-junctions between separately gridded panels -> n-gons (welded, no bow-ties)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
sc = bpy.context.scene
sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 1.0
mats = {i: material(n, RAL[SLOT_COL.get(i, "unused")]) for i, n in SLOTS.items()}
ob_main, bad_m = to_object(main, STEM + "_Main", mats)
ob_glass, bad_g = to_object(glass, STEM + "_MainGlass", {1: material("Glass_Clear", "#BFD9EE", 0.35)})
os.makedirs(os.path.dirname(OUT), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("BUILD", json.dumps({"main_faces": len(ob_main.data.polygons), "glass_faces": len(ob_glass.data.polygons),
                           "rejected_faces": [bad_m, bad_g], "t_healed_faces": HEALED, "out": OUT}))
