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
| 4 | `udim` материалы и UDIM | AGR Tools этапы 5–6, `udimtile_core` |
| 5 | `vpm-uv` UV ВПМ | `tools/blender/vpm_uv.py` [D320] |
| 6 | `ucx-oks` коллизии | `adapters/max/agr_tools/ucx_core.py` |
| 7 | `master-qa` мастер до экспорта | `tools/qa/master_topology.py` [D312] |
| 8 | `readback` экспорт и чтение | `tools/blender/fbx_readback.py`, `dt qa xview` [D152] |
| 9 | `verifier` проверка VLM перед показом Артёму (observe) | `tools/qa/verifier.py` → `verifier.json` [#1577] |
| 10 | `package-vpm` пакет | `agr package-vpm` → `package_core._write_zip` |
| 11 | `validate` проверка пакета | `agr validate` (`tools/qa/validate_package.py`) |
| 12 | `checker` SINTEZ | `agr checker` (`tools/qa/sintez_checker.py`) |
| 13 | `geojson` GeoJSON | пробел |
| 14 | `light-fbx` `_Light.fbx` | пробел |

### `oks-npm` — ОКС, НПМ (`routes/npm-oks.md`)

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `inspect` | `agr inspect --manifest JOB.json` |
| 2 | `body` | AGR Tools этапы 1–4 / `dt_ai` ops для поддержанных случаев; разбиение [D336]; Сетка бадика: [правила BM-01…BM-14](../research/body-modelling.md#5-правила) (#1618) |
| 3 | `brick-seams` кирпичные швы | пробел |
| 4 | `derive-npm` ВПМ → НПМ | `agr vpm-to-npm` (`dt derive atlas`, затем `dt derive npm`) |
| 5 | `master-qa` | `tools/qa/master_topology.py` |
| 6 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 7 | `build-manifest` манифест выпуска | `agr build-manifest record` |
| 8 | `package-npm` пакет | `agr package-npm` → `package_core._write_zip` |
| 9 | `validate` | `agr validate` |
| 10 | `review-scene` сцена для приёмки | пробел |
| 11 | `checker` | `agr checker` |

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
| 8 | `optimise` бюджет НПМ | пробел |
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

`oks-vpm`, `ground-npm` and `ground-vpm` (MAF and Flora are built inside the ground cells) run `verifier` right after
`readback` and before the model is shown to Artem:

```
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
- `optimise` — ProOptimizer в Max вручную; варианты — Артёму [D167].
