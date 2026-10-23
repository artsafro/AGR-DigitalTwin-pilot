# Source finish QA: can non-finite or overflowing areas silently clear coverage?

Research card t_c55decc5 (question from #622/#624 area-path follow-ups). Pinned tree `45a35a2dca43ba4880b2a7f2359f376f2d4884fc`, read from `.git/refs/heads/docs/research-source-finish-area-numeric-domain` (worktree HEAD is that ref). `git` was not run. No pytest, no repo-source edits, no TEC26/Drive assets. `delivery_passed=false`.

Probe: CPython 3.14.7, numpy 2.5.3, `uv run python` on scripts frozen before each run: `C:/x/t_c55decc5/probe_area_numeric.py` then `C:/x/t_c55decc5/probe_area_numeric_mix.py`. Results: `C:/x/t_c55decc5/probe_results.json`, `C:/x/t_c55decc5/probe_mix_results.json`. Every `source_finish_report` call returned (no exception) and emitted no warning. Every call left its inputs unchanged under a NaN-aware compare (`NaN` equals `NaN`; `+inf` does not equal `-inf`).

## Summary

`source_finish_report` covers a polygon when `abs(sum - p) > 1e-6 + 1e-5 * p` is false (`jobs/TEC26-OKS/scripts/qa_packages.py:153-154`). A false comparison is treated as covered. On this interpreter `NaN > x` is false and `inf > inf` is false, so the coverage counter stays 0.

With a matching owner and a matching finish, that false comparison becomes `ok: true`. Verified by run, one triangle, area A = 0.5: `t = NaN` or `p = NaN` or `p = +inf`, and also both sides `+inf`, both sides `-inf`, both sides `NaN`. Counters stay 0. No warning.

Finite-sum overflow of two `1e308` values becomes `+inf` inside the helper. Against a finite polygon area the polygon is uncovered (`ok: false`). Against a polygon area that is already that same overflow (`+inf`) the report returns `ok: true`.

`tri_areas` / `poly_areas` can emit `NaN` or `+inf` and do not raise. On every non-finite or overflowing mesh in this probe, `match_source_faces` returned an empty owner, so the fed report was `ok: false`. The coverage counter was still 0 whenever the polygon area was `NaN` or `+inf`, including a huge finite source paired with the unit triangle. `mesh_report` raises on non-finite delivered vertices and on non-finite derived triangle geometry; it does not raise on that huge-source / clean-delivery pair. `qa_packages.main` was not executed (it opens ZIP/PNG assets before the report). No delivery package was witnessed, and none is claimed. `delivery_passed=false`.

## Findings

Evidence: **Verified by run** = the probe above. **Source** = read from the pinned file, not executed as that case.

### What the predicate does

**Source.** Area mode is used only when both lists are passed (`qa_packages.py:153`). The triangle area is added only when `len(own) == 1` (`:142-144`). An empty owner increments `unmatched` and does not add (`:137-138`). `ok` is false when any counter is non-zero or `owners` is empty (`:157`). The documented band is `1e-6 + 1e-5 * area` (`:131-132`). There is no finiteness test.

**Verified by run.** Interpreter facts from the same process: `1e308 + 1e308` is `+inf`; `1e307 + 1e307` is `2e307` (finite); `float('nan') > 1` is false; `inf > inf` is false; `abs(0.5 - inf) > 1e-6 + 1e-5 * inf` is false; `abs(nan - 0.5) > 1e-6 + 1e-5 * 0.5` is false. `sys.float_info.max` is about `1.797e308`.

### Frozen report matrix

One source triangle `[[0, 1, 2]]`, expected `["A"]`, owner `[(0,)]`, delivered `["A"]`, except the two-triangle rows (owner `[(0,), (0,)]`, delivered `["A", "A"]`). Columns are `ok / tris / wrong_finish / unmatched / ambiguous / source_polygons_not_covered`. `examples` was `[]` on every row.

| case | kind | t | p | result |
|---|---|---|---|---|
| control_match | finite match | 0.5 | 0.5 | true / 1 / 0 / 0 / 0 / 0 |
| t_nan | raw nonfinite | NaN | 0.5 | **true / 1 / 0 / 0 / 0 / 0** |
| p_nan | raw nonfinite | 0.5 | NaN | **true / 1 / 0 / 0 / 0 / 0** |
| t_posinf | raw nonfinite | +inf | 0.5 | false / 1 / 0 / 0 / 0 / 1 |
| p_posinf | raw nonfinite | 0.5 | +inf | **true / 1 / 0 / 0 / 0 / 0** |
| t_neginf | raw nonfinite | -inf | 0.5 | false / 1 / 0 / 0 / 0 / 1 |
| p_neginf | raw nonfinite | 0.5 | -inf | false / 1 / 0 / 0 / 0 / 1 |
| t_zero | finite invalid, one side | 0 | 0.5 | false / 1 / 0 / 0 / 0 / 1 |
| p_zero | finite invalid, one side | 0.5 | 0 | false / 1 / 0 / 0 / 0 / 1 |
| t_neg | finite invalid, one side | -0.5 | 0.5 | false / 1 / 0 / 0 / 0 / 1 |
| p_neg | finite invalid, one side | 0.5 | -0.5 | false / 1 / 0 / 0 / 0 / 1 |
| t_pos_other | finite positive mismatch | 1 | 0.5 | false / 1 / 0 / 0 / 0 / 1 |
| p_pos_other | finite positive mismatch | 0.5 | 1 | false / 1 / 0 / 0 / 0 / 1 |
| both_zero | finite invalid, equal | 0 | 0 | **true / 1 / 0 / 0 / 0 / 0** |
| both_neg | finite invalid, equal | -0.5 | -0.5 | false / 1 / 0 / 0 / 0 / 1 |
| both_posinf | raw nonfinite, equal | +inf | +inf | **true / 1 / 0 / 0 / 0 / 0** |
| both_neginf | raw nonfinite, equal | -inf | -inf | **true / 1 / 0 / 0 / 0 / 0** |
| both_nan | raw nonfinite, equal | NaN | NaN | **true / 1 / 0 / 0 / 0 / 0** |
| sum_1e308_vs_finite_p | derived overflow vs finite | 1e308, 1e308 | 0.5 | false / 2 / 0 / 0 / 0 / 1 |
| sum_1e308_vs_1e308_p | derived overflow vs finite huge | 1e308, 1e308 | 1e308 | false / 2 / 0 / 0 / 0 / 1 |
| sum_1e308_vs_presum | derived overflow vs the same sum | 1e308, 1e308 | +inf (literal `1e308+1e308`) | **true / 2 / 0 / 0 / 0 / 0** |
| sum_1e307_vs_2e307 | finite large control | 1e307, 1e307 | 2e307 | true / 2 / 0 / 0 / 0 / 0 |

`both_neg` is uncovered because the residual is 0 and the threshold `1e-6 + 1e-5 * (-0.5)` is negative, so `0 > threshold` is true. That is the current formula, not a chosen zero/negative policy.

The silent full clears (`ok` true and coverage 0) are the bold rows. `t = +inf` or `t = -inf` against finite 0.5 is detected. `p = -inf` against finite 0.5 is detected. A finite positive mismatch is detected. Overflow of two finite `1e308` inputs is detected when `p` stays finite, and it is not detected when `p` is the overflowed sum.

### Producers and ownership

**Source.** `tri_areas` (`qa_packages.py:119-121`) is `float(norm(cross) / 2)` per delivered triangle. `poly_areas` (`:124-125`) is the Newell length over 2, or `0.0` when `_poly_geo` stores `None`. `_poly_geo` (`:68-71`) stores `None` only when `ln <= 0`. A NaN length does not take that branch. `match_source_faces` (`:95-116`) drops a polygon that fails the bbox, plane, or containment test. `float(norm(...))` squares components, so a cross component near `1e160` overflows the norm to `+inf` before the `/ 2`.

**Verified by run.** Shift is `[0, 0, 0]` unless the row says package shift (the expression at `qa_packages.py:309-310`). Fed columns are the report result after passing that row's actual `owners`, `tri_areas` and `poly_areas` through `source_finish_report` with finish `"A"`. `mesh_report` and `assign_finishes` were called on the same vertices; their exceptions are not coverage diagnostics.

| case | owners | tri | poly | mesh_report | assign_finishes | fed report |
|---|---|---|---|---|---|---|
| clean_unit | `(0,)` | 0.5 | 0.5 | passed | `["A"]` | true / 1 / 0 / 0 / 0 / 0 |
| delivered_nan, source unit | `()` | NaN | 0.5 | ValueError: vertices must be finite | `["A"]` | false / 1 / 0 / 0 / 1 / 1 |
| delivered_+inf, source unit | `()` | NaN | 0.5 | ValueError: vertices must be finite | `["A"]` | false / 1 / 0 / 0 / 1 / 1 |
| delivered_-inf, source unit | `()` | NaN | 0.5 | ValueError: vertices must be finite | `["A"]` | false / 1 / 0 / 0 / 1 / 1 |
| delivered legs `1e308`, source unit | `()` | +inf | 0.5 | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / 1 |
| both NaN x | `()` | NaN | NaN | ValueError: vertices must be finite | ValueError: non-finite vertex | false / 1 / 0 / 0 / 1 / **0** |
| both +inf x | `()` | NaN | NaN | ValueError: vertices must be finite | ValueError: non-finite vertex | false / 1 / 0 / 0 / 1 / **0** |
| both legs `1e308` | `()` | +inf | +inf | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| both leg `1e308`, height 1 | `()` | +inf | +inf | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| both leg `1e308`, height 1.7 | `()` | +inf | +inf | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| both collinear `(0,0,0),(1,0,0),(2,0,0)` | `()` | 0 | 0 | passed | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| rectangle legs `1e308` height 1, split into 2 tris | `(), ()` | +inf, +inf | NaN | ValueError: derived triangle geometry is not finite | `["A"]` | false / 2 / 0 / 2 / 0 / **0** |
| self span `1e10`, height 1 | `(0,)` | 5e9 | 5e9 | passed | `["A"]` | true / 1 / 0 / 0 / 0 / 0 |
| self span `1e154`, height 1 | `(0,)` | 5e153 | 5e153 | passed | `["A"]` | true / 1 / 0 / 0 / 0 / 0 |
| self span `1e160`, height 1 | `()` | +inf | +inf | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| source legs `1e308` height 1, delivered unit, shift 0 | `()` | 0.5 | +inf | passed (the unit mesh) | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| same pair, package shift `[5e307, 0.5, 0]` | `()` | 0.5 | +inf | passed | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |
| NaN source, delivered unit, shift 0 | `()` | 0.5 | NaN | passed | ValueError: non-finite vertex | false / 1 / 0 / 0 / 1 / **0** |
| self span `1e160`, package shift `[5e159, 0.5, 0]` | `()` | +inf | +inf | ValueError: derived triangle geometry is not finite | `["A"]` | false / 1 / 0 / 0 / 1 / **0** |

Bold coverage `0` with `ok` false means the coverage counter cleared while `unmatched` kept the report failed. Numpy `RuntimeWarning` (overflow / invalid multiply, dot, divide, cast) was emitted by the producer or by `mesh_report` on the overflowing rows, not by `source_finish_report`. Inputs of those calls were unchanged.

A separate feed used producer areas that were already `+inf` (`tri_areas` on three height-1.7 spans of `1e308`; each area `+inf`) with a **forced** owner `(0,)` on all three, not with `match_source_faces`. `p` = the sum of those areas (`+inf`) gave **true / 3 / 0 / 0 / 0 / 0**. The same areas with `p = [1.0]` gave false / 3 / 0 / 0 / 0 / 1. `mesh_report` on that mesh raised `derived triangle geometry is not finite`. This feed shows the helper certifies producer `+inf` when the caller supplies the owner. Match did not supply it.

`tri_areas` did not return a finite `1e308`. Spans `1e10` and `1e154` stayed finite (`5e9`, `5e153`) and self-matched with `ok` true. Span `1e160` and the `1e308` legs jumped to `+inf`. Two finite producer areas at the largest self-matched value (`5e153 + 5e153`) stay finite. The two-literal `1e308 + 1e308` overflow is a direct argument of the helper, not a pair `tri_areas` emitted here.

`poly_areas` on the clean unit triangle returned a numpy scalar `0.5` (`ln / 2` is not wrapped in `float`). `tri_areas` returned a Python `float`. The clean feed still matched.

### Earlier checks on the package path

**Source.** The only production calls are `qa_packages.py:410` and `:412`, inside `main`. `check` (`:275-278`) records a failure and does not return. The only early return before the report is a missing main mesh (`:287-289`). Order that matters:

1. `mesh_report` on the delivered VPM/NPM vertices (`:297-299`), which raises `ValueError("vertices must be finite")` (`src/dt_ai/ops/inv_xview.py:569-570`) and, later inside pair setup, `ValueError("derived triangle geometry is not finite")` (`inv_xview.py:477-478`).
2. `Image.open` of the finish PNGs (`qa_packages.py:361-363`). This needs the texture assets. It sits before the report.
3. `finish_map.assign_finishes` (`qa_packages.py:403`), which calls `_finite` and raises `ValueError` on a non-finite source vertex (`finish_map.py:314-317`). Huge finite coordinates pass that test.
4. `poly_areas` / `tri_areas` / `source_finish_report` (`qa_packages.py:409-413`).

**Verified by run** for steps 1, 3 and the numeric functions. **Not run:** `main`, `Image.open`, the ZIPs, the KPP file, the AC08 dump. An exception from `mesh_report` or `assign_finishes` aborts `main` before the report is written. That is not a coverage diagnostic and it is not `ok: true`.

What those executed gates do to the silent full clear:

- Delivered NaN, +inf, -inf, or a derived `+inf` triangle: `mesh_report` raises. `main` does not reach `source_finish_report` on that delivered mesh.
- Non-finite source vertices: `assign_finishes` raises, so `main` does not reach `poly_areas` on that source. Calling `poly_areas` anyway returns `NaN` and does not raise.
- Huge finite source (`1e308` by 1) and a clean unit delivery: `mesh_report` on the delivery passes, `assign_finishes` returns `["A"]`, `poly_areas` is `+inf`, match owner is empty, report is `ok` false with coverage 0. Nothing executed in this pair raises before the report. `main` itself was not run, because step 2 needs assets. No package file was written.

Other callers, **source only** (pytest was not run):

- `tests/jobs/test_source_finish_area_count_controls.py:82-83` refuses the call unless every area is finite and `> 0`. That caller cannot pass these rows.
- `tests/jobs/test_tec26_ac08_pilot.py:579-582` calls the real producers on the AC08 dump (`:30-33`, an asset). Not opened. Later calls in that file (`:633`, `:638`, `:642`, `:649`, `:657-665`) omit the area arguments, so they use the count rule (`qa_packages.py:155-156`), not this predicate.

`docs/domain/areas/body.md` indexes BODY requirements. Its L2 column names `check_floor_areas` for storey area (BODY-Q) and does not define a finite-area rule for `source_finish_report`. This predicate lives in the TEC26 package script.

## How it applies to this repository

- Predicate and the silent comparison: `jobs/TEC26-OKS/scripts/qa_packages.py:137-157`.
- Area producers: `tri_areas` `:119-121`, `poly_areas` `:124-125`, `_poly_geo` `:60-76`, `match_source_faces` `:95-116`.
- Production caller: `qa_packages.py:404-413`, after `mesh_report` `:297-299` and `assign_finishes` `:403`. The check name is `source_finish_vpm` / `source_finish_npm`. `ok` true marks that check passed (`:272-276`).
- Delivered-vertex rejection: `src/dt_ai/ops/inv_xview.py:569-570` and `:477-478`.
- Source-vertex rejection: `jobs/TEC26-OKS/scripts/finish_map.py:314-317`.
- Direct test caller that already excludes this domain: `tests/jobs/test_source_finish_area_count_controls.py:75-83`.

Helper-level silent `ok: true` is executed. Producer-plus-match did not return `ok: true` on the bad meshes, because the owner was empty. The coverage counter still cleared when the polygon area was non-finite. No end-to-end `main` witness, so no delivery exposure is claimed.

## Reproduction

Compact. The full frozen matrix is the probe scripts named above. From the worktree, with `jobs/TEC26-OKS/scripts` on `sys.path`:

```python
import math
import qa_packages as q
A = 0.5
src, own, got = [[0, 1, 2]], [(0,)], ["A"]
def R(t, p, owners=own, delivered=got):
    return q.source_finish_report(["A"], src, owners, delivered, t_areas=t, p_areas=p)
# true, true, true  -- NaN either side, and +inf on p, all clear coverage
print(R([float("nan")], [A])["ok"], R([A], [float("nan")])["ok"], R([A], [float("inf")])["ok"])
# false -- two finite 1e308 values overflow to +inf against a finite polygon area
print(R([1e308, 1e308], [A], [(0,), (0,)], ["A", "A"])["ok"])
# true -- the same overflow against p that is already 1e308+1e308
print(R([1e308, 1e308], [1e308 + 1e308], [(0,), (0,)], ["A", "A"])["ok"])
```

## Proposed next tasks

1. **Non-finite area values must not count as coverage**, size S, `Archive: no roadmap link`. The question was posed under #622/#624; those issues were not re-listed here. At `qa_packages.py:153-154` a comparison that is not true currently means covered, and with a matching owner that becomes `ok: true`. Pair: one triangle, owner `(0,)`, finish `"A"`, `t=[nan]`, `p=[0.5]` → today `true / 1 / 0 / 0 / 0 / 0`; the report should be failed and polygon 0 should not be counted covered. Pair: `t=[0.5]`, `p=[+inf]` → same today, same expected failure. Pair: `t=[1e308, 1e308]`, `p=[1e308+1e308]`, owners `[(0,), (0,)]` → today `true / 2 / 0 / 0 / 0 / 0`; expected failure. Keep the finite control `t=p=0.5` at `true / 1 / 0 / 0 / 0 / 0` and the finite mismatch `t=[1.0]`, `p=[0.5]` at `false / 1 / 0 / 0 / 0 / 1`. Leave the existing tolerance numbers as they are. Do not decide zero or negative area in this task (`both_zero` is `ok` true today; `both_neg` is `ok` false today). Do not add a key name here.

2. **Empty owner plus a non-finite polygon area must not clear the coverage counter**, size S, `Archive: no roadmap link`. The area is not added when the owner is empty (`qa_packages.py:137-138`), and the predicate still treats `NaN` and `+inf` as covered, so `source_polygons_not_covered` stays 0 while `unmatched` makes `ok` false. Pair: source and delivered both the unit triangle with x = NaN, shift 0, actual `match_source_faces` / `tri_areas` / `poly_areas` outputs → today `false / 1 / 0 / 0 / 1 / 0`; expected `unmatched` still 1 and polygon 0 counted not covered. Pair: source `(0,0,0), (1e308,0,0), (0,1,0)`, delivered unit triangle, package shift `[5e307, 0.5, 0]` → today `mesh_report` on the delivery passes, `assign_finishes` returns `["A"]`, report `false / 1 / 0 / 0 / 1 / 0`; expected the same unmatched count and polygon 0 not covered. This is the same predicate, not a new package gate and not a `main()` change. `main()` was not run.

## Open questions for the user

1. For a matching owner, should NaN / +inf / the `1e308+1e308` overflow fail the report, or abort with an exception? Both are "not `ok: true`". This note does not choose.
2. Equal zeros currently certify when the caller supplies the owner (`both_zero`). The collinear mesh does not supply that owner, and its report fails on `unmatched` while the coverage counter stays 0. Is a supplied 0 in domain? Not decided. Equal negatives already fail the current formula.
3. `qa_packages.main` was not executed, because the PNG/ZIP reads sit before the report. Is the function-level witness enough, or should a later card run `main` on a fully synthetic package with no TEC26 assets?
