# #1371 — delivered customer project intake; NOT PASSED (decision D288 applied to VPM v008)

## Краткий итог

**Решение Артёма 2026-11-14 «Принимаю рекомендации» записано как [D288] и применено:**
новый VPM `package-v008/SM_Kpp_1.zip` (db4bef46…) несёт суммы проекта
s_obsh = s_naz = 27124.36, spp_gns = 28480.58 и FNO 013 006 005 / «Объект
электроснабжения иного типа» из заказного `_002`; s_podz пуст (неизвестен), высоты R1
171.05 / 8.65 / 179.70 сохранены. Остальные 22 члена ZIP байт-в-байт как v006.
`validate_package --scene` VPM: V011 6 fail → 1 fail (только s_podz); итог `passed=false`.
NPM в v008 не пересобирался: Ground заказчика по D288 не готов (граница/привязка/исправления
согласуются отдельно). Сверка FNO в SINTEZ и quad master/F26 остаются открытыми.

Исходная разведка (до решения):
КПП найден: **VPM `_002` = первые два объекта NPM `_02`** (Main + MainGlass),
а не NPM `_01`. Это прежняя заказная версия, **не наш R1**: высота оболочки
11.08 м против 8.65 м R1. Из копий извлечены КПП и диагностический фрагмент Ground;
геометрия/UV/материальные привязки проверены повторным открытием 4/4 файлов.
Все проверенные FBX триангулированы — quad master они не заменяют.

**Важное исправление трактовки:** регламент, стр.54, строки 14–17, прямо требует
суммарные площади **всех зданий проекта АГР**, а не отдельного КПП. Ранее записанное
требование KPP1-specific areas противоречит этому тексту. Значения не применены:
нужно одно решение Артёма ниже. Ground — заказной источник, но ещё **не готовый
Ground нашего пакета**: координаты локальные, полный NPM Ground имеет 180934
треугольника при лимите 180000 и дополнительные ошибки. В новом диагностическом
package-v007 V001 стал pass, но итог `passed=false`; это не закрытие доставки.

## Scope and evidence

Cells: `oks-vpm`, `oks-npm`, interface `ground-npm`. Level: standard.
Base inspected: `origin/main` bd842f97 (#1305/#1278); acceptance not already met.
No model repair, new authority, waiver, live-scene edit, upload or signature.
Blender **5.1.2**, factory-empty background, disabled autoexec, one thread.
Max ping found live Max 2026; it was not touched. Original ZIPs are read-only inputs.

Evidence root: **`G:/Мой диск/AGR-evidence/1371-kpp1-delivered/v001/`**.
`SHA256SUMS.txt` there seals copies, diagnostics, reference scenes, drivers and logs;
local [evidence index](evidence-SHA256SUMS.txt) pins it. No binary/LFS added to git.
[properties.json](properties.json) retains every GeoJSON property except the long
image payload (length/hash instead); exact original GeoJSON bytes remain in evidence.
[mapping.json](mapping.json) contains numerical bounds, dimensions, convex envelopes,
UV hashes and the diagnostic frame bridge. Raw complete per-object census is external.

## 1. Verified archive provenance

Source directory: `G:/Мой диск/AGR-assets/KPP1/delivered-customer-2026-11-14/`.
All three archive hashes match the delivered `SHA256SUMS.txt` before/after processing.

| Archive | SHA-256 |
|---|---|
| `0607_77_05_0009005_117.zip` | `91804ecdb1fe9aac917bda34bc3342e55bc9fc117dc7c12dd01201069a6858fa` |
| `SM_77_05_0009005_117_002.zip` | `caef3a21acdb8aee1fee9e496e26bd9f9adaeef2a17272e8189bb634aee13ecf` |
| `SM_77_05_0009005_117_Ground.zip` | `a7dc3745ac587f9669e14d7020182495058eb648434006ad6269ea66b792f778` |

137 archive members inventoried; FBX/GeoJSON and all VPM PNGs copied without edits.
Important member hashes:

| Member | SHA-256 |
|---|---|
| NPM `_02.fbx` | `5a5ba8447ee101cbc3f8d92bda1f5a7f6f6bc95a051a1b091069f07309b5f15c` |
| VPM `_002.fbx` | `5286f9897dad10c12c530366e3d9aa89095e8f21c2b7708ca707307bc2117778` |
| **NPM `_Ground.fbx`** (package diagnostic source) | `d8770f4796c8d68847af7b08f6b156d0d0fdd11809de3a1b44479747cab1aebd` |
| VPM `_Ground.fbx` | `02421605fe541c506f0a0587c4d6520d0a3d7925bbe4d5e4e88e33f73ad6cd21` |

## 2. Object mapping, not revision equivalence

Render meshes only; collisions excluded. Bboxes are world-axis-aligned in each file's
own imported frame; convex envelopes are geometric footprint **envelopes**, not floor
areas, usable areas or a regulatory area schedule.

| File / subset | XYZ bbox size, m | Render triangles | XY convex envelope, m² | Mapping |
|---|---|---:|---:|---|
| NPM `_01`, both meshes | 178.112 × 124.602 × 105.991 | 145556 | 15735.266 | PSU275/main industrial assembly incl. tall context, not KPP |
| NPM `_02`, objects 0/1 only (`..._002_Main`, `..._002_MainGlass`) | 33.235 × 16.305 × 11.081 | 25130 + 64 | 432.700 | KPP customer reference; other 10 meshes are other OKS |
| VPM `_002`, Main + MainGlass | 33.230 × 16.331 × 11.079 | 26198 + 64 | 432.710 | Same KPP building, different export/tessellation; 72 additional UCX meshes |
| Our R1 package-v006 NPM | 31.898 × 14.512 × 8.650 | 18332 + 504 | 373.316 | Current R1, not substituted |
| Our R1 package-v006 VPM | 32.111 × 14.868 × 8.650 | 29980 + 504 | 380.454 | Current R1; 4 UCX excluded |

Identification evidence beyond labels: the delivered NPM `_002` pair has **13894
vertices** and **exactly identical two triangle-index arrays** to the D262 customer
reference `fc08774a...`, recovered fresh from its original hash-pinned ZIP
`219524ea...` (the historical NPZ was absent). Indexed rigid fit across both meshes:
median residual **0.0000434 m**, max **0.008824 m**, determinant positive. This is the
already-used KPP reference in a different coordinate frame, not a new R1 fit.
The small residual/outliers are retained; not claimed byte-identical geometry.
VPM and NPM KPP differ by 1068 opaque triangles; neither replaces accepted R1.

PSU275 comparison authority: `docs/sources/psu275.md` and `jobs/PSU275/STATE.md`:
main axes 108 × 93 m, body top 65.960 m, chimney/context to roughly 99 m or more;
KPP's R1 upper rectangle is 27.66 × 11.66 m. This rejects `_01` as KPP.
**A fresh readback of the historical accepted PSU275 master was not measured**:
`jobs/PSU275/outputs/delivery-v003` is absent in the pilot and checked source checkout.
The `_01` attribution is assembly-level, not certified equality to that old master.

## 3. Ground: provenance is established; approval/readiness is not

NPM has three render meshes: surface **18891**, GroundEl **51681**, Flora **110362**
triangles, total **180934**. VPM is one combined render mesh **315805** triangles
plus **702** UCX objects. Both envelopes: about **462.286 × 267.596 m**.

The shared delivered-local frame places KPP at X 82.784..116.019,
Y 85.002..101.308 m. Ground triangles intersect that region. Whole triangles
intersecting the XY bbox of KPP's convex envelope + **2 m diagnostic context** were
extracted: **282** NPM surface triangles, **2497** VPM combined triangles.
This chosen context is a labelled research AOI, **not an approved package boundary**.
Projected ground-envelope intersection 432.700 m² and 2 m ring intersection
150.760 / 182.182 m² are XY diagnostics including any projected skirt/bottom;
**not proof of top-surface support, complete landscaping, hole clearance or 3D coverage**.

Current R1 NPM is absolute MSK-like X~8056, Y~-9581, Z=171.05..179.70;
delivered Ground is local X~-231..231, Y~-129..138, Z~-4..36. Consequently an
unchanged Ground cannot spatially complete the current absolute NPM by name alone.
The indexed KPP frame bridge suggests translation
[7956.505245, -9674.557472, 169.679744] and about -0.03324° plan rotation
(exact row-vector rotation in mapping.json). **Not applied** to Ground, not an
approved survey transform or permission to change D262/D279; ground mark is not R1 zero.

New `package-v007-diagnostic/0000_Kpp_1.zip` retains the R1 member byte-for-byte and
adds the **unchanged full NPM customer Ground bytes**, renamed only at ZIP member
level to `0000_Kpp_1_Ground.fbx`. VPM ZIP stays byte-identical to v006.
This deliberately demonstrates the composition-only V001 improvement and actual
new scene failures. It is **not** an approved/customer-ready KPP package or a repair.
No Ground clipping, reprojection, retopology, naming repair or flora deletion applied.

## 4. Attribute proposal (applied in v008 after D288; see §7)

Both source GeoJSONs contain one ObjectFeature. Contrary to the opening shorthand,
Ground attributes are **not all empty**: address, organisations, cadastral number,
project name and ZU_area are populated. Ground also has the unexpected key
`Наименование GeoJSON-файла`; it is not copied into our schema.

| Field | Delivered `_002` | Proposed KPP1 handling / source |
|---|---|---|
| address | проезд Востряковский, вл. 10 | Retain current address; customer + reg p.53 row 1 |
| okrug | ЮАО | Retain; customer + row 2 |
| rajon | Бирюлево-Западное | Retain; customer + row 3 |
| name | Whole energy-project title | Retain `Центральная проходная` for KPP object; row 4 names object |
| developer | ООО 'Развитие генерации ТЭЦ-26' | Retain; customer + row 5 |
| designer | ООО 'Аспект' | Retain; customer + row 6 |
| cadNum | 77:05:0009005:117 | Retain project parcel, not a new building cadastral ID; row 7 |
| FNO_code / FNO_name | 013 006 005 / Объект электроснабжения иного типа | Source precedent on the delivered KPP `_002`, not merely PSU275. Rows 8/9 describe object's function, not an area total. Recommend accepting this customer reference for KPP pending confirmation against SINTEZ [D220], not silently issuing a new code |
| ZU_area | 6.4882 | Project parcel total in **ha**, explicitly total AGR area, p.53 row 10 / D223; retain |
| h_relief | 0.26 | Reject substitution: p.53 row 11 continued p.54 says unified project zero; retain **171.05** selected by D262/D279; height system still unknown |
| h_otn | 8.95 | Retain **8.65** for current R1 [D262]; source belongs to prior delivered geometry/attributes, not current R1 |
| h_abs | 178.6 | Retain **179.70** for current R1; do not combine with customer heights or infer ground datum |
| s_obsh | 27124.36 | Recommend project total **27124.36 m²**, not KPP-only schedule: p.54 row 14 explicitly sum of ALL buildings; requires decision because prior KPP docs/D285 continuation demand KPP-specific areas |
| s_naz | 27124.36 | Same project total **27124.36 m²**, p.54 row 15 |
| s_podz | empty string | Row 16 requires total underground parts of ALL buildings; unknown stays empty/fail, **not zero**; project-wide schedule/authority still needed |
| spp_gns | 28480.58 | Recommend project total **28480.58 m²**, p.54 row 17 explicitly all buildings; do not derive from envelope area |
| act_AGR | empty string | Retain absent information, row 18 / D011 |
| imageBase64 | 17100 characters | Keep current real R1 thumbnail, not historical object image; row 19 requires object image |
| other | empty string | Keep current approximate-placement disclosure D262; optional field |
| coordinates | [99.608, 93.322] | Customer **local** point, not MSK-77. Keep current [8056.144, -9581.270], approximate D262; p.55 row 21 |
| Glasses | One material, RGB 135/136/146; transparency .38, IOR 1.13, roughness .06, metallicity .84 | Historical material reference only; keep R1's measured glass/names, not silently transfer values |

Regulation physical pages **53 and 54 rendered and visually read**; images in evidence
`regulation/53.png`, `54.png`. Exact row 14/15/17 wording:
**«Указывается суммарная площадь всех зданий согласно проекту АГР.»**
Row 16: **«Указывается суммарная площадь подземных частей всех зданий согласно проекту АГР.»**
This is a real conflict with `site-1255/REPORT.md` and `package-1278/latest/REPORT.md`;
those files/decisions were not silently rewritten. NPM requires no GeoJSON (PKG-19).

## 5. Quad / tri and reproducible references

All **818775 polygons** across the **7** measured FBX scenes (including R1 comparison
scenes and collisions) have exactly 3 vertices; **0 quads / n-gons**. Lighting FBX was
inventoried/metadata-read, not mesh-censused. KPP VPM: 26262 surface + 960 UCX triangles.
NPM `_01`, `_02`, Ground and VPM `_002`/Ground are delivery exports, **not masters**.
Triangulated delivered precedent is expected for delivery V003; it does **not** waive
the non-triangulated work-FBX requirement [D198], Max quad-review preference [D270],
quad dimensions [D021] or close F26. Recommendation: keep F26/master check open.

Body VPM UV uses observed tiles **1001–1016**, glass remains in 1001. The archive
actually supplies Diffuse/**ERM/Normal**, all 16 tiles each (not just Diffuse/ERM).
NPM KPP body/glass UV are in 0..1; names/material lists and exact UV hashes in census.
FBX metadata: binary **7400**, UnitScaleFactor **100** (metres in FBX centimetre units),
Z up; source Creator says **Blender 5.2.1 LTS / FBX IO 5.15.0**. That string is file
metadata, not the installed runtime (5.1.2) or a recoverable full exporter preset.
No reconstruction of unknown exporter toggles is claimed.

Four isolated `.blend` references under `references/`: KPP NPM pair, full KPP VPM
(74 objects), NPM Ground AOI, VPM Ground AOI. A fresh Blender process reopened each
and compared **geometry + per-corner UV + material name + winding**, preserving
object names; **4/4 pass**, respectively **25194 / 27222 / 282 / 2497 polygons**.
Comparisons round world coordinates/UV to 7 decimals; no visual/material acceptance.
All texture PNG bytes are copied beside the original copied FBX; `.blend` references
are geometry/UV diagnostics, not certified texture relinking/rendered deliverables.

## 6. Validation and test boundary

[CHECKS.md](CHECKS.md): fresh `validate_package --scene --json`, before v006 and after
v007 diagnostic; both NPM exit **1**, VPM unchanged ZIP exit **1**, `passed=false`.
Static-only NPM after exits **2**: composition success is not delivery success.
696 affected tests passed, 18 deselected, 8 existing nonfinite-clearance warnings:
`uv run pytest -q tests/qa/test_validator.py tests/qa/test_scene.py -p no:cacheprovider --basetemp=C:/x/t_3c059f27-affected2`.
No production/test code changed; no bug fix or RED/GREEN claim, no full suite required
by this card's evidence-only conditional. Scratch drivers/logs are sealed externally.
Initial missing old NPZ was recovered from original pinned ZIP; initial nonexistent
`test_master.py` selector ran no tests and was corrected; parity driver first rejected
slotless UCX, then explicitly represented absent collision material as None and passed.
No checker was weakened and no source was repaired to make findings pass.

## One question for Artem — answered: «Принимаю рекомендации» → [D288]

Вопрос (сохранён без изменений как запись):
Подтверждаешь такой единый набор решений по найденным источникам: **площади КПП
заполняем суммами проекта** 27124.36 / 27124.36 / 28480.58 согласно стр.54
регламента (тем самым отменяем прежнюю трактовку KPP1-specific); `s_podz` пока
оставляем неизвестным — нужна суммарная подземная площадь проекта, не выдуманный 0;
FNO 013 006 005 / «Объект электроснабжения иного типа» принимаем как заказной
референс именно найденного `_002` с последующей сверкой SINTEZ; **R1 сохраняет
171.05 / 8.65 / 179.70**, не 0.26 / 8.95 / 178.60; Ground пока считаем только
заказным источником, а не закрытым delivery gate, и согласуем отдельную производную
копию/границу и её привязку к абсолютному R1 вместо подмены нулевой отметки?
Рекомендую этот вариант; quad master/F26 не снимать по триангулированным экспортам.
По завершении этапов открывать тебе сцену для приёмки?

## 7. After D288: VPM package-v008 (attribute-only)

Command (new destination; refuses existing output, `.partial`, input aliases, hash drift):

```bash
uv run python jobs/KPP1/delivered-1371/build_v008.py \
  "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v006/SM_Kpp_1.zip" \
  "G:/Мой диск/AGR-assets/KPP1/delivered-customer-2026-11-14/SM_77_05_0009005_117_002.zip" \
  "G:/Мой диск/AGR-evidence/1371-kpp1-delivered/package-v008"
```

Inputs pinned: v006 VPM 6c6b03b4…, delivered `_002` caef3a21…. Output `SM_Kpp_1.zip`
db4bef46…, `SM_Kpp_1.geojson` fbf4665f…, `assembly.json` 4341c755… (index: evidence-SHA256SUMS.txt).
Exactly five GeoJSON lines change (FNO_code, FNO_name, s_obsh, s_naz, spp_gns); property order,
CRLF bytes, heights, s_podz, image and the 22 other ZIP members stay identical. The builder
fails closed on empty/NaN/inf/negative/>2-decimal areas, non-empty delivered s_podz, an FNO pair
absent from the classifier, or an already-filled base (`tests/jobs/test_kpp1_delivered_1371.py`).

| VPM `--scene` | v006 = v007 (byte-identical) | v008 |
|---|---|---|
| exit / passed | 1 / false | 1 / false |
| V011 fail findings | FNO_code, FNO_name, s_obsh, s_naz, s_podz, spp_gns empty | s_podz empty |
| other stages | V001/2/5/7/8/9 pass; V004/V012 review; V003/V010/V013/V015-17 not_run | identical |

Still open: s_podz (project underground total), SINTEZ FNO cross-check [D220], Ground
boundary/placement/fix authority and NPM Ground [D288], quad master F26 / V003 [D198].
Original evidence and failed statuses in v001 stay immutable.
