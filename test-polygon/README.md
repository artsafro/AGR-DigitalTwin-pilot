# Тестовый полигон AGR Tools

Синтетическая сцена, чтобы нажимать кнопки AGR Tools 0.2–0.7 и видеть, на каком объекте PASS, а на каком FAIL.
Это не модель заказчика. Скамья «Верона» здесь — ящик с именем GroundEl, не актив #790.

Сборка идёт скриптом. Файл `.max` — результат, формат Max 2024 (открывается и в 2026). В git его нет.

## Как открыть и поиграть

1. Собрать сцену (ниже) или открыть уже собранный `polygon_all.max` из папки результата.
2. Поставить системные единицы в метры. Исключение — отдельный файл `cm_units.max`: он специально в сантиметрах.
3. Пройти базы слева направо: База 0.1, База 0.2, … База 0.7. У каждой базы свой цвет на плоскости земли
   (вид сверху) и подпись в углу: «База 0.x — что добавила версия, какие кнопки».
   Следующая версия AGR Tools добавляет свою базу в конец ряда (`TOUR_LAST` в `polygon_core.py`).
4. Внутри базы — станции. Подпись: «Станция 0.x.N: объект - нажми кнопка -> ожидаешь результат».
   У объекта в пользовательских свойствах `AGR_TEST` начинается с `station=0.x.N`, дальше кнопка и код.
5. Прямоугольники баз лежат на слое `_bases` и называются `_base_0_1`. Подписи — на слое `_labels`
   (`_label_base_0_1`, `_label_0_1_1`); слой можно выключить. И то и другое не экспортируется и не входит
   в проверки: префикс имени `_base_` / `_label_` плюс слой. Сборщик кладёт их только туда. Раннер выбрасывает
   такие имена из отчёта до сравнения. Кнопки выделяют названные объекты станции, не площадку.
6. Кнопки, которые правят сцену (сдвиг UV, атлас, UCX, очистка), сначала идут пробным прогоном. Второе нажатие
   пишет копии. Оригиналы не перезаписываются. Очистка на копии (`имя_AGR_export_`) — строка PASS.
   Экспорт с проверкой на грязном объекте останавливается на воротах `cleanup` (FAIL). Тот же прогон затем
   берёт копию `SM_Polygon_001_Main_AGR_export_` и пишет FBX только в новый путь
   `<папка результата>/export-pass/<имя копии>.fbx`, после чего читает файл обратно (`plan.readback`).
   Это строка PASS. Существующий файл по этому пути раннер не перезаписывает.

Отдельные сцены, их нельзя смешать с общей:

| Файл | Зачем |
|---|---|
| `polygon_all.max` | Базы 0.1–0.7 в метрах, профиль НПМ |
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
| `bases.json` | Ряд баз: версия, подпись, цвет, станции, файл ожидания |
| `scenes/` | Спеки вариантов `cm_units`, `empty`, `vpm` |
| `catalog.json` | Объекты станций и площадки: слой, `station`, `AGR_TEST` |
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

Полный список — `bases.json`. Кнопки версий после 0.7 в ряде ещё без площадки: в их JSON `base` пустой,
`stations` пустой, и записан `reason`. Когда версия входит в тур, у неё появляется база и хотя бы одна станция.

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

## Правило на следующую кнопку

Новая кнопка в том же изменении добавляет станцию на базу своей версии (версия — из
`docs/plans/agr-tools-suite.json`), объекты в `catalog.json` и файл `test-polygon/expected/<id кнопки>.json`:
минимум один PASS и один FAIL, либо текст `reason`, почему одного из них нет. Id станции уникален и
принадлежит существующей базе. Это же правило записано в `docs/plans/agr-tools-suite.md`, раздел 11.
Офлайн-проверка: `uv run pytest -q tests/max_tools/test_polygon_expected.py`.

Раннер не ставит и не снимает `%APPDATA%\Autodesk\ApplicationPlugins\AGR-Tools.bundle`.
Если установка всё же понадобится, она обязана вызвать `polygon_core.preserve_user_bundle`: копия
оператора сначала уносится в сторону и в `finally` возвращается байт-в-байт. Его пакет не удаляется.
