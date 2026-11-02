# Attached decor (`attached-decor`)

Status: draft; source: [review §7 A–C](../../../jobs/vyatskaya-tow02/REVIEW-514.md#7-root-causes-in-the-builder-outputsreview-v002rootcauserailingsmd-louvre_topmd), issue #531.
Project construction rule, not a new regulatory tolerance; [D152](../../decisions.md) still requires xView-clean delivery.

## Signs and construction

- An attached railing, basket infill or louvre has an identified host face/footprint and a measured source relation.
- Derive the coping inner edge from its measured footprint; place railing glass from that edge by the source relation.
  Do not derive coping and glass independently from a simplified wall path and two nominally equal setbacks.
  The measured relation was 107–129 mm; 130 mm is a regression control, not a universal railing offset.
- Basket glass: derive the front from the basket front, 25 mm behind it; shell 8 mm inward.
  This preserves the user's front = former inner-face relation and visible slats; do not simplify two envelopes independently.
- Never reuse another part's face level for a parallel face. Derive the attached level from its host plus the measured offset.
- Embed only through perpendicular faces; embedding through a parallel floor/coping face is not an overlap exemption.
- Every vertex projecting into another part's near-parallel face, boundary included, must be >=10 mm from it, or welded.
  Use both directions and both normal orientations; a good centroid does not certify tilted endpoints.
  For floating-point safety the construction API rejects exactly 10 mm too; build beyond the boundary.
- Weld means shared topology in an assembled mesh, not coincident independent vertices; join/weld is a separate operation.

## Kernel use and profiles

- Both `npm_min` / `mid`: same host relation and clearance; profile representation/baking remains in `facade-decor-inset`.
- `dt_ai.ops.attached_decor.clearance_pairs(scene)` checks named `PolyMesh` parts in local metres with `inv_xview` at 10 mm.
- `move_rigid(scene, seeds, vector, fixed=[host_ids])`: explicitly declare stationary hosts/obstacles and a source-approved vector.
  Grow the transitive parallel-neighbour closure within 10 mm among movable parts; translate every vertex by the same vector.
  Fixed hosts stop propagation, not checking. Never repair just one end while leaving its coping/stub behind.
- Recheck the entire candidate at xView 5 mm, including unchanged obstacles and internal faces; any contact/area overlap raises.
  No input mutation or partial result on failure. Returned `clearance` still lists 10 mm construction violations: zero xView
  contacts alone is not construction acceptance. A rigid move cannot remove an existing contact inside the moved cluster.
- Reject internal cluster contacts before translation as well as checking the full candidate afterwards; rounding must not
  make a retained defect appear repaired. Require source and candidate binary64 coordinate spacing <=1e-12 m per axis.
  This numerical support bound is not a modelling/contact tolerance: unsupported large-coordinate translations raise
  even if all faces remain nondegenerate (e.g. dz=2**45 rounds a 4/5 mm gap to 7.8125 mm). Use local metres.

## Evidence and traps

- Tests: `tests/ops/test_attached_decor.py`; portable real face extracts: `tests/fixtures/attached_decor/` (source hashes/indices).
- Louvre 0/3/5 mm = xView contact, 6/32 mm = none; 6 mm still fails the stronger construction rule. User repair: +32 mm.
- Sources: [validation xView rule](../validation.md), [geometry joint rules](../geometry.md#project-modeling-rules-user-decisions-not-regulation),
  review §7 and its retained `rootcause/RAILINGS.md` A/B, `rootcause/LOUVRE_TOP.md` C and `louvre_top/unit_cases.py`.
- Do not treat sampled area, a 2 mm vertex weld, or a sub-tolerance nudge as proof that parallel faces are clear.
- This API validates geometry, not source fidelity, materials, export readback or human acceptance; it does not rebuild a model.
