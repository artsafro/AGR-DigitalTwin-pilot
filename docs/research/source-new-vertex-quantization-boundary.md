# Five-decimal vertex rounding in `qa_packages._new_vertices`

Research note. Pinned SHA `30c0694d539f96a1e52a47f6db44bc29218988d2` (worktree ref `docs/research-source-new-vertex-quantization-boundary`, read from `.git/refs/heads/docs/research-source-new-vertex-quantization-boundary`). `git` was not run. No pytest, no `qa_packages.main`, no ZIP, PNG, FBX, or TEC26 asset. `delivery_passed=false`.

Question: is the round-to-5-decimals inside `_new_vertices` only deduplication, or can it change `geometry_report` missing / new / off-edge counts and `cut_joint_report` verdicts on finite non-`nextafter` inputs at the default `tol=2e-4` m?

The adjacent-float witness in `tests/jobs/test_source_cut_joint_width.py` (`math.nextafter(0.125, ...)`) is not re-run and is not an input below.

## Frozen probe matrix

Written before the probe process. The seven rows are the required matrix. Bracketed tokens are inputs inside a row, not rows added later. Measurements for these inputs are filled in Findings after the run. No input was added after the run except a line marked post-hoc, and there is no such line unless Findings says so.

Shared fixture, metres, decimal strings unless a cell overrides a coordinate:

- Source quad `(0,0,1), (4,0,1), (4,0,3), (0,0,3)`, face `[0,1,2,3]`.
- `expected = ["F"]`.
- `spec = {zero_m: 0, facade_uv: ["F"], finishes.F.P: [1, 1]}`. `joint_half_mm` omitted. No `facades` key.
- `tol` left at the function default (`2e-4`).
- Shift `(0,0,0)` except row 7.
- Stored float of a token is `float(Fraction(Decimal(token)))`, or `float(Fraction(1,3))` for the token `1/3`.
- Row 7 delivery is `world_float - shift_float` componentwise (IEEE subtraction). Source stays in the world frame. Production then adds `shift` back and rounds.

| Row | Question inside the row | Frozen inputs |
|---|---|---|
| 1 | Literal -Y quad, delivery equals source | The shared quad. `geometry_report` at `cuts_allowed` false and true. `cut_joint_report`. |
| 2 | Source on and off the `1e-5` m grid | Vertex 0 x replaced, delivery a copy, except 2d. 2a `0.1`. 2b `0.123456`. 2c `0.123455`. 2d source `0.123456`, delivery vertex 0 x `0.12346`. 2e `1/3`. |
| 3 | New point on the bottom edge, transverse offset below / at / above `2e-4` | Add `(2, y, 1)` with y in `0`, `0.000194`, `0.000195`, `0.000199`, `0.000200`, `0.000201`, `0.000204`, `0.000205`, `0.000206`, `-0.000201`, `-0.000205`. Diagonal add `(2, d, 1+d)` with d in `0.0001414`, `0.0001415`. |
| 4 | Source-to-delivery displacement below / at / above `2e-4` | Corner `(0,0,1)` moved in the delivery, once as a replacement and once as an added point (original corner kept). Along x by `0.000005`, `0.000194`, `0.000195`, `0.000199`, `0.000200`, `0.000201`, `0.000204`, `0.000205`, `0.000206`. Along y by `0.000199`, `0.000200`, `0.000201`, `0.000204`, `0.000205`. Along xyz by the same delta on x, y, and z, delta in `0.000199`, `0.000201`. |
| 5 | On-joint and off-joint, default 4 mm half-width, offsets of several micrometres | Add `(x, 0, 1)`. x in `0.003994`, `0.003995`, `0.003997`, `0.004000`, `0.004003`, `0.004004`, `0.004005`, `0.004006`, `0.995994`, `0.995996`, `0.996000`, `0.996003`, `0.996005`, `0.996006`, `1`, `0.5`. |
| 6 | Duplicates and permutations | Delivery `[v2,v0,v0,v3,v1,v2]`. Three `(2,0,1)` mixed with corners as `[mid,v3,v1,mid,v0,v2,v0]`. Pairs `(0.003997,0,1)` with `(0.004003,0,1)`, both orders. Pairs `(0.003995,0,1)` with `(0.004005,0,1)`, both orders. Two copies of `(2, 0.001, 1)`. Source order `[v3,v2,v1,v0]` with face `[3,2,1,0]`, delivery the same. Extra `(0.004005,0,1)` at the front and at the back. That extra on the permuted source. |
| 7 | Same world geometry, shift 0 vs exactly representable nonzero shift | Shifts `(0,0,0)`, `(0.5,0.5,0.5)`, `(1024,1024,1024)`. World sets: the quad; add `(2, 0.000201, 1)`; add `(2, 0.000205, 1)`; replace corner 0 with `(0.000201, 0, 1)`; add `(0.004003, 0, 1)`; add `(0.004005, 0, 1)`; add the pair `(0.003995,0,1)` and `(0.004005,0,1)`; add `(2, 0.0001415, 1.0001415)`. |

Current-policy outputs are observations. They are not an acceptance rule for a package.

## Summary

The 5-decimal round in `_new_vertices` is not only deduplication. On this fixture it changes `geometry_report` missing, new, and off-edge counts, and it changes `cut_joint_report` `ok`, including both pass-to-fail and fail-to-pass.

A point 1 µm past `tol` (`0.000201`) rounds to `0.0002` and is then treated as on the edge, or as the source corner. A point 3 µm past the 4 mm joint (`0.004003`) rounds to `0.004` and passes the joint test. A point 3 µm inside the far side (`0.996003`) rounds to `0.996` and fails it. Two distinct joint points can collapse to one and the off-joint point disappears.

Shift `(0,0,0)` and shift `(1024,1024,1024)` do not preserve those reports for the halfway tokens `0.000205` and `0.004005`. Exact duplicate points and a clean copy of an off-grid source do not flip a verdict. No post-hoc row was added. `delivery_passed=false`.

## Findings

**Verified by run.** CPython 3.14.7, numpy 2.5.3. Command: `uv run python C:/x/t_57cda816/probe_new_vertex_quant.py` from the repo root. JSON: `C:/x/t_57cda816/probe_results.json`. 102 calls, one per frozen sub-input. Every call left `src_v`, faces, `expected`, `spec`, `out_v`, and `shift` equal to a deepcopy taken before the call. No warnings. A Python-float reimplementation of the predicates, applied to `np.unique(np.round(out+shift, 5), axis=0)`, matched production `missing` / `new` / `off` / `ok` / `checked` / `off_joint_count` on all 102 calls. That harness is a check of the reimplementation, not an oracle for the unrounded result.

**Read-only, pinned file.** SHA `30c0694d539f96a1e52a47f6db44bc29218988d2`.

- `jobs/TEC26-OKS/scripts/qa_packages.py:162-167` rounds delivery+shift to 5 decimals, uniques rows, then Chebyshev distance. Missing and new use strict `> tol`.
- `qa_packages.py:170-173` `_on_edge`: `1e-6 < t < 1-1e-6` and Euclidean residual `<= tol`.
- `qa_packages.py:176-184` `geometry_report`. `ok` is missing 0, no off-edge point, and either cuts are allowed or there is no new point (line 182). Off-edge examples are `q.round(4)` (line 181).
- `qa_packages.py:187-211` `cut_joint_report`. Omitted `joint_half_mm` uses 4, divided by 1000. Off-joint is strict `>` (line 208). Stored `u_m` and `off_joint_m` are `round(..., 4)` (line 209).
- `main` calls `geometry_report` at `320-322` and `cut_joint_report` at `414-416`. Neither call was executed.
- Width tests, including the `nextafter(0.125)` case this note does not repeat: `tests/jobs/test_source_cut_joint_width.py:1-12`, `:116-124`, `:127-156`. Vertex-ring counts: `tests/jobs/test_source_vertex_ring_cuts.py:9-17`, `:49-71`. Exact-duplicate unique: `tests/jobs/test_source_cut_shared_edges.py:16-19`, `:166-167`. Facade-field frames were not used (`test_source_cut_field_frames.py:1-8`); the spec has no `facades` key.

Hand frame for this quad, from `finish_map.py:355-365` and `:425-428`: all y are 0, Newell normal `(0,-16,0)`, so u = x and the origin is the minimum x, which is 0. The harness matched production on `x=1` (on joint) and `x=0.5` (off by 0.5 m), which is the same frame the width test records at `test_source_cut_joint_width.py:7-8`.

Defaults read from the functions: `geometry_report` and `cut_joint_report` tol repr `0.0002`, fraction `7378697629483821/36893488147419103232`, which is `221/23058430092136939520000` above `2/10000`. `4/1000` repr `0.004`, fraction `1152921504606847/288230376151711744`, which is `3/36028797018963968000` above `4/1000`. In the diffs below, production is the left side and the reference is the right side.

Three references, all independent of production:

- **Decimal.** `Fraction` of the token, thresholds `2/10000` and `4/1000`, no 5-decimal round. Squared Euclidean compare for the edge.
- **Unrounded float.** The recovered floats and the function's own `tol` and `4/1000`, no 5-decimal round. This is the predicate the round is added to.
- **Stored-exact.** `Fraction.from_float` of those same floats, compared with the exact decimal thresholds. Disagreement here is binary storage, not `np.round`.

`np.round` of a float is a float near `k/100000`, so `Decimal.from_float` of the result is usually a few ulps off the exact decimal. That ulp gap is not a different 5-decimal choice. A different choice is recorded only where quantize-half-even of the token and of the stored float disagree.

### Why `5e-6` m is not a verdict bound

Half of `1e-5` is `5e-6` m. That is the farthest a real number can sit from its nearest 5-decimal place. It is not a bound on these reports.

The missing/new test is Chebyshev (`qa_packages.py:165-167`), so one coordinate's rounding moves that distance by about `5e-6`, not by `sqrt(3)*5e-6`. The edge test is Euclidean and 1-Lipschitz in the point, so a 3-axis move of `5e-6` each can change the residual by up to `sqrt(3)*5e-6` (about `8.7e-6`). On this axis-aligned edge the along-edge component drops out of the residual, and the bound is `sqrt(2)*5e-6`. The joint test reads one world axis, so its distance moves by about one coordinate.

Any of those comparisons flips when the pre-round distance is closer to the threshold than the move. The threshold can sit at `0.2` mm or at `4` mm; the flip does not require the point to be within `5e-6` of the origin. Rounding moved both toward a threshold (`0.000201` → `0.0002`, `0.000195` → `0.0002`) and away (`0.000194` → `0.00019`, `0.000206` → `0.00021`).

The measured maximum of `|np.round(v,5) - v|` as an exact fraction of the two floats was `22517998137/4503599627370496` (about `5.000000000032756e-06`) on `R5-x-0.996005`. Seven coordinates exceeded `5/1000000`: `R2c`, both `R4` `x=0.000005` calls, both `R4` `x=0.000195` calls, `R3-y-0.000195`, and `R5-x-0.996005`. The excess is the float of the chosen grid point, or `np.round` landing one grid step past the exact half-even of the stored float. `R2c` token `0.123455` quantizes to `0.12346`, while half-even of the stored float quantizes to `0.12345`; `np.round` returned `0.12346`. The vertex stayed matched. `R4` `x=0.000005` token quantizes to `0.00000`, stored-float half-even quantizes to `0.00001`, and `np.round` returned `0.0`. Both `0` and `1e-5` are inside the `2e-4` ball, so the report does not change.

### Row 1 — control

**Verified by run.** Delivery equals the quad. Rounded unique points are the four corners. Counts match the decimal reference and the unrounded float predicate.

`geometry_report` cuts false and true: `missing_source_vertices=0`, `new_vertices=0`, `new_off_source_edges=0`, `off_examples=[]`, `ok=true`, `cuts_allowed` false or true. `cut_joint_report`: `ok=true`, `new_vertices=0`, `checked_on_patterned_edges=0`, `off_joint=[]`, `off_joint_count=0`.

Classification: no-op. The round does not move an integer coordinate.

### Row 2 — on and off the `1e-5` grid

**Verified by run.** Delivery is the same floats as the source, except 2d. All five reports equal row 1. Rounding changes coordinates and does not change a count.

| Id | Token x | Stored float | `np.round` x | Round move | Nearest-source L∞ after the round |
|---|---|---|---|---|---|
| R2a | `0.1` | `0.1` = `3602879701896397/36028797018963968` | `0.1` | 0 | 0 |
| R2b | `0.123456` | `8895942329546431/72057594037927936` | `0.12346` | `36028797019/9007199254740992` (about `4.0e-6`) | that same move |
| R2c | `0.123455` | `8895870271952393/72057594037927936` | `0.12346` | `180143985095/36028797018963968` (slightly over `5e-6`) | that same move |
| R2d | source `0.123456`, delivery `0.12346` | delivery `8896230559922583/72057594037927936` | `0.12346` | 0 | `36028797019/9007199254740992` against the source float |
| R2e | `1/3` | `6004799503160661/18014398509481984` | `0.33333` | `60047995031/18014398509481984` (about `3.33e-6`) | that same move |

`0.1` is on the 5-decimal grid as a decimal and is not binary-exact. The round left that float unchanged. The `1e-18` gap is `float(0.1)` versus the decimal `1/10`, present before `np.round`. Classification: coordinate change, no verdict change. A `5e-6` snap is inside the `2e-4` match ball, so an exact copy of an off-grid source is still not missing.

### Row 3 — transverse offset

**Verified by run.** The added point is about 2 m from every corner, so it stays a new vertex unless the transverse coordinate itself is the question. At `x=2`, `u=2`, the joint distance is 0 whenever the point is still on the edge.

Shared production shape when the point stays on the edge: cuts false `ok=false`, `new=1`, `off=0`; cuts true `ok=true`, `new=1`, `off=0`; cut `ok=true`, `checked=1`, `off_joint_count=0`. Ids: `y` in `0`, `0.000194`, `0.000195`, `0.000199`, `0.000200`, and diagonal `0.0001414`.

`y=0.000194` rounds to `0.00019` (away from `0.0002`). `y=0.000195` and `y=0.000199` round to `0.0002` (toward it) and stay on, because on-edge is `<= tol`. `y=0.000200` does not move. Its stored float is the tol float, so `<= tol` holds. The stored-exact reference, comparing that fraction with `2/10000`, calls the point off the edge. Production does not. That disagreement is the float threshold, and the 5-decimal round is a no-op (`move=0`).

Verdict change, same for `y` in `0.000201`, `0.000204`, `0.000205`, `-0.000201`, `-0.000205`. Decimal and unrounded float: `off=1`, cuts true `ok=false`, cut `checked=0` (the point is new but not on an edge, so the joint test does not run and cut `ok` stays true). Production rounds y to `0.0002` or `-0.0002`: `off=0`, cuts true `ok=true`, cut `checked=1`. Cuts false stays `ok=false` because a new vertex remains and cuts are not allowed. Full production dict for `y=0.000201`:

```json
{"ok": false, "missing_source_vertices": 0, "new_vertices": 1, "cuts_allowed": false, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "missing_source_vertices": 0, "new_vertices": 1, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "new_vertices": 1, "checked_on_patterned_edges": 1, "off_joint": [], "off_joint_count": 0}
```

`y=0.000201` stored `926948889703905/4611686018427387904`. Decimal L∞ to the edge is `201/1000000`, which is above `2/10000`. After the round the unique point is `(2, 0.0002, 1)`.

`y=0.000206` does not flip. It rounds to `0.00021`, and both references stay off the edge. Production cuts true `ok=false`, `off=1`, `off_examples=[[2.0, 0.0002, 1.0]]`. The example is `round(0.00021, 4)`, which prints `0.0002` while the 5-decimal point used for `<= tol` is `0.00021`. Cut `ok=true` with `checked=0`. Classification: no verdict change; the 4-decimal example is not the tested coordinate.

Diagonal `d=0.0001414` stays on the edge before and after the round to `0.00014`. `d=0.0001415` is a verdict change of the same kind as `0.000201`. Decimal squared distance to the edge is `8000000080089/2000000000000`, which is above `(2/10000)^2`. Both transverse components round to `0.00014`, and `2*(0.00014)^2` is below that threshold. Production cuts true `ok=true`, `off=0`. Unrounded: `off=1`, cuts true `ok=false`. This is the 2-axis Euclidean case. The missing test does not see it: L∞ to the nearest corner is 2 m either way.

### Row 4 — displacement of a source corner

**Verified by run.** Replacing `(0,0,1)` by `(0.000201, 0, 1)` is the missing-count flip. Decimal and unrounded float: `missing=1`, `new=1`, `off=0`, `ok=false` for both cut flags (the point lies on the bottom edge, `t=0.000201/4 > 1e-6`, and the corner is gone). Production rounds x to `0.0002`, which is not `> tol`, so the point is neither missing nor new:

```json
{"ok": true, "missing_source_vertices": 0, "new_vertices": 0, "cuts_allowed": false, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "missing_source_vertices": 0, "new_vertices": 0, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "new_vertices": 0, "checked_on_patterned_edges": 0, "off_joint": [], "off_joint_count": 0}
```

The same missing/new/`ok` flip happens for replace along x at `0.000204` and `0.000205`, along y at `0.000201`, `0.000204`, `0.000205` (those are also off-edge before the round, because `t=0`), and along xyz at `0.000201`. Adding the point beside the original corner does not change `missing`. It does change `new` from 1 to 0, and cuts-false `ok` from false to true. Cuts-true `ok` stays true for the along-edge add, because the unrounded point was already on the edge.

`x=0.000206` replace does not flip: rounded x is `0.00021`, `missing=1`, `new=1`, `off=0`, `ok=false`, cut `checked=1`, `off_joint_count=0` (`0.00021 < 0.004`). The add of that point keeps `missing=0`, `new=1`, cuts false `ok=false`, cuts true `ok=true`.

`x=0.000005` replace and add: `new=0`, `missing=0`, `ok=true` before and after. The match ball absorbs `5e-6`. `np.round` lands on the corner; half-even of the stored float would be `0.00001`, which is still inside the ball. No verdict change.

xyz `0.000199`: each component rounds to `0.0002`, L∞ is not `> tol`, `missing=0` before and after. The Euclidean length of the displacement is `sqrt(3)*0.000199`, about `3.45e-4`, which is above `tol`. The code never uses that length for missing/new. Classification: no verdict change, and a reminder that the Euclidean `sqrt(n)*5e-6` figure is not the missing test.

Below-threshold tokens `0.000194`, `0.000195`, `0.000199`, and the at-threshold token `0.000200`, do not flip missing/new against the unrounded float predicate. `0.000200` has the same stored-exact quirk as row 3: exact `2/10000` says the float is outside, the float comparison says it is not.

### Row 5 — 4 mm joint

**Verified by run.** Every added x is a new on-edge point. Geometry does not flip: cuts false `ok=false`, `new=1`, `off=0`; cuts true `ok=true`. The joint report does flip.

Pass both before and after the round (`cut ok=true`, `off_joint_count=0`): `0.003994` (rounds to `0.00399`, away from 4 mm), `0.003995` and `0.003997` (round to `0.004`, toward it), `1`, and `0.996006` (rounds to `0.99601`).

`0.004000` does not move. Production passes. The decimal reference passes (`4/1000` is not `>` itself). The stored-exact reference fails, because `Fraction.from_float(0.004)` is above `4/1000` while `float(0.004) > float(0.004)` is false. Binary threshold, not a 5-decimal change.

Fail to pass, decimal and unrounded float `off_joint_count=1`, production `off_joint_count=0`. Ids `0.004003`, `0.004004`, `0.004005`. All three round to `0.004`. Full production cut dict for `0.004003`:

```json
{"ok": true, "new_vertices": 1, "checked_on_patterned_edges": 1, "off_joint": [], "off_joint_count": 0}
```

Stored `0.004003` = `576893097867651/144115188075855872`. Decimal distance `4003/1000000` is above `4/1000`.

Pass to fail: `0.996003` and `0.996005`. Unrounded distance to 1 m is `0.003997` and `0.003995`, both under `4/1000`, so both references pass. `np.round` returns `0.996`. Production:

```json
{"ok": false, "new_vertices": 1, "checked_on_patterned_edges": 1, "off_joint": [{"source_polygon": 0, "u_m": 0.996, "off_joint_m": 0.004}], "off_joint_count": 1}
```

`0.996` itself (`R5-x-0.996000`) already fails with `move=0`. Stored value `2242792614430507/2251799813685248`. `1` minus that fraction is `9007199254741/2251799813685248`, and the float joint test is strict `>`. The decimal `0.996` is exactly `4/1000` from 1 and would pass. Production matches the unrounded float predicate and not the decimal. Rounding did nothing to this token; the failure is the binary value of `0.996`. `0.996003` and `0.996005` inherit it by rounding onto that float. For `0.996005`, half-even of the stored float is `0.99601`, which would still pass; `np.round` returned `0.996` (the token's half-even place) and the report fails. The round move on that coordinate is the maximum cited above.

`0.004006` stays a fail. Rounded x is `0.00401`. The dict prints `u_m=0.004`, `off_joint_m=0.004`, because `round(0.00401, 4)` is `0.004`. The comparison that set `ok=false` used the 5-decimal value. `0.995994` rounds to `0.99599` and prints the same `u_m=0.996`, `off_joint_m=0.004`. `0.995996` rounds to `0.996` and prints that same example. The printed pair does not identify which 5-decimal point was tested.

`x=0.5` stays a clear fail: `off_joint=[{"source_polygon": 0, "u_m": 0.5, "off_joint_m": 0.5}]`. `x=1` stays a clear pass. Neither is a rounding effect.

### Row 6 — duplicates and permutations

**Verified by run.** Order and exact duplicates do not change a report. Quantization that merges unequal points does.

| Id | Production versus one logical copy | Versus the unrounded float predicate |
|---|---|---|
| `R6-dup-corners` | Same full dicts as row 1 | same |
| `R6-src-perm` | Same as row 1 | same |
| `R6-mid-mixed` | `new=1`, on edge, on joint | same (exact copies of the midpoint) |
| `R6-off-x2` | `new=1`, `off=1`, `off_examples=[[2.0, 0.001, 1.0]]`, cuts `ok=false`; cut `ok=true`, `checked=0` | same |
| `R6-extra-front`, `R6-extra-back`, `R6-perm-src-extra` | Same dicts as `R5-x-0.004005` | same rounding flip as that row; the three ids match each other |
| `R6-pair-near`, both orders | `new=1`, cut `ok=true` | unrounded `new=2`, cut `ok=false`, `off_joint_count=1` |
| `R6-pair-tie`, both orders | same collapse | same |

`R6-pair-near` is `(0.003997, 0, 1)` and `(0.004003, 0, 1)`. Both round to `(0.004, 0, 1)`. The second is off the joint before the round and on it after, and unique then drops the duplicate. Production:

```json
{"ok": false, "missing_source_vertices": 0, "new_vertices": 1, "cuts_allowed": false, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "missing_source_vertices": 0, "new_vertices": 1, "cuts_allowed": true, "new_off_source_edges": 0, "off_examples": []}
{"ok": true, "new_vertices": 1, "checked_on_patterned_edges": 1, "off_joint": [], "off_joint_count": 0}
```

Classification: exact duplicates and permutations are preserved. The unequal pair is dedup that also flips the joint verdict. Reversed order produced the same dicts.

### Row 7 — shift

**Verified by run.** Source stays in the world frame. Delivery component is `world_float - shift_float`. Production adds `shift` and rounds. Decimal reference is the world tokens and does not depend on shift.

Preserved across `(0,0,0)`, `(0.5,0.5,0.5)`, and `(1024,1024,1024)`: the quad; add `(2, 0.000201, 1)`; replace the corner with `(0.000201, 0, 1)`; add `(0.004003, 0, 1)`; add the diagonal `0.0001415`. Those are not halfway tokens. The rounding flip, where there is one, is the same at every shift.

Not preserved:

- Add `(2, 0.000205, 1)`. Shift 0 rounds y to `0.0002`: cuts true `ok=true`, `off=0`, cut `checked=1`. Shift `0.5` and shift `1024` recover `0.00020500000000001073` (`923237923611/4503599627370496` at shift `0.5`), and `np.round` returns `0.00021`. Cuts true `ok=false`, `off=1`, `off_examples=[[2.0, 0.0002, 1.0]]`, cut `checked=0`. That matches the unrounded float predicate of the recovered value, and it matches the decimal reference. Shift 0 does not.
- Add `(0.004005, 0, 1)`. Shift 0 and `0.5` round to `0.004` and the joint report passes. Shift `1024` recovers `0.004005000000006476` and rounds to `0.00401`. Cut `ok=false`, `off_joint_count=1`, printed `u_m=0.004`, `off_joint_m=0.004`.
- The pair `(0.003995, 0, 1)` and `(0.004005, 0, 1)`. Shift 0 and `0.5`: both become `0.004`, `new=1`, cut `ok=true`. Shift `1024`: unique points `0.004` and `0.00401`, `new=2`, cut `ok=false`, `checked=2`, `off_joint_count=1`.

Classification: an exactly representable shift does not by itself change an integer or a non-tie token here. It does change a halfway token when `(world - shift) + shift` crosses the tie that `np.round` sees. Permutation is a separate row and was preserved.

### What the round is, on this evidence

Exact copies, exact duplicate rows, and snaps of a few micrometres well inside `2e-4` behave as dedup or as a no-op on the counts. Tokens within a few micrometres of `tol` or of the 4 mm half-width do not. Forty-nine of the 102 calls differed from the unrounded float predicate. The distinct mechanisms are the ones named above; the rest are the replace/add pair and the shift-0 copy of the same point. Current-policy output is what the code did. It is not a chosen acceptance rule.

## How it applies

`jobs/TEC26-OKS/scripts/qa_packages.py:164` is the only round. `geometry_report` (`176-184`) and `cut_joint_report` (`187-211`) both take their vertex set from it. In `main`, `g["ok"]` is part of `geometry_source_plus_ring_cuts_{vpm,npm}` (`320-322`) and the joint dict is `cuts_at_joints_{tag}` (`414-416`). Those `main` calls were not run. A flipped `ok` on these arrays would flip those checks only if a delivery actually contained the coordinates. No package, ZIP, or readback was opened. The package sheet's statement that no delivery has passed is unchanged. `delivery_passed=false`.

## Proposed next tasks

1. **S.** Pin the measured current reports in the existing width / vertex-ring tests, without changing the round. Input: replace `(0,0,1)` with `(0.000201, 0, 1)`, shift 0. Expected: both `geometry_report` cut flags `missing=0`, `new=0`, `off=0`, `ok=true`. Input: add `(0.004003, 0, 1)`. Expected: `cut_joint_report` `ok=true`, `off_joint_count=0`. Input: add `(0.996003, 0, 1)`. Expected: `ok=false`, `off_joint_count=1`, `off_joint=[{"source_polygon": 0, "u_m": 0.996, "off_joint_m": 0.004}]`. Input: the pair `(0.003995,0,1)`, `(0.004005,0,1)` at shift 0. Expected: `new=1`, cut `ok=true`. Same pair at shift `(1024,1024,1024)`. Expected: `new=2`, cut `ok=false`, `off_joint_count=1`. Advances #149.
2. **M.** Do not start until you choose the comparison: keep this 5-decimal unique, or compare the recovered floats with no decimal round. If the choice is the unrounded float predicate, the same four inputs must come out the other way: the replaced corner `missing=1`, `new=1`, `ok=false`; `0.004003` cut `ok=false`, `off_joint_count=1`; `0.996003` cut `ok=true`, `off_joint_count=0`; the pair `new=2` and cut `ok=false` at shift 0 as well as at 1024. Advances #149.

## Open questions for the user

- Should the 5-decimal unique stay, and should tests pin the flips above as the current policy?
- `0.996` fails the 4 mm test in float64 while the decimal `0.996` is exactly 4 mm from 1. Is that in scope for the joint check?
- `off_examples` and `off_joint` round once more, to 4 decimals, so `0.00021` and `0.00401` print as `0.0002` and `0.004`. Should the example store the 5-decimal point the test used?

## Reproduction code

Verified with the command above. Exit 0. Stdlib for the references; `qa_packages` is imported only as the system under test. The script writes `C:/x/t_57cda816/probe_results.json` and does not write inside the repo.

```python
"""Frozen probe for qa_packages._new_vertices round-to-5-decimals.

Stdlib reference plus production calls. Does not import pytest.
Inputs are the matrix in docs/research/source-new-vertex-quantization-boundary.md.
"""
from __future__ import annotations

import copy
import json
import math
import sys
import traceback
import warnings
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path

ROOT = Path(r"C:\Users\artsafro\agr-pilot\AGR-DigitalTwin\.worktrees\t_57cda816")
sys.path.insert(0, str(ROOT / "jobs" / "TEC26-OKS" / "scripts"))
import qa_packages  # noqa: E402

np = qa_packages.np

OUT = Path(r"C:\x\t_57cda816\probe_results.json")
GRID = Decimal("0.00001")
TOL_EXACT = Fraction(2, 10000)
HALF_EXACT = Fraction(4, 1000)
T_EXACT = Fraction(1, 1000000)
P_EXACT = Fraction(1)
BASE = (("0", "0", "1"), ("4", "0", "1"), ("4", "0", "3"), ("0", "0", "3"))
Y_TRANS = (
    "0", "0.000194", "0.000195", "0.000199", "0.000200", "0.000201",
    "0.000204", "0.000205", "0.000206", "-0.000201", "-0.000205",
)
X_MOVE = (
    "0.000005", "0.000194", "0.000195", "0.000199", "0.000200", "0.000201",
    "0.000204", "0.000205", "0.000206",
)
Y_MOVE = ("0.000199", "0.000200", "0.000201", "0.000204", "0.000205")
XYZ_MOVE = ("0.000199", "0.000201")
JOINT_X = (
    "0.003994", "0.003995", "0.003997", "0.004000", "0.004003", "0.004004",
    "0.004005", "0.004006", "0.995994", "0.995996", "0.996000", "0.996003",
    "0.996005", "0.996006", "1", "0.5",
)


def as_fraction(token: str) -> Fraction:
    if token == "1/3":
        return Fraction(1, 3)
    return Fraction(Decimal(token))


def dec_round5(token: str) -> str:
    return str(Decimal(as_fraction(token).numerator) / Decimal(as_fraction(token).denominator)
               if False else Decimal(as_fraction(token).numerator) / Decimal(as_fraction(token).denominator))


def quantize_fraction(value: Fraction) -> Decimal:
    dec = Decimal(value.numerator) / Decimal(value.denominator)
    return dec.quantize(GRID, rounding=ROUND_HALF_EVEN)


def floats_of(pts):
    return [[float(as_fraction(c)) for c in p] for p in pts]


def frac_pts(pts):
    return [tuple(as_fraction(c) for c in p) for p in pts]


def make_spec():
    return {"zero_m": 0, "facade_uv": ["F"], "finishes": {"F": {"P": [1, 1]}}}


def plain(obj):
    if isinstance(obj, dict):
        return {str(k): plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return plain(obj.tolist())
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, Fraction):
        return str(obj)
    if isinstance(obj, Decimal):
        return format(obj, "f")
    if isinstance(obj, (bool, int, str)) or obj is None:
        return obj
    if isinstance(obj, float):
        return obj
    return str(obj)


def frac_text(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def float_pack(value: float) -> dict:
    exact = Fraction.from_float(value)
    return {
        "repr": repr(value),
        "fraction": frac_text(exact),
        "decimal_from_float": format(Decimal.from_float(value), "f"),
    }


def edges_of(n):
    face = list(range(n)) if False else None
    return face


def face_edges(face):
    return [tuple(sorted((face[k], face[(k + 1) % len(face)]))) for k in range(len(face))]


def linf(q, s):
    return max(abs(q[i] - s[i]) for i in range(3))


def on_edge_exact(q, a, b):
    e = tuple(b[i] - a[i] for i in range(3))
    ee = e[0] * e[0] + e[1] * e[1] + e[2] * e[2]
    if ee == 0:
        return False
    t = ((q[0] - a[0]) * e[0] + (q[1] - a[1]) * e[1] + (q[2] - a[2]) * e[2]) / ee
    if not (T_EXACT < t < 1 - T_EXACT):
        return False
    dist2 = sum((a[i] + t * e[i] - q[i]) ** 2 for i in range(3))
    return dist2 <= TOL_EXACT * TOL_EXACT


def on_edge_float(q, a, b, tol):
    e0, e1, e2 = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    ee = e0 * e0 + e1 * e1 + e2 * e2
    t = ((q[0] - a[0]) * e0 + (q[1] - a[1]) * e1 + (q[2] - a[2]) * e2) / max(ee, 1e-30)
    if not (1e-6 < t < 1.0 - 1e-6):
        return False
    return math.hypot(a[0] + t * e0 - q[0], a[1] + t * e1 - q[1], a[2] + t * e2 - q[2]) <= tol


def frame_ok(src):
    ys = {p[1] for p in src}
    return (
        len(ys) == 1
        and max(p[0] for p in src) > min(p[0] for p in src)
        and max(p[2] for p in src) > min(p[2] for p in src)
    )


def predict_exact(src, out, cuts):
    if not frame_ok(src):
        return {"frame": False}
    origin = min(p[0] for p in src)
    edges = []
    # caller passes the face separately via closure; use convex quad order 0..n-1 only when identity.
    return origin


def classify_exact(src, out, face, cuts):
    if not frame_ok(src):
        return {"frame": False}
    origin = min(p[0] for p in src)
    edges = face_edges(face)
    uniq = sorted(set(tuple(p) for p in out))
    new = []
    for q in uniq:
        if min(linf(q, s) for s in src) > TOL_EXACT:
            new.append(q)
    missing = 0
    for s in src:
        if min(linf(q, s) for q in uniq) > TOL_EXACT:
            missing += 1
    off = []
    for q in new:
        hit = False
        for a, b in edges:
            if on_edge_exact(q, src[a], src[b]):
                hit = True
                break
        if not hit:
            off.append(q)
    checked = 0
    off_joint = 0
    for q in new:
        on_pat = any(on_edge_exact(q, src[a], src[b]) for a, b in edges)
        if not on_pat:
            continue
        checked += 1
        u = q[0] - origin
        r = u % P_EXACT
        dist = min(r, P_EXACT - r)
        if dist > HALF_EXACT:
            off_joint += 1
    geom = {
        "missing_source_vertices": missing,
        "new_vertices": len(new),
        "new_off_source_edges": len(off),
        "ok": missing == 0 and len(off) == 0 and (cuts or len(new) == 0),
    }
    cut = {
        "ok": off_joint == 0,
        "new_vertices": len(new),
        "checked_on_patterned_edges": checked,
        "off_joint_count": off_joint,
    }
    return {"frame": True, "geom": geom, "cut": cut}


def classify_float(src, out, face, cuts, tol, half):
    edges = face_edges(face)
    uniq = sorted(set(tuple(float(c) for c in p) for p in out))
    new = []
    for q in uniq:
        if min(linf(q, s) for s in src) > tol:
            new.append(q)
    missing = 0
    for s in src:
        if min(linf(tuple(q), s) for q in uniq) > tol:
            missing += 1
    off = []
    for q in new:
        if not any(on_edge_float(q, src[a], src[b], tol) for a, b in edges):
            off.append(q)
    origin = min(p[0] for p in src)
    checked = 0
    off_joint = 0
    details = []
    for q in new:
        if not any(on_edge_float(q, src[a], src[b], tol) for a, b in edges):
            continue
        checked += 1
        u = q[0] - origin
        r = u % 1
        dist = min(r, 1 - r)
        if dist > half:
            off_joint += 1
            details.append({"u": u, "dist": dist, "u_r4": round(float(u), 4), "dist_r4": round(float(dist), 4)})
    geom = {
        "missing_source_vertices": missing,
        "new_vertices": len(new),
        "new_off_source_edges": len(off),
        "ok": missing == 0 and len(off) == 0 and (cuts or len(new) == 0),
    }
    cut = {
        "ok": off_joint == 0,
        "new_vertices": len(new),
        "checked_on_patterned_edges": checked,
        "off_joint_count": off_joint,
        "off_detail": details,
    }
    return {"geom": geom, "cut": cut}


def stored_exact_points(float_pts):
    return [tuple(Fraction.from_float(c) for c in p) for p in float_pts]


def geom_fields(report):
    return {
        "missing_source_vertices": report["missing_source_vertices"],
        "new_vertices": report["new_vertices"],
        "new_off_source_edges": report["new_off_source_edges"],
        "ok": report["ok"],
    }


def cut_fields(report):
    return {
        "ok": report["ok"],
        "new_vertices": report["new_vertices"],
        "checked_on_patterned_edges": report["checked_on_patterned_edges"],
        "off_joint_count": report["off_joint_count"],
    }


def diff(a, b):
    out = {}
    for k in a:
        if a[k] != b[k]:
            out[k] = {"left": a[k], "right": b[k]}
    return out


def point_measure(token_pt, float_pt, rounded_pt):
    rows = []
    for token, fv, rv in zip(token_pt, float_pt, rounded_pt):
        exact = as_fraction(token)
        stored = Fraction.from_float(fv)
        rounded = Fraction.from_float(rv)
        rows.append({
            "token": token,
            "exact": frac_text(exact),
            "stored": float_pack(fv),
            "np_round5": float_pack(rv),
            "decimal_quantize_of_token": format(quantize_fraction(exact), "f"),
            "decimal_quantize_of_stored": format(
                Decimal.from_float(fv).quantize(GRID, rounding=ROUND_HALF_EVEN), "f"
            ),
            "round_move": frac_text(abs(rounded - stored)),
            "round_move_gt_5e-6": abs(rounded - stored) > Fraction(5, 1000000),
            "np_matches_quantize_of_stored": Decimal.from_float(rv) == Decimal.from_float(fv).quantize(
                GRID, rounding=ROUND_HALF_EVEN
            ) or abs(Decimal.from_float(rv) - Decimal.from_float(fv).quantize(GRID, rounding=ROUND_HALF_EVEN)) == 0,
        })
        # The equality above is clumsy when the quantized decimal is not binary.
        # Replace with a numeric compare of the two Decimals.
        q_stored = Decimal.from_float(fv).quantize(GRID, rounding=ROUND_HALF_EVEN)
        rows[-1]["np_minus_quantize_stored"] = format(Decimal.from_float(rv) - q_stored, "f")
        rows[-1]["np_matches_quantize_of_stored"] = Decimal.from_float(rv) == q_stored
    return rows


def nearest_dists(q_frac, src_frac):
    best = min(linf(q_frac, s) for s in src_frac)
    best_e2 = None
    for s in src_frac:
        d2 = sum((q_frac[i] - s[i]) ** 2 for i in range(3))
        if best_e2 is None or d2 < best_e2:
            best_e2 = d2
    return best, best_e2


def build_cases():
    cases = []

    def add(row, cid, src, out, shift=("0", "0", "0"), face=(0, 1, 2, 3)):
        cases.append({
            "row": row,
            "id": cid,
            "src": tuple(tuple(p) for p in src),
            "out": tuple(tuple(p) for p in out),
            "shift": tuple(shift),
            "face": tuple(face),
        })

    add(1, "R1", BASE, BASE)
    add(2, "R2a", _setx(BASE, "0.1"), _setx(BASE, "0.1"))
    add(2, "R2b", _setx(BASE, "0.123456"), _setx(BASE, "0.123456"))
    add(2, "R2c", _setx(BASE, "0.123455"), _setx(BASE, "0.123455"))
    add(2, "R2d", _setx(BASE, "0.123456"), _setx(BASE, "0.12346"))
    add(2, "R2e", _setx(BASE, "1/3"), _setx(BASE, "1/3"))

    for y in Y_TRANS:
        add(3, f"R3-y-{y}", BASE, BASE + (("2", y, "1"),))
    for d in ("0.0001414", "0.0001415"):
        add(3, f"R3-d-{d}", BASE, BASE + (("2", d, _sum("1", d)),))

    for x in X_MOVE:
        moved = (("x",) and ((x, "0", "1"),))
        add(4, f"R4-repl-x-{x}", BASE, ((x, "0", "1"),) + BASE[1:])
        add(4, f"R4-add-x-{x}", BASE, BASE + ((x, "0", "1"),))
    for y in Y_MOVE:
        add(4, f"R4-repl-y-{y}", BASE, (("0", y, "1"),) + BASE[1:])
        add(4, f"R4-add-y-{y}", BASE, BASE + (("0", y, "1"),))
    for d in XYZ_MOVE:
        add(4, f"R4-repl-xyz-{d}", BASE, ((d, d, _sum("1", d)),) + BASE[1:])
        add(4, f"R4-add-xyz-{d}", BASE, BASE + ((d, d, _sum("1", d)),))

    for x in JOINT_X:
        add(5, f"R5-x-{x}", BASE, BASE + ((x, "0", "1"),))

    v0, v1, v2, v3 = BASE
    mid = ("2", "0", "1")
    add(6, "R6-dup-corners", BASE, (v2, v0, v0, v3, v1, v2))
    add(6, "R6-mid-mixed", BASE, (mid, v3, v1, mid, v0, v2, v0))
    pair_near = (("0.003997", "0", "1"), ("0.004003", "0", "1"))
    pair_tie = (("0.003995", "0", "1"), ("0.004005", "0", "1"))
    add(6, "R6-pair-near", BASE, BASE + pair_near)
    add(6, "R6-pair-near-rev", BASE, BASE + tuple(reversed(pair_near)))
    add(6, "R6-pair-tie", BASE, BASE + pair_tie)
    add(6, "R6-pair-tie-rev", BASE, BASE + tuple(reversed(pair_tie)))
    off = ("2", "0.001", "1")
    add(6, "R6-off-x2", BASE, BASE + (off, off))
    perm_src = (v3, v2, v1, v0)
    perm_face = (3, 2, 1, 0)
    add(6, "R6-src-perm", perm_src, perm_src, face=perm_face)
    extra = ("0.004005", "0", "1")
    add(6, "R6-extra-front", BASE, (extra,) + BASE)
    add(6, "R6-extra-back", BASE, BASE + (extra,))
    add(6, "R6-perm-src-extra", perm_src, perm_src + (extra,), face=perm_face)

    worlds = {
        "S0": BASE,
        "S1": BASE + (("2", "0.000201", "1"),),
        "S2": BASE + (("2", "0.000205", "1"),),
        "S3": (("0.000201", "0", "1"),) + BASE[1:],
        "S4": BASE + (("0.004003", "0", "1"),),
        "S5": BASE + (("0.004005", "0", "1"),),
        "S6": BASE + pair_tie,
        "S7": BASE + (("2", "0.0001415", "1.0001415"),),
    }
    for name, world in worlds.items():
        for shift in (("0", "0", "0"), ("0.5", "0.5", "0.5"), ("1024", "1024", "1024")):
            add(7, f"R7-{name}-shift-{shift[0]}", BASE if name != "S3" else BASE, world, shift=shift)
    # S3 source is the unmoved quad; world delivery has the replaced corner.
    # The loop above uses BASE as source for every name except it still passes world as out,
    # and for S3 source must stay BASE. That is what the ternary does. Good.
    return cases


def _setx(pts, x):
    out = [tuple(p) for p in pts]
    out[0] = (x, out[0][1], out[0][2])
    return tuple(out)


def _sum(a, b):
    total = as_fraction(a) + as_fraction(b)
    # Prefer a decimal string when the sum is a terminating decimal.
    dec = Decimal(total.numerator) / Decimal(total.denominator)
    text = format(dec, "f")
    if as_fraction(text) != total:
        raise SystemExit(f"cannot encode sum {a}+{b} as {text}")
    return text


def run_case(case, tol, half):
    src_tok = case["src"]
    out_tok = case["out"]
    shift_tok = case["shift"]
    face = list(case["face"])
    src_f = floats_of(src_tok)
    world_f = floats_of(out_tok)
    shift_f = [float(as_fraction(c)) for c in shift_tok]
    # Row 7 and everyone: delivery = world_float - shift_float.
    out_f = [[world_f[i][k] - shift_f[k] for k in range(3)] for i in range(len(world_f))]
    spec = make_spec()
    expected = ["F"]
    shift = list(shift_f)
    src_v = copy.deepcopy(src_f)
    out_v = copy.deepcopy(out_f)
    faces = copy.deepcopy([face])
    snap = copy.deepcopy((src_v, faces, expected, spec, out_v, shift))
    caught = []
    with warnings.catch_warnings(record=True) as caught_w:
        warnings.simplefilter("always")
        try:
            g_false = qa_packages.geometry_report(src_v, faces, out_v, shift, False)
            g_true = qa_packages.geometry_report(src_v, faces, out_v, shift, True)
            c_rep = qa_packages.cut_joint_report(src_v, faces, expected, spec, out_v, shift)
        except Exception:
            return {
                "id": case["id"],
                "row": case["row"],
                "error": traceback.format_exc(),
                "mutated": (src_v, faces, expected, spec, out_v, shift) != snap,
            }
        caught = [str(w.message) for w in caught_w]
    mutated = (src_v, faces, expected, spec, out_v, shift) != snap
    recovered = np.asarray(out_f, float) + np.asarray(shift_f, float)
    rounded = np.round(recovered, 5)
    uniq = np.unique(rounded, axis=0)
    src_frac = frac_pts(src_tok)
    out_frac = frac_pts(out_tok)
    # Decimal reference is on the intended world tokens, independent of shift.
    dec_false = classify_exact(src_frac, out_frac, face, False)
    dec_true = classify_exact(src_frac, out_frac, face, True)
    # Stored-float reference: recovered world floats, no 5-decimal round.
    rec_list = recovered.tolist()
    flt_false = classify_float(src_f, rec_list, face, False, tol, half)
    flt_true = classify_float(src_f, rec_list, face, True, tol, half)
    stored_false = classify_exact(stored_exact_points(src_f), stored_exact_points(rec_list), face, False)
    stored_true = classify_exact(stored_exact_points(src_f), stored_exact_points(rec_list), face, True)
    harness_false = classify_float(src_f, uniq.tolist(), face, False, tol, half)
    harness_true = classify_float(src_f, uniq.tolist(), face, True, tol, half)
    # Distances for non-base points, and for vertex 0 when it is the edited one.
    measures = []
    max_move = Fraction(0)
    for i, (tok, fv, rv) in enumerate(zip(out_tok, rec_list, rounded.tolist())):
        rows = point_measure(tok, [float(x) for x in fv], [float(x) for x in rv])
        for comp, row in enumerate(rows):
            move = abs(Fraction.from_float(float(rv[comp])) - Fraction.from_float(float(fv[comp])))
            if move > max_move:
                max_move = move
        q_dec = tuple(as_fraction(c) for c in tok)
        q_stored = tuple(Fraction.from_float(float(x)) for x in fv)
        q_round = tuple(Fraction.from_float(float(x)) for x in rv)
        d_dec, e2_dec = nearest_dists(q_dec, src_frac)
        d_stored, e2_stored = nearest_dists(q_stored, stored_exact_points(src_f))
        d_round, e2_round = nearest_dists(q_round, stored_exact_points(src_f))
        measures.append({
            "index": i,
            "components": rows,
            "linf_decimal_to_source": frac_text(d_dec),
            "euclid2_decimal_to_source": frac_text(e2_dec),
            "linf_stored_to_source": frac_text(d_stored),
            "euclid2_stored_to_source": frac_text(e2_stored),
            "linf_rounded_to_source_float": frac_text(d_round),
            "euclid2_rounded_to_source_float": frac_text(e2_round),
            "recovered_minus_intent": [
                frac_text(Fraction.from_float(float(fv[k])) - as_fraction(tok[k])) for k in range(3)
            ],
        })
    gf = plain(g_false)
    gt = plain(g_true)
    cr = plain(c_rep)
    return {
        "id": case["id"],
        "row": case["row"],
        "shift": list(shift_tok),
        "mutated": mutated,
        "warnings": caught,
        "max_round_move": frac_text(max_move),
        "max_round_move_gt_5e-6": max_move > Fraction(5, 1000000),
        "production": {"cuts_false": gf, "cuts_true": gt, "cut_joint": cr},
        "decimal_reference": {"cuts_false": dec_false, "cuts_true": dec_true},
        "stored_float_exact_threshold": {"cuts_false": stored_false, "cuts_true": stored_true},
        "unrounded_float_predicate": {"cuts_false": flt_false, "cuts_true": flt_true},
        "harness_on_rounded_points": {
            "cuts_false_diff": diff(geom_fields(gf), harness_false["geom"]),
            "cuts_true_diff": diff(geom_fields(gt), harness_true["geom"]),
            "cut_diff": diff(cut_fields(cr), harness_true["cut"]),
        },
        "prod_vs_unrounded_float": {
            "cuts_false": diff(geom_fields(gf), flt_false["geom"]),
            "cuts_true": diff(geom_fields(gt), flt_true["geom"]),
            "cut": diff(cut_fields(cr), flt_true["cut"]),
        },
        "prod_vs_decimal": {
            "cuts_false": diff(geom_fields(gf), dec_false["geom"]),
            "cuts_true": diff(geom_fields(gt), dec_true["geom"]),
            "cut": diff(cut_fields(cr), dec_true["cut"]),
        },
        "prod_vs_stored_exact_threshold": {
            "cuts_false": diff(geom_fields(gf), stored_false["geom"]),
            "cuts_true": diff(geom_fields(gt), stored_true["geom"]),
            "cut": diff(cut_fields(cr), stored_true["cut"]),
        },
        "decimal_vs_stored_exact": {
            "cuts_false": diff(dec_false["geom"], stored_false["geom"]),
            "cuts_true": diff(dec_true["geom"], stored_true["geom"]),
            "cut": diff(dec_true["cut"], stored_true["cut"]),
        },
        "points": measures,
        "rounded_unique": uniq.tolist(),
    }


def main():
    tol = qa_packages.geometry_report.__defaults__[-1]
    cut_tol = qa_packages.cut_joint_report.__defaults__[-1]
    half = 4 / 1000
    src_lines = Path(qa_packages.__file__).read_text(encoding="utf-8").splitlines()
    snippet = {str(i): src_lines[i - 1] for i in range(162, 212)}
    cases = build_cases()
    results = []
    harness_bad = []
    mutated = []
    errors = []
    for case in cases:
        item = run_case(case, tol, half)
        results.append(item)
        if item.get("error"):
            errors.append(item["id"])
            print(f"ERROR {item['id']}")
            continue
        if item["mutated"]:
            mutated.append(item["id"])
        h = item["harness_on_rounded_points"]
        if h["cuts_false_diff"] or h["cuts_true_diff"] or h["cut_diff"]:
            harness_bad.append(item["id"])
        flags = []
        if item["prod_vs_unrounded_float"]["cuts_false"] or item["prod_vs_unrounded_float"]["cuts_true"] or item["prod_vs_unrounded_float"]["cut"]:
            flags.append("DIFF_FLOAT")
        if item["prod_vs_decimal"]["cuts_false"] or item["prod_vs_decimal"]["cuts_true"] or item["prod_vs_decimal"]["cut"]:
            flags.append("DIFF_DEC")
        if item["decimal_vs_stored_exact"]["cuts_false"] or item["decimal_vs_stored_exact"]["cuts_true"] or item["decimal_vs_stored_exact"]["cut"]:
            flags.append("BIN")
        mark = ",".join(flags) if flags else "same"
        pf = item["production"]["cuts_false"]
        pt = item["production"]["cuts_true"]
        pc = item["production"]["cut_joint"]
        print(
            f"{item['id']} {mark} "
            f"F={pf['missing_source_vertices']}/{pf['new_vertices']}/{pf['new_off_source_edges']}/{pf['ok']} "
            f"T={pt['missing_source_vertices']}/{pt['new_vertices']}/{pt['new_off_source_edges']}/{pt['ok']} "
            f"C={pc['ok']}/{pc['new_vertices']}/{pc['checked_on_patterned_edges']}/{pc['off_joint_count']} "
            f"move={item['max_round_move']}"
        )
    # Preservation groups.
    by_id = {item["id"]: item for item in results if not item.get("error")}

    def same_prod(a, b):
        if a not in by_id or b not in by_id:
            return False
        return by_id[a]["production"] == by_id[b]["production"]

    preserve = {
        "R6_pair_near_order": same_prod("R6-pair-near", "R6-pair-near-rev"),
        "R6_pair_tie_order": same_prod("R6-pair-tie", "R6-pair-tie-rev"),
        "R6_extra_ends": same_prod("R6-extra-front", "R6-extra-back"),
        "R6_src_perm_vs_R1": same_prod("R6-src-perm", "R1"),
        "R6_perm_extra_vs_back": same_prod("R6-perm-src-extra", "R6-extra-back"),
        "R6_dup_corners_vs_R1": same_prod("R6-dup-corners", "R1"),
    }
    shift_preserve = {}
    for name in ("S0", "S1", "S2", "S3", "S4", "S5", "S6", "S7"):
        shift_preserve[name] = {
            "0_vs_0.5": same_prod(f"R7-{name}-shift-0", f"R7-{name}-shift-0.5"),
            "0_vs_1024": same_prod(f"R7-{name}-shift-0", f"R7-{name}-shift-1024"),
        }
    payload = {
        "delivery_passed": False,
        "python": sys.version,
        "numpy": np.__version__,
        "qa_packages": str(Path(qa_packages.__file__).resolve()),
        "geometry_tol_default": float_pack(tol),
        "cut_tol_default": float_pack(cut_tol),
        "half_4_over_1000": float_pack(half),
        "tol_exact": frac_text(TOL_EXACT),
        "half_exact": frac_text(HALF_EXACT),
        "tol_float_minus_exact": frac_text(Fraction.from_float(tol) - TOL_EXACT),
        "half_float_minus_exact": frac_text(Fraction.from_float(half) - HALF_EXACT),
        "snippet_162_211": snippet,
        "case_count": len(cases),
        "case_ids": [c["id"] for c in cases],
        "harness_bad": harness_bad,
        "mutated": mutated,
        "errors": errors,
        "preserve": preserve,
        "shift_preserve": shift_preserve,
        "results": results,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"cases={len(cases)} harness_bad={len(harness_bad)} mutated={len(mutated)} errors={len(errors)}")
    print(f"wrote {OUT}")
    if harness_bad or mutated or errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

