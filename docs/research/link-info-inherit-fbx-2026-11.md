# Link Info «Inherit» locks and FBX export (backlog Q10)

Research only, SYNTHETIC scene (five boxes, no real object). Source of the claim: `docs/research/telegram-3dsmax-chat-2026-11.md`
item 6. Plan step 3.3 of `docs/plans/telegram-findings-rollout.md`.

## Verdict

**Partly confirmed.** The «Inherit» flags themselves are not written to FBX: every Model carries `InheritType = 1`
(RSrs) and a re-import in Max gives all nine flags on. The exporter folds the flags into the child's local TRS
instead. That is exact for move-off and scale-off, but not when **rotate is off under a rotated, non-uniformly
scaled parent**: the needed local matrix has shear, the TRS decomposition drops it, and the child comes back
**452.9 mm / 11.39°** off on a 3 × 1 × 1 m box (both readers agree). After baking (keep world transform, unlink,
Reset XForm, collapse) every node matches within 0.004 mm / 0.0001°.

## Setup

- 3ds Max 2026.3 (28.3.0.30732), headless `3dsmaxbatch.exe` through `~/hermes_kanban/scripts/dcc_batch.py` (Max lock);
  no GUI Max, no MCP port. System units metres.
- Scene (`tools/research/link_info_inherit_fbx/build_export.ms`): parent box `P_synthetic` 3 × 2 × 4 m; children
  1.5 × 1 × 2 m boxes linked to P — `C1_inherit_all` (all on), `C2_no_rot` (rotate XYZ off), `C3_no_scale` (scale
  XYZ off), `C4_no_posX` (move X off). After linking P gets `scale [2, 1, 0.5] * rotZ 30° * translate [10, 20, 3]`.
  World transforms and world vertices (`snapshotAsMesh`) of every node go to JSON.
- Export: stock FBXEXP, `FileVersion FBX201400` (file version 7400, writer "FBX SDK/FBX Plugins version 2020.3.9"),
  binary, `ConvertUnit m` (`UnitScaleFactor 100`), Y-up, no animation, no triangulation.
- Baked variant, same scene: per child store `transform`, `parent = undefined`, inherit `#all`, restore the transform,
  `ResetXForm`, `collapseStack`; the Max world vertices before and after the bake differ by ≤ 0.002 mm.
- Readers: (1) repo readback `tools/blender/fbx_readback.py` in Blender 5.1.2 headless (world vertices);
  (2) a fresh headless Max FBX re-import (`reimport_max.ms`); (3) raw Model properties with Blender's FBX parser
  (`fbx_model_props.py`). Comparison `compare.py`: same vertex index, tolerance 1 mm and 0.01° (angle between
  centroid → vertex directions).
- Outputs (not in git): `C:\x\link-info-test-2026-11\` — `raw.fbx` sha256 `3a32cf57…54fea`, `baked.fbx` sha256
  `a4488689…ead06`, the `.max` scenes, all JSON.

## Raw export (hierarchy and flags as built)

Inherit = move / rotate / scale, XYZ bits.

| Child | Inherit | Max world centroid, m | Blender: max vertex Δ, mm / angle, ° | Max re-import: Δ, mm / angle, ° | Verdict |
|---|---|---|---|---|---|
| P_synthetic (parent) | 111 111 111 | [10, 20, 4] | 0.000 / 0.0000 | 0.002 / 0.0000 | match |
| C1_inherit_all | 111 111 111 | [18.660, 25.000, 3.5] | 0.000 / 0.0000 | 0.004 / 0.0000 | match |
| C2_no_rot | 111 000 111 | [7.500, 24.330, 3.5] | **452.911 / 11.3927** | **452.912 / 11.3927** | **MISMATCH** |
| C3_no_scale | 111 111 000 | [16.160, 29.330, 4.0] | 0.001 / 0.0000 | 0.003 / 0.0000 | match |
| C4_no_posX | 011 111 111 | [-9.660, 16.732, 4.0] | 0.003 / 0.0000 | 0.004 / 0.0000 | match |

C2's centroid is right; the box is rotated and sheared around it. In Max C2's world matrix is an axis-aligned scale
`diag(2, 1, 0.5)` (no rotation); the FBX writes `Lcl Rotation Z −49.107°`, `Lcl Scaling [1.3229, 0.9014, 1]` under
the 30° parent — a TRS that cannot reproduce a world box without rotation. C3 and C4 export exact compensating local
values (`Lcl Scaling [0.5, 1, 2]`; `Lcl Translation [-9.330, 7, 1]`), so they survive.

## Baked export (unlinked, Reset XForm, collapsed)

| Child | Blender: Δ, mm / angle, ° | Max re-import: Δ, mm / angle, ° | Verdict |
|---|---|---|---|
| P_synthetic | 0.000 / 0.0000 | 0.002 / 0.0000 | match |
| C1_inherit_all | 0.002 / 0.0000 | 0.000 / 0.0000 | match |
| C2_no_rot | 0.000 / 0.0000 | 0.000 / 0.0000 | match |
| C3_no_scale | 0.001 / 0.0000 | 0.000 / 0.0000 | match |
| C4_no_posX | 0.002 / 0.0001 | 0.000 / 0.0000 | match |

## Verification boundary

- One Max build (2026.3), one exporter version, one parent transform, static (no animation). Animated parents and
  FBX 2020 file versions were not tested.
- Not measured, expected from the algebra: under a uniformly scaled parent the rotate-off local is a similarity
  and should export exactly; partial rotate flags (one axis) and rotate-off + scale-off combinations are untested.
- The Max re-import reads the same SDK the exporter used, so it is not independent of FBX semantics; Blender is the
  independent reader and agrees on the match/mismatch verdicts at the stated 1 mm / 0.01° tolerance.
  Direct inter-reader vertex distance was not measured.

## Reproduce

```
py -3 ~/hermes_kanban/scripts/dcc_batch.py max --file tools/research/link_info_inherit_fbx/build_export.ms --card q10
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender/fbx_readback.py -- C:\x\link-info-test-2026-11\raw.fbx C:\x\link-info-test-2026-11\blender_raw.json
# same for baked.fbx -> blender_baked.json
py -3 ~/hermes_kanban/scripts/dcc_batch.py max --file tools/research/link_info_inherit_fbx/reimport_max.ms --card q10
py -3 tools/research/link_info_inherit_fbx/compare.py C:\x\link-info-test-2026-11
```
