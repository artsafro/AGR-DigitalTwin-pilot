# tec26-oks3-truba

Status: **texture foundation only**. Issue 560 acceptance items 3 and 4 are open.
No FBX, UCX, SINTEZ result or render exists for this object.

## Done

- Finish census of `maps_truba`: five uniform RGB swatches and one 4096 RGBA railing.
- RAL labels recorded in `materials.json`. The facade album does not name the truba;
  slide 58 states the site palette only. Decisions are marked `assumption` except
  `gray.png`, which matches the KPP1 RAL 7047 sample exactly.
- Naming spec for the later package: address `Truba_1`, NPM number `003` (OKS 3),
  one material, finishes as UDIM 1001-1006.
- `make_textures.py` writes 24-bit RGB maps (no alpha) to
  `C:/x/tec26-oks/textures-v001/` and `C:/x/tec26-oks/SHA256SUMS.txt`.
  Solids are 256 px placeholders. The railing keeps its raster and is split into
  diffuse plus a separate opacity map. `_r` / `_m` / `_n` / ERM / Normal are 256 px stubs.
- Regression: `tests/test_tec26_oks_truba_textures.py`.

## Not done (DCC phase, gated on the #558 census)

- Read `truba.max`, confirm the Multi/Sub assignment against these six finishes.
- Export VPM and NPM FBX, build UCX, run overlap / normals / doubles / readback and SINTEZ.
- Renders for Artem.

DCC-phase requirements (operator note 2026-10-22, applies to this object too):

- Perimeter drop: never cut the geometry at ±0.000. The base must drop at least 1.0 m below
  ground in both VPM and NPM, and the dropped shell keeps the adjacent facade/wall finish (no
  separate material id unless the Multi/Sub already has one). Check: every perimeter wall reaches
  ≤ −1.0 m.
- Renders for Artem must be depth-correct (Max scanline), UCX hidden, a line at ±0.000, and a
  plain shaded view next to the finish/id colours.

Do not treat this job as a delivery package.
