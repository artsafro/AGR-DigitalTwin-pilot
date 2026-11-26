# Autoresearch #126 — Sokolniki source binding (OBSERVE)

## Frozen contract

The modal score stop is `artifact` (3/4 formal rows; `sources-dwg` 1/4).
The original #1608 comment is historical, not a fifth ledger row. #1917 and
#1928 own artifact interventions; #1973/#1974 own isolation. No atlas fallback
while ledger rows exist. #124 tested bank declarations only; this round tests
whether the two original client inputs specified in #1784 can be bound from
actual bytes despite the cited scratch copy being unavailable. #1972 merged a
**diagnostic** package, not acceptance or admission of a trainer holdout.

- **H126 (source-binding prerequisite only):** the exact #1784 FBX + facade PDF
  yield one bindable source pair with two distinct full SHA-256 digests that
  match the historical prefixes and do not overlap any declared tuning digest.
  Old = the unmodified bank row `sokolniki-body-v005` with its empty source
  set; candidate = the two exact #1784 inbox filenames in the replay script,
  never staged in the bank. M126 = number of bindable pairs (0 or 1); success
  requires paired delta +1 in all three fresh read pairs and stable full
  digests. Report median, all deltas and spread. No production KEEP even if
  confirmed; no model quality, artifact success, or admission claim.
- **Pins:** `origin/main@d77c3249d972904f5c397aeb48d81c1c43a651e3` bank + ledger
  (Git bytes SHA-256 `016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635`
  and `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7`).
  Source roles and PDF digest prefix `fd650339` from #1784 Inputs and versions;
  exact FBX prefix `feaae5271831802b` from the pinned job `uv_config.json`.
  Pin full candidate digests in the receipt as soon as the native series
  finishes. Prefix matches are provenance corroboration, not a preexisting
  complete manifest. Compare only against tuning declarations, not their bytes.
- **Witness and controls:** #124's declared 63A/63B same-source digest must
  collide; declared 63A/G22 must not collide. Clean candidate must exercise
  two native file reads per pair. In-memory controls on those identities:
  omit the PDF, rename an injected tuning digest as a candidate source (the
  overlap predicate must still fire), and flip one leading digest digit to
  simulate corruption. The candidate must bind 0/1 in each injected state.
  The clean bank row is the unchanged negative control; no accepted/rejected
  model-quality controls exercised, no claim about geometric equivalence.
- **Budget:** one candidate, zero alternatives, first pair doubles as timing
  pilot. Up to two confirmation pairs; abort if three times the first pair
  duration exceeds 60 s or any independent preflight/identity guard fails.
  Command timeout 60 s is the hard series limit. Budget/infrastructure stop
  = inconclusive; a completed series of three zero deltas refutes H126.
- **Replay:** `python docs/research/trainer_sokolniki_source_binding_r126.py`
  in the project worktree. Set `SOKOLNIKI_R126_INBOX` only to the same files
  if on a different host. No key or model opened, no scene build, source
  copies/edits, threshold changes, trainer/bank edits, runner, or published
  package changes. Same pinned metadata and comparison predicate in both arms.
  A source pair bound here cannot replace explicit approval of trainer scope
  (DWG/PDF required by current bank vs. FBX/PDF actually used in #1784),
  source isolation, calibration, and dry-run admission.
