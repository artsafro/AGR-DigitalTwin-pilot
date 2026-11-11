# Task -> model: fixed GATES, free PATH

Read this before building or reducing a model. Start with the card, its area sheet,
[decisions](../decisions.md) and unresolved [conflicts](../domain/conflicts.md).
A conflict or unknown source fact is a user question, not a modelling assumption.
Use the matching `.agents/skills/model-*/SKILL.md` and `validate-delivery` skill.

## Entry (one sequence, from either entry point)

`docs/scenarios/<cell>.md` -> `jobs/<ID>/TASK.md` / contract questions -> `jobs/<ID>/job.yaml` gates

1. Name the cell via the [scenario skill](../../.agents/skills/scenario/SKILL.md#step-1--name-the-cell)
   and load its card and applicable area rules. A `todo` cell has no card: use its `reads` in
   [scenarios.json](../scenarios/scenarios.json), and ask rather than invent its route.
2. Hand over to [scenario Step 3](../../.agents/skills/scenario/SKILL.md#step-3--run-the-minimal-contract):
   resolve the contract questions and record the answers in `jobs/<ID>/TASK.md`.
   Reuse existing confirmed answers; an open question that changes the result stops the dependent work.
3. Create or continue `jobs/<ID>/job.yaml` with the [eight gates below](#gates-same-for-every-path).
   Return to [scenario Step 4](../../.agents/skills/scenario/SKILL.md#step-4--work-the-route) for the cell's
   stage route, recording gate evidence here as work proceeds. No build before user Gate 1 confirmation.

## GATES (same for every path)

Record every gate in `jobs/<JOB>/job.yaml`; schema:
[`JobChecklist.schema.json`](../../schemas/JobChecklist.schema.json).
Fixed dependency order below follows D104/D125: human geometry acceptance precedes
**final SINTEZ**, even though preliminary checker diagnostics may run earlier.

| ID | Completion evidence |
|---|---|
| inputs | Full source inventory with paths and SHA-256; requirement/profile/version, source units, coordinate system and source authority recorded in the job report. Mark synthetic sources. `jobs/<ID>/passport.json` (K1) is required only on the AGR Tools route until a second route exists; other OKS routes record the same facts in `job.yaml` inputs / REPORT [D247]. |
| parts | `parts.json` validates against [PartsList](../../schemas/PartsList.schema.json), via the public `dt_ai.core.models.PartsList` facade; source coverage, operation and triangle budget per part, joints and questions; **user Gate 1 confirmation before build** (D111/D124/D125). |
| operations | Follow the cell's standard route ([oks-vpm body/windows/roof](../scenarios/oks-vpm.md#route-by-stage), [D248]); alternatives use `path: deviation` below. When using [kernel operations](../../src/dt_ai/ops/), apply them to [parts](../../src/dt_ai/parts/); log operation names and before/after invariant results (D108/D131). Broken invariants roll back; stop and ask. Include additional applicable invariants, including D129, when supported; never silently omit a mandatory check. |
| budgets | Measured budgets vs cited profile/area/decision limits: master, NPM/VPM, UCX, materials, textures, density. Each measurement names its rule and comparison (`le` inclusive, `lt` exclusive); no inferred limit. |
| export_readback | New versioned export, SHA-256; clean-process readback of **exported file**, checking topology, UV, materials, units/transforms. Working-scene checks alone do not complete this gate. |
| report | Nonempty delivery report: source coverage/discrepancies, files/hashes, commands, measured checks, exceptions/deviations and missing/manual checks. Technical QA, user acceptance and publication remain separate. `jobs/<ID>/passport.json` (K1) is required only on the AGR Tools route until a second route exists; other OKS routes record the same facts in `job.yaml` inputs / REPORT [D247]. |
| visual | User decision through the **board review tool** (D119), linked to a versioned review page/sheet and exact export hashes: Face Orientation/back-face counts, album/source overlays, material legend, level sections, deviations (D125). Send a Needs-you card with link/options; notification is not approval. A code reviewer/agent cannot sign for the user. |
| checker | Complete SINTEZ AGR Checker on the same exports after visual acceptance (D104); save raw output and normalized receipt, tool/version/command in the report. Partial checks and `review`/`not_run` are not passes. |

Only all eight completed gates allow `passed=true` for this checklist. This is an
evidence contract, **not** a new geometry checker, user-authentication service or
publication authorization. Producers and the reviewer must verify receipt truth.
Never synthesize a receipt to fill a missing check or a human decision.

**Look-finished step (D227, report-only).** After the overlap postcondition, run the look-finished checks (seams, broken edge loops, decor gaps; ELV/skug26 retros) on the export and put every finding into the job report. Per [D227] the step is REPORT-ONLY for now: findings do not block delivery and do not flip `passed`. It becomes blocking only after it has run without false failures on 2-3 already accepted jobs (a later user decision).

**Overlap postcondition of every build / fix step (#527, D152).** After each step that writes geometry
(build, fix, simplify, join) and on the export, run `uv run dt qa xview <file.fbx|.blend|.npz> --out <new report.json>`
(local coordinates, NPM/VPM xView thresholds 2 mm / 5 mm) and keep its report with the step. The step is done
only with **contact pairs = 0** (`totals.overlapping_faces` = 0, the xView Overlapping Faces selection) before
export; vertex pairs, `area` pairs and bow-tie findings are fixed or listed as deviations with the user's decision.
Exit 1 = overlaps found, exit 2 = no verdict (bad input); neither is a pass. A job-local overlap script does not
replace it (review #514: a local check said 0 where xView said 185).

## Free PATH and deviation log

The implementation route is free: try another adapter/algorithm, a bounded experiment,
or write a tool. Source authority, permissions and GATES stay fixed. A workaround
cannot waive an invariant, a budget, either human gate or exported-file readback.
A successful deviation proposes a playbook extension; it does not change policy automatically.
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
and run IDs, ordered input paths/hashes, confirmed PartsList hash, ordered artifact
hashes, and file hashes must match the checklist, even if `run_id` was not changed.
Map key order has no meaning; the dependency order above determines readiness.

## Machine walk (read-only, no DCC execution)

```bash
uv run python -m dt_ai.procedure jobs/<JOB>/job.yaml --root . --output tmp/walk-v001.json
```

Exit 0 means all declared gates complete; exit 1 means malformed, missing, failed,
unverified or review evidence. Output must be a **new** file, never an input/alias.
Use repository-relative POSIX evidence paths; copy external receipts/assets into a
versioned job evidence directory when a reproducible walk is needed. References are
SHA-256 verified even for incomplete gates. Source-code evidence (`.py`, `.cs`,
`.ps1`, `.ms`, `.js`, `.ts`) is pinned to an immutable revision with a full-object-id
`commit` (#387): its `sha256` is checked against the blob at that commit, so later
working-tree edits never invalidate the recorded evidence. The pin is honored only for source
evidence: the `inputs` inventory (any path), or a supplementary source-suffixed reference in the
`parts`/`operations` roles. The primary parsed contract of a `pass` `parts` gate (the PartsList)
and the primary receipt of a `pass` `operations` gate are generated semantic roles and always
reject `commit`, regardless of suffix. Generated artifacts, receipts, parts,
reports and visual sheets always keep their working-tree `sha256` and reject a `commit`
(by role as well as by suffix, so a generated file cannot evade the check with a
source-like name); editing any of them still errors. `evidence_exists`
inventories files; `status` is the checked gate claim; `ready` additionally requires
preceding gates.

For pass claims, inputs must equal the full inventory; parts must be confirmed.
Machine receipts (operations/budgets/readback/visual/checker) are JSON or YAML maps
with `gate`, `run_id`, `artifact_sha256` (ordered list), `input_evidence` (the exact
ordered `inputs` list of `{path, sha256}`), and `parts_sha256` (the SHA-256 of the
first parts evidence file, validated as the confirmed PartsList at the parts gate).
Changing input bytes, inventory paths/order or confirmed parts invalidates every
machine receipt; real producers must rerun checks and obtain fresh approvals, not
just rewrite receipt hashes. `checks` is a nonempty map
of check IDs to `pass`/`fail`/`review`/`not_run`; all applicable checks must pass.
Operations require `before.<invariant>` and `after.<invariant>` for all six mandatory
invariants (open_borders_hidden, no_see_through_hole, no_visible_back_faces,
no_close_overlap, quad_dominance, texel_ready) and a nonempty `operations` list.
Missing producers for D129 leave the gate incomplete, not waived. Budgets use `measurements` rows
with `value`, `limit`, `comparison`, `rule`. Budgets may omit `checks` when only
measurements apply; if declared, it must be a nonempty map of nonblank string IDs
to `pass` (no ignored failed, review, not_run or malformed checks).
Readback requires `clean_process: true`
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
PartsList contract. Keep these gaps visible. The real-building [KPP1 cold run](../../jobs/KPP1/cold-run-1172/RUN-LOG.md)
(#1172 / PR #1173) records its Gate 1 stop and procedure gaps, not delivery acceptance;
use its receipts and the current job state when continuing a real-building task.
