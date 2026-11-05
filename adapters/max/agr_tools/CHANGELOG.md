# AGR Tools changelog

## 0.9.0 (#979) — в работе

Пакет остаётся 0.8.x до релизной ветки R: кнопки 0.9 есть в меню и MCP, в панели они серые «в версии 0.9».
Каждая ветка пишет только в свой подзаголовок ниже.

### Основа (ветка 0)

- `runtime.EDITS_090` (19 строк плана 0.9: id → файл ядра, функция), `READ_090` (режимы `read`/`select`: только
  preview), `SELECT_090` (`light.check`: нарушителей выделяет обвязка UI одной записью Undo, не ядро) и
  диспетчер `runtime.edits_090(tool, mode, preview, nodes, options)` на контракте `edit_core` 0.8; пустой модуль
  отвечает `status: not_implemented` с `issue: #979`.
- Заглушки модулей A–D, `data/procedural_classes.json` и `data/streets/` (владелец C); сборщик кладёт `data/` в пакет.
- `cleanup_preview` / `cleanup_apply`: проход `options` (`channels`, `keys`; по умолчанию выключены) в
  `export_core._cleanup_channels`.
- 19 Action в секциях «Проверить и выделить» / «Исправить — копии / undo / новые файлы», 19 macroScript и пунктов
  меню, 19 иконок, 19 MCP-инструментов `agr_<блок>_<имя>` (только `mode=preview`).
- Полигон: базы 0.8 и 0.9 (32 станции), хук фрагментов `test-polygon/stations/<ветка>.json`, `load_catalog()`.
- `roadmap.load()` отклоняет 8 из 8 испорченных JSON плана (SYNTHESIS §4).

### A — замены и МАФ (`improve/issue-979-place`)

- Заглушка ветки A: `place.replace`, `place.schedule`, `place.drop_to_ground`, `place.maf_checks`, `place.flora_repair`.

### B — текстуры, UDIM, атласы (`improve/issue-979-tex-udim-atlas`)

- Заглушка ветки B: `tex.erm_normal_check`, `tex.finish_map`, `udim.matid_unwrap`, `udim.slots`, `atlas.flora`,
  `atlas.groundel`; доработка `atlas.npm`.

### C — проверки (`improve/issue-979-qa`)

- Заглушка ветки C: `qa.address`, `qa.normals`, `qa.sintez`, `qa.facade_compare`, `qa.procedural_objects`.

### D — экспорт, карты, свет (`improve/issue-979-export-scene-light`)

- Заглушка ветки D: `export.batch`, `scene.maps_usage`, `light.check`.

### E1 — доработка: текстуры и имена (`improve/issue-979-rework-tex-names`)

- Заглушка ветки E1: доработки `tex.format_fix`, `tex.placeholders`, `scene.missing_maps`, `qa.names_fix`.

### E2 — доработка: геометрия и UDIM (`improve/issue-979-rework-geom-udim`)

- Заглушка ветки E2: доработки `ucx.triangulate`, `export.pivot_place`, `udim.ids_to_udims`.

### E3 — доработка: пакет и предсдача (`improve/issue-979-rework-package-suite`)

- Заглушка ветки E3: доработки `export.zip`, `qa.package`, `export.cleanup`, `qa.zero_area`, `scene.census`.

## 0.8.1 (#908)

Решения владельца от 05.11.2026 по командному аудиту T04 (GeoAGR-private `work/team-scripts-audit/T04/REPORT.md`,
«Открытые вопросы» 1–3).

### qa.scene_hygiene: всё на слое «0»

- Новый код `hyg_layer`: объект не на слое по умолчанию «0» → fail с текстом «объект на слое «X», а должен быть на
  слое «0»: все объекты в одном слое по умолчанию, других слоёв нет (reg p.28 §3.2)». Норматив есть: регламент
  стр. 28 §3.2 (требование 2.3.2 «Коллекция одна», `VPM_STANDARD.yaml geometry.one_default_layer_or_collection`).
  Идея из командного скрипта `agr_max_check_37.ms` `check_Layers` (sha256 `ead38669…`), код не брали. Имя слоя
  сравнивается точно; нет поля `layer` — ошибка, а не pass. Входит и в `qa.preflight`.
- Полигон: объекты станций теперь на слое «0» (как сдаваемая сцена), служебные `_bases/_labels/_cameras` не
  проверяются; новый объект `SM_Polygon_Layer_Main` на «Лишний слой» (станция 0.7.10) — fail `hyg_layer`.
- Тесты: `tests/max_tools/test_agr_tools_owner_decisions.py` (RED на 0.8.0 → GREEN); нативно Max 2024
  `tests/max_tools/run_agr_tools_owner_native.py`, job `20261105-104812-f5ac560d`: бокс на «0» — pass, на
  `Extra_Layer` — ровно `hyg_layer`, сцена не изменена.

### Реестр ФНО

- `standards/data/fno_codes_utf8.csv` — побайтовая копия реестра из SINTEZ AGR Checker 1.6.1 (566 кодов, sha256
  `397e75e3…`, совпадает с копией в `AGR_Checker.zip`); происхождение — `standards/data/fno_codes.PROVENANCE.md`.
- `twinqa.fno` + V011 (`qa.package`, `qa.geojson`, `validate_package.py`): для ОКС `FNO_code not in registry`
  (код верного формата, но нет в классификаторе) и `FNO_name vs registry` (имя не совпадает, пробелы не
  учитываются, как в SINTEZ) — fail. Ground не сверяется. Нечитаемый реестр — `not_run`, не pass.
- Синтетические фикстуры перешли на реальную пару `010 004` / «Общежитие».

### V004 и «центр XY» на FBX из Max

- Из пяти реальных архивов на ноутбуке FBX из 3ds Max только в двух (`1113_…_10_3`, `SM_…_4368_002`), остальные —
  Blender 4.4/5.2 (заголовок `SceneInfo ApplicationName`, новый `twinqa.fbx_header.fbx_application`).
- Дефект 0.8.0: правило «identity в любом режиме импорта» давало ложный pass объекту Max, повёрнутому на +90° X
  (импорт с bake добавляет −90° X). Измерено на эталонных FBX из Max 2024 (job `20261105-104812-f5ac560d`).
  Теперь FBX из Max судится только по обычному импорту; прочие экспортёры — как в 0.8.0.
- Реальные архивы: V004 pass на 4, fail на `1113_77_17_0120114_5803_10_3` (два меша повёрнуты на −28° по Z — верный
  fail); «центр XY» (V013 `pivot at geometric centre`) — pass 0/0 % на обоих ВПМ, ложного fail по Y-up нет.
  Ожидания: `tests/qa/real_deliveries_081.json` (имя архива, SHA256, вердикты); архивы не коммитятся, тесты
  без них пропускаются.

## 0.8.0 (#908)

Сдача: 13 кнопок плана версии 0.8 (секция «Сдача (копии)», 13 macroScript, пункты меню, иконки, MCP
`agr_<block>_<name>`). Правки только на экспортных копиях или в новых файлах, каждая с preview → apply по
хэшу, одна запись Undo на запуск, выделение восстанавливается, отчёт со списками `done` / `skipped` / `ambiguous`.

### Контракт правки

- `edit_core.py`: контракт правки — preview → apply со сверкой хэша, `new_path()` без перезаписи,
  списки `done` / `skipped` (с причиной) / `ambiguous`, JSON-контракт 0.5.0, статус `not_implemented`.
- `edit_max.py`: экспортные копии, одна запись Undo на запуск, восстановление выделения, снимок до/после.
- `runtime.EDITS_080` (13 строк плана) и `runtime.edits_080(tool, mode, preview)`; пустой модуль отвечает
  `status: not_implemented`. Секция «Сдача (копии)»: 13 macroScript, пункты меню, 13 иконок, 13 MCP-инструментов.
- План: вердикт `take_fix` по лаборатории #907 для `model.triangulate`, `ucx.triangulate`, `export.ground_fbx`.
- `edit_max.session` (общий, #908 R): исключение внутри `pymxs.undo(True, …)` в Max 2024 batch не выходило из
  блока (job `20261105-011438-a488a8fd`, найдено веткой C) — упавший apply продолжался как успешный. Теперь
  ошибка ловится внутри записи Undo и пробрасывается после неё (`test_session_reraises_an_error_swallowed_by_the_undo_context`);
  обход `names_max.in_session` остаётся совместимым.

### Геометрия и пивот

- `model.triangulate` (`geom_core.py` / `geom_max.py`): n-гоны экспортной копии триангулируются без DLL и диалога.
  Пороги относительные (грань нормируется к единичному боксу), поэтому октагоны 0,1 мм и U 0,6 мм в метровой
  сцене триангулируются так же, как 1 км. Ровно n−3 непересекающиеся диагонали на грань (ear clipping +
  флипы Делоне только внутри строго выпуклых четырёхугольников, без длинных клиньев). Применение одним
  циклом `polyop.createEdge`. Проверка «0 n-гонов» на чтении копии; вырожденные контуры в `ambiguous`.
  Площадь, UV, ID материалов, SG и скрытые грани сохраняются; Box/Mesh/модификаторы конвертируются на копии.
- `ucx.triangulate`: диагональ выбирается с учётом выпуклости (все вершины за плоскостью каждого треугольника,
  допуск 1e-4 м), для невыпуклого куска — его выпуклая оболочка. Проверка после (`ucx_core.convexity`):
  выпуклость, замкнутость, нет нулевых треугольников. Box, Editable Mesh и Poly с модификаторами
  конвертируются на копии и перечисляются, прочее — в `skipped` с причиной. Скрытые грани остаются скрытыми.
- `export.pivot_place`: копии НПМ (МСК X/Y/Z без изменений, пивот в [центр X, центр Y, ±0.000]) и ВПМ
  (пивот пола в [0,0,0]). ±0.000 = min z выделенных граней/рёбер/вершин пола или явное значение (`floor_z`,
  в интерактивном Max — запрос); без выборки отказ, низ bbox не используется. Ввод проверяется (пустое поле,
  экспонента, nan — отказ). Координаты в double, текст с фиксированными 4 знаками. Поворот как в UI (знак
  контроллера). Общий пивот у всех выбранных узлов: взаимное смещение моделей сохраняется.

### Текстуры

- `tex.format_fix` (`tex_core.py` / `tex_max.py`): исправленные PNG только в **новую** папку (по умолчанию
  `AGR_format_fix[_vNNN]` рядом с исходником; явная `out` — новая или пустая, не папка исходника). Формат из IHDR
  через `checks_core.png_info` (палитра и 16 бит видны), полный stdlib-декодер PNG (все типы, 1–16 бит, Adam7),
  запись PNG на stdlib zlib: 8 бит, colour type 2. Альфа снимается только где правило запрещает: явный фон
  `background` или `dilate` (цвет края), иначе отказ с причиной; непрозрачная альфа снимается без потерь;
  VPM Diffuse сохраняет альфу. JPG и прочие форматы — через .NET в Max, пакет не прерывается. Пропорции
  сохраняются (`max_side` уменьшает вдвое по обеим осям), неквадратные в отчёте. Лимит `max_bytes` (по
  умолчанию 3 MiB) — сначала без потерь, затем постеризация с RMSE в отчёте; недостижимый лимит — отказ с
  причиной. Dilate выключен по умолчанию. Исходник уже в норме копируется байт в байт.
- `tex.format_fix`, палитра (решение Артёма 05.11.2026: палитровый PNG допускается; командный аудит T01: 2048²
  при 256 цветах 2,36 МБ палитрой против 5,70 МБ RGB): colour type 3 — валидный формат (палитровый исходник в
  норме копируется). Сверх лимита порядок такой: RGB без потерь → точная палитра (≤ 256 цветов, без потерь) →
  квантизация в 256 цветов (median cut) → постеризация RGB. В отчёте `encoding`, число цветов,
  `max_channel_error` и RMSE. `palette: false` выключает палитру; RGBA в палитру не переводится.
- `tex.placeholders`: однотонные D/ERM/N, PNG 8 бит RGB без альфы, точный цвет, Normal [128,128,255]; имена
  VPM-2.10-4.3 `T_{Address}[_Ground]_{Diffuse|ERM|Normal}_{Slot}.{UDIM}.png` одним вызовом для слотов; размеры
  128…4096, по умолчанию 256; папка через `os.path.join` (без завершающего `\` пишет внутрь), по умолчанию
  `Maps` рядом с сохранённой сценой (несохранённая — отказ, без относительного `Maps\`); существующий файл —
  отказ или `_v002` (`on_exists`); Diffuse средним цветом исходника (`diffuse_from`).
- `scene.missing_maps` (только чтение, без apply): все bitmap-подобные карты всех узлов (скрытые и `UCX_` с
  флагом), scene materials и AssetManager; `doesFileExist`; `<UDIM>`/`<UVTILE>` по тайлам из UV и диска;
  кандидаты по базовому имени (то же имя+расширение — ранг 0, другое расширение — ранг 1) с флагом
  неоднозначности; разрешение существующих (PNG/JPG/TGA); каждый путь один раз с владельцами; JSON + таблица.

### Имена и UDIM

- `ucx.rename` (`names_core.ucx_plan`, `names_max.ucx_rename`): переименовывает на месте только UCX-геометрию
  в `UCX_SM_<Address>_(Main|Ground)_NNN` одной записью Undo. Рендер-модель, хелперы, камеры, свет пропущены
  и в отчёте; порядок по старому номеру; адрес не обрезается; префикс без учёта регистра; 001..999, больше —
  ошибка группы; номера, занятые невыделенными узлами, не выдаются; повторный запуск ничего не меняет.
- `qa.names_fix` (`names_core.names_fix_plan`, `names_max.qa_names_fix`): одна грамматика с `ucx.rename`.
  На экспортных копиях (слой `AGR_export_names`) объекты, материалы (SlotNumber 1..7) и карты получают имена
  по маскам NPM/VPM; файлы карт копируются рядом с исходником под именем по маске (папки не меняются),
  без перезаписи; существующий файл назначения переиспользуется с его хэшем в отчёте; пропавший исходник —
  карта очищается на копии и сбой в отчёте; свой материал цели в режиме донора не заменяется без
  `replace_material` и всегда в отчёте; повторный запуск — неоднозначность, не перезапись.
- `udim.ids_to_udims` (`udim_core`, `udim_max`): ID n → UDIM 1000+n на копиях (слой `AGR_export_udim`), все
  выбранные объекты; ID вне 1..100 и группы нулевой протяжённости отклонены с отчётом (без NaN); режимы
  `fit` (0.95 на ID) и `texel` (одно отношение UV/3D на все ID); UV-вершины разделяются между ID; отчёт по
  каждому ID и readback «каждая грань в своём тайле».

### Пакет и экспорт

- `qa.package` (только чтение): движок — валидатор пилота `tools/qa/validate_package.py --json`, по умолчанию
  `--scene`, в интерпретаторе проекта (`AGR_PYTHON`). Отчёт: таблица стадий V001–V017 и код выхода 0/1/2 на каждый
  ZIP (или на все ZIP папки). Валидатор (лаборатория L04): профиль по грамматике имени (`{code4}_{Address}` → NPM,
  `SM_{Address}` → VPM), а не по содержимому; V006 «embedded textures» больше не проходит на NPM FBX без текстур
  (OKS — fail, Ground — review). По аудиту командных скриптов T04: FBX со светом читается в Blender 5.1.2
  (флаг `cast_shadow` для импортёра), одна нечитаемая FBX больше не обрывает проверку остальных, V004
  «applied transforms» — тождество хотя бы в одном режиме импорта (FBX из Max и запечённый экспорт Blender
  проходят, реальный поворот падает), V010 «UCX shape» — открытые/невыпуклые куски fail, логи Blender не в cwd.
- `export.zip`: состав по точной грамматике и по адресу — NPM `{code4}_{Address}_{01..20}.fbx` + `_Ground.fbx`
  (части без пропусков), VPM `SM_{Address}[_NNN]` + `_Light.fbx` + `.geojson` + `T_…_{Diffuse|ERM|Normal}`;
  смешанные адреса и коды отклоняются, приманки не трогаются и перечислены. ZIP пишется в процессе (без 7-Zip),
  только новым файлом (`.partial` + ссылка без перезаписи), лимиты двоичные `<=` (OKS 500 MiB, Ground и NPM
  1 GiB, D015); на каждом записанном архиве — валидатор.
- `export.ground_fbx`: Ground, GroundGlass, GroundEl, GroundElGlass, Flora → `{code4}_{Address}_Ground.fbx`, ОКС
  `SM_{Address}_{NNN}_*` → `{code4}_{Address}_{NN}.fbx`; имя из адреса, не из первого выбранного; не зависит от
  порядка выбора; Triangulate включён (остальные настройки FBX как в GeoAGR: 7400 binary, м, масштаб 1, текстуры
  встроены); экспортируются сами объекты без изменений, без раскрытия скрытых, без перезаписи; выделение
  восстанавливается; readback валидатором (V002/V003/V012 в слоте Blender).
- `export.geojson_write`: новый `SM_{Address}[_Ground].geojson` — свойства App.3 только из options (ничего не
  выдумывается, пустое обязательное поле — находка), точка МСК-77 только из preview `export.pivot_place`
  (3 знака), превью JPG 256×256 в Base64, `Glasses` из стеклянных материалов; сразу после записи — `qa.geojson`
  0.5.0. Кнопки GeoAGR `GeoAGR.ms:64642-64644` отключены и без обработчиков — переносить нечего.

## 0.7.0 (#860)

Pre-delivery checks (read-only) + tab rail by block + «Путь», all from `agr-tools-suite.json` (#853 plan).

- 12 checks of plan version 0.7 (`suite_core.py` logic, `suite_max.py` pymxs reads, snapshots only, D6):
  `scene.census`, `scene.units` (D5), `model.perimeter_drop` (AGR_ZERO_M, ≥ 1 m), `tex.material_type`,
  `ucx.audit` (twinqa ucx_audit slice), `atlas.sets_count`, `qa.fbx_split`, `qa.glass` (D2, D3),
  `qa.preflight` (all object checks, one table), `qa.scene_hygiene` (D7), `qa.xform` (D6), `qa.zero_area`.
  JSON report contract of 0.5.0 (`schema`/`tool`/`status`/`objects`/`plan`), status derived from findings.
- Panel: tab rail on the left — «Путь» + the 10 blocks in plan order, one accent per block derived from the
  Max palette (≥ 3:1 against window and base, else an error, never a pale colour). Planned buttons of
  versions 0.8–1.x are shown greyed with «в версии 0.x».
- «Путь»: pipeline nodes in block colours with steps and buttons, tooltip (what / when / mode / requirements),
  «?» card, live status per block from the last reports of this scene (`%LOCALAPPDATA%/AGRTools/reports`),
  «Следующий шаг». `docs/agr-tools/GUIDE.md` + `flow.svg` are generated from the same JSON.
- MCP (`agr-mcp` phase 0): 12 read-only tools `agr_<block>_<name>` over `runtime.checks_070`.

## 0.6.0 (#808)

Native Qt UI over all 17 existing actions; no check logic changed.

- Dockable panel `AgrToolsPanel` (PySide6 on Max 2025/2026, PySide2 on 2024 through `ui_qt.py`),
  parented to the Max main window, Max accelerators disabled on focus, dock position kept in
  `3dsMax.ini` `[AGRTools] dock=`. Five sections by work step, each with its own accent hue
  (stripe, header, icon tint) derived from the Max palette; result table (red/green), click selects
  the object, «Выделить ошибки», «Сохранить отчёт JSON…».
- Progress bar + «Отмена» and the Max progress bar (progressStart/Update/getProgressCancel/End).
  xView and MatID run in chunks of 25 objects (exact merge). Cancel is read only between
  chunks, so a click takes effect on the next chunk (about 0.9 s on Max 2024); the chunk
  already running is kept. Other actions are one runtime call
  with a busy bar. Buttons are disabled while running.
- Every action is a macroScript with `iconName:"AgrIcons/agr_<id>"`, Russian label and tooltip
  (what it does + requirement ids); `agr_tools_runtime.ui('<tool>')` and `agr_tools_runtime.panel()`
  stay the Python/MAXScript API. Classic rollout `AGRToolsClassic` is the fallback.
- Menu «AGR Tools» via `#cuiRegisterMenus` (Max 2025+), survives a menu preset change.
- Application Plugin Package `AGR-Tools.bundle` (`build_agr_tools.py --bundle`), UpgradeCode
  `{BA2C2E6E-54F9-402E-8875-3D616C9030FD}`, Dark/Light icon components. Icons: own SVG set,
  PNG 24/30/36/48 rendered at build time (not committed).

## 0.5.0 (#804)

Five read-only diagnostics. None of them edits the open scene. Each writes a 0.4.0 JSON report
(`schema`, `tool`, `status`, `objects`, `plan`) to the Listener.

Base: GeoAGR 13.64 (author Artem), recovered `GeoAGR.ms` (GeoAGR-private@31c723e), with the author's
permission. Only the functions in use are adapted, in `checks_core.py`. Each function's docstring names
its `GeoAGR.ms:<line>` and its changes.

- **Names check NPM/VPM** (`names`): object (SM/UCX), (sub-)material (M) and texture file (T) names.
  Adapted from `check_names_all` (`GeoAGR.ms:6907`) and `check_names_all_vpm` (`:7331`).
  Fixes D2: the exact last token decides Main/MainGlass/Ground/UCX, not a substring `case`.
  Fixes D4: SlotNumber 1..7 is legal; GeoAGR required exactly `1`.
- **Triangle limits per FBX** (`tris`): budgets are summed per `AGR_EXPORT_PATH` FBX and per model
  kind. The limits are NPM OKS 150 000, NPM Ground 180 000, VPM OKS 1 000 000 (UCX excluded), VPM
  Ground by the site-area table (`AGR_SITE_AREA_HA`) and VPM UCX by the decided formula. Fixes D8,
  where GeoAGR summed over the selection. The stale 2 000 000 VPM limit is gone.
- **Textures check (all objects)** (`textures`): the maps of every object are checked. Fixes D1,
  where GeoAGR read the last object only. An empty `usedMaps` array means "no maps". Fixes D3,
  where GeoAGR tested the array against undefined. The checks are size, square shape, placeholders,
  alpha, 8 bits per channel (from the PNG header), file size, the UDIM set and UV padding. Padding is
  NPM 8 px and VPM 16/32 px for 2048/4096 maps; GeoAGR's 16/32 px branch was commented out.
  Padding is measured per texture atlas: each face goes to its matID's sub-material maps, and the
  islands of all objects of one FBX that share an atlas are measured together (per UDIM tile). A face
  matID outside `materialIDList` is resolved as the 3ds Max FBX export does (measured in Max 2026.3,
  #827): it wraps by the highest listed ID n, `(id - 1) mod n + 1` (`#(1,2)`: 3 -> 1, 4 -> 2;
  `#(1,5)`: 6 -> 1, 10 -> 5), is measured on that sub-material and reported as the advisory
  `tex_matid_wrapped` naming `matID 3 -> sub 1`. A wrapped ID that is still not listed (`#(1,5)`: 2, 3,
  4, 7; the export writes an empty placeholder slot) and a Multimaterial with no sub-materials are
  `tex_unmeasurable`; a sub-material without maps is `tex_missing`. The MatID check (`empty_slot`) and
  the export material evidence use the same resolver (`checks_core.max_submaterial_index`). In VPM, touching
  or overlapping islands (gap 0) are the review-level `tex_overlap_review`, not `tex_padding`:
  regulation 2.5.1.5 applies padding only to islands with unique images, and repeating islands may
  overlap. A VPM gap above 0 and below 16/32 px is still `tex_padding`; NPM is unchanged.
- **Pivot check** (`pivot`): VPM-2.9-4.b requires pivot Z = 0 within 1 mm. VPM-2.9-5 requires every
  pivot of one FBX to coincide within 1 mm. UCX pivots are free (VPM-2.9-4.c).
- **GeoJSON check** (`geojson`): runs the pilot `twinqa.geojson` checker on a chosen `.geojson`
  in the project Python (`AGR_PYTHON` or `<repo>/.venv`). A broken file or a crashing checker is
  reported as a finding, never a raise.
- D6 (Prepare LowPoly/HighPoly destroy the scene) does not apply: the glue only reads
  `snapshotAsMesh` copies in memory, `usedMaps` and the PNG files on disk.

## 0.4.0

Checked export: one FBX per `AGR_EXPORT_PATH`, gated and read back.

## 0.3.0

UCX collision, texel readout.
