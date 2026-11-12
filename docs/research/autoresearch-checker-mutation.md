# Real-etalon checker mutation research (#1261)

## Contract and provenance

Goal: improve correct-code detection of realistic agent mistakes, with no new
false alarms on the unmutated frozen corpus. This is checker research, not delivery acceptance.
Base production code at card start: `origin/main` `5a9606d58ae79ccc44acc799dc5870eda23ab662`.
The manifest's preparation HEAD is `4c30d864` (tests-first), and the controller baseline
is `b2133b9f` (harness). Neither changed production checker code from that base.
Unrelated later main merges were not folded into the frozen corpus.
Card: `t_2f2b2b55`; seed: `1261`; offline Blender: `5.1.2` (`ec6e62d40fa9`).
No live Max, source writes, source geometry repairs, relaxed checks or Git LFS.

The spec owner removed unavailable ELV v005 on the card on 2026-11-12. Its status is
**not available**, never substituted with the customer-source ZIP. The four remaining
families are represented by the explicit source selection in `checker-mutation-corpus.json`:

- Vatutino: the already-saved Ground-only v015 site slice in Flora run-v004 inputs.
  The first preparation mistakenly selected the combined delivery (559442 triangles,
  746063 vertices). Fresh readback exceeded eight minutes and used approximately 14 GB;
  it was cancelled before any score was measured. No acceptance or metric is claimed for it.
- KPP1: R1 v002 VPM FBX and its original delivery ZIP on Drive.
- MAF: accepted generated row 02 (`MAF_GEN_0001`) with v006 IDs, not a claim that the
  whole material library or a v007 delivery scene was accepted. Its source SHA-256 exactly
  matches `library/maf/catalogue.json`:
  `c6c8bf7a7ca3a34a3cfead16beb349037315d5c68756f16efe1840760eba96b0`.
  Specification dimensions are `[6.6992, 2.5001, 0.45]` metres from that catalogue, D094 tolerance.
- Flora: run-v004 representative `pos01_101_npm.fbx` (Tilia star), not final site acceptance.
- Package checks additionally use the existing combined Vatutino VPM ZIP and KPP1 ZIP.

Existing fail/review/not_run verdicts are frozen, not reclassified as false positives or
silenced. These inputs are working etalons, not an assertion that every delivery gate passed.

## Measurement boundary

Scene mutants are real operations on freshly imported FBX copies in factory Blender.
The existing `tools/blender/fbx_readback.py` functions measure the altered geometry, UV,
materials, transforms and images; the generator never plants defect counts or verdicts.
They test the scene-checker boundary, not mutant FBX export/roundtrip behaviour.
Units are actual binary GlobalSettings edits, measured only by the existing V002 metadata
checker (no invented post-unit-change scene facts). Package mutants are actual ZIP copies:
remove one PNG or resize that PNG to 8192 square, keeping its other members.

One seeded unapplied scale choice lies in the 5–50% range; a separate baked MAF size
mutation is +50%. Valid 5% changes inside an area's existing dimension tolerance must not
become false failures. MAF colour merging changes actual polygon material indices.
Missing per-project material/colour/schedule operands remain misses, never guessed rules.

The issue's literal score counts a mutant with any expected production `stage/finding name`
whose status is fail or review. An unrelated alarm earns no credit. **Both metrics are
reported:** the archived controller used a stricter *incremental* score that excludes an
alarm already present on that clean etalon. `checker_mutation_summary.py` independently
reduces the same immutable observations to the literal issue metric and validates the
stored incremental counts. This labeling distinction was caught in hostile self-review;
no generator, oracle, finding or controller event was edited to correct it. Every round
was checked under both definitions: the KEEP/discard and stopping choices are identical.

Not-applicable operations are listed with their reason, outside the denominator. Every
generated operation remains in it. The package identity adds evidence and a per-identity
occurrence index so unrelated insertions cannot create artificial new hits.

The guard preserves every existing finding verdict exactly and rejects removed findings,
relaxed failures, new fail/review and new not_run findings. A new rule may add a pass only.
The source manifest, generator, measurement runner, guard and baseline oracle are SHA-256
pinned. `measure` refuses file drift, code drift, stale oracle, existing outputs and corpus
output aliases. `seal` is preparation-only, once, before baseline.

## Preparation evidence

Acceptance table was written to the PR body draft before code (`tmp/1261-pr-body.md`).
Tests-first commit: `4c30d864`; RED: **15 failed / 1 passed** (guard module absent);
initial GREEN: **16 passed**. Expanded guard/probe tests: **24 passed**.
The initial repository-local pytest temp path was rejected by the existing conftest and
redirected; subsequent probes use the card-specific `C:/x/t_2f2b2b55` path.

Frozen manifest SHA-256 (66 files):
`205a8068bd1dc2fcee4580d9ebe6ffb9c4ca6f4e3e2ca10be87ac02a94660788`.
Binary and large JSON evidence are external artifacts; only compact text/hashes are committed.

## Results and stopping condition

**Issue mutation score: 38/52 (73.0769%) -> 42/52 (80.7692%), +7.6923 percentage
points.** Incremental auxiliary score: 30/52 -> 34/52 (65.3846%). Target 95% was
**not reached**. Stop: rounds 4, 5 and 6 each gained 0%, the specified three-round
<1% stop. Six rounds ran; only rounds 1 and 3 are retained.

All **129 original finding verdicts** across four scenes and two packages are identical.
Four new findings are pass. **0 new false alarms**, no removed or loosened checks;
this does not mean the imperfect working etalons are delivery-compliant.

| Round | One hypothesis / source | Issue caught/52 | Incremental caught/52 | Guard | Decision / Git evidence |
|---|---|---:|---:|---|---|
| baseline | frozen production base | 38 | 30 | PASS | `b2133b9f`, original source code unchanged |
| 1 | NPM image sides <=2048 px, reg p.9 §5.2 | 40 | 32 | PASS | KEEP `0d0fbfbe` |
| 2 | material-bound GroundEl 512 cap, reg p.10 §5.12; Flora independent | 40 | 32 | not_run (no gain) | trial `8f7e76f0`, revert `fbf96ad5` |
| 3 | NPM opaque material/diffuse and polygon assignment, reg p.8 §4.4 / p.9 §4.5; never VPM cleared paths | 42 | 34 | PASS | KEEP `3f03007b` |
| 4 | closed-solid orientation, reg p.8 §3.8 / p.29 §3.15 | 42 | 34 | not_run (no gain) | trial `a2c30893`, revert `78b9d8fe` |
| 5 | NPM resolution grid with 128 placeholder exception [D013] | 42 | 34 | not_run (no gain) | trial `4376ab8d`, revert `9eaefbfc` |
| 6 | packed PNG bytes <=3 MiB, reg p.9 §5.3 / [D015] | 42 | 34 | separate negative probe FAIL; control not_run (no gain) | trial `9cdaa3d8`, revert `ad048787` |

The control runs the guard only after a metric gain. `not_run` is not a guard pass.
The separate real round-6 negative probe rejects Flora's 4,216,701-byte packed diffuse.
No 3 MiB rule was relaxed and no waiver was invented; that candidate was not retained.

Round-4 repair history: the first helper exposed **6 existing structured-error regressions**
(nonfinite coordinates / invalid indices). One repair made those geometry errors explicit
fail findings rather than exceptions: **675 passed**, then its five orientation probes
passed. The candidate still had no metric gain and was reverted, not shipped.

The foreground control has no native Codex Goal API in this Hermes session. After the
three-no-gain condition, `stop` reported that it only supports detached runs. Clean HEAD
and no controller/worker were verified; the supported `archive` API preserved the ledger
at `autoresearch-results/archive/20261112-153757`. `run.json` and `events.jsonl` were
never rewritten. This is an archived stopped-by-card study, not a target-complete claim.

## Final table

The issue column includes pre-existing expected alarms; the incremental column exposes
that confound rather than calling every alarm a causal detection. Two N/A operations are
KPP1 FBX missing/oversized textures (its paths are intentionally cleared); ZIP mutants
are still measured. All 52 generated cases are retained in the denominator.

| Class | Baseline caught/total | Final caught | Final missed | Incremental caught | N/A | Finding code |
|---|---:|---:|---:|---:|---:|---|
| unapplied_scale | 4/4 | 4 | 0 | 4 | 0 | V002/scale 1:1; V004/applied transforms |
| flipped_normals | 2/4 | 2 | 2 | 1 | 0 | V004/MAF flipped normals; V004/topology defects |
| self_intersections | 4/4 | 4 | 0 | 3 | 0 | V004/topology defects |
| duplicate_faces | 4/4 | 4 | 0 | 3 | 0 | V004/co-directional clearance; V004/topology defects |
| missing_ucx | 2/2 | 2 | 0 | 2 | 0 | V010/UCX present |
| wrong_ucx_gap | 2/2 | 2 | 0 | 2 | 0 | V010/UCX intersections; V010/UCX piece gap (advisory) |
| wrong_material | 0/4 | 2 | 2 | 2 | 0 | V005/material assignments |
| wrong_texel | 0/2 | 0 | 2 | 0 | 0 | none |
| wrong_name | 4/4 | 4 | 0 | 2 | 0 | V012/mesh names |
| wrong_pivot | 2/2 | 2 | 0 | 2 | 0 | V013/origin at FBX zero; V013/pivot at geometric centre; V013/shared pivot |
| leftover_object | 4/4 | 4 | 0 | 4 | 0 | V003/object types |
| ground_skirt_missing | 1/1 | 1 | 0 | 0 | 0 | V003/ground skirt depth |
| wrong_units | 4/4 | 4 | 0 | 2 | 0 | V002/system units |
| missing_texture | 2/4 | 2 | 2 | 2 | 1 | V007/map set/slot 1/0 |
| oversized_texture | 2/4 | 4 | 0 | 4 | 1 | V006/texture dimensions; V007/map size (KPP1 / Vatutino Diffuse) |
| baked_size | 1/1 | 1 | 0 | 1 | 0 | V004/MAF dimensions vs specification |
| maf_zone_merged | 0/1 | 0 | 1 | 0 | 0 | none |
| flora_height | 0/1 | 0 | 1 | 0 | 0 | none |

## Limits and user questions

- **No undecided threshold was introduced; user threshold questions: none.** Bounds used
  are existing regulation / [D013], [D015], [D094], [D098], [D099], [D160]. Open C18
  (Flora opacity if needed) was not turned into a fail rule.
- This is a representative four-family snapshot, not every mesh in each library. The
  chosen scale draw is -50%, with +50% baked MAF size; it does not establish full recall
  throughout the allowed 5–50% stimulus range.
- Raw-scene and package boundaries are separate. VPM standalone readbacks can lack the
  diffuse-size operand, so the texel mutants remain misses. No pixel size is guessed from
  a name; the ZIP validator's scene/UDIM integration is not certified by this study.
- The raw Flora star lacks an attached per-plant schedule/crown operand. A semantic
  height/band check was not invented from its filename. MAF merged colour zones need
  approved per-face colour/specification identity; fewer material IDs is not itself a rule.
- Working MAF/Flora names/units and the Ground skirt/topology already have alarms in the
  oracle. Literal score counts them; incremental diagnostics correctly do not. No source
  was repaired to make an oracle pass.
- NPM missing-texture mutants now get the new material-assignment alarm, but that code
  was not in their frozen expected-code set. They remain strict code-matching misses;
  the expected set was not expanded after seeing the result.
- Round 2 demonstrates corpus resolution limits: 8192 px was already caught by round 1;
  the frozen set has no intermediate 1024 px MAF atlas to reward a correct 512 px check.
  No intermediate case was slipped into the denominator after baseline.

## Frozen evidence and reproduction

Evidence root: `G:/Мой диск/AGR-evidence/1261-checker-mutation/run-v001/`.
It contains the exact corpus, original baseline, all candidate cache receipts, control
ledger/logs, final observations, literal+incremental summary, CSV and `SHA256SUMS.txt`.
Large FBX/ZIP/JSON data stay there, not in Git or LFS. The compact committed
`checker-mutation-freeze.json` is byte-identical to the runtime manifest; a scoped
`.gitattributes` line preserves its CRLF instead of silently changing its frozen hash.
`checker-mutation-results.json` contains the compact result tables from real observations.

| Component | SHA-256 |
|---|---|
| Corpus manifest (66 files) | `205a8068bd1dc2fcee4580d9ebe6ffb9c4ca6f4e3e2ca10be87ac02a94660788` |
| Baseline oracle | `7d747bf91ef312692eb2b04feb2bb6ea74c623fd0c53b8cb52c097a34efd07e2` |
| Blender generator | `90eba18b1e9e0a5988f56711fd4e0ed1de3f48e327eade26b25e095c88b6a689` |
| Exact guard | `34de54dbaea2159bcb97ca09a1f1fbd4214905eead0e10bfc07df5be941b128d` |
| Frozen measurement runner | `d507f23971472a835450e184d9f8996147a4659a6caaabfca2f46f0031b3af3b` |
| Retained checker/standard tree fingerprint | `fcbb470a499cdac5e9f9ac351c5cf50d91d1c9d438eee647f812ba94cc7c3f3e` |

Run from the PR worktree with a fresh output path (existing outputs are refused):

```bash
uv run python tools/research/checker_mutation.py measure "G:/Мой диск/AGR-evidence/1261-checker-mutation/run-v001/corpus" --manifest-sha256 205a8068bd1dc2fcee4580d9ebe6ffb9c4ca6f4e3e2ca10be87ac02a94660788 --oracle-sha256 7d747bf91ef312692eb2b04feb2bb6ea74c623fd0c53b8cb52c097a34efd07e2 --output tmp/1261-replay.json
uv run python tools/research/checker_mutation_summary.py "G:/Мой диск/AGR-evidence/1261-checker-mutation/run-v001/baseline.json" tmp/1261-replay.json --output tmp/1261-summary-replay.json
```

The first command retains the frozen controller's auxiliary metric. The second prints
issue score **0.7307692307692307 -> 0.8076923076923077**, **42/52**, guard **PASS**.
Neither command claims a model/delivery pass.

## Verification receipts

- Guard initial RED **15 failed / 1 passed** -> **16 passed**, later **24 passed**.
- Round 1 production RED **10 failed** -> affected **687 passed / 18 deselected**.
- Round 3 RED **3 failed / 1 passed**, polygon-binding RED **3 failed** -> affected
  **694 passed / 18 deselected**. Expanded affected QA: **4962 passed, 6 skipped,
  7 xfailed** (pre-final-head diagnostic run, not the final suite receipt).
- Real Blender 5.1.2 generator repeat/source-preservation/invalid-input smoke: **2 passed**.
- Contract/static preflight: **107 passed / 2 deselected**; literal-metric reducer
  tests-first **5 failed / 1 passed**, then **9 passed** (includes additional bad-input probes).
  A fresh subset caught a neighboring-module import-path error; the reducer now imports
  its sibling explicitly. No frozen evaluator or guard was changed for this fix.
- Final exact-head affected/full-suite counts and generated CI-RECEIPT v1 are in the PR
  evidence block and external receipts. They are generated after the final text commit,
  so recording their numbers does not invalidate the head being certified.

