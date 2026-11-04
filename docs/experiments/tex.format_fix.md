# Lab experiment L03: `tex.format_fix` (AGR Tools 0.8)

Source check before the button enters AGR Tools (`docs/plans/agr-tools-suite.json`, row `tex.format_fix`, verdict
`take_fix`). Executed 04.11.2026 on the laptop through the AGR Lab runner (3ds Max 2024 batch), GeoAGR 13.64 Personal
runtime, **synthetic** PNG/JPG only. GeoAGR code is not reproduced here; references are `GeoAGR.ms:<line>` of the private
snapshot (rule #853). Full evidence: GeoAGR-private branch `lab-exp/L03`, `work/lab-experiments/tex.format_fix/`.

Jobs: `20261104-231049-e38efd13`, `20261104-231415-0e305be1` (valid); `20261104-230837-a21942ba` (list facts only),
`20261104-230531-409b9b19` (harness failure, no data).

## Sources
| Source | Status |
|---|---|
| GeoAGR "Format & Alpha Tex…" (`GeoAGR.ms:40195-41094`), `compress_file` (`:7971-8073`), dilate (`:8087`) | run live |
| Telegram `convert_8bit_to_24bit.py` | **not available** in any repository |

## Behaviour of the GeoAGR source (measured)
- Every PNG operation (Remove alpha, Make 8bit, Resize, Compress, Dilate) **overwrites the selected file in place, no
  backup**; there is no "new folder" mode.
- Format column: the bare `identify.exe` is not found from Max, so a .NET fallback is shown; it reports a 16-bit RGB PNG as
  `32-bit Argb`. With `identify.exe` on PATH, RGBA, palette and 24-bit PNG all show `8-bit sRGB` — palette is invisible.
- Remove alpha flattens on **white**: fully transparent pixels become (255,255,255); semi-transparent colours are lightened.
- Make 8bit: palette, grayscale and 16-bit PNG → 8-bit RGB (correct).
- A JPG among the selected rows writes a new PNG beside it and **stops the loop**; later rows stay unconverted.
- Resize forces a square: 512x256 → 256x256.
- Compress: works only on files > 3.0 MB and always targets 3.0 MB; the "Compress to" value is ignored (tested 1.0 and 5.0).
  pngquant method: 5.75 → 2.99 MB, RMSE 0.015 (good). IM dither: 6.03 → 2.99 MB. IM "Matrix": **writes nothing** — the
  shipped `magick.exe` has no `thresholds.xml`, `-ordered-dither o8x8` is rejected.
- Default "Dilate before Compress" changes an opaque texture's colours: mean 0.50 → 0.73, RMSE 0.42.

## Requirements the AGR Tools button must meet
Row reqs: NPM-2.5-2.a, NPM-2.5-3, NPM-2.5-5, VPM-2.5-1.6, VPM-2.5-1.9 (see `adapters/max/agr_tools/README.md` and
`docs/agr-tools/GUIDE.md` rows for `tex.check` / `tex.format_fix`: PNG, no alpha where not allowed, 8 bit per channel,
≤ 3 MiB; VPM alpha only in Diffuse).
- Write fixed files into a **new folder**; never touch sources.
- Decide format from the PNG header (IHDR bit depth + colour type), not from `identify` text.
- Flatten alpha only where the rule forbids it; use an explicit background (or edge colour), report what was flattened.
- Process every selected file; JPG → PNG must not abort the batch.
- Keep aspect ratio; a non-square texture is reported, not stretched.
- Size limit as a parameter (default 3 MiB = 3·1024² bytes) and honoured; lossy steps reported (e.g. RMSE).
- No dilate by default; only on request and only for textures with alpha.

## Minimal acceptance test (proposal)
Synthetic folder: RGBA8 (half transparent), palette PNG, gray8, RGB16, RGB8 control, JPG, 512x256 RGB, 1536² noise
(~5.8 MB). Run the button with output folder `out/`. Pass if: sources unchanged (md5); every output has IHDR depth 8,
colour type 2; the half-transparent file's transparent half has the chosen background colour; JPG and all PNGs after it
processed; the 512x256 file is reported, not squared; noise file ≤ 3 MiB with RMSE reported; control file byte-identical
or only re-encoded with identical pixels.
