# Placement heights — #1330

## Authority and research (2026-11-13)

[D279] resolves the card's original ground-mark definition in favour of the primary sources.
GeoJSON `h_relief` is **project zero**, not ground elevation at the insertion point.
`ground_mark_m` is a separate optional measured value with its own file/locator source.
No geometry, D262 transform, accepted GeoJSON, source asset or historical receipt is rewritten.

Sources actually examined in attempt 1 (full observations/hashes on Kanban t_0ef657c0):

| Source | Location | Finding |
|---|---|---|
| `standards/source/Rasporyajenies19012026trebovaniya(2).pdf` | physical pp.53–54, table 1 row 11; text extraction AND rendered pages | `h_relief`: «Нулевая отметка, м. Не более 2 знаков после точки»; «Указывается единая нулевая отметка согласно проекту АГР». SHA256 `933f6b700c074d0db6b82030fc79d1dbe9db4a0067495ca716e0636acd544222` |
| `C:/Users/artsafro/Downloads/Telegram Desktop/geojson ТЭЦ 26.xlsx` | `Данные GEOJSON`, B12, J1/J12/J13/J14 | B12 also defines zero, J1 Central checkpoint, heights 169.65 / 8.95 / 178.60. SHA256 `30a9c143d0241b3a06a604a8f296ce9630776122f7460124cfce33265576c598` |
| `jobs/KPP1/site-1255/REPORT.md:20,39–44,73–74` | Revit level `отм. 0,000`, D262; relative VPM frame | Chosen zero 171.050; relative top 8.65. Cached observation, RVT hash unavailable, NOT a fresh Revit measurement |
| `jobs/TEC26-OKS/census/sources.json` | text layers of its four source PDFs, examined directly from Desktop when C:/x copies were absent | No height-system name found in the searched text; this does not prove absence in scanned drawings |
| Silikatny #1315 | https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1315#issuecomment-6854271480 | Choose zero from the ±0.000 tie in PZU/VP_5, use design marks rather than existing paired marks. Does NOT determine height system |

Neither the supplied regulation nor the examined customer sources establish BSV-77/Baltic 1977
for these jobs. `MSK-77` is horizontal CRS evidence, not a vertical-datum certificate.
**Result: `height_system="unknown"` for KPP1/TEC26.** This is not a general assertion that Moscow
uses an unknown system. Question retained for Artem/customer: which survey/title-sheet statement
identifies the vertical system for TEC26/KPP1 and Silikatny? D279 explicitly permits unknown meanwhile.

## KPP1 provenance table and recomputation

| Quantity | Value, m | Provenance / use |
|---|---:|---|
| Selected project zero | 171.050 | `26_КПП1_АР_МЭП_RVT22.rvt`, `отм. 0,000`, cached `jobs/KPP1/object.json`, D262; used |
| Alternative customer project zero | 169.65 | TEC26 XLSX `Данные GEOJSON!J12`, column Central checkpoint; retained here, NOT a ground mark and NOT used |
| Customer relative / absolute height | 8.95 / 178.60 | XLSX J13/J14; retained together, not mixed with R1 geometry |
| ±0.000 in local FBX frame | 0.000 | site-1255 REPORT Applied transform: VPM rotation only, relative Z |
| R1 model top | 8.65 | REPORT GeoJSON heights; fresh immutable final-FBX readback below |
| Ground at insertion | unknown | No surveyed mark supplied; omitted, not fabricated as 0 or 169.65 |
| Computed h_otn / h_abs | 8.65 / 179.70 | shared `height_values(171.05, 0, 8.65)` |

The difference 1.40 m between zero candidates is **not a correction** and is never averaged.
The selected datum is machine-readable in `jobs/KPP1/site-1255/height-datum.json`.
The KPP1 placement producer now derives height properties from the render-mesh top and this datum,
using the same dependency-free arithmetic as Placement (Blender does not ship Pydantic).

Fresh read-only Blender 5.1.2 import of
`G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v004/SM_Kpp_1.fbx` returned render Z
`[-0.0000022736053324479144, 8.650001525878906]`; rounded heights remain
171.05 / 8.65 / 179.70. This confirms the R1 top, not a survey or delivery pass.
Historical export_meta bounds are absent: the new Z comparison truthfully returns **not_run**.

## Contract and migration

`Placement.coordinate_system` remains `SYNTHETIC_LOCAL | MSK-77`.
Ground export now rejects arbitrary labels before outputs; its default is the canonical `MSK-77`.
Do not pass descriptive prose as a CRS; keep that prose in source provenance.

When `project_zero_m` is numeric, both `height_system` and `height_source` are mandatory in the
model AND generated JSON Schema. Systems: `BSV-77`, `Baltic 1977`, `MSK local`, `unknown`;
the first two are supported source labels, not automatic equivalence/conversion.
A height source has nonblank `file` and `locator` (sheet/cell, handle, page/level).
`project_zero_fbx_z_m` and `project_zero_fbx_source` travel together; so do
`ground_mark_m` and `ground_mark_source`. No fallback to the terrain mark.

Formula, metres in the exported world frame:

```
h_otn = model_max_z_m - project_zero_fbx_z_m
h_abs = project_zero_m + h_otn
h_relief = project_zero_m
```

Round only final GeoJSON properties to two decimals. Nonfinite/bool/string operands and tops
below project zero fail. Offset zero must be explicit; the formula does not assume it.

Shared `dt derive package --object object.json` now needs `{"name": ..., "placement": <Placement>}`.
Bare legacy `h_relief` fails naming the object path and missing `placement`; migrate explicitly,
never fabricate its provenance. The old `export_meta.h_otn_model_max_z_m` key retains its historical
name but supplies the **FBX-frame top**, not height above a possibly offset ±0.000.
`--no-geojson` stays available and byte parity is tested. Unknown height system is a package blocker.
Historical job-local packagers/receipts remain historical, not automatically certified by this change.

## Export/readback Z QA

`scene_findings(..., export_meta=<one FBX record>)` adds V013 `Z bounds vs export_meta` for NPM
and VPM render meshes, excluding UCX and lighting. Full-precision min AND max are compared;
absolute difference must be **strictly below 0.001 m** (exact threshold fails closed).
This is an explicit numerical readback budget, not permission to shift project heights.

CLI / ZIP validation:

```
uv run python tools/qa/validate_package.py SM_Address.fbx --scene --export-meta export_bounds.json --json
```

`export_bounds.json` is a mapping by exact FBX filename, each record containing
`bounds_m: [[min_x,min_y,min_z],[max_x,max_y,max_z]]` and `fbx_sha256` of the exported bytes.
Bounds must come from the export, not be copied from readback to manufacture agreement.
Hash mismatch, null/partial records, unmapped filenames, malformed/nonfinite/reversed bounds,
missing render-mesh bounds, empty geometry or duplicated mesh names fail.
Missing metadata entirely is **not_run**, never pass. The CLI binds records to the byte snapshot
it stages for Blender; the function-only comparison assumes the caller supplied that same frame.
A Z-bounds pass is neither absolute-height-system confirmation nor user acceptance.

For Silikatny #1315: no numeric zero or geometry is selected here. Its chosen PZU/VP_5 zero must
be recorded with source, relative FBX datum and explicit unknown system until survey evidence exists.
