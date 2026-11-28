# #159: view-side signature realism (drawn W/H vs the model wall) for the view<->face sheet

## Резюме (по-русски)

Гипотеза H159 (ширина и высота, снятые с реального векторного фасада, совпадают со «стеной» модели из #157 в
допуске +-1,2 / +-1,0 м, и правило #157 не даёт уверенно неверных ответов на реальных видах): **ОПРОВЕРГНУТА**.
Ни один из 11 полных видов (ЭЛВ 7, Олимпийский 4) не попал в допуск своей стены (0/11), с огибающей стороны - 1/11.
Правило #157 (только стены на земле, один кандидат, нет соседа на 2 tau) на 13 реальных видах: 0 верно / **0 неверно** /
13 отказ, при масштабе 0,95 и 1,05 так же - безопасно, но не отвечает ни разу. Свидетель срабатывания есть (запрос
«стена сама себе» отвечен 1/1 в каждой модели). Три прогона побайтно одинаковы, медиана 14,35 с.
Почему: (1) стены #157 - кластеры плоскостей, а чертёж показывает всю сторону сразу (ЭЛВ: dW до 37 м к стене,
0,75-3,3 м к огибающей); (2) выделение #157 теряет первый этаж под навесами (ЭЛВ ось 0: стены с z 4,6 м, на чертеже
от земли). Пост-хок (не keep): с габаритом модели по направлению ширина ЭЛВ совпала на 6/6 прямых полных видах
(|dW| 0,19-0,88 м); высота меньше на 1,9-3,3 м - в модели есть подземная часть до -3,05 м, чертёж режется по земле.
На Олимпийском читатель отрезков ловит линии земли/выноски за зданием (+4...+12 м по ширине).
Для шага «view<->face map sheet»: подпись стен #157 к реальным видам **не применять** (покрытие 0); сравнивать
вид с надземным ортосилуэтом модели по направлению (и его отрезком для частичного вида), а габарит вида брать по
заливкам/контуру здания, а не по всем линиям. Sokolniki не открывался (#2001 открыт).

## Frozen contract (committed before any measurement)

- **Why.** #157 recommended, for an untitled partial view, to propose a wall only if its signature (W, H at
  +-1.2 / +-1.0 m, plus window columns/rows) matches exactly one ground-standing wall of the model with no neighbour at
  2 tau, else ask. #157 measured only the model side ("tolerance realism ... is the open item", #157 next 1). This
  round measures the view side on real drawn views with a known answer: how far is W/H read from a drawn vector
  elevation from the wall it shows, and does the #157 rule stay at 0 confident-wrong on real views.
  Sokolniki (#2001 OPEN) is not opened.
- **Views (pinned, reused unchanged).** ELV TC Sreda booklet (#145 `fixture.json` on main: 7 full views, fragments
  p23 D-G and p24 8-9; p20 9-10 is top-cut -> H `not_exercised`, W reported only) and Olimpijsky AR.2 p5-p8 (#151
  `fixture.json` at `4a6c6b77`: 4 full views). Boxes, drawing scale and `gt_az` exactly as frozen there; drawing
  segments by #145 `run.py` `segments()` and `scale_pt_per_m()` (main `e49d791c`, loaded by `runpy`).
- **Model walls (pinned).** #157 wall tables `elv.fwd.json` (SHA-256 `ac816566...dca8`) and `olimpijsky.fwd.json`
  (`3d9e8b92...93c6`) from `G:/Мой диск/AGR-evidence/157-view-face-signature/` (match its `SHA256SUMS.txt`);
  window counts by #157 `score.py` `attach_windows` (branch `research/autoresearch-standing-157@9acdeb0d`). No
  Blender run. PDFs: ELV `49c10527...`, Olimpijsky `cdf938e8...`. `run.py` checks every hash first.
- **View measurement (frozen).** W_view = x extent, H_view = y extent of the kept segments, in metres. Window counts
  are **not read from the views** (both albums are curtain-wall/finish-fill drawings; glass is not a countable object
  class) -> signature B on real views is **not measured**; signature A (W, H) is scored.
- **Truth (frozen).** Side walls = #157 walls with circular |az - gt_az| <= 10 deg. Truth wall = largest-area side
  wall. Side envelope = min u0..max u1, min z0..max z1 over the side walls (diagnostic).
- **Metric 1 (realism).** Per full view dW = W_view - W_truth, dH = H_view - H_truth; inside = |dW| <= 1.2 and
  |dH| <= 1.0. Same vs envelope (diagnostic). Fraction inside over the 11 full views.
- **Metric 2 (rule safety, primary safety number).** Rule A_ground (#157 recommendation without window counts):
  candidates = ground-standing walls (z0 <= model min z0 + 1 m) matching A; answer iff exactly one candidate and no
  other wall (all walls) matches A at 2 tau; else abstain. Rule A_all = same with all walls as candidates
  (diagnostic). Outcome per view: correct = answered wall on the gt side; wrong = answered wall on another side;
  abstain. Scored views: 11 full + 2 fragments (13); p20 reported, not scored.
- **H159.** CONFIRMED if Metric 1 inside >= 50 % of the 11 full views AND A_ground has 0 wrong on the 13 views.
  REFUTED if inside < 30 % OR A_ground has >= 1 wrong. Else INCONCLUSIVE.
- **Witness / perturbations (frozen).** Positive trigger witness: a synthetic query equal to each ground-standing
  wall's own (W, H) must be answered with that wall or abstain by the 2-tau neighbour rule (count both; 0 wrong
  expected). Perturbation: every real view at drawing scale k in {0.95, 1.05}: record outcome changes per view
  (expected: inside fraction drops or stays, wrongs stay 0). Invariance: views processed in reverse order -> identical
  rows (changed count recorded).
- **Series and budget.** 3 fresh runs into new directories; `rows.json` and `score.json` byte-identical; median wall
  time. Budget 45 min; up to 3 different repair attempts on extraction only before any score is read. No tuning of
  any frozen number after the first score is printed. Budget stop = inconclusive.
- **Forbidden.** Opening Sokolniki; editing delivered packages, other cards' files or product code; changing boxes,
  scales, tolerances or truth after scoring; dropping views by hand.
- **Replay.** `uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-realism/run.py <new_dir>`
  (pilot host: PDFs on the Desktop paths in the fixtures, #157 evidence on the Drive; `git fetch origin
  research/autoresearch-standing-151 research/autoresearch-standing-157`).

## Round log

- **Contract** `0af75f21`; runner + fixture + unit test `e84a764c` (before the first score). No repair attempts.
- **Series:** `run.py C:/x/ar159/run{1,2,3}` at `e84a764c`: `rows.json` (SHA-256 `deccadf4...`) and `score.json`
  (`773d6240c618edc8e67ca8a05af2941841293f0fb971872d2f0bdf249374be0a`) byte-identical in all 3 runs. Wall time
  14.694 / 14.346 / 14.350 s (median 14.350 s, spread 0.348 s), status completed inside the 45 min budget.
- **Invariance:** reverse view order -> 0 changed rows (14 rows exercised).
- **Metric 1 (realism):** inside truth wall 0/11, inside side envelope 1/11 (ELV p19 A-I). Per view:

| view | drawn W x H | truth wall W x H | dW / dH | envelope dW / dH |
|---|---|---|---|---|
| elv p18 I-A | 54.42 x 17.52 | 18.35 x 9.40 | 36.07 / 8.12 | 0.95 / 5.93 |
| elv p18 1-10 | 88.52 x 16.62 | 77.57 x 17.09 | 10.95 / -0.47 | 2.33 / -2.76 |
| elv p19 10-1 | 88.50 x 16.42 | 51.13 x 14.49 | 37.37 / 1.93 | 3.09 / -0.40 |
| elv p19 A-I | 54.71 x 17.14 | 48.09 x 14.67 | 6.62 / 2.47 | 0.75 / -0.74 |
| elv p19 6-1 | 52.16 x 15.59 | 51.13 x 14.49 | 1.02 / 1.10 | -33.25 / -1.23 |
| elv p21 I-A | 54.42 x 17.09 | 18.35 x 9.40 | 36.07 / 7.69 | 0.95 / 5.50 |
| elv p21 1-12 | 88.10 x 16.05 | 77.57 x 17.09 | 10.53 / -1.04 | 1.91 / -3.33 |
| elv p23 frag D-G | 20.18 x 15.95 | 18.35 x 9.40 | 1.82 / 6.55 | (fragment) |
| elv p24 frag 8-9 | 14.80 x 16.04 | 77.57 x 17.09 | -62.77 / -1.05 | (fragment) |
| olim p5 | 151.26 x 43.30 | 60.42 x 27.42 | 90.84 / 15.88 | 4.90 / 9.53 |
| olim p6 | 156.76 x 47.66 | 60.42 x 26.13 | 96.34 / 21.52 | 10.35 / 14.90 |
| olim p7 | 72.87 x 45.38 | 48.27 x 30.96 | 24.61 / 14.41 | 14.22 / 13.60 |
| olim p8 | 69.81 x 47.23 | 48.27 x 31.16 | 21.54 / 16.07 | 11.23 / 16.07 |

- **Metric 2 (safety):** A_ground 0 correct / 0 wrong / 13 abstain at k = 1.0, 0.95, 1.05; A_all identical. Only
  p20 (top-cut, not scored) has A_all candidates (4 small walls) and no A_ground candidate.
- **Witness:** ground-standing self-queries answered 1/1 per model (0 wrong, 0 abstain) -> the rule fires on an exact
  signature. Window counts from views: **not measured** (curtain-wall / finish-fill albums). Signature B on real
  views: **not measured**.
- **H159: REFUTED** (inside 0/11 < 30 %). Safety part held (0 wrong), coverage 0.
- **Post-hoc diagnostic (declared after the score, not a keep):** `posthoc.py` compares drawn W/H with the model's
  ortho extent per side from the #145 ELV `rays-1.npz` (`111818b8...`) and #151 Olimpijsky `types-1.npz`
  (`66105de7...`, copied to the evidence). The rasters are cropped to the model bbox, so this is the bbox extent per
  direction, not a measured silhouette. ELV face-on full views: |dW| 0.19-0.88 m on 6/6, dH -1.9..-3.3 m (model has
  geometry down to z -3.05 m, the drawing is cut at grade -0.15 m); p19 6-1 shows only part of the side (-36.5 m).
  Olimpijsky dW +4.1..+12.1 m, dH -3.1..-7.5 m: the segment-extent reader includes ground lines/callouts beyond the
  building, and the model bbox includes below-grade geometry. Output: [`posthoc.json`](autoresearch-view-face-realism/posthoc.json).
- **Receipt:** [`receipt.json`](autoresearch-view-face-realism/receipt.json) = run1 `score.json` (runner SHA-256
  `773d6240c618edc8e67ca8a05af2941841293f0fb971872d2f0bdf249374be0a`) with all pins. Evidence:
  `G:/Мой диск/AGR-evidence/159-view-face-realism/` + `SHA256SUMS.txt` (11 files, manifest SHA-256
  `3e807ff95ceb86e3d9c06639b9439d32ae77a88b40a4dae5ad114ad3c6671c3d`). Replay limited to the pilot host.

## Recommendation for the OKS step "view<->face map sheet" (measured, OBSERVE)

1. Do **not** use #157 wall-cluster signatures against drawn views: on 13 real views coverage is 0 (safe, never
   wrong, never useful); the clusters split a side into depth planes and lose canopy-covered ground floors.
2. Model side for the size check: the above-grade ortho extent per candidate azimuth (grade from the drawing's
   +-0.000 mark), and for a partial view its sub-interval (#153 localisation). On ELV the width already agrees within
   0.9 m on 6/6 full views (post-hoc, needs a frozen re-test).
3. View side: building-only extent (finish fills or the closed outline), not all orthogonal segments in the box
   (Olimpijsky +4..+12 m from ground lines/callouts).
4. Until 2-3 are re-measured on a frozen contract, a size match is a corroborating cue only; answer/ask stays with
   keyplan (#152), finish partition D (#149) and the break veto (#158).
