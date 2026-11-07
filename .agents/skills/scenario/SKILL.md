---
name: scenario
description: 'Route a production task to its cell (NPM / simplified NPM / VPM x OKS / Ground with MAF and Flora / UCX) and work inside it: card, rules, tools, etalons, minimal contract. Use when: «работаем с НПМ», «делаем ВПМ ОКС», «НПМ флора и МАФ», or a hook names a scenario cell.'
---

# Scenario: work inside a production cell

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
the result.

## Step 4 — Work the route

Follow the card's «Route by stage» table. A stage marked as a skill (`model-ground`, `model-maf`, `model-flora`)
hands over to that skill. A stage marked job scripts, manual or no tool is a known gap: say so in the report and
keep any new code minimal (`docs/backlog.md` for the generalisation). Pilot one piece end to end, show it, then the
rest.

## Step 5 — Check and report

Run the card's checks (validator stages, xView, SINTEZ) on the read-back export (`validate-delivery` skill).
`passed=true` only with every mandatory check and manual gate closed. Done when the report names, per stage, the
route used, the evidence and what stays open.

## Step 6 — Feed the card back

When the work changed what a card says (a new etalon, a tool that now exists, a gap closed, a new decision), update
the card and `scenarios.json` in the same branch; `tests/test_scenario_router.py` checks that every pointer exists.
A `todo` cell that just ran a real job gets its first card written from that job.
