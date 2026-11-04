# elv-tc-vpm — VPM of the shopping centre «СРЕDА», Moscow, Elevatornaya vl. 1A

Intake per [D186], 2026-11-04. Profile: **VPM-OKS only** (no NPM). One OKS, so no `_001` index.

## Requirement (Artem, verbatim excerpts)

> «задача только VPM UKS» (UKS = ОКС). «разобраться что это за UKS, какие используются материалы, какие будут ID,
> как будет выглядеть геометрия под VPM ... осветительные приборы, как выполнить надписи».
> «нужно сравнить геометрию с FBX и альбомы ... если все сходится, тогда FBX будет главнее».
> «Отделка свет-вывески из буклета ... Чертежи важнее рендеров, но рендеры как ориентир очень важные.
> Спорные моменты пришли мне на согласование».
> «на фасаде много где используются швы, и все эти швы мы будем показывать текстуры».
> «Откосы мы делаем в цвет фасада, заглушкой, отдельным айдишником».

## Inputs (source authority)

| Input | Path | Authority |
|---|---|---|
| Revit 2023 FBX, feet, no materials | `C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\3_sreda\for_ai\00900-МСК-ЭЛВ-ГП1-Р-АР_building (1).fbx`, SHA256 `7CCF502D9DC1494DAA885E650DD8B2B7E261C7B90B262EE157C188EC3A78B961` | geometry (matches album grid ≤ 1 mm) |
| AGR booklet, 42 sheets | `...\for_ai\ЭЛВ_ИД_АГР_45-4-25-С_Буклет АГР от 27.01.2025 (1) (1).pdf` | finishes, lights, signage; drawings > renders |
| Signage TZ from the customer | not received | «СРЕDА» letters may wait for it |

## Decisions (user, 2026-11-04)

- Delete interiors; delete a duplicate only after world-vertex verification (212 true duplicates found).
- Railings: simple geometry or alpha — decided together later.
- Windows: census of types first; missing types are added to `library/windows/` first, then placed from it.
- UCX and 1 m perimeter drop into the ground: yes.
- Lights: emissive (ERM R) per booklet, combined with FBX; keep the 6 FBX `Arktos` objects for now.
  `_Light.fbx` is made by the user later.
- Address stem `SM_Elevatornaya_1A`; GeoJSON FNO code empty for now.
- Textures: procedural by RAL + joint grid from the album; wood texture generated (no user texture).
- Reveals: two IDs by zone — grey RAL 7021 and wood RAL 1001.
- Disputes D01–D14, D16 accepted as recommended (2026-11-04):
  D01 wood RAL 1001 with render-like grain; D02 sandwich RAL 7021; D03 metal cassette 1500×500, joint 20;
  D04 wood cassette 1000×1530; D05 ribs over the whole upper curtain wall as in FBX, wood colour;
  D06 stemalit bands as in FBX; D07 add the revolving door (Ø≈4.2 m) per album; D08 rounded corners as in FBX;
  D09 tenant frames as in FBX, no brands; D10 gates RAL 7040; D11 glass clear; D12 south window strip as in FBX;
  D13 flashings coloured by zone (over wood 1001, over curtain wall 5024, else 7021);
  D14 add the 2 missing south canopies and the north door at x≈38.4 per album; D16 TP annex paint RAL 7021.
- **D15 not a discrepancy** (re-measured, `outputs/intake-v002/D15*.jpg`): south axes 9-10 are windows in the
  album too (sheet 18 window symbol, sheet 20 callout «Окна ...»), FBX 980×1180 at z 0.81; the east door near
  axis Е is at y≈−34.8 on sheet 18 and in FBX (plan sheet 25 Δ≈0.3 m). The first pass misread both. Pending the
  user's look.

- **Gate 1, pilot И-А parts v001 confirmed by the user 2026-11-04** with one change: F50 mullion caps stay
  **geometry** for now (not texture). Also confirmed: soffit under the cantilever +4.70 and the niche ceiling built
  as wood (ID 19, RAL 1001; missing in FBX); revolving door height 2.72 (niche transom line); base flashing
  RAL 5024; F50 frames RAL 7021; the 34 m south return is in the pilot; sign frames 20 mm off the facade, no
  brackets; facade lighting is a separate part after the pilot.

- **Pilot И-А accepted by the user 2026-11-04** (build-v002: geometry + UDIM 1001–1015 + procedural textures,
  683 px/m, wood RAL 1001 light beige). Roll out the same scripts to the rest of the building.

## Не трогать

- Source files in `for_ai\` (work on byte-identical copies only).
- Tenant brands from renders (frames only); FNO code (never invented).
- Geometry that matches the album: do not «improve» it from renders.

## Pilot

Main facade И-А end to end (wood volumes, curtain walls, entrance, ribs, reveals, textures), picture to the user,
then the rest.
