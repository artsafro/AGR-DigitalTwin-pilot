# Скелеты сценариев — читать первым для любой работы (job)

**Кратко.** Агент работает «как скальпель» [D324]: у каждого сценария (профиль × объект, ячейка
`docs/scenarios/scenarios.json`) есть неизменный **скелет** — упорядоченные этапы, каждый вызывает уже существующую
команду или ядро. Под задачу агент **настраивает** скелет одним файлом `jobs/<ID>/skeleton.json` и при нехватке
пишет **несколько маленьких скриптов** в `jobs/<ID>/hooks/`, подключая их к этапу (до / после / вместо пробела).
Свою цепочку скриптов вместо скелета не пишет: ревьюер возвращает такой PR на доработку, он не вливается [D325].
Скрипты, повторившиеся в 2–3 работах, раз в неделю собирает отдельная задача, Артём видит сводку, и только там
они переходят в скелет [D326]. Старые скрипты сданных работ оставлены без изменений, помечены историческими и
скрыты из поиска агента; duplicate_guard их по-прежнему сканирует [D327]. Исторические и старые — только пути,
замороженные на срезе #1546 (`job_scripts_baseline.txt`), а не целые папки: новый скрипт в старой работе
(`jobs/KPP1/<задача>-<issue>/`) видим и проверяется.

Machine-readable source: [`skeletons.json`](skeletons.json) (stages, owners, entry names, hook points).
Check: `uv run python tools/architecture/skeleton_guard.py [--job jobs/<ID>]` (exit 0 clean, 1 violations, 2 bad input).
Scenario cards keep the rules and evidence: [oks-vpm](../scenarios/oks-vpm.md),
[ground-npm](../scenarios/ground-npm.md), [ground-vpm](../scenarios/ground-vpm.md), [oks-npm](../../routes/npm-oks.md).

## Таблица скелетов (сценарий → этапы → команда/ядро)

Каждый этап принимает хуки `before` и `after`; хук `gap` разрешён только на этапе-пробеле (нет общей реализации).
Общее для всех ячеек: `blender-run` — запуск Blender без окна, `src/dt_ai/core/blender_runner.py` (`run_blender`).

### `oks-vpm` — ОКС, ВПМ

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `sources-dwg` приём чертежей | `tools/methods/body/plan_from_dxf.py` (после `dwg_to_dxf.py`) |
| 2 | `inspect` паспорт, PartsList, Gate 1 | `agr inspect --manifest JOB.json` |
| 3 | `body` бадик, окна, капсулы, крыша | AGR Tools этапы 1–4 (`body_core`, `windowgen_core`, `capsule_core`, `roof_core`) [D250]; разбиение [D336]; Сетка бадика: [правила BM-01…BM-14](../research/body-modelling.md#5-правила) (#1618) |
| 3a | `body` → вставка ограждения по измеренной оси парапета | [`agr railing`](../procedure/node-r3-fence-railing-gates.md#shared-headless-builder), отдельная геометрия, не приваривать к BODY [D336]; плоскость opacity только в лестнице бюджета НПМ |
| 4 | `mesh-quality` качество сетки в конце `body` (observe, только запись) | `tools/qa/mesh_quality_observe.py stage` → `mesh_quality.json` [#1739] |
| 5 | `udim` материалы и UDIM | AGR Tools этапы 5–6, `udimtile_core` |
| 6 | `vpm-uv` UV ВПМ | `tools/blender/vpm_uv.py` [D320] |
| 7 | `ucx-oks` коллизии | `adapters/max/agr_tools/ucx_core.py` |
| 8 | `master-qa` мастер до экспорта | `tools/qa/master_topology.py` [D312] |
| 9 | `readback` экспорт и чтение | `tools/blender/fbx_readback.py`, `dt qa xview` [D152] |
| 10 | `verifier` проверка VLM перед показом Артёму (observe) | `tools/blender/verifier_views.py` (6 видов) → `tools/qa/verifier.py` → `verifier.json` [#1577] |
| 11 | `package-vpm` пакет | `agr package-vpm` → `package_core._write_zip` |
| 12 | `validate` проверка пакета | `agr validate` (`tools/qa/validate_package.py`) |
| 13 | `checker` SINTEZ | `agr checker` (`tools/qa/sintez_checker.py`) |
| 14 | `geojson` GeoJSON | пробел |
| 15 | `light-fbx` `_Light.fbx` | пробел |

### `oks-npm` — ОКС, НПМ (`routes/npm-oks.md`)

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `inspect` | `agr inspect --manifest JOB.json` |
| 2 | `body` | AGR Tools этапы 1–4 / `dt_ai` ops для поддержанных случаев; разбиение [D336]; Сетка бадика: [правила BM-01…BM-14](../research/body-modelling.md#5-правила) (#1618) |
| 3 | `mesh-quality` (observe, только запись) | `tools/qa/mesh_quality_observe.py stage` → `mesh_quality.json` [#1739] |
| 4 | `brick-seams` кирпичные швы | пробел |
| 5 | `derive-npm` ВПМ → НПМ | `agr vpm-to-npm` (`dt derive atlas`, затем `dt derive npm`) |
| 6 | `master-qa` | `tools/qa/master_topology.py` |
| 7 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 8 | `verifier` (observe) | `tools/blender/verifier_views.py` → `tools/qa/verifier.py` → `verifier.json` [#1739] |
| 9 | `build-manifest` манифест выпуска | `agr build-manifest record` |
| 10 | `package-npm` пакет | `agr package-npm` → `package_core._write_zip` |
| 11 | `validate` | `agr validate` |
| 12 | `review-scene` сцена для приёмки | пробел |
| 13 | `checker` | `agr checker` |

### `npm-to-vpm` — existing NPM -> VPM (OKS cells `oks-npm` -> `oks-vpm`)

| # | Stage | Shared owner / command |
|---|---|---|
| 1 | `npm-ids` | `agr npm-ids SOURCE NEW_OUT --profile facade`; `tools/library/npm_ids.recover` reuses `maf_atlas_cells.segment`; skip only with an existing valid `npm_table.json` |
| 2 | `npm-udim-fit` | `npm2vpm_core.udim_fit_gate`: world metres, 4096 tile, 512-1706 px/m, region extent / texel / straddle per ID; STOP before conversion writes on non-fit, ask one grouped question with seam cuts / extra tiles / allowed density / other |
| 3 | `npm-to-vpm` | AGR Tools `npm.to_vpm`, `npm2vpm_core.plan`: `regions` without table, `table` with `npm_table.json`; core plan mode is read-only, not a native VPM certificate |
| 4 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview EXPORTED --out NEW.json`; topology, UV, materials, transforms |
| 5 | `checker` | `agr checker`; no checker/package on a blocked conversion plan |
| 6 | `package-vpm` | `agr package-vpm` -> `package_core._write_zip` after required approvals |
| 7 | `validate` | `agr validate` on the actual package |

Each stage retains the standard `before` / `after` hook points (one named stage,
no parallel conversion chain); no `gap` hook replaces a shared owner. One config:
`jobs/G22/npm2vpm-1630/skeleton.json`. IDs from atlas cells are provisional layout
labels, **not** library-material approval. Unresolved/mixed/straddling faces are
listed with source indices and remain ID0; they block conversion. JSON mode writes
`mesh_ids.json` + `id_table.json`; FBX mode adds a native `.blend` copy only when
the assignment and preflight are complete. Exit 1 = diagnostic/blocked, 2 = invalid
input or execution failure; neither is a pass. Prior delivered packages stay intact.
An explicit cleanup approval records exact source polygon drops on a new copy,
never a general geometry repair. A selected seam policy does not waive mixed
material boundaries, singular UV metrics, texel bounds or native readback.

### `vpm-to-npm` — принятая ВПМ → НПМ по практике Артёма (#1737)

ВПМ первична, НПМ выводится из неё; бадик не перестраивается и не правится, ProOptimizer не используется
(Артём 2026-11-21). Карточка: [vpm-to-npm](../scenarios/vpm-to-npm.md).

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `tris-count` треугольники ВПМ до всего | `uv run python tools/derive/vpm_to_npm.py --job jobs/<ID> --out NEW_DIR` (`vpm_npm_core.count_tris`) |
| 2 | `remove-interiors` интерьеры — всегда | `vpm_npm_core.remove_interiors`: внутренние стенки капсул / интерьерные UDIM из `config.interiors` (явно, пустые списки = нет) |
| 3 | `atlas` атлас НПМ, вся геометрия на атлас | `agr vpm-to-npm` → `npm_atlas.py --copied-udims --glass-white` + `export_npm.py` |
| 4 | `glass-merge` стекло одним объектом на белом | Хук мастер-копии объединяет стекло; `export_npm.map_white_glass` проверяет белую область и переносит UV |
| 5 | `budget-ladder` лестница бюджета | `vpm_npm_core.budget_ladder`: только пока выше бюджета, по порядку цилиндры → плоскости opacity (ограждения, кондиционеры) → плоскости окон/витражей; отчёт ran / skipped / missing |
| 6 | `master-qa` | `tools/qa/master_topology.py` |
| 7 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 8 | `verifier` (observe) | `tools/qa/verifier.py` → `verifier.json` |
| 9 | `package-npm` | `agr package-npm` → `package_core._write_zip` |
| 10 | `validate` | `agr validate` |
| 11 | `checker` | `agr checker` |
| 12 | `review-scene` | пробел |

Бюджет по умолчанию — `standards/NPM_STANDARD.yaml` `oks_triangles_per_fbx_max` (150000); шаг лестницы, нужный
при превышении, но не поданный хуком, — `missing`, а не «сделано».

### `oks-npm-lite` — ОКС, упрощённая НПМ

Нет карточки сценария: единственный этап `lite-route` — пробел; после решения пользователя ячейка берёт этапы `oks-npm`.

### `ground-npm` — Ground + МАФ + Флора, НПМ

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `sources-ground` приём СПОЗУ | `tools/source/inspect_ground_dxf.py` |
| 2 | `surfaces` плоский Ground | пробел (кирпичики `src/dt_ai/geometry/ground_cake.py`) |
| 3 | `quads` квадраты и швы | `dt ground v015` только для Ватутино; `ground_quads.py` |
| 4 | `library` МАФ и Флора, атласы | `tools/materials/atlas_maf.py`, `dt_ai.materials.flora` |
| 5 | `maf-light` лёгкий МАФ | пробел |
| 6 | `flora-star` звёзды Флоры | пробел |
| 7 | `placement` расстановка | `uv run python -m dt_ai.placement.engine` |
| 8 | `optimise` бюджет НПМ (без ProOptimizer) | пробел |
| 9 | `master-qa` | `tools/qa/master_topology.py` |
| 10 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 11 | `verifier` (observe) | `tools/qa/verifier.py` → `verifier.json` |
| 12 | `package-npm` | `agr package-npm` |
| 13 | `validate` | `agr validate` |
| 14 | `checker` | `agr checker` |

### `ground-vpm` — Ground + МАФ + Флора + UCX, ВПМ (порядок [D293], рельеф последним)

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `sources-ground` | `tools/source/inspect_ground_dxf.py` |
| 2 | `zero` граница и нуль | пробел |
| 3 | `surfaces` | пробел (кирпичики `ground_cake.build_flat`) |
| 4 | `quads` | `dt ground v015` только для Ватутино |
| 5 | `ground-textures` ID и текстуры | пробел |
| 6 | `relief` проекция на рельеф | пробел (кирпичики `ground_cake.project_z`) |
| 7 | `skirt` юбка | `agr ground` только замороженный Ватутино |
| 8 | `ucx-ground` коллизии Ground | пробел (прецедент `tools/blender/ucx_build.py`) |
| 9 | `library` | `tools/materials/atlas_maf.py`, `dt_ai.materials.flora` |
| 10 | `placement` | `uv run python -m dt_ai.placement.engine` |
| 11 | `derive-npm` | `agr vpm-to-npm` |
| 12 | `master-qa` | `tools/qa/master_topology.py` |
| 13 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 14 | `verifier` (observe) | `tools/qa/verifier.py` → `verifier.json` |
| 15 | `package-vpm` | `agr package-vpm` |
| 16 | `validate` | `agr validate --ground-area-m2` |
| 17 | `checker` | `agr checker` после визуальной приёмки |

### `library-publish` — своё в библиотеку AGR (МАФ, Флора, окна, крышное оборудование) [D361], [D368]-[D371]

Одна команда `agr library publish BATCH --kind maf --evidence DIR` проходит этапы 1–6; затем на «ок» Артёма
`agr library accept NAMES --words "..."`, на отказ `agr library reject NAME --words "..."`. Подробно:
[`docs/library/PUBLISH.md`](../library/PUBLISH.md), карточка [library-publish](../scenarios/library-publish.md).

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `intake` приём копии партии | `tools/library/publish.py` `intake_batch` (каждый файл — объект или отброс с причиной) |
| 2 | `identify` дубль / вариант / новый | `identify_object` по `library/assets/maf_unified.json`; `assets_library`, `intake_identify.dims_check` |
| 3 | `name` библиотечное имя [D369] | `library_name` (`assets_library.propose_maf_name`, translit, ё=е) |
| 4 | `qa` ВПМ и НПМ | `qa_object` на `tools/blender/fbx_readback.py` + `twinqa.maf_checks.maf_findings` |
| 5 | `register` версия vNNN + черновик [D370] | `register_version` → `AGR-assets/<kind>/<name>/vNNN/`, `library/published/catalogue.json` |
| 6 | `sheet` лист Артёму, accept/reject [D371] | `write_sheet`, `accept_records`, `reject_record` |

## OKS modelling split [D336]

Stage `body` of `oks-vpm` and `oks-npm`, all OKS buildings; the rule itself is the row [D336] in
`docs/decisions.md`, its machine form is `stages.body.modelling_split` in `skeletons.json`.

- Inset elements (separate, cut into the body, own clean quads, not welded into the body):
  `windows`, `stained_glass`, `roof`, `flashings` (roof and window), `posts`.
- Texture, not modelled: `panels` (seam in the texture/UV).
- Per project: `plinth` = `one_with_body` or `inset`; the final split follows the project, its textures and
  texturing convenience.
- Job report: one line, checked by `skeleton_guard.modelling_split_problems`:
  `Modelling split [D336]: plinth=<one_with_body|inset>; inset=<parts>; texture=<parts>; reason=<why, for this project>`.

Master/QA checks on these parts are element-wise; no check may require welding inset elements into the body:

| Check | How it sees inset elements |
|---|---|
| `tools/qa/master_topology.py` (`master_topology_core.check`) [D312] | one row and one verdict per object; quads/n-gons per element |
| `tools/qa/body_layout.py` | per named `--part`; a window/roof/post element is its own part |
| `dt qa xview` [D152] (`xview_gate.part_gate`) | per part; inside one part an inset element keeps its vertices off the body's (embed/offset, as decor [D199]) so the 2 mm overlap count stays 0 - never by welding |

## Verifier step before showing Artem (#1577, observe mode)

`oks-vpm`, `oks-npm` (#1739), `ground-npm` and `ground-vpm` (MAF and Flora are built inside the ground cells) run
`verifier` right after `readback` and before the model is shown to Artem. The 6 views come from the read-back export:

```
blender --background --factory-startup --python-exit-code 1 --python tools/blender/verifier_views.py -- --vpm VPM --npm NPM --out NEW_DIR
uv run python tools/qa/verifier.py --job jobs/<ID> --renders <dir with the 6 views> --slide <slide.png> \
  --facades south=<label>,north=..,east=..,west=.. [--legend jobs/<ID>/vpm_textures.json]
```

- Input: the 6 views `vpm_south/north/east/west/iso` + `npm_iso` (.png, `tools/qa/vlm_checklist.py` `VIEWS`) rendered
  from the read-back export. VLM = Claude CLI, as in `vlm_checklist.py`.
- It answers the fixed checklist variant A (#768: recall >= 80 %, FP <= 1) with the views forward and reversed and
  keeps only order-consistent answers, then scores the materials on 6 axes 1-5 with a one-line reason (missing,
  base_color, borders, scale, finish, consistency); fix order missing → base colour → borders → scale.
- It writes `jobs/<ID>/verifier.json` (`schemas/Verifier.schema.json`): findings, the ONE main discrepancy it would
  fix next, scores. It never overwrites a report (`--out verifier.r2.json` for a rerun) and never edits the model.
- **Observe is the only mode.** `--mode fix` is refused unless `jobs/<ID>/skeleton.json` sets
  `"config": {"verifier_mode": "fix"}` — only after Artem's word; at most 3 rounds. Not a delivery gate.
- The VLM confirms; positions and counts come from geometry and drawing vectors (CrossProjection, arXiv
  2608.00473: 82 % view matching vs 22 % line localisation). A rib/seam/door finding names *what* to check; where
  the line is and how many come from the model and the DXF, never from the image.
- After Artem's review the job records `verifier_review.json` (`{"reviews": [{"verifier": "verifier.json",
  "artem_corrected": ["material:base_color"]}]}`); `uv run python tools/qa/verifier_summary.py --jobs jobs` shows per
  job how often the main discrepancy matched his correction.

## Observe week: mesh-quality + verifier on every sheet (#1739)

Artem 2026-11-21, decision 7: the mesh-quality score and the verifier only **record** for one week; he sees their
output next to each sheet, then sets a threshold from the numbers. Until then nothing returns work to the agent.

- Stage `mesh-quality` at the end of `body` in `oks-vpm` and `oks-npm`:
  `uv run python tools/qa/mesh_quality_observe.py stage MASTER --out NEW/mesh_quality.json [--cell-m 3.0]`.
  It writes the unchanged #1616 score plus the per-facade-cell defect signal (#1724: irregular / sliver / n-gon
  faces, and triangles in a quad master, per facade cell `side u z` of `cell_m`), so a local corner defect is not
  averaged away. `returns_work` is always `false`, a `fail` status still exits 0; there is no threshold, return or
  refusal option. Errors (unreadable / non-finite geometry, output aliasing the input or existing) exit 2.
- Every sheet sent to Artem carries ONE line, printed by
  `uv run python tools/qa/verifier_summary.py --sheet-line --verifier V.json --mesh-quality MQ.json`.
- The status push carries the weekly line `uv run python tools/qa/verifier_summary.py --jobs jobs --digest`.
- Return/fix mode stays off: the verifier needs `config.verifier_mode = "fix"`; mesh-quality has no return mode.
  Both change only after Artem's word on the week's numbers.

## How a job configures the skeleton (one config file)

`jobs/<ID>/skeleton.json` (template: [`skeleton.template.json`](skeleton.template.json); copy it into the job folder):

```json
{"scenario": "oks-vpm",
 "config": {"sources": "jobs/<ID>/sources.json", "profile": "VPM"},
 "hooks": [{"script": "hooks/fix_seams.py", "stage": "vpm-uv", "point": "after"}]}
```

- `scenario` is a cell above; `config` keys are only the cell's `config_keys` in `skeletons.json` (an unknown key is an
  error naming it). The skeleton's commands read these values; the job does not copy the commands.
- Run the stages in order with the commands in the table; a job never renumbers, merges or replaces a stage that has
  a shared implementation.

## How a job adds a hook script

1. The script lives in `jobs/<ID>/hooks/` and is listed once in `hooks` with its `stage` and `point`
   (`before` | `after` | `gap`). At most 5 hooks per job; a sixth means a parallel pipeline [D324].
2. A hook **calls** the stage owners (`from tools.blender.qa_master import world_bm`), it never defines their entry
   names (`world_bm`, `pack_uv`, `_write_zip`, ...) or a copy that duplicate_guard flags — that is a re-implemented
   stage and fails `skeleton_guard` [D325].
3. `gap` is only for a stage in the gap list below; the hook fills the gap for this job, the skeleton stays as is.
4. `skeleton.json` may sit at any depth: a new task inside an old job (`jobs/KPP1/<task>-<issue>/skeleton.json` +
   `hooks/`) is its own job and is checked. Only the script paths frozen at the #1546 cut
   (`docs/agents/job_scripts_baseline.txt`, never extended) may live outside a `skeleton.json` folder; any other
   script under `jobs/` fails, in a new or an old job folder alike. An old job opts in by adding `skeleton.json`.

Example (Artem's SINTEZ error-fix case): unfold polygons / seams = `checker` → fix with the stage owners
(`vpm-uv`, `master-qa`) through one `after` hook → `checker` again; no new analysis scripts.

## Imported-library exemptions

The guard owner records the following exact-path exception in `skeleton_guard.IMPORTED_LIBRARIES` (#1591):
`jobs/KPP1/quad-1372/provenance-1563/hooks/quad_provenance.py` is a stdlib library imported by the historical
`jobs/KPP1/quad-1372/build_quad_master.py` and its tests. `write_provenance` is called after the build;
it is not an `after` hook of `master-qa` and has no standalone entry point. Keep its existing import path
and the sub-job's `skeleton.json` with an empty hook list. The guard rejects registering this library as
a hook, including path aliases. It still checks the library for stage reimplementation, duplicate code
and Python syntax errors. Sibling, renamed and nested files are not exempt. This does not extend the
frozen #1546 baseline, exempt a directory, or establish a job-configurable library bypass.

## Reviewer rule [D325]

A PR whose job adds its own chain of scripts instead of configuring the skeleton is returned for rework and not merged
(`docs/agents/REVIEW_CHECKLIST.md`). Evidence: `skeleton_guard.py` output, hooks count, stages called.

## Weekly promotion [D326]

Once a week a separate orchestrator task collects hook scripts repeated in 2–3 jobs and the lessons, and shows Artem
a summary; promotion into a skeleton stage happens only there (outside this repo change).

## Historical delivered-job scripts [D327]

Scripts of the delivered jobs (`finished_jobs` in `docs/architecture/contexts.yaml`) that no live command reaches are
listed in the generated block of the root `.ignore`, one `# HISTORICAL [D327] jobs/<ID>` header line per job, so `rg`
and agent search skip them; the files are unchanged and duplicate_guard still scans them. Regenerate after a job is
delivered or a script becomes live: `uv run python tools/architecture/duplicate_guard.py --write-ignore`. To read one on
purpose: `rg --no-ignore-dot PATTERN jobs/<ID>`.

#1614 extends this to data and docs with a second generated block (`# BEGIN historical-data`) owned by
`tools/architecture/search_noise.py`: every non-script file of a delivered job (except the job-root `STATE.md`,
`LESSONS.md`, `README.md`, `REPORT.md`, `TASK.md`, `PASSPORT.md`, `job.yaml`, `passport.json`, `sources.json`, `object.json`,
`materials.json`, `EVIDENCE-MOVED.json`, `skeleton.json` folders and `live_paths`) and every docs/ file that no entry doc,
route, scenario, skill or live code reaches (markdown links followed transitively; inventories and job files do
not propagate). A script that a route, scenario or skill names stays visible. Every `jobs/<ID>` folder is either
in `finished_jobs` or in `kept_jobs` of `docs/architecture/search-noise.yaml` with a Russian reason; an open issue
that uses a hidden path adds it to `live_paths` there. Large JSON/TXT data of delivered jobs lives in the evidence
store (rule 57): `jobs/<ID>/EVIDENCE-MOVED.json` lists path + sha256 + copy; tests read it via
`search_noise.evidence_path` and skip when the copy is absent. Commands: check `uv run python
tools/architecture/search_noise.py`, regenerate `--write-ignore`, Russian job table `--table`, what agent search
sees `--measure`, copies `--verify-evidence`. A new unreached doc or new job data stays visible until the next
`--write-ignore` (reported as pending); the check fails only when the block hides a live or gone path.

## Пробелы (нет общей реализации; по одной строке, реализация — отдельные задачи)

- `geojson` — нет готового к сдаче генератора GeoJSON, пока не изучены примеры заказчика [D220].
- `light-fbx` — нет стадии валидатора для содержимого `_Light.fbx`.
- `brick-seams` — `agr brick-seams` недоступен: алгоритмы привязаны к источнику работы.
- `review-scene` — `agr open-in-max` / `agr contact-renders` недоступны: мост Max или рендеры работы.
- `lite-route` — у `oks-npm-lite` нет карточки и правила упрощения.
- `zero` — нет команды границы и нуля проекта; читать ПЗУ / вертикальную планировку, спрашивать [D279].
- `surfaces` — нет общего построителя покрытий; `ground_cake` — только кирпичики.
- `quads` — нет команды раскроя/спаривания для нового участка; `dt ground v015` повторяет только Ватутино.
- `ground-textures` — нет общей команды ID/UV/текстур плоского Ground.
- `relief` — нет общей команды проекции на рельеф для нового участка [D293].
- `skirt` — юбка нового участка [D251] — работа в DCC, общей команды нет.
- `ucx-ground` — `agr ucx` недоступен; `ucx_build.py` — прецедент, не команда для реального участка.
- `maf-light` — нет инструмента лёгкой НПМ-версии / перекладки UV для МАФ.
- `flora-star` — нет построителя НПМ-звёзд Флоры [D102].
- `optimise` — шага ProOptimizer нет (Артём 2026-11-21, #1737); распределение бюджета Флора/МАФ решает Артём
  [D167]; бюджет треугольников ОКС — по лестнице бюджета ячейки `vpm-to-npm`.
