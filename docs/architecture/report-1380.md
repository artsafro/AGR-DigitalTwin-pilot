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
