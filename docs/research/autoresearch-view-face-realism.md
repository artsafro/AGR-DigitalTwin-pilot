# #159: view-side signature realism (drawn W/H vs the model wall) for the view<->face sheet

## Резюме (по-русски)

(заполняется после серии; до этого действует только замороженный контракт ниже)

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

(after the series)
