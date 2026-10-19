# Vatutino MAF — raw-source dimension gate (#313)

Real source-FBX readback, not final NPM/VPM QA or a ready site set.

Blender 5.1.2, headless, factory-startup; 13 copied FBX imports, exit 0, no import errors. Hashes original-before = original-after = copy for 13/13. Full hashes and exact command are in `source-dimension-gate.json`.

Evidence: `C:/x/vatutino-maf/v002-dimension-gate/` (copies, readback.json, source-hashes.json). Metres; referenced vertices in imported world coordinates. Only plan X/Y can swap; height cannot. A known deviation >0.1 m fails even if another size is missing.

Counts: {'pass': 11, 'review': 1, 'fail': 1}. Raw selected-source subtotal × SPOZU counts: 70,546 triangles. NOT an NPM budget result; no light versions exist yet. Gaps and Turnik excluded.

| Row (*T3510) | ID | Schedule L/W/H m | Aligned measured L/W/H m | Absolute deviations m | Verdict | Raw tris × instances |
|---|---|---|---|---|---|---|
| 1 | MAF_0326 | 1.800000 / 0.500000 / 0.720000 | 1.801880 / 0.474434 / 0.800827 | 0.001880 / 0.025566 / 0.080827 | pass | 240 × 5 = 1200 |
| 2 | MAF_0794 | 0.620000 / 0.470000 / 1.050000 | 0.643539 / 0.474806 / 1.063945 | 0.023539 / 0.004806 / 0.013945 | pass | 146 × 48 = 7008 |
| 7 | MAF_0747 | 1.860000 / 1.700000 / 0.790000 | 1.846767 / 1.698105 / 0.802095 | 0.013233 / 0.001895 / 0.012095 | pass | 364 × 4 = 1456 |
| 9 | MAF_0506 | 0.600000 / 1.633000 / 0.930000 | 0.610664 / 1.629719 / 0.933576 | 0.010664 / 0.003281 / 0.003576 | pass | 1460 × 6 = 8760 |
| 11 | MAF_0322 | 0.900000 / 0.600000 / 0.700000 | 0.920166 / 0.572250 / 0.686554 | 0.020166 / 0.027750 / 0.013446 | pass | 724 × 2 = 1448 |
| 12 | MAF_0920 | 2.200000 / 0.300000 / 1.900000 | 2.158081 / 0.267094 / 1.897358 | 0.041919 / 0.032906 / 0.002642 | pass | 678 × 2 = 1356 |
| 16 | MAF_0803 | 5.500000 / 2.000000 / 2.250000 | 5.534317 / 2.031555 / 2.319489 | 0.034317 / 0.031555 / 0.069489 | pass | 4562 × 1 = 4562 |
| 26 | MAF_0677 | 2.740000 / 1.520000 / 0.760000 | 2.740000 / 1.525009 / 0.913130 | 0.000000 / 0.005009 / 0.153130 | review | 8696 × 1 = 8696 |
| 27 | MAF_0219 | 2.280000 / 2.280000 / 0.750000 | 2.282158 / 2.282154 / 0.748656 | 0.002158 / 0.002154 / 0.001344 | pass | 540 × 3 = 1620 |
| 28 | MAF_0127 | 1.090000 / 1.090000 / unknown | 1.708107 / 1.999161 / 2.387311 | 0.618107 / 0.909161 / unknown | fail | 2030 × 4 = 8120 |
| 29 | MAF_0159 | 0.765000 / 0.530000 / 1.065000 | 0.770638 / 0.457466 / 1.000959 | 0.005638 / 0.072534 / 0.064041 | pass | 320 × 25 = 8000 |
| 31 | MAF_0722 | 1.000000 / 1.000000 / 0.600000 | 1.000000 / 1.000000 / 0.600000 | 0.000000 / 0.000000 / 0.000000 | pass | 212 × 16 = 3392 |
| 32 | MAF_0687 | 1.000000 / 1.000000 / 0.044000 | 1.000000 / 1.000000 / 0.047624 | 0.000000 / 0.000000 / 0.003624 | pass | 3732 × 4 = 14928 |

Row 26: Q4 says 760 mm is table-top height. Overall bounds include net (0.913130 m); table-top height still needs measurement: review, not pass.

Row 27: article mismatch 13010/13994 accepted in Q3; no rescaling.

Row 28: MAF_0127 was a candidate for row 13, not row 28. Fresh plan bounds differ from the row-28 specification by 618 and 909 mm: fails D094. Missing height does not erase the failure.

## Remaining questions

- **Q8**: Row *T3510/28: MAF_0127 measures 1.708107 x 1.999161 m vs schedule 1.09 x 1.09 m; deviations 0.618107 / 0.909161 m exceed D094. Which catalogue id should be used, or should this position remain no model? No scaling or substitution performed.
- **Q9**: Turnik is included by Q6: provide its selected library ID or manufacturer/reference and L/W/H for identification; alternatively confirm no model pending a later modelling task.

No final model, atlas, UV-slot or smoothing/normal pass claimed. No source model modified. No regression RED/GREEN claim: only job data/evidence changed; existing readback tool unchanged.
