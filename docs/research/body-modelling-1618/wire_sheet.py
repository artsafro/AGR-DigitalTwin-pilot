"""Hidden-line wire sheets of body dumps (#1618). new-case: read-only etalon wire close-ups for the research doc.

Usage: uv run python wire_sheet.py DUMP.npz --view px|nx|py|ny|iso|top --rot DEG --ppm PX_PER_M
         [--window U0 U1 V0 V1] --out PNG
Painter's algorithm on the rejoined faces (dump_mesh.py): back faces culled, far faces first.
Colours: grey quad (shade by normal), orange = triangle kept after the 1 deg coplanar rejoin
(a real diagonal), red = sliver triangle (min angle < 5 deg). Edges black. Window is in metres
from the view's lower-left corner. Refuses to write over the input.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw


def unpack(n, i):
    out, k = [], 0
    for c in n:
        out.append(i[k:k + c])
        k += c
    return out


def textured(a, d, R, base, right, up, cam, U0, W0, u0, v0, w, h, jfaces, JV, JU, JW, JD):
    """Z-buffer raster of the exported triangles with their UVs, then visible rejoined edges in black
    (orange for edges of triangles left after the rejoin)."""
    tex = np.asarray(Image.open(a.texture).convert("RGB"))
    th, tw = tex.shape[:2]
    V = (d["verts"] - base) @ R.T
    F = d["fi"].reshape(-1, 3)
    UV = d["uvf"].reshape(-1, 3, 2)
    X = (V @ right - U0 - u0) * a.ppm + 10
    Y = h - 10 - (V @ up - W0 - v0) * a.ppm
    Z = V @ cam
    canvas = np.full((h, w, 3), 255, np.uint8)
    zb = np.full((h, w), -np.inf)
    for t, f in enumerate(F):
        xs, ys, zs = X[f], Y[f], Z[f]
        if xs.max() < 0 or xs.min() >= w or ys.max() < 0 or ys.min() >= h:
            continue
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        P = V[f]
        if np.cross(P[1] - P[0], P[2] - P[0]) @ cam <= 0 or abs(den) < 1e-9:
            continue
        x0, x1 = max(int(xs.min()), 0), min(int(xs.max()) + 1, w - 1)
        y0, y1 = max(int(ys.min()), 0), min(int(ys.max()) + 1, h - 1)
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
        l1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        l2 = 1 - l0 - l1
        m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
        if not m.any():
            continue
        z = l0 * zs[0] + l1 * zs[1] + l2 * zs[2]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        m &= z > sub
        if not m.any():
            continue
        uv = UV[t]
        uu = l0 * uv[0, 0] + l1 * uv[1, 0] + l2 * uv[2, 0]
        vv = l0 * uv[0, 1] + l1 * uv[1, 1] + l2 * uv[2, 1]
        tx = np.clip((uu % 1.0) * tw, 0, tw - 1).astype(int)
        ty = np.clip((1 - vv % 1.0) * th, 0, th - 1).astype(int)
        sub[m] = z[m]
        canvas[y0:y1 + 1, x0:x1 + 1][m] = tex[ty[m], tx[m]]
    jx = (JU - u0) * a.ppm + 10
    jy = h - 10 - (JW - v0) * a.ppm
    for f in jfaces:
        col = (230, 120, 0) if len(f) == 3 else (0, 0, 0)
        for k in range(len(f)):
            p, q = f[k], f[(k + 1) % len(f)]
            n = int(max(abs(jx[q] - jx[p]), abs(jy[q] - jy[p]))) + 1
            if n > 20000:
                continue
            s = np.linspace(0, 1, n)
            px = (jx[p] + s * (jx[q] - jx[p])).astype(int)
            py = (jy[p] + s * (jy[q] - jy[p])).astype(int)
            pz = JD[p] + s * (JD[q] - JD[p])
            ok = (px >= 0) & (px < w) & (py >= 0) & (py < h)
            px, py, pz = px[ok], py[ok], pz[ok]
            vis = pz >= zb[py, px] - 0.03
            canvas[py[vis], px[vis]] = col
    return Image.fromarray(canvas)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("npz")
    ap.add_argument("--view", required=True, choices=["px", "nx", "py", "ny", "iso", "top"])
    ap.add_argument("--rot", type=float, default=0.0)
    ap.add_argument("--ppm", type=float, default=20.0)
    ap.add_argument("--window", type=float, nargs=4)
    ap.add_argument("--title", default="")
    ap.add_argument("--texture", help="diffuse PNG: z-buffered textured view + visible rejoined edges")
    ap.add_argument("--mat-rgb", help="JSON list [[r,g,b], ...] by material index: colour quads by material ID")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.npz) or not a.out.lower().endswith(".png"):
        sys.exit("output must be a new .png, not the input")
    if not (math.isfinite(a.ppm) and a.ppm > 0):
        sys.exit("ppm must be finite > 0")
    d = np.load(a.npz)
    V = d["jverts"].copy()
    faces = unpack(d["jn"], d["ji"])
    if not faces:
        sys.exit("empty mesh")
    mat_rgb, jm = None, d["jmats"]
    fi_of = {id(f): k for k, f in enumerate(faces)}
    if a.mat_rgb:  # quads filled with their material colour (#1619: finish-zone IDs on the sheet)
        mat_rgb = json.load(open(a.mat_rgb, encoding="utf-8"))
        miss = sorted(set(int(m) for m in jm) - set(range(len(mat_rgb))))
        if miss:
            sys.exit("material index %s has no colour in %s" % (miss, a.mat_rgb))
    t = math.radians(-a.rot)
    R = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
    base = d["verts"].min(0)
    V = (V - base) @ R.T
    if a.view == "iso":
        cam = np.array([1.0, -1.0, 0.8]); cam /= np.linalg.norm(cam)
        right = np.cross([0, 0, 1.0], cam); right /= np.linalg.norm(right)
        up = np.cross(cam, right)
    elif a.view == "top":
        cam, right, up = np.array([0, 0, 1.0]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    else:
        cam = {"px": [1.0, 0, 0], "nx": [-1.0, 0, 0], "py": [0, 1.0, 0], "ny": [0, -1.0, 0]}[a.view]
        cam = np.array(cam)
        right = np.cross([0, 0, 1.0], cam)
        up = np.array([0, 0, 1.0])
    U, W, D = V @ right, V @ up, V @ cam
    U0, W0 = U.min(), W.min()
    U -= U0; W -= W0
    polys = []
    for f in faces:
        P = V[f]
        n = np.zeros(3)
        for k in range(len(P)):
            n += np.cross(P[k], P[(k + 1) % len(P)])
        ln = np.linalg.norm(n)
        if ln == 0:
            continue
        n /= ln
        if n @ cam <= 1e-3:
            continue
        kind = "q"
        if len(f) == 3:
            e = [P[(k + 1) % 3] - P[k] for k in range(3)]
            angs = []
            for k in range(3):
                u, v = -e[(k + 2) % 3], e[k]
                c = u @ v / (np.linalg.norm(u) * np.linalg.norm(v) + 1e-12)
                angs.append(math.degrees(math.acos(max(-1, min(1, c)))))
            kind = "s" if min(angs) < 5 else "t"
        polys.append((float(D[f].mean()), f, kind, float(abs(n @ cam))))
    polys.sort(key=lambda p: p[0])
    u0, u1, v0, v1 = a.window if a.window else (0, float(U.max()), 0, float(W.max()))
    w, h = int((u1 - u0) * a.ppm) + 20, int((v1 - v0) * a.ppm) + 40
    if w * h > 60e6:
        sys.exit(f"image too large {w}x{h}")
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    lw = 1 if a.ppm < 60 else 2
    if a.texture:
        img = textured(a, d, R, base, right, up, cam, U0, W0, u0, v0, w, h, faces, V, U, W, D)
        dr = ImageDraw.Draw(img)
        polys = []
    for _, f, kind, sh in polys:
        xs = (U[f] - u0) * a.ppm + 10
        ys = h - 10 - (W[f] - v0) * a.ppm
        if xs.max() < 0 or xs.min() > w or ys.max() < 0 or ys.min() > h:
            continue
        g = int(170 + 70 * sh)
        fill = {"q": (g, g, g), "t": (255, 190, 110), "s": (240, 70, 60)}[kind]
        if mat_rgb is not None and kind == "q":
            c = mat_rgb[int(jm[fi_of[id(f)]])]
            k = 0.7 + 0.3 * sh
            fill = tuple(int(x * k) for x in c)
        dr.polygon(list(zip(xs.tolist(), ys.tolist())), fill=fill, outline=(0, 0, 0), width=lw)
    dr.rectangle([0, 0, w, 26], fill="white")
    dr.text((8, 6), f"{a.title} view={a.view} rot={a.rot} ppm={a.ppm} window={a.window}  grey=quad orange=triangle red=sliver",
            fill="black")
    img.save(a.out)
    print("WROTE", a.out, w, h, len(polys))


if __name__ == "__main__":
    main()
