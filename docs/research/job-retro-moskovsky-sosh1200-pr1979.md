# Job retro: moskovsky-sosh1200 (PR #1979)

Research card t_34b9cc04, 2026-11-27. Read at `origin/main` after merge of PR #1979 (merged 2026-11-27 17:17 UTC).

## Summary

- Stage closed by #1979: site NPM **Ground v003 + MAF v002 + Flora v002** for «Школа на 1200 мест», г. Московский;
  cell `ground-npm`, trail `routes/site.md`. Geometry of Ground v002 and MAF v002 accepted by the user; the
  assembled site NPM package v001 is **diagnostic, `passed=false`** (no OKS, V003/V004/xview fails, 7 PNG > 3 MiB).
- Budget held: 103 707 tris of 180 000 (Ground 11 736 / GroundEl 47 344 + 12 / Flora 44 615).
- One Ground review round was rejected (v001: building hole, missing markings, split lawn); v002 accepted in one round.
- Agent wrote 12 job scripts (~1 350 lines: markings mesh, site assembly, ID-colour review, Flora build, tiled maps);
  all were archived to Drive, none moved into the engine. Three have no engine owner and recur on every site job.
- Active session time on 2026-11-26: ~5 h 20 min of work inside a 12 h 15 min span; ~7.7 h was the user away.
  The longest work blocks were MAF modelling (51 min x2) and MAF assembly + viz compare (69 min).
- Defects the user caught, not the agent: black Ground in the review copy (UDIM maps not connected) and
  opacity not visible in the viewport. Four "long still?" pings show missing progress visibility.
- Proposed: engine module for the markings mesh, a review-copy material self-check, site assembly into
  `agr package-npm`, and an ID-colour review copy in `agr open-review`. All advance #1969.

## Inputs and what was exercised

| input | status |
|---|---|
| `jobs/moskovsky-sosh1200/STATE.md`, `TASK.md`, `passport.json`, `maf/maf_discrepancies.md` at `origin/main` | read |
| PR #1979: 32 files, 5 commits (`gh pr view 1979 --json files,commits`) | read (file list + commits; diff only grepped for `Engine gap`: 0 hits) |
| Transcript `C:/Users/artsafro/.AGR-DigitalTwin_pilot/logs/transcripts/job-moskovsky-sosh1200-ground-npm-prnone-17b154a5-….jsonl` (21.9 MB, 4 754 records) | exercised by `C:/x/job-retro-moskovsky-sosh1200-pr1979/extract.py` (out of git): user messages, tool durations, errors, sub-agent launches, compactions |
| `C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/logs/transcripts/` | no matching file |
| `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200-scripts/original/` (12 scripts) | read (docstrings, line counts) |
| `docs/backlog.md` entries naming the job | grep: **none** |
| `jobs/moskovsky-sosh1200/pipeline/*.questions.md` | **none present** |
| 11-27 integration commits (874d5d4b, 3f593b67, 1ae7efb4, 31b84401) | commit headlines only; their session transcript was **not found**, so it is not measured |
| Evidence snapshot outputs (FBX, `.max`, validate reports) | **not_exercised** (numbers below are quoted from STATE.md, not re-measured) |

The transcript also holds a preceding environment stage for the same school (2026-11-24 12:47–19:29: near zone,
far zone from OSM, Kievskoe sh.). It is outside the #1979 scope; only the user's words from that part are quoted (section 6).

## 1. Requirement vs result

Sources: TASK.md "User decisions (intake 2026-11-26)" and the later decision blocks; STATE.md; passport.json.

| # | requirement | result | verdict |
|---|---|---|---|
| 1 | Flat relief at ±0.000 | Z 0 = ±0.000; absolute Baltic mark unknown (gap 3) | met (mark open) |
| 2 | Model with stadium, cut exactly by ГПЗУ (22 021.7 m²) | `uncut/` 4 580 tris and `gpzu/` 2 940 tris, both v003 | met |
| 3 | Budget 180k: Ground 50k / MAF 60k / Flora 70k | Ground 11 736, GroundEl 47 344 (+12 glass), Flora 44 615; total 103 707 | met |
| 4 | Ledger = source of type | 40 MAF + 13 planting positions from DWG tables; ledger wins in 4 named cases | met |
| 5 | Count/position from drawing blocks, differences listed with helpers + viz check | `maf_discrepancies.md`, 21 helpers; DWG→viz rigid fit RMS 0.30 m (precise subset 0.11 m) | met |
| 6 | Canopy ВСТ 1519/1 ×7 on hatch fills | 7 placed; canopies 4–7 turned 180° (lead assumption, accepted) | met |
| 7 | MAF sizes from manufacturer + viz dummies | compare to viz 0.1–0.3 m except listed items; sport by manufacturer DWG | met |
| 8 | Trees from A101, size unchanged | scale exactly 1.0; 9 species, 5 689 plants | met |
| 9 | Review scene after Ground and after MAF + ID-colour copy [D420] | done for Ground v001/v002/v003, MAF v002, site v001/v002 | met (open not verified, see 5) |
| G1 | No footprint hole, footprint = ID02 | v002 capped | met (after v001 rejection) |
| G2 | One lawn cover ID05 | v002 | met (after v001 rejection) |
| G3 | Markings separate mesh +8 / −10 mm, own material | separate mesh, UDIM 1010/1011 | partly: 74 MTEXT game glyphs not built; widths w/o DWG width assumed 0.05 m |
| G4 | Rubber split by colour from `_ резинаV1_1.dwg` | library 27 recoloured to RAL | met |
| G5 | Ultra-thin slivers: report count only | 187 tris < 1 cm (v002) reported | met |
| G6 | Shade-canopy spots → own ID | 8 spots → ID18 CompactedSoil | met |
| G7 | Textures | 2K, 37.9 px/m; bindings 19/22/42/23 and periods are proposals, no soil map | partly |
| M1 | Fences: perimeter 527 m inside ГПЗУ, sport 4 m, step 2.5 m | group E: 681 elements (341 posts …) | met |
| M2 | MAF atlas 512 with 4 new cells | atlas v008 (last free quadrant used) | met |
| M3 | Missing MAFs → model new, then add to library | drafts in #1985 catalogue; not accepted as library | partly |
| F1 | Астильба, хоста | not done by user order | not (deferred by user) |
| F2 | Hedge 5/m² (~4 300), дёрен 3, вейник 6; nothing outside ГПЗУ | placed | met |
| P | Deliverable package | ZIP `--allow-incomplete`: V001 no OKS, V003 skirt 0.018 m, V004 topology / 220 flipped, xview, 7 PNG > 3 MiB | **not** (`passed=false`) |
| P2 | Passport identifiers | address token, code 0000, ±0.000 mark open | not |

## 2. What worked and what failed

Worked (keep doing):
- **Decisions recorded at once in `TASK.md`** after every user answer (15:23, 15:53, 16:17, 20:03, 22:10). The
  11-27 integration and this retro could be rebuilt from TASK.md without the transcript.
- **Recommendation-first questions.** The agent asked with a proposal for each item; 6 of 23 user replies are just
  "по рекомендациям". Approval cost the user about one message per batch.
- **Freezing accepted geometry and proving it.** v003 changed only IDs and textures; `geometry-compare-v002.json` shows
  identical vertices/faces. Texture work did not reopen geometry review.
- **Parallel sub-agents per MAF manufacturer group** (A–E + atlas, 20:02–20:53): six groups finished in 51 min;
  each wrote a REPORT.md with tris vs target.
- **Rigid DWG→viz fit** for discrepancy checking (RMS 0.11 m on the precise subset). It turned the user's viz scene
  into a measurable reference, not an eyeball one.

Failed, with cause:
- **Ground v001 rejected (15:53).** Cause: the agent applied the route default (D251 footprint hole, split lawn covers) and
  left out stadium markings. The user's intake message did not mention them. The intake did not ask about the footprint,
  cover merging or markings, though all three are site-job variables.
- **First DWG inventory missed both ledgers** (10:32–10:39). The tables sit inside blocks away from the site (assistant
  15:20). The user had to point at the DWG "со спецификацией".
- **Black Ground in the site review copy (22:17, user screenshot).** Cause: the Ground covers sit on UDIM tiles, but
  the Max review material carried only colour. No self-check of maps before opening.
- **Opacity not visible in the viewport (22:27–22:32).** The agent tried physical-material cutout display and then
  switched to legacy Standard materials (Diffuse atlas + Opacity mask). In the end it could not verify the result in its
  own viewport and asked the user to look.
- **Package fails** (V003 skirt from markings inside `SM_Ground`, V004 flipped faces/smoothing in MAF, xview on merged
  GroundEl instances). Cause: the job-local `assemble_site_npm.py` merges in a way the validators reject. Three
  revisions (r1/r2 superseded) were spent inside the job instead of in the engine.
- **Group E sub-agent could not write its own report file** (20:15); the lead relayed it.

## 3. What the agent wrote itself

12 scripts, archived read-only at `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200-scripts/` (Git `5f5cf971`
original, `1ae7efb4` relocated). There are no `Engine gap:` markers in the PR diff (grep: 0), so the engine gaps are
implicit. Commit 31b84401 "Archive Moskovsky job scripts and remove route exemptions" removed them from the tree.

| script | lines | does | move to engine? | candidate module | effort |
|---|---|---|---|---|---|
| `markings_mesh.py` | 192 | sport/game markings from DXF polylines → closed mesh +8/−10 mm | **yes**: every school/stadium site needs this; the user asked for the same rule on 11-24 (env) and 11-26 | `tools/ground/markings.py` (or `dt_ai.ground.markings`) + adapter field | M |
| `markings_uv.py` | 69 | NPM UV + white sheet on the marking mesh | yes, with the above | same module | S |
| `assemble_site_npm.py` | 260 | Ground + GroundEl + Flora → one Ground FBX, shared pivot | **yes**: this is #1969 `export`; it should keep markings out of `SM_Ground` (V003) and keep instances (xview) | `agr package-npm` site mode / package tooling | L |
| `review_idcolor_max.ms` | 40 | `MS_REVIEW_ID` flat-colour Multi/Sub on review copy [D420] | **yes**: D420 makes this mandatory for every site review | `agr open-review --idcolor` (`tools/open_review_scene.py`) | S |
| `review_quads_blender.py` | 62 | QUAD review copy of Ground OBJ | yes, merge with the above | `agr open-review` | S |
| `npm_tiled_maps.py` | 76 | 2K diffuse maps spanning one Ground UV cell | maybe: overlaps the #1969 `npm` atlas derivation | `tools/materials` / ground atlas | M |
| `site_adapter_v002.py`, `uncut_adapter.py` | 118 + 79 | typed SPOZU adapter JSON (GPZU + uncut), footprint cap | partly: footprint cap / `base_id` / cover merge as adapter options of `tools/ground/build_ground_site.py` | `build_ground_site.py` options | S |
| `flora_points.py` | 144 | tree/shrub points, bed/hedge polygons from SPOZU DXF | yes, generic DXF → Flora input | `tools/flora` intake | M |
| `flora_place.py` | 107 | input + run of `dt_ai.placement.engine` | no: thin wrapper, engine already owns placement | — | — |
| `flora_build_blender.py`, `flora_atlas_apply_blender.py` | 119 + 83 | build placed Flora mesh, move UVs into atlas cells | partly: atlas apply duplicates `tools/flora/build_flora_npm_light.py` intent | `tools/flora` | M |

Measurement tools written inline (not as files): DWG→viz rigid transform search (seed pairs + nearest same-type
matching), viz scene census (200 top-level objects), and a v002/v003 geometry compare. The DWG→viz fit is reusable for any job
that has a visualisation scene. Candidate: `tools/inventory_scan.py`-style `agr compare-viz` (M).

## 4. Time

Only the 2026-11-26 part is in scope. Timestamps are UTC from the transcript. Durations are wall-clock between
messages; background sub-agents ran in parallel.

| phase | span | min | note |
|---|---|---|---|
| Intake: route requirements + DWG/PDF inventory agents | 10:29–10:40 | 11 | missed the ledgers |
| *user away* | 10:40–15:13 | 273 | wait |
| Viz scene inventory, ledgers found, decisions, job opened | 15:13–15:23 | 10 | 1 hook error (skill gate) |
| Ground v001 build + review + ID-colour copy | 15:20–15:53 | 33 | rejected |
| Ground v002 (cap, one lawn, rubber DWG, markings mesh) | 15:53–16:38 | 45 | accepted |
| Ground v003 (re-ID, textures) | 16:41–16:53 | 12 | |
| MAF intake (ledger, sizes, discrepancies) | 15:23–15:39 | 16 | parallel |
| Flora v001→v002 | 15:57–16:19 | 22 | parallel |
| MAF lead: library search + 2 pilots + fence kit | 15:56–16:47 | 51 | library hit only 1 article |
| *user away* (idle compaction) | 16:53–20:01 | 188 | wait |
| MAF groups A–E + atlas v008 | 20:02–20:53 | 51 | parallel, 6 agents |
| MAF assembly + viz compare | 20:52–22:01 | 69 | longest serial block |
| Site assembly + review | 22:09–22:15 | 6 | |
| Rework: black Ground (UDIM maps) | 22:17–22:24 | 7 | user-caught |
| Rework: opacity in viewport | 22:27–22:32 | 5 | 9 viewport captures, still unverified |
| Handover: `/handover` failed, manual steps, D416→D420 | 22:39–22:56 | ~17 | PR opened 22:56 |
| Integration on 11-27 (relocate evidence, archive scripts, route exemptions) | 10:16–10:57 | 41 | other session, transcript not found |

Tool totals from the transcript (whole file, 11-24 + 11-26): 261 tool calls, 23 min of main-thread tool time
(PowerShell 13 min = Max/Blender batch launches, Bash 4.7 min). Most of the work ran inside 21 background sub-agents,
whose transcripts are not in this file, so their tool time is **not measured**. The two idle compactions
(11-24 19:21, 11-26 20:01) cost no work time but erased mid-session context; TASK.md made up for it.

Dead ends: Ground v001 (~33 min); r1/r2 of the site package (superseded, `WHY.txt`); opacity display attempts
(physical cutout → legacy).

## 5. Harness and process problems

1. **PreToolUse skill gate** blocked `select_max_instance` until the `3dsmax-mcp-dev` skill was loaded (15:14). That cost one
   round trip; the gate is correct, but the skill was not preloaded for a job that the trail knows uses Max.
2. **`/handover` failed** (22:40, `session_co…` hook): it ran outside the repo directory; the steps were done by hand.
3. **Decision number collision**: D416 was already taken on main; renumbered to D420 at handover. There is no reservation step.
4. **Review copies opened without an open check.** "Открылась ли копия, я не проверял" appears 3 times (15:39, 15:47, 16:38).
   There was also no material/map check (the black Ground).
5. **Sub-agent write permission**: group E could not write REPORT.md.
6. **Route exemptions** for job scripts had to be removed in a later integration commit (31b84401). The job ran on
   job-local scripts the trail did not own.
7. **Intake checklist gap**: footprint hole vs cap, lawn merging and stadium markings were not asked at intake (cause of the v001 rejection).
8. **Progress visibility**: 4 status pings from the user (11-24 13:31, 14:59; 11-26 16:22, 21:16), all while background agents ran.
9. 11-24 environment part: `git commit` failed with "Author identity unknown" (12:58), an environment issue.

## 6. The user's own words (UTC, transcript)

Environment stage (11-24, same transcript, context only):
- 12:58 «По рекомендациям» · 13:31 «Долго еще?» · 13:53 «Принимаю» · 13:54 «Потом поставь здания примитивами, без детализации»
- 14:15 «…нужно добавить полосы и дороги на Киевское шоссе… школы сейчас стоят на асфальтовом покрытии, и слишком большой серый кусок… скреативить и сделать… дорожку… или клумбы»
- 14:59 «Долго еще?» · 19:21 «накинь только мультисаб чтобы я id видел» · 19:29 «Принимаю»

#1979 stage (11-26):
- 10:29 «Да, PR»
- 15:13 «…я нашел ДВГ со спецификацией… рельеф мы строим плоский. Ведомость озеленения мы берем из ДВГ… Объем только участок по ГПЗУ… можно отмоделить вместе со стадионом… потом мы по границе… отделим… Мне сцену надо открыть после того, как ты сделаешь граунд, и потом… после того, как ты сделаешь мафы.»
- 15:16 «2 выбираю» (the viz scene is `MOS_GP_26.11.2026.max`)
- 15:22 «Все по ведомости… она главная, она источник истины… расставляя по блокам чертежа… расхождения выпиши. Поставь… хелперы… навес ставишь по заливке… Деревья берешь из нашей библиотеки А101, не меняя их размер. Ветку подтверждаю.»
- 15:42 «Накинь мультисаб и запиши в решение… мне нужно… видеть через мультисаб разбивку на примитивных цветах» (→ D420)
- 15:53 **«Геометрию не принимаю. Нужно закрыть дырку здания… ID 2… разметку со стадиона тоже надо… мешем с отступом 8 мм… утапливая… на 10 мм… Есть небольшие моменты с ультратонкими полигонами, но их уже можно руками поправить… весь газон, он одинаковый… живая изгородь… тоже будет газоном»**
- 15:54 «…по мафам решим сразу же. Надо отобразить все заборы, ограждения и… типовые и индивидуальные мафы по ведомости.»
- 15:56 «Да, принимаю рекомендации… модели из МАФ ты должен смотреть из МАФа 101 и… из библиотеки на диске… ничего не проходит, тогда модели потом… добавишь в библиотеку.»
- 16:16 «…я одобряю… Стильбу и Хосту не делай пока что… 4300… Текстуры… берем их из текстур А101… Растения вне ГПЗУ не ставятся. Размер мы не меняем… чтобы текстуры не поехали.»
- 16:22 «Что там по мафам?» · 16:41 «Да, по рекомендациям» · 20:01 «по рекомендациям» · 20:30 «Делать по двг»
- 21:16 «Ну что там?» · 21:17 «И сравни потом со сценой для визов»
- 22:09 **«по рекомендациям, геометрию принимаю»** (MAF v002)
- 22:11 «расставь растения мафы и гп и 3 атласа и открой сборку»
- 22:17 (screenshot only: black Ground) · 22:27 «в открытой вцене подклбчи опасити на флору и опасити на мафы»
- 22:39 «Сам сохраню» · 22:44 «?»

## 7. Proposed next tasks

1. **Ground markings mesh in the engine.** Move `markings_mesh.py` + `markings_uv.py` into `tools/ground` as an
   adapter-driven stage: polylines by layer list, offset +8/−10 mm, closed mesh, its own material and UDIM tile, and the MTEXT
   glyph gap reported. Regression: replay on the sealed `school.dxf` and match the v003 marking mesh vertex count.
   Value high / effort M. **Advances #1969** (`quads`/`npm`).
2. **Review-copy material self-check before opening.** In `agr open-review` (`tools/open_review_scene.py`), read back
   every material of the copy: fail if a mesh with UDIM/atlas UVs has no bitmap, or if an opacity atlas has no Opacity
   slot. Print a map count per material. Also confirm the new Max process loaded the file. Value high / effort S.
   **Advances #1969** (`export` review evidence).
3. **ID-colour review copy as an `open-review` option [D420].** Port `review_idcolor_max.ms` + `review_quads_blender.py`
   to `agr open-review --idcolor`. Value medium / effort S. **Advances #1969**.
4. **Site assembly into package tooling.** Replace `assemble_site_npm.py` with a site mode of `agr package-npm`. Keep
   markings in their own object (V003), keep GroundEl instances (xview) and normalise MAF normals/smoothing (V004). Gate:
   rerun on the Moskovsky v003/v002/v002 inputs gives V003/V004/xview pass, with only V001 (no OKS) left. Value high /
   effort L. **Advances #1969** (`export`).
5. **Site intake checklist questions.** Add footprint hole vs cap, cover merging (lawn/beds/hedge) and stadium/sport
   markings layers to the `routes/site.md` intake, plus "ledgers may sit inside blocks off-site" to the DWG inventory
   step. Value medium / effort S. **Advances #1969**.
6. **DWG→viz compare tool.** Turn the rigid-fit + nearest-type matching into `agr compare-viz` with RMS output.
   Value medium / effort M. Archive: no roadmap link (could attach to #1500 MAF route if the user agrees).

Testable hypotheses:

| claim | metric | threshold |
|---|---|---|
| H1: The site intake checklist (task 5) removes the first Ground rejection | Ground review rounds to geometry acceptance on the next 3 site jobs | ≤ 1 round on ≥ 2 of 3 jobs (Moskovsky: 2) |
| H2: The review-copy map check (task 2) catches untextured copies before the user | user-reported "black/untextured" review copies | 0 on the next 5 review opens; check fires on the Moskovsky site v001 copy (replay) |
| H3: Engine site assembly (task 4) removes job-local package fails | validator fails other than V001 on the Moskovsky inputs | 0 (now: V003, V004, xview, PNG size = 4) |
| H4: The engine markings stage reproduces the accepted mesh | vertex/face count vs v003 marking mesh | identical, or ≤ 1 % with a documented cause |
| H5: Periodic progress lines from background agents cut status pings | user "долго ещё / что там" messages per job | ≤ 1 (this transcript: 4) |

## How it applies to this repository

- `routes/site.md`: intake questions (task 5); D420 is already linked.
- `tools/ground/build_ground_site.py`: adapter options for footprint cap, `base_id` and cover merge (now in `site_adapter_v002.py`).
- `tools/open_review_scene.py`: `--idcolor` and map self-check (tasks 2, 3).
- `tools/flora/`: DXF Flora intake and atlas apply (overlaps `build_flora_npm_light.py`).
- Package tooling behind `agr package-npm`: site assembly (task 4).
- `jobs/moskovsky-sosh1200/STATE.md`: open gaps 1–4 stay the job's own items.

## Open questions for the user

1. Is the 0.05 m default marking width (no DWG width) acceptable as an engine default, or must it always be a question?
2. Should the 74 MTEXT game glyphs be modelled (mesh text) or textured, as a rule for future site jobs?
3. For the site package: should markings be a separate object in the Ground FBX (fixes V003), or a separate GroundEl?
4. Does `agr compare-viz` (task 6) belong to the MAF route (#1500), or should it stay unlinked?

## Sources

1. `origin/main:jobs/moskovsky-sosh1200/STATE.md` (read)
2. `origin/main:jobs/moskovsky-sosh1200/TASK.md` (read)
3. `origin/main:jobs/moskovsky-sosh1200/passport.json` (read: `gaps`)
4. `origin/main:jobs/moskovsky-sosh1200/maf/maf_discrepancies.md` (read: header)
5. https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1979 (files, commits; diff grep)
6. Transcript `job-moskovsky-sosh1200-ground-npm-prnone-17b154a5-4655-4f67-82c2-9a5510f8c5f6.jsonl` (extracted by script)
7. `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200-scripts/original/` (docstrings, line counts)
8. `origin/main:docs/decisions.md` D420 (read)
9. https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1969 (read: acceptance)
10. `tools/ground`, `tools/flora`, `tools/open_review_scene.py` listings (read)
