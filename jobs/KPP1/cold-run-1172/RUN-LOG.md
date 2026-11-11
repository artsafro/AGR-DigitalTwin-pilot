# KPP1 cold-agent run — issue #1172, run `issue-1172-cold-run-v001`

Agent: dt-worker (Hermes Kanban card t_0b1dbdbf), fresh session, 2026-11-10. Inputs: the repository at
`origin/main` 1f76e806 and the machine's file system. No chat history; the only task text was the card
(object KPP1, real АС.03 drawings, mapping #967, `plan_from_dxf` #989; Max busy -> offline only).
Checklist: `jobs/KPP1/job.yaml`; machine walk: `jobs/KPP1/cold-run-1172/walk-v002.json`.

## Result in one line

The run stops at **Gate 1 (parts, user)**: inputs and a validated draft PartsList are done with receipts,
the six later gates are `missing` (waits-user, then waits-max). `passed=false`, walker exit 1. That is the
correct outcome under TASK_TO_MODEL (D111/D124/D125: no build before Gate 1), not a failure of the run.
The real output is the gap list below (15 items, 8 proposed follow-up issues).

## Entry path and tokens

Estimate = characters / 4 (Cyrillic-heavy files read heavier); counted on the files as read.

| Step | File | chars | ~tokens |
|---|---|---:|---:|
| 1 | `AGENTS.md` (also injected as project context) | 5 953 | 1 500 |
| 2 | `docs/PROJECT_STATE.md` | 4 586 | 1 150 |
| 3 | `docs/procedure/TASK_TO_MODEL.md` (linked from AGENTS.md "Modelling or reducing a model") | 9 492 | 2 400 |
| 4 | `.agents/skills/scenario/SKILL.md` (AGENTS.md "Production task") | 3 058 | 750 |
| 5 | `docs/scenarios/oks-vpm.md` (cell `oks-vpm`; `oks-npm` is `todo`, no card) | 4 699 | 1 200 |
| 6 | `jobs/KPP1/STATE.md` | 17 740 | 4 450 |
| 7 | `docs/methods/building-body/kpp1-drawing/mapping-questions.md` (+ VARIANTS.md lines 14-30) | 6 198 | 1 550 |
| 8 | `schemas/JobChecklist.schema.json`, `schemas/PartsList.schema.json` (read via `python -c`, partial) | 16 308 | 4 100 |
| | **Entry to "I know what to do"** (1-3) | 20 031 | **~5 000** |
| | **Everything read before the first artifact** (1-8) | 68 034 | **~17 000** |

## Gates

| Gate | Status | Receipt | Why / what is missing |
|---|---|---|---|
| inputs | **review** | `cold-run-1172/inputs-manifest.json`, `jobs/KPP1/object.json`, `kpp1-drawing/plan-contours.json`, `cold-run-1172/plan-repro-v001.json` (all SHA-256 verified by the walker) | Inventory complete: 3 АС.03 DWGs (SHA-256 equal to `sheet-census.json`, 3/3), album pptx on the asset store, object.json. Units mm ($INSUNITS 4), frame of object.json, requirement BODY-F. Open: source authority above the entrance frames (question 1), profile (question 3); DWGs not on the asset store (G2). |
| parts | **review** | `cold-run-1172/parts-v001.json`, validated by `dt_ai.core.models.PartsList`: `OK draft 8 145000 960000` | 8 parts, NPM 145 000 / 150 000, VPM 960 000 / 1 000 000 (BODY-F). Gate 1 not given: 5 questions (4 user, 1 architect). Two validator rejections on the way (to_texture part with triangles; `pdf` source without `page`) — fixed, see LESSONS. |
| operations | missing — **waits-user**, then **waits-max** | none | No build before Gate 1. The cell route for body / windows / roof is AGR Tools stages 1-4 in 3ds Max (busy). The offline kernel route exists (`dt_ai.ops`, VARIANTS R14 kernel-prisms on the same contour) but is not the cell's standard path (G8). |
| budgets | missing | none | Needs a built master. |
| export_readback | missing — **waits-max** | none | Export is Max [D212] on the cell route; `tools/blender/fbx_readback.py` is ready for the read-back. |
| report | **review** | this file | A run log, not a delivery report. |
| visual | missing — **waits-user** | none | Board review tool (D119) on a versioned sheet; nothing built to show. |
| checker | missing — **waits-visual** | none | SINTEZ after visual acceptance (D104). |

Walk: `uv run python -m dt_ai.procedure jobs/KPP1/job.yaml --root . --output jobs/KPP1/cold-run-1172/walk-v002.json`
-> exit 1, `passed: false`, 0 errors, every evidence `verified: true`, every gate `ready: false`.
A first walk with the DWGs listed directly in `inputs` failed with
`evidence paths must be repository-relative POSIX paths` and wrote no output (G3).
`walk-v001.json` was withdrawn: a walk of the committed tree in a fresh worktree failed with
`hash mismatch: jobs/KPP1/cold-run-1172/plan-repro-v001.json` — the receipt was written with CRLF on Windows and
`.gitattributes` (`eol=lf`) normalised it on commit. All job files are now LF and `walk-v002.json` was produced
after the fix; the fresh-worktree walk gives the same result (G15).

### Offline work actually executed (receipts)

1. **Source location.** `G:/Мой диск/AGR-assets/tec26` holds `album/TEC26_na_RR_1.pptx` and `ac08/` only.
   The DWGs were found in `C:/Users/artsafro/Downloads` (`find`, 3 files) and in
   `Desktop/!3D viz/.../22Е56-АР2-1002-АС.03 (Центральная проходная)` (the `.pln` plot file and a ГГЭ folder).
   The #967 DXF readback `C:/x/methods/building-body/kpp1/readback/` no longer exists.
2. **DWG -> DXF readback** (headless, not Max): AutoCAD 2025 `accoreconsole.exe /i <copy of L03.dwg> /s <script>`,
   script `_.DXFOUT <path> _V _2018 16`; copy SHA-256 = source SHA-256; DXF 3 355 525 bytes.
3. **Plan contour reproduction**: `plan_from_dxf.py extract ... --contour-source hatch` with the 28-entry layer map
   rebuilt from the entity reasons in `plan-account.json` (`cold-run-1172/layer-map-L03.txt`). Receipt
   `plan-repro-v001.json`: `bands`, `coverage` (99.23 %, bbox delta 0.064 m), `levels_m`, `params`, `origin_mm`,
   `frame_shift_m` equal; `plan-account.json` equal (2 005 entities); `method`, `opening_decision`, `source`
   differ (hand-written in the committed file; the tool writes "plan wall lines" even for `--contour-source hatch`).
4. **PartsList draft** validated through the public facade (command in the parts row above).

## Procedure gaps (the real output)

| # | Where | What was unclear or wrong | Proposed follow-up |
|---|---|---|---|
| G1 | AGENTS.md -> TASK_TO_MODEL / scenario skill | Two entry procedures with no cross-reference: the scenario skill (cell, TASK.md, contract questions, route) never names `job.yaml` or the eight gates; TASK_TO_MODEL never names the cell card, `TASK.md` or the passport. A cold agent must merge them itself. | F1 |
| G2 | "named asset store" | Not defined in AGENTS.md; only `agr-tools-1.0-rules.md` names `G:\Мой диск\AGR-assets\<lib>\` (libraries). The АС.03 DWGs are not there and no repo file says where they are (`sheet-census.json` gives the file names, not the folder). The #967 readback in `C:/x` was deleted. | F2 |
| G3 | TASK_TO_MODEL "Machine walk"; rule 57 | The walker accepts only repo-relative evidence, the procedure says "copy external assets into a job evidence directory", rule 57 says binaries go to Drive, not git. A real customer source therefore cannot be in `inputs` directly; this run used an in-repo manifest as a proxy, so the walker verifies the manifest, not the DWGs. | F2 |
| G4 | `kpp1-drawing/plan-contours.json`, `plan_from_dxf.py` | The committed contour is not reproducible from a recorded command: the `--map` arguments, origin and shift are nowhere in one line; the DWG->DXF step has no committed script; three fields were edited by hand; the tool's `method` string ignores `--contour-source hatch`. | F3 |
| G5 | `JobChecklist.schema.json` | Gate status is `pass/fail/review/missing`; there is no way to say "waits-max" / "waits-user" except a note. The card's `waits-max` marker is free text the walker cannot count. | F4 |
| G6 | TASK_TO_MODEL `parts` row | "User Gate 1 confirmation before build" has no channel for a headless agent (the board review tool is named only for `visual`), and the `gate1` Approval (`actor/date/scope/note`) has no field for the card or decision reference that proves it. | F5 |
| G7 | `PartsList` `SourceRef.kind` | No `dwg`/`drawing` value; `pdf` requires `page`; DWG sources are typed `model` by precedent (`jobs/COD-20207/parts.json`). | F6 |
| G8 | Cell `oks-vpm` route vs TASK_TO_MODEL `operations` | The cell says body / windows / roof = AGR Tools stages 1-4 in Max; TASK_TO_MODEL says "apply kernel operations"; VARIANTS has an offline kernel-prisms row on this very contour. Which one is the standard path (and which is `path: deviation`) is not stated. With Max busy this decides whether any offline progress is legal after Gate 1. | F1 |
| G9 | Profile | The card names no profile. The cell router has `oks-npm` as `todo` (no card); KPP1 STATE scope is VPM + NPM (2026-10-07). The scenario skill says "ask"; the question went to Gate 1. | — (asked) |
| G10 | Passport | `agr-tools-1.0-rules.md` makes `jobs/<ID>/passport.json` mandatory (К1); KPP1 has none, and neither TASK_TO_MODEL nor the cell card says whether it applies outside the AGR Tools route. | F7 |
| G11 | `jobs/KPP1/STATE.md` | 251 lines of history (v002-v007, specs); a cold agent cannot tell whether this run continues v007 (Revit source, unaccepted) or starts from АС.03. No "current run / start here" line. | F8 |
| G12 | TASK_TO_MODEL last line | "No real-building run is required" is stale now that this card requires one. | F1 |
| G13 | Per-part triangle budgets | Only the per-FBX total is a rule (BODY-F); per-part numbers are the agent's proposal, so they became a Gate 1 question. | — (asked) |
| G14 | Plan contour bands | `plan_from_dxf` copies one plan into every band; the L03 hatch carries the 0.70 m entrance-frame bumps, so the L1 band would carry them up to 7.909 m while Revit L1 is a plain rectangle. Not in mapping-questions; found by this run. | — (asked, question 1) |
| G15 | TASK_TO_MODEL "Machine walk" | Hashes are of working-tree bytes, but `.gitattributes` normalises text to LF on commit; a receipt written with CRLF on Windows passes locally and fails on every fresh checkout. The procedure does not say "write LF" or "walk a fresh checkout before review". | F2 |

## Proposed follow-up issues (orchestrator files them)

- **F1** TASK_TO_MODEL <-> scenario skill: one entry sequence (cell -> TASK.md -> job.yaml gates), the standard
  body route per cell (Max AGR Tools vs offline kernel) and drop the stale "no real-building run" line (G1, G8, G12).
- **F2** Source registry for real jobs: where each job's customer sources live (asset store path or a named
  folder) plus walker support for an external-input manifest that re-hashes reachable paths; LF-only receipts
  and a fresh-checkout walk before review (G2, G3, G15).
- **F3** `plan_from_dxf`: write the full command (map, origin, shift) into the output, fix `method` for
  `hatch`, and a committed DWG->DXF readback script (accoreconsole DXFOUT) (G4).
- **F4** JobChecklist: an explicit wait status or a `waits` field (`user`/`max`/`visual`) that the walker reports (G5).
- **F5** Gate 1 channel for headless agents: how to request it (Needs-you card / kanban block) and an Approval
  reference field (G6).
- **F6** PartsList `SourceRef.kind`: add `drawing` (DWG/DXF with sheet, no page) (G7).
- **F7** Passport scope: is `passport.json` (К1) required for every OKS job or only the AGR Tools route (G10).
- **F8** `jobs/<ID>/STATE.md` header: a three-line "current run / source / next gate" block (G11).

## Not done, and why

- No geometry built, exported or checked: Gate 1 is not given (procedure), and the cell route is Max (busy).
- No `TASK.md` and no `passport.json` written: both need the user's contract answers (G9, G10).
- No change to shared code or procedure docs: this card records the gaps; the fixes are F1-F8.

## Re-walk after F2 (#1202)

`job.yaml` now declares `inputs-manifest.json` with `manifest: external-inputs/1`; the source registry is
`jobs/KPP1/sources.json`. Walk of a fresh worktree of the PR head (commit 5f1b86ae):
`git worktree add --detach C:/x/ev_t_e8e7dd29/fresh FETCH_HEAD`, then
`uv run python -m dt_ai.procedure jobs/KPP1/job.yaml --root . --output C:/x/ev_t_e8e7dd29/walk-fresh.json`
-> exit 1, `passed=false`; `walk-v003.json` (LF, byte-equal to the working-tree walk). Inputs gate `review`,
0 errors, external rows 4/4 `equal` (3 АС.03 DWGs in Downloads, album pptx on the asset store), 0 unreachable;
parts `review` (Gate 1 open), later gates missing as before.
