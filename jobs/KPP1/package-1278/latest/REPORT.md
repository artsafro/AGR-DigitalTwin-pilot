# Current KPP1 package #1278 — latest R1 v003, NOT PASSED

This supersedes the historical package-v003 / R1-v002 report and tables one directory up.
Current main was refreshed to bef05228, including #1246/#1289's newer R1 v003 corner pairs,
#1240/#1287 and the new shared scene checks. No sibling branch was read or copied: only merged main.
D266 and reserved [D267] were both retained in the only merge conflict (decision-log adjacency).

## Reproduce in one command

```bash
uv run python jobs/KPP1/package-1278/build_package.py "G:/Мой диск/AGR-evidence/1278-kpp1-package/site-r1-v003" "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v005"
```

Measured final candidate: **G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v004/**.
`repro-v004`: 5/5 assembly files byte-identical. Source SHA pins are in
`../source-r1-v003-SHA256SUMS.txt`; runtime manifest below binds ZIP/GeoJSON/receipts.
To regenerate the placed source, on a new directory, run the existing source-hash-checked producer:

```bash
"C:/Program Files/Blender Foundation/Blender 5.1/blender.exe" --background --factory-startup --python-exit-code 1 --python jobs/KPP1/site-1255/place_package.py -- "G:/Мой диск/AGR-evidence/1246-kpp1-corner-pairs" "G:/Мой диск/AGR-evidence/1278-kpp1-package/site-r1-v003-new"
```

The measured placed source is `site-r1-v003`. Its render/FBX serialization hashes are pinned;
regenerating it is a provenance diagnostic, not permission to accept different source hashes.
Only a 10-line explicit R1-v003 hash allowlist was added to the existing placement producer;
old v002 pins remain valid. Regression: 4d49ea86, 1 failed, then green.
No geometry rebuild or cleanup in #1278. The newly merged #1246 source is authoritative.

[D267]: approved Ground and KPP1-specific s_obsh/s_naz/s_podz/spp_gns sheet are unavailable;
assemble without them, never synthesize Ground or copy whole-site areas. FNO awaits SINTEZ.
[D262]: approximate, ±0.1 m, fitted to customer NPM 0607_77_05_0009005_117_02;
**entrance orientation not independently confirmed**. No 180-degree alternative;
point **[8056.144, -9581.270]**, zero **171.050 m**. Median 0.099 m is not a maximum bound.

## Repairs / exact preservation

- NPM glass name M_Glass_01, opacity and TransparencyFactor 0.5.
- GeoJSON coordinate token -9581.270, semantic document unchanged.
- Four flat Diffuse PNGs 2048->256; ERM/Normal already 256; exact constant colours retained.
- Native independent Blender 5.1.2 parser comparison: 409 elements, exactly 3 material-property
  differences; other geometry/UV/indices/embedded image arrays unchanged; native alpha readback 0.5.
- VPM 23/23 members retained, 0 drops, 18 unchanged byte-for-byte; exactly 4 Diffuse PNG + GeoJSON edits.
- All mandatory non-passes remain false/review/not_run, never relabelled clean.

## Validation

Fresh before/after ZIP imports: both profiles exit 1 / passed=false. All V001–V017
values BEFORE and AFTER, limits, statuses and owners: [CHECKS.md](CHECKS.md).
Every remaining non-pass is reproduced below and in jobs/KPP1/STATE.md.
Current xView: VPM 85 faces / 0 vertices (128 pairs), NPM 0/0. Historical 112/12
(unplaced R1-v002) and 99/0 (placed R1-v002) are not current measurements or fixes by this packager.
VPM geometry improvement belongs to merged #1246; native Max parity and 0/0 target remain open.

SINTEZ diagnostic: private Blender 5.1.2, process exit 0, checker error=null;
HP **64 verified / 3 failed / 53 undefined**, LP **39 / 4 / 29**.
Undefined IDs and full failed items in sintez-summary.json; no upload, UKEP or manual acceptance.
Code 0000 stays placeholder under [D262]/[D235], despite diagnostic recommendation 0607.

## Every remaining non-pass

| Stage | Value / status | Limit / missing input | Owner |
|---|---|---|---|
| npm/V001 FBX count | fail: 1 | 2..21 (1 Ground + 1..20 OKS) | Ground author / Artem: approved Ground missing |
| npm/V001 Ground FBX | fail: ['0000_Kpp_1_01.fbx'] | 0000_Kpp_1_Ground.fbx | Ground author / Artem: approved Ground missing |
| npm/V003 master quads | not_run: quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | KPP1 master author / Artem: quad work FBX missing |
| npm/V004 co-directional clearance | review: 0000_Kpp_1_01.fbx: 20374 co-directional overlapping pairs: 0 < 5 mm, 108 in band, 20266 > 20 mm; distance mm min/median/max 13.695/6870.2359/31170.3557; histogram {'0-1': 0, '1-5': 0, '5-10': 0, '10-20': 108, '20-50': 14, '50-100': 972, '100-1000': 987, '1000+': 18293}; worst: ['SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16670 d=31170.4 mm', 'SM_Kpp_1_001_Main#7465/SM_Kpp_1_001_Main#16669 d=31170.3 mm', 'SM_Kpp_1_001_Main#7462/SM_Kpp_1_001_Main#10604 d=30670.4 mm', 'SM_Kpp_1_001_Main#7447/SM_Kpp_1_001_Main#10604 d=30420.5 mm', 'SM_Kpp_1_001_Main#7482/SM_Kpp_1_001_Main#11826 d=29670.2 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | KPP1 geometry author / Artem: rotated-pair classification missing |
| npm/V014 геометрия в московских проектных координатах и высотах; углы соответствуют плану | not_run: not measured | геометрия в московских проектных координатах и высотах; углы соответствуют плану | Validator maintainer / Artem: coordinate-stage implementation absent |
| npm/V015 силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not_run: not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | Artem: architectural acceptance absent |
| npm/V017 сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not_run: not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | Artem / survey author: placement and entrance orientation sign-off absent |
| vpm/V003 master quads | not_run: quad work FBX not given (--master) | quad master; VPM faces <= 4 m [D021] | KPP1 master author / Artem: quad work FBX missing |
| vpm/V004 co-directional clearance | review: SM_Kpp_1.fbx: 105773 co-directional overlapping pairs: 0 < 5 mm, 159 in band, 105614 > 20 mm; distance mm min/median/max 14.7994/7345.9993/31170.3993; histogram {'0-1': 0, '1-5': 0, '5-10': 0, '10-20': 159, '20-50': 230, '50-100': 2722, '100-1000': 7626, '1000+': 95036}; worst: ['SM_Kpp_1_Main#12042/SM_Kpp_1_Main#28032 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#12042 d=31170.4 mm', 'SM_Kpp_1_Main#12042/SM_Kpp_1_Main#28033 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#27904 d=31170.4 mm', 'SM_Kpp_1_Main#4091/SM_Kpp_1_Main#12001 d=30920.4 mm'] | co-directional overlapping faces 5-20 mm apart (pairs beyond 20 mm: review) | KPP1 geometry author / Artem: rotated-pair classification missing |
| vpm/V010 UCX coverage and offsets | not_run: coverage of the model, offsets | reg p.34-37 | Artem / collision reviewer: independent coverage and offset evidence missing |
| vpm/V011 FNO_code empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V011 FNO_name empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V011 s_obsh empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V011 s_naz empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V011 s_podz empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V011 spp_gns empty | fail: empty | mandatory value (never invent it; ask the customer) | SINTEZ: FNO pair; Artem / architect: KPP1 area schedule missing |
| vpm/V012 archive name | review: SM_Kpp_1 | SM_{Address}; _001.. index for free-standing buildings | Validator maintainer / Artem: one-OKS index review [D019] |
| vpm/V013 MSK-77 point | not_run: GeoJSON point vs survey coordinates and project zero | reg p.32-33, p.55 | Survey author / Artem: authoritative plan tie missing; validator subset absent |
| vpm/V015 силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | not_run: not measured | силуэт, этажи, фасады, материалы, оконные типы, первый этаж, крыша, благоустройство совпадают с утверждённым проектом | Artem: architectural acceptance absent |
| vpm/V016 проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | not_run: not measured | проходы/арки/дворы свободны, расстояние коллизий до поверхностей соответствует высотной зоне | Artem: collision acceptance absent |
| vpm/V017 сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | not_run: not measured | сверка точки вставки, отметки 0 и геопривязки с утверждённым DWG/СПОЗУ; у ВПМ допуск 0.5 м | Artem / survey author: placement and entrance orientation sign-off absent |
| xView npm | 0 faces / 0 vertices; passed=True | 0 / 0 at 5 / 2 mm; native Max parity missing | KPP1 geometry author / Artem |
| xView vpm | 85 faces / 0 vertices; passed=False | 0 / 0 at 5 / 2 mm; native Max parity missing | KPP1 geometry author / Artem |
| SINTEZ hp 2.1.1 | failed:     Общее;         SM_Kpp_1.zip: файл подписи не найден. Рядом с архивом должен лежать файл УКЭП с тем же именем (SM_Kpp_1.sig);  | genuine UKEP .sig missing; cryptographic validity not verified | Artem / applicant [D163] |
| SINTEZ hp 2.2.1 | failed:     Общее;         fno_code : код не соответствует шаблонам - XXX, XXX XXX, XXX XXX XXX;  | upload-confirmed classifier values; no invented FNO/code | SINTEZ / Artem |
| SINTEZ hp 2.2.6 | failed:     Общее;         Поле FNO_code обязательно к заполнению;         Поле FNO_name обязательно к заполнению;  | upload-confirmed classifier values; no invented FNO/code | SINTEZ / Artem |
| SINTEZ lp 2.1.1 | failed:     Общее;         0000_Kpp_1.zip: файл подписи не найден. Рядом с архивом должен лежать файл УКЭП с тем же именем (0000_Kpp_1.sig);  | genuine UKEP .sig missing; cryptographic validity not verified | Artem / applicant [D163] |
| SINTEZ lp 2.1.2 | failed:     Общее;         Неверное количество fbx-файлов (1): ожидается от 2 до 21;  | mandatory approved Ground; 2..21 FBX | Ground author |
| SINTEZ lp 2.1.6 | failed:     Общее;         Файлы благоустройства - неотъемлемая часть АГР и являются обязательными к исполнению.;  | mandatory approved Ground; 2..21 FBX | Ground author |
| SINTEZ lp 2.10.3.1 | failed:     Общее;         Код в наименовании (0000) не соответствует расположению модели. По текущим координатам центр модели находится в районе «ЮАО Бирюлёво Западное» — код должен быть 0607. Исправьте код в наименовании либо координаты модели;  | upload-confirmed classifier values; no invented FNO/code | SINTEZ / Artem |
| Final AGR Tools | not_run | real Max final evidence missing | Artem frees Max / AGR Tools operator |

## Test / suite boundary

204 affected tests passed after latest-main merge and source update. Additional RED:
latest-source allowlist test failed once on 4d49ea86 before implementation. Earlier RED
commits and 64/64 seeded payload probes remain recorded in the historical report.
The first full suite on 4113a20b was invalidated by a required main merge during execution;
it reported native 0xC0000142 child-start failures and HEAD drift, not a clean receipt.
Its FAIL receipt/log are retained verbatim. The fallback final-head suite runs SERIALLY
through suite_slot under the card's explicit xdist-start-failure policy; do not count the
interrupted/non-final run as an additional accepted suite or claim it passed.
Final exact-head suite counts/receipt are in the PR, not invented here.

Full diagnostic evidence lives on Drive, never LFS. Historical outputs remain immutable.
