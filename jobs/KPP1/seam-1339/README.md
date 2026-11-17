# KPP1 roof/parapet seam on K01 (#1339)

R6 step 4 ([recipe](../../../docs/procedure/node-r6-oks-body-facade.md)) is applied to a copy of the K01
etalon. Pattern: [roof-inset-plane](../../../docs/domain/patterns/roof-inset-plane.md) [D038, D039].

- Etalon copy: `SM_Kpp_1.fbx` (KPP1 v007 VPM, the K01 etalon of `benchmark/bench-k01-kpp1`), sha256
  `5b0869a1f989fe9cfc98fb8c89c874f097b42fb7bd3571138a73700941bf6238`. Its spec reads plates 5 / 20 mm and the
  parapet 0.741 m, the same as spec v030 of v007 in `jobs/KPP1/STATE.md`.
- Command (engine on `origin/main` 8eb39d48 + this branch, Blender 5.1.2):
  `uv run python jobs/KPP1/seam-1339/measure_roof_seam.py --etalon <copy>/SM_Kpp_1.fbx --output C:/x/ev_t_69ac6dc4/seam-v002`.
  Exit 0.
- Committed result: [`seam-report.json`](seam-report.json). The full run folders (dumps, FBX, blend, reports)
  are in `G:/Мой диск/AGR-evidence/1339-roof-seam/` with `SHA256SUMS.txt` (28 files).

Both variants run the full K01 pipeline (`tools/qa/run_benchmark.py`). Only the engine's roof differs:
**welded** (before) has the roof inside the parapet welded to the parapet foot, which is one changed engine
line held in memory. **separate** (after) is the engine as it stands: the roof is its own plate 5 mm above
the hole, with its border 20 mm under the parapet. All numbers are read back from the exported FBX.

| K01 KPP1, body mesh | welded (before) | separate (after) |
|---|---|---|
| quads (all quads, 0 n-gons) | 2 361 | 1 592 (-32.6 %) |
| roof-band triangles (horizontal, within 20 mm of 7.909 m) | 1 274 | 2 (one plate quad) |
| T-junctions (0.1 mm) | 0 | 0 |
| open edges | 132: bottom ring | 238: bottom 121 + hole at the parapet foot 113 (7.909) + plate outline 4 (7.914, gap 0.005, embed 0.020) |
| non-manifold edges / vertices, overlaps | 0 / 0, 0 | 0 / 0, 0 |
| `slabs_not_inset` | 1 (solid slab, D038) | 0 |
| K01 `mesh` check | **fail** | **pass** |
| K01 model checks failed | bbox, silhouettes, mesh | bbox, silhouettes |

In the welded variant the engine carries every facade cut across the roof (`_propagate`). That gives no
T-junction, but the roof becomes 637 quads instead of 1. This is the same cascade that PSU275's seal ran
through (29k → 60k faces; `jobs/PSU275/STATE.md`, mesh clean-up v009).

## K01 step result

The K01 run stopped at "the face at 8.65 m between x 0.225 and 0.38 is no trapezoid"
(`benchmark/bench-k01-kpp1/README.md`; the 2026-10-12 runs in `C:/x/cr-76`). On `origin/main` 8eb39d48 that
stop no longer occurs: the engine builds the KPP1 spec, and the parapet/roof step passes the `mesh` check
with the separate plate. K01 as a whole is still red. The model fails `bbox` (3.78 m against 0.05 m) and
`silhouettes` (IoU 0.771 against 0.97). The etalon's bounding box, (-2.02, -2.02, -1.2) to (31.33, 12.73, 9.925) m, reaches
beyond the 27.66 x 11.66 m body to parts the engine does not build. The etalon-self failures listed in the K01 README are unchanged. Neither
of these belongs to the roof/parapet seam.

KPP1's own job model already uses the separate plate since v007, when the job was brought to the inset rule
(`jobs/KPP1/STATE.md`, "v007: inset roof"): Main went from 12 456 to 12 149 quads, and T-junctions stayed at
17, as in v005, because they are unrelated to the roof.
