# Lab experiment L03: `tex.placeholders` (AGR Tools 0.8)

Source check before the button enters AGR Tools (`docs/plans/agr-tools-suite.json`, row `tex.placeholders`, verdict
`merge`). Executed 04.11.2026 through the AGR Lab runner (3ds Max 2024 batch), GeoAGR 13.64 Personal runtime, synthetic
folder only. No GeoAGR code here, only `GeoAGR.ms:<line>` references (rule #853). Evidence: GeoAGR-private branch
`lab-exp/L03`, `work/lab-experiments/tex.placeholders/`.

Jobs: `20261104-231102-41318119` (valid); `20261104-230839-a2ae1d9d` (first writes only), `20261104-230623-dd28b4a2`
(harness failure); Set Normal/ERM from the earlier runtime suite job `20261104-033517-db86b1de` (T07-01..03).

## Sources
| Source | Status |
|---|---|
| GeoAGR Make Diffuse/Normal/ERM (`GeoAGR.ms:42227`, `:42308`, `:42384`) | run live |
| GeoAGR Set Normal/ERM (`:42333`, `:42409`) | not pressed (file dialog); measured earlier by suite T07-01..03 |
| Andrew_scripts `Texture_Zaglushki_Ground.ms` | **not available** in any repository |

## Behaviour of the GeoAGR source (measured)
- Make D/N/ERM: solid-colour PNG, 8-bit RGB (IHDR colour type 2), exact picker colour (default D [200,200,200],
  N [128,128,255], ERM [0,255,0]; custom colours exact; Max output gamma 2.2 does not affect it). ~90 ms at 256.
- Sizes 256…4096 only, **default 4096** (`GeoAGR.ms:14441`); 128 cannot be produced.
- An existing file with the same name is **overwritten silently**.
- Output path = folder text + file name without separator: a folder typed without a trailing `\` gets an **empty** folder
  created and the PNG written into the parent as `<folder><name>.png`.
- File names come from read-only fields generated from the object name; the default folder is `Maps\` beside the scene
  (relative when the scene is unsaved).
- Set Normal/ERM (replace placeholder by a resized picked file): crash before the overwrite question and on the resize
  command (string building errors, `GeoAGR.ms:42350`, `:42359`, `:42426`, `:42435`).

## Requirements the AGR Tools button must meet
Row reqs: VPM-2.5-3.1, VPM-2.5-3.3, VPM-2.5-3.4, NPM-2.5-7 (placeholder textures: allowed size 256 for VPM tiles / 128 as
named in the row label, solid single colour, D/ERM/Normal set per tile; `tex.plug_colour` checks VPM-2.5-3.4 colour
uniformity). Names by VPM-2.10-4.3 (`T_…_{Diffuse,ERM,Normal}_{Slot}.{UDIM}`).
- Sizes 128 and 256 at least; default to the rule value, not 4096.
- Write into an explicit/new folder (`Path.Combine`), never overwrite an existing texture without an explicit choice.
- Output: PNG, 8 bit per channel, RGB, no alpha; exact colour; neutral Normal [128,128,255].
- One call makes the full D+ERM+N set with rule-compliant names for a given slot/UDIM.

## Minimal acceptance test (proposal)
Empty synthetic folder; request set for slot 1, UDIM 1001, size 128 and 256, colours D [101,117,92], ERM [0,200,0], N
default. Pass if: 6 files with VPM names; IHDR 128²/256², depth 8, colour type 2; every pixel equals the requested colour;
re-running with an existing file either refuses or writes a new version, md5 of the old file unchanged; folder without a
trailing separator still writes inside the folder.
