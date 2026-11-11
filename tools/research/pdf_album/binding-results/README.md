# Album binding results (#1234)

Produced by `src/dt_ai/album/binding.py` (`python -m dt_ai.album.binding`). Not acceptance; `passed` is false in
every file. Heavy evidence (plotted KPP1 PDF, L01 DXF, its receipt, full outputs):
`G:/Мой диск/AGR-evidence/pdf-album/1234-binding/` + `SHA256SUMS.txt`
(SHA-256 of `SHA256SUMS.txt`: `5e0b3bf978fbd4881909bc9dc06b88969d317a0bd3ab4df2215bfe33ddca4522`).

| Album | Pages | Seconds | Values | axis_pair | level_pair | opening | level | unbound | vertical dims | views | calibrated |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ELV | 18, 19, 23, 26, 31 | 14.84 | 196 | 75 | 1 | 2 | 65 | 53 | 22 | 14 | 0 |
| COD20207 | all 5 | 0.21 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| TEC26 | all 6 | 7.78 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

ELV: p18 vertical `16370` binds as `level_pair -0.150/+16.220`; p26/p31 vertical chains (`52600`, `8400`, `5300`)
bind to letter-axis pairs; p23 `1850`/opening rectangles are unverified rectangles (sign detail; the report's
1180 sign-letter trap stays a human/vision check). COD facades are outlines (one text token, unbound); TEC26 is a
visualization (no values). No view is calibrated: no independent model anchors exist for these albums.

## KPP1 AS.03 L01: DWG -> card-plotted PDF -> binding (independent reference)

DWG `22Е56-АР2-1002-АС.03-R1_L01_без подписей.dwg` sha256 `cb74ba14…f3648` -> DXF via `dwg_to_dxf.py` (receipt) ->
4-page PDF plotted by `kpp1_binding_eval.py` (vector lines + real text). Truth from the DWG model space only.

| Binding class | Truth | Predicted | Correct | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| level text -> its level line | 97 | 99 | 0 | 0.000 | 0.000 |
| axis label + position | 8 | 0 | 0 | n/a | 0.000 |
| dimension value -> axis pair / opening / level pair | 0 (L01 has no dimension values) | 0 | 0 | n/a | n/a |

Calibration with the DWG grid distances as anchors: every view `unknown` (0 matched anchors: no axis-bound span).
Failure analysis (open): KPP1 (Revit) level texts sit ~0.8 m above their own level line, so the nearest-line rule
binds each text to the NEXT level line; the grid bubbles are not detected in the plot (0 axes). Both are real
precision failures of the current rules, reported, not tuned away.
