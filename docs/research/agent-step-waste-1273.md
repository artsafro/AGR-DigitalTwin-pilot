# Agent step waste in finished jobs: check levels and node recipes (draft, #1273)

Status: **research draft**. Nothing here is wired into procedures, skills or D-rows; Artem approves first
(questions at the end). Artem's individual preferences stay in each job's `LESSONS.md`; this file quotes only
patterns seen in 2+ jobs, with the jobs named.

Data: `docs/research/agent-step-waste-1273/` — `measure.py` (read-only, re-runnable),
`data/sessions.csv`, `data/board.csv`, `data/summary.json` (snapshot 2026-11-12; the newest transcripts were
still being written, so a rerun can differ in the 11-12 rows). Rerun:
`python docs/research/agent-step-waste-1273/measure.py --out <dir>` (writes only to `<dir>`).

## 1. What was measured

| Source | Scope | Count |
|---|---|---|
| Claude Code transcripts `~/.claude/projects/C--Users-artsafro*AGR-DigitalTwin*/*.jsonl` | sessions since 2026-10-13 with DCC calls, not harness/audit/letters, fork copies dropped | **28 job sessions** (of 90 transcripts), 5 696 tool calls |
| Board `agr-pilot` `kanban.db` (`tasks`, `task_runs`, `task_events`) + each run's profile `state.db` | newest finished production cards (DCC/job work) | **13 cards**, 87 runs (author + reviewer) |
| `jobs/*/LESSONS.md` (7 files), `docs/retros/*.md` (4), `docs/research/job-retro-*.md` (5) | lessons and retros already written | read, quoted below |
| PR comments under `artsafro` with Russian text (400 newest PRs) | Artem's review remarks | 21 comments; all but two are agent-written (review rounds, polygon reports). Artem's own remarks live in **chat transcripts** and in quoted acceptance lines (#906, #1178), so the remark analysis uses the transcripts. |

Step tags (heuristic, `measure.py` docstring):

- **unused** — the call returned an error (blocked command, missing file, exception);
- **repeated** — an identical call (same tool, same input) already ran; or a render right after a render with no
  edit between (extra angle); or a pytest run with no Edit/Write/DCC call since the previous one;
- **necessary** — the rest.

Limits: shell-side edits (`sed`, a Python writer) are invisible to the test rule, so `test_repeat` is an upper bound;
"unused" counts only failed calls, not successful calls whose output was ignored — the image-episode columns cover
that for renders. Hand check of two episodes (below) agrees with the tags.
Board cards run on external CLIs (Codex/Cursor) show only the driver's calls in Hermes `state.db`.

## 2. Table of measured jobs

### 2.1 Claude Code job sessions (with Artem)

`img ep≥3` = check moments where the agent made/looked at 3+ images with no edit between; `sent` = images sent
to Artem. Wall / active hours: active = sum of gaps ≤ 10 min. Out tok = output tokens (thousands).

| Date | Job (node type) | Calls | DCC | Renders | Image views | Sent | img ep≥3 | Tests | Repeated | Unused | Waste | Wall / active h | Out tok k | Source (`<dir>/<session>`) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 10-13 | OBJ03 decor (MAF) | 26 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 4% | 0.29 / 0.29 | 13 | laughing-hawking / 772bc1b2 |
| 10-15 | PSU275 PZU max file (ground) | 96 | 27 | 5 | 7 | 2 | 2 | 0 | 9 | 7 | 17% | 0.97 / 0.67 | 46 | 3d-max-floor-modeling / c8606406 |
| 10-15 | Blender → Max scene transfer | 45 | 19 | 5 | 2 | 0 | 0 | 0 | 2 | 5 | 16% | 0.97 / 0.29 | 20 | laughing-hawking / 5e0a7e13 |
| 10-20 | vyatskaya-tow02 body (OKS) | 233 | 54 | 0 | 16 | 5 | 0 | 0 | 4 | 9 | 6% | 5.98 / 4.51 | 219 | pilot root / d614e212 |
| 10-20 | vyatskaya-tow02 atlas, review (OKS) | 216 | 45 | 6 | 21 | 5 | 3 | 0 | 7 | 10 | 8% | 22.67 / 3.57 | 194 | pilot root / 3b2419ea |
| 10-21 | vyatskaya-tow02 placement (OKS) | 171 | 8 | 0 | 0 | 0 | 0 | 8 | 6 | 3 | 5% | 2.64 / 2.32 | 137 | pilot root / 1a55b0bc |
| 11-03 | MAF in Blender (library MAF) | 407 | 28 | 17 | 26 | 4 | 5 | 30 | 46 | 9 | 14% | 219.35 / 8.53 | 260 | blender-mafy-modeling / ff97e2f2 |
| 11-04 | Silikatny DWG viz prep (ground colours) | 200 | 14 | 4 | 25 | 5 | 3 | 0 | 6 | 10 | 8% | 26.14 / 1.85 | 146 | dwg-visualization-prep / c5595dd7 |
| 11-04 | Retaining walls diffuse + railing (colouring) | 60 | 34 | 6 | 5 | 0 | 1 | 0 | 1 | 1 | 3% | 0.75 / 0.44 | 34 | support-walls-diffuse-texture / 12607103 |
| 11-04 | ELV «СРЕDА» VPM (OKS) | 452 | 0 | 3 | 33 | 13 | 4 | 20 | 34 | 14 | 11% | 157.43 / 10.27 | 241 | pilot root / 271fa1bc |
| 11-05 | Gates Object001 resize (fence/gates) | 217 | 124 | 9 | 24 | 5 | 1 | 0 | 27 | 2 | 13% | 1.64 / 1.27 | 148 | gates-object-001-resize / b8d40379 |
| 11-05 | Garibaldi NPM → VPM (OKS) | 387 | 137 | 18 | 31 | 4 | 7 | 0 | 25 | 22 | 12% | 3.32 / 3.12 | 281 | garibaldi-npm-vpm-conversion / 86b05944 |
| 11-05 | K5 conditioners VPM 4K texture (colouring) | 199 | 87 | 10 | 12 | 2 | 0 | 3 | 12 | 11 | 12% | 1.45 / 1.45 | 92 | vpm-conditioner-texture-4k / bc045341 |
| 11-05 | Kasatkino ground 1 (ground) | 310 | 13 | 4 | 31 | 9 | 0 | 2 | 2 | 4 | 2% | 3.96 / 2.71 | 261 | kasatkino-ground-mesh / 5de24b46 |
| 11-05 | Kasatkino ground 2 (ground) | 52 | 1 | 0 | 0 | 0 | 0 | 1 | 4 | 2 | 12% | 15.83 / 1.16 | 25 | kasatkino-ground-mesh / b8f2a245 |
| 11-06 | Kasatkino ground 3 (ground) | 276 | 85 | 9 | 31 | 7 | 1 | 0 | 15 | 6 | 8% | 5.03 / 2.52 | 168 | kasatkino-ground-mesh / bdc7c290 |
| 11-06 | Kasatkino ground 4 (ground) | 150 | 80 | 2 | 3 | 1 | 0 | 0 | 12 | 4 | 11% | 32.02 / 0.72 | 82 | kasatkino-ground-mesh / 16b8e6d1 |
| 11-07 | Vertical posts along glass railing (fence) | 179 | 52 | 4 | 9 | 2 | 0 | 0 | 4 | 2 | 3% | 1.05 / 1.05 | 150 | vertical-posts-glass-railing / c7e298dd |
| 11-07 | Max 2026 migration (tooling) | 268 | 53 | 3 | 18 | 7 | 3 | 0 | 10 | 5 | 6% | 12.56 / 2.84 | 168 | max-2026-migration / 800a05ef |
| 11-08 | MaxScript material cleanup 1 (tooling) | 416 | 149 | 4 | 17 | 0 | 1 | 0 | 33 | 8 | 10% | 2.28 / 2.15 | 278 | maxscript-material-cleanup / f9c15b42 |
| 11-08 | MaxScript material cleanup 2 (tooling) | 353 | 86 | 26 | 23 | 0 | 3 | 0 | 6 | 1 | 2% | 1.29 / 1.29 | 210 | maxscript-material-cleanup / cc0be168 |
| 11-09 | Object 009 inner window polygons (window) | 78 | 21 | 1 | 6 | 2 | 1 | 0 | 4 | 6 | 13% | 5.93 / 0.70 | 40 | remove-window-polygons-009 / f53fab83 |
| 11-09 | Kasatkino markup on ground (ground) | 50 | 32 | 0 | 0 | 0 | 0 | 0 | 9 | 3 | 24% | 2.12 / 0.39 | 24 | markup-projection-ground / b8c7ae28 |
| 11-10 | Object009 handrail spline (fence/railing) | 64 | 23 | 6 | 8 | 2 | 2 | 0 | 1 | 3 | 6% | 2.21 / 0.64 | 34 | object009-railing-spline / 94d57781 |
| 11-10 | KG-Grupp bench VPM (library MAF) | 129 | 33 | 9 | 15 | 2 | 3 | 0 | 15 | 7 | 17% | 0.45 / 0.45 | 79 | busy-cori / f305f3dd |
| 11-12 | Staropetrovsky MAF set (library MAF) | 294 | 3 | 2 | 31 | 11 | 5 | 0 | 5 | 8 | 4% | 11.45 / 5.10 | 171 | max-2026-migration / f8d74c21 |
| 11-12 | Butovskaya MAF smoothing groups (library MAF) | 103 | 26 | 1 | 3 | 1 | 1 | 3 | 8 | 3 | 11% | 0.87 / 0.87 | 65 | blender-smoothing-groups / 196a34b0 |
| 11-12 | 4BK corpus K3 (OKS) | 265 | 45 | 6 | 46 | 14 | 6 | 0 | 3 | 7 | 4% | 3.35 / 3.04 | 189 | 4bk-corpus-k3-modeling / d1636320 |
| | **Total / median** | **5 696** / 199.5 | 1 279 | 161 | 443 | 103 | 52 in 18 sessions | 67 | 310 | 173 | **8.5%** / 9.0% | | 3 776 | |

`<dir>` is `C--Users-artsafro--AGR-DigitalTwin-pilot--claude-worktrees-<name>-<hex>` (or the old
`C--Users-artsafro-AGR-DigitalTwin--…` for the 10-13/10-15 rows); "pilot root" = `C--Users-artsafro--AGR-DigitalTwin-pilot`.

### 2.2 Board production cards (author + reviewer runs)

| Card | Task | Runs (author + review) | Review rounds | Changes requested | Calls | Renders | Image views | Test runs | Full suites | Repeated | Error results | Run hours | Out tok k |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t_cd0d8792 | #1255 KPP1 site coordinates, GeoJSON | 5 + 1 | 1 | 0 | 438 | 2 | 6 | 15 | 5 | 9 | 32 | 2.65 | 162 |
| t_dd6f4bf9 | #1244 KPP1 R1 V004 band | 2 + 1 | 1 | 0 | 171 | 0 | 0 | 9 | 2 | 21 | 6 | 2.54 | 60 |
| t_b1946208 | #1230 KPP1 R1 self-intersections, mullions | 4 + 2 | 2 | 1 | 238 | 1 | 0 | 18 | 2 | 0 | 17 | 1.31 | 122 |
| t_d1f84643 | #1209 KPP1 VPM (+NPM) to passed=true | 5 + 1 | 1 | 0 | 402 | 0 | 2 | 32 | 8 | 18 | 31 | 3.05 | 141 |
| t_3ed57b56 | #1178 rework Flora route A visual gate | 2 + 1 | 1 | 0 | 227 | 5 | 12 | 21 | 3 | 11 | 14 | 2.48 | 92 |
| t_c9ff2af1 | #1146 Flora route A steps 3+ | 2 + 1 | 1 | 0 | 197 | 0 | 11 | 15 | 2 | 4 | 6 | 2.62 | 112 |
| t_d9171ddc | #1146 Flora NPM stars, 17 positions | 3 + 2 | 2 | 1 | 260 | 0 | 1 | 24 | 3 | 23 | 13 | 2.04 | 184 |
| t_b10ac4ee | #1046 MAF «Верона» library rows | 4 + 2 | 2 | 1 | 163 | 1 | 0 | 17 | 1 | 1 | 7 | 1.71 | 88 |
| t_f6c68418 | #889 MAF colour zones, 13 positions | 4 + 4 | 2 | 1 | 201 | 2 | 0 | 14 | 4 | 77 | 8 | 4.76 | 64 |
| t_e35c49dd | #371 Ground v015 Vatutino | 2 + 1 | 1 | 0 | 264 | 2 | 1 | 8 | 2 | 9 | 11 | 1.92 | 125 |
| t_96a3cc8a | #790 MAF generator «Верона» | 6 + 2 | 1 | 0 | 329 | 11 | 29 | 27 | 2 | 1 | 8 | 2.56 | 262 |
| t_b4f6c33a | #753 AC08 (TEC26) end to end | 3 + 3 | 3 | 2 | 159 | 0 | 0 | 18 | 2 | 0 | 4 | 1.88 | 100 |
| t_5e2eb833 | #298 Vatutino site slice | 10 + 2 | 2 | 1 | 526 | 3 | 3 | 24 | 3 | 15 | 24 | 3.44 | 211 |
| | **Median** | | 1 | 6 of 13 cards | 238 | | | **18** | **2** | | | 2.48 | |

Source of every row: `agr-pilot` `kanban.db`, task id in column 1; tool calls from the `owner_admitted` session of
each run (`data/board.csv`).

## 3. Top waste patterns (numbers)

| # | Pattern | Numbers | Where (examples) |
|---|---|---|---|
| W1 | **Multi-image check moments.** The agent renders or opens 3+ images with no edit between (several angles, re-reading the same PNG, retrying the capture method). | 52 such moments in **18 of 28** sessions; **247** images beyond the first one per moment; 604 renders + image views in total against **103** images sent to Artem. | Garibaldi 7 moments, 4BK K3 6, MAF Blender 5, Staropetrovsky 5. Hand check: gates b8d40379 07:42–07:43 four captures, two sent; bench f305f3dd 09:58 four capture attempts (one method retry) and `shot_persp_v001.png` read 3×, two images sent. |
| W2 | **DCC instance juggling.** `list_max_instances` / `select_max_instance` / `manage_scene hold` / `max_dialogs` repeated with identical input. | **94** repeated + 15 failed instance calls; `list_max_instances` alone 62 repeats. | Gates (Artem: «макс закрылся дай путь», «дай путь на сцену»), bench, Garibaldi. |
| W3 | **Failed shell / tool calls.** | 173 unused calls: Bash 52 + PowerShell 41 (54%), Blender MCP `get_blendfile_summary_path_info` 21 (fails every time it is called). | Garibaldi 22, СРЕDА 14, conditioners 11. |
| W4 | **Code-style checking on a job.** Tests and review on DCC/data work where the result is a picture Artem accepts. | 67 pytest runs in 7 job sessions, 37 with no edit since the previous run (upper bound); MAF Blender 30, СРЕDА 20. Board production cards: median **18** test runs and **2** full suites per card (KPP1 #1209: 32 and 8), review round median 1, changes requested on 6 of 13. TEC26 colouring retro: «normal mode (tests, full run, review, hashes) for “just paint”» cost **~2–3 h and most tokens**; 80 runs instead of ~7 (`docs/retros/2026-10-22-tec26-colouring-claude.md`, O7, section 3). | |
| W5 | **Repeated plan/status bookkeeping.** `update_plan` with identical input. | 76 repeats (cheap, but 1.3% of all calls). | Harness noise, not job work. |
| W6 | **Over-built nodes.** Geometry more complex than asked, then rebuilt. | Gates: «ты перемудрил, надо сделать их простыми… врезкой» (11-05 07:06); bench: «излишек полигонов» (11-10 10:00); TEC26: «простая задача идёт 6 часов» (retro O7). | 3 jobs. |

Waste share per session: 2%–24%, overall **8.5%** of tool calls (repeated 5.4% + failed 3.0%), not counting the
extra images of W1 (most of them are successful calls the result did not use: 247 extra images vs 103 sent).

### Repeated remarks from Artem (3+ jobs)

Counted in Artem's own chat messages (`data/sessions.csv`, `theme_*` columns), then each read.

| Remark | Sessions / messages | Jobs (examples) |
|---|---|---|
| **«Открой сцену, посмотрю» / «дай путь»** — Artem looks in Max/Blender himself instead of agent renders | **12** sessions / 34 messages | gates, Garibaldi, Silikatny DWG, СРЕDА, MAF Blender, MaxScript cleanup, Object 009 windows, Staropetrovsky («рендеры не нужно делать… открой мне сцену», 11-12 12:16 and 12:24), Butovskaya smoothing, 4BK K3, tow02 |
| **«Почему так долго» / «перемудрил» / «хватит спрашивать»** — too slow or over-done | 5 sessions read and confirmed (theme regex: 11 sessions, 21 messages, with false hits) + TEC26 retro | tow02 ×3 messages («почему так долго?», 10-20 10:42 and 10:46, 10-21 11:42), migration («Что то долго»), 4BK («Долго им еще?»), gates («перемудрил»), СРЕDА («хватит спрашивать у меня подтверждения»), TEC26 retro («простая задача идёт 6 часов») |
| **Seams / joints** follow the source (openings, panel layout, cover joints) | 7 sessions / 21 messages | СРЕDА (continuous trims), Kasatkino («на стыках покрытий… без треугольников»), Silikatny DWG (paint line on every cover joint), 4BK (panel seams 10 mm «по логике проемов»), tow02 |
| **Side-by-side with the reference** — one preview per item next to the album/slide | 5 sessions / 13 messages | Staropetrovsky («превью мафа слева, справа фотография из альбома»), TEC26 («слайд \| VPM \| NPM», retro section 3), Flora species sheet (#1146), MAF overview contact sheet (VATUTINO `LESSONS.md`), Kasatkino tile screenshots |
| **Verification gap** — "done" before checking the viewport/source | 4 jobs (retro) | СРЕDА 7 defects after green checks, K5 alpha holes, Garibaldi no independent check, Kasatkino skipped face (`docs/retros/2026-11-05-sessions-retro-04-05.md`, problem 1) |

The last row is the reason why even `fast` keeps one readback.

## 4. Draft: check levels

One field per card or chat task: `level: fast | standard | full`. **Who decides:** the orchestrator (or the agent
in a chat) at intake, by the table below, and states it in the first message; Artem overrides with one word.
An agent may go **up** a level on its own with a one-line reason (e.g. "shared `src/` module changed"), never down.

| | `fast` | `standard` | `full` |
|---|---|---|---|
| Typical tasks | colouring, finish/diffuse swap, small geometry edit Artem describes, re-export of an accepted model | a new node or object for a job (MAF, fence, window set, ground patch, OKS body), job scripts under `jobs/` | regulation code and data: validators, `standards/`, export, schemas, shared `src/` modules; a delivery that claims `passed=true` |
| Look at the result | **1 image**: the result next to Artem's reference (his screenshot/slide/photo). If Artem is online: open the scene in his DCC version and give the absolute path instead of rendering. | 1 image per item next to its reference + 1 overview (contact sheet), or open the scene. Extra angles only for a defect Artem named. | as `standard`, plus the regulation album/sheets the delivery needs |
| Machine checks | one readback of what changed (object count, material IDs, UV channel, dimensions); no pytest | readback + the cell's validators (`validate-delivery` for the node) on the exported file | readback + validators + tests: affected tests while working, **one** full suite per PR (rule 49), probes and receipts |
| Review | none; Artem's «да» is the acceptance | dt-reviewer only when code is committed (job scripts: one round, scripts not the picture); Artem accepts the picture | dt-reviewer review + Artem's acceptance, separate statuses |
| Commit / PR | none needed; result path + one `LESSONS.md` line if Artem said something new | one PR per job at the end (scripts + manifest), not per node | one PR per issue |
| Stop rule | after Artem's «да» or a second correction on the same point → ask, do not iterate alone | | |

Evidence for the split: W1/W4 above; TEC26 retro section 3 (the 2.5–3 h plan for colouring 5 buildings is exactly
`fast` for the fan-out and `standard` for the pilot); the retaining-walls session (12607103: 60 calls, 0.44 h active,
3% waste, 6 renders for 3 sub-tasks, each accepted) is a `fast` run as it should look.

## 5. Draft: node recipes

Frequency of node types in the measured set (28 sessions + 13 cards): OKS body 11, ground/paving/markup 9, library
MAF 8, colouring/finish 5 (overlaps: Silikatny DWG is also ground, #889 also MAF; plus the TEC26 retro), window/glazing 5 (1 dedicated session + 4 OKS jobs where windows were the defect),
fence/railing/gates 4, Flora 3 cards (one job). **Canopy: 0 measured jobs** (one mention «там навесы поменялись»
in MAF Blender), so no recipe is drafted (question 5).

Every recipe: **deviate if you state why in one line.** Default level in brackets. Steps cite the jobs they come from.

### R1. Colouring / finish swap (`fast`)
1. Read the reference first: slide/legend/photo Artem gave (TEC26 retro O1, O5: the slide is the authority).
2. Inventory material IDs in the scene; map ID → material → colour/texture in one table (TEC26, Silikatny DWG).
3. Apply; one readback (IDs, UV channel, map paths).
4. One image result | reference, or open the scene for Artem.
- Done: Artem's «да» on that image. No tests, no review, no Gate-1 sheets (TEC26 retro O6/O7).

### R2. Library MAF (`standard`)
1. Sources: drawing/PDF page, photo, existing library entry (Verona #790/#1046, Staropetrovsky, bench).
2. Block-out at real size; geometry only as detailed as the reference needs (bench «излишек полигонов», gates «перемудрил»).
3. Colour zones = material IDs per the library baseline; project spec wins where it differs (#889, VATUTINO `LESSONS.md`).
4. Smoothing/normals checked in the viewport (Butovskaya smoothing groups).
5. One side-by-side sheet per item vs photo/album (Staropetrovsky, MAF overview v003).
- Done: Artem accepts the sheet or the opened scene; library entry written; UCX/budgets for the cell pass.

### R3. Fence / railing / gates (`standard`, `fast` for a resize)
1. Dimensions from the source or Artem's numbers (retaining walls: 20×20 mm posts, 40 mm rail; gates resize).
2. Straight members, simple joints first; complex nodes only when the source shows them (gates «врезкой»).
3. Repeat members by step along a spline/path (vertical posts, Object009 handrail).
4. One image per side that changed, or open the scene.
- Done: count and step of posts match the source; Artem's «да».

### R4. Window / glazing (`standard`)
1. Openings from the drawings (KPP1 facades from Revit DWG blocks, D238); frames and glass as separate material IDs (`MainGlass`).
2. Remove interior/hidden polygons (Object 009); no glass below grade where frames meet ground (Garibaldi).
3. Check mullion counts against the source (KPP1 #1230 «164/171 mullions»; tow02 imposts after Artem's review).
- Done: counts match, glass separate, readback of the exported file.

### R5. Ground / paving / lawn / markup (`standard`)
1. Contour and covers from the DWG/PZU; colour = hatch background fill (Silikatny DWG).
2. Covers meet without slivers or triangles at joints (Kasatkino, Ground v015 #371); markup lines on joints where the source shows them (Silikatny).
3. Material ID per cover/texture (#371); xView/overlap check on the exported mesh.
4. Hand over the flat base for Artem's own projection when he does it (Kasatkino, job-local).
- Done: covers and joints match the source; validators for the Ground cell; Artem's «да».

### R6. OKS body / facade (`standard`; `full` when the delivery claims `passed=true`)
1. Read slides/legend/album before modelling (TEC26 O1; 4BK; СРЕDА).
2. Body → openings → decor as separate parts («как куски лего», tow02 10-20 10:46).
3. Seams and panel joints from the source openings/layout (4BK, СРЕDА, tow02); continuous trims stay one mesh.
4. Materials per ID from the drawings; reveals separate where the job asks (Garibaldi, job-local).
5. Readback + regulation validators on the exported file; record blockers (stage, value, limit) instead of chasing a pass (KPP1 `LESSONS.md`).
- Done: Artem accepts in the opened scene; validators as measured; delivery package only at `full`.

### R7. Flora star planes (`standard`)
1. Species list from the sheet (generated, totals asserted, #1146).
2. Map per species: exact species match, colour measured, crop to the plant (VATUTINO `LESSONS.md`).
3. Bleed colour into transparent pixels; check the edge-on plane (D246).
4. Texel measured in the final atlas; ask before upscaling.
- Done: species sheet + placement accepted by Artem (#1178 visual gate).

## 6. Questions for Artem

1. **Look step.** In 12 of 28 sessions you asked to open the scene yourself. When you are online, does «open the scene + absolute path» fully replace agent renders at `fast` and `standard`? (Recommendation: yes; render only for a board card without you or for a side-by-side sheet.)
2. **Who sets the level.** The orchestrator/agent sets it at intake by the table in section 4 and you override in one word — or do you want to name it every time? (Recommendation: the table, you override.)
3. **`fast` readback.** Keep one machine readback (IDs/UV/count) in `fast`, given the verification-gap retro, or literally only the image? (Recommendation: keep it; it costs 1–2 calls.)
4. **Review on job PRs.** At `standard`, one dt-reviewer round on committed job scripts (not on the picture), one PR per job — OK? (Recommendation: yes.)
5. **Canopy and other nodes.** No canopy job in the data. Draft it from `docs/domain/` now, or wait for the first canopy job? (Recommendation: wait.)
6. **Image limits.** `fast` 1 image, `standard` 1 per item + 1 overview, extra angles only for a defect you named — OK?
7. **Where it goes.** After your «да», wire the levels into the card template / task-intake and the recipes into `docs/procedure/` as separate cards?
