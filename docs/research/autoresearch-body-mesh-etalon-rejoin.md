# Standing #26 — G22 etalon representation check (OBSERVE)

## Frozen contract

Continue #25 (`f3d45af6`) and #1619's [band harness](body-training-1619/band_compare.py) at base `4065515ca7be9a13d669099d72dbf913d2f084da`. R3–R6 did not clear accepted controls; a production body-core candidate cannot be judged by that penalty. #1736 owns the shared builder; #1649 owns atlas seams; #1609 owns KPP1 corners; #1315/#1622/#1738 and #1608 own cold runs; #1615 owns suite timing. No tooling speed target is needed.

One metric: maximum across G22 k1–k3 of the median of three paired ratios **post-rejoin triangles / raw triangles**. Diagnostic target ≤0.10 (at least 90% fewer triangle polygons in each band). Even a pass keeps no code and does not identify original editable faces. A ratio above threshold also leaves R3 rejected. The measured lever is the existing #1618 diagnostic rejoin (1°/1°, material boundaries preserved), OFF vs ON, not a novel rejoin algorithm or scorer.

Fixture: #1618 paired raw/rejoin NPZs under `C:/x/ev_1618/`, world metres, all vertices of each face in the same #1619 z band ±0.01 m, no extra orientation mask. Use #1619 polygon unpacking, not D338's facade-only count.

| Corpus | NPZ | SHA-256 | z interval (m) | #25 parity band |
|---|---|---|---|---|
| k1 | `g22_01/SM_Garibaldi_22_001_Main.npz` | `e7bb542f36ba390dc409145c04539b63785d0c0d26bc7ee67d20d79ba4ab5fbb` | 217.64–262.64 | `r2/etalon_k1.mq.json` |
| k2 | `g22_02/SM_Garibaldi_22_002_Main.npz` | `79838f9ebf6783af3d22e3fb68a0b3f28a383ccc300d3e148493646ace28b802` | 217.64–244.64 | `r4/etalon_k2.mq.json` |
| k3 | `g22_02/SM_Garibaldi_22_003_Main.npz` | `2a42c8a80967df071bb8e237b5d729b7051b87a0a7c4abe888c8d6d6bad04a9c` | 217.64–262.64 | `r1/etalon_k3.mq.json` |

Hash-check all six inputs before and after (JSON hashes from #25). Clean: post-rejoin vertices and indexed face lists equal the #25 band JSON exactly after #1619's six-decimal conversion; accepted-control triangle counts agree with #25; paired spread must be zero; raw bands must be nonempty and triangulated. Injected: wrong input hash must fail closed. Not measured: fresh DCC or original quad master, semantics of remaining triangles, 63B/KPP1 recalibration, builds or delivery checks. Counts of two representations, not an ID-level survival or authorship claim; clipping is independently applied to each representation so faces straddling the band edge may be counted differently.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-etalon-rejoin-harness/replay.py C:/x/ev_1618 C:/x/ev_1619 NEW.json`.

Budget: one confirmation of stored rejoin (#25) paired with its raw control, zero new candidates, three reads per pair; stop on one complete receipt, provenance/parity failure, or 3 minutes. No retuning, test deselection, weakened QA checks, changes to geometry, delivered packages, production code, or other cards’ files.

## Round log

**Итог OBSERVE: после диагностической сшивки в полосах эталона G22 осталось 4,73–8,10% от исходного числа треугольников.** Сравнение сырого NPM-экспорта с quad-мастером смешивает качество сетки с триангуляцией экспорта. Сшивка не доказывает, что оставшиеся треугольники были в редактируемом оригинале или являются дефектами. R3 не возвращаем; оценку и построители не меняли.

| G22 | Raw triangles | Rejoined triangles | Median ratio | Paired spread |
|---|---:|---:|---:|---:|
| k1 | 95,473 | 7,733 | 8.10% | 0 |
| k2 | 33,623 | 1,589 | 4.73% | 0 |
| k3 | 33,929 | 1,873 | 5.52% | 0 |

Worst median 0.08099672158620762 ≤ 0.10. Frozen before measurement in `ba769594`. Receipt [r26.json](autoresearch-body-mesh-etalon-rejoin-harness/r26.json) SHA-256 `c97ab1ff15280a9d0b2d30a56e1cc271deaff6e8ed10edddd3e211d3e0882649`; replay.py SHA-256 `aa6306f5717b46e851247dca9d5d596740bd98cc5b9f3a32398c71d2ad6200a3` (Git LF).

- **Clean:** pre/post input hashes, exact vertex and indexed-face parity with #25, three identical paired reads in every band. Scorer tests: `../../.venv/Scripts/python.exe -m pytest -q --basetemp=C:/x/t_48e6edb8-pytest tests/qa/test_mesh_quality_score_1616.py` → 291 passed. First invocation without a private basetemp collided with concurrent guard pytest (290 passed, 1 setup error); full affected selection passed with isolated basetemp.
- **Injected:** replace k1's expected NPZ hash with 64 zeros; `measure()` raises `ValueError: input hash mismatch` before reading geometry.
- **Not measured:** fresh native readback, editable-source topology, role of residual triangles, new metric calibration on 63B/KPP1, builder changes or delivery checks.
- **Would change:** require a representation check for the next local-penalty experiment. Do not exempt or penalize residual triangles as a class until their placement separates accepted G22 from rejected models.
