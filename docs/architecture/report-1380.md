# Compaction 5: UV / atlas (#1380)

## Result

Two of the original five rows were VPM periodic UV, not NPM atlas copies. Their byte-identical
runtime recipe (KPP1 / TEC26; only the docstring differed) now lives in `tools/blender/vpm_uv.py`.
KPP1 / TEC26 retain import shims; both PSU275 stage-5 callers select the owner directly instead
of obtaining UV from KPP1's sys.path. Existing delivered scenes, images, FBX and packages are untouched.

Program: Blender, because this VPM recipe uses bmesh edge-ring cuts and metre-period projection;
it is not a new implementation of Max `atlas_core` or permission to bypass #1141.

`vpm-uv` guards `pack_uv` / `texel_cut` definitions in jobs/, tools/, src/. The two old VPM rows and
their two UDIM inverse-formula allowlist rows were removed; `tile_offset` delegates to `udimtile_core.tile_origin`.
The wider rule found the frozen alternative `jobs/KPP1/rerun-1230/build_blender.py::texel_cut`;
it stays historical with an explicit reason (no rebuild of that result).

[D320] records Artem's #1380 comment: the slicer and master QA share `max_quad_side(tile_px)`;
the existing D021 formula with 1024 px/m and 16 px padding per 2048 tile gives 1.96875 m for 2048,
3.9375 m for 4096. Finish periods/padding can impose a smaller cut. Master QA accepts an optional
third script argument `tile_px` after output and FBX; legacy commands default to 4096. Stacked/overlapping
tileable UV remains allowed. The old 3.9 / 4.0 constants are gone from these callers.

## D320 job-local leftovers (#1497)

The shared slicer and `tools/blender/qa_master.py` use `max_quad_side`; the following
constants are explicit historical exceptions, not additional owners of the current policy.
They are retained byte-for-byte. No delivery is rebuilt and no historical QA result is upgraded.

| Script | Retained constant | Status and reason |
|---|---|---|
| `jobs/vyatskaya-tow02/scripts/build_body_blender.py` | `MAX_SIDE_M = 3.8` | historical — closed job: changing the body cut grid would change the pre-hand-finish geometry, not reproduce the user's final model. |
| `jobs/vyatskaya-tow02/scripts/build_decor_blender.py` | `MAX_EDGE_M = 3.8` | historical — closed job: changing decor subdivisions would change the pre-hand-finish topology. |
| `jobs/vyatskaya-tow02/scripts/build_review_fixes_blender.py` | `MAX_SIDE_M = 3.8` | historical — closed job: the review-fix recipe belongs to the old cut grid, before the user's final hand finish. |
| `jobs/PSU275/scripts/qa_master_psu275.py` | `MAX_EDGE = 4.0 + 1e-4` | historical — historical QA copy: preserve the completed delivery-v003 stage's diagnostic recipe, including its PSU275 mass-ray exception; it is not current D320 size acceptance. |

Sources: [TOW02 state](../../jobs/vyatskaya-tow02/STATE.md) records closure on 2026-10-22
[D185] and retention of the user's hand-finished `_05.fbx`; these three builders cannot
recreate that finish. [PSU275 state](../../jobs/PSU275/STATE.md) records the completed
2026-10-07 stage, not final delivery acceptance. The PSU275 QA copy is already listed as
`historical` under `master-qa` in `docs/architecture/contexts.yaml` (#1379).

In particular, PSU275 stage-5 now uses the shared slicer (4096 cap 3.9375 m), while this
historical QA copy still allows 4.0001 m. Its oversize verdict must not be presented as
D320 compliance for a new run. New D320 size checks use the shared master QA with the
actual tile size; the mass-ray exception remains job-local and is not replaced by that
size check. Any future authorized restart must explicitly reconcile those checks before
claiming acceptance. Keeping the copy here is the issue's documented-exception option,
not permission to rebuild, loosen the shared cap, or silently change an accepted result.

## Gated remainder (#1141 OPEN / waits-artem)

- `tools/materials/npm_atlas_udim.py::main`: live Python NPM atlas path, still listed as a bypass.
- `jobs/KPP1/scripts/make_npm_atlas.py::main`: historical NPM recipe; delivered outputs stay frozen.
- `jobs/TEC26-OKS/scripts/make_npm_atlas.py::main`: historical recipe with distinct validation and joint sizing;
  do not erase those protections in the future Max migration.

These three are intentionally not routed to Max here: #1141 waits for #1105's real-building proof.
This closes only the authorized independent compaction step, not #1141 or a delivery gate.

## UDIM behavior audit

Only VPM `tile_offset(udim)` was switched in this step: integer tile -> origin, same result as the old
`(tile - 1001) % 10, (tile - 1001) // 10` for valid integer tiles. Invalid inputs now raise the owner's
named error. No point/face classifier in another caller was changed. `test_udimtile.py` adds literal
border, nextafter-epsilon, closed-face right/top edge, real crossing and centroid-vs-corner expectations.
Point tiles remain half-open; strict whole-face bounds remain closed with the owner's 1e-6 tolerance.

## Evidence

Tests-first commit `554d663c`: initial regression 18 failed / 1 passed / 3 errors (missing owner).
Additional fail-closed RED: 4 failed; partial-period RED: 1 failed. These were genuine observed failures.
Synthetic native probe `tests/blender/run_uv_compaction_1380.py` compares the old KPP1 recipe frozen
from origin/main against the new owner (full/placeholder, shifted/unshifted, 4 tiles, glass) and tests
both tile sizes at/below/above the bound. Blender 5.1.2 headless: 43 checks passed, 0 failed, scene unchanged.
This is code/geometry QA on synthetic bmeshes, not real delivery acceptance or a new saved model.

Full suite: deferred to merge batch (rule 68).
Exact final affected-test command and counts are in the PR receipts.
