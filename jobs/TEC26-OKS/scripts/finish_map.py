"""new-case: TEC26 per-building finish assignment from a Max Multi/Sub dump (pure Python, no Blender).

Used by build_master.py (Blender) and by the tests. Contracts (fail-closed, never a default finish):
- validate_spec: every finish has a unique UDIM and an integer sRGB triple; every source ID maps to declared
  finishes; empty IDs are disjoint from mapped IDs; a finish that names a KPP twin must carry exactly the KPP RGB
  («синий, жёлтый, серый должны биться»). A full (patterned) finish must deliver its KPP twin's texel density
  (contract_density); a different density needs an approved `density_exception` citing the user decision.
- assign_finishes: one finish per polygon; a polygon whose material ID is unmapped, or declared empty, raises
  ValueError naming the ID; NaN/inf coordinates raise. Split rule `below_zero`: a polygon whose highest vertex is at
  or below `zero_m` (±0.000) takes `below`, every other polygon `above`.
- user-texture finishes (pattern `user_vjoints`, Artem 2026-10-22: vertical joints only, his 4096 texture, KPP texel):
  a full finish whose KPP colour twin is a plain placeholder carries `source_texture` (path, sha256, period_px,
  first_joint_px) and a `density_twin` (a patterned KPP finish) for the texel contract.
- joint frame (facade_joint_uv): vertical joints repeat every P from the panel's edge with the smaller world coordinate
  along its facade, so the two mirrored long facades share one joint grid and one ring cut lands on a joint on both.
- ring cuts (plan_cuts / ring_cut / apply_cuts; Artem 2026-10-22 «если не влезает, то можно аккуратно порезать через
  loop или ring»): a patterned face longer than the tile holds is split by an edge ring at a joint position; the ring
  runs through quads only, from boundary to boundary (or closed), so no T-junction is created; every new vertex lies
  on a source edge; silhouette, normals, UCX and IDs are unchanged. Fail-closed: a non-quad, a non-manifold edge, a
  non-planar face, a plane through a vertex, or a piece that still does not fit raise ValueError naming the face.
- perimeter_drop: for a footprint-aligned box body, every side of the plan must be covered by drop faces reaching
  <= -1.0 m (Artem 2026-10-22: «полигоны по периметру должны быть утоплены минимум на метр вниз»).
"""
import json
import math
import os
import re

DROP_MIN_M = -1.0


def fresh_out_dir(out, inputs):
    """Create a NEW output directory; refuse an existing one or one that is/contains/is inside an input."""
    import os
    o = os.path.realpath(out)
    for p in inputs:
        r = os.path.realpath(p)
        if o == r or r.startswith(o + os.sep) or o.startswith(r + os.sep):
            raise ValueError(f"output {out} aliases input {p}")
    if os.path.lexists(out):
        raise FileExistsError(f"output {out} already exists; choose a new version")
    os.makedirs(out)
    return out


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_spec(spec, kpp_spec=None):
    fin = spec.get("finishes") or {}
    if not fin:
        raise ValueError("spec has no finishes")
    udims = [t.get("udim") for t in fin.values()]
    if len(set(udims)) != len(udims) or not all(isinstance(u, int) and 1001 <= u <= 1100 for u in udims):
        raise ValueError(f"finish UDIMs must be unique ints 1001..1100: {udims}")
    for name, t in fin.items():
        rgb = t.get("rgb")
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in rgb)):
            raise ValueError(f"finish {name}: rgb must be three ints 0..255, got {rgb}")
        if t.get("kind") not in ("placeholder", "full"):
            raise ValueError(f"finish {name}: unsupported kind {t.get('kind')}")
        if t["kind"] == "full":
            S = t.get("S")
            if not (isinstance(S, (int, float)) and math.isfinite(S) and S > 0):
                raise ValueError(f"finish {name}: S must be a finite number > 0, got {S}")
            dens = spec["size_full"] / S
            if not 512 <= dens <= 1706:  # reg p.32 §6.2 band
                raise ValueError(f"finish {name}: density {dens:.0f} px/m outside 512..1706")
    src = spec.get("source_ids") or {}
    if not src:
        raise ValueError("spec has no source_ids")
    for sid, rule in src.items():
        names = [rule["above"], rule["below"]] if rule.get("split") == "below_zero" else [rule.get("finish")]
        if rule.get("split") not in (None, "below_zero"):
            raise ValueError(f"source ID {sid}: unsupported split {rule.get('split')}")
        for n in names:
            if n not in fin:
                raise ValueError(f"source ID {sid}: finish {n} is not declared")
    empty = {int(i) for i in spec.get("empty_ids", [])}
    clash = empty & {int(i) for i in src}
    if clash:
        raise ValueError(f"IDs both mapped and empty: {sorted(clash)}")
    if not isinstance(spec.get("zero_m"), (int, float)) or not math.isfinite(spec["zero_m"]):
        raise ValueError("zero_m must be a finite number")
    if spec.get("kpp_palette") and kpp_spec is None:
        raise ValueError("spec has a kpp_palette: validate it against the KPP spec (load_kpp())")
    if kpp_spec is not None:
        for name, ref in (spec.get("kpp_palette") or {}).items():
            k = kpp_spec["finishes"].get(ref["kpp_finish"])
            if k is None or k["udim"] != ref["kpp_udim"]:
                raise ValueError(f"{name}: KPP twin {ref} not found in the KPP spec")
            if fin[name]["rgb"] != k["rgb"]:
                raise ValueError(f"{name}: rgb {fin[name]['rgb']} != KPP {ref['kpp_finish']} {k['rgb']}")
            if fin[name]["kind"] == "full" and k["kind"] == "placeholder":  # user texture in the KPP colour
                check_user_texture(name, spec)
                check_density_contract(name, spec, density_twin(name, spec, kpp_spec), kpp_spec)
            elif fin[name]["kind"] == "full":  # same joints/noise/recess as the KPP VPM tile; only S/phase may differ
                for key in ("pattern", "P", "h_joints", "rough", "metal", "joint_half_mm"):
                    if fin[name].get(key) != k.get(key):
                        raise ValueError(f"{name}: {key} {fin[name].get(key)} != KPP {k.get(key)}")
                check_density_contract(name, spec, k, kpp_spec)
    for name, t in fin.items():
        if t.get("pattern") == "user_vjoints" and name not in (spec.get("kpp_palette") or {}):
            raise ValueError(f"{name}: a user-texture finish needs a kpp_palette twin (colour + density contract)")
    return True


DECISION_REF = re.compile(r"^(D\d+|https://github\.com/\S+#issuecomment-\d+)$")


def contract_density(name, spec, kpp_spec):
    """px/m a full finish must deliver: the KPP twin's density (Artem 2026-10-22 «такой же тексель, как в VPM КПП»),
    or the value of an approved `density_exception` that cites the user decision (D<n> or the issue-comment URL)."""
    ref = (spec.get("kpp_palette") or {}).get(name)
    if ref is None:
        raise ValueError(f"{name}: full finish without a KPP twin has no density contract")
    k = density_twin(name, spec, kpp_spec)
    exc = (spec.get("density_exception") or {}).get(name)
    if exc is not None:
        v = exc.get("px_per_m")
        if not (isinstance(exc.get("decision"), str) and DECISION_REF.match(exc["decision"])):
            raise ValueError(f"{name}: density_exception needs decision = D<n> or an issue-comment URL, got "
                             f"{exc.get('decision')!r}")
        if not (isinstance(v, (int, float)) and math.isfinite(v) and 512 <= v <= 1706):
            raise ValueError(f"{name}: density_exception px_per_m must be finite in 512..1706, got {v}")
        return float(v)
    return kpp_spec["size_full"] / k["S"]


def density_twin(name, spec, kpp_spec):
    """The patterned KPP finish whose texel density `name` must deliver: its colour twin when that is patterned,
    else the declared `density_twin` (a user texture in the colour of a plain KPP finish)."""
    ref = (spec.get("kpp_palette") or {}).get(name)
    if ref is None:
        raise ValueError(f"{name}: full finish without a KPP twin has no density contract")
    k = kpp_spec["finishes"].get(ref["kpp_finish"])
    if k is not None and k["kind"] == "full":
        return k
    dt = ref.get("density_twin")
    kd = kpp_spec["finishes"].get((dt or {}).get("kpp_finish"))
    if not dt or kd is None or kd["udim"] != dt.get("kpp_udim") or kd["kind"] != "full":
        raise ValueError(f"{name}: KPP twin {ref.get('kpp_finish')} is plain; density_twin {dt} must name a patterned "
                         f"KPP finish (no density contract otherwise)")
    return kd


HEX64 = re.compile(r"^[0-9a-f]{64}$")


def check_user_texture(name, spec):
    """A `user_vjoints` finish: vertical joints only, laid out every P[0] by whole-period u shifts, from a user image
    whose joint period in px equals P[0] at the finish density (no resampling of the user's joint profile)."""
    t = spec["finishes"][name]
    if t.get("pattern") != "user_vjoints":
        raise ValueError(f"{name}: a full finish on a plain KPP twin must be pattern user_vjoints, got {t.get('pattern')}")
    if t.get("h_joints") is not False or t.get("shift") != [True, False]:
        raise ValueError(f"{name}: vertical joints only: h_joints must be false and shift [true, false]")
    P = t.get("P")
    if not (isinstance(P, list) and len(P) == 2 and all(isinstance(x, (int, float)) and math.isfinite(x) and x > 0
                                                          for x in P)):
        raise ValueError(f"{name}: P must be two finite periods > 0, got {P}")
    st = t.get("source_texture") or {}
    if not (isinstance(st.get("path"), str) and isinstance(st.get("sha256"), str) and HEX64.match(st["sha256"])):
        raise ValueError(f"{name}: source_texture needs path and a lowercase hex sha256, got {st}")
    per, fj = st.get("period_px"), st.get("first_joint_px")
    if not (isinstance(per, int) and isinstance(fj, list) and len(fj) == 2 and all(isinstance(x, int) for x in fj)
            and 0 <= fj[0] < fj[1] and (fj[1] - fj[0]) % 2 == 0):
        raise ValueError(f"{name}: source_texture period_px / first_joint_px [a, b) malformed: {per}, {fj}")
    want = P[0] * spec["size_full"] / t["S"]
    if abs(per - want) > 1e-6:
        raise ValueError(f"{name}: source period {per} px != P {P[0]} m at {spec['size_full'] / t['S']:.1f} px/m "
                         f"({want:.2f} px); the user's joint profile is not resampled")


def check_density_contract(name, spec, k, kpp_spec, tol=0.5):
    dens = spec["size_full"] / spec["finishes"][name]["S"]
    want = contract_density(name, spec, kpp_spec)
    if not abs(dens - want) <= tol:
        raise ValueError(f"{name}: texel density {dens:.1f} px/m != contract {want:.1f} px/m "
                         f"(KPP {kpp_spec['size_full'] / k['S']:.1f}; no approved density_exception)")


def load_kpp():
    return load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "KPP1", "scripts",
                             "vpm_textures.json"))


def _finite(vertices):
    for v in vertices:
        if len(v) != 3 or not all(isinstance(c, (int, float)) and math.isfinite(c) for c in v):
            raise ValueError(f"non-finite or malformed vertex {v}")


def assign_finishes(vertices, faces, mat_ids, spec):
    """Return one finish name per polygon (fail-closed on unmapped / empty IDs)."""
    if not faces:
        raise ValueError("no polygons")
    if len(faces) != len(mat_ids):
        raise ValueError(f"{len(faces)} polygons but {len(mat_ids)} material IDs")
    _finite(vertices)
    src, empty, zero = spec["source_ids"], {int(i) for i in spec.get("empty_ids", [])}, spec["zero_m"]
    out = []
    for i, (f, m) in enumerate(zip(faces, mat_ids)):
        if int(m) in empty:
            raise ValueError(f"polygon {i}: material ID {m} is declared empty but has faces")
        rule = src.get(str(int(m)))
        if rule is None:
            raise ValueError(f"polygon {i}: material ID {m} has no finish mapping")
        if rule.get("split") == "below_zero":
            zmax = max(vertices[k][2] for k in f)
            out.append(rule["below"] if zmax <= zero else rule["above"])
        else:
            out.append(rule["finish"])
    return out


def facade_uv(vertices, face, lo, hi, tol=1e-3):
    """Metre UVs of a vertical face: u from the left corner of its facade seen from outside, v = world z.

    lo/hi: plan bbox (x, y) of the body. The facade is picked by the dominant horizontal normal axis; the winding
    follows the face (no mirrored islands). A face that is not vertical raises ValueError.
    """
    p = [vertices[k] for k in face]
    n = [0.0, 0.0, 0.0]
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(sum(c * c for c in n))
    if ln <= 0 or abs(n[2]) / ln > tol:
        raise ValueError(f"face {face} is not vertical; facade UV needs a wall face")
    if abs(n[1]) >= abs(n[0]):
        return [((q[0] - lo[0]) if n[1] < 0 else (hi[0] - q[0]), q[2]) for q in p]
    return [((q[1] - lo[1]) if n[0] > 0 else (hi[1] - q[1]), q[2]) for q in p]


def perimeter_drop(vertices, faces, finishes, drop_finish, tol=0.001):
    """Per plan side of the body bbox: covered length of drop faces reaching <= DROP_MIN_M (box bodies only)."""
    _finite(vertices)
    body = [k for f in faces for k in f if vertices[k][2] > 0.0]
    if not body:
        raise ValueError("no body above ±0.000")
    lo = [min(vertices[k][a] for k in body) for a in (0, 1)]
    hi = [max(vertices[k][a] for k in body) for a in (0, 1)]
    sides = {"x-": (0, lo[0], 1), "x+": (0, hi[0], 1), "y-": (1, lo[1], 0), "y+": (1, hi[1], 0)}
    report = {}
    for side, (axis, coord, along) in sides.items():
        iv = []
        for f, fin in zip(faces, finishes):
            p = [vertices[k] for k in f]
            if fin != drop_finish or min(q[2] for q in p) > DROP_MIN_M:
                continue
            if all(abs(q[axis] - coord) <= tol for q in p):
                iv.append((min(q[along] for q in p), max(q[along] for q in p)))
        iv.sort()
        covered, cur = 0.0, None
        for a, b in iv:
            if cur is None or a > cur[1] + tol:
                if cur:
                    covered += cur[1] - cur[0]
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        if cur:
            covered += cur[1] - cur[0]
        length = hi[along] - lo[along]
        report[side] = {"length_m": round(length, 4), "covered_m": round(covered, 4),
                        "ok": covered >= length - tol}
    return report


# ------------------------------------------------------------------ joint frame and ring cuts (pure Python)
def body_plan_bbox(vertices, zero_m):
    pts = [c for c in vertices if c[2] > zero_m]
    if not pts:
        raise ValueError("no body above ±0.000")
    return [min(c[0] for c in pts), min(c[1] for c in pts)], [max(c[0] for c in pts), max(c[1] for c in pts)]


def facade_axis(vertices, face, lo, hi):
    """(world axis along the facade, +1 if facade u grows with that world coordinate else -1)."""
    uv = facade_uv(vertices, face, lo, hi)
    p = [vertices[k] for k in face]
    for axis in (0, 1):
        span = max(q[axis] for q in p) - min(q[axis] for q in p)
        if span > 1e-9:
            i, j = max(range(len(p)), key=lambda m: p[m][axis]), min(range(len(p)), key=lambda m: p[m][axis])
            if abs(abs(uv[i][0] - uv[j][0]) - span) < 1e-6:
                return axis, (1 if uv[i][0] > uv[j][0] else -1)
    raise ValueError(f"face {face}: no facade axis (zero width)")


def joint_origin(vertices, face, lo, hi):
    """Joint frame of a patterned source face: (axis, sign, origin) with origin = its smallest world coordinate."""
    axis, sign = facade_axis(vertices, face, lo, hi)
    return axis, sign, min(vertices[k][axis] for k in face)


def facade_joint_uv(vertices, face, frame):
    """Metre UVs (u', z) of a vertical face in a joint frame: vertical joints sit at u' = n * P."""
    axis, sign, origin = frame
    return [(sign * (vertices[k][axis] - origin), vertices[k][2]) for k in face]


def piece_fits(span, spec, name):
    t = spec["finishes"][name]
    return span <= t["S"] - 2 * spec["pad_m"] - t["P"][0] + 1e-9


def _newell(p):
    n = [0.0, 0.0, 0.0]
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    ln = math.sqrt(sum(c * c for c in n))
    return [c / ln for c in n] if ln > 0 else None


def ring_cut(vertices, faces, parents, start, axis, X, tol=1e-4, planar_tol=1e-3):
    """Edge-ring cut of the quad strip through face `start` by the plane coordinate[axis] == X.

    Returns (vertices, faces, parents, info); inputs are not modified. Each ring quad has exactly two opposite edges
    straddling X; the ring is followed across them to the mesh boundary (or until it closes). Fail-closed ValueError:
    X not finite, start not straddled, a ring face that is not a quad / not planar / has a vertex within tol of the
    plane, a non-manifold edge."""
    if not (isinstance(X, (int, float)) and math.isfinite(X)):
        raise ValueError(f"cut position must be finite, got {X}")
    edge_faces = {}
    for i, f in enumerate(faces):
        for k in range(len(f)):
            edge_faces.setdefault(frozenset((f[k], f[(k + 1) % len(f)])), []).append(i)
    side = lambda v: vertices[v][axis] - X  # noqa: E731

    def crossing(i):
        f = faces[i]
        if len(f) != 4:
            raise ValueError(f"ring face {i} (source {parents[i]}) is not a quad ({len(f)} corners)")
        if any(abs(side(v)) <= tol for v in f):
            raise ValueError(f"cut plane {X:.4f} passes through a vertex of ring face {i} (source {parents[i]})")
        ks = [k for k in range(4) if side(f[k]) * side(f[(k + 1) % 4]) < 0]
        if len(ks) != 2 or (ks[1] - ks[0]) != 2:
            raise ValueError(f"ring face {i} (source {parents[i]}) is not crossed on two opposite edges")
        n = _newell([vertices[v] for v in f])
        if n is None or max(abs(sum((vertices[v][c] - vertices[f[0]][c]) * n[c] for c in range(3))) for v in f) \
                > planar_tol:
            raise ValueError(f"ring face {i} (source {parents[i]}) is not planar within {planar_tol} m")
        return ks

    ring = {start: crossing(start)}
    todo = [start]
    while todo:
        i = todo.pop()
        f = faces[i]
        for k in ring[i]:
            e = frozenset((f[k], f[(k + 1) % 4]))
            nb = [j for j in edge_faces[e] if j != i]
            if len(nb) > 1:
                raise ValueError(f"non-manifold edge {sorted(e)} in the ring")
            for j in nb:
                if j not in ring:
                    ring[j] = crossing(j)
                    todo.append(j)
    V = [list(c) for c in vertices]
    cache = {}

    def point(a, b):
        key = frozenset((a, b))
        if key not in cache:
            pa, pb = vertices[a], vertices[b]
            t = (X - pa[axis]) / (pb[axis] - pa[axis])
            V.append([pa[c] + t * (pb[c] - pa[c]) for c in range(3)])
            V[-1][axis] = X
            cache[key] = len(V) - 1
        return cache[key]

    F, P = [], []
    for i, f in enumerate(faces):
        if i not in ring:
            F.append(list(f))
            P.append(parents[i])
            continue
        k = ring[i][0]
        a, b, c, d = (f[(k + m) % 4] for m in range(4))
        p, q = point(a, b), point(c, d)
        F += [[a, p, q, d], [p, b, c, q]]
        P += [parents[i], parents[i]]
    return V, F, P, {"axis": axis, "X": X, "ring_faces": len(ring),
                     "source_faces": sorted({parents[i] for i in ring}), "new_vertices": len(cache)}


def apply_cuts(vertices, faces, finishes, spec, lo, hi, max_rings=64):
    """Cut every patterned (facade_uv) face that does not fit its tile at whole joints (ring cuts), deterministic.

    Returns {"vertices", "faces", "parents", "frames" (per source face, None if not patterned), "cuts": [...]}.
    A face of length L gets ceil(L / Lmax) - 1 cuts at the joints nearest the even split points; the loop re-plans
    on the current pieces, so a ring that already cut a face elsewhere is not cut again next to it."""
    _finite(vertices)
    patterned = set(spec.get("facade_uv", {}))
    frames = [joint_origin(vertices, f, lo, hi) if fin in patterned else None for f, fin in zip(faces, finishes)]
    V, F, par = [list(c) for c in vertices], [list(f) for f in faces], list(range(len(faces)))
    cuts = []
    while True:
        todo = None
        for i, f in enumerate(F):
            fr = frames[par[i]]
            if fr is None:
                continue
            name = finishes[par[i]]
            us = [u for u, _ in facade_joint_uv(V, f, fr)]
            a, b = min(us), max(us)
            if piece_fits(b - a, spec, name):
                continue
            Pu = spec["finishes"][name]["P"][0]
            lmax = spec["finishes"][name]["S"] - 2 * spec["pad_m"] - Pu
            n = math.ceil((b - a) / lmax)
            u_cut = round((a + (b - a) / n) / Pu) * Pu
            if not (a + 1e-3 < u_cut < b - 1e-3) or not piece_fits(u_cut - a, spec, name):
                u_cut = math.floor((a + lmax) / Pu) * Pu  # largest joint that still fits the first piece
            if not (a + 1e-3 < u_cut < b - 1e-3) or not piece_fits(u_cut - a, spec, name):
                raise ValueError(f"source face {par[i]} ({name}, {b - a:.3f} m): no joint cut fits the tile")
            axis, sign, origin = fr
            todo = (i, axis, origin + sign * u_cut, par[i], name, u_cut)
            break
        if todo is None:
            break
        if len(cuts) >= max_rings:
            raise ValueError(f"more than {max_rings} ring cuts; refusing")
        i, axis, X, src, name, u_cut = todo
        V, F, par, info = ring_cut(V, F, par, i, axis, X)
        cuts.append(dict(info, planned_for=src, finish=name, u_joint_m=round(u_cut, 6)))
    return {"vertices": V, "faces": F, "parents": par, "frames": frames, "cuts": cuts}
