# AGR Tools #707 — synthetic acceptance evidence

No production scene, team source or encrypted plugin was used. The package is
built entirely from new adapter code and our existing Python hygiene planner.
The original team scripts were not opened during implementation; only the two
public audit documents were consulted. Reviewer spot-check remains independent.

## Rework R1 — physical-distance frame (current candidate)

The initial results below are historical evidence for `4723827`, not the current
package. Reviewer R1 found that unbaked object scale changed native xView's
physical thresholds. `3d393ce` adds a test-first installed-package regression:
14/48 cases fail on the previous implementation. The repair detaches and bakes
only evaluated disposable copies; originals and hierarchy remain unchanged.

- Current MZP SHA256: `84122ef47e61e7d5ce380218e389bedc6517c3bb454ac0e9e94145e5538253b8`;
  two fresh builds agree. Storage: `G:/Мой диск/AGR-evidence/707-agr-tools-max/t_17f45574-v002/`.
  `rework-SHA256SUMS.txt` pins both packages and synthetic source/copy fixtures.
- Final matrix: 10 transforms × 6 physical gaps × 2 system-unit settings =
  **120/120** assertions in Max 2024 and **120/120** in Max 2026. Transforms:
  identity, uniform small/large, nonuniform small/large, mirrored X/Z,
  parent small/large, rotated-child/nonuniform-parent shear. Gaps in mm:
  1, 2, 4.99, 5, 5.01, 10. Exact IDs and original-offender selection asserted;
  source geometry/attributes/transforms/parent, checker settings and scene node
  counts verified unchanged even on threshold errors.
- 1 mm: vertices 1–6 and faces 1–2; 2 mm: explicit ambiguity error;
  4.99 mm: faces 1–2; 5 mm: native faces 1–2 or explicit ambiguity error,
  never clean; 5.01/10 mm: zero findings. Primary thresholds remain 2/5 mm.
  A separate face ambiguity probe at 5 mm × (1 + 2e-7) may only reject additional
  faces; it never supplies findings. This follows an expanded RED case where
  nominal 5 mm × scale .1 became 5.00000035 mm after float32 baking.
- Max 2024: **native exit 0**, 37.1 s; baseline installation, three clean/planted
  checks and all earlier dry-run/guard controls also pass. Max 2026: final reports
  and completion marker verified, 37.8 s, but native exit 4294967166 retains the
  known external startup CLR error; not claimed as a clean process.
- Affected Python tests: `uv run pytest -q tests/max_tools -p no:cacheprovider
  --basetemp=C:/x/t_17f45574/rework-final`: **31 passed**, 0 failed (0.26 s).
  Per rule 49, no second full suite: the first-review 15201-pass receipt stays
  bound to `4723827`, not relabelled as current-head evidence.

`rework-summary.json` records repair attempts; `rework-red-transforms.json`
retains the original failing matrix. `rework-max2024-*` and `rework-max2026-*`
are the current complete raw logs, baseline results and transform reports.
Use `AGR_TEST_PACKAGE=<new-built-mzp>` to select a package without overwriting
an earlier artifact; `AGR_TEST_OUTPUT` must be a new native `C:/...` path.

## Measured results (initial candidate)

- Builder: two fresh outputs, SHA256
  `6cdd47073c7c532a346a52c2dc6c654519d825d6e0d93aeb401e2e7feba51406`.
  `build.json` records commands, Python toolchain and exact ZIP member inventory.
- Max 2024.2.5 (26.2.5.192), Python 3.10.14: native process **exit 0**, 39.5 s;
  real MZP install registered four macros; three registered button macros executed;
  three clean fixtures produced zero findings; three planted checks matched the
  literal expected identities; cleanup applied to independent copies with zero
  remaining hygiene findings. Source geometry, face IDs, channel-1 coordinates,
  original CA/UDP and source-file hash were preserved.
- Max 2026.3 (28.3.0.30732), Python 3.11.12: identical fixture assertions and final
  completion marker, 42.9 s. **Not a clean native process exit**: 4294967166 from
  the pre-existing `polyunwrapper_autoload.mse` startup CLR exception (documented
  in CAPABILITIES.md). Wrapper status `ok` with warnings is retained verbatim,
  not relabelled as process success. The fresh results file was independently read.
- Python unit tests: `uv run pytest -q tests/max_tools -p no:cacheprovider
  --basetemp=C:/x/t_17f45574/pytest-final`: **31 passed**, 0 failed, 0.25 s.
  Includes 16 generated planner-parity stimuli, 10 declared-status combinations,
  duplicate/unsupported/non-finite/partial report rejection, source mutation,
  hardlink/resolved input aliases, stale output/partial preservation and fresh CLI.

The raw per-version logs and results are adjacent. Findings are diagnostic,
not whole-scene delivery acceptance. `attempts.json` retains failed development
probes (including the initial missing implementation RED and environment crash).

## Native probe coverage

`tests/max_tools/run_agr_tools_native.py` is run only through the shared lock:

```bash
AGR_TEST_OUTPUT="<worktree>/tmp/<new-run-directory>" python C:/Users/artsafro/.hermes/scripts/dcc_batch.py max --version 2024 --file tests/max_tools/run_agr_tools_native.py --card t_17f45574 --out tmp/<new-log>.json --timeout 300 --wait 600
```

The MZP must first be built at `<worktree>/tmp/AGR-Tools-0.1.0.mzp`.
Every invocation requires a new output directory. It creates its own synthetic
scene, saves an immutable source and opens a file copy before button checks.
Installation/startup destinations are isolated below that directory, including
an apostrophe in the measured path. The user scripts/startup directories are not
installation targets. Max's own third-party startup scripts still run unchanged.

The runner checks stale-preview rejection before cloning; duplicate and empty
explicit target lists; helper/empty-mesh rejection by all three cores; missing UV
rejection; MatID 999/1000/1001/1002; missing material; metre/millimetre parity;
restored native tolerance settings; exactly-2-mm error; startup re-registration;
repeat-install refusal with unchanged installed bytes. The two native thresholds
remain 0.002 m and 0.005 m. A narrow float32 boundary ambiguity returns an error
rather than silently asserting clean. Full source and output inventories are
reported; unsupported nodes are errors, not silently skipped.

## Repairs and limitations

- Initial test-only commit `7bf4d8c`: builder assertion failed because it did not
  exist. Parser RED: 8 failed before implementation; later malformed-tool probe:
  1 failed / 30 passed before string-type validation, 31 passed after.
- Native slices progressed from missing macros -> missing xView -> missing MatID
  -> missing cleanup; each was exercised before its implementation.
- Fixture CA definition needed explicit MAXScript global binding. An empty mesh
  fixture needed explicit zero vertex/face counts because Max reused constructor
  defaults. Expected defect findings/thresholds were not retuned.
- Hostile probes found: exact-2-mm native false-clean (now explicit error), quote
  interpolation in startup (now ExecuteFile with a native root lookup; nested
  ExecuteFile does not reliably change Python `__file__`), and a builder accepting
  inputs rewritten during assembly (now immutable byte capture + pre-publication
  reread). A rewrite restored between reads is not detected; no stronger lock is
  claimed. Predictable `.partial` files are neither created nor deleted.
- One Max 2024 startup died before the script (exit 4294967295, no START marker);
  rerun succeeded. No machine-wide settings or user startup plugins were changed.
- Native xView is used rather than the kernel's *additional* projected-area rule;
  this diagnostic is not the complete geometry validator. Cleanup supports an
  Editable Poly/Mesh base, preserves modifier stacks and only changes export
  copies. The remaining roadmap buttons are deliberately not implemented.

## Binary storage

`G:/Мой диск/AGR-evidence/707-agr-tools-max/t_17f45574-v001/`
contains the installable MZP and synthetic source/copy MAX fixtures for both
versions. `SHA256SUMS.txt` is stored there and mirrored here. No binary or LFS
object is committed. Full-suite and procedural-eval receipts are in the PR body;
procedural telemetry not measured by Hermes is never called passed.
