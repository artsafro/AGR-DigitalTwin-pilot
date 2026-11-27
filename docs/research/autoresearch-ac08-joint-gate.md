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

**Amendment A1 (committed before the re-render, after the first gate call).** Repair attempt 1: on the Drive v007
renders the gate crashes (`KeyError: 'views'`, exit 1 = crash, not MISMATCH): v007 `renders.json` predates the camera
block that `render_facades.py` gained in a1f41ee2 (v009). v010 on its Drive renders gave exit 0, 29/29/11/11, all match,
3/3 identical (`compare.json` sha256 `558bd841966d7936...`), i.e. (c) holds on the stored renders. Both packages are
therefore re-rendered from their Drive ZIPs with the current `render_facades.py` (the documented replay path,
`AC08/PILOT_REPORT.md` «Как повторить»), new dirs only:
`blender -b --factory-startup --python jobs/TEC26-OKS/scripts/render_facades.py -- jobs/TEC26-OKS/AC08/vpm_textures.json
<P>/vpm/SM_Nku_1.fbx <P>/vpm <P>/npm/0000_Nku_1_01.fbx <P>/renders_r127`, then the gate as above on `renders_r127`.
The metric, keep rule and gate are unchanged. Parity (c) is now required on the fresh v010 render as well; if the
fresh v010 render does not reproduce 29/29/11/11 the round is `inconclusive`.

**Forbidden.** Editing the gate, `joint_count.py`, the spec, the sheet, any delivered package or render on Drive; files
of other cards; changing labels after scoring.

## Results

**Hypothesis H127: confirmed for AC08 only** (calibration of an existing gate; held-out **not measured**). Review
readiness is a separate status. OBSERVE: nothing is changed in the gate, the spec or any delivered package.

Receipt `docs/research/autoresearch-ac08-joint-gate-harness/receipt_r127.json` (input ZIP / readback / render /
`compare.json` SHA-256 per package and run, gate / joint_count / render_facades / spec / sheet / slide hashes). Evidence
(fresh renders, compare sheets, readbacks, witness PNGs): `G:/Мой диск/AGR-evidence/127-ac08-joint-gate/`
(46 files + `SHA256SUMS.txt`, sha256 `28ff6d84...4ccd15`).

| Package | Label | Gate exit | 1-2 vpm/npm | 2-1 | А-Б | Б-А | E | 3 runs |
|---|---|---|---|---|---|---|---|---|
| pilot-v007 (fresh render) | **rejected** | 1 (MISMATCH 4/4) | 11/11 of 29 | 11/11 | 0/0 of 11 | 0/0 | **116** | identical `cfa154ed...` |
| pilot-v010 (fresh render) | **accepted** | 0 | 29/29 | 29/29 | 11/11 | 11/11 | **0** | identical `558bd841...` |
| pilot-v010 (Drive render) | accepted | 0 | 29/29 | 29/29 | 11/11 | 11/11 | 0 | identical `558bd841...` |
| pilot-v007 (Drive render) | rejected | crash `KeyError: 'views'` | - | - | - | - | not measured | 3x crash |

Witnesses (synthetic, v010 NPM south = facade 2-1, `witness.py`): W1 missing joint -> 28 found, E = 1, exit 1;
W2 extra joint -> 30 found, E = 1, exit 1; N0 = clean v010 = committed `pilot-v010/compare.json` counts. All 3x identical.

Keep-rule check: (a) E(v007) 116 >= 4, E(v010) 0, exits 1 / 0: **passes**. (b) 3/3 byte-identical everywhere: passes.
(c) parity: v010 fresh-render `compare.json` is byte-identical to the Drive-render one and its counts equal the committed
29/29/11/11: passes. (d) W1, W2 rise by 1: passes.

**Observations (not tuned, recorded for the next round).**
1. The gate catches v007 on every facade. The found long-facade joints sit at the 0.60 m pitch Artem rejected
   (-2.331, -1.729, -1.129, -0.530, 0.069 m ...).
2. **Gate precision defect:** on the v007 short facades the compare sheet visibly shows 3 dark joints in both renders,
   but the gate counts 0 (`compare_east_Б-А.png`, `compare_west_А-Б.png`). The verdict is still right (3 != 11), but
   the count is wrong, so E overstates (count-by-eye E would be about 104). Likely cause (not measured): `render_row`
   drops pixels whose blue-minus-red <= 25 as "not panel", so a near-black joint becomes NaN instead of dark.
   Not fixed here (OBSERVE, the gate belongs to #559).
3. **Gate robustness:** on renders made before a1f41ee2 the gate crashes with `KeyError: 'views'` instead of refusing
   with a clear message.
4. Limit: the gate counts against the authority's rib count, which was written down from Artem's rejection of v007.
   So this calibrates the gate on its own originating case and does not show it generalises. Held-out = the next
   TEC26 building with a presentation slide (AC04-07, AC09 wait for this pilot's acceptance).

**Replay** (Drive mount + Blender 5.1; inputs checked against the folders' `SHA256SUMS.txt`):
restore `C:/x/tec26-oks/pptx/facades/slide49.png` from the v010 Drive folder; per package extract `SM_Nku_1.zip` ->
`<P>/vpm`, `0000_Nku_1.zip` -> `<P>/npm`; `blender -b --python jobs/TEC26-OKS/scripts/qa_readback.py --
<P>/vpm/SM_Nku_1.fbx <P>/vpm.readback.json`; the A1 render command; the gate command on `renders_r127`; witnesses:
`uv run python docs/research/autoresearch-ac08-joint-gate-harness/witness.py jobs/TEC26-OKS/AC08/vpm_textures.json
<v010>/renders_r127 <v010>/fcmp_r1/compare.json <new dir>`, then the gate on each witness dir.
