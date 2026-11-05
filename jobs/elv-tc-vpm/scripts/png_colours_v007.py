"""elv-tc-vpm: number of distinct colours and min/max per channel of PNG maps (read only).

uv run --no-project --with pillow --with numpy python png_colours_v007.py <png> [<png> ...]
"""
import sys
import numpy as np
from PIL import Image

for p in sys.argv[1:]:
    a = np.asarray(Image.open(p).convert("RGB")).reshape(-1, 3)
    u = np.unique(a[:: max(1, len(a) // 2000000)], axis=0)
    print(p.split("\\")[-1].split("/")[-1], a.shape[0], "distinct", len(u), "min", a.min(0).tolist(), "max", a.max(0).tolist())
