# Autoresearch #124 — source-independent trainer holdout admission (OBSERVE)

## Frozen contract (before the series)

The first failing step is `artifact` in 3/4 formal ledger rows; #1608's original
issue-comment row is historical, not a fifth formal row. The expanded #123 census
also has `artifact` as mode (20/68, with 24 unscored under its candidate selection
rules). Do not duplicate the FBX-first and Revit adapter trials (#1917/#1928), the
63B one-off (#121), Sokolniki admission (#122), or multi-FBX selection (#123).
The repinned G22 scoring key (#1970) does not itself provide a new build input.

- H124 (eligibility only): the published bank contains at least one stage-1 OKS
  holdout that admits a plain dry-run and has a nonempty, fully declared input
  hash set disjoint from the union of all three tuning entries. This conservative
  source-level criterion is for the next transfer trial, not a change to the bank's
  held-out label. A separate tower can test a different region, but sharing the
  whole Revit source cannot establish transfer to an independent source.
- M124: count of qualifying held-out IDs. Threshold >=1 in all 3 invocations
  to unlock planning of a transfer series; KEEP no product change in any case.
  `confirmed` if all three meet the threshold, `refuted` if all three return 0,
  otherwise `inconclusive`. This cannot confirm or refute an artifact treatment.
- Freeze all nine entries, six holdouts, three tuning IDs, unchanged production
  trainer and bank at `origin/main@e7cb8800ad537ca0cbad19e49ade2ea8ae1e904b`.
  Worktree code base `83e44c0c863fdd70839b76a9cab384618ed8af84`; `tools/trainer`
  and `docs/trainer` identical by Git diff. Bank Git bytes SHA-256
  `016aab0c7ae3496643fdfdc69582be8e6cb877e2f62d2ff19ebef23a7be36635`;
  ledger Git bytes SHA-256 `230eace1a0a434cb25091f449760d3895d5b7d169086a2f2ba049db88a8496a7`.
  Manifest digests are declarations, not a readback of source bytes. Filesystem
  reachability is point-in-time, therefore dry-run observations can differ on
  another host. Never read the key bytes.
- Replay at the freeze commit (first commit adding this file and its companion):
  `uv run --offline python docs/research/trainer_holdout_sources_r124.py`.
  It calls existing `agr trainer run ID --lane codex --out NEW --dry-run`.
  Budget: three complete nine-entry sweeps, zero alternate candidates, no new
  overlays, stop at first unexpected CLI failure or at 150 s (inconclusive).
  Each sweep re-invokes the CLI; manifest overlap is static, not three independent
  source acquisitions or cold attempts. Record wall time separately.
- Witnesses: 63A/63B must share >=1 declared hash (the original site FBX),
  regardless of dry-run outcome; 63A and G22 must have disjoint source hashes.
  The 63A dry-run is expected to admit on this host and 63B to refuse as unscheduled.
  Synthetic predicate-only injections: rename the shared file without changing
  its digest (still 1 match), change it to a new digest (0), remove its digest
  (unclassified, not independent). Unknown evidence is never a pass.
- No flag flips, source copies/edits, key access, live agent/Max, threshold changes,
  fake `passed`, or edits to anyone else's files. Dry-run must not create `--out`.
  Not measured: native source hashes or geometric equivalence, calibration of
  model quality, isolation, artifact passage, and cold-agent adoption.
