## Summary

Replay #111: document the optional component-volume diagnostic as `new-case`,
bound its synthetic guarantees and distinguish author evidence from historical
reviewer checks. No numeric algorithm, baseline behavior or test assertions change.

```diff
 src/twinqa/geometry/component_volume.py
+  new-case and bounded-scope docstring
 docs/qa/component-volume.md
+  Author evidence boundary, generator bounds and reproduction command
 docs/qa/evidence/component-volume-111/
+  README.md, red.txt, green.txt
```

## Evidence

- RED at `fab1fdd`, clean tracked source: `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t111-red tests/qa/test_component_volume_evidence.py::test_diagnostic_documentation_regression`
  -> **1 failed**, exit 1: expected missing `new-case` assertion.
- GREEN at `fab1fdd` plus the module docstring and documentation diff committed
  in `3de3c9a`: `uv run pytest -q -p no:cacheprovider --basetemp=C:/x/t111-green tests/qa/test_component_volume_evidence.py tests/qa/test_component_volume.py`
  -> **449 passed, 0 failed, 0 skipped**, exit 0. Includes the unchanged RED
  regression, 400 seeded cases and 48 existing tests (including the frozen
  24-case matrix and unchanged baseline controls).
- Final head `187a27f` changes only receipt text and output whitespace after
  testing; tested source, documentation and test assertions are unchanged.
- Evidence: `docs/qa/evidence/component-volume-111/README.md`, `red.txt`, `green.txt`.
- Full suite: **not measured**, explicitly prohibited by this replay. Benchmarks
  not run; focused diagnostic tests supply the bounded evidence.
- Regression evals: passed **not measured**, failed **not measured**,
  not-measured task count **not measured**; no supported author-session transcript
  or classified-question evidence supplied, so no run/report path exists.
  No unavailable check is counted as passing. A future merge requires the
  checklist's branch-evidence regression-eval report and broader checks.
- Review fixes: not applicable; no review round in this replay.

## Author receipts

Author ran the existing beyond-matrix synthetic probe in this session; this PR
does not claim newly authored probe code. Invariant -> probe -> result:

- Analytic product volume / reversed sign -> randomized boxes -> **100/100 cases**.
- Coincident index-disjoint and separate-mesh membership -> exact local IDs -> **100/100 cases**.
- Open/inconsistent topology -> abstention with null volume/sign -> **100/100 cases**.
- Determinism, ordering, immutability and empties -> repeats / permutations -> **100/100 cases**.

Command: the GREEN command above. Generator:
`tests/qa/test_component_volume_evidence.py`; independent Python `random.Random`
seeds **0..99**, side lengths **[0.2, 20.0]**, Z rotation **[-pi, pi]**,
XYZ translation **[-1e6, 1e6]**, shuffled triangles and chosen deletion/reversal.
Analytic relative tolerance **1e-6**. These count pytest cases, not assertions.
Evidence path: `docs/qa/evidence/component-volume-111/green.txt`.
Historical reviewer 800 checks are not author-session telemetry.

Environment: Windows PowerShell, CPython **3.14.7**, pytest **9.1.1**, NumPy
**2.5.3**; `.venv` created here with `uv sync`. No other checkout/venv used.

## Verification boundary

Verification boundary: author ran the RED/GREEN commands above on `fab1fdd` and
the exact source/doc diff committed as `3de3c9a`, Windows local venv, 1 failed
then 449 passed; final `187a27f` normalizes evidence only; reviewer pending,
no independent review claimed; not measured full suite (replay prohibition),
benchmarks (focused scope), regression evals/session telemetry (no supported
transcript); CI not measured (GitHub access/publication prohibited).

All requested documentation and author probe receipts are present. Independent
review and future merge gates remain open. No delivery acceptance is claimed.
An initial `gh issue view` attempt failed before the local replay restrictions
were discovered; no GitHub operation succeeded and no subsequent calls were made.

## Merge Danger

**Door:** two-way

**Blast Radius:** documentation and module docstring; no runtime statements change.

## Out of scope

Numeric fixes, registered-pattern creation, arbitrary imported-model guarantees,
real-model certification, CAD proxy #99, policy/evaluation/hook changes,
benchmark/jobs/standards changes and publication. No push, real PR or merge.

## Agent trace

- Sessions: not measured (no transcript)
- Written by: Codex
- Subagents: not measured (no usage log, no transcript)
- Skills: not measured (no usage log, no transcript)
- Commands: not measured (no usage log, no transcript)
- Hook denials: not measured (no transcript)
- Retries: not measured (no transcript)
- Context at handover: not measured (no transcript)
- Duration: not measured (no transcript)
- Commits: `fab1fdd..187a27f` (2 commits)
