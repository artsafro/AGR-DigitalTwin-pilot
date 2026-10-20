# Ground v015 option-(a) session checkpoint — #371

**Status: incomplete; neither candidate is a v015 delivery. No PR, Max scene, FBX,
review-queue entry or acceptance receipt was published.** This session stops at the
remaining xView offenders, as directed by the latest card decision. Production
`build_ground.py`, `ground_details.py`, `ground_cake.py`, D150 and the original
v014 assets are unchanged. The construction changes below are diagnostic only.

## Active decision

[D157] records the user's latest option (a) and explicitly supersedes [D156].
The 90k Steiner route and coarse remesh routes are rejected. Ground NPM may retain
up to 35% triangles by polygon count after pairing; this is the whole Ground share,
not a statement that every texture slot has that share. Pure quads remain a VPM
goal. The 50,000 surface-polygon cap, 180,000 whole-Ground triangle budget, 10 mm
relief tolerance, fixed texture IDs, D150 and xView 0/0 are unchanged.
The general D129 implementation was **not** silently weakened to make a receipt pass.

## Implemented primitive (not yet integrated)

`dt_ai.geometry.ground_quads.pair_triangles` pairs D129-mergeable triangles with
matching slot, level and shared-edge UVs. It introduces no vertices or Steiner
subdivision. The original shared diagonal is always output corners 0--2; the fixed
fan is exactly the original source triangle inventory. Every input face is retained
in `source_faces`, once. Discontinuities and non-mergeable triangles remain triangles;
malformed/empty/duplicate/nonfinite seeds raise errors before conversion.

This preserves the piecewise-linear surface only **with that tessellation**.
Max/Blender/FBX may choose another diagonal: exported-file deviation is still
unmeasured, not certified zero. Mixed triangles/quads use per-face UV arrays.
The earlier all-quad `remesh` checkpoint is retained but is not selected for delivery.

Tests-first commit `e89da2d`: **24 failed** before the primitive, then **67 passed**
(new pairing + existing remesher tests). Decision-supersession regression at
`5bd8b29`: **1 failed / 1 passed** before the documentation change.
Combined focused run: **158 passed / 0 failed** (10.68 s initially; final source
recheck 8.55 s, `tmp/pair-final.log`). Independent evidence consistency assertions:
**8/8 passed** (slot totals, budgets, share, source inventory, exact remaining-pair
list and explicit failed status). Test selection:

```text
uv run pytest -q tests/test_ground_pairing.py tests/test_ground_quads.py tests/test_ground_v015_budget_decision.py tests/test_ground_surface_requirement_sheet.py tests/test_ground_cake.py tests/test_ground_details.py tests/test_ground_cleanup.py tests/test_ground_review_r1.py tests/test_ground_review_r2.py tests/test_ground_gap_exceptions.py -p no:cacheprovider --basetemp=C:/x/t_eb1c51ca/pair-focus
```

## Real v014 pairing measurement

Source: `C:/x/ev_t_eb1c51ca/v014_rebuild/ground_master_vpm.json`, SHA-256
`82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5`.
This is the earlier source-pinned v014 rebuild, not a newly invented input.

Legacy detail triangles each had a separate UV frame, preventing useful pairing.
The geometry probe reprojects details onto common metric planes before pairing;
final tile containment, density and map appearance are **not** certified. Surface
pair candidates also check the original NPM shared-edge UVs (zero additional splits).

| Slot | v014 triangles (0 quads) | Paired quads | Paired triangles | Triangle share |
|---|---:|---:|---:|---:|
| CurbGarden | 9844 | 4713 | 418 | 8.147% |
| FlowerBed | 134 | 45 | 44 | 49.438% |
| Gravel | 618 | 204 | 210 | 50.725% |
| LawnReinforced | 1311 | 459 | 393 | 46.127% |
| LawnRolled | 2088 | 650 | 788 | 54.798% |
| Mulch | 3263 | 1083 | 1097 | 50.321% |
| Pebbles | 291 | 71 | 149 | 67.727% |
| Skirt | 3578 | 1789 | 0 | 0.000% |
| Stairs | 100 | 46 | 8 | 14.815% |
| TileDark | 509 | 218 | 73 | 25.086% |
| TileLight | 21603 | 8047 | 5509 | 40.639% |
| TileRed | 3004 | 1193 | 618 | 34.125% |

Whole paired mesh: **18,518 quads + 9,307 triangles = 33.448% triangles**;
**20,851 surface polygons**, **46,343 triangle-equivalent** excluding MAF/Flora.
Source inventory equality is exact under the fixed diagonal, so its corresponding
surface deviation is 0 mm. This is not an exported-file or silhouette receipt.
The per-slot `raw_d129_labels` in the evidence retains every measured reason,
including `unneeded` and `mergeable`; it is not falsely reported as baseline D129 pass.

## xView construction probe and remaining offenders

Pairing alone: **ours 0 overlapping vertex pairs / 76 overlapping face pairs**.
This is fewer *polygon pairs*, not proof that triangle-pair geometry defects disappeared.
The v014 triangle report counted 222 face pairs: Skirt/Stairs 148, CurbGarden/Stairs
29, Skirt/Skirt 18, Stairs/Stairs 12, CurbGarden/raised cake 15 (card analysis).

A bounded **geometry-only** probe then:

1. Rebuilt closed curb solids with a 6 mm XY clearance around stair footprints,
   instead of subtracting exactly touching footprints.
2. Clipped 66 skirt triangles against stair faces in a 5.1 mm plane slab, retaining
   all non-overlapping curtain fragments and their source-face identities; no
   source skirt face was completely removed. Perimeter depth/continuity after
   this clipping is unmeasured, not accepted.
3. Reused original cake and stair geometry and re-ran cleanup, pairing and ours xView.

Candidate: **19,224 quads + 7,996 triangles**, 20,152 surface polygons,
46,444 triangle-equivalent, 29.375% triangles. Its all-surface metric UV is only
for feasibility; do not export it as final material mapping.

Remaining **ours 0 OV pairs / 24 OF pairs**:

| Remaining pair class | Pairs | Construction origin / unresolved cause |
|---|---:|---|
| Skirt × Skirt | 6 | `add_skirt`: near-coincident source outline curtain segments |
| Stairs × Stairs | 8 | `_stairs_solid`: vertical T-junction/contact subdivisions |
| CurbGarden × Stairs | 4 | `build_details`: residual near-parallel junction faces despite XY clearance |
| CurbGarden × Mulch | 3 | `_curb_solid` datum versus locally steep-raised cake |
| CurbGarden × LawnReinforced | 3 | `_curb_solid` datum versus locally steep-raised cake |

Complete face IDs, kinds, separations and both face coordinate lists are in
`ground-v015-pairing-evidence.json`, `construction_probe.face_witnesses`.
These are polygon IDs for that exact diagnostic, not v014 triangle IDs.
No third geometry repair was attempted after these two xView-failing candidates.

### Bow-tie conversion risk (not a native Max measurement)

Both candidates still contain **59 vertices with multiple edge-connected face fans**.
An independent incidence/fan-split simulation yields **59 coincident vertex pairs /
118 affected vertices at 2 mm**. The original indexed polygon mesh's OV=0 hides this
conversion risk. Exact vertex coordinates and incident fan face lists are retained
under `fan_conversion_risk`. Splitting coincident vertices is **not** an OV fix.
Native Max xView on a delivered scene: **not run; no delivered scene exists**.

## Material IDs and D150

`ground-material-ids-v015.json` fixes the inherited alphabetical 12-slot order,
one-based IDs 1..12 and exact `M_Vatutino_Ground_<Slot>` names. It is an ID
**specification**, not a Max/Blender material-ID readback table. No Multi/Sub scene
has been generated or certified. The D150 manifest is unchanged and its hash is
recorded. Pairing preserves its triangle surface in the fixed tessellation, but
polygon/readback sample identities and centroids still need an explicit re-pin and
remeasurement before final acceptance; construction-probe acceptance is not implied.

## Reproduction and handoff

`ground-v015-pairing-evidence.json` embeds the exact three diagnostic programs and
SHA-256 fingerprints, both complete xView reports, per-slot classifications, source
hashes and all 59 bow-tie witnesses. Extract the `programs[*].utf8` values into this
worktree's ignored `tmp/` and run in order:

```text
uv run python tmp/paired-xview-probe.py
uv run python tmp/construction-probe.py
uv run python tmp/bowtie-conversion-risk.py
```

Local logs/arrays remain under this worktree's `tmp/`: paired-detailuv-xview.log,
construction-probe.log/.json/.npz, paired-v014.json, bowtie-conversion-risk.json,
pair-red.log, pair-green.log, d157-red.log and pair-focus.log.
The initial original-detail-UV probe wrote a complete measurement report and then
failed to serialize numpy integer IDs in its mesh scratch output. SELF-FIX: retain
that report as paired-original-uv-xview.json, serialize IDs explicitly, and run the
separate shared-detail-UV variant successfully (exit 0). No source asset was altered.

Still open: the 24 face pairs, 59 bow-ties, construction perimeter/relief/gap checks,
final profile UVs, D150 re-pin, actual Multi/Sub IDs, Max + Blender export/readback,
UCX/placement compatibility and review publication (#348/PR #373 is still external).
The full non-DCC suite and DCC tests were **not run for these rejected candidates**;
the 158 focused tests are primitive/regression evidence only. Do not request review
or mark #371 complete from this checkpoint. Any continuation requires the user's
disposition after the explicitly bounded xView-cleaning session.
