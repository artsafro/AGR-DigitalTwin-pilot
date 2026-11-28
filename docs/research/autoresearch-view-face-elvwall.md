# H167 — ELV TC Sreda: transfer of the Silikatny wall stack (#163 → #165 → #166), OBSERVE

## Кратко для Артёма

(заполняется после замера — см. «Round log»)

## Frozen contract (committed before any score was computed)

Card t_2dfecd45 (standing #167), focus 0 (view↔face map sheet). #2001 is OPEN: Sokolniki held out, not opened.
Takes #166 next (1): the stack built on Silikatny (#163 per-wall frontal renders + width eligibility + tau/delta,
#165 full-view length veto, #166 full-view glazing-rhythm veto) has only been measured on the album it was built on.
This card runs it, parameters unchanged, on an independent labelled album: ELV TC Sreda (#145 fixture: AGR booklet
PDF `49c10527…9545` + Revit 2023 FBX `7ccf502d…b961`, 7 full views + 3 real fragments, side-level truth from
`autoresearch-view-face-elv/fixture.json` on main). Not duplicated: #2073/#2074 finish partition, #2075 wall
exercise; atlas/form/trainer parked.

**H167.** Arm C (= #163 decide → #165 `length_veto` → #166 `rhythm_gate`, all executed from SHA-pinned blobs) on
the 10 clean native ELV views: **0 wrong** AND **≥ 4/7 full views correct** (the #145 bound) AND blank masks abstain
10/10. Any miss refutes. Arms A (#163 only) and B (+#165) are reported beside C; #145 (5/0/2 full) is the reference.

**Primary metric.** Side-level correct / wrong / abstain: an answered wall is correct iff its azimuth equals the
#145 `gt_az` (same truth as #145, so the numbers are comparable). Diagnostic, not scored: whether the answered wall
is an *outer* wall (< 50 % of its length covered by a further-out wall of the same azimuth) — this catches a
parapet-inner face answering for the right side.

**What is adapted for ELV (frozen, the only changes; everything else is the pinned code):**

| Item | Silikatny (#161–#166) | ELV (#167) | Why |
|---|---|---|---|
| Model import | category OBJ, mm → m | FBX import (Blender 4.4), meshes with world max z > 30 m deleted (#145 rule, 1 stray batten) | different source format |
| Facade / glass / hidden sets | `Ctx_steny+okna+paneli_vitrazha` / `okna+paneli_vitrazha` / `perekrytiya` | Revit type regex: facade `^(Базовая стена\|Системная панель\|\(WN\)-RD\|Окно )`; glass `^(Системная панель (С остекление\|Стемалит\|\(CP\)_Glass)\|\(WN\)-RD\|Окно )`; hidden `^Перекрытие` | same categories (walls, windows, curtain panels; doors excluded as on Silikatny) |
| Azimuths | 8 (#161) | 0/90/180/270 (#145) | ELV is orthogonal; the slanted north wall (≈ 6°) falls in az 90 within the ±12° tolerance |
| Band z | 0–12.9 m | 0–16.4 m (#145 building top; facade max z 16.17 = +16.220) | building height |
| Drawing glass mask | legend complement + luminance | exact vector fills of legend items 5/6/7 (p18): RGB (207,227,250) stemalit, (236,244,253) glazing, distance ≤ 8 (white is 22 away) | ELV booklet is vector with exact fills |
| Datum anchors | manual (#162 table) | label rule: nearest exact level text to the view box, anchor y = text bottom; vertical scale = #145 `scale_pt_per_m` (axis labels; p20 level labels). Labels: `+0.000` (p18/p19), `+15.900` sign top (p21, p23, p24), `-0.100` (p20) | no manual reading |
| kind | manual | #145 `kind`; `fragment_top_cut` → fragment | — |

Unchanged (pinned): wall extraction, frontal clipped renders, 0.1 m/px, grid 0.25 m, `min_overlap` 0.8, `fit_tol`
0.10, tau 0.30, delta 0.10, rhythm threshold 0.35 (128 bins), #161 `opening`/`largest_bbox`/`best_offset`, #162
`register`, #163 `wall_masks`/`decide`/`block_shuffle` (2 m blocks, seed 163).

**Pre-score checks (no view scored).**
- *Geometry* (`C:/x/ev_t_2dfecd45/probe2`, 8 min Blender): 1 mesh dropped (z > 30 m), 3 790 facade / 694 glass /
  253 hidden meshes, facade z −2.85…16.17; 27 160 vertical faces in band, 5 716 exterior; 34 walls. Outer shell:
  east az 0 W08 (x 75.9, L 51.0), W09/W10 (x 79.0, 18.4 each, split by the recessed entrance); north az 90 W16
  (y 1.35, L 85.2, includes the slanted part); south az 270 W33 (y −50.6, L 76.5); west az 180 W24 (x −0.4, L 30.4),
  W25/W26 (annex). Many parapet-inner faces pass the 45° sky ray (e.g. W27 az 270 at y 0, W17–W21 az 180 at
  x 47–79): they are candidates exactly as on Silikatny.
- *Front end* (`--probe`, `C:/x/ev_t_2dfecd45/probe_fe`): widths 54.5 / 88.5 / 88.5 / 55.0 / 52.5 / 54.5 / 88.0 m
  for the seven full views (nominal 52.6 / 84 / 84 / 52.6 / 50.4 / 52.6 / 84 + margins), fragments 20.25 / 14.75 /
  3.75 m. Scales 9.44–9.45 pt/m (1:300) on full views. **Drawn glass fraction:** I-A 0.41 (p18), 0.16 (p21,
  faded sheet); 1-10 0.010, 10-1 0.004, A-I 0.003, 6-1 0.001, p21 1-12 0.000; fragments D-G 0.44, 8-9 0.012, 9-10
  0.034. ELV is mostly opaque: only the east curtain wall carries glass. **Expected (written before scoring):**
  low coverage — answers possible on I-A and D-G only; near-empty masks must abstain, not guess.

**Perturbations (per state changed cells recorded; `exercised` = changed > 0).** mirror, blank (must abstain),
shuffle (2 m blocks, seed 163). Candidate-order reversal must reproduce every arm's answer (checked in every state).

**Budget and series.** One fresh run = Blender walls + renders + fresh PDF read + all arms/states. 3 fresh runs,
0 exploratory rounds after this freeze; median and max−min wall time reported. 3600 s budget: stop after a run if the
rest cannot fit → `inconclusive`. Runs must be byte-identical (body digest); inputs hashed before and after.
Forbidden: changing any pinned parameter, the truth, the regexes or the anchors after seeing scores; deselection;
writes to delivered packages or other cards' files; opening Sokolniki.

**Not measured:** wall-level truth inside a side (only the outer-wall diagnostic), within-wall bay localisation,
accepted/rejected delivery calibration, blind full/fragment classification, Sokolniki STOP 04.

**Replay.**
```bash
git fetch origin research/autoresearch-standing-161 research/autoresearch-standing-162 research/autoresearch-standing-163 research/autoresearch-standing-165 research/autoresearch-standing-166
uv run --offline --locked --extra pdf-review python docs/research/autoresearch-view-face-elvwall/run.py <new_dir>
```
Inputs: the #145 fixture paths on the pilot host (owner's `Dima_Andrew/3_sreda/for_ai`), SHA-256 checked before and
after; staged copies in `G:/Мой диск/AGR-evidence/145-view-face-elv/`. Replay limited to the pilot host.

## Round log

(after the run)
