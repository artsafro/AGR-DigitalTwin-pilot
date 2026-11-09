"""K5 conditioner screens: VPM 4K UDIM 1004 maps (Diffuse RGBA with hole alpha, ERM, Normal).

Hole grids measured on the source FBX plates (SKUG-26_PP_AR_K5_fsd), hole D = 50 mm.
Islands are in metres at TEXEL px/m; pixel origin bottom-left (UV space).
"""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
N = 4096; TEXEL = 1300.0; R = 0.025
PLATE = (228, 210, 181); HOLE_PREVIEW = (60, 60, 60)
ERM = (0, 128, 0); NORMAL = (128, 128, 255)


def grid(w, h, ncol, pcol, nrow, prow, left=None):
    fw, fh = (ncol - 1) * pcol, (nrow - 1) * prow
    u0 = (w - fw) / 2 if left is None else left
    v0 = (h - fh) / 2
    return [(u0 + i * pcol, v0 + j * prow) for j in range(nrow) for i in range(ncol)]


# island: size (m), bottom-left pixel origin, hole centres (m, island-local, u right / v up)
ISL = {
    "VF": dict(w=1.200, h=1.944, x=32, y=32, holes=grid(1.200, 1.944, 10, 0.095, 18, 0.100, left=0.125)),
    # side: u = 0 at the front edge; source margins front 0.2075 / wall 0.125 scaled to 0.685 depth
    "VS": dict(w=0.685, h=1.944, x=1656, y=32, holes=grid(0.685, 1.944, 4, 0.0875, 18, 0.100,
                                                         left=0.2075 / 0.3325 * (0.685 - 0.2625))),
    "HF": dict(w=1.903, h=0.580, x=32, y=2623, holes=grid(1.903, 0.580, 18, 1.66 / 17, 5, 0.0875)),
    "HS": dict(w=0.685, h=0.580, x=2570, y=2623, holes=grid(0.685, 0.580, 5, 0.0875, 5, 0.0875)),
}

SS = 4  # supersampling of the hole edge
alpha = np.full((N, N), 255, np.uint8)
r_px = R * TEXEL
for k, isl in ISL.items():
    isl["w_px"], isl["h_px"] = isl["w"] * TEXEL, isl["h"] * TEXEL
    assert isl["x"] + isl["w_px"] <= N - 32 and isl["y"] + isl["h_px"] <= N - 32, k
    for (u, v) in isl["holes"]:
        cx = isl["x"] + u * TEXEL; cy = N - (isl["y"] + v * TEXEL)  # image row from top
        x0, x1 = int(cx - r_px - 2), int(cx + r_px + 3); y0, y1 = int(cy - r_px - 2), int(cy + r_px + 3)
        ys, xs = np.mgrid[y0:y1, x0:x1]
        cov = np.zeros(ys.shape)
        for a in range(SS):
            for b in range(SS):
                px = xs + (a + 0.5) / SS; py = ys + (b + 0.5) / SS
                cov += ((px - cx) ** 2 + (py - cy) ** 2 <= r_px ** 2)
        cov /= SS * SS
        alpha[y0:y1, x0:x1] = np.minimum(alpha[y0:y1, x0:x1], np.round(255 * (1 - cov)).astype(np.uint8))

rgb = np.empty((N, N, 3), np.uint8); rgb[:] = PLATE
# holes also dark in RGB (visible where alpha is ignored); same coverage as the alpha edge
a_f = alpha.astype(float)[..., None] / 255
rgb = (np.array(PLATE) * a_f + np.array(HOLE_PREVIEW) * (1 - a_f)).round().astype(np.uint8)
Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(OUT / "T_K5_Diffuse_AC.1004.png", optimize=True)
Image.new("RGB", (N, N), ERM).save(OUT / "T_K5_ERM_AC.1004.png", optimize=True)
Image.new("RGB", (N, N), NORMAL).save(OUT / "T_K5_Normal_AC.1004.png", optimize=True)

# preview: holes dark, island borders red (not a delivery file)
a = alpha.astype(float)[..., None] / 255
prev = (rgb * a + np.array(HOLE_PREVIEW) * (1 - a)).astype(np.uint8)
for isl in ISL.values():
    x0, x1 = int(isl["x"]), int(isl["x"] + isl["w_px"]); y1 = N - int(isl["y"]); y0 = N - int(isl["y"] + isl["h_px"])
    prev[y0:y1, [x0, x1 - 1]] = (220, 0, 0); prev[[y0, y1 - 1], x0:x1] = (220, 0, 0)
Image.fromarray(prev).resize((1024, 1024), Image.LANCZOS).save(OUT.parent / "preview_AC_1004.png")

layout = {k: dict(w=v["w"], h=v["h"], x=v["x"], y=v["y"], n_holes=len(v["holes"])) for k, v in ISL.items()}
layout.update(texel=TEXEL, size=N, udim=1004)
(OUT.parent / "layout_AC_1004.json").write_text(json.dumps(layout, indent=1))
print(json.dumps(layout))
