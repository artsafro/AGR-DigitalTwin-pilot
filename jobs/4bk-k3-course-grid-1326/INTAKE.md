# 4BK stylobate course-grid pilot #1326 — intake checkpoint

Status: **finish cohort, stair-return seams and two main-wall ring terminations confirmed; no UV production performed**.
Main-wall answer (2026-11-14): `main-wall-seam-approval.json`; the earlier pending
termination question in `LOOP_POLICY.md` is answered. Check level: `full` (reusable tooling).

Current checkpoint: `LOOP_POLICY.md`, fresh source-bound `ring-audit-v003.json` and
Artem's exact stair-only permission in `seam-approval.json`. Earlier questions below
are historical; do not reopen the approved cohort or stair-return seam scope.

The prior pending-cohort status below is superseded by Artem's 2026-11-13 voice answer
recorded on card `t_d517d7c6` (18:43 UTC board comment). See `finish-approval.json`
and `CHART_POLICY.md`; source assignments and their original manifest hash are unchanged.
Cell: `oks-vpm`. This is not the final 4BK delivery.

## Authority and scope

- Frozen source repository: `C:/Users/artsafro/.AGR-DigitalTwin_pilot`,
  `job/4bk-k3-vpm`, commit `06546d3d9691d1bcc62171ffd07aa56a6c4de9e3`.
- Latest delivered scene named in transcript S1:2608:
  `C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/3k_v004.max`.
- Its assembly source from S1:2591: `build/blender/K3_assembly_v006.blend`.
- Transcript and historical evidence: `docs/research/vpm-course-grid-1314.md`.
- Pilot decisions: [D275], reserved on card t_d517d7c6 after
  `uv run python tools/git-hooks/decision_ids.py next` returned `D275`
  across origin/main, this branch and 8 open PR heads.
- Tool choice: own background Blender 5.1.2, on a hash-identical copy;
  this keeps Artem's daytime Max and delivered files untouched.

## Do not touch

Source/delivered scenes and bitmaps; tower brick, tower metal, stylobate
non-brick finishes, geometry/topology, source face indices and material IDs.
No replication, cuts, density reduction or additional tiles.

## Job-local opening preference

Artem's answer:
https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1326#issuecomment-6852161335

Prepare separate versioned copies. Ask when a stage is ready; open in Max 2026
only after Artem says **«открой»**, with quads and an absolute path. Never
switch or modify his daytime scene automatically. This preference is not a D-row.

## Finish-manifest gate

The card's ID1 brick / ID2 metal / ID3 reveals is **not** the delivered
stylobate's actual material-slot assignment. Fresh source-copy readback gives:

| Object | Source material ID (one-based) | Source material name | Faces |
|---|---:|---|---:|
| K3_StylobateWalls.001 | 1 | ID1_Brick_Stylo | 705 |
| K3_StylobateWalls.001 | 4 | ID4_Reveal_Sill_RAL7024 | 491 |
| K3_StylobateWalls.001 | 10 | ID10_Surround_Stylo | 317 |
| K3_StylobateStair.001 | 1 | ID1_Brick_Stylo | 66 |
| K3_StylobateStair.001 | 7 | ID7_Metal_RAL7024.003 | 436 |

The source has zero used ID2/ID3 faces in these two meshes. ID4 combines
reveals and sills, and ID10 is a separate surround finish. Do not silently
renumber or relabel these as the card's ID3.

**Question to Artem:** retain the delivered assignment and target only the
771 existing ID1 faces (705 wall + 66 stair), preserving the 491 ID4,
317 ID10 and 436 ID7 faces? Recommended: yes, preserve those existing finishes
and IDs. If some surrounds/reveals must instead join the brick cohort, identify
the intended regions before UV work. The first manifest deliberately records
source assignments and proposed dispositions, not an invented approved finish map.

## Frozen numerical contract

38 courses per 3.15 m; Bricks1 unchanged. Proposed seam convention: a full
10 mm joint inside the owning panel, centre 5 mm inward from its edge.
No joint convention has yet been applied to a new texture.

The delivered compact tile's declared sampling density is 512 px/m;
this is distinct from the underlying 38-course physical brick repeat
(4096 px / (48 * 3.15 / 38) = approximately 1029.418 source px/m).
Fresh directional measurements of its existing UVs are in `intake.json`.
They are **not passing**: the minimum is below 512. Do not reuse historical
1,953/1,953 joint counts as new evidence and do not waive the legal band.

After finish confirmation: rectify/prove source chart scale at the frozen
sampling target before packing; reuse existing UV cores; measure full phase,
joint masks, density, union occupancy, islands and padding on fresh readback;
request Artem's visual verdict before replication. Report overflow and ask
extra-tile versus authorized loop-cut options; never choose a fallback alone.
