"""elv-tc-vpm: revolving door on sheet 25, second pass: all bezier items in the east entrance clip, grouped by drawing.

uv run --no-project --with pymupdf python pdf_revolving_door_b.py <booklet.pdf> <out_dir>
Scale 9.4429 pt/m from axis bubbles 11-12 (first pass). Plan x -> building x: x_m = 75.6 - (925.16 - x_pt) / scale.
"""
import sys, os, json
import pymupdf

pdf, out_dir = sys.argv[1], sys.argv[2]
S = 9.4429; AX12 = 925.16
doc = pymupdf.open(pdf); page = doc[24]
clip = pymupdf.Rect(860, 290, 960, 400)
out = []
for d in page.get_drawings():
    if not d["rect"].intersects(clip):
        continue
    curves = [it for it in d["items"] if it[0] == "c"]
    if not curves:
        continue
    pts = [p for it in curves for p in it[1:]]
    x0 = min(p.x for p in pts); x1 = max(p.x for p in pts); y0 = min(p.y for p in pts); y1 = max(p.y for p in pts)
    out.append({"bbox_pt": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], "w_m": round((x1 - x0) / S, 3),
                "h_m": round((y1 - y0) / S, 3), "centre_x_m": round(75.6 - (AX12 - (x0 + x1) / 2) / S, 2),
                "n_curves": len(curves), "stroke_w": d.get("width"), "color": d.get("color"), "fill": d.get("fill")})
out.sort(key=lambda o: -o["w_m"])
json.dump(out, open(os.path.join(out_dir, "revolving_door_p25_v001b.json"), "w"), indent=1)
page.get_pixmap(matrix=pymupdf.Matrix(10, 10), clip=clip).save(os.path.join(out_dir, "revolving_door_p25_v001.png"))
for o in out[:20]:
    print(o)
