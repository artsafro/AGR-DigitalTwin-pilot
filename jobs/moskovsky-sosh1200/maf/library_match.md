# MAF library match — moskovsky-sosh1200

Read-only search, 2026-11-26. Matching: articles normalised (case, spaces/dots/dashes/slashes stripped,
Cyrillic transliterated, ВСТ=VST, ИО=IO, СО=SO, ИК=IK), plus transliterated names. A hit needs an article or a clear
name; what matched is in the note. Tris/dims for .max hits = fresh `3dsmaxbatch` load (snapshot tris, world bbox,
file units); nothing saved, user Max PIDs 332840/489216 untouched. Scratch: `C:/Users/artsafro/AppData/Local/Temp/claude/maflib-scratch/`
(`hits.txt`, `names_out.txt`, `fbx_names.txt`, `stats_out.txt`).

**Key finding:** the AGR library proper (A101 + union) has almost nothing for this list; the hits are in the
Weltbau viz library `C:/Users/artsafro/Desktop/!3D viz/!Weltbau/Assets/MAF_LIB/` (called `MAF_LIB` below) and in
the Sokolniki job MAF folder. Several MAF_LIB tris equal the "viz dummy faces" in `maf_plan.md` exactly
(aerofon 97775, drum 34916, pipes 136042, Skarlet 25320, volleyball 53380), so the client viz scene
`MOS_GP_26.11.2026.max` was built from MAF_LIB. MAF_LIB entries are single viz (high) models: **no NPM/Low variant
exists for any of them**; many are far above the NPM budget per item.

## 1. Searched locations

| Path | How | Files | Reachable |
|---|---|---|---|
| `G:/Мой диск/AGR-assets/` (maf/a101, a101_meta, a101_fixed, union_v001, projects, atlas, _inbox, silikatny, moskovsky-sosh1200, …) | recursive file names | 4376 | yes |
| `G:/Мой диск/AGR-assets/maf/maf-union-allin.max` | `getMAXFileObjectNames` (batch) | 996 objects | yes |
| `library/assets/maf_unified.json` (1039 records + 170 spec rows without model) | fields name/article/title/spec | — | yes |
| `library/maf/catalogue.json` (931 entries, 205 spec matches), `library/maf/fbx_materials.json`, `library/assets/maf_measured.json` | fields | — | yes |
| `library/published/catalogue.json` | — | 0 records | yes (empty) |
| `C:/Users/artsafro/Desktop/!3D viz/` (all, incl. `!А101/`, `!Weltbau/Assets/MAF_LIB`, `!Weltbau/MAF`, `!Weltbau/10_Сокольники/MAF`, `!TG_LIB`) | recursive file names | 61073 | yes |
| A101 scenes: `!А101/MAF_A101_2022.max`, `MAF_All/*.max` (5), `MAF_26sk/*.max`, `51_MAF_2026/*.max` (10 incl. 4BK, 10.3, 4аск) | `getMAXFileObjectNames` (batch) | 17 scenes, ~1070 names | yes |
| `!Weltbau/Assets/Weltbau_Master_File.max` | object names | 365 | yes |
| A101 FBX: `MAF_All/МАФЫ_НПМ.fbx`, `MAF_All/Mafs_ВПМ.fbx`, `51_MAF_2026/MAF_10.3.fbx` | model names from binary FBX | 644 names | yes |
| `C:/x/` (depth ≤ 4; .max .fbx .blend .obj .json .md) | file names | 455036 | yes |
| `C:/x/silikatny-maf-viz/` (SIL_MAF_v004: VST 9624/3, Bunker 5003-1, Hozblok 5052, AL-L-06-11, SO-053, MK001, fence PRO, gates 4.5, wickets, sport fence H4 — per `jobs/silikatny-maf-viz/README.md`) | — | 0 | **no — folder absent**; items partly survive in MAF_LIB / Sokolniki |

## 2. Matches

Paths: `LIB` = `C:/Users/artsafro/Desktop/!3D viz/!Weltbau/Assets/MAF_LIB`, `SOK` = `C:/Users/artsafro/Desktop/!3D viz/!Weltbau/10_Сокольники/MAF`.
Dims as stored (X×Y×Z m, file units cm). NPM? = a light/Low variant exists.

| pos | item / code | match | file | object | tris | dims m | NPM? | note |
|---|---|---|---|---|---|---|---|---|
| 1 | Теневой навес «Нордик» ВСТ 1519/1 | exact | `LIB/VST_1519-1_NAVES/VST_1519-1_NAVES.max` | VST_1519-1_NAVES | 2248 | 6.88×5.14×2.72 | no | article; larger than page 6.4×4.85 (viz dummy was 6.6). Near: `LIB/IND_NAVES_25` (4456, 6.64×4.52×3.10) = Sokolniki/Savelovsky individual canopy |
| 2 | Доска для рисования мелом 7W2002 | exact | `LIB/ROB_7W2002_DOSKA/ROB_7W2002_DOSKA.max` | ROB_7W2002_DOSKA | 59112 | 1.20×0.16×1.59 | no | article; heavy. Near (other mfr): `LIB/IGR_MN8642P_CHALKBOARD` 1664, 1.06×0.10×1.25 |
| 3 | «Собрание» 6W7000 | exact | `LIB/ROB_6W7000_SOBRANIE/ROB_6W7000_SOBRANIE.max` | ROB_6W7000_SOBRANIE | 8064 | 1.66×1.68×0.50 | no | article + name; page 1.79×1.79 |
| 4 | БУМ-Бревно ИК 0209Т-6.1 | near | `LIB/IGR_MN8404M_BUM_BREVNO/IGR_MN8404M_BUM_BREVNO.max` | IGR_MN8404M_BUM_BREVNO | 11638 | 2.30×0.18×0.46 | no | name «БУМ-Бревно» only; manufacturer Игратекс MN8404M, not Тайга. Dims = viz dummy (2.3×0.18×0.46) |
| 5 | Переговорные трубы ИО 1215.1 | exact (+ check) | `LIB/TAI_IO-1215-1_EHO/TAI_IO-1215-1_EHO.max` | TAI_IO-1215-1_EHO | 207626 | 0.70×0.33×1.26 | no | article ИО 1215.1, but H 1.26 ≠ page 1.00. The viz used `LIB/TAI_IO-1215_TRUBY` (136042, 0.31×3.67×0.98, two posts; tris = viz dummy). Also `SOK/SOK_08_IO-1215` (66858, one post, H 1.415) and `LIB/IGR_IO-1215_TRUBY` (4386, 0.40×0.15×1.10) |
| 6 | Аэрофон ИО 1204 | exact | `LIB/TAI_IO-1204_AEROFON/TAI_IO-1204_AEROFON.max` | TAI_IO-1204_AEROFON | 97775 | 1.09×0.30×0.94 | no | article + name; = viz dummy |
| 7 | Язычковый барабан ИО 1211 | exact | `LIB/TAI_IO-1211_BARABAN/TAI_IO-1211_BARABAN.max` | TAI_IO-1211_BARABAN | 34916 | 0.58×0.58×0.78 | no | article; = viz dummy. (`TAI_IO-1211-1_BARABANY` = set of drums, 156466, 2.31×2.47) |
| 8 | Шахматный стол «Шах и мат» 6U7004 | near | `G:/Мой диск/AGR-assets/maf/union_v001/max/MAF_0829_Shahmaty.max` (+ .fbx) | Shahmaty (union) | 376 | 2.37×0.70×0.78 | no | name «шахматы» only, unknown mfr, longer than 1.7×0.8. No 6U7004 anywhere |
| 9 | Скамейка «Стрела-дуга» 6U2023 | none | — | — | — | — | — | no article/name hit |
| 10 | «Плато 1» 6W3000.1 | exact | `LIB/ROB_6W3000-1_PLATO/ROB_6W3000-1_PLATO.max` | ROB_6W3000-1_PLATO | 58014 | 0.91×1.49×0.43 | no | article + name |
| 11 | «Хитроу гранд» 6W2006.1 | none | — | — | — | — | — | no article/name hit |
| 17 | Стол теннисный СО 0216-3 | exact | `LIB/TAI_SO-0216-3_TENNIS/TAI_SO-0216-3_TENNIS.max` | TAI_SO-0216-3_TENNIS | 51306 | 2.75×1.53×0.91 | no | article; height 0.91 (plan question 0.76 stays). Near light: union `MAF_0678_M_Tennis_Table_002` 872 tris |
| 19 | Баскетбольная стойка СО-012 | none | — | — | — | — | — | near only (other mfr): `G:/…/_inbox/BUHV12/maf/Mafmarket_BasketbolnyySchitSKoltsom_SPE100.zip`; Sokolniki inbox `Баскетбольная стойка красная QQS-002/3D/kolco_1900X1700X3500.max` (source, not built) |
| 21 | Волейбол СО053 | exact | `LIB/POK_SO-053_VOLLEY/POK_SO-053_VOLLEY.max` | POK_SO-053_VOLLEY | 53380 | 10.16×0.15×2.66 | no | article; = viz dummy. (Silikatny had a 300-tris version, files absent) |
| 22 | Стойки большого тенниса 11.100 ГЛАВСПОРТ | none | — | — | — | — | — | "11100" only hits a union gate name (false). Near: `_inbox/BUHV12/maf/SportivnyeGoroda_StoykiVoleybolnyeTeleskopicheskieTonus_SG-1550.zip` (volleyball posts) |
| 23 | Флагшток AL-L-06-11 | exact | `SOK/SOK_28_AL-L-06-11/SOK_28_AL-L-06-11.max` | SOK_28_AL-L-06-11 | 17364 | 0.60×2.20×9.00 | no | article; 9 m pole + flag. Same mesh as `LIB/FLAG_9M_RUS` / `FLAG_9M_WHITE` (17364, H 9.35 = viz dummy) |
| 24 | Стол со скамейкой и диваном ВСТ 9504/1 | exact | `G:/Мой диск/AGR-assets/maf/a101/GKVysota_StolSoSkameykoyIDivanom_VST9504-1.zip`; staged `G:/…/_inbox/vst9504-2026-11-19/maf/` | GKVysota_StolSoSkameykoyIDivanom_VST9504-1 _high/_low | 1020 / 636 | 1.80×2.00×0.85 | **yes** (low 636) | article; record `C:/x/library-publish/AGR-assets/maf/Gkvysota_…/v001/RECORD.json` status draft, qa fail (sinking −0.1 m); not in `maf_unified.json` yet. Source model `C:/x/vst9504-table` |
| 25 | Пергола ВСТ 9614/4 (blocks 9612/6) | near / exact-block | `C:/Users/artsafro/Desktop/!3D viz/!Weltbau/MAF/Высота арт.ВСТ-9612.3/Pergola_Visota.max`; `LIB/VST-9612-6_PERGOLA/VST-9612-6_PERGOLA.max` | Pergola_Visota; VST-9612-6_PERGOLA | 1016; 542 | 5.88×2.20×2.61; 3.00×2.20×2.61 | no (both light already) | 9612/6 = exact for the drawn block (3.0 m). Pergola_Visota = 5.88 m Высота pergola (folder says ВСТ-9612.3) ≈ ledger 9614/4 5.8×2×2.7 by size — article not confirmed. No 9614 anywhere |
| 26 | Навес для МГН ВСТ 9624/3 | exact | `SOK/SOK_25_VST-9624-3/SOK_25_VST-9624-3.max` | SOK_25_VST-9624-3 | 5304 | 5.00×1.75×2.00 | no | article; Silikatny build [D190] re-used in Sokolniki. Near: `LIB/DP_N155465_NAVES_MGN` (22170, 2.08×1.40×2.22, other item) |
| 27 | Скамейка «Скарлет» 10027-1 | exact | `LIB/ADN_10027-1_SKARLET/ADN_10027-1_SKARLET.max` | ADN_10027-1_SKARLET | 25320 | 0.65×1.80×0.81 | no | article + name; = viz dummy |
| 28 | Урна «Город» 9004 Аданат (block Робинзон 6W9006) | near (ledger) / exact (block) | `LIB/ROB_6W9006_KUB/ROB_6W9006_KUB.max` | ROB_6W9006_KUB | 13228 | 0.47×0.40×0.87 | no | 6W9006 = the drawing block (dims = viz dummy). No Аданат 9004 «Город». Name-only near: A101 `G:/…/maf/a101/Hobbika_UrnaGorodWood_58619.zip` (high 314 / low 230, 0.41×0.45×1.02, has NPM), other mfr. Also `LIB/IGR_5963-S_URNA` 412 |
| 32 | Контейнерная площадка на 3 контейнера Аданат (Бункер 5003-1 / Панель 5029-2) | exact (Бункер 5003-1) | `LIB/ADN_5003-1_BUNKER3/ADN_5003-1_BUNKER3.max` | ADN_5003-1_BUNKER3 | 5736 | 4.60×2.62×2.47 | no | article 5003-1 (page 4.54×2.51×2.49). Also `LIB/ADN_KP6_KONTPLOSHCHADKA` (11416, 7.64×2.53×2.48 ≈ viz dummy 7.24 wide), `LIB/ADN_5003-2_BUNKER4` (8160), `SOK/SOK_27_5029-3` (Панель on 3? 3220, 7.0×2.30×2.53) and `SOK/SOK_26_5030-1` (2640) — 5029-2 itself not found |
| 33 | Хозблок Аданат | exact (name) | `LIB/ADN_5052_HOZBLOK/ADN_5052_HOZBLOK.max` | ADN_5052_HOZBLOK | 3312 | 1.18×2.62×2.47 | no | name + mfr (ledger has no code; Silikatny used 5052) |
| 34 | Контейнер МК001 | exact | `LIB/MK001_CONTAINER/MK001_CONTAINER.max`; same in `SOK/SOK_30_MK001` | MK001_CONTAINER | 520 | 1.40×1.10×1.37 | n/a (already light) | article |
| 35 | Сварное ограждение PRO H 2.5 (individual) | exact (name/height) | `SOK/SOK_37_IND-OgrPRO-sekc2-04/SOK_37_IND-OgrPRO-sekc2-04.max` | SOK_37_IND-OgrPRO-sekc2-04 | 2160 | 2.035×0.10×2.50 | no | one section 2.04 c/c, for array; individual design from Silikatny DWG — check against this job's drawing |
| 36 | Ворота распашные 4.5 (individual) | none (on disk) | — | — | — | — | — | Silikatny `MAF_P30_IND_VorotaRaspashnye_4-2` (4.5×0.15×2.51, 636) documented, files absent. MAF_LIB `*_VOROTA` are football goals |
| 37/38 | Калитка 1.2 / калитка спорт (individual) | none (on disk) | — | — | — | — | — | Silikatny `MAF_P31` / `MAF_P32` documented, files absent |
| 39 | Ограждение спортивное H 4 (individual) | none (on disk) | — | — | — | — | — | Silikatny `MAF_P33` documented, files absent |

A101 library (`maf_unified.json`, `G:/…/maf/a101`, A101 desktop scenes and FBX): no article hit for any position except
pos 24; only name-level near hits (union Shahmaty, tennis tables, Бункер, Hobbika «Город» urn). No Робинзон, Поколение,
ГЛАВСПОРТ, Grand-mag items in A101; Тайга only carousel/island (not ours); Аданат items are other models.

## 3. Positions with no model (= new models)

- 9 Скамейка «Стрела-дуга» 6U2023 (Робинзон)
- 11 «Хитроу гранд» 6W2006.1 (Робинзон)
- 19 Баскетбольная стойка СО-012 (Поколение)
- 22 Стойки большого тенниса 11.100 (ГЛАВСПОРТ) — not in the drawing anyway
- 36 Ворота 4.5, 37/38 калитки, 39 ограждение спортивное H 4 — individual; Silikatny versions were documented but the files are gone

Near only (a model exists but is not this article): 4 (Игратекс БУМ-бревно), 8 (union шахматы), 28 ledger type
Аданат 9004 (block type Робинзон 6W9006 exists), 25 ledger type 9614/4 (Pergola_Visota by size; 9612/6 block exact).

Every exact MAF_LIB / Sokolniki hit is a viz model with no Low/NPM variant; only pos 24 has an NPM version.
Items already within an NPM-scale budget: 25 (542 / 1016), 34 (520), 33 (3312), 1 (2248), 35 (2160 per section).
