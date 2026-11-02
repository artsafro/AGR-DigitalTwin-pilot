# Job retro: TEC26-OKS intake (PR #570)

Card: t_538972f1 (research). Stage under review: issue #558 → card `t_8e55c5f5` → PR
[#570](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/570) (branch `job/tec26-oks-intake`, head `f53ef25`,
merged 2026-10-23 08:18 CEST). All times are CEST (UTC+2), 2026-10-22 unless marked.

## Summary

- The intake took **60.4 min** of worker time (10:34:40–11:35:05) plus a 3-min review (P1/P2/P3 = 0/0/0). Of that
  time, **30.3 min** was the one full suite (13367 passed / 19 skipped / 179 deselected) on a diff that touched only
  `jobs/` and `tests/jobs/`. About **25 min** of it was idle polling.
- Delivered: 64 source copies (144 040 284 B, 128/128 hashes), a native Max 2026 census of 3 scenes (9 OKS surfaces + 63
  collision candidates, truba 1 + 60, KPP 4 + 33), a KPP recipe (19 tiles, ID→tile matched) and a provisional pilot,
  AC.08 (348 tris). The pilot held: #559 built AC.08 first and the user accepted it.
- The operator narrowed the scope at 10:43. Acceptance lines 3–4 (drawings census, ID → finish table) moved to
  #561–#566, so they are **not met** in this PR by decision.
- Biggest miss, judged in hindsight: the facade album `ТЭЦ26 на РР (1).pptx` was copied and hashed but never opened.
  Later the slides turned out to be the binding colour/seam source. The job-level retros
  (`docs/retros/2026-10-22-tec26-colouring-{codex,claude}.md`) put about 6 h of downstream rework on that gap.
- The user's only correction inside this stage concerned the pictures. The flat painter-sorted ID images showed
  triangles that do not exist («странные очень треугольники»). They were replaced by depth-correct Blender renders
  in 10 min, and the perimeter-drop rule (≥ 1 m below ±0.000) was recorded.
- Engine candidates: a generic headless Max Multi/Sub census adapter (M), a census → depth-correct Gate-image renderer
  (S/M), and a per-wall perimeter-drop check (S). All of them exist today only as job scripts.

Sources (all read by me, no web): `origin/main:jobs/TEC26-OKS/{STATE.md,object.json,census/*,scripts/*}`,
`gh pr view 570`, kanban card `t_8e55c5f5` (comments, events, runs), Hermes session
`local-e92d7962…` in `C:/Users/artsafro/.hermes/profiles/dt-worker-codex/state.db` (268 messages, extracted with
`C:/x/job-retro-tec26-oks-pr570/timeline.py`, outside git), the orchestrator chat `20261021_225323_669071ea` in
`C:/Users/artsafro/.hermes/state.db` (user quotes), `docs/retros/2026-10-22-tec26-colouring-*.md`.
No JSONL transcript matching `*TEC26-OKS*` exists in either `logs/transcripts/` folder. `docs/backlog.md` has no
entry naming the job, and there is no `jobs/TEC26-OKS/pipeline/*.questions.md`.

## 1. Requirement vs result

Acceptance of #558 as written, plus the two requirements added mid-run:

| # | Acceptance line | Verdict | Numbers / evidence |
|---|---|---|---|
| 1 | Copies + `SHA256SUMS.txt` under `C:/x/tec26-oks/`; `jobs/TEC26-OKS/` with STATE.md, object.json, REGISTRY row | **met** | 64 files, 144 040 284 B, staged in 3 s; 128/128 source/copy hashes (re-verified by reviewer); REGISTRY row `tec26-oks` |
| 2 | Scene census per layer + truba: mesh vs UCX, tris/quads, Multi/Sub tree, per-ID faces + m², UV channels, units/pivot, naming, Max version | **met** (one caveat) | `census/{oks,truba,kpp}.json` (11 931 / 6 184 / 5 050 lines); 170 nodes; reviewer recomputed ID/area for 170 objects. Real layers are `004…009`, not `0.0.0.4…` (the card was wrong). Caveat: "UCX" was classified by name (`Colizii_*`, `Col_*`) and is reported as *collision candidates*, not validated hulls; `Col_002` bbox parity is false by 0.101 mm. UV checked for presence only, not quality |
| 3 | Drawings census АС.04–09 (sheets, legend, RAL, locator) | **not met (descoped 10:43)** | Only the title-block text per АС was kept (README "Titles only"). The partial pre-scope DWG/PDF extraction is outside git (`C:/x/tec26-oks/pre-scope-change-drawings.json`). Owners: #561–#566 |
| 4 | Per building `ID → finish → evidence`, `?` if none | **not met (descoped)** | Delegated to #561–#566; no finish assigned by viewport colour |
| 5 | KPP etalon recipe (UDIM count, tile size, texel, ID→tile, joints, NPM atlas + `_o_`, names) | **met** | 19 tiles 1001–1019, 4096² full / 256² smooth, nominal 1000 px/m, NPM 2048² 5×4 grid 409 px cells → 96.92 px/m, separate `_o_` RGB opacity; finding: `maps_kpp` has **no ERM** files |
| 6 | Truba: what exists vs full VPM+NPM set, missing list | **partly** | Exists: `Tuba` 50 256 tris, 60 `Col_*`, IDs 1,2,3,5,6,7, UV ch1 (U to 138.4), map paths to a dead `A:` drive; railing is 4096², not 2048² as the card said. The missing-list was handed to #560 |
| 7 | Pilot recommendation + ONE question list for Artem, then stop | **partly** | Pilot AC.08 (smallest: 348 tris, 3 IDs, 1 collision candidate), fallback AC.05; **held**: #559 built AC.08 first and the user accepted it. Question list: none ("consolidate after #561–566") |
| + | Perimeter drop (user 11:20): keep ≤ −1.0 m in VPM and NPM | **recorded, not measured per wall** | Global node minima −2.003 … −2.047 m (truba −1.446 m), not presented as a per-wall pass. The per-wall check later appeared in `jobs/TEC26-OKS/AC04/perimeter-drop.json` |
| + | Gate pictures depth-correct, UCX hidden, ±0.000 line, shaded next to ID (orchestrator 11:21) | **met** | Blender 5.1.2 Workbench, 14 renders → 7 sheets, 23/23 hashes, `G:/Мой диск/AGR-evidence/tec26-oks/depth-census-v002/` |

`object.json` keeps `production_authorized: false`, `pilot_recommendation.status: provisional…`, and
`unverified: [coordinates, project_zero, topology, uv_quality_and_density, collision_hull_validity,
material_finish_evidence, human_acceptance]`. These match the results. `passed=true` is never asserted.

## 2. What worked and what failed

Keep doing:
- **Census first, on disk, before the PR.** Raw native JSON was in `C:/x/tec26-oks/census/` by 10:44, so 7 parallel
  cards could read it 50 min before the PR existed. AC04 later measured its per-wall drop from "exact census
  world-space vertices" (`AC04/perimeter-drop.json`, `basis`), with no second Max session.
- **One locked Max batch for all three scenes** (card orchestrator note). Native run v002 took ≈ 3 min. Copies only,
  no saves, plus a test (`test_native_reader_never_saves_or_exports_and_only_loads_copies`).
- **Test-first for native failures**: two RED commits (`1b55514` Bitmap-as-Material, `d6747fc` factory-empty
  World), each fixed in one attempt.
- **Honest reporting of what is not certified**: collision candidates vs UCX, the `Col_002` 0.1 mm discrepancy, node
  minima ≠ per-wall proof, the ERM absence, and the card's wrong layer names and railing size.
- **Smallest-scene pilot pick** (by tris/IDs/collisions) was right for a first full build.

Failed or weak, with the cause:
- **The facade album was not read.** The pptx was staged (`census/sources.json:395`), but neither the card's
  acceptance nor the narrowed scope asked for a slide map, and no worker had a pptx reader (orchestrator answer at
  11:09: «pptx-библиотеки нет, для трубы хватит распаковки»). Cause: the intake spec ranked DWG/PDF as the material
  source, and the census stage was where a slide → building → legend map would have cost about 10 min. Both
  job-level retros place the main 6 h loss here (codex retro A1, claude retro O1).
- **Painter-sorted ID images used as user-facing pictures.** `publish_census.py` drew flat polygons in PIL without a
  depth buffer, which produced false crossing triangles. The README labelled them "diagnostic, not geometry QA", but
  the orchestrator sent one to the user at 11:16 as «так агенты видят разбивку мультисаба». Cause: no rule that
  every image a human sees must be depth-correct. The worker added the rule to the `headless-fbx-intake` skill
  (11:32).
- **The full suite gated the PR on a job-only diff.** 30.3 min, 0 failures, and the diff could not affect `src/`.
  Cause: rule 49 (one full suite before the first review) has no exemption for `jobs/**` + `tests/jobs/**` diffs.
- **The D049 intake format was not used.** The engine has `src/dt_ai/intake/model.py` (`jobs/<JOB>/intake/sources.json`,
  `spec-draft.json`, `questions.md`, checked by `dt_ai.intake.check`). The job wrote its own `census/sources.json`
  and `stage_sources.py` instead. Cause: neither the card nor `docs/procedure/TASK_TO_MODEL.md` pointed at it.
- **Drawings work thrown away.** About 5 min of AutoCAD DXFOUT + ezdxf (3 patches after an ezdxf read error on a
  74.9 MB DXF) was dropped when the scope narrowed at 10:43, and `read_acad.py`/`read_drawings.py` were deleted. The
  orchestrator narrowed the card 9 min after it started; that is cheap, but the card was dispatched before the
  priority decision («приступили немедленно», 10:40).

## 3. What the agent wrote

| File | Lines | What it does | Engine candidate | Effort |
|---|---:|---|---|---|
| `jobs/TEC26-OKS/scripts/stage_sources.py` | 46 | No-clobber copy of the source tree to `C:/x/tec26-oks/sources-v001/`, SHA-256 of source and copy, `SHA256SUMS.txt` + `census/sources.json` | Fold into `dt_ai.intake` (D049 `sources.json` already exists): `dt intake stage <src> <dst>` | S |
| `jobs/TEC26-OKS/scripts/read_max.py` | 128 | pymxs, run via `dcc_batch.py max`: loads each copy, writes per node layer, kind, tris/quads/ngon degrees, Multi/Sub tree (texmap vs material split by superclass, the `1b55514` fix), per-ID face count + m², UV channels/extents, bbox parity, units, version; never saves | `adapters/max/scene_census.py` with pure helpers (`material_tree`, `per_id_area`) so tests import them instead of exec'ing AST fragments | M |
| `jobs/TEC26-OKS/scripts/publish_census.py` | 113 | Validates native JSON (finite numbers, every node classified, bbox parity explicit), classifies `Colizii_*/Col_*/UCX_*` as collision candidates, mirrors classified JSON into git, writes Drive checksums | Same module: `validate_scene` + `classify` as a census schema (pydantic, next to `dt_ai.intake.model`) | S |
| `jobs/TEC26-OKS/scripts/render_depth.py` | 116 | Blender 5.1 factory-empty scene from census vertices, Workbench depth render, ID-colour + plain shaded views, UCX not loaded, red ±0.000 guide, creates World explicitly (`d6747fc`) | `tools/blender/id_depth_render.py`: the single Gate-picture renderer for any census JSON or FBX | S/M |
| `tests/jobs/test_tec26_intake.py` | 107 | 19 tests: Bitmap stub, real census complete/finite/classified, no collision in surface budget, fail-closed corruption, `Col_002` explicit, reader never saves, World creation, depth receipts | Becomes the adapter's tests once the code moves; the AST-fragment `exec` pattern (tests 1, 7) disappears | — |
| `read_acad.py`, `read_drawings.py` (deleted) | — | AutoCAD DXFOUT on copies + ezdxf text with locators | `adapters/cad/dwg.py` already covers DXFOUT; text-with-locator extraction is a small add there | S |

No `Engine gap:` markers appear in the job scripts (`git grep "Engine gap" origin/main -- jobs/TEC26-OKS` returns
nothing). The later per-wall perimeter check (`AC04/perimeter-drop.json`: planar shell side faces within 0.1 mm,
bottom-edge interval coverage at z ≤ −1.0 m) is a natural `src/dt_ai/geometry/perimeter_drop.py` (S).

## 4. Time (worker session 60.4 min, from `timeline.py`)

| Phase | Clock | Min | Note |
|---|---|---:|---|
| Orient (card, AGENTS, PROJECT_STATE, npm-vpm, COORDINATION_RULES 53.7 k chars, skills, conflicts) | 10:34:40–10:36:09 | 1.5 | Plan comment at 10:36 |
| Stage sources (64 files) | 10:36:28–10:37:16 | 0.8 | |
| Max reader v001 → native error → RED test → fix → v002 | 10:38:23–≈10:44:25 | 6.0 | Startup `polyunwrapper_autoload.mse` .NET error (exit 4294967166) tolerated; real error `getNumSubMtls(Bitmap)` |
| AutoCAD DXFOUT + ezdxf (parallel with Max) | 10:39:16–10:44:09 | 4.9 | 3 patches after an ezdxf read error; **dead end** after the narrowing |
| Publish census, classify, KPP recipe, README/STATE/object.json, commit `bd342f4` | 10:44:23–10:53:58 | 9.6 | `validate_scene` failed on `Col_002` parity → made explicit (correct) |
| Full suite via suite_slot | 10:54:12–11:24:28 | 30.3 | Useful work in parallel ≈ 5 min (push, PR body, eval receipt); **≈ 25 min idle** in 7 × 180 s waits |
| Depth-render follow-up (2nd operator note) | 11:24:28–11:33:30 | 9.0 | Blender World None → RED `d6747fc` → rerun 11:29 OK; vision check of 2 sheets |
| PR create/readback, review request | 11:33:39–11:35:05 | 1.4 | |
| Review (dt-reviewer) | 11:35:33–11:38:42 | 3.2 | clean, independent hash/area recompute |
| Wait for merge | → 2026-10-23 08:18 | 20.7 h | The user's «Да, все дошло» at 14:02 was correctly *not* read as a merge order; merge came after «Замерджи все что можно» |

Tokens (session row): 262.6 k input + 18.37 M cache-read + 45.3 k output; 146 tool calls. Two `kanban_show` calls
returned 38 k and 72 k chars, and the final one (after `request_review`) was unnecessary.

## 5. Harness / process problems

1. **Full suite for job-only diffs** (rule 49): 30 min per job-stage PR with no possible effect on `src/`. Shown here:
   0 failures, while the PR waited.
2. **Mid-run notes arrive only between tool calls**: the 2nd operator note (posted 11:21) reached the worker at 11:24:28,
   when a 180 s `process_manage wait` ended. That was harmless here, but a 3-min blind window per wait is a fixed cost.
3. **No pptx reader in the worker toolset**, and the intake spec did not require a slide map (§2).
4. **D049 intake format undiscovered** (`src/dt_ai/intake/model.py`); the job made its own `census/` schema (§2).
5. **Evals cannot measure Hermes sessions**: the receipt is `0 passed / 0 failed / 10 not measured (no Claude
   transcript)`, and `agent_trace.py` writes "Sessions: not measured (no transcript)", while the session sits in
   `state.db`. The retro had to write its own extractor.
6. **CI not run (billing lock)**: there is no remote check; the full suite and DCC runs are author-only, which the reviewer
   noted as an open item.
7. **Card facts wrong at dispatch**: layer names (`0.0.0.4` vs `004`) and railing size (2048 vs 4096). The worker caught
   both; an orchestrator 5-min source read before writing the card (now `task-intake`, PR #576/D186) prevents it.
8. **Tool slips**: an `execute_code` `NameError: patch` (missing import, 11:27:25) and a failed `patch` on
   `evidence.json` (11:33:02). Each cost about 10 s.

## 6. The user's own words (orchestrator chat, Telegram, CEST)

Inside this stage:
- 10:12 (voice, the requirement): «…проанализировать существующую сцену 3ds Max, взять оттуда меши, потом сопоставить эти меши … просмотреть чертежи на предмет материалов и спецификаций, составить список материалов…»
- 10:40: «Я хочу чтобы по котельне проекту там где труба и несколько зданий приступили немедленно работу, все остальное можно отложить, это приоритетная задача» (this led to the narrowing at 10:43)
- 11:18, on the census ID picture: «им мешает колизиядля просмотра? странные очень треугольники»
- 11:19: «или это клиппинг вбпорта, странно короче»
- 11:20, answering "срезаем ли часть ниже нуля?": «должна, это опуски геометрии по требования что полигоны по периметры должны быьб утоплены минимум на метр вниз»
- 11:26, accepting the restated rules (drop kept, depth-correct pictures): «да, принимаю»
- 14:02, answering "смержить #570? картинки дошли?": «Да, все дошло» (read as an answer about the pictures, not a merge order)
- 2026-10-23 08:16: «Замерджи все что можно» → merged 08:18

Job-level verdicts after this stage (they concern #559–#566, quoted for context, because they judge the intake's source choice):
- 15:29: «бля все равно говно, почему нельзя сделать как на презе тут прям все читается и швы и количество»
- 16:06: «Да, теперь похоже панели принимаю, только почему внешняя стенка серая, когда как в презе должна быть синяя»
- 16:38: «Даже в двг написано Сендвич панель и рал, у нас почему ни сендвеча ни рала нормального»
- 17:44: «Пришли крайние результаты, пока я очень недоволен, простую задачу мусолим 6 часов»
- 18:44: «…Я дал геометрию, я дал расстояние на ID. Я дал примеры, где расписаны все ралы, все материалы. Нужно было просто сгенерировать пять диффузов … Зачем миллионы тестов и проверок, когда я просто попросил покрасить?…»
- 2026-10-23 01:12: «Пиздец день сегодня, пусть воркеры разберут переписку и косяки»

## 7. Proposed next tasks and hypotheses

Open roadmap issues checked with `gh issue list --label roadmap --state open` (#149, #298, #337, #349, #352, #371, #425, #426).

1. **Max Multi/Sub scene census adapter.** Move `read_max.py` + `publish_census.py` into `adapters/max/scene_census.py`
   (pymxs side) and a bpy/pymxs-free `dt_ai` census schema with `validate_scene`/`classify`. Output per node: tris/quads/ngon
   degrees, material tree (texmap/material split), per-ID faces + m², UV channels, bbox parity, collision-candidate
   classification. Rerun it on the hashed TEC26 and KPP1 copies and require byte-equal JSON with the job output.
   Tests import pure functions instead of exec'ing AST fragments. Value: high (every mid-poly texturing job starts
   here). Effort M. **Advances #149** (L1 sheets/L2 self-checks: the census is the input of both).
2. **Depth-correct Gate-image renderer.** Turn `render_depth.py` into `tools/blender/id_depth_render.py`: census JSON or FBX in;
   ID + shaded pair, UCX excluded, ±0.000 guide, explicit World, receipts with hashes. Make it the only allowed
   generator of human-facing ID pictures, and retire painter views. Value: high (it removes the false-triangle class).
   Effort S/M. **Advances #149**.
3. **Per-wall perimeter-drop check.** Generalise the AC04 measurement into `src/dt_ai/geometry/perimeter_drop.py`:
   identify outer shell walls, bottom-edge interval coverage at z ≤ −1.0 m, a per-wall verdict, fail-closed on
   unidentified walls. Wire it into the TEC26 build cards' QA. Value: medium (the user's rule from 11:20, now checked by hand per
   card). Effort S. **Advances #149** (L2 self-check).
4. **Intake: slide map from pptx facade albums.** A small reader (zip + `ppt/slides/*.xml` text + slide images) that
   writes `slide → building/АС → legend/RAL text` into the D049 `jobs/<JOB>/intake/` format. The task-intake procedure
   requires it whenever a pptx is staged. Value: high (the main downstream loss of this job). Effort S.
   Archive: no roadmap link (process/intake; partly covered by PR #576/D186).
5. **Job-only diff test scope.** Rule 49 exemption: a diff limited to `jobs/**` + `tests/jobs/**` (no `src/`, `adapters/`, `tools/`,
   conftest, pyproject) runs the affected tests + `tests/jobs/` only. Value: about 30 min per job-stage PR. Effort S
   (COORDINATION_RULES + `suite_slot.py` check). Archive: no roadmap link (harness).

Hypotheses for the hypothesizer:
- H1 **Census removes reopening**: claim: building cards that read `C:/x/tec26-oks/census/` did not open
  `04-09 Geometry Final.max` again. Metric: number of `dcc_batch.py max` calls on that file in #561–#566/#559 sessions
  (`state.db`). Threshold: 0 (or ≤ 1 per card, with a reason).
- H2 **Job-only diffs never fail the full suite**: metric: full-suite failures attributable to the diff on the last 20 PRs
  whose diff is `jobs/**` + `tests/jobs/**` only. Threshold: 0/20 → adopt task 5.
- H3 **A slide map at intake cuts rebuilds**: metric: build versions per building before user acceptance (TEC26: AC08 v010,
  AC07 v006, AC04 v003). Threshold: median ≤ 3 on the next mid-poly job that has a facade album.
- H4 **Depth renders end picture confusion**: metric: user questions about non-existent geometry ("треугольники",
  "клиппинг") per Gate picture batch. Threshold: 0 over the next 3 jobs using `id_depth_render`.
- H5 **Adapter parity**: metric: the per-node per-ID area difference between `adapters/max/scene_census.py` and the job JSON on the
  TEC26 + KPP1 copies. Threshold: ≤ 1e-6 m² on every node, identical node/ID sets.

## Open questions for the user

1. Should a facade album (pptx) count as the binding colour/seam source over DWG/PDF for every mid-poly texturing job, or
   only when you say so per job? (It decides whether task 4 becomes a gate.)
2. May job-only PRs (`jobs/**` + `tests/jobs/**`) skip the full suite (task 5), or do you want the 30-min run kept as
   a safety net?
