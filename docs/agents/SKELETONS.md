# Скелеты сценариев — читать первым для любой работы (job)

**Кратко.** Агент работает «как скальпель» [D324]: у каждого сценария (профиль × объект, ячейка
`docs/scenarios/scenarios.json`) есть неизменный **скелет** — упорядоченные этапы, каждый вызывает уже существующую
команду или ядро. Под задачу агент **настраивает** скелет одним файлом `jobs/<ID>/skeleton.json` и при нехватке
пишет **несколько маленьких скриптов** в `jobs/<ID>/hooks/`, подключая их к этапу (до / после / вместо пробела).
Свою цепочку скриптов вместо скелета не пишет: ревьюер возвращает такой PR на доработку, он не вливается [D325].
Скрипты, повторившиеся в 2–3 работах, раз в неделю собирает отдельная задача, Артём видит сводку, и только там
они переходят в скелет [D326]. Старые скрипты сданных работ оставлены без изменений, помечены историческими и
скрыты из поиска агента; duplicate_guard их по-прежнему сканирует [D327].

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
| 3 | `body` бадик, окна, капсулы, крыша | AGR Tools этапы 1–4 (`body_core`, `windowgen_core`, `capsule_core`, `roof_core`) [D250] |
| 4 | `udim` материалы и UDIM | AGR Tools этапы 5–6, `udimtile_core` |
| 5 | `vpm-uv` UV ВПМ | `tools/blender/vpm_uv.py` [D320] |
| 6 | `ucx-oks` коллизии | `adapters/max/agr_tools/ucx_core.py` |
| 7 | `master-qa` мастер до экспорта | `tools/qa/master_topology.py` [D312] |
| 8 | `readback` экспорт и чтение | `tools/blender/fbx_readback.py`, `dt qa xview` [D152] |
| 9 | `package-vpm` пакет | `agr package-vpm` → `package_core._write_zip` |
| 10 | `validate` проверка пакета | `agr validate` (`tools/qa/validate_package.py`) |
| 11 | `checker` SINTEZ | `agr checker` (`tools/qa/sintez_checker.py`) |
| 12 | `geojson` GeoJSON | пробел |
| 13 | `light-fbx` `_Light.fbx` | пробел |

### `oks-npm` — ОКС, НПМ (`routes/npm-oks.md`)

| # | Этап | Что вызывает |
|---|---|---|
| 1 | `inspect` | `agr inspect --manifest JOB.json` |
| 2 | `body` | AGR Tools этапы 1–4 / `dt_ai` ops для поддержанных случаев |
| 3 | `brick-seams` кирпичные швы | пробел |
| 4 | `derive-npm` ВПМ → НПМ | `agr vpm-to-npm` (`dt derive atlas`, затем `dt derive npm`) |
| 5 | `master-qa` | `tools/qa/master_topology.py` |
| 6 | `readback` | `tools/blender/fbx_readback.py`, `dt qa xview` |
| 7 | `build-manifest` манифест выпуска | `agr build-manifest record` |
| 8 | `package-npm` пакет | `agr package-npm` → `package_core._write_zip` |
| 9 | `validate` | `agr validate` |
| 10 | `review-scene` сцена для приёмки | пробел |
| 11 | `checker` | `agr checker` |

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
| 11 | `package-npm` | `agr package-npm` |
| 12 | `validate` | `agr validate` |
| 13 | `checker` | `agr checker` |

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
| 14 | `package-vpm` | `agr package-vpm` |
| 15 | `validate` | `agr validate --ground-area-m2` |
| 16 | `checker` | `agr checker` после визуальной приёмки |

## How a job configures the skeleton (one config file)

`jobs/<ID>/skeleton.json` (template: [`jobs/_template/skeleton.json`](../../jobs/_template/skeleton.json)):

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
4. Folders that existed before #1546 (`LEGACY_JOBS`) are checked once they add `skeleton.json`; any new job folder
   with scripts must have one.

Example (Artem's SINTEZ error-fix case): unfold polygons / seams = `checker` → fix with the stage owners
(`vpm-uv`, `master-qa`) through one `after` hook → `checker` again; no new analysis scripts.

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
