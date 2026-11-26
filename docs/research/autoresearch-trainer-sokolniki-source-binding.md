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

## Result

**RU:** H126 подтверждена только для привязки исходников. Найдены оригинальный
Revit FBX и фасадный PDF из #1784: `0 → 1` пригодная для фиксации пара в каждом
из трёх повторов, совпадений с пятью заявленными tuning-хешами нет. Это не
допуск в тренажёр и не измерение прохождения `artifact`. KEEP и PR нет.

- Contract and measured code frozen at `7dad9a8481a1618c64eb630d6e39d7a1e1fc22a3`.
  Raw receipt: `trainer_sokolniki_source_binding_r126.jsonl`. Series complete;
  wall 0.329 s, individual pairs 0.056 / 0.044 / 0.044 s. Deltas +1/+1/+1;
  median +1, min/max +1/+1, spread 0. All six native reads used the original
  filenames at the #1784 inbox. The cited scratch copy was missing.
- Clean: old 0/0/0, candidate 1/1/1. Both full hashes are in every row.
  Declared overlap 63A↔63B = 1, 63A↔G22 = 0. Injected: all three states
  refused in every pair; one role changed per state (PDF omitted, FBX digest
  replaced, FBX prefix altered), the other role not exercised in that state.
  No native source was modified. Hash-bound replay matched all four records
  excluding timing. Replay elsewhere is **limited** to hosts with access to
  the same source bytes; the researcher did not distribute the client files.
- Not measured: cold artifact passes, accepted/rejected quality separation,
  source-isolated runner or dry-run admission of this pair, tuning source bytes
  or semantic equivalence. D409 accepts the body v006; D419 starts packaging,
  not acceptance of the #1972 diagnostic package. Neither changes the frozen
  `sokolniki-body-v005` trainer row or authorizes swapping its key.
- Review readiness: receipt only. Affected tests: `uv run --offline pytest -q tests/tools/test_trainer.py`
  → 93 passed. `bash C:/Users/artsafro/hermes_kanban/scripts/repo_guards.sh`
  → GREEN, 563 passed. Full suite: deferred to merge batch (rule 68).
- Next: bank owner and Artem decide whether the #1784 FBX/PDF pair and a
  specific accepted **body-only** key may replace the unbound DWG/PDF brief;
  bind matched rejected control separately. After verified isolation and audit
  (#1973/#1974), admit the held-out fixture and rerun the already-owned
  artifact interventions (#1917/#1928) on three fresh pairs.
