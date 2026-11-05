# Тестовый полигон AGR Tools

## Как играться (одна страница)

1. **Открой сцену.** 3ds Max 2026 (или 2024) → File → Open → `polygon_all.max`
   (из папки прогона, например `C:/x/test-polygon/polygon_all.max`, или с Drive
   `G:/Мой диск/AGR-evidence/885-test-polygon/`). Окно «Missing External Files» — нажми «Continue»:
   одна текстура отсутствует нарочно (станция 0.7.1).
2. **Открой панель.** Главное меню → **AGR Tools → AGR Tools**. Панель встаёт справа (скриншот `GUIDE/01`, `02`).
3. **Перейди на базу.** Клик по названию вида в левом верхнем углу вьюпорта → **Cameras → `_cam_База 0.1`**
   (так же `_cam_База 0.2` … `0.9`). Режим отображения — Default Shading (цвет баз виден).
4. **Прочитай станцию.** Над объектами — подпись «Станция 0.1.1: нажми «MatID»», ниже по строке на объект:
   `SM_Polygon_010_Main -> fail udim_id`. Под каждым объектом — его имя.
5. **Нажми.** Выдели объекты станции (рамкой или по имени, H), в панели нажми кнопку из подписи.
6. **Сравни.** Таблица внизу панели: «Объект / Проверка / Результат / Треб.».
   `pass` — объект прошёл; `fail udim_id` — найдена ошибка с этим кодом. Совпало с подписью — кнопка работает.
   Пример: База 0.1 → нажми «MatID» на `SM_Polygon_010_Main` → увидишь `fail udim_id` (ID граней вне слотов).
7. **Все кнопки сразу (агент или ты):** `python test-polygon/run_polygon.py --out C:/x/test-polygon-новая`
   → таблица `table.txt` «кнопка → ожидалось → получилось → OK / НЕ OK».

Скриншоты по шагам: [`GUIDE/README.md`](GUIDE/README.md) (шаг 1 … шаг N, снято в живом Max 2026).

---

Синтетическая сцена, чтобы нажимать кнопки AGR Tools 0.1–0.9 и видеть, на каком объекте PASS, а на каком FAIL.
Это не модель заказчика. Скамья «Верона» здесь — ящик с именем GroundEl, не актив #790.

Сборка идёт скриптом. Файл `.max` — результат, формат Max 2024 (открывается и в 2026). В git его нет.

## Как открыть и поиграть

1. Собрать сцену (ниже) или открыть уже собранный `polygon_all.max` из папки результата.
2. Поставить системные единицы в метры. Исключение — отдельный файл `cm_units.max`: он специально в сантиметрах.
3. Пройти базы слева направо: База 0.1, База 0.2, … База 0.9. У каждой базы свой цвет на плоскости земли
   (вид сверху) и подпись в углу: «База 0.x — что добавила версия, какие кнопки».
   Следующая версия AGR Tools добавляет свою базу в конец ряда (`TOUR_LAST` в `polygon_core.py`).
4. Внутри базы — станции, сверху вниз, по четыре в колонке. Подпись станции (многострочная, 1 м):
   «Станция 0.x.N: нажми «кнопка»» и по строке на объект «имя -> ожидаешь». Под каждым объектом его имя.
   У объекта в пользовательских свойствах `AGR_TEST` начинается с `station=0.x.N`, дальше кнопка и код.
5. Прямоугольники баз лежат на слое `_bases` и называются `_base_0_1`. Подписи — на слое `_labels`
   (`_label_base_0_1`, `_label_0_1_1`, `_label_obj_<имя>`); слой включён, его можно выключить. Камеры баз
   `_cam_База 0.x` — слой `_cameras`. Всё это не экспортируется и не входит в проверки: префикс имени
   `_base_` / `_label_` / `_cam_` плюс слой. Раннер выбрасывает такие имена из отчёта до сравнения.
   Кнопки выделяют названные объекты станции, не площадку.
6. Кнопки, которые правят сцену (сдвиг UV, атлас, UCX, очистка), сначала идут пробным прогоном. Второе нажатие
   пишет копии. Оригиналы не перезаписываются. Очистка на копии (`имя_AGR_export_`) — строка PASS.
   Экспорт с проверкой на грязном объекте останавливается на воротах `cleanup` (FAIL). Тот же прогон затем
   берёт копию `SM_Polygon_001_Main_AGR_export_` и пишет FBX только в новый путь
   `<папка результата>/export-pass/<имя копии>.fbx`, после чего читает файл обратно (`plan.readback`).
   Это строка PASS. Существующий файл по этому пути раннер не перезаписывает.

Отдельные сцены, их нельзя смешать с общей:

| Файл | Зачем |
|---|---|
| `polygon_all.max` | Базы 0.1–0.9 в метрах, профиль НПМ |
| `frag_<ветка>_*.max` | Свои сцены станций 0.8/0.9, которым нужна отдельная сцена (метры или см), из фрагментов `stations/` |
| `cm_units.max` | Единицы — сантиметры. Кнопка «Единицы и гамма» должна дать `system_unit` |
| `empty.max` | Пусто. Проверки объектов дают ошибку `empty target set`, это не pass |
| `vpm.max` | Профиль ВПМ: пивот и лимит треугольников Ground без площади участка |

## Папки

| Папка | Что внутри |
|---|---|
| `build/` | `build_polygon.ms` открывает сборщик в Max. `build_scene.py` строит узлы. `run_inside_max.py` нажимает кнопки |
| `textures/` | `spec.json` — какие PNG нужны (квадрат 256, кривой размер 100×50, альфа, 16 бит). `generate.py` пишет PNG в папку результата, не в git |
| `fbx/` | Текстовый эталон `reference_box.fbx` и обрубок `broken_truncated.fbx` для readback. `make_fbx.py` копирует их в результат. Двоичный FBX не коммитится |
| `geojson/` | `valid_oks.geojson` проходит twinqa. `broken_syntax.geojson` не JSON. `broken_schema.geojson` — JSON, но не FeatureCollection |
| `expected/` | Один JSON на id кнопки. Внутри: база → станция → кнопка → объекты и коды. Версия кнопки берётся из `docs/plans/agr-tools-suite.json` |
| `bases.json` | Ряд баз: версия, подпись, цвет, станции, файл ожидания. Генерируется `polygon_core.py` |
| `stations/` | Фрагменты баз 0.8 и 0.9 (#979): `<ветка>.json` — объекты и ожидания станций ветки, `<ветка>_build.py` — их узлы |
| `scenes/` | Спеки вариантов `cm_units`, `empty`, `vpm` |
| `catalog.json` | Объекты станций и площадки: слой, `station`, `AGR_TEST`. Генерируется `polygon_core.py` (база + фрагменты) |
| `polygon_core.py` | Предсказание кодов теми же ядрами, что и кнопки, и сравнение отчёта |
| `run_polygon.py` | Сборка в пустом Max через общий замок DCC, нажатие кнопок, таблица |

Коды проверок 0.5 и 0.7 в `expected/` посчитаны ядрами `checks_core` / `suite_core` по этой же сетке.
Кнопки, которым нужен сам Max (xView, MatID, живая очистка), заложены по их кодам в `runtime.py`.
Первый живой прогон их и сверяет: если Max добавит код (например `rename_map_channel_1`, когда канал 1 назван не `UV`),
это строка «НЕ OK» в таблице, а не тихий pass.

У части кнопок PASS или FAIL нет, и в JSON записана причина:

- `ucx.build` — ящик даёт пустые findings; находка `at_threshold` только на 15 000 треугольниках коллизии;
- `atlas.npm` — pack всегда сдвигает остров (`atlas_cell`), повторный pack тоже.

## Как пересобрать

Из корня репозитория, папка результата — новая, не внутри `test-polygon/`:

```
python test-polygon/textures/generate.py C:/x/test-polygon
python test-polygon/fbx/make_fbx.py C:/x/test-polygon/fbx
```

В 3ds Max 2024 или новее: `File > Run Script` → `test-polygon/build/build_polygon.ms`, затем в listener
(после того как скрипт добавил путь):

```
import sys
sys.path.insert(0, r"<корень репозитория>\test-polygon")
sys.path.insert(0, r"<корень репозитория>\test-polygon\build")
import build_scene
build_scene.build("polygon_all", texture_dir=r"C:/x/test-polygon/textures")
build_scene.save(r"C:/x/test-polygon/polygon_all.max")
```

`save` пишет формат 2024 (`saveAsVersion:2024`). То же для `cm_units`, `empty`, `vpm`.

Обновить JSON ожидания после смены ядра проверок:

```
python test-polygon/polygon_core.py
```

## Раннер

```
python test-polygon/run_polygon.py --out C:/x/test-polygon --version 2024
```

Если есть `G:/Мой диск/`, без `--out` результат идёт в `G:/Мой диск/AGR-evidence/test-polygon/`.
Иначе в `C:/x/test-polygon/`.

**Ноутбук (Max 2024, релиз 0.9.0).** `run_polygon.py` без `--actual` запускает Max через планировщик DCC (Hermes);
на ноутбуке так не делают. Сборка и нажатия идут джобом AGR Lab runner (`build/run_inside_max.py` в одноразовой
сцене слота), затем сравнение без Max:

```
cd C:\agr\agr-lab; py -3.11 -m agr_lab submit <job.json> --wait 900
python test-polygon/run_polygon.py --out <новая папка> --actual <папка джоба>/out/actual.json
```

**ПК (Max 2026).** `run_max_batch.ps1` (слоты + охрана UI), тот же `run_inside_max.py`, затем то же `--actual`.

Раннер отказывается писать, если выход, отчёт или временный путь совпадает с исходниками или друг с другом,
и в этом случае ничего не создаёт. Исходники он не удаляет. Max запускается через
`C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py` (общий замок сессии), в пустой сцене.
Дальше скрипт нажимает каждую поставленную кнопку, сравнивает отчёт с `expected/` и пишет `report.json`
и `table.txt`. Строки сгруппированы базой и станцией: база → станция → кнопка → ожидалось → получилось → итог.
Колонка «получилось» — статус и коды живого отчёта (`pass []`, `fail [cleanup]`).
Имена `_base_` и `_label_` в результат проверки не попадают.

Код выхода — число расхождений (`count` в `report.json`). Пустой отчёт, пропущенная кнопка, NaN/Inf,
`not_run`, кнопка без записи в `expected/` и невыполненная строка PASS (копия очистки или readback экспорта)
— это расхождение. Неизвестная кнопка — ошибка, в тексте есть её id.

Известная ошибка #886 не входит в код выхода. Если живой отчёт совпал с записанным `known_bug`, строка
печатается как `НЕ OK (известная ошибка #886)`, а не `OK`. Число таких строк лежит отдельно: поле
`known_bug` в `report.json` и хвост строки `mismatches N known_bug M`. `N` — код выхода, `M` его не меняет.

Только сравнить уже снятый `actual.json`, без Max:

```
python test-polygon/run_polygon.py --out C:/x/test-polygon-report --actual C:/x/test-polygon/actual.json
```

## AGR MCP

Сервер `agr-mcp` в этом репозитории не заведён (фаза 0 в `docs/plans/agr-mcp.md`). Отдельный инструмент
пока не регистрируется. Вызов тот же, только чтение: `python test-polygon/run_polygon.py --out <новая папка>`.
Будущее имя — `agr_polygon_run`, режим read, тот же `report.json`. Кнопки панели по-прежнему
`agr_<блок>_<имя>` из id строки плана.

## База → станция → кнопка → ожидание

Полный список — `bases.json`. Тур идёт до `TOUR_LAST = '0.9'`: 9 баз, 57 станций (0.6 — без станций).
Базы 0.8 и 0.9 стоят в `polygon_core.py`, а их объекты и ожидания — во фрагментах `stations/<ветка>.json` веток #979
(владелец кнопки — `polygon_core.OWNER`). `catalog.json` и `bases.json` перегенерирует релизная ветка R командой
`python test-polygon/polygon_core.py`; ветка только добавляет свой фрагмент и `expected/<id>.json`.
Кнопки 1.0 и дальше в ряде ещё без площадки: в их JSON `base` пустой, `stations` пустой, и записан `reason`.

| База | Станция | Кнопка | Ожидание |
|---|---|---|---|
| 0.1 | 0.1.1 | `qa.matid` | `expected/qa.matid.json` |
| 0.1 | 0.1.2 | `qa.xview` | `expected/qa.xview.json` |
| 0.1 | 0.1.3 | `export.cleanup` | `expected/export.cleanup.json` (FAIL на объекте, PASS на копии `*_AGR_export_`) |
| 0.2 | 0.2.1 | `udim.nudge` | `expected/udim.nudge.json` |
| 0.2 | 0.2.2 | `atlas.npm` | `expected/atlas.npm.json` (PASS нет, см. reason) |
| 0.3 | 0.3.1 | `ucx.build` | `expected/ucx.build.json` (FAIL нет, см. reason) |
| 0.3 | 0.3.2 | `udim.texel` | `expected/udim.texel.json` |
| 0.4 | 0.4.1 | `export.checked` | `expected/export.checked.json` (FAIL `cleanup` на оригинале, PASS — новый FBX копии и readback) |
| 0.5 | 0.5.1 | `tex.check` | `expected/tex.check.json` |
| 0.5 | 0.5.2 | `qa.geojson` | `expected/qa.geojson.json` |
| 0.5 | 0.5.3 | `qa.names` | `expected/qa.names.json` |
| 0.5 | 0.5.4 | `qa.pivot` | `expected/qa.pivot.json` |
| 0.5 | 0.5.5 | `qa.tris` | `expected/qa.tris.json` |
| 0.6 | — | кнопок нет | Qt-панель, станций нет |
| 0.7 | 0.7.1 … 0.7.12 | кнопки предсдачи | `expected/<id>.json`, id станции в `bases.json` |
| 0.8 | 0.8.1 | `scene.missing_maps` | `expected/scene.missing_maps.json` |
| 0.8 | 0.8.2 | `model.triangulate` | `expected/model.triangulate.json` |
| 0.8 | 0.8.3 | `tex.format_fix` | `expected/tex.format_fix.json` |
| 0.8 | 0.8.4 | `tex.placeholders` | `expected/tex.placeholders.json` |
| 0.8 | 0.8.5 | `ucx.triangulate` | `expected/ucx.triangulate.json` |
| 0.8 | 0.8.6 | `ucx.rename` | `expected/ucx.rename.json` |
| 0.8 | 0.8.7 | `udim.ids_to_udims` | `expected/udim.ids_to_udims.json` |
| 0.8 | 0.8.8 | `qa.names_fix` | `expected/qa.names_fix.json` |
| 0.8 | 0.8.9 | `qa.package` | `expected/qa.package.json` |
| 0.8 | 0.8.10 | `export.geojson_write` | `expected/export.geojson_write.json` |
| 0.8 | 0.8.11 | `export.ground_fbx` | `expected/export.ground_fbx.json` |
| 0.8 | 0.8.12 | `export.pivot_place` | `expected/export.pivot_place.json` |
| 0.8 | 0.8.13 | `export.zip` | `expected/export.zip.json` |
| 0.9 | 0.9.1 | `tex.erm_normal_check` | `expected/tex.erm_normal_check.json` |
| 0.9 | 0.9.2 | `tex.finish_map` | `expected/tex.finish_map.json` |
| 0.9 | 0.9.3 | `udim.matid_unwrap` | `expected/udim.matid_unwrap.json` |
| 0.9 | 0.9.4 | `udim.slots` | `expected/udim.slots.json` |
| 0.9 | 0.9.5 | `atlas.flora` | `expected/atlas.flora.json` |
| 0.9 | 0.9.6 | `atlas.groundel` | `expected/atlas.groundel.json` |
| 0.9 | 0.9.7 | `place.flora_repair` | `expected/place.flora_repair.json` |
| 0.9 | 0.9.8 | `place.maf_checks` | `expected/place.maf_checks.json` |
| 0.9 | 0.9.9 | `place.replace` | `expected/place.replace.json` |
| 0.9 | 0.9.10 | `place.schedule` | `expected/place.schedule.json` |
| 0.9 | 0.9.11 | `place.drop_to_ground` | `expected/place.drop_to_ground.json` |
| 0.9 | 0.9.12 | `qa.address` | `expected/qa.address.json` |
| 0.9 | 0.9.13 | `qa.facade_compare` | `expected/qa.facade_compare.json` |
| 0.9 | 0.9.14 | `qa.normals` | `expected/qa.normals.json` |
| 0.9 | 0.9.15 | `qa.sintez` | `expected/qa.sintez.json` |
| 0.9 | 0.9.16 | `export.batch` | `expected/export.batch.json` |
| 0.9 | 0.9.17 | `scene.maps_usage` | `expected/scene.maps_usage.json` |
| 0.9 | 0.9.18 | `light.check` | `expected/light.check.json` |
| 0.9 | 0.9.19 | `qa.procedural_objects` | `expected/qa.procedural_objects.json` |

## Правило на следующую кнопку

Новая кнопка в том же изменении добавляет станцию на базу своей версии (версия — из
`docs/plans/agr-tools-suite.json`), объекты в `catalog.json` и файл `test-polygon/expected/<id кнопки>.json`:
минимум один PASS и один FAIL, либо текст `reason`, почему одного из них нет. Id станции уникален и
принадлежит существующей базе. Это же правило записано в `docs/plans/agr-tools-suite.md`, раздел 11.
Офлайн-проверка: `uv run pytest -q tests/max_tools/test_polygon_expected.py`.

Раннер не ставит и не снимает `%APPDATA%\Autodesk\ApplicationPlugins\AGR-Tools.bundle`.
Если установка всё же понадобится, она обязана вызвать `polygon_core.preserve_user_bundle`: копия
оператора сначала уносится в сторону и в `finally` возвращается байт-в-байт. Его пакет не удаляется.
