# Job retro: vyatskaya-tow02 stage 2 — texture, review fixes, overlaps, export-v005 (PR #515)

## Summary

- Stage 2 of job `vyatskaya-tow02` (tower TOW02, ул. Вятская вл. 47–49) took the accepted mid-poly master (build-v013, PR #392)
  through texturing (OKS 013 run-strip atlas [D156]), the user's 3ds Max review fixes, glass cleanup, overlap fixes and the
  F8 builder fix to `export-v005` (35 407 faces: 35 271 quads + 136 tris, one material). PR #515 merged 2026-10-21T19:13Z.
- Wall clock 29 h 18 min over two sessions (2026-10-20T13:22Z → 2026-10-21T18:40Z); the agent was engaged only **≈ 5 h 10 min**
  (≈ 3 h 30 min session `3b2419ea`, ≈ 1 h 40 min session `dda7a500`). The rest was user review (80 min in Max), the user being
  away (4 h 26 min + night) and the user's own hand finish (≤ 4 h 57 min).
- Result: the user accepted the base ("ты неплохо справился с задачей, с этим можно работать ... базу и большую часть работы
  ты выполнил") but **finished the model by hand** — top floors under-cut / extra edges, balcony glass railings rebuilt, UV and
  colours touched. NPM derivation is not done (2 of 5 acceptance lines open).
- Main failure: the agent's own Blender "Overlapping Faces" check said **0**, an independent method found **23 pairs**, 3ds Max
  xView at 5 mm found **185 faces**. Root cause: an early wrong conclusion that xView tolerances can only be set in a dialog
  (they are exposed as `OverlappingFaces.tolerance` / `OverlappingVertices.tolerance`), so a home-made proxy replaced the
  user's real gate for ~2.5 h.
- What worked: parallel measurement subagents against the source, user rules turned into scripts within minutes
  (`clean_glass_blender.py` matched the user's hand result 787 vs 816 quads), and the reproducibility check
  (chain v013→v025 rerun bit-identical) that made the F8 fix a builder fix instead of a patch.
- Proposed: xView runner as a CLI (R17) and a Blender overlap checker calibrated against xView (R16), both `Advances #371`;
  move `resolve_tjunctions` / sliding walls / window-glass cleanup into the engine; NPM from the user's final FBX.

Sources (all read by me, this card): `origin/main:jobs/vyatskaya-tow02/STATE.md`, `object.json`; PR #515 body and file list
(`gh pr view 515`); `origin/main:docs/backlog.md` (P13, EG6, R15–R17); the two session transcripts
`C:/Users/artsafro/.AGR-DigitalTwin_pilot/logs/transcripts/job-vyatskaya-tow02-midpoly-pr392-3b2419ea-….jsonl` (14.9 MB; despite
the `pr392` name it starts 2026-10-20T13:22Z, after PR #392 was opened, and covers this stage) and
`…-pr515-dda7a500-….jsonl` (2.6 MB); 7 subagent transcripts under
`C:/Users/artsafro/.claude/projects/C--Users-artsafro--AGR-DigitalTwin-pilot/{07124eda…,dda7a500…}/subagents/`; previous retro
`docs/research/job-retro-vyatskaya-tow02-pr392.md`; `gh issue list --label roadmap`. Timeline extractor (out of git):
`C:/x/job-retro-vyatskaya-tow02-pr515/extract.py` → `A.txt`, `B.txt`. No web sources (not needed for a job retro).
`jobs/vyatskaya-tow02/pipeline/spec-v002.questions.md` exists but belongs to stage 1 (engine route, PR #392).
Transcript times are UTC; local time = UTC+2.

## 1. Requirement vs result

Acceptance lines of `jobs/vyatskaya-tow02/STATE.md` (object.json has no acceptance block; its `task` still says "mid-poly
master body by the engine (route hybrid)" — stale since the engine route was dropped 2026-10-20).

| Acceptance line | Verdict | Numbers / evidence |
|---|---|---|
| Body, decor, glass, openings as logical groups | **met** | 37 objects in build-v015..v030 (TOW02_body, *_glass, fins F01–F26, ac_*, louvre, coping, top, soffit); joined into one mesh only at export |
| Every level from the user's helpers built | **met** (stage 1) | 6 levels 0.04–79.24 m; unchanged in this stage except top/coping fixes |
| Openings as planes or windows, per facade | **met** | glass cleaned to user rule: body_glass 2 761 → 787 quads, top_glass 509 → 86; user's own hand result 816 quads (within 1 cm) |
| Mid-poly rules (quads, no doubles/T-junctions, normals) | **partly** | export-v005: 0 mismatched winding (6 418 reveal faces were wound inward since build-v013 and fixed), Overlapping Vertices 2 mm = 0 (Blender and xView), F8 T-vertices 134 → 0, 136 tris, 304 by-design boundary T-vertices; **xView Overlapping Faces 5 mm = 185 faces** (own check 0, independent 23 pairs) → fixed by the user by hand |
| NPM derived from the master | **not met** | textured (one material `M_Vyatskaya_Vl_47_49_013_Main_1`, UV 0–1, 0 zero-area UV faces) and joined into `SM_Vyatskaya_Vl_47_49_013_Main`; NPM naming / transform reset [D135] / triangulation / validate-delivery not done. Next per STATE: derive NPM from the user's `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx`, not from export-v005 |

Stage-specific asks (from the transcript), not in the acceptance list:

| Ask (time UTC) | Verdict | Numbers |
|---|---|---|
| Texture via the accepted atlas of OKS 013, windows as source types, walls/rest solid colours (10-20 13:38, 13:58) | **met after one rework** | build-v015 used a uniform 7-pane strip, pitch 1.0 m (assumption) — not the source types the user asked for at 13:58; build-v018: 31 source run strips, 77.25 px/m, 873 window faces, ray-cast vs source ≤ 1 cm (one run 1.5 cm) |
| Mullions, top-storey pane layout, balcony railings, louvre as in the source FBX (10-21 09:04) | **met** | v016: AC coping 50 mm + 4 posts (1 628 quads), railing glass shell 20 mm, louvre 271 blades + 18 crossbars + 286 rails; distances to source median ≤ 0.3 mm |
| Flat window = 1 quad, bend keeps segments, 90° corner = 6 points (10-21 09:53) | **met** | see table above |
| xView clean at 5 mm / 2 mm (10-21 10:13, 10:41, 12:58) | **not met by the agent** | xView: vertices 0, **faces 185**; user fixed by hand |
| Fix overlaps without deleting, move/embed ≥ 6 mm (10-21 10:52) | **partly** | moves: baskets −6.6 mm, railings 0–12 mm, soffit steps ≤ 22.7 mm, fins ≤ 2 mm; real xView still 185 faces |

## 2. What worked and what failed

### Worked (keep doing)

1. **Reference analysis before texturing.** Subagent "Analyse OKS 013 UV and atlas" (12 min) decoded the accepted atlas
   (4 baked orthographic elevations ~17.2 px/m + swatches, m/r binary) and showed it is not reusable 1:1 (window rows IoU
   0.57–0.70). The first textured build (v014→v015) took **6 min** of agent time (14:04–14:10).
2. **Parallel source measurements on review.** Three background subagents at 09:07 (mullions 26 min, balconies + louvre
   17 min, Max side-by-side captures 10 min) turned the user's screenshots into numbers (49 run types, fixed panes
   0.335–1.465 m, sash with own 5 cm frame, louvre rails 0.051 × 0.183 running 6 m). One question round (09:34, 3
   recommended options, all accepted) — no second review round on these items.
3. **User rule → script in minutes.** The user showed the glass cleanup by hand at 09:53; `clean_glass_blender.py`
   (117 lines) was written, debugged and run by 09:58 and matched the user's 816 quads with 787.
4. **Reproducibility before fixing.** The chain build-v013 → v019 → v023 → v024 → v025 was rerun from scripts and was
   identical; the body config was reconstructed (`CFG_TOW02`). So F8 was fixed in `build_stack` (sliding walls,
   `resolve_tjunctions`) and the chain rerun to v026–v030 — no hand patch of the finished master.
5. **Independent checker with its own method** found 23 pairs where the builder said 0 — it proved the builder QA wrong
   before the user had to.
6. **Rules from the user recorded at once** in STATE (1 cm skip tolerance, "no deleting, embed ≥ 6 mm", "weld only coincident
   seams", "only Overlapping Faces 5 mm and Overlapping Vertices 2 mm matter").

### Failed (with cause)

1. **Own overlap check instead of xView (the central failure).** 10:00–10:20 the first xView run used the default 0.01 m;
   the agent searched Max macros for a tolerance property, found none, and wrote "xView tolerances cannot be set from script
   (dialog only)". Everything after (diagnosis, fix chain, builder QA `xview-v004`) used a Blender proxy. Result: builder
   "Overlapping Faces 5 mm = 0" vs xView 185 faces. Cause: an unverified negative ("cannot") was written into STATE and never
   re-tested; `showInterface OverlappingFaces` would have shown `.tolerance` (it was found at 13:27 in 1 min).
2. **Texture v015 ignored the user's 13:58 instruction** ("типы взять с исходника") and used a uniform 1.0 m mullion pitch and
   an assumed 3.5 m transom. Cause: no window measurement of the source existed yet; the agent shipped an assumption marked
   ASSUMPTION instead of measuring first. Cost: a review round (09:04) and an atlas rewrite (30 min subagent).
3. **Reveal winding wrong since build-v013** (6 418 faces into the wall; Max split 6 298 edges on import) — not caught by
   stage-1 QA, found only on the first Max import. Cause: no readback in the target DCC in stage 1.
4. **Top floors and balcony railings** still needed the user's hand: under-cut geometry and extra edges at the top
   (`TOW02_top`, `build_top_blender.py`), railing glass that overlapped. Cause: these parts were fixed by moves under the proxy
   check; the proxy missed exactly these pairs (independent check: 3 opposite pairs at 69.52 / 76.32, 58 slivers at
   69.175 / 75.975). Detailed diff is issue #514.
5. **F8 post-hoc test failed** (`option_a_report.json`: 0 points merged) because the strip corners slide 5–50 cm along the
   wall; only the builder change worked. Cause: a 6 mm point-match assumption on a sliding geometry.
6. **The fix-chain subagent took 63 min** (10:53–11:56) incl. an API crash (ENOTFOUND at 11:21, resumed 11:25); the user
   asked "почему так долго?" at 11:42.

## 3. What the agent wrote itself

All in `jobs/vyatskaya-tow02/scripts/` (`Engine gap: EG6`, texture `EG4`), +2 861 lines in PR #515.

| Script (lines) | What it does | Move to engine? candidate / effort |
|---|---|---|
| `texture_atlas_blender.py` (739) | finds glass runs (faces joined by shared vertical edges), matches them to measured source run types, builds a strip library, packs strips + 13 solid swatches into one atlas, writes d/m/r PNGs and UV, face attribute `tow02_finish` | **yes, partly**: run detection + strip packing + swatch atlas → `src/dt_ai/uv/run_strip_atlas.py` (EG4); source-run measurement stays job input. **L** |
| `build_review_fixes_blender.py` (622) | AC basket coping + posts, railing glass shell, louvre blades/crossbars/rails, shaft caps, ledge | no — part-specific; keep as a pattern example (`docs/domain/patterns/`) |
| `clean_glass_blender.py` (117) | flat window → 1 quad, bends keep segments, 90° corner → 2 quads on one edge | **yes**: a generic "planar glass element cleanup" op → `src/dt_ai/geometry/glass_cleanup.py`. **S** |
| `fix_overlaps_blender.py` (782) | reveal winding, bow-tie reveals, non-convex caps, fin vs jamb, soffit steps into fins, railing inward, basket moves (each a named finding F6–F14) | split: winding fix + polygon overlap test (`overlap`, `_clip`, `newell`) → checker library **M**; per-finding moves stay job code |
| `join_export_blender.py` (148) | joins parts, welds only listed seam pairs, `skip_point_contacts` (no bow-ties), FBX export | **yes**: "seam weld by object pair + bow-tie guard" → `src/dt_ai/export/` **S** |
| `build_body_blender.py` (+453) | `sliding_walls`, `snap_upper_cols`, `resolve_tjunctions`, `split_ngon`, `seal_leftovers` for ring stacks | **yes**: T-junction resolution between stacked rings is generic for any ring-stack body → `src/dt_ai/geometry/ring_stack.py` with TOW02 rings as fixture. **M** |
| `xview_check.ms` (69) + `outputs/xview-v005/open_ovl.ms` | 3ds Max startup script: import FBX, run xView checkers, answer the "Disable xView" dialog, one JSONL line per checker; tolerances set via `OverlappingFaces.tolerance` | **yes** = backlog R17, CLI `dt qa xview`. **S** |
| `outputs/xview-v002/scripts/`, `outputs/xview-v004/scripts/`, `outputs/xview-v005/ovl_pairs_blender.py`, `outputs/icheck-v001/` | Blender-side overlap / winding / bow-tie QA and marker FBX | = backlog R16; only after calibration against xView (H1). **M** |

## 4. Time

Wall clock 29 h 18 min. Agent engaged ≈ 310 min. Phases (UTC):

| Phase | Time | Min | Note |
|---|---|---|---|
| Takeover after rotation, wait for user | 10-20 13:22–13:38 | 16 | |
| Texture plan: 2 questions (127 s, 143 s), UV analysis subagent 12 min | 13:38–14:04 | 26 | |
| Texture build v014 → v015, D156, renders sent | 14:04–14:10 | 6 | fast, but wrong window types (Failed 2) |
| User away / night | 14:10–07:41 | 1 051 | incl. 18:36 scene opened for the user (1 min) |
| Export to 3ds Max 2024, not triangulated | 10-21 07:41–07:44 | 3 | |
| User review in Max | 07:44–09:04 | 80 | |
| Review analysis: 3 parallel subagents, question | 09:04–09:37 | 33 | |
| v016 fixes + atlas rewrite (2 subagents), glass cleanup v017 by main | 09:37–10:07 | 30 | |
| **xView loop 1**: default tolerance, dialog, "cannot set tolerance" → diagnose subagent (29 min), scope narrowed by user | 10:00–10:48 | 48 | dead end: proxy check |
| User fix rules | 10:48–10:54 | 6 | |
| Fix chain v019–v025, export-v004 (subagent, API crash 4 min) | 10:53–11:56 | 63 | user: "почему так долго?" |
| Handover / takeover | 11:56–12:05 | 9 | `/handover` cannot be invoked by the model |
| F8 option A in builder, chain v026–v030, export-v005 (subagent) | 12:05–12:51 | 46 | |
| Independent check (26 min) ∥ **xView loop 2** in a separate Max (run 15 min, tolerance found 13:27, 185 faces, marker scene, Max hang 13:31) | 12:52–13:38 | 46 | |
| User finishes the model by hand | 13:38–18:35 | ≤ 297 | upper bound (user time not instrumented) |
| Experience transfer, STATE, PR | 18:35–18:40 | 5 | PR opened 18:40, merged 19:13 |

Where the agent time went: xView/overlap work ≈ 160 min (two xView loops 94 min + fix chain 63 min, partly wasted by the
proxy check) ≈ 50 % of engaged time; review-driven rework (texture + review fixes) ≈ 63 min; builder F8 fix 46 min;
texturing itself 6 min. Main-session tool time is small (Bash 576 s + 193 s); the long items were background subagents and
polling waits (PowerShell 242 s and 362 s waiting for xView files).

## 5. Harness / process problems

1. **Unverified negative written as fact** ("xView tolerances: dialog only") steered 2.5 h of work. No rule asks to re-test a
   "cannot" before it becomes a STATE fact.
2. **Proxy QA reported as the user's gate.** `xview-v004` reported "Overlapping Faces 5 mm 121 → 0"; the name implies xView.
   Rule needed: a check is named after the tool that ran it; xView numbers only from 3ds Max (now a STATE lesson, not a rule).
3. **Subagent hooks blocked the independent checker's own scratch writes** (4 denials 12:55–12:57: "read-only subagent: this
   command writes a file"; one "does not read src/dt_ai/geometry/"), then 2 bash-quoting failures (`unexpected EOF`) while it
   inlined the script — ~5 min and a fragile workaround.
4. **`sleep N; cmd` blocked** in two subagents (09:10, 11:35) — the harness wants Monitor/until-loops; subagent prompts do
   not say so.
5. **`/handover` cannot be invoked by the model** (11:58 `disable-model-invocation`); the agent must ask the user, costing a
   rotation round-trip.
6. **Hook gate `3dsmax-mcp-dev` skill** denied `list_max_instances` at 13:20 in the second session although the skill was
   loaded in the first — per-session skill gates re-fire after rotation.
7. **Network**: subagent "Build v016 geometry fixes" died on `ENOTFOUND` at 11:21; the main agent resumed it by SendMessage
   with a file-state summary (worked, 4 min lost).
8. **Auto-mode classifier** denied a PowerShell window-interaction script (10:39, "Interfere With Workloads") during xView
   dialog handling.
9. **SendUserFile path error** (09:17): relative path vs the session cwd `outputs/`.
10. **Tests not run locally** for PR #515 (`tests/test_vyatskaya_fins_output_guard.py`: clone lacks `shapely` / `dt_ai`
    install); CI only.
11. **Builder inputs live in ignored `outputs/`** (`measure-v00N/*.json`); the chain is reproducible only on this PC.
12. **Stale `object.json` `task`** (still "body by the engine, hybrid") — the job record contradicts STATE.

## 6. The user's own words (verbatim, UTC)

Session `3b2419ea`:
- 10-20 13:38 — "Я могу тебе дать атлас, который использовался на похожем домике. У них различия только в этажности. ...
  Ты можешь взять старую итерацию, проанализировать, какие UV лежат на каком меше, где эти UV лежат на атласе ... Префиксы,
  номеры, номер ОКС я тебе вот возьму из старого ... И вот использование за 7 дней 0000000 тоже не совсем понял, к чему ты
  это написал. ... принимаю рекомендации все, кроме тех, которые я там сказал."
- 10-20 13:43 (answer) — "…0200_Vyatskaya_Vl_47_49_02.fbx вот тут открой в отдельной сцене сними скриншот убедись возьми
  мелкое здание и разбери его меш и атлас"; OKS number: "Как у образца".
- 10-20 13:49 — "013 и презеапкустил mcp"
- 10-20 13:58 (answer) — "Я думал окошки сделать на атласе отдельными, сами стены в солид цвет и остальные элементы с
  солидные цвета только окошки показываем на атласе с рамой и белым стеклом, посколько они типовые, можно несколько типов на
  атлас положить и на них положить полигоны, типы взять с исходника по которому моделили"
- 10-20 14:04 — "Да"
- 10-20 18:36 — "дай мне сцену, чтоюбы я посмотрел как получилосб"
- 10-21 07:41 — "можешь не триангулировать закинуть в макс  2024 с  дифузкой атласа"
- 10-21 09:04 — "Проверил твою модель, в принципе, выполнено уже неплохо, материалы тоже выполнены неплохо, но есть немного косяков
  с импостами и с окошками. ... на надстройке ... на окнах разбежка импостов чуть другая. ... верхняя часть закрывается
  отливом и четыре вертикальные стойки по углам на изгибах. ... сделать shell стеклу окна и удалить верхний полигон ...
  жалюзи ... там нету горизонтальных слэбов, которые ты сделал. Там есть горизонтальные перемычки ... Скажи, как понял задачу."
- 10-21 09:06 — "все верно"
- 10-21 09:35 (answers) — "Ленты как в источнике", "Поперечины + рейки", "И то и то правим"
- 10-21 09:53 — "посмотри как я в максе сделал окошки ... на всех 4 угольных без изгиба окнах я оставил 4 точки ... на угловых изгибах
  я оставил сегменты ... угловые окна под 90 градусов ... я сделал им общую грань ... единый элемент с 6 точками, также
  далее надо бует сделать аттач всех кусочков лего и пронать через xn view ... если вылезут ошибки, отметить и решим как
  фиксить и из за чего они"
- 10-21 09:59 — "оставь как в исходнике"
- 10-21 10:00 — "ок, жду результат xView"
- 10-21 10:13 — "ты уверен что не зависнет? x vertices на 0,002 м проверяем а x overlapping faces на 0,005м"
- 10-21 10:20 — "ок, жду список ошибок"
- 10-21 10:39 — "как умпехи?"
- 10-21 10:41 — "мне нужна проверка только на overlapping faces и overlapping vertices и фикс геометрии под нее когдад определим ошибки"
- 10-21 10:48 — "...выводил все точки на 0,002 метра. И провел оверлаппинг вертекс. У меня 0 точек показало. Теперь я прогнал
  оверлаппинг faces, у меня показало 1000 фейсов. Основные фейсы у нас это оверлап верхней крышки парапета ... с стеклом ...
  на наших балкончиках ... на горизонтальный пояс ... на углах у нас точки там не велдятся ... тест-стыки на ступенчатых
  ... фасадах панелях."
- 10-21 10:52 — "Нет, скрывать процесс не нужно. ... где-то нужно подрезать геометрию с welded, где-то нужно просто ее подвинуть
  для того, чтобы был расстояние между полигонами больше 5 миллиметров. ... Лучше не обрезать, а утапливать. ... Жалюзи ...
  Лучше тоже не удалять, а попробовать разнести побольше грани. ... Перевернуть диагональ, это согласен. Сдвиг 6 мм, согласен."
- 10-21 10:54 — "ок, жду результат и да хочу после этого этапа"
- 10-21 11:42 — "почему так долго?"; 11:43 — "ок, жди ещё 15 минут"

Session `dda7a500`:
- 10-21 12:04 — "да, F8 вариант A, корзины оставить"
- 10-21 12:58 — "Ты проверь в максе через xn view"
- 10-21 13:20 — "Открой в максе новый файл с 23 парой"
- 10-21 13:31 — "что то макс завис"
- 10-21 18:35 — "Короче, я сам поправил модель. ... Оверлапы были на верхних этажах, там была недорезана геометрия, и были лишние
  эджи, которые мне я удалил. Плюс на балкончиках стекло, вот это стеклянное ограждение я переделал, для того, чтобы оно
  выглядело нормально и не было оверлапов. ... доработал текстуру, чуть-чуть подразвернул. Вот, поменял там цвета. ... окошки
  твои оставил, твою основную геометрию оставил. ... ты неплохо справился с задачей, с этим можно работать. ... базу, как
  бы, и большую часть работы ты выполнил. ... потом можно уже поставить на GitHub в план разбор этой задачи ... сравнить с
  тем, что у меня получилось ... сделать выводы из этой джобы"

## 7. How it applies to this repository

- `jobs/vyatskaya-tow02/scripts/` — generic parts listed in §3 are engine candidates (`src/dt_ai/geometry/`, `src/dt_ai/uv/`,
  `src/dt_ai/export/`); `jobs/REGISTRY.md` / `docs/agents/NAMING.md` name the new CLI if R17 lands.
- `docs/backlog.md` R15–R17 already describe the side-by-side renders, the xView-equivalent checker and the xView runner;
  this retro adds the calibration requirement (H1) and the tolerance fact (`OverlappingFaces.tolerance` settable by script).
- `.agents/skills/validate-delivery` (and `docs/domain/` validation file) — add: "Overlapping Faces / Vertices numbers count
  only from 3ds Max xView with tolerances set by script; a Blender proxy is labelled `proxy`".
- `docs/agents/CAPABILITIES.md` — 3ds Max xView via startup script is a verified route (≈ 2.5 min on 35 k faces); MCP bridge
  does not compute xView.
- `jobs/vyatskaya-tow02/object.json` `task` field is stale (engine/hybrid) — fix in #514 or the NPM card.
- Issue #514 (open) is the natural home for the export-v005 vs user-final diff.

## 8. Proposed next tasks (no GitHub issues created) and testable hypotheses

### Next tasks

1. **CLI `dt qa xview` (backlog R17).** Wrap `xview_check.ms` / `open_ovl.ms`: start a separate 3ds Max 2024, import FBX,
   set `OverlappingFaces.tolerance` / `OverlappingVertices.tolerance` (default 0.005 / 0.002), answer the dialog, write
   JSONL + the face/vertex index lists + a marker FBX; timeout and hang detection. Value high (the user's real gate), effort
   **S**. `Advances #371`.
2. **Blender overlap checker calibrated against xView (R16).** Port `fix_overlaps_blender.overlap` / `ovl_pairs_blender.py`
   to `src/dt_ai/` and calibrate on three fixtures with known xView counts (export-v004, export-v005 = 185 faces at 5 mm,
   the user's `0213_..._05.fbx`); report only as `proxy` until H1 holds. Value medium, effort **M**. `Advances #371`.
3. **Review #514 diff tool.** Per-part face diff of export-v005 vs the user's final FBX (moved / deleted / added faces per
   z-band and part) to quantify the hand finish. Value high (lessons with numbers), effort **S**. `Advances #149`.
4. **Ring-stack T-junction resolution into the engine.** Move `sliding_walls`, `snap_upper_cols`, `resolve_tjunctions`,
   `split_ngon` from `build_body_blender.py` to `src/dt_ai/geometry/ring_stack.py` with TOW02 rings as fixture (expect 0
   T-vertices, ≤ 1.4 mm moves). Value medium, effort **M**. `Advances #149`.
5. **Window-glass cleanup + seam weld ops.** `clean_glass` rule (1 quad / bend segments / 6-point corner) and
   `weld_seams` + `skip_point_contacts` as library ops. Value medium, effort **S**. `Advances #149`.
6. **NPM-OKS 013 from the user's final FBX.** Names `0200_Vyatskaya_Vl_47_49` / OKS 013 (package prefix 0213), transform
   reset [D135], triangulate, FBX, validate-delivery, xView via task 1. Value high (closes the job), effort **S/M**.
   `Advances #149`.
7. **Run-strip atlas generator (EG4).** Generalise `texture_atlas_blender.py`: input = measured source window runs JSON +
   swatch palette, output = atlas d/m/r + UV + coverage report. Value medium, effort **L**. `Advances #149`.
8. **Harness: subagent scratch + waits.** Let read-only subagents write to their own scratch dir; add Monitor/until-loop
   guidance to subagent prompts; rule "a 'cannot' found by search is re-tested by `showInterface` / help before it enters
   STATE". Value medium, effort **S**. `Archive: no roadmap link`.

### Testable hypotheses (for the hypothesizer)

| # | Claim | Metric | Threshold |
|---|---|---|---|
| H1 | A Blender overlap checker can reproduce xView Overlapping Faces | |proxy − xView| / xView on export-v004, export-v005, user final, tol 5 mm | ≤ 10 % on all three, and 0 ↔ 0 agreement on a clean file |
| H2 | The user's hand finish is concentrated in the top and the railings | share of changed faces (export-v005 vs `0213_…_05.fbx`) in `TOW02_top`, `top_glass`, `ac_railing_glass`, z ≥ 64.7 | ≥ 80 % |
| H3 | Running real xView (task 1) as the gate before reporting removes the user's overlap hand-fix round | user hand-fix rounds for overlaps on the next tower job | 0 (vs 1 here) |
| H4 | Measuring source window runs before the first atlas avoids the texture rework round | review rounds on window layout on the next textured job | 0 extra rounds (first atlas accepted for window layout; 1 here) |
| H5 | With tasks 1, 4, 5 in the engine, stage 2 of a comparable tower needs less agent time | agent-engaged minutes texture → xView-clean export | ≤ 150 min (vs ≈ 310 here) |
| H6 | Rerun-from-scripts check makes builder fixes cheap | time from decision to new export when the chain is bit-reproducible | ≤ 60 min (46 min here for F8) |

## 9. Open questions for the user

1. Is the user's hand finish (13:38–18:35 UTC) ≈ 5 h of work, or was part of that time something else? H5 and the value of
   tasks 1–2 depend on it.
2. NPM: derive from your final `for_placement/0213_Vyatskaya_Vl_47_49_05.fbx` only (as STATE says), and our export-v005 is
   archived — confirmed?
3. Is a Blender proxy of xView wanted at all (task 2), or is "xView in 3ds Max only" the permanent rule (then task 2 is
   archived and task 1 is enough)?
4. The colours you changed in the atlas — should the swatch palette of `texture_atlas_blender.py` take your values as the
   OKS 013 palette for the next tower?
