# Standing #35 — Ground short-edge density Qe (OBSERVE)

Card t_f4f34f04, branch `research/autoresearch-standing-35`. Focus: Ground quality (Artem 2026-11-21 «Переключай»).
Mode: OBSERVE only. No Ground is built or repaired here (#1738 owns it). No delivered package and no other card's
file is edited.

## Итог (по-русски)

_Заполняется после серии; контракт ниже заморожен до первого замера._

## Why this candidate (continuing #31–#34, no new harness)

- #31 `Q = V+F+C` refuted (the delivered COD has many overlapping faces).
- #32 `Qv` (near vertices ≤ 2 mm) separates the frozen corpus on the Blender readback (0 vs 421–484). But #33 showed
  that 3ds Max `convertToPoly` splits non-manifold vertices into coincident copies, so native Max finds 278–580
  near vertices on four delivered NTR Ground. That makes Qv depend on the node state.
- #34 `Qfan` refuted (non-manifold fans: 0 on SIL13, 25 on the delivered COD).

H35 tests the *connected* part of the SIL13 defect: edges shorter than the xView vertex tolerance (slivers and
collapsed stitch edges). Splitting a non-manifold vertex creates coincident copies with **no** edge between them,
and every edge keeps its two endpoints' positions. So Qe is unchanged by construction under the Max-like split, unlike
Qv. Whether SIL13's 1 576–1 769 near vertices are connected by edges at all is unknown before this measurement.

## Frozen contract (before any score)

**Metric.** `Qe = 1e4 * E / T`, lower is better. `E` = unique undirected index edges of the polygon faces of the
scored part (consecutive corners including last→first; an edge (a,b) with a == b counts) with Euclidean length
`<= 0.002 m` (`inv_xview.tolerance_for('NPM').vertex_m`, same comparison as `vertex_pairs`). `T` = fan triangles
(k-gon = k-2), as in #31. Scored part: the only object whose name ends with `_Ground` (amendment 1 of #31).
`V` (#32 near-vertex count) is recomputed next to it for parity only.

**Fixture (frozen, no replacement).** #31 dumps `C:/x/ev_t_193a0887/dumps-v002`, hashes in
`docs/research/autoresearch-ground-quality-harness/dumps.sha256` (A1 Vatutino v015 + A2–A8 Artem's delivered NTR NPM
Ground; F1–F5 SIL13 #1315 r1–r5, F3 = F5 bytes). NTR copies and hashes: `C:/x/ground-etalons/` (#31/#32 custody).
Holdout, declared now and **not** a calibration input: W1 Vatutino v014 NPM Blender readback
`C:/x/ev_t_304e8c0c/dumps/W1_Vatutino_v014_NPM.npz` SHA-256
`29393a0b5ed7ce39a2e5a8d8c7b0014885ecf4bfcde5a9ae07088bfc76aa6683`. Expected for W1: `E = 0`, because its
rejection (#370) is the non-manifold split class that the delivered A3–A6 also carry; W1 is reported, not used for
the verdict.

**Hypothesis H35 (this corpus only).** Confirmed iff all hold on one completed series:

1. Separation: `min Qe(F) > max Qe(A)` and `min Qe(F) >= 2 * max(1, max Qe(A))`.
2. Parity: per input `T` and `V` equal the #32 receipt (`research/autoresearch-standing-32@ebb32458`,
   `autoresearch-ground-near-vertices-r32.json`).
3. Repeat: three evaluations per input, identical `E`, `T` (median reported, spread 0).
4. Rigid motion (#31 `rigid`: rotate 30° about Z + shift (123.456, -78.9, 3.21) m): `E`, `T` exactly unchanged.
   Expected direction none.
5. Max-like split (representative perturbation of the #33 failure mode, every input): split every non-manifold
   vertex into one copy per edge-connected face fan. Bound: `E`, `T` exactly unchanged. `V` after the split is
   published descriptively (expected to rise on inputs with fans; this is the property that broke Qv).
6. Positive witness (injected, every accepted input; Vatutino A1 is the non-SIL13 witness): take interior vertices
   (not on an open edge) in index order, every k-th with `k = n_interior // 50`, first 50; for each picked `v`
   with a picked-free first neighbour `u` (first edge of its first face), move `v` to `u + 0.001 * (v-u)/|v-u|`.
   Expected direction up. Bound: `E_inj - E >= 25` and `T` unchanged.
7. Accepted control on which the rule fires: an accepted input with `E > 0`. If none, recorded **not measured**
   (collateral impact on accepted work unknown, not zero).

Refuted if 1 or 2 fails on a completed series, or 3–6 fail; inconclusive if the series does not complete.

**Then (only if confirmed).** Score the first published #1738 core export, SIL13 shared v003
`C:/x/ev_t193/sil13_shared_v003/SM_SIL13_Ground.obj` SHA-256
`8f51940939e921dc206280c385c6f045da13fc2c1b78d685bf63d0c7d0f1a450` (= Drive
`G:/Мой диск/AGR-evidence/1738-ground-shared-core/sil13_shared_v003/`), three evaluations. The #1738 r2/r3 packets
publish reports only (no meshes), so later core builds are **not measured**. No rebuild.

**Budget.** First pair A1 + F4 timed; cap 5 minutes wall for the whole series; if `first_pair * 7` exceeds the cap,
stop `inconclusive` and publish the replay command. Confirm-vs-new-candidate: one candidate, zero new candidates
in this card.

**Forbidden.** Replacing or dropping inputs after seeing scores; changing the 2 mm tolerance; editing delivered
packages, SIL13/#1738 evidence or other cards' files; building or repairing Ground; deselecting tests; any gate or
threshold in production code.

**Not measured (by design).** Native Max readback (no Max geometry dump exists for A1–A8; the split perturbation
models it), VPM (no rejected VPM Ground), skirt (#1738/#1787), visible deviation, triangle budget, overlapping
faces, independent rejected site outside SIL13 (W1 is a different defect class).

**Replay.** From the repo root (the worktree uv env lacks NumPy; the parent venv provides it):
`../../.venv/Scripts/python.exe docs/research/autoresearch-ground-short-edges-r35.py C:/x/ev_t_f4f34f04/NEW.json`.
Inputs are customer packages outside Git, so replay is limited to this PC.

## Round log

_Filled after the series._
