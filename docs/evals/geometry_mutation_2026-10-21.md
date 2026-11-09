# Synthetic geometry mutation recall

Seed: 461. Synthetic data only.
Caught 7 of 8 planted defects; clean-base false positives: 0.
Corpus SHA256: `ccf5f56dbce411b1757f4002ae9adf6c3affdaf68e1e3300013847c5306e4fae`.

| Defect | Expected checker / adapter | Verdict | Caught |
|---|---|---|---|
| duplicate_faces | topology | fail | yes |
| duplicate_faces | clearance_target | fail | yes |
| duplicate_faces | mesh_target | fail | yes |
| false_contact | clearance | fail | yes |
| flipped_normals | orientation | fail | yes |
| flipped_normals | horizontal_faces | fail | yes |
| low_density | uv_density_adapter | fail | yes |
| moved_opening | opening_planes | fail | yes |
| polycount | triangle_budget | fail | yes |
| polycount | complexity | fail | yes |
| sliver_triangle | topology | pass | MISSED |
| sliver_triangle | mesh_target | pass | MISSED |
| wall_slab_gap | mesh_joint | fail | yes |

| Checker / adapter | Caught | Applicable defects |
|---|---|---|
| clearance | 1 | 1 |
| clearance_target | 1 | 1 |
| complexity | 1 | 1 |
| horizontal_faces | 1 | 1 |
| mesh_joint | 1 | 1 |
| mesh_target | 1 | 2 |
| opening_planes | 1 | 1 |
| orientation | 1 | 1 |
| topology | 1 | 2 |
| triangle_budget | 1 | 1 |
| uv_density_adapter | 1 | 1 |

| Function | Caught | Applicable defects |
|---|---|---|
| twinqa.clearance.near_parallel_overlaps | 2 | 2 |
| twinqa.geometry.checks.check_budget | 1 | 1 |
| twinqa.geometry.checks.check_horizontal_faces | 1 | 1 |
| twinqa.geometry.checks.check_mesh | 2 | 3 |
| twinqa.geometry.checks.check_opening_planes | 1 | 1 |
| twinqa.geometry.checks.check_orientation | 1 | 1 |
| twinqa.geometry.complexity.check_complexity | 1 | 1 |
| twinqa.geometry.topology.count_defects | 1 | 2 |
| twinqa.uv.edge_densities | 1 | 1 |

## Measurement boundary and reproduction

- Baseline: pilot main `7b88d09` (includes merged #451 and #456). Seed 461.
- Run `uv run python tools/evals_geometry_mutation.py --json` for all observed
  checker values, limits, details, input hashes and explicit per-adapter scope/exclusions.
  Omit `--json` for these generated tables; `--seed` changes actual cube coordinates.
- Runtime for this measurement: runtime_seconds=0.566819. Runtime is stderr-only so repeated JSON is byte-stable.
- VALID means finite nonempty indexed triangles loaded by `twinqa.geometry.mesh.from_dump`,
  not "defect-free". No real source data, FBX/DCC export or official AGR acceptance.
- There are eight components: a source-spec window plane, normal/topology cube,
  supporting slab and bottom-open wall, two intentionally separated contact panels,
  a material-21 UV panel and a budget panel. A mutation alters just one component
  (UVs only for density). Not every component is suitable for every checker:
  seating uses `check_mesh(..., build="from_source")` on wall/slab; opening matching
  uses the synthetic B01 fixture's L0 opening; orientation/topology use the closed cube;
  clearance uses the named panels or cube; budget/complexity use the whole scene.
  The JSON records every component as in-scope or explicitly excluded per adapter.
- Adapters do not consume defect labels. Only a measured `fail` is caught;
  `not_measured` is a miss, unknown statuses/errors abort, a non-passing base aborts.
  Exit 0 means a completed experiment, **not** 100% recall or delivery acceptance.
- `uv_density_adapter` calls the existing `uv.edge_densities` helper then compares
  against the issue's explicit 512 px/m diagnostic threshold (base 1024, mutant 256).
  It is **not** a newly implemented V009 checker or a resolution of C10/C36.
  Without this explicitly named eval adapter, native verdict-checker coverage is
  6/8 defects, plus one measured metric-helper detection. No general UV claim is made.
- Topology uses its existing 2 mm clustering and V004 policy: <=100 combined
  duplicates/self-intersections; zero isolated vertices/edges/polygons or zero edges.
  Clearance uses its existing 5 mm lower-band gate. Complexity uses an explicit
  synthetic group budget and the existing npm_min 150000 total triangle cap.
  The polycount mutant has a conforming 275x275 grid, not duplicated triangles.
- Two applicable checker-defect pairs miss the same sliver (strictly positive area,
  almost collinear split inside an existing cube face). It keeps every edge well
  above the zero-edge threshold: a long thin triangle is not a zero-length edge.
  This is a measured gap, not permission to change tolerances/checkers in this PR.
- Fingerprints bind corpus and checker/configuration files; before/after snapshots
  reject persistent input edits during a run, not edits restored between snapshots.
  Loaded-code tampering, cross-process adversarial execution and formal recall on
  real scenes are not claimed. This is a fixed eight-sample diagnostic, not an
  unbiased population recall estimate. Clean-base 0 false positives covers only
  the recorded adapter scopes, not every possible twinqa check on every component.

## Proposed follow-ups (not implemented)

- sliver_triangle / topology gap -> Detect positive-area high-aspect sliver triangles independently of zero-edge and duplicate ceilings.
- sliver_triangle / mesh_target gap -> Add a scoped geometric sliver/triangle-quality signal to check_mesh.
- native UV verdict gap -> Wire measured per-material edge density into V009 with explicit applicability and policy.
