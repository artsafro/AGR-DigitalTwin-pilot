# Хендофф Max ↔ Blender с материалами (ветка BH, #1024)

06.11.2026, 3ds Max 2024 (ноутбук, AGR Lab runner) и Blender 5.1.2. Только синтетические сцены и копия KPP1, которые строят сами джобы.
Код: `adapters/max/agr_tools/handoff_core.py` (чистое ядро, без pymxs/bpy), `adapters/max/agr_tools/handoff_max.py`,
`tools/blender/handoff_blender.py`; схема бандла `schemas/Handoff.schema.json`.
Тесты: `tests/max_tools/test_agr_tools_handoff.py` (дефекты H1–H9), нативный прогон `tests/max_tools/run_agr_tools_handoff_native.py`.

## 1. Что сделано

Бандл `handoff/<job>/<seq>/`:

- `model.fbx` — не триангулирован, метры, Z-up;
- `manifest.json` — объекты, трансформы, слоты материалов, `instance_of`, `ngon_ref` (`handoff_core.py:506`, `:529`);
- `sidecar.json` — роли, user props, маркеры (`OPEN_001`, `LEVEL_L1` живут только здесь) (`handoff_core.py:565`);
- `materials.json` — материалы сцены; та же копия пишется рядом со сценой как `<scene>.materials.json`
  (с суффиксом `_vNNN`, если файл уже есть) (`handoff_core.py:603`);
- `readback_max.json` — факты, перечитанные из Max после экспорта (эталон для сверки).

Четыре функции (`handoff_max.py`):

| Функция | Что делает | Где |
|---|---|---|
| `handoff.export` | пишет бандл из выделения или слоя | `handoff_max.py:427` |
| `handoff.import` | читает FBX бандла только в слой `AGENT_<req>`; пишет `request.json` + `baseline.json` для `agent.accept` ветки U | `handoff_max.py:668` |
| `handoff.verify` | read-only: сверка сцены с бандлом, число расхождений | `handoff_max.py:804` |
| `handoff.restore_materials` («Восстановить материалы») | подбор по имени и роли; имена Blender `.001` и обрезанные до 63 байт восстанавливаются; материал сцены используется повторно, если он идентичен (`reuse=scene`), либо пересобирается из JSON (`reuse=never`); каждый параметр перечитывается и сравнивается; несопоставленные и неоднозначные объекты попадают в отчёт | `handoff_max.py:859`, `handoff_core.py:767` |

Сторона Blender — скрипт `tools/blender/handoff_blender.py`: `import_bundle` (`:215`), `normalise` (`:91`), `relink_instances` (`:133`),
`dissolve_diagonals` (`:155`), `mark_sharp_from_reference` (`:187`), `export_bundle` (`:318`), `roundtrip` (`:335`).

## 2. materials.json

На каждый объект: ключ материала. Узлы лежат в общем списке:

- класс: `Standardmaterial` (Standard Legacy), `Multimaterial` (Multi/Sub с `materialIDList`), `Bitmaptexture` (с `filename`);
- имена узлов;
- ВСЕ параметры из `getPropNames`, закодированные типами `color` / `point` / `name` / `array` / `ref` / `sub` / `skip`;
- общие узлы остаются общими (одна запись, несколько ссылок);
- список `maps`: пути карт и их пользователи.

Сравнение двух наборов узлов — `diff_nodes` (`handoff_core.py:709`), допуск `TOL['float']`. Проверка схемы — `validate_materials` (`:610`).
Писатель в Max — `MaterialWriter` (`handoff_max.py:211`), сборщик — `MaterialBuilder` (`:301`).

## 3. Измеренные дефекты простого круга FBX и их исправления

- **Триангуляция.** Экспортёр FBX Max 2024 пишет ТРЕУГОЛЬНИКИ для Editable_Mesh и для мешей с n-гонами рядом с другими гранями
  (диагностика `20261106-134859-6511047e`: box, box+UV2, цилиндр sides=4 остаются квадами; 8-угольный цилиндр и 8-угольная призма,
  собранная `createPolygon`, становятся треугольниками; одинокий пятиугольник остаётся 5-угольником), а также для инстансированного
  Editable_Poly при `Preserveinstances` (`20261106-134044-fbdf80ba`). Исправление: экспорт временных копий Editable_Poly
  (`_export_copies`, `handoff_max.py:181`), `Preserveinstances` выключен (`FBX_EXPORT_PARAMS`, `handoff_core.py:58`); меши с n-гонами несут
  `ngon_ref` (исходные рёбра и вершины), диагонали триангуляции (`diagonals`, `handoff_core.py:212`) растворяются в Blender (bmesh,
  `dissolve_diagonals`) и при импорте в Max (`_dissolve_diagonals`, `handoff_max.py:615`, Remove edges у EditablePoly).
- **Масштаб и пивот в матрице объекта Blender.** Импортёр кладёт масштаб единиц cm (0,01) и смещение объекта Max (геометрическая
  трансформация FBX) в МАТРИЦУ ОБЪЕКТА; потомок наследует смещение пивота родителя (GLASS_001 сдвинулся на смещение пивота BODY_Brick_001,
  `20261106-134044-fbdf80ba`). Исправление: смещения запекаются на экспортных копиях; в `normalise()` (`handoff_blender.py:91`)
  G = W_ref⁻¹ @ M_cur уходит в данные меша, матрица объекта = трансформ из манифеста, масштаб 1.
- **Импорт FBX в Max** кладёт пересчёт м→см в масштаб УЗЛА 100 (`20261106-134859-c0574780`). Исправление: `_set_transforms`
  (`handoff_max.py:590`) выставляет трансформы узлов из манифеста, сохраняя мировые вершины.
- **Группы сглаживания** приходят в Blender только как пользовательские нормали, острых рёбер нет. Исправление: острые рёбра ставятся по
  серединам жёстких рёбер из `readback_max` (`mark_sharp_from_reference`, `handoff_blender.py:187`); экспорт с `mesh_smooth_type
  SMOOTH_GROUP`.
- **Один материал (не Multi/Sub)** теряет matID по граням (GLASS_001: box с ID 1..6, болты). Исправление: `ids_by_centre`
  (`handoff_core.py:305`) по ключам граней из readback — для фактов Blender и для импорта в Max.
- **Multi/Sub с пропусками ID** (KPP1: 3/9/12/16/29/35) возвращается порядком слотов. Исправление: `matid_remap`
  (`handoff_core.py:189`) по именам подматериалов и поиск по центрам граней (`_remap_matids`, `handoff_max.py:635`).
- **Инстансы.** Blender пересвязывает меши по `instance_of` из манифеста (`relink_instances`, `handoff_blender.py:133`);
  импорт в Max при необходимости делает `instanceReplace`.
- **Сравнение зависело от порядка** (13.83 против 13.829999 переставили отсортированных соседей на KPP1_Parapet,
  `20261106-134538-40e13b6f`). Исправление: `multiset_close` (`handoff_core.py:388`).

В тестах дефекты H1–H9 КРАСНЫЕ на модели наивного круга (`naive_*`) и ЗЕЛЁНЫЕ на `handoff_core`.

## 4. Приёмка

### Что переживает круг (REPORT §3.12)

| Свойство | Допуск | Blender (импорт бандла) | Max (возврат) | Как обеспечено |
|---|---|---|---|---|
| Имена объектов и роли (1:1) | совпадают | 0 | 0 | `restore_name(s)`, sidecar |
| matID ↔ слоты | совпадают | 0 | 0 | `ids_by_centre`, `matid_remap` |
| UV / UDIM | тайлы равны, дробная часть ≤ 1e-6 | 0 | 0 | UV каналы в readback, сверка `compare` |
| Нормали и сглаживание | жёсткие рёбра равны | 0 | 0 | `mark_sharp_from_reference`, `SMOOTH_GROUP` |
| Единицы, ось, масштаб | метры, scale 1, bbox ±0,1 мм | 0 | 0 | `normalise`, `_set_transforms` |
| Пивоты и трансформы | ±1e-5 | 0 | 0 | запекание смещений, манифест |
| Топология (квады и n-гоны) | полигоны и рёбра равны | 0 | 0 | копии Editable_Poly, `ngon_ref`, `diagonals` |
| Инстансы | группы равны | 0 | 0 | `instance_of`, `relink_instances` |

Числа в колонках — число расхождений. Цепочка зелёная:

- экспорт Max 2024: `20261106-135137-44de5679`;
- Blender 5.1.2: `20261106-135159-664da499` — 0 расхождений при импорте и при перечитывании собственного экспорта, оба бандла;
- возврат Max 2024: `20261106-135201-2d9ea983`.

Два бандла:

- **001, синтетика в см.** BODY_Brick_001 — восьмиугольная призма с двумя 8-угольными крышками, 3 matID, гладкие бока и 16 жёстких рёбер
  крышек; UV канал 1 в тайлах 1001/1011, канал 2 сдвинут на +1 по U (тайлы 1001/1002/1012); пивот вынесен с геометрии, поворот 30°. BODY_Brick_002 — инстанс.
  GLASS_001 — потомок с одним материалом Standard. Маркеры OPEN_001 / LEVEL_L1 только в sidecar.
- **002, копия типа KPP1.** Фасад 258 квадов, парапет, 2 болта, ID библиотеки 3/9/12/16/29/35.

Материалы:

- бандл 001 в своей сцене: повторное использование материалов сцены BH_Multi / BH_Glass, diff 0;
- бандл 002: пересборка из JSON (KPP1_AR, KPP1_AR_29), diff 0;
- пустая сцена без оригиналов: BH_Multi и BH_Glass пересобраны из `materials.json`, diff 0, пути карт и имена узлов равны
  (BH_Cap_Bottom, BH_Cap_Bottom_bump, BH_Cap_Top, BH_Cap_Top_diffuse, BH_Glass, BH_Glass_opacity, BH_Multi, BH_Side, BH_Side_diffuse,
  BH_Side_opacity); посторонний объект Stray_Box попал в отчёт как несопоставленный.

`agent.accept` (ветка U): вердикт accept для обоих бандлов; объекты ушли в слои ролей, оригиналы скрыты в `AGENT_<req>_SOURCE`.

## 5. Не сделано / риски

- Регистрация четырёх кнопок и MCP-инструментов `agr_handoff_export` / `import` / `verify` в общих файлах (`runtime.py` EDITS_100 и
  READ_100 для `handoff.verify`, `ui_model.py`, `agr_tools.mcr`, `tools/max/build_agr_tools.py` FILES, `src/agr_mcp/tools.py`) —
  отдельный небольшой PR в стиле ветки 0.
- Станции полигонов не добавлены.
- Blender предупреждает «Cannot register a valid material index … different material slots layouts» на пересвязанном инстансе
  BODY_Brick_002; readback при этом остаётся 0.
- Размер `readback_max` растёт с размером меша (ключи граней, `ngon_ref`).
- Эвристика диагоналей растворила бы новое ребро агента внутри исходного n-гона, только если оба конца — исходные вершины.
- Материалы нестандартных классов (V-Ray, Corona) сериализуются обобщённо, но измерены были только Standard, Multi и Bitmap.
- Паритет AGR Tools в Blender (N-панель) вне объёма (REPORT §4.5).
