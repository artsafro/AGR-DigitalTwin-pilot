# Autoresearch #131: is the D171 joint gate measuring the panel field on every facade? (OBSERVE)

Card t_2d2b153c (standing #131). Focus override (Artem 2026-11-27 ~02:15): calibrated texture/atlas defect signal.
The NPM-vs-VPM render-diff line is spent on the labelled data that exists: refuted on v007 (#125, #128), confirmed for
the single pair v006/v010 only (#130); KPP1 v004, Vatutino and Staropetrovskiy MAF have no byte-bound texture
reject (#128/#130 census, #1500 still open); v009 vs v010 differ only in FBX header bytes (all texture and atlas
hashes equal), so it adds no information. The calibrated seam signal that does separate Artem's v007 rejection is the
D171 joint gate (#127, E 116 vs 0). #127 recorded a precision defect on it (observation 2: v007 short facades show 3
joints in the sheet, the gate counts 0) and guessed the blue-panel mask. This round measures that defect.

## Preflight (before the contract; read-only, no gate run)

The v007 VPM readback (`AGR-evidence/127-ac08-joint-gate/pilot-v007/vpm.readback.json`) has its panel finish on UDIM
1001 on all four facades and the plinth on 1002 (field z -2.047..-0.041 m, width 2.438 m). The current spec
(`jobs/TEC26-OKS/AC08/vpm_textures.json`) binds the short facades to `PanelVJ12_RAL5015` = UDIM 1002 (the v010 layout).
The #127 `compare.json` rows for v007 А-Б / Б-А are at z = -1.645 / -0.141 m, below ground. Suspected cause: the gate
binds facade triangles by the CURRENT spec's UDIM and never checks that the selected field is the drawn panel field.

## Contract (frozen before the first measurement)

**Binding predicate P** (one facade, one package): the spec-bound VPM field `(lo, hi, zlo, zhi)` from
`joint_count.field_extent` is the drawn panel field iff `|(hi - lo) - field_width_mm / 1000| <= 0.010` m
(`sheet-facades.json`) and `zlo >= ground_m` (gate's own `ground_m` = min plinth `bbox_mm[1]` / 1000).
Tolerance 0.010 m frozen; no change after any score.

**Metric B131** (one number per package, lower = better): number of the 4 facades whose spec-bound field fails P.

**H131a (binding defect).** confirmed iff B131(v007) == 2 (exactly А-Б and Б-А), B131(v010) == 0, the unchanged gate
functions reproduce the #127 v007 row heights (-1.645 / -0.141) and v010 counts 29/29/11/11, 3/3 rounds identical.
B131(v007) == 0 = refuted; anything else / parity failure = inconclusive.

**Candidate C1 (harness only, OBSERVE - never applied to the gate).** For a facade failing P, rebind to the unique
UDIM on that facade normal whose field passes P; zero or several = refuse (reported, not scored). Then count exactly as
`compare_facades.main` does (rows 0.2 / 0.95 of the field, `render_row`, `count_joints(tol=0.01, dark=0.85)`,
reported count = 0.95 row), on the unchanged #127 renders.

**Render-free truth T** (per facade): `joint_count.mesh_facade_report` on the VPM readback with the package's own
Diffuse tiles read from its Drive `SM_Nku_1.zip` (as `qa_packages.facade_joint_checks`, tol 0.003, rows 0.2 / 0.95),
on the C1 binding; T = `joints_found` of the 0.95 row.

**H131b (#127 blue-mask guess).** On v007 short facades after C1, for each of {vpm, npm}: render count = 0 while
T >= 2 -> blue mask confirmed; |render - T| <= 1 on all four -> blue mask refuted (the zero came from binding);
otherwise inconclusive.

**Accuracy A131** (reported per label, C1 binding): sum over facades x {vpm, npm} of |render count - T|.
**E127 under C1** reported beside the #127 value: sum |render - (ribs - 1)|; ordering v007 > v010 must survive.

**Accepted control where the rule fires + perturbations** (in-memory spec copies, v010 only, synthetic):
- `K1` PanelVJ12 udim -> 1003 (v010 plinth): expected P fails on 2 facades, C1 rebinds to 1002, counts 11/11 exactly.
- `K2` PanelVJ30 udim -> 1004 (v010 frame): expected P fails on 2 long facades, C1 rebinds to 1001, counts 29/29.
- `N0` unchanged v010: P passes 4/4, C1 changes 0 facades (invariance: changed count 0, label exercised).
Per-variant bound: counts equal the clean v010 counts; any difference = C1 not recovering = inconclusive.

**Inputs (pinned, preflight aborts on mismatch).** `G:/Мой диск/AGR-evidence/127-ac08-joint-gate/` renders_r127 +
vpm.readback.json of pilot-v007 / pilot-v010, each checked against that folder's `SHA256SUMS.txt`
(sha256 `28ff6d843ff5ef759cb6267c19c653a22c8b8ddce7412a767f5897efde4ccd15`); `SM_Nku_1.zip` of
`559-tec26-oks-ac08-pilot-v007` (`271ee11b...`) / `-v010` (`2fe98379...`) checked against their folder sums. Code,
spec and sheet: this branch at the commit that adds this contract; the receipt records Git blob ids of
`joint_count.py`, `compare_facades.py`, spec and sheet. No Blender, no Max, no slide needed.

**Command** (3 rounds, deterministic; JSON per round must be byte-identical):
`uv run --frozen python docs/research/autoresearch-ac08-joint-gate-binding-harness/run.py <new out dir>`

**Budget / stop.** One candidate (C1). One measurement series of 3 rounds; wall stop 600 s -> inconclusive with the
same command. Harness repair attempts <= 3, each recorded. Labels: v007 rejected (`AC08/PILOT_REPORT.md` line 5),
v010 accepted visual reference; v006 / v009 not measured (no fresh camera-block renders; v009 texture-identical to v010).

**Forbidden.** Editing `compare_facades.py`, `joint_count.py`, `qa_packages.py`, the spec, the sheet, any Drive file
or delivered package; changing P, tolerances or labels after scoring; other cards' files.

## Results

(filled after the run)
