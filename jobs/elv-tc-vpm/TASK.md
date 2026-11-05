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

- Lighting layout `parts/lighting_layout_v001.json` (sheets 33–35, 498 fixtures). Claude's choices (minor, within
  source tolerance): 2000K belt over metal / 2700K wood parapet per sheet 33 legend + render 38; plan (sheet 35)
  for position along the facade, facade sheets for height; fixtures on R3.15 arcs placed by unrolled length;
  the 6 FBX `Arktos` boxes are not booklet fixtures → kept as geometry ID27 without emission; housing sections
  assumed (sheet 40 gives lengths only).

- Railings (terrace) and fire ladders: **geometry** (simple posts/rails/stringers/rungs), not alpha (user, 2026-11-04).

- **Railings (terrace) and fire ladders stay GEOMETRY** as built in v003, not alpha (user 2026-11-04); textured as
  metal RAL 7021 (ID20 placeholder), no alpha maps.

## Whole building v004 / tex-v002 (2026-11-05, technical QA only; user acceptance open)

- Library first: single doors In-1H added as ELV-18 (900, frame 1050×2050), ELV-19 (1100, 1250×2050, variant of
  ELV-18), ELV-20 (1100 with a 2250 frame at the TP annex, variant of ELV-18 — the FBX instance is 20 cm taller than
  its nominal type, so by [D140] it is its own size). The 3 single doors are placed from them.
- Lights: housings as Main geometry (part P42, ID27 RAL 7021), glow faces own IDs.
- **Deviation — working IDs beyond the attachments range 26-30:** glow IDs ID28 purple, ID29 2700K, ID30 2000K,
  ID31 4000K (LINE + DECO), ID32 RGB static warm white (FOCUS, PLAT-A4), ID33 3000K (TUBE M); colour in Diffuse,
  ERM R = 1.0 only on these tiles. ID27 = housings + the 6 Arktos (no emission).
- **Deviation — DECO over the 4 gates raised +0.32 m** (z 4.30 → 4.62) to clear the dock-shelter hoods (top +4.50).
- Glow faces: lines and DECO / FOCUS / PLAT the front face, TUBE M top + bottom (assumed; sheet 40 gives no sections).
- Base flashing 5024 continued on the new plinth flashing (P25); other new flashings 7021 [D13].
- Sandwich horizontal joints from the FBX rows (+4.62, +10.37, +5.71), anchored per face (v lattice 3.2 m).

## Delivery v002 decisions (user, 2026-11-05)

- GeoJSON point: for now at the building centre in model coordinates (pivot 0,0,0), no MSK-77 binding; FNO code and
  name empty. V011 stays open (TODO) until the customer gives the SPOZU DWG or an MSK-77 point. Okrug ЮАО (derived
  from the address) confirmed.
- Attachments stand off by 6 mm instead of the 10 mm embed; the 4 remaining self-intersections of the pilot niche frame
  are accepted (conflicts #44). UCX names keep the project form `UCX_SM_Elevatornaya_1A_Main_NNN` (#45). V007 DirectX
  review on flat tiles accepted (#46) [D196].
- Next: renders of build-v006 (all sides, day and night), 3ds Max xView 5/2 mm after Mesh + Weld 0.002 in an own Max
  instance, then one acceptance pack: Gate 1 for P21–P42, library types ELV-01..20 [D140], visual acceptance.

## Acceptance (user, 2026-11-05)

- **Accepted by the user** («Принимаю всё»): parts P21–P42 (Gate 1), library types ELV-01..20 [D140] and the visual of
  delivery v002 (`outputs/renders-v002/`), including the wood colour, the NW corner strip on the west elevation and
  the layer over the roof terrace as rendered.
- Technical QA: V001–V004 pass (V004 max 4); 3ds Max 2024 xView after Mesh + Weld 0.002: 0 faces (5 mm) / 0 vertices
  (2 mm) on all 962 meshes (`outputs/xview-max-v001/`); Blender xView 0.
- Not passed (passed=true forbidden): V011 (MSK-77 point, FNO code/name — waiting for the customer); SINTEZ AGR
  Checker not run; signage «СРЕDА» waits for the TZ; `_Light.fbx` by the user.

## Customer TZ 2026-11-05 (rework list on the customer's blank `SM_Elevatornaya_Vl_1_A_001`)

Inputs (read-only copies): `Dima_Andrew\3_sreda\customer_2026-11-05\` — `TC_Sreda-04-11-2026-1.pur` (sha256 1e088d29…849b),
`SREDA_fasad_v0.6.blend` (acecd0ad…615e), `SM_Elevatornaya_Vl_1_A_001.zip` (3051e465…813f). Analysis:
`outputs/customer-tz-v001/tz_summary.md`, `outputs/customer-blank-v001/compare.md`.

User answers (2026-11-05):
- Base: **our** accepted model (delivery v002), not the customer's blank.
- Name: **the customer's stem** `SM_Elevatornaya_Vl_1_A_001` (replaces `SM_Elevatornaya_1A`).
- Horizontal joints stay in the texture for now. Which «накладки» the TZ means is unclear — to clarify (customer
  scene collection `RZshow_SRC_Накладки`, 131 meshes; TZ notes at +4.6 / +10.4) before any geometry.
- Cutting windows / entrances through the stemalit on the front facade: not decided — look at the model first.
- Customer's false rooms and door niches: not decided — show which ones first.
- Colours: cassette RAL 7024 (customer) instead of 7021; wood as smooth cassettes per the site photo, colour from
  the photo until the act gives the target.
- Checker: SINTEZ AGR Checker run and clean except FNO code (no data).

User answers 2 (2026-11-05, after `outputs/customer-clarify-v001/`), all recommendations accepted:
- «Накладки» = the 24 horizontal joint cover strips (booklet item 14 «нащельник RAL 7021», Revit Batten_FS-8P,
  165 × 22 mm, +4.535…4.700 and +10.285…10.450, ~413 m) → geometry, RAL 7021. Other joints stay in the texture.
- Stemalit on И-А: nothing to cut (our openings are real glass; TZ item 5 describes the customer blank).
- False rooms = **interior capsules**: behind every window and glazed door a box (parallelepiped) with the opening
  side removed, so through the glass one never sees back faces or the void. Its open-edge contour sits inside the
  opening at the depth of the **middle of the frame** (window / door frame, or reveal), sized to the opening, so at a
  grazing view (~180°) through the glass the open edges stay hidden. Dark interior ID. Customer depth reference
  0.80 m (0.92 m on the slanted NW wall).
- Check west opening №30 (door per booklet and customer, missing in ours?) and the glass vision panels of doors
  №1, 4, 11, 21, 25; fix per booklet.

## Не трогать

- Source files in `for_ai\` (work on byte-identical copies only).
- Tenant brands from renders (frames only); FNO code (never invented).
- Geometry that matches the album: do not «improve» it from renders.

## Pilot

Main facade И-А end to end (wood volumes, curtain walls, entrance, ribs, reveals, textures), picture to the user,
then the rest.
