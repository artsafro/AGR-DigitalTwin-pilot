# Real-etalon checker mutation research (#1261)

## Contract and provenance

Goal: improve incremental correct-code detection of realistic agent mistakes, with no new
false alarms on the unmutated frozen corpus. This is checker research, not delivery acceptance.
Base production code: `origin/main` `5a9606d58ae79ccc44acc799dc5870eda23ab662`.
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

A hit requires an expected production `stage/finding name` and a **new** fail or review;
a pre-existing failure or an unrelated alarm earns no credit. Not-applicable operations
are listed with their reason, outside the denominator. All generated operations remain in
it, including misses and pre-existing-alarm cases. The package identity adds evidence and
a per-identity occurrence index so unrelated insertions cannot create artificial new hits.

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

## Results

Baseline measurement is in progress. No score, guard result or production improvement is
claimed until the measurement returns. Final per-class results and experiment receipts follow.
