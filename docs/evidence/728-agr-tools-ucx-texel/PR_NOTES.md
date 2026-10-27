# AGR Tools 0.3.0 — review notes

## Build sha256 (twice)

`AGR-Tools-0.3.0-g.mzp` and `AGR-Tools-0.3.0-h.mzp`:

`1b1b7b42eb27a28f92595e35e2e33216caae9766cd07a5e5a925775fd9d5aceb`

The two files are byte-identical.

## Parity

| Check | Python tool | Button | Delta |
|---|---|---|---|
| 1 m box, near-convex | `single-hull`: 1 piece, 12 triangles | same | 0 |
| clipped cube x+y+z<=2.8 | real hull: 10 verts, 16 triangles, volume 0.9986666666666665 | same, not a 12-triangle AABB | 0 |
| L passage | `kernel-boxes`: 2 pieces, 24 triangles | same | 0 |
| Two equal storeys | `slice-prisms`: 2 pieces, 24 triangles | same | 0 |
| 12 random assemblies | `ucx_variants.build` with the real source hull | same piece count and triangle count | 12/12 exact |
| Texel, unit quad 1024 px | `texel_density_readout`: 1024 px/m | min = median = 1024 | 0 |
| Texel, UV 0.1, 1024 px | 102.4 px/m, below the VPM band | 102.4 px/m, status fail | 0 |
| 16 random quads | `readout` face px/m | min and median | 16/16, relative < 1e-6 |
| Max float32 planted readback | 102.4 | 102.4000015258789 | relative 1.49e-8 |

## Hostile self-review

| Class | Witness | Result |
|---|---|---|
| empty | `build([], [])` and a texel payload with no faces | error naming `empty`; no pieces and no pass |
| non-finite | NaN vertex, inf vertex, NaN UV | error naming `non-finite` |
| unmapped kind | `AGR_UCX_KIND=part-boxes` | error naming `part-boxes`; no new nodes in Max |
| unmapped material | map entry `stone` while the face is `brick`, and a material with no `map_px` | error naming `brick` or `stone` |
| exactly at the convex limit | `kind_from_outside(0.05, 1)` | `at_threshold`, not rounded to either kind |
| triangles == budget | `budget_verdict(12, 12)` | status `fail`, code `at_threshold`, not pass |
| triangles over budget | `budget_verdict(13, 12)` | error, the word `exceed` |
| zero map size | `map_px` 0 | `at_threshold` |
| relative readback exactly 1e-6 | `assert_texel_close(1/(1-1e-6), 1)` | error `threshold` |
| partial face | one face with no mesh next to a valid face | dropped with a reason, both indices reported, status fail |
| alias output | `publish(source, source)` | error naming `input`; source bytes unchanged; no `.partial` |
| input mutation | the three fixed meshes passed through `build` | vertex and triangle lists unchanged |
| audit `not_run` | an unmeasurable hull | finding `ucx_unmeasurable`; report status fail, never pass or not_run |
| Cyrillic install path | `G:/Мой диск/...` written into the startup script | Max `fileIn` stored `???`; the run used an ASCII package path |

## Native Max 2024 (this sha)

Exit 0. `AGR_REVIEW_R1 mesh=1 poly=1 plain=1 modifier=1 clipped_tris=16 stale=1 names=1`.
Physical-distance matrix 120/120. Full marker log: `max2024-native.log`.
