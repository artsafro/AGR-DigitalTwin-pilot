# Source face containment: an on-edge mesh can pass area and vertex checks while leaving the notch

Research card (no GitHub issue). Follow-up left open by the concave-containment note: a complete delivery whose vertices lie on the source, with one triangle crossing the notch. Synthetic L only. `delivery_passed=false`. Git was not run. `main()` was not run. The 768 sample-stability calls and the interior-vertex mesh from that note were not repeated.

The prior note was read from the sibling worktree file `docs/research/source-face-concave-containment.md` (its open question 2). Code citations are this worktree's `jobs/TEC26-OKS/scripts/qa_packages.py`.

## Summary

A frozen 6-triangle delivery on the L passes `match_source_faces`, area-mode `source_finish_report` and `geometry_report(cuts_allowed=True)` together, in XY and in XZ.
Triangle 0 is the known chord `(0,1), (0,5), (5,0)`: notch clip 0.5, and an interior sliver of area 0.5 stays uncovered.
The six triangles do not overlap; their areas sum to 20, the polygon area. Source corner `(2,2)` is stored and is not a face corner.
The chord alone has containment owner `(0,)`, geometry ok, area-mode not ok. A contained 4-triangle control passes both checks with exterior 0.
Adding the sliver back (sum 20.5) makes area-mode not ok. These are helper calls. `main()` was not run. `delivery_passed=false`.
Frozen corpus: 4 deliveries × 2 embeddings, 1 outline, 6 boundary points, 0.065 s. One witness on that corpus.

## Findings

Marks: **run** = this probe's printed JSON. **read** = this worktree's `qa_packages.py`, not executed as `main()`.

### Oracle assumptions (separate from the checker)

The L is the union of rectangle A `[0,2]×[0,6]` and rectangle B `[2,6]×[0,2]`. Those rectangles meet on the segment `x=2`, `y∈[0,2]`, which has area 0. Inside the square `[0,6]²` the complement is the notch `[2,6]×[2,6]`. Shoelace of the CCW outline is 20 (**run**), and `2×6 + 4×2 = 20`.

Intersection area is absolute shoelace after Sutherland–Hodgman clipping. The clip polygon is forced CCW. A self-check passed before the cases: the right triangle `(0,0),(1,0),(0,1)` has area 0.5 against the unit square, and two triangles that only share an edge clip to area below `1e-8` (**run**). Proper segment hits require both parameters in `(0,1)`. `_inside2d` is not this oracle.

Because the chord triangle's corners lie in the square and a triangle is convex, the chord triangle lies in the square. Its area therefore splits into L plus notch. Measured split: shoelace 10, notch clip 0.5, rectangle-union clip 9.5 (**run**).

Identity used only for this mesh, after the oracle numbers: if triangles are pairwise interior-disjoint, each lies in `L ∪ notch`, the sum of areas equals `|L|`, and the notch measure is `E`, then the uncovered interior measure equals `E`. Here `E = 0.5` and the uncovered interior is 0.5. The area helper compares a sum with a band. It does not receive `E`.

### Frozen corpus (run)

Outline, CCW: `(0,0), (6,0), (6,2), (2,2), (2,6), (0,6)`.

Boundary points, declared before the calls: `(0,1), (0,5), (5,0), (2,3), (3,2), (4,0)`. The first three are the known chord. `(2,3)` and `(3,2)` are its proper hits. `(4,0)` is the split that leaves the sliver out.

Deliveries, and nothing else:

| id | faces on the vertex list below | role |
|---|---|---|
| control | 4 triangles on the 6 corners | contained cover |
| single_crossing | one chord; 6 corners present and unreferenced | known single triangle |
| candidate | 6 triangles; corner `(2,2)` present and unreferenced | witness |
| contrast_with_sliver | candidate plus the sliver | area-sum contrast |

Vertex indices for candidate and contrast: `0 (0,0), 1 (6,0), 2 (6,2), 3 (2,2), 4 (2,6), 5 (0,6), 6 (0,1), 7 (0,5), 8 (5,0), 9 (2,3), 10 (3,2), 11 (4,0)`.

Candidate faces: `(6,7,8), (7,5,4), (7,4,9), (0,11,6), (10,2,1), (10,1,8)`.

Omitted sliver, not a candidate face: `(0,1), (4,0), (5,0)`, index triple `(6,11,8)`.

Control faces on the six corners: `(0,1,2), (0,2,3), (0,3,5), (3,4,5)`.

Single-crossing vertices are the six corners plus `(0,1),(0,5),(5,0)`, one face `(6,7,8)`.

Each delivery was embedded as XY `(x,y,0)` and XZ `(x,0,z)` with `z` equal to the 2D `y`. Shift `[0,0,0]`. One source face, indices `0..5`. `expected=["A"]`, delivered finish `"A"` on every triangle. Default `tol` is `2e-4` (`inspect.signature`); the probe never passes `tol`. No tolerance search. Runtime 0.065 s. Inputs compared by deep copy stayed unchanged on every call. No exceptions.

Chord `(0,5)–(5,0)` has two proper hits (**run**): edge `(6,2)–(2,2)` at `(3,2)` with chord parameter 0.6, and edge `(2,2)–(2,6)` at `(2,3)` with chord parameter 0.4. Point `(2.2, 2.2)` is strictly inside the chord triangle and strictly inside the notch, and outside both bars. Point `(3, 1/3)` is strictly inside the bottom bar and strictly inside the sliver.

### Control (run)

Oracle: shoelace areas `[6, 4, 6, 4]`, sum 20, notch clips all 0, covered interior 20, uncovered 0, overlap pairs empty. All six corners are referenced.

XY and XZ, same dicts:

Owners `[(0,), (0,), (0,), (0,)]`.

`tri_areas` `[6.0, 4.0, 6.0, 4.0]`, `poly_areas` `[20.0]`.

Area mode: `{"ok": true, "tris": 4, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 0, "uncovered_examples": [], "examples": []}`.

Count mode: the same `ok: true` dict (`6-2 = 4` visited triangles).

`geometry_report(..., cuts_allowed=True)`: `{"ok": true, "missing_source_vertices": 0, "new_vertices": 0, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}`.

### Single crossing (run)

Oracle: shoelace 10, notch 0.5, covered interior 9.5, uncovered interior 10.5. Referenced corners are only `(0,1), (0,5), (5,0)`. The six source corners sit in the vertex list and are unused.

XY and XZ: owner `[(0,)]`. That owner is the wrong containment owner: the notch clip is 0.5 and two proper boundary hits exist. Finish counters stay 0 because delivered `"A"` matches `expected`.

Area mode: `{"ok": false, "tris": 1, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 1, "uncovered_examples": [0], "examples": []}`.

`|10-20|` is above the band `1e-6 + 1e-5 * 20 = 0.000201` (**read** of `qa_packages.py:154`, applied to the measured areas).

Geometry with cuts allowed: `{"ok": true, "missing_source_vertices": 0, "new_vertices": 3, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}`.

### Candidate witness (run)

Oracle: shoelace `[10, 1, 3, 2, 3, 1]`, sum 20, notch clips `[0.5, 0, 0, 0, 0, 0]`, exterior 0.5, rectangle clips `[9.5, 1, 3, 2, 3, 1]`, covered interior 19.5, uncovered interior 0.5, overlap pairs empty.

The sliver's shoelace is 0.5 and its notch clip is 0. Its clip area against each candidate triangle is at most `1e-8` (the overlap list is empty). `(3, 1/3)` lies in no candidate triangle. `(2.2, 2.2)` lies only in candidate triangle 0. The uncovered interior measure equals the sliver area.

Inventory: all six source corners are present. Referenced corners are every vertex except index 3, `(2,2)`. That unused vertex is a source corner. `geometry_report` still reports `missing_source_vertices: 0` (**run**). **Read:** missing is a count of source positions absent from the rounded delivery coordinates (`qa_packages.py:162-167`), so an unreferenced corner that is present in the array satisfies that count.

XY and XZ, same dicts:

Owners six times `(0,)`. Triangle 0 keeps the wrong containment owner while the other five stay inside the bars (notch clip 0 and rectangle clip equal to shoelace).

`tri_areas` equals the shoelace list. `poly_areas` is `[20.0]`.

Area mode: `{"ok": true, "tris": 6, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 0, "uncovered_examples": [], "examples": []}`.

Count mode: `{"ok": false, "tris": 6, "wrong_finish": 0, "unmatched": 0, "ambiguous": 0, "source_polygons_not_covered": 1, "uncovered_examples": [0], "examples": []}`. **Read:** count mode wants `len(face)-2 = 4` triangles (`qa_packages.py:156`). Six visited triangles fail that test. Production callers pass both area lists (`qa_packages.py:409-413`), so the passing path is the area path.

Geometry with cuts allowed: `{"ok": true, "missing_source_vertices": 0, "new_vertices": 6, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}`. The six new vertices are the six boundary points. `(2,2)` is not among them.

### Contrast, sliver included (run)

Oracle: seven areas summing to 20.5, exterior still 0.5, covered interior 20.0, uncovered 0.0, overlap pairs empty. The sliver's rectangle clip printed `0.4999999999999999` (one binary rounding off 0.5). The summed covered interior still printed 20.0.

XY and XZ: owners seven times `(0,)`. `tri_areas` ends with `0.5`. Area mode `ok: false`, `source_polygons_not_covered: 1`, because `|20.5-20|` exceeds `0.000201`. Geometry stays `ok: true` with `new_vertices: 6` (the sliver reuses points already on edges). Count mode is also `ok: false`.

The area pass on the candidate is the omission of this interior 0.5, which balances the notch spill of 0.5.

### Helper triple versus package execution (read)

`main` calls `geometry_report` at `320-322` with `cuts_allowed=bool(spec.get("ring_cuts"))`, and the recorded check is `g["ok"] and tris >= src_tris`. `src_tris` is `sum(len(f)-2)` over source faces (`311`), which is 4 for this hexagon. There is no `return` between that call and `source_finish_report` at `410-413`. The early return at `287-289` is only when a named mesh is missing, and it sits before both calls. Area mode is what those lines pass (`tri_areas` and `poly_areas`). `cut_joint_report` follows at `414-416`. Exit 0 requires every later check as well (`493`, docstring lines 14-15): names, budget, UV, xView, colour, joints, ZIP, PNG.

`main()` was not executed. Substituting the measured helper fields into the geometry expression, still without calling it:

| delivery | `g["ok"]` from the run | `tris >= 4` | area-mode `ok` from the run |
|---|---|---|---|
| control | true | 4 ≥ 4 | true |
| single crossing | true | 1 ≥ 4 is false | false |
| candidate | true | 6 ≥ 4 | true |
| contrast | true | 7 ≥ 4 | false |

Those substitutions assume `ring_cuts` is true, because the probe passed `cuts_allowed=True` itself. A spec without `ring_cuts` would pass false into `geometry_report` (`320`). `cut_joint_report` and the ZIP checks were not called. `delivery_passed=false`.

## How it applies to this repository

- Matcher, corner test with `tol` and strict centroid: `jobs/TEC26-OKS/scripts/qa_packages.py:95-116` (centroid at line 113).
- Area sum versus `1e-6 + 1e-5 * polygon_area`, and the count rule `len(face)-2`: `qa_packages.py:128-159` (area add `141-144`, band `153-154`, count `156`).
- Vertex gate, including source corners that need only be present: `qa_packages.py:162-184`.
- Package order that this probe did not execute: geometry `320-322`, source finish `404-413`, joints `414-416`, final return `493`.
- The prior interior-vertex cover that area-mode accepted and `geometry_report` rejected is the 11-triangle mesh in the concave-containment note. This witness replaces those interior corners with boundary points, so the vertex gate accepts it too.

## Proposed next tasks

No change to containment, `tol`, ring-cut policy, or delivery acceptance is proposed here.

1. **Pin this helper witness as a current-behavior fixture**, value M / effort S, Advances #149 (the number already used in `docs/research/source-finish-stream-cardinality.md`; `gh issue list` was not run). Add a test that builds the candidate arrays in the reproducer and calls the three helpers. Input: candidate vertices and faces, XY, shift `[0,0,0]`, `expected=["A"]`, delivered `["A"]*6`, `cuts_allowed=True`. Expected output: owners six times `(0,)`, area-mode `ok true` with `source_polygons_not_covered 0`, geometry `ok true` with `missing_source_vertices 0` and `new_vertices 6`. The same test keeps an oracle assertion that triangle 0 clips to notch area 0.5 and that sliver `(0,1),(4,0),(5,0)` has shoelace 0.5 and clip area 0 against each delivered triangle. The fixture records the exposure. It does not flip the expected `ok` flags.

2. **Pin count mode on the same arrays**, value S / effort S, Advances #149 (same copied number). Input: the candidate owners and `delivered=["A"]*6`, calling `source_finish_report` with `t_areas=None` and `p_areas=None`. Expected output: `ok false`, `tris 6`, `source_polygons_not_covered 1`, `uncovered_examples [0]`. Value: a later edit can see that the exposure is the area path, which is the path `qa_packages.py:410-413` uses, while count mode already returns not ok on this mesh.

## Open questions for the user

1. Should the candidate stay a docs-only witness until you decide whether an area-mode sum must also be an interior cover, or should proposal 1 land as a fixture of today's helper output?
2. The helper triple was measured directly. Package `main()` was not run, and its geometry check also depends on `spec["ring_cuts"]` and `tris >= src_tris` before UV, colour, joints and ZIP. Do you want a later package-level probe of this mesh, or is the helper triple the input you wanted?

## Reproduction

Probe file used for the run, outside the repo: `C:/x/t_6812d246/onedge_probe.py`. From this worktree:

`uv run python C:/x/t_6812d246/onedge_probe.py jobs/TEC26-OKS/scripts`

```python
"""Frozen on-edge cover probe. Usage: uv run python onedge_probe.py <jobs/TEC26-OKS/scripts>

Corpus is the literals below. No tolerance loop, no extra candidates.
"""
import copy, inspect, json, os, sys, time

sys.path.insert(0, sys.argv[1])
import qa_packages as q

assert inspect.signature(q.match_source_faces).parameters["tol"].default == 2e-4

# Frozen L, CCW. Notch rectangle [2,6] x [2,6] is the exterior of this L inside [0,6]^2.
L = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6)]
# Frozen boundary points: the known chord plus its two proper hits and one bottom split.
SUB = [(0, 1), (0, 5), (5, 0), (2, 3), (3, 2), (4, 0)]
RECT_A = [(0, 0), (2, 0), (2, 6), (0, 6)]  # left bar
RECT_B = [(2, 0), (6, 0), (6, 2), (2, 2)]  # bottom bar
NOTCH = [(2, 2), (6, 2), (6, 6), (2, 6)]
SHIFT = [0.0, 0.0, 0.0]
WITNESS = (2.2, 2.2)          # exterior, inside the known chord triangle
GAP = (3.0, 1.0 / 3.0)        # interior point of the omitted sliver
SLIVER = [(0, 1), (4, 0), (5, 0)]

# name -> (xy vertices, faces). Source corners are always the first 6 of every list that includes them.
CONTROL_V = list(L)
CONTROL_F = [[0, 1, 2], [0, 2, 3], [0, 3, 5], [3, 4, 5]]
SINGLE_V = list(L) + SUB[:3]
SINGLE_F = [[6, 7, 8]]
CAND_V = list(L) + list(SUB)
CAND_F = [[6, 7, 8], [7, 5, 4], [7, 4, 9], [0, 11, 6], [10, 2, 1], [10, 1, 8]]
CONTRAST_V = list(CAND_V)
CONTRAST_F = list(CAND_F) + [[6, 11, 8]]  # adds the sliver; area sum 20.5


def shoelace(poly):
    s = 0.0
    for i, (x, y) in enumerate(poly):
        x2, y2 = poly[(i + 1) % len(poly)]
        s += x * y2 - x2 * y
    return 0.5 * s


def ccw(poly):
    return list(poly) if shoelace(poly) > 0 else list(reversed(poly))


def seg_hit(p, q, a, b):
    def cross(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    den = (q[0] - p[0]) * (b[1] - a[1]) - (q[1] - p[1]) * (b[0] - a[0])
    if den == 0:
        return None
    t = cross(p, a, b) / den
    u = cross(a, p, q) / ((b[0] - a[0]) * (q[1] - p[1]) - (b[1] - a[1]) * (q[0] - p[0]))
    # t is along pq, u along ab; both open
    if 0 < t < 1 and 0 < u < 1:
        return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), t, u)
    return None


def clip(subject, clip_poly):
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= -1e-12

    def meet(p, r, a, b):
        rx, ry = r[0] - p[0], r[1] - p[1]
        sx, sy = b[0] - a[0], b[1] - a[1]
        den = rx * sy - ry * sx
        t = ((a[0] - p[0]) * sy - (a[1] - p[1]) * sx) / den
        return (p[0] + t * rx, p[1] + t * ry)

    out = list(subject)
    c = ccw(clip_poly)
    for i in range(len(c)):
        a, b = c[i], c[(i + 1) % len(c)]
        if not out:
            break
        nxt, prev = [], out[-1]
        for cur in out:
            if inside(cur, a, b):
                if not inside(prev, a, b):
                    nxt.append(meet(prev, cur, a, b))
                nxt.append(cur)
            elif inside(prev, a, b):
                nxt.append(meet(prev, cur, a, b))
            prev = cur
        out = nxt
    return out


def area_cap(poly, region):
    return abs(shoelace(clip(poly, region)))


def tri_area(tri):
    return abs(shoelace(tri))


def bary(p, tri):
    (ax, ay), (bx, by), (cx, cy) = tri
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    u = ((by - cy) * (p[0] - cx) + (cx - bx) * (p[1] - cy)) / den
    v = ((cy - ay) * (p[0] - cx) + (ax - cx) * (p[1] - cy)) / den
    w = 1 - u - v
    return u, v, w


def strict_in_tri(p, tri, eps=1e-9):
    u, v, w = bary(p, tri)
    return u > eps and v > eps and w > eps


def in_rect(p, lo, hi, eps=1e-9):
    return lo[0] + eps < p[0] < hi[0] - eps and lo[1] + eps < p[1] < hi[1] - eps


def tris_of(verts, faces):
    return [[verts[i] for i in f] for f in faces]


def embed(xy, mode):
    if mode == "xy":
        return [[float(x), float(y), 0.0] for x, y in xy]
    return [[float(x), 0.0, float(y)] for x, y in xy]


def oracle(verts, faces):
    tris = tris_of(verts, faces)
    areas = [tri_area(t) for t in tris]
    notch = [area_cap(t, NOTCH) for t in tris]
    covered_parts = [area_cap(t, RECT_A) + area_cap(t, RECT_B) for t in tris]
    pairs = []
    for i in range(len(tris)):
        for j in range(i + 1, len(tris)):
            ij = area_cap(tris[i], tris[j])
            if ij > 1e-8:
                pairs.append([i, j, ij])
    covered = sum(covered_parts)
    return {
        "tri_shoelace": areas,
        "shoelace_sum": sum(areas),
        "notch_clip": notch,
        "exterior": sum(notch),
        "clip_L_via_rects": covered_parts,
        "covered_interior": covered,
        "uncovered_interior": 20.0 - covered,
        "overlap_pairs": pairs,
        "pairwise_nonoverlap": not pairs,
    }


def inventory(verts, faces):
    used = sorted({i for f in faces for i in f})
    unused = [i for i in range(len(verts)) if i not in set(used)]
    return {
        "n_vertices": len(verts),
        "referenced_corners": [(i, verts[i]) for i in used],
        "unused_vertices": [(i, verts[i]) for i in unused],
        "unused_are_source_corners": all(i < 6 for i in unused),
        "source_corners_present": verts[:6] == L,
    }


def call(fn, args):
    before = copy.deepcopy(args)
    out = fn(*args)
    return out, before == args


def run_case(name, xy, faces):
    ora = oracle(xy, faces)
    inv = inventory(xy, faces)
    out = {"name": name, "oracle": ora, "inventory": inv, "embeddings": {}}
    for mode in ("xy", "xz"):
        src = embed(L, mode)
        ov = embed(xy, mode)
        src_f = [list(range(6))]
        shift = list(SHIFT)
        owners, same_m = call(q.match_source_faces, (src, src_f, ov, faces, shift))
        t_areas, same_t = call(q.tri_areas, (ov, faces))
        p_areas, same_p = call(q.poly_areas, (src, src_f))
        delivered = ["A"] * len(faces)
        area_rep, same_a = call(
            q.source_finish_report, (["A"], src_f, owners, delivered, t_areas, p_areas))
        count_rep, same_c = call(
            q.source_finish_report, (["A"], src_f, owners, delivered))
        geo, same_g = call(
            q.geometry_report, (src, src_f, ov, shift, True))
        out["embeddings"][mode] = {
            "owners": [list(t) for t in owners],
            "owners_unique_0": all(t == (0,) for t in owners),
            "tri_areas": t_areas,
            "poly_areas": p_areas,
            "area_mode": area_rep,
            "count_mode": count_rep,
            "geometry_cuts_true": geo,
            "inputs_unchanged": all((same_m, same_t, same_p, same_a, same_c, same_g)),
        }
    return out


def self_test():
    unit = [(0, 0), (1, 0), (0, 1)]
    assert abs(tri_area(unit) - 0.5) < 1e-12
    assert abs(area_cap(unit, [(0, 0), (1, 0), (1, 1), (0, 1)]) - 0.5) < 1e-12
    assert abs(shoelace(L) - 20) < 1e-12
    assert abs(2 * 6 + 4 * 2 - 20) < 1e-12
    # shared-edge triangles: intersection area ~ 0
    a = [(0, 0), (2, 0), (0, 2)]
    b = [(0, 0), (0, 2), (-1, 1)]
    assert area_cap(a, b) < 1e-8


def main():
    t0 = time.perf_counter()
    self_test()
    hits = []
    chord = (SUB[1], SUB[2])  # (0,5)-(5,0)
    for i in range(6):
        h = seg_hit(chord[0], chord[1], L[i], L[(i + 1) % 6])
        if h:
            hits.append({"edge": [L[i], L[(i + 1) % 6]], "point": [h[0], h[1]], "t": h[2], "u": h[3]})
    tri = [SUB[0], SUB[1], SUB[2]]
    report = {
        "seconds": None,
        "L_shoelace": shoelace(L),
        "chord_proper_hits": hits,
        "chord_tri_shoelace": tri_area(tri),
        "chord_notch": area_cap(tri, NOTCH),
        "witness_in_chord": strict_in_tri(WITNESS, tri),
        "witness_in_notch": in_rect(WITNESS, (2, 2), (6, 6)),
        "witness_in_L_rects": in_rect(WITNESS, (0, 0), (2, 6)) or in_rect(WITNESS, (2, 0), (6, 2)),
        "gap_in_L_bottom": in_rect(GAP, (2, 0), (6, 2)),
        "gap_in_sliver": strict_in_tri(GAP, SLIVER),
        "sliver_shoelace": tri_area(SLIVER),
        "sliver_notch": area_cap(SLIVER, NOTCH),
        "cases": [
            run_case("control", CONTROL_V, CONTROL_F),
            run_case("single_crossing", SINGLE_V, SINGLE_F),
            run_case("candidate", CAND_V, CAND_F),
            run_case("contrast_with_sliver", CONTRAST_V, CONTRAST_F),
        ],
    }
    # sliver vs candidate triangles
    cand_tris = tris_of(CAND_V, CAND_F)
    report["sliver_overlap_candidate"] = [
        [i, area_cap(SLIVER, t)] for i, t in enumerate(cand_tris) if area_cap(SLIVER, t) > 1e-8
    ]
    report["gap_in_candidate_tris"] = [i for i, t in enumerate(cand_tris) if strict_in_tri(GAP, t)]
    report["witness_in_candidate_tris"] = [i for i, t in enumerate(cand_tris) if strict_in_tri(WITNESS, t)]
    report["seconds"] = time.perf_counter() - t0
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
```
