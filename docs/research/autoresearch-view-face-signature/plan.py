"""Plan PNG of a #157 wall table: open walls blue, inner walls red, windows grey dots (evidence only)."""
import json
import math
import sys

from PIL import Image, ImageDraw


def plan_png(table, out, scale=6):
    walls = table["walls"]
    pts = []
    for w in walls:
        a = math.radians(w["az"])
        s, t = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
        dm = (w["d0"] + w["d1"]) / 2
        for u in (w["u0"], w["u1"]):
            pts.append((s[0] * dm + t[0] * u, s[1] * dm + t[1] * u))
        w["_seg"] = pts[-2:]
        w["_n"] = s
    xs = [p[0] for p in pts] + [p[0] for p in table["windows"]]
    ys = [p[1] for p in pts] + [p[1] for p in table["windows"]]
    x0, y0, x1, y1 = min(xs) - 5, min(ys) - 5, max(xs) + 5, max(ys) + 5
    img = Image.new("RGB", (int((x1 - x0) * scale), int((y1 - y0) * scale)), "white")
    dr = ImageDraw.Draw(img)

    def px(p):
        return ((p[0] - x0) * scale, (y1 - p[1]) * scale)

    for p in table["windows"]:
        q = px(p)
        dr.ellipse([q[0] - 1, q[1] - 1, q[0] + 1, q[1] + 1], fill=(170, 170, 170))
    for i, w in enumerate(walls):
        col = (220, 30, 30) if w["cls"] == "inner" else (30, 60, 220)
        a, b = px(w["_seg"][0]), px(w["_seg"][1])
        dr.line([a, b], fill=col, width=3)
        m = ((a[0] + b[0]) / 2 + w["_n"][0] * 8, (a[1] + b[1]) / 2 - w["_n"][1] * 8)
        dr.text(m, str(i), fill=col)
    img.save(out)


if __name__ == "__main__":
    plan_png(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
