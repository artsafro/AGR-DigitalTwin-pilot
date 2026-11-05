"""elv-tc-vpm: measure the revolving door on booklet sheet 25 (plan 1st floor) from PDF vector data.

uv run --no-project --with pymupdf python pdf_revolving_door.py <booklet.pdf> <out_dir>
Scale from the axis bubbles 11 and 12 (8.4 m apart, horizontal) and И..А (vertical) found as text; circle candidates =
near-square drawing items (bezier paths) in the east entrance zone. Writes a json + a crop PNG. Read-only on the PDF.
"""
import sys, os, json
import pymupdf

pdf, out_dir = sys.argv[1], sys.argv[2]
doc = pymupdf.open(pdf)
page = doc[24]
W, H = page.rect.width, page.rect.height
words = page.get_text("words")
# axis bubble labels: digits at the bottom row, letters at the left column
bottom = [w for w in words if w[4] in ("10", "11", "12") and w[1] > H * 0.70]
left = [w for w in words if w[4] in ("Г", "Д") and w[0] < W * 0.12]
res = {"page_size_pt": [W, H], "bottom_labels": [(w[4], round((w[0] + w[2]) / 2, 2), round((w[1] + w[3]) / 2, 2)) for w in bottom],
       "left_labels": [(w[4], round((w[0] + w[2]) / 2, 2), round((w[1] + w[3]) / 2, 2)) for w in left]}
xs = {}
for w in bottom:
    xs.setdefault(w[4], []).append((w[0] + w[2]) / 2)
if "11" in xs and "12" in xs:
    pt_per_m = (min(xs["12"]) - min(xs["11"])) / 8.4
    res["pt_per_m_from_axes_11_12"] = round(pt_per_m, 4)
else:
    pt_per_m = None
# circle candidates in the east third, middle height
cands = []
for d in page.get_drawings():
    r = d["rect"]
    if r.x0 < W * 0.70 or r.width < 5 or r.height < 5:
        continue
    if not (0.85 < r.width / r.height < 1.18):
        continue
    if not any(it[0] == "c" for it in d["items"]):
        continue
    cands.append({"rect": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)], "w_pt": round(r.width, 2),
                  "h_pt": round(r.height, 2), "n_items": len(d["items"]), "width": d.get("width"),
                  "d_m": round(r.width / pt_per_m, 3) if pt_per_m else None})
cands.sort(key=lambda c: -c["w_pt"])
res["circle_candidates"] = cands[:25]
os.makedirs(out_dir, exist_ok=True)
json.dump(res, open(os.path.join(out_dir, "revolving_door_p25_v001.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if cands:
    c = cands[0]["rect"]; m = 40
    clip = pymupdf.Rect(c[0] - m, c[1] - m, c[2] + m, c[3] + m)
    page.get_pixmap(matrix=pymupdf.Matrix(8, 8), clip=clip).save(os.path.join(out_dir, "revolving_door_p25_v001.png"))
print(json.dumps(res, ensure_ascii=False)[:3000])
