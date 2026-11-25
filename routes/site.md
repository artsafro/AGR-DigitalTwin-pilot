# Site trail: Ground -> MAF -> Flora (`ground-npm`, `ground-vpm`)

**Trail of the site cells (#1895, hygiene rec 9), modelled on [routes/npm-oks.md](npm-oks.md).** It orders the
stages and names the rule and the command at each step; the rules stay in their owners (cell cards
[ground-npm](../docs/scenarios/ground-npm.md), [ground-vpm](../docs/scenarios/ground-vpm.md), area sheets, skills).
Not an approval of any model or delivery. Call `agr --help` before writing a script.

## Entry

Passport first: `jobs/<ID>/passport.json` (K1, `schemas/ProjectPassport.schema.json`) for every task [D397], then
intake (`docs/agents/task-intake.md`) and the cell block
(`uv run python tools/architecture/skeleton_guard.py --show ground-npm` or `--show ground-vpm`).
Read the stage skill when the stage starts: Ground `.agents/skills/model-ground/SKILL.md`, MAF
`.agents/skills/model-maf/SKILL.md`, Flora `.agents/skills/model-flora/SKILL.md`; area sheets at their step.
Order for VPM: textures and IDs on the flat Ground first, relief last [D293]. VPM + NPM: VPM first, NPM is derived.

## Stages

| # | Stage | Command / owner | Rule at this step | Evidence |
|---|---|---|---|---|
| 1 | Sources (SPOZU DWG/DXF) | `uv run python tools/source/inspect_ground_dxf.py` | sources outside git + SHA-256 (`jobs/<ID>/sources.json`) | hashes, units, layers, boundary candidates |
| 2 | Boundary and zero (VPM) | boundary and ±0.000 from PZU / vertical planning, else ask; `agr zero` only verifies a supplied zero | [D279] | zero source recorded; no inferred zero |
| 3 | Ground surfaces, IDs, relief, skirt | `agr ground site SPEC.json NEW_OUT` (`dt ground site`; shared covers `params.surfaces: "shared"`, #1738) | [D293] order; cover ID 1..10 -> UDIM 1001-1010; skirt >= 1 m | `ground-report.json`; OBJ readback, `skirt_check_export` |
| 4 | Ground quads (new site) | gap: `dt ground v015` replays Vatutino only | `docs/agents/SKELETONS.md` gaps | ask before a job hook |
| 5 | UCX Ground (VPM) | `agr ucx MODEL OUT Ground` | [D330] | readback, `ucx10_core` gap check, V010 |
| 6 | MAF: library match / new model | skill `model-maf`; `tools/materials/atlas_maf.py`; NPM-light `agr npm-light SPEC.json --out NEW_DIR` | `docs/domain/areas/groundel-maf.md` | library ids, atlas, silhouette gate |
| 7 | Flora | skill `model-flora`; `dt_ai.materials.flora`, `tools/flora/build_flora_star.py` | `docs/domain/areas/flora.md` | catalogue match or star, NPM point |
| 8 | Placement | `uv run python -m dt_ai.placement.engine`; NPM + VPM pair `agr place` | owner `dt_ai.placement` [D330] | placement report |
| 9 | Derive NPM (VPM + NPM) | `agr vpm-to-npm` | cell `vpm-to-npm` budget ladder; no ProOptimizer step | NPM readback |
| 10 | QA, package, checker | `tools/qa/master_topology.py`; `tools/blender/fbx_readback.py`, `dt qa xview`; `agr package-npm` / `agr package-vpm`; `agr validate` (`--ground-area-m2` for VPM); `agr checker` after visual acceptance | `validate-delivery` skill | exported-file readback, package validation, checker report |

Stage details and hooks: [SKELETONS-stages.md](../docs/agents/SKELETONS-stages.md) (`ground-npm`, `ground-vpm`).
