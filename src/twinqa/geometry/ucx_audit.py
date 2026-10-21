"""Read-only UCX hull measurements and collision findings (reg p.36 §13.4; [D098], [D162]).

Pure Python (no numpy, no bpy) so the same functions run inside Blender
(`tools/blender/ucx_audit.py`) and under pytest. Measurement helpers do not emit a
pass/fail verdict, except `classify`, which returns `status: "review"` (undetermined) for a
hull with a degenerate triangle (issue #460) so a sliver can never pass closed/convex.
`pair_findings` and `collision_findings` report req 2.13.4:
too-close (< 0.2 mm, SINTEZ), gap outside the D098 2 mm - 1 cm band, intersect and
nested. A hull the SAT machinery cannot measure is `not_run`, never skipped.
A hull is `(verts, tris)` with `verts` a list of xyz tuples in metres and
`tris` a list of vertex-index triples.
"""
from __future__ import annotations

import itertools
import math
import re

GAP_BAND_M = (0.002, 0.01)  # [D098]: 2 mm - 1 cm inclusive (reg p.36 §13.4 0.02-1 cm is a typo, C15)
BAND_TOL_M = 1e-5  # float32 FBX coordinates: a modelled 2.000 mm gap reads back within 0.01 mm
TOUCH_M = 0.0002  # faces practically touch; SINTEZ too-close is gap < this [D162]
# Same constant as scene.OVERLAP_EPS_M (scene.py imports this module, so it cannot be imported
# here). Comment there: it is numerical precision, not a permitted overlap.
OVERLAP_EPS_M = 1e-5
DEGENERATE_VOLUME_M3 = 1e-9  # absolute enclosed volume at or below this is not a volumetric hull
DEGENERATE_AREA_M2 = 1e-10  # zero-area / sliver triangle area at or below this is degenerate (issue #460)
NEIGHBOUR_M = 0.10  # pairs closer than this are "neighbours" in the gap report
CONVEX_TOL_M = 1e-4  # float32 FBX coordinates around 100 m carry ~1e-5 noise
REQ_COLLISION = "2.13.4"  # no intersections; neighbour gap 2 mm - 1 cm [D098], plus SINTEZ too-close [D162]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(a):
    return math.sqrt(_dot(a, a))


def _unit(a):
    n = _norm(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else None


def weld(verts, tris, tol=1e-5):
    """Merge coincident vertices (FBX import splits them per face) and drop degenerate tris."""
    key = {}
    remap, out = [], []
    for v in verts:
        k = tuple(round(c / tol) for c in v)
        if k not in key:
            key[k] = len(out)
            out.append(tuple(v))
        remap.append(key[k])
    new_tris = []
    for t in tris:
        a, b, c = (remap[i] for i in t)
        if len({a, b, c}) == 3:
            new_tris.append((a, b, c))
    return out, new_tris


def degenerate_triangles(verts, tris, area_tol=DEGENERATE_AREA_M2):
    """Indices of degenerate triangles: a repeated vertex index or area <= area_tol (m^2).

    A zero-area / sliver triangle fools `is_closed` (its edges, each used twice, "close" a
    hole) and is silently skipped by `is_convex` (`if plane is None: continue`). Report these
    up front so the caller can return an undetermined verdict instead of a false pass. The raw
    input is measured before `weld`, because weld drops repeated-index triangles silently.
    """
    out = []
    for i, (a, b, c) in enumerate(tris):
        if a == b or b == c or a == c:
            out.append(i)
            continue
        area = _norm(_cross(_sub(verts[b], verts[a]), _sub(verts[c], verts[a]))) / 2.0
        if area <= area_tol:
            out.append(i)
    return out


def face_planes(verts, tris):
    """Outward-agnostic plane per triangle: (unit normal, offset) or None for slivers."""
    planes = []
    for a, b, c in tris:
        n = _unit(_cross(_sub(verts[b], verts[a]), _sub(verts[c], verts[a])))
        planes.append(None if n is None else (n, _dot(n, verts[a])))
    return planes


def is_closed(tris):
    """Every undirected edge is shared by exactly two triangles."""
    count = {}
    for t in tris:
        for i in range(3):
            e = tuple(sorted((t[i], t[(i + 1) % 3])))
            count[e] = count.get(e, 0) + 1
    return bool(count) and all(n == 2 for n in count.values())


def is_convex(verts, tris, tol=CONVEX_TOL_M):
    """All vertices lie on one side of every triangle plane (either orientation)."""
    for plane in face_planes(verts, tris):
        if plane is None:
            continue
        n, d = plane
        s = [_dot(n, v) - d for v in verts]
        if max(s) > tol and min(s) < -tol:
            return False
    return True


def _normal_axes(verts, tris, angle_tol_deg=0.5):
    """Distinct face-normal directions up to sign."""
    cos_tol = math.cos(math.radians(angle_tol_deg))
    axes = []
    for plane in face_planes(verts, tris):
        if plane is None:
            continue
        n = plane[0]
        if not any(abs(_dot(n, a)) >= cos_tol for a in axes):
            axes.append(n)
    return axes


def classify(verts, tris):
    """Hull kind: box_aabb | box_oriented | convex | custom (open or non-convex).

    A hull with a degenerate triangle (repeated vertex index or zero area, issue #460) is
    `review` (undetermined): its closed/convex state cannot be verified, so it is never a
    false pass. Clean hulls keep their previous verdicts unchanged.
    """
    degenerate = degenerate_triangles(verts, tris)
    if degenerate:
        return {"kind": "custom", "closed": None, "convex": None, "verts": len(verts),
                "tris": len(tris), "status": "review",
                "degenerate_triangles": {"count": len(degenerate), "triangles": degenerate[:5]}}
    verts, tris = weld(verts, tris)
    closed, convex = is_closed(tris), is_convex(verts, tris)
    kind = "custom"
    if closed and convex:
        kind = "convex"
        axes = _normal_axes(verts, tris)
        if len(verts) == 8 and len(axes) == 3 and all(
                abs(_dot(a, b)) < 1e-3 for a, b in itertools.combinations(axes, 2)):
            aligned = all(max(abs(c) for c in a) > 1 - 1e-6 for a in axes)
            kind = "box_aabb" if aligned else "box_oriented"
    return {"kind": kind, "closed": closed, "convex": convex, "verts": len(verts), "tris": len(tris)}


def face_signature(verts, tris):
    """Distinct face directions split into horizontal (roof/floor), vertical (wall) and tilted:
    e.g. a box is (1, 2, 0), a vertical prism over a non-rectangular plan (1, k, 0), a
    truncated pyramid or wedge has tilted directions."""
    verts, tris = weld(verts, tris)
    h = v = t = 0
    for a in _normal_axes(verts, tris):
        if abs(a[2]) > 1 - 1e-6:
            h += 1
        elif abs(a[2]) < 1e-3:
            v += 1
        else:
            t += 1
    return (h, v, t)


def bounds(verts):
    return ([min(v[i] for v in verts) for i in range(3)], [max(v[i] for v in verts) for i in range(3)])


def bbox_gap(ba, bb):
    """Euclidean distance between two AABBs (0 when they overlap)."""
    d = [max(ba[0][i] - bb[1][i], bb[0][i] - ba[1][i], 0.0) for i in range(3)]
    return _norm(d)


def _edges(tris):
    return {tuple(sorted((t[i], t[(i + 1) % 3]))) for t in tris for i in range(3)}


def sat_separation(a, b):
    """Largest separation of two convex hulls over the SAT axes (face normals, edge crosses).

    > 0: separated by at least that much; <= 0: overlap, -value = penetration depth along the
    best axis. a and b are (verts, tris) of convex hulls.
    """
    (va, ta), (vb, tb) = a, b
    axes = [p[0] for p in face_planes(va, ta) + face_planes(vb, tb) if p is not None]
    da = [_unit(_sub(va[j], va[i])) for i, j in _edges(ta)]
    db = [_unit(_sub(vb[j], vb[i])) for i, j in _edges(tb)]
    for u in da:
        for w in db:
            if u is None or w is None:
                continue
            c = _unit(_cross(u, w))
            if c is not None:
                axes.append(c)
    best = -math.inf
    for ax in axes:
        pa = [_dot(ax, v) for v in va]
        pb = [_dot(ax, v) for v in vb]
        best = max(best, min(pb) - max(pa), min(pa) - max(pb))
    return best


def _closest_on_segment(p, a, b):
    ab = _sub(b, a)
    den = _dot(ab, ab)
    t = 0.0 if den < 1e-18 else max(0.0, min(1.0, _dot(_sub(p, a), ab) / den))
    return (a[0] + ab[0] * t, a[1] + ab[1] * t, a[2] + ab[2] * t)


def point_triangle_distance(p, a, b, c):
    n = _cross(_sub(b, a), _sub(c, a))
    nn = _dot(n, n)
    if nn > 1e-18:
        t = _dot(_sub(p, a), n) / nn
        q = (p[0] - n[0] * t, p[1] - n[1] * t, p[2] - n[2] * t)
        # barycentric inside test
        inside = all(_dot(_cross(_sub(y, x), _sub(q, x)), n) >= -1e-15 for x, y in ((a, b), (b, c), (c, a)))
        if inside:
            return abs(t) * math.sqrt(nn)
    return min(_norm(_sub(p, _closest_on_segment(p, x, y))) for x, y in ((a, b), (b, c), (c, a)))


def segment_segment_distance(p1, q1, p2, q2):
    d1, d2, r = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, e, f = _dot(d1, d1), _dot(d2, d2), _dot(d2, r)
    if a < 1e-18 and e < 1e-18:
        return _norm(r)
    if a < 1e-18:
        s, t = 0.0, max(0.0, min(1.0, f / e))
    else:
        c = _dot(d1, r)
        if e < 1e-18:
            s, t = max(0.0, min(1.0, -c / a)), 0.0
        else:
            b = _dot(d1, d2)
            den = a * e - b * b
            s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-18 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                s, t = max(0.0, min(1.0, -c / a)), 0.0
            elif t > 1.0:
                s, t = max(0.0, min(1.0, (b - c) / a)), 1.0
    c1 = (p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s)
    c2 = (p2[0] + d2[0] * t, p2[1] + d2[1] * t, p2[2] + d2[2] * t)
    return _norm(_sub(c1, c2))


def surface_distance(a, b):
    """Exact minimum distance between the surfaces of two triangle meshes that do not cross:
    vertex-triangle both ways and edge-edge (the closest pair always involves one of them)."""
    (va, ta), (vb, tb) = a, b
    best = math.inf
    for p in va:
        for t in tb:
            best = min(best, point_triangle_distance(p, vb[t[0]], vb[t[1]], vb[t[2]]))
    for p in vb:
        for t in ta:
            best = min(best, point_triangle_distance(p, va[t[0]], va[t[1]], va[t[2]]))
    for i, j in _edges(ta):
        for k, m in _edges(tb):
            best = min(best, segment_segment_distance(va[i], va[j], vb[k], vb[m]))
    return best


def pair_relation(a, b):
    """Relation of two convex hulls: (class, gap_m, penetration_m).

    class: overlap (penetration > OVERLAP_EPS_M), touch (gap < TOUCH_M), below_band
    (TOUCH_M <= gap < 2 mm), in_band (2 mm - 1 cm inclusive, [D098]), wide (1 cm < gap
    <= NEIGHBOUR_M), apart (gap > NEIGHBOUR_M, not neighbours).

    OVERLAP_EPS_M separates a true intersection from numerical contact. TOUCH_M is only the
    SINTEZ too-close gap (< 0.2 mm) and is not an overlap cutoff. A separation at or below
    OVERLAP_EPS_M is touching; a larger positive separation is a measured gap.
    """
    sep = sat_separation(a, b)
    if sep < -OVERLAP_EPS_M:
        return "overlap", 0.0, -sep
    gap = surface_distance(a, b) if sep > OVERLAP_EPS_M else 0.0
    if gap < TOUCH_M:
        return "touch", gap, max(0.0, -sep)
    if gap < GAP_BAND_M[0] - BAND_TOL_M:
        return "below_band", gap, 0.0
    if gap <= GAP_BAND_M[1] + BAND_TOL_M:
        return "in_band", gap, 0.0
    if gap <= NEIGHBOUR_M:
        return "wide", gap, 0.0
    return "apart", gap, 0.0


def inside_convex(p, verts, tris, tol=0.0):
    """Point inside a closed convex hull (normals oriented away from the centroid)."""
    cen = tuple(sum(v[i] for v in verts) / len(verts) for i in range(3))
    for plane in face_planes(verts, tris):
        if plane is None:
            continue
        n, d = plane
        if _dot(n, cen) - d > 0:
            n, d = (-n[0], -n[1], -n[2]), -d
        if _dot(n, p) - d > tol:
            return False
    return True


def _enclosed_volume(verts, tris):
    """Absolute enclosed volume (m^3) from the signed tetrahedron sum over triangles.

    Vertices are shifted by the first vertex before the sum. Signed volume is
    translation-invariant; the local frame avoids cancellation when the hull sits
    far from the global origin. Same sum as scene._enclosed_volume, which keeps its
    own copy because scene.py imports this module.
    """
    if not verts:
        return 0.0
    origin = verts[0]
    total = 0.0
    for ia, ib, ic in tris:
        a, b, c = _sub(verts[ia], origin), _sub(verts[ib], origin), _sub(verts[ic], origin)
        total += a[0] * (b[1] * c[2] - b[2] * c[1])
        total -= a[1] * (b[0] * c[2] - b[2] * c[0])
        total += a[2] * (b[0] * c[1] - b[1] * c[0])
    return abs(total) / 6.0


def _unmeasurable(verts, tris):
    """Why SAT must not run on this hull, or None when the hull is closed, convex and volumetric."""
    try:
        if len(verts) == 0 or len(tris) == 0:
            return "empty"
    except TypeError:
        return "missing geometry"
    try:
        for v in verts:
            if len(v) != 3 or not all(math.isfinite(float(c)) for c in v):
                return "non-finite coordinates"
        n = len(verts)
        for t in tris:
            if len(t) != 3:
                return "invalid topology"
            for i in t:
                if isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= n:
                    return "invalid topology"
    except (TypeError, ValueError):
        return "non-finite coordinates"
    if not is_closed(tris):
        return "open"
    if not is_convex(verts, tris):
        return "non-convex"
    try:
        volume = _enclosed_volume(verts, tris)
    except (ArithmeticError, TypeError, ValueError, IndexError):
        return "degenerate"
    # NaN and +inf compare false against the threshold and would otherwise fall through.
    if not isinstance(volume, (int, float)) or isinstance(volume, bool) or not math.isfinite(volume):
        return "degenerate"
    if volume <= DEGENERATE_VOLUME_M3:
        return "degenerate"
    return None


def _drop(reason, hull, index=None):
    rec = {"type": "not_run", "req": REQ_COLLISION, "reason": reason, "hull": hull}
    if index is not None:
        rec["index"] = index
    return rec


def _finding(kind, gap_m, penetration_m, ref_a, ref_b):
    return {"type": kind, "req": REQ_COLLISION, "gap_m": gap_m, "penetration_m": penetration_m,
            "a": ref_a, "b": ref_b}


def _one_inside_the_other(a, b):
    """True when every vertex of one hull lies inside the other (boundary counts as inside)."""
    (va, ta), (vb, tb) = a, b
    return (all(inside_convex(p, vb, tb) for p in va)
            or all(inside_convex(p, va, ta) for p in vb))


def pair_findings(a, b, name_a=None, name_b=None):
    """Req 2.13.4 findings for one unordered pair of convex hulls. Zero or more.

    Overlap (penetration > OVERLAP_EPS_M) is `nested` when one hull contains the other, otherwise
    `intersect`. A gap below TOUCH_M emits both `too_close` and `gap_out_of_band` [D162].
    A gap outside 2 mm - 1 cm emits `gap_out_of_band` (above 1 cm only while the pair is still
    a neighbour, gap <= NEIGHBOUR_M). In-band and non-neighbour gaps emit nothing.
    An unmeasurable hull is `not_run` and is not given a gap or overlap finding.
    """
    ref_a = 0 if name_a is None else name_a
    ref_b = 1 if name_b is None else name_b
    drops = []
    for hull, ref in ((a, ref_a), (b, ref_b)):
        try:
            verts, tris = hull[0], hull[1]
        except (TypeError, ValueError, IndexError, KeyError):
            drops.append(_drop("missing geometry", ref))
            continue
        reason = _unmeasurable(verts, tris)
        if reason:
            drops.append(_drop(reason, ref))
    if drops:
        return drops
    cls, gap, pen = pair_relation(a, b)
    if cls == "overlap":
        kind = "nested" if _one_inside_the_other(a, b) else "intersect"
        return [_finding(kind, 0.0, pen, ref_a, ref_b)]
    if cls == "touch":
        return [_finding("too_close", gap, 0.0, ref_a, ref_b),
                _finding("gap_out_of_band", gap, 0.0, ref_a, ref_b)]
    if cls in ("below_band", "wide"):
        return [_finding("gap_out_of_band", gap, 0.0, ref_a, ref_b)]
    return []


def collision_findings(hulls):
    """Findings for every unordered pair of named hulls, plus a drop for each hull SAT cannot measure.

    Each hull is `{"name", "verts", "tris"}`. An empty list returns `[]` (no pairs, not a pass).
    Open, non-convex, degenerate, empty and non-finite hulls are `not_run` and are left out of pair checks;
    every other pair is still measured. Pair order follows input order.
    """
    if isinstance(hulls, (list, tuple)) and len(hulls) == 0:
        return []
    if not isinstance(hulls, (list, tuple)):
        return [_drop("missing geometry", None)]
    drops, usable = [], []
    for index, item in enumerate(hulls):
        if not isinstance(item, dict):
            drops.append(_drop("missing geometry", index, index))
            continue
        name = item["name"] if item.get("name") not in (None, "") else index
        verts, tris = item.get("verts"), item.get("tris")
        if verts is None or tris is None:
            drops.append(_drop("missing geometry", name, index))
            continue
        reason = _unmeasurable(verts, tris)
        if reason:
            drops.append(_drop(reason, name, index))
        else:
            usable.append((name, (verts, tris)))
    findings = list(drops)
    for (name_a, hull_a), (name_b, hull_b) in itertools.combinations(usable, 2):
        findings.extend(pair_findings(hull_a, hull_b, name_a=name_a, name_b=name_b))
    return findings


def output_alias_reason(source, out):
    """Why `out` must not be written for `source` (None when it is safe).

    The audit writes a JSON report; it must never land on the model it reads. Rejected:
    the same resolved path (case-insensitive on Windows, `..`, symlinks) and an existing
    output that is the same file as the source (hard link, symlink, junction).
    """
    import os
    from pathlib import Path

    src, dst = Path(source), Path(out)
    try:
        src_r, dst_r = src.resolve(), dst.resolve()
    except OSError as exc:
        return f"cannot resolve paths: {exc}"
    if os.path.normcase(str(src_r)) == os.path.normcase(str(dst_r)):
        return f"output path is the input path: {dst_r}"
    if src.exists() and dst.exists():
        try:
            if os.path.samefile(src, dst):
                return f"output {dst_r} is the same file as input {src_r} (link alias)"
        except OSError as exc:
            return f"cannot compare input and output identity: {exc}"
    if dst.is_dir():
        return f"output path is a directory: {dst_r}"
    return None


def name_report(names, main_name):
    """Collision names vs reg p.34 §4.2: UCX_SM_{Address}_{Main|Ground}_{001..999}."""
    address = main_name[3:-5] if main_name.startswith("SM_") and main_name.endswith("_Main") else None
    pat = re.compile(r"^UCX_SM_(?P<addr>.+)_(?P<target>Main|Ground)_(?P<idx>\d{3})$")
    bad, idx = [], {"Main": [], "Ground": []}
    for n in names:
        m = pat.match(n)
        if not m or (address is not None and m["addr"] != address) or m["idx"] == "000":
            bad.append(n)
            continue
        idx[m["target"]].append(int(m["idx"]))
    report = {"address": address, "mask_ok": len(names) - len(bad), "mask_bad": bad[:20],
              "mask_bad_count": len(bad)}
    for target, values in idx.items():
        dup = sorted({v for v in values if values.count(v) > 1})
        report[target] = {"count": len(values), "duplicates": dup,
                          "contiguous_from_1": sorted(values) == list(range(1, len(values) + 1))}
    return report
