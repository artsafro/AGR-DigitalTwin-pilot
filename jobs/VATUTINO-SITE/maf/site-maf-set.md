# Vatutino site MAF set (#313) — v005-set

Status: **technical QA only, `passed=false`** (visual review lines open). Built from `site-maf-map` (Q1–Q9 answered). #296 reads this file instead of the raw library. Files are outside git under `C:/x/vatutino-maf/v005-set`.

Route: Blender 5.1.2 headless `--factory-startup`; build `tools/blender/maf_site_set_build.py` (config `site-maf-set.config.json`), readback `tools/blender/fbx_readback.py`, checks `twinqa.maf_checks.maf_findings`, rules `tools/library/maf_site_set.py`. Commands and exit codes are in the JSON.

## Set (13 positions)

| Set id | Source | Schedule | SPOZU block × count | NPM route | Tris raw / NPM / VPM | Measured NPM L/W/H m | Schedule L/W/H m | Dev m | Verdict | Atlas materials | Smooth ° |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VAT_MAF_T3510_01 | MAF_0326 | *T3510/1 | Скамья × 5 | npm_matches (as is) | 240 / 240 / 240 | 1.802 / 0.474 / 0.801 | 1.800 / 0.500 / 0.720 | 0.002 / 0.026 / 0.081 | pass | larch_light_oak, steel_ral7047 | 40 |
| VAT_MAF_T3510_02 | MAF_0794 | *T3510/2 | Урна × 48 | raw kept | 146 / 146 / 146 | 0.643 / 0.475 / 1.064 | 0.620 / 0.470 / 1.050 | 0.024 / 0.005 / 0.014 | pass | steel_ral7047 | 40 |
| VAT_MAF_T3510_07 | MAF_0747 | *T3510/7 | Шезлонг фестиваль модуль 1 × 4 | npm_matches (as is) | 364 / 364 / 364 | 1.847 / 1.698 / 0.802 | 1.860 / 1.700 / 0.790 | 0.013 / 0.002 / 0.012 | pass | larch_light_oak | 40 |
| VAT_MAF_T3510_09 | MAF_0506 | *T3510/9 | лежак2 × 6 | Decimate 0.5 | 1460 / 730 / 1460 | 0.611 / 1.630 / 0.934 | 0.600 / 1.633 / 0.930 | 0.011 / 0.003 / 0.004 | pass | larch_light_oak, steel_ral7047 | 40 |
| VAT_MAF_T3510_11 | MAF_0322 | *T3510/11 | Качалка на пружине ИО 0323Т-3 × 2 | Decimate 0.6 | 724 / 434 / 724 | 0.920 / 0.580 / 0.679 | 0.900 / 0.600 / 0.700 | 0.020 / 0.020 / 0.021 | pass | larch_light_oak, steel_ral7047 | 40 |
| VAT_MAF_T3510_12 | MAF_0920 | *T3510/12 | ио 0118т-1 × 2 | raw kept | 678 / 678 / 678 | 2.158 / 0.267 / 1.897 | 2.200 / 0.300 / 1.900 | 0.042 / 0.033 / 0.003 | pass | steel_ral7047 | 40 |
| VAT_MAF_T3510_16 | MAF_0803 | *T3510/16 | ДП 090 × 1 | Decimate 0.5 | 4562 / 2281 / 4562 | 5.535 / 2.030 / 2.318 | 5.500 / 2.000 / 2.250 | 0.035 / 0.030 / 0.068 | pass | larch_light_oak | 40 |
| VAT_MAF_T3510_26 | MAF_0677 | *T3510/26 | Теннисный стол × 1 | Decimate 0.35 | 8696 / 3043 / 8696 | 2.739 / 1.525 / 0.761 (top) | 2.740 / 1.520 / 0.760 | 0.002 / 0.005 / 0.001 | pass | hpl_satin_wood, steel_ral7047 | 40 |
| VAT_MAF_T3510_27 | MAF_0219 | *T3510/27 | Стол Ландау × 3 | npm_matches (as is) | 540 / 540 / 540 | 2.282 / 2.282 / 0.749 | 2.280 / 2.280 / 0.750 | 0.002 / 0.002 / 0.001 | pass | larch_light_oak, steel_ral7047 | 40 |
| VAT_MAF_T3510_28 | MAF_0127 | *T3510/28 | Подвес качели гнездо × 4 | npm_matches (as is) | 2030 / 2030 / 2030 | 1.708 / 1.999 / 2.387 | 1.090 / 1.090 / — | 0.618 / 0.909 / — | review | rope_pp, steel_ral7047 | 40 |
| VAT_MAF_T3510_29 | MAF_0159 | *T3510/29 | Кресло Парк 12750 × 25 | raw kept | 320 / 320 / 320 | 0.771 / 0.458 / 1.001 | 0.765 / 0.530 / 1.065 | 0.006 / 0.072 / 0.064 | pass | larch_light_oak | 40 |
| VAT_MAF_T3510_31 | MAF_0722 | *T3510/31 | Стол Лондон Тип 3 × 16 | raw kept | 212 / 212 / 212 | 1.000 / 1.000 / 0.600 | 1.000 / 1.000 / 0.600 | 0.000 / 0.000 / 0.000 | pass | larch_light_oak | 40 |
| VAT_MAF_T3510_32 | MAF_0687 | *T3510/32 | Приствольная решетка × 4 | npm_matches (as is) | 3732 / 3726 / 3726 | 1.000 / 1.000 / 0.048 | 1.000 / 1.000 / 0.044 | 0.000 / 0.000 / 0.004 | pass | steel_ral7047 | 40 |

Row 26: height is the table-top plane (Q4: 760 mm = table top), measured as the largest upward horizontal plane above the model bottom; overall height with the net is in the JSON. Row 28: `review` = user exception Q8, never `pass`. VPM dimensions: {'pass': 12, 'review': 1}.

## Budget [D097], MAF-07 / MAF-08

| Set id | × | Raw | NPM | VPM | NPM total | VPM total |
|---|---|---|---|---|---|---|
| VAT_MAF_T3510_01 | 5 | 240 | 240 | 240 | 1200 | 1200 |
| VAT_MAF_T3510_02 | 48 | 146 | 146 | 146 | 7008 | 7008 |
| VAT_MAF_T3510_07 | 4 | 364 | 364 | 364 | 1456 | 1456 |
| VAT_MAF_T3510_09 | 6 | 1460 | 730 | 1460 | 4380 | 8760 |
| VAT_MAF_T3510_11 | 2 | 724 | 434 | 724 | 868 | 1448 |
| VAT_MAF_T3510_12 | 2 | 678 | 678 | 678 | 1356 | 1356 |
| VAT_MAF_T3510_16 | 1 | 4562 | 2281 | 4562 | 2281 | 4562 |
| VAT_MAF_T3510_26 | 1 | 8696 | 3043 | 8696 | 3043 | 8696 |
| VAT_MAF_T3510_27 | 3 | 540 | 540 | 540 | 1620 | 1620 |
| VAT_MAF_T3510_28 | 4 | 2030 | 2030 | 2030 | 8120 | 8120 |
| VAT_MAF_T3510_29 | 25 | 320 | 320 | 320 | 8000 | 8000 |
| VAT_MAF_T3510_31 | 16 | 212 | 212 | 212 | 3392 | 3392 |
| VAT_MAF_T3510_32 | 4 | 3732 | 3726 | 3726 | 14904 | 14904 |
| **Total** | 121 | raw 70546 | | | **57628** | **70522** |

NPM MAF total 57628 ≤ 60 000 (MAF share of the shared 180 000 NPM Ground budget): within, no overrun. Light versions only where the library has no `npm_matches`: rows 09 (0.5), 11 (0.6), 16 (0.5), 26 (0.35). VPM Ground limit is area-dependent (reg p.28-29): plot 568BF = 25 854 m2 = 2.585 ha before subtracting the building footprint (not measured here); if (site - footprint) > 1.5 ha the Ground limit is 4 500 000 and the MAF VPM total is 1.6 % of it. Verdict: review (footprint subtraction is #298 site assembly).

## Atlas (one 512 RGB set, MAF-09, [D020])

`C:/x/vatutino-maf/v005-set/atlas/vatutino_maf_atlas_512.png` 512×512 RGB, sha256 `5aaf8b55d2ed08d74a02b9239bc4d76399c428b16e2c74d537f335f51ca9b87a`.

| Material | Colour | Slot px | Reason |
|---|---|---|---|
| steel_ral7047 | #D0D0D0 | [0, 0, 64, 64] | schedule: steel, powder coat RAL 7047 (Telegrey 4, #D0D0D0; RAL 7047 missing from tools/materials/ral_classic.json) |
| larch_light_oak | #C49A6C | [64, 0, 64, 64] | schedule: larch, oil + lacquer 'light oak'; solid colour (no texture source), visual review |
| hpl_satin_wood | #B4825A | [0, 64, 64, 64] | schedule *T3510/26: HPL 'satin wood'; solid colour, visual review |
| rope_pp | #7A7A7A | [64, 64, 64, 64] | schedule *T3510/28: polypropylene rope, colour not given -> review |

UV-slot measurement on the exported FBX readback: 38442 faces in 26 files, faces outside their material's slot = **0** (per-material UV bounds in the JSON).

Material-map coverage (review round 1): the builder now rejects, before any export (exit 3), a source material that has no mapping and no explicit `"*"`. All 13 maps are covered: 6 positions map every sub-material by name, 7 single-material positions (02, 07, 12, 16, 29, 31, 32) use an explicit `"*"` on purpose. A re-run of the fixed builder on the same copies (`C:/x/vatutino-maf/v006-check`, exit 0) gives the same readback as v005 for all 26 files: triangles, size, faces and UV bounds per material, flips and flat-shaded counts. FBX bytes differ between any two runs, the old builder included (`v006-oldbuilder`), so the published v005 files are kept; their hashes were checked again, 27/27 match.

## L2 MAF checks (`maf_findings`, smoothing threshold 40°)

NPM: {'pass': 25, 'not_run': 1}; VPM: {'pass': 25, 'not_run': 1}. The one `not_run` per profile is VAT_MAF_T3510_32 «MAF flipped normals»: listed **review** — flat grate plates (44 mm open sheets), 5 flat components without measurable volume; 0 flipped, 0 inconsistent. Faces reversed to outward (copy only) and faces flat-shaded to keep hard edges are counted per position in the JSON.

## Gaps (37, not in the set)

| Schedule | Name | Status |
|---|---|---|
| *T3508/1 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/2 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/3 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/4 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/5 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/6 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/7 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/8 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/9 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/10 | Скамья индивидуального изготовления на основе Скамейка стальная «Верона» / Артик | no model |
| *T3508/11 | Барная стойка | no model |
| *T3508/12 | Перучень для МГН | not a MAF item |
| *T3508/13 | Навес "Андромеда" Тип 1 | no model |
| *T3508/14 | Навес "Андромеда" Тип 2 | no model |
| *T3508/15 | Навес "Андромеда" Тип 3 | no model |
| *T3508/16 | Навес "Андромеда" Тип 4 | no model |
| *T3508/17 | Песочница с повышением , подпорной стенкой и пандусом / Индивидуального изготовл | no model |
| *T3510/3 | Качели садово-парковые «Кассиопея» / Артикул: 20895 | no model |
| *T3510/4 | Гамак HARDWOOD «Сен-Тропе» / Артикул: 25308 | no model |
| *T3510/5 | Площадка для контейнеров ТБО | no model |
| *T3510/6 | Контейнер пластиковый ТБО | no model |
| *T3510/8 | Скамейка «Фестиваль» Модуль 3 / арт. nv 521-03 | no model |
| *T3510/10 | Стул на ножке "Бар" | no model |
| *T3510/13 | Игра с песком / Артикул: ИО 1005Т-11 | no model |
| *T3510/14 | Игровой комплекс / Артикул: ИК 0408Т-23 | no model |
| *T3510/15 | Бетонные раскопки / Артикул:  / ИО 0860Т-1-5 | no model |
| *T3510/17 | Вертушка / Артикул: ИО 0208Т-1 | no model |
| *T3510/18 | Пенёк / ИО 0906Т-7 | no model |
| *T3510/19 | Пергола «Андромеда» с поликарбонатом и обшивкой / Артикул: 40146-2/1 | no model |
| *T3510/20 | Спортивное оборудование / Артикул: 217170 | no model |
| *T3510/21 | Спортивное оборудование / Артикул: 217070 | no model |
| *T3510/22 | Тренажер Wotkout nature 217100 | no model |
| *T3510/23 | Тренажер 'Лыжи' | no model |
| *T3510/24 | Тренажер 'Волна' | no model |
| *T3510/25 | Тренажер 'Мышиная охота' | no model |
| *T3510/30 | Скамья тетрис 03 / Артикул: С-Т03 | no model |
| plan block «Турник» (no row) | Турник | no model |

## Verify lines for the user

- material layout per sub-material (geometry-based assumption, see material_reason) - visual review
- larch/HPL as solid colours (no wood texture source) - visual review
- light versions (Decimate) rows 09, 11, 16, 26: silhouette - visual review
- row 28 dimension exception Q8 (architect question D112)
- row 32 orientation undetermined on flat plates - visual review

## Hashes

Sources: sha256 before = after = copy for 13/13 (full values in the JSON). Produced FBX:

- VAT_MAF_T3510_01: NPM `51cdd9ebf9e25d8ba24a8acebb0ddd5dad0a5f6d867d0bdf2b025e4c620e60f1`, VPM `f4fcf71a13d318fe2dcfdceb4724cded586cde7ab169996129547bdbbded1f6f`
- VAT_MAF_T3510_02: NPM `3d1633c3b8bff07143056769a7bac362bc75a0d8d3642586f12a889583ca3376`, VPM `1e94baf0ea41de50fc735247de412e3999e0409278d9674457c31d880733bead`
- VAT_MAF_T3510_07: NPM `e998bce3af146f0c6c17d28c0252f57d809ebd20354a45bf66c0d6dc8a25f45f`, VPM `81e4b7b278d7bafbe961902f93fff5d28daf493e39230c1eee083e43bdd509dc`
- VAT_MAF_T3510_09: NPM `76676dfccc4c7007485fdb5f481c41661c69ef572ee523766a92587acfa6ee3b`, VPM `6a848d79ea333cee898ff70f11f61ac562915d72f7bc01a57303816a6fa05a2d`
- VAT_MAF_T3510_11: NPM `294dafbc3d49e25b8317784ee4a2c8be713cc5a9d96d63cba2b1d589e5401419`, VPM `6915cce13b73615997a2f7c202533645b278fff716f2f71e1b4b0ee319c6a0dd`
- VAT_MAF_T3510_12: NPM `f8c81dac007dffc07f27aba822be19ce6d20a42bb891b29e0c9063f7658a0bcc`, VPM `01807e36072a509ece1b48f52faefb45738e6be66430c096f9731f72e2544a66`
- VAT_MAF_T3510_16: NPM `d8d97d1727f55633b50407747871c145ebb170bd30f576476b0b6397b6cfdead`, VPM `ace54c1e86052140303a13cb75d285c2fb635c1441eb4bbea175c399c0cebbb0`
- VAT_MAF_T3510_26: NPM `069365a04644cd9c46c874a179ade58c846798e253506852c2d81ff14ccbcff8`, VPM `e85303515c3e38de619dbb9e5ce990ef43eb1a9deea67fc8ec1b36e7e8a8b147`
- VAT_MAF_T3510_27: NPM `da045d22e456418c30e425a835de2136d24d22e2d0d85181588692035394f913`, VPM `61f9d62388c8ff2234fcf889703c22dc3961941a9cc79293cb6ec2fc73790785`
- VAT_MAF_T3510_28: NPM `1b615fb94b8a7840b68da70f3c8e2bb07b10b57c79bb504d6c39ce9b7ba75743`, VPM `68d0528655b227cd6a1af0b9b9696fe912c925900e44ab0cde28eea771a7071b`
- VAT_MAF_T3510_29: NPM `4850474bc24a565c200b945cdfb8fa58167d1cfd40806df5d325519ffc0b4ad0`, VPM `8fce0255153b13a803ec86c4a7f9b80b2680255b303d56464383c532e029c96e`
- VAT_MAF_T3510_31: NPM `805c25844f1d671e3cbc0facf6c83431bda9cb6b9b9f7ca1dc89b2c23c842bf6`, VPM `084480b9e85d827b0c9e1700c9cd858ab139845a7b54b5c65af5c12df4b28761`
- VAT_MAF_T3510_32: NPM `4529dc5ef08666020ac75b26dfcf484b0a11b8c81aa135c7ec5578e51f6664b2`, VPM `0e51b957e24f873bd38059beb0b8cb470bfc6f62451e30de326c483693acd00c`
