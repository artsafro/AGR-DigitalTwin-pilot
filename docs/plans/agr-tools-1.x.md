# AGR Tools 1.x: что сделано в 1.0, хвост и хендофф Max↔Blender

> **Статус: ПЛАН, не факт.** Раздел 1 — сводка того, что записано в `adapters/max/agr_tools/CHANGELOG.md` (1.0.0, #1024), прочитанная [стат.], без повторного прогона. Разделы 2–4 — очередь работ после 1.0.0: что решено владельцем и ещё не исполнено в коде. Реестр кнопок и их версий — `docs/plans/agr-tools-suite.json`; точка входа для агента — `docs/agr-tools/OVERVIEW.md`.

## 1. Что сделано в 1.0.0

Конвейер ОКС: паспорт проекта, этапы 0–9 и агентский мост. Ветка 0 дала основу, ветки F…U наполнили кнопки, ветка R собрала релиз (CHANGELOG 1.0.0, «Релиз»).

| Этап | Кнопки (id в плане) | Ветка |
|---|---|---|
| 0 Паспорт | `project.passport`, `source.intake`, `scene.source_class`, `scene.small_parts` | F |
| 1 Бадик | `body.prepare`, `model.attach_by_material`, `model.move_apart`, `model.grid_cleanup` | G, H |
| 2 Окна | `win.generate`, `win.place`, `model.glass_planes` | J, H |
| 3–4 Капсулы, крыша | `body.capsules`, `body.roof` | K |
| 5 Материалы | `mat.table`, `mat.tiles`, `tex.plug_colour` | L |
| 6 ВПМ | `vpm.build`, `udim.rescale`, `udim.distortion`, `tex.dilate`, `udim.plugs` | M, N |
| 7 НПМ | `npm.build`, `atlas.facade_strip` | P |
| 8 НПМ → ВПМ | `npm.to_vpm`, `udim.udims_to_ids` | Q |
| 9 Сдача | `ucx.gap`, `light.export`, `pack.deliver`, `ucx.stairs`, `qa.omk_te`, `export.place_by_passport` | S, T |
| Агент | `agent.request`, `agent.accept`, мост `agr-mcp`, лот L12b | U |

Проверено на релизе (CHANGELOG, «Релиз»): полигон Max 2024 на ноутбуке через AGR Lab runner — 0 расхождений по базам 0.1–1.0 (в базе 1.0 — 33 станции); MZP 1.0.0 собирается побайтно одинаково; живой Max 2026 в изолированном слоте подтвердил мост агента и `agent.accept` (лот L12b). Не проверено: прогон полигона в Max 2026 — за оркестратором на ПК; корпус OBJ03 и школа SOSH1150 (копий корпуса нет в разрешённых папках); три сценарных eval агента в ночном Lab CI не включены. Ручная проверка владельца в интерактивном Max (Undo после `light.check`, одна запись Undo на `place.*`, светлая тема панели): «всё норм».

Сквозняк на синтетическом KPP1-like (`tests/max_tools/run_agr_tools_kpp1_e2e_native.py`, Max 2024) проходит этапы 0–5 и 7 и **не** проходит 6, 8 и 9 — подробности и цифры в CHANGELOG, «Известные ограничения»; они же — главный пункт хвоста ниже.

Сверка источников: в сообщении коммита релиза сказано, что ветка Q отложена на 1.1, а CHANGELOG 1.0.0 включает Q (#1085) и считает 33 выпущенные кнопки. Перед ссылкой на состав релиза сверяйтесь с `docs/plans/agr-tools-suite.json` (`version`, `deferred`) и `ui_model.WIP_100`.

## 2. Хвост 1.x

### 2.1 Из «Известных ограничений» CHANGELOG 1.0.0

- **Сквозняк KPP1, этап 6.** `vpm.build` с `library_path` отказывает: `matlib_core` хранит roughness 0..255, `vpmmaps_core.erm_colour` ждёт 0..1. `udim.plugs` отказывает на копии `vpm.build` (Editable_Mesh вместо Editable_Poly).
- **Этап 8.** `npm.to_vpm` отказывает `udim_mismatch` на НПМ из `npm.build` того же прогона.
- **Этап 9.** Сдача блокируется гейтом cleanup `export.checked` (у UCX 0.8 нет канала 1, канал Main не переименован, user props `agr_*` кнопок 1.0); `qa.names` отвергает имена подматериалов `mat.table` (`L0NN_*`); `ucx.rename` не переименовывает куски `*_AGR_ucx__NN`; `AGR_EXPORT_PATH`, `AGR_ZERO_M` и перенос копии ВПМ на слой «0» ни одна кнопка 1.0 не делает.
- **SINTEZ и пакет.** Нужен отчёт SINTEZ AGR Checker из Blender (`qa.sintez` без него отказывает); `qa.package` не запускался — архива нет.
- **Панель.** Панель передаёт кнопке 1.0 только выделение, без `options`; 15 из 31 кнопки в релизном смоуке отказывают с понятным текстом (нужна сохранённая сцена, Editable Poly или параметр, которого в панели нет: `atlas.facade_strip` — `period_by_id`, `tex.dilate` / `tex.plug_colour` — файлы, `export.place_by_passport` — `fbx`, `agent.request` — `task`, `agent.accept` — `request`). Формы параметров в панели — 1.1; пока параметры задаются через MCP (`agr_op_preview`) или скриптом.
- **Агент.** Кнопка `agent.dock` (Claude-док) не зарегистрирована в панели (функция `agentbridge_max.agent_dock` есть); операции `place_window`, `make_capsule`, `make_roof_plane` зависят от J и K; живой Max подтверждён только на Max 2026.
- **Ветка за веткой.** G: `model.move_apart` пропускает объекты с модификаторами и примитивы. H: `model.glass_planes` — не-квад даёт `ambiguous`; `model.grid_cleanup` без канала 1 — `skipped`. J: 6 из 67 типов окон в карантине, арка, угловой и нестандартный проём в `win.place` дают `ambiguous`; лист превью PNG не лежит в git (бюджет LFS). K: отказы `ambiguous` вместо капсулы (`border_nonplanar`, `corner_concave`, `corner_unsupported`, `capsules_overlap`…), материал капсулы — заглушка `LIB_Interior_Stub`; `body.roof` при уклоне > 10° — `roof_steep` и запрос агенту. M: швы на рёбрах замыкания контура и трёхгранных углах откосов. P: раскладка `layout` (`islands` / `stack`) — вопрос владельцу, параметр. T: без `accept_precision_loss` apply не идёт при ошибке одинарной точности Max (> 1 мм на больших МСК-координатах); `qa.omk_te` без своей таблицы (параметр `table`).

### 2.2 Решения владельца, ещё не доведённые до кода

Решения записаны в `docs/decisions.md`; код на момент переноса частично несёт значения до решений.

| Что | Решение | Состояние кода (по файлам) |
|---|---|---|
| Плотность текстур | 1000 px/м, тайл UDIM 3,6 м = 3600 px [D206] | `adapters/max/agr_tools/tiles_core.py`: `px_per_m` по умолчанию 1024 (комментарий «audit Q1 open») — переключить, пересобрать `library/materials/materials_v002.json`, поправить тесты `tests/max_tools/` |
| Таблица материалов | Q2–Q12 [D215]–[D217] | `library/materials/materials_v001.json` ещё до решений: кассета KPP, RAL 8023 без RGB; добавить RAL 8023, 7024, 9006, 7035 в `tools/materials/ral_classic.json`, параметрический паттерн «N рёбер на поле», две текстуры газона, отдельная таблица Ground |
| Кирпич | 14 кирпичей на тайл, шаг 257,14 мм, допуск `tile_facts` 1,5 % [D215] | проверить в `tiles_core.py` (`max_stretch_pct`) |
| Образцы текстур | четыре PNG в `AGR-assets/textures/samples/` [D217] | путь записан в `library/README.md`; наличие файлов на Диске не проверялось |
| Ассеты ВПМ | флора и МАФ — в UDIM после UDIM Ground [D209] | исполнение в `vpm_core.py` / `flora_atlas_max.py` в этом переносе не проверялось |
| Таблица SOSH1150 | реестр отделок F1…F14 — когда docx или `materials.json` окажется в репозитории [D217] | пробел; штукатурка и кровля жилых |
| Материалы AC.05–07 и трубы | заполнить из рабочих Max-сцен, не блокирует [D217] | пробел |

### 2.3 Строки плана с версией 1.x

В `docs/plans/agr-tools-suite.json` у строк `version: 1.x` и `fate: tail` — очередь после 1.0: `model.ground_border`, `model.ground_slice`, `model.ground_surface`, `model.three_pt_align`, `model.pipe_lo`, `tex.browser`, `ucx.ground`, `place.maf_generator`, `place.scatter`, `place.tree_cards`, `light.place`, `export.library_zip`, `qa.names_library`. Строки `obsolete` (`tex.multimat`, `udim.unwrap_tiles`, `udim.viewer`) не реализуются: их заменили кнопки 1.0. Приоритет и порядок определяет владелец; `place.scatter` и работа со сторонними скаттер-плагинами вне границ AGR Tools (`docs/agents/agr-tools-impl-rules.md`).

### 2.4 Агент и MCP

Очередь из ревью MCP (`docs/plans/agr-mcp-target.md`): операции агента `place_window`, `make_capsule`, `make_roof_plane`; три сценарных eval агента («сделай станцию 1.0.N зелёной», приёмка К4 с откатом, «разметь проёмы KPP1 → типы окон») в ночной Lab CI; проверка пути через `agr_mcp`, а не сырой `3dsmax-mcp`; снятие регистрации `3dsmax-mcp` после проверки своего listener [D210].

## 3. Хендофф Max ↔ Blender (карточка BH, после 1.0.1)

Решение владельца: запускать после релиза `agr-tools-v1.0.1`. Ветка `improve/issue-1024-blender-handoff`, PR «Part of #1024» (или новый issue 1.x). Основание: контракт бандла в `docs/plans/agr-mcp-target.md` §3.12 и контракты ветки 0 (`adapters/max/agr_tools/contract_core.py`: `ObjRef`, `HostAdapter`, роли `agr_role`). Блок «в Blender» ниже — план, в коде его пока нет [стат.].

### Что сделать

1. **Схема v1:** `schemas/Handoff.schema.json`.
   - manifest: единицы, ось, `system_scale`; объекты (name, `agr_role`, layer, parent, world matrix, `instance_of`, хеши геометрии); таблица `slot_index ↔ matID ↔ library_id ↔ UDIM`; UV-каналы;
   - sidecar: user props, hard edges и сглаживание, метки `OPEN_*`, `LEVEL_*`.
2. **`materials.json` (критично) [D213].** Перед выгрузкой из Max рядом со сценой пишется: для каждого объекта — назначенный материал, тип (Standard Legacy и т. п.), Multi/Sub с ID, все подключённые карты с путями, имена нод и их настройки.
3. **Кнопки в Max:**
   - `handoff.export` — FBX + manifest + sidecar + `materials.json`;
   - `handoff.import` — FBX из Blender в слой `AGENT_<req>`, приёмка через `agent.accept` [D212];
   - **«Восстановить материалы»** — переподключает материалы и карты по `materials.json`; объекты сопоставляются по имени и роли, несопоставленные идут в отчёт.
4. **Сторона Blender (headless, `blender_runner` 5.1.2):** импорт бандла и экспорт обратно с сохранением имён, слотов материалов, UV, нормалей, единиц, пивотов, квадов и инстансов.
5. **`handoff.verify`** — readback обеих сторон и сравнение по таблице §3.12 плана MCP.
6. **MCP-инструменты:** `agr_handoff_export`, `agr_handoff_import`, `agr_handoff_verify` — правка `src/agr_mcp/tools.py` маленьким PR.

### Бандл

`handoff/<job>/<seq>/`: `model.fbx` — рабочий, без триангуляции, квады и n-гоны как построены (по образцу [D198]), без UCX; `manifest.json`; `sidecar.json`; `materials.json`. Что обязано пережить круг и допуски — таблица в `docs/plans/agr-mcp-target.md` §3.12 (имена и роли 1:1; matID ↔ слоты по таблице; UV/UDIM — целые части тайлов равны, дробная ≤ 1e-6, метрика шва 0; единицы метры, bbox ±0,1 мм; world matrix ±1e-5; число полигонов и рёбер равно; инстансы остаются инстансами).

UDIM нумеруется в каждом меше отдельно с 1001 [D208]: тело ОКС и окна/стекло — отдельные меши, у каждого 1001.

### Приёмка

- Синтетика: куб с n-гоном, 3 matID, 2 UV-канала, инстанс, пивот не в нуле, сцена в см. Круг Max → Blender → Max даёт 0 расхождений по таблице.
- Материалы Standard Legacy с картами (diffuse, bump, opacity) и Multi/Sub после круга восстанавливаются кнопкой; пути карт и имена нод совпадают, отчёт пустой.
- Копия KPP1-like (синтетика `tests/max_tools/run_agr_tools_kpp1_e2e_native.py`): круг без потерь.
- Нативно: AGR Lab runner, слоты Max 2024 и Blender 5.1, не больше 25 джобов (`docs/agents/agr-tools-impl-rules.md`).

### Не делать

Полный паритет AGR Tools в Blender (N-panel, порт кнопок) — после чекпоинта MVP, раздел 4.

## 4. Паритет Blender после MVP в Max

Решение владельца (06.11.2026, передано координатором): Blender — полноценный второй хост. После MVP в Max те же AGR Tools и тот же MCP строятся для Blender, а чистая квадовая модель возвращается в Max.

**Критерии чекпоинта MVP** (§4.5 ревью MCP). Старт паритета — только при выполнении всех:

1. AGR Tools 1.0.0 выпущен, полигон 0.1–1.0 с 0 расхождений в Max 2024 и 2026 (на момент переноса подтверждён Max 2024, Max 2026 — прогон оркестратора).
2. MVP MCP: конверт v2, `preview_id`, журнал; профили `observer` / `operator`; все инструменты кнопок 1.0 проходят нативное равенство; не меньше одного сценарного eval агента зелёный три ночи подряд.
3. Шлюз К4 работает в Max: откат доказан тестом.
4. Ни один новый `*_core.py` 1.0 не принимает pymxs-объекты; handle-специфика спрятана за `ObjRef`.
5. Схема хендоффа v1 и `agr_handoff_verify` зелёные на синтетике (раздел 3).

**Порядок паритета:**

- **B0 — общий слой.** `HostAdapter` для bpy, `ObjRef`; хост `blender-batch` получает операции, а не только readback.
- **B1 — хендофф.** Max → Blender → Max на копии KPP1: таблица §3.12 с нулевыми расхождениями.
- **B2 — Blender-first операции.** Меню D108, капсулы и крыша, UV шов к шову, UCX, рендер-листы: те же id операций и те же `expected`; полигон дублируется сценой `.blend`.
- **B3 — Blender-панель.** N-panel из `ui_model.py` / `roadmap.py` и мост `blender-live` (свой аддон).
- **B4 — сравнение.** Время по этапам Max против Blender на триадах эталона; решение, какие этапы закреплять за Blender.

Риски: двойная поддержка адаптеров; потери в FBX-круге (matID, имена, инстансы); два слота Blender в AGR Lab; финальный экспорт — из Max или Blender (по [D211] допустимо и то и другое, предпочтительно Max).
