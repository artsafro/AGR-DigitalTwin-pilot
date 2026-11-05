"""elv-tc-vpm pilot И-А: pure-Python geometry kernel (no bpy) used by build_pilot_ia.py.

MB      - welded mesh builder (vertex dict on 1e-6 m), faces carry material ID, part and kind ('quad' or 'ngon').
Poly    - plan polyline with arc-length parameter u, segment normals on the right of the walking direction
          (= outward when the outline is walked with the building on the left), mitred normals at vertices.
relief  - facade relief over a polyline: a (u, z) grid of cells, each cell at an offset h from the base line
          (frame / rib / glass / opaque / door plate / void); walls between cells of different h; boundary walls.
          Everything is quads and welded; glass goes to a second builder as flat quads.
Pattern: relief-over-baseline (same idea as jobs/KPP1/scripts/build_kpp1.py relief(), job-local).
"""
import math

E = 1e-7
LEVELS = ()  # extra wall split levels; neighbour levels are propagated along each wall line (see relief)


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell(pts):
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        p, q = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (p[1] - q[1]) * (p[2] + q[2])
        n[1] += (p[2] - q[2]) * (p[0] + q[0])
        n[2] += (p[0] - q[0]) * (p[1] + q[1])
    return tuple(n)


class MB:
    def __init__(self):
        self.verts, self.vidx, self.faces = [], {}, []

    def v(self, p):
        k = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
        i = self.vidx.get(k)
        if i is None:
            i = len(self.verts)
            self.verts.append(k)
            self.vidx[k] = i
        return i

    def face(self, pts, mat, part, normal=None, kind="quad"):
        idx = []
        for p in pts:
            i = self.v(p)
            if not idx or idx[-1] != i:
                idx.append(i)
        if len(idx) > 1 and idx[0] == idx[-1]:
            idx.pop()
        if len(set(idx)) < 3:
            return
        if normal is not None:
            n = newell([self.verts[i] for i in idx])
            if dot(n, normal) < 0:
                idx.reverse()
        self.faces.append((idx, mat, part, kind))

    def strip(self, a, b, mat, part, normal, kind="quad"):
        """ladder of quads between two equally long point lists"""
        for i in range(len(a) - 1):
            self.face([a[i], a[i + 1], b[i + 1], b[i]], mat, part, normal, kind)


class Poly:
    def __init__(self, pts):
        self.p = [tuple(map(float, q)) for q in pts]
        self.cum = [0.0]
        self.t, self.n = [], []
        for a, b in zip(self.p, self.p[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            self.cum.append(self.cum[-1] + L)
            self.t.append((dx / L, dy / L))
            self.n.append((dy / L, -dx / L))
        self.length = self.cum[-1]

    def seg(self, u):
        for i in range(len(self.t)):
            if u <= self.cum[i + 1] + E:
                return i
        return len(self.t) - 1

    def vert(self, u):
        for i, c in enumerate(self.cum):
            if abs(c - u) < E:
                return i
        return None

    def base(self, u):
        i = self.seg(u)
        f = u - self.cum[i]
        a = self.p[i]
        return (a[0] + self.t[i][0] * f, a[1] + self.t[i][1] * f)

    def normal(self, u):
        """mitred at interior vertices (m . n_adjacent = 1), segment normal elsewhere"""
        k = self.vert(u)
        if k is not None and 0 < k < len(self.p) - 1:
            a, b = self.n[k - 1], self.n[k]
            d = 1.0 + a[0] * b[0] + a[1] * b[1]
            return ((a[0] + b[0]) / d, (a[1] + b[1]) / d)
        return self.n[self.seg(u)]

    def unit_normal(self, u):
        m = self.normal(u)
        L = math.hypot(*m)
        return (m[0] / L, m[1] / L)

    def tangent(self, u):
        k = self.vert(u)
        if k is not None and 0 < k < len(self.p) - 1:
            a, b = self.t[k - 1], self.t[k]
            L = math.hypot(a[0] + b[0], a[1] + b[1])
            return ((a[0] + b[0]) / L, (a[1] + b[1]) / L)
        return self.t[self.seg(u)]

    def project(self, q):
        best = None
        for i, (a, b) in enumerate(zip(self.p, self.p[1:])):
            dx, dy = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dy * dy
            f = max(0.0, min(1.0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L2))
            px, py = a[0] + dx * f, a[1] + dy * f
            d = math.hypot(q[0] - px, q[1] - py)
            if best is None or d < best[0] - 1e-9:
                best = (d, self.cum[i] + f * math.sqrt(L2))
        return best[1]

    def offset_pts(self, us, h):
        out = []
        for u in us:
            b, m = self.base(u), self.normal(u)
            out.append((b[0] + h * m[0], b[1] + h * m[1]))
        return out


def arc(cx, cy, r, a0, a1, n=None, angles=None):
    """points of a polygonal arc (degrees), both ends included"""
    if angles is None:
        angles = [a0 + (a1 - a0) * k / n for k in range(n + 1)]
    return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in angles]


def splits(poly, u0, u1, maxlen=3.9):
    """vertex u's inside [u0,u1] plus uniform splits so that no piece is longer than maxlen"""
    us = [u0, u1] + [c for c in poly.cum if u0 + E < c < u1 - E]
    us = sorted(set(us))
    out = []
    for a, b in zip(us, us[1:]):
        k = max(1, math.ceil((b - a) / maxlen - 1e-9))
        out += [a + (b - a) * i / k for i in range(k)]
    return out + [us[-1]]


class Cell:
    __slots__ = ("h", "face", "wall", "part", "glass", "rib")

    def __init__(self, h, face, wall, part, glass=False, rib=None):
        self.h, self.face, self.wall, self.part, self.glass, self.rib = h, face, wall, part, glass, rib


def relief(mb, gb, poly, u0, u1, zlines, regions, default, ulines=(), omit=(), glass_part="P20_MainGlass",
           glass_ext=0.01, rib_dirs=()):
    """regions: list of (u0, u1, z0, z1, Cell); later regions win. default: Cell for the rest of [u0,u1]x[zmin,zmax].
    rib_dirs: list of (ua, ub, (dx, dy)) - points with h > 0.02 inside [ua, ub] are offset along that direction.
    omit: boundary sides without walls: 'left' (u0), 'right' (u1), 'bottom', 'top'. Returns grid lines (U, Z)."""
    U = {u0, u1}
    U |= {c for c in poly.cum if u0 + E < c < u1 - E}
    U |= {u for u in ulines if u0 + E < u < u1 - E}
    Z = set(zlines)
    for (a, b, c, d, _) in regions:
        U |= {x for x in (a, b) if u0 - E < x < u1 + E}
        Z |= {c, d}
    U = sorted(U)
    Uc = [U[0]]
    for u in U[1:]:
        if u - Uc[-1] > 1e-6:
            Uc.append(u)
    U = Uc
    Z = sorted(Z)
    zmin, zmax = min(zlines), max(zlines)
    Z = [z for z in Z if zmin - E <= z <= zmax + E]
    nu, nz = len(U) - 1, len(Z) - 1
    grid = [[default] * nz for _ in range(nu)]
    for (a, b, c, d, cell) in regions:
        for i in range(nu):
            um = 0.5 * (U[i] + U[i + 1])
            if not (a - E < um < b + E):
                continue
            for j in range(nz):
                zm = 0.5 * (Z[j] + Z[j + 1])
                if c - E < zm < d + E:
                    grid[i][j] = cell

    def ribdir(u):
        for (a, b, d) in rib_dirs:
            if a - 1e-6 <= u <= b + 1e-6:
                return d
        return None

    def P(u, h, z):
        b = poly.base(u)
        rd = ribdir(u)
        if rd is not None and h > 0.02 + E:
            n = poly.normal(u)
            return (b[0] + 0.02 * n[0] + (h - 0.02) * rd[0], b[1] + 0.02 * n[1] + (h - 0.02) * rd[1], z)
        n = poly.normal(u)
        return (b[0] + h * n[0], b[1] + h * n[1], z)

    def pieces(lo, hi):
        cuts = [lo] + [l for l in LEVELS if lo + E < l < hi - E] + [hi]
        return list(zip(cuts, cuts[1:]))

    def wall_mat(low, high, a, b):
        # above the base plane a wall belongs to the protruding cell (cap side, rib, plinth step, sign frame),
        # below it to the recessed cell (reveal of a door / glass cell / opening)
        if a >= -E:
            return high.wall, high.part
        return low.wall, low.part

    # faces
    for i in range(nu):
        ua, ub = U[i], U[i + 1]
        n2 = poly.n[poly.seg(0.5 * (ua + ub))]
        rd = ribdir(0.5 * (ua + ub))
        for j in range(nz):
            c = grid[i][j]
            za, zb = Z[j], Z[j + 1]
            if c.face is not None:
                nrm = (rd[0], rd[1], 0.0) if (rd and c.h > 0.02) else (n2[0], n2[1], 0.0)
                mb.face([P(ua, c.h, za), P(ub, c.h, za), P(ub, c.h, zb), P(ua, c.h, zb)], c.face, c.part, nrm)
    # glass: one flat quad per glass region (not per grid cell: neighbouring pieces would overlap by 2 x ext)
    if gb is not None:
        for (a, b, c0, d0, cell) in regions:
            if not cell.glass:
                continue
            hit = [(i, j) for i in range(nu) for j in range(nz) if grid[i][j] is cell]
            if not hit:
                continue
            ua, ub = U[min(i for i, _ in hit)], U[max(i for i, _ in hit) + 1]
            za, zb = Z[min(j for _, j in hit)], Z[max(j for _, j in hit) + 1]
            n2 = poly.n[poly.seg(0.5 * (ua + ub))]
            ga, gbb = ua - glass_ext, ub + glass_ext
            gb.face([P(ga, cell.h, za - glass_ext), P(gbb, cell.h, za - glass_ext), P(gbb, cell.h, zb + glass_ext),
                     P(ga, cell.h, zb + glass_ext)], 1, glass_part, (n2[0], n2[1], 0.0))
    # walls: collected per line first, then every piece is cut at the levels of its neighbours on the same line,
    # so coplanar wall pieces that share an edge share all its vertices (xView contact rule flags T-vertices)
    W = {}  # line key -> {index: (lo, hi, quad(a, b), nrm, low, high)}

    def add(key, k, lo, hi, quad, nrm, low, high):
        W.setdefault(key, {})[k] = (lo, hi, quad, nrm, low, high)

    for i in range(nu - 1):
        u = U[i + 1]
        t = poly.tangent(u)
        for j in range(nz):
            A, B = grid[i][j], grid[i + 1][j]
            if abs(A.h - B.h) < E:
                continue
            low, high = (A, B) if A.h < B.h else (B, A)
            sgn = 1.0 if A.h > B.h else -1.0  # faces toward the lower cell
            add(("u", i + 1), j, low.h, high.h,
                lambda a, b, u=u, j=j: [P(u, a, Z[j]), P(u, b, Z[j]), P(u, b, Z[j + 1]), P(u, a, Z[j + 1])],
                (sgn * t[0], sgn * t[1], 0.0), low, high)
    for i in range(nu):
        ua, ub = U[i], U[i + 1]
        for j in range(nz - 1):
            A, B = grid[i][j], grid[i][j + 1]
            if abs(A.h - B.h) < E:
                continue
            low, high = (A, B) if A.h < B.h else (B, A)
            z = Z[j + 1]
            add(("z", j + 1), i, low.h, high.h,
                lambda a, b, ua=ua, ub=ub, z=z: [P(ua, a, z), P(ub, a, z), P(ub, b, z), P(ua, b, z)],
                (0.0, 0.0, 1.0 if A.h > B.h else -1.0), low, high)
    zero = Cell(0.0, None, None, None)
    if "left" not in omit:
        t = poly.tangent(U[0])
        for j in range(nz):
            if grid[0][j].h > E:
                add(("L",), j, 0.0, grid[0][j].h, lambda a, b, j=j: [P(U[0], a, Z[j]), P(U[0], b, Z[j]),
                    P(U[0], b, Z[j + 1]), P(U[0], a, Z[j + 1])], (-t[0], -t[1], 0.0), zero, grid[0][j])
    if "right" not in omit:
        t = poly.tangent(U[-1])
        for j in range(nz):
            if grid[-1][j].h > E:
                add(("R",), j, 0.0, grid[-1][j].h, lambda a, b, j=j: [P(U[-1], a, Z[j]), P(U[-1], b, Z[j]),
                    P(U[-1], b, Z[j + 1]), P(U[-1], a, Z[j + 1])], (t[0], t[1], 0.0), zero, grid[-1][j])
    for side, j, z, nz_ in (("bottom", 0, Z[0], -1.0), ("top", nz - 1, Z[-1], 1.0)):
        if side in omit:
            continue
        for i in range(nu):
            if grid[i][j].h > E:
                add((side,), i, 0.0, grid[i][j].h, lambda a, b, i=i, z=z: [P(U[i], a, z), P(U[i + 1], a, z),
                    P(U[i + 1], b, z), P(U[i], b, z)], (0.0, 0.0, nz_), zero, grid[i][j])
    for key, line in W.items():
        cut = {k: {w[0], w[1]} | {l for l in LEVELS if w[0] < l < w[1]} for k, w in line.items()}
        changed = True
        while changed:  # propagate levels along the line until neighbours agree on their shared edges
            changed = False
            for k, w in line.items():
                for kk in (k - 1, k + 1):
                    if kk in cut:
                        add_ = {c for c in cut[kk] if w[0] + E < c < w[1] - E} - cut[k]
                        if add_:
                            cut[k] |= add_
                            changed = True
        for k, (lo, hi, quad, nrm, low, high) in line.items():
            cuts = sorted(cut[k])
            for a, b in zip(cuts, cuts[1:]):
                if b - a < 1e-6:
                    continue
                m, prt = wall_mat(low, high, a, b)
                mb.face(quad(a, b), m, prt, nrm)
    return U, Z, P


def box(mb, x0, x1, y0, y1, z0, z1, mat, part, skip=(), maxlen=3.9):
    """axis-aligned box of quads; skip any of 'x0','x1','y0','y1','z0','z1'; long sides split <= maxlen"""
    def lin(a, b):
        k = max(1, math.ceil((b - a) / maxlen - 1e-9))
        return [a + (b - a) * i / k for i in range(k + 1)]
    X, Y, Zs = lin(x0, x1), lin(y0, y1), lin(z0, z1)

    def grid(A, B, f, nrm):
        for a0, a1 in zip(A, A[1:]):
            for b0, b1 in zip(B, B[1:]):
                mb.face([f(a0, b0), f(a1, b0), f(a1, b1), f(a0, b1)], mat, part, nrm)
    if "z0" not in skip:
        grid(X, Y, lambda a, b: (a, b, z0), (0, 0, -1))
    if "z1" not in skip:
        grid(X, Y, lambda a, b: (a, b, z1), (0, 0, 1))
    if "y0" not in skip:
        grid(X, Zs, lambda a, b: (a, y0, b), (0, -1, 0))
    if "y1" not in skip:
        grid(X, Zs, lambda a, b: (a, y1, b), (0, 1, 0))
    if "x0" not in skip:
        grid(Y, Zs, lambda a, b: (x0, a, b), (-1, 0, 0))
    if "x1" not in skip:
        grid(Y, Zs, lambda a, b: (x1, a, b), (1, 0, 0))


def heal_t(mb, tol=1e-5, cell=0.5):
    """insert every vertex that lies inside an edge of a face into that face's loop (T-junction -> n-gon).
    Separately gridded panels meet with different vertex rows; after this pass they share all vertices on the
    common line (no T-vertices: no xView contact on coplanar neighbours, no bow-tie fans). Returns faces changed."""
    grid = {}
    for i, v in enumerate(mb.verts):
        grid.setdefault((int(math.floor(v[0] / cell)), int(math.floor(v[1] / cell)), int(math.floor(v[2] / cell))),
                        []).append(i)
    changed = 0
    for fi, (idx, mat, part, kind) in enumerate(mb.faces):
        new = []
        hit = False
        for k in range(len(idx)):
            a, b = idx[k], idx[(k + 1) % len(idx)]
            A, B = mb.verts[a], mb.verts[b]
            new.append(a)
            d = sub(B, A)
            L2 = dot(d, d)
            if L2 < 1e-12:
                continue
            lo = [int(math.floor((min(A[i], B[i]) - tol) / cell)) for i in range(3)]
            hi = [int(math.floor((max(A[i], B[i]) + tol) / cell)) for i in range(3)]
            ins = []
            for gx in range(lo[0], hi[0] + 1):
                for gy in range(lo[1], hi[1] + 1):
                    for gz in range(lo[2], hi[2] + 1):
                        for c in grid.get((gx, gy, gz), ()):
                            if c == a or c == b or c in idx:
                                continue
                            q = mb.verts[c]
                            t = dot(sub(q, A), d) / L2
                            if t <= 1e-9 or t >= 1 - 1e-9:
                                continue
                            pr = (A[0] + d[0] * t - q[0], A[1] + d[1] * t - q[1], A[2] + d[2] * t - q[2])
                            if dot(pr, pr) <= tol * tol:
                                ins.append((t, c))
            if ins:
                hit = True
                new += [c for _, c in sorted(set(ins))]
        if hit:
            mb.faces[fi] = (new, mat, part, kind)
            changed += 1
    return changed
