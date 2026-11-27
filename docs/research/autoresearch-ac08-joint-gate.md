# Autoresearch #127: does the D171 joint-count gate reject the rejected AC08 version? (OBSERVE)

Card t_698e8a8c (standing #127). Trainer focus: no free lever (ledger `docs/trainer/ledger.json` unchanged since
28430fbe, `C:/x/trainer/runs` still 68 dirs, artifact owned by OPEN PR #1928; #1917 merged but no new run). Fallback =
texture/atlas focus, continuing #125 (t_a2ac596e, H125 refuted: NPM-vs-VPM drift does not see the 0.60 m joints
because they are in both packages).

## Why this target (decided before any measurement)

#125 next (1) proposed an authority-free seam signal (periodic dark-line energy on the render). It is dropped a priori:
the accepted v010 carries intentional vertical joints every 0.195 / 0.186 m (Artem's joint texture [D169]), so a
periodic dark-line signal fires on the accepted control as well. What Artem rejected in v007 is the joint PITCH relative
to the authority (presentation slide 49 [D171]: 29 / 11 joint lines), not the presence of joints. The repo already has
a render-pixel gate for exactly this: `jobs/TEC26-OKS/scripts/compare_facades.py` (`joint_count.render_row` +
`count_joints`). It was built on v009/v010 and **has never been run on the rejected v007**. This round calibrates that
existing gate, unchanged, on the rejected version. No new harness.

## Contract (frozen before the first measurement)

**Hypothesis H127.** The unchanged gate run on the rejected v007 Drive renders reports MISMATCH on at least one facade
(exit 1) and a larger joint-count error than on the accepted v010, which matches on 4/4.

**Metric** (one number per package, lower = better): joint-count error
`E = sum over the 4 facades and the 2 renders (vpm, npm) of |render_joints - (ribs - 1)|`, read from the gate's
`compare.json` (`vpm_render_joints`, `npm_render_joints`, `contract_ribs`). Also reported: `match` per facade, exit code.

**Keep rule (OBSERVE signal, no production change).** `confirmed` only if all hold:
(a) `E(v007) >= 4` and `E(v010) == 0`, v010 exit 0, v007 exit 1;
(b) 3 runs per package give byte-identical `compare.json` (paired spread 0, checked);
(c) parity: v010 counts equal the committed `jobs/TEC26-OKS/AC08/pilot-v010/compare.json` (29/29/11/11, all match);
(d) witnesses move in the expected direction (below).
(a) failing = `refuted`; (b)-(d) failing = `inconclusive`.

**Command** (per package `<P>` in {pilot-v007, pilot-v010}, outputs to new dirs under `C:/x/ev_t_698e8a8c/`):
1. readback of the Drive VPM ZIP (as `run_building.sh` lines 36-40): extract `SM_Nku_1.zip`, then
   `blender -b --python jobs/TEC26-OKS/scripts/qa_readback.py -- <dir>/SM_Nku_1.fbx <dir>/vpm.readback.json`;
2. `uv run python jobs/TEC26-OKS/scripts/compare_facades.py jobs/TEC26-OKS/AC08/vpm_textures.json
   jobs/TEC26-OKS/AC08/sheet-facades.json "G:/Мой диск/AGR-evidence/559-tec26-oks-ac08-<P>/renders"
   <dir>/vpm.readback.json <new out>` (default 200 px/m).
The spec reads the slide at `C:/x/tec26-oks/pptx/facades/slide49.png`; it is restored there as a byte copy of the Drive
`559-tec26-oks-ac08-pilot-v010/slide49.png` (sha256 `256f32da...08a8fd`, the gate itself checks the hash).

**Fixture** (Drive, each render PNG, `renders.json` and the ZIP checked against the folder's `SHA256SUMS.txt` before use;
a mismatch aborts): `559-tec26-oks-ac08-pilot-v007` = **rejected** (`AC08/PILOT_REPORT.md` line 5 «швы 0,60 м,
отклонено Артёмом»); `559-tec26-oks-ac08-pilot-v010` = **accepted** (`STATE.md`). Spec and sheet from this branch's
merge of origin/main 7e504b8f (unchanged files).

**Witnesses** (synthetic image perturbations of the accepted v010 NPM south render, marked synthetic, written to
a copy of the renders dir; they test the gate, not the pipeline). Expected: E rises by >= 1 vs clean v010.
- `W1 missing_joint`: one joint column near the field centre painted over with the panel colour sampled 0.05 m left of it.
- `W2 extra_joint`: a dark line (the measured joint colour, joint width) added midway between two joints.
- `N0 identity`: clean v010 = the committed counts (same as (c)).

**Not measured** (recorded as such, not as results): held-out etalon (no other object has a presentation slide plus
rendered paired packages: KPP1 v004, Vatutino / Staropetrovskiy MAF have none); authority-free seam energy (dropped
a priori above); unlabeled `pilot`, `pilot-v006`, `pilot-v009` are reported if run, never used for the verdict.

**Stop rule.** One variant only (the gate as on origin/main). No parameter change after seeing v007. Budget = this card
run; if Blender readback fails three different ways, stop `inconclusive` with the exact next command.

**Forbidden.** Editing the gate, `joint_count.py`, the spec, the sheet, any delivered package or render on Drive; files
of other cards; changing labels after scoring.
