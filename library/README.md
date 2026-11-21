# Библиотеки AGR Tools: где лежат (К5, #1024)

Данные в git — это таблицы и указатели. Тяжёлое (меши, карты, превью) лежит на Google Диске.

**Правило.** Читать только с копии в своей scratch-папке. Скопируйте нужную версию, работайте с копией. Оригинал на Диске не открывать в Max и не менять. Новая версия — новый файл, старые не перезаписываются.

## Outside-agent retrieval

For an executable, exact-version selection start with
[`outside-retrieval-v001.json`](outside-retrieval-v001.json): MAF_0002 source FBX,
Tilia A101 low v002 (container plus RGBA/RGB/alpha dependencies), and the published
material-40 interior diffuse placeholder. Each file has a direct download URL,
SHA-256 and size; none needs a local cache or Drive desktop mount. Asset boundaries
are explicit: a placeholder is not a complete texture triplet or delivery shader.
The [#1316 receipt](../docs/library/outside-retrieval-1316.md) preserves failed probes,
native readback, successful A101 cold downloads and the exact Tilia approval.
`assets/README.md` and its `manifest.json` remain the shared Drive root route;
`recorded_path` and old catalogue C:/x paths are provenance/local bindings, not URLs.
The read-only `cold_check.py` checks existing local/mounted copies; it does **not**
download assets and is not by itself proof of outside retrieval.

Current Flora routes/availability are in `flora/maps.json`; hash-keyed A101 versions
and download records are in `flora/a101-native-v002.json`. Frozen v003 geometry/light
releases reproduce from `flora/maps-v003-snapshot.json`, not from today's selection.
Do not substitute A101 atlases on the old v003 geometry. Visual requests/answers use
[the version-bound loop](../docs/library/visual-loop.md), not implicit approvals.

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
- Актуальная версия списка ID материалов: `library/maf/material_ids_v007.json` (с `material_ids_v007.md`): v006 + ID 33 `wood_pine` (сосна, отдельный слот WOOD2), D240. Изменения от предыдущих версий: `library/maf/material_ids_v006_change.json`, `library/maf/material_ids_v007_change.json`.
- Предыдущая версия v005 — первая рабочая (D181); не актуальна, новые МАФ на неё не назначаются.
- Атлас 512 v007 (`library/maf/atlas_512_v007.json`) — только для новых МАФ; у библиотечных МАФ развёртка и атлас остаются прежними, ничего не переназначается (D240).
- Данные в git: `library/maf/` (каталог, раскладки атласа v005 / v006, атлас 512 v007, аудит).

## Flora

- Диск: `G:\Мой диск\AGR-assets\flora\`.
- Данные в git: `library/flora/catalogue.json`, `maps.json`, `species-curation.json` (см. `library/flora/README.md`).
- Версии и download routes: `library/flora/a101-native-v002.json`; текущая доступность — `maps.json`, исторический v003 snapshot не является обещанием доступности карт. См. `library/flora/README.md`.

## Корпус

- `G:\Мой диск\AGR-assets\corpus\` — KPP1, OBJ03, SOSH1150.
- Приватный. В git и публичные репозитории не попадает. Читать только с копии.
