# Паспорт проекта 4bk-k3

**4БК, корпус К3 (STLB-04), ВПМ → НПМ ОКС**

Файл данных: `passport.json` (схема `ProjectPassport.schema.json`, контракт К1 #1024). Этот файл — только просмотр; правится паспорт кнопкой «Паспорт».

## Источник

- путь: `C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/inbox/STLB-04_RR_K3_FSD.fbx`
- уровень: **B**, класс: `panelised`
- маршрут: AGR Tools 1.0 in 3ds Max 2026 on Vlad's work scene (layer К3); typical parts modelled once, textured, then replicated
- заметка: Revit 2024 FBX (K3 facade, FSD), feet, no materials; already imported into 3k.max layer 'revit' (metres, 5787 meshes). Finishes only as images (ТЗ_Архитекторы): K3 brick-look concrete tile 280x85 RAL 020 30 20, АКП RAL 4009, frames/sills RAL 7024. Brick texture Bricks1 4096². All inputs with hashes: sources.json.

## Нормализация

- единицы: m (источник: ft), ось вверх: Z (источник: —), масштаб: 0.3048
- общий ноль, м: [0.0, 0.0, 0.0]
- ноль сетки, м: [0.0, 0.0, 0.0]

## Этапы

| Этап | Статус | Время, с |
|---|---|---|
| 0 | todo | — |
| 1 | todo | — |
| 2 | todo | — |
| 3 | todo | — |
| 4 | todo | — |
| 5 | todo | — |
| 6 | todo | — |
| 7 | todo | — |
| 8 | todo | — |
| 9 | todo | — |
| agent | todo | — |

## Части здания (0)

—

## Проёмы (0)

—

## Материалы (0)

—

## Журнал

`journal.jsonl`: строк 0


## Запросы агенту (0)

—

## Вопросы

- Source level A/B/C is not defined in #1024; default rule: A shell, B panelised, C ambiguous/unclassified (scene10_core.LEVEL_RULE).

## Пробелы

- K2: the spec names window_type as an int; the opening marker stores a string library id (agr_window_type). The spec is not changed in this wave (#1024).
- Address, stem SM_<Address>_NNN, GeoJSON point and FNO not given yet.
- Level 0.000 assumed at Z=0 of 3k.max (floor 1 slab top); the Revit link dummy sits at Z=-0.15. User places elevation points.
- No written texture spec: joint width, bond phase, alignment to corners/openings/floors not given; Bricks1 module ratio 3.43 (~290x85 mm) vs scheme 280x85.
- Window surround colour: scheme RAL 7024 vs messenger note ~RGB 122 92 96 (close to АКП RAL 4009).
- Roof, pergola, railing, capsule finishes not specified.
- Tower floor 1, stair and door: Vlad (meeting 2026-11-11); GAP data for floor 1 pending.
