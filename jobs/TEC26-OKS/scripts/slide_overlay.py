"""new-case: research (#769) - rectified presentation-slide overlay of the frame bands and ribs on one AC08 facade.

Method (Texture2LoD3, arXiv 2504.05249: a prior building model is the planar target that ortho-rectifies an image):
the slide facade is mapped onto the facade plane of the delivered VPM by a 4-point DLT homography, from the slide's
body-outline corners (sub-pixel line fits on the slide pixels) to the model's body corners (readback geometry, camera
"right" coordinate u and height z, metres). The VPM render goes into the same (u, z) frame through its orthographic
camera (renders.json). Both are resampled at `px_per_m` (default 200) and the SAME profile measurement runs on both:
the field-outline lines (the inner edges of the four frame bands) and the joint lines. Offsets are reported in px of
the rectified frame; the overlay passes when every band-edge offset is finite and <= tol_px.

Registration `model` (default) = the Texture2LoD3 target above. Registration `datum` = the drawing's own body size
(sheet size_mm) centred on the model body, body bottom at +-0.000 (what compare_facades.py does for the sheets).

Research only: no checker, gate or threshold reads this module (issue #769, report docs/experiments/issue-769-slide-overlay.md).

Usage: uv run python slide_overlay.py <spec.json> <sheet-facades.json> <renders_dir> <vpm.readback.json> <new_out_dir>
           [--facade 1-2] [--px-per-m 200] [--tol-px 2] [--register model|datum]
           [--plant-u M] [--plant-top-band M]
  --plant-u M         planted error: the delivered facade moved by M metres along u (camera centre offset by -M).
  --plant-top-band M  planted error: the render rows of the top field outline moved M metres down (band M taller).
Exit 0 = overlay pass, 1 = overlay fail (offset > tol), 2 = refused input (message on stderr, nothing written).
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import joint_count  # noqa: E402

VIEW = {"+y": "north", "-y": "south", "+x": "east", "-x": "west"}
Z_TOP, Z_BOT, PAD = 2.85, -0.45, 0.3   # rectified frame: metres above / below +-0.000 and beside the body
EDGE_KEEP = 0.03                       # profile windows stay this far inside the body (excludes the body outline)
SLIDE_DARK, RENDER_DARK = 0.75, 0.85  # line = HSV value below this x the profile median: the slide_count / render
#                                       joint_count factors (a render's thin field outline reaches only ~0.79)
EDGES = ("field_left", "field_right", "field_top", "field_bottom")


def lum(rgb):
    return np.asarray(rgb, float)[..., :3].sum(-1)


def value(rgb):
    """HSV value (max channel): a drawn/painted dark line is dark in every channel, the render's red +-0.000 marker
    line is not (on the RGB sum it reads as dark as a thin field outline, ~0.8 x the panel)."""
    return np.asarray(rgb, float)[..., :3].max(-1)


def homography(src, dst):
    """3x3 H with dst ~ H @ [src, 1] from >= 4 point pairs (normalised DLT). Raises ValueError on non-finite or
    degenerate input (fewer than 4 points, 3 collinear points, rank < 8)."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    if src.shape != dst.shape or src.ndim != 2 or src.shape[1] != 2 or len(src) < 4:
        raise ValueError(f"homography needs >= 4 matching 2-D point pairs, got {src.shape} and {dst.shape}")
    if not (np.isfinite(src).all() and np.isfinite(dst).all()):
        raise ValueError("homography: non-finite point")

    def norm(p):
        c = p.mean(0)
        d = np.sqrt(((p - c) ** 2).sum(1)).mean()
        if not d > 0:
            raise ValueError("homography: all points coincide")
        s = np.sqrt(2) / d
        return np.array([[s, 0, -s * c[0]], [0, s, -s * c[1]], [0, 0, 1]])

    for P in (src, dst):
        for i in range(len(P)):
            for j in range(i + 1, len(P)):
                for k in range(j + 1, len(P)):
                    a, b = P[j] - P[i], P[k] - P[i]
                    if abs(a[0] * b[1] - a[1] * b[0]) <= 1e-12 * max(1.0, (a ** 2).sum() * (b ** 2).sum()):
                        raise ValueError(f"homography: points {i},{j},{k} are collinear")
    Ts, Td = norm(src), norm(dst)
    s = (Ts @ np.c_[src, np.ones(len(src))].T).T
    d = (Td @ np.c_[dst, np.ones(len(dst))].T).T
    A = []
    for (x, y, _), (u, v, _) in zip(s, d):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    _, sv, vt = np.linalg.svd(np.asarray(A))
    if sv[7] <= 1e-10 * sv[0]:
        raise ValueError("homography: degenerate point configuration")
    H = np.linalg.inv(Td) @ vt[-1].reshape(3, 3) @ Ts
    return H / H[2, 2]


def apply_h(H, pts):
    p = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ np.asarray(H, float).T
    return p[:, :2] / p[:, 2:3]


def bilinear(img, x, y, fill=255.0):
    """Sample img (H, W, C) at continuous pixel coordinates (pixel k covers [k, k+1)); outside = fill."""
    img = np.asarray(img, float)
    Hh, Ww = img.shape[:2]
    xf, yf = x - 0.5, y - 0.5
    x0, y0 = np.floor(xf).astype(int), np.floor(yf).astype(int)
    ax, ay = (xf - x0)[..., None], (yf - y0)[..., None]
    out = np.zeros(x.shape + (img.shape[2],))
    for dx, dy, w in ((0, 0, (1 - ax) * (1 - ay)), (1, 0, ax * (1 - ay)), (0, 1, (1 - ax) * ay), (1, 1, ax * ay)):
        xi, yi = x0 + dx, y0 + dy
        inside = ((xi >= 0) & (xi < Ww) & (yi >= 0) & (yi < Hh))[..., None]
        v = img[np.clip(yi, 0, Hh - 1), np.clip(xi, 0, Ww - 1)]
        out += w * np.where(inside, v, fill)
    return out


def frame(body, pxm):
    """Rectified frame around the body (u_lo, u_hi, z_lo, z_hi metres): origin, size in px."""
    u0 = body[0] - PAD
    w = int(round((body[1] - body[0] + 2 * PAD) * pxm))
    h = int(round((Z_TOP - Z_BOT) * pxm))
    return {"u0": u0, "z_top": Z_TOP, "px_per_m": pxm, "w": w, "h": h}


def frame_uz(fr, ss=3):
    """(u, z) of ss x ss sub-samples of every rectified pixel: arrays (h, w, ss*ss)."""
    o = (np.arange(ss) + 0.5) / ss
    j = (np.arange(fr["w"])[:, None] + o[None, :]).ravel()
    i = (np.arange(fr["h"])[:, None] + o[None, :]).ravel()
    u = fr["u0"] + j / fr["px_per_m"]
    z = fr["z_top"] - i / fr["px_per_m"]
    U, Z = np.meshgrid(u, z)
    return U, Z, ss


def _pool(a, ss):
    h, w = a.shape[0] // ss, a.shape[1] // ss
    return a.reshape(h, ss, w, ss, -1).mean((1, 3))


def rectify_slide(slide, H_uz_to_px, fr, ss=3):
    U, Z, ss = frame_uz(fr, ss)
    p = apply_h(H_uz_to_px, np.c_[U.ravel(), Z.ravel()])
    out = bilinear(slide, p[:, 0].reshape(U.shape), p[:, 1].reshape(U.shape))
    return _pool(out, ss)


def render_px(view, u, z):
    """Continuous render pixel coordinates of camera-right coordinate u and height z (orthographic, square px)."""
    c, r = np.asarray(view["center"], float), np.asarray(view["right"], float)
    W, Hh = view["res"]
    scale = view["ortho_scale"] / W
    return W / 2 + (u - c @ r) / scale, Hh / 2 - (z - c[2]) / scale


def rectify_render(img, view, fr, ss=3):
    U, Z, ss = frame_uz(fr, ss)
    x, y = render_px(view, U, Z)
    return _pool(bilinear(img, x, y), ss)


def dark_lines(prof, pos, frac=0.75):
    """Centres (in `pos` units) of the dark runs of a 1-D profile (< frac x median); each centre is the centroid of
    the darkness (median - value) over the run plus one pixel each side (sub-pixel, no threshold bias)."""
    prof, pos = np.asarray(prof, float), np.asarray(pos, float)
    if prof.size < 5 or not np.isfinite(prof).all():
        raise ValueError(f"profile empty or non-finite ({prof.size} samples)")
    med = np.median(prof)
    out = []
    for a, b in joint_count.runs(prof < frac * med):
        a, b = max(a - 1, 0), min(b + 1, prof.size)    # the partly covered pixels beside the run belong to the line
        w = np.clip(med - prof[a:b], 0, None)
        out.append(float((pos[a:b] * w).sum() / w.sum()))
    return out


def measure(rect, fr, body, dark):
    """Field-outline lines and joint lines on a rectified image (h, w, 3) in frame `fr`; body = (u_lo, u_hi, z_lo,
    z_hi). Horizontal profile = mean of the rows 30-70 % of the body height (vertical lines); vertical profile =
    median of the field columns (ribs removed). Windows stay EDGE_KEEP inside the body, so a drawn body outline is
    never taken; the first / last dark line in each window is the field outline. Raises ValueError when missing."""
    pxm = fr["px_per_m"]
    L = value(rect)
    u = fr["u0"] + (np.arange(fr["w"]) + 0.5) / pxm
    z = fr["z_top"] - (np.arange(fr["h"]) + 0.5) / pxm
    zb = body[2] + np.array([0.3, 0.7]) * (body[3] - body[2])
    rows = (z >= zb[0]) & (z <= zb[1])
    cols = (u >= body[0] + EDGE_KEEP) & (u <= body[1] - EDGE_KEEP)
    hl = dark_lines(L[rows][:, cols].mean(0), u[cols], dark)
    if len(hl) < 2:
        raise ValueError(f"field outline (left/right) not found: {len(hl)} dark lines across the body")
    fcols = (u >= hl[0] + 0.05) & (u <= hl[-1] - 0.05)
    zr = (z >= body[2] + EDGE_KEEP) & (z <= body[3] - EDGE_KEEP)
    vl = dark_lines(np.median(L[zr][:, fcols], axis=1)[::-1], z[zr][::-1], dark)     # bottom -> top
    if len(vl) < 2:
        raise ValueError(f"field outline (top/bottom) not found: {len(vl)} dark lines up the body")
    return {"field_left": hl[0], "field_right": hl[-1], "field_bottom": vl[0], "field_top": vl[-1],
            "joints_u": hl[1:-1], "profile_u": u[cols], "profile_lum": L[rows][:, cols].mean(0)}


def slide_corners(slide, box, win=2.5):
    """Sub-pixel body-outline corners on the slide (continuous px): each side of the drawn body outline is a line fit
    through per-row (left/right) or per-column (top/bottom) darkness centroids near the blue box edge; corners are
    the line intersections, order TL, TR, BR, BL. Raises ValueError when a side has no dark outline."""
    L = lum(slide)
    x0, y0, x1, y1 = box
    h, w = y1 - y0, x1 - x0
    med = np.median(L[y0:y1, x0:x1])
    thr = 0.75 * med

    def centroid(vals, pos):
        wgt = np.clip(thr - vals, 0, None)
        return float((pos * wgt).sum() / wgt.sum()) if wgt.sum() > 0 else np.nan

    def side(edge, vertical):
        if vertical:                                   # x = a*y + b, rows in the middle 60 %
            ys = np.arange(y0 + int(0.2 * h), y0 + int(0.8 * h))
            xs = np.arange(int(np.floor(edge - win)) - 1, int(np.ceil(edge + win)) + 1)
            c = np.array([centroid(L[y, xs], xs + 0.5) for y in ys])
            t = ys + 0.5
        else:                                          # y = a*x + b, columns in the middle 60 %
            xs = np.arange(x0 + int(0.2 * w), x0 + int(0.8 * w))
            ys_ = np.arange(int(np.floor(edge - win)) - 1, int(np.ceil(edge + win)) + 1)
            c = np.array([centroid(L[ys_, x], ys_ + 0.5) for x in xs])
            t = xs + 0.5
        ok = np.isfinite(c)
        if ok.sum() < 0.8 * len(c):
            raise ValueError(f"slide body outline missing near {'x' if vertical else 'y'}={edge}: "
                             f"{int(ok.sum())}/{len(c)} samples")
        a, b = np.polyfit(t[ok], c[ok], 1)
        res = float(np.abs(c[ok] - (a * t[ok] + b)).max())
        return a, b, res

    sides = {"left": side(x0, True), "right": side(x1, True), "top": side(y0, False), "bottom": side(y1, False)}

    def meet(v, hz):                                   # x = a1 y + b1 ; y = a2 x + b2
        a1, b1, _ = sides[v]
        a2, b2, _ = sides[hz]
        x = (a1 * b2 + b1) / (1 - a1 * a2)
        return x, a2 * x + b2

    corners = [meet("left", "top"), meet("right", "top"), meet("right", "bottom"), meet("left", "bottom")]
    return np.asarray(corners), {k: {"slope": round(v[0], 6), "max_residual_px": round(v[2], 3)}
                                 for k, v in sides.items()}


def model_body(vrb_obj, key, view, zero_m=0.0):
    """Model body extent on the facade plane: (u_lo, u_hi, z_lo, z_hi), u = camera-right coordinate. Body = the
    facade's vertical triangles that reach above +-0.000 (the foundation face below is not the drawn body)."""
    V = np.asarray(vrb_obj["vertices"], float)
    F = vrb_obj["faces"]
    tris = [t for t in joint_count.facade_triangles(V, F, lambda t: True, key)
            if V[F[t]][:, 2].max() > zero_m + 1e-6]
    if not tris:
        raise ValueError(f"no body triangles facing {key}")
    pts = V[np.asarray([F[t] for t in tris]).ravel()]
    u = pts @ np.asarray(view["right"], float)
    return float(u.min()), float(u.max()), float(pts[:, 2].min()), float(pts[:, 2].max())


def plant_top_band(img, view, z_from, z_to, dz):
    """Planted error on a render: the rows with world z in [z_from, z_to] moved dz metres DOWN; the vacated rows get
    the row just above z_to (frame colour). Returns a copy."""
    img = np.array(img)
    _, y_from = render_px(view, 0.0, z_from)
    _, y_to = render_px(view, 0.0, z_to)
    scale = view["ortho_scale"] / view["res"][0]
    k = int(round(dz / scale))
    a, b = int(round(y_to)), int(round(y_from))         # image rows: z_to is above (smaller y)
    band = img[a:b].copy()
    img[a + k:b + k] = band
    img[a:a + k] = img[a - 1]
    return img


def verdict(offsets_px, tol_px):
    """pass iff every offset is finite and |offset| <= tol_px (an empty set is a fail)."""
    vals = list(offsets_px.values())
    return bool(vals) and all(np.isfinite(v) and abs(v) <= tol_px for v in vals)


def sha(p):
    with open(p, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def run(spec, sheet, rdir, vrb, facade="1-2", pxm=200.0, tol_px=2.0, register="model", plant_u=0.0,
        plant_band=0.0, slide=None):
    """The whole overlay on one facade; returns (report, slide_rect, vpm_rect)."""
    if facade not in spec["facades"]:
        raise ValueError(f"facade {facade!r} not in spec facades {sorted(spec['facades'])}")
    if register not in ("model", "datum"):
        raise ValueError(f"register must be model or datum, got {register!r}")
    if not (np.isfinite(pxm) and pxm > 0 and np.isfinite(tol_px) and tol_px >= 0):
        raise ValueError(f"px_per_m {pxm} / tol_px {tol_px} must be finite and positive")
    fc, f = spec["facades"][facade], sheet["facades"][facade]
    key = fc["normal"]
    pres = spec["presentation"]
    if slide is None:
        slide = np.asarray(Image.open(pres["image"]).convert("RGB"))
    meta = json.load(open(os.path.join(rdir, "renders.json"), encoding="utf-8"))
    view = dict(meta["vpm"]["views"][VIEW[key]])
    obj = next(o for o in vrb["objects"] if not o["name"].startswith("UCX_"))
    body = model_body(obj, key, view, spec.get("zero_m", 0.0))
    if register == "datum":
        uc, W, Hb = (body[0] + body[1]) / 2, f["size_mm"][0] / 1000, f["size_mm"][1] / 1000
        target = (uc - W / 2, uc + W / 2, spec.get("zero_m", 0.0), spec.get("zero_m", 0.0) + Hb)
    else:
        target = body
    from compare_facades import slide_boxes                      # local import: compare_facades pulls finish_map
    box = dict(zip(pres["quadrants"], slide_boxes(slide)))[facade]
    corners, fit = slide_corners(slide, box)
    dst = np.array([[target[0], target[3]], [target[1], target[3]], [target[1], target[2]], [target[0], target[2]]])
    H = homography(corners, dst)                                 # slide px -> (u, z)
    fr = frame(body, pxm)
    s_rect = rectify_slide(slide, np.linalg.inv(H), fr)
    img = np.asarray(Image.open(os.path.join(rdir, view["png"])).convert("RGBA"), float)
    rgb = img[..., :3] * (img[..., 3:] / 255) + 255 * (1 - img[..., 3:] / 255)   # transparent -> white
    if plant_band:
        fld = measure(rectify_render(rgb, view, fr), fr, body, RENDER_DARK)
        rgb = plant_top_band(rgb, view, fld["field_top"] - 0.05, body[3] - 0.01, plant_band)
    if plant_u:
        c, r = np.asarray(view["center"], float), np.asarray(view["right"], float)
        view["center"] = list(c - plant_u * r)
    v_rect = rectify_render(rgb, view, fr)
    ms, mv = measure(s_rect, fr, target, SLIDE_DARK), measure(v_rect, fr, body, RENDER_DARK)   # each image inside its own body outline
    sign = {"field_left": 1, "field_right": 1, "field_top": 1, "field_bottom": 1}
    off = {e: round(sign[e] * (ms[e] - mv[e]) * pxm, 3) for e in EDGES}
    rib = {}
    for tag, m in (("slide", ms), ("vpm", mv)):
        r = joint_count.count_joints(m["profile_u"], m["profile_lum"], m["field_left"], m["field_right"], fc["ribs"],
                                     tol=0.012, dark=0.85)
        rib[tag] = {"joints_found": r["joints_found"], "ok": r["ok"], "max_position_error_m": r["max_position_error_m"],
                    "lines": len(m["joints_u"])}
    nj = min(len(ms["joints_u"]), len(mv["joints_u"]))
    jo = [abs(a - b) * pxm for a, b in zip(ms["joints_u"][:nj], mv["joints_u"][:nj])]
    back = apply_h(H, corners) - dst
    rep = {
        "facade": facade, "normal": key, "register": register, "px_per_m": pxm, "tol_px": tol_px,
        "planted": {"u_m": plant_u, "top_band_m": plant_band},
        "slide_box_px": [int(v) for v in box], "slide_corners_px": np.round(corners, 3).tolist(), "outline_fit": fit,
        "homography_slide_px_to_uz": np.round(H, 9).tolist(),
        "perspective_terms": [float(H[2, 0]), float(H[2, 1])],
        "corner_backprojection_max_m": float(np.abs(back).max()),
        "model_body_uz_m": [round(v, 5) for v in body], "target_body_uz_m": [round(v, 5) for v in target],
        "frame_px": [fr["w"], fr["h"]],
        "slide_edges_m": {e: round(ms[e], 5) for e in EDGES}, "vpm_edges_m": {e: round(mv[e], 5) for e in EDGES},
        "band_edge_offset_px": off, "max_band_edge_offset_px": max(abs(v) for v in off.values()),
        "joint_pairs": nj, "max_joint_offset_px": round(max(jo), 3) if jo else None,
        "ribs_contract": fc["ribs"], "rib_counts": rib,
    }
    rep["ribs_agree"] = bool(rib["slide"]["joints_found"] == rib["vpm"]["joints_found"] == fc["ribs"] - 1)
    rep["pass"] = verdict(off, tol_px)
    return rep, s_rect, v_rect


def main(argv):
    t0 = time.perf_counter()
    if len(argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    spec_p, sheet_p, rdir, vrb_p, out = argv[:5]

    def opt(name, conv, default):
        return conv(argv[argv.index(name) + 1]) if name in argv else default

    try:
        facade = opt("--facade", str, "1-2")
        pxm, tol = opt("--px-per-m", float, 200.0), opt("--tol-px", float, 2.0)
        register = opt("--register", str, "model")
        pu, pb = opt("--plant-u", float, 0.0), opt("--plant-top-band", float, 0.0)
        if not (np.isfinite(pu) and np.isfinite(pb)):
            raise ValueError(f"planted shifts must be finite: {pu}, {pb}")
        spec = json.load(open(spec_p, encoding="utf-8"))
        ins = [spec_p, sheet_p, rdir, vrb_p, spec["presentation"]["image"]]
        ro = os.path.realpath(out)
        for p in ins:
            rp = os.path.realpath(p)
            if ro == rp or ro.startswith(rp + os.sep) or rp.startswith(ro + os.sep):
                raise ValueError(f"output {out} aliases input {p}")
        if os.path.lexists(out):
            raise ValueError(f"refusing to overwrite {out}")
        if sha(spec["presentation"]["image"]) != spec["presentation"]["image_sha256"]:
            raise ValueError("slide image sha256 differs from the spec")
        sheet = json.load(open(sheet_p, encoding="utf-8"))
        vrb = json.load(open(vrb_p, encoding="utf-8"))
        rep, s_rect, v_rect = run(spec, sheet, rdir, vrb, facade, pxm, tol, register, pu, pb)
    except (ValueError, KeyError, OSError, StopIteration) as e:
        print(f"slide_overlay: refused: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    rep["inputs_sha256"] = {"slide": spec["presentation"]["image_sha256"], "vpm_readback": sha(vrb_p),
                            "renders_json": sha(os.path.join(rdir, "renders.json"))}
    tmp = out + ".partial"
    os.makedirs(tmp)
    Image.fromarray(np.clip(s_rect, 0, 255).astype(np.uint8)).save(os.path.join(tmp, "slide_rect.png"))
    Image.fromarray(np.clip(v_rect, 0, 255).astype(np.uint8)).save(os.path.join(tmp, "vpm_rect.png"))
    ov = np.stack([lum(s_rect) / 3, lum(v_rect) / 3, lum(v_rect) / 3], -1)   # slide = red channel, VPM = cyan
    Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).save(os.path.join(tmp, "overlay.png"))
    rep["seconds"] = round(time.perf_counter() - t0, 3)
    with open(os.path.join(tmp, "overlay.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, out)
    print("OVERLAY", json.dumps({k: rep[k] for k in ("facade", "register", "band_edge_offset_px", "rib_counts",
                                                       "pass", "seconds")}, ensure_ascii=False))
    return 0 if rep["pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
