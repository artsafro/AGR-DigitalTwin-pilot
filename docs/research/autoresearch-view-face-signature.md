# #157: wall-signature identifiability for untitled partial views (inner-corner walls)

## Резюме (по-русски)

_Заполняется после замера (ниже - контракт, зафиксированный до любых расчётов)._

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

_After scoring._
