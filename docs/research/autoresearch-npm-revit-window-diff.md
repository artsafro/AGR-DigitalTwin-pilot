# Autoresearch #137: NPM window/curtain-wall atlas vs Revit render-diff (Sokolniki, OBSERVE)

Card t_bab8c465 (standing #137). Focus: NPM atlas render-diff as a calibrated texture/atlas signal [card focus
override 2026-11-27]. OBSERVE only: nothing here changes a tool, a job or a delivered package.

## Резюме (по-русски)

См. раздел «Result» ниже; русское резюме — в отчёте на карточке.

## Why this target (considered)

- AC08 NPM-vs-VPM render-diff is spent on its labels (#125/#128/#130/#132/#134 in the backlog); KPP1 v004
  (#2020 open), Vatutino MAF (#1499 closed without a texture pair), Staropetrovskiy (#1500 open) still have no
  asymmetric texture refusal. #2014 owns the joint gate, #1947 atlas/master binding, trainer and form are parked.
- New, never used: **Sokolniki NPM window texture labels** (#1784/#1925). Same 720x600 Workbench ortho cameras
  (`question-windows/measure.json`) were rendered for Revit, v009 and two NPM atlas states:
  - rejected R1 = step-4 NPM atlas windows (`step4-uv-atlas-v001/npm/NPM_Sokolniki_UVK1000_01.fbx`),
    [D413] «окна ещё не сделаны нормально» — windows NOT accepted;
  - rejected R2 = v009 flat insets (frozen render only, `question-windows/renders/v009_*`), same [D413] refusal;
  - accepted A = windows drawn in the atlas (`windows-texture-v001/npm/...fbx`), [D418] «Принимаю» (windows W1-W4 + doors).
- Held-out (scored with the gate frozen on the windows set, never tuned on it): curtain walls,
  before = `windows-texture-v001` state (superseded by [D418], CW drawn like windows), after = `curtain-walls-v001`
  (accepted in [D419]); cams `curtain-walls-v001/scripts/cams.json`, Revit reference `close/revit/`.
  Label strength: «before» is superseded by a rule, not a refusal by words — weaker label, reported separately.
- Reference is the **Revit source render** (Sokolniki has no VPM; [D419] VPM out of scope). This is
  NPM-vs-source drift, the same render-diff method with a different fixed reference.

## Frozen contract (written before any measurement)

Metric (primary) **M_edge**, per element cell, lower = better:
1. Cell = the element box from `measure.json` (`center`, `t`, `nout`, `half`), its 8 corners projected through
   the ortho camera (`dir`, `scale`, 720x600, Blender `to_track_quat('-Z','Y')` basis), bbox + 10 % margin,
   clipped to the image. Label-blind (geometry only). CW cells: whole frame (cams.json has no box).
2. Mask = cell AND candidate alpha == 255 (NPM renders are transparent outside geometry; Revit is opaque).
3. Luma Y = 0.2126R+0.7152G+0.0722B (0..1); Sobel magnitude / 4; edge = magnitude > 0.05.
4. M_edge = mean of the two directed chamfer means (Revit edges -> nearest candidate edge, candidate edges ->
   nearest Revit edge), Euclidean px, capped at 10 px, only over edge pixels inside the mask.
Secondary **M_de** = mean CIE76 ΔE (sRGB D65 -> Lab) over the mask (the classic colour render-diff).

Hypothesis H137 (windows set, primary): for all 10 cells (W1-W4, D1 x `_f`/`_q`) M_edge(A) < M_edge(R1) and
M_edge(A) < M_edge(R2), each margin >= 0.25 px, in every one of 3 fresh render rounds -> **confirmed**;
any cell ordered wrong -> **refuted**. M_de is reported, not gated (expected weak: NPM glass is darker than Revit
glass in both A and R1).
Held-out H137b (CW set, same metric, same threshold): after < before on 8/8 cells -> confirmed, 6-7 -> inconclusive,
<= 5 -> refuted.

Rounds: 3 fresh Blender renders of every re-renderable candidate (A, R1, CW before, CW after) with the archived
render script `question-windows/scripts/qwin_npm.py` (SHA-256 pinned), Blender 5.1.2, shift `26.148,61.907`
(NPM local -> master frame: master bbox centre xy, checked by render parity below). R2 (v009) and all Revit
references stay frozen renders (not re-rendered: needs the v009 blend + Revit FBX chain, out of budget) —
reported as `frozen`, not as stability evidence. Stability = spread of M_edge over the 3 rounds.
Parity: each fresh render vs its archived render — opaque-pixel RGB diff count > 8 levels and alpha-mismatch
count recorded per cell (pre-measurement probe on A D1_q: 6 px > 8 levels, 2576 alpha-edge px).

Witnesses (on round-1 fresh A, cell W1_f): N0 Revit vs itself = 0 (expected exactly 0);
P1 pane/frame pattern erased (5x5 box blur repeated 6 times inside the cell) -> M_edge up (expected > +0.5 px);
P2 image shift 2/5/10 px -> monotone increase; P3 brightness x0.8 (colour only) -> |ΔM_edge| < 10 % while M_de up.
Positive trigger witness = R1 on W1_f (wrong pane layout, visible in the archived question sheet).
Invariance: input SHA-256 preflight on every pinned file; untouched candidates are `not_exercised`.

Budget: one measured pair (~3 s per Blender call) -> whole series < 5 min; stop after the 3 rounds or 45 min.
No improvement round is planned unless H137 is confirmed AND H137b is not refuted (calibrate first).
Forbidden: re-tuning threshold/cells after seeing scores, dropping cells, editing any Drive evidence or job file,
touching other cards' files, presenting the CW «before» label as a word-for-word refusal.

Replay: `uv run --frozen python docs/research/autoresearch-npm-revit-window-diff-harness/run.py <new out dir>`
(Windows, Blender 5.1 at the default install path, Drive `G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/`;
inputs hash-checked before rendering).

## Result

Contract commit 0a8e0e17, harness + pins 9fc7a3ac (both before the first score). Run: 3 fresh rounds, 154.6 s
wall, status complete, preflight 70/70 hashes equal, M_edge spread over rounds 0.0 on every cell.
Receipt `autoresearch-npm-revit-window-diff-harness/receipt_r137.json`; evidence (round-1 renders, cell overlay,
receipt) `G:/Мой диск/AGR-evidence/137-npm-revit-window-diff/` (`SHA256SUMS.txt` 42 files).

**H137: REFUTED** (stable, identical in all 3 rounds). **H137b (CW held-out): REFUTED** (3/8).

| cell | A (accepted) | R1 (step-4, rejected) | R2 v009 (rejected, frozen) | ΔE A / R1 / R2 |
|---|---|---|---|---|
| W1_f | 4.229 | 4.445 (margin 0.216 < 0.25) | **2.896** | 20.2 / 23.3 / 7.7 |
| W1_q | 5.612 | 5.887 | **3.649** | 20.6 / 23.6 / 8.3 |
| W2_f | 5.736 | **5.519** | **4.788** | 27.8 / 31.1 / 7.3 |
| W2_q | 5.118 | 5.651 | **4.311** | 28.0 / 30.6 / 7.4 |
| W3_f | 2.605 | 3.164 | **2.386** | 18.4 / 20.5 / 7.8 |
| W3_q | 3.121 | 3.870 | 3.129 (margin 0.008) | 14.4 / 15.9 / 8.6 |
| W4_f | 3.405 | 4.288 | **3.368** | 21.3 / 24.4 / 7.7 |
| W4_q | 5.068 | 5.791 | **4.201** | 20.2 / 22.6 / 8.9 |
| D1_f | 5.279 | 6.528 | 5.791 | 32.6 / 34.3 / 16.7 |
| D1_q | 4.743 | 5.596 | 5.900 | 25.2 / 26.4 / 12.9 |

- A < R1 with margin: 8/10 (W1_f ordered but under margin, W2_f reversed). A < R2: 2/10 — the flat v009 insets
  that Artem refused score **closer** to Revit than the accepted drawn windows on all 8 window cells.
- M_de (not gated): A < R1 10/10, A < R2 0/10 (v009 keeps the Revit pale-blue glass and grey facade; ΔE 7-17 vs 18-33).
- CW held-out: after < before 3/8 (CF_f, CF_q, CWL_f); CW4/CWS/CWL_q within ±0.27 px or reversed.
- Witnesses (W1_f, round 1): N0 = 0.0; P1 pattern erased +0.890 px (> +0.5); P2 shift 2/5/10 px
  +0.323/+1.251/+2.645 (monotone); P3 brightness x0.8 −0.204 px (−4.8 %, < 10 %) while ΔE +7.40. The instrument
  responds as frozen; the failure is in the signal, not the instrument.
- Parity fresh vs archived renders: opaque RGB > 8 levels 0-486 px per cell (max W4_f 484/486 of 287,504 mask px),
  alpha mismatch 0 except CF_q before (2,320, AA edge). Exercised: A, R1, CW before, CW after (fresh x3).
  R2 and every Revit reference: frozen, **not re-rendered** (not stability evidence for those inputs).

Interpretation: NPM-vs-Revit render-diff is dominated by the NPM atlas styling that BOTH Artem-accepted and
rejected NPM states share and Revit/v009 do not (dark glass, cassette and brick joints, RAL 7016 frames).
Like #125/#128 (NPM vs VPM on AC08), a whole-cell diff against a reference of a different style measures
style drift, not the refused defect class (missing or wrong pane layout). Within one pipeline (A vs R1) the
edge signal orders 8/10 at the frozen margin — too weak and with a reversal, so not a gate.

Nothing kept; no improvement round (contract: calibrate first). Next targets are in the card report and the backlog.
