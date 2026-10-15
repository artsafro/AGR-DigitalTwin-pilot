"""Five orthographic views (four facades + top) of a model dump as small flat-shaded png (painter's algorithm).

    uv run python jobs/butovskaya-sosh1000/scripts/render_views.py --model C:/x/butovskaya-npm/model_dump.json \
        --out docs/experiments/autoresearch-butovskaya-npm --etalon
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate import SNAP, etalon_silhouettes  # noqa: E402

# view -> (right axis, sign), (up axis, sign), (towards-viewer axis, sign)
VIEWS = {"south": ((0, 1), (2, 1), (1, -1)), "north": ((0, -1), (2, 1), (1, 1)),
         "east": ((1, 1), (2, 1), (0, 1)), "west": ((1, -1), (2, 1), (0, -1)), "top": ((0, 1), (1, 1), (2, 1))}
COLOURS = {1: (205, 190, 170), 11: (90, 130, 190), 12: (150, 90, 60), 21: (150, 150, 150), 0: (190, 180, 170)}


def render(corners, mids, view, px_per_m, path):
    (ra, rs), (ua, us), (da, ds) = VIEWS[view]
    u, v, d = corners[:, :, ra] * rs, corners[:, :, ua] * us, corners[:, :, da] * ds
    n = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    toward = np.zeros(3)
    toward[da] = ds
    facing = n @ toward
    light = np.clip(0.55 + 0.45 * (n @ np.array([0.3, -0.5, 0.8]) / np.linalg.norm([0.3, -0.5, 0.8])), 0.3, 1.0)
    u0, v1 = u.min(), v.max()
    w, h = int((u.max() - u0) * px_per_m) + 4, int((v1 - v.min()) * px_per_m) + 4
    im = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(im)
    for i in np.argsort(d.mean(axis=1)):
        if facing[i] < -1e-6:
            continue
        base = np.array(COLOURS.get(int(mids[i]), COLOURS[0]), float) * light[i]
        pts = [((u[i, k] - u0) * px_per_m + 2, (v1 - v[i, k]) * px_per_m + 2) for k in range(3)]
        dr.polygon(pts, fill=tuple(int(c) for c in base))
    im.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="C:/x/butovskaya-npm/model_dump.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="model")
    ap.add_argument("--px", type=float, default=6.0)
    ap.add_argument("--etalon", action="store_true", help="also render the snapshot (its silhouettes, as the metric sees it)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    from twinqa.geometry.mesh import from_dump
    m = from_dump(json.loads(Path(a.model).read_text(encoding="utf-8")))
    for view in VIEWS:
        render(m.corners(), m.material_ids, view, a.px, out / f"{a.prefix}-{view}.png")
    if a.etalon:                    # the reference as the metric sees it: the silhouettes of the snapshot meshes
        sil = etalon_silhouettes(SNAP)
        for view in VIEWS:
            render_silhouette(sil, view, a.px, out / f"snapshot-{view}.png")


# view -> (silhouette of evaluate.VIEWS, mirror the horizontal axis); measure.VIEWS: x = (y, z), y = (x, z), top = (x, y)
SIL_OF = {"south": ("y", False), "north": ("y", True), "east": ("x", False), "west": ("x", True), "top": ("top", False)}


def render_silhouette(sil, view, px_per_m, path):
    import shapely
    key, mirror = SIL_OF[view]
    g = sil[key]
    x0, y0, x1, y1 = g.bounds
    w, h = int((x1 - x0) * px_per_m) + 4, int((y1 - y0) * px_per_m) + 4
    im = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(im)

    def pts(coords):
        return [(((x1 - x) if mirror else (x - x0)) * px_per_m + 2, (y1 - y) * px_per_m + 2) for x, y in coords]
    for p in shapely.get_parts(g):
        if p.geom_type != "Polygon":
            continue
        dr.polygon(pts(p.exterior.coords), fill=(150, 150, 150))
        for hole in p.interiors:
            dr.polygon(pts(hole.coords), fill=(255, 255, 255))
    im.save(path)


if __name__ == "__main__":
    main()
