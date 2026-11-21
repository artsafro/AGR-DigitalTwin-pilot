# Album binding results (#1234)

Produced by `src/dt_ai/album/binding.py` (`python -m dt_ai.album.binding`). Not acceptance; `passed` is false in
every file. Heavy evidence (plotted KPP1 PDF, L01 DXF, its receipt, full outputs):
`G:/Мой диск/AGR-evidence/pdf-album/1234-binding/` + `SHA256SUMS.txt` (round 1, SHA-256 of `SHA256SUMS.txt`:
`5e0b3bf978fbd4881909bc9dc06b88969d317a0bd3ab4df2215bfe33ddca4522`) and `.../1234-binding/round2/` + `SHA256SUMS.txt`
(round 2 = the files here; SHA-256 of `SHA256SUMS.txt`: `259b834258ec68582f440f3476ffd206716052928e3c6e2a769db5bee6ff0fa5`).

Round 2 (review P1-1): a level mark binds only through its own symbol (shelf -> arrow/triangle tip, directly or
through a vertical stem); no tip -> `unbound no_level_line`, two tips -> `level_line_ambiguous`; a mark whose
written value disagrees with the other marks of its view -> `unbound level_value_inconsistent` + D112 finding.
Seconds were measured while other suites ran on this PC (TEC26 has no level marks and still went 7.78 -> 24.73 s).

| Album | Pages | Seconds | Values | axis_pair | level_pair | opening | level | unbound | vertical dims | views | calibrated |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ELV | 18, 19, 23, 26, 31 | 42.72 | 196 | 75 | 1 | 2 | 27 | 91 | 22 | 14 | 0 |
| COD20207 | all 5 | 0.36 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| TEC26 | all 6 | 24.73 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 |

ELV level marks: 27 bound, 38 `no_level_line` (p31: 29 plan marks without a tip; p19: 6; p18: 2; p26: 1). Scale-free
check of the 27 bound marks (least squares of written value vs drawn line y per view): p18-v1 11 marks 105.8 mm/pt,
max residual 4.8 mm; p18-v2 5 / 105.9 / 3.1 mm; p19-v1 3 / 105.9 / 3.2 mm; p19-v2 7 / 105.8 / 4.6 mm.
ELV: p18 vertical `16370` binds as `level_pair -0.150/+16.220`; p26/p31 vertical chains (`52600`, `8400`, `5300`)
bind to letter-axis pairs; p23 `1850`/opening rectangles are unverified rectangles (sign detail; the report's
1180 sign-letter trap stays a human/vision check). COD facades are outlines (one text token, unbound); TEC26 is a
visualization (no values). No view is calibrated: no independent model anchors exist for these albums.

## KPP1 AS.03 L01: DWG -> card-plotted PDF -> binding (independent reference)

DWG `22Е56-АР2-1002-АС.03-R1_L01_без подписей.dwg` sha256 `cb74ba14…f3648` -> DXF via `dwg_to_dxf.py` (receipt) ->
4-page PDF plotted by `kpp1_binding_eval.py` (vector lines + real text). Truth from the DWG model space only.

| Binding class | Truth | Predicted | Correct | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| level text -> its level line (round 1, nearest line) | 97 | 99 | 0 | 0.000 | 0.000 |
| level text -> its level line (round 2, mark symbol) | 97 | 43 | 43 | 1.000 | 0.443 |
| level marks refused `level_value_inconsistent` vs DWG-unverified marks | 2 | 1 | 1 | 1.000 | 0.500 |
| axis label + position | 8 | 0 | 0 | n/a | 0.000 |
| dimension value -> axis pair / opening / level pair | 0 (L01 has no dimension values) | 0 | 0 | n/a | n/a |

Round 2 level marks: 43 bound (all correct), 53 `no_level_line`, 2 `level_line_ambiguous`, 1
`level_value_inconsistent`: page 1 `+3,000`, whose own arrow tip is at model y 3720 mm in the DWG itself (MTEXT at
y 4547 = 3720 + 827, a DIMS line at 3720, none at 3000) - a source discrepancy for the architect (D112), not a
binder error. Calibration with the DWG grid distances as anchors: every view `unknown` (0 matched anchors: no
axis-bound span, because the grid bubbles are not detected in the plot: 0/8 axes).

## Partial acceptance and follow-up

Artem accepted this partial result on 2026-11-12 (card t_e8aff8d9, option (a),
«принимаю рекомендации»), authorizing `Closes #1234` so the album chain can proceed.
This is acceptance of the bounded intake increment, not architectural approval or a complete binding benchmark.
Acceptance item 4 remains only partly measured: level precision 43/43 (1.000), recall 0.443;
axis recall 0/8; dimension precision/recall is not measurable because L01 has no dimension values.
Follow-up https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1254 owns axis bubbles inside block
references, level recall and a dimension truth set from KPP1 AS.03 DWG plotted to PDF and compared with DWG.
Opening identity still needs vision/human review. All existing `passed: false`, unresolved bindings,
unknown scales and mandatory ground-truth/approval gates remain unchanged.
