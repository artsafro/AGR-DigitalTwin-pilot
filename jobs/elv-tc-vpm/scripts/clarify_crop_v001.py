"""elv-tc-vpm customer-clarify-v001: inspection crop helper (read-only on input).

py -3 -I clarify_crop_v001.py <in.png> <out.png> x0 y0 x1 y1 [max_w]
"""
import sys
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
src, out = sys.argv[1], sys.argv[2]
x0, y0, x1, y1 = map(int, sys.argv[3:7])
mw = int(sys.argv[7]) if len(sys.argv) > 7 else 1800
im = Image.open(src).convert("RGB").crop((x0, y0, x1, y1))
if im.width > mw:
    im = im.resize((mw, round(im.height * mw / im.width)), Image.LANCZOS)
im.save(out)
print(im.size)
