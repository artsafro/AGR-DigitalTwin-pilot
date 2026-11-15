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
задания или с живой цепочкой — провал с цепочкой; `wrapper`, который не зовёт владельца, — провал.
Пересчитать таблицу: `uv run python tools/architecture/duplicate_guard.py --table` (тест сверяет её с этим файлом).

### Живые обходы по областям

Строк дублей во всех картах: 112; живой обход 28, обёртка 7, исторические 70, своя обязанность 7; разных живых копий 27.

| Область | Живых обходов | Файлы | Шаг сжатия |
|---|---|---|---|
| Общее ядро: номер тайла UDIM | 11 | `src/dt_ai/geometry/ground_cake.py`, `tools/blender/ground_json_to_fbx.py`, `tools/experiments/dreamsim_ac08.py`, `tools/flora/build_flora_star.py`, `tools/methods/methods_metrics.py`, `tools/methods/windows/windows_variants.py`, `tools/source/measure_spec_blender.py` | #1397 |
| Общее ядро: номер тайла UDIM | 11 | `adapters/max/agr_tools/atlas_core.py`, `adapters/max/agr_tools/npm2vpm_core.py`, `adapters/max/agr_tools/npm_core.py`, `adapters/max/agr_tools/udim_core.py`, `adapters/max/agr_tools/udimplug_core.py`, `adapters/max/agr_tools/udimview_core.py`, `adapters/max/agr_tools/uvlayout_core.py`, `adapters/max/agr_tools/uvtile_core.py` | нет карточки |
| UV и атлас | 1 | `tools/materials/npm_atlas_udim.py` | #1380 |
| Коллизии UCX (только ВПМ) | 1 | `jobs/KPP1/scripts/vpm_ucx.py` | #1404 |
| Проверка и приёмка | 1 | `jobs/KPP1/scripts/run_agr_checker.py` | #1379 |
| Связь с DCC (Blender / 3ds Max) | 1 | `jobs/VATUTINO-SITE/place_site.py` | #1407 |
| Экспорт и пакет сдачи | 1 | `jobs/VATUTINO-SITE/npm_code.py` | нет карточки |

### Порядок оставшихся шагов сжатия (по живым обходам)

| № | Шаг | Живых обходов |
|---|---|---|
| 1 | нет карточки | 12 |
| 2 | #1397 | 11 |
| 3 | #1379 | 1 |
| 4 | #1380 | 1 |
| 5 | #1404 | 1 |
| 6 | #1407 | 1 |
| 7 | #1381 | 0 |
| 8 | #1405 | 0 |
| 9 | #1406 | 0 |
| 10 | #1410 | 0 |

### Рекомендуемый порядок сжатия

1. **Новая карточка: копии UDIM в ядрах AGR Tools (11).** Восемь ядер MZP (`npm_core`, `udim_core`, `uvtile_core`,
   `udimplug_core`, `udimview_core`, `uvlayout_core`, `npm2vpm_core`, `atlas_core`) считают тайл сами, хотя рядом
   лежит `udimtile_core` (#1337). Это самый большой живой обход, и ни один открытый шаг его не покрывает
   (#1376 закрыт, #1397 — только `tools/` и `src/`). Нужна карточка «Сжатие 1c».
2. **#1397 (11)** — UDIM в живых маршрутах Ground (`ground_cake`), Флора (`build_flora_star`) и в инструментах
   `tools/` (методы, эксперимент, замер исходника; для `measure_spec_blender` сначала решение: сырой тайл или отказ).
3. **#1379 (1)** — запуск чекера СИНТЕЗ: маршруты НПМ / ВПМ / пакет идут через `jobs/KPP1/scripts/run_agr_checker.py`.
4. **#1380 (1)** — `tools/materials/npm_atlas_udim.py`, путь А атласа НПМ (после #1141).
5. **#1404 (1)** — UCX ВПМ через `jobs/KPP1/scripts/vpm_ucx.py`.
6. **#1407 (1)** — свой запуск Blender в `jobs/VATUTINO-SITE/place_site.py` (расстановка; сам `run` уже обёртка движка).
7. **Без карточки (1)** — `jobs/VATUTINO-SITE/npm_code.py::rename_npm_zip`: этап «загрузка» маршрута пакета пишет
   ZIP сам; закрыть вместе с командой загрузки (#1379 — ближайший шаг).
8. **#1381, #1405, #1406, #1410 (0)** — живых обходов нет: копии корпуса КПП1 (#1381) исторические, а #1405, #1406,
   #1410 — недостающие команды (красные блоки маршрутов), а не дубли; их порядок задаёт маршрут, не этот реестр.
