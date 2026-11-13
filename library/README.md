# Библиотеки AGR Tools: где лежат (К5, #1024)

Данные в git — это таблицы и указатели. Тяжёлое (меши, карты, превью) лежит на Google Диске.

**Правило.** Читать только с копии в своей scratch-папке. Скопируйте нужную версию, работайте с копией. Оригинал на Диске не открывать в Max и не менять. Новая версия — новый файл, старые не перезаписываются.

## Outside-agent retrieval

Start at [assets/README.md](../assets/README.md) and its `manifest.json` shared
Drive URL; `recorded_path` and catalogue `C:/x/...` paths are provenance/local
bindings, not portable download URLs. Override the local root in a private workspace.
The read-only `cold_check.py` checks existing local/mounted copies; it does **not**
download assets and is not by itself proof of retrieval on an outside machine.
The [#1316 partial receipt](../docs/library/outside-retrieval-1316.md) records three
real unauthenticated payload downloads, hashes, exact file pointers, and the missing
approved Flora-map dependency gate. It is not a complete three-asset or visual-loop pass.

## Окна

- Диск: `G:\Мой диск\AGR-assets\windows\` (превью, меши).
- Актуальная версия: `library/windows/window_types.json` (в git).
- Данные в git: `library/windows/window_types.json`, `confirmations.json`, `sources/`.
- Генератор: кнопка `win.generate` (`windowgen_core`) строит меш типа по стандарту. Сборка записей — `tools/library/build_window_types.py`.
- Reusable review release: [Windows README](windows/README.md), `catalogue.json`; common [library template](../docs/library/TEMPLATE.md) and [audit](../docs/library/AUDIT.md). Source JSON remains authoritative; quarantine is not an offered asset.

## Материалы

- Диск: `G:\Мой диск\AGR-assets\materials\` (карты, три серые плитки).
- Актуальная версия: указатель `library/materials/materials.json` с sha256 → `materials_vNNN.json`.
- Образцы текстур (решение владельца 06.11.2026, [D218]): `G:\Мой диск\AGR-assets\textures\samples\` — `tiles_dark_grey.png`, `tiles_light_grey.png`, `tiles_white.png`, `bricks.png`. Путь решён; наличие файлов на Диске при переносе не проверялось (аудит видел их только на рабочем столе владельца).
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
