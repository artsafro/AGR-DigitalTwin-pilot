# silikatny-maf-viz — МАФ ЖК «Силикатный» для визуализации

Status: modelled; FBX read back in Blender and in 3ds Max 2026.3 (headless) — technical checks pass; user acceptance open.
Route: visualisation, not NPM/VPM [D189]. Binaries and builder scripts stay outside git in `C:/x/silikatny-maf-viz/`.

## Sources (read only)

| Source | sha256 (16) | Role |
|---|---|---|
| `Downloads/Telegram Desktop/МАФ_и_свет_модели_фото (4).docx` | `577c5af4e36527b2` | task list: 32 MAF rows, red = not modelled (pos 4, 15) |
| `Silikatniy_UVK/pravki/СИЛ13-УВК-ПД-ПЗУ_.dwg` | `b6f302d433a22c9b` | newest ПЗУ: MAF schedule, plan blocks, gate/fence elevations |
| `Downloads/Telegram Desktop/Силикатный маф.zip` | `4ec932521c3c0800` | manufacturer photos (same DWG inside) |
| `Задание на визы Силикатный/Альбом АГР_Силикатный_ корр. Гранель 08.04.25 (2).pdf` p31 | — | render of the shade canopy (pos 1, v1, superseded) |
| `Downloads/screenshot-2026-11-06-16-01-36.png` | `4a0e3feffc2d7188` | pos 1 v2 look: the schedule picture (table cell block «28»), sent by Artem 2026-11-06 |

Manufacturer dimensions: `C:/x/silikatny-maf-viz/sources/maf_research.md`; DWG inspection
`C:/x/silikatny-maf-viz/sources/individual_maf.md` (hashes before = after).

## Outputs

| File | sha256 (16) |
|---|---|
| `C:/x/silikatny-maf-viz/blend/SIL_MAF_v004.blend` (collection `SIL_MAF`, 30 objects; v003 + pos 1 v2) | `dfe4d1e13faa3fdf` |
| `C:/x/silikatny-maf-viz/fbx/SIL_MAF_v004.fbx` | `f4e7ff1c59bee2b2` |
| `C:/x/silikatny-maf-viz/max/SIL_MAF_v004_max2024.max` (3ds Max 2024, one Multi/Sub `SIL_MAF_multisub_33`) | — |
| `C:/x/silikatny-maf-viz/scripts/` `maf_kit.py`, `maf_models.py`, `maf_models2.py`, `run_build.py` | `facabd41`, `263d3e89`, `948a7f7e`, `d6f19ab8` |
| previews `C:/x/silikatny-maf-viz/preview/` (pos 1 v2: `p01_v2/`) | — |

v003 (`638003f9483a5943` / FBX `435304f5cc1acb2e`) stays as the previous version. Rebuild in Blender 5.1: exec the
four scripts in that order, then `build_all()`; v004 = v003 with pos 1 replaced by `build_v004_p01.py`.

## Materials [D189]

Every object has the same 33 slots: `ID01_paint_ral9005` … `ID31_polycarbonate` (library v005 [D181]) +
`ID32_paint_ral2003` (ДОО) + `ID33_paint_ral5012` (СОШ). HPL parts of play items are ID 32; swap to 33 for СОШ copies.
This list is job-local: library v006 gives ID 32 to `wood_hpl_satin` [D229]; the set is not renumbered, and a model
taken from here into the library remaps 32/33 first [D237].
Blender FBX readback: 30/30 objects keep 33 slots in order, same IDs, tris, dims, one UV layer (box, 1 m = 1 UV).
3ds Max 2026.3 FBX import (defaults, metres): 30/30 Editable_Poly sharing one `MultiMat_0` with subs 1..33 in order;
per-object face IDs equal the Blender IDs for all 30; one Multi/Sub assigned to all objects changes 0 faces.
Evidence: `C:/x/silikatny-maf-viz/max_readback/` (`readback_report.txt`, `SIL_MAF_v003_shared_multisub.max`).
v004: Blender FBX readback 30/30 objects with 33 slots in order and one UV layer; against v003 only pos 1 differs
(`C:/x/silikatny-maf-viz/fbx/readback_v003.json`, `readback_v004.json`). 3ds Max 2024 batch import: 30 objects,
one Multi/Sub of 33 subs in order, 0 faces changed material (`max/SIL_MAF_v004_max2024_log.txt`).

## Objects (dims L × W × H m; card = manufacturer page)

| Pos | Object | Source | Card | Model | Tris |
|---|---|---|---|---|---|
| 1 | `MAF_P01_IND_NavesTenevoy` (v2) | plan 6.0 × 4.2 (8 inserts) + schedule picture | S = 25.0 m², H not given | roof 6.0 × 4.2 × 2.87 (6.1 × 4.32 with gutter) | 2460 |
| 3 | `MAF_P03_MDP-1007_Stolik` | Деткки | 1.156 × 1.154 × 0.53 | 1.16 × 1.16 × 0.53 | 896 |
| 5 | `MAF_P05_BLR-2007_Balansir` | Деткки | 2.03 × 0.13 × 0.30 | same | 272 |
| 6 | `MAF_P06_IPN-2012_Chasy` | Деткки | 0.948 × 0.089 × 1.256 | same | 704 |
| 7 | `MAF_P07_IPN-2007_Gipno2` | Деткки | 0.55 × 0.11 × 1.368 | 0.55 × 0.08 × 1.368 | 7418 |
| 8 | `MAF_P08_IPN-2015_MelovayaDoska` | Деткки | 0.948 × 0.089 × 1.256 | 0.948 × 0.095 × 1.256 | 444 |
| 9 | `MAF_P09_IPN-2005_Truby` | Деткки | 1.319 × 0.525 × 1.255 | 1.318 × 0.52 × 1.269 | 2248 |
| 10 | `MAF_P10_IPN-2028_Schety` | Деткки | 0.96 × 0.122 × 1.256 | same | 4748 |
| 13 | `MAF_P13_SKM-0069-1_Forum` | Деткки | 2.0 × 0.5 × 0.802 | 2.0 × 0.5 × 0.804 | 1804 |
| 14 | `MAF_P14_SKM-0069_Forum` | Деткки | 2.0 × 0.5 × 0.45 | 2.0 × 0.5 × 0.452 | 1568 |
| 16 | `MAF_P16_SPT-0001_Paskal` | Деткки | table 1.0 × 1.0 × 0.8, 2 chairs | 1.0 × 2.43 × 0.80 (set) | 1444 |
| 17 | `MAF_P17_STL-M-0007_Briz` | Деткки | 1.5 × 1.88 × 0.78 | 1.5 × 1.915 × 0.78 | 1480 |
| 18 | `MAF_P18_VLP-0001_Rumb` | Деткки | 1.2 × 0.98 × 0.5 | 1.2 × 0.99 × 0.505 | 984 |
| 19 | `MAF_P19_PM-158_Vud` | Рельеф | 7.5 × 1.8 × 2.53 | 7.5 × 1.79 × 2.53 | 5308 |
| 20 | `MAF_P20_VST-9624-3_Naves` | ГК «Высота» card [D190] | 5.0 × 1.75 × 2.0 | same | 1656 |
| 21 | `MAF_P21_5003-1_Bunker3` | Аданат | 4.54 × 2.51 × 2.49 | 4.60 × 2.63 × 2.47 | 5736 |
| 22 | `MAF_P22_5003-2_Bunker4` | Аданат | 6.62 × 2.51 × 2.49 | 6.68 × 2.63 × 2.47 | 8160 |
| 23 | `MAF_P23_5052_Hozblok` | Аданат | 1.12 × 2.51 × 2.49 | 1.18 × 2.63 × 2.47 | 3312 |
| 24 | `MAF_P24_AL-L-06-11_Flagshtok` | Grand-mag (Ø estimated) | H 9.0 | 0.3 × 0.3 × 9.0 | 360 |
| 25 | `MAF_P25_44708_Vorota` | Хоббика (name dims) | 2.05 × 1.44 × 2.22 | 2.05 × 1.46 × 2.23 | 1592 |
| 26 | `MAF_P26_SO-053_Voleibol` | Поколение | 8.7 × 0.08 × 2.5 | 8.70 × 0.08 × 2.5 | 300 |
| 27 | `MAF_P27_MK001_Konteiner1100` | reference 1100 L (article not found) | 1.36 × 1.085 × 1.37 | 1.40 × 1.10 × 1.37 | 520 |
| 28 | `MAF_P28_5963-S_Urna` | Игратекс | 0.40 × 0.28 × 0.855 | same | 412 |
| 29 | `MAF_P29_IND_OgrazhdeniePRO_sekciya` | DWG section (scale from H 2.5) | 2.04 c/c × 2.5 | 2.04 × 0.10 × 2.5 | 240 |
| 30 | `MAF_P30_IND_VorotaRaspashnye_4-2` | DWG elevation 1:1 | opening 4.2, H 2.51 | 4.5 × 0.15 × 2.51 | 636 |
| 31 | `MAF_P31_IND_KalitkaPRO_1-2` | plan 1.2; gate pattern (est.) | 1.2 | 1.5 × 0.15 × 2.51 | 240 |
| 32 | `MAF_P32_IND_KalitkaSport_1-0` | plan 1.0; height from older revision (est.) | 1.0 | 1.12 × 0.11 × 4.0 | 120 |
| 33 | `MAF_P33_IND_OgrazhdenieSport_sekciya` | H 4 from older revision (est.) | — | 2.49 × 0.09 × 4.0 | 60 |
| 34 | `MAF_P34_IDN-500S_Lezhachiy` | Стандартпарк: 11 middle modules | 5.5 × 0.5 × 0.056 | 5.5 × 0.5 × 0.058 | 968 |
| 35 | `MAF_P35_DO-IDN-500-KK_KoncElement` | Стандартпарк end element | 0.25 × 0.5 × 0.056 | same | 36 |

Not modelled: pos 4, 15 (red in the task), lighting [D189]. Fences 29 and 33 are one section each (array along the route).

## Verify lines (individual projects — each needs Artem's look)

- Pos 1 shade canopy v2 (2026-11-06): plan contour measured in the open ПЗУ DWG (block `A$Ca0fdae5c`, 6.0 × 4.2,
  8 inserts at scale 1, rotations 53.2° ×6 and 117.9° ×2) = roof outline; look from the schedule picture: deck on
  sleepers, black steel posts 100 (4 back, 2 front, 1 per end) and ring beam, vertical slats 45/90 mm on the back and
  both ends with polycarbonate inside, bench 0.45 × 0.45 along the back wall, timber roof 0.20 falling 3 % to the
  back, gutter + downpipe, 2-tube snow guard on 8 brackets. Estimated: heights (beam 2.60, top 2.87), post pitch,
  slat pitch, slope, which long side is open (the plan symbol does not show it). Design sheet still missing.
- Pos 29 fence PRO: section scale inferred from H 2.5; colour RAL 7016 assumed (not in the sources).
- Pos 30 gates: elevation 1:1, opening set to 4.2 per the schedule (elevation shows 4.05).
- Pos 31 perimeter wicket: no elevation; gate pattern used.
- Pos 32 sport wicket: no elevation; leaf 1.0 × 2.0 with mesh above to 4.0 (estimate).
- Pos 33 sport fence: height 4.0 and mesh from the older revision (ООО «Палисад»); newest revision gives none.

## Open

- Not in the task list but in the pravki legend: noise barrier H 2.5 from monolithic polycarbonate, 207 m.
- Photos in the zip not in the schedule: `5.png` (blue speaking pipes), two pebbles (`h3gaef…jpg`, `ЛГСП-97.1`).
