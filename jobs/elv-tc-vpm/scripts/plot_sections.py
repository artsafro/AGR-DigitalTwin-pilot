"""Plot ref_sections json: one PNG per cut, colour per category. Optional zoom window per cut.

uv run --no-project --with matplotlib python plot_sections.py <sections.json> <out_dir> [cut x0 x1 y0 y1] ...
"""
import json, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

src, outd = sys.argv[1], sys.argv[2]
zooms = {}
a = sys.argv[3:]
while a:
    zooms.setdefault(a[0], []).append(tuple(float(v) for v in a[1:5])); a = a[5:]
D = json.load(open(src, encoding="utf-8"))
cats = sorted({s[0] for v in D.values() for s in v})
cm = plt.get_cmap("tab20")
col = {c: cm(i % 20) for i, c in enumerate(cats)}
for cut, segs in D.items():
    if cut not in zooms:
        continue
    ax_name = cut.split("=")[0]
    h, v = {"z": (0, 1), "y": (0, 2), "x": (1, 2)}[ax_name]
    for k, (x0, x1, y0, y1) in enumerate(zooms[cut]):
        fig, ax = plt.subplots(figsize=(16, 16 * (y1 - y0) / (x1 - x0) + 1))
        seen = set()
        for s in segs:
            p0, p1 = s[2:5], s[5:8]
            if max(p0[h], p1[h]) < x0 or min(p0[h], p1[h]) > x1 or max(p0[v], p1[v]) < y0 or min(p0[v], p1[v]) > y1:
                continue
            ax.plot([p0[h], p1[h]], [p0[v], p1[v]], color=col[s[0]], lw=0.8, label=None if s[0] in seen else s[0])
            seen.add(s[0])
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.grid(True, lw=0.3)
        ax.minorticks_on(); ax.grid(True, which="minor", lw=0.1)
        ax.legend(fontsize=7, loc="best"); ax.set_title(f"{cut} window {x0},{x1},{y0},{y1}")
        fig.savefig(os.path.join(outd, f"sec_{cut}_{k}.png"), dpi=110, bbox_inches="tight"); plt.close(fig)
print("ok")
