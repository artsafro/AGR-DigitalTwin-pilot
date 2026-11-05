import sys, collections, numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

csv, tex, out = sys.argv[1:4]
A = np.asarray(Image.open(tex))[..., 3]
N = A.shape[0]
lab, nh = ndimage.label(A < 128)
cent = np.array(ndimage.center_of_mass(np.ones_like(A), lab, range(1, nh + 1)))  # (row, col)
print("holes in texture:", nh)
from matplotlib.path import Path
counts = collections.Counter(); bad = []
img = Image.open(tex).convert("RGB"); bg = Image.new("RGB", img.size, (60, 60, 60))
img = Image.composite(img, bg, Image.open(tex).getchannel("A")); dr = ImageDraw.Draw(img)
tiles = set()
for line in open(csv):
    t = line.strip().split(","); nm, fi, mid = t[0], int(t[1]), int(t[2])
    uv = np.array(t[3:], float).reshape(-1, 2)
    tiles.add(int(1001 + np.floor(uv[:, 0].mean()) + 10 * np.floor(uv[:, 1].mean())))
    px = np.c_[(uv[:, 0] - np.floor(uv[:, 0].mean())) * N, (1 - uv[:, 1]) * N]
    inside = Path(px).contains_points(cent[:, ::-1]).sum()
    counts[(nm, inside)] += 1
    dr.polygon([tuple(p) for p in px], outline=(255, 0, 0))
print("UDIM tiles:", tiles)
for k, v in sorted(counts.items()): print(k, "faces:", v)
img.resize((1024, 1024), Image.LANCZOS).save(out)
