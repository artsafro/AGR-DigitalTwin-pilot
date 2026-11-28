# #157: wall-signature identifiability for untitled partial views (inner-corner walls)

## Резюме (по-русски)

Гипотеза H157 (стену частичного вида во внутреннем углу можно узнать по «подписи» стены модели: ширина, высота,
число колонн и рядов окон): по замороженным порогам **ОПРОВЕРГНУТА**. На Савеловской уникальны 68 % «внутренних»
стен (порог 70 %), и при ошибке масштаба 5 % 3,7 % запросов дают уверенно неверную стену (порог 3 %). Все ошибки -
низкие полосы без окон (H 3,1-3,6 м, парапеты и уступы над кровлей) и один почти-близнец на Московском (две соседние
стены 9,4 x 19,0 и 10,5 x 20,3 м, 4x4 окна). Объявленная до расчёта диагностика: стены внутренних углов, стоящие на
земле (то, что показывает частичный вид), уникальны **5/5 (Савеловская) и 7/7 (Московский)**, соседа на двойном допуске
нет; при ошибке масштаба 5 %: 14 верно / 0 неверно / 10 отказ (отказывают стены длиннее ~28 м или выше 20 м). Вид, обрезавший
колонну окон, всегда отказ. ELV: 0 таких стен (как в #153), Олимпийский: 1. Три прогона побайтно одинаковы, 387 с.
Для шага «view<->face map sheet»: кандидатами брать только стены на земле, отвечать при одном кандидате и без соседа
на двойном допуске, иначе спрашивать. Сами листы (Савеловская, Московский) - растровые, частичных видов нет: точность
по реальным видам **не измерена**. Sokolniki не открывался (#2001 открыт).

## Frozen contract (committed before any scoring)

- **Why.** #139-#156 measured side identity (keyplan marks, finish partition D, raster/edge cues) and within-side
  localisation (+-1.2 m, #153). The open item for the OKS step "view<->face map sheet" is the Sokolniki STOP 04 case
  (#2001, held out, not opened here): an untitled partial view of a wall in an inner corner / courtyard, i.e. a wall
  that is NOT seen face-on in any of the four main elevations. No calibration album with independently labelled
  partial views of such walls exists (ELV: one wall per side, #153; Olimpijsky: none; KPP1/AC08/OBR22 screened
  before). Two new Weltbau pairs were screened for this card: Savelovskaya UVK1000 V3 (same typology as Sokolniki)
  and Moskovsky SHK1200 V3 - both elevation sheets are raster tiles with four full keyplan-marked views and no partial
  views, so a view-side score is **not measured** in this round. What can be measured without the held-out key is the
  **ceiling** for any signature method: if a partial view shows one whole wall, how often does the wall's own
  signature (width, height, window columns/rows) pick exactly one wall of the model, and how often does a small
  measurement error turn that into a confident wrong answer. That number decides whether the step may propose an
  answer for inner walls or must ask.
- **H157.** On both Weltbau models, signature B (W, H at +-1.2 m / +-1.0 m, plus exact window column and row counts)
  is unique for >= 70 % of *inner* walls (>= 5 inner walls exercised per model), and the perturbed queries (W, H
  scaled by 0.95 and 1.05) give 0 confident-wrong answers over all walls of both models.
  **Refuted** if either model < 50 % or perturbed confident-wrong > 3 % of queries on either model.
  Otherwise, or if < 5 inner walls are exercised on a model, **inconclusive**.
- **Inputs (pinned).** [`fixture.json`](autoresearch-view-face-signature/fixture.json): 4 Revit FBX with SHA-256
  (Savelovskaya, Moskovsky = gated; ELV, Olimpijsky = reported controls, not gated), Blender 4.4 hash as #149. The two
  PDFs are hashed for the record and not scored. `run.py` checks every hash before running.
- **Walls (frozen).** Meshes as #149 `rays_type.py` (UCX/UBX/USP/UCP/COLIZ skipped, objects reaching z > 30 m
  skipped). Vertical triangles `|n.z| < 0.1`, area >= 0.02 m2. For each side s in {+n, -n}: the side is *exterior* if
  the segment c -> c + 0.6 s is free and an upward ray from c + 0.6 s escapes (no hit). Exactly one exterior side
  required, else the triangle is dropped (fins, parapets, interiors). Horizontal exposure ray from c + 0.02 s along s:
  no hit = **open**, hit at >= 2.0 m = **inner**, hit < 2.0 m = dropped (reveal / niche). Grouping: azimuth bin 2 deg;
  within a bin, plane depth d = s . c single-linkage clusters (gap 0.5 m); within a depth cluster, u = c . t
  (t = (-s_y, s_x)) triangle extents merged with gap <= 0.5 m -> one **wall** = (az, depth cluster, u interval).
  W = u extent, H = z extent, class = area-weighted majority open/inner. Kept: W >= 3.0 m and H >= 3.0 m.
- **Windows (frozen).** Objects whose name contains `окно`, `window` or `витраж` (case-insensitive); centre = bbox
  centre. Window belongs to a wall if its centre lies within the wall's depth range +-0.8 m, u interval and z
  interval. ncol / nrow = number of 1D single-linkage clusters (gap 0.6 m) of window u / z centres.
- **Signatures (frozen).** A = (W, H), tau_W 1.2 m, tau_H 1.0 m. B = A + exact (ncol, nrow). R (scale-free) =
  |ln(W/H) - ln(W'/H')| <= 0.05 + exact (ncol, nrow). Wall i is *unique* under X if no other wall matches it.
  Risk2 = share of walls with another wall matching under B at 2 tau.
- **Perturbed queries (frozen).** For every kept wall i and k in {0.95, 1.05}: query = (k W_i, k H_i, ncol_i,
  nrow_i), candidates = walls matching under B. correct = {i}; wrong = exactly one candidate != i; abstain = none or
  several. Also a window-cut query (ncol_i - 1, a partial view that misses a column) for walls with ncol >= 2.
- **Invariance.** Each model is processed twice in the same run: objects in name order and in reverse order. The wall
  table must be identical (per-model changed count recorded; models without windows label the window checks
  `not_exercised`).
- **Series and budget.** 3 fresh runs into new directories; outputs must be byte-identical (wall tables and score
  JSON); median wall time recorded. Budget: 90 min total for the series; if a run crashes, up to 3 different repair
  attempts on extraction only, each recorded with its error, before any score is read. No tuning of any frozen number
  after the first score is printed. Budget stop = inconclusive.
- **Forbidden.** Opening Sokolniki sources or accepted outputs; editing delivered packages, other cards' files or
  product code; changing tolerances after scoring; dropping walls from the score by hand.
- **Positive trigger witness / controls.** Moskovsky (courtyards visible on its sheet p3 isometric) must produce
  inner walls; if fewer than 5 the extraction is wrong and the result is `not measured`, not a refutation. ELV
  (#153: one wall per side) is the low-inner control. A plan PNG per model (walls coloured open/inner) is written as
  evidence and inspected by eye against the sheet keyplans.
- **Replay.** `uv run --offline --locked python docs/research/autoresearch-view-face-signature/run.py <new_dir>`
  (pilot host; inputs per fixture.json; Blender 4.4).

## Round log

- **Contract** `d021c0dd`; runner/extraction/scoring `5fecbc13`, test fix `eea720db` (frozen before the first
  score: the ground-standing diagnostic was added to `score.py` before any run). No repair attempts were needed.
- **Feasibility probe (before the contract, not scored):** both Weltbau FBX are Revit exports in metres
  (Savelovskaya 166 x 62 x 17.7 m, 11108 objects; Moskovsky 115 x 66 x 21.6 m, 8846 objects) with per-instance
  window objects (`WB_120_Окно_*`, `ADSK_ОкноВитражное*`, `ASML_АР_Витражная*`).
- **Series:** `uv run --offline --locked python docs/research/autoresearch-view-face-signature/run.py C:/x/ar157/run{1,2,3}`
  at `eea720db`. All 9 output files byte-identical across the 3 runs. Wall time 387.242 / 385.177 / 394.695 s
  (median 387.242 s, spread 9.5 s); status completed, inside the 90 min budget.
- **Invariance:** name order vs reverse order: 0 changed walls on all 4 models, window lists identical (exercised).

| model | walls | inner | inner unique A / B / R | inner risk2 B | open unique B | perturbed correct / wrong / abstain | ground inner n, unique B, risk2 |
|---|---|---|---|---|---|---|---|
| savelovskaya (gated) | 35 | 19 | 0.58 / 0.68 / 0.74 | 0.47 | 0.94 | 26 / 3 / 53 (3.7 %) | 5, 1.00, 0.00 |
| moskovsky (gated) | 29 | 13 | 0.77 / 0.92 / 1.00 | 0.08 | 0.81 | 23 / 1 / 48 (1.4 %) | 7, 1.00, 0.00 |
| elv (control) | 34 | 21 | 0.29 / 0.43 / 0.62 | 0.62 | 0.77 | 23 / 0 / 52 | 0, n/a (not exercised) |
| olimpijsky (control) | 93 | 52 | 0.21 / 0.23 / 0.29 | 0.88 | 0.27 | 26 / 8 / 168 (4.0 %) | 1, 1.00, 0.00 |

- **H157: REFUTED** (Savelovskaya inner unique B 0.684 < 0.70 and perturbed wrong 3.66 % > 3 %).
- **Where the wrongs are.** Savelovskaya walls 5 and 22: inner, 24.5 / 25.4 x 3.4 m, no windows (strips above lower
  roofs; doubled lines on the plan PNG). Moskovsky wall 25: open, 10.46 x 20.29 m, 4 x 4 windows; at scale 0.95 its
  height misses itself by 1.01 m and the adjacent wall 24 (9.41 x 18.99 m, 4 x 4) is the only candidate.
- **Diagnostic (declared before scoring, not gated): ground-standing inner walls** (z0 <= lowest + 1 m, the subjects
  of inner-corner partial elevations). Savelovskaya 1, 2, 3, 24, 28; Moskovsky 1, 2, 3, 4, 5, 6, 12. All unique under
  A, B and R with no neighbour at 2 tau. Scale-perturbed queries 14 correct / 0 wrong / 10 abstain (abstain = walls
  28-49 m long or 20 m high, where 5 % exceeds the tolerance); window-cut queries 0 / 0 / 7 (exact counts never
  match a cut view).
- **Witness check (by eye on the plan PNGs).** Savelovskaya walls 2/28/1 = the notch at the top-left of the keyplan
  (real inner corner); Moskovsky 1 and 12 face each other across the stepped middle (real inner corners, sheet p3).
  Spurious "inner" walls: rooftop boxes and above-roof strips (Savelovskaya 7/14/19/20/21/29 with z0 8.7-12.9 m, ELV 21 of 21);
  they are what the ground filter removes. ELV ground inner 0 matches #153 ("one wall per side").
- **Not measured.** Any view-side number: both new sheets are raster tiles with four full keyplan-marked views and no
  partial views, so no measured W/H/window counts from drawn views, no real-view accuracy. Tolerance realism
  (is a drawn partial view within 1.2 m / 1.0 m and exact window counts of its wall?) is the open item.
- **Receipt:** [`receipt.json`](autoresearch-view-face-signature/receipt.json) = run1 `score.json`
  (SHA-256 `cc50e3306b953656f1a6baed9a621e75cd33de4c409239c009b66380c671a21e`, identical in run2/run3) with all pins.
  Evidence (wall tables fwd/rev, plan PNGs, score, wall time): `G:/Мой диск/AGR-evidence/157-view-face-signature/`
  + `SHA256SUMS.txt` (14 files, manifest SHA-256 `3751f27e4ce36eb4cc51cd42d8e61bbddabcf9ce8f1dfbed2c088328fe7783ae`).
  Replay is limited to the pilot host (customer FBX outside git).

## Recommendation for the OKS step "view<->face map sheet" (measured, OBSERVE)

1. Side for full views: keyplan mark (#152) or finish partition D (#149) as before; within-side interval +-1.2 m (#153).
2. Untitled partial view that matches no main elevation: candidates = **ground-standing** exterior walls of the model
   (all azimuths, this runner's extraction). Measure W, H at the sheet scale and window columns/rows from the view.
   Answer only if exactly one candidate matches (+-1.2 m / +-1.0 m, exact counts) **and** no other wall lies within
   2 tau; otherwise ask Artem with the candidate list. Measured ceiling on the two Weltbau schools: 12/12 ground
   inner walls unique; under 5 % scale error 14/24 queries correct, 0 wrong; long or tall walls and views that cut a
   window column fall back to asking.
3. Not yet allowed: answering without a view-side measurement check (not measured here) - see next targets.
