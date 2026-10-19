# model-ground skill — dry walk-through on the GROUND-PROJECTION inputs

Date: 2026-10-16. Card: pilot #176. Skill: [`.agents/skills/model-ground/SKILL.md`](../../.agents/skills/model-ground/SKILL.md).
A dry walk: each step is read against the inputs of `jobs/GROUND-PROJECTION/` and the tools of this workstation;
no Ground is built (out of scope). This is not delivery validation and claims no acceptance.

## Inputs of GROUND-PROJECTION

From [`jobs/GROUND-PROJECTION/RESULT.md`](../../jobs/GROUND-PROJECTION/RESULT.md),
[`NPM_RESULT.md`](../../jobs/GROUND-PROJECTION/NPM_RESULT.md) and the
[case study](../agr/case_studies/GROUND_CONTOURS_AND_NPM.md) (lessons only):

- `GROUND.fbx` (Telegram Desktop download, SHA-256 `21ee39bb…cf`): mesh `Ground` (flat coverings, 18 material IDs,
  no UVs) and mesh `Relef` (relief surface); site 116.447 × 163.833 m; the source was 100× off in world units.
- No SPOZU DWG, no boundary layer, no vertical-planning points: the job started from a finished FBX.
- On 2026-10-16 the file is no longer at `Downloads/Telegram Desktop/GROUND.fbx`
  (`ls: cannot access ... No such file or directory`); the job outputs (`outputs/`) are local-only and not in this worktree.

Supplementary probe for steps 1-3 and 5 (GROUND-PROJECTION has no DWG): a real SPOZU drawing of another project
from the user's Desktop, copied to the scratch dir, exported and inventoried. Counts only; nothing committed.

```text
python hermes_kanban/scripts/dcc_batch.py acad --ping                       -> AGR_PING acad=25.0, exit 0, 2.8 s
python hermes_kanban/scripts/dcc_batch.py acad --file dxfout.scr --dwg <copy>.dwg
   (_.DXFOUT <copy>.dxf _V 2018 16)                                          -> AGR_DXFOUT_DONE; 19.7 MB DWG -> 142 MB DXF
uv run --offline --extra cad python probe.py <copy>.dxf                     -> read 41 s, $INSUNITS 6 (m), 248 layers, layouts Model, СПОЗУ
   model space: 23 hatches on 9 layers; 0 entities on the 8 «границ*» layers; 0 elevation-like texts
   all block records (nested): 6097 hatches on 60 layers; 2530 elevation-like texts (NNN.NN);
   «границ*» layers: Граница, Граница площадки, Граница заказа, 1.1_Граница_ГПЗУ, Граница улицы, ... —
   none named «граница проектируемого участка» / «граница ГП»
```

Lessons fed into the skill: geometry sits inside block references (step 1 counts nested entities), and the boundary
layer name varies by project (step 2 asks the user when no layer matches).

## Step by step

| Step | GROUND-PROJECTION input for it | Route today | Automatable today |
|---|---|---|---|
| 1 SPOZU DWG intake | none (no DWG in the job) | `dcc_batch.py acad` DXFOUT + `ezdxf` — exercised above on another SPOZU | yes (headless, proven on the probe); picking the coverings sheet is human |
| 2 Boundary layer | none; extent known only from the FBX bbox | `ezdxf` layer search + closed-polyline area | partly: search runs; the probe shows no canonical layer name, so the user picks |
| 3 Coverings to contours | contours implicit in `Ground` faces (18 IDs, accepted in v003) | `ezdxf` hatch paths -> polylines; DXF -> DWG via core console `SAVEAS` | partly: no reviewed contour script; covering -> material list is human |
| 4 Layered cake | 18 covering regions, flat | 3ds Max batch (startup `polyunwrapper_autoload.mse` error) or Blender headless | no tool yet; route exists (Blender 4.4/5.1 headless, Max 2026 batch smoke-checked) |
| 5 Elevations | none: `Relef` is already a surface, no marks | `ezdxf` text/attribute parse | partly: 2530 candidate marks found nested in the probe; design vs existing marks need the user |
| 6 Relief surface | `Relef` mesh (given) | Blender headless `mathutils.geometry.delaunay_2d_cdt` + source Z (probe `tests/fixtures/model_ground_route_probe.py`) | step skipped for this job (input already a surface); route proven on synthetic points (4 points -> 2 faces, Z kept; empty/2/collinear/contradictory-Z rejected), no reviewed tool yet (T-GND-3) |
| 7 Project onto relief | `Ground` + `Relef` | Blender headless `BVHTree.ray_cast` per vertex, `z = relief + layer offset` (same probe) | partly: route proven on synthetic layers (6 mm kept, XY/UV/material IDs unchanged, misses listed); the job's v003 projection was single-layer and is a lesson, not the method (C37); plain Shrinkwrap/`Conform` collapses the 6 mm steps |
| 8 Curbs, steps, ramps, walls | not modelled in the job (v008 smoothed steps away) | Max batch / Blender headless extrusions | no: live or human today; threshold open (C37) |
| 9 NPM and VPM | NPM only (v008, TD 19.5-20.3 px/m measured with AGR Checker's TD body) | Blender headless export + TD per face | partly: NPM TD measurement exists in the job scripts; VPM derivation, UDIM, perimeter skirt not done |
| 10 Checks | v003/v008 readbacks (material IDs, contours ≤ 0.715 mm, no duplicates) | `tools/qa/validate_package.py`, Blender readback/renders | partly: readback and package checks headless; seams, collisions, visual verdict human |

Summary: of 10 steps, 1 is automatable end-to-end today (1), 6 partly (2, 3, 5, 7, 9, 10), 2 have a route but no
reviewed tool (4, 6), 1 needs a live program or a human (8). GROUND-PROJECTION cannot exercise steps 1-3 and 5 at all, because
it has no SPOZU DWG; a benchmark from a SPOZU drawing (T-GND-4) is the input those steps need.
