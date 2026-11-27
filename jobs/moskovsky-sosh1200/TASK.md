# moskovsky-sosh1200 — NPM Ground, MAF, Flora (site)

Object: «Общеобразовательная организация на 1200 мест», г. Москва, г. Московский, мкр 1, з/у 47А (ЛСР / Weltbau).
Cell `ground-npm`, trail `routes/site.md`. Branch `job/moskovsky-sosh1200-ground-npm`.

## Sources

- `G:/Мой диск/AGR-assets/moskovsky-sosh1200/source/` + `SHA256SUMS.txt`:
  SPOZU DWG `33_п.Московский Школа 1200_13.11.26.dwg` (ed87f7f9…), PDF `ЛСР-МОСК-ШК1200_ФР_03_09_2026.pdf`.
- DXF of the DWG: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/intake/school.dxf` (МСК-77, m).
- Ledgers extracted from the DWG tables: `intake/maf_ledger.json` (40 positions, block `_МАФ`),
  `intake/planting_ledger.json` (13 positions, block `A$C7f310a12`), `intake/callout_map.json`, `intake/all_tables.json`.
- Reference only: the user's visualisation scene `MOS_GP_26.11.2026.max` (Max 2026, read only) — MAF dummies for size.

## User decisions (intake 2026-11-26)

1. Relief: flat Ground at ±0.000 of the building (confirmed by the user).
2. Scope: model together with the stadium, then cut exactly by the ГПЗУ boundary (`_GL_01_Границы_ГПЗУ`, 22 021.7 m²).
3. Budget 180k tris: Ground 50k / MAF 60k / Flora 70k (default split).
4. Type: the ledgers are the source of truth. Where a ledger and a block name differ, the ledger wins
   (pergola ВСТ 9614/4, urn Аданат 9004, conifer = Туя западная 'Brabant', hedge = пузыреплодник).
5. Count / positions: from the drawing blocks (actual points). Ledger vs drawing count differences are listed and
   marked with helpers in the scene; check each against the visualisation scene.
6. Canopy ВСТ 1519/1 x7: placed on the 7 hatch fills (~31 m² each).
7. MAF sizes: manufacturer pages + dummies from the visualisation scene.
8. Trees: from the A101 flora library, size unchanged.
9. Review: open the scene for the user after Ground and after MAF (3ds Max 2026 QUAD review copy), plus an
   ID-colour copy [D420].

## MAF decisions (2026-11-26)

- Fences: perimeter welded PRO H 2.5 m (whole line along ГПЗУ), sport H 4 m, projected fence; posts as boxes,
  panels as opacity planes in the MAF atlas; wickets 37/38 and gates by blocks.
- Pergola ВСТ 9614/4 x7 (one per back-to-back block pair); container pads Аданат «Бункер» 5003-1 x3 on the 4 «ТБО»
  points; flagpoles 9.35 m; extra drawing points (3rd «Стрела-дуга», 6th log) placed + helper; pos. 19/21/26/34 sized
  from the viz-scene dummies.
- Model source order: A101 MAF library and the MAF library on G: by article / name; no match -> model new, then add
  the new models to the library (publish route).

## MAF answers after the pilots (2026-11-26, "по рекомендациям")

1. Library models (Weltbau `MAF_LIB`, Sokolniki) are not decimated: rebuild light by their construction, in the
   manufacturer size (as the canopy pilot ВСТ 1519/1).
2. Manufacturer photos / DWG may be downloaded per MAF and fence position; retained reference files and their hashes are archived
   (`G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/maf/refs/<pos>/`), reference only, never executed.
3. MAF 512 atlas: add new cells for light wood, concrete, green, blue.
4. Perimeter fence: only the 527 m drawn inside ГПЗУ.
5. Fences: perimeter panel ID 28 «полоски», sport ID 27 «рабица»; posts RAL 7016; panel = one plane, two-sided
   material; sport fence keeps the 13.3 m open side; wickets 1.2 m, sport wicket leaf full height; no 4.5 m gates
   outside ГПЗУ; section step 2.5 m (Grand Line catalogue).

- Sport MAF sizes (group D, 2026-11-26): "делать по DWG" — the manufacturer DWG wins over the page plan and the viz
  dummy (basketball SO-012 board 1800, H 3500; volleyball SO-053 overall 8700, H 2500).

## MAF v002 review (2026-11-26): geometry accepted, open items "по рекомендациям"

Accepted: `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/outputs/maf-npm-v002/review/SM_MoskovskySosh1200_MAF_review_quad_v002.max`
(810 instances, 47 356 tris, atlas 512 v008, 21 helpers). This is the assembled review scene; the individual reusable masters are #1985 drafts in the [published catalogue](../../library/published/catalogue.json).
- Lead's assumptions accepted: canopies 4–7 turned 180° to the play areas; pergolas on block-pair centres facing the
  benches; container yards door on block −Y, 3 containers at 1.45 m; short fence panels by instance X scale; post #214
  0.3 m outside ГПЗУ kept.
- A: chessboard no decal (plain cell); «бежевый бетон» pos 8/10 → cell 24; «Стрела-дуга» flat, red + orange, 3rd point
  kept (drawing = count).
- B: ИК 0209Т-6 for 0209Т-6.1; colours as on the renders; drum without balls.
- C: container 34 at ledger size (v001); yard 32 kept at 1 058 tris; pergola frame ID 2; yard roof ID 30.
- D: flags plain white (no decal, atlas full). E: partitions as drawn (0.31 m short).
- Viz compare (`outputs/maf-npm-v002/compare_viz_v002.json`): matches 0.1–0.3 m except the listed discrepancies.

## Flora decisions (2026-11-26)

- A101 substitutes approved: пихта → elka_t1_h400, клён остролистный → klen_t3_h350, туя 'Brabant' →
  mojevelnik_t2_h400, сирень → siren_t1_h160, дёрен → deren_t1_h120, вейник → zlaki_t1_h150; exact: Гиннала,
  сосна горная, пузыреплодник.
- Астильба, хоста: not done, the user decides later how to show them.
- Densities: hedge 5 /m² (~4 300), дёрен 3 /m², вейник 6 /m². Nothing outside ГПЗУ.
- A101 textures (TextureFlora, low) approved for these species; one Flora atlas from them.
- Scale exactly 1.0 (library size, textures must not drift) — user deviation from the D100 ±10 % jitter.

## Ground v001 review (2026-11-26): not accepted

- Building footprint: no hole; capped, cover ID 2 (paving) — user deviation from D251 for this job.
- One lawn cover: flower beds, shrub beds, hedge, rolled lawn = lawn (plants are placed on top).
- Rubber: split by colour and drawings from `_ резинаV1_1.dwg` (bbf22dce…), sent by the architects 2026-11-26.
- Stadium part inside ГПЗУ: covers + markings.
- Markings = separate mesh, top +8 mm, embedded ~10 mm (or per rule): long jump («3D контура»), track lanes,
  volleyball, badminton (layer 0), basketball (layer «проектируемые дороги»), rubber-DWG drawings.
- Ultra-thin slivers: the user fixes by hand; report the count only.

## Ground v002 (2026-11-26): geometry accepted

- 8 leftover rubber spots under shade canopies → compacted soil, own ID.
- Rubber zones: rubber-crumb texture recoloured to the zone RAL.
- Markings: white NPM texture + UV in the Ground atlas set.
- Curbs: not modelled.
