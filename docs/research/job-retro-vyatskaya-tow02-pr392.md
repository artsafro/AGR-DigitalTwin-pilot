# Job retro: vyatskaya-tow02 mid-poly master (PR #392)

## Summary

- Job `vyatskaya-tow02` built tower TOW02 (ул. Вятская вл. 47–49) as a mid-poly master from a panelised 3ds Max curtain-wall source (`RC_TOW_02`, 604 k tris; `RC_TOW_Lapatki_02` fins, 81 k tris; `SLAB_TOW_02` slabs), session `d614e212…`, 5 h 57 min (2026-10-20T07:23–13:20 UTC), 2 commits (`2f07939`, `6983bba`) + handoff (`8e0f442`) in PR #392 (not merged; review running).
- User verdict on the master: **"4+", accuracy and geometry fine, too slow ("раньше было быстрее")**; modelling stage closed, texturing/NPM is the next stage.
- 3 of 5 acceptance lines met (logical part groups, every level, openings as planes), 1 partly (mid-poly rules: 64 triangles + 44 faces < 2 cm kept as listed exceptions, no independent check yet), 1 not (NPM derivation — next stage).
- The dominant time sink was a **~1.5 h dead end on the engine route**: the extractor ran 20 min on 690 k triangles (pure Python), sized none of 889 ribbon openings, found 0 decor, then `run_benchmark` re-extracted and the build hung 64 min until the user forced a pivot to a direct "Lego" build.
- Root cause: **no source-class pre-check** — a panelised curtain wall (5 561 connected parts, largest 11 % of area = no shell) was fed to an engine that expects a shell; after the pivot, parallelised measurement subagents + four `Engine gap: EG6` build scripts produced the master.
- Harness frictions: `pipeline_gate` blocks read-only measurement scripts in `jobs/<JOB>/scripts/` (they ended in `outputs/`), subagents cannot write report `.md` files, the dumper writes negative-scale meshes inward, and the user's level helpers (`Empty`…`Empty.007`) are not read (only `LEVEL_*`).
- The four `EG6` build scripts and the measurement method are candidates to generalise into the engine/library (ring-stack body **L**, decor loft **M**, top/zones **M**, decor attachments **M**, measurement frame/outlines **M**, plus three S-sized checker/CLI reuse proposals R11–R14).

---

## 1. Requirement vs result

Requirement and acceptance from `jobs/vyatskaya-tow02/STATE.md` (branch `origin/job/vyatskaya-tow02-midpoly`), compared at handover against master `outputs/build-v013/tow02_master.blend`. Times UTC. **Verified** = read from git objects / transcript directly.

| # | Acceptance line | Result | Evidence / numbers |
|---|---|---|---|
| 1 | Body, decor (bands, fins), glass and openings separated as logical groups | **met** | `TOW02_body`, `TOW02_body_glass`, fins `F01–F26`, `TOW02_ac_baskets`, `TOW02_ac_floor`, `TOW02_louvre` (+plates), `TOW02_coping`, `TOW02_top`, `TOW02_top_glass`, `TOW02_railing_glass`, `TOW02_soffit` (STATE Build log build-v013). |
| 2 | Every level from the user's helpers built (colonnade, bend, typical, top storey, superstructures 1–2) | **met** | `cmp_all` elevation vs source; levels z 0.04/6.906/31.367/65.405/69.456/72.201/76.25/79.237; colonnade 0–6.9 modelled (fins + soffit), body 6.9–64.7, top 64.7–79.25 (STATE Build log build-v009/v013). |
| 3 | Openings as planes (or windows where simpler), chosen per facade | **met** | Ribbon glazing as planes at mid reveal (0.12 m, glass at 0.06 m behind body face); glass faces on the outline above 64.7 (decision 2026-10-20). Body glass 2 761 planes, top glass 509 faces. |
| 4 | Mid-poly rules of `docs/domain/geometry.md` (quads, < 3.8 m, no doubles/T-junctions, normals) | **partly** | Mostly met; **64 triangles** kept as listed exceptions (soffit slab 57, top 6, body 1) and **44 faces with a side < 2 cm**; 0 n-gons; 0 non-manifold. Independent-checker not run yet; user verdict "4+", detailed look pending. Final totals 34 074 faces / 64 triangles. |
| 5 | NPM derived from the master | **not** | Next stage (texturing → NPM), explicitly deferred. |

NPM is out of this stage's scope by the Requirement ("с последующим переводом в NPM" — mid-poly first), so items 1–4 are the modelling contract and 5 is a later stage.

---

## 2. What worked (keep doing) and what failed

### Worked

- **Direct "Lego" build from measurements** after the pivot: body rings → opening planes → decor → top volumes, one object per part, then assembly and per-part comparison. Produced the accepted master. (STATE "Route = direct Lego build"; transcript 10:46–13:10.)
- **Parallelised measurement subagents**: "Measure typical floor and fins" (41 min) and "Measure bend zone and top levels" (38 min) ran in parallel and returned self-checked numbers (identity ≤ 20 mm, outline 44 vertices, fins profiles/paths) with proof PNGs. (Transcript task-notifications `<duration_ms>`, 2 486 s and 2 284 s.)
- **Measurement method**: building-local frame by min-area rectangle of a slab, orthographic elevations/sections from numpy triangle dumps instead of viewport captures, storey outlines with vertex correspondence between rings. This is the reusable core. (`inspect_sections.py`, `outputs/measure-v00N/*/scripts/`.)
- **Self-checking build scripts**: BVH nearest-distance of built faces vs source (median/p95/max, per material + z), open-edge classification, T-junction detection, read-back of the exported OBJ/blend. Numbers are quoted per part in the Build log.
- **Discipline**: worked on a copy (`tow02_master_work.blend`), never touched the user's `Untitled.blend`; every save to a new versioned `build-vNNN`; explicit exception lists (the 64 triangles, the 44 small faces) instead of hiding them.

### Failed

- **Engine route on a source it cannot read** (~1.5 h): `source_class: panelised` (slabs as body, contours from panels) — extractor 20 min on 690 k triangles (pure Python), **889 ribbon openings unsized** (no reveal measurable on a panel facade), **0 decor**, terrace parapets 3.41 / 2.75 m, roof parapet read off a glass railing, roof boxes absent, contour edges skewed up to ±3°; then `run_benchmark` re-extracts and the build runs 64 min with no progress output or timeout before it was stopped; `BuildError "2D plan weld moves 0.0036 m, beyond weld_m 0.003"` — and the spec forbids `weld_m >= plate_gap_m` (0.005), so the spec is **unbuildable**. (backlog P13; `pipeline/spec-v002.*`; STATE "Lessons".)
- **Cause (root)**: the first route recommendation was made **without checking the source class**. `RC_TOW_02` is 5 561 connected parts, the largest 11 % of its area — no shell. Rule learned: for a panelised curtain wall, check the source class first; if no shell, go straight to measurements → Lego build, do not start the extractor.
- **Dumper mirror-matrix**: `measure_spec_blender.py` writes faces of meshes with a mirrored world matrix (negative scale, typical of 3ds Max FBX) inward; some slabs inward too (backlog P13).
- **Level helpers not read**: the user's `Empty`…`Empty.007` are not read (only `LEVEL_*`), so levels went into `object.json` by hand (P13).

---

## 3. What the agent wrote itself (job scripts / Engine-gap code / measurement tools)

All build scripts are in `jobs/vyatskaya-tow02/scripts/` and carry `Engine gap: EG6` in their docstring (checked by `pipeline_gate`). Lines from PR #392 diff.

| File (lines) | What it does | Candidate module → engine/library | Effort |
|---|---|---|---|
| `scripts/build_body_blender.py` (481) | Ring-stack body: one outline per storey with vertex correspondence; shared columns on fixed edges (union over storeys), own columns on moving edges; step soffits between differing storeys cut into strips so walls/soffits share vertices (no T-junctions); collapsed-jog handling; fixed-line snap; 1 cm weld; mitred reveals; mid-reveal glass planes; `seal_leftovers` for quad holes/T-junctions. | Body builder for `source_class: panelised` (ring correspondence + step soffit is the hard part to generalise). | **L** |
| `scripts/build_fins.py` (1017) | Decor loft along a measured 3D path with linear profile morph A↔B; cut at the body with ≥ 10 mm embed (ray sampling); ring spacing by chord error; cap lift over coplanar roof faces. | Decor loft (`decor` block, curved-path extrude). | **M** |
| `scripts/build_top_blender.py` | Zones with z-patterns (solid / opening / glass_face); quad cap fill with holes; single-section coping sweep; railing planes; roof boxes; bottom row equal to the body seam vertex-for-vertex. | Roof structures / zones in `from_spec`. | **M** |
| `scripts/build_decor_blender.py` (1015) | AC baskets (one-sided planes + floor), railings, louvre blades as boxes with ray-cast end embed, colonnade soffit that closes the body's open loop. | Decor attachments (EG2-adjacent). | **M** |
| `scripts/inspect_sections.py` | Building-local frame (min-area rectangle of a slab) + orthographic sections from numpy dumps. | Measurement library (frame + section dumps). | **S–M** |

Measurement tools were **blocked from `scripts/`** by `pipeline_gate` (they name no engine gap), so they live next to their data under `outputs/` (untracked): `measure-v001/typical/scripts/` (`measure_common.py`, `measure_typical_floor.py`, `measure_fins.py`), `measure-v001/bend_top/scripts/` (`measure_bend.py`, `measure_top.py`, `measure_soffit.py`), `measure-v002/bend_rings/scripts/` (`measure_bend_rings.py`, `plot_bend_rings.py`), `outputs/spec-v001/tools/` (`prepare_dump_v002.py`, `check_dump.py`). The reusable method (frame + ortho elevations + storey outlines with vertex correspondence) belongs in a library module, effort **M**.

Reuse proposals already recorded in `docs/backlog.md` (all effort **S**): **R11** orthographic-elevation PNG stack CLI; **R12** BVH nearest-distance checker module; **R13** open-edge classifier + T-junction finder; **R14** skill step to save the open scene as the next `build-vNNN`.

---

## 4. Time

Total **5 h 57 min** (2026-10-20T07:23:01Z → 13:20:33Z). Transcript times UTC (the assistant also quotes local UTC+2 in some messages; minutes below are wall-clock, `~` = estimated from message/file timestamps).

| Phase | Window (UTC) | ~min | Notes |
|---|---|---|---|
| Repo clone + wait for the user | 07:23–08:00 | 37 | `git clone` + gh auth; idle waiting for the voice task. |
| Task understanding + Blender MCP setup | 08:00–08:08 | 8 | MCP bridge did not start: 4 connection errors + user toggled Online Access (transcript errors 08:00–08:05). |
| Scene analysis, sections, local frame | 08:08–08:23 | 15 | Three Max meshes (690 k tris), sections, building frame. |
| **Measurement subagents (parallel)** | 08:23–09:05 | ~42 wall | "bend/top" 38 min and "typical/fins" 41 min, parallel. |
| **Engine route (dead end)** | 09:20–10:48 | ~88 | extractor 20 min → spec v002; `run_benchmark` re-extract + build hung 64 min; stopped at 10:44; user forced pivot 10:46–10:48. |
| Body "Lego" build + 3 rewrites of step logic | 10:48–11:39 | ~51 | Typical ring (10:53), bend rings (11:26), full rewrite of the step/soffit builder (11:31), open-edge fixes, body 6.9–64.7 done 11:39. |
| Fins + decor + top subagents + assembly | 11:49–12:46 | ~57 | fins ~23 min, decor ~37 min, top ~55 min (parallel-ish); saved build-v009 master 12:46. |
| User review edits ×4 (parallel) | 12:55–13:10 | ~15 | fins +8 mm, AC floors, single-section coping, louvre as geometry → build-v013. |
| Commit + handoff + PR | 13:16–13:20 | 4 | commit `2f07939`, acceptance compare `6983bba`, handoff `8e0f442`. |

**Where the time went**: the engine dead end (~1.5 h, ~25 % of the session) is the single largest avoidable sink; the three rewrites of the ring-stack step logic (~30–40 min of the body phase) are the second; measurement subagents (35–55 min each, but parallelised) and the "waiting for the user" gaps fill the rest. The user noticed the slowness ("раньше было быстрее") and asked "сколько ещё?" / "почему так долго?" five times (10:24, 10:42, 12:13 and the pivot at 10:46).

---

## 5. Harness / process problems

1. **No source-class gate before route choice** — the engine route was recommended before checking whether the source has a shell. Fix: a pre-check (largest connected part / mesh area) before extractor dispatch. (STATE Lessons; P13.)
2. **`pipeline_gate` only admits `Engine gap: EG<n>` scripts in `jobs/<JOB>/scripts/`** — read-only `measure_*`/`inspect_*` tools are not gaps, so they landed in ignored `outputs/`. Proposal: admit read-only tools (no bpy writes) or a `jobs/<JOB>/tools/` dir. (P13; subagent handback 08:59/09:05.)
3. **Subagents cannot write report `.md` files** — their reports existed only in the chat transcript and had to be pasted back; the orchestrator had to save them as `outputs/…/REPORT.md` (which is gitignored). (P13; subagent handbacks.)
4. **Extractor is pure-Python and O(triangles)** — 20 min on 690 k tris; `run_benchmark` extracts a second time inside the build. (P13.)
5. **Engine build has no progress output / timeout** — 64 min silent hang before a manual stop. (P13.)
6. **Dumper mirror-matrix** — negative-scale meshes written inward. (P13.)
7. **Level helpers** — only `LEVEL_*` read, the user's `Empty`…`Empty.007` were hand-mapped into `object.json`. (P13.)
8. **Environment friction (self-resolved)**: MCP bridge not started (needed the user to enable Online Access + Save Preferences), `git` hooks not installed (`core.hooksPath` unset → pre-commit run by hand), git identity unset (commits via `-c user.name/email`). (HANDOFF "Rules broken".)
9. **8 tool errors total** in the session (4 MCP connection/hook denials, 1 Bash exit 49, 1 ModuleNotFoundError in a scratch plot script, 1 exit 2); none blocked the outcome.

---

## 6. The user's own words (verbatim, with transcript times UTC)

All from `job-vyatskaya-tow02-midpoly-pr392-d614e212….jsonl`, human turns. Russian is kept as spoken.

- `07:23:01` — «подключись и получи репо https://github.com/artsafro/AGR-DigitalTwin-pilot»
- `08:00:25` — the voice task: «…нужно проанализировать корпус… определить декор-элементы, бадик-элементы, стекла, проемы… попробовать смоделировать модель под Медполе с последующим переводом в NPM. Если проще проемы делать плейном… Тут смотри сам. …я пока расставлю эти хелперы. В блендере.» (also: «Медполе» = mid-poly, «бадик» = body)
- `08:04:06` — «…Untitled.blend вот сам открой в 5.1»
- `08:06:39` — «открой 5.1 еще раз»
- `08:17:56` — «коллонаду отобразить а стилобат в другом файле, он нам не нужен, да подверждаю» (colonnade in; stylobate out of scope)
- `08:37:47` — «ок, жду результаты замеров»
- `09:10:18` — «ок» · `09:20:50` — «да» (approve the hybrid route/build defaults)
- `10:08:14` — «ок, жду результат экстрактора»
- `10:24:13` — «сколько еще?»
- `10:41:43` — «ок, жду»
- `10:42:08` — «почему так долго?»
- `10:44:18` — «давай» (stop the engine build)
- `10:46:32` — **the pivot**: «пока выясни что так долго? почему нельзя построить бадик потом проемы потом декор как куски лего, что опять не так?»
- `10:48:02` — «да» (approve the Lego route)
- `11:42:55` — «ок, жду лопатки и верх»
- `12:05:50` — «ок, жду верх и декор»
- `12:13:04` — «сколько еще ждать?»
- `12:55:52` — the four review corrections: «…нужно добавить верхний полигон на балкончике… пол. Надо верхний полигоны… колоночек чуть-чуть приподнять на восемь миллиметров… чтобы не было оверлапа с крышей… поправить сечение на отливах… одним сечением прямоугольным… единый меш… не нужно выдумывать переходы вот эти ступенчатые… жалюзи который декор ты сделал плейны… я хочу их сделать геометрией… чтобы проще было текстурировать. Как понял правки?»
- `12:57:15` — «сохранил, +8 мм над кровлей»
- `13:16:07` — **the verdict**: «В принципе, по моделингу мы закончили. Справился ты на 4 с плюсом. Очень, конечно, много времени это заняло все. На мой взгляд, как будто бы раньше это было быстрее. Но в плане точности и сложности геометрии вроде бы ты справился. Я еще детально не смотрел, но вроде пока что да. Все норм. …зафиксировал все проблемы движка… сделал коммит локальный и перейдем к текстурированию»

Note: the card states "Approved by Artem 2026-10-20 22:3x"; the transcript verdict above is at 13:16 UTC (15:16 local UTC+2). If there is a later review/approval session it is not in the transcript directories searched — see Open questions.

---

## 7. How it applies to this repository

- `docs/backlog.md` **P13** already carries the engine/harness findings + the "new job code to generalise" list; **EG6** is already extended (user "да") to "whole body of a panelised source built from measurements". A future engine PR reads these directly.
- `docs/backlog.md` **R11–R14** are the four small reuse proposals (elevation CLI, BVH checker, open-edge classifier, versioned-save skill step) — all effort S, ready for the hypothesizer/adopt lane.
- The build scripts to lift into the engine live in `jobs/vyatskaya-tow02/scripts/*` (section 3); the measurement method in `jobs/vyatskaya-tow02/outputs/measure-v00N/*/scripts/` and `inspect_sections.py`.
- `jobs/vyatskaya-tow02/object.json` records `source_class: panelised`, the frame derivation, and the hand-mapped levels — the concrete spec for a "panelised" engine path.
- `jobs/vyatskaya-tow02/STATE.md` "Lessons" and "Build log" are the canonical numbers; `pipeline/spec-v002.questions.md` (937 rows) is the evidence of the 889 unsized openings.
- This retro is docs-only under `docs/research/`; no code changes.

---

## 8. Proposed next tasks (do NOT create GitHub issues) and testable hypotheses

### Next tasks (title — scope — value/effort)

1. **Source-class pre-check before engine dispatch** — a read-only classifier (largest connected part / mesh area, shell presence) that gates the extractor and recommends measurements → Lego for panelised sources. Value: avoids the ~1.5 h dead end. **S**.
2. **Extractor performance: vectorise + cache the dump** — replace the pure-Python 690 k-triangle parse with numpy/vectorised path and make `run_benchmark` reuse the already-written spec instead of re-extracting. Value: high (20 min → minutes, and no second 20-min run). **M–L**.
3. **Generalise the ring-stack body builder (EG6) into the engine** — `build_body_blender.py`'s vertex-correspondence + step-soffit + no-T-junction logic as a `source_class: panelised` body path. Value: high for the next curtain-wall tower. **L**.
4. **Generalise decor loft (fins) into the engine** — curved-path extrude with profile morph, ray-cast embed, chord-error ring spacing (`build_fins.py`). **M**.
5. **Engine gap: roof zones + decor attachments** — `build_top_blender.py` + `build_decor_blender.py` (AC baskets, louvre, soffit) as `from_spec` modules. **M**.
6. **Harness: admit read-only job tools** — allow `measure_*`/`inspect_*` scripts (no bpy writes) in `jobs/<JOB>/scripts/` or a `jobs/<JOB>/tools/` dir, and let subagents write report `.md` files. Value: removes the two largest harness frictions. **S**.
7. **Read the user's level helpers** — a rename/markup step or reading any empty named in `object.json`, so `Empty`…`Empty.007` become `LEVEL_*` without hand-mapping. **S–M**.
8. **Fix the dumper mirror-matrix winding** — detect negative-scale matrices and correct face winding. **S**.

### Testable hypotheses (claim — metric — threshold)

1. A source-class pre-check (largest connected part < 25 % of mesh area ⇒ panelised/no-shell) before extractor dispatch avoids the engine dead end. *Metric:* source-analysis → first Lego body wall time on a 690 k-tri panelised source. *Threshold:* < 30 min (observed ~1.5 h).
2. The extractor is the dominant cost and is linear in pure-Python; a numpy/vectorised dump cuts it. *Metric:* extractor wall time on the same `RC_TOW_02` source. *Threshold:* < 5 min vs 20 min observed.
3. `run_benchmark` re-extracting wastes a full second dump; reusing the already-written spec halves engine-route wall time. *Metric:* engine route wall time. *Threshold:* ≥ 20 min saved (no second extract).
4. The ring-stack step/soffit logic is generalisable: a shared primitive eliminates the three rewrites. *Metric:* number of job-specific rewrites of the step logic on the next panelised source. *Threshold:* 0 (observed 3).
5. Parallel per-zone measurement subagents bound the measurement phase. *Metric:* measurement wall time for a curtain-wall tower. *Threshold:* < 45 min for a 690 k-tri source (observed ~42 min with 2 agents; test whether 3–4 zones stay under this).
6. The BVH nearest-distance checker (R12) + open-edge classifier (R13) as a reusable module removes the ad-hoc measurement/QA scripts. *Metric:* distinct ad-hoc comparison scripts per job. *Threshold:* 0 new ones once R12/R13 exist.

---

## 9. Open questions for the user

1. **Approval time / second session.** The transcript's "4+" verdict is at 13:16 UTC (15:16 local UTC+2), but the card says "Approved by Artem 2026-10-20 22:3x". Is there a later review/approval session whose transcript is not in `…/.AGR-DigitalTwin_pilot/logs/transcripts/` or `…/AGR-DigitalTwin/logs/transcripts/`? (Only one `*vyatskaya-tow02*` transcript was found.)
2. **Panelised sources in or out of engine scope.** Should the engine gain a real `source_class: panelised` path (contour from panels + reveal measurement), or is "panelised ⇒ always Lego from measurements" the standing policy (i.e. close EG6's body extension as "measurements only")?
3. **Measurement scripts location.** `pipeline_gate` blocks read-only tools in `jobs/<JOB>/scripts/`; do you prefer a new `jobs/<JOB>/tools/` directory, or relaxing the gate for no-`bpy`-write scripts?
4. **Subagent report files.** Subagents could not write `.md` reports (they lived only in chat). Should subagents be allowed to write report files under `outputs/`, or is that restriction intentional?

---

## Sources

1. `git show origin/job/vyatskaya-tow02-midpoly:jobs/vyatskaya-tow02/STATE.md` (Requirement, Build log, Lessons) — verified.
2. `git show 8e0f442:docs/HANDOFF.md` (session metadata, "Rules broken", agent trace) — verified.
3. `git show origin/job/vyatskaya-tow02-midpoly:docs/backlog.md` (P13, EG6, R11–R14) — verified.
4. `git show origin/job/vyatskaya-tow02-midpoly:jobs/vyatskaya-tow02/object.json` and `materials.json` — verified.
5. `gh pr view 392` (files, commits, +47 427/−0) and `jobs/vyatskaya-tow02/pipeline/spec-v002.questions.md` (889 unsized openings) — verified.
6. Session transcript `…/.AGR-DigitalTwin_pilot/logs/transcripts/job-vyatskaya-tow02-midpoly-pr392-d614e212-20e5-4614-ba51-2f51c9bb7026.jsonl` (11 MB JSONL; timeline extracted with a script under `C:/x/job-retro-vyatskaya-tow02-pr392/`, 39 human messages, 63 assistant blocks, 225 tool results, 8 errors) — verified.
