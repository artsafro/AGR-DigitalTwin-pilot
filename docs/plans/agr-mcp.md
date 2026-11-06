# План: свой MCP `agr-mcp` для 3ds Max и Blender

Карточка: issue #807. Это только план. Кода сервера здесь нет.

Ветка issue в тексте карточки — `plan/agr-mcp`. Этот worktree уже на `improve/issue-807-plan-our-own-agr-mcp-server-for-3ds-max`; план лежит здесь, переименование не делалось.

Цель: агенты вызывают наши инструменты (`agr_*`), а не чужой каталог. Свой репозиторий `artsafro/agr-mcp` — после фазы 0, не сейчас. Пока сервер не написан, маршруты из `docs/agents/CAPABILITIES.md` не меняются.

Проверено до записи файла: `docs/plans/` и `docs/plans/agr-mcp.md` на этой ветке отсутствовали (`Test-Path` → `False`).

## 1. Инвентарь

Что агенты делают с DCC сегодня: чужой MCP, `max_exec.py`, `dcc_batch.py`, плюс headless Blender и живой `blender_exec.py`. Счётчик — число строк `rg -n | wc -l`, не число живых вызовов. `.agents/skills` и `.claude/skills` дублируют одни и те же тексты (Ground / MAF / Flora).

Корень: worktree. Фильтр один на все команды этого каталога. `docs/plans/**` исключён, чтобы сам план не попадал в счётчик. Первая команда — колонка matches, вторая — files:

```
rg -n -F -g "jobs/**" -g "tools/**" -g "scripts/**" -g ".agents/skills/**" -g ".claude/skills/**" -g "docs/**" -g "!docs/plans/**" -- "<pattern>" | wc -l
rg -l -F -g "jobs/**" -g "tools/**" -g "scripts/**" -g ".agents/skills/**" -g ".claude/skills/**" -g "docs/**" -g "!docs/plans/**" -- "<pattern>" | wc -l
```

Шаблоны, которые начинаются с `-`, стоят после `--`, иначе `rg` съедает их как флаги. Прогон: 2026-11-04, HEAD `b049d99f`. Таблица ниже — строки и файлы этого прогона.

| pattern | matches | files |
|---|---:|---:|
| `max_exec.py` | 3 | 2 |
| `dcc_batch.py` | 115 | 56 |
| `dcc_batch.py max` | 43 | 29 |
| `dcc_batch.py acad` | 22 | 15 |
| `blender_exec` | 54 | 17 |
| `execute_maxscript` | 1 | 1 |
| `execute_python` | 3 | 1 |
| `execute_blender_code` | 14 | 3 |
| `3dsmaxbatch` | 39 | 22 |
| `get_objects_summary` | 2 | 2 |
| `get_blendfile_summary` | 7 | 3 |
| `get_object_detail_summary` | 4 | 2 |
| `--factory-startup` | 200 | 118 |
| `--background` | 206 | 130 |
| `holdMaxFile` | 5 | 3 |
| `saveMaxFile` | 31 | 16 |
| `exportFile` | 33 | 19 |
| `importFile` | 18 | 18 |
| `xview_dump.ms` | 14 | 10 |
| `build_agr_tools` | 4 | 2 |
| `MaxClient` | 0 | 0 |
| `send_command` | 0 | 0 |

Отдельный прогон, только чтение, вне фильтра worktree. Команда:

```
rg -n -F -- "max_exec.py" C:/Users/artsafro/hermes_kanban/scripts
```

| pattern | matches | files |
|---|---:|---:|
| `max_exec.py` в `C:/Users/artsafro/hermes_kanban/scripts` | 4 | 2 |

Четыре строки: шапка самого `max_exec.py` (строки 4–6) и упоминание команды в `agr_refill.py:55`. Другого скрипта в этой папке, который вызывает `max_exec.py`, нет.

`--background` (206) включает почти все `--factory-startup` (200): это один класс запуска, не вторая сотня действий. `dcc_batch.py` (115) включает строки `max` (43) и `acad` (22); остальные 50 — общее имя обёртки. Отдельного каталога card logs в worktree нет. В фильтр попал evidence `jobs/vyatskaya-tow02/evidence/xview-528/SUMMARY.md`. Тела карточек в `hermes_kanban` не сканировались; каталог `scripts` там посчитан отдельной строкой выше.

| Действие | Где (пример) | Маршрут | Совпадения | Что даёт чужой сервер и чего нам не хватает | Риск |
|---|---|---|---|---:|---|
| Живой MAXScript в открытом Max | `tools/review/max_adapter.py:52` (`--file`); упоминания `docs/research/default-suite-max-lock-exposure.md:193` | `max_exec.py` → pipe `3dsmax-mcp`, `MaxClient.send_command(..., cmd_type="maxscript")` | 3 (1 call site в репозитории) | Именованный pipe и ответ JSON. Своего типизированного инструмента нет: в worktree `MaxClient` / `send_command` = 0 | Произвольный MAXScript. Lock `%LOCALAPPDATA%\Temp\agr-3dsmax-live.lock` есть (файл вне репозитория, прочитан). Журнала вызовов JSONL нет |
| Headless Max, свой скрипт `.py`/`.ms` на копии | `tools/flora/dump_flora_library_faces.py:5`; skills `model-flora` `.agents/skills/model-flora/SKILL.md:86` и `.claude/skills/model-flora/SKILL.md:86` | `dcc_batch.py max` → `3dsmaxbatch.exe`. Чужой MCP в этом пути не участвует | 43 / 29 файлов | Пакетный прогон без каталога инструментов. Нужны наши функции, а не произвольный файл job | Произвольный код job. Lock `agr-max-session.lock` есть. Аудит — listener log, не JSONL по инструменту |
| Headless AutoCAD `DXFOUT` / `SAVEAS` | `.agents/skills/model-ground/SKILL.md:42` (то же в `.claude/skills/model-ground/SKILL.md:42`) | `dcc_batch.py acad` | 22 / 15 файлов | Это не Max/Blender MCP. В v1 сервер его не забирает | Скрипт `.scr`. Lock `agr-acad-session.lock`. Вне объёма #807 |
| Живой Python в открытом Blender | `docs/experiments/blender-exec-session.md:3` | `blender_exec.py` → аддон на порту (в эксперименте ahujasid, 9876) | 54 / 17 файлов | Выполнение `bpy`. Нам нужен readback и сборка, не произвольный код | Произвольный Python. Lock `agr-blender-session.lock` (прочитан заголовок `blender_exec.py`). JSONL нет |
| Headless Blender `--background --factory-startup` | `tools/blender/fbx_readback.py:9`, `tools/blender/ground_json_to_fbx.py:5` | Прямой `blender.exe`. Не Blender Lab MCP и не `dcc_batch` (у `dcc_batch.py` есть только `max` и `acad`) | 200 / 118 файлов | Ничего из чужого MCP: процесс сам исполняет `--python` | Произвольный скрипт в аргументе. Отдельного lock в этих docstring нет |
| Осмотр сцены Blender Lab | `docs/agents/CAPABILITIES.md:175`; `.agents/skills/blender-mcp/SKILL.md:28` | MCP `blender`, пакет `blender-mcp` 1.0.3, порт 9877 | `get_objects_summary` 2, `get_blendfile_summary` 7, `get_object_detail_summary` 4 | Семь read-only инструментов из CAPABILITIES. Схемы в репозитории не зафиксированы | Эти семь — read-only по регистру риска. Всё остальное на маршруте, включая Python, — destructive |
| Произвольный код чужого MCP | `docs/research/mcp-dcc-bridges.md:38` (`execute_maxscript`), `:61` и `:208` (`execute_blender_code`) | `3dsmax-mcp` / Blender Lab | `execute_maxscript` 1, `execute_python` 3 (1 файл), `execute_blender_code` 14 (3 файла) | Именно это v1 не повторяет как обычный инструмент | CAPABILITIES: все инструменты `3dsmax-mcp` — destructive. `safe_mode` не песочница (см. §7) |
| Нативный xView пакетом | `jobs/vyatskaya-tow02/evidence/xview-528/SUMMARY.md:3` | `dcc_batch.py max` + `tools/qa/xview_dump.ms` | 14 / 10 файлов | Дамп для сверки с `tools/qa/xview_parity.py` | Скрипт на копии. Тот же lock, что у headless Max |
| Правка/сохранение/импорт/экспорт внутри job | `tools/export/benchmark_export_max.py:235` (`holdMaxFile`); `saveMaxFile` / `exportFile` / `importFile` | Текст скриптов, которые крутит batch или живой мост | 5 / 31 / 33 / 18 | Чужой `execute_maxscript` это просто проносит | Прямая мутация сцены или диска. Аудита вызова нет |

Итого по маршрутам (совпадения, с оговоркой про вложенность выше): живой Max 3, headless Max 43, headless AutoCAD 22, живой Blender 54, headless Blender 200. Плюс имена чужих tool в документах: `execute_maxscript` 1, `execute_python` 3, `execute_blender_code` 14 в 3 файлах. Единственный call site `max_exec.py` внутри репозитория — `tools/review/max_adapter.py:52`. В `hermes_kanban/scripts` строка `max_exec.py` встречается 4 раза (2 файла), внешних вызовов там нет.

Свой код, который сервер должен вызывать, уже в пилоте: `adapters/max/agr_tools/runtime.py` (версия в файле `0.4.0`), чекеры `src/twinqa/`, `tools/qa/xview_parity.py`, `tools/blender/fbx_readback.py`. Сборщики Ground / MAF / Flora в v1 остаются библиотеками, не MCP-инструментами: им не нужен живой DCC (`src/dt_ai/geometry/ground_cake.py` `build_flat`, `src/twinqa/maf_checks.py` `maf_findings`, `src/twinqa/flora.py` `flora_findings`).

## 2. Инструменты v1

16 имён. Вход и выход — набросок JSON Schema черновика 2020-12, не регистрация. Функции Max принимают узлы pymxs: слой MCP резолвит `handles` в узлы уже внутри Max и зовёт функцию. Ответ Max-инструментов — словарь `_report` в `runtime.py:250`: `schema`, `tool`, `status` (`pass`/`fail`), `objects[].findings[]` с `code`, `ids`, `detail`.

Срезы `hygiene_core.py`, `uv_nudge_core.py`, `ucx_audit_core.py` в дереве исходников рядом с `runtime.py` отсутствуют: их пишет `tools/max/build_agr_tools.py` из `src/twinqa/export_hygiene.py` (`repair_plan`), `src/dt_ai/geometry/uv_nudge.py` (`nudge_repeating_islands`) и `src/twinqa/geometry/ucx_audit.py`. Установленный MZP их содержит (`install.ms` перечисляет эти имена).

Общие поля входа Max-инструментов: `scene` (путь копии или `live`), `handles` (массив целых), `scope` (необязательно, только `"selection"`), `instance` (необязательно, pid интерактивного `3dsmax.exe`; правило в §3 «Целевой экземпляр Max»). Пустой `handles` — ошибка, см. «Контракт выделения» ниже. Мутации — только на копиях экспорта или на одноразовой сцене, как AGR Tools.

1. `agr_xview_check` — Max — selection-modifying. `runtime.xview` (`runtime.py:295`) возвращает `_report('xview', entries, nodes)` (`runtime.py:348`) без аргумента `select`. У `_report` значение по умолчанию `select=True` (`runtime.py:250`), и тогда вызывается `_rt().select` по узлам с findings (`runtime.py:257`). Геометрия исходных узлов не переписывается (проверка идёт по временной копии). По контракту выделения (ниже) вызов обязан дойти до `_report(select=False)`; если `xview` аргумент не принимает, это правка `runtime.py` в фазе 0, не этой карточки. Вход: общие поля + `select_findings` (bool, по умолчанию `false`). Выход: `_report` плюс пороги 2 мм / 5 мм в `extra`, если функция их кладёт.
2. `agr_matid_check` — Max — selection-modifying, тот же механизм. `runtime.matid` (`runtime.py:351`) возвращает `_report('matid', entries, nodes)` (`runtime.py:381`) без `select`, значит снова `select=True`. Контракт тот же: `_report(select=False)`. Вход: общие поля + `select_findings` (bool, по умолчанию `false`). Выход: `_report` (id ≥ 1001, id 0, пустые слоты).
3. `agr_cleanup_preview` — Max — read-only (`cleanup_preview` пишет «No mutation», `runtime.py:443`). Вход: общие поля. Выход: план правок, сцена не меняется.
4. `agr_cleanup_apply` — Max — новые узлы-копии. `runtime.cleanup_apply` (`runtime.py:462`). Вход: общие поля + `preview` (объект прошлого preview). Выход: `_report` по копиям. Оригиналы функция не чистит.
5. `agr_uv_nudge_preview` — Max — read-only. `runtime.nudge_preview` (`runtime.py:701`). Вход: общие поля. Выход: острова и шаги тайла. `nudge_apply` (`runtime.py:751`) в v1 отдельным именем не выводится: тот же контракт, что у `cleanup_apply`, фаза 1.
6. `agr_atlas_preview` — Max — read-only. `runtime.atlas_preview` (`runtime.py:1031`). Вход: общие поля. Выход: раскладка UDIM → NPM. `atlas_apply` (`runtime.py:1215`) — фаза 1, тот же приём preview.
7. `agr_ucx_preview` — Max — read-only. `runtime.ucx_preview` (`runtime.py:1373`). Вход: общие поля. Выход: вариант, число кусков, вердикт аудита.
8. `agr_ucx_apply` — Max — копии `*_AGR_ucx_` и `UCX_*`. `runtime.ucx_apply` (`runtime.py:1402`). Вход: общие поля + `preview`. Выход: имена кусков и bounds. Занятое имя — ошибка до создания узла.
9. `agr_texel_readout` — Max — read-only. `runtime.texel_preview` (`runtime.py:1505`). Вход: общие поля. Выход: min/median px/m. Свойства `AGR_TEXEL_PROFILE`, `AGR_TEXEL_MAP` остаются на узле, как в AGR Tools.
10. `agr_export_preview` — Max — read-only, файл не пишет. `runtime.export_preview` (`runtime.py:1748`). Вход: общие поля + `target` (новый путь FBX). Выход: ворота и счётчики dry-run.
11. `agr_export_commit` — Max — один новый FBX, если preview совпал. `runtime.export_commit` (`runtime.py:1807`). Вход: общие поля + `preview` + `target`. Выход: путь FBX и JSON-отчёт рядом. Существующий файл функция отвергает.
12. `agr_fbx_readback` — Blender headless — read-only по файлу. `src/twinqa/scene.py` `readback` (`scene.py:59`) запускает `tools/blender/fbx_readback.py`; факты сетки собирает `mesh_facts` (`fbx_readback.py:66`). Вход: `{fbx_path, timeout?}`. Выход: словарь readback (счётчики, единицы). `bpy` снаружи Blender эта функция не требует: его поднимает subprocess.
13. `agr_package_validate` — без живого DCC, при `scene=true` зовёт тот же readback. `tools/qa/validate_package.py` `validate` (`validate_package.py:189`). Внутри уже есть `geojson_findings`, `vpm_texture_findings`, `npm_texture_findings`, `scene_findings` (pivot, лимиты треугольников, зазоры). Вход: `{target, kind, scene, ground_area_m2, footprint_holes}`. `profiles` сервер грузит сам через `twinqa.profiles.load_profiles`. Выход: поля `ValidationReport` (стадии, findings). Это не замена узким инструментам 14–15.
14. `agr_mesh_names` — офлайн. `src/twinqa/naming.py` `mesh_name_findings` (`naming.py:102`). Вход: `{names, kind, role, fbx_stem, limit, src}`. Выход: список findings (`name`, `status`, `observed`, `expected`). На этой ветке в `adapters/max/agr_tools` строк `0.5.0` нет: `runtime.py` держит `VERSION = "0.4.0"`. Имена/лимиты/текстуры/pivot/GeoJSON из текста #804 здесь живут в `twinqa`, не в MZP.
15. `agr_geojson_check` — офлайн. `src/twinqa/geojson.py` `geojson_findings` (`geojson.py:98`). Вход: `{path, ground, source_name}` (байты читает сервер; `profile` снова `load_profiles`). Выход: список findings.
16. `agr_xview_parity` — офлайн, после дампа Max. `tools/qa/xview_parity.py` `compare` (`xview_parity.py:84`). Вход: `{dump}` (объект с `nodes`, `m_per_unit`, допусками). Выход: список строк сравнения vertex/face. Дамп по-прежнему снимает `xview_dump.ms` через фазу 0, пока `agr_xview_check` не отдаёт те же id.

`agr_exec_unsafe` в список v1 не входит. Это отдельный люк (§3), выключенный по умолчанию.

### Контракт выделения (закрывает п. 3 из #816)

Вход: слой MCP никогда не передаёт в функции Max `nodes=None` (иначе `runtime._targets` берёт текущее выделение пользователя). Выход: инструменты 1–2 не меняют выделение, пока нет явного `select_findings: true`.

| Вход | Ожидаемый исход |
|---|---|
| `handles: [12, 15]`, оба существуют | узлы 12 и 15 резолвятся в Max, функция получает список узлов |
| `handles: []` или поля нет, `scope` нет | ошибка `handles_required`, Max не вызывается |
| `handles: []`, `scope: "selection"` | цели = текущее выделение; в JSONL `scope: "selection"` и список handles выделения |
| `handles: [12]`, `scope: "selection"` | ошибка: два источника целей |
| `handles` с несуществующим handle | ошибка с этим handle, остальные не обрабатываются |
| `agr_xview_check` / `agr_matid_check`, `select_findings` нет | `_report(select=False)`; множество handles выделения до = после, иначе ошибка `selection_changed` (ответ не `pass`) |
| то же, `select_findings: true` | выделение = узлы с findings; инструмент помечен selection-modifying, в JSONL `selection_modified: true` |

Проверка после вызова: слой читает множество handles выделения до и после каждого вызова фазы 0 и сравнивает как множества; это идея `core/layers.ms:438-443` в MAX Ultra MCP (`docs/research/max-ultra-mcp-vs-agr-mcp-plan.md`). Инструменты 3–11 тоже проверяются, но делятся на два класса (номера как в списке выше; ссылки на `runtime.py` — по `origin/main`):

| Инструмент | Класс | Что делает с выделением | Правило слоя |
|---|---|---|---|
| 3 `agr_cleanup_preview` | selection-preserving | не трогает | выделение до = после, иначе `selection_changed` |
| 4 `agr_cleanup_apply` | selection-mutating by design | `rt.select(copies)` (`runtime.py:494`) | сохранить выделение до вызова, восстановить после; `selection_changed` проверяется после восстановления |
| 5 `agr_uv_nudge_preview`; `nudge_apply` (фаза 1) | preview — preserving; apply — mutating | `_apply_uv` делает `rt.select(copies)` (`runtime.py:743`, `nudge_apply` `runtime.py:751`) | preview как у 3; apply как у 4 |
| 6 `agr_atlas_preview`; `atlas_apply` (фаза 1) | preview — preserving (`_report(select=False)`, `runtime.py:1078`); apply — mutating | `atlas_apply` вызывает `_apply_uv` (`runtime.py:1222`), тот делает `rt.select(copies)` (`runtime.py:743`) | preview как у 3; apply как у 5 (`nudge_apply`) и 4: сохранить до, восстановить после, проверка после восстановления |
| 7 `agr_ucx_preview` | selection-mutating by default | `_report('ucx', ...)` без `select` (`runtime.py:1384`), по умолчанию `select=True` (`runtime.py:250`) выполняет `_rt().select` (`runtime.py:257`) | как у 1–2: слой вызывает `_report(select=False)` и выделяет findings только при `select_findings: true`; иначе как у 4 (сохранить до, восстановить после) |
| 8 `agr_ucx_apply` | selection-mutating через `ucx_preview` | `ucx_apply` (`runtime.py:1402`) вызывает `ucx_preview` (`runtime.py:1417`), а тот выделяет узлы с findings (см. 7) | как у 4 (или как у 7 после перевода `ucx_preview` на `select=False`) |
| 9 `agr_texel_readout` | selection-mutating by default | `_report('texel', ...)` без `select` (`runtime.py:1521`), по умолчанию `select=True` (`runtime.py:250`, `runtime.py:257`) | как у 7 |
| 10 `agr_export_preview` | selection-preserving | файл не пишет | как у 3 |
| 11 `agr_export_commit` | selection-mutating by design | `_write_max_fbx`: `rt.select(copies)` (`runtime.py:1791`) и `exportFile(..., selectedOnly=True)` (`runtime.py:1792`) | как у 4: сохранить до, восстановить после, проверка после восстановления |

Правило: у selection-mutating инструмента слой сохраняет множество handles выделения до вызова, восстанавливает его после вызова, и только потом сравнивает; расхождение после восстановления — ошибка `selection_changed`. Инструмент без `select_findings`, который оставил другое выделение (и восстановление не помогло), — тоже `selection_changed`.

Приёмка (вход → ожидание):

| Вход | Ожидание |
|---|---|
| `agr_cleanup_apply`, `handles: [12]`, выделение `{5}` | после вызова выделение `{5}`, ошибки `selection_changed` нет |
| `agr_xview_check`, выделение `{5}` | выделение `{5}` |
| `agr_texel_readout` (или `agr_ucx_preview`), `handles: [12]`, у узла 12 есть finding, выделение `{5}` | после вызова выделение `{5}`, ошибки `selection_changed` нет (через `_report(select=False)` либо восстановление) |
| `agr_atlas_apply` (фаза 1), `handles: [12]`, выделение `{5}` | после вызова выделение `{5}`, ошибки нет |
| инструмент без `select_findings`, оставивший выделение `{12}` при исходном `{5}` | ошибка `selection_changed` |

Тесты выделения (строки приёмки) от Q1 не зависят: Q1 (#816) касается только теста двух экземпляров Max (`docs/research/max-ultra-mcp-vs-agr-mcp-plan.md:184`).

Общий вход Max (`handles` непустой, либо `scope: "selection"`):

```json
{"type":"object","required":["scene"],"properties":{"scene":{"type":"string"},"handles":{"type":"array","items":{"type":"integer"}},"scope":{"const":"selection"},"instance":{"type":"integer"}}}
```

Общий выход Max (`runtime._report`):

```json
{"type":"object","required":["schema","tool","status","objects"],"properties":{"schema":{"const":1},"tool":{"type":"string"},"status":{"enum":["pass","fail"]},"objects":{"type":"array","items":{"type":"object","required":["findings"],"properties":{"findings":{"type":"array","items":{"type":"object","required":["code","ids"],"properties":{"code":{"type":"string"},"ids":{"type":"array","items":{"type":"integer"}},"detail":{"type":"string"}}}}}}}}}
```

Дальше только то, что добавляется к этим двум. `preview` — объект, который сервер сохранил из предыдущего ответа, без правок агента.

| Инструмент | Вход сверх общего | Выход сверх общего |
|---|---|---|
| `agr_xview_check` | — | `extra` с порогами, как вернёт `xview` |
| `agr_matid_check` | — | — |
| `agr_cleanup_preview` | — | план в `objects`, сцена не пишется |
| `agr_cleanup_apply` | `preview` object, required | те же `objects` уже по копиям |
| `agr_uv_nudge_preview` | — | шаги тайла в `objects` |
| `agr_atlas_preview` | — | клетки атласа в `objects` |
| `agr_ucx_preview` | — | вариант и бюджет в `objects` |
| `agr_ucx_apply` | `preview` object, required | имена `UCX_*` |
| `agr_texel_readout` | — | min/median px/m |
| `agr_export_preview` | `target` string, required | ворота и счётчики, файла нет |
| `agr_export_commit` | `preview` object, `target` string, оба required | `fbx` string, `report_path` string |

Офлайн-инструменты, схемы целиком:

```json
{"agr_fbx_readback":{"in":{"type":"object","required":["fbx_path"],"properties":{"fbx_path":{"type":"string"},"timeout":{"type":"integer"}}},"out":{"type":"object","required":["source"]}}}
{"agr_package_validate":{"in":{"type":"object","required":["target"],"properties":{"target":{"type":"string"},"kind":{"enum":["npm","vpm",null]},"scene":{"type":"boolean"},"ground_area_m2":{"type":["number","null"]},"footprint_holes":{}}},"out":{"type":"object","required":["stages"]}}}
{"agr_mesh_names":{"in":{"type":"object","required":["names","kind","role","fbx_stem","limit","src"],"properties":{"names":{"type":"array","items":{"type":"string"},"minItems":1},"kind":{"enum":["npm","vpm"]},"role":{"type":"string"},"fbx_stem":{"type":"string"},"limit":{"type":"integer","exclusiveMinimum":0},"src":{"type":"string"}}},"out":{"type":"array","items":{"type":"object","required":["name","status","observed","expected"]}}}}
{"agr_geojson_check":{"in":{"type":"object","required":["path","ground"],"properties":{"path":{"type":"string"},"ground":{"type":"boolean"},"source_name":{"type":"string"}}},"out":{"type":"array"}}}
{"agr_xview_parity":{"in":{"type":"object","required":["dump"],"properties":{"dump":{"type":"object","required":["nodes","m_per_unit"]}}},"out":{"type":"array","items":{"type":"object","required":["node","vertices_only_max","vertices_only_ours"]}}}}
```

Finding офлайн-чекеров — это `twinqa.report.Finding`, не словарь `_report`. Сервер сериализует поля, которые у Finding уже есть; новые ключи не выдумывает.

## 3. Архитектура

Рекомендация: один процесс stdio на клиента, Python-пакет `agr-mcp`, протокол MCP. Транспорт stdio, как у `blender` в `.agents/mcp_config.json` (`--transport stdio`) и у `3dsmax-mcp` (`uv run --directory ... 3dsmax-mcp`). Локальный HTTP не нужен, пока один агент держит один stdio-сеанс, а общую сцену держит файловый lock. HTTP понадобится, только если несколько клиентов должны делить один процесс сервера; это не фаза 0.

Спека, на которую опираемся: ревизия **2026-07-28** (страница `https://modelcontextprotocol.io/specification/2026-07-28`, индекс `https://modelcontextprotocol.io/specification`). Её текст на сайте открывался 2026-11-04. Ревизия убирает handshake `initialize` и сессии у Streamable HTTP. Наш v1 на stdio этот слом не обязан повторять, пока закреплённый SDK его не говорит. В venv Blender Lab стоит пакет `mcp` **1.30.0** (`blender_mcp-1.0.3.dist-info` рядом, METADATA). Совпадает ли 1.30.0 с ревизией 2026-07-28 — не проверялось. Сервер пишет в `serverInfo` ту ревизию, которую реально реализует закреплённый SDK, и поле `tool_schema_version`.

Как достучаться до Max на фазе 0: повторно использовать pipe `3dsmax-mcp`, тем же приёмом, что `max_exec.py` (`MaxClient`, `cmd_type="maxscript"`), и звать только `fileIn` уже установленного AGR Tools плюс вызов одной функции `runtime.*`. Свой listener (MAXScript/Python plugin с сокетом) — после того, как типизированные вызовы стабильны. До этого дня сервер не открывает второй канал в тот же Max. Headless-проверки идут через `3dsmaxbatch` и lock `dcc_batch`, не через pipe пакетного Max (pipe batch уже путал живой сеанс: комментарий в `max_exec.py` про SAFE_MODE на карточке #189).

Blender v1: headless subprocess, как `scene.readback` (`blender --background --factory-startup`). Живой аддон (ahujasid на 9876 в экспериментах, Blender Lab на 9877 в CAPABILITIES) на фазе 0 не вызываем. Произвольный `execute_blender_code` не оборачиваем.

### Целевой экземпляр Max

Каждый вызов живого Max резолвит ровно один pid интерактивного `3dsmax.exe`. Сегодня `max_exec.py` молча берёт новейший не-batch Max; здесь вместо этого правило MAX Ultra MCP (`core/server.js:429-446`, из отчёта `docs/research/max-ultra-mcp-vs-agr-mcp-plan.md`).

Порядок выбора: `instance` во входе, затем `MCP_MAX_PID`, затем выбор сеанса; если ничего нет и интерактивный Max один — он.

| Вход | Ожидаемый исход |
|---|---|
| два интерактивных Max (pid 1000, 2000), нет `instance`, `MCP_MAX_PID`, выбора сеанса | отказ до любого вызова в Max, ответ со списком `[1000, 2000]` |
| тот же случай, `instance: 2000` | вызов идёт в pid 2000 |
| тот же случай, `MCP_MAX_PID=1000`, `instance` нет | вызов идёт в pid 1000; `instance` приоритетнее переменной |
| `instance: 3000`, такого интерактивного Max нет | ошибка с pid 3000 и списком живых интерактивных |
| один интерактивный Max (pid 1000) | вызов идёт в pid 1000 |
| есть только batch Max (`3dsmaxbatch`) | отказ `no interactive Max`; batch никогда не цель |
| интерактивный 1000 и batch 4000, `instance: 4000` | отказ: pid 4000 — batch |

В журнал (поля ниже) добавляются `max_pid` и `max_version` резолвленного экземпляра; у отказа `max_pid` — null, в `error` список pid. Офлайн- и Blender-вызовы правило не затрагивает.

Lock, те же файлы, что уже есть:

- живой Max: `%LOCALAPPDATA%\Temp\agr-3dsmax-live.lock` (`max_exec.py`);
- headless Max: `%LOCALAPPDATA%\Temp\agr-max-session.lock` (`dcc_batch.lock_path("max")`);
- живой Blender: `%LOCALAPPDATA%\Temp\agr-blender-session.lock` (`blender_exec.py`);
- headless Blender: новый файл `agr-blender-batch.lock` с теми же правилами, что `dcc_batch.acquire` (O_EXCL, pid, чужой timeout). Общий lock с живым Blender не ставим: живой Max и batch Max уже разделены нарочно (`max_exec.py`, строки про два процесса).

Прототип lease `experiments/mcp-dcc-bridges/dcc_lease.py` (PID + fencing) в v1 не подключаем. Его вердикт в `docs/experiments/mcp-dcc-bridges.md` — «adopt», но это отдельная работа. Пока хватает существующего lock на время всего вызова, не на один шаг внутри инструмента.

Журнал: один JSONL на машину, `%LOCALAPPDATA%\agr-mcp\audit.jsonl`, append. Поля: `ts` (UTC), `tool`, `tool_schema_version`, `server_version`, `client` (имя из `_meta`, если клиент его прислал), `card`, `pid`, `lock`, `host` (`max-live` | `max-batch` | `blender-batch` | `offline`), `scene`, `target`, `max_pid`, `max_version`, `args_sha256`, `status`, `duration_ms`, `error`. Тела скриптов и байты FBX в журнал не пишем.

Safe mode по умолчанию: в каталоге нет инструмента с полем `code`. Аргументы — пути, handles, числа, прошлый preview. `agr_exec_unsafe` регистрируется только если окружение `AGR_MCP_UNSAFE=1`. Иначе `tools/list` его не показывает и `tools/call` отвечает отказом. Каждый такой вызов пишет в JSONL `unsafe: true`, `code_sha256`, `code_bytes`. Флаг не отменяет lock и не разрешает путь к исходнику сцены: `target` по-прежнему новый файл. Это люк для отладки, не профиль «full» чужого сервера.

Чужой `safe_mode = true` таким правилом не считается. В локальном `C:\Users\artsafro\tools\3dsmax-mcp\mcp_config.ini` стоит `safe_mode = true`. `docs/ADVANCED.md` того дерева говорит: это список подстрок (`DOSCommand`, `ShellLaunch`, `deleteFile`, `python.Execute`, `createFile`), не песочница; штатные инструменты вроде удаления объектов идут мимо списка.

## 4. Установка из будущего репозитория

Одна команда из клона `artsafro/agr-mcp` (имя команды — проект, реализации ещё нет):

```
uv run agr-mcp install
```

Она делает три вещи: ставит консольный скрипт `agr-mcp` в venv репозитория (`uv sync`), копирует плагин Max тем же приёмом, что `python tools/max/build_agr_tools.py` (новый MZP, без перезаписи), кладёт Blender-скрипты readback рядом с пакетом. Аддон в живой Blender на фазе 0 не регистрируется: хватает `blender.exe` из переменной `AGR_BLENDER` (сегодня версия закреплена в `src/dt_ai/core/blender_runner.py`, имя константы `BLENDER_VERSION`, значение в CAPABILITIES — 5.1.2).

Регистрация — один и тот же stdio: `uv run --directory <clone> agr-mcp`. Ниже четыре формата. `<clone>` — путь клона `artsafro/agr-mcp`.

Hermes, профиль, `config.yaml`. Ключи stdio — `command`, `args`, `env` (`C:\Users\artsafro\.hermes\hermes-agent\website\docs\reference\mcp-config-reference.md:18-22`; таблица тех же ключей на строках 48–50). Блок `mcp_servers` читается из config активного профиля (`C:\Users\artsafro\.hermes\hermes-agent\tools\mcp_tool_config.py:710`, `load_config().get("mcp_servers")`). Файл профиля — `config.yaml` в каталоге под `~/.hermes/profiles/` (`C:\Users\artsafro\.hermes\hermes-agent\website\docs\user-guide\profiles.md:11`). Пример формы — `C:\Users\artsafro\.hermes\hermes-agent\website\docs\user-guide\features\mcp.md:317-324`.

```yaml
# ~/.hermes/profiles/<name>/config.yaml
mcp_servers:
  agr-mcp:
    command: "uv"
    args: ["run", "--directory", "<clone>", "agr-mcp"]
    env:
      AGR_BLENDER: "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
```

Codex, `~/.codex/config.toml`, таблица `[mcp_servers.<name>]`. Живой образец той же команды `uv run --directory`: `[mcp_servers.3dsmax-mcp]` с `command` и `args` (`C:\Users\artsafro\.codex\config.toml:136-138`). Окружение — отдельная таблица `[mcp_servers.<name>.env]` (`config.toml:111`). Инвентарь пилота указывает этот файл и поля `command` / `local_path_args` (`docs/agr/inventory/mcp-registrations.json:56` и `:58-62`); в toml `local_path_args` записывается как `args`.

```toml
[mcp_servers.agr-mcp]
command = "uv"
args = ["run", "--directory", "<clone>", "agr-mcp"]

[mcp_servers.agr-mcp.env]
AGR_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
```

Antigravity, JSON в форме `.agents/mcp_config.json` (там `3dsmax-mcp` уже `uv` / `args` / `env`, строки 3–10):

```json
"agr-mcp": {
  "command": "uv",
  "args": ["run", "--directory", "<clone>", "agr-mcp"],
  "env": {"AGR_BLENDER": "C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"}
}
```

Claude Code, user scope, не файл проекта. CAPABILITIES: Claude берёт свои user-scope записи (`docs/agents/CAPABILITIES.md:137`). Команда `claude mcp add <name> -- <cmd>` — `C:\Users\artsafro\.hermes\hermes-agent\website\docs\user-guide\skills\bundled\autonomous-ai-agents\autonomous-ai-agents-claude-code.md:158`. Флаг `--scope user` (глобальная запись пользователя) — `C:\Users\artsafro\.claude\plugins\marketplaces\claude-plugins-official\plugins\mcp-server-dev\skills\build-mcp-server\references\remote-http-scaffold.md:186` (в той строке флаг показан на HTTP-примере; для stdio тот же scope). Файл user-scope на диске не открывался.

```
claude mcp add --scope user agr-mcp -- uv run --directory <clone> agr-mcp
```

Cursor (как уже было; записи `mcp-registrations.json`: `config` = `%USERPROFILE%\.cursor\mcp.json`, первая запись `docs/agr/inventory/mcp-registrations.json:2-6`, `command` = исполняемый файл из venv пакета):

```json
"agr-mcp": {
  "command": "C:\\Users\\artsafro\\src\\agr-mcp\\.venv\\Scripts\\agr-mcp.exe",
  "args": []
}
```

Версии: semver пакета (`agr-mcp` `0.x.y`) и целое `tool_schema_version` в каждом ответе и в журнале. Ломающее поле входа поднимает `tool_schema_version`. Пилот закрепляет git-tag `agr-mcp-vX.Y.Z` в строке CAPABILITIES (это правка уже фазы 2, не этого плана) и в lockfile dependency, когда пакет появится на индексе или как path/git pin. Пока репозитория нет, пилот ничего не закрепляет.

## 5. Переход

Фаза 0 — в этом пилоте, ветка работы по #807 (сейчас `improve/issue-807-...`). Сервер вызывает инструменты 1–3, 5–7, 9–10, 12–16. `agr_xview_check` и `agr_matid_check` в этой фазе — selection-modifying: живой вызов меняет выделение Max, потому что `_report` по умолчанию делает `select=True`. Геометрию и файлы они не пишут. Инструменты 3, 5–7, 9–10 и 12–16 на фазе 0 выделение, геометрию и файлы не меняют. Запись геометрии и файлов на фазе 0 не вызывается.

Импорт фазы 0 ограничен уже существующими модулями: `adapters/max/agr_tools/runtime.py` (после `build_agr_tools.py`, чтобы рядом лежали сгенерированные срезы), `src/twinqa/scene.py`, `src/twinqa/naming.py`, `src/twinqa/geojson.py`, `src/twinqa/profiles.py`, `tools/qa/validate_package.py`, `tools/qa/xview_parity.py`, `tools/blender/fbx_readback.py`. Новый геометрический код в фазе 0 не пишется. Обёртка MCP только резолвит handles, берёт lock, пишет JSONL и возвращает словарь функции.

Выходной тест расписан по инструментам, на синтетике, без производственной сцены:

| Инструмент | С чем совпасть |
|---|---|
| `agr_xview_check` | `runtime.xview` на той же копии |
| `agr_matid_check` | `runtime.matid` |
| `agr_texel_readout` | `runtime.texel_preview` |
| `agr_fbx_readback` | `scene.readback` по тому же FBX |
| `agr_package_validate` | `validate_package.validate` |
| `agr_mesh_names` | `mesh_name_findings` |
| `agr_geojson_check` | `geojson_findings` |
| `agr_xview_parity` | `xview_parity.compare` |

Плюс две проверки замка и журнала: параллельный вызов в тот же `host` получает отказ, пока lock держится; в JSONL число строк равно числу вызовов теста. Вызовы Max фазы 0 идут в уже открытую копию либо в `3dsmaxbatch` на копии. `agr_xview_check` и `agr_matid_check` при findings меняют выделение этой копии; остальные инструменты фазы 0 выделение не трогают. Сцена — синтетика, которую уже гоняют `tests/max_tools/` (каталог на этой ветке есть). Расхождение хотя бы одного кода finding — фаза 0 не сдана. После зелёного теста репозиторий `artsafro/agr-mcp` заводится отдельно, пилот зависит от тега. До зелёного теста отдельный репозиторий не создаём.

Фаза 1 — мутации на копиях: `agr_cleanup_apply`, `agr_ucx_apply`, `agr_export_commit`, затем `nudge_apply` и `atlas_apply` теми же именами. Выходной тест: исходный `.max` по хешу не изменился, новый FBX читается `agr_fbx_readback`, повторный commit в тот же путь — отказ. Сборщики `build_flat` / `maf_findings` / `flora_findings` остаются в пилоте; в MCP их поднимаем только если агенту иначе приходится тащить их через произвольный `bpy`.

Реализация этой фазы — issue #1021 (в issue она названа «phase 2», фаза 0 здесь = «phase 1» там). Десять инструментов, все `max-live`, runtime 0.9.0: `agr_cleanup_preview` / `agr_cleanup_apply`, `agr_uv_nudge_preview` / `agr_uv_nudge_apply`, `agr_atlas_preview` / `agr_atlas_apply`, `agr_ucx_preview` / `agr_ucx_apply`, `agr_export_preview` / `agr_export_commit`. Решения, зафиксированные кодом и тестами (`tests/agr_mcp/test_agr_mcp_phase2.py`):

- Цели только явные (контракт выделения §2, #851): непустой `handles` или `scope: "selection"`; оба или ни одного — ошибка `handles_required` / «two target sources» до вызова Max. `runtime._targets(None)` не достигается.
- Выделение сохраняется до вызова и восстанавливается после у всех десяти; расхождение после восстановления — `selection_changed`. `select_findings` в этой фазе не вводится.
- `preview` хранит мост в Max (по sha256 канонического JSON, 8 на семейство); apply получает родной объект runtime, только неизменённый и только один раз. Байты в preview (PNG атласа) клиент видит как `{"bytes", "sha256"}`.
- Новые узлы после apply = ровно отчётные копии; удалённый исходный узел — ошибка с его handle; preview, оставивший узел, — ошибка.
- `target` экспорта — новый абсолютный `.fbx` в существующей папке; `.report.json` и `.partial` рядом тоже новые; ни один из них не файл сцены. Проверка на сервере, до Max.
- Lock: каждый инструмент держит `agr-3dsmax-live.lock` на весь вызов (таймаут `AGR_MCP_MAX_TIMEOUT`); журнал — одна строка на вызов, у фазы плюс `scope`, `handles`, `written`.
- Люк произвольного кода не меняется: `agr_exec_unsafe` регистрируется только при `AGR_MCP_UNSAFE` ровно `1` (вопрос 4 §6, Артём 2026-11-04); у инструментов фазы нет поля `code`.
- Нативная сверка: `tests/agr_mcp/run_agr_mcp_phase2_native.py` в `3dsmaxbatch` на сцене полигона `polygon_all` выполняет тот же MAXScript, что сервер шлёт в pipe, и сравнивает с прямым вызовом runtime (Max 2026.3 и 2024.2.5: 10/10).

Фаза 2 — замена чужого MCP в skills и в разделе `3ds Max — 3dsmax-mcp` файла CAPABILITIES. Выходной тест: skill Ground/MAF/Flora вызывает `agr_*` и `dcc_batch` там, где batch ещё нужен; сценарий карточки больше не требует `execute_maxscript` / `execute_blender_code`. Регистрацию `3dsmax-mcp` и Blender Lab из конфигов убираем отдельным решением, когда фаза 2 зелёная. До того обе регистрации живут рядом.

## 6. Вопросы

Пять вопросов. Рекомендация стоит первой.

1. Фаза 0 ходит в Max через pipe уже стоящего `3dsmax-mcp` или сразу пишет свой listener? Рекомендация: pipe и вызов `runtime.*`, свой listener позже. Иначе фаза 0 строит второй мост раньше, чем есть хотя бы один зелёный инструмент.
2. Живой Blender входит в v1? Рекомендация: нет, только headless subprocess. Живые аддоны на 9876 и 9877 остаются чужими маршрутами до фазы 2.
3. Включать ли `dcc_batch.py acad` (22 совпадения) в этот сервер? Рекомендация: нет. #807 — Max и Blender. AutoCAD остаётся на `dcc_batch.py`.
4. Где живёт люк произвольного кода? Рекомендация: `agr_exec_unsafe` только при `AGR_MCP_UNSAFE=1`, всегда в JSONL, нет в обычном `tools/list`. В CAPABILITIES он сразу класс destructive.
5. Когда отрезаем `artsafro/agr-mcp`? Рекомендация: после выходного теста фазы 0, до мутаций фазы 1. Пилот до этого момента держит план и тесты контракта; пакет и инсталлятор переезжают в новый репозиторий одним тегом.

## 7. Источники

- MCP: ревизия 2026-07-28, проверена по сайту 2026-11-04, `https://modelcontextprotocol.io/specification/2026-07-28` и оглавление `https://modelcontextprotocol.io/specification`. Предыдущая ревизия, которую сайт ещё отдаёт: 2025-11-25 (`https://modelcontextprotocol.io/specification/2025-11-25`). Что из 2026-07-28 уже умеет локальный пакет `mcp` 1.30.0 — не сверено.
- `3dsmax-mcp`: локальная копия `C:\Users\artsafro\tools\3dsmax-mcp`. `pyproject.toml` `version = "1.7.5"` (это же число в CAPABILITIES). README той копии пишет «Current release: 1.7.2» — расхождение с `pyproject.toml`, в плане берётся 1.7.5. Исходники на GitHub: `https://github.com/cl0nazepamm/3dsmax-mcp`. Лицензия прочитана из локального `LICENSE`: MIT, Copyright (c) 2025 clone - m3org. Инструменты произвольного кода: `maxmcp/tools/execute.py` `execute_maxscript` (строка 12) и `execute_python` (строка 58). `execute_python` в docstring требует `safe_mode=false`.
- Blender, рабочий маршрут пилота: пакет с именем `blender-mcp` версии 1.0.3 в `C:\Users\artsafro\AppData\Local\CodexMCP\BlenderLab103\venv\Lib\site-packages\blender_mcp-1.0.3.dist-info\METADATA`. Поля License в этом METADATA нет. Лицензия **не проверена**. CAPABILITIES называет это Blender Lab MCP 1.0.3, порт 9877.
- ahujasid/blender-mcp (`https://github.com/ahujasid/blender-mcp`): в экспериментах (`docs/experiments/mcp-dcc-bridges.md:30`, порт 9876) это другой аддон, не пакет 1.0.3. Локальный LICENSE этого репозитория не читался. Лицензия **не проверена**.
- Обёртки вне worktree, только чтение: `C:\Users\artsafro\hermes_kanban\scripts\max_exec.py`, `dcc_batch.py`, заголовок `blender_exec.py`.
- Регистрации в репозитории: `.agents/mcp_config.json`, `docs/agr/inventory/mcp-registrations.json`.
- Hermes `mcp_servers`: `C:\Users\artsafro\.hermes\hermes-agent\website\docs\reference\mcp-config-reference.md:18-22`, `C:\Users\artsafro\.hermes\hermes-agent\website\docs\user-guide\profiles.md:11`, `C:\Users\artsafro\.hermes\hermes-agent\tools\mcp_tool_config.py:710`.
- Codex toml: `C:\Users\artsafro\.codex\config.toml:136-138` и `:111`.
- Claude Code CLI: `autonomous-ai-agents-claude-code.md:158`, `remote-http-scaffold.md:186`.

Не проверено и в план как факт не входит: схема всех 160 инструментов README `3dsmax-mcp` (README пишет 160 и релиз 1.7.2); актуальность GitHub-ревизии относительно локальной копии 1.7.5; файл user-scope Claude на диске (команда регистрации выше цитирует справку CLI, сам файл не открывался); совпадение SDK `mcp` 1.30.0 со спекой 2026-07-28; что #804 уже влит в это дерево (здесь AGR Tools 0.4.0).
