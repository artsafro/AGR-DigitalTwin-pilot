# Ground v015 route proposal after unfreeze (2026-11-04) — NOT_DELIVERY, decision needed

Card t_e35c49dd, issue #371, resumed from checkpoint `cec6b57` (card t_eb1c51ca). Artem's unfreeze
comment (2026-11-04 18:45): one-page route proposal with numbers, recommendation first, then wait
for his choice; no long build before the answer. No new build, export or DCC call was made for this
page; every number below is copied from the committed evidence named in the last column.

## Recommendation: route A — v009 paired-fan + a recorded, enumerated texel exception

Take the reproducible CPU candidate v009 (D157 pairing, both profiles 46,479 triangle-equivalent),
record a v015-only exception to `texel_ready` (#346) that lists every offending face per slot and
caps it at the measured counts, then finish the remaining mandatory work: clean the last 13 xView
OF witnesses (skirt curtains, curb bottom vs raised cake, one Curb/Stairs), fixed material IDs, export, Max + Blender
readback, real xView in Max, UCX/D150/placement, review scene. The 13 OF were measured on the
diagnostic stair-fix candidate (production stair fix `a621607` + diagnostic 12 mm clearance). Why: it is the only route that
already meets 50k/180k, ≤35 % triangles, relief 10 mm and contours 2.2 mm, and it **halves** the
texel offenders of the v014 that is delivered today (v014 itself fails strict `texel_ready`).
Estimate: 1–2 sessions; the open risk is the 13 OF, not the mesh.

## Routes with numbers

| | A. v009 + texel exception (recommended) | B. strict texel, own conforming quad mesher | C. different external mesher |
|---|---|---|---|
| Surface polygons (cap 50,000) | 27,496 NPM / 28,167 VPM | unknown; naive subdivision alone adds ~22,300 faces | Gmsh v002: **64,626**; v004: 158,148 |
| Triangle share (cap 35 %, D157) | 30.96 % NPM / 34.99 % VPM | unknown | Gmsh v002 **40.4 %**; QuadriFlow 0 % |
| Triangle-equivalent (cap 180,000) | 46,479 | unknown | Gmsh v004 **272,592** |
| `texel_ready` offenders (strict = 0) | **8,511 NPM / 11,430 VPM** (v014: 19,350 / 22,556) | 0 by construction (goal) | Gmsh 13,991–15,777; QuadriFlow 196 |
| Contours 2.2 mm / relief 10 mm | 0 off-outline / 9.97 mm | to be proven | QuadriFlow moves boundary up to **125 m**; Gmsh merged-relief run did not finish in 1,800 s |
| Ours xView OV / OF (0.002 / 0.005 m) | **0 / 13** on the stair-fix candidate (to clean) | to be proven | Gmsh v002 OV 109 |
| Known blocker | 13 OF: 6 Skirt/Skirt (near-coincident base-outline curtains), 3 Curb/Mulch + 3 Curb/LawnReinforced (curb bottom datum vs locally raised cake, 3.0–4.8 mm), 1 Curb/Stairs | chord propagation diverges on 5,536 NPM chords; needs count-changing transition templates (1→3, 2→4) and interior apex quads for 1.12 mm tongues — not written | isotropic recombine cannot follow 1–3 mm bands; slot-wise remesh breaks slot borders |
| Effort | 1–2 sessions | multi-session new mesher, 50k budget not guaranteed | already measured; no candidate left that keeps contours |

Route D (fallback, not a v015): keep v014 for #298, close only xView 0/0 and the Multi/Sub IDs on
v014 triangles; it does not answer "в квадах".

## What A needs from Artem

1. Approve a v015-only `texel_ready` exception: the frozen list of 8,511 NPM / 11,430 VPM offending
   faces (per-slot counts in `ground-v015-texel-contract-checkpoint.md`), never more than these
   counts and never a face not on the list; UV density itself stays inside D097 (NPM 11.4–30.2,
   VPM 589.6–1,442.1 px/m). All other thresholds unchanged.
2. Nothing else: the 13 OF are cleaned by construction (dedupe the skirt base-outline curtains;
   curb bottom follows the locally raised cake; Curb/Stairs clearance), not by a waiver. If they
   cannot be cleaned, the session stops with the offender list (as D157 already says).

Note: D157, D169 and D170 are recorded only on this branch (`docs/decisions.md`), not on `main`;
they land with the v015 PR. `src/dt_ai/ops/inv_xview.py` changed on `main` since the checkpoint
(+469/-63, fast core), so route A starts by merging `origin/main` and re-measuring v009 with it.

Sources: `ground-v015-texel-contract-checkpoint.md`, `ground-v015-final-xview-session.md`,
`ground-v015-conformity-census.md`, `ground-v015-external-mesher-probe.md` (all in this folder).
