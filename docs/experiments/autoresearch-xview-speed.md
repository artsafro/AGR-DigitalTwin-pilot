# Autoresearch: xView-exact overlap check speed (#553)

Goal: the fastest exact core for the 3ds Max xView Overlapping Faces (5 mm) / Overlapping Vertices (2 mm) selection,
for #535 (parity guard, incremental mode, Blender path) to adopt. Method: skill `autoresearch`, classic mode,
`Iterations: 25` cap, time box 3 h; run by Hermes dt-worker (claude-opus-5-5), card t_fb698124, 2026-10-22.

- Pilot main at start: `996b34a6d84c06a1bdef7fe4caa9288d556bb48c`; the branch base is `e74e77d` (`inv_xview.py`,
  `inv_quads.py` and `tools/qa/` identical between the two, so the baseline is the same).
- Candidate: `src/dt_ai/ops/inv_xview_fast.py` (new; `src/dt_ai/ops/inv_xview.py` untouched, it is the baseline).
- Frozen bench: `tools/qa/xview_bench.py`, SHA-256 `883d08e5d30b03ab4455e50ab07a1ded5646c6f9b53302ed4a2d7acba6a399cb`
  (committed in `9a75d32` before the first experiment, unchanged during the loop). After the loop, the hostile
  self-review found that `--out` could overwrite an oracle file; `23ff90b` adds an `--out` alias guard and an
  input-changed check (exit 2). The fixtures, timing and comparison code did not change. New SHA-256
  `48442a0073040d38de9506e8d1bf510081212cab087eb6e1e142f6afa76999a4`; baseline and winner were re-run with it (table
  below, quiet board).
- Metric: `cpu_s` = median of 5 `time.process_time()` runs of the candidate on TOW02 export-v005, single process.
- Evidence (small text, committed): `docs/experiments/autoresearch-xview-speed/` (`results.tsv`, `bench_baseline.json`,
  `bench_final.json`, `bench_baseline2.json`, `bench_final2.json`, `pairs_parity.json`, `ab.py`). Logs: `C:/x/ev_t_fb698124/` on this PC.

## Result

| | TOW02 export-v005 `cpu_s` | wall | TOW02 user `_05` | Ground v014 NPM | Ground v014 NPM poly | parity |
|---|---|---|---|---|---|---|
| baseline `inv_xview.part_report`, loaded board (bench `883d08e5`) | **40.0 s** | 40.4 s | 51.1 s | 20.0 s | 17.7 s | 11/11 |
| winner `inv_xview_fast` (`d3a0cee`), loaded board (bench `883d08e5`) | **0.438 s** | 0.455 s | 0.594 s | 0.266 s | 0.391 s | 11/11 |
| baseline, quiet board (bench `48442a00`) | **21.6 s** | 21.7 s | 20.2 s | 10.2 s | 10.0 s | 11/11 |
| winner (`23ff90b`), quiet board (bench `48442a00`) | **0.219 s** | 0.220 s | 0.359 s | 0.219 s | 0.203 s | 11/11 |

91x faster on the primary metric under load and 99x on a quiet board (target <= 2 s met, #535's <= 10 s met),
28x-86x on the other fixtures, with exact list parity on every fixture. Board load: CPU 40 % (loaded baseline,
other workers' suites running), 24-36 % (loaded winner), 1-2 % (quiet pair, run back to back after the full
suite); 32 logical CPUs. Under load `process_time` ran ~2x higher and moved +-25 % run to run (see "Noise"). Same PC,
same venv (numpy 2.x, shapely; scipy is NOT installed, so no cKDTree).

Parity per fixture (oracle = stored xView lists, never a candidate output):

| fixture | oracle faces / vertices | baseline | winner |
|---|---|---|---|
| tow02_v005 (`xview/ours_v005.keep`, 35 407 polys) | 185 / 0 | 185 / 0 equal | 185 / 0 equal |
| tow02_user05 (`xview/user_fbx05.keep`, node 013, 73 594 tris, in-place coordinates) | 0 / 10 | equal | equal |
| ground_v014_npm (headless-Max dump `npm_xview.json`) | 146 / 0 | equal | equal |
| ground_v014_npm_poly (`npm_poly_xview.json`, n-gons) | 351 / 118 | equal | equal |
| syn_boundary_contact (vertex exactly on the other face's edge) | 2 / 0 | equal | equal |
| syn_normal_0.810deg / 0.815deg | 2 / 0, 0 / 0 | equal | equal |
| syn_face_5.000mm / 5.100mm | 2 / 0, 0 / 0 | equal | equal |
| syn_vertex_2.000mm / 2.100mm (kernel fail-closed `<=`) | 0 / 2, 0 / 0 | equal | equal |

Beyond the bench (stronger than the face/vertex lists): `pairs_parity.json` - the winner's contact polygon pairs and
vertex pairs equal the baseline's pair for pair on all 11 fixtures (TOW02 164 pairs, Ground 155 and 361).

## Experiments

Decision rule: keep only with the guard passing and >= 5 % lower `cpu_s`. Because the board load made single bench
runs noisy (+-25 %), decisions after E1 used an in-process A/B (`ab.py`: HEAD vs working tree, alternated, 9-15
rounds, lists asserted equal every run) and, for the borderline ones, 3 alternating frozen-bench runs (median of
the medians).

| # | idea | `cpu_s` (bench) | parity | status |
|---|---|---|---|---|
| 0 | baseline `inv_xview.part_report` (triangle-pair sweep + shapely area rule) | 40.0 | 11/11 | baseline |
| 1 | search order per (triangle, vertex): vertex grid gives the vertices in each triangle box padded `face_m / cos_min`; own-polygon test, plane-distance prefilter, barycentric with the baseline's expressions; only hits look up the vertex's triangles (live, other polygon, near-parallel); convex quads fanned vectorised, anything unclear by the baseline's `_polygon_triangles` | 1.016 | 11/11 | kept (-97 %) |
| 2 | grid cell 0.25 x median box | 0.625 / 0.969 | 11/11 | discarded: A/B +11.5 % TOW02, +21 % user05 |
| 3 | one query box per polygon (union of its live triangles), own-vertex test before expanding to triangles | 0.688 / 0.625 | 11/11 | kept: A/B -38 % TOW02 (+5.7 % user05, all-triangle mesh) |
| 4 | sorted keys instead of `np.unique` hashing (membership, polygon groups) | 0.438 / 0.453 | 11/11 | kept: A/B -16 % / -20 % |
| 5 | grid cell 0.5 x median polygon box (2.0: +62 %, 0.35: -23 % / 0 %) | 0.359 vs HEAD 0.438 | 11/11 | kept: bench A/B -18 % |
| 6 | dense cell -> (first, count) table instead of 2 x `searchsorted` | - | asserted | discarded: A/B 0 % / -2 % |
| 7 | int32 indices in candidate generation | 0.422 vs HEAD 0.406 | 11/11 | discarded: bench A/B +4 % (A/B -11 % did not hold) |

The loop stopped at 7 of 25 iterations: the target was met 4.5x over at E1/E3, the last two ideas were inside the
noise floor, and the remaining profile (~0.25 s candidate generation, ~0.1 s triangulation and input checks,
~0.03 s vertex pairs) has no single dominant term left. Not tried (no gain expected at this level or out of the
allowed toolset): normal bucketing on the 0.81 deg cone, scipy cKDTree (not installed), per-part caching (that is
#535's incremental mode).

## Why it is exact

- Same rule, same thresholds (D152: 0.002 m / 0.005 m / |cos| >= 0.9999), same triangulation (convex quads fanned
  from the first vertex like the baseline; every polygon whose convexity is not clear by a 1e-9 relative margin,
  every n-gon and every near-degenerate quad goes through the baseline's own `_polygon_triangles`), same float
  expressions for the normal, plane distance and barycentric test (`_dot` imported from the baseline).
- The broad phase is a pure superset: a vertex that projects into a triangle within `face_m` lies inside the
  triangle's box padded by `face_m / cos_min + 1e-9` (the baseline's own pad), so no pair the baseline tests can be
  missed; every later filter is one of the rule's own conditions.
- Guards: the bench (11 fixtures), pair-for-pair parity on the real fixtures, 300 generated near-parallel scenes and
  200 random float T-vertices compared pair for pair with the baseline (`tests/ops/test_inv_xview_fast.py`), and
  mutation checks: `<=` -> `<` on `face_m`, dropping any of the three barycentric 1e-12 slacks, a looser cos limit,
  skipping the own-polygon test and a shrunken pad are each caught by the tests.

## Noise

`time.process_time()` on Windows under 24-40 % board load: the same code measured 0.73-1.02 s (E1) and
0.27-0.59 s (winner) in different runs. Single runs are not decisions; the A/B harness alternates both versions in
one process so both see the same load.

## Tokens

Not measured: the Hermes dt-worker lane writes no usage log for this run (see the Agent trace in the PR). About 80
tool calls, one session, ~2 h 20 min including the full suite (21 min) and the re-runs.

## Verdict on the method

Worked and was cheap: the frozen bench with the stored xView lists as the oracle made every change safe to try,
and the first experiment (changing the search order, not tuning the old one) delivered almost all of the gain
(40 s -> 1 s); the loop then took it to ~0.4 s in three kept steps. Two lessons: (1) under board load a single
`process_time` median is not a decision - alternate A/B in one process; (2) the oracle lists alone are coarse
(a set of face ids), so the loop also needs a pair-level comparison against the baseline and generated boundary
cases; the generated T-vertex probe was what caught a barycentric-slack mutation the fixtures missed.

Handoff to #535 / an Adopt card: `xview_lists(vertices, faces, tol)` returns `xview_faces`, `vertices`,
`vertex_pairs` and `face_pairs` (contact rule only; the kernel's extra `area` rule stays in `inv_xview`).
Adopting it into `part_report` means running the area rule only on the near-parallel pairs, or keeping the area
rule as a separate slower pass.
