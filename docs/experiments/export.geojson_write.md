# Lab note: `export.geojson_write` (AGR Tools 0.8, #908 branch D)

Date 2026-11-05. No GeoAGR code is reproduced (rule #853); references are `GeoAGR.ms:<line>` of GeoAGR 13.64.

## Sources checked (static)
- GeoAGR rollout `Geojson` (`GeoAGR.ms:64615-64874`): buttons "Create file", "Save file", "Load file"
  (`GeoAGR.ms:64642-64644`) are declared `enabled:false`, and **no event handler exists for any of them** anywhere in
  the file (the three control names occur only on their declaration lines). A lab run cannot exercise anything:
  there is no behaviour to measure. Decision: **не берём** (nothing to port); the button is written anew.
- "Base64 to Clipboard" (`GeoAGR.ms:64853-64874`): resizes a picture by shelling out to ImageMagick `magick`
  (`GeoAGR.ms:64859`, external exe, path from an INI) and puts `ConvertImageToBase64String` (`GeoAGR.ms:3668`) of the
  file into the clipboard; the guard `bitmap != undefined or bitmap != <placeholder>` is always true. Static only.
- Pivot buttons of the same rollout are covered by `export.pivot_place` (branch A, `docs/experiments/export.pivot_place.md`).

## Implementation decisions
- Properties (App.3, `standards/VPM_STANDARD.yaml` `geojson.properties_keys`) only from `options.properties`; an empty
  mandatory value is a finding, never invented (`missing_value_note`). Ground uses `ground_nullable_as_empty_string`.
- Point MSK-77 `[x, y]` with 3 decimals only from `runtime.edits_080('export.pivot_place', 'preview')` (`plan.pivot_value`);
  a stub or failed pivot preview is an error. `geom_*` is not imported.
- Preview: a 256x256 JPG given by `options.image`; the tool never resizes (no external exe).
- `Glasses`: `[]` without glass; else one object keyed by each glass material (diffuse colour, opacity/100,
  IOR, 1 - glossiness/100, metallicity 0 for Standard).
- New file only; checked right after writing by the 0.5.0 `qa.geojson` (twinqa checker).

## Measured
- Unit: the written document passes `twinqa.geojson.geojson_findings` (OKS with glass, Ground); Base64 decodes to
  the same JPEG bytes; missing values reported, unknown keys refused.
- Max 2024 batch, lab job `20261105-011838-85456b6a` (disposable scene): `SM_X.geojson` written, `qa.geojson`
  imageBase64/Glasses/schema pass, second run writes nothing. The pivot was a recorded stand-in because
  `export.pivot_place` (branch A) was not in main yet; rerun after A is merged.

## Minimal acceptance
Synthetic scene → GeoJSON → `qa.geojson` without errors; a repeat does not overwrite; fields per VPM-2.2-x / GJ-x;
the preview Base64 decodes.
