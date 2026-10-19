# Hypothesis #93: component-local signed volume detects occluded inverted solids

Verdict: **CONFIRMED** (synthetic fixtures only). `delivery_passed=false`.
Issue: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/93

All inputs are **synthetic** boxes derived from the tracked fixture topology. They are not data of a real object.

## Claim

On explicitly labelled synthetic closed box solids, a component-local signed-volume diagnostic identifies a fully
inverted, occluded small component that the current outside-ray/winding checker (`check_orientation`) and one
scene-wide signed-volume sum cannot distinguish from the all-outward control. The diagnostic is invariant under
positive-determinant rigid transforms and mesh packing, and abstains on open or inconsistently wound components.

## Setup

- Base: `main` @ `3cf7c9358591a12813ec5bcbcb8e082ddf5fe342`, branch `experiment/hyp-93`.
- Python 3.14.7 (repo venv), NumPy 2.5.3. No DCC, no data/, no production code changed.
- Command: `uv run python experiments/hyp-93/driver.py` (3 repeats inside one run; 24 cases per repeat).
- Prototype: `experiments/hyp-93/component_volume.py` (report-only). Driver: `experiments/hyp-93/driver.py`.
  Raw evidence: `experiments/hyp-93/results.json` (every field of every case of repeat 1, per-repeat hashes,
  median runtimes).
- Code written by Cursor CLI (model `grok-4.7-medium`, 1 round); driven, re-run and checked by the Hermes worker.

### Inputs

- `_BOX_TRIS` is read from `tests/qa/test_orientation.py` with `ast.literal_eval` (the test module is not imported);
  unit vertices as in its `_box`.
- Outer: unit cube x 100 -> [0,100]^3, outward. Analytic volume 1e6, label +1.
- Inner (separate synthetic SOLID, not a cavity boundary): unit cube x 0.2 + (49.9,49.9,49.9), analytic 0.008.
  Variants: `inner_outward` (+1), `inner_inverted` (all 12 triangles reversed, -1), `inner_open`
  (`_BOX_TRIS[2:]`, bottom removed), `inner_inconsistent` (only triangle 4 reversed).
- Packings: `two_meshes` (`outer`, `inner`) and `one_mesh` (`scene`, disjoint vertex/index sets; oracle triangle
  membership kept).
- Transforms: `identity`; `translate` (600000, 7500000, 150) m; `rz37_translate` (Rz 37 deg, then that translation).
- Baseline: `checks.check_orientation(from_dump({"meshes": ...}), {"weld_m": 0.001})`, unchanged.
- Candidate: per mesh, triangles split by shared undirected index edges (no position weld); eligibility = every edge
  used exactly twice, opposite directed uses, nondegenerate triangles, one face fan per vertex; signed volume
  `fsum(dot(a-r, cross(b-r, c-r)))/6` with `r` = mean of the component's unique vertices.

### Hashes (sha256)

| File | sha256 |
|---|---|
| tests/qa/test_orientation.py | c84c55f9cadeeb558563e607b4f12dc04f4e7027a76100d524fa1b12dafe82e1 |
| src/twinqa/geometry/checks.py | f89313eba22a0dcff59f4582db03fd06e26dcefa7fb25df17c9604a050419d8b |
| src/twinqa/geometry/mesh.py | 409353aa5ce5e952857c351b65f47274a93ca5d0024b0a3c5521c66021ecf25d |
| experiments/hyp-93/driver.py | 15ba3bd90dc4d622251c38d732ed51635f2530830b2918e56422462e493f4019 |
| experiments/hyp-93/component_volume.py | 22d8a4d77487b2a21fc492f2219cb0279ed727e798040e51aff80a04132f4477 |
| results without runtime, repeats 1/2/3 | 209f96ce09d3d9966452dda2a9fcf966c7d8517880fd88ab6abfe3afbc407a00 (all three identical) |

## Prediction table (frozen from the issue before execution)

| Metric | Inputs | Baseline (current code) | Rejection threshold | Measured (3 repeats, identical) | Verdict |
|---|---|---|---|---|---|
| Baseline blind spot: `check_orientation` on inverted inner | 6 inverted cases (2 packings x 3 transforms) | pass/value=0 | reject if any inverted case fails or value != 0 | 6/6 pass, value 0 | holds |
| Inner unjudged when named separately | 3 inverted `two_meshes` cases | `judged_faces` of `inner` | reject if inner judged_faces > 0 | 3/3 `judged_faces=0`, `inner` in `unjudged_meshes` | holds |
| Scene-wide signed volume hides the inversion | 12 closed cases (both labels) | sign of total volume | reject if any total <= 0 | 12/12 positive (inverted: 999999.992) | holds |
| Candidate component count / membership | 24 cases | n/a | reject unless exactly 2 components with exact oracle membership | 24/24 | holds |
| Candidate sign (outer +1, inner = label) | 12 closed cases | n/a | reject on any sign mistake | 0 sign mistakes (12/12 outer +1; inner +1 x6, -1 x6) | holds |
| Relative volume error per eligible component | 12 closed + 12 control (outer) | n/a | reject if any > 1e-6 | max inner 3.958e-9 (translate), max outer 2.827e-13 | holds |
| Abstention on open/inconsistent inner | 12 control cases | open: pass/0; inconsistent: fail/3 | reject unless inner `not_measured` with reasons and outer +1 | 12/12 `not_measured` (open: `open_or_nonmanifold_edge,inconsistent_winding`; inconsistent: `inconsistent_winding`), outer +1 | holds |
| Repeatability | 3 repeats x 24 cases | n/a | reject if any non-runtime field differs | identical hash x3 | holds |
| Runtime (descriptive only) | median over 24 cases of per-case medians | 0.0582 s | none (not a speed claim) | candidate 0.00128 s | descriptive |

## Raw evidence (repeat 1, condensed)

```
inner_inverted two_meshes identity       base=pass/0 inner_judged=0 scene_sign=+1 n=2 mem=True outer=+1/0.000e+00 inner=measured/-1/4.250e-14
inner_inverted two_meshes translate      base=pass/0 inner_judged=0 scene_sign=+1 n=2 mem=True outer=+1/0.000e+00 inner=measured/-1/3.958e-09
inner_inverted two_meshes rz37_translate base=pass/0 inner_judged=0 scene_sign=+1 n=2 mem=True outer=+1/2.827e-13 inner=measured/-1/2.214e-10
inner_inverted one_mesh   identity       base=pass/0                scene_sign=+1 n=2 mem=True outer=+1/0.000e+00 inner=measured/-1/4.250e-14
inner_inverted one_mesh   translate      base=pass/0                scene_sign=+1 n=2 mem=True outer=+1/0.000e+00 inner=measured/-1/3.958e-09
inner_inverted one_mesh   rz37_translate base=pass/0                scene_sign=+1 n=2 mem=True outer=+1/2.827e-13 inner=measured/-1/2.214e-10
inner_outward  (all 6)                   base=pass/0 scene_sign=+1 n=2 mem=True outer=+1 inner=measured/+1 (same errors as above)
inner_open     (all 6)                   base=pass/0 inner_judged=0 n=2 mem=True outer=+1 inner=not_measured open_or_nonmanifold_edge,inconsistent_winding
inner_inconsistent (all 6)               base=fail/3 inner_judged=0 n=2 mem=True outer=+1 inner=not_measured inconsistent_winding
closed_inner_sign_rel 12/12, closed_membership_exact 12/12, closed_outer_sign_rel 12/12, closed_two_components 12/12,
defect_inner_not_measured 12/12, defect_membership_exact 12/12, defect_outer_sign_rel 12/12, defect_two_components 12/12,
inverted_baseline_pass_value0 6/6, inverted_inner_judged_faces_0 3/3, inverted_scene_volume_positive 6/6,
cases_ok 24/24, repeats_identical True -> VERDICT: CONFIRMED
```

`uv run pytest -q tests/qa/test_orientation.py`: 29 passed (production tests untouched).

## Counterexamples and limits

- None found inside the frozen matrix.
- The open control lists `inconsistent_winding` in addition to `open_or_nonmanifold_edge`: the prototype counts a
  boundary edge (one use) as "not an opposite pair". Harmless for abstention; an adoption should report only the
  primary reason for boundary edges.
- The inconsistent control is not a baseline blind spot: the baseline already fails it (winding, value 3).
- Without recentering, the translated case would lose precision; local recentering keeps the 0.2 m box at
  rel. error 4e-9 at 7.5e6 m offsets. Eligibility does not prove non-self-intersection of arbitrary input.
- Negative volume is an orientation fact, not a model defect: nested cavity shells are legitimately negative.

## Adoption scope (optional, report-only)

- New `src/twinqa/geometry/component_volume.py` (port of the prototype; primary-reason fix above).
- New `tests/qa/test_component_volume.py`: the 24-case matrix above (both packings, three transforms,
  inverted/outward/open/inconsistent), plus a boundary-edge reason test.
- Keep `check_orientation`, `checks.run`, pass/fail semantics and hidden-mesh behaviour UNCHANGED. No outwardness
  gate, no cavity-shell defect policy, no geometry repair, no delivery certification.
