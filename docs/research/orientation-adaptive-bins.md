# Orientation adaptive candidate filtering (#203)

Synthetic data only; no `data/` inputs. Base: `5e7b85526a7bfac0dff5a7d6897bbbedd4e3a056`.
Environment: Windows 11, CPython 3.14.7, NumPy 2.5.3, Shapely 2.1.2 (`uv sync`).

## Algorithm and equivalence boundary

- Adaptive resolution: `clip(ceil(4 * sqrt(triangles + rays)), 64, 1024)`.
  A factor of one left too many ray/triangle pairs in the sliver case; four met both budgets.
- Rasterize each projected triangle as horizontal column spans in each row strip,
  including vertices and edge/strip intersections. Join sorted ray cell IDs directly
  against span endpoints; do not expand a triangle's entire rectangular cell area.
- Grow spans by the legacy bbox padding plus a condition-dependent floating-point
  margin: `256 * eps * (dot00*dot11 + dot01**2) / abs(den)` times the window extent.
  Above `1e-3`, or at a singular denominator, fall back to the whole legacy bbox-cell
  envelope. This deliberately retains numeric sliver hits rather than substituting
  an ideal geometric inside test for the legacy barycentric calculation.
- Also filter every pair by its original 64x64 cell envelope: a finer grid may not
  introduce candidates the old algorithm could not see.
- Barycentric and interpolated-depth arithmetic is copied unchanged, not reassociated.
  Rounded depth, normal dot, then original triangle index determine each ray winner.
  Triangle index makes the legacy stable-sort tie rule explicit across batches.
- The 49 directions, global grid, centroid rays, `_ORI_BARY`, `_ORI_DEPTH`, ground-cap
  exemption and winding logic are untouched. `near_parallel_overlaps` and #110 are untouched.

## Reproduction

```bash
uv run python tests/qa/bench_orientation.py --output tmp/orientation-benchmark.jsonl
```

The benchmark constructs exactly the appendix A `box(n)` and `bipyramid(faces)` inputs
from `mesh-audit-scaling-real-sizes.md`. It times the complete `check_orientation`,
including winding, in seconds with `perf_counter`. Before substitutes only the frozen
legacy `_first_back_hits`; after uses production. Each is one measured call, not an
extrapolation or best-of selection. Memory is a separate run (tracemalloc affects time).

Final tracked-CLI run after the full offline suite (no concurrent benchmark/suite).
The earlier development run also met both budgets (6.1543 s box / 4.0270 s slivers).

| Shape | Triangles | Before (s) | After (s) |
|---|---:|---:|---:|
| box(9) | 972 | 0.1362 | 0.1258 |
| box(20) | 4,800 | 0.5401 | 0.5587 |
| box(41) | 20,172 | 5.4353 | 2.5465 |
| box(65) | 50,700 | 24.9017 | **5.8218** |
| bipyramid(1000) | 1,000 | 2.7151 | 0.4818 |
| bipyramid(5000) | 5,000 | 51.7370 | **3.2855** |

All returned orientation value 0, before and after. Peak traced allocation for the
50,700-triangle box: **41,665,795 bytes (39.74 MiB)** (full checker, not just the join).

## Working-set bound

Persistent projection/ray/winner arrays are O(F + R). Each row batch contains at most
65,536 registrations (a single triangle has at most 1,024 rows); no global list of
F * bins^2 registrations is created. Cumulative pair offsets use O(row batch) memory.
Expansion, barycentrics and sorting operate on at most 131,072 pairs per batch,
including a single crowded bin whose Cartesian product exceeds that cap. Winners
are reduced into O(R) arrays; hit lists are not accumulated between batches.

`test_pair_working_set_is_bounded` forces 127-pair batches and a 1,024-row budget on
75,000 pairs in one occupied ray cell. Every narrow-phase invocation checks its
length; a later front face must replace earlier back hits across batch boundaries,
with arrays exactly equal to the frozen oracle.

## Regression and probes

RED: tests-first commit `b4b3011`, before the production fix, command:

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q tests/qa/test_orientation_scaling.py -k slivers -p no:cacheprovider --basetemp=C:/x/t_2c1b6332/red
```

Result: **1 failed, 1 deselected**; 5,000 slivers took **52.8147 s**, exceeding 5 s.
The frozen `_first_back_hits` and `_orientation_hits` in `tests/qa/orientation_reference.py`
are copied from the base, not reconstructed from the new implementation.

Probe command: `uv run pytest -q tests/qa/test_orientation_scaling.py` (use the same
MSYS environment and a private `--basetemp` as above).

- Exact arrays / result dictionaries -> fixed seeds 0..7, six meshes per seed
  (boxes, bipyramids, rotated/stretched inverted parts, open shells, nested meshes) -> 8/8.
- Existing fixture equivalence -> clean/inverted/tiny/decor/nested/open/mirrored/flipped
  boxes, ground/elevated/sloped caps, D093 pilaster, B01/B02/B02t -> 15/15.
- Candidate filter preserves ordered winner/back arrays -> seeds 203..218,
  arbitrary projections, width 1e-12..1e-1 slivers, vertices, centroids, +/-1e-10
  edge rays and exact depth/dot ties -> 16/16.
- Scale/translation -> seed 203, scales 1e-6/1/1e6, offsets 0/1e9/-1e12 -> 3/3.
- Bounded pairs and stable cross-batch ranking -> crowded-cell probe above -> 1/1.
- Empty triangle/ray inputs -> (0,0), (0,4), (4,0) -> 3/3.
- Whole-check timing budgets -> 50,700 box <10 s, 5,000 slivers <5 s -> 2/2.

Full offline suite on implementation `13dae8b` plus the one-line baseline documentation
repair `357abda` (and the benchmark CLI): **3,797 passed, 13 skipped, 26 deselected,
0 failed**, 333.94 s. The original orientation/D093/#93/#109 tests were not changed.

```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL TMPDIR="$HERMES_KANBAN_WORKSPACE/tmp/process-temp" TMP="$HERMES_KANBAN_WORKSPACE/tmp/process-temp" TEMP="$HERMES_KANBAN_WORKSPACE/tmp/process-temp" uv run pytest -q -m "not blender and not dcc" -p no:cacheprovider --basetemp=C:/x/t_2c1b6332/offline-final
```

Create the basetemp parent before running: pytest does not create missing parents.
The first attempt exposed that environment issue; after repair the only failure was
an existing source-citation/dated-decision false positive in
`docs/experiments/flora-library-audit.md:15` (also tracked by #243 / PR #244).
A one-line provenance clarification, allowed as a minimal baseline repair, made
`tests/test_decisions.py` pass 4/4; no test, decision, model or data changed.
`dt profiles check`: 3 profiles OK. `dt schemas --check`: 11 schemas OK.
Regression evals: `tmp/evals/report.json`, 0 passed / 0 failed / 10 not measured
(exit 2; no Claude transcript / PR-view evidence on this Hermes branch).
