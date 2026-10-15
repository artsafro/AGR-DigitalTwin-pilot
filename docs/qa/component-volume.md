# Component-local signed volume

`component_signed_volumes` is an optional, report-only diagnostic. It does not
change `check_orientation`, `checks.run`, hidden-mesh handling or pass/fail semantics.
It never repairs geometry or sets delivery status. Synthetic evidence remains
`delivery_passed=false`; this helper is not delivery certification.

## API

```python
from twinqa.geometry.component_volume import component_signed_volumes

# meshes: raw mesh-dump dictionaries, not a welded Soup.
rows = component_signed_volumes(meshes)
```

Each mesh has `name` (string), `vertices` (finite real N×3 coordinates) and
`triangles` (integer M×3 vertex indices). Lists and NumPy arrays are supported;
empty lists are accepted. Array shapes must be exact even when empty. Boolean,
complex and floating-point indices, negative/out-of-range indices, non-finite
coordinates and malformed mesh dictionaries raise `ValueError` rather than
being silently cast or wrapped. No triangles means no component rows.

Rows contain:

| Field | Meaning |
|---|---|
| `mesh` | Original mesh name |
| `triangle_ids` | Sorted original local triangle IDs; never welded/reindexed |
| `n_triangles` | Number of triangles in this component |
| `eligible` | All combinatorial/area prerequisites met |
| `reasons` | Empty when eligible; otherwise reason codes below |
| `status` | `measured` or `not_measured` |
| `signed_volume` | Signed cubic input units; `None` when ineligible |
| `sign` | +1, -1; `None` for zero volume or ineligible component |

Meshes stay separate. Within each mesh, triangles connect only through shared
undirected **index edges**, never coincident coordinates or a vertex alone.
Rows follow mesh order, then minimum triangle ID. Inputs are not modified.

## Eligibility and precision

- `open_or_nonmanifold_edge`: an edge does not have exactly two uses by distinct triangles.
- `inconsistent_winding`: a two-use manifold edge is not traversed in opposite directions.
  A boundary/nonmanifold edge alone does not also produce this reason.
- `degenerate_triangle`: repeated indices or triangle area ≤ 1e-12 × component bbox diagonal².
- `vertex_not_single_fan`: incident triangles at a vertex are disconnected
  **within the component**.

For eligible components, float64 coordinates are recentered on the mean of their
unique vertices, then `math.fsum(dot(a-r, cross(b-r, c-r))) / 6` is evaluated.
This avoids large-offset cancellation in the tested coordinate range. It does
not guarantee numerical stability for every possible magnitude/shape.

Negative volume is an orientation fact, **not automatically a defect**: a nested
cavity shell may legitimately be negative. Eligibility does not prove absence of
self-intersection. Open facades, arbitrary imported shells and cavity semantics
need independent domain interpretation. A positive scene sum cannot certify
individual components. No outwardness gate or generalized certification is added.

## Synthetic evidence

[Hypothesis #93](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/97) tested
100 m outer / 0.2 m inner boxes, two packings, three rigid transforms (including
7.5e6 m translation), and outward/inverted/open/inconsistent variants (24 cases).
The prior experiment measured max relative volume error 3.958e-9, 24/24 exact
component memberships and 12/12 control abstentions. The baseline missed 6/6
occluded inverted solids; the diagnostic made zero closed-component sign mistakes.
These are synthetic observations, not arbitrary imported-model guarantees or a
speed claim. Production regression tests reproduce the matrix with ≤1e-6 relative
error, three identical repeats, unchanged baseline results and the corrected
boundary-edge reason. See `tests/qa/test_component_volume.py`.

## Scope and bounds

- **new-case scope**: The helper is strictly an optional report-only diagnostic. It introduces
  no delivery certification, outwardness gate, or registered building-node pattern.
- **Negative cavity semantics**: Negative signed volume reflects mathematical orientation and
  winding order, not an automatic geometric defect. Nested cavity shells may legitimately possess
  negative volume.
- **No arbitrary self-intersection or numerical magnitude guarantee**: The helper checks configured
  component-local edge, winding, degeneracy and vertex-fan prerequisites; eligibility is not
  generalized geometric certification. It does not detect arbitrary self-intersections among faces,
  nor does it guarantee numerical stability or magnitude bounds across arbitrary coordinate scales
  beyond the tested range.

## Author evidence boundary

Reviewer 800 checks are not author-session telemetry. Author-owned verification strictly
distinguishes prior hypothesis 24-case observations and reviewer prior runs from this
follow-up driver run.

The reproducible author-owned synthetic probe is `tests/qa/test_component_volume_evidence.py`:
- 4 parametrized families × seeds `range(100)`:
  - `random.Random(seed)`
  - side lengths uniform `[0.2, 20.0]`
  - $\theta_z$ uniform in `[-math.pi, math.pi]`
  - translations $t_x, t_y, t_z$ each uniform in `[-1e6, 1e6]`
  - shuffled triangles
  - fourth family additionally shuffles combined triangles using `seed + 9999`
- Invariant matrix (400 passed total, 100/100 each):
  - Analytic signed volume positive outward, negative inverted
    (`test_synthetic_signed_volume_analytic`): 100/100 passed
  - Coincident and separate mesh index isolation
    (`test_synthetic_coincident_and_separate`): 100/100 passed
  - Open and inconsistent winding abstentions
    (`test_synthetic_abstain_defects`): 100/100 passed
  - Determinism and input immutability
    (`test_synthetic_determinism_and_immutability`): 100/100 passed

Driver execution command:
```bash
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t_fe1430a0 tests/qa/test_component_volume_evidence.py -k synthetic --junitxml=tmp/issue-111/probe.xml
```
Durable summary receipt generated by driver from actual XML:
[`docs/qa/evidence/issue-111/verification.json`](evidence/issue-111/verification.json).

Driver run state:
- RED baseline run on base `2e61c73eca03c9def317a7b36eb5a31e5186004b` with new tests:
  metadata / assertion regression RED 1 failed (`test_diagnostic_documentation_regression`
  for missing docstring requirement), 400 passed. All 400 numeric probes already passed before
  the fix; no numeric defect claimed. Tests-first commit `fab1fdd74a07b30f2caccf88135938f2338ab0a0`.
- Actual author driver results (tests-first commit `fab1fdd` plus module docstring and documentation
  edits; no numeric implementation changes):
  - Targeted existing plus new evidence tests: 449 passed (`test_component_volume_evidence.py`
    and `test_component_volume.py`).
  - Generated subset: 400 passed, 1 deselected (`-k synthetic`).
  - Full suite: 3109 passed, 9 skipped, 13 deselected, 48 warnings in 543.08 s.
- Eval command already executed on tests-first commit:
  ```bash
  uv run dt evals --suite regression --main . --output docs/qa/evidence/issue-111/regression
  ```
  Actual report `docs/qa/evidence/issue-111/regression/report.json`:
  `0 passed, 0 failed, 10 not measured, exit 2`.
  Breakdown: 7 missing Claude-format branch transcript (Hermes driver / Antigravity author format
  not supported), 3 missing PR snapshots before PR creation.
- Explicitly, this is a pre-PR evidence run, not a pass nor final merge certification.
