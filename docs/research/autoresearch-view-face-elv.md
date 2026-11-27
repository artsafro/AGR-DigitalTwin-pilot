# Autoresearch #145 — view -> face transfer test on a fresh asymmetric pair (ELV TC Sreda, OBSERVE)

Card t_6c816f20, branch `research/autoresearch-standing-145`. Focus 0 (Artem 2026-11-27 ~15:05): tie every elevation
view on a sheet, including untitled partial views, to the model face it shows; abstain (ask) below a threshold.
Sokolniki (#2001, OPEN) is HELD OUT and was not opened.

## Frozen contract (committed before any scoring)

**Why this target.** #139-#144 measured view->face only on KPP1/AC08 (boxes, synthetic crops) and OBR22 K02
(raster). #140 B (2D drawing lines vs orthographic mesh edges) was the only CONFIRMED method, on calibration only;
its own next step was "a second asymmetric, independently labelled PDF/model pair to test transfer before
implementing an OKS step". ELV TC Sreda (`jobs/elv-tc-vpm`, sources.json) is such a pair and was never used:
vector AGR booklet (42 sheets, SHA-256 `49c10527...`) + Revit 2023 FBX (SHA-256 `7ccf502d...`). It has what the
earlier cohort lacked: a slanted (non-axis) wall drawn true-length as its own view (`6-1`), a west annex with a
re-entrant corner, a recessed entrance, and three REAL partial views (fragments) on other sheets.

**H145:** #140 B, unchanged (pinned `score.py` @ `ab33b7e4`, thresholds score >= 0.30 and margin >= 0.10, 0.1 m/px,
width slack 0.6 m), transfers to ELV: zero confident-wrong answers on all clean cases AND at least 4 of 7 real full
views answered correctly. Refuted if any clean case is confidently wrong or fewer than 4/7 full views are correct.
Fragments are reported separately (n = 3 is too small for a rate) and must not be confidently wrong either.

- **Metric (one number + abstain):** correct / answered and abstain / total per group: real full views (7: p18 I-A,
  p18 1-10, p19 10-1, p19 A-I, p19 6-1, p21 I-A, p21 1-12), synthetic crops of those (63, #139 scheme 25/40/60 % x
  left/centre/right), real fragments (p23 D-G 1:100, p24 8-9 1:100), real top-cut fragment (p20 9-10, 1:20; B
  aligns tops, so its precondition is violated: expected abstain). Safety = confident-wrong count.
- **Candidates:** 4 sides, az 0/90/180/270 (as #139/#140). The slanted wall (about 5.9 deg off +Y) belongs to side
  az 90; its orthographic foreshortening is 0.5 % (0.25 m over 50 m, inside the 0.6 m slack). Face identity is
  side-level; within-face localisation is NOT scored (not measured).
- **GT (independent of the method):** title convention (left axis -> right axis seen from outside) mapped to the model
  frame via the ray-cast roof footprint: axes 1..12 west->east (12 = east wall with the rounded entrance recess, p23
  plan fragment), axes A..I north->south (I = south: p20 section B-B, p24 plan fragment). Visual cross-check before
  scoring (`preview` contact sheet: stepped wood volume and loading gates have the same handedness in drawing and
  render). Recorded in `autoresearch-view-face-elv/fixture.json`.
- **Front end (frozen before scoring):** PDF vector items fully inside a per-view box that excludes titles, axis
  bubbles, dimension chains and level marks; only segments within 2 deg of horizontal/vertical, longer than 0.05 m
  (drops glass hatch, rhomb callouts, letter curves); rasterised with #139 `raster_view` logic. Scale (pt per m) from
  the x-distance of the two end axis labels and the written dimension (labels used ONLY for scale; p20 from the
  +2.700/-0.100 level marks). Callout boxes and leader lines that overlap the facade (p21, p20) stay in: real noise.
  Model: pinned #139 `rays.py` @ `38f7d95e`, one change: skip mesh objects with world max z > 30 m (one stray
  Revit batten at z 166 m; building top 16.4 m).
- **Controls:** injected mirror of each full view (changed-pixel count, `not_exercised` if 0), not pooled with clean.
  Positive witness = the 4 axis-aligned full views (distinct silhouettes); hard case = 6-1 (slanted, sub-span of
  side 90) and the p21 sheets (callout boxes over the facade). Symmetric-negative control: p18/p21 I-A are nearly
  mirror-symmetric glazed entrance facades - a confident answer is allowed only on the correct side.
- **Repeatability / budget:** 3 fresh pairs (new Blender ray cast + new PDF read each, not rescoring a dump), outputs
  must be byte-identical; one pair measured at about 36 s in the preview, budget 15 min. ONE variant only (B as is);
  no threshold or box change after the first scoring. A failed bound is a result, not a reason to retune.
- **Forbidden:** editing sources/deliveries/other cards' files, tuning boxes/thresholds after scoring, opening
  Sokolniki outputs, presenting synthetic crops as real views, deselecting tests.
- **Replay:** `uv run --offline --extra pdf-review python docs/research/autoresearch-view-face-elv/run.py <new_dir>`
  (pilot host: inputs in the owner's named folder per `jobs/elv-tc-vpm/sources.json`; needs
  `git fetch origin research/autoresearch-standing-139 research/autoresearch-standing-140`). All inputs and upstream
  bytes are SHA-256 checked at stage time and the inputs again after the run. Replay is limited to hosts with that
  folder; hash-identical copies go to the evidence folder.
