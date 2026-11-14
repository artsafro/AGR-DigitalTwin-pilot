# Паспорт проекта elv-tc-vpm

**ТЦ «СРЕDА», VPM ОКС (SM_Elevatornaya_Vl_1_A_001)**

Адрес: Москва, ул. Элеваторная, вл. 1А

Файл данных: `passport.json` (схема `ProjectPassport.schema.json`, контракт К1 #1024). Этот файл — только просмотр; правится паспорт кнопкой «Паспорт».

## Источник

- путь: `C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\3_sreda\for_ai\00900-МСК-ЭЛВ-ГП1-Р-АР_building (1).fbx`
- уровень: **B**, класс: `panelised`
- маршрут: contour_rebuild (Blender scripts, before AGR Tools 1.0)
- заметка: Revit 2023 FBX, feet, no materials; plus the AGR booklet PDF, 42 sheets (finishes, lights, signage), and the customer TZ 2026-11-05 (stem SM_Elevatornaya_Vl_1_A_001). Level B = parts file source_tier B.

## Нормализация

- единицы: m (источник: ft), ось вверх: Z (источник: —), масштаб: 0.3048
- общий ноль, м: [35.1, -24.2535, 0.0]
- ноль сетки, м: [0.0, 0.0, 0.0]

## Этапы

| Этап | Статус | Время, с |
|---|---|---|
| 0 | done | — |
| 1 | done | — |
| 2 | done | — |
| 3 | done | — |
| 4 | done | — |
| 5 | done | — |
| 6 | done | — |
| 7 | todo | — |
| 8 | todo | — |
| 9 | blocked | — |
| agent | done | — |

## Части здания (44)

- `P01_WoodVolume` — body
- `P02_MetalBase` — body
- `P03_Plinth` — body
- `P04_Soffit_Canopy` — body
- `P05_CW_Upper` — window
- `P06_CW_Lower` — window
- `P07_EntranceNiche` — body
- `P08_RevolvingDoor` — window
- `P09_GlassDoors` — window
- `P10_Ribs` — decor
- `P11_SignFrames` — decor
- `P12_ParapetCaps` — parapet
- `P13_BaseFlashing` — decor
- `P14_FlushDetails_Texture` — decor
- `P15_RoofEdge` — roof
- `P16_Windows` — window
- `P17_MetalDoors_N` — window
- `P18_SouthCanopy` — decor
- `P19_SouthLamellas` — decor
- `P20_MainGlass` — glass
- `P21_S_Facade` — body
- `P22_W_Facade` — body
- `P23_TP_Annex` — body
- `P24_N_Facade` — body
- `P25_Plinth_Flashing_New` — decor
- `P26_Windows_New` — window
- `P27_Doors_New` — window
- `P28_Gates_DockShelters` — window
- `P29_Canopies_New` — decor
- `P30_Lamellas_New` — decor
- `P31_Parapets_New` — parapet
- `P32_Roof_Main` — roof
- `P33_Terrace` — roof
- `P34_Railings` — decor
- `P35_Skylight` — roof
- `P36_Superstructures` — roof
- `P37_RoofBoxes` — equipment
- `P38_FireLadders` — decor
- `P39_Downpipes` — decor
- `P40_Arktos` — equipment
- `P41_Joints` — decor
- `P42_Lights` — equipment
- `P43_InteriorCapsules` — capsule
- `P44_CoverStrips` — decor

## Проёмы (0)

—

## Материалы (3)

- ID 7 → UDIM None
- ID 40 → UDIM None
- ID 39 → UDIM None

## Журнал

`journal.jsonl`: строк 0


## Запросы агенту (0)

—

## Вопросы

—

## Пробелы

- Retro-filled 2026-11-11 from TASK.md and parts/elv_full_parts_v003.json: the job ran before AGR Tools 1.0 (Blender scripts in scripts/), stage times unknown; no Max scene carries agr_passport.
- Stages 7 НПМ and 8 НПМ↔ВПМ are out of scope (VPM-only job); left todo, the schema has no n/a status.
- Materials: only unambiguous matches to library/materials/materials_v002.json are listed (cassette RAL 7024, interior, glass). Delivery IDs 1, 3-33 (RAL 7021 / 1001 / 5024 / 7040 / 9005, wood #C1AE93, glows) have no library entry; UDIM tiles 1001-1015 live in the job texture spec.
- Part roles mapped by hand: doors, gates and curtain walls -> window; flashings, ribs, railings, joints, cover strips -> decor.
- Openings: no OPEN_<nnn> markers (doors and windows placed from library types ELV-01..21 by the job scripts).
- Delivery v005 is the current candidate, accepted by the user 2026-11-05; passed=false until the stage 9 blockers clear.
- Parts file: the `history` key fails the parts schema (open since v002).
