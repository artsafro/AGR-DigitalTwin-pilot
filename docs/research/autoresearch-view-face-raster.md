# Autoresearch #141: raster elevation view -> model face by window rhythm (OBSERVE)

## Кратко для Артёма

(заполняется после замера; см. «Round log»)

## Frozen protocol (committed before scoring)

Card t_c97df96b, branch `research/autoresearch-standing-141`, focus 0 (Artem 2026-11-27 ~15:05): tie every
elevation view to the model face it shows; abstain (ask) below a threshold. Sokolniki (#2001, still OPEN) is
held out and not opened. Continues #139 (`research/autoresearch-standing-139@38f7d95e`) and #140
(`research/autoresearch-standing-140@ab33b7e4`), whose next step (2) was "a second asymmetric, independently
labelled PDF/model pair". #139 diagnosed rhythm failure as "NPM without window geometry"; #140 left raster/vector
PDF, G22/OBR22/Vatutino unmeasured.

- **H141:** on a held-out project (OBR22 K02, never used by #139/#140) with a **raster** PDF elevation sheet and an
  accepted model **with window geometry**, a 1D window-column rhythm matcher (variant C) assigns both long
  facades correctly from the image alone, with zero confident-wrong answers on all clean cases, where the #139
  width baseline V0 cannot answer (both face pairs have equal widths).
- **Cohort (fixture.json, SHA-256 per input):** `АГР_зона 2.1 — 1.pdf` pages 14-15 (Корпус 2, four facades;
  facade = raster tiles, annotation = vector) and the accepted NPM v012 `OBR22_K02_v012_NPM_ATLAS.blend`
  (one typical floor, 88.9 × 16.3 m, 45 `WINDOW_*` objects). Full views 4 (2 long, 2 short); synthetic
  horizontal crops 25/40/60 % at left/centre/right = 36 (labelled synthetic); injected horizontal mirror of
  each full view = 4. There are no real untitled partial views and no inner corners in this cohort.
- **GT (independent of the elevations):** PDF plan p36 (vector cut walls) registered to the Revit wall
  footprint (`plan_reg.py`): rot180 0.9097, mirror_y 0.9018, identity 0.6902, mirror_x 0.6853. Both top/bottom
  flips agree on the long faces: 2.1-2.25 = model +Y (az 90), 2.25-2.1 = -Y (270). Short ends: Revit sheets are
  not mirrored -> rot180: А.2-Е.2 = -X (180), Е.2-А.2 = +X (0); weak (margin 0.008) and reported separately.
  Cross-check: the plan stair cores are on the Е side; model -Y has the three narrow core windows. Titles are
  read only to label GT; the matcher never reads page text except level marks for scale.
- **Method C (frozen):** view = raster images only (all vector paths dropped), rendered at 0.1 m/px using the
  page scale from signed level marks (Theil-Sen, median); views split on >= 3 m empty columns; window pixels
  luma < 0.45; body rows = non-white >= 90 % and dark <= 60 % (drops plinth, roof plant, ground line); profile =
  window fraction per column. Model = Blender 4.4 orthographic first-hit ray cast per azimuth 0/90/180/270 at
  0.1 m, profile = fraction of `WINDOW_*` first hits per column. Gaussian s=1.5 px, sliding NCC with 0.6 m
  slack; answer only if best >= 0.30 and margin >= 0.10 (#139 thresholds, unchanged). Empty/flat view -> no
  score -> abstain. Baseline A = #139 V0 width-only.
- **Bounds / outcome:** confirmed if, at the median of 3 fresh runs, C answers both long full views correctly,
  >= 9/18 long crops correctly, and makes 0 confident-wrong answers on all 40 clean cases in every run.
  Short-end answers count wrong if they differ from the rot180 GT. Refuted if measured and any bound is missed.
  Mirror control (separate, not pooled): count changed pixels per view (`not_exercised` if 0); a confident
  answer on a mirrored view that differs from the original face is recorded as a handedness risk.
- **Expected direction:** long faces differ in window rhythm (core windows on -Y, loggias on +Y), so C should
  separate them; short ends have no windows in the elevation -> C should abstain; V0 abstains everywhere.
- **Budget / stop:** one candidate, one baseline, three fresh runs (new ray cast + PDF read each). After run 1,
  continue only if 2 more runs at 2× run-1 wall time fit in 20 minutes. No threshold or variant change after
  scoring; a failure is published as refuted, not retuned. Stop at run 3 or on hash/extraction mismatch.
- **Forbidden:** editing the PDF, the accepted model or other cards' files; opening Sokolniki outputs; tuning
  on the scored set; deselecting tests; presenting synthetic crops as real untitled views.
- **Round 2 addendum (frozen after R1 scoring, before R2 scoring; post-hoc, in-sample — cannot confirm H141):**
  R1 showed two structural flaws (see Round log): dark cladding bands counted as glass, and an end view with
  no windows had no admissible windowless candidate. R2 = C with (a) vertical dark runs taller than 25 px
  (2.5 m, below the 3.0 m storey; glass is one storey at most) removed before the column profile and (b)
  abstain when the view's mean window fraction < 0.02 (low evidence). Model side, thresholds 0.30/0.10, crops
  and GT unchanged. Same three-run rule; R1 must replay byte-identical cases after the code change (parity).
  R2 outcome is labelled `diagnostic` (tuned on the scored cohort); the bounds above are reported for it but a
  pass would only justify a held-out test, never adoption.
- **Replay:** `uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-raster/run.py <new_dir>`
  (pilot host: needs the Desktop PDF, `C:/Users/artsafro/.AGR_Project/jobs/OBR22-K02/outputs/` and Blender 4.4;
  preflight and postflight hash every input). Regression: `uv run --offline pytest -q
  docs/research/autoresearch-view-face-raster/test_score.py`.
