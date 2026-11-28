# Autoresearch #161 — view -> wall direction by drawn glass vs model glazing (Silikatny, OBSERVE)

## Кратко для Артёма

(заполняется после замера; контракт ниже заморожен до первого счёта)

## Frozen contract (committed before any score was computed)

Card t_4246c1cc (standing #161), focus 0 (view<->face map sheet). #2001 is OPEN: Sokolniki is held out and was not
opened. Rounds #145-#160 all ended with next step (1) "an independent album with REAL inner-corner views"; ELV,
Olimpijsky, OBR22, KPP1, AC08, Savelovskaya and Moskovsky have none. #2073/#2074 own finish-partition scoring,
#2075 owns wall exercise; atlas / form / trainer targets were not reopened.

**Fixture (never used by #139-#160; screened in this card).** Silikatny UK350/DO150 school (Mosproekt-4), Weltbau
`Silikatniy_UVK`: AGR album `Альбом АГР_Силикатный_ корр. Гранель 08.04.25 (2).pdf` (35 p, SHA-256 `785e4015…9131`)
and the Revit model exported from DWFx R23 by category, `context_full_model_by_category.obj` (17 category objects,
1.72 M tris, SHA-256 `6ab64e6b…ea62`). The plan is V/7-shaped (left wing, top wing, oblique wing at 60 deg) with a
concave courtyard side carrying a curved glazed stair. Views: 5 full facade schemes (p14 1-4', 4'-1; p15 K-A, A-G,
A'-K) and 2 real 1:20 fragments (p16 box bay, p17 curved stair zone, both titled only «Фрагмент фасада»). The
GRN_2_SLK FBX in the same folder is the neighbouring residential complex, not this school (checked: heights to 245 m).
Known confound, recorded before scoring: the album is dated 08.04.25 and the model is R23 (28.08.26) with renamed axes
(1-12 / A-1..Ж-1 in the R23 facade DWG vs 1-4' / A..K in the album); content drift is part of the test.

**GT (model geometry + visibility only, labelled before scoring; titles not used by the method).** Candidate
directions = the 8 peaks of the area-weighted horizontal normal histogram of `Ctx_steny` (0, 60, 90, 150, 180, 240,
270, 330). A'-K and fragment 1 = the oblique wing's curtain-wall side with 7 projecting glazed boxes, normal 330 (box
glass normals 150/330 at x 62-89 m; the boxes are visible from 330 and only obliquely from 0/270) -> {330}. 4'-1 = the
large glazed truss block on the top wing's north side -> {90}. 1-4' (developed courtyard facade) and fragment 2 (the
truss/screen/stair zone on the concave side) -> {240, 270} (the V-truss block is seen frontally between those two
directions; both accepted). K-A and A-G: no independent GT within this card -> diagnostic rows, not scored.
Inner (courtyard) views: 1-4' (full, developed) and fragment 2 (real partial). Hard negatives: the opposite direction
(reported per row) and the near-parallel neighbour 0 for the 330 views.

**Candidate G (one, frozen in `autoresearch-view-face-glass/fixture.json`).** View: page raster at zoom 4 inside a
fixture clip; building = pixels with RGB sum < 760; view box = bbox after a 7 px opening; glass = building pixel, not
red, farther than 45 RGB units from every legend swatch on p15 (RAL 1013 panel, RAL 5001, RAL 7031, white) and
luminance 100-225. Vertical scale: the box spans 0.000-12.900 (parapet level on every sheet; fragment 1 dimension
chain sums to 12 900); isotropic. Model: Blender 4.4 Workbench orthographic renders per candidate az at 0.1 m/px,
`Ctx_okna` + `Ctx_paneli_vitrazha` black, all else grey, slabs hidden; band z 0-12.9 m. Both masks resampled to
0.25 m. Score(az) = max Pearson NCC over horizontal offsets with overlap >= 0.8 x the narrower width. Answer = top az
if score >= 0.30 and margin to the best other az >= 0.10 (the #140 frozen values, inherited, not tuned), else
abstain. Pre-score check (boxes and masks only, no NCC) is recorded below.

**Primary metric.** correct / wrong / abstain on the 5 scored views; answered accuracy = correct / answered (undefined
if 0). Secondary: inner views separately (2), fragments separately (2), opposite-direction score per row.

**Acceptance H161 (frozen).** wrong = 0 on the 5 scored rows, AND correct >= 3/5, AND at least one of the
two inner views correct. Wrong >= 1 or correct < 3 refutes. Positive trigger witness: A'-K must answer (it has the
strongest unique glazing pattern); abstention witness: every `blank` state must abstain.

**Perturbations (constructed, per state changed-pixel counts recorded).** `mirror`: view mask flipped left-right —
expected: the true az no longer wins with margin (abstain or other az); a pattern-blind scorer would still answer. Near-symmetric views (A'-K, F1) may legitimately keep the true az; mirror is reported per row and is not part of acceptance.
`blank`: glass mask zeroed — expected abstain (NCC undefined -> 0). Not measured: rotated sheets, fresh native
re-export from Revit, rejected deliveries (none exist for this object), Sokolniki transfer (held out), wall
interval/bay localisation (a fragment's offset is reported, not scored), K-A / A-G identity.

**Stability / budget.** Replay `uv run --offline --locked --extra pdf-review python
docs/research/autoresearch-view-face-glass/run.py C:/x/ar161/<fresh>` (pilot host with the owner's Weltbau folder;
Blender 4.4). Three fresh runs, each re-renders the model and re-reads the PDF; row JSON must be byte-identical;
median / spread wall time reported. One candidate, no retuning after the first score; a failed row is reported, not
fixed. Stop `inconclusive` if the three runs exceed 30 min in total or on a parity failure.

**Forbidden.** Changing params, GT, clips or states after a score; opening Sokolniki outputs; editing source drawings,
models, deliveries, production `src/` or other cards' files; weakening guards.

## Pre-score check (no NCC computed)

View boxes / widths (m) / glass fraction: A'-K 73.4 / 0.49; 4'-1 91.6 / 0.28; 1-4' 83.4 / 0.25; F1 10.7 / 0.58;
F2 10.9 / 0.79; K-A 54.9 / 0.22; A-G 27.2 / 0.32. The masks show window rows, the 7 boxes and the truss blocks;
F1/F2 boxes touch their clips (the 1:20 sheets carry dimension chains inside the clip) — kept as frozen.

## Round log

(after scoring)

Full suite: deferred to merge batch (rule 68).
