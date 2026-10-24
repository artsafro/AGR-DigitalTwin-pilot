# Source QA: do raw malformed faces survive ownership and area checks?

Research card (question from the malformed-geometry witnesses on PR #654). This note does not re-investigate the Ground checker repair or `invariants.Mesh` coercion. Pinned worktree ref `docs/research-source-qa-raw-topology-boundary` = `176fdad325e2df74f56403491373bd2ca4ad2c14` (read from `.git/refs/heads/docs/research-source-qa-raw-topology-boundary`). `git` was not run. No pytest, no `qa_packages.main`, no ZIP/PNG, no TEC26 asset, no DCC. `delivery_passed=false`.

Probe: CPython 3.14.7, numpy 2.5.3, `uv run python C:/x/t_2129c17c/probe_raw_topology.py`. Results: `C:/x/t_2129c17c/probe_results.json`. A second `uv run python` printed the boolean-index shapes below. Every case left its vertex and face lists unchanged.

## Summary

The frozen control is one unit-square source quad and two delivered triangles, shift `[0, 0, 0]`. It returns owners `[(0,), (0,)]`, areas `[0.5, 0.5]` / `[1.0]`, and `source_finish_report` `ok` true.

Source indices are Python-list lookups (`qa_packages.py:63`). Negative indices that name the same four corners are accepted, and the finish report stays `ok` true. `assign_finishes` on a plain finish rule never reads the face, so it returns `["A"]`. `mesh_report` sees only the clean delivery and returns `passed` true. No executed gate aborts that row.

`tri_areas` reads only corners 0, 1 and 2 (`qa_packages.py:121`). One delivered quad of the same square is measured as area `0.5` against polygon area `1.0`, and the report is `ok` false. That same quad followed by the remaining half-triangle is measured as `[0.5, 0.5]`, the sum matches `[1.0]`, and the report is `ok` true, while the full polygon areas of those two faces are `1.0` and `0.5`. `mesh_report` on that pair returns `passed` false and does not raise. `main` records `triangulated_*` and `xview_*` and continues (`qa_packages.py:275-278`, `:292`, `:297`).

Delivered negatives, out-of-range indices, floats, booleans, faces shorter than 3, and repeated indices raise in `mesh_report` before the finish report. Those isolated helper successes are not package verdicts. `main()` was not executed. No delivery package was witnessed.

## Findings

Evidence: **Verified by run** = the probe above. **Source** = read from the pinned file, not executed as that case. Report columns are `ok / tris / wrong_finish / unmatched / ambiguous / source_polygons_not_covered`.

### Frozen inputs

Vertices, both sides unless a row replaces one side: `(0,0,0), (1,0,0), (1,1,0), (0,1,0)`. Source faces `[[0, 1, 2, 3]]`. Delivery `[[0, 1, 2], [0, 2, 3]]`. Shift `[0, 0, 0]`. Spec `{"source_ids": {"1": {"finish": "A"}}, "zero_m": 0.0}`, material ids `[1]`. Expected and delivered finish names are `"A"`. The plain rule does not take the `below_zero` / `facade` index paths (`finish_map.py:335-344`).

**Verified by run.** Control: `_poly_geo` / `poly_areas` `[1.0]`, owners `[(0,), (0,)]`, `tri_areas` `[0.5, 0.5]`, report `true / 2 / 0 / 0 / 0 / 0`. `all(len(f) == 3)` is true. `mesh_report(..., profile="VPM")` returns `passed` true, count 0. `assign_finishes` returns `["A"]`.

### Where a face index is read

**Source.**

- Source polygons: `_poly_geo` indexes the original vertex list (`qa_packages.py:63`). `poly_areas` and `match_source_faces` call that (`:100`, `:124-125`). A zero Newell length becomes `None`, then area `0.0` (`:68-71`, `:125`).
- Delivered ownership: `ov[list(f)]` uses every index in the face (`:104`).
- Delivered area: `tri_areas` uses `f[0]`, `f[1]`, `f[2]` only (`:121`).
- The report adds that area when `len(own) == 1` (`:141-144`) and treats a polygon as covered when `abs(sum - p) > 1e-6 + 1e-5 * p` is false (`:153-154`). `ok` is false when any counter is non-zero or `owners` is empty (`:157`).
- `assign_finishes` checks that every vertex has three finite components (`finish_map.py:314-317`). On the plain rule it does not read face indices (`:344`).
- `mesh_report` builds a `PolyMesh` (`inv_xview.py:566-575`). `PolyMesh` rejects a bool, a non-integer, fewer than 3 indices, an index outside `0 .. len(vertices)-1`, and a repeated index (`inv_quads.py:74-85`). A 4-index face is legal there. `mesh_report` does not raise when the overlap count is non-zero; it returns `passed` false (`inv_xview.py:577`).
- In `main`, `triangulated_*` is `all(len(f) == 3)` (`qa_packages.py:292`). `check` stores a failure and continues (`:275-278`). `mesh_report` is next (`:297`). `assign_finishes`, `match_source_faces`, `poly_areas`, `tri_areas` and `source_finish_report` are later (`:403-413`). An exception from `mesh_report` or `assign_finishes` is uncaught. Image and ZIP reads sit between `mesh_report` and `assign_finishes` (`:361-363`) and were not executed.

### Per-case results

`full face area` is `_poly_geo` on the delivered faces (every corner). `package-order finish` is the finish report only when `mesh_report` and `assign_finishes` both returned on these arrays. When either raised, the finish report was not executed. Isolated helper results are a separate column and are not a substitute verdict.

| case | poly area | owners | tri areas | full face area | isolated finish report | len==3 | mesh_report | assign | package-order finish |
|---|---|---|---|---|---|---|---|---|---|
| control | 1.0 | `(0,) (0,)` | 0.5, 0.5 | 0.5, 0.5 | true / 2 / 0 / 0 / 0 / 0 | true | passed true | `["A"]` | true / 2 / 0 / 0 / 0 / 0 |
| source `[-4,-3,-2,-1]` | 1.0 | `(0,) (0,)` | 0.5, 0.5 | 0.5, 0.5 | **true / 2 / 0 / 0 / 0 / 0** | true | passed true | `["A"]` | **true / 2 / 0 / 0 / 0 / 0** |
| delivered `[-4,-3,-2], [-4,-2,-1]` | 1.0 | `(0,) (0,)` | 0.5, 0.5 | 0.5, 0.5 | true / 2 / 0 / 0 / 0 / 0 | true | ValueError: face 0: index outside the vertices | `["A"]` | not executed after mesh_report |
| source `[0,1,2,4]` | IndexError: list index out of range | same IndexError | 0.5, 0.5 | 0.5, 0.5 | not executed | true | passed true | `["A"]` | not executed after match (IndexError) |
| delivered `[0,1,4], [0,2,3]` | 1.0 | IndexError: index 4 is out of bounds for axis 0 with size 4 | same IndexError | IndexError: list index out of range | not executed | true | ValueError: face 0: index outside the vertices | `["A"]` | not executed after mesh_report |
| source `[0.0,1.0,2.0,3.0]` | TypeError: list indices must be integers or slices, not float | same TypeError | 0.5, 0.5 | 0.5, 0.5 | not executed | true | passed true | `["A"]` | not executed after match (TypeError) |
| delivered `[0.0,1.0,2.0], [0.0,2.0,3.0]` | 1.0 | IndexError: only integers, slices … are valid indices | same IndexError | TypeError: list indices … not float | not executed | true | ValueError: face 0: index 0.0 is not an integer | `["A"]` | not executed after mesh_report |
| source `[0.5,1.0,2.0,3.0]` | TypeError: list indices … not float | same TypeError | 0.5, 0.5 | 0.5, 0.5 | not executed | true | passed true | `["A"]` | not executed after match (TypeError) |
| delivered `[0.5,1.0,2.0], [0.0,2.0,3.0]` | 1.0 | IndexError: only integers, slices … are valid indices | same IndexError | TypeError: list indices … not float | not executed | true | ValueError: face 0: index 0.5 is not an integer | `["A"]` | not executed after mesh_report |
| source `[True, False, 2, 3]` | 0.0 (`_poly_geo` None) | `() ()` | 0.5, 0.5 | 0.5, 0.5 | false / 2 / 0 / 2 / 0 / **0** | true | passed true | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| delivered `[False, True, 2], [0,2,3]` | 1.0 | `(0,) (0,)` | **0.0**, 0.5 | 0.5, 0.5 | false / 2 / 0 / 0 / 0 / 1 | true | ValueError: face 0: index False is not an integer | `["A"]` | not executed after mesh_report |
| source `[[]]` | 0.0 | `() ()` | 0.5, 0.5 | 0.5, 0.5 | false / 2 / 0 / 2 / 0 / **0** | true | passed true | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| source `[[0]]` | 0.0 | `() ()` | 0.5, 0.5 | 0.5, 0.5 | false / 2 / 0 / 2 / 0 / **0** | true | passed true | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| source `[[0,1]]` | 0.0 | `() ()` | 0.5, 0.5 | 0.5, 0.5 | false / 2 / 0 / 2 / 0 / **0** | true | passed true | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| delivered `[], [0,2,3]` | 1.0 | ValueError: zero-size array to reduction operation minimum which has no identity | IndexError: list index out of range | None, 0.5 | not executed | false | ValueError: face 0: fewer than 3 sides | `["A"]` | not executed after mesh_report |
| delivered `[[0]], [0,2,3]` | 1.0 | `(0,) (0,)` | IndexError: list index out of range | None, 0.5 | not executed after tri_areas | false | ValueError: face 0: fewer than 3 sides | `["A"]` | not executed after mesh_report |
| delivered `[[0,1]], [0,2,3]` | 1.0 | `(0,) (0,)` | IndexError: list index out of range | None, 0.5 | not executed after tri_areas | false | ValueError: face 0: fewer than 3 sides | `["A"]` | not executed after mesh_report |
| delivered `[0,0,1], [0,2,3]` | 1.0 | `(0,) (0,)` | 0.0, 0.5 | None, 0.5 | false / 2 / 0 / 0 / 0 / 1 | true | ValueError: face 0: repeated vertex index | `["A"]` | not executed after mesh_report |
| source `[0,0,1]` | 0.0 | `() ()` | 0.5, 0.5 | 0.5, 0.5 | false / 2 / 0 / 2 / 0 / **0** | true | passed true | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| delivered `[[0,1,2,3]]` | 1.0 | `(0,)` | **0.5** | **1.0** | false / 1 / 0 / 0 / 0 / 1 | false | passed true, count 0 | `["A"]` | false / 1 / 0 / 0 / 0 / 1 |
| delivered `[[0,1,2,3], [0,2,3]]` | 1.0 | `(0,) (0,)` | **0.5, 0.5** | **1.0, 0.5** | **true / 2 / 0 / 0 / 0 / 0** | false | passed false, count 1 | `["A"]` | **true / 2 / 0 / 0 / 0 / 0** |
| source vertex `[0.0, 0.0]` | ValueError: inhomogeneous shape | same ValueError | 0.5, 0.5 | 0.5, 0.5 | not executed | true | passed true | ValueError: non-finite or malformed vertex [0.0, 0.0] | not executed after assign_finishes |
| delivered vertex `[0.0, 0.0]` | 1.0 | ValueError: inhomogeneous shape | same ValueError | same ValueError | not executed | true | same ValueError from `np.asarray` | `["A"]` | not executed after mesh_report |

The empty delivered face also emitted `RuntimeWarning: Mean of empty slice` and `RuntimeWarning: invalid value encountered in divide` from `match_source_faces`, then the ValueError. No other row emitted a warning.

### What those rows mean

**Verified by run.** Source `[-4, -3, -2, -1]` resolves through list indexing to the same four corners as `[0, 1, 2, 3]`. Area, owners and `ok` match the control. That is a successful finish verdict on wrapped indices.

**Verified by run.** Delivered `[-4, -3, -2]` and `[-4, -2, -1]` do the same inside the helpers (`tri_areas` and `ov[list(f)]` both accept the wrap), so the isolated report is `ok` true. `mesh_report` raises `index outside the vertices` first. The package-order finish report was not executed. The isolated `ok` true is not the verdict.

**Verified by run.** Integer-valued floats and the fractional index `0.5` are not truncated. A source list raises `TypeError`. A delivered numpy index raises `IndexError`. `PolyMesh` raises `index 0.0 is not an integer` or `index 0.5 is not an integer`. These helpers do not construct `invariants.Mesh`.

**Verified by run, plus the shape probe.** Source `[True, False, 2, 3]` is list-indexed as `[1, 0, 2, 3]` because `bool` is a subclass of `int`. Newell length is 0, so the area is `0.0`, both deliveries are unmatched, and `ok` is false. The coverage counter stays 0 because `abs(0 - 0) > 1e-6` is false. `assign_finishes` still returns `["A"]`, and `mesh_report` never sees the source face.

Delivered `[False, True, 2]` is rejected by `PolyMesh` (`index False is not an integer`), so the finish report is not executed on the package order. In isolation the two helpers disagree. `ov[[False, True, 2]]` is the three points `(0,0,0), (1,0,0), (1,1,0)` and the owner is `(0,)`. `tri_areas` indexes with the scalar: on this numpy, `v[False].shape` is `(0, 4, 3)` and `v[True].shape` is `(1, 4, 3)`. The cross product is empty and `float(norm(...))` is `0.0`. The isolated report is `ok` false because the areas sum to `0.5` against `1.0`.

**Verified by run.** Source faces `[]`, `[0]`, `[0, 1]` and `[0, 0, 1]` follow the same zero-area path: area `0.0`, empty owners, `ok` false, coverage counter 0, `assign_finishes` returns `["A"]`.

**Verified by run.** A delivered face `[0]` or `[0, 1]` gets owner `(0,)` from `match_source_faces` (the corners that exist lie in the square). `tri_areas` then raises `IndexError: list index out of range`, so no finish report is composed. `mesh_report` raises `fewer than 3 sides` earlier, so the package-order report is not executed. The empty face raises inside `match` (`zero-size array to reduction operation minimum which has no identity`) after the warnings above; `mesh_report` again raises first.

**Verified by run.** Delivered `[0, 0, 1]` has `tri_areas` `0.0`, owner `(0,)`, and an isolated report `ok` false (`not_covered` 1). `len == 3` is true, so the triangulation predicate does not see the repeat. `mesh_report` raises `repeated vertex index`, and the package-order report is not executed.

**Verified by run. Lone quad versus the false complete report.** Delivery `[[0, 1, 2, 3]]` is owned as `(0,)`. `tri_areas` is `0.5`. The full polygon area is `1.0`. The report is `false / 1 / 0 / 0 / 0 / 1`. The shortfall is visible. `mesh_report` returns `passed` true, count 0. `len == 3` is false and, in `main`, that failure does not return.

Delivery `[[0, 1, 2, 3], [0, 2, 3]]` is the same partial measurement plus the second control triangle. `tri_areas` is `[0.5, 0.5]`. Full polygon areas are `[1.0, 0.5]`. Owners are `(0,)` and `(0,)`. The report is `true / 2 / 0 / 0 / 0 / 0`. The first three corners of the quad sum with the half-triangle to the source area `1.0`. `mesh_report` returns `passed` false, count 1, and does not raise. `assign_finishes` returns `["A"]`. On these arrays the finish helper's `ok` true survives both of those calls.

**Source, applied to those owners.** The count branch (`qa_packages.py:155-156`) was not called. `main` always passes the area lists (`:410-413`). On the owners this run returned, that count branch would also treat the source quad as covered: two owned delivered faces and `len(f) - 2 == 2`.

**Verified by run.** A vertex stored as `[0.0, 0.0]` makes `assign_finishes` raise `non-finite or malformed vertex [0.0, 0.0]` on the source side, which is before the finish report in `main`. On the delivered side, `np.asarray` inside `mesh_report` raises `inhomogeneous shape` first. Both are aborts. Neither is `ok` true.

### Readers, static

**Source. Not executed.** No Blender and no 3ds Max process was started.

`qa_readback.py:26-27` writes `list(mw @ v.co)` and `list(p.vertices)`. The script does not apply a negative-end marker and does not drop a coordinate. A polygon is copied at whatever length `p.vertices` has, including four indices. These lines are the delivered-face producer `main` loads as JSON (`qa_packages.py:267`, `:282`, `:404`). They were not run, so this note does not claim a Blender mesh is incapable of a bad index. It claims this producer, as written, performs no index-range test and no triangulation.

`dump_max_poly.py:32-33` writes three floats per vertex and `int(i) - 1` per face corner from `polyop.getFaceVerts`. The subtraction yields a Python `int`. This card did not call Max, so it does not claim what `getFaceVerts` returns. The expression can be negative when the runtime value is below 1. The dump was not run. `main` reads those faces as `body["faces"]` (`qa_packages.py:307`, `:403-404`).

`qa_packages.load` is `json.load` (`qa_packages.py:35-37`). JSON `true` is a Python `bool`, and JSON `1.0` is a Python `float`. That is how the bool and float rows can exist as helper inputs. It is not a claim that either native writer emits them.

`docs/domain/areas/package.md` maps V001–V017 onto archive, FBX, name and GeoJSON rows. It does not define a face-index domain for `source_finish_report`. The predicate lives in the TEC26 package script.

## How it applies to this repository

- Successful wrap of a source face: `jobs/TEC26-OKS/scripts/qa_packages.py:63` and the report at `:153-157`. Production calls of the report are `:410-413`, after `assign_finishes` at `:403`.
- Three-corner area of a longer delivered face: `tri_areas` at `:119-121`. The false `ok` true row is the synthetic delivery `[[0, 1, 2, 3], [0, 2, 3]]`.
- Delivered rejection that actually runs first: `mesh_report` at `qa_packages.py:297` and `src/dt_ai/ops/inv_quads.py:74-85`. A quad is not rejected there. `triangulated_*` at `qa_packages.py:292` records `len != 3` and continues.
- Source vertex shape: `finish_map.py:314-317`. Plain-rule index silence: `finish_map.py:344`.
- Delivered faces in the readback JSON: `jobs/TEC26-OKS/scripts/qa_readback.py:27`. Source faces in the Max dump JSON: `jobs/TEC26-OKS/scripts/dump_max_poly.py:33`.

Helper `ok` true on the negative source quad, and helper `ok` true on the quad-plus-half delivery, were both executed. `main()` was not. Image and ZIP stages were not. No whole-package exposure is claimed. `delivery_passed=false`.

## Reproduction

From the worktree, with `src` and `jobs/TEC26-OKS/scripts` on `sys.path`. The full matrix is the probe script named above.

```python
import copy
import qa_packages as q
import finish_map
from dt_ai.ops.inv_xview import mesh_report
sq = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]]
spec = {"source_ids": {"1": {"finish": "A"}}, "zero_m": 0.0}
shift = [0.0, 0.0, 0.0]

def finish(src_f, out_f, src_v=None, out_v=None):
    src_v, out_v = src_v or sq, out_v or sq
    owners = q.match_source_faces(src_v, src_f, out_v, out_f, shift)
    report = q.source_finish_report(["A"], src_f, owners, ["A"] * len(owners),
                                    q.tri_areas(out_v, out_f), q.poly_areas(src_v, src_f))
    return owners, report["ok"], report["source_polygons_not_covered"]

# control: owners [(0,), (0,)], ok True, not_covered 0
print(finish([[0, 1, 2, 3]], [[0, 1, 2], [0, 2, 3]]))
# source negatives wrap; ok True. assign_finishes returns ["A"]
print(finish([[-4, -3, -2, -1]], [[0, 1, 2], [0, 2, 3]]))
print(finish_map.assign_finishes(sq, [[-4, -3, -2, -1]], [1], spec))
# lone quad: tri area 0.5, full area 1.0, ok False
print(q.tri_areas(sq, [[0, 1, 2, 3]]), q._poly_geo(sq, [[0, 1, 2, 3]])[0]["area"])
print(finish([[0, 1, 2, 3]], [[0, 1, 2, 3]]))
# quad plus the other half: tri areas [0.5, 0.5], full areas 1.0 and 0.5, ok True
print(finish([[0, 1, 2, 3]], [[0, 1, 2, 3], [0, 2, 3]]))
print(mesh_report(sq, [[0, 1, 2, 3], [0, 2, 3]], profile="VPM")["passed"])
```

## Proposed next tasks

1. **In-range integer source indices before a finish verdict**, size S, `Archive: no roadmap link`. The user owns whether this is an exception or a failed check. At `qa_packages.py:63` a negative index is a list lookup, and with the plain rule `assign_finishes` returns a finish without reading the face (`finish_map.py:344`). Pair: unit-square vertices, source `[[-4, -3, -2, -1]]`, delivery `[[0, 1, 2], [0, 2, 3]]`, shift `[0, 0, 0]` → today owners `[(0,), (0,)]`, areas `[0.5, 0.5]` / `[1.0]`, report `true / 2 / 0 / 0 / 0 / 0`, `assign_finishes` `["A"]`; expected a diagnostic that names an index outside `0 .. 3`, and the finish report is not `ok` true. Pair: source `[[True, False, 2, 3]]` → today area `0.0`, owners empty, `false / 2 / 0 / 2 / 0 / 0` (coverage counter 0), `assign_finishes` `["A"]`; expected a diagnostic that names a non-integer index, with polygon 0 not judged by the zero-area comparison. Keep the control source `[[0, 1, 2, 3]]` at `true / 2 / 0 / 0 / 0 / 0`. Leave `invariants.Mesh` and the non-finite area predicate untouched.

2. **Coverage area of a delivered face includes every corner**, size S, `Archive: no roadmap link`. The user owns refuse-versus-measure. `tri_areas` (`qa_packages.py:121`) ignores corner 3 and beyond. Pair: the same square and source quad, delivery `[[0, 1, 2, 3], [0, 2, 3]]` → today `tri_areas` `[0.5, 0.5]`, full polygon areas `1.0` and `0.5`, owners `[(0,), (0,)]`, report `true / 2 / 0 / 0 / 0 / 0`; expected not `ok` true. The 4-index face must not contribute only its first triangle. Keep delivery `[[0, 1, 2], [0, 2, 3]]` at `true / 2 / 0 / 0 / 0 / 0`. The lone quad `[[0, 1, 2, 3]]` is already `false / 1 / 0 / 0 / 0 / 1` with `tri_areas` `0.5` and full area `1.0`; keep that failure. `mesh_report` on the false-pass pair returns `passed` false and does not raise; this task does not change xview or `triangulated_*`.

## Open questions for the user

1. A negative source index that names an existing vertex currently certifies. Should that be an exception, or a failed `source_finish_*` check? This note does not choose.
2. For a delivered face longer than three indices, should the helper refuse it, or add the whole polygon area? The lone quad already fails the area comparison. The quad plus the remaining half currently returns `ok` true. `triangulated_*` already records `len != 3` and does not stop `main`.
3. Source faces shorter than three indices, and the boolean source face, fail `ok` because every delivery is unmatched, while the coverage counter stays 0 on area `0.0`. Is that the intended diagnostic? The zero-area comparison itself is the subject of `docs/research/source-finish-area-numeric-domain.md` and is not reopened here.
4. `qa_packages.main` was not executed. The Image/ZIP reads sit before `assign_finishes`. Is the direct witness of `mesh_report`, `assign_finishes` and the finish helpers enough?
