# ZIP names: do malformed UTF-8 headers escape before V001 can report?

Card t_aef27b2b, report-only, pilot only. Synthetic stored ZIPs, no scene, no extraction, no DCC. No web source was needed: every claim below was measured by running the probe or read from the named code.

## Summary

- Yes. A ZIP member name that is not valid UTF-8 while general-purpose flag bit 11 (0x800) is set raises `UnicodeDecodeError` out of `zipfile`. It is not a `BadZipFile` or `OSError`, so `twinqa.bundle.read_bundle` does not wrap it into `BundleError`, and `validate()` never reaches its V001 `ZIP` finding.
- All three malformed fixtures (invalid in both headers, central only, local only) ended the same way: `validate()` raised, the CLI printed a traceback to stderr, stdout was empty (0 bytes, not parseable JSON), process exit 1, no report. Exit 1 is the Python uncaught-exception exit; the same exit 1 is returned for an ordinary `passed: false` report, so the exit code alone does not tell them apart.
- Central-only and local-only differ only in where the exception originates: central at `zipfile.ZipFile(path)` open (`_RealGetContents`, `__init__.py:1578`), local at member read (`ZipFile.open`, `__init__.py:1764`). The user-visible outcome of the V001 path is the same: no report. The local-only archive opens fine and `infolist()` lists `a.bin`.
- The same invalid bytes with flag bit 11 off decode as CP437 (`\xa0■.bin`), the archive is read, and V001 reports ordinary composition failures (`foreign files`, `FBX count`), not a ZIP failure.
- The development reader (`dt_ai.publish.bundle.read_bundle`) fails with the same `UnicodeDecodeError` at the same `zipfile` lines, so the two readers agree on these fixtures.
- Input hashes were identical before and after every call.

## Method (verified by running)

Script: `C:/x/t_aef27b2b/probe_zip_name_decoding.py`, SHA-256 `4bc70afa6151f2a5ce0115cf4c1005e8a2ae3e32fbe07f15720272f3647051e8`. Lossless rows: `C:/x/t_aef27b2b/results.json`, SHA-256 `f224911b6293caaa3d7af8f6daf538e8f283ff6db2ef6d4826159ec136641cbe`. Corpus `C:/x/t_aef27b2b/corpus/*.zip`, CLI stdout/stderr captures `C:/x/t_aef27b2b/reports/`. Interpreter: repo `.venv` CPython 3.14.7. Nothing from `C:/x` is committed.

Each ZIP is built with `struct.pack`: one ZIP_STORED member, payload `payload-bytes-0123456789` (24 bytes), CRC, sizes, offsets, EOCD valid. Local and central name bytes and flag word are set independently. The probe re-parses the raw headers (names, flags, offsets, CRC, sizes) before any call; `crc_ok` and header/EOCD arithmetic were true for all 7 fixtures. Invalid name bytes are `ff fe 2e 62 69 6e` (`b"\xff\xfe.bin"`).

Observed per fixture: `zipfile.ZipFile(path)` (open), `read` of the first info, `twinqa.bundle.read_bundle`, `dt_ai.publish.bundle.read_bundle`, `validate(path, "npm", profiles)` in process, and a fresh-process `validate_package.py <zip> --profile npm --json`. The card asks for one CLI run per distinct exception class; I ran the CLI for all 7 fixtures (cheap), which covers both distinct origins.

## Findings

SHA-256 prefixes are of the whole fixture ZIP (full values in `results.json`). "Flag" is the flag word in local/central.

| Fixture | local / central name (hex) | Flag | SHA-256 | zipfile open | zipfile read | twinqa / dev reader | `validate()` | CLI: exit, stdout, stderr |
|---|---|---|---|---|---|---|---|---|
| ascii_flag_off | `612e62696e` / same | 0 / 0 | `29ce9802599f` | ok | payload exact | `a.bin`, payload hash equal | report, `passed` false | exit 1, JSON parses, stderr empty |
| ascii_flag_on | `612e62696e` / same | 0x800 / 0x800 | `8c014585acb5` | ok | payload exact | `a.bin` | report, `passed` false | exit 1, JSON parses, stderr empty |
| valid_utf8_flag_on | `c3a92e62696e` / same (`é.bin`) | 0x800 / 0x800 | `c1922424bb06` | ok | payload exact | `é.bin` | report, `passed` false | exit 1, JSON parses, stderr empty |
| invalid_both_flag_on | `fffe2e62696e` / same | 0x800 / 0x800 | `c75be77cbd8a` | `UnicodeDecodeError` `_RealGetContents` 1578 | not reached | both raise `UnicodeDecodeError` | raises, no report | exit 1, stdout 0 B, stderr 1286 B traceback |
| invalid_central_only_flag_on | `612e62696e` / `fffe2e62696e` | 0x800 / 0x800 | `a114759648ee` | `UnicodeDecodeError` `_RealGetContents` 1578 | not reached | both raise | raises, no report | same as above |
| invalid_local_only_flag_on | `fffe2e62696e` / `612e62696e` | 0x800 / 0x800 | `4aa5dddde974` | ok (`infolist` = `a.bin`) | `UnicodeDecodeError` `ZipFile.open` 1764 | both raise | raises, no report | exit 1, stdout 0 B, stderr 1347 B traceback |
| invalid_both_flag_off_cp437 | `fffe2e62696e` / same | 0 / 0 | `2413e08a551f` | ok (`\xa0■.bin`) | payload exact | `\xa0■.bin` | report, `passed` false | exit 1, JSON parses, stderr empty |

Notes:

- **Controls are ordinary composition failures, not ZIP integrity failures.** For the three readable name controls, the V001 findings are `archive size` pass, `foreign files` fail (`a.bin`, `é.bin`), `FBX count` fail (0). No `ZIP` finding. Both readers returned the identical member (payload hash equal across `zipfile`, twinqa and dev).
- **Exception family and origin** (both malformed-flag-on cases): `UnicodeDecodeError`, MRO `UnicodeDecodeError -> UnicodeError -> ValueError`. Message `'utf-8' codec can't decode byte 0xff in position 0: invalid start byte`. Traceback tail for central cases: `twinqa/bundle.py:17 read_bundle -> zipfile.__init__:1480 __init__ -> :1578 _RealGetContents`; for the local case `bundle.py:33 read_bundle -> zipfile:1690 read -> :1764 open`.
- **Why the V001 handler does not see it** (read from `src/twinqa/bundle.py`): the open is wrapped in `except (zipfile.BadZipFile, OSError)` and the read in `except (zipfile.BadZipFile, OSError, EOFError)`. `UnicodeDecodeError` is neither, so it passes through `validate()`, whose only handler around `read_bundle` is `except BundleError` (`tools/qa/validate_package.py` lines 198-205). `BundleError` is a `ValueError` subclass, but `UnicodeDecodeError` is not a `BundleError`, so the equal base class does not help.
- **Exit 1 is not a V001 report.** CLI exit 1 occurs both for the readable controls (`passed` false, JSON exit_code 1) and for the three malformed fixtures (traceback). The only reliable discriminator measured here is stdout JSON parseability plus stderr content. For the malformed rows there is no `V001` finding of any name and no stdout.
- **Local-only vs central-only.** For `zipfile` they differ: the central error stops at open (nothing can be listed), the local error allows listing and fails only when that member is read. Neither is caught. The asymmetry matters for a reader that lists names before reading (it would see the central name only), not for the two readers under test.
- **Flag off.** The identical invalid bytes with bit 11 clear are decoded by `zipfile` as CP437 and read cleanly. Whether CP437 mojibake should be accepted by V001 is a policy question, not measured here beyond the outcome above (V001 sees the mojibake name `\xa0■.bin` and reports it as `foreign files`).
- Not tested: mixed flags (local on / central off or the reverse), data-descriptor ZIPs, the Unicode Path extra field (0x7075), multiple members, `vpm` profile, other Python versions. No outcome is claimed for them.

## How it applies to this repository

- `src/twinqa/bundle.py` lines 17 and 33 (`read_bundle`): the two `except` tuples are where the decoding failure escapes.
- `tools/qa/validate_package.py` lines 198-205 (`validate`): turns only `BundleError` into the V001 `ZIP` finding.
- `src/dt_ai/publish/bundle.py` `read_bundle`: same escape; no handler there at all.
- Companion reports on other branches: `docs/research/zip-member-error-report-boundary.md` (`RuntimeError` for encrypted, `NotImplementedError` for unsupported method also escape V001) and `docs/research/zip-raw-member-name-boundary.md` (raw-name identity splits). This card adds a third escaping class, `UnicodeDecodeError`, and separates it by origin. I did not read those files on this branch (not merged here); the summary comes from the card text and the #682 report.

## Proposed next tasks

1. **Pin the measured name-decoding escape as a current-behavior fixture.** Scope: one test module building the five fixtures above (valid control, invalid both/central/local with flag on, flag-off CP437 control) with `struct`, asserting today's outcomes: exception family and origin line family from `twinqa.bundle.read_bundle`, `dt_ai.publish.bundle.read_bundle`, and CLI exit 1 with empty stdout. No behavior change; a later fix then flips the assertions deliberately. Distinguishes confirmed report loss (the three flag-on fixtures: measured, no report) from untested behavior (mixed flags, 0x7075 extra field, VPM). Value: medium; effort S. `Advances #149`.
2. **Probe the untested neighbours before any handler policy.** Scope: extend the same script to local/central flag mismatch, Unicode Path extra field, and the `vpm` profile, record outcomes only, no code change. Value: low-medium; effort S. `Archive: no roadmap link`.

## Open questions for the user

- Should a name that fails UTF-8 decoding be a V001 `ZIP` finding (like other unreadable members), or may the CLI keep the traceback? This research does not choose.
- Should flag-off bytes that look like UTF-8 mojibake in CP437 be accepted as a name, or reported separately?
