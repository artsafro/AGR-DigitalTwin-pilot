"""elv-tc-vpm: one-page picture of the pilot parts - east elevation (y-z) + top view (x-y), parts coloured and labelled.

uv run --no-project --with matplotlib python draw_parts.py <ref_dump.json> <parts.json> <out.png>
Source boxes come from the clean reference dump; parts missing in the FBX (soffit P04, revolving door P08) are drawn
from the measured outlines. Never overwrites.
"""
import json, sys, os, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, Patch

dump, parts_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
D = json.load(open(dump, encoding="utf-8"))
PL = json.load(open(parts_path, encoding="utf-8"))
PID = {p["id"].split("_")[0]: p for p in PL["parts"]}
COL = {"P01": "#d9a35f", "P02": "#5a5f68", "P03": "#8c7b6b", "P04": "#f0c27a", "P05": "#2f5fa8", "P06": "#4f7fc8",
       "P07": "#7a4fa0", "P08": "#e0402a", "P09": "#c0306a", "P10": "#f2d21b", "P11": "#111111", "P12": "#e8743b",
       "P13": "#b5523b", "P14": "#bbbbbb", "P15": "#a8a091", "P16": "#20a0c0", "P17": "#6a2030", "P18": "#9a6a2a",
       "P19": "#d8b830", "P20": "#a9d6f5"}


def part_of(r):
    c, mn, mx, n = r["cat"], r["mn"], r["mx"], r["name"]
    S = mx[1] < -48.0 and mx[0] >= 41.8
    N = mn[1] > 1.4 and mx[0] >= 59.3
    E = mn[0] > 72.0
    if not (S or N or E):
        return None
    niche = mn[0] < 75.8 and mx[1] < -19.4 and mn[1] > -28.1 and mx[2] < 4.75 and E
    if c == "wood_cassette": return "P01"
    if c == "metal_cassette": return "P07" if niche else "P02"
    if c == "plinth": return "P03"
    if c == "glass": return "P20"
    if c == "stemalit": return "P07" if niche else ("P05" if mn[2] > 4.6 else "P06")
    if c == "rib_lamella": return "P10" if E else "P19"
    if c == "sign_frame": return "P11"
    if c == "parapet_flashing":
        if "Batten_top" in n: return "P12"
        if "кассеты" in n or "Batten_RAL7021 [" in n: return "P13"
        return "P14"
    if c == "door": return "P17" if N else "P09"
    if c == "window": return "P16"
    if c == "canopy": return "P18"
    if c in ("roof", "wall_ext", "sandwich"): return "P15"
    if c == "mullion": return "P14"
    return None


items = [(part_of(r), r) for r in D]
items = [(p, r) for p, r in items if p]
fig = plt.figure(figsize=(16.5, 11.7), dpi=150)
fig.suptitle("elv-tc-vpm  pilot И-А (east facade + returns) - parts v001 (DRAFT, Gate 1 pending)", fontsize=14, x=0.02, ha="left")
axE = fig.add_axes([0.04, 0.60, 0.70, 0.32]); axT = fig.add_axes([0.04, 0.04, 0.70, 0.54]); axL = fig.add_axes([0.76, 0.05, 0.23, 0.88])
# elevation: viewer looks west, +y to the right; draw back (small x) to front (large x); E side only + corner pieces
el = sorted([(p, r) for p, r in items if r["mn"][0] > 72.0 or (r["mx"][0] > 74.3 and p in ("P01", "P02", "P03", "P12"))],
            key=lambda t: (t[1]["mx"][0], t[0] == "P14"))
for p, r in el:
    if p == "P14" and r["cat"] == "mullion":
        axE.plot([r["mn"][1], r["mx"][1]] if r["mx"][1] - r["mn"][1] > 0.1 else [(r["mn"][1] + r["mx"][1]) / 2] * 2,
                 [r["mn"][2], r["mx"][2]] if r["mx"][2] - r["mn"][2] > 0.1 else [(r["mn"][2] + r["mx"][2]) / 2] * 2,
                 color="#666666", lw=0.25, zorder=r["mx"][0])
        continue
    axE.add_patch(Rectangle((r["mn"][1], r["mn"][2]), r["mx"][1] - r["mn"][1], max(r["mx"][2] - r["mn"][2], 0.03),
                            fc=COL[p], ec="#00000055" if p != "P11" else COL[p], lw=0.2, zorder=r["mx"][0], fill=p != "P11"))
# missing parts drawn from measurements
axE.add_patch(Rectangle((-48.8, 4.62), 51.3, 0.10, fc=COL["P04"], ec="k", lw=0.4, hatch="////", zorder=200))
axE.add_patch(Rectangle((73.08 * 0 - 23.73 - 2.06, 0.0), 4.12, 2.72, fc=COL["P08"], ec="k", lw=0.6, alpha=0.85, zorder=60))
axE.set_xlim(-52, 5.5); axE.set_ylim(-1.3, 15.2); axE.set_aspect("equal")
axE.set_title("East elevation (looking west), y [m] left = south / right = north; P04 soffit and P08 revolving door = built from measurements (not in FBX)", fontsize=9, loc="left")
axE.axhline(0, color="k", lw=0.5)
for ax_y, lab in ((2.566, "А"), (-2.734, "Б"), (-11.134, "В"), (-19.534, "Г"), (-27.934, "Д"), (-36.334, "Е"), (-44.734, "Ж"), (-50.034, "И")):
    axE.axvline(ax_y, color="#999999", lw=0.4, ls="-.", zorder=0); axE.text(ax_y, -1.1, lab, ha="center", fontsize=9)
lab_pos = {"P01": (-46, 12.9), "P02": (-46.5, 1.0), "P05": (-36, 12.4), "P20": (-38, 8.4), "P06": (-39, 3.3), "P10": (-31, 9.0),
           "P11": (-45.9, 6.6), "P12": (-25, 14.5), "P04": (-10, 5.05), "P07": (-23.7, 4.1), "P08": (-23.7, 1.3), "P09": (-42.6, 1.0),
           "P03": (-8, -0.6), "P13": (-31, 0.6), "P14": (-15, 7.0)}
for p, (x, y) in lab_pos.items():
    axE.text(x, y, p, fontsize=8, ha="center", va="center", zorder=500, bbox=dict(fc="white", ec=COL[p], lw=1.2, pad=1.2))
# top view
tv = sorted(items, key=lambda t: t[1]["mx"][2])
for p, r in tv:
    if p == "P14":
        continue
    w = max(r["mx"][0] - r["mn"][0], 0.04); h = max(r["mx"][1] - r["mn"][1], 0.04)
    axT.add_patch(Rectangle((r["mn"][1], r["mn"][0]), h, w, fc=COL[p], ec="#00000044", lw=0.15, zorder=r["mx"][2]))
# soffit outline (E band between metal 76.17 and upper face 79.03) and niche ceiling
for poly in ([(-48.8, 76.17), (-47.6, 79.03), (-30.33, 79.03), (-27.25, 76.0)], [(-20.21, 76.0), (-17.13, 79.03), (0.14, 79.03), (1.37, 76.17)]):
    axT.add_patch(Polygon(poly, closed=True, fc="none", ec="#c08a2a", lw=1.2, hatch="////", zorder=300))
axT.add_patch(Rectangle((-27.31, 73.10), 7.15, 2.9, fc="none", ec="#c08a2a", lw=1.2, hatch="\\\\\\\\", zorder=300))
axT.add_patch(Circle((-23.73, 73.08), 2.06, fc=COL["P08"], ec="k", lw=0.8, alpha=0.8, zorder=400))
axT.set_xlim(-52, 5.5); axT.set_ylim(81.5, 40.5); axT.set_aspect("equal")
axT.set_title("Top view under the elevation (y right = north, x down = east, facade at the bottom); hatched = soffit P04 (missing in FBX), red circle = P08 D 4.12 m", fontsize=9, loc="left")
for ax_x, lab in ((42.0, "6"), (50.4, "7"), (58.8, "8"), (67.2, "9"), (75.6, "12*")):
    pass
tl = {"P01": (60, -51.9), "P02": (50, -49.3), "P05": (80.3, -36), "P06": (77.2, -38), "P07": (74.4, -24.5), "P08": (71.0, -23.7),
      "P10": (80.7, -10), "P12": (60, 4.3), "P15": (70, -10), "P16": (54.6, -52.3), "P18": (58, -52.5), "P19": (62.5, -52.2),
      "P17": (62, 4.4), "P11": (66, -52.0), "P04": (77.6, -5)}
for p, (x, y) in tl.items():
    axT.text(y, x, p, fontsize=7.5, ha="center", va="center", zorder=500, bbox=dict(fc="white", ec=COL[p], lw=1.2, pad=1.0))
for ax in (axE, axT):
    ax.tick_params(labelsize=7); ax.grid(False)
# legend table
axL.axis("off")
yy = 1.0
axL.text(0, yy, "Part / operation / material ID / VPM tris", fontsize=9, weight="bold", va="top"); yy -= 0.03
for p in PL["parts"]:
    k = p["id"].split("_")[0]
    mid = p["legend_item"].split(";")[0].split("(")[0].strip()
    op = p["operation"] + ("/" + p["build_as"] if p.get("build_as") else "")
    axL.add_patch(Rectangle((0, yy - 0.022), 0.05, 0.018, fc=COL[k], ec="k", lw=0.4, transform=axL.transAxes))
    axL.text(0.07, yy, f"{p['id']}", fontsize=7.6, va="top", weight="bold")
    axL.text(0.07, yy - 0.015, f"{op} | {mid[:40]} | {p['triangle_budget']['vpm']}", fontsize=6.6, va="top")
    yy -= 0.043
axL.text(0, yy - 0.01, f"Sum {sum(p['triangle_budget']['vpm'] for p in PL['parts'])} / pilot {PL['triangle_budget']['vpm']} tris\n"
         "P14 = flush details (<= 5 cm) baked to texture:\ncassette joints 20 mm, F50 caps 20 mm,\nflush flashings (reg p.32 §7)",
         fontsize=7.5, va="top")
fig.savefig(out, facecolor="white")
print("WROTE", out)
