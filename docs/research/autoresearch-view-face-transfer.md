# #151 — Transfer of finish-partition view -> face (#149 D) to a second pair: Olimpijsky FOK (OBSERVE)

## Кратко для Артёма

(заполняется после измерения — см. раздел «Result»)

## Frozen contract (committed before any score was computed)

Card t_a117effc (standing #151), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. #149 (PR #2073, OPEN) confirmed D (PDF fill-colour partition vs Revit type partition, chance-corrected U,
#140 decide 0.30/0.10) on ELV only; its next step (1) and #150 next (2) ask for a transfer test of D **unchanged**
on a second coloured PDF + Revit FBX pair. This round is that test. No threshold, label or score change.

**Pair (never used by #139-#150).** Olimpijsky FOK (MFK «Олимпийский», vl. 16, etap 6, str. 4):
`АР.2_ Фасады_29.07.2026.pdf` (21 pages; p5-p8 = four 1:150 elevations, vector finish fills with 9-13 colours,
one view per sheet, title «Фасад в осях A-B» + situation plan with a red line on the shown side) and
`ZЦИМ01_Олимпийский02_ФОК02_АГР02_FBX.fbx` (Revit FBX for AGR: 48645 mesh objects, 116 Revit types after the
#149 R1b suffix strip, 0 materials, bbox 147.0 x 60.6 x 50.5 m, max object z 46.5 m). Both on the owner's PC
(`C:/Users/artsafro/Desktop/!3D viz/Dima_Andrew/`), SHA-256 in [`fixture.json`](autoresearch-view-face-transfer/fixture.json);
copies + `SHA256SUMS.txt` in `G:/Мой диск/AGR-evidence/151-view-face-transfer/inputs/`.

- **GT** (independent of any score): title convention (left axis -> right axis seen from outside) plus the red
  line on each sheet's situation plan, registered to the model by the roof ray-cast footprint (curved low podium
  on the -Y side and the +X end, stepped block at +X/+Y; same as the situation plan with 86ф left, 228.8ф right,
  952.2ф top). p5 «228.8ф-86.8ф» = az 90 (+Y), p6 «86.8ф-228.8ф» = az 270, p7 «952.9ф-890ф» = az 180 (-X),
  p8 «890ф-952.9ф» = az 0 (+X). Candidates az 0/90/180/270.
- **Boxes / scale** (frozen in the fixture, before scores): view drawing only; titles, axis bubbles, level marks,
  legend, situation plan and the callout-label row above the roof are outside. Scale from level marks +41.600 to
  +8.850 (18.901 pt/m on all four sheets = 1:150). Preflight (no scores): axis-bubble distances gave 19.12 (p6)
  and 19.40 (p8) pt/m, inconsistent with the level marks, so `scale_levels` is used for all views.
- **Cases** (#145 `cases`, unchanged): per view full, mirror (injected), 9 synthetic crops (25/40/60 % at
  0/0.5/1.0) = 44 rows.
- **Code**: #149 `run.py` `measure`/`summarize`, `score.py`, `rays_type.py` at `94b74bca` and #145 helpers at
  `640b3678`, staged from git and executed as is. Only byte change: the #145 ELV outlier-height skip in
  `rays_type.py` `> 30.0` -> `> 60.0` (this building is 46.5 m; 0 objects skipped by the probe).
- **Preflight geometry finding (recorded before scores).** The drawn views are wider than the model faces:
  p5 151.3 m, p6 156.8 m (model az 90/270 face 147.0 m), p7 72.9 m, p8 69.9 m (model az 0/180 face 60.6 m); the
  sheets draw parts of the neighbouring stages (Котельная, Водный комплекс, red «Граница этапов»). D slides the
  view inside the model face ± 0.6 m, so a wider view scores −1 on its own face: p5/p6 full can only abstain,
  and p7/p8 full can only fit the long faces — the wrong ones. This is the transfer hazard measured here.
- **Primary metric (D, unchanged).** correct / wrong / abstain per class (full, synthetic_crop, mirror).
- **Acceptance H151 (frozen).** D: full wrong 0, full correct ≥ 3 of 4, crop wrong ≤ 1, crop correct ≥ 15 of 36,
  witness `p5 228.8-86.8 full` correct. (By the preflight geometry full correct ≥ 3 and the witness are
  infeasible for D; they stay as the transfer bar. The informative D numbers are the wrong counts.)
  Invariance: reversed view-palette relabelling must change 0 of 44 rows (run 1, every row exercised).
- **Secondary, pre-declared diagnostic G** (not a keep; candidate for the shared step if it holds): D unchanged
  when the view fits the face; when the view is wider than face + 2 slack, slide face-width windows of the view
  (step 2·slack+1 px, gap-free with D's ±slack search), trim each window to its own top row, score with D, take
  the max. Bounds: G full wrong 0, full correct ≥ 3, crop wrong ≤ 1, G = D on every non-windowed row.
- **Not measured.** Real untitled partial views (this set has none; only synthetic crops), inner-corner /
  footprint-edge candidates, KPP1/AC08/OBR22/G22/Vatutino, Sokolniki (held out), within-face localisation,
  accepted-vs-rejected delivery quality, line-based A/C on this pair.
- **Replay and budget.** `git fetch origin research/autoresearch-standing-145 research/autoresearch-standing-149`,
  then `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-transfer/run.py
  C:/x/ar151/<fresh>` (pilot host, inputs mounted; Blender 4.4 hash-checked). Three fresh runs (Blender import +
  ray cast + scoring each), byte-identical row JSON required; median/min/max wall reported. One candidate (D) +
  one pre-declared diagnostic (G). Stop `inconclusive` if elapsed + 1.15 × first-run s × remaining runs > 3600 s
  or on any parity failure; timing stop and hypothesis verdict are reported separately.
- **Forbidden.** Threshold/label/box/GT changes after seeing scores, fixture substitution, reading Sokolniki
  outputs, editing source drawings, models, deliveries, production `src/` or other cards' files, weakening guards.

## Result

(after measurement)
