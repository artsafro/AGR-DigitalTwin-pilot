# #149 — Finish-partition agreement for elevation view -> model face (OBSERVE)

## Frozen contract (committed before any score was computed)

Card t_141c9690 (standing #149), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was
not opened. Rounds #139-#148 used line/edge or raster-luma cues and plateaued on two confounders: the
dense-edge attractor (ELV east curtain wall, #145) and periodic bays (#143/#144). This round measures a cue that
uses neither edge density nor rhythm.

**H149.** On the ELV TC Sreda vector booklet the elevation views are colour-filled by finish (vector fill paths),
and the Revit FBX keeps the Revit family type name per object (`Базовая стена (AR)_metall kasset WOOD`,
`Системная панель Стемалит`, `(SC)-Batten_RAL 7021`, ...). The FBX has a single Blender material, so object
type, not material, is the model finish label (feasibility probe: 1 material, 9773 mesh objects). A
label-permutation-invariant agreement between the view's fill-colour partition and the model's type partition
assigns views to faces with fewer confident errors than #147 C at equal or better coverage.

- **Fixture (pinned).** Exactly the #145 ELV inputs and views (`autoresearch-view-face-elv/fixture.json` at
  `origin/research/autoresearch-standing-145`, PDF SHA-256 `49c10527...9545`, FBX `7ccf502d...b961`), the same
  80 cases (7 full, 7 mirror, 63 synthetic crops 25/40/60 % at 0/0.5/1.0, 2 real fragments, 1 top-cut
  fragment), same view extents and crop offsets computed by the #145 segment raster at 0.1 m. Row identity
  parity (view, case, width_m) against the #147 receipt rows is checked; any mismatch stops the run.
  Candidate faces: az 0/90/180/270 (as #145). GT: #145 fixture `gt_az` (title convention + roof footprint);
  titles, axis bubbles and level marks are outside the boxes and are not read for the face.
- **Model labels (D).** Blender 4.4 (hash-checked) orthographic ray cast, same frame and skip list as #145
  `rays_elv.py`, 0.2 m/px, label = Revit type name = object name with the trailing instance suffix removed
  (`re.sub(r"[\d_.\[\]#-]+$", "", name)`), 0 = no hit.
- **View labels (D).** Fill paths (`get_drawings()` with a fill, fill_opacity > 0) fully inside the #145 box,
  painted in drawing order (later on top) as polygons (`re`, `qu`, `l`/`c` endpoints; even-odd holes ignored),
  rasterised at 0.05 m and reduced to 0.2 m by majority of filled sub-pixels; label = fill RGB rounded to 0.02;
  0 = unfilled. View raster spans the #145 metric x-extent and the segment y-extent.
- **Score (D).** For each candidate and each horizontal offset (1 px step, ±0.6 m slack, as #140) with the view top
  aligned to the model top in that column window and vertical shifts −3..+3 px: over pixels where the view is
  filled AND the model has a hit, `U = (I(V;M) − (|V|−1)(|M|−1)/(2N)) / H(V)` (nats, Miller–Madow chance term,
  |V|,|M| = labels present in the overlap). Score −1 if the overlap N < 30 % of the view's filled pixels.
  Face score = max over offsets/shifts. Decision = #140 `decide` unchanged: best ≥ 0.30 and best − second ≥ 0.10,
  else abstain.
- **E (pre-declared secondary).** C (#147 receipt, raw/chance agreement) where C answers; D only where C abstains.
- **Primary metric.** correct / wrong / abstain per class (full, synthetic_crop, fragment, fragment_top_cut,
  mirror). Mirror = injected negative scored under the #145 oracle; changed filled-label pixels recorded per row,
  0 changed = `not_exercised`.
- **Acceptance (frozen).** H149 confirmed iff D has 0 wrong on full and on real fragments, ≤ 1 wrong on synthetic
  crops, and ≥ 15 correct crops (> C 14, = A 15). E bound: clean wrong (full+fragments+crops) ≤ 1 and crop
  correct ≥ 20. Positive witness: `p18 I-A` full (east curtain wall) answered correct. C residual witness:
  `p19 A-I partial25@1.0` (C wrong) must be abstain or correct under D. Invariance witness: permuting the view
  colour labels must leave every D score bit-identical (exercised on all 80 rows).
- **Not measured.** KPP1, AC08, OBR22 (pinned inputs have no colour-fill views / not checked for type labels),
  G22, Vatutino, Sokolniki transfer; accepted-vs-rejected delivery quality. Synthetic crops test face identity,
  not localisation within the face.
- **Replay and budget.** `uv run --offline --locked --extra pdf-review python
  docs/research/autoresearch-view-face-material/run.py C:/x/ar149/<fresh>` (pilot host, mounted inputs). Three
  fresh runs (ray cast + scoring each), byte-identical row JSON required; report median/min/max wall. One
  candidate (D, plus E derived), no threshold or label tuning, no second candidate under this contract. Stop
  `inconclusive` if elapsed + 1.15 × first-run seconds × remaining runs > 1500 s or on any parity failure.
  Timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Threshold/label search after seeing scores, fixture substitution, reading Sokolniki outputs,
  editing source drawings, models, deliveries, production `src/` or other cards' files, weakening guards.
