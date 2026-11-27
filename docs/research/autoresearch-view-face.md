# Autoresearch #139 — elevation view -> model face map (OBSERVE)

Card t_8845bd2c, branch `research/autoresearch-standing-139`. Focus 0 of the card (Artem 2026-11-27 ~15:05):
tie every elevation view on a sheet, including untitled partial views, to the model face it shows, and
abstain (ask) below a threshold. Found in the Sokolniki cold run (#2001 STOP 04). Sokolniki is HELD OUT.

## Frozen contract (committed before any scoring)

- **Metric (one number + abstain):** view->face assignment accuracy on answered views and abstain rate, per
  variant and per view class (real full views; synthetic partial crops). Safety = confident-wrong count
  (must be 0 for a recommendation). Fixture and GT: `autoresearch-view-face-harness/fixture.json`
  (SHA-256 of every input, preflight-checked on every run).
- **Method under test (OBSERVE, research only):** model side = Blender headless orthographic ray-cast depth/normal
  maps from each candidate outward normal (`rays.py`); view side = DXF vector geometry inside the view,
  annotation layers (titles, axes, dimensions, notes, level marks) removed, rasterised at 0.1 m/px.
  1D signals along the facade: roofline (top profile relative to view max) and vertical-edge rhythm
  (column density). A view slides along each face (partial views allowed); face score = best NCC over offsets.
  Variants frozen: V0 width only, V1 roofline, V2 rhythm, V3 = mean(V1, V2) (proposed).
- **Decision rule frozen:** answer the best face only if score >= 0.30 and margin to the best other face >= 0.10;
  otherwise abstain. Thresholds are fixed a priori, not tuned on this fixture; the full margin table is published.
- **Fixtures:** KPP1 L01 (Revit vector export, 4 elevations, accepted delivered model) = positive set;
  TEC26 AC08 (AutoCAD sheet, 4 elevations, symmetric source box) = abstain control (within-pair abstain is
  correct; a confident within-pair pick counts as wrong). Synthetic partials: crops at 25/40/60 % width,
  left/centre/right, labelled synthetic. **Not measured:** real untitled partial views (only Sokolniki has them,
  held out), PDF-only raster sheets (AC06 slides), G22/OBR22/Vatutino (no vector elevation + model pair found
  locally within budget), non-orthogonal faces and inner corners (KPP1/AC08 are boxes).
- **Calibration requirement (card rule 3):** applies as GT accuracy here: a wrong face must not win with margin.
  Witnesses: positive = KPP1 full views (asymmetric stairs/canopies); abstain control = AC08 within-pair;
  perturbation = mirrored KPP1 view (expected: score drop or abstain, not a confident correct pick).
- **Repeatability:** 3 full runs (ray-cast + DXF + scoring), median; deterministic expected, spread published.
- **Budget / stop rule:** one card run; at most 3 rounds of method change after the first frozen scoring,
  each recorded; stop at 3 rounds or when V3 reaches 100 % answered-accuracy with 0 confident-wrong.
- **Forbidden:** editing sources/deliveries/other cards' files, tuning thresholds on the scored set without
  recording it as a new round, opening Sokolniki accepted outputs, presenting synthetic crops as real views.
- **Deliverable:** measured recommendation for a shared OKS-trail step "view<->face map sheet" (core + agr command),
  not the step itself.

## Replay

```
blender -b --factory-startup -P docs/research/autoresearch-view-face-harness/rays.py -- <model.fbx> <out.npz> 0.1 0,90,180,270
uv run --offline --extra cad python docs/research/autoresearch-view-face-harness/view_face.py --out <dir>
```

## Round log

(filled after scoring)
