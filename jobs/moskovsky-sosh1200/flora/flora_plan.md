# moskovsky-sosh1200 — Flora NPM plan v001 (2026-11-26)

Machine-readable: `flora_plan.json`; points/beds: `flora_points.json` (`scripts/flora_points.py`).
Library: A101 `FLORIO_221.max` (sha256 `c9edd5f3…676b`, copy read headless in 3ds Max 2026 batch →
`G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/flora/inspect/a101_dump.json`, 347 objects). Catalogue v003 (`library/flora/catalogue.json`)
is not usable for this job: every species' v001 maps are `missing` (`library/flora/maps.json`).
Ledger = species, drawing blocks = positions/counts (TASK decisions 4–5). Inside = in ГПЗУ ring 2B6 (22 021.7 m²).

| Pos | Ledger species | Inside ГПЗУ | A101 object (W×D×H m, tris) | Match | Status | Tris est. |
|---|---|---|---|---|---|---|
| 1 | Пихта сибирская (Abies sibirica) | 1 pt | `elka_t1_h400_low` 1.29×1.33×3.93, 48 | none (no Abies) | question | 48 |
| 2 | Клён остролистный (Acer platanoides) | 37 pt | `klen_t3_h350_low` 2.95×2.56×3.40, 571 | genus; A101 maples are red/purple cultivars, t3 the only green-yellow | question | 21 127 |
| 3 | Туя западная 'Брабант' (blocks «Сосна обыкн») | 19 pt (+6 out) | `mojevelnik_t2_h400_low` 1.29×1.33×3.93, 48 | none (no Thuja) | question | 912 |
| 4 | Клён Гиннала (Acer tataricum subsp. ginnala) | 12 pt (+3 out) | `klen_ginnala_t1_h150_low` 1.63×1.62×1.63, 4 | exact species | **placed** | 48 |
| 5 | Сирень обыкн. 'Красавица Москвы' | 59 pt | `siren_t1_h160_low` 2.05×2.34×1.74, 4 | genus, cultivar unknown | question | 236 |
| 6 | Дёрен белый 'Элегантиссима' | bed 92.2 m² | `deren_t1_h120_low` 1.32×1.39×1.33, 4 | genus, not variegated | question (rate 3/m² proposed) | 1 104 |
| 7 | Сосна горная 'Мугус' | bed 66.4 m² | `sosna_gornaya_t1_h60_low` 1.12×1.13×0.64, 4 | exact species | **placed**, 6/m² = 398 | 1 592 |
| 8 | Пузыреплодник 'Дартс Голд' (живая изгородь) | hedge 859.6 m² | `puzyreplodnik_kalinolistnyj_t1_h150_low` 1.89×1.89×1.55, 4 | exact species, yellow form | **placed**, 5/m² = 4 299 | 17 196 |
| 9 | Астильба Арендса 'айс Глория' | bed 23.0 m² | none; candidate `derbennik_ivolistniy_t1_h80_low` | none | question | 920 |
| 10 | Вейник 'Карл Форстер' | bed 98.2 m² | `zlaki_t1_h150_low` 1.16×1.25×1.54, 4 | generic plumed grass; catalogue 409 exact but maps missing | question (rate 6/m² proposed) | 2 356 |
| 11 | Хоста гибридная 'Стилет' | bed 127.4 m² | none; candidate `osoka_palmolistnaya_t1_h80_low` | none | question | 5 096 |
| 12–13 | Газоны | — | — | Ground texture (FLO-01) | — | 0 |

Total estimate with the recommended stand-ins: **50 631 tris** of 70 000 (Flora share, D097). Placed now: 18 836.

Beds (hatch → position by the label's leader arrow): hedge = the 253 «Стефанандра» layer only (1035.3 m² = ledger
1036; 859.6 m² inside ГПЗУ); 240 «Живая изгородь» hatches are the perennial beds 9–11. Four hatches resolved by the
ledger area balance (`RESOLVE` in the script): A008FB → 6 (54.4 + 40.7 = 95.1 = ledger 95), A00902, A0090D, A00947
→ 11 (133.4 ≈ ledger 132). Bed areas inside ГПЗУ vs ledger: 6 92.2/95, 7 66.4/66, 9 23.0/23, 10 98.2/97, 11 127.4/132.

Placement v001 (`scripts/flora_place.py` → `dt_ai.placement.engine`, seed 1200): 4 709 placed / 0 failed, sink 0.100 m
on all, random Z rotation, scale ±10 % (D100; schedule band = A101 size, ledger has no sizes). Status `review` only
for the skirt's vertical triangles skipped (WARN). Ground = v001 GPZU OBJ (flat ±0; to be rebuilt — positions are XY,
heights 0, so a re-run on the new Ground changes nothing in XY).

Atlas: `tools/library/flora_atlas_from_scene.py` (#217) is in the tree; it refuses — the A101 maps are `pending`
(only `lipa_t1_h550_low` is approved). Prepared: split maps (RGB + unchanged A) and a `pending` job catalogue; packing
check: 3 species → 1024 tiles (scale 0.496), 11 species → 512 tiles (scale 0.246), one 2048 atlas either way.

## v002 (2026-11-26, user answers)

- Substitutes approved by the user: 1 → `elka_t1_h400_low` (ID 128), 2 → `klen_t3_h350_low` (107), 3 → `mojevelnik_t2_h400_low`
  (119), 5 → `siren_t1_h160_low` (111), 6 → `deren_t1_h120_low` (240, 3/m²), 10 → `zlaki_t1_h150_low` (409, 6/m²);
  exact: 4 (106), 7 (224, 6/m²), 8 hedge (301, 5/m²). IDs are job-local.
- **Pos 9 Астильба, pos 11 Хоста: NOT DONE — waiting for the user's decision how to show them.**
- Nothing outside ГПЗУ. **User deviation from D100 for this job:** scale exactly 1.0 (no ±10 % jitter), random Z
  rotation kept (`engine.SCALE_JITTER = 0` in `scripts/flora_place.py`).
- A101 TextureFlora low maps of these 9 objects approved by the user 2026-11-26 (job scope); recorded in
  `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/flora/job_catalogue_v002.json`.
- Result `G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/outputs/flora-npm-v002/`: 5 689 plants placed / 0 failed, sink 0.100 m, scale 1.0
  (|det−1| ≤ 2e-16); one object `SM_MoskovskySosh1200_Flora`, **44 615 tris of 70 000**; one atlas 2048
  (`T_MoskovskySosh1200_Flora_d_1` + `_o_1`, 9 tiles, scale 0.329), one material `M_MoskovskySosh1200_Flora_1`;
  FBX readback: 0 UV loops outside their cell. Note: `elka_t1_h400_low` and `mojevelnik_t2_h400_low` share the same
  48-tri mesh in A101 (identical bbox), only the texture differs.
- Open: FBX is not triangulated (polygons 32 951; triangulate at delivery, FLO-16); Ground v001 is being rebuilt
  (XY unchanged, z 0); no package.
