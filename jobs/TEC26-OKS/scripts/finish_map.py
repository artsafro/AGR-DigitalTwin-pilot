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
  first_joint_px) and a `density_twin` (a patterned KPP finish) for the texel contract. Split rule `facade`: the
  finish of a vertical polygon is its facade's finish (spec facades, by outward normal +x/-x/+y/-y).
- facade rib contract (validate_facades / field_frames; Artem 2026-10-22, supersedes the 0.60 m step): per facade the
  sheet's rib count `ribs` is spread evenly over the whole panel field (all patterned faces of the facade together),
  P = field_m / ribs, joints at field_lo + k * P (k = 1 .. ribs - 1), symmetric; the user texture gives one joint's
  look only. Without a facades block the old per-face frame (joint_origin) is used and user_vjoints is rejected.
  [D169]; the wall edging around the field is blue RAL 5015 with a dark field outline (outline_z_m) [D170].
- ring cuts (plan_cuts / ring_cut / apply_cuts; Artem 2026-10-22 «если не влезает, то можно аккуратно порезать через
  loop или ring»): a patterned face longer than the tile holds is split by an edge ring at a joint position; the ring
  runs through quads only, from boundary to boundary (or closed), so no T-junction is created; every new vertex lies
  on a source edge; silhouette, normals, UCX and IDs are unchanged. Fail-closed: a non-quad, a non-manifold edge, a
  non-planar face, a plane through a vertex, or a piece that still does not fit raise ValueError naming the face.
- perimeter_drop: for a footprint-aligned box body, every side of the plan must be covered by drop faces reaching
  <= -1.0 m (Artem 2026-10-22: «полигоны по периметру должны быть утоплены минимум на метр вниз»).
"""
import math
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.derive.finish_map import (  # noqa: F401,E402 - replay API
    DECISION_REF, HEX64, LEGEND_TEXTURES, NORMALS, check_density_contract,
    check_user_texture, contract_density, density_twin, fresh_out_dir, load,
    validate_facades, validate_legend,
)
from tools.derive import finish_map as _owner  # noqa: E402

def validate_spec(spec, kpp_spec=None):
    """Owner validate_spec with this module's validate_legend resolved at call time (job adapters patch it)."""
    return _owner.validate_spec(spec, kpp_spec, legend_check=lambda s, k: validate_legend(s, k))

DROP_MIN_M = -1.0


def facade_key(vertices, face, tol=1e-3):
    """Outward facade of a vertical face: '+x', '-x', '+y' or '-y' by the dominant Newell normal; ValueError else."""
    n = _newell([vertices[k] for k in face])
    if n is None or abs(n[2]) > tol:
        raise ValueError(f"face {face} is not vertical; a facade finish needs a wall face")
    a = 0 if abs(n[0]) >= abs(n[1]) else 1
    return ("+" if n[a] > 0 else "-") + "xy"[a]


def facade_of(spec, key):
    for name, f in spec["facades"].items():
        if f["normal"] == key:
            return name, f
    raise ValueError(f"no facade in the spec faces {key}")


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
        elif rule.get("split") == "facade":
            try:
                out.append(facade_of(spec, facade_key(vertices, f))[1]["finish"])
            except ValueError as e:
                raise ValueError(f"polygon {i}: material ID {m} (split facade): {e}") from None
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


def field_frames(vertices, faces, finishes, spec, lo, hi, tol=1e-3):
    """Joint frames of the patterned faces from the facade PANEL FIELD (all patterned faces of one facade together):
    origin = the field's smallest world coordinate along the facade, so joints sit at field_lo + k * P with
    P = field_m / ribs (spec facades) - evenly over the whole field, symmetric, continuous across face splits.
    Returns (frames per face or None, report per facade). Fail-closed: a field whose measured width differs from the
    spec field_m by more than `tol`, or a patterned face whose finish is not its facade's finish."""
    patterned = set(spec.get("facade_uv", {}))
    groups = {}
    for i, (f, fin) in enumerate(zip(faces, finishes)):
        if fin in patterned:
            groups.setdefault(facade_key(vertices, f), []).append(i)
    frames: list = [None] * len(faces)
    report = {}
    for key, idx in sorted(groups.items()):
        name, fc = facade_of(spec, key)
        axis = 1 - NORMALS[key][0]
        cs = [vertices[k][axis] for i in idx for k in faces[i]]
        a, b = min(cs), max(cs)
        if abs((b - a) - fc["field_m"]) > tol:
            raise ValueError(f"facade {name}: measured panel field {b - a:.4f} m != spec field_m {fc['field_m']} m")
        oz = spec["finishes"][fc["finish"]].get("outline_z_m")
        zs = [vertices[k][2] for i in idx for k in faces[i]]
        if oz and (abs(min(zs) - oz[0]) > tol or abs(max(zs) - oz[1]) > tol):
            raise ValueError(f"facade {name}: panel field z {min(zs):.4f}..{max(zs):.4f} != outline_z_m {oz}")
        for i in idx:
            if finishes[i] != fc["finish"]:
                raise ValueError(f"face {i}: finish {finishes[i]} on facade {name} expects {fc['finish']}")
            ax, sign = facade_axis(vertices, faces[i], lo, hi)
            if ax != axis:
                raise ValueError(f"face {i}: facade axis {ax} != field axis {axis}")
            frames[i] = (axis, sign, a)
        P = spec["finishes"][fc["finish"]]["P"][0]
        report[name] = {"normal": key, "finish": fc["finish"], "faces": len(idx), "axis": "xy"[axis],
                        "field_lo": round(a, 6), "field_hi": round(b, 6), "field_m": round(b - a, 6),
                        "ribs": fc["ribs"], "pitch_m": round(P, 6),
                        "joints_world": [round(a + k * P, 6) for k in range(1, fc["ribs"])]}
    return frames, report


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
    on the current pieces, so a ring that already cut a face elsewhere is not cut again next to it. Joint frames are
    the facade panel fields (field_frames) when the spec has a facades contract, else per face (joint_origin)."""
    _finite(vertices)
    patterned = set(spec.get("facade_uv", {}))
    if spec.get("facades"):
        frames, _ = field_frames(vertices, faces, finishes, spec, lo, hi)
    else:
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
