# Native xView version-refusal smoke: #1790 / #1798

Date: 2026-11-24. Card: `t_14809b3f`. Verdict: **PASS — retain the merged fallback**.

## Question and scope

Does merged PR #1798 actually refuse Max 2026.3 with the named diagnostic before
job parsing, .NET helper compilation, staging or receipt mutation?

#1790 allowed either real 2026 count support or a named early refusal. #1798 chose
**refusal**, not count support. Its offline reference is 141 affected tests passing
and 26/26 release-predicate probes; native execution was explicitly pending.
This experiment closes that native gap, not Max 2026 count parity. One method only:
version preflight. No production code was changed.

## Setup

- Repository base: `8aa00f70`; includes merge `4290e456` (#1798).
- Before: exact `tools/qa/xview_dump.ms` from `d453175c^`, materialized as a temp copy.
- After: unmodified merged `tools/qa/xview_dump.ms` from this worktree.
- Headless **3ds Max 2026.3 (28.3.0.30732)**, verified from native process log and
  `maxVersion() = #(28000, 68, 0, 28, 3, 0, 30732, 2026, ".3")`.
- Only `dcc_batch.py max --version 2026`; initial `--ping` succeeded.
  Sessions were serialized through the shared runner lock. No GUI attach, no other DCC.
- One **synthetic** 100 x 100 x 100 mm Editable Poly box, 6 quad faces / 8 vertices,
  system units millimetres, system scale 1.0. It was saved to a fresh temp `.max`.
  No project source, benchmark etalon or `data/` file was opened or modified.
- `jobs.txt` cases: absent; partial (`#nonce:native1790` + `box|partial`);
  valid (same nonce + `box|<synthetic.max>|synthetic_box|plain||`).
- Each run has a fresh output/stage directory. Pre-existing sentinel `box.json`,
  `report.jsonl`, `done.txt`, `failed.txt`, and stage sentinel test preservation of
  stale receipts, not just absence of new files. Snapshots compare file inventory,
  SHA-256, sizes and modification timestamps, including the source `.max`.
- Baseline valid case ran first (3 fresh sessions), then all three merged cases
  (3 fresh sessions each). Each process exits on refusal, so fresh sessions are required.

## Commands

From the task worktree:

```bash
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --ping
python experiments/1790-xview-native-smoke/run.py
env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run pytest -q -p no:cacheprovider tests/qa/test_xview_dump_contract.py tests/qa/test_xview_parity_cli.py
```

`run.py` invokes the permitted wrapper with `--file`, `--out`, `--version 2026`,
`--card t_14809b3f`, and per-run `XVIEW_OUT` / `XVIEW_TEMP`. Inputs and raw evidence
were created under `%TEMP%/agr-3dsmax-t_14809b3f/`. Reruns intentionally refuse to
reuse case directories: archive/remove only this experiment's temp directory or
choose a fresh card-specific directory before repeating.

## Baseline versus merged

Times are wrapper-reported native-session wall time, including startup, not xView
checker time. Medians use three runs each; this is not a speedup claim.

| Implementation / input | Runs | Median seconds | Native exit (unsigned Windows) | Diagnostic | Inventory/bytes/mtime unchanged |
|---|---:|---:|---:|---|---:|
| Before #1798 / valid | 3 | 26.7 | 4294967295 | .NET `Operation is not supported on this platform` | 3/3 |
| Merged #1798 / absent jobs | 3 | 25.1 | 4294967295 | `XVIEW_UNSUPPORTED_MAX_VERSION` | 3/3 |
| Merged #1798 / partial jobs | 3 | 26.1 | 4294967295 | `XVIEW_UNSUPPORTED_MAX_VERSION` | 3/3 |
| Merged #1798 / valid jobs | 3 | 28.3 | 4294967295 | `XVIEW_UNSUPPORTED_MAX_VERSION` | 3/3 |
| Affected offline tests after smoke | 141 | 35.62 total | 0 | 141 passed | n/a |

`dcc_batch.py` returned 1 / status `error` for all 12 expected native failures.
Native exit was **4294967295**, not an assumed literal exit 1; acceptance requires
nonzero. The harness itself exited 0 after checking all 12 expected outcomes.

Actual merged diagnostic (all nine runs):

```text
XVIEW_ERROR -- Runtime error: XVIEW_UNSUPPORTED_MAX_VERSION: unsupported Max version (release 28000); the file-identity helper requires .NET Framework CodeDOM. Use 3ds Max 2024.
```

All nine merged cases reject independently of job completeness, replacing the
original helper exception. Zero input/output/stage inventory differences; zero
byte/mtime differences. No fresh receipt or count was emitted. Existing stale
receipts are intentionally left untouched and must not be treated as fresh success.

Counts and maximum geometric deviation: **not measured / not applicable**: the
accepted fallback refuses before reading geometry. The synthetic fixture inventory
was measured during preparation only. No Max 2024 rerun or 2026 checker parity is claimed.
Offline release-boundary probes from the PR were not native-tested here.

Code size: production runner 457 -> 460 lines in #1798 (+3); this experiment adds
111 lines of isolated orchestration and no production changes. The affected run
matches the PR's 141/141 result. One pytest basetemp warning was redirected by the
repository safeguard to `C:/x/t-c4302d68`; no failure. No full suite was run, per card.

## Evidence

Small machine-readable results: `experiments/1790-xview-native-smoke/results.json`
(per-run diagnostics, exits, timing, source/output/stage snapshots and native setup log).

Durable raw receipts, `.max`, scripts and inventory sentinels (86 files plus manifest):

`G:/Мой диск/AGR-evidence/1790-xview-native-smoke/evidence/`

Manifest: `SHA256SUMS.txt`, SHA-256:
`24158b9916b970a0d408085bdf972379cb81e9cb9d71c2a88c68d4c97eff3341`.
No binary evidence or Git LFS is committed.

## Verdict and follow-up

**ADOPT / retain #1798 version preflight.** Native fallback contract passes 9/9;
original #1790 defect reproduces 3/3. No fix is needed and #1790 need not reopen.
This is technical acceptance of refusal only, not model/delivery/user acceptance.

Proposed follow-up (not created): **Support native xView on Max 2026 without runtime
CodeDOM** — replace the file-identity implementation behind a new supported path,
retain alias/input/nonce protections, add RED tests and run native 2024/2026 count
parity on synthetic and copied real fixtures before lifting the version guard.
This is optional capability work, not a missing requirement of the accepted fallback.
