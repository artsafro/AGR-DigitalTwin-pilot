# Скелеты сценариев — индекс входа (одна дверь)

**Кратко.** Вход один: `AGENTS.md` → этот индекс → блок своей ячейки → тропа ячейки (маршрут или карточка) →
правило и команда на шаге тропы. Агент работает «как скальпель» [D324]: у ячейки неизменный скелет — этапы, каждый
вызывает существующую команду или ядро; под задачу он настраивается одним `jobs/<ID>/skeleton.json` и не более чем
пятью маленькими хуками в `jobs/<ID>/hooks/`. Своя цепочка скриптов возвращается ревьюером [D325]; повторы
собирает еженедельная задача [D326]; скрипты сданных работ скрыты из поиска [D327]. Перед любым этапом —
паспорт `jobs/<ID>/passport.json` [D397] и опрос по `docs/agents/task-intake.md`.

Блок ячейки (этапы, команды, владельцы, пробелы, тропа) печатает
`uv run python tools/architecture/skeleton_guard.py --show <cell>`; машинный источник — [`skeletons.json`](skeletons.json).
Полные таблицы этапов и правила (разбиение ОКС [D336], верификатор, неделя наблюдения, хуки, `sintez-fix`,
исключения, история) — [`SKELETONS-stages.md`](SKELETONS-stages.md): читать на этапе, не на входе.
Проверка задания: `uv run python tools/architecture/skeleton_guard.py [--job jobs/<ID>]` (0 чисто, 1 нарушения, 2 плохой вход).

**Дерево решений на каждом этапе (#2039).** Перед этапом прочитай его узел:
`uv run python tools/architecture/decision_trees.py --show <cell> --stage <stage>` — вопрос, ветки, кто решает
(AGENT по процитированному правилу или ARTEM по листу-картинке) и следующий шаг. Источник —
[`decision-trees.json`](decision-trees.json), по ячейке — [`decision-trees/<cell>.md`](decision-trees/oks-npm.md)
(Mermaid + таблица). Ветка без правила — вопрос Артёму, правило не выдумывается; правило с пометкой job-local
действует только в своём задании.

## Ячейки: тропа и первая команда

| Ячейка | Тропа | Первая команда |
|---|---|---|
| `oks-vpm` | [docs/scenarios/oks-vpm.md](../../docs/scenarios/oks-vpm.md) | `agr inspect --manifest JOB.json`, тело `agr body PLAN NEW_OUT` [D373] |
| `oks-npm` | [routes/npm-oks.md](../../routes/npm-oks.md) | `agr inspect --manifest JOB.json`, тело `agr body PLAN NEW_OUT` [D373] |
| `oks-npm-lite` | [routes/npm-oks.md](../../routes/npm-oks.md) | нет: заморожена до определения NPM-lite [D405] (пробел `lite-route`) |
| `npm-to-vpm` | [docs/scenarios/npm-to-vpm.md](../../docs/scenarios/npm-to-vpm.md) | `agr npm-ids SOURCE NEW_OUT --profile facade` |
| `vpm-to-npm` | [docs/scenarios/vpm-to-npm.md](../../docs/scenarios/vpm-to-npm.md) | `uv run python tools/derive/vpm_to_npm.py --job jobs/<ID> --out NEW_DIR` |
| `maf-npm-to-vpm` | [docs/research/maf-npm-to-vpm-1745.md](../../docs/research/maf-npm-to-vpm-1745.md) | `agr maf-npm-to-vpm --plan` |
| `ground-npm` | [routes/site.md](../../routes/site.md) | `tools/source/inspect_ground_dxf.py`, затем `agr ground site SPEC NEW_OUT` [D293] |
| `ground-vpm` | [routes/site.md](../../routes/site.md) | `tools/source/inspect_ground_dxf.py`, затем `agr ground site SPEC NEW_OUT` [D293] |
| `library-publish` | [docs/scenarios/library-publish.md](../../docs/scenarios/library-publish.md) | `agr library publish BATCH --kind maf --evidence DIR` |
| `sintez-fix` | [docs/research/sintez-fix-1744.md](../../docs/research/sintez-fix-1744.md) | `agr checker COPY_DIR --output NEW_BASELINE.json` (только по просьбе Артёма) |

Тело ОКС (этап 1) во всех профилях строится только решёткой `agr body` [D373], [D392]; AGR Tools заморожены на
1.1.x и остаются исполнителями этапов 2–4 [D393]. `agr --help` — перечень команд до того, как писать свой скрипт.

## Этапы ячеек

- `oks-vpm`: `sources-dwg` → `inspect` → `body` → `mesh-quality` → `udim` → `vpm-uv` → `ucx-oks` → `master-qa` → `readback` → `verifier` → `geojson` → `package-vpm` → `light-fbx` → `validate` → `review-scene` → `checker`
- `oks-npm`: `inspect` → `body` → `mesh-quality` → `brick-seams` → `derive-npm` → `master-qa` → `readback` → `verifier` → `build-manifest` → `package-npm` → `validate` → `review-scene` → `checker`
- `oks-npm-lite`: `lite-route`
- `npm-to-vpm`: `npm-ids` → `npm-udim-fit` → `npm-to-vpm` → `readback` → `checker` → `package-vpm` → `validate`
- `vpm-to-npm`: `tris-count` → `remove-interiors` → `atlas` → `glass-merge` → `budget-ladder` → `master-qa` → `readback` → `verifier` → `package-npm` → `validate` → `checker` → `review-scene`
- `maf-npm-to-vpm`: `maf-segments` → `maf-texture-class` → `maf-atlas-strategy` → `maf-pack` → `maf-stubs` → `master-qa` → `readback` → `checker` → `maf-sheet`
- `ground-npm`: `sources-ground` → `surfaces` → `quads` → `library` → `maf-light` → `flora-star` → `placement` → `optimise` → `master-qa` → `readback` → `verifier` → `package-npm` → `validate` → `checker`
- `ground-vpm`: `sources-ground` → `zero` → `surfaces` → `quads` → `ground-textures` → `relief` → `skirt` → `ucx-ground` → `library` → `placement` → `derive-npm` → `master-qa` → `readback` → `verifier` → `package-vpm` → `validate` → `checker`
- `library-publish`: `intake` → `identify` → `name` → `qa` → `register` → `sheet`
- `sintez-fix`: `checker` → `sintez-classify` → `sintez-recipe` → `sintez-uv-drift` → `sintez-recheck` → `sintez-sheet`

Before hiding or archiving a `jobs/` path, run `uv run pytest -q tests/test_live_route_imports.py`.
The fresh-process runtime guard must show no live route loads Python from that path; if the affected
route is not covered, add its runtime import probe first. Static search and duplicate checks alone do
not prove that lazy or path-based imports are gone. Explicit job data inputs are not Python dependencies.

## Пробелы (нет общей реализации; по одной строке, реализация — отдельные задачи)

- `maf-segments` — ручная правка кругового профиля с замером отклонения и бюджета.
- `maf-texture-class` — ручное подтверждение происхождения отделки и альфы.
- `maf-atlas-strategy` — выбор по замерам плотности, отступов и швов.
- `maf-stubs` — подготовка согласованной тройки карт и контроль применимости заглушек.
- `maf-sheet` — парные виды и замеры для Артёма.
- `sintez-recipe` — один согласованный хук задания или работа у владельца; автоматической правки нет.
- `sintez-sheet` — ручной лист по отчётам и замерам, общего генератора нет.
- `lite-route` — `oks-npm-lite` заморожена [D405]; карточки и правила упрощения нет, пока Артём не определит её.
- `zero` — `agr zero` только проверяет заданный нуль; граница и сам нуль — из ПЗУ / вертикальной планировки, иначе вопрос [D279].
- `quads` — нет команды раскроя/спаривания для нового участка; `dt ground v015` повторяет только Ватутино.
- `optimise` — шага ProOptimizer нет (Артём 2026-11-21, #1737); распределение бюджета Флора/МАФ решает Артём [D167]; бюджет треугольников ОКС — по лестнице бюджета ячейки `vpm-to-npm`.
