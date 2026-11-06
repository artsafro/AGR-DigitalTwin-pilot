# Библиотеки AGR Tools: где лежат (К5, #1024)

Данные в git — это таблицы и указатели. Тяжёлое (меши, карты, превью) лежит на Google Диске.

**Правило.** Читать только с копии в своей scratch-папке. Скопируйте нужную версию, работайте с копией. Оригинал на Диске не открывать в Max и не менять. Новая версия — новый файл, старые не перезаписываются.

## Окна

- Диск: `G:\Мой диск\AGR-assets\windows\` (превью, меши).
- Актуальная версия: `library/windows/window_types.json` (в git).
- Данные в git: `library/windows/window_types.json`, `confirmations.json`, `sources/`.
- Генератор: кнопка `win.generate` (`windowgen_core`) строит меш типа по стандарту. Сборка записей — `tools/library/build_window_types.py`.
- Появится в ветке J: `standard.json`, `drafts/`, лист превью, статусы и карантин.

## Материалы

- Диск: `G:\Мой диск\AGR-assets\materials\` (карты, три серые плитки).
- Актуальная версия: указатель `library/materials/materials.json` с sha256 → `materials_vNNN.json`.
- Образцы текстур (решение владельца 06.11.2026, [D217]): `G:\Мой диск\AGR-assets\textures\samples\` — `tiles_dark_grey.png`, `tiles_light_grey.png`, `tiles_white.png`, `bricks.png`. Путь решён; наличие файлов на Диске при переносе не проверялось (аудит видел их только на рабочем столе владельца).
- Аудит материалов по джобам и решения Q1–Q12: `library/materials/AUDIT-2026-11.md`.

## МАФ

- Диск: `G:\Мой диск\AGR-assets\maf\`.
- Актуальная версия: `library/maf/material_ids_v005.json` (с `material_ids_v005.md`).
- Данные в git: `library/maf/` (каталог, раскладка атласа v005, аудит).

## Flora

- Диск: `G:\Мой диск\AGR-assets\flora\`.
- Данные в git: `library/flora/catalogue.json`, `maps.json`, `species-curation.json` (см. `library/flora/README.md`).
- Сейчас бинарники Flora лежат вне git по пути из `library/flora/README.md`. Перенос на Диск — по решению владельца.

## Корпус

- `G:\Мой диск\AGR-assets\corpus\` — KPP1, OBJ03, SOSH1150.
- Приватный. В git и публичные репозитории не попадает. Читать только с копии.
