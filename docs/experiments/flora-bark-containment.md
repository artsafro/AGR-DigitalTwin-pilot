# Flora bark containment experiment (#369)

## Question

Does the clarified D155 continuous-bark containment check distinguish a correctly mapped narrow original bark island from a misplaced island, without requiring it to cover an entire bark strip?

## Method and setup

Offline Python only in this continuation; no AutoCAD, Revit, Max or Blender was launched. Reuse the previous owner's full native extraction, `inventory-all-v005.json`, and copied source bitmaps. Original Tilia VPM `19_Lipa_HP`, island 166 / face 332; original 4096×4096 atlas. The continuous bark rectangle `[3304,0,4096,4096]` was visually inspected in the original-only witness and the source atlas contact sheet. Its opaque pixels, not a brown-colour heuristic, define the diagnostic bark mask.

Baseline: the previous generic sprite-bbox intersection metric. Prototype: explicit reviewed bark mask, containment = raster island pixels on that mask / raster island pixels. The numerator and denominator use the same native-pixel raster; unlike the sprite check this is a semantic containment fraction, not polygon/bbox coverage. Missing masks fail closed. No source geometry, UV, map pixels, catalogue or published asset is modified.

## Baseline versus prototype

Three identical calls per method after loading the same copied inputs:

| Method | Score | Result under its respective rule | Median seconds (3 calls) |
|---|---:|---|---:|
| Baseline: island intersection / entire bark bbox | 0.2444722245% | Fail; wrong applicability for a tiling bark region | 0.011435 |
| Prototype: containment on reviewed opaque bark | 99.5347214144% | Pass (>=95%) | 0.013396 |

Baseline polygon area: 7,930.757195 px² / strip bbox 3,244,032 px². Prototype native raster: 8,557 / 8,597 pixels. The difference in area representation is explicit; the polygon number is not presented as a raster count. The original leaf-card control still covers 100% of its discrete sprite bbox, with zero neighbouring opaque pixels.

The timings measure only the in-memory metric call, not file IO or native automation, and make no speedup claim. Exact three-call samples and results: `experiments/flora-texture-diagnosis/bark-containment-v002.json`. Synthetic tests include displaced bark, absent/invalid masks, and the exact 95% boundary. A source-wide geometric/semantic calibration is a separate prerequisite; one passing witness does not certify 99 objects.

## Verdict

**Adopt the role-specific measurement in the diagnostic tool, not as a production delivery gate.** It resolves the confirmed false rejection of the original narrow bark island under the clarified rule. Require reviewed region provenance; alpha density or RGB brownness alone does not certify bark.

Proposed follow-up title: **Flora: calibrate role-aware atlas correspondence before library republishing**. Scope: establish reviewed foliage/bark regions and geometry roles, retain explicit unknowns, verify discrete-sprite coverage and NPM clipping independently, then choose map/UV repair routes. No asset repair or GitHub issue is implemented by this experiment.

The complete task evidence and remaining calibration limitations are in [`docs/research/flora-texture-diagnosis.md`](../research/flora-texture-diagnosis.md).
