# Реестр дублей: статус каждой строки и порядок сжатия (#1424)

Кратко. Каждой строке `duplicates` всех шести карт контекстов (`contexts.yaml` — она же список разрешённых копий
`duplicate_guard` — и карты маршрутов ВПМ ОКС, Ground, МАФ, Флора, пакет) дан статус. Статус выведен из реальных
цепочек вызовов, а не из пути, и проверяется `tools/architecture/duplicate_guard.py` на каждом запуске:

- `live-bypass` — живой обход: файл достигается из живой команды или маршрута и не зовёт владельца;
  `step` — карточка сжатия, которая его уберёт («-» = карточки нет);
- `wrapper` — обёртка: функция строки зовёт владельца (импорт или `_sibling('<владелец>.py')`);
- `historical` — исторический: ни одна живая цепочка его не достигает, и он лежит в задании из `finished_jobs`
  (`contexts.yaml`: задание с принятым или сданным результатом и файл-доказательство);
- `own-duty` — своя обязанность, не копия; `why` говорит какая;
- `superseded` — заменённый черновик (не сдача), с обязательным `why` и без живой цепочки (#1441).

**Сверка #1441:** ЭЛВ не сдан (Артём, 15.11); v001–v005 — заменённые черновики, v006 — живой кандидат.
#1104 остаётся parked. Построчные доказательства и исправления: [report-1441.md](report-1441.md).
`entrypoints` в contexts.yaml добавляет пропущенные текущие команды shell и кандидатов: путь и текст
файла-доказательства проверяются на каждом запуске. Это статическая достижимость, не исполнение DCC.

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

Строк дублей во всех картах: 116; живой обход 38, обёртка 7, исторические 36, своя обязанность 23; разных живых копий 37.
Заменённые черновики (не сдача): 12.

| Область | Живых обходов | Файлы | Шаг сжатия |
|---|---|---|---|
| Связь с DCC (Blender / 3ds Max) | 16 | `src/dt_ai/cli/shared_tools.py`, `tools/flora/build_flora_npm_light.py`, `tools/flora/build_flora_star.py`, `tools/library/check_library.py`, `tools/library/migrate_windows.py`, `tools/materials/bind_ground_textures.py`, `tools/methods/body/run_benchmarks.py`, `tools/methods/ground/build_variant.py`, `tools/methods/parametric_parts/mesh_recipe.py`, `tools/methods/run_variant.py`, `tools/methods/ucx/run_benchmarks.py`, `tools/methods/windows/run_benchmarks.py`, `tools/research/checker_mutation.py`, `tools/research/fbx_reader_compare.py`, `tools/sintez_parity.py` | нет карточки |
| Общее ядро: номер тайла UDIM | 15 | `adapters/max/agr_tools/atlas_core.py`, `adapters/max/agr_tools/npm2vpm_core.py`, `adapters/max/agr_tools/npm_core.py`, `adapters/max/agr_tools/udim_core.py`, `adapters/max/agr_tools/udimplug_core.py`, `adapters/max/agr_tools/udimview_core.py`, `adapters/max/agr_tools/uvlayout_core.py`, `adapters/max/agr_tools/uvtile_core.py`, `jobs/KPP1/scripts/vpm_uv.py`, `jobs/TEC26-OKS/scripts/vpm_uv.py`, `jobs/elv-tc-vpm/scripts/uv_tex_full_v008.py` | нет карточки |
| Экспорт и пакет сдачи | 2 | `jobs/TEC26-OKS/scripts/package_vpm.py`, `jobs/elv-tc-vpm/scripts/package_vpm_v006.py` | #1377 |
| UV и атлас | 1 | `tools/materials/npm_atlas_udim.py` | #1380 |
| Копия раскладки UV ВПМ | 1 | `jobs/TEC26-OKS/scripts/vpm_uv.py` | нет карточки |
| Пакеты НПМ / ВПМ и передача | 1 | `jobs/TEC26-OKS/scripts/package_vpm.py` | #1377 |
| Экспорт и пакет сдачи | 1 | `jobs/VATUTINO-SITE/npm_code.py` | нет карточки |

### Порядок оставшихся шагов сжатия (по живым обходам)

| № | Шаг | Живых обходов |
|---|---|---|
| 1 | нет карточки | 33 |
| 2 | #1377 | 3 |
| 3 | #1380 | 1 |
| 4 | #1379 | 0 |
| 5 | #1381 | 0 |
| 6 | #1397 | 0 |
| 7 | #1404 | 0 |
| 8 | #1405 | 0 |
| 9 | #1406 | 0 |
| 10 | #1407 | 0 |
| 11 | #1410 | 0 |

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
6. **#1404 (0 относительно ucx10_core)** — построитель UCX и измеритель зазора имеют разные обязанности.
7. **Без карточки (1)** — `jobs/VATUTINO-SITE/npm_code.py::rename_npm_zip`: этап «загрузка» маршрута пакета пишет
   ZIP сам; закрыть вместе с командой загрузки (#1379 — ближайший шаг).
8. **#1381 (3)** — сделано: шов КПП1 перенесён в `tools/blender/seam_seal.py` (правило `seam-seal`), плита кровли `build_kpp1.roof` берёт контур и высоту из `roof_core.hole_plate` (обёртка).
9. **Владелец #1377 (3 строки)** — TEC26 ZIP (описательная и hash-pinned строки) и кандидат ELV v006:
   будущая миграция на package_core; закрытый предыдущий шаг не доказывает перенос этих файлов.
10. **#1405, #1406, #1407, #1410 (0)** — place_site уже вызывает run_blender; остальные — недостающие команды.
11. **Без карточки: ещё 4 формулы UDIM и TEC26 pack_uv.** Текущие KPP1/TEC26 и кандидат ELV v008,
    не сданные исторические копии. Числа таблицы — `(at, hash)`, не уникальные обязанности.
