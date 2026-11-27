# MAF plan — moskovsky-sosh1200 (NPM site)

Plan only: no modelling, nothing accepted. Type = ledger, count/position = drawing blocks inside ГПЗУ (TASK.md decisions 4-7).
Machine-readable: `maf_plan.json`; points: `maf_points.json`; count/type conflicts: `maf_discrepancies.md`.

At intake, `library/published/catalogue.json` was empty (0 records); `library/assets/maf_unified.json` has no entry for any code here (searched codes, names, manufacturers). Only hit: pos 24 = the accepted ВСТ 9504/1 model (historical A101 candidate; see [library match](library_match.md) for the distinct #1985 draft variant), staged as a library candidate, not yet accepted. Per the model-maf skill (step 2) Artem names a library object first if he knows one (e.g. in `МАФы_Union_ALLin.max`).

| pos | ledger name / code / mfr | drawing in ГПЗУ | ledger | viz | plan | library | L×W×H m (page) | viz dummy L×W×H m, faces | NPM tris each / total (est.) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Теневой навес 6400x4850x2700 мм / ВСТ 1519/1 / Высота | 7 | 7 | 7 | 7 | new | 6.4×4.85×2.7 | 6.6×4.85×2.72, 1060 | 800 / 5600 |
| 2 | Доска для рисования мелом / 7w2002 / Робинзон | 5 | 5 | 5 | 5 | new | 1.2×0.15×1.56 | 1.2×0.16×1.59, 36236 | 150 / 750 |
| 3 | Малые архитектурные формы "Собрание" / 6W7000 / Робинзон | 7 | 7 | 7 | 7 | new | 1.79×1.79×0.5 | 1.77×1.77×0.5, 5522 | 500 / 3500 |
| 4 | Гимнастический комплекс "БУМ-Бревно" / ИК 0209Т-6.1 / Тайга | 6 | 11 | 5 | 6 | new | 2.3×0.3×0.5 | 2.3×0.18×0.46, — | 300 / 1800 |
| 5 | Переговорные трубы / ИО 1215.1 / Тайга | 4 | 4 | 4 | 4 | new | 0.3×0.2×1 | 0.55×4.49×0.98, 136042 | 300 / 1200 |
| 6 | Аэрофон / ИО 1204 / Тайга | 2 | 2 | 2 | 2 | new | 1.1×0.3×0.9 | 1.09×0.32×0.94, 97775 | 400 / 800 |
| 7 | Язычковый барабан / ИО 1211 / Тайга | 2 | 2 | 2 | 2 | new | 0.6×0.6×0.8 | 0.58×0.58×0.78, 34916 | 200 / 400 |
| 8 | Шахматный стол "Шах и мат" (цвет Бежевый) / 6U7004 / Робинзон | 10 | 4 | 10 | 10 | new | 1.7×0.8×0.756 | 1.74×0.81×0.76, 69614 | 200 / 2000 |
| 9 | Скамейка "Стрела-дуга" / 6U2023 / Робинзон | 3 | 3 | 2 | 3 | new | 10.33×4.26×0.4 | 10.69×9.97×0.4, 6136 | 1000 / 3000 |
| 10 | Малые архитектурные формы "Плато 1" / 6W3000.1 / Робинзон | 9 | 9 | 9 | 9 | new | 1.49×0.91×0.43 | 1.42×0.98×0.43, 28914 | 150 / 1350 |
| 11 | Малые архитектурные формы "Хитроу гранд" / 6W2006.1 / Робинзон | 3 | 12 | 3 | 3 | new | 2×1.2×0.7 | 2×1.2×0.71, 15220 | 400 / 1200 |
| 17 | Стол теннисный / СО 0216-3 / Тайга | 4 | 7 | 4 | 4 | new | 2.7×1.5×— | 2.75×1.53×0.91, 469674 | 300 / 1200 |
| 19 | Баскетбольная стойка / СО-012 / Поколение | 2 | — | 2 | 2 | new | —×—×— | 2.07×1.2×3.79, 33623 | 400 / 800 |
| 21 | Спортивный комплекс (волейбол) с возможностью регулирования крепления сетки по высоте, оборудован сеткой, от 6лет / СО053 / Поколение | 1 | 1 | 1 | 1 | new | —×—×— | 10.16×0.16×2.66, 53380 | 300 / 300 |
| 23 | Уличный флагшток из алюминия / AL-L-06-11 / Grand-mag | 3 | 3 | 3 | 3 | new | —×—×6-12 | 0.3×0.3×9.35, 8682 | 150 / 450 |
| 24 | Стол со скамейкой и диваном / ВСТ 9504/1 / Высота | 7 | 4 | 7 | 7 | candidate VST9504-1 | 1.8×2.02×0.855 | 2.11×1.8×0.86, 780 | 636 / 4452 |
| 25 | Пергола / ВСТ 9614/4 / Высота | 14 | 14 | 7 | 7 | new | 5.8×2×2.7 | 5.82×2×2.7, 51220 | 600 / 4200 |
| 26 | Навес для МГН / ВСТ 9624/3 / Высота | 1 | 2 | 1 | 1 | new | —×—×— | 5.01×1.77×2, 721 | 400 / 400 |
| 27 | Скамейка «Скарлет» с подлокотниками / 10027-1 / Аданат | 19 | 16 | 19 | 19 | new | 1.8×0.65×0.805 | 1.8×0.65×0.81, 25320 | 500 / 9500 |
| 28 | Урны "Город" / 9004 / Аданат | 11 | 14 | 11 | 11 | new | 0.4×0.4×1 | 0.47×0.4×0.87, 5466 | 230 / 2530 |
| 32 | Контейнерная площадка  на 3 контейнера / — / Аданат | 1 | 6 | 4 | 4 | new | 4.54×2.51×2.49 | 7.24×2.53×2.48, 5678 | 400 / 1600 |
| 34 | Контейнер для мусора с крышкой / МК001 / Поколение | 4 | 18 | 12 dumpster proxies in 4 enclosures | 12 | new | 1.4×1.4×0.9 | 1.74×1.11×1.58, — | 200 / 2400 |
| 37/38 | Калитка периметрального ограждения / — / Индивидуальный проект | 4 | [3.0, 3.0] | 0 | 0 | new (fence item) | 1.2×—×— | —×—×—, — | 0 / 0 |

**Total NPM estimate: ~49,432 tris vs the 60 000 MAF budget** (pergola as 7 pieces; with 14: ~53,632). Under budget in both readings; no light versions needed by this estimate. The budget split stays with Artem [D167].

Viz dummy faces = 3ds Max `getPolygonCount` summed over the group (reference only, render models).

## Manufacturer pages and notes

- **1** https://gk-vysota.ru/catalog/parkovaya-mebel/tproduct/673007226-979496308342-tenevoi-naves-nordik — not stated on page (Нордик, light wood + metal per blog). Теневой навес «Нордик». Viz dummy L 6.60 vs page 6.40 (+20 cm, outside the 10 cm tolerance): size from the page.
- **2** https://robinzon-maf.ru/igrovye-elementy/7w2002-bezhevyy — beige; materials not stated.
- **3** https://robinzon-maf.ru/malye-arhitekturnye-formy/6w7000-bezhevyy — beige (also blue/red); materials not stated. Table with stump seats «Собрание».
- **4** https://playtaiga.ru/product/2289-brevno-naklonnoe-ik-0209t6/ (closest: ИК 0209Т-6) — 5 colour options, no RAL. Code ИК 0209Т-6.1 not found on playtaiga.ru; closest ИК 0209Т-6 «Бревно наклонное». Ledger 11.
- **5** https://playtaiga.ru/product/2893-peregovornye-truby-io-12151/ — 5 colour options, no RAL. ИО 1215 (h 1.40) also exists; ledger says ИО 1215.1 (h 1.00); viz H 0.98 agrees with 1215.1.
- **6** https://playtaiga.ru/product/2809-aerofon-io-1204/ — metal tubes; 5 colour options.
- **7** https://playtaiga.ru/product/2824-yazychkovyy-baraban-io-1211/ — 5 colour options.
- **8** https://robinzon-maf.ru/malye-arhitekturnye-formy/skameyki/6u7004 (404 now; dims from search snippet) — бежевый (ledger); concrete. Ledger 4.
- **9** https://robinzon-maf.ru/malye-arhitekturnye-formy/skameyki/6u2023-bezhevyy — beige; materials not stated. Large curved bench; block base point at a corner. 1 drawing point has no viz object.
- **10** https://robinzon-maf.ru/malye-arhitekturnye-formy/6w30001-bezhevyy — beige (also blue/red); concrete base + boards (viz). 3 viz benches of the south cluster sit ~2 m off the drawing points.
- **11** https://robinzon-maf.ru/malye-arhitekturnye-formy/6w20061-bezhevyy — beige; galvanized steel + larch/thermowood/composite (category text). Ledger 12.
- **17** https://playtaiga.ru/product/2574-stol-tennisnyy-so-02163/ — 5 colour options. Page height 100 mm is a site error; viz 0.91 / standard 0.76 -> review. Ledger 7.
- **19** NOT FOUND (pokolenie-pk.ru catalogue is script-loaded) — unknown. Ledger count empty. One block mirrored.
- **21** NOT FOUND (Поколение СО053) — unknown. Volleyball posts + net; block extents 14.2 x 5.1 m (court marking incl.).
- **23** https://www.grand-mag.ru/catalog/flagshtoki_statsionarnye/flagshtok_statsionarnyy_6_12_metrov_iz_alyuminiya/ — aluminium АД31Т1, RAL 7040 standard. Height not fixed by the ledger; viz 9.35 m incl. flag -> question.
- **24** https://gk-vysota.ru/catalog/parkovaya-mebel/tproduct/673007226-539081018201-stol-so-skameikoi-i-divanom — ФСФ plywood + powder-coated metal (page); model IDs wood_light + paint_ral7016. Low 636 / High 1020 tris. Ledger 4.
- **25** https://davinci-play.ru/catalog/ulichnaya-mebel/pergoly/%D0%92%D0%A1%D0%A2-9614-4/ (dealer); drawn type 9612/6: https://davinci-play.ru/catalog/ulichnaya-mebel/pergoly/%D0%92%D0%A1%D0%A2-9612-6/ — not stated. Ledger type 9614/4 is 5.8 m = one pair of 3.0 m 9612/6 blocks; viz has 7 x 5.82 m at the pair centres. Plan 7 (14 if Artem keeps the ledger count).
- **26** NOT FOUND (ВСТ 9624/3) — unknown. Size only from viz/DWG (block 5.0 x 1.76). Ledger 2.
- **27** https://adanatgroup.ru/katalog/ulichnaya-mebel/ulichnye-skameiki/skamejka-skarlet-s-podlokotnikami/ — cast iron RAL 7016 shagreen; pine/larch «светлый дуб». 14 of 19 sit in the pergola groups. Ledger 16.
- **28** https://adanatgroup.ru/katalog/ulichnaya-mebel/urny-ulichnye/urna-gorod/ — steel RAL 7016 shagreen; pine/larch «светлый дуб». Ledger type Аданат 9004 «Город» wins over block Robinzon 6W9006 (0.47x0.40x0.88). Ledger 14.
- **32** https://adanatgroup.ru/katalog/ulichnaya-mebel/kontejnernye-ploshadki/kontejnernaya-ploshhadka-bunker-na-3-konteynera/ (closest; no code in ledger) — steel RAL 7016, pine/larch walls, galvanized roof. Drawing: 1 yard outline + 4 ТБО непищ groups inside (1 more 2.6 m outside). Viz: 4 enclosures on the ТБО points. Model choice open (Бункер 5003-1 / Панель 5029-2 / ...). Ledger 6.
- **34** NOT FOUND (Поколение МК001) — unknown (ledger dims). Ledger 18 containers (= 6 yards x 3). Plan 4 yards x 3 = 12 (follows the pos 32 answer).
- **37/38** individual project — fence. 4 gates inside ГПЗУ (+1 on the boundary). Fences are out of MAF scope here: modelled with the fence or not at all -> question; not in the budget.

## Not found / needs Artem

- Pages not found: 19 СО-012, 21 СО053 (Поколение, catalogue loads by script), 26 ВСТ 9624/3, 34 МК001. Sizes then only from viz dummies + DWG block outlines.
- 4: ИК 0209Т-6.1 not on playtaiga.ru; closest ИК 0209Т-6.
- 32: which Аданат 3-container yard (no code in the ledger).
- 23: flagpole height (6-12 m; viz 9.35 m).
- Робинзон and Тайга pages state no materials; colour per ledger (8: бежевый) or page swatches.
- 22 tennis posts (ГЛАВСПОРТ 11.100, ledger 2) and 33 Хозблок (ledger 1): no block in the drawing -> not in this plan (see discrepancies).

Sources: DWG sha256 ed87f7f9…, DXF G:/Мой диск/AGR-evidence/1979-moskovsky-sosh1200/intake/school.dxf (sha256 80848000…); viz scene MOS_GP_26.11.2026.max read only (no select/move/save).
