"""KPP1 #1416 [D313]: 2x2 contact sheet of the wire_render.py PNGs + SHA256SUMS.txt for the folder.

Pattern: n/a | new-case: job script; reads <dir>/wire-report.json and the four PNGs, writes
<dir>/wire-sheet-v003.png (refuses to overwrite) and <dir>/SHA256SUMS.txt over every file in <dir>.

  uv run python wire_sheet.py <wire_dir>
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SHOTS = ["01_overview_top", "02_densest_cell", "03_skirt_edge", "04_building_edge"]


def main(d: Path) -> None:
    rep = json.loads((d / "wire-report.json").read_text(encoding="utf-8"))
    sheet = d / "wire-sheet-v003.png"
    if sheet.exists():
        raise SystemExit(f"exists: {sheet}")
    imgs = []
    for s in SHOTS:
        p = d / f"{s}.png"
        if not p.is_file():
            raise SystemExit(f"missing render: {p}")
        imgs.append(Image.open(p).convert("RGB").resize((1000, 750)))
    head = 90
    out = Image.new("RGB", (2000, 1500 + head), "white")
    dr = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    qv = rep["quad_review_view_by_sides"]
    dr.text((12, 8), f"KPP1 #1416 - NPM Ground v003 (packaged 0000_Kpp_1_Ground.fbx, sha {rep['ground_sha256'][:12]}), "
            f"{rep['tris_equiv_total']} triangles <= 180000 [D307, D308, D313]", fill="black", font=font)
    dr.text((12, 38), "Wire = quad review view (display only): " + "; ".join(
        f"{k.replace('SM_Kpp_1_', '')} {v.get('4', 0)} quads + {v.get('3', 0)} tris" for k, v in qv.items())
        + ". Grey block = R1 building (context, no wire).", fill="black", font=font)
    labels = ["Overview, top (whole site)", f"Densest 10 m cell {rep['densest_cell_10m']['center']} "
              f"({rep['densest_cell_10m']['polygons']} polys)", "Skirt (perimeter) edge, south side",
              "Near the building (SE corner of R1)"]
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x, y = (i % 2) * 1000, head + (i // 2) * 750
        out.paste(im, (x, y))
        dr.rectangle([x, y, x + 1000, y + 34], fill="white")
        dr.text((x + 8, y + 5), f"{SHOTS[i][:2]}  {lab}", fill="black", font=font)
    out.save(sheet)
    lines = []
    for p in sorted(d.iterdir()):
        if p.is_file() and p.name != "SHA256SUMS.txt":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()} *{p.name}")
    (d / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
