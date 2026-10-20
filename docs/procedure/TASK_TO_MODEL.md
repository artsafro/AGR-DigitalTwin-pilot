# Task -> model: fixed GATES, free PATH

Read this before building or reducing a model. Start with the card, its area sheet,
[decisions](../decisions.md) and unresolved [conflicts](../domain/conflicts.md).
A conflict or unknown source fact is a user question, not a modelling assumption.
Use the matching `.agents/skills/model-*/SKILL.md` and `validate-delivery` skill.

## GATES (same for every path)

Record every gate in `jobs/<JOB>/job.yaml`; schema:
[`JobChecklist.schema.json`](../../schemas/JobChecklist.schema.json).
Fixed dependency order below follows D104/D125: human geometry acceptance precedes
**final SINTEZ**, even though preliminary checker diagnostics may run earlier.

| ID | Completion evidence |
|---|---|
| inputs | Full source inventory with paths and SHA-256; requirement/profile/version, source units, coordinate system and source authority recorded in the job report. Mark synthetic sources. |
| parts | `parts.json` validates against [PartsList](../../schemas/PartsList.schema.json), via `dt_ai.parts.model.PartsList`; source coverage, operation and triangle budget per part, joints and questions; **user Gate 1 confirmation before build** (D111/D124/D125). |
| operations | Apply [kernel operations](../../src/dt_ai/ops/) to [parts](../../src/dt_ai/parts/); log operation names and before/after invariant results (D108/D131). Broken invariants roll back; stop and ask. Include additional applicable invariants, including D129, when supported; never silently omit a mandatory check. |
| budgets | Measured budgets vs cited profile/area/decision limits: master, NPM/VPM, UCX, materials, textures, density. Each measurement names its rule and comparison (`le` inclusive, `lt` exclusive); no inferred limit. |
| export_readback | New versioned export, SHA-256; clean-process readback of **exported file**, checking topology, UV, materials, units/transforms. Working-scene checks alone do not complete this gate. |
| report | Nonempty delivery report: source coverage/discrepancies, files/hashes, commands, measured checks, exceptions/deviations and missing/manual checks. Technical QA, user acceptance and publication remain separate. |
| visual | User decision through the **board review tool** (D119), linked to a versioned review page/sheet and exact export hashes: Face Orientation/back-face counts, album/source overlays, material legend, level sections, deviations (D125). Send a Needs-you card with link/options; notification is not approval. A code reviewer/agent cannot sign for the user. |
| checker | Complete SINTEZ AGR Checker on the same exports after visual acceptance (D104); save raw output and normalized receipt, tool/version/command in the report. Partial checks and `review`/`not_run` are not passes. |

Only all eight completed gates allow `passed=true` for this checklist. This is an
evidence contract, **not** a new geometry checker, user-authentication service or
publication authorization. Producers and the reviewer must verify receipt truth.
Never synthesize a receipt to fill a missing check or a human decision.

## Free PATH and deviation log

The implementation route is free: try another adapter/algorithm, a bounded experiment,
or write a tool. Source authority, permissions and GATES stay fixed. A workaround
cannot waive an invariant, a budget, either human gate or exported-file readback.
A new tool needs tests and the same before/after checks; it becomes shared only through
the capability registration policy in AGENTS.md. No new kernel operations are supplied here.

Set `path: deviation` and append a record **before continuing**:

```yaml
deviations:
  - gate: operations
    what_failed: "operation and exact failure/evidence reference"
    what_was_tried: "alternative, command, parameters and before/after checks"
    new_tool_written: "path + revision + tests, or explicit none"
    result: "measured outcome and evidence reference; remaining gate/question"
```

`path: standard` requires an empty log. Repeated attempts append records; they do
not erase earlier failures. A changed source/export/run invalidates old receipts:
use a new `run_id`, recompute evidence, and re-run downstream gates. Receipt gate
and run IDs, ordered artifact hashes, and file hashes must match the checklist.
Map key order has no meaning; the dependency order above determines readiness.

## Machine walk (read-only, no DCC execution)

```bash
uv run python -m dt_ai.procedure jobs/<JOB>/job.yaml --root . --output tmp/walk-v001.json
```

Exit 0 means all declared gates complete; exit 1 means malformed, missing, failed,
unverified or review evidence. Output must be a **new** file, never an input/alias.
Use repository-relative POSIX evidence paths; copy external receipts/assets into a
versioned job evidence directory when a reproducible walk is needed. References are
SHA-256 verified even for incomplete gates. `evidence_exists` inventories files;
`status` is the checked gate claim; `ready` additionally requires preceding gates.

For pass claims, inputs must equal the full inventory; parts must be confirmed.
Machine receipts (operations/budgets/readback/visual/checker) are JSON or YAML maps
with `gate`, `run_id`, `artifact_sha256` (ordered list). `checks` is a nonempty map
of check IDs to `pass`/`fail`/`review`/`not_run`; all applicable checks must pass.
Operations require `before.<invariant>` and `after.<invariant>` for the four base
kernel invariants and a nonempty `operations` list. Budgets use `measurements` rows
with `value`, `limit`, `comparison`, `rule`. Readback requires `clean_process: true`
and topology/uv/materials/transforms checks. Visual requires face_orientation,
album_overlay, source_overlay, material_legend, sections checks; `actor_role: user`,
actor/date/review_tool/decision_reference, `decision: approved`, scope `project` or
`synthetic_fixture`, and a hashed `sheet` reference. Checker requires
`tool: SINTEZ AGR Checker`, `complete: true` and complete checks.

## Repository dry runs

Walk `jobs/KERNEL-SYNTHETIC/job.yaml` and `jobs/VATUTINO-SITE/job.yaml` with the same
command. [Dry-run evidence](task-to-model-dry-run.md) records both inventories.
Kernel tests are synthetic capability evidence, not a delivered model or invented
user approval. Vatutino's committed reports describe real local artifacts but do
not make absent exports/receipts reproducible here; `ground-parts.json` is not the
PartsList contract. Keep these gaps visible. No real-building run is required.
