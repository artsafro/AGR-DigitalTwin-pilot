# Sokolniki NPM v002 — diagnostic delivery FBX copy (#2098)

**Not ready for delivery.** [D438] confirms UCX/GeoJSON are not required without a customer spec. [D439] authorizes only the seam snap on the delivery FBX copy. Accepted body v006, assembly v009, the work FBX, and v001 evidence were not edited. The v001 ZIP member, not the standalone `share` FBX, was the input.

- `0000_Sokolniki_UVK1000_01.fbx` input SHA-256: `5b9b42a65c96e63f5732e16aed2ec80bd3bd8085aafad5e7a9e0f839f18ae973`.
- Diagnostic v002 FBX SHA-256: `bbbd6bb96981b25ec78f4fbd45d70a03d864e508b3bede5229b5c097bfb6b58d`.
- In `SM_Sokolniki_UVK1000_001_Main`, the D|N mismatch at +13.50 m was closed by moving **344 vertices along Z only**, max **0.901222229 mm** (limit 1 mm). Eight xView vertex pairs at 0.900269 mm now have exactly 0 mm separation; the two already coincident pairs were unchanged. There was no weld or face deletion. At +14.30 m the two Z levels differ by about 0.000954 mm, not 0.9 mm; a trial aligning them did not improve xView or V004, so that edit was discarded.
- Raw comparison: all decoded FBX fields except the affected vertex coordinate array are identical (including winding, UVs, normal layers, materials, embedded images, transforms and the glass mesh). Fresh Blender 5.1.2 imports confirm exact indexed loops, XY, object origins and glass parity; no zero-area triangles added.
- `archive_diff.py` was run before packing. The only reported error was pre-existing `M_Glass_01.001` (the same material name in v001 and v002); no new ZIP was built. Do not rename the glass material or deliver the diagnostic FBX without approval.

| Check | Measured result | Evidence / limits |
|---|---|---|
| V001 | **Fail**: 1 FBX, 0 Ground (minimum 2 FBX for the ZIP) | Fresh check of v001 ZIP; the v002 member list independently fails the same two composition rules without building a ZIP. Single-file V001 stays `not_run`. No new package manifest. No MSK-77/DWG placement verification (V014 / V017); survey placement was not part of the snap. |
| V002 | Pass | Binary FBX 7400, 100 cm/unit, mesh scale 1:1. |
| V003 | **Fail on unchanged work FBX**: 123 n-gons, 1,462 T-junctions (review) | The delivery FBX itself is fully triangulated (31,497 tris); work face IDs/centroids are in `sheet-01-v003-ngons.csv`. |
| V004 | **Fail**: 49,887 → **49,889** self-intersections; aggregate 49,901 → 49,903 | 10 duplicate vertices and 4 duplicate edges unchanged; 7 co-directional pairs below 5 mm unchanged. Historical v001 cause breakdown: 39,176 pergola-frame crossings, also inset/body and inset/inset contacts. That attribution was not re-counted for v002. |
| V005 | Pass for measured subset | 0 color attributes; opaque assignments have diffuse images. |
| V006 | Pass for measured subset | Embedded maps, measured sides ≤2,048 px, 31,377 faces across 14 atlas regions; measured nearest UV corner 17.79 px. |
| xView NPM offline | **Fail**: 92 face pairs / 89 marked faces; 10 vertex pairs / 20 marked vertices (unchanged vs v001 dump) | `84 contact + 8 area+contact`, 5 bow-tie pairs. The 43 pairs cited in the intake/overview are not the same count as the full offline JSON; no zero-pair claim. Coincident vertices still have separate indices. |
| SINTEZ / native xView in 3ds Max | **Needs free Max** | Not run. Offline Blender results do not certify Max. |

Evidence: `G:/Мой диск/AGR-evidence/2098-sokolniki-npm-v002/` (`SHA256SUMS.txt` covers 38 files, SHA-256 `c1a285be622bc5a80909a871b07bb63727ccb754a564ce45ccb6e7b21a7ee3d4`). The selected FBX is in `after-low-only/`; `review-sheets.md` lists the three review items. The folder includes scripts and ledgers, validator JSON and raw Blender dumps, the rejected wider snap and the pre-pack report. No delivery, visual, or manual acceptance claimed.

Reproduction from staged copies (`FBX` = candidate from the evidence, `WORK` = untouched v001 work FBX, `ATLAS` = v001 `npm_atlas.json`):

```sh
uv run agr validate "$FBX" --profile npm --scene --master "$WORK" --npm-atlas "$ATLAS" --json
uv run dt qa xview "$FBX" --out xview-v002.json --profile NPM --blender "$BLENDER"
uv run python tools/qa/archive_diff.py "$V001_FBX" "$FBX" --expect-changed SM_Sokolniki_UVK1000_001_Main:geometry --report archive-diff-v002.json
```
