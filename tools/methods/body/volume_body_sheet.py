"""Step-2 sheet of the volume body (#1784): straight elevations per facade side + iso + keyplan, PNG pages and a PDF.

Pattern: n/a | new-case: evidence renderer of `volume_body.py` output (PIL only, no DCC): every non-hidden side of
every volume straight-on with its lattice (walls grey, window planes blue, 5-sided local-cut cells orange), the level
list with the ring-closure result of the core, the local-signal map (local cuts orange, source rectangles that were
not cut drawn dashed red with their state), and an iso view of all volumes.

    uv run python tools/methods/body/volume_body_sheet.py <volume-lines.json> <build_dir> <out_dir>
"""
from __future__ import annotations

import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/arial.ttf"
COL = {"WALL": (214, 210, 200), "WINDOW": (92, 140, 190), "ROOF": (150, 150, 155)}


def _font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except OSError:
        return ImageFont.load_default()


def side_faces(mesh, xy, depth=0.5, tol=0.01):
    """Faces of `mesh` seen straight-on from the outside of side xy: (u0..), z, mat, n_verts. u along xy[0]->xy[1]."""
    (ax, ay), (bx, by) = xy
    L = math.hypot(bx - ax, by - ay)
    tx, ty = (bx - ax) / L, (by - ay) / L
    out = []
    V = mesh["verts"]
    for f in mesh["faces"]:
        co = [V[i] for i in f["v"]]
        us = [(p[0] - ax) * tx + (p[1] - ay) * ty for p in co]
        ds = [abs(-(p[0] - ax) * ty + (p[1] - ay) * tx) for p in co]
        if min(us) < -tol or max(us) > L + tol or max(ds) > depth:
            continue
        nz = _nz(co)
        if abs(nz) > 0.1:
            continue
        if f["mat"] != "WINDOW" and max(ds) > tol:
            continue  # reveal jambs / sills are not seen straight-on
        out.append(([(u, p[2]) for u, p in zip(us, co)], f["mat"], len(co)))
    return out, L


def _normal(co):
    nx = ny = nz = 0.0
    for a, b in zip(co, co[1:] + co[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / n, ny / n, nz / n


def _nz(co):
    nx = ny = nz = 0.0
    for a, b in zip(co, co[1:] + co[:1]):
        nx += (a[1] - b[1]) * (a[2] + b[2])
        ny += (a[2] - b[2]) * (a[0] + b[0])
        nz += (a[0] - b[0]) * (a[1] + b[1])
    n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nz / n


def elevation(mesh, edge_name, e, rects, report, scale=14):
    faces, L = side_faces(mesh, e["xy"])
    levels = e["levels"]
    zmax = max(levels)
    W, H = int(L * scale) + 260, int(zmax * scale) + 150
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    ox, oy = 200, H - 60

    def P(u, z):
        return (ox + u * scale, oy - z * scale)
    for poly, mat, n in faces:
        pts = [P(u, z) for u, z in poly]
        d.polygon(pts, fill=COL.get(mat, (255, 0, 255)), outline=(40, 40, 40))
        if n > 4 and mat != "ROOF":
            d.polygon(pts, outline=(235, 120, 0), width=3)
    for r in rects:
        s0, s1, z0, z1 = r.get("projected_rect") or r["source_rect"]
        if r["state"] == "level_conflict":
            d.rectangle([P(s0, z1), P(s1, z0)], outline=(235, 120, 0), width=3)
        elif r["state"] != "cut":
            x0, y0 = P(s0, z1)
            x1, y1 = P(s1, z0)
            for k in range(int(x0), int(x1), 10):
                d.line([(k, y0), (min(k + 5, x1), y0)], fill=(210, 30, 30), width=2)
                d.line([(k, y1), (min(k + 5, x1), y1)], fill=(210, 30, 30), width=2)
            for k in range(int(y0), int(y1), 10):
                d.line([(x0, k), (x0, min(k + 5, y1))], fill=(210, 30, 30), width=2)
                d.line([(x1, k), (x1, min(k + 5, y1))], fill=(210, 30, 30), width=2)
    f = _font(15)
    for z in levels:
        d.text((8, oy - z * scale - 8), "%+.2f" % z, fill=(20, 40, 60), font=f)
        d.line([(ox - 20, oy - z * scale), (ox - 4, oy - z * scale)], fill=(20, 40, 60), width=1)
    title = "%s  %s  %.2f m  seam %s  faces %d" % (edge_name, e.get("facade") or "-", L, e.get("seam") or "-", len(faces))
    d.text((8, 8), title, fill=(0, 0, 0), font=_font(20))
    return im


def iso(meshes, size=(1800, 1100), angle=225):
    allv = [p for m in meshes.values() for p in m["body"]["verts"]]
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))

    def pr(p):
        x, y = p[0] * c - p[1] * s, p[0] * s + p[1] * c
        return (x - y) * 0.866, (x + y) * 0.5 - p[2]
    pts = [pr(p) for p in allv]
    minx, maxx = min(p[0] for p in pts), max(p[0] for p in pts)
    miny, maxy = min(p[1] for p in pts), max(p[1] for p in pts)
    k = min((size[0] - 80) / (maxx - minx), (size[1] - 120) / (maxy - miny))
    im = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(im)
    cam = (c + s, c - s, 1.2)  # towards the viewer: screen-down (x'+y') and up
    cl = math.sqrt(sum(x * x for x in cam))
    cam = tuple(x / cl for x in cam)
    polys = []
    for vn, m in meshes.items():
        V = m["body"]["verts"]
        for f in m["body"]["faces"]:
            co = [V[i] for i in f["v"]]
            n = _normal(co)
            if n[0] * cam[0] + n[1] * cam[1] + n[2] * cam[2] <= 0:
                continue  # back face
            depth = sum(p[0] * cam[0] + p[1] * cam[1] + p[2] * cam[2] for p in co) / len(co)
            polys.append((depth, co, f["mat"]))
    polys.sort(key=lambda t: t[0])  # far first
    for _, co, mat in polys:
        base = COL.get(mat, (255, 0, 255))
        q = [((pr(p)[0] - minx) * k + 40, (pr(p)[1] - miny) * k + 80) for p in co]
        d.polygon(q, fill=base, outline=(60, 60, 60))
    return im


def main(argv=None):
    argv = argv or sys.argv[1:]
    vl_path, build, out = argv[:3]
    os.makedirs(out, exist_ok=True)
    with open(vl_path, encoding="utf-8") as fh:
        vl = json.load(fh)
    with open(os.path.join(build, "meshes.json"), encoding="utf-8") as fh:
        meshes = json.load(fh)
    with open(os.path.join(build, "build_report.json"), encoding="utf-8") as fh:
        rep = json.load(fh)
    pages = []
    for vn in sorted(meshes):
        mesh = meshes[vn]["body"]
        r = rep["volumes"][vn]
        cl = r["closure"][0]
        head = ("Volume %s: levels %d/%d closed, stations %d/%d continuous, openings %d, local cuts %d, "
                "hidden seam cells removed %d, facade tris %d, defect cells %d"
                % (vn, cl["closed_levels"], cl["levels"], cl["continuous_stations"], cl["stations"], r["openings"],
                   r["local_cuts"], r["hidden_seam_cells_removed"], r["body"]["facade_triangles"],
                   r["body"]["defect_cells"]))
        tiles = []
        for en, e in vl["edges"].items():
            if e["volume"] != vn or e["length"] < 1.0:
                continue
            if e.get("seam") and e.get("visible_from", 0) >= max(e["levels"]) - 1e-6:
                continue  # fully hidden by the mate volume
            rects = [x for x in vl["rectangles"] if x.get("edge") == en]
            tiles.append(elevation(mesh, en, e, rects, r))
        W = max([t.width for t in tiles] + [1800])
        y, page, n = 0, None, 0
        for t in [None] + tiles:
            if page is None or (t is not None and y + t.height > 2400):
                if page is not None:
                    pages.append(page)
                n += 1
                page = Image.new("RGB", (W, 2480), "white")
                ImageDraw.Draw(page).text((10, 10), "#1784 Sokolniki step 2 body - %s (page %d)" % (head, n),
                                          fill=(0, 0, 0), font=_font(22))
                y = 60
            if t is not None:
                page.paste(t, (0, y))
                y += t.height + 10
        pages.append(page)
    for k, ang in enumerate((45, 225)):
        im = iso(meshes, angle=ang)
        ImageDraw.Draw(im).text((10, 10), "#1784 Sokolniki step 2 body - iso %d deg (all volumes; grey wall, blue "
                                          "window planes, dark roof caps)" % ang, fill=(0, 0, 0), font=_font(24))
        pages.insert(k, im)
    names = []
    for i, p in enumerate(pages):
        nm = "sok-step2-p%02d.png" % i
        p.save(os.path.join(out, nm))
        names.append(nm)
    pages[0].convert("RGB").save(os.path.join(out, "sok-step2.pdf"), save_all=True,
                                 append_images=[p.convert("RGB") for p in pages[1:]])
    print(json.dumps({"pages": names}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
