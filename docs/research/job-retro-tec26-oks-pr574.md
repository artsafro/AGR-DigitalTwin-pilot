# Job retro: TEC26-OKS AC08 pilot (PR #574)

Job `TEC26-OKS`, stage "pilot building AC.08 (Контейнер НКУ), VPM + NPM", issue #559, branch
`job/tec26-oks-pilot-ac08`, PR #574 (merged 2026-10-23 06:49 UTC, 23 commits, 72 files, +17 461 lines).
All times below are CEST on 2026-10-22 unless a date is given.

## Summary

- **Result.** The technical contract was met by run `pilot-v010` (`ed743ab`): 30/12 ribs per facade, counted on presentation
  slide 49 = DWG sheet, slide | VPM | NPM equal on 4/4 facades. `qa_packages` gave 40/40, and also 40/40 from the Drive ZIPs.
  Drive hashes 34/34, full suite 13373 passed. Artem accepted v010 as the reference at 18:06 («Да, похоже»).
  Still open: roof colour, outer outline and UCX triangulation (SINTEZ 2.3.17 fails in both profiles).
- **Cost.** From card creation (13:32) to the clean review (17:33) took 4 h 01 min, and the whole day from the 10:12 request
  was about 8 h. In that time we made 10 builds (v001–v010), went through 5 worker runs (177 min), 4 review runs (~22 min)
  and 3 full suites (one lost to a reclaim), and spent 25 min idle on provider rate limits. The 5 worker sessions made
  489 tool calls, 462 k output tokens and 83 M cache-read tokens.
- **Main cause.** The contract changed 6 times after the first build. The order was: geometry rebuild → colour only; no
  joints → KPP cassette joints; vertical joints only, with Artem's texture; a 0.60 m step → the sheet's rib count;
  frame 7004 → blue; DWG → the presentation as the authority. The presentation and the legend existed from the morning.
  Each change cost one build and one review, about 45–60 min.
- **What fixed it.** A machine count of ribs on the source slide's pixels, plus one acceptance picture (slide | VPM | NPM
  at the same scale, with the measured count under each panel). After that picture existed there were no more rejections.
- **Engine candidates.** `finish_map.py` (608 lines: legend gate, per-ID finish, ring cut), `qa_packages.py` (500), the
  facade-compare trio (`render_facades` / `joint_count` / `compare_facades`, 520 lines) and 9 verbatim KPP1 recipe copies.
  These should become one parameterised OKS colour pipeline in `src/dt_ai`.

Sources (all read by me, nothing from the web):
- the PR: `gh pr view/diff 574`;
- `origin/main:jobs/TEC26-OKS/{STATE.md,object.json,AC08/PILOT_REPORT.md}`;
- `docs/decisions.md` D169–D171;
- the kanban board `agr-pilot` (cards `t_e9cc2568`, `t_e4f28db7`, `t_0cae7834`, `t_2e18a13b`; `task_runs` and comments);
- the five worker sessions in `~/.hermes/profiles/dt-worker/state.db` (`local-c42021a9`, `18c0c02b`, `bdf95371`,
  `25aeb575`, `68afd397`), extracted with `C:/x/job-retro-tec26-oks-pr574/timeline.py`, which is out of git;
- the orchestrator chat in `~/.hermes/state.db` (session `20261021_225…`), used for the user quotes;
- the existing retros `docs/retros/2026-10-22-tec26-colouring-{claude,codex}.md`.

No JSONL transcript matching `*TEC26-OKS*` exists in `C:/Users/artsafro/.AGR-DigitalTwin_pilot/logs/transcripts/`, and
`agr-pilot/AGR-DigitalTwin/logs/transcripts/` does not exist. The Hermes `state.db` sessions were used instead.

## 1. Requirement vs result

The requirement is the STATE.md line: «Сначала одно здание целиком (mid-poly -> материалы -> VPM + NPM), после моей
приёмки остальные параллельно». It was refined by the scope note «геометрию менять не надо» and by D169–D171.

| Acceptance line (STATE.md / object.json / D169–D171) | Verdict | Evidence (numbers) |
|---|---|---|
| One building end-to-end, VPM + NPM | **met** | `SM_Nku_1.zip` + `0000_Nku_1.zip`, pilot-v010; Drive `559-tec26-oks-ac08-pilot-v010/` 34/34 hashes |
| Colour only: geometry, topology, UCX and IDs as in the source; one ring cut allowed at a joint | **met** | 1 ring cut at joint 12 (X = 33.3673), 19 quads → 38, +20 vertices on source edges, T-junctions 0; UCX/IDs unchanged on readback |
| Rib count per facade from the colour sheet (D169) | **met** | 29/29/11/11 joints (30/12 ribs) on the slide pixels, VPM and NPM; error ≤ 0.6 mm (VPM) / ≤ 3.6 mm (NPM, door facade) |
| Presentation is the authority; legend is binding (D171) | **met** | `finish_map.validate_legend`: 4 rows / 5 finishes; 10 legend mutations → 10/10 `ValueError` |
| Frame band blue RAL 5015 with a dark outline (D170) | **met** | 124 `Frame_RAL5015` polygons; 4 mm outline (VPM) / 8 mm (NPM) |
| Perimeter drop ≥ 1 m kept, plain finish below ±0.000 | **met** | 18 plinth polygons down to −2.047 m, RAL 7004 |
| KPP texel 1000 px/m on 4K UDIM | **met** | 999.99926–1000.00055 px/m on 38 triangles (reviewer, independent) |
| NPM: one 2048 atlas + separate opacity | **met** | d + o 2048 RGB, embedded bytes = files |
| SINTEZ AGR Checker | **partly** | VPM 62 / **4** / 54, NPM 38 / **5** / 29. Fails: 2.3.17 (UCX not triangulated), GeoJSON, district code `0000`, Ground, signature — all deferred "as KPP" |
| Human visual acceptance before the other buildings | **met (late)** | Rejected at v006 14:22, v006 14:59, v007 15:29, v008 16:06 (partly), v009 16:36/16:38; accepted v010 at 18:06 |
| object.json `unverified`: coordinates, project zero | **not** | Pivot, `Nku_1` address and code `0000` are placeholders (PILOT_REPORT open item 5) |
| object.json `unverified`: collision hull validity | **not** | UCX `Colizii_044` not triangulated, waiting for the user's decision |
| object.json `production_authorized: false` / `stage: intake` | **stale** | object.json was not updated by PR #574; it still says intake |
| PILOT_REPORT open questions (roof colour, outer outline, ribs even vs "as drawn" 200 mm) | **not answered** | Listed in `AC08/PILOT_REPORT.md` §"Открытые вопросы" |

## 2. What worked and what failed

**Worked (keep doing):**
- **Copying the KPP1 recipe.** With 9 script copies and `run_building.sh`, the first full package (v004, QA 31/31) was
  built 20 min after the run started (13:57 → 14:17).
- **The reviewer's mutation test.** In round 1, a readback where all 30 cassette triangles had been remapped to plain blue
  still passed `qa_packages` 33/33. That was a real false-clean. The fix (`f97eac6`) checks each delivered triangle
  against its source polygon and requires patterned-surface coverage. The joint-loss mutant now fails.
- **Test-first rounds with recorded RED.** `a2f7797` (collection error), `d86191f` (6 failed), `1ff6cf7` (21 failed),
  `e51f422` (12 failed). Every contract change produced a counterexample test (for example "v007 0.60 m readbacks fail
  all facades").
- **Counting on pixels against the source.** Slide 49 was counted on its pixels, the renders were counted the same way,
  and the result was put in one picture with the slide. This is what finally matched Artem's own way of checking ("как
  на презе — тут прям всё читается, и швы, и количество").
- **Evidence handling.** Drive evidence with SHA256SUMS each round (24/27/33/34) and a Drive-ZIP readback QA in v010. No
  LFS, small JSON receipts in git.
- **A reclaim lost no code.** v008/v009 had been committed before the manual reclaim at 16:40, and run 1355 continued
  from `360b2f8`.

**Failed (with cause):**
1. **The scope was not fixed before the build.** The card body said "VPM + NPM from mid-poly (KPP recipe)". The worker
   planned quadification and 3.9 m cuts (comment 13:59). «только раскрасить» arrived at 14:13, as an out-of-band note
   in the middle of the run. Cause: the orchestrator did not ask the user, and did not read the presentation, before
   fanning out. Both retros of 2026-10-22 agree on this.
2. **The 0.60 m step came from the texture image.** The orchestrator measured Artem's texture (7 joints every 600 px) and
   turned that into a rule (comment 15:01). v007 was built to it, review r2 passed it clean, and Artem rejected it at 15:29.
   The orchestrator admits this in its 15:29 comment. Cause: a parameter was inferred from a material sample, not from
   the facade drawing or slide.
3. **The DWG was used where the presentation was the authority.** v008/v009 were built against the DWG colour sheet
   (`sheet_facades.py`), although the presentation had been supplied in the morning. Artem at 16:36: «почему то
   сравнение с двг по матам хотя есть преза». This became D171.
4. **Green QA, red eye.** v004 (31/31) and v006 (33/33) passed every technical check while Artem saw «Не вижу швов» and
   «Панели неверные». The checks measured the spec, not the picture the user compares with. The acceptance picture only
   appeared in v010.
5. **Clean review on the wrong contract.** Review r2 (15:23–15:29) approved v007, 6 min before the visual rejection. A
   technical review cannot catch visual intent if it does not see the source slide.
6. **First density pass at 750 px/m.** v006 shipped 750 px/m instead of the KPP 1000 px/m without a decision. The
   reviewer caught it (P1-1), and it cost a block plus a 10 min wait for the user.

## 3. What the agent wrote itself

Line counts are from PR #574.

| Script | Lines | What it does | Move to engine? (candidate, effort) |
|---|---|---|---|
| `finish_map.py` | 608 | Finish per Multi/Sub ID from the Max dump; quad pairing; ID1 split at ±0.000; drop probe; `validate_spec` (density contract); `validate_legend` (legend → finish → RAL → texture); `ring_cut` / `plan_cuts` (pure-Python edge-ring cut at joint positions, fail-closed) | Yes: `src/dt_ai/materials/finish_map.py` (legend + ID mapping, **M**) and `src/dt_ai/geometry/ring_cut.py` next to `ring_stack.py` (**S**) |
| `qa_packages.py` | 500 | Package QA from FBX readback: names, budget, xView via the fast core, source-face ownership by containment/area, finish per triangle vs the source ID, patterned coverage, texel contract, `facade_joints_*`, `cuts_at_joints` | Yes: generic parts into `src/dt_ai/ops/` (source-ID finish check, patterned coverage) on top of `inv_xview_fast.py` / `inv_texel.py` (**M**) |
| `render_facades.py` + `joint_count.py` + `compare_facades.py` | 117 + 197 + 206 | Workbench facade renders of the VPM/NPM FBX at fixed px/m; count vertical joints on pixels; slide pixel count; one sheet slide \| VPM \| NPM at 200 px/m with the counts; exit 1 on mismatch | Yes, the highest value: `src/dt_ai/acceptance/facade_compare.py`. The user rule "no render without slide match" (17:41) makes it mandatory for every OKS (**M**) |
| `sheet_facades.py` | 130 | Reads the «Фасад … Цветовое решение» sheets from the DXF readback: field bounds, joint lines, step | Partly: a DXF facade-sheet adapter under `src/dt_ai/cad/` (**S**). Lower priority since D171 put the slide first |
| `dump_max_poly.py` | 68 | Dumps one Max layer (Editable Poly + collisions) to JSON from a staged copy | Yes: next to the dcc_batch Max adapters (**S**) |
| `build_master.py`, `qa_readback.py`, `run_building.sh` | 150 + 48 + 44 | Blender master from the dump; readback dump; one-command per-building run | Becomes the driver of the library pipeline (**part of L**) |
| 9 KPP1 copies (`vpm_uv`, `make_textures`, `make_npm_atlas`, `export_vpm`, `export_npm`, `export_safety`, `package_vpm`, `qa_master`, `run_agr_checker`) | 1 356 | The KPP1 recipe, copied with `new-case:` markers | **L**: one parameterised "OKS colour pipeline" (UDIM VPM + NPM atlas from a finish spec). This is now the second copy of the KPP1 recipe, and AC04–AC09 reuse the AC08 copy |
| `tests/jobs/test_tec26_ac08_pilot.py` | 1 002 | 115 focused tests, including synthetic counterexamples | Moves with the modules above |

No `Engine gap:` markers were written. The `new-case:` docstrings mark every file as job-local.

## 4. Time

These are wall-clock minutes from `task_runs` and session timelines. "Suite" means a waited-on full suite via `suite_slot`.

| Window | Min | What happened | Why |
|---|---|---|---|
| 13:32–13:57 | 25 | 4 Codex spawns, each `rate_limited` after ~1 min, on a 6 min cadence | Provider quota wall; the card switched to Claude only on the 5th try |
| 13:57–14:43 (r1321) | 45.5 | v001→v006. Plan for geometry work; scope note at 14:13 (colour only); joints note at 14:24; ~14 min suite wait (14:28–14:42); errors: missing `numpy`/`scipy` in Hermes python (×2), `int64` JSON keys, 2-D vs 3-D `cross` | Two contract changes in the middle of the run |
| 14:43–14:47 | 4 | Review r1: 2 × P1 (750 px/m; false-clean QA) | |
| 14:47–14:53 (r1340) | 6 | P1-2 fixed; blocked for the density decision | Needed the user's choice |
| 14:53–15:03 | 10 | Waiting for Artem (answered 14:59 + texture at 15:01) | |
| 15:03–15:22 (r1341) | 19.6 | v007: user texture, 0.60 m step, ring cut; RED 21 failed | 0.60 m came from the orchestrator |
| 15:23–15:29 | 6 | Review r2 clean (on the wrong contract) | |
| 15:29–15:38 | 9 | Follow-up card; duplicate card `t_e4f28db7` `spawn_failed` ×2 (branch held by worktree `t_e9cc2568`) | Two follow-ups were created for one rework |
| 15:38–16:40 (r1345) | 61.3 | v008 (16:08; panels accepted at 16:06, frame not), v009 (commit 16:22); suite 16:22–16:37 (~15 min); `docs/decisions.md` index test failed ×3 (D169/D170 rows) | Then **manual reclaim at 16:40**: new rules came at 16:37/16:39; the suite result was discarded |
| 16:40–17:25 (r1355) | 44.6 | v010: slide pixel count, legend gate, compare picture; RED 12 failed; decisions test failed ×2 (D171); suite 17:04–17:24 (~20 min, `sleep 400`/`sleep 380` polls) | Suite rerun required because `docs/decisions.md` (a shared file) was touched |
| 17:25–17:33 | 7.7 | Review clean | |
| 17:33–18:06 | 33 | Orchestrator delivery; stale images auto-sent at 17:36 (outside this card); acceptance at 18:06 | |

Totals:
- worker 177 min;
- full-suite waiting ≈ 49 min (28 % of worker time; 1 of 3 suites lost);
- rate-limit idle 25 min;
- user waits ≈ 10 min.

About 120 min of worker time went into builds that were later superseded (v001–v009).

## 5. Harness and process problems

1. **No intake step before the build.** The scope, the authority source (presentation vs DWG) and the rib-count rule were
   all settled mid-flight, through out-of-band notes. The user asked for exactly this rule at 15:05. It is drafted in
   PR #576 ("task intake before building — questions first, first piece, then fan out"), which is still OPEN.
2. **Orchestrator relays as an extra rule source.** The operator comments were rewritten as "Rule for ALL TEC26
   buildings", and one of them (the 0.60 m step) was wrong. Nothing checked a relay against the user's literal words.
3. **Reclaim discards a running suite.** The manual reclaim at 16:40 killed a run whose suite had been running for
   ~15 min, so the next run paid another 20 min. Suite receipts are not keyed to a commit that a later run could reuse.
4. **Touching `docs/decisions.md` forces a full suite.** It also failed the decisions-index test 5 times (D169/D170/D171
   rows) because the row format/path column was wrong. A job PR that records a decision pays ~20 min per round.
5. **Duplicate follow-up cards.** Both the reviewer (`t_0cae7834`) and someone else (`t_e4f28db7`) created the v008
   rework, and the second one failed to spawn twice on the held worktree. The dispatcher has no "branch already
   owned" check before creating cards.
6. **The environment keeps failing in the same ways.** Hermes `python` has no `numpy`/`scipy` (4 `ModuleNotFoundError`s
   across 3 sessions). The `/tmp/pytest_tmp` vs MSYS path confusion caused `FileNotFoundError` ×2. Polling for the
   suite with `sleep 400` blocked heartbeats.
7. **Review without the source picture.** Neither review round compared against the slide, so r2 passed v007.
   `REVIEW_CHECKLIST.md` has no "visual contract against the source sheet" item for facade or colour work.
8. **Evals cannot see Hermes sessions.** This is the same as in the #570 retro. The session data is in `state.db`, and
   this retro needed its own extractor again.

## 6. The user's own words

These are from the orchestrator chat (Telegram); the operator relays to the cards are noted where they add a rule.

- 10:12 — the task was set (colour the mid-poly from the Max scene, drawings, many buildings).
- 11:20 — «должна, это опуски геометрии по требования что полигоны по периметры должны быьб утоплены минимум на метр вниз»
- 14:12 — «Окей, там задача только раскрасить, геотмерию менять не надо и собрать атлас для нпм и юдимы для впм для каждого домика»
- 14:18 — «Почему задача занимает столько времени, если уже геометрия есть, просто взять материал и по требования развернуть»
- 14:22 — «Не вижу швов на панелях» (on the v004 render). The relay added «такой же тексель, как в VPM КПП» and «ниже ±0.000 без швов».
- 14:59 — «Панели неверные, должны быть вертикальные швы только, текстуру пришлю сейчас тебе и если не влезает то можно акуратно порезать через луп или ринг»
- 15:05 — asks for a harness rule: before starting, the agent questions him about the task so that "ускорить выполнение задачи"
  (it led to PR #576); 15:21 — «Да внеси в 2 репо в пай лот тоже».
- 15:29 — «бля все равно говно, почему нельзя сделать как на презе  тут прям все читается и швы и количество» (v007)
- 16:06 — «Да, теперь похоже панели принимаю, только почему внешняя стенка серая, когда как в презе должна быть синяя» (v008 → D170)
- 16:36 — «Опять неверно, и почему то сравнение с двг по матам хотя есть преза» (v009 → D171)
- 16:38 — «Даже в двг написано Сендвич панель и рал, у нас почему ни сендвеча ни рала нормального»
- 17:42 — «Не знаю, я посмотрел картинки которые пришли, удачного результата не вижу, мб мне что то не то отправили»
  (the auto-push had sent stale sheets)
- 17:44 — «Пришли крайние результаты, пока я очень недоволен, простую задачу мусолим 6 часов»
- 18:06 — «Да, похоже» (v010 accepted as the reference for the other buildings)
- 18:44 — «…Нужно было просто сгенерировать пять диффузов. И пять диффузов, из них раскидать часть сначала на Udemy, потом из
  этих Udemy собрать Atlas, все. Что в этом такого сложного? … Зачем миллионы тестов и проверок, когда я просто попросил
  покрасить? … Агент очень долго проверял, очень долго все делает. И еще делает неправильно.»
- 10-23 01:12 — «Пиздец день сегодня, пусть воркеры разберут переписку и косяки» (this retro series).

## 7. Proposed next tasks and hypotheses

Open roadmap issues: #149 (capability roadmap NPM/VPM, L1 sheets / L2 self-checks / L3 verify), #298, #337, #349,
#352, #371, #425, #426. None is TEC26-specific. Library and acceptance work maps to #149.

1. **Facade acceptance picture as a library op** (`src/dt_ai/acceptance/facade_compare.py`). Port
   `render_facades` / `joint_count` / `compare_facades` into one bpy-free compare plus a headless render step. The input
   is a source sheet or slide image, its scale and the facade order; the output is a slide | VPM | NPM sheet with
   pixel-measured counts, exit 1 on mismatch. Make it a required artifact before any OKS colour review.
   Value high / effort **M**. `Advances #149` (L2 self-check).
2. **OKS colour pipeline library.** Replace the 9 KPP1 copies plus `build_master` / `run_building.sh` with one
   parameterised pipeline: finish spec → UDIM VPM → NPM atlas → package → readback QA. Reuse the #546 atlas packer.
   AC04–AC09 and the next site then run from config, not from copies. Value high / effort **L**. `Advances #149`.
3. **Finish map and legend gate in `src/dt_ai/materials`, ring cut in `src/dt_ai/geometry`.** Port `validate_legend`,
   the per-ID finish assignment with the ±0.000 split, and `ring_cut` / `plan_cuts` with their tests. Value medium /
   effort **M**. `Advances #149`.
4. **Source-ID finish QA in `src/dt_ai/ops`.** Promote the per-triangle "delivered finish == source ID mapping" check and
   the patterned-coverage rule, so a remapped readback can never pass vacuously. This repeats the reviewer's P1-2 as a
   library contract. Value medium / effort **S**. `Advances #149`.
5. **Reclaim-safe suite receipts.** `suite_slot` writes a receipt keyed to the commit SHA and the tree hash, and a
   later run on the same SHA reuses it instead of re-running. A reclaim does not delete it. Value medium (~15–20 min
   per reclaim or rerun) / effort **S**. `Archive: no roadmap link`.
6. **Decisions without a full suite.** Either a dedicated affected-test set for `docs/decisions.md` (the index test plus
   the referenced tests), or the rule "decisions land in a separate docs PR by the orchestrator". Value medium
   (~20 min per round) / effort **S**. `Archive: no roadmap link`.
7. **Review checklist item "visual contract against the source sheet"** for colour or facade tasks. The reviewer opens
   the compare picture and the slide, and returns changes if there is no picture. Value medium / effort **S**.
   `Archive: no roadmap link`.
8. **Hermes python dependencies.** Either `numpy`/`scipy`/`PIL` in Hermes's own interpreter, or an AGENTS note: "use
   `uv run python` for probes". Value low / effort **S**. `Archive: no roadmap link`.

Hypotheses for the hypothesizer:

- **H1 (intake).** With the PR #576 intake step (questions + authority source settled before the first build), the
  number of user contract changes after the first build of an OKS colour card is ≤ 1 (AC08: 6).
  Metric: operator "Rule for ALL …" / user correction comments after the first `review_requested`, counted per card from
  `task_comments`. Threshold: ≤ 1 on the next 3 colour cards.
- **H2 (compare picture first).** Cards that send a slide | VPM | NPM picture with every review request get ≤ 1 visual
  rejection per building (AC08 before the picture: 4 rejections; after: 0). Metric: user rejections in the orchestrator
  chat per building, for AC04/05/06/07/09 (cards `t_223eb7bb`, `t_850845ab` etc.). Threshold: ≤ 1.
- **H3 (suite cost).** With receipts reused on the same SHA and decisions kept out of job PRs, full-suite waiting per job
  PR is ≤ 20 min (AC08: ~49 min, 3 suites). Metric: summed `suite_slot` wall time per PR from session timelines.
  Threshold: ≤ 20 min, and ≤ 1 full suite per PR.
- **H4 (library reuse).** After task 2, a new OKS building from a finished finish spec reaches QA-PASS packages in
  ≤ 20 min of worker time (AC08 v004 took 20 min from copies; AC04 build-v003 is the comparison). Metric: run minutes
  until the first `qa_packages` PASS. Threshold: ≤ 20 min, with zero new scripts under `jobs/`.
- **H5 (environment).** After task 8, `ModuleNotFoundError` for numpy/scipy/PIL appears 0 times per job session
  (AC08: 4 across 3 sessions). Metric: timeline extractor error count. Threshold: 0.

## Open questions for the user

1. AC08 PILOT_REPORT items still need an answer, and they decide AC04–AC09 too. Should the roof (ID1) be blue 5015 or
   7004? Is the outer outline needed? Should the ribs be spaced evenly, or "as drawn" (200 mm from the left with a
   58/38 mm remainder)? Should the UCX be triangulated for SINTEZ 2.3.17?
2. Should `jobs/TEC26-OKS/object.json` move from `stage: intake` / `production_authorized: false` to the pilot-accepted
   state? Or is the job object only updated at the end of the whole job?
3. The cheapest single next step is proposal 1 (the compare picture as a library op) or proposal 5 (suite receipts).
   Which one first?
