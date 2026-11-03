"""Parametric MAF generator, first family: slab bench on square-tube posts along a plan run (#790).

Pattern: new-case: model-maf step 3 tool - spec row + plan run + section parameters -> one welded mid-poly
quad mesh («lego» [D165]: posts are let into the seat as inserts, one closed manifold, no fasteners).
Pure Python (no bpy), so tests run without Blender; tools/blender/maf_gen_bench_build.py writes the FBX.

Geometry: the plan run is a centreline polyline in metres (straight, L or U); the seat is a strip of
`depth` mitred at every corner, `seat_thickness` thick, top at `seat_top`. Leg rows stand across the
strip at <= `max_leg_span` spacing, `end_overhang` from a free end and `depth/2 + post` from a corner; each
row has two square posts `post` wide, `post_inset` from the strip sides. Every face is a quad; the seat
top/bottom/walls share one (s, t) grid per segment so no T-junction appears where a post is let in.
Pivot (exported): horizontal bbox centre at XY 0, lowest point at Z 0; the longest segment lies on +X and
`plan_rotation_deg` records the plan rotation applied (placement restores it, model-maf step 8).
Every invalid input raises ValueError naming the problem; nothing is defaulted silently.
"""

from __future__ import annotations

import math

REQUIRED = ("path", "depth", "seat_top", "seat_thickness", "post", "post_inset", "end_overhang",
            "max_leg_span", "materials")
OPTIONAL = ("synthetic", "name", "source", "notes", "align")
MATERIAL_ROLES = ("seat", "frame")
MAX_TURN_DEG = 135.0
CLOSE_GAP_M = 0.01  # a drawn outline whose end misses its start by <= 1 cm counts as closed (DWG row 5: 6.5 mm)


def _finite_pos(spec, key):
    v = spec[key]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError(f"{key} must be a finite number > 0, got {v!r}")
    return float(v)


def _points(raw, what="path"):
    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"{what} must be a list of [x, y] points")
    pts = []
    for p in raw:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError(f"{what}: point {p!r} is not [x, y]")
        x, y = p
        if any(isinstance(c, bool) or not isinstance(c, (int, float)) or not math.isfinite(c) for c in (x, y)):
            raise ValueError(f"{what}: point {p!r} is not finite")
        pts.append((float(x), float(y)))
    return pts


def _validate(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    unknown = sorted(set(spec) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ValueError(f"unknown spec keys: {unknown}")
    missing = [k for k in REQUIRED if k not in spec]
    if missing:
        raise ValueError(f"missing spec keys: {missing}")
    p: dict = {k: _finite_pos(spec, k) for k in ("depth", "seat_top", "seat_thickness", "post", "end_overhang",
                                            "max_leg_span")}
    inset = spec["post_inset"]
    if isinstance(inset, bool) or not isinstance(inset, (int, float)) or not math.isfinite(inset) or inset <= 0:
        raise ValueError(f"post_inset must be a finite number > 0, got {inset!r}")
    p["post_inset"] = float(inset)
    if p["seat_thickness"] >= p["seat_top"]:
        raise ValueError("seat_thickness must be below seat_top (posts need a height)")
    if p["post_inset"] + p["post"] >= p["depth"] / 2:
        raise ValueError("post_inset + post must stay inside half the seat depth (two posts per row)")
    if p["max_leg_span"] <= p["post"]:
        raise ValueError("max_leg_span must exceed the post size")
    mats = spec["materials"]
    if not isinstance(mats, dict) or set(mats) != set(MATERIAL_ROLES):
        raise ValueError(f"materials must map exactly {list(MATERIAL_ROLES)}, got {mats!r}")
    for role, mid in mats.items():
        if isinstance(mid, bool) or not isinstance(mid, int) or mid < 1:
            raise ValueError(f"material id for {role!r} must be a positive int, got {mid!r}")
    p["materials"] = dict(mats)
    pts = _points(spec["path"])
    if len(pts) < 2:
        raise ValueError("path needs at least two points")
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 1e-3:
            raise ValueError(f"path has a zero-length segment at {a}")
    p["path"] = pts
    p["align"] = bool(spec.get("align", True))
    return p


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _unit(v):
    n = math.hypot(*v)
    return (v[0] / n, v[1] / n)


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def _seg_dist(p1, p2, q1, q2):
    def pd(p, a, b):
        ab = _sub(b, a)
        t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / (ab[0] ** 2 + ab[1] ** 2)))
        return math.dist(p, (a[0] + t * ab[0], a[1] + t * ab[1]))

    d1, d2 = _sub(p2, p1), _sub(q2, q1)
    den = _cross(d1, d2)
    if abs(den) > 1e-12:
        w = _sub(q1, p1)
        t, u = _cross(w, d2) / den, _cross(w, d1) / den
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0
    return min(pd(p1, q1, q2), pd(p2, q1, q2), pd(q1, p1, p2), pd(q2, p1, p2))


def _offsets(pts, h):
    """Left (+normal) and right offset polylines, mitred at interior vertices."""
    dirs = [_unit(_sub(b, a)) for a, b in zip(pts, pts[1:])]
    norms = [(-d[1], d[0]) for d in dirs]
    left, right = [], []
    for i, p in enumerate(pts):
        if i == 0:
            n, k = norms[0], 1.0
        elif i == len(pts) - 1:
            n, k = norms[-1], 1.0
        else:
            n1, n2 = norms[i - 1], norms[i]
            turn = math.degrees(math.acos(max(-1.0, min(1.0, dirs[i - 1][0] * dirs[i][0] + dirs[i - 1][1] * dirs[i][1]))))
            if turn > MAX_TURN_DEG:
                raise ValueError(f"turn of {turn:.1f} deg at path point {i} exceeds the mitre limit {MAX_TURN_DEG}")
            n = _unit((n1[0] + n2[0], n1[1] + n2[1]))
            k = 1.0 / (n[0] * n1[0] + n[1] * n1[1])
        left.append((p[0] + n[0] * h * k, p[1] + n[1] * h * k))
        right.append((p[0] - n[0] * h * k, p[1] - n[1] * h * k))
    for i, d in enumerate(dirs):
        for side in (left, right):
            e = _sub(side[i + 1], side[i])
            if e[0] * d[0] + e[1] * d[1] <= 1e-6:
                raise ValueError(f"segment {i} is shorter than its mitres: the strip folds")
    return left, right, dirs


def _rotate(pts, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [(x * c - y * s, x * s + y * c) for x, y in pts]


def build_bench(spec):
    """Spec dict -> {"verts": [[x,y,z]], "faces": [[i,j,k,l]], "face_mat": [id], "plan_rotation_deg": float}."""
    p = _validate(spec)
    pts = p["path"]
    rot = 0.0
    if p["align"]:
        lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
        i = lens.index(max(lens))
        rot = -math.degrees(math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0]))
        pts = _rotate(pts, rot)
    depth, h = p["depth"], p["depth"] / 2
    for i in range(len(pts) - 1):
        for j in range(i + 2, len(pts) - 1):
            if _seg_dist(pts[i], pts[i + 1], pts[j], pts[j + 1]) < depth:
                raise ValueError(f"segments {i} and {j} come closer than the seat depth: strips overlap")
    left, right, _dirs = _offsets(pts, h)
    zt, zb = p["seat_top"], p["seat_top"] - p["seat_thickness"]
    post = p["post"]
    ta0, ta1 = p["post_inset"] / depth, (p["post_inset"] + post) / depth
    T = [0.0, ta0, ta1, 1.0 - ta1, 1.0 - ta0, 1.0]
    post_t = {1, 3}  # t-interval indices holding a post
    nseg = len(pts) - 1

    seg_s, seg_post_s = [], []
    for k in range(nseg):
        L = math.dist(pts[k], pts[k + 1])
        e0 = p["end_overhang"] if k == 0 else h + post
        e1 = p["end_overhang"] if k == nseg - 1 else h + post
        span = L - e0 - e1
        if span < 2 * post:
            raise ValueError(f"segment {k} ({L:.3f} m) is too short for two leg rows")
        n = math.ceil(span / p["max_leg_span"]) + 1
        centres = [e0 + span * r / (n - 1) for r in range(n)]
        cuts = [0.0, 1.0]
        posts = set()
        for c in centres:
            a, b = (c - post / 2) / L, (c + post / 2) / L
            cuts += [a, b]
        cuts = sorted(set(cuts))
        for c in centres:
            a = (c - post / 2) / L
            posts.add(cuts.index(a))
        seg_s.append(cuts)
        seg_post_s.append(posts)

    verts, index = [], {}

    def vid(xy, z):
        key = (round(xy[0], 9), round(xy[1], 9), round(z, 9))
        if key not in index:
            index[key] = len(verts)
            verts.append([xy[0], xy[1], z])
        return index[key]

    def P(k, s, t):
        a = left[k] if s == 0 else left[k + 1] if s == 1 else (
            left[k][0] * (1 - s) + left[k + 1][0] * s, left[k][1] * (1 - s) + left[k + 1][1] * s)
        b = right[k] if s == 0 else right[k + 1] if s == 1 else (
            right[k][0] * (1 - s) + right[k + 1][0] * s, right[k][1] * (1 - s) + right[k + 1][1] * s)
        if t == 0:
            return a
        if t == 1:
            return b
        return (a[0] * (1 - t) + b[0] * t, a[1] * (1 - t) + b[1] * t)

    faces, fmat = [], []

    def add(corners, ref, mat):
        ids = [vid(xy, z) for xy, z in corners]
        q = [verts[i] for i in ids]
        n = [0.0, 0.0, 0.0]
        for a, b in zip(q, q[1:] + q[:1]):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        if n[0] * ref[0] + n[1] * ref[1] + n[2] * ref[2] < 0:
            ids.reverse()
        faces.append(ids)
        fmat.append(mat)

    seat, frame = p["materials"]["seat"], p["materials"]["frame"]
    for k in range(nseg):
        S = seg_s[k]
        for j in range(len(S) - 1):
            s0, s1 = S[j], S[j + 1]
            for m in range(len(T) - 1):
                t0, t1 = T[m], T[m + 1]
                cell = [P(k, s0, t0), P(k, s1, t0), P(k, s1, t1), P(k, s0, t1)]
                add([(c, zt) for c in cell], (0, 0, 1), seat)
                if not (j in seg_post_s[k] and m in post_t):
                    add([(c, zb) for c in cell], (0, 0, -1), seat)
            for t, ref_t in ((0.0, 0.5), (1.0, 0.5)):
                a, b = P(k, s0, t), P(k, s1, t)
                mid, inner = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), P(k, (s0 + s1) / 2, ref_t)
                add([(a, zb), (b, zb), (b, zt), (a, zt)], (mid[0] - inner[0], mid[1] - inner[1], 0), seat)
        for j in seg_post_s[k]:
            s0, s1 = S[j], S[j + 1]
            for m in post_t:
                t0, t1 = T[m], T[m + 1]
                ring = [P(k, s0, t0), P(k, s1, t0), P(k, s1, t1), P(k, s0, t1)]
                cx, cy = sum(c[0] for c in ring) / 4, sum(c[1] for c in ring) / 4
                for a, b in zip(ring, ring[1:] + ring[:1]):
                    add([(a, zb), (b, zb), (b, 0.0), (a, 0.0)], ((a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy, 0),
                        frame)
                add([(c, 0.0) for c in ring], (0, 0, -1), frame)
    for k, s, inward in ((0, 0.0, 1e-3), (nseg - 1, 1.0, 1 - 1e-3)):
        for m in range(len(T) - 1):
            a, b = P(k, s, T[m]), P(k, s, T[m + 1])
            mid, inner = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), P(k, inward, (T[m] + T[m + 1]) / 2)
            add([(a, zb), (b, zb), (b, zt), (a, zt)], (mid[0] - inner[0], mid[1] - inner[1], 0), seat)

    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for v in verts:
        v[0] -= cx
        v[1] -= cy
    return {"verts": verts, "faces": faces, "face_mat": fmat, "plan_rotation_deg": rot}


CLAD_REQUIRED = ("path", "depth", "height", "foot_height", "courses", "seam_width", "seam_depth", "frame_width",
                 "top_boards", "foot_length", "foot_inset", "end_overhang", "max_foot_span", "materials")
SEAM_MODES = ("geometry", "texture")


def _validate_clad(spec):
    if not isinstance(spec, dict):
        raise ValueError("spec must be a dict")
    unknown = sorted(set(spec) - set(CLAD_REQUIRED) - set(OPTIONAL) - {"seams"})
    if unknown:
        raise ValueError(f"unknown spec keys: {unknown}")
    missing = [k for k in CLAD_REQUIRED if k not in spec]
    if missing:
        raise ValueError(f"missing spec keys: {missing}")
    p: dict = {k: _finite_pos(spec, k) for k in CLAD_REQUIRED if k not in ("path", "courses", "top_boards",
                                                                          "materials")}
    for k in ("courses", "top_boards"):
        v = spec[k]
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError(f"{k} must be an int >= 1, got {v!r}")
        p[k] = v
    h, g, sd, f = p["depth"] / 2, p["seam_width"], p["seam_depth"], p["frame_width"]
    p["course_h"] = (p["height"] - p["foot_height"] - (p["courses"] - 1) * g) / p["courses"]
    p["board_w"] = (p["depth"] - 2 * f - (p["top_boards"] + 1) * g) / p["top_boards"]
    if p["course_h"] <= sd:
        raise ValueError(f"course height {p['course_h']:.4f} m must exceed seam_depth {sd}")
    if p["board_w"] <= g:
        raise ValueError(f"{p['top_boards']} top boards do not fit in depth {p['depth']} (board width {p['board_w']:.4f})")
    if sd >= f:
        raise ValueError("seam_depth must stay below frame_width (the side frame carries the ring seam)")
    if p["foot_inset"] >= h:
        raise ValueError("foot_inset must stay inside half the depth")
    if p["foot_length"] >= p["max_foot_span"]:
        raise ValueError("foot_length must be below max_foot_span")
    if p["end_overhang"] - p["foot_length"] / 2 <= p["foot_inset"]:
        raise ValueError("end_overhang must keep the end foot clear of the bottom end band (foot_inset)")
    mats = spec["materials"]
    if not isinstance(mats, dict) or set(mats) != set(MATERIAL_ROLES):
        raise ValueError(f"materials must map exactly {list(MATERIAL_ROLES)}, got {mats!r}")
    for role, mid in mats.items():
        if isinstance(mid, bool) or not isinstance(mid, int) or mid < 1:
            raise ValueError(f"material id for {role!r} must be a positive int, got {mid!r}")
    p["materials"] = dict(mats)
    pts = _points(spec["path"])
    if len(pts) < 2:
        raise ValueError("path needs at least two points")
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 1e-3:
            raise ValueError(f"path has a zero-length segment at {a}")
    p["path"] = pts
    p["align"] = bool(spec.get("align", True))
    p["seams"] = spec.get("seams", "geometry")
    if p["seams"] not in SEAM_MODES:
        raise ValueError(f"seams must be one of {SEAM_MODES}, got {p['seams']!r}")
    return p


def _align(pts, align):
    if not align:
        return pts, 0.0
    lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    i = lens.index(max(lens))
    rot = -math.degrees(math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0]))
    return _rotate(pts, rot), rot


def _check_strips_apart(pts, depth):
    for i in range(len(pts) - 1):
        for j in range(i + 2, len(pts) - 1):
            if _seg_dist(pts[i], pts[i + 1], pts[j], pts[j + 1]) < depth:
                raise ValueError(f"segments {i} and {j} come closer than the seat depth: strips overlap")


def build_clad_box(spec):
    """Closed timber box bench («Верона» form) along a plan run -> one welded quad mesh with modelled seams.

    Body from `foot_height` to `height`: `courses` horizontal boards on every side, separated by ring seams
    (`seam_width` high, `seam_depth` deep) that wrap the whole outline; the top is a frame `frame_width` wide around
    `top_boards` lengthwise boards with seams between them (and against the frame) that stop at the end frames and
    turn mitred through the corners. Steel foot plates (`foot_length` along the run, depth − 2·`foot_inset` across,
    `foot_height` high) are let into the bottom at the free ends (`end_overhang` to the plate centre), at
    <= `max_foot_span` spacing and `depth/2 + foot_length` from every corner. Planar bands whose two edges carry a
    different vertex count are filled by a 3-to-1 quad reduction with interior points only, so no T-junction.

    `seams="texture"` (Artem 2026-11-03 correction): no board gaps in the geometry; the top is one quad per segment
    and the sides one ring from `foot_height` to `height`. The board layout lives in the UV instead: `face_uv`
    (per face, per vertex (s, t) in 0..1 of a board pattern of `top_boards + 2` equal boards along t, or None for
    faces that show no boards) puts the top across the whole pattern (t = lateral / depth, mitred so the boards turn
    the corners) and the sides over `courses` boards of the same pattern, so every seam line of the texture falls on
    a board joint. `uv_pattern` names the pattern the texture cell must carry.
    """
    p = _validate_clad(spec)
    pts, rot = _align(p["path"], p["align"])
    depth, h = p["depth"], p["depth"] / 2
    _check_strips_apart(pts, depth)
    _offsets(pts, h)  # raises on a fold or a too-sharp turn
    nseg = len(pts) - 1
    dirs = [_unit(_sub(b, a)) for a, b in zip(pts, pts[1:])]
    norms = [(-d[1], d[0]) for d in dirs]
    lens = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    mit = []  # per vertex: mitred unit normal scaled so that u is the lateral distance on both legs
    for i in range(len(pts)):
        if i == 0 or i == nseg:
            n = norms[0] if i == 0 else norms[-1]
            mit.append(n)
        else:
            n = _unit((norms[i - 1][0] + norms[i][0], norms[i - 1][1] + norms[i][1]))
            k = 1.0 / (n[0] * norms[i][0] + n[1] * norms[i][1])
            mit.append((n[0] * k, n[1] * k))

    def Q(k, d, u):
        return (pts[k][0] + dirs[k][0] * d + norms[k][0] * u, pts[k][1] + dirs[k][1] * d + norms[k][1] * u)

    def start(k, u, inset):
        return Q(0, inset, u) if k == 0 else (pts[k][0] + mit[k][0] * u, pts[k][1] + mit[k][1] * u)

    def end(k, u, inset):
        return Q(k, lens[k] - inset, u) if k == nseg - 1 else (pts[k + 1][0] + mit[k + 1][0] * u,
                                                              pts[k + 1][1] + mit[k + 1][1] * u)

    def along(k, xy):
        return (xy[0] - pts[k][0]) * dirs[k][0] + (xy[1] - pts[k][1]) * dirs[k][1]

    tex = p["seams"] == "texture"
    nb = p["top_boards"] + 2
    verts, index, faces, fmat, fuv = [], {}, [], [], []

    def vid(xy, z):
        key = (round(xy[0], 9), round(xy[1], 9), round(z, 9))
        if key not in index:
            index[key] = len(verts)
            verts.append([xy[0], xy[1], z])
        return index[key]

    def add(corners, ref, mat, uvf=None):
        ids = [vid(xy, z) for xy, z in corners]
        q = [verts[i] for i in ids]
        n = [0.0, 0.0, 0.0]
        for a, b in zip(q, q[1:] + q[:1]):
            n[0] += (a[1] - b[1]) * (a[2] + b[2])
            n[1] += (a[2] - b[2]) * (a[0] + b[0])
            n[2] += (a[0] - b[0]) * (a[1] + b[1])
        if n[0] * ref[0] + n[1] * ref[1] + n[2] * ref[2] < 0:
            ids.reverse()
        faces.append(ids)
        fmat.append(mat)
        fuv.append([uvf(verts[i]) for i in ids] if uvf else None)

    def band(inner, o0, o1, z, ref, mat):
        """Fill the planar band between the collinear chain `inner` (any odd segment count) and the edge o0-o1."""
        m = len(inner) - 1
        if m % 2 == 0:
            raise ValueError("internal: band chain needs an odd segment count")
        a, b = inner[0], inner[-1]
        tot = math.dist(a, b)

        def pos(sr):
            s, r = sr
            lo = (a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s)
            hi = (o0[0] + (o1[0] - o0[0]) * s, o0[1] + (o1[1] - o0[1]) * s)
            return (lo[0] + (hi[0] - lo[0]) * r, lo[1] + (hi[1] - lo[1]) * r)

        exact = {(0.0, 1.0): o0, (1.0, 1.0): o1}
        chain = [(0.0, 1.0)] + [(math.dist(a, q) / tot, 0.0) for q in inner] + [(1.0, 1.0)]
        chain[1], chain[-2] = (0.0, 0.0), (1.0, 0.0)
        for (s, _r), q in zip(chain[1:-1], inner):
            exact[(s, 0.0)] = q

        def P(sr):
            return (exact.get(sr) or pos(sr), z)

        def quad(*sr):
            add([P(x) for x in sr], ref, mat)

        rho = 0.0
        while len(chain) - 1 > 3:
            M = len(chain) - 1
            r_new, r_mid = (rho + 1) / 2, (3 * rho + 1) / 4
            new = [chain[0], (chain[2][0], r_new)]
            quad(chain[0], chain[1], chain[2], new[1])
            j, triples = 2, (M - 4) // 3
            while j < M - 2:
                if triples and j + 3 <= M - 2:
                    x0, x1, x2, x3 = chain[j:j + 4]
                    A, B, y1 = (x1[0], r_mid), (x2[0], r_mid), (x3[0], r_new)
                    quad(x0, x1, A, new[-1])
                    quad(x1, x2, B, A)
                    quad(x2, x3, y1, B)
                    quad(A, B, y1, new[-1])
                    new.append(y1)
                    triples -= 1
                    j += 3
                else:
                    y1 = (chain[j + 1][0], r_new)
                    quad(chain[j], chain[j + 1], y1, new[-1])
                    new.append(y1)
                    j += 1
            quad(chain[M - 2], chain[M - 1], chain[M], new[-1])
            new.append(chain[M])
            chain, rho = new, r_new
        quad(*chain)

    wood, steel = p["materials"]["seat"], p["materials"]["frame"]
    zt, zf, g, sd, f = p["height"], p["foot_height"], p["seam_width"], p["seam_depth"], p["frame_width"]
    hf = h - f
    kl = nseg - 1
    if tex:
        span_k = [lens[k] + 2 * h for k in range(nseg)]

        def top_uv(k):
            def uvf(v):
                xy = (v[0], v[1])
                lat = (xy[0] - pts[k][0]) * norms[k][0] + (xy[1] - pts[k][1]) * norms[k][1]
                return ((along(k, xy) + h) / span_k[k], min(1.0, max(0.0, (lat + h) / depth)))
            return uvf

        for k in range(nseg):
            add([(start(k, h, 0), zt), (end(k, h, 0), zt), (end(k, -h, 0), zt), (start(k, -h, 0), zt)], (0, 0, 1),
                wood, top_uv(k))
        prof = [(zf, 0.0), (zt, 0.0)]
    else:
        prof = None
    # --- top: frame bands, boards, seam pockets ---------------------------------------------------------------
    us = [hf]
    for _ in range(p["top_boards"] if not tex else 0):
        us += [us[-1] - g, us[-1] - g - p["board_w"]]
    if not tex:
        us += [-hf]
    for k in range(nseg if not tex else 0):
        for j in range(len(us) - 1):
            u0, u1 = us[j], us[j + 1]
            cell = [start(k, u0, f), end(k, u0, f), end(k, u1, f), start(k, u1, f)]
            if j % 2:
                add([(c, zt) for c in cell], (0, 0, 1), wood)
                continue
            zs = zt - sd
            add([(c, zs) for c in cell], (0, 0, 1), wood)
            for u, sgn in ((u0, -1), (u1, 1)):
                a, b = start(k, u, f), end(k, u, f)
                add([(a, zs), (b, zs), (b, zt), (a, zt)], (norms[k][0] * sgn, norms[k][1] * sgn, 0), wood)
            if k == 0:
                a, b = start(0, u0, f), start(0, u1, f)
                add([(a, zs), (b, zs), (b, zt), (a, zt)], (dirs[0][0], dirs[0][1], 0), wood)
            if k == nseg - 1:
                a, b = end(k, u0, f), end(k, u1, f)
                add([(a, zs), (b, zs), (b, zt), (a, zt)], (-dirs[k][0], -dirs[k][1], 0), wood)
        for side in (1, -1):
            add([(start(k, side * h, 0), zt), (end(k, side * h, 0), zt), (end(k, side * hf, f), zt),
                 (start(k, side * hf, f), zt)], (0, 0, 1), wood)
    if not tex:
        band([Q(0, f, u) for u in us], Q(0, 0, h), Q(0, 0, -h), zt, (0, 0, 1), wood)
        band([Q(kl, lens[kl] - f, u) for u in us], Q(kl, lens[kl], h), Q(kl, lens[kl], -h), zt, (0, 0, 1), wood)
    # --- sides: courses and ring seams around the whole outline -----------------------------------------------
    def loop(w):
        left = [start(k, h - w, w) for k in range(nseg)] + [end(kl, h - w, w)]
        right = [start(k, w - h, w) for k in range(nseg)] + [end(kl, w - h, w)]
        return left + right[::-1]

    ch = p["course_h"]
    if prof is None:
        prof = [(zf, 0.0)]
    for c in range(p["courses"] - 1 if not tex else 0):
        top = zf + (c + 1) * ch + c * g
        prof += [(top, 0.0), (top, sd), (top + g, sd), (top + g, 0.0)]
    if not tex:
        prof.append((zt, 0.0))
    loops = {w: loop(w) for w in (0.0, sd)}
    nl = len(loops[0.0])
    for (z0, w0), (z1, w1) in zip(prof, prof[1:]):
        l0, l1 = loops[w0], loops[w1]
        for i in range(nl):
            j = (i + 1) % nl
            d = _sub(loops[0.0][j], loops[0.0][i])
            out = _unit((-d[1], d[0]))
            ref = (out[0] * (z1 - z0), out[1] * (z1 - z0), w1 - w0)
            uvf = None
            if tex:
                a, el = loops[0.0][i], math.dist(loops[0.0][i], loops[0.0][j])

                def uvf(v, a=a, el=el):
                    return (math.dist(a, (v[0], v[1])) / el, (v[2] - zf) / (zt - zf) * p["courses"] / nb)
            add([(l0[i], z0), (l0[j], z0), (l1[j], z1), (l1[i], z1)], ref, wood, uvf)
    # --- bottom: steel plates let in, bands filled without touching the outline -------------------------------
    fl, fi = p["foot_length"], p["foot_inset"]
    ui = h - fi
    for k in range(nseg):
        e0 = p["end_overhang"] if k == 0 else h + fl
        e1 = p["end_overhang"] if k == nseg - 1 else h + fl
        span = lens[k] - e0 - e1
        if span < fl:
            raise ValueError(f"segment {k} ({lens[k]:.3f} m) is too short for two foot plates")
        n = math.ceil(span / p["max_foot_span"]) + 1
        cuts = []
        for r in range(n):
            c = e0 + span * r / (n - 1)
            cuts += [c - fl / 2, c + fl / 2]
        chains = {}
        for u in (ui, -ui):
            a, b = start(k, u, fi), end(k, u, fi)
            if not along(k, a) + 1e-6 < cuts[0] or not cuts[-1] < along(k, b) - 1e-6:
                raise ValueError(f"segment {k}: foot plates reach into the corner mitre")
            chains[u] = [a] + [Q(k, d, u) for d in cuts] + [b]
        L_, R_ = chains[ui], chains[-ui]
        for j in range(len(L_) - 1):
            cell = [L_[j], L_[j + 1], R_[j + 1], R_[j]]
            if j % 2 == 0:
                add([(c, zf) for c in cell], (0, 0, -1), wood)
                continue
            cx, cy = sum(c[0] for c in cell) / 4, sum(c[1] for c in cell) / 4
            for a, b in zip(cell, cell[1:] + cell[:1]):
                add([(a, zf), (b, zf), (b, 0.0), (a, 0.0)], ((a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy, 0), steel)
            add([(c, 0.0) for c in cell], (0, 0, -1), steel)
        band(L_, start(k, h, 0), end(k, h, 0), zf, (0, 0, -1), wood)
        band(R_, start(k, -h, 0), end(k, -h, 0), zf, (0, 0, -1), wood)
    band([start(0, ui, fi), start(0, -ui, fi)], Q(0, 0, h), Q(0, 0, -h), zf, (0, 0, -1), wood)
    band([end(kl, ui, fi), end(kl, -ui, fi)], Q(kl, lens[kl], h), Q(kl, lens[kl], -h), zf, (0, 0, -1), wood)

    xs, ys = [v[0] for v in verts], [v[1] for v in verts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    for v in verts:
        v[0] -= cx
        v[1] -= cy
    out = {"verts": verts, "faces": faces, "face_mat": fmat, "plan_rotation_deg": rot}
    if tex:
        out["face_uv"] = fuv
        out["uv_pattern"] = {"boards": nb, "axis": "t"}
    return out


def signed_volume(mesh):
    vol = 0.0
    V = mesh["verts"]
    for f in mesh["faces"]:
        a = V[f[0]]
        for b, c in zip((V[i] for i in f[1:-1]), (V[i] for i in f[2:])):
            vol += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                    + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
    return vol


def mesh_facts(mesh):
    V, F = mesh["verts"], mesh["faces"]
    use = {}
    for f in F:
        for a, b in zip(f, f[1:] + f[:1]):
            e = (min(a, b), max(a, b))
            use[e] = use.get(e, 0) + 1
    parent = list(range(len(V)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in use:
        parent[find(a)] = find(b)
    used = {i for f in F for i in f}
    mn = [min(V[i][c] for i in used) for c in range(3)]
    mx = [max(V[i][c] for i in used) for c in range(3)]
    return {"dims_m": [mx[c] - mn[c] for c in range(3)], "min_z": mn[2],
            "centre_xy": [(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2],
            "faces": len(F), "tris": sum(len(f) - 2 for f in F), "verts": len(used),
            "quad_only": all(len(f) == 4 for f in F), "manifold": bool(use) and set(use.values()) == {2},
            "components": len({find(i) for i in used}), "loose_verts": len(V) - len(used)}


def centreline_from_outline(points, depth, tol=0.05):
    """Closed strip outline (end cap, one long side, end cap, other side) -> centreline polyline.

    The two end caps are the only edges within `tol` of `depth`; anything else (no cap, three caps, sides of
    unequal vertex count, non-finite input) raises ValueError instead of guessing a shape.
    """
    pts = _points(points, "outline")
    clean = []
    for q in pts:
        if not clean or math.dist(clean[-1], q) > CLOSE_GAP_M:
            clean.append(q)
    if len(clean) > 1 and math.dist(clean[0], clean[-1]) <= CLOSE_GAP_M:
        clean.pop()
    n = len(clean)
    if n < 4:
        raise ValueError(f"outline needs at least 4 distinct points, got {n}")
    caps = [i for i in range(n) if abs(math.dist(clean[i], clean[(i + 1) % n]) - depth) <= tol]
    if len(caps) != 2 or (caps[1] - caps[0]) % n in (1, n - 1):
        raise ValueError(f"outline must have exactly two non-adjacent end caps of {depth} m, found edges {caps}")
    c1, c2 = caps
    a = [clean[i % n] for i in range(c1 + 1, c2 + 1)]
    b = [clean[i % n] for i in range(c2 + 1, c1 + n + 1)]
    if len(a) != len(b) or len(a) < 2:
        raise ValueError(f"outline sides have {len(a)} and {len(b)} points: not one strip")
    # The outer (longer) side carries the drawn leg lengths; drawn inner sides and caps are often skewed, so the
    # centreline is the outer side offset inward by depth/2 (mitred), not the vertex midpoints.
    length = lambda c: sum(math.dist(p, q) for p, q in zip(c, c[1:]))  # noqa: E731
    outer, inner = (a, b) if length(a) >= length(b) else (b, a)
    left, right, _dirs = _offsets(outer, depth / 2)
    cx, cy = sum(p[0] for p in inner) / len(inner), sum(p[1] for p in inner) / len(inner)
    dl = sum(math.dist(p, (cx, cy)) for p in left)
    dr = sum(math.dist(p, (cx, cy)) for p in right)
    return [[p[0], p[1]] for p in (left if dl < dr else right)]
