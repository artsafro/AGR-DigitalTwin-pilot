# Реестр дублей: статус каждой строки и порядок сжатия (#1424)

Кратко. Каждой строке `duplicates` всех шести карт контекстов (`contexts.yaml` — она же список разрешённых копий
`duplicate_guard` — и карты маршрутов ВПМ ОКС, Ground, МАФ, Флора, пакет) дан статус. Статус выведен из реальных
цепочек вызовов, а не из пути, и проверяется `tools/architecture/duplicate_guard.py` на каждом запуске:

- `live-bypass` — живой обход: файл достигается из живой команды или маршрута и не зовёт владельца;
  `step` — карточка сжатия, которая его уберёт («-» = карточки нет);
- `wrapper` — обёртка: функция строки зовёт владельца (импорт или `_sibling('<владелец>.py')`);
- `historical` — исторический: ни одна живая цепочка его не достигает, и он лежит в задании из `finished_jobs`
  (`contexts.yaml`: задание с принятым или сданным результатом и файл-доказательство);
- `own-duty` — своя обязанность, не копия; `why` говорит какая.

Живые корни (`tools/architecture/call_chains.py`): команды `dt`, `agr`, `agr-mcp` из `pyproject.toml`; файлы MZP
AGR Tools из списка `FILES` в `tools/max/build_agr_tools.py`; каждый `.py`, который называет маршрут (владельцы
локальных контекстов, доказательства этапов и ветвей) и владельцы карт; каждый скрипт `tools/`. Рёбра: `import`
(и ленивые внутри функций), `.py`-строки (запуск подпроцессом, `agr validate`, `dt derive`). Доказательства
«горячих точек» не корни: они называют проблему, а не шаг маршрута.

Охрана: новая строка `live-bypass` (нет в `LIVE_BYPASS_BASELINE`) — провал «NEW LIVE BYPASS»; строка из базы, которой
больше нет, — провал «FIXED LIVE BYPASS» (убрать из базы, храповик затягивается); `historical` вне законченного
задания или с живой цепочкой — провал с цепочкой; `wrapper`, который не зовёт владельца, — провал. Для правила
`blender-launch` обёрткой считается только вызов `blender_command` / `run_blender` (`POLICY_NAMES`): взять у владельца
один путь к Blender и собрать командную строку самому — обход.
Пересчитать таблицу: `uv run python tools/architecture/duplicate_guard.py --table` (тест сверяет её с этим файлом).

### Живые обходы по областям

Строк дублей во всех картах: 123; живой обход 30, обёртка 4, исторические 80, своя обязанность 9; разных живых копий 30.

| Область | Живых обходов | Файлы | Шаг сжатия |
|---|---|---|---|
| Связь с DCC (Blender / 3ds Max) | 16 | `src/dt_ai/cli/shared_tools.py`, `tools/flora/build_flora_npm_light.py`, `tools/flora/build_flora_star.py`, `tools/library/check_library.py`, `tools/library/migrate_windows.py`, `tools/materials/bind_ground_textures.py`, `tools/methods/body/run_benchmarks.py`, `tools/methods/ground/build_variant.py`, `tools/methods/parametric_parts/mesh_recipe.py`, `tools/methods/run_variant.py`, `tools/methods/ucx/run_benchmarks.py`, `tools/methods/windows/run_benchmarks.py`, `tools/research/checker_mutation.py`, `tools/research/fbx_reader_compare.py`, `tools/sintez_parity.py` | нет карточки |
| Общее ядро: номер тайла UDIM | 11 | `adapters/max/agr_tools/atlas_core.py`, `adapters/max/agr_tools/npm2vpm_core.py`, `adapters/max/agr_tools/npm_core.py`, `adapters/max/agr_tools/udim_core.py`, `adapters/max/agr_tools/udimplug_core.py`, `adapters/max/agr_tools/udimview_core.py`, `adapters/max/agr_tools/uvlayout_core.py`, `adapters/max/agr_tools/uvtile_core.py` | нет карточки |
| UV и атлас | 1 | `tools/materials/npm_atlas_udim.py` | #1380 |
| Коллизии UCX (только ВПМ) | 1 | `jobs/KPP1/scripts/vpm_ucx.py` | #1404 |
| Экспорт и пакет сдачи | 1 | `jobs/VATUTINO-SITE/npm_code.py` | нет карточки |

### Порядок оставшихся шагов сжатия (по живым обходам)

| № | Шаг | Живых обходов |
|---|---|---|
| 1 | нет карточки | 28 |
| 2 | #1380 | 1 |
| 3 | #1404 | 1 |
| 4 | #1379 | 0 |
| 5 | #1381 | 0 |
| 6 | #1397 | 0 |
| 7 | #1405 | 0 |
| 8 | #1406 | 0 |
| 9 | #1407 | 0 |
| 10 | #1410 | 0 |

### Рекомендуемый порядок сжатия

1. **Новая карточка: свой запуск Blender в живых инструментах (16 строк, 15 файлов).** После слияния с #1378
   правило `blender-launch` нашло командные строки Blender мимо `blender_command` / `run_blender` в `tools/`
   (Флора, библиотека, текстуры Ground, каталог методов, исследования, сверка СИНТЕЗ) и в `dt derive`
   (`src/dt_ai/cli/shared_tools.py`). Четыре инструмента методов берут у владельца только путь к Blender
   (`blender_executable`), а командную строку собирают сами (без `--disable-autoexec`, без изоляции настроек) —
   это обход, не обёртка. Нужна карточка «Сжатие 3b».
2. **Новая карточка: копии UDIM в ядрах AGR Tools (11).** Восемь ядер MZP (`npm_core`, `udim_core`, `uvtile_core`,
   `udimplug_core`, `udimview_core`, `uvlayout_core`, `npm2vpm_core`, `atlas_core`) считают тайл сами, хотя рядом
   лежит `udimtile_core` (#1337). Ни один открытый шаг их не покрывает (#1376 закрыт, #1397 — только `tools/` и
   `src/`). Нужна карточка «Сжатие 1c».
3. **#1397 completed:** live Ground, Flora, methods and DreamSim UDIM helpers now call `udimtile_core`.
   Source intake keeps its raw tile diagnostic as `own-duty` (arbitrary UVs, not a delivery UDIM).
4. **#1379 (0)** — запуск чекера СИНТЕЗ объединён: маршруты НПМ / ВПМ / пакет идут через `agr checker` и общего владельца `tools/blender/sintez_checker.py`.
5. **#1380 (1)** — `tools/materials/npm_atlas_udim.py`, путь А атласа НПМ (после #1141).
6. **#1404 (1)** — UCX ВПМ через `jobs/KPP1/scripts/vpm_ucx.py`.
7. **Без карточки (1)** — `jobs/VATUTINO-SITE/npm_code.py::rename_npm_zip`: этап «загрузка» маршрута пакета пишет
   ZIP сам; закрыть вместе с командой загрузки (#1379 — ближайший шаг).
8. **#1381, #1405, #1406, #1407, #1410 (0)** — живых обходов нет: копии корпуса КПП1 (#1381) исторические; свой запуск
   Blender в `jobs/VATUTINO-SITE/place_site.py` (#1407) убран в #1378 (теперь `run_blender`); #1405, #1406, #1410 —
   недостающие команды (красные блоки маршрутов), а не дубли; их порядок задаёт маршрут, не этот реестр.
