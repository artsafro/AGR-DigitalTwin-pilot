# Atomic seam join and simplification (#530)

`dt_ai.ops.seams` provides pure-numpy topology operations on `invariants.Mesh`
(triangles) and `inv_quads.PolyMesh` (polygons), in local metres. No Blender,
job/model mutation, filesystem publication or production-scene access is involved.

```python
from dt_ai.ops.seams import join_parts, simplify_part

joined = join_parts({'top': top_mesh, 'glass': glass_mesh})
cleaned = simplify_part({'top': top_mesh, 'glass': glass_mesh}, 'glass')
```

## Contract

- Boundary contacts of near-parallel incident faces (`abs(cos) >= 0.9999`)
  within 5 mm are projected onto the receiving boundary. Larger faces anchor
  welds, with source part name / face index breaking equal-area ties. Endpoint
  contacts form equivalence groups with one original authoritative endpoint;
  reciprocal projections cannot exchange positions. Every receiving edge is
  split at existing seam vertices.
  Coincident corners, including bow-ties, become one indexed vertex.
- Noncoincident interior overlaps are not guessed into a Boolean union. Supply
  an explicit rigid part displacement of at least 6 mm, for example
  `join_parts(parts, displacements={'rail': (0, 0, 0.006)})`. A tangent or
  insufficient final separation still refuses. No automatic 3 mm nudge exists.
- Dissolve merges connected near-coplanar, consistently wound disk patches of
  the selected part. Holes and branching boundaries are retained, not filled.
  Straight boundary removal is bounded against every original point replaced
  by a chord, not the preceding simplified chord. Default `line_m = 0.002`;
  larger/nonfinite/negative limits are rejected.
- Simplification and conformance are one transaction. A neighbour's surviving
  vertex is inserted into the simplified boundary; it never remains a T-vertex.
  All parts, not just one named neighbour, take part.
- The entire joined mesh must have zero `inv_xview.face_pairs`, including
  contact and area-only pairs. Unsupported/unresolved geometry raises
  `OperationRefused`; malformed/empty/unknown/duplicated input raises an error.
  There is no successful partial result. Inputs remain unchanged.
- Each output face and vertex carries its original `(part, index)` lineage.
  Dissolved faces retain all source labels. Unused vertices have explicit drop
  records. `max_weld_m` includes coincident consolidation as well as projection,
  separately from requested rigid displacements, and cannot exceed 5 mm.

The result is an **intermediate source-labelled polygon mesh**, not a delivery
certificate. Edge insertion can produce n-gons; existing quad-dominance,
visibility, UV/material and exported-file checks still apply downstream. It does
not synthesize material/UV defaults or artificial bridging faces. Partition
attribute-incompatible source patches before dissolving; use lineage for the
caller's explicit attribute policy. This does not change TOW02 production files.

## Retained real-source replay

Original read-only evidence root:
`C:/Users/artsafro/.AGR-DigitalTwin_pilot/jobs/vyatskaya-tow02/outputs/review-v002/rootcause/louvre_top/`.
Only local copies under this card's ignored `tmp/tow02/` were operated on.

| Fixture | Before contact pairs | Operation | After contact/area pairs | Faces before -> after |
|---|---:|---|---:|---:|
| `top_build-v016.npz` | 0 | join control | 0 | 3305 -> 3305 |
| `top_build-v016.npz` | 0 | simplify glass + atomic join | 0 | 3305 -> 2882 |
| `top_build-v017.npz` | 141 | conforming join | 0 | 2882 -> 2882 |

Fixture SHA256 (original and copy, unchanged after execution):

- v016: `eca2de87fc3c597eee9d20a622f8c8bbe182955920e3b3041b8cec8fcc2575a1`
- v017: `848cf3b3208532d11398df4150df52974d58b05fb1d2e89f5eeb99788a0bb384`

Reproduce with `AGR_TOW02_FIXTURE_ROOT` set to a copied fixture directory:

```bash
AGR_TOW02_FIXTURE_ROOT=tmp/tow02 uv run pytest -q tests/ops/test_seams_tow02.py \
  -p no:cacheprovider --basetemp=C:/x/t_9d33337d-pt
```

This replays recorded Blender arrays through the kernel; it is **not** fresh
native Max or FBX/export parity. The source TOW02 model remains out of scope.

## Regression evidence

- Tests-first commit `7b6cc35`: sagged 30-column seam fails before implementation
  (`ModuleNotFoundError`), then passes. The atomic simplification test also failed
  before its public operation existed (1 failed / 1 passed).
- Hostile report probe: coincident 5 nm consolidation initially reported 0 m
  movement; observed assertion RED, then corrected to account for every source
  vertex. This was an in-scope repair, not a threshold change.
- Initial `tests/ops/test_seams.py`: 56 synthetic controls, including the original
  `unit_cases.py` band/bow-tie and rail/soffit examples, 12 seeded 3D transforms,
  16 column/sag bounds, all-neighbour conformance, conservation, immutable inputs,
  fresh-process imports, explicit separation thresholds and invalid inputs.
- Initial affected run: 295 passed (56 synthetic, 2 real-fixture, 237 existing
  xView tests). Original `unit_cases.py` also executed unchanged: all 11 diagnostic
  rows reproduced the review's counts. Full-suite evidence belongs in the PR.
- Review P1: tests-first `a667b8e` reproduces reciprocal endpoint exchange:
  12 failed / 4 controls passed at offsets {2,3,5} mm, widths {1,2} m, both
  part orders. Grouping endpoint contacts and selecting one original endpoint
  fixes all 16, preserving <=5 mm motion, source lineage and input immutability.
  A blanket strongest-incident-face protection attempt was rejected because the
  existing unilateral shifted bow-tie regressed (1 failed / 73 passed).
- Rework affected run: **324 passed in 34.44 s** (same five seam/xView test files).
  This includes 12 generated transformed/order-independent reciprocal controls
  and one combined reciprocal + sagged/all-neighbour/simplification regression.
  Retained real fixtures still assert v017 141 -> 0 and v016 simplification
  0 -> 0 / 3305 -> 2882 faces, and unchanged input bytes. Full suite was run on
  initial head only; per coordination rule 49 it is not repeated for this rework.
- Environment self-repair: `$PWD` produced `/c/...` for native Windows fixture
  paths (2 FileNotFoundError cases); using relative `tmp/tow02` fixed both.
