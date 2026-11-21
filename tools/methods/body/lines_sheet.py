"""Sheet of the lattice lines of one band (#1736, [D372]): what the core will cut, before any mesh is built.

Pattern: n/a | new-case: per-facade elevation of the lines list (kept / dropped as texture) from plan_adapter_dwg lines.

uv run python tools/methods/body/lines_sheet.py LINES.json NEW.png [--ppm 60] [--title TEXT]
LINES.json = `plan_adapter_dwg.py lines` output. One row per facade (u along the facade, z up, band only): element
outlines by class (opening blue, door/opening brown, zone green, niche grey), kept levels and stations as solid red
lines with their values, dropped ones dashed grey. Review sheet only, never an acceptance. NEW.png must not exist.
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

COL = {"surrounds": (40, 90, 200), "doors": (150, 90, 30), "portals": (40, 150, 60), "features": (40, 150, 60),
       "grilles": (130, 130, 130)}


def _font(size):
    for f in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def render(lines, ppm=60.0, title=""):
    z0, z1 = lines["band"]
    els = lines["elements"]
    facs = sorted({e["facade"] for e in els} | set(lines["stations"]))
    umax = {f: max([e["rect"][1] for e in els if e["facade"] == f] + lines["stations"].get(f, [0])) + 1.0
            for f in facs}
    m, head, gap = 70, 60, 50
    W = int(m * 2 + max(umax.values()) * ppm)
    H = int(head + len(facs) * ((z1 - z0) * ppm + gap) + 40)
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    f12, f16 = _font(12), _font(16)
    d.text((m, 12), title, fill="black", font=f16)
    d.text((m, 34), "red = line kept (cell class change >= %.1f m or opening), dashed grey = dropped (texture); "
           "snap %.2f m; blue window block, brown door, green zone/portal, grey niche/grille"
           % (lines["min_reason_m"], lines["snap_m"]), fill=(60, 60, 60), font=f12)
    y = head
    for f in facs:
        h = (z1 - z0) * ppm
        X = lambda u: m + u * ppm  # noqa: E731
        Y = lambda z: y + h - (z - z0) * ppm  # noqa: E731
        d.rectangle([X(0), Y(z1), X(umax[f]), Y(z0)], outline=(0, 0, 0))
        d.text((8, y + h / 2 - 8), f, fill="black", font=f16)
        for e in [e for e in els if e["facade"] == f]:
            u0, u1, zb, zt = e["rect"]
            d.rectangle([X(u0), Y(min(zt, z1)), X(u1), Y(max(zb, z0))], outline=COL[e["kind"]], width=2)
        for dl in lines["stations_dropped"].get(f, []):
            for yy in range(int(Y(z1)), int(Y(z0)), 8):
                d.line([X(dl["at"]), yy, X(dl["at"]), yy + 4], fill=(170, 170, 170))
        for s in lines["stations"].get(f, []):
            d.line([X(s), Y(z1), X(s), Y(z0)], fill=(220, 30, 30), width=1)
            d.text((X(s) + 2, Y(z0) + 2), "%.1f" % s, fill=(220, 30, 30), font=f12)
        for dl in lines["levels_dropped"]:
            for xx in range(int(X(0)), int(X(umax[f])), 10):
                d.line([xx, Y(z0 + dl["at"]), xx + 5, Y(z0 + dl["at"])], fill=(170, 170, 170))
        for z in lines["levels"]:
            d.line([X(0), Y(z0 + z), X(umax[f]), Y(z0 + z)], fill=(220, 30, 30), width=1)
            d.text((X(umax[f]) + 4, Y(z0 + z) - 7), "+%.1f" % (z0 + z), fill=(220, 30, 30), font=f12)
        y += h + gap
    return im


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    ppm, title = 60.0, ""
    if "--ppm" in args:
        i = args.index("--ppm")
        ppm = float(args[i + 1])
        del args[i:i + 2]
    if "--title" in args:
        i = args.index("--title")
        title = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        print("usage: lines_sheet.py LINES.json NEW.png [--ppm 60] [--title TEXT]", file=sys.stderr)
        return 2
    src, out = args
    if os.path.exists(out) or os.path.realpath(out) == os.path.realpath(src):
        print("refused: NEW.png exists or is the input", file=sys.stderr)
        return 2
    im = render(json.load(open(src, encoding="utf-8")), ppm, title)
    im.save(out)
    print("SHEET", out, im.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
