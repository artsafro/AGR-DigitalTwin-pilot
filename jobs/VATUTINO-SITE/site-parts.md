# Vatutino site parts list — MAF and Flora placement, gate 1 [D125] (#296)

Status: **gate 1 open — waiting for the user's answers** (questions at the end). Nothing is placed yet; no DCC run. `passed=false`.

## Sources

- SPOZU points: #195 adapter output for the master paving DWG (inventory Q7), `C:/x/t_d94665f2/paving_ground_inputs_v4.json`, sha256 `3b6b433d718c0292f472293849f3363fd2ae90d4892e598efca52be44cd9d502` (the same input as the #295 Ground v014). Boundary `568BF` (Q1). Counts = points with `inside=true`.
- Planting schedule: model-space `ACAD_TABLE` `*T3509` «Ведомость озеленения», read from the #313 table dump of the main DWG copy (`C:/x/vatutino-maf/v001/src/dump.json`, sha256 `1af8f3cd6f226781107288a0bb2f563f754abdb58f0f3bbbc28c6b51dee4054e`; DWG copy sha256 `64e22677…46e4`). The paving file's schedule was not re-read; its per-block counts equal the main file except Стефанандра (inventory).
- Flora library: `library/flora/catalogue.json` (schema `flora-library-v1`, file `C:/x/flora-library/v003/flora-library-v003.max`, 61 species, 15 shared stand-in gaps).
- MAF set: `jobs/VATUTINO-SITE/maf/site-maf-set.md` (#313, Q1–Q9 answered, «Принимаю» 2026-10-19). #296 places this set; it makes no new MAF choices.
- Ground: #295 v014 NPM 46 343 triangles (32 821 surface + details/skirt), `jobs/VATUTINO-SITE/ground-build-v014.md`.

## MAF ([D094]; picks by the user in #313 Q2–Q4)

| Schedule | Name | SPOZU block | Points in 568BF | Catalogue id (reason) | Spec L/W/H m | Library NPM L/W/H m | Verdict [D094] | NPM tris × n |
|---|---|---|---|---|---|---|---|---|
| *T3510/1 | Скамейка стальная «Андромеда» / Артикул: 14122 | `Скамья` | 5 (set: 5) | MAF_0326 (user pick, #313) | 1.800 / 0.500 / 0.720 | 1.802 / 0.474 / 0.801 | pass | 240 × 5 = 1200 |
| *T3510/2 | Урна стальная «Арго» / Артикул: 19648 | `Урна` | 48 (set: 48) | MAF_0794 (user pick, #313) | 0.620 / 0.470 / 1.050 | 0.643 / 0.475 / 1.064 | pass | 146 × 48 = 7008 |
| *T3510/7 | Скамейка «Фестиваль» Модуль 1 / арт. nv 521-01 | `Шезлонг фестиваль модуль 1` | 4 (set: 4) | MAF_0747 (user pick, #313) | 1.860 / 1.700 / 0.790 | 1.698 / 1.847 / 0.802 | pass | 364 × 4 = 1456 |
| *T3510/9 | Лежак «Городской» / 11061 | `лежак2` | 6 (set: 6) | MAF_0506 (user pick, #313) | 0.600 / 1.633 / 0.930 | 0.611 / 1.630 / 0.934 | pass | 730 × 6 = 4380 |
| *T3510/11 | Качалка балансир / Артикул: ИО 0410-2 | `Качалка на пружине ИО 0323Т-3` | 2 (set: 2) | MAF_0322 (user pick, #313) | 0.900 / 0.600 / 0.700 | 0.580 / 0.920 / 0.679 | pass | 434 × 2 = 868 |
| *T3510/12 | Качели / Артикул:Качели / ИО 0118Т-1 | `ио 0118т-1` | 2 (set: 2) | MAF_0920 (user pick, #313) | 2.200 / 0.300 / 1.900 | 2.158 / 0.267 / 1.897 | pass | 678 × 2 = 1356 |
| *T3510/16 | Детская площадка / Артикул: ДП 090 | `ДП 090` | 1 (set: 1) | MAF_0803 (user pick, #313) | 5.500 / 2.000 / 2.250 | 5.535 / 2.030 / 2.318 | pass | 2281 × 1 = 2281 |
| *T3510/26 | Теннисный стол Премиум / Артикул: 4-060 | `Теннисный стол` | 1 (set: 1) | MAF_0677 (user pick, #313) | 2.740 / 1.520 / 0.760 | 1.525 / 2.739 / 0.911 | pass | 3043 × 1 = 3043 |
| *T3510/27 | Комплект мебели «Ландау» / Артикул: 13994 | `Стол Ландау` | 3 (set: 3) | MAF_0219 (user pick, #313) | 2.280 / 2.280 / 0.750 | 2.282 / 2.282 / 0.749 | pass | 540 × 3 = 1620 |
| *T3510/28 | Качели-гнездо круг / 189.001 | `Подвес качели гнездо` | 4 (set: 4) | MAF_0127 (user pick, #313) | 1.090 / 1.090 / — | 1.708 / 1.999 / 2.387 | review | 2030 × 4 = 8120 |
| *T3510/29 | Кресло «Парк» / Артикул: 12750 | `Кресло Парк 12750` | 25 (set: 25) | MAF_0159 (user pick, #313) | 0.765 / 0.530 / 1.065 | 0.458 / 0.771 / 1.001 | pass | 320 × 25 = 8000 |
| *T3510/31 | Стол «Лондон» Тип 3 / Артикул: 13032 | `Стол Лондон Тип 3` | 16 (set: 16) | MAF_0722 (user pick, #313) | 1.000 / 1.000 / 0.600 | 1.000 / 1.000 / 0.600 | pass | 212 × 16 = 3392 |
| *T3510/32 | Приствольная решетка | `Приствольная решетка` | 4 (set: 4) | MAF_0687 (user pick, #313) | 1.000 / 1.000 / 0.044 | 1.000 / 1.000 / 0.048 | pass | 3726 × 4 = 14904 |

MAF to place: **13 types, 121 instances, NPM 57628 triangles** (share 60 000 [D097]).

MAF blocks inside 568BF without a library object (user answers #313 Q1/Q5: no model, modelling is a later card) — listed, not placed:

| SPOZU block | Points in 568BF |
|---|---|
| `Андромеда Металл Крыша поликарбонат` | 2 |
| `Барная стойка` | 1 |
| `Бетонные раскопки` | 8 |
| `Воркаут` | 1 |
| `Воркаут 217100` | 1 |
| `Воркаут 217170` | 1 |
| `Гамак` | 3 |
| `Игровой комплекс Кубики` | 1 |
| `Карусель` | 2 |
| `Качели парковые` | 11 |
| `Контейнер 1100л ТБО` | 8 |
| `Навес 1` | 1 |
| `Навес 2` | 1 |
| `Навес 3` | 1 |
| `Навес 4` | 1 |
| `Пенек` | 9 |
| `Песочница индивидуальный МАФ` | 1 |
| `Площадка для контейнеров БТО 2` | 1 |
| `Скамья верона` | 1 |
| `Скамья верона 2` | 1 |
| `Скамья индивид лестн 1` | 2 |
| `Скамья индивид общ отд 1` | 1 |
| `Скамья индивид общ отд 2` | 1 |
| `Скамья индивид пл. дети1-3лет` | 1 |
| `Скамья тетрис 03` | 4 |
| `Стул бар` | 4 |
| `Тренажер волна` | 1 |
| `Тренажер лыжи` | 1 |
| `Тренажер мышиная охота` | 1 |
| `Турник` | 1 |
| `Шезлонг фестиваль модуль 3` | 1 |
| `ио 1005т-11` | 1 |
| `скамья индивид под андромедой` | 1 |

Total not placed: 76 points (in-plot MAF points 197 = 121 placed + 76 no model).

## Flora ([D099] band = schedule height ±20 %; the schedule gives no crown diameter)

Proposed library object = the first candidate (agent proposal, **not a user pick**). `fail` = outside the height band; the number is the uniform scale that brings it to the band edge (model-flora step 4). VPM: catalogue `vpm_status`.

| Поз. | Schedule (RU / Latin) | Height cm → band m | Sched. qty | SPOZU in 568BF (total) | Exact catalogue entry | Candidates: id latin, h m, crown m, verdict, NPM/VPM tris, VPM | Proposed |
|---|---|---|---|---|---|---|---|
| 1 | Липа мелколистная Rancho / *Tilia cordata Greenspire* | 500–550 → 4.00–6.60 | 23 | 23 (25) | 122 Tilia cordata 'Greenspire': shared stand-in gap, no own mesh | 101 Tilia cordata, h 6.094, crown 4.227, pass, 357/830, available | 101 |
| 2 | Ольха серая / *Alnus glutinosa Laciniata* | 500–550 → 4.00–6.60 | 23 | 8 (24) | 123 Alnus incana: shared stand-in gap, no own mesh | **none** | question (no object) |
| 3 | Черемуха обыкновенная / *Prunus padus Watereri* | 300–550 → 2.40–6.60 | 11 | 11 (12) | — | 120 Prunus padus, h 4.411, crown 3.837, pass, 166/494, available | 120 |
| 4 | Яблоня Маковецкого / *Malus Makowieckiana* | 300–550 → 2.40–6.60 | 24 | 21 (25) | — | 115 Malus niedzwetzkyana, h 4.549, crown 3.859, pass, 125/394, available; 118 Malus 'Evereste', h 3.807, crown 3.276, pass, 394/—, unconfirmed | 115 |
| 5 | Лиственница обыкновенная / *Larix decidua Pendula* | 150–500 → 1.20–6.00 | 13 | 13 (14) | — | **none** | question (no object) |
| 6 | Ирга колосистая / *Amelanchier spicata* | 125–350 → 1.00–4.20 | 38 | 38 (39) | — | 105 Amelanchier lamarckii, h 1.553, crown 1.502, pass, 979/4894, available | 105 |
| 7 | Боярышник обыкновенный / *Crataegus laevigata Paul`s Scarlet* | 125–350 → 1.00–4.20 | 29 | 29 (30) | — | 103 Crataegus mollis, h 3.832, crown 4.676, pass, 488/574, available; 202 Crataegus monogyna, h 0.989, crown 1.405, fail (scale 1.011), 72/—, unconfirmed | 103 |
| 8 | Лох узколистный / *Elaeagnus angustifolia* | 125–350 → 1.00–4.20 | 25 | 25 (26) | — | **none** | question (no object) |
| 9 | Пузыреплодник калинолистный ‘Lady in red’ / *Physocarpus opulifolius ‘Lady in red’* | 125–200 → 1.00–2.40 | 191 | 191 (192) | — | 205 Physocarpus opulifolius 'Diabolo', h 0.990, crown 1.354, fail (scale 1.01), 18/144, available; 211 Physocarpus opulifolius, h 0.951, crown 0.920, fail (scale 1.052), 20/160, available; 234 Physocarpus opulifolius 'Luteus', h 1.524, crown 1.704, pass, 10/20, available | 205 |
| 10 | Дерен кроваво-красный / *Cornus sanguinea Anny Winter Orange* | 125–200 → 1.00–2.40 | 439 | 439 (440) | 228 Cornus sanguinea 'Anny's Winter Orange': shared stand-in gap, no own mesh | **none** | question (no object) |
| 11 | Рябинник рябинолистный / *Sorbaria sorbifolia* | 125–200 → 1.00–2.40 | 866 | 866 (876) | — | 212 Sorbaria sorbifolia, h 1.075, crown 1.459, pass, 10/84, available; 219 Sorbaria sorbifolia 'Sem', h 1.332, crown 1.889, pass, 112/—, unconfirmed | 212 |
| 12 | Дерен отпрысковыи 'Red Gnome' / *Cornus sericea 'Red Gnome'* | 125–200 → 1.00–2.40 | 325 | 325 (326) | 229 Cornus alba 'Red Gnome': shared stand-in gap, no own mesh | 204 Cornus sericea, h 0.972, crown 1.194, fail (scale 1.029), 80/—, unconfirmed; 203 Cornus alba, h 0.723, crown 1.120, fail (scale 1.383), 64/128, available | 204 |
| 13 | Облепиха крушиновидная / *Hippophae rhamnoides hikul* | 125–200 → 1.00–2.40 | 1059 | 1059 (1060) | — | **none** | question (no object) |
| 14 | Лапчатка кустарниковая / *Potentila fruticosa* | 80–100 → 0.64–1.20 | 558 | 558 (559) | — | 230 Dasiphora fruticosa, h 0.835, crown 1.133, pass, 10/20, available; 213 Dasiphora fruticosa 'Goldfinger', h 1.332, crown 1.889, fail (scale 0.901), 112/—, unconfirmed | 230 |
| 15 | Стефанандры надрезаннолистная / *Stephanandra incisa* | 20–60 → 0.16–0.72 | 1002 | 1002 (1003) | — | 223 Stephanandra incisa 'Crispa', h 0.724, crown 1.967, fail (scale 0.994), 10/90, available | 223 |
| 16 | Ель нидиформис / *Picea abies Nidiformis* | 60–100 → 0.48–1.20 | 70 | 70 (71) | 236 Picea abies 'Nidiformis': shared stand-in gap, no own mesh | **none** | question (no object) |
| 17 | Сосна горная ф. Мугус / *Pinus mugo var. Mughus* | 60–100 → 0.48–1.20 | 99 | 106 (107) | 237 Pinus mugo var. mughus: shared stand-in gap, no own mesh | 224 Pinus mugo, h 0.618, crown 1.284, pass, 10/64, available | 224 |
| — | not in the schedule: `Ива швейцарская (Salix helvetica) К` | — | — | 131 (131) | none | none (208 Salix purpurea, 231 Salix repens gap) | question |

With the proposed objects: 3170 plants placed, NPM **118774** triangles; not placed (no library object): 1614 plants of positions 2, 5, 8, 10, 13, 16 + 131 Ива.

Count differences (SPOZU in plot vs schedule): Поз. 2 Ольха 8 vs 23 (15 outside 568BF), Поз. 4 Яблоня 21 vs 24 (3 outside), Поз. 17 Сосна горная 106 vs 99 (+7). All other positions equal. The one extra point per block outside the plot is the schedule legend sample.

Source notes: Поз. 1 Russian «Rancho» vs Latin/block «Greenspire»; Поз. 2 Russian «Ольха серая» (*Alnus incana*) vs Latin *Alnus glutinosa*; Поз. 12 schedule «Дерен отпрысковый» *Cornus sericea* vs block «Дерен белый»; Поз. 7 schedule «обыкновенный» vs block «средний».

## Flower beds and lawn ([D101], FLO-01/FLO-02)

| Row | Wording | Verdict | Decided by |
|---|---|---|---|
| `укрепленный цветник 01–08` (8 layers, 69.03 m² in 29 parts) | legend «Цветник»; not in `*T3509` | Ground texture, one FlowerBed material, no Flora | user, inventory Q8 (quoted below) |
| `*T3509` 18 Газон универсальный рулонный | area 1326,29 m² | Ground texture | FLO-01 (lawn rows are Ground) |
| `*T3509` 19 Мульча | area 3646,97 m² | Ground texture | FLO-01 (lawn rows are Ground) |
| `*T3509` 20 Газон укрепленный | area 2460,11 m² | Ground texture | FLO-01 (lawn rows are Ground) |

Q8 answer, Artem 2026-10-19 (PR #308 «Gate 1 answers»): "8. Flower beds: Ground texture, ONE FlowerBed material, not Flora."

## Budget [D097] (NPM, before placement)

| Part | Share | Planned | Note |
|---|---|---|---|
| Ground surface (#295 v014) | 50 000 | 46 343 | 32 821 surface + details/skirt |
| MAF | 60 000 | 57628 | 121 instances |
| Flora | 70 000 | 118774 | proposed objects; 1745 plants not counted |
| **Total** | 180 000 | 222745 | Flora room left after Ground + MAF: 76029 |

Largest Flora contributors: Поз. 6 id 105 979 × 38 = 37202; Поз. 12 id 204 80 × 325 = 26000; Поз. 7 id 103 488 × 29 = 14152; Поз. 15 id 223 10 × 1002 = 10020.

## Questions for the user (gate 1 stops here)

- **Q2a**: Planting outside the plot (inventory Q2): 15 Ольха (Поз. 2) and 3 Яблоня (Поз. 4) stand outside 568BF, where there is no Ground. Proposal: do not place them, list them in the report (the engine would fail them as `point_outside_ground`).
- **Q2b**: Сосна горная (Поз. 17): 106 points in the plot vs 99 in the schedule. Proposal: one plant per point (106), the +7 listed.
- **F1**: Positions with no library object — 2 Ольха (8), 5 Лиственница (13), 8 Лох (25), 10 Дерен кроваво-красный (439), 13 Облепиха (1059), 16 Ель нидиформис (70) = 1614 plants, plus 131 `Ива швейцарская` (block not in the schedule). The catalogue has only shared FLORIO stand-in gaps for 2/10/16 and nothing for 5/8/13/Ива. Proposal: leave them unplaced and listed as questions (modelling is model-flora step 5-7, a separate card). Or should a named stand-in be used?
- **F2**: Proxy picks (species or cultivar differs from the schedule): 1→101 Tilia cordata; 3→120 Prunus padus; 4→115 Malus niedzwetzkyana (or 118 'Evereste', VPM unconfirmed); 6→105 Amelanchier lamarckii; 7→103 Crataegus mollis (tree 3.8 m; 202 monogyna 0.99 m fails the band); 9→205 'Diabolo' (red leaves, scale 1.01; 234 'Luteus' is yellow); 11→212 Sorbaria sorbifolia (exact); 12→204 Cornus sericea (scale 1.03, VPM unconfirmed; 203 Cornus alba needs scale 1.38); 14→230 Dasiphora fruticosa (exact); 15→223 Stephanandra incisa 'Crispa' (scale 0.994); 17→224 Pinus mugo. Accept, or name another id per position?
- **F3**: The schedule has no crown diameter: check height only ±20 % and record crown as `review`?
- **F4**: Budget [D097]: with these picks Flora NPM = 118774 > 70 000 (Ground 46 343 + MAF 57628 leave 76029). Main load: 105 Ирга 979 tris × 38 = 37 202, 204 Дерен 80 × 325 = 26 000, 103 Боярышник 488 × 29 = 14 152. Options: (a) place as is and report the overrun for this slice, (b) lighter library variants (name them), (c) a lighter NPM for these species later (out of this card).

Answered earlier and only applied here: inventory Q1 (boundary 568BF), Q7 (paving file is master), Q8 (flower beds = Ground texture) — PR #308; MAF Q1–Q9 — #313 `site-maf-map.md`.

