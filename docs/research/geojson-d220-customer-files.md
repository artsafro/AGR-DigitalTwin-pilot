# GeoJSON per D220 — customer files (ELV, KPP1, PSU275) vs our writer

Source: issue #1107 / decision D220 («start from the customer's example, then our generator»). Collected
2026-11-09 on the workstation; the customer files are read-only external data, not committed to the repo
(only their paths, sha256 and the field comparison live here).

## Collected customer files

| Job | Customer file | Source zip / path | sha256 |
|---|---|---|---|
| ELV (ТЦ «СРЕDА», Элеваторная вл. 1А) | `SM_Elevatornaya_Vl_1_A_001.geojson` | `C:\Users\artsafro\Desktop\!3D viz\Dima_Andrew\3_sreda\customer_2026-11-05\SM_Elevatornaya_Vl_1_A_001.zip` (zip `3051e465046c926738d17f83b07ee86d09e64c9a0f2e89f192c9a2a870da813f`) | `6f6285f0be20b12a14c4d474febd31ca076205c8070e972a3afe2d9ab00a7446` |
| PSU275 (ТЭЦ-26, главный корпус № 1) | `SM_77_05_0009005_117_001.geojson` | `C:\Users\artsafro\Downloads\Telegram Desktop\SM_77_05_0009005_117_001.geojson` | `ae65d6196f787b81234986e9e98571860b5c55cc47b356f998ad85dfdb218622` |
| KPP1 (ТЭЦ-26, Центральная проходная) | **not found** | the TEC-26 set `SM_77_05_0009005_117_00{1,3..10}` covers the PSU275 energy block and its chimney (`_010 Дымовая труба ПСУ`), not the КПП1 checkpoint; `jobs/KPP1/STATE.md` and `REPORT.md` say GeoJSON is deferred by the user | — |

The KPP1 customer GeoJSON does not exist yet (deferred in `jobs/KPP1`); the field comparison below is therefore
built on the two available customer files, with the ELV file (the issue's «RED test … first» reference) as the
primary example.

## Field-by-field: ELV customer file vs our ELV writer (`jobs/elv-tc-vpm/scripts/package_vpm_v006.py`; v005 unchanged except the okrug field)

| Field | Customer (ELV) | Our writer (v006) | Match? | Note |
|---|---|---|---|---|
| `address` | `г. Москва, … вл. 1А; вл. 1А, стр. 1, 2, 3` | same (taken from customer) | ✅ | the TZ doubts the doubled «вл. 1А» (flagged) |
| `okrug` | `ЮАО` | `ЮАО` (v006; v005 had the full name) | ✅ | **«округ» field format** — the customer writes the abbreviation; fixed in `package_vpm_v006.py` |
| `rajon` | `Бирюлёво Восточное` | same | ✅ | |
| `name` | `Торговый центр` | same | ✅ | |
| `developer` | `ООО 'ЛОГИСТИК-СЕРВИС'` | same | ✅ | |
| `designer` | `` | `ООО 'Темпро'` | ⚠️ | data difference, not in scope |
| `cadNum` | `77:05:0010002:6` | same | ✅ | |
| `FNO_code` | `` | `` | ✅ | empty by user decision (SINTEZ issues it later, D220) |
| `FNO_name` | `` | `` | ✅ | |
| `ZU_area` | `10386.0000` (**m²**) | `1.0386` (**ha**) | ⚠️ | **ZU_area units** — the customer writes m², the reg says ha; kept as ha until Artem decides (docs/domain/conflicts.md) |
| `h_relief` | `167.65` | same | ✅ | |
| `h_otn` | `16.22` | same | ✅ | |
| `h_abs` | `183.87` | same | ✅ | |
| `s_obsh` | `8639.11` | same | ✅ | |
| `s_naz` | `8639.11` | same | ✅ | |
| `s_podz` | `` | `0` (`0.00`) | ⚠️ | data difference, not in scope |
| `spp_gns` | `8384.60` | `8384.60` | ✅ | |
| `act_AGR` | `` | `` | ✅ | |
| `imageBase64` | JPG 256×256 | JPG 256×256 | ✅ | |
| `other` | `` | `` | ✅ | |
| `coordinates` (anchor) | `[9676.355, -7135.700]` | `[9676.419, -7136.278]` | ⚠️ | see «anchor point» below |
| `Glasses` | one object keyed by glass material | one object keyed by glass material | ✅ | |

## The three named discrepancies (acceptance)

1. **`ZU_area` units — open source conflict, no side chosen.** The ELV customer writes `10386.0000` (m²), but the
   regulation p.53 table 1 row 10 says «ZU_area — Площадь участка, га» (example `0.5191`, <=4 decimals), and the
   PSU275 customer file writes `6.4882` (ha) — agreeing with the reg. Our writer keeps `1.0386` (ha, per the reg)
   until Artem decides; the three sources are recorded in `docs/domain/conflicts.md` (#48). The issue's
   acceptance («ZU_area units (not hectares)») is therefore *not applied* pending that decision.

2. **«округ» field format.** Both customer files write the abbreviation `ЮАО` (and the reg's own example is
   «СВАО»); our ELV writer wrote the full name `Южный административный округ`. The field carries the standard
   Moscow administrative-okrug abbreviation — applied in the new `package_vpm_v006.py` (the delivered v005 is
   left unchanged).

3. **Anchor point.** The customer writes `coordinates` as MSK-77 `[x, y]` with 3 decimals (the insertion point /
   FBX origin). Our writer already emits 3-decimal MSK-77 (`pivot_coordinates`, `COORD_DECIMALS = 3`); the ELV
   value differs from the customer's only because it re-derives the point for OUR FBX origin (rigid 2D fit
   `t = (-0.064, +0.578) m`). «No change to placement geometry» means the anchor VALUE is not moved; the fix here
   is the FORMAT (3 decimals MSK-77), which the writer already satisfies and the RED test pins.
   Observation (open, DCC-level): the AGR Tools writer takes `plan.pivot_value` = `[centre X, centre Y, floor]`
   from `export.pivot_place`, while the spec (`PKG-24`) and the customer files carry the *insertion point* (FBX
   origin). Whether the GeoJSON `coordinates` must be the origin rather than the centre is a placement decision
   that is not resolved here (and «No change to placement geometry» forbids moving the FBX).
