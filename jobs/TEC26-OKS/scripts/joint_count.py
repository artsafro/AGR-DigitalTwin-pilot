"""new-case: count the vertical panel joints that a TEC26 delivery ACTUALLY shows per facade (pure numpy, no Blender).

Two measurement paths, both on delivered data only (never on spec fields or the generated texture period alone):
- mesh path (`mesh_facade_report`): along a horizontal line at height z on each facade, every sample point is located
  in a delivered triangle of the facade's panel field, its UV interpolated, the delivered texture sampled (VPM: the
  UDIM Diffuse tile of the triangle; NPM: the embedded 2048 atlas); dark runs are the joints;
- render path (`render_row`): the same counting on a pixel row of an orthographic facade render, with the camera
  metadata written by render_facades.py.
`count_joints` turns a luminance profile into joint centres and compares them with the sheet contract: joints at
field_lo + k * P (k = 1 .. ribs - 1), P = field / ribs. Half joints on the field edges (the field outline) are not
joints. A joint hidden by another finish (the door) is reported as hidden, not as missing, only where the profile
has no panel sample around it.
"""
import numpy as np

AXIS = {"+x": (0, 1), "-x": (0, 1), "+y": (1, 0), "-y": (1, 0)}  # normal -> (normal axis, along-facade axis)


def runs(mask):
    """[(start, end_exclusive)] of True runs of a 1-D bool array."""
    m = np.concatenate([[False], np.asarray(mask, bool), [False]])
    d = np.diff(m.astype(int))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def count_joints(s, lum, field_lo, field_hi, ribs, tol, dark=0.8, edge=0.25, footprint=0.0):
    """Joint centres (world metres) in a luminance profile `lum` sampled at positions `s` (NaN = no panel there).

    Dark = below `dark` x the median panel luminance. Runs whose centre lies within `edge` x P of a field edge are the
    field outline, not joints. Returns a report: found centres, expected positions, which are matched (within tol),
    hidden (no panel sample within max(tol, 6 mm)), extra (found but not expected), symmetric phase (first/last offsets).
    `footprint` (m, 0 <= footprint < P/2): half-width of a painted joint's dark footprint incl. its darkening halo
    (AC07 joint_dark). A hidden joint's halo may show beside the occluder: ONE dark run within `footprint` of a hidden
    joint is that joint's remnant (`hidden_partial`), and ONE such run for a visible joint whose centre the occluder
    shifted beyond tol is that joint (`clipped`); ONE such run beside a matched joint is the rest of its footprint cut
    off by the threshold (`split`) - in all cases only a run that ENDS at the occluder (NaN), at most one per joint;
    never a free-standing line. Default 0 = nothing absorbed."""
    s, lum = np.asarray(s, float), np.asarray(lum, float)
    P = (field_hi - field_lo) / ribs
    if isinstance(footprint, bool) or not isinstance(footprint, (int, float)) or not np.isfinite(footprint) or not (
            0 <= footprint < P / 2):
        raise ValueError(f"joint footprint must be finite in [0, P/2 = {P / 2:.4f}) m, got {footprint!r}")
    ok = np.isfinite(lum)
    if ok.sum() < 10:
        return {"ok": False, "reason": "no panel samples on this row", "found": [], "expected": ribs - 1}
    thr = dark * np.median(lum[ok])
    found = []
    touch = set()                                    # runs that end at an occluder (another finish, NaN)
    for a, b in runs(ok & (lum < thr)):
        c = float(s[a:b].mean())
        if field_lo + edge * P < c < field_hi - edge * P:
            found.append(c)
            if (a > 0 and not ok[a - 1]) or (b < len(ok) and not ok[b]):
                touch.add(c)
    exp = [field_lo + k * P for k in range(1, ribs)]
    hidden, matched, missing = [], [], []
    for e in exp:
        near = ok & (np.abs(s - e) <= max(tol, 0.006))  # a joint is visible only where panel surrounds it
        if not near.any():
            hidden.append(round(e, 4))
            continue
        hit = [f for f in found if abs(f - e) <= tol]
        (matched if hit else missing).append(round(e, 4))
    extra = [f for f in found if not any(abs(f - e) <= tol for e in exp)]
    partial, clipped, split = [], [], []   # a joint's dark footprint cut by the occluder: hidden / missing / matched
    for e, bucket in [(e, partial) for e in hidden] + [(e, clipped) for e in missing] + [(e, split) for e in matched]:
        near = [f for f in extra if abs(f - e) <= footprint and f in touch]
        if len(near) == 1:
            bucket.append(e)
            extra.remove(near[0])
    missing = [e for e in missing if e not in clipped]
    extra = [round(f, 4) for f in extra]
    first = found[0] - field_lo if found else None
    last = field_hi - found[-1] if found else None
    errs = [min(abs(f - e) for e in exp) for f in found] if found else []
    return {"ok": not missing and not extra and len(found) == len(exp) - len(hidden) + len(partial) + len(split),
            "hidden_partial": partial, "clipped": clipped, "split": split,
            "joints_found": len(found), "joints_expected": len(exp), "ribs_expected": ribs,
            "hidden_by_other_finish": hidden, "missing": missing, "extra": extra,
            "pitch_m": round(P, 6), "max_position_error_m": round(max(errs), 5) if errs else None,
            "first_joint_from_field_m": round(first, 4) if first is not None else None,
            "last_joint_to_field_m": round(last, 4) if last is not None else None,
            "found_m": [round(f, 4) for f in found]}


def local_median(lum, ok, win):
    """Median luminance of the panel samples within +-win/2 samples (a colour band - AC07 grey 7047 below +2.500,
    blue 5015 above - is a wide step, not a narrow dark joint: compare each sample with its own neighbourhood)."""
    out = np.full(lum.shape, np.nan)
    h = max(win // 2, 1)
    for i in range(len(lum)):
        seg = lum[max(0, i - h):i + h + 1][ok[max(0, i - h):i + h + 1]]
        if seg.size:
            out[i] = np.median(seg)
    return out


def symmetric(rep, tol):
    """Symmetric phase on a full (unhidden) row: the first and last joints sit one pitch inside the field edges."""
    a, b = rep.get("first_joint_from_field_m"), rep.get("last_joint_to_field_m")
    return a is not None and b is not None and abs(a - b) <= tol and abs(a - rep["pitch_m"]) <= tol


def tri_normal(p):
    n = np.cross(p[1] - p[0], p[2] - p[0])
    ln = np.linalg.norm(n)
    return n / ln if ln > 0 else n


def facade_triangles(V, F, keep, key, tol=1e-3):
    """Indices of triangles kept by `keep(t)` whose outward normal is facade `key` ('+x', ...)."""
    na, _ = AXIS[key]
    sign = 1 if key[0] == "+" else -1
    out = []
    for t, f in enumerate(F):
        if not keep(t):
            continue
        n = tri_normal(V[f])
        if abs(n[2]) <= tol and n[na] * sign > 1 - tol:
            out.append(t)
    return out


def field_extent(V, F, tris, key):
    _, aa = AXIS[key]
    pts = V[np.asarray([F[t] for t in tris]).ravel()]
    return float(pts[:, aa].min()), float(pts[:, aa].max()), float(pts[:, 2].min()), float(pts[:, 2].max())


def interpolate_uv(V, F, UV, tris, key, s, z, eps=1e-7):
    """UV at facade points (s along the facade axis, height z) inside the given triangles; NaN where none covers."""
    _, aa = AXIS[key]
    s = np.asarray(s, float)
    z = np.broadcast_to(np.asarray(z, float), s.shape)
    out = np.full(s.shape + (2,), np.nan)
    for t in tris:
        p = V[F[t]][:, [aa, 2]]
        uv = np.asarray(UV[t], float)
        (x0, y0), (x1, y1), (x2, y2) = p
        det = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(det) < 1e-12:
            continue
        l0 = ((y1 - y2) * (s - x2) + (x2 - x1) * (z - y2)) / det
        l1 = ((y2 - y0) * (s - x2) + (x0 - x2) * (z - y2)) / det
        l2 = 1 - l0 - l1
        inside = (l0 >= -eps) & (l1 >= -eps) & (l2 >= -eps) & np.isnan(out[..., 0])
        if inside.any():
            out[inside] = (l0[inside, None] * uv[0] + l1[inside, None] * uv[1] + l2[inside, None] * uv[2])
    return out


def bilinear(img, u, v):
    """Luminance (R+G+B) of `img` (rows from the top, UV v up) at local UV in [0, 1], bilinear, texel centres."""
    h, w = img.shape[:2]
    x = np.clip(u * w - 0.5, 0, w - 1.0001)
    y = np.clip((1 - v) * h - 0.5, 0, h - 1.0001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    L = img[..., :3].astype(float).sum(-1)
    return (L[y0, x0] * (1 - fx) * (1 - fy) + L[y0, x0 + 1] * fx * (1 - fy) + L[y0 + 1, x0] * (1 - fx) * fy
            + L[y0 + 1, x0 + 1] * fx * fy)


def sample_luminance(uv, tile_of):
    """tile_of(u, v) -> (image, u_local, v_local) for arrays; NaN UV stays NaN."""
    lum = np.full(uv.shape[:-1], np.nan)
    ok = np.isfinite(uv[..., 0])
    if ok.any():
        img_groups = tile_of(uv[ok, 0], uv[ok, 1])
        vals = np.full(ok.sum(), np.nan)
        for idx, img, ul, vl in img_groups:
            vals[idx] = bilinear(img, ul, vl)
        lum[ok] = vals
    return lum


def mesh_facade_report(V, F, UV, keep, key, ribs, tile_of, tol, step=0.0005, rows=None, field=None, footprint=0.0):
    """Joint count of one facade of a delivered mesh. `keep(t)`: triangle shows the patterned finish. Rows default to
    the panel field's 20 % and 95 % heights (the 95 % row runs above the door). Also checks a vertical profile through
    the middle of the first, middle and last rib for horizontal joints (there must be none)."""
    V = np.asarray(V, float)
    tris = facade_triangles(V, F, keep, key)
    if not tris:
        return {"ok": False, "reason": f"no patterned triangles facing {key}"}
    lo, hi, zlo, zhi = field if field else field_extent(V, F, tris, key)
    P = (hi - lo) / ribs
    s = np.arange(lo + step / 2, hi, step)
    out = {"triangles": len(tris), "field": [round(lo, 4), round(hi, 4)], "z": [round(zlo, 4), round(zhi, 4)],
           "rows": {}}
    ok = True
    for frac in (rows or (0.2, 0.95)):
        z = zlo + frac * (zhi - zlo)
        lum = sample_luminance(interpolate_uv(V, F, UV, tris, key, s, z), tile_of)
        r = count_joints(s, lum, lo, hi, ribs, tol, footprint=footprint)
        out["rows"][f"z={z:.3f}"] = r
        ok &= r["ok"]
    # rows whose first and last expected joints are visible (doors/windows may hide joints in between, AC07)
    exp_ends = (round(lo + P, 4), round(lo + (ribs - 1) * P, 4))
    full = [r for r in out["rows"].values() if "hidden_by_other_finish" in r
            and not set(exp_ends) & set(r["hidden_by_other_finish"])]
    out["symmetric"] = bool(full) and all(symmetric(r, tol) for r in full)
    out["symmetric_rows"] = len(full)
    zs = np.arange(zlo + 0.02, zhi - 0.02, step)
    hj = {}
    for k in (0, ribs // 2, ribs - 1):
        sc = lo + (k + 0.5) * P
        uv = interpolate_uv(V, F, UV, tris, key, np.full(zs.shape, sc), zs)
        lum = sample_luminance(uv, tile_of)
        okm = np.isfinite(lum)
        dark = okm & (lum < 0.8 * local_median(lum, okm, int(round(0.2 / step)))) if okm.any() else okm
        hj[f"rib{k + 1}"] = len(runs(dark))
    out["horizontal_joint_runs"] = hj
    out["no_horizontal_joints"] = all(v == 0 for v in hj.values())
    out["ok"] = bool(ok and out["symmetric"] and out["no_horizontal_joints"])
    return out


def render_row(img, view, axis_index, z, lo, hi, mask="blue"):
    """Luminance along the pixel row of world height z between world coordinates lo..hi on the facade axis of an
    orthographic render. `view`: {"center", "right", "up", "ortho_scale", "res"} from render_facades.py (horizontal
    sensor fit). Returns (s world positions, luminance; NaN where the pixel is not the panel). `mask`: "blue" = the
    RAL 5015 panel; "grey" = the RAL 7047 lower band of AC07 (neutral, panel lum 540..700 or joint lum 120..330, so
    RAL 7004 doors/plinth ~450, white RAL 9016 frames ~740 and the black background are not panel)."""
    c, r, u = (np.asarray(view[k], float) for k in ("center", "right", "up"))
    W, H = view["res"]
    scale = view["ortho_scale"] / W                       # metres per pixel (square pixels)
    y = int(round(H / 2 - (z - c[2]) / scale - 0.5))
    xs = np.arange(W)
    world = c[None, :] + r[None, :] * ((xs + 0.5 - W / 2) * scale)[:, None]
    s = world[:, axis_index]
    sel = (s >= min(lo, hi)) & (s <= max(lo, hi))
    rgb = img[y, :, :3].astype(float)
    lum = rgb.sum(-1)
    if mask == "grey":  # pure neutral (7047 panel 207 and its joints 73 and their blends; RAL 7004 has a +7 green tint,
        # so a 60/40 anti-aliased 7004|7047 door-edge pixel has tint 4 and lum < 0.85 x panel: <= 2 keeps it out)
        neutral = (rgb.max(-1) - rgb.min(-1)) <= 2
        lum[~(neutral & (lum >= 120) & (lum <= 700))] = np.nan
    elif mask == "blue":
        lum[(rgb[:, 2] - rgb[:, 0]) <= 25] = np.nan      # not the blue panel (frame, door, background): no sample
    else:
        raise ValueError(f"unknown panel mask {mask!r}")
    order = np.argsort(s[sel])
    return s[sel][order], lum[sel][order]
