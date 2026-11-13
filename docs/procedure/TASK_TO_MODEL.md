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
3. Create or continue `jobs/<ID>/job.yaml` with the [eight gates below](#gates-same-for-every-path);
   a new job starts from a copy of [`jobs/_template/job.yaml`](../../jobs/_template/job.yaml) (walks with exit 1, no errors) [#1310].
   Return to [scenario Step 4](../../.agents/skills/scenario/SKILL.md#step-4--work-the-route) for the cell's
   stage route, recording gate evidence here as work proceeds. No build before user Gate 1 confirmation.

## Check levels

Worker policy [D273], adopted from [#1273 section 4](../research/agent-step-waste-1273.md#4-draft-check-levels).
Record `level: fast | standard | full` at [intake](../agents/task-intake.md#check-level-d273),
selected by the orchestrator/agent; Artem overrides with one word. The agent may escalate with a one-line
reason, never downgrade on its own. Use the highest applicable column; shared tooling or a claim of
`passed=true` means `full`, even inside a job. Checking depth does not waive mandatory gates or
source/permission rules; a small edit/re-export of an accepted model is not a new delivery certificate [D273].

| Level | Typical work | Machine checks | Review and handoff |
|---|---|---|---|
| `fast` | colouring, finish/diffuse swap, small geometry edit described by Artem, re-export of an accepted model | one machine readback (IDs/UV/count, 1-2 calls), plus changed dimensions/map paths as applicable; no pytest | no code review; Artem accepts the picture or opened scene; result path, no commit/PR needed; add a LESSONS.md line for a new preference [D273] |
| `standard` | new node or object for a job: MAF, fence, windows, Ground patch, OKS body; scripts under jobs/ | readback + cell validators on the exported file | one dt-reviewer round on committed job scripts (not on the picture); one PR per job at the end (scripts + manifest), not per node; Artem accepts the picture or opened scene [D273] |
| `full` | regulation code/data, validators, standards/, export tooling, schemas, shared src/ modules; a delivery claiming passed=true | readback + validators + affected tests while working, one full suite per PR (rule 49), probes and receipts | dt-reviewer review + Artem acceptance, separate statuses; one PR per issue; full author receipts for code [D273] |

**Visual evidence [D273].** When Artem is online, open the scene in his DCC version and give the absolute path instead of renders.
Render only for board cards without him. Image limits: `fast`: 1 image (result next to reference);
`standard`: 1 image per item + 1 overview (contact sheet), each item beside its reference.
Extra angles only for a defect Artem named. `full` uses the standard image set plus required regulation
album/sheets. These are limits, not a render quota when the scene is opened [D273].

**Fast stop [D273].** Stop after Artem's «да»; on a second correction on the same point, ask rather than iterate alone.
For full delivery certification continue through the gates below; technical QA, user acceptance and publication stay separate.

## GATES (same for every path)

Record every gate in `jobs/<JOB>/job.yaml`; schema:
[`JobChecklist.schema.json`](../../schemas/JobChecklist.schema.json).
A non-pass gate parked on someone else sets `waits: user | max | visual` (never on `pass`); the walk JSON reports it per gate and counts it under `waits` [#1204].
A not-started gate is just `status: missing` (`note`/`evidence` optional); any other status needs a `note`, `pass` needs evidence. Each `inputs` path appears once: a repeated path (also via `./` or case aliases) fails the inputs gate naming it [#1310].
Fixed dependency order below follows D104/D125: human geometry acceptance precedes
**final SINTEZ**, even though preliminary checker diagnostics may run earlier.

| ID | Completion evidence |
|---|---|
| inputs | Full source inventory with paths and SHA-256; requirement/profile/version, source units, coordinate system and source authority recorded in the job report. Mark synthetic sources. `jobs/<ID>/passport.json` (K1) is required only on the AGR Tools route until a second route exists; other OKS routes record the same facts in `job.yaml` inputs / REPORT [D247]. |
| parts | `parts.json` validates against [PartsList](../../schemas/PartsList.schema.json), via the public `dt_ai.core.models.PartsList` facade; `source_tier`: A = Revit + album, B = structured FBX/SKP + album, C = mesh soup + album, D = drawings-only (DWG/DXF/PDF, no source mesh); source coverage, operation and triangle budget per part, joints and questions; `triangle_budget` is the allocated project budget for NPM/VPM (OKS ≤150 000 per profile [D010/D161]), not the regulatory ceiling; the ceiling stays in budgets/QA [D276]; **user Gate 1 confirmation before build** (D111/D124/D125). A headless agent requests Gate 1 through the existing board channel ([KANBAN](../agents/KANBAN.md), [WORKFLOW](../agents/WORKFLOW.md) step 0): post the questions (with the `parts.json` path, file SHA-256 and `approval_sha256()`) as an issue comment and set the gate to `waits: user`; for build scope move the card to Needs you (`needs_input` naming that comment), but for Gate-1-only scope use the [scoped handoff below](#gate-1-handoff). It builds nothing until the answer. Record the user's answer in `gate1` (`actor/date/scope/note`), `ref` = answering comment URL/card id/`D<n>`, and `parts_sha256` = the proposed content's `approval_sha256()` [#1205, #1309]. Missing/stale binding or missing answer ref fails the walk; an old object-level approval is not transferable. |
| operations | Follow the cell's standard route ([oks-vpm body/windows/roof](../scenarios/oks-vpm.md#route-by-stage), [D250]); alternatives use `path: deviation` below. When using [kernel operations](../../src/dt_ai/ops/), apply them to [parts](../../src/dt_ai/parts/); log operation names and before/after invariant results (D108/D131). Broken invariants roll back; stop and ask. Include additional applicable invariants, including D129, when supported; never silently omit a mandatory check. |
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

## Gate 1 handoff

Use the existing #1205 channel: post an issue comment with the versioned PartsList path,
file SHA-256, approval content hash, questions and proposed choices. Record the request URL
in the job report; keep parts `status: review`, `waits: user` in `job.yaml` while unanswered.

- **Build scope:** move to Needs you / Hermes `needs_input`, naming that comment; resume build only
  after the user's hash-bound answer. Neither a notification nor a code review is approval.
- **Scope ends at Gate 1** (measurement, dry-run or parts-only): post the same request and retain
  `waits: user`, then finish the scoped evidence/report and normal code review handoff: **no needs_input block**
  merely to wait for an answer outside the card's scope. The job remains incomplete (`passed=false`);
  downstream production still waits for the user's answer. Hand off the request URL and PartsList identity.

**Approval identity (#1309).** Compute before requesting Gate 1:

```bash
uv run python -c "from pathlib import Path; from dt_ai.core.models import PartsList; p=PartsList.model_validate_json(Path('jobs/ID/parts.json').read_bytes()); print(p.approval_sha256())"
```

`gate1.parts_sha256` is this content hash, **not the complete file hash** (which would include itself).
It hashes the validated, default-expanded PartsList JSON excluding only `gate1` and `status`, with
sorted keys, compact separators, UTF-8/unescaped Unicode and no NaN/inf; list order matters.
The user's answer must explicitly name/confirm this hash (or the immutable request that names it).
Record that exact hash and answer `ref`; changing any proposed content, including source references,
part budgets, joints or question answers, requires a new request and answer. Resolve questions first,
then request confirmation of the final proposal. Never refresh an approval hash on the user's behalf.
Historical unbound lists remain readable but cannot pass the walker. `job.yaml` evidence and downstream
receipt `parts_sha256` still use SHA-256 of the **complete confirmed file bytes**; re-hash them after
recording approval. Formatting may preserve approval identity but changes file evidence identity.

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
unverified or review evidence. A schema error is reported per field (`gates.<gate>.<field>: <message>`) in
`errors` and in that gate's row (`status: fail`); other gates keep their declared status, none is ready [#1310]. Output must be a **new** file, never an input/alias.
Use repository-relative POSIX evidence paths; copy external receipts into a
versioned job evidence directory when a reproducible walk is needed.

**Customer sources (#1202).** The named asset store is the shared Google Drive folder
`G:/Мой диск/AGR-assets/` (one subfolder per library or object, `library/README.md`);
customer sources are never committed (rule 57). An object's customer sources go to
`G:/Мой диск/AGR-assets/<object>/source/` with a `SHA256SUMS.txt` (#1239; copy, never move,
and hash the originals before and after). Each job keeps a source registry
`jobs/<ID>/sources.json`: an `external-inputs/1` manifest whose `files` rows give the
absolute `path`, `sha256`, `location` (`asset-store` or `named-folder`) and `folder` of
every customer source, wherever it lives today; a row's `kind` is `customer-source` or
`delivered-output`, and `original_path` keeps where a copied file came from. List such a manifest in `inputs` with
`manifest: external-inputs/1`; the walker verifies the manifest itself as repo-relative
evidence, then re-hashes every listed path and reports each row in the inputs gate's
`external_inputs` as `equal`, `mismatch` (an error, the gate fails) or `unreachable`
(not on this machine: not a hash failure, but a `pass` claim drops to `review`).
A malformed, NaN, duplicated-path or undeclared manifest is an error.

**LF only.** `.gitattributes` stores text with `eol=lf`, so a receipt hashed with CRLF on
Windows fails on every fresh checkout (G15). Write receipts and walk output as LF bytes
(`dt_ai.core.io.write_json`, or `open(path, "wb")`/`newline="\n"`); the walker's
`--output` and stdout are LF on every OS.

**Fresh-checkout walk before review.** Walk the pushed PR head from a new worktree, not
your working tree, and attach that output:

```bash
git fetch origin <branch> && git worktree add --detach "$TMPDIR/walk-<branch>" FETCH_HEAD
cd "$TMPDIR/walk-<branch>" && uv run python -m dt_ai.procedure jobs/<JOB>/job.yaml --root . --output "$TMPDIR/walk-fresh.json"
cd - && git worktree remove "$TMPDIR/walk-<branch>"
```

References are
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
