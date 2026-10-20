# Vatutino site slice: MAF + Flora placement report (#296)

Status: **technical QA; user geometry acceptance open**, `passed=false` [D104]. Seed **296**. Engine `dt_ai.placement` (#316) computed every instance; Blender instancing equals it (`scene_mismatches` = 0 per variant).
Machine-readable: `placement-report.json`. Scenes (not in git): `C:\x\t_5e4ea2be\run_v005\npm\VATUTINO-SITE_placement_npm_v001.blend` sha256 `d4104d1d3f7e638c…`, `C:\x\t_5e4ea2be\run_v005\vpm\VATUTINO-SITE_placement_vpm_v001.blend` sha256 `7c689149b4a58d2e…`

## NPM

Engine review; totals {'failed': 0, 'input': 3289, 'placed': 3289}; scene mismatches 0; sinking measured in the scene at every pivot (3289/3289): flora 3170: 0.0998–0.1001 m; maf 119: 0.1000–0.1000 m (10 cm ± 1 cm: ok).
Bottom faces: deleted 1933, kept as `review` 7, exposed on slopes 0.

### MAF

| schedule | block | library | catalogue | SPOZU in 568BF | placed | tris/inst placed (library) | tris total placed |
|---|---|---|---|---|---|---|---|
| *T3510/1 | Скамья | VAT_MAF_T3510_01 | MAF_0326 | 5 | 5 | 232 (240) | 1160 |
| *T3510/2 | Урна | VAT_MAF_T3510_02 | MAF_0794 | 48 | 46 | 146 (146) | 6716 |
| *T3510/7 | Шезлонг фестиваль модуль 1 | VAT_MAF_T3510_07 | MAF_0747 | 4 | 4 | 364 (364) | 1456 |
| *T3510/9 | лежак2 | VAT_MAF_T3510_09 | MAF_0506 | 6 | 6 | 692 (730) | 4152 |
| *T3510/11 | Качалка на пружине ИО 0323Т-3 | VAT_MAF_T3510_11 | MAF_0322 | 2 | 2 | 434 (434) | 868 |
| *T3510/12 | ио 0118т-1 | VAT_MAF_T3510_12 | MAF_0920 | 2 | 2 | 678 (678) | 1356 |
| *T3510/16 | ДП 090 | VAT_MAF_T3510_16 | MAF_0803 | 1 | 1 | 2281 (2281) | 2281 |
| *T3510/26 | Теннисный стол | VAT_MAF_T3510_26 | MAF_0677 | 1 | 1 | 3037 (3043) | 3037 |
| *T3510/27 | Стол Ландау | VAT_MAF_T3510_27 | MAF_0219 | 3 | 3 | 524 (540) | 1572 |
| *T3510/28 | Подвес качели гнездо | VAT_MAF_T3510_28 | MAF_0127 | 4 | 4 | 2030 (2030) | 8120 |
| *T3510/29 | Кресло Парк 12750 | VAT_MAF_T3510_29 | MAF_0159 | 25 | 25 | 318 (320) | 7950 |
| *T3510/31 | Стол Лондон Тип 3 | VAT_MAF_T3510_31 | MAF_0722 | 16 | 16 | 208–212 (212) | 3335 |
| *T3510/32 | Приствольная решетка | VAT_MAF_T3510_32 | MAF_0687 | 4 | 4 | 3350 (3726) | 13400 |

### Flora

| pos | schedule (ru / latin) | library object | match | scheduled | SPOZU all / in | placed | base scale | tris/inst placed (library) | tris total placed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Липа мелколистная Rancho / *Tilia cordata Greenspire* | 101 Tilia_cordata_NPM | substitute | 23 | 25 / 23 | 23 | 1.0000 | 357 (357) | 8211 |
| 3 | Черемуха обыкновенная / *Prunus padus Watereri* | 120 Prunus_padus_NPM | substitute | 11 | 12 / 11 | 11 | 1.0000 | 166 (166) | 1826 |
| 4 | Яблоня Маковецкого / *Malus Makowieckiana* | 115 Malus_niedzwetzkyana_NPM | substitute | 24 | 25 / 21 | 21 | 1.0000 | 125 (125) | 2625 |
| 6 | Ирга колосистая / *Amelanchier spicata* | 105 Amelanchier_lamarckii_NPM | substitute | 38 | 39 / 38 | 38 | 1.0000 | 979 (979) | 37202 |
| 7 | Боярышник обыкновенный / *Crataegus laevigata Paul`s Scarlet* | 103 Crataegus_mollis_NPM | substitute | 29 | 30 / 29 | 29 | 1.0000 | 488 (488) | 14152 |
| 9 | Пузыреплодник калинолистный ‘Lady in red’ / *Physocarpus opulifolius ‘Lady in red’* | 205 Physocarpus_opulifolius_Diabolo_NPM | substitute | 191 | 192 / 191 | 191 | 1.0106 | 18 (18) | 3438 |
| 11 | Рябинник рябинолистный / *Sorbaria sorbifolia* | 212 Sorbaria_sorbifolia_NPM | exact | 866 | 876 / 866 | 866 | 1.0000 | 10 (10) | 8660 |
| 12 | Дерен отпрысковыи 'Red Gnome' / *Cornus sericea 'Red Gnome'* | 204 Cornus_sericea_NPM | substitute | 325 | 326 / 325 | 325 | 1.0284 | 80 (80) | 26000 |
| 14 | Лапчатка кустарниковая / *Potentila fruticosa* | 230 Dasiphora_fruticosa_NPM | exact | 558 | 559 / 558 | 558 | 1.0000 | 10 (10) | 5580 |
| 15 | Стефанандры надрезаннолистная / *Stephanandra incisa* | 223 Stephanandra_incisa_Crispa_NPM | exact | 1002 | 1003 / 1002 | 1002 | 0.9947 | 10 (10) | 10020 |
| 17 | Сосна горная ф. Мугус / *Pinus mugo var. Mughus* | 224 Pinus_mugo_NPM | substitute | 99 | 107 / 106 | 106 | 1.0000 | 10 (10) | 1060 |

Crown diameter: `review` for every species (not in the schedule, gate-1 F3).

### Not placed (points, reason)

| label | reason | points |
|---|---|---|
| Андромеда Металл Крыша поликарбонат | no_library_model | 2 |
| Барная стойка | no_library_model | 1 |
| Бетонные раскопки | no_library_model | 8 |
| Боярышник средний  'Paul's Scarlet' | outside_boundary | 1 |
| Воркаут | no_library_model | 1 |
| Воркаут 217100 | no_library_model | 1 |
| Воркаут 217170 | no_library_model | 1 |
| Гамак | no_library_model | 3 |
| ДП 090 | outside_boundary | 1 |
| Дерен белый 'Red Gnome' | outside_boundary | 1 |
| Дерен кроваво-красный (Cornus sanguinea) ‘Anny’s Winter Orange’ | no_library_model | 439 |
| Дерен кроваво-красный (Cornus sanguinea) ‘Anny’s Winter Orange’ | outside_boundary | 1 |
| Ель нидиформис | no_library_model | 70 |
| Ель нидиформис | outside_boundary | 1 |
| Ива швейцарская (Salix helvetica) К | no_library_model | 131 |
| Игровой комплекс Кубики | no_library_model | 1 |
| Ирга колосистая | outside_boundary | 1 |
| Карусель | no_library_model | 2 |
| Качели парковые | no_library_model | 11 |
| Контейнер 1100л ТБО | no_library_model | 8 |
| Контейнер 1100л ТБО | outside_boundary | 10 |
| Кресло Парк 12750 | outside_boundary | 2 |
| Лапчатка кустарниковая (Dasiphora fruticosa) К | outside_boundary | 1 |
| Липа мелколистная 'Greenspire' | outside_boundary | 2 |
| Лиственница обыкновенная 'Pendula' | no_library_model | 13 |
| Лиственница обыкновенная 'Pendula' | outside_boundary | 1 |
| Лох узколистный | no_library_model | 25 |
| Лох узколистный | outside_boundary | 1 |
| Навес 1 | no_library_model | 1 |
| Навес 1 | outside_boundary | 1 |
| Навес 2 | no_library_model | 1 |
| Навес 2 | outside_boundary | 1 |
| Навес 3 | no_library_model | 1 |
| Навес 3 | outside_boundary | 1 |
| Навес 4 | no_library_model | 1 |
| Навес 4 | outside_boundary | 1 |
| Облепиха крушиновидная ‘Hikul’ | no_library_model | 1059 |
| Облепиха крушиновидная ‘Hikul’ | outside_boundary | 1 |
| Ольха серая 'Laciniata' | no_library_model | 8 |
| Ольха серая 'Laciniata' | outside_boundary | 16 |
| Пенек | no_library_model | 9 |
| Пенек | outside_boundary | 3 |
| Песочница индивидуальный МАФ | no_library_model | 1 |
| Площадка для контейнеров БТО 2 | no_library_model | 1 |
| Площадка для контейнеров ТБО | outside_boundary | 1 |
| Пузыреплодник калинолистный (Physocarpus opulifolius) ‘Lady in red’ | outside_boundary | 1 |
| Рябинник рябинолистный | outside_boundary | 10 |
| Скамья верона | no_library_model | 1 |
| Скамья верона | outside_boundary | 1 |
| Скамья верона 2 | no_library_model | 1 |
| Скамья верона 2 | outside_boundary | 1 |
| Скамья индивид лестн 1 | no_library_model | 2 |
| Скамья индивид лестн 1 | outside_boundary | 3 |
| Скамья индивид общ отд 1 | no_library_model | 1 |
| Скамья индивид общ отд 1 | outside_boundary | 1 |
| Скамья индивид общ отд 2 | no_library_model | 1 |
| Скамья индивид общ отд 2 | outside_boundary | 1 |
| Скамья индивид пл. дети1-3лет | no_library_model | 1 |
| Скамья индивид пл. дети1-3лет | outside_boundary | 1 |
| Скамья тетрис 03 | no_library_model | 4 |
| Сосна горная ф. Мугус | outside_boundary | 1 |
| Стефанандра надрезаннолистная Crispa (Stephanandra incisa Crispa) | outside_boundary | 1 |
| Стол Лондон Тип 3 | outside_boundary | 1 |
| Стул бар | no_library_model | 4 |
| Тренажер волна | no_library_model | 1 |
| Тренажер лыжи | no_library_model | 1 |
| Тренажер мышиная охота | no_library_model | 1 |
| Турник | no_library_model | 1 |
| Урна | ground_exception | 2 |
| Урна | outside_boundary | 1 |
| Черемуха обыкновенная 'Watereri' | outside_boundary | 1 |
| Шезлонг фестиваль модуль 3 | no_library_model | 1 |
| Яблоня 'Makowieckiana' | outside_boundary | 4 |
| ио 1005т-11 | no_library_model | 1 |
| скамья индивид под андромедой | no_library_model | 1 |
| скамья индивид под андромедой | outside_boundary | 1 |

Excluded by a user-approved Ground exception (bound to this Ground master; a repaired Ground places them again):

| handle | label | library | reason | Ground master sha256 | approved |
|---|---|---|---|---|---|
| 15E288 | Урна | VAT_MAF_T3510_02 | Урна inside 568BF but ~1 cm outside the edge of a Ground v014 cut-out (border bbox x -7680.43..-7675.91, y -15352..-15336); engine finding point_outside_ground (run_v003). Ground defect reported to #295. | `f1a03db9d7b2293db50817f8cb7c0c021d25737ff0c2f9ea984e47192b1979bb` | Artem 2026-10-20: "option a: the 2 urns 15E288/15E289 (VAT_MAF_T3510_02), ~1 cm outside the Ground v014 cut-out edge, are NOT placed for this run; list them in the placement report with the reason and the Ground v014 sha256. The exclusion is bound to Ground v014 only: a corrected Ground places them again." |
| 15E289 | Урна | VAT_MAF_T3510_02 | Урна inside 568BF but ~1 cm outside the edge of a Ground v014 cut-out (border bbox x -7680.43..-7675.91, y -15352..-15336); engine finding point_outside_ground (run_v003). Ground defect reported to #295. | `f1a03db9d7b2293db50817f8cb7c0c021d25737ff0c2f9ea984e47192b1979bb` | Artem 2026-10-20: "option a: the 2 urns 15E288/15E289 (VAT_MAF_T3510_02), ~1 cm outside the Ground v014 cut-out edge, are NOT placed for this run; list them in the placement report with the reason and the Ground v014 sha256. The exclusion is bound to Ground v014 only: a corrected Ground places them again." |

## VPM

Engine review; totals {'failed': 0, 'input': 2964, 'placed': 2964}; scene mismatches 0; sinking measured in the scene at every pivot (2964/2964): flora 2845: 0.0998–0.1001 m; maf 119: 0.1000–0.1000 m (10 cm ± 1 cm: ok).
Bottom faces: deleted 2499, kept as `review` 7, exposed on slopes 0.

### MAF

| schedule | block | library | catalogue | SPOZU in 568BF | placed | tris/inst placed (library) | tris total placed |
|---|---|---|---|---|---|---|---|
| *T3510/1 | Скамья | VAT_MAF_T3510_01 | MAF_0326 | 5 | 5 | 232 (240) | 1160 |
| *T3510/2 | Урна | VAT_MAF_T3510_02 | MAF_0794 | 48 | 46 | 146 (146) | 6716 |
| *T3510/7 | Шезлонг фестиваль модуль 1 | VAT_MAF_T3510_07 | MAF_0747 | 4 | 4 | 364 (364) | 1456 |
| *T3510/9 | лежак2 | VAT_MAF_T3510_09 | MAF_0506 | 6 | 6 | 1340 (1460) | 8040 |
| *T3510/11 | Качалка на пружине ИО 0323Т-3 | VAT_MAF_T3510_11 | MAF_0322 | 2 | 2 | 722 (724) | 1444 |
| *T3510/12 | ио 0118т-1 | VAT_MAF_T3510_12 | MAF_0920 | 2 | 2 | 678 (678) | 1356 |
| *T3510/16 | ДП 090 | VAT_MAF_T3510_16 | MAF_0803 | 1 | 1 | 4562 (4562) | 4562 |
| *T3510/26 | Теннисный стол | VAT_MAF_T3510_26 | MAF_0677 | 1 | 1 | 8620 (8696) | 8620 |
| *T3510/27 | Стол Ландау | VAT_MAF_T3510_27 | MAF_0219 | 3 | 3 | 524 (540) | 1572 |
| *T3510/28 | Подвес качели гнездо | VAT_MAF_T3510_28 | MAF_0127 | 4 | 4 | 2030 (2030) | 8120 |
| *T3510/29 | Кресло Парк 12750 | VAT_MAF_T3510_29 | MAF_0159 | 25 | 25 | 318 (320) | 7950 |
| *T3510/31 | Стол Лондон Тип 3 | VAT_MAF_T3510_31 | MAF_0722 | 16 | 16 | 208–212 (212) | 3335 |
| *T3510/32 | Приствольная решетка | VAT_MAF_T3510_32 | MAF_0687 | 4 | 4 | 3350 (3726) | 13400 |

### Flora

| pos | schedule (ru / latin) | library object | match | scheduled | SPOZU all / in | placed | base scale | tris/inst placed (library) | tris total placed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Липа мелколистная Rancho / *Tilia cordata Greenspire* | 101 Tilia_cordata_VPM | substitute | 23 | 25 / 23 | 23 | 1.2023 | 830 (830) | 19090 |
| 3 | Черемуха обыкновенная / *Prunus padus Watereri* | 120 Prunus_padus_VPM | substitute | 11 | 12 / 11 | 11 | 1.0000 | 494 (494) | 5434 |
| 4 | Яблоня Маковецкого / *Malus Makowieckiana* | 115 Malus_niedzwetzkyana_VPM | substitute | 24 | 25 / 21 | 21 | 1.0000 | 394 (394) | 8274 |
| 6 | Ирга колосистая / *Amelanchier spicata* | 105 Amelanchier_lamarckii_VPM | substitute | 38 | 39 / 38 | 38 | 0.9866 | 4894 (4894) | 185972 |
| 7 | Боярышник обыкновенный / *Crataegus laevigata Paul`s Scarlet* | 103 Crataegus_mollis_VPM | substitute | 29 | 30 / 29 | 29 | 1.0000 | 574 (574) | 16646 |
| 9 | Пузыреплодник калинолистный ‘Lady in red’ / *Physocarpus opulifolius ‘Lady in red’* | 205 Physocarpus_opulifolius_Diabolo_VPM | substitute | 191 | 192 / 191 | 191 | 1.0106 | 144 (144) | 27504 |
| 11 | Рябинник рябинолистный / *Sorbaria sorbifolia* | 212 Sorbaria_sorbifolia_VPM | exact | 866 | 876 / 866 | 866 | 1.2136 | 84 (84) | 72744 |
| 14 | Лапчатка кустарниковая / *Potentila fruticosa* | 230 Dasiphora_fruticosa_VPM | exact | 558 | 559 / 558 | 558 | 1.0000 | 20 (20) | 11160 |
| 15 | Стефанандры надрезаннолистная / *Stephanandra incisa* | 223 Stephanandra_incisa_Crispa_VPM | exact | 1002 | 1003 / 1002 | 1002 | 1.0000 | 90 (90) | 90180 |
| 17 | Сосна горная ф. Мугус / *Pinus mugo var. Mughus* | 224 Pinus_mugo_VPM | substitute | 99 | 107 / 106 | 106 | 1.0000 | 64 (64) | 6784 |

Crown diameter: `review` for every species (not in the schedule, gate-1 F3).

### Not placed (points, reason)

| label | reason | points |
|---|---|---|
| Андромеда Металл Крыша поликарбонат | no_library_model | 2 |
| Барная стойка | no_library_model | 1 |
| Бетонные раскопки | no_library_model | 8 |
| Боярышник средний  'Paul's Scarlet' | outside_boundary | 1 |
| Воркаут | no_library_model | 1 |
| Воркаут 217100 | no_library_model | 1 |
| Воркаут 217170 | no_library_model | 1 |
| Гамак | no_library_model | 3 |
| ДП 090 | outside_boundary | 1 |
| Дерен белый 'Red Gnome' | no_confirmed_vpm | 325 |
| Дерен белый 'Red Gnome' | outside_boundary | 1 |
| Дерен кроваво-красный (Cornus sanguinea) ‘Anny’s Winter Orange’ | no_library_model | 439 |
| Дерен кроваво-красный (Cornus sanguinea) ‘Anny’s Winter Orange’ | outside_boundary | 1 |
| Ель нидиформис | no_library_model | 70 |
| Ель нидиформис | outside_boundary | 1 |
| Ива швейцарская (Salix helvetica) К | no_library_model | 131 |
| Игровой комплекс Кубики | no_library_model | 1 |
| Ирга колосистая | outside_boundary | 1 |
| Карусель | no_library_model | 2 |
| Качели парковые | no_library_model | 11 |
| Контейнер 1100л ТБО | no_library_model | 8 |
| Контейнер 1100л ТБО | outside_boundary | 10 |
| Кресло Парк 12750 | outside_boundary | 2 |
| Лапчатка кустарниковая (Dasiphora fruticosa) К | outside_boundary | 1 |
| Липа мелколистная 'Greenspire' | outside_boundary | 2 |
| Лиственница обыкновенная 'Pendula' | no_library_model | 13 |
| Лиственница обыкновенная 'Pendula' | outside_boundary | 1 |
| Лох узколистный | no_library_model | 25 |
| Лох узколистный | outside_boundary | 1 |
| Навес 1 | no_library_model | 1 |
| Навес 1 | outside_boundary | 1 |
| Навес 2 | no_library_model | 1 |
| Навес 2 | outside_boundary | 1 |
| Навес 3 | no_library_model | 1 |
| Навес 3 | outside_boundary | 1 |
| Навес 4 | no_library_model | 1 |
| Навес 4 | outside_boundary | 1 |
| Облепиха крушиновидная ‘Hikul’ | no_library_model | 1059 |
| Облепиха крушиновидная ‘Hikul’ | outside_boundary | 1 |
| Ольха серая 'Laciniata' | no_library_model | 8 |
| Ольха серая 'Laciniata' | outside_boundary | 16 |
| Пенек | no_library_model | 9 |
| Пенек | outside_boundary | 3 |
| Песочница индивидуальный МАФ | no_library_model | 1 |
| Площадка для контейнеров БТО 2 | no_library_model | 1 |
| Площадка для контейнеров ТБО | outside_boundary | 1 |
| Пузыреплодник калинолистный (Physocarpus opulifolius) ‘Lady in red’ | outside_boundary | 1 |
| Рябинник рябинолистный | outside_boundary | 10 |
| Скамья верона | no_library_model | 1 |
| Скамья верона | outside_boundary | 1 |
| Скамья верона 2 | no_library_model | 1 |
| Скамья верона 2 | outside_boundary | 1 |
| Скамья индивид лестн 1 | no_library_model | 2 |
| Скамья индивид лестн 1 | outside_boundary | 3 |
| Скамья индивид общ отд 1 | no_library_model | 1 |
| Скамья индивид общ отд 1 | outside_boundary | 1 |
| Скамья индивид общ отд 2 | no_library_model | 1 |
| Скамья индивид общ отд 2 | outside_boundary | 1 |
| Скамья индивид пл. дети1-3лет | no_library_model | 1 |
| Скамья индивид пл. дети1-3лет | outside_boundary | 1 |
| Скамья тетрис 03 | no_library_model | 4 |
| Сосна горная ф. Мугус | outside_boundary | 1 |
| Стефанандра надрезаннолистная Crispa (Stephanandra incisa Crispa) | outside_boundary | 1 |
| Стол Лондон Тип 3 | outside_boundary | 1 |
| Стул бар | no_library_model | 4 |
| Тренажер волна | no_library_model | 1 |
| Тренажер лыжи | no_library_model | 1 |
| Тренажер мышиная охота | no_library_model | 1 |
| Турник | no_library_model | 1 |
| Урна | ground_exception | 2 |
| Урна | outside_boundary | 1 |
| Черемуха обыкновенная 'Watereri' | outside_boundary | 1 |
| Шезлонг фестиваль модуль 3 | no_library_model | 1 |
| Яблоня 'Makowieckiana' | outside_boundary | 4 |
| ио 1005т-11 | no_library_model | 1 |
| скамья индивид под андромедой | no_library_model | 1 |
| скамья индивид под андромедой | outside_boundary | 1 |

Excluded by a user-approved Ground exception (bound to this Ground master; a repaired Ground places them again):

| handle | label | library | reason | Ground master sha256 | approved |
|---|---|---|---|---|---|
| 15E288 | Урна | VAT_MAF_T3510_02 | Урна inside 568BF but ~1 cm outside the edge of a Ground v014 cut-out (border bbox x -7680.43..-7675.91, y -15352..-15336); engine finding point_outside_ground (run_v003). Ground defect reported to #295. | `82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5` | Artem 2026-10-20: "option a: the 2 urns 15E288/15E289 (VAT_MAF_T3510_02), ~1 cm outside the Ground v014 cut-out edge, are NOT placed for this run; list them in the placement report with the reason and the Ground v014 sha256. The exclusion is bound to Ground v014 only: a corrected Ground places them again." |
| 15E289 | Урна | VAT_MAF_T3510_02 | Урна inside 568BF but ~1 cm outside the edge of a Ground v014 cut-out (border bbox x -7680.43..-7675.91, y -15352..-15336); engine finding point_outside_ground (run_v003). Ground defect reported to #295. | `82cb1e6876ba98b92966aa7fc4242a2e9f354ee5ecdd42ed12806b57db666ae5` | Artem 2026-10-20: "option a: the 2 urns 15E288/15E289 (VAT_MAF_T3510_02), ~1 cm outside the Ground v014 cut-out edge, are NOT placed for this run; list them in the placement report with the reason and the Ground v014 sha256. The exclusion is bound to Ground v014 only: a corrected Ground places them again." |

No confirmed VPM version (not cloned, not placed in VPM): pos 12 Cornus_sericea_NPM

## NPM budget [D097]

| part | triangles | share |
|---|---|---|
| Ground surface (#295 v014 NPM) | 46343 | 50 000 |
| MAF | 55403 | 60 000 |
| Flora | 118774 | 70 000 |
| **total** | **220520** | **180 000** |

Flora overrun +48774 vs its share and total +40520 vs 180 000: accepted for this slice by the user (gate-1 F4 option a, 2026-10-20); a lighter Flora NPM is a separate card.

## Questions to the user (not modelled, not substituted)

- Flora without a library object (gate-1 F1): pos 2 Ольха, 5 Лиственница, 8 Лох, 10 Дерен кроваво-красный, 13 Облепиха, 16 Ель нидиформис; unscheduled Ива швейцарская (131 points).
- MAF without a library model (#313 Q1/Q5): see `not_placed` rows `no_library_model`.
- Points excluded by a user-approved Ground exception bound to the Ground master sha256: `ground_exception` rows (a repaired Ground places them again).
- Out-of-plot planting (gate-1 Q2a): `outside_boundary` rows. Pinus mugo placed by 106 plan points, schedule 99 (+7, gate-1 Q2b).
