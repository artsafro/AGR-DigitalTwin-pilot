"""new-case: polygon station objects of #1024 branch K (body.capsules 1.0.12, body.roof 1.0.13) + synthetic data.

build_scene.py calls make(obj, rt) -> node for every K.json object with `"builder": "K_build"`; obj['extra'] says
what to build (metres; converted to system units with units.SystemScale, so a centimetre scene gets the same
metric object):
* {"kind": "badik", "size": [W, L, H], "reveal": d, "openings": [...], "at": [x, y, z]} - a box body without a
  bottom, recessed openings (facade hole -> reveal faces -> open border loop at depth d). Opening rows:
  {"wall": 0..3, "s": [s0, s1], "z": [z0, z1]} rectangle; {"corner": 0..3, "a": sa, "b": sb, "z": [z0, z1]} a corner
  opening around the end of wall k (sa before the corner on wall k, sb after it on wall k+1);
  {"wall": k, "s": [...], "z": [...], "arch": n} a round head of n (even) segments, alone on its wall; {"wall": k, "s": [...], "z": [...],
  "bump": m} the top-right border vertex m metres out of the border plane.
* {"kind": "parapet", "outline": [[x, y]...], "level": z, "height": h, "thickness": t, "slope_deg": s,
  "terrace": bool, "at": [...]} - inner parapet faces around the roof hole (open bottom loop = contour A), the
  parapet top and outer faces; `slope_deg` tilts the whole parapet about the X axis (a pitched slab case).

The pure generators (badik_mesh, parapet_mesh, synthetic_openings) also feed the unit tests. synthetic_openings is
a TEST stand-in for openings_core.find_openings (branch J) until J merges: open border loops of the mesh, frame
from the wall, corner = two straight runs at 90 degrees in plan.
"""
import math

WALL_DIRS = [((1.0, 0.0), (0.0, -1.0)), ((0.0, 1.0), (1.0, 0.0)), ((-1.0, 0.0), (0.0, 1.0)),
             ((0.0, -1.0), (-1.0, 0.0))]  # (run direction, outward normal) of walls S, E, N, W (CCW from above)


def _walls(W, L):
    starts = [(0.0, 0.0), (W, 0.0), (W, L), (0.0, L)]
    lens = [W, L, W, L]
    return [(starts[k], lens[k], WALL_DIRS[k][0], WALL_DIRS[k][1]) for k in range(4)]


class _Mesh:
    def __init__(self):
        self.verts, self.faces, self.index = [], [], {}

    def v(self, p):
        key = tuple(round(c, 7) for c in p)
        if key not in self.index:
            self.index[key] = len(self.verts)
            self.verts.append([float(c) for c in p])
        return self.index[key]

    def f(self, pts):
        ids = [self.v(p) for p in pts]
        out = []
        for i in ids:
            if not out or out[-1] != i:
                out.append(i)
        if len(out) > 1 and out[0] == out[-1]:
            out.pop()
        if len(out) >= 3:
            self.faces.append(out)


def _wp(wall, s, z, depth=0.0):
    (x0, y0), _, (tx, ty), (nx, ny) = wall
    return (x0 + tx * s - nx * depth, y0 + ty * s - ny * depth, z)


def _arch_pts(s0, s1, z0, z1, n):
    """Rectangle with a round head (half circle of the width) from (s0,z0) CCW in (s, z)."""
    r = (s1 - s0) / 2.0
    zc = z1 - r
    pts = [(s0, z0), (s0 + r, z0), (s1, z0)]  # the crown column splits the sill too (no T-junction)
    for i in range(n + 1):
        t = math.pi * i / n
        pts.append((s0 + r + r * math.cos(t), zc + r * math.sin(t)))
    return pts


def badik_mesh(W, L, H, reveal, openings):
    """Box body without a bottom, recessed openings; returns {'verts', 'faces', 'openings': ground truth}."""
    m = _Mesh()
    walls = _walls(W, L)
    rects = {k: [] for k in range(4)}  # holes in (s, z) per wall
    zs = {0.0, H}
    for op in openings:
        z0, z1 = op['z']
        zs.update((z0, z1))
        if 'corner' in op:
            k = op['corner']
            rects[k].append((walls[k][1] - op['a'], walls[k][1], z0, z1))
            rects[(k + 1) % 4].append((0.0, op['b'], z0, z1))
        else:
            rects[op['wall']].append((op['s'][0], op['s'][1], z0, z1))
            if op.get('arch'):  # no T-junctions at the springing line and the crown of the round head
                r = (op['s'][1] - op['s'][0]) / 2.0
                zs.add(z1 - r)
                rects[op['wall']].append((op['s'][0] + r, op['s'][0] + r, z0, z0))
    zs = sorted(zs)
    ssw = [sorted({0.0, w[1]} | {r[0] for r in rects[k]} | {r[1] for r in rects[k]}) for k, w in enumerate(walls)]

    def run(a, b, cuts):  # a, then the grid cuts strictly between a and b in order (b excluded)
        mid = sorted(c for c in cuts if min(a, b) + 1e-9 < c < max(a, b) - 1e-9)
        return [a] + (mid if b > a else mid[::-1])
    for k, wall in enumerate(walls):
        ss = ssw[k]
        for i in range(len(ss) - 1):
            for j in range(len(zs) - 1):
                cs, cz = (ss[i] + ss[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2
                if any(r[0] < cs < r[1] and r[2] < cz < r[3] for r in rects[k]):
                    continue
                pts = [_wp(wall, ss[i], zs[j]), _wp(wall, ss[i + 1], zs[j])]
                # a vertical seam on the left/right edge also gets the z breakpoints of the neighbours (no T)
                pts += [_wp(wall, ss[i + 1], zs[j + 1]), _wp(wall, ss[i], zs[j + 1])]
                m.f(pts)
    # top cap: all top vertices along the walls, CCW from above (normal up)
    top = []
    for k, wall in enumerate(walls):
        top += [_wp(wall, s, H) for s in ssw[k][:-1]]
    m.f(top)
    truth = []
    for n, op in enumerate(openings, 1):
        z0, z1 = op['z']
        if 'corner' in op:
            k = op['corner']
            wa, wb = walls[k], walls[(k + 1) % 4]
            sa = wa[1] - op['a']
            kb_ = (k + 1) % 4
            ca = (wa[0][0] + wa[2][0] * wa[1] - wa[3][0] * reveal - wb[3][0] * reveal,
                  wa[0][1] + wa[2][1] * wa[1] - wa[3][1] * reveal - wb[3][1] * reveal)
            outer, inner = [], []
            for s_ in run(sa, wa[1], ssw[k]):
                outer.append(_wp(wa, s_, z0))
                inner.append(_wp(wa, s_, z0, reveal))
            outer.append(_wp(wa, wa[1], z0))
            inner.append((ca[0], ca[1], z0))
            for s_ in run(0.0, op['b'], ssw[kb_])[1:]:
                outer.append(_wp(wb, s_, z0))
                inner.append(_wp(wb, s_, z0, reveal))
            for z_ in run(z0, z1, zs):
                outer.append(_wp(wb, op['b'], z_))
                inner.append(_wp(wb, op['b'], z_, reveal))
            for s_ in run(op['b'], 0.0, ssw[kb_]):
                outer.append(_wp(wb, s_, z1))
                inner.append(_wp(wb, s_, z1, reveal))
            outer.append(_wp(wa, wa[1], z1))
            inner.append((ca[0], ca[1], z1))
            for s_ in run(wa[1], sa, ssw[k])[1:] + [sa]:
                outer.append(_wp(wa, s_, z1))
                inner.append(_wp(wa, s_, z1, reveal))
            for z_ in run(z1, z0, zs)[1:]:
                outer.append(_wp(wa, sa, z_))
                inner.append(_wp(wa, sa, z_, reveal))
            frame_z = [wa[3][0], wa[3][1], 0.0]
            frame_x = [wa[2][0], wa[2][1], 0.0]
            corner = True
        else:
            wall = walls[op['wall']]
            s0, s1 = op['s']
            if op.get('arch'):
                sz = _arch_pts(s0, s1, z0, z1, op['arch'])
            else:
                ss = ssw[op['wall']]
                sz = [(s_, z0) for s_ in run(s0, s1, ss)] + [(s1, z_) for z_ in run(z0, z1, zs)] +                      [(s_, z1) for s_ in run(s1, s0, ss)] + [(s0, z_) for z_ in run(z1, z0, zs)]
            outer = [_wp(wall, s, z) for s, z in sz]
            inner = [_wp(wall, s, z, reveal) for s, z in sz]
            if op.get('bump'):
                i = len(inner) // 2 if op.get('arch') else sz.index((s1, z1))
                p = inner[i]
                inner[i] = (p[0] + wall[3][0] * op['bump'], p[1] + wall[3][1] * op['bump'], p[2])
            frame_z = [wall[3][0], wall[3][1], 0.0]
            frame_x = [wall[2][0], wall[2][1], 0.0]
            corner = False
            if op.get('arch'):
                # the facade hole of the arch: the grid cell is the bounding rectangle; fill the corners above
                # the round head between the rectangle and the arch (wall material in front of the reveal)
                head = [_wp(wall, s, z) for s, z in sz[3:]]
                m.f([_wp(wall, s1, z1)] + head[:len(head) // 2 + 1])
                m.f([_wp(wall, s0, z1)] + head[len(head) // 2:])
        for i in range(len(outer)):
            j = (i + 1) % len(outer)
            m.f([outer[i], outer[j], inner[j], inner[i]])
        xs = [p for p in inner]
        truth.append({'id': n, 'border': [list(p) for p in xs], 'corner': corner, 'depth': reveal,
                      'frame': {'origin': list(xs[0]), 'x': frame_x, 'y': [0.0, 0.0, 1.0], 'z': frame_z}})
    faces = _orient(m.verts, m.faces)
    return {'verts': m.verts, 'faces': faces, 'openings': truth}


def _orient(verts, faces):
    """Consistent winding from face 0 (a facade quad, outward), the same BFS as capsule_core.orient."""
    by_edge = {}
    for k, f in enumerate(faces):
        for i in range(len(f)):
            by_edge.setdefault(tuple(sorted((f[i], f[(i + 1) % len(f)]))), []).append(k)
    faces = [list(f) for f in faces]
    done = [False] * len(faces)
    for start in range(len(faces)):
        if done[start]:
            continue
        done[start] = True
        todo = [start]
        while todo:
            k = todo.pop()
            f = faces[k]
            for i in range(len(f)):
                a, b = f[i], f[(i + 1) % len(f)]
                for j in by_edge[tuple(sorted((a, b)))]:
                    if not done[j]:
                        g = faces[j]
                        if any(g[t] == a and g[(t + 1) % len(g)] == b for t in range(len(g))):
                            faces[j] = list(reversed(g))
                        done[j] = True
                        todo.append(j)
    return faces


def parapet_mesh(outline, level, height, thickness, slope_deg=0.0, terrace=False, heights=None):
    """Parapet ring around a CCW plan outline (the inner line = contour A at `level`): inner faces (open bottom
    loop), top, outer faces down to level - 0.3 m (closed outer bottom is not modelled: outer bottom stays open
    but its faces look outwards). `terrace`: the first edge is a 3 m wall instead of a parapet. Tilt about X."""
    m = _Mesh()
    n = len(outline)
    inner = [list(p) for p in outline]
    # outward offset of a CCW polygon by `thickness` (mitre)
    outer = []
    for i in range(n):
        a, b, c = inner[i - 1], inner[i], inner[(i + 1) % n]
        n1 = _edge_out(a, b)
        n2 = _edge_out(b, c)
        k = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
        outer.append([b[0] + thickness * (n1[0] + n2[0]) / k, b[1] + thickness * (n1[1] + n2[1]) / k])
    t = math.tan(math.radians(slope_deg))

    def P(p, z):
        return (p[0], p[1], z + p[1] * t)
    hv = list(heights) if heights else [height] * n
    if terrace:
        hv[0] = hv[1] = 3.0
    for i in range(n):
        j = (i + 1) % n
        h, hj = hv[i], hv[j]
        m.f([P(inner[j], level), P(inner[i], level), P(inner[i], level + h), P(inner[j], level + hj)])
        m.f([P(inner[i], level + h), P(outer[i], level + h), P(outer[j], level + hj), P(inner[j], level + hj)])
        m.f([P(outer[i], level - 0.3), P(outer[j], level - 0.3), P(outer[j], level + hj), P(outer[i], level + h)])
    faces = _orient(m.verts, m.faces)
    return {'verts': m.verts, 'faces': faces}


def _edge_out(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    return (dy / ln, -dx / ln)


# ---- TEST stand-in for openings_core.find_openings (branch J) --------------------------------------------------
def synthetic_openings(mesh, options=None):
    """Open border loops of a badik mesh -> rows of the find_openings signature (branch 0 stub). Bottom loops
    (all points on the lowest z) are not openings. Frame z: horizontal, away from the mesh centre."""
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.normpath(os.path.join(here, '..', '..', 'adapters', 'max', 'agr_tools'))
    spec = importlib.util.spec_from_file_location('k_build_roof_core', os.path.join(root, 'roof_core.py'))
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    G = rc.G
    verts = mesh['verts']
    zmin = min(v[2] for v in verts)
    cx = sum(v[0] for v in verts) / len(verts)
    cy = sum(v[1] for v in verts) / len(verts)
    loops, _ = rc.boundary_loops(mesh['faces'])
    out = []
    for loop in loops:
        pts = [verts[i] for i in loop]
        if all(abs(p[2] - zmin) < 1e-6 for p in pts):
            continue
        c = G.centroid(pts)
        plan = []
        for p in pts:
            if not any(math.hypot(p[0] - q[0], p[1] - q[1]) < 1e-4 for q in plan):
                plan.append([p[0], p[1]])
        corner = False
        if len(plan) == 3 and min(math.hypot(plan[i][0] - plan[i - 1][0], plan[i][1] - plan[i - 1][1])
                                  for i in range(3)) >= 0.2:
            a, b, k = plan[0], plan[1], plan[2]
            for ea, cc, eb in ((a, b, k), (b, k, a), (k, a, b)):
                u = (ea[0] - cc[0], ea[1] - cc[1])
                v = (eb[0] - cc[0], eb[1] - cc[1])
                if abs(u[0] * v[0] + u[1] * v[1]) < 1e-6 * math.hypot(*u) * math.hypot(*v) + 1e-9:
                    corner = True
                    zdir = [-(v[0]) / math.hypot(*v), -(v[1]) / math.hypot(*v), 0.0]
        if not corner:
            n = G.newell(pts)
            nh = [n[0], n[1], 0.0]
            zdir = G._unit(nh) if G._norm(nh) > 1e-9 else [0.0, -1.0, 0.0]
            if (c[0] - cx) * zdir[0] + (c[1] - cy) * zdir[1] < 0:
                zdir = [-zdir[0], -zdir[1], 0.0]
        else:
            # outward of the wall that holds the first run: away from the body centre
            if (c[0] - cx) * zdir[0] + (c[1] - cy) * zdir[1] < 0:
                zdir = [-zdir[0], -zdir[1], 0.0]
        out.append({'id': len(out) + 1, 'border': pts, 'corner': corner, 'depth': None,
                    'frame': {'origin': pts[0], 'x': [-zdir[1], zdir[0], 0.0], 'y': [0.0, 0.0, 1.0], 'z': zdir}})
    return out


# ---- Max builder ---------------------------------------------------------------------------------------------
def _sys_per_m(rt):
    per = {'millimeters': 0.001, 'centimeters': 0.01, 'meters': 1.0, 'kilometers': 1000.0,
           'inches': 0.0254, 'feet': 0.3048, 'miles': 1609.344}
    return 1.0 / (per[str(rt.units.SystemType).lower().lstrip('#')] * float(rt.units.SystemScale))


def mesh_node(rt, name, data, at=(0.0, 0.0, 0.0)):
    """Editable_Poly node from {'verts' (m), 'faces' (n-gons)}; positions in system units."""
    k = _sys_per_m(rt)
    node = rt.box(name=name, width=1, length=1, height=1)  # Editable_Poly is not creatable (Max 2024/2026)
    rt.convertToPoly(node)
    rt.polyop.deleteFaces(node, rt.execute('#{1..6}'), delIsoVerts=True)
    for v in data['verts']:
        rt.polyop.createVert(node, rt.Point3((v[0] + at[0]) * k, (v[1] + at[1]) * k, (v[2] + at[2]) * k))
    for f in data['faces']:
        rt.polyop.createPolygon(node, rt.Array(*[i + 1 for i in f]))
    return node


def make(obj, rt):
    ex = obj.get('extra') or {}
    kind = ex.get('kind')
    at = ex.get('at', (0.0, 0.0, 0.0))
    if kind == 'badik':
        W, L, H = ex['size']
        data = badik_mesh(W, L, H, ex['reveal'], ex['openings'])
    elif kind == 'parapet':
        data = parapet_mesh(ex['outline'], ex['level'], ex['height'], ex['thickness'], ex.get('slope_deg', 0.0),
                            ex.get('terrace', False), ex.get('heights'))
    else:
        raise RuntimeError('K_build: unknown kind {!r} for {}'.format(kind, obj['name']))
    node = mesh_node(rt, obj['name'], data, at)
    rt.setUserProp(node, 'agr_role', 'body')
    return node
