"""Build a welded, material-ID'd ground mesh plus paint and curb curves from the PZU DXF.

Every covering hatch boundary is read as exact primitives (lines, arcs, circles). Arcs are tessellated
on a per-circle angular grid (step <= 5 deg, sagitta <= 3 mm) anchored at angle 0, so two coverings that
share an arc get identical vertices. All boundaries are noded together, polygonized, assigned a covering
(smallest containing hatch wins; override layers first) and triangulated with constrained Delaunay.

Output JSON (metres, local to `origin`) is consumed by build_ground.ms in 3ds Max.

Usage: python -I build_ground.py <dxf> <clip_handle|clip.json> <out_dir>
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import ezdxf
import shapely
import shapely.affinity
from ezdxf import path as ep
from ezdxf.math import bulge_to_arc
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

MAX_STEP_DEG = 5.0
SAGITTA = 0.003
SNAP = 0.001
CIRCLE_TOL = 0.002
SLIVER = 0.05  # m2
UNDEF_MAX = 30.0  # m2: an uncovered face up to this size (an equipment pad) takes its neighbour's covering
JOINT_COVERED = 0.04  # m: a joint closer than this to a DWG paint line is already painted
JOINT_MIN_LEN = 0.15  # m
JOINT_ALONG = 0.20  # m: a covered stretch shorter than this is a crossing, not a parallel line

# Coverings are split by the shade the DWG shows: the hatch background colour when it has one, else the hatch
# colour (user 2026-11-04: «разбить по оттенкам как в двг»). Rule: (layer, pattern|None, colour|None, bg|None).
# First matching rule wins. Order in MATERIALS gives the material ID (1-based).
RULES = [
    ("ГП_Резиновое покрытие", None, None, "rgb(233, 224, 210)", "Rubber_Sand"),
    ("ГП_Резиновое покрытие", None, None, "rgb(0, 124, 176)", "Rubber_Blue"),
    ("ГП_Резиновое покрытие", None, None, "rgb(99, 125, 150)", "Rubber_GreyBlue"),
    ("ГП_Резиновое покрытие", None, None, "rgb(246, 115, 44)", "Rubber_Orange"),
    ("_ГП_покрытие проезда пл", None, None, "rgb(199, 200, 202)", "Tile_Grey"),
    ("_ГП_покрытие проезда пл", None, None, "rgb(0, 0, 252)", "Tile_Blue"),
    ("ГП_асфальтобетон", None, None, None, "Asphalt"),
    ("253_Озел_Газоны_G1.1_Lawn 2_Газон посевной злаковый (сеянный)", None, None, None, "Lawn_Seeded"),
    ("253_Озел_Газоны_G2.1_Lawn 1_Газон рулонный (спортивный износостойкий)", None, None, None, "Lawn_Rolled_Sport"),
    ("ГП_Кусты", None, "aci94", None, "Shrub_Bed_Dark"),
    ("ГП_Кусты", None, "aci60", None, "Shrub_Bed_Light"),
    ("253_Озел_Многолетники_№Mix14_Сенсорный", None, None, None, "Flowerbed_Sensory_Violet"),
    ("ФВ-2", None, None, None, "Equipment_Pad_White"),
]
COLOURS = {  # Corona base colour = the shade shown in the DWG
    "Rubber_Sand": (233, 224, 210), "Rubber_Blue": (0, 124, 176), "Rubber_GreyBlue": (99, 125, 150),
    "Rubber_Orange": (246, 115, 44), "Tile_Grey": (199, 200, 202), "Tile_Blue": (0, 0, 252),
    "Asphalt": (191, 191, 191), "Lawn_Seeded": (110, 150, 70), "Lawn_Rolled_Sport": (80, 140, 60),
    "Shrub_Bed_Dark": (0, 127, 63), "Shrub_Bed_Light": (127, 255, 0), "Flowerbed_Sensory_Violet": (159, 127, 255),
    "Equipment_Pad_White": (255, 255, 255),
    "Undefined": (255, 0, 255), "Paint_White": (250, 250, 250), "Curb_Concrete": (160, 160, 160),
}
MATERIALS = [r[4] for r in RULES] + ["Undefined", "Paint_White", "Curb_Concrete"]
JOINT_MATERIALS = {m for m in MATERIALS if m.startswith("Rubber_")}
PAINT_LAYER = "255_краска"
CURB_LAYERS = {"254_Борт_садовый_50х20х5_серый": ("Curb_Garden", 0.05, 0.05),
               "254_Борт_дорожный 30": ("Curb_Road", 0.15, 0.15),
               "~06 bort_100x20x8_small": ("Curb_Small", 0.08, 0.05)}  # name, width, height above ground


def colour_key(e) -> str:
    tc = e.dxf.get("true_color")
    return f"rgb{tuple(ezdxf.colors.int2rgb(tc))}" if tc is not None else f"aci{e.dxf.color}"


def bg_key(e) -> str | None:
    bg = e.bgcolor
    return f"rgb{tuple(bg)}" if bg is not None else None


def covering_of(e) -> str | None:
    lay, pat, col, bg = e.dxf.layer, e.dxf.pattern_name, colour_key(e), bg_key(e)
    for rl, rp, rc, rb, mat in RULES:
        if rl == lay and rp in (None, pat) and rc in (None, col) and rb in (None, bg):
            return mat
    return None


def walk(ents, depth=0):
    for e in ents:
        if e.dxftype() == "INSERT" and depth < 6:
            try:
                yield from walk(e.virtual_entities(), depth + 1)
            except Exception:
                pass
        else:
            yield e


# ---------- arc tessellation on a shared grid ----------
_circles: list[tuple[float, float, float]] = []


def canon_circle(cx, cy, r):
    for c in _circles:
        if abs(c[0] - cx) < CIRCLE_TOL and abs(c[1] - cy) < CIRCLE_TOL and abs(c[2] - r) < CIRCLE_TOL:
            return c
    _circles.append((cx, cy, r))
    return _circles[-1]


def grid_n(r):
    step = MAX_STEP_DEG
    if r > SAGITTA:
        step = min(step, math.degrees(2 * math.acos(max(-1.0, 1 - SAGITTA / r))))
    n = math.ceil(360.0 / step)
    return int(math.ceil(n / 8.0) * 8)


def arc_pts(cx, cy, r, a0, a1, ccw=True):
    """Points from angle a0 to a1 (radians) incl. both ends, grid angles in between."""
    cx, cy, r = canon_circle(cx, cy, r)
    n = grid_n(r)
    step = 2 * math.pi / n
    if not ccw:
        return arc_pts(cx, cy, r, a1, a0, True)[::-1]
    a0 %= 2 * math.pi
    a1 %= 2 * math.pi
    if a1 <= a0 + 1e-12:
        a1 += 2 * math.pi
    pts = [a0]
    k = math.floor(a0 / step) + 1
    while k * step < a1 - 1e-9:
        if k * step > a0 + 1e-9:
            pts.append(k * step)
        k += 1
    pts.append(a1)
    return [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in pts]


def circle_pts(cx, cy, r):
    cx, cy, r = canon_circle(cx, cy, r)
    n = grid_n(r)
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return pts + [pts[0]]


def bulge_seg(p0, p1, b):
    if abs(b) < 1e-9:
        return [p0, p1]
    c, sa, ea, r = bulge_to_arc(p0, p1, b)  # always ccw from sa to ea
    pts = arc_pts(c.x, c.y, r, sa, ea, True)
    if b < 0:
        pts = pts[::-1]
    pts[0], pts[-1] = tuple(p0), tuple(p1)
    return pts


def poly_pts(vertices, closed):
    """vertices: (x, y, bulge)."""
    out = []
    n = len(vertices)
    for i in range(n if closed else n - 1):
        x0, y0, b = vertices[i]
        x1, y1, _ = vertices[(i + 1) % n]
        seg = bulge_seg((x0, y0), (x1, y1), b)
        out.extend(seg if not out else seg[1:])
    return out


def edge_path_pts(path):
    out = []
    for ed in path.edges:
        t = ed.type.name
        if t == "LINE":
            seg = [tuple(ed.start)[:2], tuple(ed.end)[:2]]
        elif t == "ARC":
            if abs((ed.end_angle - ed.start_angle) % 360) < 1e-9 and abs(ed.end_angle - ed.start_angle) > 1:
                seg = circle_pts(ed.center[0], ed.center[1], ed.radius)
            else:
                ca = ed.construction_tool()  # ezdxf resolves the clockwise storage into a ccw arc
                seg = arc_pts(ca.center.x, ca.center.y, ca.radius,
                              math.radians(ca.start_angle), math.radians(ca.end_angle), True)
                if not ed.ccw:
                    seg = seg[::-1]
        else:  # ellipse / spline: plain flattening
            p = ep.Path()
            ep.add_ellipse(p, ed.construction_tool()) if t == "ELLIPSE" else ep.add_spline(p, ed.construction_tool())
            seg = [(v.x, v.y) for v in p.flattening(SAGITTA)]
        if out and math.dist(out[-1], seg[0]) > math.dist(out[-1], seg[-1]) + 1e-6:
            seg = seg[::-1]
        out.extend(seg if not out else seg[1:])
    return out


def hatch_rings(e):
    rings = []
    for p in e.paths:
        if p.type.name == "POLYLINE" or p.type == 1:
            pts = poly_pts([(v[0], v[1], v[2]) for v in p.vertices], True)
        else:
            pts = edge_path_pts(p)
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def snap(pts):
    return [(round(x / SNAP) * SNAP, round(y / SNAP) * SNAP) for x, y in pts]


def ring_area_poly(pts):
    pg = Polygon(pts)
    return pg if pg.is_valid else pg.buffer(0)


def main(dxf, clip_arg, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.readfile(dxf)
    msp = doc.modelspace()
    ents = list(walk(msp))

    if Path(clip_arg).exists():
        clip = Polygon(json.loads(Path(clip_arg).read_text())["ring"])
    else:
        ce = doc.entitydb[clip_arg]
        clip = Polygon(snap(poly_pts([(x, y, b) for x, y, b in ce.get_points("xyb")], True)))
    clip = clip.buffer(0)

    lines, regions = [], []
    skipped = Counter()
    for e in ents:
        if e.dxftype() != "HATCH":
            continue
        mat = covering_of(e)
        if mat is None:
            skipped[(e.dxf.layer, colour_key(e))] += 1
            continue
        rings = hatch_rings(e)
        geom = None
        for r in rings:
            g = ring_area_poly(r)
            geom = g if geom is None else geom.symmetric_difference(g)
        if geom is None or geom.is_empty or not geom.intersects(clip):
            continue
        regions.append({"mat": mat, "geom": geom, "area": geom.area, "handle": e.dxf.get("handle")})
        for r in rings:
            rr = snap(r)
            if rr[0] != rr[-1]:
                rr.append(rr[0])
            lines.append(LineString(rr))
        # Circle islands: a hole in the base rubber and a filled island of the track rubber (even-odd);
        # the smaller hatch wins, so they take the track colour. User check 2026-11-04.
    clip_ring = snap(list(clip.exterior.coords))
    lines.append(LineString(clip_ring))
    for hole in clip.interiors:
        lines.append(LineString(snap(list(hole.coords))))

    noded = unary_union(lines)
    polys, cuts, dangles, invalid = shapely.polygonize_full(shapely.get_parts(noded))
    print("polygonize: polys", len(shapely.get_parts(polys)), "cuts", len(shapely.get_parts(cuts)),
          "dangles", len(shapely.get_parts(dangles)), "invalid_rings", len(shapely.get_parts(invalid)))
    faces = [f for f in shapely.get_parts(polys) if f.area > 1e-7]
    faces = [f for f in faces if clip.contains(f.representative_point())]

    regions.sort(key=lambda r: r["area"])
    tree = shapely.STRtree([r["geom"] for r in regions])
    face_mat = []
    for f in faces:
        rp = f.representative_point()
        cand = [regions[i] for i in tree.query(rp, predicate="intersects")]
        cand.sort(key=lambda r: r["area"])
        face_mat.append(cand[0]["mat"] if cand else "Undefined")

    # Small undefined faces (equipment pads cut out of a covering) take the covering whose outer contour
    # holds them, smallest first: the pad lies inside the rubber's outline, not inside the lawn's hole.
    for i, f in enumerate(faces):
        if face_mat[i] != "Undefined" or f.area > UNDEF_MAX:
            continue
        rp = f.representative_point()
        hosts = [r for r in regions if any(Polygon(p.exterior).contains(rp) for p in shapely.get_parts(r["geom"])
                                           if p.geom_type == "Polygon")]
        if hosts:
            face_mat[i] = min(hosts, key=lambda r: r["area"])["mat"]

    # Undefined faces (no covering hatch, e.g. equipment pads) and slivers (< SLIVER m2) take the material
    # of the neighbour with the longest shared edge. Geometry is kept, only the ID changes.
    reassigned = []
    ftree = shapely.STRtree(faces)
    for _ in range(3):
        for i, f in enumerate(faces):
            if face_mat[i] != "Undefined" and f.area >= SLIVER:
                continue
            if face_mat[i] == "Undefined" and f.area > UNDEF_MAX:  # building footprints etc. stay for review
                continue
            best, best_len = None, 0.0
            for j in ftree.query(f, predicate="touches"):
                if j == i or face_mat[j] == "Undefined" or (faces[j].area < SLIVER and faces[j].area < f.area):
                    continue
                L = f.boundary.intersection(faces[j].boundary).length
                if L > best_len:
                    best, best_len = face_mat[j], L
            if best and best != face_mat[i]:
                reassigned.append((face_mat[i], best, round(f.area, 4)))
                face_mat[i] = best

    # ---------- triangulate with shared vertices ----------
    x0, y0 = (round(clip.bounds[0]), round(clip.bounds[1]))
    vid: dict[tuple[int, int], int] = {}
    verts, tris, tri_mat = [], [], []

    def v(pt):
        key = (round(pt[0] / SNAP), round(pt[1] / SNAP))
        if key not in vid:
            vid[key] = len(verts)
            verts.append((round(pt[0] - x0, 4), round(pt[1] - y0, 4)))
        return vid[key]

    area_by_mat = Counter()
    for f, m in zip(faces, face_mat):
        area_by_mat[m] += f.area
        for t in shapely.get_parts(shapely.constrained_delaunay_triangles(f)):
            c = list(t.exterior.coords)[:3]
            a = (c[1][0] - c[0][0]) * (c[2][1] - c[0][1]) - (c[2][0] - c[0][0]) * (c[1][1] - c[0][1])
            if abs(a) < 1e-9:
                continue
            if a < 0:
                c = [c[0], c[2], c[1]]
            ids = [v(p) for p in c]
            if len(set(ids)) < 3:
                continue
            tris.append(ids)
            tri_mat.append(MATERIALS.index(m) + 1)

    # ---------- checks: open edges and T-junctions ----------
    ecount = Counter()
    for t in tris:
        for i in range(3):
            a, b = t[i], t[(i + 1) % 3]
            ecount[(min(a, b), max(a, b))] += 1
    open_edges = [e for e, n in ecount.items() if n == 1]
    nonmanifold = [e for e, n in ecount.items() if n > 2]
    clip_b = clip.boundary.buffer(0.002)
    inner_open = [e for e in open_edges
                  if not clip_b.contains(LineString([(verts[e[0]][0] + x0, verts[e[0]][1] + y0),
                                                      (verts[e[1]][0] + x0, verts[e[1]][1] + y0)]))]
    mesh_area = sum(area_by_mat.values())

    # ---------- paint and curbs ----------
    paint, curbs = [], []
    for e in ents:
        lay = e.dxf.layer
        t = e.dxftype()
        if lay == PAINT_LAYER:
            if t == "LWPOLYLINE":
                pts = e.get_points("xyb")
                if not clip.buffer(0.05).intersects(LineString([(p[0], p[1]) for p in pts]) if len(pts) > 1 else Point(pts[0][:2])):
                    continue
                paint.append({"kind": "poly", "closed": bool(e.closed), "width": e.dxf.const_width or 0.05,
                              "v": [(round(p[0] - x0, 5), round(p[1] - y0, 5), p[2]) for p in pts]})
            elif t in ("CIRCLE", "ARC"):
                c = e.dxf.center
                if not clip.contains(Point(c.x, c.y)):  # a circle belongs to the area of its centre
                    continue
                item = {"kind": "circle" if t == "CIRCLE" else "arc", "c": (round(c.x - x0, 5), round(c.y - y0, 5)),
                        "r": e.dxf.radius, "width": 0.05}
                if t == "ARC":
                    item.update(a0=e.dxf.start_angle, a1=e.dxf.end_angle)
                paint.append(item)
        elif lay in CURB_LAYERS and t == "LWPOLYLINE":
            pts = e.get_points("xyb")
            ls = LineString([(p[0], p[1]) for p in pts])
            if not clip.buffer(0.3).intersects(ls):
                continue
            name, w, h = CURB_LAYERS[lay]
            curbs.append({"name": name, "width": w, "height": h, "closed": bool(e.closed),
                          "v": [(round(p[0] - x0, 5), round(p[1] - y0, 5), p[2]) for p in pts]})

    # ---------- joint paint: a white line where two different rubbers meet (user 2026-11-04) ----------
    # Parts already carried by a DWG paint line (e.g. the outer ring of a circle) are left out.
    def item_line(p):
        if p["kind"] == "poly":
            pts = poly_pts(p["v"], p["closed"])
        elif p["kind"] == "circle":
            pts = circle_pts(p["c"][0] + x0, p["c"][1] + y0, p["r"])
            pts = [(a - x0, b - y0) for a, b in pts]
        else:
            return None
        return LineString(pts) if len(pts) > 1 else None

    covered = unary_union([g for g in (item_line(p) for p in paint) if g is not None]).buffer(JOINT_COVERED)
    by_mat = defaultdict(list)
    for f, m in zip(faces, face_mat):
        by_mat[m].append(shapely.affinity.translate(f, -x0, -y0))
    rub = sorted(m for m in by_mat if m in JOINT_MATERIALS)
    unions = {m: unary_union(by_mat[m]) for m in rub}
    joint_lines = []
    for i, a in enumerate(rub):
        for b in rub[i + 1:]:
            shared = unions[a].boundary.intersection(unions[b].boundary)
            shared = shapely.line_merge(unary_union([g for g in shapely.get_parts(shared)
                                                     if g.geom_type in ("LineString", "MultiLineString")]))
            # only stretches running along a DWG line count as covered; crossings do not cut the joint
            along = [g for g in shapely.get_parts(shared.intersection(covered)) if g.length >= JOINT_ALONG]
            free = shared.difference(unary_union(along).buffer(0.001)) if along else shared
            joint_lines += [g for g in shapely.get_parts(shapely.line_merge(free) if not free.is_empty else free)
                            if g.geom_type == "LineString" and g.length >= JOINT_MIN_LEN]
    for g in joint_lines:
        cs = [(round(x, 5), round(y, 5)) for x, y in g.coords]
        paint.append({"kind": "pts", "closed": cs[0] == cs[-1], "width": 0.05,
                      "pts": cs[:-1] if cs[0] == cs[-1] else cs})

    data = {
        "origin": [x0, y0, 0.0],
        "materials": [{"id": i + 1, "name": m, "rgb": COLOURS[m]} for i, m in enumerate(MATERIALS)],
        "verts": verts, "faces": tris, "matid": tri_mat, "paint": paint, "curbs": curbs,
    }
    (out_dir / "ground.json").write_text(json.dumps(data), encoding="utf-8")
    report = {
        "clip_area": round(clip.area, 3), "mesh_area": round(mesh_area, 3),
        "area_by_material": {k: round(v, 3) for k, v in area_by_mat.most_common()},
        "faces_polygonized": len(faces), "triangles": len(tris), "vertices": len(verts),
        "open_edges_total": len(open_edges), "open_edges_inside_clip": len(inner_open),
        "nonmanifold_edges": len(nonmanifold), "circle_grids": len(_circles),
        "paint_items": Counter(p["kind"] for p in paint), "curbs": len(curbs),
        "regions_used": Counter(r["mat"] for r in regions), "reassigned_faces": reassigned,
        "hatches_skipped_by_layer_colour": {f"{k[0]} | {k[1]}": n for k, n in skipped.most_common()},
        "origin": [x0, y0],
    }
    (out_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=dict), encoding="utf-8")
    print(json.dumps({k: report[k] for k in list(report)[:12]}, ensure_ascii=False, default=dict))


if __name__ == "__main__":
    main(*sys.argv[1:4])
