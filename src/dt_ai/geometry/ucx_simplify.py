"""`agr ucx FBX REPORT.json Main|Ground --simplify-report`: the two simplification passes of the Codex
oks-collision-builder skill (#2097) as an OBSERVE report. It never refuses on a finding and never writes geometry.

Pattern: n/a | new-case: exact triangle-halfspace coverage per convex UCX body + delete/absorb/keep lists (#2097).

    agr ucx FBX REPORT.json Main|Ground --simplify-report [--blender EXE] [--margin-m M] [--absorb-m M]

FBX holds the render mesh and its UCX (e.g. an `agr ucx` OUT, a delivered VPM file). Blender (headless,
`tools/blender/ucx_mesh_dump.py`) only dumps world-space triangles; this module measures in CPython (numpy).

Coverage is exact on FULL source triangles (not vertices or centres): each triangle is clipped by the half-spaces
of a convex body; `covered_m2` is the clipped area. The control margin `--margin-m` (default 10 mm, the pack's
QA value) expands every body before clipping, so a face flush with the model or across a 2-10 mm seam counts;
`covered_tight_m2` uses 1 mm ([D436]). `unique_m2` is the part of the body's coverage that no OTHER (expanded)
body covers: the clipped polygons minus every neighbour, by an exact convex decomposition.

Pass A (empty / duplicate): covered 0 even with the margin -> `delete`; covered > 0 but unique 0 -> deleted one
at a time (smallest first) and re-measured, so interchangeable blocks are never deleted together.
Pass B (useful but over-split), on the kept convex bodies:
- `merge`: two bodies across one seam whose convex hull adds no more air than the seam itself (one box split in
  two); the smaller is listed with the triangles saved.
- `plane_shift`: a body lying in front of one face plane of a neighbour, inside its other planes, absorbed by
  moving that plane out by `shift_m` <= `--absorb-m` (default 0.30 m Main [D134] R12, 0.10 m Ground R11). The whole
  moved face (`moved_face_area_m2`) stands out by that much more: a rebuild hypothesis to re-check, not a result.
Everything else is `keep` with the measured reason. Ported checks (`twinqa.geometry.ucx_seams`): seam gap over
the whole facing face, winding/outward normals, slivers.

Exit 0 measured (findings included); 2 the dump failed; 4 refused before any write.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

from twinqa.geometry import ucx_seams as sm

ROOT = Path(__file__).resolve().parents[3]
DRIVER = ROOT / "tools" / "blender" / "ucx_mesh_dump.py"
MARGIN_M, TIGHT_M, SEAM_M = 0.010, 0.001, 0.010
ABSORB_M = {"Main": 0.30, "Ground": 0.10}
CONVEX_TOL_M = 0.001  # [D436]
AREA_EPS_M2 = 1e-6
USAGE = "usage: agr ucx FBX REPORT.json Main|Ground --simplify-report [--blender EXE] [--margin-m M] [--absorb-m M]"


# ---- clipping ---------------------------------------------------------------------------------------------------
def _clip(poly, n, d):
    """Sutherland-Hodgman: keep n.x <= d of a convex polygon (list of 3-tuples)."""
    out = []
    m = len(poly)
    for k in range(m):
        p, q = poly[k], poly[(k + 1) % m]
        sp = n[0] * p[0] + n[1] * p[1] + n[2] * p[2] - d
        sq = n[0] * q[0] + n[1] * q[1] + n[2] * q[2] - d
        if sp <= 0:
            out.append(p)
        if (sp < 0 < sq) or (sq < 0 < sp):
            t = sp / (sp - sq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), p[2] + t * (q[2] - p[2])))
    return out


def _area(poly):
    if len(poly) < 3:
        return 0.0
    x0, y0, z0 = poly[0]
    sx = sy = sz = 0.0
    for k in range(1, len(poly) - 1):
        ax, ay, az = poly[k][0] - x0, poly[k][1] - y0, poly[k][2] - z0
        bx, by, bz = poly[k + 1][0] - x0, poly[k + 1][1] - y0, poly[k + 1][2] - z0
        sx += ay * bz - az * by
        sy += az * bx - ax * bz
        sz += ax * by - ay * bx
    return 0.5 * math.sqrt(sx * sx + sy * sy + sz * sz)


def _subtract(pieces, pn, pd):
    """Convex pieces minus the convex body {n.x <= d}: disjoint convex remainders."""
    out = []
    for poly in pieces:
        rest = poly
        for n, d in zip(pn, pd):
            outside = _clip(rest, -n, -d)
            if _area(outside) > 0:
                out.append(outside)
            rest = _clip(rest, n, d)
            if len(rest) < 3:
                break
    return out


# ---- bodies -----------------------------------------------------------------------------------------------------
def split_bodies(meshes):
    """[{name, verts, tris}] -> one entry per connected part (welded); several parts get `name#k`."""
    out = []
    for m in meshes:
        v, t = sm.weld(m["verts"], m["tris"])
        if not len(t):
            continue
        parent = list(range(len(v)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b, c in t.tolist():
            ra, rb, rc = find(a), find(b), find(c)
            parent[rb] = ra
            parent[find(rc)] = ra
        roots = np.array([find(a) for a in t[:, 0].tolist()])
        order = list(dict.fromkeys(roots.tolist()))
        for k, r in enumerate(order, 1):
            tt = t[roots == r]
            used = np.unique(tt)
            remap = -np.ones(len(v), int)
            remap[used] = np.arange(len(used))
            name = m["name"] if len(order) == 1 else f"{m['name']}#{k}"
            out.append({"name": name, "verts": v[used], "tris": remap[tt]})
    return out


def _volume(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


class _Body:
    def __init__(self, b):
        self.name = b["name"]
        self.v = np.asarray(b["verts"], float)
        self.t = np.asarray(b["tris"], int)
        self.pn, self.pd = sm.planes(self.v, self.t)
        self.lo, self.hi = self.v.min(axis=0), self.v.max(axis=0)
        s = self.v @ self.pn.T - self.pd
        self.convex_worst_m = float(s.max()) if s.size else math.inf
        self.convex = bool(len(self.pd) >= 4 and self.convex_worst_m <= CONVEX_TOL_M)
        self.volume = _volume(self.v, self.t)
        proj = self.v @ self.pn.T
        self.thickness = float((proj.max(axis=0) - proj.min(axis=0)).min()) if proj.size else 0.0


# ---- coverage ---------------------------------------------------------------------------------------------------
class _Model:
    def __init__(self, verts, tris):
        v = np.asarray(verts, float).reshape(-1, 3)
        t = np.asarray(tris, int).reshape(-1, 3)
        self.a, self.b, self.c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
        self.lo = np.minimum(np.minimum(self.a, self.b), self.c)
        self.hi = np.maximum(np.maximum(self.a, self.b), self.c)
        self.area = 0.5 * np.linalg.norm(np.cross(self.b - self.a, self.c - self.a), axis=1)

    def candidates(self, body, m):
        sel = np.all(self.hi >= body.lo - m, axis=1) & np.all(self.lo <= body.hi + m, axis=1)
        idx = np.nonzero(sel)[0]
        if not len(idx):
            return idx, idx
        d = body.pd + m
        sa = self.a[idx] @ body.pn.T - d
        sb = self.b[idx] @ body.pn.T - d
        sc = self.c[idx] @ body.pn.T - d
        out = ((sa > 0) & (sb > 0) & (sc > 0)).any(axis=1)
        full = ((sa <= 0) & (sb <= 0) & (sc <= 0)).all(axis=1)
        keep = ~out
        return idx[keep], full[keep]

    def pieces(self, body, m):
        """{triangle index: [convex polygons of the triangle inside the expanded body]}."""
        idx, full = self.candidates(body, m)
        out = {}
        d = body.pd + m
        for i, f in zip(idx.tolist(), full.tolist()):
            poly = [tuple(self.a[i]), tuple(self.b[i]), tuple(self.c[i])]
            if not f:
                for n, dd in zip(body.pn, d):
                    poly = _clip(poly, n, dd)
                    if len(poly) < 3:
                        break
            if _area(poly) > 0:
                out[i] = [poly]
        return out


def _aabb_near(a, b, reach):
    return bool(np.all(a.lo - reach <= b.hi) and np.all(b.lo - reach <= a.hi))


def _unique(model, i, bodies, pieces_i, others, m):
    rest = {k: list(v) for k, v in pieces_i.items()}
    for j in others:
        bj = bodies[j]
        idx, _ = model.candidates(bj, m)
        for k in set(idx.tolist()) & rest.keys():
            rest[k] = _subtract(rest[k], bj.pn, bj.pd + m)
    return sum(_area(p) for ps in rest.values() for p in ps)


# ---- pass B -----------------------------------------------------------------------------------------------------
def _off_line(q, r, s):
    """Distance of r from the line q-s."""
    qs = np.subtract(s, q)
    return float(np.linalg.norm(np.cross(np.subtract(r, q), qs)) / max(float(np.linalg.norm(qs)), 1e-12))


def _hull_triangles_volume(pts, tol=2e-5):
    """Convex hull of a few points by brute force over point triples (robust; merge test needs <= ~32 points):
    (triangles of the hull with coplanar faces merged and fan-triangulated, volume)."""
    p = np.unique(np.round(np.asarray(pts, float), 9), axis=0)
    if len(p) < 4:
        raise ValueError("flat hull")
    p = p - p.mean(axis=0)
    i, j, k = np.array([(a, b, e) for a in range(len(p)) for b in range(a + 1, len(p))
                        for e in range(b + 1, len(p))]).T
    n = np.cross(p[j] - p[i], p[k] - p[i])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-9
    n, i = n[ok] / ln[ok, None], i[ok]
    d = (n * p[i]).sum(axis=1)
    flip = d < 0
    n[flip], d[flip] = -n[flip], -d[flip]
    face = ((p @ n.T - d) <= tol).all(axis=0)
    # volume from the EXACT supporting facets (each distinct set of points on a supporting plane once): merging
    # near-coplanar float32 facets by a loose tolerance loses facet area and gives a hull smaller than its bodies
    s = p @ n.T - d
    exact = (s <= 1e-9).all(axis=0)
    seen, vol = set(), 0.0
    for q in np.nonzero(exact)[0]:
        on_idx = np.nonzero(np.abs(s[:, q]) <= 1e-9)[0]
        key = frozenset(on_idx.tolist())
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        on = p[on_idx]
        u, w = sm._basis(n[q])
        rel = on - on.mean(axis=0)
        vol += d[q] * _area([tuple(x) for x in on[np.argsort(np.arctan2(rel @ w, rel @ u))]]) / 3.0
    # triangle count after merging coplanar faces within tol and dropping collinear boundary points
    fn, fd = [], []
    for a, b in zip(n[face], d[face]):
        if not any(float(a @ m) > 1 - 1e-7 and abs(b - e) < 1e-4 for m, e in zip(fn, fd)):
            fn.append(a)
            fd.append(b)
    tris = 0
    for a, b in zip(fn, fd):
        on = p[np.abs(p @ a - b) <= tol]
        if len(on) < 3:
            continue
        u, w = sm._basis(a)
        rel = on - on.mean(axis=0)
        poly = [tuple(x) for x in on[np.argsort(np.arctan2(rel @ w, rel @ u))]]
        while len(poly) > 3:  # drop collinear boundary points (seam corners of a merged pair)
            k = next((k for k in range(len(poly))
                      if _off_line(poly[k - 1], poly[k], poly[(k + 1) % len(poly)]) <= tol), None)
            if k is None:
                break
            poly.pop(k)
        tris += len(poly) - 2
    if vol <= 0:
        raise ValueError("flat hull")
    return tris, vol


def _plane_shift(bi, bj, seam_m):
    """Smallest outward move of one face plane of bj that swallows bi, or None."""
    best = None
    s = bi.v @ bj.pn.T - bj.pd  # (verts, planes)
    for k in range(len(bj.pd)):
        lo, hi = float(s[:, k].min()), float(s[:, k].max())
        if lo < -1e-3 or lo > seam_m + 1e-6:
            continue
        other = np.delete(s, k, axis=1)
        if other.size and float(other.max()) > seam_m + 1e-6:
            continue
        if best is None or hi < best[1]:
            best = (k, hi)
    return best


def _face_area(body, k):
    n, d = body.pn[k], body.pd[k]
    for fn, fd, corners in sm.faces(body.v, body.t):
        if float(fn @ n) > 1 - 1e-6 and abs(fd - d) < 1e-4:
            a, b, c = corners[:, 0], corners[:, 1], corners[:, 2]
            return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())
    return 0.0


def simplify_report(model_verts, model_tris, bodies, margin_m=MARGIN_M, tight_m=TIGHT_M, absorb_m=0.30,
                    seam_m=SEAM_M):
    parts = split_bodies(bodies)
    bs = [_Body(b) for b in parts]
    model = _Model(model_verts, model_tris)
    n = len(bs)
    near = [[j for j in range(n) if j != i and _aabb_near(bs[i], bs[j], 2 * margin_m)] for i in range(n)]
    rows = []
    pieces = []
    for i, b in enumerate(bs):
        p = model.pieces(b, margin_m) if b.convex else {}
        pieces.append(p)
        cov = sum(_area(x) for xs in p.values() for x in xs)
        tight = sum(_area(x) for xs in model.pieces(b, tight_m).values() for x in xs) if b.convex else None
        uniq = _unique(model, i, bs, p, [j for j in near[i] if bs[j].convex], margin_m) if b.convex else None
        rows.append({"name": b.name, "triangles": int(len(b.t)), "volume_m3": round(b.volume, 6),
                     "thickness_m": round(b.thickness, 4), "convex": b.convex,
                     "convex_worst_m": round(b.convex_worst_m, 6),
                     "covered_m2": round(cov, 6) if b.convex else None,
                     "covered_tight_m2": round(tight, 6) if tight is not None else None,
                     "unique_m2": round(uniq, 6) if uniq is not None else None, "decision": None, "reason": None})
    removed = set()
    # pass A: empty
    for i, r in enumerate(rows):
        if not bs[i].convex:
            r["decision"], r["reason"] = "keep", (f"not convex (worst {r['convex_worst_m'] * 1000:.2f} mm > "
                                                  f"{CONVEX_TOL_M * 1000:.0f} mm [D436]): passes not measured")
        elif r["covered_m2"] <= AREA_EPS_M2:
            r["decision"] = "delete"
            r["reason"] = (f"no source surface inside even with the {margin_m * 1000:.0f} mm control margin; "
                           "delete unless it has an explicit volume function")
            removed.add(i)
    # pass A: duplicates, one at a time
    dup = sorted((i for i, r in enumerate(rows) if r["decision"] is None and r["unique_m2"] <= AREA_EPS_M2),
                 key=lambda i: (rows[i]["covered_m2"], rows[i]["name"]))
    for i in dup:
        others = [j for j in near[i] if j not in removed and bs[j].convex]
        u = _unique(model, i, bs, pieces[i], others, margin_m)
        if u <= AREA_EPS_M2:
            rows[i]["decision"] = "delete"
            rows[i]["reason"] = (f"zero unique coverage: neighbours {[bs[j].name for j in others][:6]} cover all "
                                 f"{rows[i]['covered_m2']:.4f} m2; re-check after deleting")
            removed.add(i)
        else:
            gone = [bs[j].name for j in near[i] if j in removed]
            rows[i]["decision"] = "keep"
            rows[i]["reason"] = f"unique once {gone} deleted ({u:.4f} m2): interchangeable, keep one"
            rows[i]["unique_after_m2"] = round(u, 6)
    # pass B
    kept = [i for i in range(n) if i not in removed and bs[i].convex]
    keep_set = set(kept)
    seams = sm.seam_face_gaps([{"name": i, "verts": bs[i].v, "tris": bs[i].t} for i in kept], with_prism=True)
    for s in seams:  # their c3 "meshDistInGap": does source surface show through a seam wider than 1 cm?
        prism = s.pop("_prism")
        if s["gap_max_m"] <= seam_m + 1e-6:
            continue
        a, b = bs[s["a"]], bs[s["b"]]
        box = type("Prism", (), {"pn": prism[0], "pd": prism[1], "lo": np.minimum(a.lo, b.lo),
                                 "hi": np.maximum(a.hi, b.hi)})()
        inside = model.pieces(box, 0.0)
        third = [k for k in keep_set if k not in (s["a"], s["b"]) and _aabb_near(bs[k], box, margin_m)]
        for k in third:  # a third body (with the control margin: a seam <= 1 cm is allowed [D098]) fills it
            idx, _ = model.candidates(bs[k], margin_m)
            for q in set(idx.tolist()) & inside.keys():
                inside[q] = _subtract(inside[q], bs[k].pn, bs[k].pd + margin_m)
        s["model_in_seam_m2"] = round(sum(_area(p) for ps in inside.values() for p in ps), 6)
    seam_vol = {}
    for s in seams:
        if s["gap_max_m"] <= seam_m + 1e-6:
            key = (min(s["a"], s["b"]), max(s["a"], s["b"]))
            seam_vol[key] = seam_vol.get(key, 0.0) + s["overlap_area_m2"] * max(s["gap_mean_m"], 0.0)
    absorb, absorbed, targets = [], set(), set()
    for (i, j), sv in sorted(seam_vol.items()):
        try:
            ht, hv = _hull_triangles_volume(np.vstack([bs[i].v, bs[j].v]))
        except ValueError:
            continue
        air = hv - bs[i].volume - bs[j].volume
        if air <= 1.1 * sv + 1e-6:
            small, big = (i, j) if (bs[i].volume, bs[i].name) <= (bs[j].volume, bs[j].name) else (j, i)
            absorb.append({"name": bs[small].name, "kind": "merge", "into": bs[big].name,
                           "added_air_m3": round(air, 6), "seam_volume_m3": round(sv, 6),
                           "triangles_saved": int(len(bs[i].t) + len(bs[j].t) - ht)})
            absorbed.add(small)
            targets.add(big)
    for i in sorted(kept, key=lambda i: (bs[i].volume, bs[i].name)):
        if i in absorbed or i in targets:  # a body that absorbs another is not itself absorbed (no chains)
            continue
        best = None
        for j in near_any(bs, i, keep_set, absorb_m):
            if j in absorbed:
                continue
            got = _plane_shift(bs[i], bs[j], seam_m)
            if got and (best is None or got[1] < best[2]):
                best = (j, got[0], got[1])
        if best and best[2] <= absorb_m + 1e-9:
            j, k, s = best
            area = _face_area(bs[j], k)
            absorb.append({"name": bs[i].name, "kind": "plane_shift", "into": bs[j].name, "shift_m": round(s, 6),
                           "moved_face_area_m2": round(area, 4),
                           "added_air_m3": round(max(area * s - bs[i].volume, 0.0), 6),
                           "triangles_saved": int(len(bs[i].t)),
                           "recheck": "rebuild, then re-check the whole moved face: R12/R13 outward offset grows "
                                      "by shift_m, seams with its other neighbours, openings"})
            absorbed.add(i)
            targets.add(j)
            rows[i]["_best_shift"] = s
        elif best:
            rows[i]["_best_shift"] = best[2]
    names_absorbed = {a["name"] for a in absorb}
    for i, r in enumerate(rows):
        bs_i = r.pop("_best_shift", None)
        if r["decision"] is not None:
            continue
        if r["name"] in names_absorbed:
            r["decision"], r["reason"] = "absorb_rebuild", "see lists.absorb_rebuild (deleting it loses coverage)"
        else:
            r["decision"] = "keep"
            r["reason"] = (f"unique coverage {r['unique_m2']:.4f} m2; " +
                           (f"best neighbour plane shift {bs_i:.3f} m > absorb tolerance {absorb_m} m"
                            if bs_i is not None else "no neighbour plane spans it within the seam and no merge"))
    # ported checks
    winding = {r["name"]: sm.winding_report(b.v, b.t) for r, b in zip(rows, bs)}
    slivers = {r["name"]: sm.sliver_report(b.v, b.t) for r, b in zip(rows, bs)}
    seam_named = [dict(s, a=bs[s["a"]].name, b=bs[s["b"]].name) for s in seams]
    seam_classes = {}
    for s in seam_named:
        seam_classes[s["class"]] = seam_classes.get(s["class"], 0) + 1
    lists = {"delete": [r["name"] for r in rows if r["decision"] == "delete"],
             "absorb_rebuild": absorb,
             "keep_with_reason": [{"name": r["name"], "reason": r["reason"]} for r in rows if r["decision"] == "keep"]}
    total_tris = int(sum(len(b.t) for b in bs))
    summary = {"bodies": n, "triangles": total_tris, "delete": len(lists["delete"]),
               "delete_triangles": int(sum(r["triangles"] for r in rows if r["decision"] == "delete")),
               "absorb_merge": sum(1 for a in absorb if a["kind"] == "merge"),
               "absorb_plane_shift": sum(1 for a in absorb if a["kind"] == "plane_shift"),
               "absorb_triangles_saved_upper": int(sum(a["triangles_saved"] for a in absorb)),
               "keep": len(lists["keep_with_reason"]), "not_convex": sum(1 for b in bs if not b.convex),
               "model_area_m2": round(float(model.area.sum()), 4)}
    return {"status": "observe", "issue": "#2097", "params": {"margin_m": margin_m, "tight_m": tight_m,
                                                              "absorb_m": absorb_m, "seam_m": seam_m},
            "summary": summary, "lists": lists, "bodies": rows,
            "ported_checks": {
                "seams": {"classes": seam_classes,
                          "open_with_model": sum(1 for s in seam_named if s.get("model_in_seam_m2", 0) > 1e-4),
                          "open_with_model_m2": round(sum(s.get("model_in_seam_m2", 0) for s in seam_named), 4),
                          "not_ok": sorted((s for s in seam_named if s["class"] != "ok"),
                                           key=lambda s: (-s.get("model_in_seam_m2", 0), -s["gap_max_m"]))[:50]},
                "winding": {"inconsistent": [k for k, w in winding.items() if not w["consistent"]],
                            "inward": [k for k, w in winding.items() if not w["outward"]]},
                "slivers": {"flagged": sorted(([k, w["min_edge_m"], w["min_height_m"]] for k, w in slivers.items()
                                               if w["flag"]), key=lambda x: x[1])[:50],
                            "count": sum(1 for w in slivers.values() if w["flag"]),
                            "thresholds_m": [sm.EDGE_MIN_M, sm.HEIGHT_MIN_M]}}}


def near_any(bs, i, keep_set, reach):
    return [j for j in keep_set if j != i and _aabb_near(bs[i], bs[j], reach)]


# ---- CLI --------------------------------------------------------------------------------------------------------
class Refused(ValueError):
    pass


def parse(argv):
    pos, opts = [], {"blender": None, "margin_m": MARGIN_M, "absorb_m": None}
    it = iter(argv)
    for a in it:
        if a in ("--blender", "--margin-m", "--absorb-m"):
            val = next(it, None)
            if val is None or val.startswith("--"):
                raise Refused(f"{a} needs a value")
            if a == "--blender":
                opts["blender"] = val
            else:
                try:
                    x = float(val)
                except ValueError:
                    raise Refused(f"{a} must be a number in metres") from None
                if not math.isfinite(x) or x < 0 or x > 1.0:
                    raise Refused(f"{a} must be within 0..1 m")
                opts[a[2:].replace("-", "_")] = x
        elif a.startswith("--"):
            raise Refused(f"unknown option {a!r}")
        else:
            pos.append(a)
    if len(pos) != 3:
        raise Refused(USAGE)
    fbx, out, target = Path(pos[0]), Path(pos[1]), pos[2]
    if target not in ABSORB_M:
        raise Refused(f"target must be Main or Ground, got {target!r}")
    if fbx.suffix.lower() != ".fbx" or not fbx.is_file():
        raise Refused(f"no input .fbx {fbx}")
    if out.suffix.lower() != ".json":
        raise Refused("REPORT must be a .json path")
    if out.exists() or out.is_symlink():
        raise Refused(f"report {out} exists; write a new versioned path, nothing overwritten")
    if out.resolve() == fbx.resolve():
        raise Refused("report aliases the input")
    if opts["absorb_m"] is None:
        opts["absorb_m"] = ABSORB_M[target]
    return {"fbx": fbx, "out": out, "target": target, **opts}


def _dump(a, work):
    from dt_ai.core.blender_runner import run_blender

    meta_p, npz_p = work / "meta.json", work / "meshes.npz"
    meta = run_blender(DRIVER, [str(a["fbx"]), str(meta_p), str(npz_p)], executable=a["blender"],
                       output_json=meta_p, outputs=[npz_p], timeout=1800, log_path=work / "dump.log")
    z = np.load(npz_p)
    voff, toff = z["ucx_vert_offsets"], z["ucx_tri_offsets"]
    meshes = []
    for k, name in enumerate(meta["ucx"]):
        v = z["ucx_verts"][voff[k]:voff[k + 1]]
        t = z["ucx_tris"][toff[k]:toff[k + 1]]
        meshes.append({"name": name, "verts": v, "tris": t})
    return meta, z["model_verts"], z["model_tris"], meshes


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        a = parse(argv)
    except Refused as exc:
        print(f"ERROR: agr ucx --simplify-report refused: {exc}; nothing written", file=sys.stderr)
        return 4
    report = {"command": "agr ucx --simplify-report", "fbx": str(a["fbx"]), "target": a["target"]}
    with tempfile.TemporaryDirectory(prefix="agr-ucx-simplify-") as tmp:
        try:
            meta, mv, mt, meshes = _dump(a, Path(tmp))
        except Exception as exc:  # the dump failed: report it, exit 2
            report.update(exit=2, error=f"mesh dump failed: {exc}")
            a["out"].write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"AGR_UCX_SIMPLIFY 2 {a['out']}")
            return 2
    report["model_meshes"] = meta["model_meshes"]
    report["model_triangles"] = meta["model_triangles"]
    report.update(simplify_report(mv, mt, meshes, margin_m=a["margin_m"], absorb_m=a["absorb_m"]))
    report["exit"] = 0
    a["out"].write_text(json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False), encoding="utf-8")
    print(f"AGR_UCX_SIMPLIFY 0 {a['out']}")
    return 0
