"""TOW02 body: a stack of rings with step soffits, plus ribbon-opening glass planes (runs inside Blender).

Engine gap: EG6 (panelised curtain-wall source: body built from measurements, docs/backlog.md).

A ring = spandrel band (base .. base+band_h) + glazed storey (.. base+ring_h) on one closed outline. All rings of
a stack have outlines with the same vertex count and order (vertex i of ring k = vertex i of ring k+1;
outputs/measure-v002/bend_rings/bend_rings.json). Outline edges carry intervals `flush solid` / `recessed (glass
behind)`; a recessed run is a hole in the storey row with reveals `reveal_m` deep (mitred at outline vertices,
jambs only at run ends) and a glass plane at mid reveal, `plane_overlap_m` beyond the opening on all sides.

Edges are of two kinds across the stack:
- fixed: one end (or both) never moves. Its columns are shared by all rings (no T-junctions): measured from the
  fixed end, they are every ring's end point plus the interval breakpoints, snapped within `snap_m` to the
  reference (last) ring's breakpoints.
- moving ("own"): the edge moves in every ring; each ring uses its own breakpoints (same count in every ring).
A run of moving edges between two fixed edges is a chain. Where ring k+1 differs from ring k, the step between
them is filled with quads between corresponding columns of the chain, cut into strips at the fractions where
the fixed edges at the chain ends have columns in their extension zone (between the two rings' end points); the
same fractions are added as columns to both fixed edges, so the strips meet the walls without T-junctions.
An edge that collapses in a ring (< 5 mm, a jog that disappears) is kept as one column and the next edge starts
`collapse_shift_m` further along itself, so the step stays quads.
Coordinates: building-local (inspect_sections.py, rotation 56.7 deg) -> world on output. All faces are quads.

    ns = {}; exec(open(path).read(), ns); ns["build"](cfg)   # from the Blender MCP / Python console
"""
import json
import math

import bmesh
import bpy
from mathutils import Vector

LOCAL_ANGLE_DEG = 56.7
MAX_SIDE_M = 3.8
EPS_POS = 0.01           # positions closer than this are one column (user 2026-10-20: <= 1 cm is skipped)
END_EPS = 0.02           # interval breakpoints closer than this to an edge end are the end (piers >= 0.3 m)
COLLAPSE_M = 0.005       # an edge shorter than this has collapsed in that ring
WELD_M = 0.01            # generated points closer than this are one vertex (user: <= 1 cm is skipped)


def to_world(x, y, z):
    """Building-local -> world: inverse of co_local = co_world @ R (R = rotZ(56.7 deg))."""
    a = math.radians(LOCAL_ANGLE_DEG)
    c, s = math.cos(a), math.sin(a)
    return Vector((x * c - y * s, x * s + y * c, z))


def V(p):
    return Vector((p[0], p[1]))


class Builder:
    """bmesh of generated quads: points within WELD_M are one vertex, degenerate and duplicate quads refused."""

    def __init__(self):
        self.bm = bmesh.new()
        self.grid, self.fset = {}, set()
        self.skipped = {"degenerate": 0, "duplicate": 0}

    def v(self, p):
        cell = tuple(int(math.floor(c / WELD_M)) for c in p)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q, vert in self.grid.get((cell[0] + dx, cell[1] + dy, cell[2] + dz), ()):
                        if (Vector(q) - Vector(p)).length <= WELD_M:
                            return vert
        vert = self.bm.verts.new(to_world(*p))
        self.grid.setdefault(cell, []).append((tuple(p), vert))
        return vert

    def quad(self, pts, mat, want=None):
        vs = [self.v(p) for p in pts]
        if len(set(vs)) < 4:
            self.skipped["degenerate"] += 1
            return None
        a, b, c, d = (Vector(p) for p in pts)
        if ((c - a).cross(d - b)).length < 1e-8:
            self.skipped["degenerate"] += 1
            return None
        key = frozenset(vs)
        if key in self.fset:
            self.skipped["duplicate"] += 1
            return None
        self.fset.add(key)
        f = self.bm.faces.new(vs)
        f.material_index = mat
        if want is not None:
            f.normal_update()
            if f.normal.dot(want) < 0:
                f.normal_flip()
        return f


def _breaks(e):
    """Interior interval breakpoints of an edge, sorted, merged within EPS_POS."""
    ts = sorted(t for iv in e["intervals"] for t in (iv["t0"], iv["t1"]) if END_EPS < t < e["length"] - END_EPS)
    out = []
    for t in ts:
        if not out or t - out[-1] > EPS_POS:
            out.append(t)
    return out


def _gaps(breaks, L):
    full = [0.0] + breaks + [L]
    return [full[k + 1] - full[k] for k in range(len(full) - 1)]


def _add(pos, p, tol):
    if all(abs(p - q) > tol for q in pos):
        pos.append(p)


def prepare(rings, cfg):
    """Edge kinds, shared positions of fixed edges, splits of moving edges, chains and step fractions."""
    n = len(rings[0]["edges"])
    if any(len(r["edges"]) != n for r in rings):
        raise ValueError("rings differ in vertex count")
    for r in rings:                      # collapsed edge i: start edge i+1 `collapse_shift_m` further along it
        r["start_shift"] = [0.0] * n
        for i, e in enumerate(r["edges"]):
            if e["length"] < COLLAPSE_M:
                j = (i + 1) % n
                first = min([iv["t0"] for iv in r["edges"][j]["intervals"] if iv["t0"] > 1e-4] +
                            [r["edges"][j]["length"]])
                r["start_shift"][j] = min(cfg["collapse_shift_m"], 0.5 * first)
    ref_ring = rings[-1]
    kinds, pos, splits = [], [], []
    for i in range(n):
        A0, B0 = V(ref_ring["edges"][i]["a"]), V(ref_ring["edges"][i]["b"])
        ma = max((V(r["edges"][i]["a"]) - A0).length for r in rings)
        mb = max((V(r["edges"][i]["b"]) - B0).length for r in rings)
        if ma < 1e-3 and mb < 1e-3:
            kind = "still"
        elif ma < 1e-3:
            kind = "a"                   # end a fixed, end b moves
        elif mb < 1e-3:
            kind = "b"
        else:
            kind = "own"
        kinds.append(kind)
    snapped = _snap_fixed_lines(rings, kinds)
    for i in range(n):
        kind = kinds[i]
        if kind == "own":
            counts = {len(_breaks(r["edges"][i])) for r in rings if r["edges"][i]["length"] >= COLLAPSE_M}
            if len(counts) > 1:
                raise ValueError(f"edge {i}: moving edge with a different number of breakpoints per ring {counts}")
            gaps = _gaps(_breaks(ref_ring["edges"][i]), ref_ring["edges"][i]["length"])
            splits.append([max(1, math.ceil(g / MAX_SIDE_M - 1e-9)) for g in gaps])
            pos.append(None)
            continue
        splits.append(None)
        p = []
        for r in rings:                  # every ring's end point, exactly
            _add(p, r["edges"][i]["length"], EPS_POS)
        dist = (lambda r, t: t) if kind in ("a", "still") else (lambda r, t: r["edges"][i]["length"] - t)
        for t in _breaks(ref_ring["edges"][i]):
            _add(p, dist(ref_ring, t), cfg["snap_m"])
        for r in rings:
            for t in _breaks(r["edges"][i]):
                _add(p, dist(r, t), cfg["snap_m"])
        p.sort()
        full = [0.0] + p
        out = []
        for k in range(len(full) - 1):
            g = full[k + 1] - full[k]
            m = max(1, math.ceil(g / MAX_SIDE_M - 1e-9))
            out += [full[k] + g * s / m for s in range(1, m + 1)]
        pos.append(out)
    # chains: maximal runs of moving edges, bounded by fixed edges whose moving end touches the run
    chains = []
    i = 0
    seen = set()
    for start in range(n):
        if kinds[start] == "own" and kinds[(start - 1) % n] != "own" and start not in seen:
            run = []
            j = start
            while kinds[j % n] == "own":
                run.append(j % n)
                seen.add(j % n)
                j += 1
            left, right = (start - 1) % n, j % n
            if kinds[left] != "a" or kinds[right] != "b":
                raise ValueError(f"chain {run}: bounded by {left}:{kinds[left]} / {right}:{kinds[right]}")
            chains.append({"edges": run, "left": left, "right": right})
    # step fractions per chain and ring pair; add the matching columns to both bounding edges
    fracs = {}
    for k in range(len(rings) - 1):
        for c, ch in enumerate(chains):
            s_set = []
            for side in ("left", "right"):
                e = ch[side]
                L0, L1 = rings[k]["edges"][e]["length"], rings[k + 1]["edges"][e]["length"]
                if abs(L1 - L0) < 1e-4:
                    continue
                lo, hi = min(L0, L1), max(L0, L1)
                for d in pos[e]:
                    if lo + 1e-4 < d < hi - 1e-4:
                        _add(s_set, (d - L0) / (L1 - L0), EPS_POS / abs(L1 - L0))
            s_set.sort()
            fracs[(k, c)] = s_set
            for side in ("left", "right"):
                e = ch[side]
                L0, L1 = rings[k]["edges"][e]["length"], rings[k + 1]["edges"][e]["length"]
                if abs(L1 - L0) < 1e-4:
                    continue
                for s in s_set:
                    _add(pos[e], L0 + s * (L1 - L0), EPS_POS)
                pos[e].sort()
    return kinds, pos, splits, chains, fracs, snapped


def _snap_fixed_lines(rings, kinds):
    """Put every ring's vertices of fixed edges on the reference ring's lines (rings measured separately differ
    by ~1 mm, which would leave seams between rings). Returns the largest vertex move."""
    n = len(kinds)
    ref = rings[-1]["edges"]
    worst = 0.0
    for r in rings:
        E = r["edges"]
        verts = [V(E[i]["a"]) for i in range(n)]
        new = []
        for i in range(n):
            prev, cur = kinds[(i - 1) % n], kinds[i]
            if prev in ("still", "b") or cur in ("still", "a"):
                p = V(ref[i]["a"])                       # this vertex never moves
            elif prev == "a":                            # moving end b of the previous fixed edge
                p = _project(verts[i], V(ref[(i - 1) % n]["a"]), V(ref[(i - 1) % n]["b"]))
            elif cur == "b":                             # moving end a of this fixed edge
                p = _project(verts[i], V(ref[i]["a"]), V(ref[i]["b"]))
            else:
                p = verts[i]
            worst = max(worst, (p - verts[i]).length)
            new.append(p)
        edges = []
        for i in range(n):
            e = dict(E[i])
            a, b = new[i], new[(i + 1) % n]
            e["a"], e["b"], e["length"] = [a.x, a.y], [b.x, b.y], (b - a).length
            edges.append(e)
        r["edges"] = edges
    return worst


def _project(p, a, b):
    d = (b - a).normalized()
    return a + d * (p - a).dot(d)


def ring_columns(r, kinds, pos, splits):
    """Cyclic columns of one ring: (x, y, edge, recessed_after)."""
    cols = []
    for i, e in enumerate(r["edges"]):
        L = e["length"]
        a, b = V(e["a"]), V(e["b"])
        if L < COLLAPSE_M:               # kept as one column; the next edge starts `start_shift` further on
            cols.append((a.x, a.y, i, False))
            continue
        t_start = r["start_shift"][i]
        ts = [t_start]
        if kinds[i] == "own":
            full = [0.0] + _breaks(e) + [L]
            for k, m in enumerate(splits[i]):
                ts += [full[k] + (full[k + 1] - full[k]) * s / m for s in range(1, m + 1)]
            ts = [t for t in ts if t_start - 1e-9 <= t < L - EPS_POS]
        else:
            for d in pos[i]:
                t = d if kinds[i] in ("a", "still") else L - d
                if t_start + 1e-4 < t < L - 1e-4:
                    ts.append(t)
        ts = sorted(set(round(t, 7) for t in ts))
        for k, t in enumerate(ts):
            t1 = ts[k + 1] if k + 1 < len(ts) else L
            mid = 0.5 * (t + t1)
            rec = any(iv["kind"].startswith("recessed") and iv["t0"] - 1e-4 <= mid <= iv["t1"] + 1e-4
                      for iv in e["intervals"])
            p = a + (b - a) * (t / L)
            cols.append((p.x, p.y, i, rec))
    return cols


def edge_points(cols, i):
    """Columns of edge i plus its closing point (the next column in cyclic order)."""
    idx = [q for q, c in enumerate(cols) if c[2] == i]
    nxt = cols[(idx[-1] + 1) % len(cols)]
    return [(cols[q][0], cols[q][1]) for q in idx] + [(nxt[0], nxt[1])]


def offset_points(cols, depth):
    """Point `depth` inside the outline at every column (mitred at corners)."""
    n = len(cols)
    out = []
    for i in range(n):
        p0, p1, p2 = (Vector(cols[(i + k) % n][:2]) for k in (-1, 0, 1))
        d0, d1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0, n1 = Vector((d0.y, -d0.x)), Vector((d1.y, -d1.x))   # outward = right of a CCW edge
        m = n0 + n1
        if m.length < 1e-6:
            m = n1
        m.normalize()
        out.append(p1 - m * (depth / max(m.dot(n1), 0.2)))
    return out


def build_stack(rings, cfg, body_name, glass_name, coll):
    kinds, pos, splits, chains, fracs, snapped = prepare(rings, cfg)
    B, G = Builder(), Builder()
    facade, reveal = 0, 1
    allcols = [ring_columns(r, kinds, pos, splits) for r in rings]
    for k, r in enumerate(rings):
        cols = allcols[k]
        n = len(cols)
        z0, z1, z2 = r["base"], r["base"] + r["band_h"], r["base"] + r["ring_h"]
        inner = offset_points(cols, cfg["reveal_m"])
        mid = offset_points(cols, cfg["reveal_m"] / 2)
        P = lambda i, z: (cols[i % n][0], cols[i % n][1], z)
        Q = lambda i, z: (inner[i % n].x, inner[i % n].y, z)
        for i in range(n):
            j = (i + 1) % n
            B.quad((P(i, z0), P(j, z0), P(j, z1), P(i, z1)), facade)
            if not cols[i][3]:
                B.quad((P(i, z1), P(j, z1), P(j, z2), P(i, z2)), facade)
                continue
            B.quad((Q(i, z1), Q(j, z1), P(j, z1), P(i, z1)), reveal)            # sill
            B.quad((P(i, z2), P(j, z2), Q(j, z2), Q(i, z2)), reveal)            # head
            if not cols[(i - 1) % n][3]:
                B.quad((P(i, z1), P(i, z2), Q(i, z2), Q(i, z1)), reveal)        # jamb at run start
            if not cols[j][3]:
                B.quad((P(j, z1), Q(j, z1), Q(j, z2), P(j, z2)), reveal)        # jamb at run end
        start = next((i for i in range(n) if not cols[i][3]), None)             # glass planes per run
        i0 = None
        for s in range(1, n + 1):
            i = (start + s) % n
            if cols[i][3] and i0 is None:
                i0 = i
            if not cols[i][3] and i0 is not None:
                idx = [(i0 + q) % n for q in range(((i - i0) % n) + 1)]
                pts = [mid[q].copy() for q in idx]
                pts[0] -= (V(cols[idx[1]]) - V(cols[idx[0]])).normalized() * cfg["plane_overlap_m"]
                pts[-1] += (V(cols[idx[-1]]) - V(cols[idx[-2]])).normalized() * cfg["plane_overlap_m"]
                ga, gb = z1 - cfg["plane_overlap_m"], z2 + cfg["plane_overlap_m"]
                for q in range(len(pts) - 1):
                    G.quad(((pts[q].x, pts[q].y, ga), (pts[q + 1].x, pts[q + 1].y, ga),
                            (pts[q + 1].x, pts[q + 1].y, gb), (pts[q].x, pts[q].y, gb)), 0)
                i0 = None
    steps = {"quads": 0, "count_mismatch": []}
    for k in range(len(rings) - 1):
        lo, up = rings[k], rings[k + 1]
        z = lo["base"] + lo["ring_h"]
        if abs(z - up["base"]) > 1e-6:
            raise ValueError(f"ring {k} top {z} != ring {k + 1} base {up['base']}")
        for c, ch in enumerate(chains):
            ss = [0.0] + fracs[(k, c)] + [1.0]
            for i in ch["edges"]:
                pl, pu = edge_points(allcols[k], i), edge_points(allcols[k + 1], i)
                if len(pl) != len(pu):
                    steps["count_mismatch"].append({"ring": k, "edge": i, "lo": len(pl), "up": len(pu)})
                    continue
                for q in range(len(pl) - 1):
                    a0, b0, a1, b1 = V(pl[q]), V(pl[q + 1]), V(pu[q]), V(pu[q + 1])
                    if (a0 - a1).length < 1e-4 and (b0 - b1).length < 1e-4:
                        continue
                    e = b0 - a0 if (b0 - a0).length > 1e-6 else b1 - a1
                    outward = Vector((e.y, -e.x)).dot((a1 + b1) - (a0 + b0)) > 0
                    want = Vector((0, 0, -1 if outward else 1))
                    for s0, s1 in zip(ss[:-1], ss[1:]):
                        A0, B0 = a0.lerp(a1, s0), b0.lerp(b1, s0)
                        A1, B1 = a0.lerp(a1, s1), b0.lerp(b1, s1)
                        f = B.quad(((A0.x, A0.y, z), (B0.x, B0.y, z), (B1.x, B1.y, z), (A1.x, A1.y, z)),
                                   facade, want)
                        steps["quads"] += f is not None
    sealed = seal_leftovers(B.bm, [r["base"] for r in rings[1:]])
    body = _to_object(B.bm, body_name, coll)
    glass = _to_object(G.bm, glass_name, coll)
    return body, glass, {"rings": len(rings), "sealed": sealed, "columns_per_ring": [len(c) for c in allcols],
                         "chains": [(ch["left"], ch["edges"][0], ch["edges"][-1], ch["right"]) for ch in chains],
                         "snap_fixed_lines_max_m": round(snapped, 4), "skipped": B.skipped, "steps": steps}


def seal_leftovers(bm, open_z, reveal_mat=1):
    """Close what the step logic leaves at ring joins (z in open_z): a closed 4-edge boundary loop gets a quad;
    a collinear 3-edge loop is a T-junction: the T vertex is welded into the long edge and the long edge's face is
    cut from the T vertex to its far corner (one triangle, reported)."""
    report = {"quads_added": 0, "tjunctions": 0, "triangles": 0, "left": 0}

    def candidates():
        out = []
        for e in bm.edges:
            if not e.is_boundary or {f.material_index for f in e.link_faces} == {reveal_mat}:
                continue
            z0, z1 = e.verts[0].co.z, e.verts[1].co.z
            if abs(z0 - z1) < 1e-6 and any(abs(z0 - z) < 1e-4 for z in open_z):
                out.append(e)
        return out

    def loops(edges):
        es, groups = set(edges), []
        while es:
            e = es.pop()
            g, front = [e], [e]
            while front:
                x = front.pop()
                for v in x.verts:
                    for y in v.link_edges:
                        if y in es:
                            es.remove(y)
                            g.append(y)
                            front.append(y)
            groups.append(g)
        return groups

    for g in loops(candidates()):
        vs = list({v for e in g for v in e.verts})
        if len(g) == 4 and len(vs) == 4:
            ordered = [g[0].verts[0], g[0].verts[1]]
            while len(ordered) < 4:
                nxt = next(e.other_vert(ordered[-1]) for e in g
                           if ordered[-1] in e.verts and e.other_vert(ordered[-1]) not in ordered)
                ordered.append(nxt)
            f = bm.faces.new(ordered)
            f.normal_update()
            if f.normal.z > 0:           # step soffit under an overhang faces down
                f.normal_flip()
            report["quads_added"] += 1
        elif len(g) == 3 and len(vs) == 3:
            long_e = max(g, key=lambda e: e.calc_length())
            t = next(v for v in vs if v not in long_e.verts)
            face = long_e.link_faces[0]
            a = long_e.verts[0]
            fac = (t.co - a.co).length / long_e.calc_length()
            new_e, nv = bmesh.utils.edge_split(long_e, a, fac)
            bmesh.ops.pointmerge(bm, verts=[nv, t], merge_co=t.co.copy())
            t = nv if nv.is_valid else t
            report["tjunctions"] += 1
            far = max((v for v in face.verts if v is not t), key=lambda v: (v.co - t.co).length)
            bmesh.ops.connect_verts(bm, verts=[t, far])
            report["triangles"] += sum(1 for f in t.link_faces if len(f.verts) == 3)
        else:
            report["left"] += len(g)
    return report


def _to_object(bm, name, collection):
    if name in bpy.data.objects:
        raise ValueError(f"object {name} exists; use a new name")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def material(name, rgba):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = rgba
    return m


def build(cfg):
    """cfg: collection, name, rings_json, typical_bases, band_h, ring_h, reveal_m, plane_overlap_m,
    collapse_shift_m, snap_m. Bend rings = the non-reference rings of rings_json; typical rings use its reference."""
    coll = bpy.data.collections.get(cfg["collection"])
    if coll is None:
        coll = bpy.data.collections.new(cfg["collection"])
        bpy.context.scene.collection.children.link(coll)
    data = json.load(open(cfg["rings_json"], encoding="utf-8"))["rings"]
    typical = next(r for r in data if r.get("reference"))
    rings = [dict(base=r["base"], band_h=cfg["band_h"], ring_h=cfg["ring_h"], edges=r["edges"])
             for r in data if not r.get("reference")]
    rings += [dict(base=b, band_h=cfg["band_h"], ring_h=cfg["ring_h"], edges=typical["edges"])
              for b in cfg["typical_bases"]]
    rings.sort(key=lambda r: r["base"])
    body, glass, info = build_stack(rings, cfg, cfg["name"], cfg["name"] + "_glass", coll)
    body.data.materials.append(material("TOW02_facade", (0.12, 0.12, 0.12, 1)))
    body.data.materials.append(material("TOW02_reveal", (0.35, 0.35, 0.35, 1)))
    glass.data.materials.append(material("TOW02_glass", (0.25, 0.5, 0.9, 1)))
    info.update(body_faces=len(body.data.polygons), glass_faces=len(glass.data.polygons))
    return info
