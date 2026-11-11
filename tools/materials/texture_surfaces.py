"""Generate tileable synthetic surface maps at 1000 px/m [D207] for the materials library [D239].

Called by `tools/materials/inbox_maps.py` for spec sources with a `generate` block; returns PIL images, writes nothing.
Every recipe is periodic by construction over `period_m`, so the master is exactly round(period_m * 1000) px:

* `base_map`: the AGR Tools K3 grey mask (`adapters/max/agr_tools/tiles_core.py`, same module/joint/bond as the
  tools use), recoloured with the record RGB, DirectX normal from the joints. Nothing is re-implemented here.
* `pebbles`: rounded stones packed without overlap on a torus, per-stone tone, dark lower layer; 1 m period.
* `membrane`: PVC / bitumen roof membrane: fine periodic grain (FFT-filtered noise); optional roll seams
  (overlap step, weld strip, edge line) every `seam_every` metres along U.
* `profiled_sheet`: trapezoid sheet, ribs along V, pitch / height / shelves in metres; 3.6 m period.

Images: `d` (RGB colour), `n` (DirectX normal, green down), `mask` (base maps only: R body grey, G joint).

Pattern: new-case — periodic synthetic library surfaces; no registry pattern covers texture generation.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "adapters/max/agr_tools"))
import tiles_core as tc  # noqa: E402

PX_PER_M = 1000.0  # [D207]


def _img(rows, w, h):
    return Image.frombytes("RGB", (w, h), b"".join(rows))


def _rgb(a):
    return Image.fromarray(np.clip(np.rint(a), 0, 255).astype(np.uint8), "RGB")


def _normal(height_m, px_m):
    """DirectX normal (green down) of a periodic height field in metres; px_m = pixel size in metres."""
    dx = (np.roll(height_m, -1, 1) - np.roll(height_m, 1, 1)) / (2 * px_m)
    dy = (np.roll(height_m, -1, 0) - np.roll(height_m, 1, 0)) / (2 * px_m)
    n = np.stack([-dx, dy, np.ones_like(dx)], -1)  # +Y of the image goes down: DirectX green = -dh/dv(up) = +dy
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return _rgb((n * 0.5 + 0.5) * 255)


def _noise(size, sigma_px, rng):
    """Periodic Gaussian-filtered white noise, zero mean, unit std."""
    f = np.fft.fft2(rng.standard_normal((size, size)))
    k = np.fft.fftfreq(size)
    kk = k[:, None] ** 2 + k[None, :] ** 2
    a = np.real(np.fft.ifft2(f * np.exp(-2 * (np.pi * sigma_px) ** 2 * kk)))
    return (a - a.mean()) / (a.std() + 1e-9)


def base_map(name, rgb):
    s, grey, result, findings = tc.check_base(name, None, rals=[{"code": "record", "rgb": list(rgb)}])
    if findings and any(f["code"] not in ("module_stretched",) for f in findings):
        raise SystemExit(f"base map {name}: {findings}")
    ref = tc.grey_ref(tc.body_histogram(grey))
    luts, joint = tc.recolour_luts(list(rgb), ref)
    w = h = s["size_px"]
    info = {k: result[k] for k in ("size_px", "period_m", "px_per_m_eff", "seam_levels", "recolour")}
    info.update({k: result[k] for k in ("module_m", "counts", "stretch_pct", "joint_m", "bond", "grain_m", "cells")
                 if k in result})
    return {
        "mask": _img(tc.mask_rows(grey), w, h),
        "d": _img(tc.colour_rows(grey, luts, joint), w, h),
        "n": _img(tc.normal_rows(grey), w, h),
    }, s["period_m"], info


def _pack(rng, period_m, r_min, r_max, gap, tries, pts, rs):
    """Add non-overlapping disks on a torus to (pts, rs), largest first (dart throwing)."""
    for r in np.sort(rng.uniform(r_min, r_max, tries))[::-1]:
        p = rng.random(2) * period_m
        if len(rs):
            d = (pts - p + period_m / 2) % period_m - period_m / 2
            if np.any(np.hypot(d[:, 0], d[:, 1]) < rs + r + gap):
                continue
        pts, rs = np.vstack([pts, p]), np.append(rs, r)
    return pts, rs


def pebbles(rgb, seed, period_m=1.0, d_min=0.02, d_max=0.06, fill_min=0.006, gap=0.0015, tries=30000):
    """Rounded pebbles d_min..d_max packed without overlap on a torus (largest first), then smaller stones
    fill_min..d_min in the gaps; slightly elliptic, dome height; a dark lower stone layer in the gaps."""
    size = int(round(period_m * PX_PER_M))
    rng = np.random.default_rng(seed)
    sites, radius = _pack(rng, period_m, d_min / 2, d_max / 2, gap, tries, np.empty((0, 2)), np.empty(0))
    n_main = len(radius)
    sites, radius = _pack(rng, period_m, fill_min / 2, d_min / 2, gap, 2 * tries, sites, radius)
    n = len(radius)
    squash = rng.uniform(0.82, 1.0, n)
    angle = rng.uniform(0, np.pi, n)
    tone = rng.normal(1.0, 0.08, n)
    hue = rng.normal(0.0, 0.015, (n, 3))
    height = np.zeros((size, size), np.float32)
    dome_all = np.zeros((size, size), np.float32)
    stone = np.zeros((size, size), np.float32)
    col = np.zeros((size, size, 3), np.float32)
    base = np.asarray(rgb, np.float32)
    for i in range(n):  # disks do not overlap: paint each in its own (wrapped) window
        r = radius[i]
        cx, cy = sites[i] * PX_PER_M - 0.5
        k = int(np.ceil(r * PX_PER_M)) + 1
        xs = np.arange(int(cx) - k, int(cx) + k + 2)
        ys = np.arange(int(cy) - k, int(cy) + k + 2)
        dx = (xs[None, :] - cx) / PX_PER_M
        dy = (ys[:, None] - cy) / PX_PER_M
        ca, sa = np.cos(angle[i]), np.sin(angle[i])
        q = np.sqrt((dx * ca + dy * sa) ** 2 + ((dy * ca - dx * sa) / squash[i]) ** 2) / r
        inside = q < 1
        dome = np.where(inside, np.sqrt(np.clip(1 - q ** 2, 0, 1)), 0)
        iy, ix = np.ix_(ys % size, xs % size)
        height[iy, ix] = np.where(inside, 0.5 * r * squash[i] * dome, height[iy, ix])
        dome_all[iy, ix] = np.where(inside, dome, dome_all[iy, ix])
        stone[iy, ix] = np.maximum(stone[iy, ix], np.clip((1 - q) * r * PX_PER_M, 0, 1))  # 1 px anti-alias
        c = base * tone[i] * (1 + hue[i])
        col[iy, ix] = np.where(inside[..., None], c, col[iy, ix])
    shade = 0.72 + 0.28 * dome_all  # ambient occlusion only, no directional light
    col *= (shade * (1 + 0.03 * _noise(size, 2.0, rng)))[..., None]
    under = base * 0.42 * (1 + 0.12 * _noise(size, 2.5, rng))[..., None]  # lower layer of stones, in shadow
    d = col * stone[..., None] + under * (1 - stone[..., None])
    return {"d": _rgb(d), "n": _normal(height, 1 / PX_PER_M)}, period_m, {
        "size_px": size, "period_m": period_m, "stones": n_main, "fill_stones": n - n_main,
        "diameter_m": [d_min, d_max], "fill_diameter_m": [fill_min, d_min], "gap_m": gap,
        "stone_cover": round(float(stone.mean()), 3)}


def membrane(rgb, seed, period_m=1.0, grain=0.012, mottle=0.03, seam_every=None, overlap=0.10, thickness=0.0015,
             weld=0.04, weld_tone=-0.04, edge_line=0.003, edge_tone=-0.12):
    """Roof membrane. With `seam_every` (m, must divide period_m): roll seams run along V every seam_every; the
    upper roll's edge is at x = 0 (a height step of `thickness`), the overlap band [0, overlap) is double thickness,
    the welded strip [0, weld) and the thin edge line (weld bead / bitumen squeeze-out) are tinted."""
    size = int(round(period_m * PX_PER_M))
    rng = np.random.default_rng(seed)
    fine = _noise(size, 1.2, rng)
    low = _noise(size, 60.0, rng)
    tint = 1 + grain * fine + mottle * low
    height = 0.00015 * fine
    info = {"size_px": size, "period_m": period_m, "grain": grain, "mottle": mottle}
    if seam_every:
        n = period_m / seam_every
        if abs(n - round(n)) > 1e-6:
            raise SystemExit(f"membrane: seam step {seam_every} m does not divide {period_m} m")
        x = ((np.arange(size) + 0.5) / PX_PER_M) % seam_every  # metres from the upper roll's edge
        ramp = np.clip(x * PX_PER_M, 0, 1)  # 1 px anti-aliased step at the edge
        band = ramp * np.clip((overlap - x) / 0.02, 0, 1)  # the lower roll's edge under the upper one: soft
        height = height + thickness * band[None, :]
        tone = np.where(x < weld, weld_tone, 0.0) + np.where(x < edge_line, edge_tone, 0.0)
        tint = tint * (1 + tone[None, :])
        info.update({"seam_every_m": seam_every, "seams": int(round(n)), "overlap_m": overlap,
                     "thickness_m": thickness, "weld_m": weld, "edge_line_m": edge_line})
    d = np.asarray(rgb, np.float32)[None, None, :] * tint[..., None]
    return {"d": _rgb(d), "n": _normal(height, 1 / PX_PER_M)}, period_m, info


def profiled_sheet(rgb, seed, period_m=3.6, pitch=0.1, rib_h=0.021, top=0.025, slope=0.0125):
    """Trapezoid profile along U (ribs run along V): bottom shelf, slope, top shelf, slope inside one pitch."""
    size = int(round(period_m * PX_PER_M))
    waves = period_m / pitch
    if abs(waves - round(waves)) > 1e-6:
        raise SystemExit(f"profiled_sheet: pitch {pitch} m does not divide {period_m} m")
    rng = np.random.default_rng(seed)
    x = ((np.arange(size) + 0.5) / PX_PER_M) % pitch
    bottom = pitch - top - 2 * slope
    prof = np.where(x < bottom, 0.0,
                    np.where(x < bottom + slope, (x - bottom) / slope,
                             np.where(x < bottom + slope + top, 1.0, 1 - (x - bottom - slope - top) / slope)))
    height = np.tile(prof * rib_h, (size, 1))
    d = np.asarray(rgb, np.float32)[None, None, :] * (1 + 0.012 * _noise(size, 1.5, rng))[..., None]
    return {"d": _rgb(d), "n": _normal(height, 1 / PX_PER_M)}, period_m, {
        "size_px": size, "period_m": period_m, "pitch_m": pitch, "rib_h_m": rib_h, "top_m": top, "slope_m": slope,
        "bottom_m": round(bottom, 6), "waves": int(round(waves))}


RECIPES = {"pebbles": pebbles, "membrane": membrane, "profiled_sheet": profiled_sheet}


def generate(gen: dict):
    """gen = {"recipe": "base_map", "base_map": name, "rgb": [r, g, b]} or {"recipe": <RECIPES>, "rgb", "seed",
    **params}. Returns (images, period_m, info)."""
    rgb = gen["rgb"]
    if gen["recipe"] == "base_map":
        return base_map(gen["base_map"], rgb)
    params = {k: v for k, v in gen.items() if k not in ("recipe", "rgb", "seed")}
    return RECIPES[gen["recipe"]](rgb, gen["seed"], **params)
