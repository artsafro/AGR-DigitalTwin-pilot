# Autoresearch standing #31: calibrated Ground NPM quality number (OBSERVE)

Card t_193a0887, branch `research/autoresearch-standing-31`. Focus set by Artem 2026-11-21 («Переключай»: Ground).
Mode: OBSERVE only. No Ground is built or repaired here (that is #1738); no delivered package is edited.

## Краткий итог (по-русски)

Заполняется после замера (раздел «Round log»). Контракт ниже заморожен до первого замера.

## 1. Contract (frozen before any measurement)

### Metric

`Q` = Ground defect density, defects per 10 000 triangles, lower is better:

    Q = 1e4 * (V + F + C) / T

- `V` = xView overlapping vertices, `F` = xView overlapping faces: the repo kernel `dt_ai.ops.xview_gate.gate_report`
  (inv_xview, profile NPM: vertex 2 mm, face 5 mm, parallel cos 0.9999), coords `local`, summed over the mesh parts.
- `C` = crack edges: open (one-face) edges whose midpoint lies within 5 mm (xView face_m) of another open edge of the same
  part that shares no vertex index with it (unstitched seam / T-junction). The true outer border and building holes
  are open edges too but have no coincident open partner, so they do not count.
- `T` = triangles after fan triangulation (a k-gon counts k-2), summed over the parts.
- Parts whose name starts with `UCX_` are ignored (collision, not render mesh).

One number per input. Components V, F, C, T and the per-part table are published next to Q.

**Amendment 1 (before the series, after the dump):** the delivered NTR `*_Ground.fbx` files carry the whole site
package (objects `*_Ground`, `*_GroundEl`, `*_GroundElGlass`, `*_Flora`). The fixture is the Ground surface, so
the scored parts are the objects whose name ends with `_Ground` (one per input; SIL13 `SM_SIL13_Ground`, Vatutino
`SM_Vatutino_Ground`). The all-parts score is published next to it as `Q_all` (secondary, not used for the
verdict). Seen before this amendment: probe scores of A1, A2 (all parts) and F5 only (first-pair timing).
F3 and F5 dumps are byte-identical (r5 changed no geometry), so the fixture has 4 distinct failed meshes.

### Fixture (frozen; SHA-256 in `docs/research/autoresearch-ground-quality-harness/inputs.sha256`)

Accepted (A), Artem's own delivered NPM Ground (latest revision folder, read-only originals in
`C:/Users/artsafro/Desktop/!3D viz/NTR/`, byte-identical copies in `C:/x/ground-etalons/` and
`C:/x/ev_t_193a0887/inputs/`), plus the accepted Vatutino precedent:

| id | source | why accepted |
|---|---|---|
| A1 | Vatutino Ground v015 NPM, `session-v001.zip!artefacts/ground-v015-dcc-v001/textured/npm/SM_Vatutino_Ground.fbx` (`G:/Мой диск/AGR-evidence/371-ground-v015-route-a-20261104/`) | D193, docs/cases.md |
| A2 | 14_Skolkovo `pravki_15.09/LP/0809_BolshoyBulvar_64_Ground.fbx` | delivered (NTR) |
| A3 | 22_COD `maps/low/0309_Tup_Skladochnyj_ZU_5_1_Ground.fbx` | delivered (NTR) |
| A4 | 29_Donskoy `0610_5jDonskoyProezd_Vl_15/0610_5jDonskoyProezd_Vl_15_Ground.fbx` | delivered (NTR) |
| A5 | 31_Ostrov `0906_NizhnieMnevniki_ZU_66_Ground.fbx` | delivered (NTR) |
| A6 | 32_Kasatkino `blender/0301_Kasatkina_Vl_11/0301_Kasatkina_Vl_11_Ground.fbx` | delivered (NTR) |
| A7 | 6 (Volokolamskoe) `0903_VolokolamskoeShosse_Vl_71_22_Ground.fbx` | delivered (NTR) |
| A8 | Stolbovo `1113_DerevnyaStolbovo_Uch_23_Ground.fbx` | delivered (NTR) |

Failed (F), SIL13 #1315 NPM Ground pilots, not adopted / rejected
(`G:/Мой диск/AGR-evidence/1315-cold-silikatny/`):

| id | file | receipt |
|---|---|---|
| F1 | `npm-ground-stitch-r1-NOT-ADOPTED/pilot/geometry.npz` | 843 one-face edges, stopped before FBX |
| F2 | `npm-ground-stitch-r2-BUDGET-CHOICE-NOT-ADOPTED/working-xview-input.npz` | xView 16 / 1 767, budget 187 102 |
| F3 | `npm-option-a-ground-r3-NOT-ADOPTED/ground-micro.npz` | xView 16 / 1 751 |
| F4 | `npm-ground-reprofile-r4-REJECTED/ground.npz` | xView 27 / 1 576 |
| F5 | `npm-ground-retess-r5-REJECTED/ground.npz` | xView 16 / 1 751 |

VPM: there is no rejected SIL13 VPM Ground, so VPM is **not measured** in this calibration (VPM copies of the
delivered packages are listed in the harness for the next lane only).

FBX inputs are dumped once with the repo dump `tools/blender/xview_dump.py` (Blender 5.1, read-only on the source)
and converted to metres with `xview_gate.to_metres`; the metre dumps are hash-bound in `dumps.sha256`. F1 is
converted from its `vertices/faces` arrays to the dump format (one part `SM_SIL13_Ground`, location 0).

### Calibration rule (keep threshold)

The metric is **calibrated** only if all of these hold:

1. Separation: `min Q(F) > max Q(A)` and `min Q(F) >= 2 * max(max Q(A), 1.0)`.
2. Parity: V and F on F2-F5 equal the sealed receipts above (16/1 767, 16/1 751, 27/1 576, 16/1 751) exactly; F1
   one-face edges = 843.
3. Repeat: three runs per input give byte-identical Q (spread 0; median of 3 is reported).
4. Rigid-motion stability (representative perturbation, every input): translate (+123.456, -78.9, +3.21) m and
   rotate 30 deg about Z (vertices and object location). Expected direction: none. Bound per input:
   `|Q' - Q| <= max(0.01 * Q, 0.1)`.
5. Positive trigger witness (injected, every accepted input): unweld 50 interior vertices (deterministic choice:
   every k-th interior vertex of the first part, k = n_interior // 50) by moving one incident face's corner to a new
   vertex shifted 1 mm along +X. Expected direction: up. Bound: `Q_inj - Q >= 0.5 * 1e4 * 100 / T` (each unweld
   adds at least 2 near vertices).
6. Accepted control on which the rule fires: an accepted input with `V + F + C > 0`. If none exists, this is
   recorded as **not measured** (the rule never fires on an accepted package in this fixture) and collateral
   impact on accepted work is unknown, not zero.

Hypothesis H31: Q is calibrated (1-5 hold). `confirmed` if 1-5 hold, `refuted` if 1 or 2 fails, `inconclusive` if
the series does not fit the budget or 3-5 cannot be run.

### Budget and stop rule

- Core budget: 90 min wall for dumps + 3 repeats + perturbation + injection; frozen after the first measured
  input pair (one A, one F). If the series does not fit, publish `inconclusive` and the exact next command; never
  shorten the series silently.
- Confirm-vs-new-candidate: no second metric candidate in this card. If H31 is refuted, the card records which
  inputs break the order and stops (one candidate, one confirmation).
- Then (only if calibrated): score the first Ground built by the #1738 core. If it does not exist yet, record
  **not measured** and the exact command.

### Forbidden shortcuts

Dropping or replacing an input after seeing its score; changing the xView tolerances; editing delivered packages,
the SIL13 evidence or other cards' files (`C:/x/ground-etalons/` is read only here); counting the outer border as
defects; deselecting tests; any auto-applied change to delivered work.

### Not measured (by design)

NPM triangle budget (site-level, 180 000 for SIL13; failed variants do not differ by intrinsic quality there);
visible deviation of elevations/borders from the source; skirt height >= 1 m (needs the source footprint, #1738
validator); VPM.

### Replay

    uv run python docs/research/autoresearch-ground-quality-harness/dump.py    # FBX/NPZ -> metre dumps
    uv run python docs/research/autoresearch-ground-quality-harness/score.py --out <new.json>

Inputs: `C:/x/ev_t_193a0887/inputs/` (copies; originals and hashes above). Replay is limited to this PC (the inputs
are customer packages and are not committed).

## 2. Round log

(filled after measurement)
