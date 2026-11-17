---
name: scenario
description: 'Route a production task to its cell (NPM / simplified NPM / VPM x OKS / Ground with MAF and Flora / UCX) and work inside it: card, rules, tools, etalons, minimal contract. Use when: «работаем с НПМ», «делаем ВПМ ОКС», «НПМ флора и МАФ», or a hook names a scenario cell.'
---

# Scenario: work inside a production cell

One entry sequence (also used by [TASK_TO_MODEL](../../../docs/procedure/TASK_TO_MODEL.md#entry-one-sequence-from-either-entry-point)):

`docs/scenarios/<cell>.md` -> `jobs/<ID>/TASK.md` / contract questions -> `jobs/<ID>/job.yaml` gates

A **cell** is one product profile times one object class, as in the NTR pipeline map: `oks-vpm`, `oks-npm`,
`oks-npm-lite`, `ground-npm`, `ground-vpm`. MAF and Flora live inside the Ground cells; UCX is VPM only. The table of
cells, triggers and cards is [scenarios.json](../../../docs/scenarios/scenarios.json); each ready cell has a card
`docs/scenarios/<cell>.md` with what to read, the binding rules, the route by stage, etalons, checks, the minimal
contract and the known gaps. The card is a map of pointers; the rules stay in `docs/decisions.md` and `docs/domain/`.

## Step 1 — Name the cell

Take the cell from the hook hint (`Scenario cell ...`) or match the task against `scenarios.json` yourself. With only
a profile or only an object class, ask the user one question (`НПМ, НПМ упрощённый или ВПМ?` /
`ОКС, Ground, МАФ или Флора?`) instead of guessing. Done when one or more cells are named and confirmed by the
task's own words or the user's answer.

## Step 2 — Load the card

Open the card and read its «Read first» list in order, only the items the task touches (a texture-only task skips
the body sheet). A cell with `status: todo` has no card: read its `reads` list from `scenarios.json` and the task
intake. Done when every binding rule row that the task touches is known with its decision id.

## Step 3 — Run the minimal contract

Ask the card's contract questions that the sources leave open, in one batch of at most 5, each with your
recommendation first, per [task-intake](../../../docs/agents/task-intake.md). Write the answers into
`jobs/<ID>/TASK.md` (requirement verbatim, «Не трогать», acceptance, pilot). Done when no open item would change
the result. Then hand over to [TASK_TO_MODEL GATES](../../../docs/procedure/TASK_TO_MODEL.md#gates-same-for-every-path):
create or continue `jobs/<ID>/job.yaml` and track all eight gates there. This is the continuation of this
contract, not a second intake. Do not build before user Gate 1 confirms the PartsList.

## Step 4 — Work the route

Follow the card's «Route by stage» table. A stage marked as a skill (`model-ground`, `model-maf`, `model-flora`)
hands over to that skill. A stage marked job scripts, manual or no tool is a known gap: say so in the report and
keep any new code minimal (`docs/backlog.md` for the generalisation). Pilot one piece end to end, show it, then the
rest.

### Body stage: clean body grid (#1618)

For the OKS `body` stage follow [body-modelling.md](../../../docs/research/body-modelling.md#5-правила) (rules
BM-01..BM-14, measured on Artem's G22 etalon): 1) body from the floor-plan outline, vertices only at breaks and
opening/zone lines; 2) loops only where a line has a reason (opening sill/head, finish zone, band), vertical rings
through the whole floor module, rounded corners by radius (chord sagitta <= 2 cm, then snap to the texture
step [D337]), never Revit tessellation;
3) inset, never weld, windows/roof/flashings/posts/decor with projection [D336]; posts are geometry by default,
panels are texture with a seam, no diagonal across a typical facade; edges only on finish-zone borders and window
lines: the ~0.6 m panel step and an extra loop above windows are texture; dark/light cladding (from the source
materials) get separate material IDs with a vertical at their joint [D340];
4) build and check ONE floor module with IDs and UV, then replicate it; 5) measure the master (typical-facade quad
share, slivers, n-gons, module repeat; `tools/qa/body_layout.py`, `tools/qa/master_topology.py`) and show a
wire + texture sheet of the module and one corner before replicating; 6) unique ground floor, top and roof last,
within the triangle budget [D010]. Typical-facade thresholds: quads >= 95 %, slivers <= 0.5 % [D338],
WARN-only (OBSERVE) for the first week; no blocking gate is enabled by this decision.

## Step 5 — Check and report

Run the card's checks (validator stages, xView, SINTEZ) on the read-back export (`validate-delivery` skill).
`passed=true` only with every mandatory check and manual gate closed. Done when the report names, per stage, the
route used, the evidence and what stays open.

OKS cells (`oks-vpm`, `oks-npm`): model by the OKS modelling split [D336] (inset elements vs texture parts,
plinth per project; list in docs/agents/SKELETONS.md, section "OKS modelling split [D336]") and write its
`Modelling split [D336]:` line with the reason in the job report.

Before showing Artem (cells `oks-vpm`, `ground-npm`, `ground-vpm`): run the skeleton `verifier` stage in observe
mode (`tools/qa/verifier.py` → `jobs/<ID>/verifier.json`, docs/agents/SKELETONS.md) and name its main discrepancy in
the report. The VLM confirms; positions/counts come from geometry/vectors (CrossProjection: 82 % view matching vs
22 % line localisation): rib, seam and opening positions and counts are read from the model and the DXF.

## Step 6 — Feed the card back

When the work changed what a card says (a new etalon, a tool that now exists, a gap closed, a new decision), update
the card and `scenarios.json` in the same branch; `tests/test_scenario_router.py` checks that every pointer exists.
A `todo` cell that just ran a real job gets its first card written from that job.
