# Source face matching: corners and a centroid do not prove containment in a concave polygon

Research card t_66d99b9d (no new GitHub issue). Pinned origin/main SHA from the card: `45a35a2dca43ba4880b2a7f2359f376f2d4884fc`. Git was not run, so drift of this worktree from that SHA was not measured. No pytest, no `main()`, no ZIP/PNG/assets, no production edit. `delivery_passed=false`.

`docs/research` contains one source-finish QA note, `source-finish-stream-cardinality.md`. A second source-finish report is not in the tree. The issue number below is the one that note already writes (`#149`), not a lookup of `gh issue list`.

## Summary

`match_source_faces` assigns a source polygon when the three corners lie in its plane and in its outline (an edge within `tol=2e-4` counts as inside) and the centroid passes a strict ray cast (`jobs/TEC26-OKS/scripts/qa_packages.py:95-116`, sample test at line 113). On a frozen set of simple planar L, U and notched outlines, four triangles that leave the polygon through the notch still receive owner `(0,)`. The same owner is returned for every cyclic start, both windings, XY and XZ, and two paired translations (768 variant calls, 0 disagreements, 0 exceptions). Convex inside and outside controls, and triangles that stay in a concave bar, match the sample rule. A separate closed set of all 20 triangles formed by the L's own six vertices produced no accepted crossing: 12 with positive exterior clip area got owner `()`, 8 with clip area 0 got `(0,)`.

Area-sum coverage can hide the crossing. An 11-triangle nonoverlapping delivery on the L, whose owners are the tuples `match_source_faces` actually returns, has triangle areas summing to the polygon area 20. `source_finish_report` in area mode returns `ok: true`. The same call in count mode returns `ok: false` because 11 is not `len(face)-2` = 4. One triangle alone, with its real area, does not get `ok: true`. Setting both area lists equal by hand does. `geometry_report` rejects the 11-triangle mesh (three interior vertices off source edges) and accepts the on-edge crossing triangle when cuts are allowed. Those are direct function calls on synthetic vertices. Package `main()` was not run.

## Findings

Oracle, used for every "outside" claim: proper segment intersection (both parameters in `(0, 1)`) and Sutherland–Hodgman clipping of the triangle to a CCW rectangle that is exterior to the polygon (L notch `[2,6]×[2,6]`, U bite `[3,5]×[2,6]`, N bite `[4.5,5.5]×[1,4]`), then absolute shoelace. A witness point is inside the triangle by barycentric coordinates and inside that rectangle by interval tests. `_inside2d` is recorded only as the code's own corner (`tol=2e-4`) and centroid (`tol=-1`) classification. It is not the oracle. All four outlines passed a non-adjacency intersection check (`simple=true`). Areas: L 20, U 40, N 37 (`10×4 − 1×3`), convex quad 12. Default `tol` on `match_source_faces` is `2e-4` (`inspect.signature`); the probe never passes `tol`.

Code path (read, not a substitute for the run): the module docstring says every delivered triangle is inside one source polygon and the areas cover it (`qa_packages.py:8`, matcher text at `96-99`). The implementation tests three corners and the centroid (`113`). `source_finish_report` adds a triangle's area only when the owner tuple has length 1 (`141-144`) and compares the sum with `1e-6 + 1e-5 * polygon_area` (`153-154`). On area 20 that band is `0.000201`.

### Frozen single triangles (verified by run)

Base pose is CCW, cyclic start 0, XY, shift 0. `keep` is `[0,1]` in XY and `[0,2]` in XZ. Plane residual is 0. Every listed owner is stable across `len(polygon) × {ccw,cw} × {xy,xz} × {zero, both translated by (12, 3, -7.5), output translated and shift = -(12, 3, -7.5)}`. Inputs compared by deep copy stayed unchanged (a mutation would have been stored as a disagreement; the list is empty).

| id | triangle | code corners / strict centroid | proper hits | clip area | owner |
|---|---|---|---|---|---|
| conv_in | `(0.5,0.5) (3.5,0.5) (2,2.5)` on quad `(0,0)(4,0)(4,3)(0,3)` | T T T / T, centroid `(2, 1.167, 0)` | none | n/a (hull inside the open rectangle) | `(0,)` |
| conv_out | `(5,1) (7,1) (6,2)` | F F F / F, bbox reject, centroid `(6, 1.333, 0)` | none | 1 (whole triangle; `x≥5` vs quad `x≤4`) | `()` |
| L_contained | `(0.4,0.4) (5.5,0.4) (3,1.5)` | T T T / T, centroid `(2.967, 0.767, 0)` | none | 0 | `(0,)` |
| L_cross | `(0.5,0.5) (0.5,4.5) (4.5,0.5)` | T T T / T, centroid `(1.833, 1.833, 0)` | edge BC at `(3,2)` and `(2,3)` | 0.5 | `(0,)` |
| L_outside | `(7,7) (9,7) (8,9)` | F F F / F, bbox reject | none | 2 (whole triangle) | `()` |
| L_boundary | `(0,1) (0,5) (5,0)` on L edges | T T T / T, centroid `(1.667, 2, 0)` | edge BC at `(3,2)` t=0.6 and `(2,3)` t=0.4 | 0.5 | `(0,)` |
| U_contained | `(1,0.5) (7,0.5) (4,1.5)` | T T T / T | none | 0 | `(0,)` |
| U_cross | `(1,2.5) (7,2.5) (4,0.5)` | T T T / T, centroid `(4, 1.833, 0)` | top edge at `(5,2.5)` and `(3,2.5)` | 1 | `(0,)` |
| N_contained | `(1,0.25) (9,0.25) (5,0.75)` | T T T / T | none | 0 | `(0,)` |
| N_cross | `(1,1.25) (9,1.25) (5,0.25)` | T T T / T, centroid `(5, 0.917, 0)` | top edge at `(5.5,1.25)` and `(4.5,1.25)` | 0.25 | `(0,)` |

L, U and N are the CCW outlines in the reproducer. Witness points, all barycentric-inside the crossing triangle and inside the exterior rectangle: L_cross `(2.4, 2.4)`, L_boundary `(2.2, 2.2)`, U_cross `(4, 2.25)`, N_cross `(5, 1.125)`.

L_contained stays in the bottom bar because every convex combination has `0.4 ≤ y ≤ 1.5 < 2` and `0.4 ≤ x ≤ 5.5`. U_contained and N_contained stay below the bite the same way (`y ≤ 1.5 < 2`, `y ≤ 0.75 < 1`). That containment argument is independent of `_inside2d`. The accepted owners on those three are the sample rule agreeing with a triangle that does not leave the polygon.

Two-face control (verified): source faces L then quad `(20,0)(24,0)(24,3)(20,3)`. L_cross owner `[(0,)]`. Triangle `(20.5,0.5)(23.5,0.5)(22,2.5)` owner `[(1,)]`. No ambiguous pair.

Closed L vertex triples (verified, `C(6,3)=20`, XY, CCW, shift 0, no further search): 8 with clip area 0 accepted as `(0,)`; 12 with positive clip area rejected as `()`; 0 accepted with positive clip area; 0 exceptions. Triangles that use only this L's corners did not reproduce the crossing acceptance. The accepted crossings use extra points, either interior (L_cross) or on edges (L_boundary).

### (1) Wrong owner (verified)

L_cross, L_boundary, U_cross and N_cross are owners `(0,)` while the clip area is positive and two proper boundary intersections exist. That is a wrong containment owner. The finish string is not what fails: with delivered `"A"` and `expected=["A"]` the finish counters stay 0.

### (2) `source_finish_report` with real areas and with forced owners (verified)

Single triangle, XY, `expected=["A"]`, delivered `["A"]`. `tri_areas` / `poly_areas` are the module values. Columns: ok / tris / wrong_finish / unmatched / ambiguous / source_polygons_not_covered. No exceptions. Inputs unchanged.

| id | areas t / p | matcher owners | forced owner `(0,)` and those areas | forced owner `(0,)` and `t=p=[polygon area]` |
|---|---|---|---|---|
| L_cross | 8 / 20 | false / 1 / 0 / 0 / 0 / 1, examples `[0]` | same false / … / 1 | **true / 1 / 0 / 0 / 0 / 0** |
| L_contained | 2.805 / 20 | false / 1 / 0 / 0 / 0 / 1 | same | **true / 1 / 0 / 0 / 0 / 0** |
| L_boundary | 10 / 20 | false / 1 / 0 / 0 / 0 / 1 | same | **true / 1 / 0 / 0 / 0 / 0** |
| conv_in | 3 / 12 | false / 1 / 0 / 0 / 0 / 1 | same | **true / 1 / 0 / 0 / 0 / 0** |
| conv_out | 1 / 12 | false / 1 / 0 / **1** / 0 / 1 | false / 1 / 0 / 0 / 0 / 1 (the forced owner hides the empty match) | **true / 1 / 0 / 0 / 0 / 0** |

A single crossing triangle with its real area is uncovered (`|8-20|` and `|10-20|` are far above `0.000201`). The helper returns `ok: true` when the caller forces the owner and sets the two area numbers equal, including for conv_out, which the matcher rejected. That is a contrived area list, not a geometric cover.

### (3) Complete nonoverlapping delivery, owners from the matcher (verified)

Eleven triangles on L, listed in the reproducer as `MESH`. Independent checks before the matcher: pairwise clip area ≤ `1e-8` (none above), shoelace sum 20, gap point `(1, 5.9)` inside L (`0<x<2`, `0<y<6`) and in no triangle. The missing rectangle `[0,2]×[5.75,6]` has area `2×0.25=0.5`, equal to L_cross's exterior clip area. Witness `(2.4, 2.4)` lies only in triangle 0.

`match_source_faces` returns `(0,)` for all 11, in XY and in XZ. Module `tri_areas` equals the shoelace list `[8, 1.125, 1.125, 1.25, 1.25, 1.375, 1.375, 1.125, 1.125, 1.125, 1.125]`. `poly_areas` is `[20.0]`.

Area mode, both embeddings:

`{"ok": true, "tris": 11, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 0, "uncovered_examples": [], "examples": []}`

Count mode, both embeddings:

`{"ok": false, "tris": 11, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 1, "uncovered_examples": [0], "examples": []}`

No exceptions. Inputs unchanged. The area sum certifies a delivery that leaves 0.5 outside the notch and leaves 0.5 of the L empty. Production calls pass both area lists (`qa_packages.py:410-413`, read). This probe did not execute those lines.

### What else can reject the witness (function calls plus a read of `main`)

`geometry_report` (`176-184`) checks vertices, not faces. On the synthetic soups (all L corners included):

| fixture | cuts allowed | result |
|---|---|---|
| L_cross, three interior corners | true and false | `ok false`, `missing_source_vertices 0`, `new_vertices 3`, `new_off_source_edges 3` |
| L_boundary, three points on edges | true | **`ok true`**, `new_vertices 3`, `new_off_source_edges 0` |
| L_boundary | false | `ok false` because `new_vertices != 0` while cuts are disallowed (`182`) |
| 11-triangle mesh, XY | true and false | `ok false`, `new_vertices 12`, `new_off_source_edges 3` (the L_cross corners). XZ same, with those corners stored as `(x, 0, z)` |

`main` calls `geometry_report` at `320-322` and `source_finish_report` at `410-413` and does not return between them (read of `318-413`). It was not executed. A single wrong owner is not a package pass and not a package fail. The on-edge chord is a case where `geometry_report` with cuts allowed returns ok while the matcher still assigns the L; area mode on that one triangle still returns ok false because 10 ≠ 20. Whether a full on-edge triangulation can satisfy both at once was not measured.

### Tests and callers (read)

Production callers of `match_source_faces` are `qa_packages.py:404` and `:405` only. `source_finish_report` is called at `:410` and `:412`. `geometry_report` is called at `:320`.

`tests/jobs/test_tec26_ac08_pilot.py` calls the matcher on the AC08 ring-cut body (`test_qa_ownership_after_ring_cuts`, line 562) and on a fan of that body (`test_source_finish_report_catches_joint_loss` at 625, `test_source_finish_report_fail_closed` at 652). `tests/jobs/test_source_finish_area_count_controls.py` states that its oracles are hand totals and that it does not call `match_source_faces` (lines 1-8). No test in those files builds a concave notch crossing.

`docs/domain/areas/body.md` records BODY-A architectural comparison as L2 coverage `none`. This note does not add a BODY check. The helper under test is the TEC26 package QA that ties delivered body triangles to source faces.

## How it applies to this repository

- Sample test: `jobs/TEC26-OKS/scripts/qa_packages.py:79-116`. Corner proximity uses `tol`; the centroid call passes `-1`, which skips the proximity short-circuit (`85-89`).
- Area cover: `qa_packages.py:128-159`, especially `137-144` and `153-154`. Count mode uses `len(face)-2` (`156`). The 11-triangle mesh is legal for the area branch and illegal for the count branch.
- Vertex gate that can still fail an interior witness, and that accepts L_boundary when cuts are allowed: `qa_packages.py:170-184` and the call at `320-322`.
- The live finish check passes module areas: `404-413`.
- Existing tests do not contain these outlines: `tests/jobs/test_tec26_ac08_pilot.py`, `tests/jobs/test_source_finish_area_count_controls.py`.
- Prior QA note on stream length, which is a different hole in the same helper: `docs/research/source-finish-stream-cardinality.md`.

## Reproduction

Scratch copy that was executed: `C:/x/t_66d99b9d/probe.py`. Command, from the worktree:

`uv run python "C:/x/t_66d99b9d/probe.py" "jobs/TEC26-OKS/scripts"`

The process returned in about 4 seconds, including a first-time virtualenv build. The corpus is closed: 10 shapes × cyclic × winding × embedding × shift, plus 20 vertex triples, plus the mesh in XY and XZ. There is no parameter search. Call counter in the output: 830. Exceptions: 0.

```python
"""Frozen concave-containment probe of qa_packages.match_source_faces.

Usage: uv run python probe.py <path to jobs/TEC26-OKS/scripts>
Does not pass tol (default 2e-4). Oracle is segment intersection and clipping, not _inside2d.
"""
import copy
import inspect
import itertools
import json
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
import qa_packages as q  # noqa: E402

assert inspect.signature(q.match_source_faces).parameters["tol"].default == 2e-4

T3 = (12.0, 3.0, -7.5)
# Frozen outlines (simple, no holes). Frozen triangles. Frozen witnesses.
L = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6)]
U = [(0, 0), (8, 0), (8, 6), (5, 6), (5, 2), (3, 2), (3, 6), (0, 6)]
N = [(0, 0), (10, 0), (10, 4), (5.5, 4), (5.5, 1), (4.5, 1), (4.5, 4), (0, 4)]
CV = [(0, 0), (4, 0), (4, 3), (0, 3)]
NOTCH_L = [(2, 2), (6, 2), (6, 6), (2, 6)]  # exterior square of L
BITE_U = [(3, 2), (5, 2), (5, 6), (3, 6)]
BITE_N = [(4.5, 1), (5.5, 1), (5.5, 4), (4.5, 4)]

CASES = [
    ("conv_in", CV, [(0.5, 0.5), (3.5, 0.5), (2, 2.5)], None, (2, 1.5), "contained"),
    ("conv_out", CV, [(5, 1), (7, 1), (6, 2)], None, (6, 1), "separated"),
    ("L_contained", L, [(0.4, 0.4), (5.5, 0.4), (3, 1.5)], NOTCH_L, (3, 1), "contained"),
    ("L_cross", L, [(0.5, 0.5), (0.5, 4.5), (4.5, 0.5)], NOTCH_L, (2.4, 2.4), "notch"),
    ("L_outside", L, [(7, 7), (9, 7), (8, 9)], NOTCH_L, (8, 8), "separated"),
    ("L_boundary", L, [(0, 1), (0, 5), (5, 0)], NOTCH_L, (2.2, 2.2), "notch"),
    ("U_contained", U, [(1, 0.5), (7, 0.5), (4, 1.5)], BITE_U, (4, 1), "contained"),
    ("U_cross", U, [(1, 2.5), (7, 2.5), (4, 0.5)], BITE_U, (4, 2.25), "notch"),
    ("N_contained", N, [(1, 0.25), (9, 0.25), (5, 0.75)], BITE_N, (5, 0.5), "contained"),
    ("N_cross", N, [(1, 1.25), (9, 1.25), (5, 0.25)], BITE_N, (5, 1.125), "notch"),
]
MESH = [
    [(0.5, 0.5), (0.5, 4.5), (4.5, 0.5)],
    [(0, 0), (0.5, 0), (0.5, 4.5)],
    [(0, 0), (0.5, 4.5), (0, 4.5)],
    [(0, 4.5), (2, 4.5), (2, 5.75)],
    [(0, 4.5), (2, 5.75), (0, 5.75)],
    [(0.5, 0), (6, 0), (6, 0.5)],
    [(0.5, 0), (6, 0.5), (0.5, 0.5)],
    [(4.5, 0.5), (6, 0.5), (6, 2)],
    [(4.5, 0.5), (6, 2), (4.5, 2)],
    [(0.5, 4.5), (2, 4.5), (2, 3)],
    [(3, 2), (4.5, 2), (4.5, 0.5)],
]
GAP_PT = (1, 5.9)  # inside L, in the uncovered 0.5-area rectangle y in [5.75, 6]


def shoelace(poly):
    s = 0.0
    for i, (x, y) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x * y2 - x2 * y
    return 0.5 * s


def tri_area(t):
    return abs(shoelace(t))


def cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


def seg_hit(a, b, c, d):
    """Proper intersection, both parameters in (0, 1). None if parallel or only touching an end."""
    r = (b[0] - a[0], b[1] - a[1])
    s = (d[0] - c[0], d[1] - c[1])
    den = cross(r, s)
    if abs(den) < 1e-15:
        return None
    qmp = (c[0] - a[0], c[1] - a[1])
    t = cross(qmp, s) / den
    u = cross(qmp, r) / den
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (a[0] + t * r[0], a[1] + t * r[1], t, u)
    return None


def proper_hits(tri, poly):
    hits = []
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        for j in range(len(poly)):
            h = seg_hit(a, b, poly[j], poly[(j + 1) % len(poly)])
            if h:
                hits.append({"tri_edge": i, "poly_edge": j, "at": [h[0], h[1]], "t": h[2], "u": h[3]})
    return hits


def simple(poly):
    n = len(poly)
    if n < 3 or abs(shoelace(poly)) < 1e-12:
        return False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < 1e-18:
            return False
        if abs(cross((b[0] - a[0], b[1] - a[1]), (poly[(i + 2) % n][0] - b[0], poly[(i + 2) % n][1] - b[1]))) < 1e-12:
            return False
        for j in range(i + 1, n):
            if abs(i - j) % n <= 1 or abs(i - j) % n >= n - 1:
                continue
            if seg_hit(a, b, poly[j], poly[(j + 1) % n]):
                return False
    return True


def clip(subject, clip_poly):
    """Sutherland-Hodgman. clip_poly CCW. Inside = left of each edge."""
    def inside(p, a, b):
        return cross((b[0] - a[0], b[1] - a[1]), (p[0] - a[0], p[1] - a[1])) >= -1e-12

    def inter(p, e, a, b):
        r = (e[0] - p[0], e[1] - p[1])
        s = (b[0] - a[0], b[1] - a[1])
        den = cross(r, s)
        t = cross((a[0] - p[0], a[1] - p[1]), s) / den
        return (p[0] + t * r[0], p[1] + t * r[1])

    out = list(subject)
    for i in range(len(clip_poly)):
        a, b = clip_poly[i], clip_poly[(i + 1) % len(clip_poly)]
        inp, nxt = out, []
        if not inp:
            return []
        s = inp[-1]
        for e in inp:
            ein, sin = inside(e, a, b), inside(s, a, b)
            if ein:
                if not sin:
                    nxt.append(inter(s, e, a, b))
                nxt.append(e)
            elif sin:
                nxt.append(inter(s, e, a, b))
            s = e
        out = nxt
    return out


def ccw(poly):
    return list(poly) if shoelace(poly) > 0 else list(reversed(poly))


def bary_in(p, tri):
    a, b, c = tri
    v0, v1, v2 = (c[0] - a[0], c[1] - a[1]), (b[0] - a[0], b[1] - a[1]), (p[0] - a[0], p[1] - a[1])
    den = cross(v0, v1)
    if abs(den) < 1e-18:
        return False
    u, v = cross(v2, v1) / den, cross(v0, v2) / den
    return u >= -1e-9 and v >= -1e-9 and u + v <= 1 + 1e-9


def embed(pts, mode, trans):
    out = []
    for x, y in pts:
        p = [x, y, 0.0] if mode == "xy" else [x, 0.0, y]
        out.append([p[0] + trans[0], p[1] + trans[1], p[2] + trans[2]])
    return out


def orient_poly(poly, winding, cyclic):
    pts = poly[cyclic:] + poly[:cyclic]
    return list(reversed(pts)) if winding == "cw" else pts


def call(fn, args):
    before = copy.deepcopy(args)
    try:
        result = fn(*args)
        err = None
    except Exception as e:
        result = None
        err = type(e).__name__ + ": " + str(e)
    return result, err, before == args


def match(src, out, shift):
    faces = [list(range(len(src)))]
    tri_f = [[0, 1, 2]]
    owners, err, same = call(q.match_source_faces, (src, faces, out, tri_f, shift))
    return owners, err, same, faces


def diagnose(src, out, shift):
    geo = q._poly_geo(src, [list(range(len(src)))])[0]
    ov = np.asarray(out, float) + np.asarray(shift, float)
    c = ov.mean(0)
    keep = [int(i) for i in geo["keep"]]

    def pin(p, tol):
        return bool(q._inside2d(np.asarray(p, float)[keep], geo["p2"], tol))

    qlo, qhi = ov.min(0), ov.max(0)
    return {
        "keep": keep,
        "plane_max": float(np.abs(ov @ geo["n"] - geo["d"]).max()),
        "bbox_reject": bool((qlo < geo["lo"] - 2e-4).any() or (qhi > geo["hi"] + 2e-4).any()),
        "corners": [pin(ov[i], 2e-4) for i in range(3)],
        "centroid_strict": pin(c, -1),
        "centroid": [float(x) for x in c],
    }


def finish_rep(args):
    """args = (expected, src_faces, owners, delivered, t_areas or None, p_areas or None)."""
    exp, src_f, owners, delivered, ta, pa = args
    kw_args = (exp, src_f, owners, delivered) if ta is None else (exp, src_f, owners, delivered, ta, pa)
    # source_finish_report takes t_areas, p_areas as keyword-capable positionals
    before = copy.deepcopy(kw_args)
    try:
        if ta is None:
            result = q.source_finish_report(exp, src_f, owners, delivered)
        else:
            result = q.source_finish_report(exp, src_f, owners, delivered, ta, pa)
        err = None
    except Exception as e:
        result = None
        err = type(e).__name__ + ": " + str(e)
    same = before == kw_args
    keys = ("ok", "tris", "wrong_finish", "unmatched", "ambiguous", "source_polygons_not_covered",
            "uncovered_examples", "examples")
    slim = None if result is None else {k: result[k] for k in keys}
    return slim, err, same


def prep(poly, tri, winding, cyclic, mode, shift_mode):
    trans = T3 if shift_mode in ("both", "undo") else (0.0, 0.0, 0.0)
    src_trans = trans if shift_mode == "both" else (0.0, 0.0, 0.0)
    out_trans = trans if shift_mode in ("both", "undo") else (0.0, 0.0, 0.0)
    shift = [-(trans[i] if shift_mode == "undo" else 0.0) for i in range(3)]
    src = embed(orient_poly(poly, winding, cyclic), mode, src_trans)
    out = embed(tri, mode, out_trans)
    return src, out, shift


def main():
    outlines = {"L": L, "U": U, "N": N, "CV": CV}
    outline_simple = {k: simple(v) for k, v in outlines.items()}
    grid = []
    exceptions = []
    n_calls = 0
    for name, poly, tri, bite, witness, kind in CASES:
        hits = proper_hits(tri, poly)
        outside = abs(shoelace(clip(ccw(tri), bite))) if bite else None
        if kind == "separated":
            outside = tri_area(tri)
        base_owner = None
        disagree = []
        n_var = 0
        base_diag = {}
        for cyclic in range(len(poly)):
            for winding in ("ccw", "cw"):
                for mode in ("xy", "xz"):
                    for shift_mode in ("zero", "both", "undo"):
                        src, out, shift = prep(poly, tri, winding, cyclic, mode, shift_mode)
                        owners, err, same, _ = match(src, out, shift)
                        n_calls += 1
                        n_var += 1
                        tag = f"{name}|c{cyclic}|{winding}|{mode}|{shift_mode}"
                        if err:
                            exceptions.append({"variant": tag, "error": err})
                            disagree.append(tag)
                            continue
                        if not same:
                            disagree.append(tag + "|MUTATED")
                        own = [list(t) for t in owners]
                        if base_owner is None and cyclic == 0 and winding == "ccw" and mode == "xy" and shift_mode == "zero":
                            base_owner = own
                            base_diag = diagnose(src, out, shift)
                            src_x, out_x, shift_x = prep(poly, tri, "ccw", 0, "xz", "zero")
                            base_diag["xz"] = diagnose(src_x, out_x, shift_x)
                        elif own != base_owner:
                            disagree.append({"variant": tag, "owner": own})
        grid.append({
            "id": name, "kind": kind, "poly": poly, "tri": tri, "witness": list(witness),
            "witness_in_tri": bary_in(witness, tri),
            "tri_area": tri_area(tri), "poly_area": abs(shoelace(poly)),
            "proper_hits": hits, "outside_area": outside,
            "variants": n_var, "owner": base_owner, "disagree": disagree, "diag": base_diag,
        })

    # Closed enumeration: every triangle of three L vertices. Not a search.
    enum = []
    for comb in itertools.combinations(range(len(L)), 3):
        tri = [L[i] for i in comb]
        src, out, shift = prep(L, tri, "ccw", 0, "xy", "zero")
        owners, err, same, _ = match(src, out, shift)
        n_calls += 1
        hits = proper_hits(tri, L)
        outside = abs(shoelace(clip(ccw(tri), NOTCH_L)))
        enum.append({
            "idx": list(comb), "tri": tri, "area": tri_area(tri), "owner": None if err else [list(t) for t in owners],
            "error": err, "inputs_unchanged": same, "proper_hits": len(hits), "outside_area": outside,
            "diag": None if err else diagnose(src, out, shift),
        })

    # Level 3 mesh, XY and XZ, shift zero, CCW.
    mesh_report = []
    for mode in ("xy", "xz"):
        src = embed(L, mode, (0, 0, 0))
        verts = []
        index = {}
        faces = []
        for tri in MESH:
            face = []
            for p in tri:
                key = (round(p[0], 9), round(p[1], 9))
                if key not in index:
                    index[key] = len(verts)
                    verts.append(p)
                face.append(index[key])
            faces.append(face)
        out = embed(verts, mode, (0, 0, 0))
        areas = [tri_area(t) for t in MESH]
        pair_overlap = []
        for i, j in itertools.combinations(range(len(MESH)), 2):
            ov = abs(shoelace(clip(ccw(MESH[i]), ccw(MESH[j]))))
            if ov > 1e-8:
                pair_overlap.append({"i": i, "j": j, "area": ov})
        covered_gap = any(bary_in(GAP_PT, t) for t in MESH)
        covered_witness = [i for i, t in enumerate(MESH) if bary_in((2.4, 2.4), t)]
        src_f = [list(range(len(src)))]
        owners, err, same = call(q.match_source_faces, (src, src_f, out, faces, [0.0, 0.0, 0.0]))
        n_calls += 1
        ta = None if err else q.tri_areas(out, faces)
        pa = None if err else q.poly_areas(src, src_f)
        own = None if err else [list(t) for t in owners]
        delivered = ["A"] * len(MESH)
        expected = ["A"]
        area_rep = count_rep = None
        area_err = count_err = None
        area_same = count_same = None
        if not err:
            area_rep, area_err, area_same = finish_rep((expected, src_f, owners, delivered, ta, pa))
            count_rep, count_err, count_same = finish_rep((expected, src_f, owners, delivered, None, None))
            n_calls += 2
        # geometry_report sees vertices, not faces. Include every L corner.
        soup = src + [p for p in out if min(np.linalg.norm(np.asarray(p) - np.asarray(s)) for s in src) > 1e-8]
        g_true, g_err_t, g_same_t = call(q.geometry_report, (src, src_f, soup, [0.0, 0.0, 0.0], True))
        g_false, g_err_f, g_same_f = call(q.geometry_report, (src, src_f, soup, [0.0, 0.0, 0.0], False))
        n_calls += 2
        mesh_report.append({
            "embed": mode, "n_tris": len(MESH), "sum_shoelace": sum(areas), "shoelace_each": areas,
            "pair_overlap": pair_overlap, "gap_point_in_any_tri": covered_gap,
            "witness_2_4_in_tris": covered_witness, "owner": own, "match_error": err, "inputs_unchanged": same,
            "tri_areas": ta, "poly_areas": pa,
            "area_mode": area_rep, "area_error": area_err, "area_inputs_unchanged": area_same,
            "count_mode": count_rep, "count_error": count_err, "count_inputs_unchanged": count_same,
            "geometry_cuts_true": g_true, "geometry_cuts_true_error": g_err_t, "geometry_cuts_true_unchanged": g_same_t,
            "geometry_cuts_false": g_false, "geometry_cuts_false_error": g_err_f,
        })

    # (1) single-triangle reports and (2) forced / contrived owners. Base XY.
    level12 = []
    for name in ("L_cross", "L_contained", "L_boundary", "conv_in", "conv_out"):
        row = next(r for r in grid if r["id"] == name)
        src, out, shift = prep(row["poly"], row["tri"], "ccw", 0, "xy", "zero")
        src_f = [list(range(len(src)))]
        owners, err, same, _ = match(src, out, shift)
        n_calls += 1
        ta = q.tri_areas(out, [[0, 1, 2]])
        pa = q.poly_areas(src, src_f)
        actual, aerr, asame = finish_rep((["A"], src_f, owners, ["A"], ta, pa))
        forced_actual, faerr, fasame = finish_rep((["A"], src_f, [(0,)], ["A"], ta, pa))
        forced_lie, flerr, flsame = finish_rep((["A"], src_f, [(0,)], ["A"], [pa[0]], [pa[0]]))
        n_calls += 3
        soup = src + out
        g_true, _, _ = call(q.geometry_report, (src, src_f, soup, shift, True))
        g_false, _, _ = call(q.geometry_report, (src, src_f, soup, shift, False))
        n_calls += 2
        level12.append({
            "id": name, "match_owner": None if err else [list(t) for t in owners], "match_error": err,
            "match_unchanged": same, "tri_areas": ta, "poly_areas": pa,
            "report_matcher_owners": actual, "report_matcher_error": aerr, "report_matcher_unchanged": asame,
            "forced_owner_real_areas": forced_actual, "forced_real_error": faerr, "forced_real_unchanged": fasame,
            "forced_owner_areas_set_equal": forced_lie, "forced_lie_error": flerr, "forced_lie_unchanged": flsame,
            "geometry_cuts_true": g_true, "geometry_cuts_false": g_false,
        })

    # Two source faces: L and a far quad. Crossing must not also own the quad.
    far = [(20, 0), (24, 0), (24, 3), (20, 3)]
    two = []
    for name, tri in (("L_cross", CASES[3][2]), ("far_in", [(20.5, 0.5), (23.5, 0.5), (22, 2.5)])):
        src = embed(L + far, "xy", (0, 0, 0))  # wrong: one vertex soup, two faces need separate index ranges
        # Build explicitly.
        src = [list(p) + [0.0] for p in L] + [list(p) + [0.0] for p in far]
        faces = [list(range(6)), list(range(6, 10))]
        out = [list(p) + [0.0] for p in tri]
        owners, err, same = call(q.match_source_faces, (src, faces, out, [[0, 1, 2]], [0.0, 0.0, 0.0]))
        n_calls += 1
        two.append({"id": name, "owner": None if err else [list(t) for t in owners], "error": err, "unchanged": same})

    accepted = [r["id"] for r in grid if r["owner"] == [[0]]]
    rejected = [r["id"] for r in grid if r["owner"] == [[]]]
    crossing_accepted = [r["id"] for r in grid if r["kind"] == "notch" and r["owner"] == [[0]] and r["outside_area"] > 1e-8]
    enum_cross_accepted = [e for e in enum if e["owner"] == [[0]] and e["outside_area"] > 1e-8]
    enum_cross_rejected = [e for e in enum if e["outside_area"] > 1e-8 and e["owner"] == [[]]]
    out_obj = {
        "tol_default": 2e-4,
        "outline_simple": outline_simple,
        "outline_areas": {k: abs(shoelace(v)) for k, v in outlines.items()},
        "grid": grid,
        "accepted_owner_0": accepted,
        "rejected_empty": rejected,
        "notch_accepted": crossing_accepted,
        "exceptions": exceptions,
        "match_calls_and_reports": n_calls,
        "vertex_triples": {
            "n": len(enum),
            "accepted_with_outside_area": [{k: e[k] for k in ("idx", "tri", "area", "owner", "proper_hits", "outside_area", "diag")} for e in enum_cross_accepted],
            "rejected_with_outside_area": len(enum_cross_rejected),
            "accepted_no_outside": sum(1 for e in enum if e["owner"] == [[0]] and e["outside_area"] <= 1e-8),
            "errors": sum(1 for e in enum if e["error"]),
        },
        "level12": level12,
        "mesh": mesh_report,
        "two_faces": two,
        "delivery_passed": False,
    }
    path = r"C:\x\t_66d99b9d\out.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out_obj, fh, indent=1)
    print(json.dumps({
        "simple": outline_simple,
        "accepted": accepted,
        "rejected": rejected,
        "notch_accepted": crossing_accepted,
        "exceptions": exceptions,
        "calls": n_calls,
        "disagree": {r["id"]: r["disagree"] for r in grid if r["disagree"]},
        "enum_cross_accepted": len(enum_cross_accepted),
        "enum_cross_rejected": len(enum_cross_rejected),
        "mesh_xy_area_ok": mesh_report[0]["area_mode"],
        "mesh_xy_overlap": mesh_report[0]["pair_overlap"],
        "mesh_xy_owners_unique": sorted({tuple(o) for o in (mesh_report[0]["owner"] or [])}),
        "two": two,
    }, default=str))


if __name__ == "__main__":
    main()
```

## Proposed next tasks

Proposals only. They do not change `tol`, do not choose a new boundary policy, and do not edit production, tests, gates or procedures in this note.

1. **Reject a delivered edge that properly intersects a source edge**, size S, Advances #149 (number copied from `docs/research/source-finish-stream-cardinality.md`). In `match_source_faces`, after the existing corner and centroid tests, skip a hit when any delivered edge meets a source edge in the kept plane with both parameters in `(0, 1)`. Leave `tol=2e-4` as it is. Acceptance pair: L with triangle `(0.4, 0.4), (5.5, 0.4), (3, 1.5)` still returns owner `(0,)`; L with triangle `(0.5, 0.5), (0.5, 4.5), (4.5, 0.5)`, whose edge meets the source at `(2, 3)` and `(3, 2)`, returns `()`. The same empty owner is required for L_boundary `(0, 1), (0, 5), (5, 0)`. Regression belongs next to the existing TEC26 ownership tests. Value: the four accepted notch crossings in this note become unmatched, so the 11-triangle area sum loses the area-8 triangle and area mode stops returning ok. Effort S because the plane projection and the edge list are already in the function.

2. **Area-mode fixture for this mesh, without turning ring-cut covers back into count mode**, size M, Advances #149 (same copied number). Add a regression whose input is the 11 triangles in `MESH` and whose `source_finish_report` area-mode result must be `ok false` once proposal 1 is in place, while `tests/jobs/test_source_finish_area_count_controls.py::test_area_mode_three_triangles_cover_quad` stays ok true on its contained quad. Acceptance pair for the matcher half of the same change: the clean L triangle above keeps owner `(0,)`; the notch-crossing triangle above gets no owner. Value: locks the mask this probe measured (area mode ok true, count mode ok false, owners from the real matcher) so a later edit cannot keep the sum check as the only geometric cover. Effort M because the fixture is an 11-triangle mesh and the existing area-mode quad split has to stay green. The band `1e-6 + 1e-5 * area` stays as written at `qa_packages.py:154`.

## Open questions for the user

1. The card asked for two source-finish reports. Only `docs/research/source-finish-stream-cardinality.md` is present. Does a missing second note constrain this result?
2. `geometry_report` with cuts allowed returns ok for L_boundary, and area mode returns ok false for that single triangle (10 against 20). A complete on-edge triangulation that crosses the notch and still sums to area 20 was not built. Do you want that measured before any code change?
3. Advances #149 is taken from the stream-cardinality note. If this containment hole should not share that issue, say so; this card did not look up the issue list.
