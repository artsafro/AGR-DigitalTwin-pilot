# AGR Tools changelog

## 0.5.0 (#804)

Five read-only diagnostics. None of them edits the open scene. Each writes a 0.4.0 JSON report
(`schema`, `tool`, `status`, `objects`, `plan`) to the Listener.

Base: GeoAGR 13.64 (author Artem), recovered `GeoAGR.ms` (GeoAGR-private@31c723e), with the author's
permission. Only the functions in use are adapted, in `checks_core.py`. Each function's docstring names
its `GeoAGR.ms:<line>` and its changes.

- **Names check NPM/VPM** (`names`): object (SM/UCX), (sub-)material (M) and texture file (T) names.
  Adapted from `check_names_all` (`GeoAGR.ms:6907`) and `check_names_all_vpm` (`:7331`).
  Fixes D2: the exact last token decides Main/MainGlass/Ground/UCX, not a substring `case`.
  Fixes D4: SlotNumber 1..7 is legal; GeoAGR required exactly `1`.
- **Triangle limits per FBX** (`tris`): budgets are summed per `AGR_EXPORT_PATH` FBX and per model
  kind. The limits are NPM OKS 150 000, NPM Ground 180 000, VPM OKS 1 000 000 (UCX excluded), VPM
  Ground by the site-area table (`AGR_SITE_AREA_HA`) and VPM UCX by the decided formula. Fixes D8,
  where GeoAGR summed over the selection. The stale 2 000 000 VPM limit is gone.
- **Textures check (all objects)** (`textures`): the maps of every object are checked. Fixes D1,
  where GeoAGR read the last object only. An empty `usedMaps` array means "no maps". Fixes D3,
  where GeoAGR tested the array against undefined. The checks are size, square shape, placeholders,
  alpha, 8 bits per channel (from the PNG header), file size, the UDIM set and UV padding. Padding is
  NPM 8 px and VPM 16/32 px for 2048/4096 maps; GeoAGR's 16/32 px branch was commented out.
- **Pivot check** (`pivot`): VPM-2.9-4.b requires pivot Z = 0 within 1 mm. VPM-2.9-5 requires every
  pivot of one FBX to coincide within 1 mm. UCX pivots are free (VPM-2.9-4.c).
- **GeoJSON check** (`geojson`): runs the pilot `twinqa.geojson` checker on a chosen `.geojson`
  in the project Python (`AGR_PYTHON` or `<repo>/.venv`). A broken file or a crashing checker is
  reported as a finding, never a raise.
- D6 (Prepare LowPoly/HighPoly destroy the scene) does not apply: the glue only reads
  `snapshotAsMesh` copies in memory, `usedMaps` and the PNG files on disk.

## 0.4.0

Checked export: one FBX per `AGR_EXPORT_PATH`, gated and read back.

## 0.3.0

UCX collision, texel readout.
