# Issue 1630 — blocked diagnostic checkpoint, not review-ready

## Status

Stopped on the operator's UDIM decision gate before any VPM output. No topology,
source UVs, delivered package or user-owned DCC session was modified. No PR yet.

Branch: `improve/issue-1630-npm-without-material-ids-ids-from-atlas`.
RED test commit: `02a6d246` (two expected missing-feature failures).

## Measured input

Read-only headless intake used Blender 5.1.2, METRIC, scale_length=1.0.
`0707_Garibaldi_22_01.fbx`: one mesh `SM_Garibaldi_22_001_Main`,
148186 polygons/triangles, one diffuse atlas 2048 x 2048.
Copies: `C:/x/npm2vpm-g22/src/`; source hashes: `C:/x/npm2vpm-g22/SHA256SUMS.txt`.

External retained diagnostics:
`G:/Мой диск/AGR-evidence/1630-npm2vpm-g22/t_9d398e0d-v001-01/`:
`intake.json`, `intake.log`, `mesh_ids.json`, `id_table.json`, `apply.log`.
These are incomplete diagnostic artifacts, NOT certified IDs or a delivery.

The existing MAF segmenter returns 184 candidate cells and mixed remainder 5.
31835 polygons assigned; 24347 straddling; 92004 unassigned; ambiguous=0.
These three groups account for all 148186 polygons. This is incomplete coverage.
The MAF flat-block refinement mistakes repeated window details for cells on this
facade atlas; a UV-informed facade extension of the SAME segmenter remains due.
Do not ask Artem to hand-label 184 false cells or accept them as library IDs.

## UDIM decision needed

The assigned subset alone already fails at minimum 512 px/m and 4096 tiles.
Axis/differential measurements preserving the current region layout:

| Provisional ID | Assigned area m2 | Conservative tiles at 512 | Current region UV extent | Required extent at 512 |
|---|---:|---:|---|---|
| 2 | 3268.450133 | 52950 | 0.994148 x 0.997907 | 149.534334 x 352.247991 |
| 3 | 1609.917223 | 656 | 0.999208 x 0.998772 | 40.230999 x 15.996602 |
| 4 | 2888.416552 | 2 | 0.998902 x 0.991844 | 1.039762 x 0.310476 |

Tiles are conservative current-layout estimates, NOT an optimal repacking lower
bound. ID 2/3 also have extreme UV metric distortion; lowering density below 512
is not offered. IDs 182/183/184 exceed the existing regions-mode 1..100 range;
that comes from the unresolved segmentation, not permission to change the range.

Question for the overflowing ID group: recommendation (a) authorize seam cuts
into multiple IDs/tiles after corrected cell segmentation; (b) extra UDIM tiles
per ID; (c) lower texel within 512..1706 (already at 512 here); (d) another policy?
No option has been selected or applied. Body _02 and VPM production stopped.

## Implementation checkpoint

- `tools/library/npm_ids.py`: shared segmenter reuse, centroid classification,
  exact polygon accounting, UV polygon union, manual diagnostics.
- `tools/derive/npm_ids.py` + `agr npm-ids`: new-directory CLI and native intake;
  nonzero on incomplete recovery/gate failure. A blocked gate now forbids native
  apply (regression first observed RED, then fixed).
- `tools/blender/npm_ids.py`: isolated extract/apply boundary; no live bridge.
- `npm2vpm_core.udim_fit_gate`: pure reusable stop check; `plan` returns no parts
  on non-fit; preserves original range/straddle diagnostics.

Failures retained: initial 26 pass / 1 fail showed replaced legacy diagnostics,
fixed by retaining them. Native apply failed with KeyError `atlases` after an
accidental one-line edit during the background run; that line was removed.
No native apply success is claimed. The subsequent regression disallows apply
entirely on a blocked gate. Do not reuse v001 as a successful native receipt.

## Remaining before review

Correct facade segmentation with synthetic patterned-atlas regressions; harden
CLI JSON/index/path/mutation validation and output rollback; improve invalid-ID
area/straddle diagnostics; certify actual output density rather than only
required-fit estimates; run full affected selection and hostile probes. Add the
machine/human npm-to-vpm skeleton, stage hooks and one job config, CAPABILITIES
row (hotspot: PR #1628 first), G22 _01/_02 numbered/wire-colour sheets and native
copy readback. Produce VPM plan/result only under Artem's answered policy.
Author receipts/evals/Agent trace and one PR remain due. This is a checkpoint,
not an acceptance claim. Full suite: deferred to merge batch (rule 68).
