# KPP1 cold-agent run #2 — issue #1279, run `issue-1279-cold-run-v001`

Measurement, not a fix session. Repository at `origin/main` `b5581d02` (after F1-F8, #1201-#1208).
Agent: Hermes `dt-worker` (claude-opus), headless Kanban card `t_d6dcad2e`, fresh context. Read: the repository,
its docs and skills, the KPP1 sources (copies) and the first cold run (`cold-run-1172/RUN-LOG.md`, read **after**
the walk, for the comparison only). Not read: `jobs/KPP1/rerun-*` (only their directory names were seen in `ls`
and in the text of `jobs/KPP1/job.yaml`, `STATE.md` and `docs/decisions.md`, see F19).

## Result in one line

Stops at **Gate 1 (parts, user)** as the procedure requires: `inputs` **pass** (sources.json re-hashed, 4/4
`equal`), draft PartsList validated (9 parts, VPM 29 200 / 150 000), six later gates `missing`; walker exit 1,
`passed: false`, `waits: {user: 1}`. **5 min 56 s and 43 tool calls** from the card to the Gate 1 walk
(first run: not timed; ~17 000 tokens of reading before the first artifact). 12 new findings F9-F20 below;
F1-F8 of the first run: 6 gone, 2 partly (F3, F8).

## Run log per stage

Times are file mtimes and `date` stamps on this PC (no estimates); calls = tool calls of this session,
including failed ones. Renders and image views: 0 in every stage (nothing is built before Gate 1).

| Stage | From - to | Wall | Calls | Failed / retried calls | Result |
|---|---|---:|---:|---|---|
| S0 orient: card, `TASK_TO_MODEL.md` (AGENTS.md, PROJECT_STATE injected) | 17:40:20 - | | 5 | 0 | entry sequence and eight gates known |
| S1 cell + contract: scenario skill, `oks-vpm.md`, `scenarios.json`, `jobs/KPP1/job.yaml`, `questions.md`, decisions, source-intake skill, asset store | - 17:42:01 | 1 min 41 s (S0+S1) | 12 | 0; 1 call wasted on `questions.md` (F13) | cell `oks-vpm`; contract answers found in D238/D249/D254/D262, no `TASK.md` |
| S2 sources: copy 3 DWGs from `G:/Мой диск/AGR-assets/KPP1/source/` to `C:/x/cr1279/source`, `dwg_to_dxf.py` x3 | 17:42:01 - 17:42:34 | 33 s | 4 | 1 (`/usr/bin/time` missing in git-bash) | 3/3 readback `pass`, copies = sources (SHA-256), DXF 11.4 / 9.1 / 3.4 MB, 18 s AutoCAD |
| S3 plan contour: find the route, `plan_from_dxf.py extract` (map, origin, shift from `REPRODUCE.md`) | - 17:43:05 | 31 s | 4 | 0 | exit 0, 2 bands, hatch coverage `pass` 0.992, bbox delta 0.064 m, unaccounted 0.0 m2 |
| S4 PartsList: schema, tiers, opening tools, L01/L03 layer census (ezdxf), budgets, write + validate | - 17:45:02 | 1 min 57 s | 11 | 2 (`execute_code` refused headless; validator: `build_as` only with `primitive`) | `parts-v001.json` valid, 9 parts, 4 questions |
| S5 `job.yaml` + walk | - 17:46:16 | 1 min 14 s | 7 | 2 (walk: not-started gates need `note` + `evidence`, F17; one report print error) | walk-v002: exit 1, inputs `pass` ready, parts `review` waits user |
| **Card -> Gate 1 walk** | 17:40:20 - 17:46:16 | **5 min 56 s** | **43** | **5 (12 %)** | Gate 1 stop |
| S6 comparison with run 1, F1-F8 checks, #1273 numbers, finding checks | - 17:48:49 | 2 min 33 s | 15 | 0 | table below |

Comparison with #1273 (PR #1277, board production cards, author runs only): median card 238 calls, 18 test
runs, 2 full suites, 2.48 h; the KPP1 cards #1209 402 calls / 3.05 h, #1230 238 / 1.31 h, #1244 171 / 2.54 h,
#1255 438 / 2.65 h. This run reached its stop point with 43 calls, 0 test runs, 0 renders and 12 % failed calls
(#1273 overall waste 8.5 %, failed 3.0 %): the pre-Gate-1 path is cheap now; all failed calls here are tooling
friction (shell, schema), not procedure guesses. The guesses are the findings below; each cost 0-2 calls but
leaves a wrong or arbitrary value in the PartsList that Gate 1 has to catch.

## Gates (walk `C:/x/cr1279/walk-v002.json`)

| Gate | Status | Evidence | Note |
|---|---|---|---|
| inputs | **pass**, ready | `jobs/KPP1/sources.json` (`external-inputs/1`, 4 rows `equal`, 0 unreachable), `dxf-readback-L0{1,2,3}.json`, `plan-contours-v001.json` | units mm, placement [D262], levels [D254] |
| parts | **review**, `waits: user` | `parts-v001.json` sha256 `4d36ed15…fb32` | Gate 1 requested on the issue (#1205 channel), 4 questions |
| operations … checker | missing | — | no build before Gate 1 |

Command: `uv run python -m dt_ai.procedure jobs/KPP1/cold-run-1279/job.yaml --root . --output C:/x/cr1279/walk-v002.json`.
All six committed files are LF (0 CR bytes).

## F1-F8 of the first cold run: what is really gone

| # | First run (G-items) | Now | Evidence from this run |
|---|---|---|---|
| F1 | two entry procedures, no standard body route, stale "no real-building run" line (G1, G8, G12) | **gone** | `TASK_TO_MODEL.md` "Entry" and scenario skill Step 3 name the same sequence; `oks-vpm.md` names the standard route and the deviation [D250]; the last line now points at the cold run |
| F2 | no source registry, walker cannot verify customer sources, CRLF receipts (G2, G3, G15) | **gone** | `jobs/KPP1/sources.json` + `G:/.../KPP1/source/SHA256SUMS.txt`; the walker re-hashed 4/4 rows `equal`; the procedure says LF and fresh-checkout walk |
| F3 | contour not reproducible, no DWG->DXF script, `method` wrong for hatch (G4) | **partly** | `dwg_to_dxf.py` 3/3 pass; `plan_from_dxf` writes `invocation` and `method` "plan wall hatch union"; but `REPRODUCE.md` still points at `Downloads` and the map/frame only exist for this one sheet (F15) |
| F4 | no wait status (G5) | **gone** | `waits: user` accepted, walk counts `waits.user = 1` |
| F5 | no Gate 1 channel for a headless agent, no reference field (G6) | **gone** (one edge open, F18) | `TASK_TO_MODEL` parts row names the channel; `Approval.ref` exists |
| F6 | no `drawing` source kind (G7) | **gone** | `SourceRef.kind: drawing` with `sheet`, validated |
| F7 | passport scope (G10) | **gone** | [D247] in `TASK_TO_MODEL` and `oks-vpm.md` |
| F8 | `STATE.md` without a "current run" header (G11) | **partly** | the 3-line header exists but is stale (F19) |

## New findings (F9-F19)

Same format as the first run: where, what was unclear/missing/wrong, what it cost, what should change.

| # | Stage | Where | What was unclear or wrong | Cost | Doc/code that should change |
|---|---|---|---|---|---|
| F9 | S4 | `PartsList.source_tier` (`src/dt_ai/parts/model.py` `SourceTier`, schema) | Tiers are A Revit+album, B FBX/SKP+album, C mesh soup+album [Q29a]; a 2D-drawings-only source (DWG sheets) fits none and no doc explains the tiers. Recorded `C` as a guess and a Gate 1 question. | 2 calls; a guessed value in the contract | `SourceTier` + its doc in `TASK_TO_MODEL` parts row: a drawings-only tier or the rule which tier a DWG set is |
| F10 | S4 | `TASK_TO_MODEL` parts row, `oks-vpm.md` Budget row, [D161]/BODY-F | Which number is the PartsList `triangle_budget`: the project target 150 000 [D161] or the regulation ceiling 1 000 000 (BODY-F)? Run 1 wrote VPM 960 000, run 2 wrote 150 000 from the same docs. | 1 call; two cold agents disagree | one sentence in the parts row: "PartsList `triangle_budget` = project target [D161]; the ceiling is the budgets-gate limit" (or the opposite, user decision) |
| F11 | S4 | `TASK_TO_MODEL` parts row, `Approval` | Does an existing Gate 1 answer ([D238] = cold-run-1172 `parts-v001.json`) cover a new PartsList of the same object (different file and hash)? `Approval` carries no parts SHA-256, so the walker cannot tell which list was approved. | asked as a Gate 1 question | parts row: Gate 1 binds to the PartsList hash; `Approval.parts_sha256` (or the ref must name the file + hash) |
| F12 | S1/S4 | `jobs/KPP1/sources.json` vs [D238]/[D254] | Levels 3.900 / 7.909 and the L1 rectangle are "from Revit" by decision, but the source registry lists only the three DWGs and the album; the Revit file / `object.json` is not an input. A cold agent following the registry has no source row for the levels it must use. | 1 Gate 1 question | `jobs/KPP1/sources.json`: add the Revit row (`data/sources/revit/26_КПП1_АР_МЭП_RVT22.rvt`) or `object.json` as the levels authority |
| F13 | S1 | `jobs/KPP1/` (no `TASK.md`), `questions.md` | Entry step 2 says the contract answers are in `jobs/<ID>/TASK.md`; KPP1 has none. The answers are spread over D238, D249, D254, D256, D262; `questions.md` is an 83-row spec table of an older route (all `gone v021`), which a cold agent reads for nothing. | 1 call, ~11 k chars | `jobs/KPP1/TASK.md` with the contract answers and decision ids (or the procedure says: no TASK.md -> grep decisions for the job id) |
| F14 | S1/S3 | `analyze-architectural-source` skill, `oks-vpm.md` "Source intake", `docs/domain/areas/body.md`, `docs/sources/README.md` | The intake skill is mesh-only (steps 4-6: `classify_source` on a welded mesh, UV, slots); it never names the 2D-drawing route `dwg_to_dxf.py` -> `plan_from_dxf.py` (`census`/`extract`). Found via a CAPABILITIES grep and a `cold run` grep. Step 1 "row in `docs/sources/README.md`": the АС.03 R1 DWGs have no row. | 3 calls of search | skill: a "2D drawing (DWG/DXF)" branch linking the two tools and `REPRODUCE.md`; `docs/sources/README.md` row for the АС.03 R1 sheets |
| F15 | S3 | `docs/methods/building-body/kpp1-drawing/REPRODUCE.md` | Source path is still `C:/Users/artsafro/Downloads/...` (moved to the asset store by #1239; `sources.json` is the registry). Origin 25884.5 mm and shift -14.655/-5.355 m are given without the link to `mapping-questions.md` item 6 that derives them; the census -> map step for another sheet is not described. | 0 calls (used as given) | `REPRODUCE.md`: source from `jobs/KPP1/sources.json`, link mapping-questions, one line "new sheet: `plan_from_dxf.py census` -> map -> extract" |
| F16 | S4 | `tools/methods/body/openings.py`, `jobs/KPP1/scripts/extract_openings.py` | No shared tool reads an opening schedule from a facade DXF (L01): `openings.py` only validates a schedule, the job script reads Revit. Windows/doors parts were drafted from layer names (`A-GLAZ-*`, `A-DOOR-*`) only; D238 item 2 ("openings from L01 dimensions") has no tool. | 2 calls | `docs/backlog.md` row / tool: facade-DXF opening schedule (or the cell card's "Known gaps" says so) |
| F17 | S5 | `schemas/JobChecklist.schema.json`, `TASK_TO_MODEL` | No minimal `job.yaml` template; a gate that has not started needs `note` and `evidence: []`. One missing field makes the whole walk report every gate `missing` with one pydantic blob, so the valid `inputs` gate looked failed too. | 1 walk retry | a 15-line template in `TASK_TO_MODEL` (or `dt job init`), and per-gate errors from the walker |
| F18 | S5 | `TASK_TO_MODEL` parts row (#1205 channel) | The channel says "block the card as `needs_input`". For a card whose deliverable stops at Gate 1 (this measurement, a dry run, a parts-only card) blocking stalls the deliverable; not said whether to post + `waits: user` + finish instead. This run posted the Gate 1 comment and did not block. | judgement call | parts row: "a card whose scope ends at Gate 1 posts the request, sets `waits: user` and finishes" |
| F19 | S1 | `jobs/KPP1/STATE.md` header, `jobs/KPP1/job.yaml` | The F8 header says "Current run: #1209 … Source: cold-run-1172/inputs-manifest.json", while D256 (11-12) and D262 cite `rerun-1244` / `site-1255`; `job.yaml` still lists `cold-run-1172/inputs-manifest.json` (not `sources.json`) with the note "DWGs still outside the asset store (cold-run G2)", false since #1239. Nothing checks the header against the newest run. Also the job-level `job.yaml` carries the previous run's route (deviation text), so a cold agent cannot work in it without seeing earlier-run hints. | 0 calls, but wrong orientation | a test or `after_merge` step: STATE header "Current run" names the run dir that `job.yaml` points at; `job.yaml` inputs -> `sources.json` |
| F20 | after S5 (probe) | `src/dt_ai/procedure.py` inputs gate | Probe `probe_walk.py`: listing `jobs/KPP1/sources.json` twice in `inputs` still gives `inputs: pass, ready`, 0 errors (`evidence_exists` 6 rows, the manifest re-hashed twice). The procedure calls a duplicated-path manifest an error, but a duplicated inventory row is not caught. | 0 (found by the fail-closed probe, 4/5 others reject) | walker: a duplicated `inputs` path is an error naming it |

Fail-closed probes (`uv run python jobs/KPP1/cold-run-1279/probe_walk.py . <new dir>`): parts hash off by one
nibble -> hash mismatch; parts `pass` without gate1 -> rejected; `waits` on a pass gate -> rejected; unknown
`waits` value -> rejected; duplicated inputs row -> **accepted** (F20). 4/5 reject.

Minor friction, no issue proposed: the `build_as`-only-with-`primitive` rule is in the validator message, not in
the schema description (1 retry); `execute_code` is refused in a headless session (use a script file).

## Gate 1 request

Posted on issue #1279: https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1279#issuecomment-6830005968 with the `parts-v001.json` path and SHA-256 and the four questions
of the file. Measurement card: not blocked (F18); `parts` gate `waits: user`.
