# NPM / OKS — first route draft (#1296)

**Research draft for Artem, not an installed command or an approved production procedure.**
Only cell `oks-npm`; `oks-npm-lite` and VPM/Ground are not drafted here. The router
[scenarios.json](../docs/scenarios/scenarios.json) still marks this cell `todo`.
All `agr ...` invocations below are **proposed interfaces**, not executable today.
Today's equivalents are explicitly named; inspect their arguments and job assumptions before use.

## Entry: narrow context, explicit contract

Read AGENTS.md, the task and `jobs/<ID>/{TASK.md,STATE.md,LESSONS.md,sources.json}`,
then the `oks-npm` reads list in scenarios.json, selecting only applicable requirements.
Start with [BODY](../docs/domain/areas/body.md) and
[derivation](../docs/domain/areas/derivation.md); load windows and UV/atlas at those steps.
Use [TASK_TO_MODEL](../docs/procedure/TASK_TO_MODEL.md) for all eight gates.
Do **not** preload Ground/MAF/Flora/UCX rules, all job histories, all tool schemas or
`docs/agr/` recursively. Read a cross-area interface only when the task actually needs it.
The required project state read is an index, not permission to load every linked area.

At intake: resolve source authority, dimensions, materials, protected geometry/UV/IDs,
placement/district/address, deliverable and pilot once. Missing facts/conflicts stop the
dependent step; no generic shell thickness, joint module or georeference is guessed.
`jobs/<ID>/job.yaml` holds gates. On AGR Tools routes `passport.json` is mandatory;
on other OKS routes D247 permits equivalent inputs/report facts (do not falsely claim
that a passport is already universal). The proposed CLI should consume that contract,
not replace or silently amend it.

## Level and recipes

Use the accepted requirements of [#1280](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1280)
and the merged [#1273 table](../docs/research/agent-step-waste-1273.md#4-draft-check-levels):
`standard` for a new job node; `fast` only for an accepted-model colour/minor change
with one machine readback; `full` for shared code/export changes or `passed=true` delivery.
Artem can override; raise the level when scope grows, never silently lower it.
This research PR follows its card's full-suite requirement, regardless of a future job level.

Recipes: [#1281](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1281)
will publish production recipes; until merged, the concrete available sources are
[R6 BODY/facade](../docs/research/agent-step-waste-1273.md#r6-oks-body--facade-standard-full-when-the-delivery-claims-passedtrue),
[R4 windows](../docs/research/agent-step-waste-1273.md#r4-window--glazing-standard),
and [R1 colouring](../docs/research/agent-step-waste-1273.md#r1-colouring--finish-swap-fast).
No dependency branch or unmerged recipe file is consumed.

## Route by stage: proposal versus today's tool

| Step / gate | Proposed interface | Reuse today / boundary | Evidence required |
|---|---|---|---|
| 1. Sources / inputs | `agr inspect --job ID --sources sources.json --out NEW` | Source inventory; `tools/research/pdf_corpus/pdf_corpus_inventory.py` if applicable; job source census, not automatic interpretation | Original/copy hashes, units, revision, dimensions, source authority; no writes to originals |
| 2. Parts / user Gate 1 | Same inspect report into confirmed PartsList, no invented auto-approval | `dt_ai.core.models.PartsList`, job contract and checklist | User confirmation of exact parts hash before construction |
| 3. BODY / operations | Geometry remains the existing approved source/engine route; no universal `agr build` promised | `src/dt_ai/spec`, `src/dt_ai/parts`, `src/dt_ai/ops` for supported cases; existing job build only for its validated object | Separate body/openings/decor, dimensions and source overlays; before/after invariants; deviation when unsupported |
| 4. Facade detail | `agr brick-seams --job ID --config CONFIG --out NEW` only if approved source calls for brick seams | Candidate job algorithms need extraction/calibration; never apply to cassette facades automatically | Source module/phase/width, opening intersections, silhouette and unchanged protected IDs |
| 5. NPM derivation / budgets | `agr vpm-to-npm --job ID --master MASTER --config CONFIG --out NEW` then `agr unwrap-atlas --profile npm --config CONFIG --out NEW` | `tools/derive/{export_npm,npm_atlas}.py`, `tools/materials/npm_atlas_udim.py`; KPP1 scripts are precedents, not portable executables | One mid-poly master; profile-specific alpha/atlas, glass separated, NPM no UCX; limits from area sheets, not arbitrary raster density |
| 6. Delivery / export_readback | `agr delivery-export --profile npm --job ID --out NEW`; `agr validate --profile npm --input EXPORT --master MASTER --out NEW` | Existing export/readback and `tools/qa/validate_package.py`; `uv run dt qa xview FILE --out NEW.json` after geometry writes and on export | Fresh-process exported-file topology, UV, materials, transforms; hashes; defects with values/limits, not scene-only QA |
| 7. Report / visual | `agr open-in-max --input COPY --read-only`; Blender review if Max busy | Existing Blender runner/review scene; Max lock and version/document/unit confirmation before Max; never interrupt Artem's render | Open scene + absolute path when Artem online; otherwise one side-by-side per item + overview at standard; no gratuitous renders |
| 8. Checker / delivery decision | `agr validate --checker sintez --profile npm --input EXPORT --out NEW` | Existing SINTEZ runner/installed checker; final AGR Tools-in-Max only when that required route is available | Final complete checker after human visual approval on the same export hashes; manual gates stay explicit |

Headless **Blender first** for measurements, analysis, construction and readback of copies.
Max is retained for Corona/viz, Max-native work and final AGR Tools checks, not as a reason
to stall Blender-capable work. Unknown write outcome: reconcile IDs/counts/hashes first,
never retry a write blindly. CLI is the portable entry; an MCP wrapper can dispatch the
same contract later. [#1292](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1292)
batches guarded DCC operations, not source interpretation or acceptance gates.

**Today's executable discovery (no geometry is produced):** `uv run dt --help` and
`uv run dt derive atlas --help`. For an authorized packet the existing chain is
`uv run dt derive atlas SPEC NEW_ATLAS --recipe-dir RECIPE`, then
`uv run dt derive --blender BLENDER npm MASTER SPEC ATLAS NEW_EXPORT PREFIX`;
these dispatch the shared tools, not copied job scripts. Units, placement and remaining
job dependencies must be reviewed before execution; no authorization is implied by this example.

## Worked continuation: KPP1, not a new fabricated run

[STATE.md](../jobs/KPP1/STATE.md) records a VPM/master + NPM pipeline, historical
`make_npm_atlas.py` / `export_npm.py`, and current rerun blockers. A worker first loads
current `TASK.md`, `job.yaml` and exact rerun receipts; the historical v002 is not today's acceptance.
Keep approved R1 geometry, run the approved master through today's NPM atlas/export
path on a new copy, then fresh readback, xView and NPM validator diagnostics.
The proposed `agr vpm-to-npm` + `unwrap-atlas` + `delivery-export` would remove job-path
editing, not invent district code/address/coordinates or mark deferred Ground complete.
Historical KPP1 2048 atlas / 4.096 m region / about 97 px/m are **job-specific** config,
not an NPM OKS density rule. KPP1's outstanding human/Max/checker items remain outstanding;
this draft performs no DCC call and produces no model.

## Definition of done

For a node: source-matched geometry/materials, exported-file readback and measured applicable
checks, a versioned artifact/path and Artem's visual verdict. For a complete delivery:
all eight TASK_TO_MODEL gates, every mandatory machine/manual check and final checker closed
on the same inputs/parts/exports; only then `passed=true`. Unsupported, missing, review,
not_run and partial results are not passes. Technical QA != user acceptance != publication.
Fail closed on missing inputs/material maps, NaN/inf, aliases among input/output/report/temp,
changed sources and stale receipts. CLI implementation must test these; this draft does not
claim those guards already exist in every wrapper.

## Questions for Artem (approval, not implementation blockers)

1. Is this one-cell route understandable enough to use as the template? Recommendation: pilot KPP1 NPM derivation before drafting VPM/Ground.
2. Approve the top-10 reuse priority after the inventory, keeping `agr` a facade over existing cores rather than a rewrite?
3. Which immutable, already accepted KPP1/master + source packet can be authorized for the comparison benchmark? Do not spend the $10 or choose production material/joint values until authorized.
