# G22 NPM-to-VPM regions — #1649 checkpoint

**STOP — no production VPM written.** This is a continuation of the `npm-to-vpm`
skeleton, `oks-npm` → `oks-vpm`, on the immutable #1630 r2 inputs. The current
route still refuses unresolved colour region boundaries. The colour clipping
and metric seam functions are planning primitives, not a native adapter or a
delivery certificate.

[D355]: the exact 460 source triangles use one solid placeholder with their
mean source Diffuse colour. Do not rebuild their UV, rebake, or apply the texel
band to these triangles. This does not exempt any neighbouring triangle. Use
Blender only for any production continuation. The two zero-world-area source
polygons previously approved for removal remain accounted for by #1630.

## Shared primitives

- `tools.library.npm_ids.recover_regions` uses the existing facade segmenter
  and exact pixel-space intersections. A mixed leaf is subdivided by connected
  palette masks. A source triangle not fully covered remains a reported
  residual, rather than publishing part of the triangle or guessing a finish.
- `npm2vpm_core.fit_metric_region` uses a *new* metric chart in metres from the
  caller, prefers named panel/zone seam coordinates, clips geometry and UV
  together, and returns separate tile-local pieces. It does not derive such a
  chart from distorted NPM UVs or allocate the final finish/UDIM table.
- Next when the atlas partition is resolved: transfer pieces to a conforming
  native copy, lay out textured charts through `vpm_uv`, allocate per-piece
  IDs/tiles, and run Blender readback, checker and xView. No PASS is claimed.

Evidence: `G:/Мой диск/AGR-evidence/1649-npm2vpm-g22/t_2692a5c8-v002-colour-STOP/`.
The folder contains three atlas sheets, a tolerance matrix and exact original
polygon IDs with input SHA-256 bindings. The sheets use RGB8 max-channel
comparison (`distance < 18`); lower runs at `<6` and `<12` are retained.
The sealed diagnostic sheets retain the pre-publication decision label;
[D355] is the final registry ID for that same approval.

| Mesh | Source after approved zero-area drops | Placeholder | Residual at <18 | Faces cut in UV at <18 |
|---|---:|---:|---:|---:|
| 001 | 148186 | 293 | 13135 | 5322 |
| 002 | 73304 | 167 | 10610 | 550 |
| 003 | 51146 | 0 | 3370 | 24 |

The narrow palette produces fragment IDs (108 used IDs on mesh001 at `<6`),
while broader tolerances still leave atlas footprints that cross blended,
patterned or unresolved swatches. Neither a majority vote nor converting all
unclassified pixels to one finish is a source-bound material decision. Request
a marked material boundary mask (with patterned/solid labels) for the marked
areas or an equivalent source material-ID map. Do not promote these provisional
counts to final material IDs, tile allocations or a geometry cut list.
