"""Shared core of the skeleton cell `vpm-to-npm` (#1737): accepted VPM -> NPM by Artem's practice.

Pattern: n/a | new-case: tris count, interior removal, glass-on-white merge and the fixed tris-budget ladder of the
`vpm-to-npm` cell (stages tris-count / remove-interiors / glass-merge / budget-ladder in docs/agents/skeletons.json).

Artem 2026-11-21 (#1737): count tris first; ALWAYS delete interiors (inner capsule walls, interior UDIMs); build the
NPM atlas and lay all geometry on it (stage `atlas`, owner tools/materials/npm_atlas_udim.py, the VPM_to_NPM.ms /
GeoAGR «Unwrap to Atlas» logic); glass merged into ONE object on pure-white atlas pixels. Only while still over the
tris budget, in this order: fewer segments on cylinders, railings / AC units as one-sided opacity planes, last
windows and stained glass as planes with the window image. No ProOptimizer; the body mesh is not edited.

Pure functions; the Blender glue is tools/blender/vpm_to_npm.py. Every refusal is a VpmNpmError naming the element;
nothing is defaulted: interiors are an explicit config ({"udims": [...], "objects": [...]}, empty lists = none),
every face ends kept or in the drop list with its reason, a ladder step that is not supplied while over budget is
reported in `missing` (never treated as done). Pixel arrays are rows top-down (row 0 = v 1), RGB 0-255.
"""
from __future__ import annotations

import importlib.util
import math
import numbers
import os

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_UDIM = os.path.normpath(os.path.join(_HERE, "..", "..", "adapters", "max", "agr_tools", "udimtile_core.py"))
_spec = importlib.util.spec_from_file_location("udimtile_core_vpm_npm", _UDIM)
_udimtile = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_udimtile)

LADDER = ("cylinder-segments", "opacity-planes", "window-planes")
INTERIOR_KEYS = ("udims", "objects")
WHITE = 255


class VpmNpmError(ValueError):
    """Input the vpm-to-npm cell refuses, naming the element."""


def count_tris(faces):
    """Triangles of a list of faces (vertex-index lists or {'verts': [...]}) after a fan triangulation."""
    if not faces:
        raise VpmNpmError("tris-count: empty mesh")
    total = 0
    for i, f in enumerate(faces):
        n = len(f["verts"]) if isinstance(f, dict) else len(f)
        if n < 3:
            raise VpmNpmError(f"tris-count: face {i} has {n} corners (< 3)")
        total += n - 2
    return total


def face_udim(uv):
    """UDIM tile of one face from its UV corners (udimtile_core.face_tile, strict)."""
    try:
        return _udimtile.face_tile(uv, strict=True)
    except _udimtile.UdimDomainError as exc:
        raise VpmNpmError(f"face UV: {exc}") from None


def _int_list(value, key):
    if not isinstance(value, list):
        raise VpmNpmError(f"interiors config: {key!r} must be a list, got {value!r}")
    return value


def remove_interiors(faces, interiors):
    """Drop interior faces: UDIM tiles in interiors['udims'] and objects in interiors['objects'].

    faces: [{'object': str, 'verts': [...], 'uv': [(u, v), ...]}]. Returns kept face indices, the drop list
    [{'face', 'object', 'reason'}] and tris before/after. A tile or object named in the config but absent from the
    mesh, a non-integer tile, an unknown/missing key, or a config that drops every face is an error."""
    if not isinstance(interiors, dict):
        raise VpmNpmError(f"interiors config must be {{'udims': [...], 'objects': [...]}}, got {interiors!r}")
    for k in interiors:
        if k not in INTERIOR_KEYS:
            raise VpmNpmError(f"interiors config: unknown key {k!r}")
    for k in INTERIOR_KEYS:
        if k not in interiors:
            raise VpmNpmError(f"interiors config: missing key {k!r}")
    udims = _int_list(interiors["udims"], "udims")
    objects = _int_list(interiors["objects"], "objects")
    for t in udims:
        if isinstance(t, bool) or not isinstance(t, numbers.Integral):
            raise VpmNpmError(f"interiors config: udim {t!r} must be an integer tile")
    for o in objects:
        if not isinstance(o, str) or not o:
            raise VpmNpmError(f"interiors config: object {o!r} must be a name")
    if not faces:
        raise VpmNpmError("remove-interiors: empty mesh")
    tiles = [face_udim(f["uv"]) for f in faces]
    names = [f["object"] for f in faces]
    for t in udims:
        if t not in tiles:
            raise VpmNpmError(f"interiors config: udim {t} has no face in the mesh")
    for o in objects:
        if o not in names:
            raise VpmNpmError(f"interiors config: object {o} is not in the mesh")
    kept, dropped = [], []
    for i, f in enumerate(faces):
        if names[i] in objects:
            dropped.append({"face": i, "object": names[i], "reason": f"interior_object {names[i]}"})
        elif tiles[i] in udims:
            dropped.append({"face": i, "object": names[i], "reason": f"interior_udim {tiles[i]}"})
        else:
            kept.append(i)
    if not kept:
        raise VpmNpmError("interiors config drops every face of the mesh")
    return {"kept": kept, "dropped": dropped, "tris_before": count_tris(faces),
            "tris_after": count_tris([faces[i] for i in kept])}


def _rgb(px):
    a = np.asarray(px)
    if a.ndim != 3 or a.shape[2] < 3 or not a.shape[0] or not a.shape[1]:
        raise VpmNpmError(f"atlas pixels must be H x W x RGB, got shape {a.shape}")
    return a[:, :, :3].astype(np.int64)


def _white_mask(px):
    return (_rgb(px) == WHITE).all(axis=2)


def _sat(mask):
    s = np.zeros((mask.shape[0] + 1, mask.shape[1] + 1), dtype=np.int64)
    s[1:, 1:] = mask.astype(np.int64).cumsum(0).cumsum(1)
    return s


def _window_sums(sat, n):
    return sat[n:, n:] - sat[:-n, n:] - sat[n:, :-n] + sat[:-n, :-n]


def find_white(px, min_px):
    """Largest square of pure-white (255, 255, 255) atlas pixels as (x0, y0, n, n), or None below min_px."""
    if isinstance(min_px, bool) or not isinstance(min_px, numbers.Integral) or min_px < 1:
        raise VpmNpmError(f"find_white: min_px must be a positive integer, got {min_px!r}")
    mask = _white_mask(px)
    sat = _sat(mask)
    lo, hi, best = min_px, min(mask.shape), None
    while lo <= hi:
        n = (lo + hi) // 2
        hits = np.argwhere(_window_sums(sat, n) == n * n)
        if len(hits):
            best = (int(hits[0][1]), int(hits[0][0]), n, n)
            lo = n + 1
        else:
            hi = n - 1
    return best


def reserve_white(px, occupied, size_px, pad):
    """Paint a size_px square of pure white where no occupied rect (x, y, w, h) is within pad px; returns it."""
    a = np.asarray(px)
    h, w = a.shape[0], a.shape[1]
    busy = np.zeros((h, w), dtype=bool)
    for x, y, rw, rh in occupied:
        busy[max(0, y - pad):y + rh + pad, max(0, x - pad):x + rw + pad] = True
    busy[:pad, :] = busy[h - pad:, :] = True
    busy[:, :pad] = busy[:, w - pad:] = True
    if size_px > min(h, w):
        raise VpmNpmError(f"reserve_white: no free {size_px} px cell in a {w} x {h} atlas")
    free = np.argwhere(_window_sums(_sat(busy), size_px) == 0)
    if not len(free):
        raise VpmNpmError(f"reserve_white: no free {size_px} px cell outside the atlas cells (pad {pad} px)")
    y0, x0 = int(free[0][0]), int(free[0][1])
    if isinstance(px, np.ndarray):
        px[y0:y0 + size_px, x0:x0 + size_px, :3] = WHITE
    else:
        for y in range(y0, y0 + size_px):
            for x in range(x0, x0 + size_px):
                px[y][x] = (WHITE, WHITE, WHITE)
    return (x0, y0, size_px, size_px)


def sample(px, u, v):
    """RGB of the atlas pixel under (u, v) (nearest, v up)."""
    a = np.asarray(px)
    h, w = a.shape[0], a.shape[1]
    if not (math.isfinite(u) and math.isfinite(v) and 0 <= u <= 1 and 0 <= v <= 1):
        raise VpmNpmError(f"sample: uv ({u}, {v}) outside the atlas")
    x, y = min(int(u * w), w - 1), min(int((1 - v) * h), h - 1)
    return tuple(int(c) for c in a[y, x, :3])


def glass_merge(faces, px, name, cell):
    """Merge every glass face into ONE object `name` with all UVs inside the pure-white atlas cell (x0, y0, w, h).

    The cell must be pure white; each glass UV corner is read back on the atlas and must be white (else error)."""
    if not faces:
        raise VpmNpmError("glass-merge: no glass faces")
    a = np.asarray(px)
    h, w = a.shape[0], a.shape[1]
    x0, y0, cw, ch = cell
    if cw < 3 or ch < 3 or x0 < 0 or y0 < 0 or x0 + cw > w or y0 + ch > h:
        raise VpmNpmError(f"glass-merge: cell {cell} outside the {w} x {h} atlas or under 3 px")
    if not _white_mask(a[y0:y0 + ch, x0:x0 + cw]).all():
        raise VpmNpmError(f"glass-merge: atlas cell {cell} is not pure white")
    us = [p[0] for f in faces for p in f["uv"]]
    vs = [p[1] for f in faces for p in f["uv"]]
    if not all(math.isfinite(c) for c in us + vs):
        raise VpmNpmError("glass-merge: non-finite glass UV")
    m = max(1, min(cw, ch) // 4)
    ix0, ix1, iy0, iy1 = x0 + m, x0 + cw - m, y0 + m, y0 + ch - m   # inner pixel box, top-down rows
    du, dv = (max(us) - min(us)) or 1.0, (max(vs) - min(vs)) or 1.0
    merged_from, out, samples, white = [], [], 0, 0
    for f in faces:
        if f["object"] not in merged_from:
            merged_from.append(f["object"])
        uv = []
        for u, v in f["uv"]:
            pxx = ix0 + (u - min(us)) / du * (ix1 - ix0)
            pyy = iy1 - (v - min(vs)) / dv * (iy1 - iy0)
            nu, nv = pxx / w, 1 - pyy / h
            samples += 1
            white += sample(a, nu, nv) == (WHITE, WHITE, WHITE)
            uv.append((nu, nv))
        out.append({**f, "object": name, "uv": uv})
    if white != samples:
        raise VpmNpmError(f"glass-merge: {samples - white} of {samples} glass UVs off the white cell {cell}")
    return {"object": name, "merged_from": merged_from, "faces": out, "cell": tuple(cell),
            "uv_samples": samples, "white_samples": white}


def budget_ladder(tris, budget, steps):
    """Run the fixed ladder steps (LADDER order) only while tris > budget; steps = {step: callable(tris) -> tris}.

    Returns {'start', 'budget', 'ran', 'skipped', 'missing', 'final', 'within'}; a needed step that is not supplied
    goes to `missing` and leaves `within` false. Exactly at the budget is within."""
    if isinstance(budget, bool) or not isinstance(budget, numbers.Real) or not math.isfinite(budget) or budget <= 0:
        raise VpmNpmError(f"budget-ladder: budget must be a finite number > 0, got {budget!r}")
    if isinstance(tris, bool) or not isinstance(tris, numbers.Integral) or tris < 0:
        raise VpmNpmError(f"budget-ladder: tris must be a non-negative integer, got {tris!r}")
    for k in steps:
        if k not in LADDER:
            raise VpmNpmError(f"budget-ladder: unknown ladder step {k!r} (allowed: {', '.join(LADDER)})")
    cur, ran, skipped, missing = tris, [], [], []
    for step in LADDER:
        if cur <= budget:
            skipped.append(step)
        elif step not in steps:
            missing.append(step)
        else:
            new = steps[step](cur)
            if isinstance(new, bool) or not isinstance(new, numbers.Integral) or not 0 <= new < cur:
                raise VpmNpmError(f"budget-ladder: step {step} did not reduce the tris ({cur} -> {new!r})")
            ran.append(step)
            cur = int(new)
    return {"start": tris, "budget": budget, "ran": ran, "skipped": skipped, "missing": missing, "final": cur,
            "within": cur <= budget}
