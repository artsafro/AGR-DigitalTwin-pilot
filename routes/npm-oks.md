# NPM / OKS — accepted route template (#1296, #1317)

**Accepted route shape [D271]; not approval of any particular model or delivery.**
Only cell `oks-npm`; `oks-npm-lite` and VPM/Ground are not drafted here. The router
[scenarios.json](../docs/scenarios/scenarios.json) points this ready cell here.
Call `agr --help` before writing a script. Milestone 1 is five thin dispatch aliases
and six fail-closed pointer stubs (11 named commands, correcting #1317's counting typo).
The stage table retains proposed future job/config flags, not executable syntax;
use the exact executable forms below. Existing tools retain their validation and job assumptions.

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
| 1. Sources / inputs | `agr inspect --manifest JOB.json`; source inventory remains separate | Source inventory; `tools/research/pdf_corpus/pdf_corpus_inventory.py` if applicable; job source census, not automatic interpretation | Original/copy hashes, units, revision, dimensions, source authority; no writes to originals |
| 2. Parts / user Gate 1 | Same inspect report into confirmed PartsList, no invented auto-approval | `dt_ai.core.models.PartsList`, job contract and checklist | User confirmation of exact parts hash before construction |
| 3. BODY / operations | Geometry remains the existing approved source/engine route; no universal `agr build` promised | `src/dt_ai/spec`, `src/dt_ai/parts`, `src/dt_ai/ops` for supported cases; existing job build only for its validated object | Separate body/openings/decor, dimensions and source overlays; before/after invariants; deviation when unsupported |
| 4. Facade detail | `agr brick-seams --job ID --config CONFIG --out NEW` only if approved source calls for brick seams | Candidate job algorithms need extraction/calibration; never apply to cassette facades automatically | Source module/phase/width, opening intersections, silhouette and unchanged protected IDs |
| 5. NPM derivation / budgets | `agr vpm-to-npm [--blender BLENDER] ATLAS_ARGS --then-npm NPM_ARGS`; `unwrap-atlas` remains a pointer | `tools/derive/{export_npm,npm_atlas}.py`, `tools/materials/npm_atlas_udim.py`; KPP1 scripts are precedents, not portable executables | Master by task [D292]: VPM+NPM derives NPM from one VPM / mid-poly master; NPM-only builds NPM directly, no mid-poly master. Atlas path A (UDIM) or B (material IDs); profile-specific alpha/atlas, glass separated, NPM no UCX; limits from area sheets, not arbitrary raster density |
| 6. Delivery / export_readback | `delivery-export` remains a pointer; `agr validate EXPORT --profile npm --scene --master MASTER --json` | Existing export/readback and `tools/qa/validate_package.py`; `uv run dt qa xview FILE --out NEW.json` after geometry writes and on export | Fresh-process exported-file topology, UV, materials, transforms; hashes; defects with values/limits, not scene-only QA |
| 7. Report / visual | `agr open-in-max --input COPY --read-only`; Blender review if Max busy | Existing Blender runner/review scene; Max lock and version/document/unit confirmation before Max; never interrupt Artem's render | Open scene + absolute path when Artem online; otherwise one side-by-side per item + overview at standard; no gratuitous renders |
| 8. Checker / delivery decision | Existing installed SINTEZ route; `agr validate` does not add a `--checker` mode | Existing SINTEZ runner/installed checker; final AGR Tools-in-Max only when that required route is available | Final complete checker after human visual approval on the same export hashes; manual gates stay explicit |

### Branches by task [D292]

The [route map](../docs/architecture/npm-oks-route.svg) draws these as branches inside a stage
(source: `docs/architecture/npm-oks-route.events.yaml`). Pick one per task and state it in the job report.

- **Master (step 3/5).** VPM+NPM: build the VPM or a mid-poly master and derive NPM from it [D010].
  NPM-only: build NPM directly; no mid-poly master is made.
- **Atlas (step 5).** Path A: unwrap the master to UDIMs, then build the NPM atlas from the UDIMs
  (`tools/materials/npm_atlas_udim.py`; no `agr`/`dt` command, `unwrap-atlas` stays a pointer).
  Path B: directly by material ID, each ID = a finish from the specification/sources; texture from the
  library (`library/materials/`), an existing diffuse, or a newly generated diffuse that is added to the
  library, then laid onto the atlas (`dt derive atlas`, the atlas half of `agr vpm-to-npm`).
- **Packaging (step 6).** VPM: `agr package-vpm`. NPM: `agr package-npm` (#1361).
- **Roof and openings (steps 3–4).** Roof inside a parapet per [R6](../docs/procedure/node-r6-oks-body-facade.md)
  step 4; windows per [R4](../docs/procedure/node-r4-window-glazing.md) step 1 (library window with a
  small inset if one fits, else the window generator).

The agent chooses **Blender or Max per step**, from the available toolset and task context,
and states why in one line; neither DCC is the default for every step (#1297).
Use the **Max 2026 quad acceptance view** for quad inspection; confirm version, document,
units and ownership before opening a copy. This does not replace exported-file readback.
Unknown write outcome: reconcile IDs/counts/hashes first,
never retry a write blindly. CLI is the portable entry; an MCP wrapper can dispatch the
same contract later. [#1292](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1292)
batches guarded DCC operations, not source interpretation or acceptance gates.

## Executable milestone 1 [D271]

Discovery (no geometry): `uv run agr --help`, `uv run agr vpm-to-npm --help`.
Arguments after each single-step alias are forwarded unchanged, including `--help`:

| Alias | Existing implementation |
|---|---|
| `agr inspect --manifest JOB.json` | `dt inspect --manifest JOB.json` |
| `agr package-vpm ARGS` | `dt derive package ARGS` |
| `agr validate ARGS` | `python tools/qa/validate_package.py ARGS` (not development-bundle `dt validate`) |
| `agr ground ARGS` | `dt ground v015 ARGS` |
| `agr vpm-to-npm [--blender BLENDER] ATLAS_ARGS --then-npm NPM_ARGS` | `dt derive atlas ATLAS_ARGS`, then `dt derive [--blender BLENDER] npm NPM_ARGS` only on exit 0 |

For an authorized packet: `uv run agr vpm-to-npm --blender BLENDER SPEC NEW_ATLAS --recipe-dir RECIPE --then-npm MASTER SPEC NEW_ATLAS NEW_EXPORT PREFIX`.
`--then-npm` is reserved as the argument-group separator (exactly once); `--blender`
must precede atlas arguments, or set `DT_BLENDER`. Paths are explicit; no inferred
config or job flags, rollback, or second implementation. The facade preserves the caller's cwd;
existing `dt derive` / `dt ground` launch their tools from the repository root. Prefer absolute paths.
If NPM fails after atlas success, the atlas remains; use fresh authorized output paths.
Units, placement, path safety, inputs and job dependencies remain the existing tool's
contract, not new guarantees from this facade. Missing/partial group syntax starts no tool.

`unwrap-atlas`, `delivery-export`, `open-in-max`, `contact-renders`, `brick-seams`
and `ucx` always exit nonzero with today's tool/document pointer, including with `--help`.
PDF discovery stays `dt index-pdf --help`; topology discovery stays `dt qa xview --help`.
No authorization is implied by these examples.

## Worked continuation: KPP1, not a new fabricated run

[STATE.md](../jobs/KPP1/STATE.md) records a VPM/master + NPM pipeline, historical
`make_npm_atlas.py` / `export_npm.py`, and current rerun blockers. A worker first loads
current `TASK.md`, `job.yaml` and exact rerun receipts; the historical v002 is not today's acceptance.
Keep approved R1 geometry, run the approved master through today's NPM atlas/export
path on a new copy, then fresh readback, xView and NPM validator diagnostics.
The `agr vpm-to-npm` alias reuses that chain; `unwrap-atlas` and `delivery-export`
remain pointers, not new automation. No district code/address/coordinates are invented
and deferred Ground is not marked complete.
Historical KPP1 2048 atlas / 4.096 m region / about 97 px/m are **job-specific** config,
not an NPM OKS density rule. KPP1's outstanding human/Max/checker items remain outstanding;
this documentation update performs no DCC call and produces no model.

## Definition of done

For a node: source-matched geometry/materials, exported-file readback and measured applicable
checks, a versioned artifact/path and Artem's visual verdict. For a complete delivery:
all eight TASK_TO_MODEL gates, every mandatory machine/manual check and final checker closed
on the same inputs/parts/exports; only then `passed=true`. Unsupported, missing, review,
not_run and partial results are not passes. Technical QA != user acceptance != publication.
Fail closed on missing inputs/material maps, NaN/inf, aliases among input/output/report/temp,
changed sources and stale receipts. These remain production-tool requirements;
milestone 1 delegates and does not claim those guards already exist in every wrapper.

## Accepted scope and remaining benchmark gate [D271]

The route shape is accepted as the template; VPM/Ground comes later. First `agr`
milestone is aliases over existing commands, not a rewrite. First benchmark is a
repeatable NPM-derivation microbenchmark; the $10 full VPM+NPM target is the second,
gated track. Neither benchmark is run by #1317. An immutable accepted master/source
packet still needs authorization; do not spend the $10 or choose material/joint values.
