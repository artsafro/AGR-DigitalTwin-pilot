"""elv-tc-vpm customer-clarify-v001: render booklet pages to PNG (read-only on the PDF).

py -3 -I clarify_booklet_pages_v001.py <booklet.pdf> <out_dir> <dpi> <page> [page ...]
"""
import sys
from pathlib import Path
import pymupdf

pdf, out, dpi = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(pdf)
for p in map(int, sys.argv[4:]):
    f = out / f"booklet_p{p:02d}_{dpi}.png"
    if f.exists():
        print("exists", f)
        continue
    pix = doc[p - 1].get_pixmap(dpi=dpi)
    pix.save(f)
    print(p, pix.width, pix.height)
