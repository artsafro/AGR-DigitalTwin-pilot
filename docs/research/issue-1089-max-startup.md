# Max 2026 batch startup diagnosis (#1089)

## Result and limits

The reproducible `_maxUsd` startup failure is **parent virtualenv contamination**, not evidence that the installed USD plugin is incompatible with this Max build. Removing only `VIRTUAL_ENV` from the child environment restores native PySide/Shiboken and USD imports. No installed plugin was disabled, renamed, uninstalled or updated; no foreign Max process was terminated.

There is also a **separate, still unresolved native shutdown crash**: Windows Application Error 1000 records `ntdll.dll`, exception `c0000005`, offset `000000000001a12d`, even after successful scripts and a zero batch-wrapper native exit. This report does **not** certify crash-free Max operation or identify that shutdown crash's root cause. The startup fix must not be used to filter or reinterpret that event as clean. A debugger/dump investigation of the shutdown failure remains necessary before declaring the installation healthy.

## Authorization and safety

- Issue comment `https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/1089#issuecomment-6815089205` opened the Max window on 2026-11-12: headless/copies only; stop if Artem reopens Max.
- Read-only process inventory found no `3dsmax.exe`/`3dsmaxbatch.exe`; live bridge ping was unreachable. The old live-lock sentinel's PID 193532 was absent. The sentinel was not removed or modified.
- All native work used the existing `dcc_batch.py` session lock, no source scene, a blank document (0 objects), measured metre system units and scale 1.0. No MCP scene call was made.
- A concurrent `staropetrovskiy-maf-shots` batch acquired the lock between probes. Our immediate attempt returned busy/exit 3; the next attempt waited through the wrapper. Its processes and lock were untouched.
- All scene writes in affected tests were disposable synthetic FBX/MAX/PNG under card-specific pytest roots. Neither user scenes nor application installation files were edited. No kill command was used.

## Installed and actually loaded versions

| Component | Observation |
|---|---|
| Max | `2026.3`, file/product version `28.3.0.30732` |
| Embedded Python | `3.11.12` |
| USD package | `C:/ProgramData/Autodesk/ApplicationPlugins/USD for 3ds Max 2026`, manifest `0.13.0.7`, SeriesMin/Max `2026` |
| AGR Tools | `%APPDATA%/Autodesk/ApplicationPlugins/AGR-Tools.bundle`, manifest and startup registration `1.1.0` (not the issue's older 0.7/0.9 candidate) |
| Parent pytest venv | CPython `3.14.7`, PySide6/Shiboken6 `6.12.0` from `uv sync` |
| Bad process | PID 529480 loads worktree `.venv/Lib/site-packages/shiboken6/Shiboken.pyd` and `shiboken6.abi3.dll` |
| Clean process | PID 529296 loads Max's own `Shiboken.cp311-win_amd64.pyd`, `shiboken6.cp311-win_amd64.dll`, and USD's `bin/python/maxUsd/_maxUsd.pyd` |
| Corrected inventory | PID 530568: 414 registered plugin records, 1093 loaded native modules; no inventory error |

The clean inventory includes `usdimport.dli`, `usdexport.dle`, `maxusdobjects.dlo` registration and actual USD DLL/PYD paths. Registration alone is not treated as proof of loading: the `modules` list is the loaded-module authority. No evidence supports blaming AGR Tools 1.1.0, or silently reinstalling an older version.

## Minimal reproduction and differential

All commands ran from this card's worktree. `probe.py` reads version, document, units, plugin registrations and its own native process modules, writes a JSON snapshot, then prints `ISSUE1089_SCRIPT_COMPLETED`. It does not change the scene.

```text
python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 --file tmp/issue-1089-v001/probe.py --card t_d739fdee --wait 0 --timeout 180 --out tmp/issue-1089-v001/batch.json
# status ok; native exit 0; 59.6 s

uv run python C:/Users/artsafro/hermes_kanban/scripts/dcc_batch.py max --version 2026 --file tmp/issue-1089-v001/probe.py --card t_d739fdee --wait 180 --timeout 180 --out tmp/issue-1089-v001/batch-uv.json
# status error; native exit 4294967166; 70.0 s
```

The second run shows QtWidgets/QtCore procedure lookup failures, then:

```text
DLL load failed while importing _maxUsd: The specified module could not be found.
ISSUE1089_SCRIPT_COMPLETED {"pid": 529480, ...}
Task Completed with Error(s) - see above
3ds Max Shutting Down
```

Thus it reaches the job; calling this an `_maxUsd.dll` startup crash conflates import failure and native termination. The actual imported extension is `_maxUsd.pyd`.

A third run used the same uv interpreter and inherited PATH, removing **only** `VIRTUAL_ENV` in the subprocess environment. It returned `status=ok`, native exit 0, 53.4 s; no foreign `.venv` module remained and native `_maxUsd.pyd` loaded. The final helper-driven v002 run independently returned exit 0 in 53.3 s with complete plugin/module inventory.

The original v001 plugin-registration collector attempted an unsupported `pluginDllIsLoaded` method and recorded `plugin_inventory_error`; module collection and the job completion marker still ran. The corrected v002 collector records registrations without that method and independently enumerates loaded modules through `EnumProcessModules`. The archived v001 probe copy includes this instrumentation correction; use v002 for a reproducible complete inventory, not v001 as a byte-exact historical script snapshot.

### Hypotheses and discriminating evidence

1. **Parent virtualenv/Python DLL conflict — confirmed for startup.** The bad native `sys.path` prepends the parent venv and its site-packages; foreign Shiboken is loaded. Removing `VIRTUAL_ENV` alone changes the result while keeping PATH and installed packages unchanged.
2. **USD package/build mismatch — not supported on this host.** The same installed USD package loads successfully with Max 2026.3 under a sanitized child environment.
3. **AGR Tools package regression — not supported for this startup failure.** The same AGR Tools 1.1.0 registers in both paired runs; it was not removed for the passing control.
4. **Missing USD file/global PATH edit needed — not supported.** No DLL was added or path repaired between the paired controls. The failing lookup is a consequence of the foreign Python binding environment, not proof that `_maxUsd.pyd` is absent.

These observations diagnose the available host, not every historical 20261105/06 process. Historical environment snapshots are unavailable.

## Windows crash correlation: do not discard

The event snapshots contain 77 Application Error 1000 records in the initial ten-day query, all naming the same ntdll exception signature. WER 1001 records are retained separately. A module named in an event is not, by itself, the faulty plugin's identity.

Examples tied to our own read-only probe PIDs (host local time, UTC+01):

| PID | Job/batch outcome | Subsequent Application Error 1000 |
|---|---|---|
| 526784 | Initial clean job; `Shutting Down` at 07:27:15; batch exit 0 | 07:27:24.8958921, ntdll/c0000005 |
| 529480 | Contaminated job reaches completion; error/shutdown at 07:35:15 | 07:35:24.2995976, ntdll/c0000005 |
| 529296 | Only VIRTUAL_ENV removed; successful/shutdown at 07:36:36; batch exit 0 | 07:36:44.6009689, ntdll/c0000005 |
| 530568 | Corrected inventory succeeds/shutdown at 07:42:21; batch exit 0 | 07:42:29.4494620, ntdll/c0000005 |

This establishes a post-job shutdown failure in both controls. Disabling USD has not been tested and is not justified as its fix. No crash dump or debugger stack was collected; the ntdll root cause remains unknown.

## Proposed and implemented safe fix

`src/dt_ai/core/max_env.py:max_child_env` now removes parent `VIRTUAL_ENV`, in addition to the existing four Qt settings, using case-insensitive environment-key matching. It returns a copy, preserves PATH and unrelated values, and never writes files or controls processes. Existing review launchers already call this helper. The parametric-parts readback launch now calls it as well.

No change was made to the shared `hermes_kanban/scripts/dcc_batch.py` (read-only scope). Direct invocations of that external script through `uv run` still require a sanitized child environment; the repository helper fixes callers that actually use it, not every external automation route. No generic success downgrade or startup-error suppression was added.

For the separate ntdll shutdown crash, recommend a bounded dump/stack capture on an owned headless blank-scene process, then a process-local plugin-isolation experiment only if the stack implicates a plugin. Any installed-package repair/update/disable requires Artem's explicit authorization. Do not infer a reinstall recommendation from the startup ImportError.

## Verification

- Test-first commit `ec5b9501`: new regressions fail **5/5**, specifically retaining VIRTUAL_ENV or failing to sanitize the parametric caller (no collection errors).
- Affected default selection: **93 passed, 4 deselected** across `test_max_child_env.py`, `test_parametric_parts_measure.py`, `test_review_publish.py`, `test_review_round2.py`.
- Explicit native `-m max` selection: **3 passed, 1 skipped, 71 deselected** in 309.86 s. Synthetic 3-file FBX readback, review selftest MAX/PNG creation and Review_Camera roundtrip all pass. The original catalog test remains skipped because `bench-solidcraft.fbx` and `aerator-solidcraft.fbx` are absent; synthetic cubes are labelled synthetic, not presented as those assets.
- Generated isolation probe exhausts **32/32** unsafe-key subsets, including duplicate case aliases, parent immutability and PATH preservation. Explicit upper/lower/mixed-case VIRTUAL_ENV and fresh-process child tests also pass.
- The issue's original three-test pre-fix selection was **1 failed, 1 passed, 1 skipped**. The failing review test wrote its FBX but rejected the startup ImportError. The existing success-receipt fallback in `max_adapter.py` is not new in this card and was not weakened.
- Full-suite and exact-head CI receipts are published in the PR body after the final commit. The normal suite excludes opt-in Max tests; it cannot replace the native result above. Native output validation and pytest success do not waive the Windows shutdown events.

## Evidence

Raw text/JSON, native module lists, Windows events, RED/GREEN logs and reproduction scripts are sealed at:

`G:/Мой диск/AGR-evidence/1089-max-startup/t_d739fdee-v001/`

`SHA256SUMS.txt` covers the 15 evidence files. The adjacent committed `issue-1089-evidence.json` gives exact file hashes and byte sizes. Raw parent environment dumps are deliberately not published (they can contain credentials). No large binary, dump, render or LFS object is committed.
